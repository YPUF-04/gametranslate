# SPDX-License-Identifier: AGPL-3.0-only
"""Oyun sesinden sahne tanıma (PROTOKOL 21.4): tepe çifti (landmark) parmak izi ve akışlı eşleme.

Yalnız numpy. İşçi sürecine de kopyalanır (canlı yakalama her 250 ms bloğu buradan geçirir). Mikrofon YOK:
yalnız zaten dinlenen oyun sesi. Parmak izi ses düzeyinden bağımsızdır (tepeler çerçeve içinde göreli seçilir).

- `AkisIz`: akan sesi (16 kHz) parmak izine çevirir; her blokta yalnız kesinleşen izleri verir, son ~30 sn'yi
  geçmişte tutar (bir konuşma parçasının 1 sn ön paylı izini çıkarmak için).
- `iz_cikar`: bütün bir ses için aynı izler (kayıt/video için; akışla birebir aynı yol).
- `Dizin` + `Tanici`: kayıtlı satırların izleri; akan seste hizalı oy sayımıyla eşleşme.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

GIRIS_SR = 16000
SR = 8000
NFFT = 512
HOP = 128                       # 16 ms
KARE_SN = HOP / SR
F_ALT, F_UST = 8, 243           # 125–3800 Hz (8 kHz / 512 → 15,6 Hz kutu)
R_F, R_T = 8, 3                 # yerel tepe komşuluğu (kutu, kare)
CERCEVE_TEPE = 3
ESIK_DB = 10.0                  # çerçeve ortancasının üstü
MUTLAK_TABAN_DB = -75.0         # sessizlikte tepe yok
DT_EN_AZ, DT_EN_COK = 1, 16
DF_EN_COK = 64
YELPAZE = 5                     # bir tepe en çok kaç hedefle eşleşir
ON_PAY_SN = 1.0                 # parçanın başından önceki ses de izlenir (satır başlamadan tanınsın)
PENCERE_SN = 2.0
GECMIS_SN = 30.0
# eşleme
OY_PENCERE_SN = 3.0
ESLESME_EN_AZ = 9               # hizalı puan (satır içi oy 1, ön pay oyu 0,5)
SATIR_ICI_EN_AZ = 3             # satırın kendi sesinden en az bu kadar hizalı oy...
ON_PAY_GUCLU = 16               # ...ya da ön payın kendisi çok güçlü eşleşiyorsa (sabit zamanlı ara sahne: satırdan önce)
HIZA_ORAN = 0.35
DF_SINIR = 6                    # bu kadar satırdan fazlasında geçen özet yok sayılır (müzik döngüsü)
SATIR_ICI_TEKRAR = 4
CEKIRDEK = None


def _alcak_geciren(n: int = 31) -> np.ndarray:
    m = np.arange(n) - (n - 1) / 2
    h = np.sinc(m * 0.9 / 2) * np.hamming(n)      # kesim ~3,6 kHz (16 kHz'de)
    return (h / h.sum()).astype(np.float32)


_H = _alcak_geciren()
_PENCERE = np.hanning(NFFT).astype(np.float32)


def ozet(f1: int, f2: int, dt: int) -> int:
    return (int(f1) << 14) | (int(f2) << 6) | int(dt)


def _kayan_max(a: np.ndarray, r: int, eksen: int) -> np.ndarray:
    pad = [(0, 0), (0, 0)]
    pad[eksen] = (r, r)
    p = np.pad(a, pad, mode="constant", constant_values=-np.inf)
    v = np.lib.stride_tricks.sliding_window_view(p, 2 * r + 1, axis=eksen)
    return v.max(axis=-1)


def _spektrum(x8: np.ndarray) -> np.ndarray:
    n = 1 + (len(x8) - NFFT) // HOP
    if n <= 0:
        return np.zeros((0, NFFT // 2 + 1), np.float32)
    kare = np.lib.stride_tricks.as_strided(x8, shape=(n, NFFT), strides=(x8.strides[0] * HOP, x8.strides[0]))
    S = np.abs(np.fft.rfft(kare * _PENCERE, axis=1)).astype(np.float32)
    return 20 * np.log10(S + 1e-7)


def tepeler(S: np.ndarray) -> list[tuple[int, int]]:
    """(kare, kutu) yerel tepeleri; çerçeve başına en güçlü CERCEVE_TEPE tane."""
    if len(S) == 0:
        return []
    B = S[:, F_ALT:F_UST + 1]
    m = _kayan_max(_kayan_max(B, R_F, 1), R_T, 0)
    ortanca = np.median(B, axis=1, keepdims=True)
    aday = (B >= m) & (B > ortanca + ESIK_DB) & (B > MUTLAK_TABAN_DB)
    sonuc = []
    for t in np.nonzero(aday.any(axis=1))[0]:
        f = np.nonzero(aday[t])[0]
        if len(f) > CERCEVE_TEPE:
            f = f[np.argsort(B[t, f])[::-1][:CERCEVE_TEPE]]
        for fi in sorted(f.tolist()):
            sonuc.append((int(t), int(fi + F_ALT)))
    return sonuc


class AkisIz:
    """16 kHz akan ses → kesinleşmiş (kare, özet) izleri. Kare numaraları akışın başından (16 ms)."""

    def __init__(self, gecmis_sn: float = GECMIS_SN) -> None:
        self._buf = np.zeros(0, np.float32)     # son PENCERE_SN (16 kHz)
        self._buf0 = 0                          # tamponun ilk örneğinin akıştaki yeri (16 kHz)
        self.toplam = 0                         # akıştaki toplam örnek (16 kHz)
        self._bitti_kare = -1                   # bu kareye kadar tepeler işlendi
        self._acik: dict[tuple[int, int], int] = {}   # hedef bekleyen çapalar -> verilen çift sayısı
        self.gecmis: deque[tuple[int, int]] = deque(maxlen=int(gecmis_sn / KARE_SN * CERCEVE_TEPE * YELPAZE))

    def simdiki_kare(self) -> float:
        return self.toplam / 2 / HOP

    def besle(self, blok: Any, son: bool = False) -> list[tuple[int, int]]:
        x = np.asarray(blok, dtype=np.float32).reshape(-1)
        self._buf = np.concatenate([self._buf, x])
        self.toplam += len(x)
        azami = int(PENCERE_SN * GIRIS_SR)
        if len(self._buf) > azami:
            at = len(self._buf) - azami
            at -= at % (2 * HOP)                 # kare ızgarası kaymasın
            self._buf = self._buf[at:]
            self._buf0 += at
        if len(self._buf) < 2 * NFFT:
            return []
        # 8 kHz'e indir (çift örnekler akış başına göre hizalı)
        suz = np.convolve(self._buf, _H, mode="same")
        x8 = np.ascontiguousarray(suz[(self._buf0 % 2)::2])
        bas8 = (self._buf0 + (self._buf0 % 2)) // 2
        ilk_kare = -(-bas8 // HOP)               # tamponda tam başlayan ilk kare
        x8 = x8[ilk_kare * HOP - bas8:]
        S = _spektrum(x8)
        if len(S) == 0:
            return []
        son_kare = ilk_kare + len(S) - 1
        tp = [(t + ilk_kare, f) for t, f in tepeler(S)]
        # Tepe kesin: komşuluğu tamamen tamponda. Çiftler hedef tepe kesinleşir kesinleşmez verilir (çapa beklemez):
        # sıralı işlendiği için toplu hesapla birebir aynı çiftler çıkar, gecikme yalnız R_T kare.
        kesin_tepe = son_kare - (0 if son else R_T)
        alt = max(self._bitti_kare + 1, ilk_kare + R_T)
        cikti: list[tuple[int, int]] = []
        for t2, f2 in tp:
            if t2 < alt or t2 > kesin_tepe:
                continue
            for cap in list(self._acik):
                t1, f1 = cap
                dt = t2 - t1
                if dt > DT_EN_COK:
                    del self._acik[cap]
                    continue
                if dt < DT_EN_AZ or abs(f2 - f1) > DF_EN_COK:
                    continue
                cikti.append((t1, ozet(f1, f2, dt)))
                self._acik[cap] += 1
                if self._acik[cap] >= YELPAZE:
                    del self._acik[cap]
            self._acik[(t2, f2)] = 0
        if kesin_tepe >= alt:
            self._bitti_kare = kesin_tepe
        self.gecmis.extend(cikti)
        return cikti

    def aralik(self, bas_kare: float, bitis_kare: float, on_pay_sn: float = ON_PAY_SN) -> list[list[int]]:
        """Geçmişten [bas - ön pay, bitis] aralığındaki izler, `bas`a göre kare: [[özet, kare], ...]."""
        alt = bas_kare - on_pay_sn / KARE_SN
        b = int(round(bas_kare))
        return [[h, t - b] for t, h in self.gecmis if alt <= t <= bitis_kare]


def iz_cikar(pcm: Any, sr: int = GIRIS_SR, bas_sn: float = 0.0, bitis_sn: float | None = None,
             on_pay_sn: float = ON_PAY_SN) -> list[list[int]]:
    """Bütün bir sesten, [bas_sn - ön pay, bitis_sn] aralığının izleri (kare `bas_sn`ye göre). Akışla aynı yol."""
    x = np.asarray(pcm, dtype=np.float32).reshape(-1)
    if sr != GIRIS_SR and len(x):
        n = max(1, int(round(len(x) * GIRIS_SR / sr)))
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    ilk = max(0, int((bas_sn - on_pay_sn - 0.6) * GIRIS_SR))
    ilk -= ilk % (2 * HOP)
    son = len(x) if bitis_sn is None else min(len(x), int((bitis_sn + 0.6) * GIRIS_SR))
    a = AkisIz(gecmis_sn=max(GECMIS_SN, (son - ilk) / GIRIS_SR + 5))
    a.toplam = a._buf0 = ilk
    blok = GIRIS_SR // 4
    for i in range(ilk, son, blok):
        a.besle(x[i:min(son, i + blok)])
    a.besle(np.zeros(int(0.1 * GIRIS_SR), np.float32), son=True)
    bitis = (bitis_sn if bitis_sn is not None else len(x) / GIRIS_SR) / KARE_SN
    return a.aralik(bas_sn / KARE_SN, bitis, on_pay_sn)


def iz_bayt(iz: Iterable[Iterable[int]]) -> bytes:
    return np.asarray(list(iz) or np.zeros((0, 2)), dtype="<i4").reshape(-1, 2).tobytes()


def bayt_iz(veri: bytes | None) -> list[list[int]]:
    if not veri:
        return []
    return np.frombuffer(veri, dtype="<i4").reshape(-1, 2).tolist()


@dataclass
class Eslesme:
    kimlik: int
    ofset_sn: float          # satırın başına göre şu an (negatif: satır daha başlamadı)
    puan: int                # hizalı oy
    oran: float              # hizalı / o kimliğin tüm oyları

    def sozluk(self) -> dict[str, Any]:
        return {"kimlik": self.kimlik, "ofset_sn": round(self.ofset_sn, 3), "puan": self.puan,
                "oran": round(self.oran, 3)}


class Dizin:
    def __init__(self) -> None:
        self._girdiler: dict[int, list[tuple[int, int]]] = {}
        self._ilan: dict[int, list[tuple[int, int]]] = {}
        self._df: dict[int, int] = {}

    def __len__(self) -> int:
        return len(self._girdiler)

    def ekle(self, kimlik: int, iz: Iterable[Iterable[int]]) -> None:
        self.sil(kimlik)
        sayac: dict[int, int] = {}
        liste = []
        for h, t in iz:
            h, t = int(h), int(t)
            sayac[h] = sayac.get(h, 0) + 1
            liste.append((h, t))
        liste = [(h, t) for h, t in liste if sayac[h] <= SATIR_ICI_TEKRAR]
        if not liste:
            return
        self._girdiler[kimlik] = liste
        for h in {h for h, _ in liste}:
            self._df[h] = self._df.get(h, 0) + 1
        for h, t in liste:
            self._ilan.setdefault(h, []).append((kimlik, t))

    def sil(self, kimlik: int) -> None:
        eski = self._girdiler.pop(kimlik, None)
        if not eski:
            return
        for h in {h for h, _ in eski}:
            self._df[h] -= 1
            if self._df[h] <= 0:
                del self._df[h]
            kalan = [p for p in self._ilan.get(h, []) if p[0] != kimlik]
            if kalan:
                self._ilan[h] = kalan
            else:
                self._ilan.pop(h, None)

    def temizle(self) -> None:
        self._girdiler.clear()
        self._ilan.clear()
        self._df.clear()

    def ara(self, h: int) -> list[tuple[int, int]]:
        if self._df.get(h, 0) > DF_SINIR:
            return []
        return self._ilan.get(h, [])


class Tanici:
    """Akan oyun sesinde kayıtlı satırları tanır. `besle(blok)` → yeni eşleşmeler."""

    def __init__(self, dizin: Dizin | None = None) -> None:
        self.dizin = dizin or Dizin()
        self.akis = AkisIz()
        self._oylar: deque[tuple[int, int, int, int]] = deque()     # (sorgu karesi, kimlik, hiza, satır içi mi)
        self._sayim: dict[int, dict[int, list[int]]] = {}            # kimlik -> hiza -> [satır içi, ön pay]
        self._yayinlanan: dict[int, int] = {}

    def sifirla(self) -> None:
        self._oylar.clear()
        self._sayim.clear()
        self._yayinlanan.clear()

    def besle(self, blok: Any) -> list[Eslesme]:
        yeni = self.akis.besle(blok)
        if not len(self.dizin):
            return []
        dokunulan: set[tuple[int, int]] = set()
        for g, h in yeni:
            for k, t in self.dizin.ara(h):
                hiza = g - t
                ic = 1 if t >= 0 else 0
                self._oylar.append((g, k, hiza, ic))
                s = self._sayim.setdefault(k, {}).setdefault(hiza, [0, 0])
                s[0 if ic else 1] += 1
                dokunulan.add((k, hiza))
        simdi = self.akis.simdiki_kare()
        alt = simdi - OY_PENCERE_SN / KARE_SN
        while self._oylar and self._oylar[0][0] < alt:
            _, k, hz, ic = self._oylar.popleft()
            s = self._sayim[k]
            s[hz][0 if ic else 1] -= 1
            if sum(s[hz]) <= 0:
                del s[hz]
                if not s:
                    del self._sayim[k]
        sonuc: list[Eslesme] = []
        for k in sorted({k for k, _ in dokunulan}):
            s = self._sayim.get(k)
            if not s:
                continue
            toplam = sum(a + b for a, b in s.values())
            en, en_ic, en_hiza, en_ham = 0.0, 0, 0, 0
            for hz in {hz for kk, hz in dokunulan if kk == k}:
                ic = on = 0
                for d in (-1, 0, 1):
                    v = s.get(hz + d)
                    if v:
                        ic += v[0]
                        on += v[1]
                puan = ic + 0.5 * on
                if puan > en:
                    en, en_ic, en_hiza, en_ham = puan, ic, hz, ic + on
            oran = en_ham / toplam if toplam else 0.0
            if en >= ESLESME_EN_AZ and (en_ic >= SATIR_ICI_EN_AZ or en_ham - en_ic >= ON_PAY_GUCLU) and oran >= HIZA_ORAN:
                onceki = self._yayinlanan.get(k)
                if onceki is not None and abs(onceki - en_hiza) <= 3:
                    continue
                self._yayinlanan[k] = en_hiza
                sonuc.append(Eslesme(k, (simdi - en_hiza) * KARE_SN, int(round(en)), oran))
        return sonuc


# ---------- sınama için sentetik sesler (yalnız numpy) ----------

def sentetik_konusma(tohum: int, sure_sn: float = 2.5, sr: int = GIRIS_SR) -> np.ndarray:
    """Konuşmaya benzer: hece hece değişen perde ve formantlar, araya kısa duraklar."""
    r = np.random.default_rng(tohum)
    parcalar = []
    t_top = 0.0
    f0_taban = r.uniform(95, 230)
    while t_top < sure_sn:
        d = r.uniform(0.11, 0.28)
        n = int(d * sr)
        t = np.arange(n) / sr
        f0 = f0_taban * (1 + 0.15 * np.sin(2 * np.pi * r.uniform(1, 4) * t + r.uniform(0, 6))) * r.uniform(0.85, 1.2)
        faz = 2 * np.pi * np.cumsum(f0) / sr
        formant = r.choice([(700, 1200, 2600), (300, 2300, 3000), (500, 900, 2400), (400, 1900, 2550),
                            (600, 1700, 2500), (350, 800, 2300)])
        x = np.zeros(n)
        for k in range(1, 30):
            fk = f0 * k
            g = sum(np.exp(-((fk - F) / 110.0) ** 2) * (1.0 / (1 + i)) for i, F in enumerate(formant))
            x += (g + 0.01) * np.sin(k * faz) / k ** 0.3
        zarf = np.sin(np.pi * np.arange(n) / n) ** 0.6
        parcalar.append(x * zarf)
        t_top += d
        if r.random() < 0.25:
            bos = r.uniform(0.04, 0.15)
            parcalar.append(np.zeros(int(bos * sr)))
            t_top += bos
    y = np.concatenate(parcalar)[:int(sure_sn * sr)]
    return (0.3 * y / (np.abs(y).max() + 1e-9)).astype(np.float32)


def sentetik_muzik(tohum: int, sure_sn: float, sr: int = GIRIS_SR) -> np.ndarray:
    """Akor + bas + davul benzeri gürültü (arka plan müziği)."""
    r = np.random.default_rng(tohum)
    n = int(sure_sn * sr)
    t = np.arange(n) / sr
    y = np.zeros(n)
    akor_sn = 1.0
    for i in range(int(np.ceil(sure_sn / akor_sn))):
        a, b = int(i * akor_sn * sr), min(n, int((i + 1) * akor_sn * sr))
        kok = 110 * 2 ** (r.integers(0, 12) / 12)
        for oran in (1, 1.26, 1.5, 2):
            y[a:b] += 0.2 * np.sin(2 * np.pi * kok * oran * t[a:b])
    vurus = np.zeros(n)
    for i in range(0, n, sr // 2):
        m = min(n - i, int(0.05 * sr))
        vurus[i:i + m] = r.standard_normal(m) * np.exp(-np.arange(m) / (0.01 * sr))
    y += 0.5 * vurus
    return (0.3 * y / (np.abs(y).max() + 1e-9)).astype(np.float32)
