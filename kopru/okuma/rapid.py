# SPDX-License-Identifier: AGPL-3.0-only
"""Her yerde çalışan yedek OCR (rapidocr_onnxruntime)."""
from __future__ import annotations

import importlib

from typing import Any

from . import Satir


def kullanilabilir() -> bool:
    try:
        importlib.import_module("rapidocr_onnxruntime")
        return True
    except Exception:   # eksik ya da bozuk kurulum (ImportError, DLL/OSError)
        return False


class Okuyucu:
    ad = "RapidOCR"

    def __init__(self) -> None:
        self._motor: Any = None

    def oku(self, resim: Any) -> list[Satir]:
        import numpy as np
        if self._motor is None:
            from rapidocr_onnxruntime import RapidOCR
            self._motor = RapidOCR()
        W, H = resim.size
        sonuc, _ = self._motor(np.asarray(resim.convert("RGB")))
        out: list[Satir] = []
        for kutu, metin, _guven in sonuc or []:
            xs = [p[0] for p in kutu]
            ys = [p[1] for p in kutu]
            if str(metin).strip():
                out.append(Satir(str(metin).strip(), min(xs) / W, min(ys) / H,
                                 (max(xs) - min(xs)) / W, (max(ys) - min(ys)) / H))
        return out
