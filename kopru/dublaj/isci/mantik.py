# SPDX-License-Identifier: AGPL-3.0-only
"""Dublajın saf hesapları (yalnız numpy): satırlara bölme, konuşmacı gruplama, duygu, süreye
sığdırma kararı, parça parça ayırma planı, karıştırma (ducking + EQ + sınırlayıcı), SRT.

Hiçbiri dosya okumaz/yazmaz ve ağır paket istemez: hem işçide hem testlerde aynen çalışır.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import numpy as np

# ---------- 1) kelimelerden satırlar ----------

CUMLE_SONU = (".", "!", "?", "…")


@dataclass
class Satir:
    bas: float
    son: float
    metin: str
    konusan: int = 0

    @property
    def sure(self) -> float:
        return max(0.0, self.son - self.bas)

    def sozluk(self) -> dict[str, Any]:
        return {"bas": round(self.bas, 3), "son": round(self.son, 3), "metin": self.metin, "konusan": self.konusan}


def satirlara_bol(kelimeler: Sequence[dict[str, Any]], en_cok_sn: float = 8.0, sessizlik_sn: float = 0.6,
                  en_az_sn: float = 0.35) -> list[Satir]:
    """Kelime zaman damgalarını (`{"k","b","s"}`) dublaj satırlarına böler.

    Yeni satır: araya `sessizlik_sn`den uzun sessizlik girerse, satır `en_cok_sn`yi aşacaksa ya da
    önceki kelime cümle sonuysa (ve satır en az ~1,2 sn ise). Çok kısa satırlar (`en_az_sn`) atılır.
    """
    satirlar: list[Satir] = []
    simdi: list[dict[str, Any]] = []

    def kapat() -> None:
        if simdi:
            metin = " ".join(str(k["k"]).strip() for k in simdi).strip()
            s = Satir(float(simdi[0]["b"]), float(simdi[-1]["s"]), " ".join(metin.split()))
            if s.metin and s.sure >= en_az_sn:
                satirlar.append(s)
            simdi.clear()

    for k in kelimeler:
        if not str(k.get("k", "")).strip():
            continue
        if simdi:
            onceki = simdi[-1]
            ara = float(k["b"]) - float(onceki["s"])
            uzunluk = float(k["s"]) - float(simdi[0]["b"])
            cumle = str(onceki["k"]).strip().endswith(CUMLE_SONU) and float(onceki["s"]) - float(simdi[0]["b"]) >= 1.2
            if ara >= sessizlik_sn or uzunluk > en_cok_sn or cumle:
                kapat()
        simdi.append(k)
    kapat()
    return satirlar


# ---------- 2) konuşmacı gruplama ----------

def _birim(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


def kumele(izler: np.ndarray, esik: float = 0.72, en_cok: int = 12) -> list[int]:
    """Ortalama bağlantılı birleştirmeli kümeleme (kosinüs). Etiketler ilk görünüş sırasına göre 0,1,2...

    Benzerliği `esik`ten düşük kümeler birleşmez; `en_cok` kümeyi aşarsa en benzer olanlar zorla birleşir.
    """
    n = len(izler)
    if n == 0:
        return []
    x = _birim(np.asarray(izler, dtype=np.float64))
    kumeler: list[list[int]] = [[i] for i in range(n)]
    merkez = x.copy()
    while len(kumeler) > 1:
        m = _birim(merkez) @ _birim(merkez).T
        np.fill_diagonal(m, -np.inf)
        i, j = np.unravel_index(int(np.argmax(m)), m.shape)
        if m[i, j] < esik and len(kumeler) <= en_cok:
            break
        i, j = min(i, j), max(i, j)
        kumeler[i] += kumeler[j]
        del kumeler[j]
        merkez = np.delete(merkez, j, axis=0)
        merkez[i] = x[kumeler[i]].mean(axis=0)
    etiket = np.zeros(n, dtype=int)
    sira = sorted(range(len(kumeler)), key=lambda c: min(kumeler[c]))
    for yeni, c in enumerate(sira):
        etiket[kumeler[c]] = yeni
    return [int(e) for e in etiket]


def referans_araliklari(satirlar: Sequence[Satir], puanlar: Sequence[float], hedef_sn: float = 8.0,
                        en_cok_sn: float = 10.0) -> dict[int, list[tuple[float, float]]]:
    """Her konuşmacı için klon örneği: en temiz (yüksek puanlı) ve uzun satırlardan 3-10 sn'lik seçki.

    `puanlar[i]`: satırın temizliği (konuşma/arka plan oranı vb., büyük = temiz).
    """
    gruplar: dict[int, list[int]] = {}
    for i, s in enumerate(satirlar):
        gruplar.setdefault(s.konusan, []).append(i)
    sonuc: dict[int, list[tuple[float, float]]] = {}
    for k, idx in gruplar.items():
        sirali = sorted(idx, key=lambda i: (puanlar[i] * min(satirlar[i].sure, 6.0)), reverse=True)
        secilen: list[tuple[float, float]] = []
        toplam = 0.0
        for i in sirali:
            s = satirlar[i]
            sure = min(s.sure, en_cok_sn - toplam)
            if sure < 0.5:
                continue
            secilen.append((s.bas, s.bas + sure))
            toplam += sure
            if toplam >= hedef_sn:
                break
        sonuc[k] = sorted(secilen)
    return sonuc


# ---------- 3) duygu ----------

def rms(pcm: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(pcm, dtype=np.float64)))) if len(pcm) else 0.0


def perde_degiskenligi(pcm: np.ndarray, sr: int) -> float:
    """Kaba perde (f0) izi → yarım ton cinsinden standart sapma (canlı/düz konuşma ayrımı)."""
    pen = int(sr * 0.04)
    adim = int(sr * 0.02)
    if len(pcm) < pen * 2:
        return 0.0
    f0 = []
    en_az, en_cok = int(sr / 400), int(sr / 70)
    for b in range(0, len(pcm) - pen, adim):
        p = pcm[b:b + pen].astype(np.float64)
        p = p - p.mean()
        if rms(p) < 0.01:
            continue
        ac = np.correlate(p, p, mode="full")[pen - 1:]
        if ac[0] <= 0 or en_cok >= len(ac):
            continue
        g = int(np.argmax(ac[en_az:en_cok])) + en_az
        if ac[g] / ac[0] > 0.45:
            f0.append(sr / g)
    if len(f0) < 3:
        return 0.0
    yt = 12 * np.log2(np.asarray(f0) / np.median(f0))
    return float(np.std(yt))


def duygu(pcm: np.ndarray, sr: int, referans_rms: float | None = None) -> dict[str, float]:
    """Orijinal satırın enerjisi ve perde oynaklığından Chatterbox ayarları.

    `canlilik` (exaggeration): fısıltı ~0.3, düz ~0.5, bağırma ~1.0+. `cfg`: canlılık arttıkça biraz
    düşer (motorun önerisi: yüksek exaggeration + düşük cfg = daha doğal tempo).
    """
    r = rms(pcm)
    ref = referans_rms if referans_rms and referans_rms > 1e-6 else max(r, 1e-6)
    gurultu = 20 * np.log10(max(r, 1e-6) / ref)          # dB, konuşmacının ortalamasına göre
    pv = perde_degiskenligi(pcm, sr)
    canlilik = 0.5 + 0.045 * gurultu + 0.06 * (pv - 2.0)
    if r < 0.02:                                          # çok kısık: fısıltı
        canlilik = min(canlilik, 0.35)
    canlilik = float(np.clip(canlilik, 0.25, 1.2))
    cfg = float(np.clip(0.5 - 0.3 * (canlilik - 0.5), 0.3, 0.7))
    return {"canlilik": round(canlilik, 3), "cfg": round(cfg, 3)}


# ---------- 4) süreye sığdırma ----------

def sigdir_karari(tts_sn: float, hedef_sn: float, sinir: float = 1.25, tolerans: float = 1.03,
                  kisaltma_denendi: bool = False) -> tuple[str, float]:
    """("tamam", 1.0) | ("hizlandir", oran) | ("kisalt", oran). Kısaltma bir kez denendiyse sınırda hızlanır."""
    if hedef_sn <= 0:
        return "tamam", 1.0
    oran = tts_sn / hedef_sn
    if oran <= tolerans:
        return "tamam", 1.0
    if oran <= sinir:
        return "hizlandir", oran
    if not kisaltma_denendi:
        return "kisalt", oran
    return "hizlandir", sinir


def yer_ayarla(baslar: Sequence[float], sureler: Sequence[float], toplam_sn: float, bosluk: float = 0.05) -> list[float]:
    """Seslendirilmiş satırlar üst üste binmesin: gerekirse bir sonrakini biraz kaydırır (en çok 0,6 sn)."""
    yeni = []
    onceki_son = -1e9
    for b, s in zip(baslar, sureler):
        bas = max(b, onceki_son + bosluk) if onceki_son - b < 0.6 else b
        bas = min(bas, max(0.0, toplam_sn - s))
        yeni.append(bas)
        onceki_son = bas + s
    return yeni


# ---------- 5) parça parça ayırma planı ----------

def parca_plani(n: int, pencere: int, bindirme: float = 0.25) -> list[tuple[int, int]]:
    """[0,n) aralığını `pencere` boylu, `bindirme` oranında üst üste binen parçalara böler (son parça sona dayanır)."""
    if n <= pencere:
        return [(0, n)]
    adim = max(1, int(pencere * (1 - bindirme)))
    plan = []
    b = 0
    while True:
        if b + pencere >= n:
            plan.append((max(0, n - pencere), n))
            break
        plan.append((b, b + pencere))
        b += adim
    return plan


def bindirmeli_birlestir(parcalar: Iterable[tuple[int, int, np.ndarray]], n: int, kanal: int = 2) -> np.ndarray:
    """Üçgen ağırlıklarla birleştirme (parça kenarlarında yumuşak geçiş). Parça: (bas, son, dizi[kanal, uz])."""
    cikis = np.zeros((kanal, n), dtype=np.float64)
    agirlik = np.zeros(n, dtype=np.float64)
    for b, s, x in parcalar:
        uz = s - b
        w = np.minimum(np.arange(1, uz + 1), np.arange(uz, 0, -1)).astype(np.float64)
        w = np.minimum(w / max(1.0, uz * 0.125), 1.0)
        cikis[:, b:s] += np.asarray(x, dtype=np.float64)[:, :uz] * w
        agirlik[b:s] += w
    return (cikis / np.maximum(agirlik, 1e-9)).astype(np.float32)


# ---------- 6) karıştırma ----------

def _yuksek_gecir(x: np.ndarray, sr: int, fc: float = 80.0) -> np.ndarray:
    """Tek kutuplu yüksek geçiren süzgeç (uğultuyu keser)."""
    if len(x) == 0:
        return x
    a = 1.0 / (1.0 + 2 * np.pi * fc / sr)
    y = np.empty_like(x, dtype=np.float64)
    onceki_x = 0.0
    onceki_y = 0.0
    xs = x.astype(np.float64)
    # vektörleştirilmiş IIR yok; bloklar hâlinde python döngüsü pahalı → scipy varsa onu kullan
    try:
        from scipy.signal import lfilter  # isteğe bağlı
        return lfilter([a, -a], [1, -a], xs).astype(np.float32)
    except Exception:
        for i, v in enumerate(xs):
            onceki_y = a * (onceki_y + v - onceki_x)
            onceki_x = v
            y[i] = onceki_y
        return y.astype(np.float32)


def kisma_zarfi(n: int, araliklar: Sequence[tuple[int, int]], sr: int, kis_db: float = -6.0,
                rampa_sn: float = 0.15) -> np.ndarray:
    """Konuşma aralıklarında arka planı `kis_db` kısan, kenarları rampalı kazanç eğrisi (0-1)."""
    hedef = 10 ** (kis_db / 20)
    z = np.ones(n, dtype=np.float64)
    r = max(1, int(rampa_sn * sr))
    for b, s in araliklar:
        b, s = max(0, b), min(n, s)
        if s <= b:
            continue
        z[b:s] = np.minimum(z[b:s], hedef)
        gir = np.linspace(1.0, hedef, r)
        bb = max(0, b - r)
        z[bb:b] = np.minimum(z[bb:b], gir[r - (b - bb):])
        ss = min(n, s + r)
        z[s:ss] = np.minimum(z[s:ss], gir[::-1][:ss - s])
    return z


def sinirla(x: np.ndarray, tavan: float = 0.97) -> np.ndarray:
    """Tepe sınırlayıcı: tavanı aşan kısımları yumuşak (tanh) bükerek kırpar."""
    a = np.abs(x)
    if a.size == 0 or a.max() <= tavan:
        return x.astype(np.float32)
    esik = tavan * 0.8
    y = np.where(a > esik, np.sign(x) * (esik + (tavan - esik) * np.tanh((a - esik) / (tavan - esik))), x)
    return y.astype(np.float32)


def karistir(arka: np.ndarray, sesler: Sequence[tuple[np.ndarray, int]], sr: int, kis_db: float = -6.0,
             ses_kazanc: float = 1.0) -> np.ndarray:
    """Türkçe sesleri (mono, başlangıç örneği) arka planın (kanal, n) üstüne bindirir.

    Konuşma boyunca arka plan yumuşakça kısılır; seslere 80 Hz yüksek geçiren + sınırlayıcı uygulanır.
    Dönüş: (kanal, n) float32.
    """
    arka = np.atleast_2d(np.asarray(arka, dtype=np.float32))
    kanal, n = arka.shape
    sesyolu = np.zeros(n, dtype=np.float64)
    araliklar = []
    for pcm, bas in sesler:
        pcm = _yuksek_gecir(np.asarray(pcm, dtype=np.float32).reshape(-1), sr)
        bas = max(0, int(bas))
        son = min(n, bas + len(pcm))
        if son <= bas:
            continue
        sesyolu[bas:son] += pcm[:son - bas] * ses_kazanc
        araliklar.append((bas, son))
    zarf = kisma_zarfi(n, araliklar, sr, kis_db)
    cikis = arka.astype(np.float64) * zarf[None, :] + sesyolu[None, :]
    return sinirla(cikis)


# ---------- 7) altyazı dosyası ----------

def _zaman(sn: float) -> str:
    ms = int(round(max(0.0, sn) * 1000))
    s, ms = divmod(ms, 1000)
    d, s = divmod(s, 60)
    sa, d = divmod(d, 60)
    return f"{sa:02d}:{d:02d}:{s:02d},{ms:03d}"


def srt(satirlar: Sequence[tuple[float, float, str]]) -> str:
    parcalar = []
    for i, (b, s, m) in enumerate(satirlar, 1):
        parcalar.append(f"{i}\n{_zaman(b)} --> {_zaman(s)}\n{m.strip()}\n")
    return "\n".join(parcalar)


def temizlik_puani(konusma: np.ndarray, arka: np.ndarray) -> float:
    """Konuşmanın arka plana oranı (dB). Büyük = temiz (klon örneği için iyi)."""
    return float(20 * np.log10(max(rms(konusma), 1e-6) / max(rms(arka), 1e-6)))


# ---------- 8) akışlı seslendirme için bölme ----------

def cumlecik_bol(metin: str, en_az: int = 28, en_cok: int = 90) -> list[str]:
    """Metni seslendirme parçalarına böler: önce cümle sonu, sonra virgül/bağlaç; çok kısa parçalar
    öncekiyle birleşir (motor tek kelimeyi kötü okur). İlk parça kısa tutulur: ilk ses erken çıksın."""
    import re
    kelimeler = metin.split()
    if not kelimeler:
        return []
    parcalar: list[str] = []
    simdi: list[str] = []
    for k in kelimeler:
        simdi.append(k)
        uz = len(" ".join(simdi))
        sinir = en_az if not parcalar else en_az + 12
        if (re.search(r"[.!?…]$", k) and uz >= sinir * 0.6) or (re.search(r"[,;:]$", k) and uz >= sinir) or uz >= en_cok:
            parcalar.append(" ".join(simdi))
            simdi = []
    if simdi:
        kalan = " ".join(simdi)
        if parcalar and len(kalan) < 12:
            parcalar[-1] += " " + kalan
        else:
            parcalar.append(kalan)
    return parcalar


def hiz_tahmini(uretilen_sn: float, uretilen_karakter: int, toplam_karakter: int, hedef_sn: float,
                sinir: float = 1.25) -> float:
    """İlk parçanın hızından tüm metnin süresini tahmin eder → gereken hızlandırma (1..sinir)."""
    if hedef_sn <= 0 or uretilen_karakter <= 0:
        return 1.0
    tahmin = uretilen_sn * toplam_karakter / uretilen_karakter
    return float(min(sinir, max(1.0, tahmin / hedef_sn)))


def hafif_mi(ayar: str, vram_gb: float | None) -> bool:
    """`hafif_mod` ayarı: "otomatik" → ekran kartı belleği ≤ 8,5 GB ya da bilinmiyorsa hafif."""
    if ayar == "acik":
        return True
    if ayar == "kapali":
        return False
    return vram_gb is None or vram_gb <= 8.5


# ---------- 9) canlı: akışlı ayırma ve uyarlamalı konuşma algılama ----------

class AkisAyirici:
    """Gelen kısa blokları geçmişle (sol bağlam) birlikte ayırıcıya verir, YALNIZ yeni kısmı döndürür.

    `ayirici(pcm, sr) -> (konusma, arka)`. Gecikme = blok boyu + ayırma süresi (sağ bağlam yok).
    """

    def __init__(self, ayirici: Any, sr: int, baglam_sn: float = 3.0) -> None:
        self.ayirici = ayirici
        self.sr = sr
        self.baglam = int(baglam_sn * sr)
        self._gecmis = np.zeros(0, dtype=np.float32)

    def besle(self, blok: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        self._gecmis = np.concatenate([self._gecmis, blok.astype(np.float32)])[-self.baglam:]
        k, a = self.ayirici(self._gecmis, self.sr)
        n = len(blok)
        return np.asarray(k, dtype=np.float32)[-n:], np.asarray(a, dtype=np.float32)[-n:]


class UyarlamaliVAD:
    """Enerji tabanlı, gürültü tabanını izleyen konuşma algılayıcı.

    Oyunda diyalog sesi kısıkken (%10-20) sabit eşik konuşmayı kaçırır; burada eşik, konuşma olmayan
    blokların yavaşça izlenen düzeyinin `kat` katıdır (en az `en_az_esik`). Ayrılmış konuşma izinde
    (müzik/efekt çıkarılmış) taban düşük olduğundan kısık konuşma da yakalanır.
    """

    def __init__(self, sr: int, sessizlik_sn: float = 0.5, azami_sn: float = 12.0, en_az_esik: float = 0.0015,
                 kat: float = 3.0) -> None:
        self.sr, self.sessizlik_sn, self.azami_sn = sr, sessizlik_sn, azami_sn
        self.en_az_esik, self.kat = en_az_esik, kat
        self.taban: float | None = None
        self._k: list[np.ndarray] = []
        self._h: list[np.ndarray] = []
        self._sessiz = 0.0
        self._uz = 0.0

    def esik(self) -> float:
        return max(self.en_az_esik, (self.taban or 0.0) * self.kat)

    def besle(self, konusma: np.ndarray, ham: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray] | None:
        ham = konusma if ham is None else ham
        r = rms(konusma)
        sure = len(konusma) / self.sr
        sesli = r > self.esik()
        if not sesli:   # taban yalnız sessiz bloklardan, yavaşça (yukarı yavaş, aşağı hızlı)
            if self.taban is None:
                self.taban = r
            else:
                self.taban = self.taban + (0.02 if r > self.taban else 0.3) * (r - self.taban)
        if sesli:
            self._k.append(konusma)
            self._h.append(ham)
            self._sessiz = 0.0
            self._uz += sure
        elif self._k:
            self._k.append(konusma)
            self._h.append(ham)
            self._sessiz += sure
            self._uz += sure
        if self._k and (self._sessiz >= self.sessizlik_sn or self._uz >= self.azami_sn):
            k, h = np.concatenate(self._k), np.concatenate(self._h)
            self._k, self._h, self._sessiz, self._uz = [], [], 0.0, 0.0
            return k, h
        return None
