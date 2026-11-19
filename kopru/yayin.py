# SPDX-License-Identifier: AGPL-3.0-only
"""Olay yayını: SSE istemcilerine olay dağıtır, son durumu hatırlar."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any


class Yayin:
    def __init__(self) -> None:
        self._aboneler: set[asyncio.Queue[tuple[str, dict[str, Any]]]] = set()
        self.son_gorunum: dict[str, Any] | None = None
        self.son_yazi: dict[str, Any] | None = None
        self._yazi_bitis = 0.0
        self.son_ekran: dict[str, Any] | None = None
        self.son_durum: dict[str, Any] | None = None
        self._dinleyiciler: list[Any] = []   # (olay, veri) çağrılan yerel dinleyiciler (ör. dublaj)

    @property
    def istemci_sayisi(self) -> int:
        return len(self._aboneler)

    def abone_ol(self) -> asyncio.Queue[tuple[str, dict[str, Any]]]:
        q: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue(maxsize=200)
        self._aboneler.add(q)
        return q

    def ayril(self, q: asyncio.Queue) -> None:
        self._aboneler.discard(q)

    def dinle(self, cb: Any) -> None:
        """Yayınlanan her olayı `cb(olay, veri)` ile de ver (SSE istemcisi olmadan)."""
        if cb not in self._dinleyiciler:
            self._dinleyiciler.append(cb)

    def dinlemeyi_birak(self, cb: Any) -> None:
        if cb in self._dinleyiciler:
            self._dinleyiciler.remove(cb)

    def yayinla(self, olay: str, veri: dict[str, Any] | None = None) -> None:
        veri = veri if veri is not None else {}
        for cb in list(self._dinleyiciler):
            try:
                cb(olay, veri)
            except Exception:   # dinleyici hatası yayını bozmasın
                pass
        if olay == "gorunum":
            self.son_gorunum = veri
        elif olay == "yazi":
            self.son_yazi = veri
            self._yazi_bitis = time.monotonic() + veri.get("sure_ms", 0) / 1000
        elif olay == "yazi-sil":
            self.son_yazi = None
        elif olay == "ekran":
            self.son_ekran = veri
        elif olay == "ekran-sil":
            self.son_ekran = None
        elif olay == "durum":
            self.son_durum = veri
        for q in list(self._aboneler):
            try:
                q.put_nowait((olay, veri))
            except asyncio.QueueFull:  # yavaş istemci: eskiyi at
                try:
                    q.get_nowait()
                    q.put_nowait((olay, veri))
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass

    def kalan_ms(self) -> int:
        """Ekrandaki yazının kalan süresi (yazı yoksa 0)."""
        if self.son_yazi is None:
            return 0
        return max(0, int((self._yazi_bitis - time.monotonic()) * 1000))

    def acilis_olaylari(self) -> list[tuple[str, dict[str, Any]]]:
        """Yeni bağlanan istemciye gönderilecek son durum."""
        out: list[tuple[str, dict[str, Any]]] = []
        if self.son_gorunum is not None:
            out.append(("gorunum", self.son_gorunum))
        if self.son_durum is not None:
            out.append(("durum", self.son_durum))
        if self.son_yazi is not None and time.monotonic() < self._yazi_bitis:
            kalan = int((self._yazi_bitis - time.monotonic()) * 1000)
            out.append(("yazi", {**self.son_yazi, "sure_ms": max(kalan, 500)}))
        if self.son_ekran is not None:
            out.append(("ekran", self.son_ekran))
        return out


def sse_bicim(olay: str, veri: dict[str, Any]) -> bytes:
    return f"event: {olay}\ndata: {json.dumps(veri, ensure_ascii=False)}\n\n".encode()
