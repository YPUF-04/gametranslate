# SPDX-License-Identifier: AGPL-3.0-only
"""Dublaj sesinin çıkışı: bu bilgisayarın hoparlörü (oyun sesi kısılarak) ya da TV (SSE `ses`).

Her ses yalnız bellekte tutulur. TV için ses `SesDeposu`nda 60 sn yaşar, sonra 404 olur.
Oyun sesini kısma (ducking):
- Windows: `pycaw` ile YALNIZ oyun/Remote Play uygulamasının ses oturumu kısılır (bizim işlemimiz hariç).
- macOS/Linux: uygulama başına kısma yoktur; en iyi çaba olarak genel çıkış sesi kısılır
  (`osascript` / `pactl`), sonra eski değere döner. Bulunamazsa hiçbir şey kısılmaz.
"""
from __future__ import annotations

import asyncio
import atexit
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Protocol

from .temel import DublajHatasi

if TYPE_CHECKING:   # numpy yalnız dublaj açıkken gerekir (tembel yüklenir)
    import numpy as np

log = logging.getLogger("kopru.dublaj")
SES_OMRU_SN = 60.0
ONCELIKLI_UYGULAMALAR = ("remoteplay", "chiaki", "xboxpcapp", "xbox", "playstation", "ps remote",
                         "steam", "parsec", "moonlight", "geforcenow", "gamestream")
KIS_RAMPA_SN = 0.15
ACMA_RAMPA_SN = 0.45


# ---------- TV için bellek deposu ----------

class SesDeposu:
    """`/kopru/ses/<id>.wav` için bellek içi, süreli depo (diske yazılmaz)."""

    def __init__(self, omur_sn: float = SES_OMRU_SN, saat: Callable[[], float] = time.monotonic) -> None:
        self.omur = omur_sn
        self.saat = saat
        self._veri: dict[str, tuple[float, bytes]] = {}
        self._sayac = 0

    def koy(self, wav: bytes) -> str:
        self._temizle()
        self._sayac += 1
        kimlik = f"s{self._sayac}"
        self._veri[kimlik] = (self.saat() + self.omur, wav)
        return kimlik

    def al(self, kimlik: str) -> bytes | None:
        self._temizle()
        v = self._veri.get(kimlik)
        return v[1] if v else None

    def _temizle(self) -> None:
        simdi = self.saat()
        for k in [k for k, (bitis, _) in self._veri.items() if bitis <= simdi]:
            del self._veri[k]

    def bosalt(self) -> None:
        self._veri.clear()

    def __len__(self) -> int:
        self._temizle()
        return len(self._veri)


# ---------- ses kısma ----------

class KisiciArkaUc(Protocol):
    def bul(self) -> list[Any]: ...                 # kısılacak oturumlar
    def al(self, oturum: Any) -> float: ...         # şu anki ses (0-1)
    def ayarla(self, oturum: Any, deger: float) -> None: ...


def _pencere_islemi(kaynak: str) -> int | None:
    """`pencere:<hwnd>` kaynağının işlem numarası (yalnız Windows)."""
    if sys.platform != "win32" or not kaynak.startswith("pencere:"):
        return None
    try:
        import ctypes
        pid = ctypes.c_ulong(0)
        ctypes.windll.user32.GetWindowThreadProcessId(int(kaynak.split(":", 1)[1]), ctypes.byref(pid))  # type: ignore[attr-defined]
        return int(pid.value) or None
    except Exception:
        return None


class WindowsArkaUc:
    """pycaw: yalnız seçilen uygulamaların ses oturumunu kısar."""

    def __init__(self, kaynak: str = "") -> None:
        self.kaynak = kaynak

    def bul(self) -> list[Any]:
        try:
            from pycaw.pycaw import AudioUtilities  # tembel (yalnız Windows)
        except Exception:
            log.info("pycaw kurulu değil: oyun sesi kısılamaz (pip install \"altyazikoprusu[dublaj]\")")
            return []
        benim = os.getpid()
        pencere_pid = _pencere_islemi(self.kaynak)
        tum, secilen = [], []
        try:
            oturumlar = AudioUtilities.GetAllSessions()
        except Exception:
            return []
        for o in oturumlar:
            try:
                pid = int(getattr(o, "ProcessId", 0) or (o.Process.pid if o.Process else 0))
                if not pid or pid == benim:
                    continue
                ad = (o.Process.name() if o.Process else "").lower()
                tum.append((o, ad, pid))
            except Exception:
                continue
        for o, ad, pid in tum:
            if pid == pencere_pid or any(k in ad for k in ONCELIKLI_UYGULAMALAR):
                secilen.append(o)
        if secilen:
            return secilen
        # tanınan uygulama yok: şu an ses çalan (etkin) oturumları kıs
        return [o for o, _, _ in tum if getattr(o, "State", 0) == 1]

    def al(self, oturum: Any) -> float:
        return float(oturum.SimpleAudioVolume.GetMasterVolume())

    def ayarla(self, oturum: Any, deger: float) -> None:
        oturum.SimpleAudioVolume.SetMasterVolume(max(0.0, min(1.0, deger)), None)


