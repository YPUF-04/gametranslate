# SPDX-License-Identifier: AGPL-3.0-only
"""Test/demo için deterministik sahte motor."""
from __future__ import annotations

from .temel import Ceviri


class SahteMotor:
    kod = "sahte"
    ad = "Sahte (deneme)"
    anahtar_gerekli = False
    cevrimdisi = True
    ucretsiz = True

    def __init__(self) -> None:
        self.cagrilar: list[list[str]] = []

    async def cevir(self, metinler: list[str], kaynak: str, hedef: str,
                    sozluk: dict[str, str], aciklama: bool = False) -> list[Ceviri]:
        self.cagrilar.append(list(metinler))
        return [Ceviri(f"[TR] {m}", "Görev: deneme" if aciklama else None) for m in metinler]
