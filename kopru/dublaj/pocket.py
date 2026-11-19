# SPDX-License-Identifier: AGPL-3.0-only
"""Kyutai Pocket TTS + Türkçe topluluk modeli (kaanhgunay/pocket-tts-tr) - yerel, CPU'da çalışır.

Paket: `pocket-tts`. Gerçek API (pocket-tts 4.0 kaynağından):
  TTSModel.load_model(config="hf://<repo>/config.yaml@<sürüm>")      # CPU
  model.get_state_for_audio_prompt(torch.Tensor[kanal, örnek])        # bellekten, 24 kHz
  model.generate_audio(state, metin)  -> torch.Tensor [örnek]         # model.sample_rate
Referans ses bir torch tensörü olarak verilir: DİSKE HİÇBİR ŞEY YAZILMAZ.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any

import numpy as np

from . import dsp
from .hf_indir import indir
from .temel import DublajHatasi, IlerlemeCb

log = logging.getLogger("kopru.dublaj")
DEPO = "kaanhgunay/pocket-tts-tr"
SURUM = "v0.1-base"
AYAR_YOLU = f"hf://{DEPO}/config.yaml@{SURUM}"


class PocketMotoru:
    kod = "pocket"
    ad = "Pocket TTS"
    yerel = True

    def __init__(self) -> None:
        self._model: Any = None
        self._durum_ozeti = ""
        self._durum: Any = None
        self._kilit = asyncio.Lock()

    def hazir(self) -> bool:
        if self._model is not None:
            return True
        try:
            from huggingface_hub import try_to_load_from_cache
            return isinstance(try_to_load_from_cache(DEPO, "config.yaml", revision=SURUM), str)
        except Exception:
            return False

    async def hazirla(self, ilerleme_cb: IlerlemeCb | None = None) -> None:
        if self._model is not None:
            return
        try:
            import torch  # noqa: F401
            from pocket_tts import TTSModel
        except ImportError as e:
            raise DublajHatasi("dublaj_paket_yok", "pocket-tts") from e
        await indir(DEPO, None, ilerleme_cb, SURUM)
        if ilerleme_cb:
            ilerleme_cb(100.0, "yukleniyor")
        try:
            self._model = await asyncio.to_thread(lambda: TTSModel.load_model(config=AYAR_YOLU))
        except Exception as e:
            raise DublajHatasi("dublaj_yukleme_hata", f"{type(e).__name__}: {e}") from e
        if ilerleme_cb:
            ilerleme_cb(100.0, "bitti")

    def _uret(self, metin: str, pcm: np.ndarray, sr: int) -> tuple[np.ndarray, int]:
        import torch
        model = self._model
        ozet = hashlib.sha1(pcm.tobytes()).hexdigest() + str(sr)
        if ozet != self._durum_ozeti:       # aynı konuşmacı örneği için durum yeniden kurulmaz
            hedef_sr = int(model.config.mimi.sample_rate)
            ornek = dsp.yeniden_ornekle(pcm, sr, hedef_sr)
            self._durum = model.get_state_for_audio_prompt(torch.from_numpy(ornek).unsqueeze(0))
            self._durum_ozeti = ozet
        ses = model.generate_audio(self._durum, metin)
        return np.asarray(ses.detach().cpu().numpy(), dtype=np.float32).reshape(-1), int(model.sample_rate)

    async def seslendir(self, metin: str, referans_pcm: Any, sr: int) -> tuple[np.ndarray, int]:
        if self._model is None:
            raise DublajHatasi("dublaj_hazir_degil", "pocket")
        async with self._kilit:      # pocket-tts iş parçacığı güvenli değildir
            try:
                return await asyncio.to_thread(self._uret, metin, dsp.mono_float(referans_pcm), sr)
            except DublajHatasi:
                raise
            except Exception as e:
                raise DublajHatasi("dublaj_uretim_hata", f"{type(e).__name__}: {e}") from e
