# SPDX-License-Identifier: AGPL-3.0-only
"""REST motorları için ortak yardımcı."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .temel import AgHatasi, AnahtarHatasi, ModelBulunamadi, MotorHatasi


_ORTAK: dict[int, tuple[Any, aiohttp.ClientSession]] = {}


def ortak_oturum() -> aiohttp.ClientSession:
    """PROTOKOL §16.4: aynı olay döngüsünde tek oturum; bağlantı (TLS el sıkışması) istekler arasında açık
    kalır (keep-alive), her altyazı satırı yeni bağlantı kurmaz."""
    dongu = asyncio.get_running_loop()
    k = _ORTAK.get(id(dongu))
    if k is None or k[0] is not dongu or k[1].closed:
        o = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit_per_host=8, keepalive_timeout=75))
        _ORTAK[id(dongu)] = (dongu, o)
        for anahtar in [a for a, (d, _) in _ORTAK.items() if d.is_closed()]:
            _ORTAK.pop(anahtar, None)
        return o
    return k[1]


async def ortak_kapat() -> None:
    """Sunucu kapanırken (aynı döngüde) ortak oturumu kapatır."""
    try:
        k = _ORTAK.pop(id(asyncio.get_running_loop()), None)
    except RuntimeError:
        return
    if k is not None and not k[1].closed:
        await k[1].close()


async def post_json(url: str, govde: dict[str, Any], basliklar: dict[str, str],
                    zaman_asimi: float = 8.0, oturum: aiohttp.ClientSession | None = None) -> Any:
    oturum = oturum or ortak_oturum()
    try:
        async with oturum.post(url, json=govde, headers=basliklar,
                               timeout=aiohttp.ClientTimeout(total=zaman_asimi)) as r:
            if r.status in (401, 403):
                raise AnahtarHatasi(url)
            if r.status == 400:
                # Gemini geçersiz anahtara 400 + API_KEY_INVALID döner
                govde = (await r.text(errors="replace"))[:2000].lower()
                if "api_key_invalid" in govde or "api key not valid" in govde:
                    raise AnahtarHatasi(url)
                raise AgHatasi("HTTP 400")
            if r.status == 404:
                raise ModelBulunamadi("HTTP 404")
            if r.status == 429 or r.status >= 500:
                raise AgHatasi(f"HTTP {r.status}")
            if r.status >= 400:
                raise AgHatasi(f"HTTP {r.status}")
            return await r.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, asyncio.TimeoutError) as e:
        raise AgHatasi(type(e).__name__) from e
    except ValueError as e:   # gövde JSON değil (proxy/captive portal HTML'i vb.)
        raise MotorHatasi("Sunucu yanıtı okunamadı") from e
