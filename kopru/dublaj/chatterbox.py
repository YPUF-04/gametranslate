# SPDX-License-Identifier: AGPL-3.0-only
"""Chatterbox Multilingual (Resemble AI, MIT) - yerel, en iyi kalite, güçlü ekran kartı ister.

Paket: `chatterbox-tts`. Ağır bağımlılıklar (torch...) yalnız `hazirla`da yüklenir.
Gerçek API (chatterbox-tts 0.1.7 kaynağından):
  ChatterboxMultilingualTTS.from_pretrained(device)      # Hugging Face'ten indirir
  .prepare_conditionals(wav_fpath)                        # librosa.load(...) -> dosya-benzeri nesne olur
  .generate(text, language_id="tr", audio_prompt_path=..) # torch.Tensor (1, N), .sr = 24000
`librosa.load` (soundfile üzerinden) dosya-benzeri nesne kabul ettiği için referans ses
`io.BytesIO` WAV olarak verilir: DİSKE HİÇBİR ŞEY YAZILMAZ. Bir sürüm bunu kabul etmezse
(bilinen sınırlama) yedek yol: RAM diskinde (Linux /dev/shm; Windows/macOS'ta RAM diski yoktur,
sistem geçici klasörü) kısa ömürlü `NamedTemporaryFile`; `prepare_conditionals` biter bitmez silinir.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
import tempfile
from typing import Any

import numpy as np

from . import donanim, dsp
from .hf_indir import indir
from .temel import DublajHatasi, IlerlemeCb

log = logging.getLogger("kopru.dublaj")
REPO = "ResembleAI/chatterbox"
DOSYALAR = ["ve.pt", "t3_mtl23ls_v2.safetensors", "s3gen.pt", "grapheme_mtl_merged_expanded_v1.json",
            "conds.pt", "Cangjie5_TC.json"]


def _ram_dizini() -> str | None:
    return "/dev/shm" if os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK) else None


class ChatterboxMotoru:
    kod = "chatterbox"
    ad = "Chatterbox"
    yerel = True

    def __init__(self) -> None:
        self._model: Any = None
        self._cihaz = "cpu"
        self._son_ref = ""            # son hazırlanan referansın özeti (aynıysa yeniden hazırlanmaz)
        self._kilit = asyncio.Lock()

    def hazir(self) -> bool:
        if self._model is not None:
            return True
        try:
            from huggingface_hub import try_to_load_from_cache
            return isinstance(try_to_load_from_cache(REPO, "s3gen.pt"), str)
        except Exception:
            return False

    async def hazirla(self, ilerleme_cb: IlerlemeCb | None = None) -> None:
        if self._model is not None:
            return
        try:
            import torch  # noqa: F401
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        except ImportError as e:
            raise DublajHatasi("dublaj_paket_yok", "chatterbox-tts") from e
        await indir(REPO, DOSYALAR, ilerleme_cb)
        if ilerleme_cb:
            ilerleme_cb(100.0, "yukleniyor")
        self._cihaz = donanim.cihaz_sec()
        if self._cihaz == "cpu":
            log.warning("Chatterbox ekran kartı olmadan çok yavaş çalışır; Pocket TTS önerilir.")
        try:
            self._model = await asyncio.to_thread(ChatterboxMultilingualTTS.from_pretrained, self._cihaz)
        except Exception as e:
            raise DublajHatasi("dublaj_yukleme_hata", f"{type(e).__name__}: {e}") from e
        if ilerleme_cb:
            ilerleme_cb(100.0, "bitti")

    def _hazirla_referans(self, pcm: np.ndarray, sr: int) -> None:
        ozet = hashlib.sha1(pcm.tobytes()).hexdigest() + str(sr)
        if ozet == self._son_ref:
            return
        wav = dsp.wav_bayt(pcm, sr)
        try:
            self._model.prepare_conditionals(io.BytesIO(wav))      # tamamen bellekte
        except Exception as e:
            log.info("Bellekten okuma olmadı (%s); RAM diskinde kısa ömürlü yedek yol deneniyor", type(e).__name__)
            with tempfile.NamedTemporaryFile(suffix=".wav", dir=_ram_dizini(), delete=False) as f:
                yol = f.name
                f.write(wav)
            try:
                self._model.prepare_conditionals(yol)
            finally:
                try:
                    os.unlink(yol)     # hemen silinir
                except OSError:
                    pass
        self._son_ref = ozet

    def _uret(self, metin: str, pcm: np.ndarray, sr: int) -> tuple[np.ndarray, int]:
        self._hazirla_referans(pcm, sr)
        wav = self._model.generate(metin, language_id="tr")
        return np.asarray(wav.squeeze().detach().cpu().numpy(), dtype=np.float32), int(self._model.sr)

    async def seslendir(self, metin: str, referans_pcm: Any, sr: int) -> tuple[np.ndarray, int]:
        if self._model is None:
            raise DublajHatasi("dublaj_hazir_degil", "chatterbox")
        async with self._kilit:      # model tek seferde bir cümle üretir
            try:
                return await asyncio.to_thread(self._uret, metin, dsp.mono_float(referans_pcm), sr)
            except DublajHatasi:
                raise
            except Exception as e:
                raise DublajHatasi("dublaj_uretim_hata", f"{type(e).__name__}: {e}") from e
