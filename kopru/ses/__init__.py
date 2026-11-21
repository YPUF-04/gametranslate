# SPDX-License-Identifier: AGPL-3.0-only
"""Oyun sesini dinler (İSTEĞE BAĞLI): konuşma çevirisi ve Türkçe dublaj için konuşma parçaları.

Gizlilik kuralları (değişmez):
- YALNIZ sistem çıkış sesi (hoparlörün loopback'i) dinlenir; mikrofon ASLA açılmaz.
- Ses diske yazılmaz; yalnız bellekte tutulur.
"""
from __future__ import annotations

import logging
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

log = logging.getLogger("kopru.ses")


class SesHatasi(Exception):
    """Ses çevirisi kullanılamıyor; mesaj Türkçe, `kod` metinler.py anahtarıdır."""

    def __init__(self, mesaj: str, kod: str = "dublaj_ses_kaynagi") -> None:
        super().__init__(mesaj)
        self.kod = kod


ORNEK_HIZI = 16000
SESSIZLIK_SN = 0.7
AZAMI_SN = 12.0
ESIK = 0.01  # RMS enerji eşiği


@dataclass
class Parca:
    """Bitmiş bir konuşma parçası (VAD çıktısı). Saat: `time.monotonic()` alanı."""
    pcm: Any            # float32 mono numpy dizisi
    sr: int
    bas: float          # parçanın başladığı an
    bitis: float        # parçanın bittiği an


def kutuphaneleri_kontrol(dublaj: bool = False) -> None:
    if sys.platform == "darwin":
        raise SesHatasi("macOS'ta oyun sesini dinlemek için BlackHole gibi bir sanal ses "
                        "aygıtı kurup sistem çıkışı olarak seçmeniz gerekir.", "dublaj_macos_ses")
    gerekli = ["numpy", "soundcard"] + ([] if dublaj else ["faster_whisper"])
    for ad in gerekli:
        try:
            __import__(ad)
        except ImportError as e:
            raise SesHatasi(f"Ses için '{ad}' paketi gerekli. "
                            "Kurulum: pip install \"altyazikoprusu[dublaj]\"", "dublaj_paket_yok") from e


def kaynak_ac(sc: Any = None) -> Any:
    """Dinlenecek aygıtı açar: varsayılan HOPARLÖRÜN loopback'i. Mikrofon aygıtı ASLA istenmez.

    `sc`: `soundcard` modülü (testlerde sahtesi verilir). Dönen nesne loopback olmak zorundadır.
    """
    if sc is None:
        import soundcard as sc  # tembel
    hoparlor = sc.default_speaker()
    kaynak = sc.get_microphone(id=str(hoparlor.name), include_loopback=True)
    if not getattr(kaynak, "isloopback", True):
        raise SesHatasi("Oyun sesi dinlenemedi: sistem çıkışının loopback aygıtı bulunamadı.",
                        "dublaj_ses_kaynagi")
    return kaynak


class _Ps5Kayit:
    def __init__(self, kaynak: Any) -> None:
        self.kaynak = kaynak

    def __enter__(self) -> "_Ps5Kayit":
        self.kaynak.ac()
        return self

    def __exit__(self, *_: Any) -> None:
        self.kaynak.kapat()

    def record(self, numframes: int) -> Any:
        return self.kaynak.oku().reshape(-1, 1)


class _Ps5Aygit:
    """`kaynak_ac` ile aynı biçim: `recorder(...)` bağlamı `record(n)` verir. Ses gizli PS5 bağlantısından gelir."""
    isloopback = True

    def recorder(self, samplerate: int = ORNEK_HIZI, channels: int = 1) -> _Ps5Kayit:
        from .. import uzaktan
        from ..dublaj.isci.canli import Ps5Ses
        y = uzaktan.etkin()
        kanal = y.ses_kanali()
        if not y.calisiyor():
            y.baglan()
        return _Ps5Kayit(Ps5Ses(kanal["kapi"], kanal["anahtar"]))