class GenelSesArkaUc:
    """macOS / Linux: tek genel çıkış sesi (en iyi çaba)."""

    def bul(self) -> list[Any]:
        return ["genel"] if self._oku() is not None else []

    def _calistir(self, *a: str) -> str | None:
        try:
            return subprocess.run(list(a), capture_output=True, text=True, timeout=3, check=True).stdout
        except Exception:
            return None

    def _oku(self) -> float | None:
        if sys.platform == "darwin":
            c = self._calistir("osascript", "-e", "output volume of (get volume settings)")
            return float(c) / 100 if c and c.strip().isdigit() else None
        c = self._calistir("pactl", "get-sink-volume", "@DEFAULT_SINK@")
        if c and "%" in c:
            try:
                return int(c.split("%")[0].split()[-1]) / 100
            except ValueError:
                return None
        return None

    def al(self, oturum: Any) -> float:
        return self._oku() or 1.0

    def ayarla(self, oturum: Any, deger: float) -> None:
        yuzde = int(round(max(0.0, min(1.0, deger)) * 100))
        if sys.platform == "darwin":
            self._calistir("osascript", "-e", f"set volume output volume {yuzde}")
        else:
            self._calistir("pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{yuzde}%")


class Kisici:
    """Oyun sesini yumuşakça kısar ve bitince eski değere geri açar."""

    def __init__(self, arka_uc: KisiciArkaUc, uyku: Callable[[float], Any] = time.sleep) -> None:
        self.arka = arka_uc
        self._uyku = uyku
        self._eski: list[tuple[Any, float]] = []
        atexit.register(self.geri_ac)     # program kapanırsa ses kısık kalmasın

    def kis(self, oran: float) -> None:
        """`oran`: oyun sesinin kalacağı kesir (0.25 = dörtte birine insin)."""
        if self._eski:
            return
        try:
            self._eski = [(o, self.arka.al(o)) for o in self.arka.bul()]
        except Exception:
            self._eski = []
        self._rampa([(o, v, v * oran) for o, v in self._eski], KIS_RAMPA_SN)

    def geri_ac(self) -> None:
        if not self._eski:
            return
        eski, self._eski = self._eski, []
        try:
            self._rampa([(o, self.arka.al(o), v) for o, v in eski], ACMA_RAMPA_SN)
        finally:
            for o, v in eski:      # son durum her koşulda tam eski değer
                try:
                    self.arka.ayarla(o, v)
                except Exception:
                    pass

    def _rampa(self, isler: list[tuple[Any, float, float]], sure: float, adim: int = 6) -> None:
        for i in range(1, adim + 1):
            for o, bas, son in isler:
                try:
                    self.arka.ayarla(o, bas + (son - bas) * i / adim)
                except Exception:
                    pass
            if i < adim:
                self._uyku(sure / adim)


def kisici_olustur(kaynak: str = "") -> Kisici:
    return Kisici(WindowsArkaUc(kaynak) if sys.platform == "win32" else GenelSesArkaUc())


# ---------- çıkışlar ----------

@dataclass
class OynatmaBilgisi:
    sure_sn: float
    kimlik: str | None = None      # TV için ses kimliği


class BilgisayarCikis:
    """Varsayılan hoparlörden çalar; çalarken oyun sesini kısar."""

    ad = "bilgisayar"

    def __init__(self, kisici_fabrika: Callable[[str], Kisici] = kisici_olustur,
                 oynatici: Callable[[np.ndarray, int], None] | None = None) -> None:
        self._kisici_fabrika = kisici_fabrika
        self._oynatici = oynatici or self._sounddevice_oynat

    @staticmethod
    def _sounddevice_oynat(pcm: np.ndarray, sr: int) -> None:
        try:
            import sounddevice as sd  # tembel
        except (ImportError, OSError) as e:   # OSError: PortAudio kütüphanesi yok
            raise DublajHatasi("dublaj_cikis_yok", type(e).__name__) from e
        try:
            sd.play(pcm, sr)     # varsayılan ÇIKIŞ aygıtı (mikrofon değil)
            sd.wait()
        except Exception as e:
            raise DublajHatasi("dublaj_cikis_yok", f"{type(e).__name__}: {e}") from e

    def durdur(self) -> None:
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass

    async def oynat(self, pcm: np.ndarray, sr: int, ayar: dict[str, Any], yazi_id: str | None = None) -> OynatmaBilgisi:
        import numpy as np
        d = ayar.get("dublaj") or {}
        kaynak = str(ayar.get("kaynak") or "")
        veri = np.clip(pcm * float(d.get("ses_seviyesi", 1.0)), -1.0, 1.0).astype(np.float32)
        kis = float(d.get("oyun_sesi_kis", 0.25))
        kisici = self._kisici_fabrika(kaynak) if kis < 1.0 else None
        await asyncio.to_thread(lambda: kisici.kis(kis) if kisici else None)
        try:
            await asyncio.to_thread(self._oynatici, veri, sr)
        finally:
            if kisici:
                await asyncio.to_thread(kisici.geri_ac)
        return OynatmaBilgisi(len(pcm) / sr)


class TvCikis:
    """TV uygulamasına SSE `ses` olayı yollar; ses bellekten sunulur. Oyun sesi kısılmaz."""

    ad = "tv"

    def __init__(self, depo: SesDeposu, yayin: Any) -> None:
        self.depo = depo
        self.yayin = yayin
        self._bitis_gorevi: asyncio.Task | None = None

    async def oynat(self, pcm: np.ndarray, sr: int, ayar: dict[str, Any],
                    yazi_id: str | None = None) -> OynatmaBilgisi:
        import numpy as np
        from . import dsp
        d = ayar.get("dublaj") or {}
        veri = np.clip(pcm * float(d.get("ses_seviyesi", 1.0)), -1.0, 1.0).astype(np.float32)
        kimlik = self.depo.koy(dsp.wav_bayt(veri, sr))
        sure = len(veri) / sr
        self.yayin.yayinla("ses", {"id": kimlik, "url": f"/kopru/ses/{kimlik}.wav",
                                   "sure_ms": int(sure * 1000), "yazi_id": yazi_id})
        return OynatmaBilgisi(sure, kimlik)

    def durdur(self) -> None:
        self.yayin.yayinla("ses-dur", {})
