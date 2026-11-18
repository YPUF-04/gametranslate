# SPDX-License-Identifier: AGPL-3.0-only
"""DeepL motoru (REST). Talimat almaz: terimler yer tutucuyla korunur."""
from __future__ import annotations

from typing import Any

from .. import sozluk as sozluk_mod
from . import _http
from .temel import AnahtarHatasi, Ceviri, MotorHatasi

DIL = {"tr": "TR", "en": "EN-US", "de": "DE", "fr": "FR", "es": "ES", "it": "IT",
       "ru": "RU", "ja": "JA", "ko": "KO", "zh": "ZH", "pt": "PT-PT", "pl": "PL"}


class DeepLMotoru:
    kod = "deepl"
    ad = "DeepL"
    anahtar_gerekli = True
    cevrimdisi = False
    ucretsiz = True

    def __init__(self, anahtar: str | None) -> None:
        self._anahtar = anahtar

    def _url(self) -> str:
        assert self._anahtar
        ana = "api-free.deepl.com" if self._anahtar.endswith(":fx") else "api.deepl.com"
        return f"https://{ana}/v2/translate"

    async def cevir(self, metinler: list[str], kaynak: str, hedef: str,
                    sozluk: dict[str, str], aciklama: bool = False) -> list[Ceviri]:
        if not self._anahtar:
            raise AnahtarHatasi("deepl")
        if not metinler:
            return []
        korunmus = [sozluk_mod.koru(m, sozluk) for m in metinler]
        govde: dict[str, Any] = {
            "text": [k[0] for k in korunmus],
            "target_lang": DIL.get(hedef, hedef.upper()),
            "tag_handling": "xml",
            "ignore_tags": [],
        }
        if kaynak not in ("otomatik", "", "auto"):
            govde["source_lang"] = kaynak.upper()
        veri = await _http.post_json(self._url(), govde,
                                     {"Authorization": f"DeepL-Auth-Key {self._anahtar}"})
        try:
            ceviriler = [t["text"] for t in veri["translations"]]
        except (KeyError, TypeError) as e:
            raise MotorHatasi("DeepL yanıtı okunamadı") from e
        if len(ceviriler) != len(metinler):
            raise MotorHatasi("DeepL yanıtı okunamadı")
        return [Ceviri(sozluk_mod.geri_koy(c, k[1])) for c, k in zip(ceviriler, korunmus)]
