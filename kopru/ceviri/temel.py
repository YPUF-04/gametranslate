# SPDX-License-Identifier: AGPL-3.0-only
"""Çeviri motoru arayüzü ve ortak hatalar."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AgHatasi(Exception):
    """Ağ/sunucu sorunu: yönetici yedek motora geçer."""


class AnahtarHatasi(Exception):
    """API anahtarı yok ya da geçersiz."""


class MotorHatasi(Exception):
    """Motor kullanılamıyor (kurulu değil vb.)."""


@dataclass
class Ceviri:
    metin: str
    aciklama: str | None = None


class CeviriMotoru(Protocol):
    kod: str
    ad: str
    anahtar_gerekli: bool
    cevrimdisi: bool

    async def cevir(self, metinler: list[str], kaynak: str, hedef: str,
                    sozluk: dict[str, str], aciklama: bool = False) -> list[Ceviri]: ...
