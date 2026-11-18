# SPDX-License-Identifier: AGPL-3.0-only
"""Ana boru hattı: kare al -> değişim? -> OCR -> kararlılaştır -> çevir -> yayınla."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from .ceviri.temel import AgHatasi, AnahtarHatasi, MotorHatasi
from .onbellek import normallestir
from .okuma import Satir

log = logging.getLogger("kopru.isleme")

ARALIK_SN = 0.25
SILME_GECIKME_SN = 0.6
DEGISIM_ESIGI = 3.0  # küçültülmüş gri karelerde ortalama mutlak fark (0-255)
_KONUSAN = re.compile(r"^([A-ZÇĞİÖŞÜ][\w'. -]{0,24}):\s+(\S.*)$", re.UNICODE)


def sure_ms(metin: str) -> int:
    return max(1500, min(9000, 800 + len(metin) * 55))


def parmak_izi(resim: Any) -> bytes:
    """Hızlı değişim algısı için 32x18 gri küçük kare."""
    return resim.convert("L").resize((32, 18)).tobytes()


def fark(a: bytes, b: bytes) -> float:
    if len(a) != len(b):
        return 255.0
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def bolgede_mi(s: Satir, b: dict[str, float]) -> bool:
    cx, cy = s.x + s.g / 2, s.y + s.y2 / 2
    return b["x"] <= cx <= b["x"] + b["g"] and b["y"] <= cy <= b["y"] + b["y2"]


def birlestir(satirlar: list[Satir]) -> list[Satir]:
    """Yakın satırları (alt alta, aynı hizada) tek öğede toplar."""
    sirali = sorted(satirlar, key=lambda s: (s.y, s.x))
    gruplar: list[list[Satir]] = []
    for s in sirali:
        for g in gruplar:
            son = g[-1]
            if 0 <= s.y - (son.y + son.y2) < son.y2 * 0.8 and abs(s.x - son.x) < 0.05 \
                    and abs(s.y2 - son.y2) < son.y2 * 0.5:
                g.append(s)
                break
        else:
            gruplar.append([s])
    out: list[Satir] = []
    for g in gruplar:
        x1 = min(s.x for s in g)
        y1 = min(s.y for s in g)
        x2 = max(s.x + s.g for s in g)
        y2 = max(s.y + s.y2 for s in g)
        out.append(Satir(" ".join(s.metin for s in g), x1, y1, x2 - x1, y2 - y1))
    return out


def tur_bul(o: Satir) -> str:
    n = len(o.metin)
    if o.x < 0.4 and o.y < 0.25 and n >= 25:
        return "gorev"
    if abs((o.x + o.g / 2) - 0.5) < 0.2 and n <= 24:
        return "menu"
    if n >= 40:
        return "bilgi"
    if n <= 24:
        return "menu"
    return "diger"


@dataclass
class _Alan:
    """Bir yazı alanının kararlılaştırma durumu."""
    onceki: str = ""            # önceki karedeki aday
    gosterilen: str = ""        # şu an yayında olan (normalize) kaynak
    bos_since: float | None = None
    bitis: float = 0.0          # TV'nin yazıyı kaldıracağı an


class Isleme:
    def __init__(self, kare_kaynagi: Callable[[], Any], okuyucu: Any, yonetici: Any,
                 yayin: Any, ayar_getir: Callable[[], dict[str, Any]],
                 saat: Callable[[], float] = time.monotonic) -> None:
        self.kare_kaynagi = kare_kaynagi
        self.okuyucu = okuyucu
        self.yonetici = yonetici
        self.yayin = yayin
        self.ayar = ayar_getir
        self.saat = saat
        self._izi: bytes | None = None
        self._son_satirlar: list[Satir] = []
        self._yazi = _Alan()
        self._ekran = _Alan()
        self._sayac = {"a": 0, "e": 0}
        self._yazi_id = ""
        self._yazi_asil = ""
        self._yazi_metin = ""
        self._yazi_konusan: str | None = None
        self._yazi_tur = "altyazi"
        self.durum_hatasi: str | None = None

    # -- yardımcılar --
    def _yeni_id(self, on: str) -> str:
        self._sayac[on] += 1
        return f"{on}{self._sayac[on]}"

    def _hata(self, e: Exception) -> None:
        kod = {AnahtarHatasi: "anahtar", AgHatasi: "ag", MotorHatasi: "motor"}.get(type(e), "genel")
        if kod != self.durum_hatasi:
            self.durum_hatasi = kod
            log.warning("Çeviri hatası: %s", type(e).__name__)
            self.yayin.yayinla("durum", {"calisiyor": True, "motor": self.yonetici.birincil.ad,
                                         "yedek": bool(self.yonetici.yedekte), "hata": kod})

    # -- bir adım --
    async def adim(self) -> None:
        resim = await asyncio.to_thread(self.kare_kaynagi)
        izi = parmak_izi(resim)
        if self._izi is None or fark(izi, self._izi) > DEGISIM_ESIGI:
            self._son_satirlar = await asyncio.to_thread(self.okuyucu.oku, resim)
        self._izi = izi  # değişmediyse son OCR sonucu yeniden kullanılır
        ayar = self.ayar()
        bolge = ayar["bolge_altyazi"]
        altyazi = [s for s in self._son_satirlar if bolgede_mi(s, bolge)]
        diger = [s for s in self._son_satirlar if not bolgede_mi(s, bolge)]
        await self._altyazi_adimi(altyazi, ayar)
        if ayar.get("ekrani_cevir"):
            await self._ekran_adimi(diger, ayar)
        elif self._ekran.gosterilen:
            self._ekran = _Alan()
            self.yayin.yayinla("ekran-sil", {})

    async def _altyazi_adimi(self, satirlar: list[Satir], ayar: dict[str, Any]) -> None:
        a, simdi = self._yazi, self.saat()
        sirali = sorted(satirlar, key=lambda s: (round(s.y, 2), s.x))
        metin = " ".join(s.metin for s in sirali).strip()
        aday = normallestir(metin)
        if aday:
            a.bos_since = None
            if aday == a.onceki and aday != a.gosterilen:
                await self._altyazi_yayinla(metin, aday, ayar, simdi)
            elif aday == a.gosterilen and simdi > a.bitis - 0.8:
                # kaynak hâlâ ekranda: yazıyı canlı tut
                a.bitis = simdi + 2.0
                self.yayin.yayinla("yazi", {
                    "id": self._yazi_id, "metin": self._yazi_metin, "asil": self._yazi_asil,
                    "tur": self._yazi_tur, "konusan": self._yazi_konusan, "sure_ms": 2000})
        elif a.gosterilen:
            if a.bos_since is None:
                a.bos_since = simdi
            elif simdi - a.bos_since >= SILME_GECIKME_SN:
                a.gosterilen = ""
                self.yayin.yayinla("yazi-sil", {})
        a.onceki = aday

    async def _altyazi_yayinla(self, metin: str, aday: str, ayar: dict[str, Any], simdi: float) -> None:
        konusan = None
        m = _KONUSAN.match(metin)
        if m:
            konusan, metin = m.group(1), m.group(2)
        try:
            (c,) = await self.yonetici.cevir([metin], ayar["kaynak_dil"], ayar["hedef_dil"])
        except (AgHatasi, AnahtarHatasi, MotorHatasi) as e:
            self._hata(e)
            return
        self.durum_hatasi = None
        s = sure_ms(c.metin)
        self._yazi_id = self._yeni_id("a")
        self._yazi_asil, self._yazi_metin, self._yazi_konusan = metin, c.metin, konusan
        self._yazi_tur = "altyazi"
        self._yazi.gosterilen = aday
        self._yazi.bitis = simdi + s / 1000
        self.yayin.yayinla("yazi", {"id": self._yazi_id, "metin": c.metin, "asil": metin,
                                    "tur": "altyazi", "konusan": konusan, "sure_ms": s})

    async def _ekran_adimi(self, satirlar: list[Satir], ayar: dict[str, Any]) -> None:
        a, simdi = self._ekran, self.saat()
        ogeler = birlestir([s for s in satirlar if len(s.metin.strip()) >= 2])
        imza = "|".join(normallestir(o.metin) for o in ogeler)
        if imza:
            a.bos_since = None
            if imza == a.onceki and imza != a.gosterilen:
                await self._ekran_yayinla(ogeler, imza, ayar)
        elif a.gosterilen:
            if a.bos_since is None:
                a.bos_since = simdi
            elif simdi - a.bos_since >= SILME_GECIKME_SN:
                a.gosterilen = ""
                self.yayin.yayinla("ekran-sil", {})
        a.onceki = imza

    async def _ekran_yayinla(self, ogeler: list[Satir], imza: str, ayar: dict[str, Any]) -> None:
        turler = [tur_bul(o) for o in ogeler]
        acik = bool(ayar.get("kisa_aciklama"))
        # açıklama yalnız görev/bilgi öğeleri için istenir
        acikli = [i for i, t in enumerate(turler) if acik and t in ("gorev", "bilgi")]
        duz = [i for i in range(len(ogeler)) if i not in acikli]
        sonuc: dict[int, Any] = {}
        try:
            for idx, ac in ((duz, False), (acikli, True)):
                if idx:
                    gelen = await self.yonetici.cevir([ogeler[i].metin for i in idx],
                                                      ayar["kaynak_dil"], ayar["hedef_dil"], ac)
                    sonuc.update(zip(idx, gelen))
        except (AgHatasi, AnahtarHatasi, MotorHatasi) as e:
            self._hata(e)
            return
        liste = []
        for i, o in enumerate(ogeler):
            c = sonuc[i]
            oge = {"x": round(o.x, 4), "y": round(o.y, 4), "g": round(o.g, 4),
                   "y2": round(o.y2, 4), "metin": c.metin, "tur": turler[i]}
            if c.aciklama:
                oge["aciklama"] = c.aciklama[:60]
            liste.append(oge)
        self._ekran.gosterilen = imza
        self.yayin.yayinla("ekran", {"id": self._yeni_id("e"), "ogeler": liste})

    # -- döngü --
    async def calis(self) -> None:
        while True:
            t0 = time.monotonic()
            try:
                await self.adim()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Boru hattı adımı başarısız")
                await asyncio.sleep(1.0)
            await asyncio.sleep(max(0.0, ARALIK_SN - (time.monotonic() - t0)))
