# SPDX-License-Identifier: AGPL-3.0-only
"""Gemini motoru (REST)."""
from __future__ import annotations

import logging
from typing import Any

from . import _http, istem
from .temel import AgHatasi, AnahtarHatasi, Baglam, Ceviri, ModelBulunamadi, MotorHatasi

log = logging.getLogger("kopru.ceviri")
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
VARSAYILAN_MODEL = "gemini-3.8-flash"
# Model "bulunamadı" (404) dönerse sırayla denenir; çalışan hatırlanır.
YEDEK_MODELLER = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
# §16.4: altyazı isteğinin düşünme düzeyi. Flash'larda "low" (az ama sıfır değil: daha doğal Türkçe, ~1-2 sn),
# Flash-Lite'ta "minimal" (en kısa gecikme). gemini-3.8-flash ve Gemini 4 "minimal"i TANIMAZ (HTTP 400).
# Model bir düzeyi tanımazsa (400) o model için düşünme ayarı gönderilmez ve bu hatırlanır.
ALTYAZI_SN = 8.0
HIZLI_YEDEK_MODEL = "gemini-3.5-flash-lite"   # zaman aşımı / 429 / 5xx: kendi kotası olan hızlı model bir kez
HIZLI_YEDEK_SN = 6.0
DERIN_SN = 15.0          # PROTOKOL 19.2: iyileştirme isteği (ekrandaki ilk çeviriyi bekletmez)
DERIN_DUZEY = "medium"


def dusunme_duzeyi(model: str) -> str | None:
    m = (model or "").lower()
    if m.startswith("gemini-2.") or m.startswith("gemini-1."):
        return None                     # eski modeller düzey değil bütçe ister: hiç gönderilmez
    if "flash-lite" in m:
        return "minimal"
    return "low"


# Kapatılmış eski modeller: ayar dosyasında kalmışsa seçim sayılmaz, yükseltilir.
ESKI_MODELLER = frozenset({"gemini-2.5-flash", "gemini-2.0-flash"})


class GeminiMotoru:
    kod = "gemini"
    ad = "Gemini"
    anahtar_gerekli = True
    cevrimdisi = False
    ucretsiz = True
    baglam_destekler = True
    iyilestirme_destekler = True   # PROTOKOL 19.2

    def __init__(self, anahtar: str | None, model: str = VARSAYILAN_MODEL) -> None:
        self._anahtar = anahtar
        self.model = model
        # §16.4: model -> gönderilecek düşünme düzeyi (None: gönderme). 400 alınan model burada None olur.
        self._duzey: dict[str, str | None] = {}

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

    @property
    def dusunme_kapali(self) -> bool:
        """Geriye uyum: bu modelde düşünme ayarı hâlâ gönderiliyor mu."""
        return self.duzey(self.model) is not None

    def duzey(self, model: str) -> str | None:
        return self._duzey.get(model, dusunme_duzeyi(model))

    @staticmethod
    def _dusunmeli(govde: dict[str, Any], duzey: str | None) -> dict[str, Any]:
        if duzey is None:
            return govde
        return {**govde, "generationConfig": {**govde["generationConfig"], "thinkingConfig": {"thinkingLevel": duzey}}}

    async def _hizli_gonder(self, govde: dict[str, Any], zaman_asimi: float | None = None) -> Any:
        zaman_asimi = ALTYAZI_SN if zaman_asimi is None else zaman_asimi
        model = self.model
        duzey = self.duzey(model)
        if duzey is None:
            return await self._gonder(govde, zaman_asimi)
        try:
            return await self._gonder(self._dusunmeli(govde, duzey), zaman_asimi)
        except AgHatasi as e:
            if not str(e).startswith("HTTP 400"):
                raise
            # bu model bu düşünme düzeyini tanımıyor: hatırla, onsuz dene (eşzamanlı isteklerin hepsi de)
            log.info("Gemini %s düşünme düzeyi %r'yi kabul etmedi; düzeysiz deneniyor", model, duzey)
            self._duzey[model] = None
            return await self._gonder(govde, zaman_asimi)

    async def _altyazi_gonder(self, govde: dict[str, Any]) -> Any:
        """Altyazı isteği: asıl model; zaman aşımı / hız sınırı (429) / sunucu hatasında satır kaybolmasın diye
        kendi kotası olan hızlı model (Flash-Lite, düşünme `minimal`) bir kez denenir."""
        try:
            return await self._hizli_gonder(govde)
        except AgHatasi as e:
            if str(e).startswith("HTTP 400") or self.model == HIZLI_YEDEK_MODEL:
                raise
            log.info("Gemini %s yanıt vermedi (%s); bu satır %s ile deneniyor", self.model, e, HIZLI_YEDEK_MODEL)
            try:
                return await _http.post_json(URL.format(model=HIZLI_YEDEK_MODEL),
                                             self._dusunmeli(govde, self.duzey(HIZLI_YEDEK_MODEL)),
                                             {"x-goog-api-key": self._anahtar}, zaman_asimi=HIZLI_YEDEK_SN)
            except (AgHatasi, ModelBulunamadi):
                raise e from None

    async def _derin_gonder(self, govde: dict[str, Any]) -> Any:
        """İyileştirme: aynı model, daha çok düşünme, daha uzun süre; hızlı yedek model denenmez."""
        duzey = DERIN_DUZEY if self.duzey(self.model) is not None else None
        try:
            return await self._gonder(self._dusunmeli(govde, duzey), DERIN_SN)
        except AgHatasi as e:
            if duzey is None or not str(e).startswith("HTTP 400"):
                raise
            return await self._gonder(govde, DERIN_SN)

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
        veri = await (self._derin_gonder(govde) if baglam is not None and baglam.derin
                      else self._altyazi_gonder(govde))
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
