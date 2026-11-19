# SPDX-License-Identifier: AGPL-3.0-only
"""Windows 10/11 yerleşik OCR (winocr paketi)."""
from __future__ import annotations

import importlib

import sys
from typing import Any

from . import Satir


def kullanilabilir() -> bool:
    if sys.platform != "win32":
        return False
    try:
        importlib.import_module("winocr")
        return True
    except Exception:   # eksik ya da bozuk kurulum (ImportError, DLL/OSError)
        return False


def _al(nesne: Any, ad: str) -> Any:
    return nesne[ad] if isinstance(nesne, dict) else getattr(nesne, ad)


# İngilizce okuma paketi yoksa (ör. Türkçe Windows) kurulu başka bir Latin dille okunur;
# Türkçe okuyucu İngilizce harfleri de okur. Daha iyi sonuç için panel İngilizce paketi kurdurabilir.
TERCIH = ("en-US", "en-GB", "en", "tr-TR", "tr", "de-DE", "fr-FR", "es-ES", "it-IT")
EN_PAKETI_KOMUTU = 'Add-WindowsCapability -Online -Name "Language.OCR~~~en-US~0.0.1.0"'


def kurulu_diller() -> list[str]:
    """Windows'ta kurulu OCR dilleri (ör. ['tr-TR'])."""
    try:
        from winrt.windows.media.ocr import OcrEngine
        return [str(d.language_tag) for d in OcrEngine.available_recognizer_languages]
    except Exception:   # noqa: BLE001
        return []


def dil_sec(kurulu: list[str]) -> str | None:
    kucuk = {d.lower(): d for d in kurulu}
    for t in TERCIH:
        if t.lower() in kucuk:
            return kucuk[t.lower()]
    for d in kurulu:   # tercih listesinde yoksa İngilizce benzeri herhangi bir dil
        if d.lower().startswith("en"):
            return d
    return kurulu[0] if kurulu else None


def ingilizce_var(kurulu: list[str]) -> bool:
    return any(d.lower().startswith("en") for d in kurulu)


class Okuyucu:
    ad = "Windows OCR"

    def __init__(self, dil: str | None = None) -> None:
        self.dil = dil

    def _dil(self) -> str:
        if self.dil is None:
            secilen = dil_sec(kurulu_diller())
            if secilen is None:
                from . import OkumaHatasi
                raise OkumaHatasi("Windows'ta hiç yazı okuma dili kurulu değil.")
            self.dil = secilen
        return self.dil

    def oku(self, resim: Any) -> list[Satir]:
        import winocr
        sonuc = winocr.recognize_pil_sync(resim, self._dil())
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
