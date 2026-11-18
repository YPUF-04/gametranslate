# SPDX-License-Identifier: AGPL-3.0-only
"""macOS Apple Vision OCR (ocrmac paketi)."""
from __future__ import annotations

import sys
from typing import Any

from . import Satir


def kullanilabilir() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        import ocrmac  # noqa: F401
        return True
    except ImportError:
        return False


class Okuyucu:
    ad = "Apple Vision"

    def oku(self, resim: Any) -> list[Satir]:
        from ocrmac import ocrmac
        out: list[Satir] = []
        for metin, _guven, (x, y, g, h) in ocrmac.OCR(resim, recognition_level="fast").recognize():
            if metin.strip():  # Vision'da başlangıç sol alttır
                out.append(Satir(metin.strip(), x, 1 - (y + h), g, h))
        return out
