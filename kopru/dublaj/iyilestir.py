# SPDX-License-Identifier: AGPL-3.0-only
"""Dublaj hafızası: boşta iyileştirme (PROTOKOL 21.6) — daha iyi çeviri, birkaç aday, nesnel puan, cila.

Puanlar (0–1, yüksek iyi): anlaşılırlık (Türkçe geri yazımın WER'i), konuşmacı benzerliği (ses kodlayıcı kosinüsü),
İngilizce süreye uyum, temizlik (kırpılma / içte uzun sessizlik / uydurma uzunluk), duygu yakınlığı (İngilizce
satırın enerji/perde profilinden çıkan canlılığa yakınlık). Ağır işler (seslendirme, Whisper, ses kodlayıcı) işçide.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import numpy as np

log = logging.getLogger("kopru.dublaj.iyilestir")

AGIRLIK = {"anlasilirlik": 0.35, "benzerlik": 0.25, "sure": 0.15, "temizlik": 0.15, "duygu": 0.10}
HEDEF_LUFS = -18.0
ADAY_SAYISI = 3
BOS_BEKLE_SN = 5.0
IS_YOK_BEKLE_SN = 30.0


# ---------- ölçüler (yalnız numpy) ----------

def _kelimeler(m: str) -> list[str]:
    m = m.replace("I", "ı").replace("İ", "i").casefold()
    return re.findall(r"[0-9a-zçğıöşüâîû]+", m)


def wer(dogru: str, tahmin: str) -> float:
    """Kelime hata oranı (Levenshtein / doğru kelime sayısı), en çok 1."""
    a, b = _kelimeler(dogru), _kelimeler(tahmin)
    if not a:
        return 0.0 if not b else 1.0
    onceki = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        su = [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            su[j] = min(onceki[j] + 1, su[j - 1] + 1, onceki[j - 1] + (x != y))
        onceki = su
    return min(1.0, onceki[-1] / len(a))


def sure_uyumu(tr_sn: float, en_sn: float | None) -> float:
    if not en_sn or en_sn <= 0:
        return 0.7
    oran = tr_sn / en_sn
    if 0.85 <= oran <= 1.15:
        return 1.0
    if oran > 1.15:
        return float(max(0.0, 1 - (oran - 1.15) / 0.45))
    return float(max(0.0, 1 - (0.85 - oran) / 0.35))


def temizlik(pcm: np.ndarray, sr: int, metin: str = "") -> float:
    x = np.asarray(pcm, dtype=np.float32).reshape(-1)
    if len(x) < sr * 0.2:
        return 0.0
    kirp = float(np.mean(np.abs(x) > 0.985))
    pen = int(0.02 * sr)
    n = len(x) // pen
    e = np.sqrt(np.mean(x[:n * pen].reshape(n, pen) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(e / (e.max() + 1e-12))
    ic = db[np.argmax(db > -35): len(db) - np.argmax(db[::-1] > -35)] if (db > -35).any() else db
    sessiz = float(np.mean(ic < -40)) if len(ic) else 1.0
    ceza = 6 * kirp + max(0.0, sessiz - 0.3) * 1.5
    if metin:   # uydurma: harf başına süre makul aralığın dışında (Chatterbox bazen anlamsız uzatır)
        hs = len(x) / sr / max(1, len(metin))
        ceza += max(0.0, hs - 0.16) * 6 + max(0.0, 0.035 - hs) * 10
    return float(np.clip(1 - ceza, 0.0, 1.0))


def duygu_yakinligi(pcm: np.ndarray, sr: int, hedef: dict[str, Any] | None, referans_rms: float | None = None) -> float:
    if not hedef or "canlilik" not in hedef:
        return 0.7
    from .isci.mantik import duygu
    c = duygu(np.asarray(pcm, dtype=np.float32), sr, referans_rms)["canlilik"]
    return float(max(0.0, 1 - abs(c - float(hedef["canlilik"])) / 0.4))


def toplam(p: dict[str, float | None]) -> float:
    t = w = 0.0
    for k, a in AGIRLIK.items():
        v = p.get(k)
        if v is None:
            continue
        t += a * float(v)
        w += a
    return round(t / w, 4) if w else 0.0


# ---------- cila ----------

def _yukseklik_db(x: np.ndarray, sr: int) -> float:
    """Kabaca LUFS: 400 ms bloklar, −70 dB mutlak ve −10 dB göreli kapı (K ağırlığı yaklaşık: 100 Hz altı az sayılır)."""
    blok = int(0.4 * sr)
    adim = max(1, blok // 4)
    if len(x) < blok:
        blok = adim = len(x)
    g = [float(np.mean(x[i:i + blok] ** 2)) for i in range(0, max(1, len(x) - blok + 1), adim)]
    g = np.asarray([v for v in g if v > 1e-7]) if g else np.zeros(0)
    if not len(g):
        return -120.0
    esik = np.mean(g) * 10 ** (-10 / 10)
    g = g[g >= esik]
    return float(10 * np.log10(np.mean(g)) - 0.691)


def cila(pcm: Any, sr: int, hedef_lufs: float = HEDEF_LUFS) -> np.ndarray:
    """80 Hz altı kesme, hafif sibilans bastırma (5–9 kHz −3 dB), ses yüksekliği hedefi, tepe sınırı, yumuşak uçlar."""
    x = np.asarray(pcm, dtype=np.float64).reshape(-1)
    if len(x) == 0:
        return x.astype(np.float32)
    x = x - x.mean()
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    kazanc = np.clip((f - 40) / 40, 0, 1)                         # 40→80 Hz yumuşak kesim
    sib = (f >= 5000) & (f <= 9000)
    if sib.any():
        oran = np.sum(np.abs(X[sib]) ** 2) / max(np.sum(np.abs(X) ** 2), 1e-12)
        if oran > 0.08:                                            # yalnız sibilans belirginse
            kazanc = kazanc * np.where(sib, 10 ** (-3 / 20), 1.0)
    x = np.fft.irfft(X * kazanc, len(x))
    l = _yukseklik_db(x, sr)
    if l > -100:
        x = x * 10 ** ((hedef_lufs - l) / 20)
    tepe = np.max(np.abs(x))
    if tepe > 0.95:
        x = np.tanh(x / tepe * 1.2) / np.tanh(1.2) * 0.95 if tepe > 1.5 else x * (0.95 / tepe)
    gir, cik = int(0.01 * sr), int(0.03 * sr)
    if len(x) > gir + cik:
        x[:gir] *= np.linspace(0, 1, gir)
        x[-cik:] *= np.linspace(1, 0, cik)
    return x.astype(np.float32)


# ---------- iş ----------

class Kesildi(Exception):
    """Canlı dublaj ya da video başladı: iyileştirme hemen bırakılır (satır sonra yeniden denenir)."""


@dataclass
class Aday:
    pcm: np.ndarray
    sr: int
    ayar: dict[str, Any]
    puanlar: dict[str, float | None] = field(default_factory=dict)
    puan: float = 0.0
    geri: str = ""


def aday_ayarlari(duygu: dict[str, Any] | None, n: int = ADAY_SAYISI) -> list[dict[str, Any]]:
    c = float((duygu or {}).get("canlilik", 0.5))
    cfg = float((duygu or {}).get("cfg", 0.3))
    liste = [{"tohum": 11, "canlilik": c, "cfg": cfg},
             {"tohum": 23, "canlilik": min(0.9, c + 0.1), "cfg": max(0.2, cfg - 0.05), "sicaklik": 0.75},
             {"tohum": 37, "canlilik": max(0.3, c - 0.1), "cfg": min(0.45, cfg + 0.1), "sicaklik": 0.7},
             {"tohum": 41, "canlilik": c, "cfg": cfg, "sicaklik": 0.6}]
    return [{k: round(v, 3) if isinstance(v, float) else v for k, v in d.items()} for d in liste[:n]]


class Iyilestirici:
    """Boşta (canlı dublaj ve video yok, işçi boş) hafızadaki satırları sırayla iyileştirir."""

    def __init__(self, depo: Any, kodlayici: Any, motor_getir: Callable[[], Any],
                 olc: Callable[[np.ndarray, int, Any, int], Awaitable[tuple[str, float | None]]],
                 cevir: Callable[[str, str, str | None], Awaitable[str | None]] | None,
                 referans: Callable[[str | None], tuple[np.ndarray, int] | None],
                 bos_mu: Callable[[], bool], aday_sayisi: int = ADAY_SAYISI,
                 uyku: Callable[[float], Awaitable[Any]] = asyncio.sleep) -> None:
        self.depo, self.kodlayici, self.motor_getir = depo, kodlayici, motor_getir
        self.olc, self.cevir, self.referans, self.bos_mu = olc, cevir, referans, bos_mu
        self.aday_sayisi = aday_sayisi
        self.uyku = uyku
        self.durum = "bosta"
        self.son: dict[str, Any] | None = None
        self.biten = 0
        self._gorev: asyncio.Task | None = None

    def bilgi(self) -> dict[str, Any]:
        try:
            kalan = len(self.depo.iyilestirilecekler(500))
        except Exception:   # noqa: BLE001
            kalan = None
        return {"durum": self.durum, "kalan": kalan, "biten": self.biten, "son": self.son}

    def baslat(self) -> None:
        if self._gorev is None or self._gorev.done():
            self._gorev = asyncio.get_running_loop().create_task(self.calis())

    def durdur(self) -> None:
        if self._gorev is not None:
            self._gorev.cancel()
            self._gorev = None
        self.durum = "bosta"

    def calisiyor(self) -> bool:
        return self._gorev is not None and not self._gorev.done()

    async def calis(self) -> None:
        try:
            while True:
                if not self.bos_mu() or self.motor_getir() is None:
                    self.durum = "bekliyor"
                    await self.uyku(BOS_BEKLE_SN)
                    continue
                isler = await asyncio.to_thread(self.depo.iyilestirilecekler, 1)
                if not isler:
                    self.durum = "bitti"
                    await self.uyku(IS_YOK_BEKLE_SN)
                    continue
                self.durum = "calisiyor"
                s = isler[0]
                try:
                    self.son = await self.satir(s)
                    self.biten += 1
                except Kesildi:
                    continue
                except asyncio.CancelledError:
                    raise
                except Exception as e:   # noqa: BLE001 — bir satır bozuksa sıradakine geç
                    log.info("satır iyileştirilemedi (%s): %s", s.get("id"), e)
                    self.son = {"id": s.get("id"), "hata": type(e).__name__}
                await asyncio.to_thread(self.depo.iyilestirildi, s["id"])
        except asyncio.CancelledError:
            self.durum = "bosta"
            raise

    async def satir(self, s: dict[str, Any], zorla: bool = False) -> dict[str, Any]:
        """Tek satır: (gerekirse) daha iyi çeviri → adaylar → puan → en iyisi cilalanıp (eskiden iyiyse) yazılır."""
        motor = self.motor_getir()
        if motor is None:
            raise RuntimeError("motor yok")
        tr, kaynak = s["tr"], s.get("tr_kaynak") or "canli"
        if self.cevir is not None and kaynak not in ("kullanici", "en_iyi"):
            yeni = await self.cevir(s["asil"], tr, s.get("konusan"))
            if yeni and yeni.strip() and yeni.strip() != tr:
                tr, kaynak = yeni.strip(), "en_iyi"
        ref = self.referans(s.get("konusan"))
        ref_pcm, ref_sr = ref if ref is not None else (np.zeros(0, np.float32), 24000)
        varsayilan = None if ref is not None or s.get("cinsiyet") not in ("k", "e") else s["cinsiyet"]
        adaylar: list[Aday] = []
        for ayar in aday_ayarlari(s.get("duygu"), self.aday_sayisi):
            if not zorla and not self.bos_mu():
                raise Kesildi()
            ek: dict[str, Any] = {}
            if varsayilan and getattr(motor, "yerlesik_ses", False):
                ek["varsayilan"] = varsayilan
            if getattr(motor, "duygu_destekli", False):
                pcm, sr = await motor.seslendir(tr, ref_pcm, ref_sr, duygu=ayar, **ek)
            else:
                pcm, sr = await motor.seslendir(tr, ref_pcm, ref_sr, **ek)
            pcm = np.asarray(pcm, dtype=np.float32).reshape(-1)
            a = Aday(pcm, int(sr), ayar)
            geri, benzer = await self.olc(pcm, int(sr), ref_pcm if len(ref_pcm) else None, ref_sr)
            a.geri = geri
            a.puanlar = {"anlasilirlik": round(1 - wer(tr, geri), 3),
                         "benzerlik": None if benzer is None else round(float(np.clip((benzer - 0.5) / 0.4, 0, 1)), 3),
                         "sure": round(sure_uyumu(len(pcm) / sr, s.get("en_sure_sn")), 3),
                         "temizlik": round(temizlik(pcm, int(sr), tr), 3),
                         "duygu": round(duygu_yakinligi(pcm, int(sr), s.get("duygu")), 3)}
            a.puan = toplam(a.puanlar)
            adaylar.append(a)
        en = max(adaylar, key=lambda a: a.puan)
        eski = s.get("puan")
        yazildi = False
        if zorla or eski is None or en.puan > eski or kaynak != s.get("tr_kaynak"):
            temiz = cila(en.pcm, en.sr)
            veri, bicim, ssr = await self.kodlayici.kodla(temiz, en.sr)
            await asyncio.to_thread(self.depo.kaydet, s["asil"], s.get("konusan"), tr, kaynak, veri, bicim, ssr,
                                    len(temiz) / en.sr, None, s.get("cinsiyet"), s.get("konusan") or varsayilan,
                                    {**en.ayar, "iyilestirme": True, "zaman": int(time.time())},
                                    {**en.puanlar, "geri": en.geri[:200]}, en.puan, None, None, True)
            yazildi = True
        return {"id": s["id"], "puan": en.puan, "eski_puan": eski, "aday": len(adaylar), "yazildi": yazildi,
                "tr": tr, "puanlar": en.puanlar, "tum": [a.puan for a in adaylar]}
