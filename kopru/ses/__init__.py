# SPDX-License-Identifier: AGPL-3.0-only
"""Konuşma çevirisi (İSTEĞE BAĞLI). Yalnız sistem çıkış sesini dinler.

Mikrofon ASLA açılmaz; ses diske yazılmaz (yalnız bellekte tutulur).
"""
from __future__ import annotations

import sys
import threading
from typing import Any, Callable


class SesHatasi(Exception):
    """Ses çevirisi kullanılamıyor; mesaj Türkçe."""


ORNEK_HIZI = 16000
SESSIZLIK_SN = 0.7
AZAMI_SN = 12.0
ESIK = 0.01  # RMS enerji eşiği


def kutuphaneleri_kontrol() -> None:
    if sys.platform == "darwin":
        raise SesHatasi("macOS'ta oyun sesini dinlemek için BlackHole gibi bir sanal ses "
                        "aygıtı kurup sistem çıkışı olarak seçmeniz gerekir.")
    try:
        import numpy  # noqa: F401
        import soundcard  # noqa: F401
        import faster_whisper  # noqa: F401
    except ImportError as e:
        raise SesHatasi("Ses çevirisi için ek paketler gerekli. "
                        "Kurulum: pip install \"altyazikoprusu[ses]\"") from e


def konusma_parcala(blok: Any, durum: dict[str, Any]) -> Any | None:
    """Enerji tabanlı basit VAD. Bir konuşma bitince birleşik diziyi döndürür."""
    import numpy as np
    sesli = float(np.sqrt(np.mean(blok ** 2))) > ESIK
    sure = len(blok) / ORNEK_HIZI
    if sesli:
        durum["tampon"].append(blok)
        durum["sessiz"] = 0.0
        durum["uzunluk"] += sure
    elif durum["tampon"]:
        durum["tampon"].append(blok)
        durum["sessiz"] += sure
        durum["uzunluk"] += sure
    if durum["tampon"] and (durum["sessiz"] >= SESSIZLIK_SN or durum["uzunluk"] >= AZAMI_SN):
        dizi = np.concatenate(durum["tampon"])
        durum.update(tampon=[], sessiz=0.0, uzunluk=0.0)
        return dizi
    return None


class SesCevirici:
    """Arka plan iş parçacığında dinler; her konuşma için geri_cagri(metin) çağırır."""

    def __init__(self, geri_cagri: Callable[[str], None], model: str = "small") -> None:
        self.geri_cagri = geri_cagri
        self.model = model
        self._dur = threading.Event()
        self._is: threading.Thread | None = None

    def baslat(self) -> None:
        kutuphaneleri_kontrol()
        self._dur.clear()
        self._is = threading.Thread(target=self._calis, daemon=True, name="kopru-ses")
        self._is.start()

    def durdur(self) -> None:
        self._dur.set()

    def _calis(self) -> None:
        import soundcard as sc
        from faster_whisper import WhisperModel
        model = WhisperModel(self.model, compute_type="int8")
        hoparlor = sc.default_speaker()
        # include_loopback: hoparlörün çıkışını dinler, mikrofon değildir
        kaynak = sc.get_microphone(id=str(hoparlor.name), include_loopback=True)
        durum: dict[str, Any] = {"tampon": [], "sessiz": 0.0, "uzunluk": 0.0}
        with kaynak.recorder(samplerate=ORNEK_HIZI, channels=1) as kayit:
            while not self._dur.is_set():
                blok = kayit.record(numframes=ORNEK_HIZI // 4)[:, 0]
                dizi = konusma_parcala(blok, durum)
                if dizi is None:
                    continue
                parcalar, _ = model.transcribe(dizi, vad_filter=True)
                metin = " ".join(p.text.strip() for p in parcalar).strip()
                if metin:
                    self.geri_cagri(metin)
