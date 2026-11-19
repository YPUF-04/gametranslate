# SPDX-License-Identifier: AGPL-3.0-only
"""Küçük, bağımlılıksız (yalnız numpy) ses yardımcıları.

Hepsi bellekte çalışır; hiçbiri dosya yazmaz. Burada: sessizlik kırpma, ucuz konuşmacı
parmak izi (MFCC ortalaması), hız değiştirme (WSOLA) ve bellekte WAV üretimi.
"""
from __future__ import annotations

import io
import wave
from typing import Any

import numpy as np


def mono_float(pcm: Any) -> np.ndarray:
    """Her girdiyi tek kanallı float32 diziye çevirir."""
    a = np.asarray(pcm)
    if a.ndim > 1:
        a = a.mean(axis=1) if a.shape[1] <= 8 else a.reshape(-1)
    if a.dtype.kind in "iu":
        a = a.astype(np.float32) / float(np.iinfo(a.dtype).max)
    return np.ascontiguousarray(a, dtype=np.float32)


def yeniden_ornekle(pcm: np.ndarray, sr: int, hedef: int) -> np.ndarray:
    """Doğrusal ara değerleme (konuşma örneği için yeterli; ağır bağımlılık gerekmez)."""
    if sr == hedef or len(pcm) == 0:
        return pcm
    n = max(1, int(round(len(pcm) * hedef / sr)))
    x = np.linspace(0, len(pcm) - 1, n)
    return np.interp(x, np.arange(len(pcm)), pcm).astype(np.float32)


def _enerji(pcm: np.ndarray, sr: int, pencere_sn: float = 0.02) -> np.ndarray:
    n = max(1, int(sr * pencere_sn))
    k = len(pcm) // n
    if k == 0:
        return np.array([float(np.sqrt(np.mean(pcm ** 2))) if len(pcm) else 0.0])
    return np.sqrt(np.mean(pcm[:k * n].reshape(k, n) ** 2, axis=1))


def sessizlik_kirp(pcm: np.ndarray, sr: int, esik_db: float = -35.0, pay_sn: float = 0.05) -> np.ndarray:
    """Baştaki/sondaki sessizliği atar (en gürültülü pencerenin `esik_db` altı sessizdir)."""
    if len(pcm) == 0:
        return pcm
    e = _enerji(pcm, sr)
    zirve = float(e.max())
    if zirve <= 1e-6:
        return pcm[:0]
    sesli = np.where(e >= zirve * (10 ** (esik_db / 20)))[0]
    n = max(1, int(sr * 0.02))
    pay = int(sr * pay_sn)
    bas = max(0, int(sesli[0]) * n - pay)
    son = min(len(pcm), (int(sesli[-1]) + 1) * n + pay)
    return pcm[bas:son]


def en_iyi_pencere(pcm: np.ndarray, sr: int, azami_sn: float) -> np.ndarray:
    """Parça `azami_sn`den uzunsa, en çok sesli (enerjisi en yüksek) kesiti seçer."""
    uz = int(azami_sn * sr)
    if len(pcm) <= uz:
        return pcm
    adim = max(1, int(0.25 * sr))
    kare = pcm.astype(np.float64) ** 2
    toplam = np.concatenate([[0.0], np.cumsum(kare)])
    en_iyi, yer = -1.0, 0
    for b in range(0, len(pcm) - uz + 1, adim):
        e = toplam[b + uz] - toplam[b]
        if e > en_iyi:
            en_iyi, yer = e, b
    return pcm[yer:yer + uz]


# ---------- konuşmacı parmak izi (ağır diarizasyon yok) ----------

_MEL_ONBELLEK: dict[tuple[int, int, int], np.ndarray] = {}


