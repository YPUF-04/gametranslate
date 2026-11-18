# SPDX-License-Identifier: AGPL-3.0-only
"""Gemini motoru (REST)."""
from __future__ import annotations

from typing import Any

from . import _http, istem
from .temel import AnahtarHatasi, Ceviri, MotorHatasi

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiMotoru:
    kod = "gemini"
    ad = "Gemini"
    anahtar_gerekli = True
    cevrimdisi = False
    ucretsiz = True

    def __init__(self, anahtar: str | None, model: str = "gemini-2.5-flash") -> None:
        self._anahtar = anahtar
        self.model = model

    async def cevir(self, metinler: list[str], kaynak: str, hedef: str,
                    sozluk: dict[str, str], aciklama: bool = False) -> list[Ceviri]:
        if not self._anahtar:
            raise AnahtarHatasi("gemini")
        if not metinler:
            return []
        govde: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": istem.sistem_istemi(kaynak, hedef, sozluk, aciklama)}]},
            "contents": [{"role": "user", "parts": [{"text": istem.kullanici_metni(metinler)}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        veri = await _http.post_json(URL.format(model=self.model), govde,
                                     {"x-goog-api-key": self._anahtar})
        try:
            ham = "".join(p.get("text", "") for p in veri["candidates"][0]["content"]["parts"])
            return istem.yaniti_coz(ham, len(metinler), aciklama)
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise MotorHatasi("Gemini yanıtı okunamadı") from e
