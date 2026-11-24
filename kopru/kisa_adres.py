# SPDX-License-Identifier: AGPL-3.0-only
"""PROTOKOL 20.2: kısa adres. Kapı 80'de YALNIZ yönlendiren küçük bir sunucu: TV'nin tarayıcısına
`http://192.168.1.20` yazmak yeter; `/` ve `/tv` asıl kapıdaki `/tv` sayfasına yönlenir. Başka hiçbir şey sunulmaz."""
from __future__ import annotations

import errno
import logging
from typing import Any

from aiohttp import web

log = logging.getLogger("kopru.kisa_adres")
KAPI = 80


def _ad(host: str | None) -> str:
    """Host başlığından kapısız ad ("192.168.1.20:80" -> "192.168.1.20", "[fe80::1]" aynen)."""
    h = (host or "").strip()
    if h.startswith("["):
        return h.split("]", 1)[0] + "]"
    return h.rsplit(":", 1)[0] if h.count(":") == 1 else h


def uygulama(ana_kapi: int) -> web.Application:
    async def yonlendir(request: web.Request) -> web.StreamResponse:
        ad = _ad(request.headers.get("Host")) or request.url.host or "127.0.0.1"
        if not all(c.isalnum() or c in ".-:[]" for c in ad):   # başlık enjeksiyonu / tuhaf ad
            raise web.HTTPBadRequest()
        sorgu = ("?" + request.query_string) if request.query_string else ""
        raise web.HTTPFound(f"http://{ad}:{ana_kapi}/tv{sorgu}")
    app = web.Application()
    app.router.add_get("/", yonlendir)
    app.router.add_get("/tv", yonlendir)
    return app


class KisaAdres:
    def __init__(self) -> None:
        self.runner: web.AppRunner | None = None
        self.durum: dict[str, Any] = {"acik": False, "kapi": KAPI, "hata": "kapali"}

    async def baslat(self, ana_kapi: int, kapi: int = KAPI, host: str = "0.0.0.0") -> dict[str, Any]:
        if ana_kapi == kapi:
            self.durum = {"acik": False, "kapi": kapi, "hata": "kapali"}
            return self.durum
        runner = web.AppRunner(uygulama(ana_kapi), access_log=None)
        await runner.setup()
        try:
            await web.TCPSite(runner, host, kapi).start()
        except OSError as e:
            await runner.cleanup()
            izin = e.errno in (errno.EACCES, errno.EPERM) or getattr(e, "winerror", None) == 10013
            self.durum = {"acik": False, "kapi": kapi, "hata": "izin" if izin else "dolu"}
            log.info("Kısa adres (kapı %d) açılamadı: %s", kapi, e)
            return self.durum
        self.runner = runner
        self.durum = {"acik": True, "kapi": kapi, "hata": None}
        return self.durum

    async def durdur(self) -> None:
        if self.runner is not None:
            await self.runner.cleanup()
            self.runner = None
        self.durum = {"acik": False, "kapi": self.durum.get("kapi", KAPI), "hata": "kapali"}