def _mel_banka(sr: int, nfft: int, adet: int = 26) -> np.ndarray:
    anahtar = (sr, nfft, adet)
    if anahtar in _MEL_ONBELLEK:
        return _MEL_ONBELLEK[anahtar]
    mel = lambda f: 2595.0 * np.log10(1.0 + f / 700.0)          # noqa: E731
    mel_ters = lambda m: 700.0 * (10 ** (m / 2595.0) - 1.0)      # noqa: E731
    noktalar = mel_ters(np.linspace(mel(60.0), mel(min(sr / 2, 7600.0)), adet + 2))
    bin_ = np.floor((nfft + 1) * noktalar / sr).astype(int)
    banka = np.zeros((adet, nfft // 2 + 1), dtype=np.float64)
    for i in range(adet):
        a, b, c = bin_[i], bin_[i + 1], bin_[i + 2]
        for k in range(a, b):
            banka[i, k] = (k - a) / max(1, b - a)
        for k in range(b, c):
            banka[i, k] = (c - k) / max(1, c - b)
    _MEL_ONBELLEK[anahtar] = banka
    return banka


def parmak_izi(pcm: np.ndarray, sr: int) -> np.ndarray:
    """Ucuz konuşmacı vektörü: sesli karelerin MFCC (1-12) ortalaması + spektral ağırlık merkezi.

    Kimlik kanıtı değildir; yalnız "bu iki parça benzer tonda mı" sorusuna ucuz bir yanıttır.
    """
    nfft = 512 if sr <= 16000 else 1024
    adim = nfft // 2
    if len(pcm) < nfft:
        pcm = np.pad(pcm, (0, nfft - len(pcm)))
    n = 1 + (len(pcm) - nfft) // adim
    idx = np.arange(nfft)[None, :] + adim * np.arange(n)[:, None]
    kareler = pcm[idx].astype(np.float64) * np.hanning(nfft)
    guc = np.abs(np.fft.rfft(kareler, axis=1)) ** 2
    enerji = guc.sum(axis=1)
    sesli = enerji >= enerji.max() * 0.05          # sessiz kareleri dışarıda bırak
    guc, enerji = guc[sesli], enerji[sesli]
    if len(guc) == 0:
        return np.zeros(13)
    logmel = np.log(guc @ _mel_banka(sr, nfft).T + 1e-10)
    m = logmel.shape[1]
    dct = np.cos(np.pi / m * (np.arange(m) + 0.5)[None, :] * np.arange(1, 13)[:, None])  # c1..c12
    mfcc = logmel @ dct.T
    frekans = np.fft.rfftfreq(nfft, 1.0 / sr)
    merkez = float(np.mean((guc * frekans).sum(axis=1) / np.maximum(enerji, 1e-12)))
    return np.concatenate([mfcc.mean(axis=0), [merkez / 1000.0]])


def benzerlik(a: np.ndarray, b: np.ndarray) -> float:
    """Kosinüs benzerliği (-1..1)."""
    pa, pb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if pa < 1e-9 or pb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (pa * pb))


# ---------- hız değiştirme (perde korunur): WSOLA ----------

def hizlandir(pcm: np.ndarray, sr: int, oran: float) -> np.ndarray:
    """Sesi `oran` kat hızlandırır (oran > 1 kısaltır), perde değişmez.

    `librosa` kuruluysa onu kullanır; değilse aşağıdaki numpy WSOLA'ya düşer.
    """
    if oran <= 1.001 or len(pcm) == 0:
        return pcm
    try:
        import librosa  # tembel: isteğe bağlı, daha iyi kalite
        return np.asarray(librosa.effects.time_stretch(pcm.astype(np.float32), rate=float(oran)),
                          dtype=np.float32)
    except Exception:  # librosa yok ya da başarısız: numpy yoluna dön
        return wsola(pcm, sr, oran)


def wsola(pcm: np.ndarray, sr: int, oran: float) -> np.ndarray:
    """Dalga biçimi benzerliğiyle üst üste bindirme-toplama (Waveform Similarity OLA)."""
    pcm = pcm.astype(np.float32)
    n = int(sr * 0.032) // 2 * 2 or 2              # pencere ~32 ms
    hs = n // 2                                    # çıkış adımı
    ha = hs * oran                                 # giriş adımı
    delta = n // 4                                 # arama aralığı
    cikis_uz = int(len(pcm) / oran) + n
    cikis = np.zeros(cikis_uz + n, dtype=np.float64)
    agirlik = np.zeros_like(cikis)
    pen = np.hanning(n + 1)[:n]
    onceki = 0                                     # bir önceki karenin seçilen giriş konumu
    k = 0
    while True:
        nominal = int(round(k * ha))
        if nominal + n + delta >= len(pcm) or k * hs + n > len(cikis):
            break
        if k == 0:
            yer = 0
        else:
            hedef = pcm[onceki + hs: onceki + hs + n]   # doğal devam
            lo, hi = max(0, nominal - delta), min(len(pcm) - n, nominal + delta)
            aday = np.lib.stride_tricks.sliding_window_view(pcm[lo:hi + n], n)[: hi - lo + 1]
            yer = lo + int(np.argmax(aday @ hedef)) if len(hedef) == n and len(aday) else nominal
        parca = pcm[yer:yer + n]
        cikis[k * hs:k * hs + n] += parca * pen
        agirlik[k * hs:k * hs + n] += pen
        onceki = yer
        k += 1
    agirlik[agirlik < 1e-6] = 1.0
    sonuc = (cikis / agirlik)[:int(len(pcm) / oran)]
    return sonuc.astype(np.float32)


# ---------- WAV (yalnız bellekte) ----------

def wav_bayt(pcm: np.ndarray, sr: int) -> bytes:
    """16-bit mono WAV baytları; diske hiç yazılmaz."""
    a = np.clip(pcm, -1.0, 1.0)
    veri = (a * 32767.0).astype("<i2").tobytes()
    tampon = io.BytesIO()
    with wave.open(tampon, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes(veri)
    return tampon.getvalue()


def pcm16_to_float(veri: bytes) -> np.ndarray:
    return np.frombuffer(veri, dtype="<i2").astype(np.float32) / 32768.0


def sentetik_referans(sr: int = 24000, sure: float = 4.0) -> np.ndarray:
    """"Dene" düğmesi için, oturumda yakalanmış karakter sesi yoksa kullanılan KÜÇÜK sentetik ses.

    Gerçek bir kişinin sesi değildir: harmonik kaynaktan formant süzmesiyle üretilen sesli harf dizisi.
    """
    t = np.arange(int(sr * sure)) / sr
    f0 = 118.0 * (1.0 + 0.012 * np.sin(2 * np.pi * 5.0 * t))        # hafif titreşim
    faz = 2 * np.pi * np.cumsum(f0) / sr
    sesliler = [(730, 1090), (530, 1840), (270, 2290), (570, 840), (300, 870)]   # a e i o u formantları
    seg = np.minimum((t / sure * 10).astype(int), 9) % len(sesliler)
    out = np.zeros_like(t)
    for h in range(1, 40):
        f = h * f0
        agirlik = np.zeros_like(t)
        for k, (f1, f2) in enumerate(sesliler):
            m = seg == k
            agirlik[m] = (np.exp(-0.5 * ((f[m] - f1) / 120.0) ** 2)
                          + 0.6 * np.exp(-0.5 * ((f[m] - f2) / 180.0) ** 2) + 0.03)
        out += agirlik / h ** 0.6 * np.sin(h * faz)
    zarf = 0.55 + 0.45 * np.sin(2 * np.pi * 3.5 * t) ** 2
    out *= zarf
    return (out / np.abs(out).max() * 0.6).astype(np.float32)
