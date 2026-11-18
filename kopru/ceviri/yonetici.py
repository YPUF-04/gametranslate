# SPDX-License-Identifier: AGPL-3.0-only
"""Çeviri yöneticisi: hafıza -> önbellek -> motor (bağlamla) -> yedek."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, Callable

from .. import sozluk as sozluk_mod
from ..hafiza import Hafiza, OneriDeposu
from ..onbellek import Onbellek
from .istem import SON_SATIR_ADEDI
from .temel import AgHatasi, Baglam, Ceviri, CeviriMotoru

log = logging.getLogger("kopru.ceviri")
YENIDEN_DENEME_SN = 60.0


class CeviriYoneticisi:
    def __init__(self, birincil: CeviriMotoru, yedek: CeviriMotoru | None,
                 onbellek: Onbellek | None, yayinla: Callable[[str, dict], None] | None = None,
                 oyun: str = "varsayilan", hafiza: Hafiza | None = None,
                 oneriler: OneriDeposu | None = None) -> None:
        self.birincil = birincil
        self.yedek = yedek
        self.onbellek = onbellek
        self.hafiza = hafiza
        self.oneriler = oneriler
        self._yayinla = yayinla or (lambda o, v: None)
        self.oyun = oyun
        self.oyun_bilgisi: dict[str, Any] = {}      # ad, aciklama, hitap, karakterler
        self.yedekte = False
        self._yedek_zamani = 0.0
        self._ucusta: dict[tuple, asyncio.Future] = {}
        self.terimler: dict[str, str] = {}
        self.son_satirlar: deque[tuple[str, str]] = deque(maxlen=SON_SATIR_ADEDI)
        self.gecmis: deque[dict[str, str]] = deque(maxlen=30)   # /api/son-ceviriler (yalnız RAM)

    def _durum(self) -> None:
        motor = self.yedek if self.yedekte and self.yedek else self.birincil
        self._yayinla("durum", {"calisiyor": True, "motor": motor.ad, "yedek": self.yedekte})

    # -- bağlam ve geçmiş --
    def _baglam(self) -> Baglam:
        b = self.oyun_bilgisi
        return Baglam(oyun_ad=b.get("ad", ""), aciklama=b.get("aciklama", ""),
                      hitap=b.get("hitap", "sen"), karakterler=list(b.get("karakterler", [])),
                      son_satirlar=list(self.son_satirlar))

    def satir_kaydet(self, id_: str, asil: str, ceviri: str, kaynak: str = "motor") -> None:
        """Yayınlanan altyazıyı bağlama ve son-çeviriler listesine ekler."""
        self.son_satirlar.append((asil, ceviri))
        self.gecmis.append({"id": id_, "asil": asil, "ceviri": ceviri, "kaynak": kaynak})

    def satir_guncelle(self, id_: str, asil: str, ceviri: str, kaynak: str = "motor") -> None:
        """Aynı cümlenin devamı: son-çeviriler listesinde yeni satır açmadan günceller."""
        for g in reversed(self.gecmis):
            if g["id"] == id_:
                eski = g["asil"]
                g["asil"], g["ceviri"], g["kaynak"] = asil, ceviri, kaynak
                self.son_satirlar = deque(((asil, ceviri) if a == eski else (a, c)
                                           for a, c in self.son_satirlar), maxlen=SON_SATIR_ADEDI)
                return
        self.satir_kaydet(id_, asil, ceviri, kaynak)

    def duzeltildi(self, asil: str, ceviri: str) -> None:
        """Kullanıcı düzeltmesini geçmişe ve bağlam satırlarına yansıtır."""
        from ..onbellek import normallestir
        n = normallestir(asil)
        for g in self.gecmis:
            if normallestir(g["asil"]) == n:
                g["ceviri"], g["kaynak"] = ceviri, "kullanici"
        self.son_satirlar = deque(((a, ceviri if normallestir(a) == n else c)
                                   for a, c in self.son_satirlar), maxlen=SON_SATIR_ADEDI)

    # -- motor çağrısı --
    async def _cagir(self, motor: CeviriMotoru, metinler: list[str], kaynak: str, hedef: str,
                     aciklama: bool, baglam: Baglam) -> list[Ceviri]:
        if getattr(motor, "baglam_destekler", False):
            return await motor.cevir(metinler, kaynak, hedef, self.terimler, aciklama, baglam=baglam)
        return await motor.cevir(metinler, kaynak, hedef, self.terimler, aciklama)

    async def _motorla(self, metinler: list[str], kaynak: str, hedef: str,
                       aciklama: bool) -> tuple[list[Ceviri], str | None]:
        """(sonuç, motor kodu); yedek motor kullanıldıysa kod None (hafızaya yazılmaz)."""
        baglam = self._baglam()
        # yedekteyken belirli aralıkla birincili yeniden dene
        if self.yedekte and self.yedek and time.monotonic() - self._yedek_zamani < YENIDEN_DENEME_SN:
            return await self._cagir(self.yedek, metinler, kaynak, hedef, aciklama, baglam), None
        try:
            sonuc = await self._cagir(self.birincil, metinler, kaynak, hedef, aciklama, baglam)
        except AgHatasi:
            if not self.yedek:
                raise
            log.warning("Birincil motor ulaşılamadı, yedeğe geçildi")
            self.yedekte = True
            self._yedek_zamani = time.monotonic()
            self._durum()
            return await self._cagir(self.yedek, metinler, kaynak, hedef, aciklama, baglam), None
        if self.yedekte:
            self.yedekte = False
            self._durum()
        self._terimleri_isle(baglam.yeni_terimler, metinler)
        return sonuc, getattr(self.birincil, "kod", None)

    def _terimleri_isle(self, terimler: list[dict], metinler: list[str]) -> None:
        """Motorun bulduğu yeni özel isimleri öneri olarak saklar (sözlüğe kendiliğinden girmez)."""
        if not self.oneriler:
            return
        bilinen = {a.casefold() for a in self.terimler}
        govde = " ".join(metinler).casefold()
        for t in terimler[:10]:
            asil, ceviri = str(t.get("asil", "")).strip(), str(t.get("ceviri", "")).strip()
            # kısa, metinde gerçekten geçen ve bilinmeyen terimler
            if 0 < len(asil) <= 60 and 0 < len(ceviri) <= 60 and \
                    asil.casefold() not in bilinen and asil.casefold() in govde:
                self.oneriler.ekle(asil, ceviri)

    # -- arama / çeviri --
    def ara(self, metin: str, kaynak: str, hedef: str, aciklama: bool = False) -> Ceviri | None:
        """Hafıza/önbellekte varsa anında sonuç (motor çağrılmaz)."""
        if self.hafiza and not aciklama:
            vur = self.hafiza.bul(metin)
            if vur:
                return Ceviri(vur[0], None, vur[1])
        if self.onbellek:
            vur = self.onbellek.al(metin, kaynak, hedef, self.oyun, aciklama)
            if vur:
                return Ceviri(vur[0], vur[1])
        return None

    async def cevir(self, metinler: list[str], kaynak: str = "otomatik", hedef: str = "tr",
                    aciklama: bool = False) -> list[Ceviri]:
        sonuc: list[Ceviri | None] = [None] * len(metinler)
        eksik: list[int] = []
        for i, m in enumerate(metinler):
            vur = self.ara(m, kaynak, hedef, aciklama)
            if vur:
                sonuc[i] = vur
            else:
                eksik.append(i)
        if eksik:
            ayri = list(dict.fromkeys(metinler[i] for i in eksik))
            gelen = await self._ucustaki(ayri, kaynak, hedef, aciklama)
            for i in eksik:
                c = gelen[metinler[i]]
                sonuc[i] = c
        return [s for s in sonuc if s is not None]

    async def _ucustaki(self, ayri: list[str], kaynak: str, hedef: str,
                        aciklama: bool) -> dict[str, Ceviri]:
        """Aynı anda aynı metin için tek istek (dedupe)."""
        bekleyen: dict[str, asyncio.Future] = {}
        yeni: list[str] = []
        for m in ayri:
            anahtar = (m, kaynak, hedef, aciklama)
            f = self._ucusta.get(anahtar)
            if f is None:
                f = asyncio.get_running_loop().create_future()
                self._ucusta[anahtar] = f
                yeni.append(m)
            bekleyen[m] = f
        if yeni:
            try:
                ceviriler, motor_kodu = await self._motorla(yeni, kaynak, hedef, aciklama)
                for m, c in zip(yeni, ceviriler):
                    c = Ceviri(sozluk_mod.son_kontrol(m, c.metin, self.terimler), c.aciklama)
                    if self.onbellek and c.metin:
                        self.onbellek.koy(m, kaynak, hedef, self.oyun, c.metin, c.aciklama, aciklama)
                    if self.hafiza and c.metin and not aciklama and motor_kodu:
                        self.hafiza.kaydet(m, c.metin, "motor", motor_kodu)
                    self._ucusta.pop((m, kaynak, hedef, aciklama)).set_result(c)
            except BaseException as e:
                for m in yeni:
                    f = self._ucusta.pop((m, kaynak, hedef, aciklama), None)
                    if f and not f.done():
                        if isinstance(e, asyncio.CancelledError):
                            f.cancel()
                        else:
                            f.set_exception(e)
                            f.exception()  # "never retrieved" uyarısını önle
                raise
        return {m: await f for m, f in bekleyen.items()}
