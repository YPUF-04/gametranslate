# SPDX-License-Identifier: AGPL-3.0-only
"""DeepSeek motoru (OpenAI uyumlu REST)."""
from __future__ import annotations

from typing import Any

from . import _http, istem
from .temel import AnahtarHatasi, Baglam, Ceviri, MotorHatasi

URL = "https://api.deepseek.com/chat/completions"


class DeepSeekMotoru:
    kod = "deepseek"
    ad = "DeepSeek"
    anahtar_gerekli = True
    cevrimdisi = False
    ucretsiz = False
    baglam_destekler = True

    def __init__(self, anahtar: str | None, model: str = "deepseek-chat") -> None:
        self._anahtar = anahtar
        self.model = model

    async def cevir(self, metinler: list[str], kaynak: str, hedef: str,
                    sozluk: dict[str, str], aciklama: bool = False,
                    baglam: Baglam | None = None) -> list[Ceviri]:
        if not self._anahtar:
            raise AnahtarHatasi("deepseek")
        if not metinler:
            return []
        govde: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": istem.sistem_istemi(kaynak, hedef, sozluk, aciklama, baglam)},
                {"role": "user", "content": istem.kullanici_metni(metinler, baglam)},
            ],
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        veri = await _http.post_json(URL, govde, {"Authorization": f"Bearer {self._anahtar}"})
        try:
            sonuc, terimler = istem.yaniti_coz_tam(veri["choices"][0]["message"]["content"],
                                                   len(metinler), aciklama)
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise MotorHatasi("DeepSeek yanıtı okunamadı") from e
        if baglam is not None:
            baglam.yeni_terimler.extend(terimler)
        return sonuc

    async def serbest_istem(self, sistem: str, kullanici: str, zaman_asimi: float = 45.0) -> str:
        """Çeviri dışı tek seferlik istek (oyun bilgisi, PROTOKOL 12.3): JSON yanıt metnini döndürür."""
        if not self._anahtar:
            raise AnahtarHatasi("deepseek")
        govde: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": sistem}, {"role": "user", "content": kullanici}],
            "stream": False,
            "response_format": {"type": "json_object"},
            "max_tokens": 4000,
        }
        veri = await _http.post_json(URL, govde, {"Authorization": f"Bearer {self._anahtar}"}, zaman_asimi=zaman_asimi)
        try:
            return str(veri["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as e:
            raise MotorHatasi("DeepSeek yanıtı okunamadı") from e
