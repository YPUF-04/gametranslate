# SPDX-License-Identifier: AGPL-3.0-only
"""Çeviri yöneticisi: önbellek -> sözlük -> motor -> yedek."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable

from .. import sozluk as sozluk_mod
from ..onbellek import Onbellek
from .temel import AgHatasi, Ceviri, CeviriMotoru

log = logging.getLogger("kopru.ceviri")
YENIDEN_DENEME_SN = 60.0


class CeviriYoneticisi:
    def __init__(self, birincil: CeviriMotoru, yedek: CeviriMotoru | None,
                 onbellek: Onbellek | None, yayinla: Callable[[str, dict], None] | None = None,
                 oyun: str = "varsayilan") -> None:
        self.birincil = birincil
        self.yedek = yedek
        self.onbellek = onbellek
        self._yayinla = yayinla or (lambda o, v: None)
        self.oyun = oyun
        self.yedekte = False
        self._yedek_zamani = 0.0
        self._ucusta: dict[tuple, asyncio.Future] = {}
        self.terimler: dict[str, str] = {}

    def _durum(self) -> None:
        motor = self.yedek if self.yedekte and self.yedek else self.birincil
        self._yayinla("durum", {"calisiyor": True, "motor": motor.ad, "yedek": self.yedekte})

    async def _motorla(self, metinler: list[str], kaynak: str, hedef: str, aciklama: bool) -> list[Ceviri]:
        # yedekteyken belirli aralıkla birincili yeniden dene
        if self.yedekte and self.yedek and time.monotonic() - self._yedek_zamani < YENIDEN_DENEME_SN:
            return await self.yedek.cevir(metinler, kaynak, hedef, self.terimler, aciklama)
        try:
            sonuc = await self.birincil.cevir(metinler, kaynak, hedef, self.terimler, aciklama)
        except AgHatasi:
            if not self.yedek:
                raise
            log.warning("Birincil motor ulaşılamadı, yedeğe geçildi")
            self.yedekte = True
            self._yedek_zamani = time.monotonic()
            self._durum()
            return await self.yedek.cevir(metinler, kaynak, hedef, self.terimler, aciklama)
        if self.yedekte:
            self.yedekte = False
            self._durum()
        return sonuc

    async def cevir(self, metinler: list[str], kaynak: str = "otomatik", hedef: str = "tr",
                    aciklama: bool = False) -> list[Ceviri]:
        sonuc: list[Ceviri | None] = [None] * len(metinler)
        eksik: list[int] = []
        for i, m in enumerate(metinler):
            vur = self.onbellek.al(m, kaynak, hedef, self.oyun, aciklama) if self.onbellek else None
            if vur:
                sonuc[i] = Ceviri(vur[0], vur[1])
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
                ceviriler = await self._motorla(yeni, kaynak, hedef, aciklama)
                for m, c in zip(yeni, ceviriler):
                    c = Ceviri(sozluk_mod.son_kontrol(m, c.metin, self.terimler), c.aciklama)
                    if self.onbellek and c.metin:
                        self.onbellek.koy(m, kaynak, hedef, self.oyun, c.metin, c.aciklama, aciklama)
                    self._ucusta.pop((m, kaynak, hedef, aciklama)).set_result(c)
            except BaseException as e:
                for m in yeni:
                    f = self._ucusta.pop((m, kaynak, hedef, aciklama), None)
                    if f and not f.done():
                        f.set_exception(e)
                        f.exception()  # "never retrieved" uyarısını önle
                raise
        return {m: await f for m, f in bekleyen.items()}
