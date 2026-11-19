# SPDX-License-Identifier: AGPL-3.0-only
"""OCR soyutlaması: normalize kutulu satırlar döndürür."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Protocol


class OkumaHatasi(Exception):
    """Metin okuma motoru yok/çalışmıyor; mesaj Türkçe."""


@dataclass
class Satir:
    metin: str
    x: float   # sol üst, 0-1
    y: float
    g: float   # genişlik
    y2: float  # yükseklik
    satir: int = 1   # birleştirilmiş öğede kaç okuma satırından oluştuğu (yazı boyu hesabı için)


class Okuyucu(Protocol):
    ad: str

    def oku(self, resim: Any) -> list[Satir]: ...


def sec(tercih: str | None = None) -> Okuyucu:
    """Bu bilgisayarda kullanılabilen en iyi okuyucuyu seçer."""
    from . import mac, rapid, windows
    sira = {"windows": windows, "mac": mac, "rapid": rapid}
    adaylar = [sira[tercih]] if tercih in sira else []
    if sys.platform == "win32":
        adaylar += [windows, rapid]
    elif sys.platform == "darwin":
        adaylar += [mac, rapid]
    else:
        adaylar += [rapid]
    for m in adaylar:
        if m.kullanilabilir():
            return m.Okuyucu()
    raise OkumaHatasi("Ekrandaki yazıyı okuyacak bileşen kurulu değil. "
                      "Kurulum: pip install \"altyazikoprusu[ocr]\"")
