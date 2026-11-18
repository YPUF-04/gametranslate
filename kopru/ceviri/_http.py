# SPDX-License-Identifier: AGPL-3.0-only
"""REST motorları için ortak yardımcı."""
from __future__ import annotations

from typing import Any

import aiohttp

from .temel import AgHatasi, AnahtarHatasi


async def post_json(url: str, govde: dict[str, Any], basliklar: dict[str, str],
                    zaman_asimi: float = 8.0, oturum: aiohttp.ClientSession | None = None) -> Any:
    kendi = oturum is None
    oturum = oturum or aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=zaman_asimi))
    try:
        async with oturum.post(url, json=govde, headers=basliklar) as r:
            if r.status in (401, 403):
                raise AnahtarHatasi(url)
            if r.status == 429 or r.status >= 500:
                raise AgHatasi(f"HTTP {r.status}")
            if r.status >= 400:
                raise AgHatasi(f"HTTP {r.status}")
            return await r.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError) as e:
        raise AgHatasi(type(e).__name__) from e
    finally:
        if kendi:
            await oturum.close()
