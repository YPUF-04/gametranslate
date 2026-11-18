# SPDX-License-Identifier: AGPL-3.0-only
"""Çevrimdışı motor (argostranslate, isteğe bağlı kurulum)."""
from __future__ import annotations

import asyncio

from .. import sozluk as sozluk_mod
from .temel import Ceviri, MotorHatasi


class YerelMotor:
    kod = "yerel"
    ad = "Çevrimdışı (yerel)"
    anahtar_gerekli = False
    cevrimdisi = True
    ucretsiz = True

    @staticmethod
    def kurulu_mu() -> bool:
        try:
            import argostranslate.translate  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def hazirla(kaynak: str, hedef: str) -> None:
        """Dil paketini indirir (kullanıcı onayıyla çağrılmalı; ağ gerekir)."""
        if not YerelMotor.kurulu_mu():
            raise MotorHatasi("argostranslate kurulu değil")
        import argostranslate.package as paket
        paket.update_package_index()
        for p in paket.get_available_packages():
            if p.from_code == kaynak and p.to_code == hedef:
                paket.install_from_path(p.download())
                return
        raise MotorHatasi(f"{kaynak}->{hedef} dil paketi bulunamadı")

    def _cevir_senkron(self, metin: str, kaynak: str, hedef: str) -> str:
        import argostranslate.translate as tr
        k = "en" if kaynak in ("otomatik", "", "auto") else kaynak
        return tr.translate(metin, k, hedef)

    async def cevir(self, metinler: list[str], kaynak: str, hedef: str,
                    sozluk: dict[str, str], aciklama: bool = False) -> list[Ceviri]:
        if not self.kurulu_mu():
            raise MotorHatasi("Çevrimdışı çeviri için argostranslate kurulu değil")
        out: list[Ceviri] = []
        for m in metinler:
            korunan, harita = sozluk_mod.koru(m, sozluk)
            try:
                s = await asyncio.to_thread(self._cevir_senkron, korunan, kaynak, hedef)
            except Exception as e:  # dil paketi eksik vb.
                raise MotorHatasi("Çevrimdışı dil paketi hazır değil") from e
            out.append(Ceviri(sozluk_mod.geri_koy(s, harita)))
        return out
