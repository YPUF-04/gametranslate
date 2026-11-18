# SPDX-License-Identifier: AGPL-3.0-only
"""DeepSeek motoru (OpenAI uyumlu REST)."""
from __future__ import annotations

from typing import Any

from . import _http, istem
from .temel import AnahtarHatasi, Ceviri, MotorHatasi

URL = "https://api.deepseek.com/chat/completions"


class DeepSeekMotoru:
    kod = "deepseek"
    ad = "DeepSeek"
    anahtar_gerekli = True
    cevrimdisi = False
    ucretsiz = False

    def __init__(self, anahtar: str | None, model: str = "deepseek-chat") -> None:
        self._anahtar = anahtar
        self.model = model

    async def cevir(self, metinler: list[str], kaynak: str, hedef: str,
                    sozluk: dict[str, str], aciklama: bool = False) -> list[Ceviri]:
        if not self._anahtar:
            raise AnahtarHatasi("deepseek")
        if not metinler:
            return []
        govde: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": istem.sistem_istemi(kaynak, hedef, sozluk, aciklama)},
                {"role": "user", "content": istem.kullanici_metni(metinler)},
            ],
            "stream": False,
        }
        veri = await _http.post_json(URL, govde, {"Authorization": f"Bearer {self._anahtar}"})
        try:
            return istem.yaniti_coz(veri["choices"][0]["message"]["content"],
                                    len(metinler), aciklama)
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise MotorHatasi("DeepSeek yanıtı okunamadı") from e