def ps5_kaynak() -> Any:
    """PROTOKOL §15.8: kaynak `ps5:gizli` iken oyun sesi (16 kHz mono) PS5 bağlantısından okunur."""
    return _Ps5Aygit()


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


class SesKaynagi:
    """Arka plan iş parçacığında loopback'i dinler; her konuşma parçası için `parca_cb(Parca)` çağırır."""

    def __init__(self, parca_cb: Callable[[Parca], None], saat: Callable[[], float] = time.monotonic,
                 kaynak_fabrika: Callable[[], Any] = kaynak_ac, hata_cb: Callable[[SesHatasi], None] | None = None) -> None:
        self.parca_cb = parca_cb
        self.saat = saat
        self.kaynak_fabrika = kaynak_fabrika
        self.hata_cb = hata_cb
        self._dur = threading.Event()
        self._is: threading.Thread | None = None

    def baslat(self, dublaj: bool = True) -> None:
        kutuphaneleri_kontrol(dublaj)
        self._dur.clear()
        self._is = threading.Thread(target=self._calis, daemon=True, name="kopru-ses")
        self._is.start()

    def durdur(self) -> None:
        self._dur.set()

    def _calis(self) -> None:
        try:
            kaynak = self.kaynak_fabrika()
            durum: dict[str, Any] = {"tampon": [], "sessiz": 0.0, "uzunluk": 0.0}
            with kaynak.recorder(samplerate=ORNEK_HIZI, channels=1) as kayit:
                while not self._dur.is_set():
                    blok = kayit.record(numframes=ORNEK_HIZI // 4)[:, 0]
                    dizi = konusma_parcala(blok, durum)
                    if dizi is not None:
                        bitis = self.saat()
                        self.parca_cb(Parca(dizi, ORNEK_HIZI, bitis - len(dizi) / ORNEK_HIZI, bitis))
        except SesHatasi as e:
            if self.hata_cb:
                self.hata_cb(e)
        except Exception as e:     # aygıt kopması vb.: program çökmesin
            log.warning("Ses dinleme durdu: %s", type(e).__name__)
            if self.hata_cb:
                self.hata_cb(SesHatasi(f"Oyun sesi dinlenemedi: {type(e).__name__}", "dublaj_ses_kaynagi"))


class WhisperSTT:
    """faster-whisper ile konuşmayı yazıya çevirir (yerel, tembel yüklenir)."""

    def __init__(self, model: str = "small", atla_dil: str | None = "tr") -> None:
        self.model = model
        self.atla_dil = atla_dil     # algılanan dil buysa (zaten Türkçe konuşuyor) boş döner
        self._m: Any = None
        self.dil: str | None = None

    def _yukle(self) -> Any:
        if self._m is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise SesHatasi("Konuşmayı yazıya çevirmek için 'faster-whisper' gerekli. "
                                "Kurulum: pip install \"altyazikoprusu[dublaj]\"", "dublaj_paket_yok") from e
            self._m = WhisperModel(self.model, compute_type="int8")
        return self._m

    def _yaz(self, pcm: Any) -> str:
        parcalar, bilgi = self._yukle().transcribe(pcm, vad_filter=True)
        self.dil = getattr(bilgi, "language", None)
        if self.atla_dil and self.dil == self.atla_dil:
            return ""
        return " ".join(p.text.strip() for p in parcalar).strip()

    async def yaz(self, pcm: Any, sr: int) -> str:
        import asyncio
        return await asyncio.to_thread(self._yaz, pcm)


class SesCevirici:
    """(Eski) konuşmayı yazıya çevirir; her konuşma için geri_cagri(metin) çağırır."""

    def __init__(self, geri_cagri: Callable[[str], None], model: str = "small") -> None:
        self.geri_cagri = geri_cagri
        self.stt = WhisperSTT(model, None)
        self.kaynak = SesKaynagi(self._parca)

    def _parca(self, p: Parca) -> None:
        metin = self.stt._yaz(p.pcm)
        if metin:
            self.geri_cagri(metin)

    def baslat(self) -> None:
        self.kaynak.baslat(dublaj=False)

    def durdur(self) -> None:
        self.kaynak.durdur()
