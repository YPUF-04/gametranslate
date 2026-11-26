# SPDX-License-Identifier: AGPL-3.0-only
"""Canlı dublajın dublaj hafızası bağlantısı (PROTOKOL 21.3–21.5).

Isleyici bu nesneyi yalnız `hafiza_izni:true` iken alır. Diskteki depo (`hafiza.DublajHafizasi`) iş
parçacığında çağrılır (olay döngüsü takılmasın); sesler belleğe çözülür ve küçük bir önbellekte tutulur.
"""
from __future__ import annotations

import asyncio
import io
import logging
import wave
from collections import OrderedDict, deque
from typing import Any, Awaitable, Callable

import numpy as np

from .hafiza import DublajHafizasi

log = logging.getLogger("kopru.dublaj.hafiza")

ONBELLEK = 48            # belleğe çözülmüş ses sayısı


def wav_kodla(pcm: Any, sr: int) -> tuple[bytes, str, int]:
    from . import dsp
    return dsp.wav_bayt(dsp.mono_float(pcm), int(sr)), "wav", int(sr)


def wav_coz(veri: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(veri), "rb") as w:
        sr = w.getframerate()
        n = w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768
    if n > 1:
        x = x.reshape(-1, n).mean(1)
    return x, sr


class WavKodlayici:
    async def kodla(self, pcm: Any, sr: int) -> tuple[bytes, str, int]:
        return wav_kodla(pcm, sr)

    async def coz(self, veri: bytes, bicim: str, sr: int) -> tuple[np.ndarray, int]:
        return wav_coz(veri)


class HafizaOturumu:
    def __init__(self, depo: DublajHafizasi, kodlayici: Any = None,
                 tanima_ekle: Callable[[int, list[list[int]]], Awaitable[None]] | None = None,
                 sinir_mb: Callable[[], float] = lambda: 1000.0,
                 tanima_sil: Callable[[list[int]], Awaitable[None]] | None = None) -> None:
        self.depo = depo
        self.kodlayici = kodlayici or WavKodlayici()
        self.tanima_ekle = tanima_ekle
        self.tanima_sil = tanima_sil
        self.sinir_mb = sinir_mb
        self._ses: OrderedDict[int, tuple[np.ndarray, int]] = OrderedDict()
        self.isabet_ms: deque[int] = deque(maxlen=50)
        self.iskalama_ms: deque[int] = deque(maxlen=50)
        self.sayac = {"isabet": 0, "tanima": 0, "iskalama": 0, "kayit": 0}

    async def bul(self, asil: str, konusan: str | None) -> dict[str, Any] | None:
        return await asyncio.to_thread(self.depo.bul, asil, konusan)

    async def getir(self, kimlik: int) -> dict[str, Any] | None:
        return await asyncio.to_thread(self.depo.getir, kimlik)

    def bellekte(self, kimlik: int) -> bool:
        return kimlik in self._ses

    async def ses(self, kimlik: int, kullan: bool = True) -> tuple[np.ndarray, int] | None:
        if kimlik in self._ses:
            self._ses.move_to_end(kimlik)
            if kullan:
                await asyncio.to_thread(self.depo.kullanildi, kimlik)
            return self._ses[kimlik]
        r = await asyncio.to_thread(self.depo.ses_al, kimlik, kullan)
        if r is None:
            return None
        veri, bicim, sr = r
        pcm, psr = await self.kodlayici.coz(veri, bicim, sr)
        self._ses[kimlik] = (np.asarray(pcm, dtype=np.float32), int(psr))
        while len(self._ses) > ONBELLEK:
            self._ses.popitem(last=False)
        return self._ses[kimlik]

    async def kaydet(self, asil: str, konusan: str | None, tr: str, pcm: Any = None, sr: int = 0,
                     **ek: Any) -> int:
        ses = bicim = None
        ssr = None
        if pcm is not None and len(pcm):
            ses, bicim, ssr = await self.kodlayici.kodla(pcm, sr)
        kimlik = await asyncio.to_thread(self.depo.kaydet, asil, konusan, tr, ek.pop("tr_kaynak", "canli"), ses, bicim,
                                         ssr, (len(pcm) / sr) if ses else None, **ek)
        self._ses.pop(kimlik, None)
        self.sayac["kayit"] += 1
        silinen = await asyncio.to_thread(self.depo.sinirla, float(self.sinir_mb()))
        for k in silinen:
            self._ses.pop(k, None)
        if silinen and self.tanima_sil is not None:
            await self._guvenli(self.tanima_sil(silinen))
        if ses is not None and self.tanima_ekle is not None and kimlik not in silinen:
            iz = await asyncio.to_thread(self.depo.iz_al, kimlik)
            if iz:
                await self._guvenli(self.tanima_ekle(kimlik, iz))
        return kimlik

    async def iz_ekle(self, kimlik: int, iz: list[list[int]], en_sure_sn: float | None,
                      duygu: dict[str, Any] | None = None) -> bool:
        tamam = await asyncio.to_thread(self.depo.iz_ekle, kimlik, iz, en_sure_sn, duygu)
        if tamam and self.tanima_ekle is not None:
            s = await self.getir(kimlik)
            if s and s.get("sesli"):
                await self._guvenli(self.tanima_ekle(kimlik, iz))
        return tamam

    async def gecis(self, onceki: int, sonraki: int, dt: float | None) -> None:
        await asyncio.to_thread(self.depo.gecis_ekle, onceki, sonraki, dt)

    async def sonrakiler(self, kimlik: int, adet: int = 3) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self.depo.sonrakiler, kimlik, adet)

    async def tum_izler(self) -> list[tuple[int, list[list[int]]]]:
        return await asyncio.to_thread(self.depo.tum_izler)

    def unut(self, kimlik: int | None = None) -> None:
        if kimlik is None:
            self._ses.clear()
        else:
            self._ses.pop(kimlik, None)

    @staticmethod
    async def _guvenli(c: Awaitable[Any]) -> None:
        try:
            await c
        except Exception as e:   # noqa: BLE001 — tanıma dizini güncellenemezse hafıza yine çalışır
            log.debug("tanıma dizini güncellenemedi: %s", e)

    def olcum(self) -> dict[str, Any]:
        def ort(d: deque[int]) -> int | None:
            return int(sum(d) / len(d)) if d else None
        return {"hafiza_isabet_ms": ort(self.isabet_ms), "hafiza_iskalama_ms": ort(self.iskalama_ms), **self.sayac}
