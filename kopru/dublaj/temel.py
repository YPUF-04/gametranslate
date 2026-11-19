# SPDX-License-Identifier: AGPL-3.0-only
"""Ses motoru arayüzü ve ortak hata (PROTOKOL 9.2)."""
from __future__ import annotations

from typing import Any, Callable, Protocol


class DublajHatasi(Exception):
    """Dublaj kullanılamıyor. `kod` metinler.py'deki bir mesajı gösterir; `ayrinti` ham sebeptir."""

    def __init__(self, kod: str, ayrinti: str = "") -> None:
        super().__init__(kod)
        self.kod = kod
        self.ayrinti = ayrinti


# ilerleme_cb(yuzde 0-100, durum_kodu)  durum_kodu: "indiriliyor" | "yukleniyor" | "bitti"
IlerlemeCb = Callable[[float, str], None]


class SesMotoru(Protocol):
    kod: str
    ad: str
    yerel: bool     # False = ses örneği başka bir servise gider (yalnız ElevenLabs)

    def hazir(self) -> bool:
        """Model indirilmiş/yüklenebilir durumda mı (ağ gerektirmeden hızlı bakış)."""

    async def hazirla(self, ilerleme_cb: IlerlemeCb | None = None) -> None:
        """Gerekli modeli indirir ve belleğe yükler. Eksik paket/ağ için DublajHatasi."""

    async def seslendir(self, metin: str, referans_pcm: Any, sr: int) -> tuple[Any, int]:
        """Türkçe `metin`i, `referans_pcm` (float32 mono, `sr` Hz) sesinin tonunda okur.

        Dönüş: (float32 mono pcm, çıkış_sr). Referans yalnız bellekte kalır.
        """
