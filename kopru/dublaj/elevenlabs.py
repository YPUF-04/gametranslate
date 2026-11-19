# SPDX-License-Identifier: AGPL-3.0-only
"""ElevenLabs (bulut, ücretli) - İSTEĞE BAĞLI ve çift onaylı; kullanıcının kendi anahtarıyla.

Dürüst özet:
- Birinci onay (`elevenlabs_onay`): çevrilen Türkçe METİN ElevenLabs'e gönderilir.
- Ses seçimi: kullanıcının kendi hesabından seçtiği `voice_id` ile okutulur (ses örneği gitmez).
- İkinci onay (`elevenlabs_klon_onay`): karakterin ses ÖRNEĞİ ElevenLabs'e YÜKLENİR ve orada
  geçici bir "anında ses klonu" oluşturulur. ElevenLabs hesabında kalıcı bir kayıttır; bu yüzden
  program oturum bitince (`kapat`) o klonları siler. Program çökerse kalmış olabilir: ElevenLabs
  panelinden "Voices" listesinden elle silinebilir. İkinci onay yoksa hiçbir ses örneği gönderilmez.
Anahtar yalnız işletim sisteminin şifreli kasasındadır (anahtarlar.py).
Kullanılan uç noktalar (docs.elevenlabs.io): POST /v1/text-to-speech/{voice_id}?output_format=pcm_24000,
POST /v1/voices/add (çok parçalı), DELETE /v1/voices/{voice_id}.
"""
from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from typing import Any, Awaitable, Callable

import numpy as np

from .. import anahtarlar
from . import dsp
from .temel import DublajHatasi, IlerlemeCb

log = logging.getLogger("kopru.dublaj")
TABAN = "https://api.elevenlabs.io"
CIKIS_SR = 24000
EN_COK_KLON = 3          # hesapta aynı anda en çok bu kadar geçici klon; eskisi silinir

# istek(yontem, yol, json=None, veri=None, sorgu=None) -> (durum_kodu, gövde_baytı)
Istek = Callable[..., Awaitable[tuple[int, bytes]]]


class ElevenLabsMotoru:
    kod = "elevenlabs"
    ad = "ElevenLabs"
    yerel = False      # ses örneği/metin başka bir servise gider

    def __init__(self, ses_kimligi: str = "", model: str = "eleven_multilingual_v2",
                 klon_onay: bool = False, onay: bool = True, istek: Istek | None = None) -> None:
        self.ses_kimligi = (ses_kimligi or "").strip()
        self.model = model or "eleven_multilingual_v2"
        self.klon_onay = bool(klon_onay)
        self.onay = bool(onay)
        self._istek = istek or self._http
        self._klonlar: OrderedDict[str, str] = OrderedDict()   # örnek özeti -> geçici voice_id

    # -- gerekli koşullar --
    def _anahtar(self) -> str:
        a = anahtarlar.oku("elevenlabs")
        if not a:
            raise DublajHatasi("dublaj_eleven_anahtar_yok")
        return a

    def hazir(self) -> bool:
        """Anahtar kayıtlı, onay verilmiş ve (klon onayı ya da seçili ses) var."""
        return bool(anahtarlar.oku("elevenlabs")) and self.onay and (self.klon_onay or bool(self.ses_kimligi))

    async def hazirla(self, ilerleme_cb: IlerlemeCb | None = None) -> None:
        """İndirilecek model yok; anahtarı ve onayları denetler."""
        if not self.onay:
            raise DublajHatasi("dublaj_eleven_onay_yok")
        self._anahtar()
        if not (self.klon_onay or self.ses_kimligi):
            raise DublajHatasi("dublaj_eleven_ses_yok")
        if ilerleme_cb:
            ilerleme_cb(100.0, "bitti")

    # -- HTTP --
    async def _http(self, yontem: str, yol: str, json: Any = None, veri: Any = None,
                    sorgu: dict[str, str] | None = None) -> tuple[int, bytes]:
        import aiohttp
        basliklar = {"xi-api-key": self._anahtar()}
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as s:
                async with s.request(yontem, TABAN + yol, json=json, data=veri, params=sorgu,
                                     headers=basliklar) as r:
                    return r.status, await r.read()
        except (aiohttp.ClientError, TimeoutError) as e:
            raise DublajHatasi("dublaj_eleven_ag", type(e).__name__) from e

    @staticmethod
    def _durum_hatasi(durum: int) -> DublajHatasi:
        if durum in (401, 403):
            return DublajHatasi("dublaj_eleven_anahtar_gecersiz", str(durum))
        if durum == 429:
            return DublajHatasi("dublaj_eleven_kota", str(durum))
        return DublajHatasi("dublaj_eleven_hata", str(durum))

    # -- ses klonu (yalnız ikinci onayla) --
    async def _klon_kimligi(self, pcm: np.ndarray, sr: int) -> str:
        if not self.klon_onay:                 # güvenlik: onay yoksa ASLA örnek yüklenmez
            raise DublajHatasi("dublaj_eleven_klon_onay_yok")
        ozet = hashlib.sha1(pcm.tobytes()).hexdigest()
        if ozet in self._klonlar:
            self._klonlar.move_to_end(ozet)
            return self._klonlar[ozet]
        import aiohttp
        form = aiohttp.FormData()
        form.add_field("name", "AltyaziKoprusu-gecici")
        form.add_field("remove_background_noise", "true")
        form.add_field("files", dsp.wav_bayt(pcm, sr), filename="ornek.wav", content_type="audio/wav")
        durum, govde = await self._istek("POST", "/v1/voices/add", veri=form)
        if durum != 200:
            raise self._durum_hatasi(durum)
        import json
        try:
            kimlik = str(json.loads(govde)["voice_id"])
        except (ValueError, KeyError, TypeError) as e:
            raise DublajHatasi("dublaj_eleven_hata", "voice_id yok") from e
        self._klonlar[ozet] = kimlik
        while len(self._klonlar) > EN_COK_KLON:
            _, eski = self._klonlar.popitem(last=False)
            await self._klon_sil(eski)
        return kimlik

    async def _klon_sil(self, kimlik: str) -> None:
        try:
            await self._istek("DELETE", f"/v1/voices/{kimlik}")
        except DublajHatasi:
            log.warning("ElevenLabs geçici ses klonu silinemedi; hesabınızdaki Voices listesinden silebilirsiniz.")

    async def kapat(self) -> None:
        """Oturum bitti: oluşturulan bütün geçici klonlar hesaptan silinir."""
        while self._klonlar:
            _, kimlik = self._klonlar.popitem(last=False)
            await self._klon_sil(kimlik)

    # -- üretim --
    async def seslendir(self, metin: str, referans_pcm: Any, sr: int) -> tuple[np.ndarray, int]:
        if not self.onay:
            raise DublajHatasi("dublaj_eleven_onay_yok")
        self._anahtar()
        pcm = dsp.mono_float(referans_pcm)
        if self.klon_onay:
            kimlik = await self._klon_kimligi(pcm, sr)
        elif self.ses_kimligi:
            kimlik = self.ses_kimligi
        else:
            raise DublajHatasi("dublaj_eleven_ses_yok")
        durum, govde = await self._istek(
            "POST", f"/v1/text-to-speech/{kimlik}", json={"text": metin, "model_id": self.model},
            sorgu={"output_format": f"pcm_{CIKIS_SR}"})
        if durum != 200:
            raise self._durum_hatasi(durum)
        return dsp.pcm16_to_float(govde), CIKIS_SR
