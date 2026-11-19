# SPDX-License-Identifier: AGPL-3.0-only
"""Gemini motoru (REST)."""
from __future__ import annotations

from typing import Any

from . import _http, istem
from .temel import AnahtarHatasi, Baglam, Ceviri, ModelBulunamadi, MotorHatasi

URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
VARSAYILAN_MODEL = "gemini-3.8-flash"
# Model "bulunamadı" (404) dönerse sırayla denenir; çalışan hatırlanır.
YEDEK_MODELLER = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
# Kapatılmış eski modeller: ayar dosyasında kalmışsa seçim sayılmaz, yükseltilir.
ESKI_MODELLER = frozenset({"gemini-2.5-flash", "gemini-2.0-flash"})


class GeminiMotoru:
    kod = "gemini"
    ad = "Gemini"
    anahtar_gerekli = True
    cevrimdisi = False
    ucretsiz = True
    baglam_destekler = True

    def __init__(self, anahtar: str | None, model: str = VARSAYILAN_MODEL) -> None:
        self._anahtar = anahtar
        self.model = model

    async def _gonder(self, govde: dict[str, Any], zaman_asimi: float = 8.0) -> Any:
        """İstek; model 404 verirse sıradaki yedek modelle yeniden dener, çalışanı hatırlar."""
        denenecek = [self.model] + [m for m in YEDEK_MODELLER if m != self.model]
        son: ModelBulunamadi | None = None
        for m in denenecek:
            try:
                veri = await _http.post_json(URL.format(model=m), govde, {"x-goog-api-key": self._anahtar},
                                             zaman_asimi=zaman_asimi)
            except ModelBulunamadi as e:
                son = e
                continue
            self.model = m
            return veri
        raise son or ModelBulunamadi("HTTP 404")

    async def cevir(self, metinler: list[str], kaynak: str, hedef: str,
                    sozluk: dict[str, str], aciklama: bool = False,
                    baglam: Baglam | None = None) -> list[Ceviri]:
        if not self._anahtar:
            raise AnahtarHatasi("gemini")
        if not metinler:
            return []
        govde: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": istem.sistem_istemi(kaynak, hedef, sozluk, aciklama, baglam)}]},
            "contents": [{"role": "user", "parts": [{"text": istem.kullanici_metni(metinler, baglam)}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        veri = await self._gonder(govde)
        try:
            ham = "".join(p.get("text", "") for p in veri["candidates"][0]["content"]["parts"])
            sonuc, terimler = istem.yaniti_coz_tam(ham, len(metinler), aciklama)
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise MotorHatasi("Gemini yanıtı okunamadı") from e
        if baglam is not None:
            baglam.yeni_terimler.extend(terimler)
        return sonuc

    async def serbest_istem(self, sistem: str, kullanici: str, zaman_asimi: float = 45.0) -> str:
        """Çeviri dışı tek seferlik istek (oyun bilgisi, PROTOKOL 12.3): JSON yanıt metnini döndürür."""
        if not self._anahtar:
            raise AnahtarHatasi("gemini")
        govde: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": sistem}]},
            "contents": [{"role": "user", "parts": [{"text": kullanici}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        veri = await self._gonder(govde, zaman_asimi)
        try:
            return "".join(p.get("text", "") for p in veri["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError, TypeError) as e:
            raise MotorHatasi("Gemini yanıtı okunamadı") from e
