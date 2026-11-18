# SPDX-License-Identifier: AGPL-3.0-only
"""Windows 10/11 yerleşik OCR (winocr paketi)."""
from __future__ import annotations

import sys
from typing import Any

from . import Satir


def kullanilabilir() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winocr  # noqa: F401
        return True
    except ImportError:
        return False


def _al(nesne: Any, ad: str) -> Any:
    return nesne[ad] if isinstance(nesne, dict) else getattr(nesne, ad)


class Okuyucu:
    ad = "Windows OCR"

    def __init__(self, dil: str = "en-US") -> None:
        self.dil = dil

    def oku(self, resim: Any) -> list[Satir]:
        import winocr
        sonuc = winocr.recognize_pil_sync(resim, self.dil)
        W, H = resim.size
        out: list[Satir] = []
        for satir in _al(sonuc, "lines"):
            kutular = [_al(k, "bounding_rect") for k in _al(satir, "words")]
            if not kutular:
                continue
            x1 = min(_al(b, "x") for b in kutular)
            y1 = min(_al(b, "y") for b in kutular)
            x2 = max(_al(b, "x") + _al(b, "width") for b in kutular)
            y2 = max(_al(b, "y") + _al(b, "height") for b in kutular)
            metin = str(_al(satir, "text")).strip()
            if metin:
                out.append(Satir(metin, x1 / W, y1 / H, (x2 - x1) / W, (y2 - y1) / H))
        return out
