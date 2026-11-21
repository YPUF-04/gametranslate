# SPDX-License-Identifier: AGPL-3.0-only
"""Canlı dublajın işçi tarafı (PROTOKOL 14.3): YALNIZ oyunun sesini dinler, konuşma parçalarını
ana programa `parca` olayıyla yollar, Türkçe sesi çalar ve çalarken oyun sesini kısar.

- Windows 10 2004+: seçili oyunun süreci için WASAPI process loopback (yalnız o süreç ağacı).
  Olmazsa tüm sistem çıkışının loopback'i (soundcard). Mikrofon ASLA açılmaz.
- Ses örnekleri yalnız bellekte; bu modül dosya yazmaz.
- "Tamamen Türkçe" (DENEYSEL): oyunun ses oturumu 0'a çekilir, oyunun sesinden konuşma ayrılır ve
  yalnız arka plan (müzik/efekt) ~2 sn gecikmeyle çalınır. Windows'ta gerçek donanımda doğrulanmadı;
  susturulan oturumdan yakalanan ses de sessizleşirse kendiliğinden "kıs" moduna döner.
"""
from __future__ import annotations

import ctypes
import logging
import os
import queue
from collections import deque
import sys
import threading
import time
from typing import Any, Callable

import numpy as np

from . import protokol

log = logging.getLogger("kopru.isci.canli")
SR = 16000
BLOK = SR // 4                 # 250 ms
ARKA_BLOK_SN = 0.25            # tamamen Türkçe: arka plan bu boyda bloklarla çalınır (gecikme ≈ blok + ayırma süresi)
ARKA_BAGLAM_SN = 3.0           # ayırıcıya verilen geçmiş (sol bağlam)
KALIBRASYON_SN = 1.5           # oturum sesi kısılmadan / kısıldıktan sonra ölçüm süresi
TELAFI_SES = 0.03              # yakalama kısılmış sesi görüyorsa oyunun bırakılan sesi (−30 dB)


# ---------- Windows: WASAPI process loopback (ctypes + comtypes) ----------

def surec_loopback_destek() -> bool:
    if sys.platform != "win32":
        return False
    try:
        v = sys.getwindowsversion()
        if (v.major, v.build) < (10, 19041):      # Windows 10 2004
            return False
        import comtypes  # noqa: F401
        return True
    except Exception:
        return False


class SurecLoopback:
    """Tek bir sürecin (ve alt süreçlerinin) sesini yakalar. `oku()` → float32 mono 16 kHz blok."""

    def __init__(self, pid: int) -> None:
        self.pid = int(pid)
        self._istemci: Any = None
        self._yakalayici: Any = None
        self._olay: Any = None
        self._kanal = 2
        self._sr = 48000
        self._artik = np.zeros(0, dtype=np.float32)

    def ac(self) -> None:
        import comtypes
        from comtypes import GUID, COMMETHOD, HRESULT, IUnknown, COMObject
        from ctypes import POINTER, byref, c_void_p, c_uint32, c_int64, c_uint16, Structure, Union, c_ulong
        from ctypes import wintypes

        comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)

        class WAVEFORMATEX(Structure):
            _fields_ = [("wFormatTag", c_uint16), ("nChannels", c_uint16), ("nSamplesPerSec", c_uint32),
                        ("nAvgBytesPerSec", c_uint32), ("nBlockAlign", c_uint16), ("wBitsPerSample", c_uint16),
                        ("cbSize", c_uint16)]

        class IAudioCaptureClient(IUnknown):
            _iid_ = GUID("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")
            _methods_ = [
                COMMETHOD([], HRESULT, "GetBuffer", (["out"], POINTER(POINTER(ctypes.c_ubyte)), "data"),
                          (["out"], POINTER(c_uint32), "frames"), (["out"], POINTER(c_uint32), "flags"),
                          (["out"], POINTER(ctypes.c_uint64), "pos"), (["out"], POINTER(ctypes.c_uint64), "qpc")),
                COMMETHOD([], HRESULT, "ReleaseBuffer", (["in"], c_uint32, "frames")),
                COMMETHOD([], HRESULT, "GetNextPacketSize", (["out"], POINTER(c_uint32), "frames"))]

        class IAudioClient(IUnknown):
            _iid_ = GUID("{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}")
            _methods_ = [
                COMMETHOD([], HRESULT, "Initialize", (["in"], c_uint32, "mode"), (["in"], c_uint32, "flags"),
                          (["in"], c_int64, "buf"), (["in"], c_int64, "period"), (["in"], POINTER(WAVEFORMATEX), "fmt"),
                          (["in"], c_void_p, "session")),
                COMMETHOD([], HRESULT, "GetBufferSize", (["out"], POINTER(c_uint32), "n")),
                COMMETHOD([], HRESULT, "GetStreamLatency", (["out"], POINTER(c_int64), "l")),
                COMMETHOD([], HRESULT, "GetCurrentPadding", (["out"], POINTER(c_uint32), "p")),
                COMMETHOD([], HRESULT, "IsFormatSupported", (["in"], c_uint32, "m"), (["in"], c_void_p, "f"),
                          (["out"], POINTER(c_void_p), "c")),
                COMMETHOD([], HRESULT, "GetMixFormat", (["out"], POINTER(c_void_p), "f")),
                COMMETHOD([], HRESULT, "GetDevicePeriod", (["out"], POINTER(c_int64), "d"), (["out"], POINTER(c_int64), "m")),
                COMMETHOD([], HRESULT, "Start"),
                COMMETHOD([], HRESULT, "Stop"),
                COMMETHOD([], HRESULT, "Reset"),
                COMMETHOD([], HRESULT, "SetEventHandle", (["in"], wintypes.HANDLE, "h")),
                COMMETHOD([], HRESULT, "GetService", (["in"], POINTER(GUID), "iid"), (["out"], POINTER(c_void_p), "s"))]

        class IActivateAudioInterfaceAsyncOperation(IUnknown):
            _iid_ = GUID("{72A22D78-CDE4-431D-B8CC-843A71199B6D}")
            _methods_ = [COMMETHOD([], HRESULT, "GetActivateResult", (["out"], POINTER(HRESULT), "hr"),
                                   (["out"], POINTER(POINTER(IUnknown)), "iface"))]

        class IActivateAudioInterfaceCompletionHandler(IUnknown):
            _iid_ = GUID("{41D949AB-9862-444A-80F6-C261334DA5EB}")
            _methods_ = [COMMETHOD([], HRESULT, "ActivateCompleted",
                                   (["in"], POINTER(IActivateAudioInterfaceAsyncOperation), "op"))]

        class IAgileObject(IUnknown):
            _iid_ = GUID("{94ea2b94-e9cc-49e0-c0ff-ee64ca8f5b90}")
            _methods_ = []

        bitti = threading.Event()
        sonuc: dict[str, Any] = {}

        class Tamamlayici(COMObject):
            _com_interfaces_ = [IActivateAudioInterfaceCompletionHandler, IAgileObject]

            def ActivateCompleted(self, op: Any) -> int:   # noqa: N802 (COM adı)
                try:
                    hr, arayuz = op.GetActivateResult()
                    sonuc["hr"], sonuc["arayuz"] = hr, arayuz
                except Exception as e:   # noqa: BLE001
                    sonuc["hata"] = e
                bitti.set()
                return 0

        class LOOPBACK(Structure):
            _fields_ = [("TargetProcessId", c_ulong), ("ProcessLoopbackMode", c_uint32)]

        class PARAMS(Structure):
            _fields_ = [("ActivationType", c_uint32), ("Loopback", LOOPBACK)]

        class BLOB(Structure):
            _fields_ = [("cbSize", c_ulong), ("pBlobData", c_void_p)]

        class _PV(Union):
            _fields_ = [("blob", BLOB), ("pad", ctypes.c_byte * 16)]

        class PROPVARIANT(Structure):
            _fields_ = [("vt", c_uint16), ("r1", c_uint16), ("r2", c_uint16), ("r3", c_uint16), ("v", _PV)]

        params = PARAMS(1, LOOPBACK(self.pid, 0))   # PROCESS_LOOPBACK, INCLUDE_TARGET_PROCESS_TREE
        pv = PROPVARIANT()
        pv.vt = 65                                  # VT_BLOB
        pv.v.blob.cbSize = ctypes.sizeof(params)
        pv.v.blob.pBlobData = ctypes.cast(ctypes.pointer(params), c_void_p)
        tam = Tamamlayici()
        islem = POINTER(IActivateAudioInterfaceAsyncOperation)()
        mmdevapi = ctypes.WinDLL("Mmdevapi.dll")
        etkinlestir = mmdevapi.ActivateAudioInterfaceAsync
        etkinlestir.argtypes = [wintypes.LPCWSTR, POINTER(GUID), c_void_p, c_void_p, c_void_p]
        hr = etkinlestir("VAD\\Process_Loopback", byref(IAudioClient._iid_), byref(pv),
                         tam.QueryInterface(IActivateAudioInterfaceCompletionHandler), byref(islem))
        if hr != 0:
            raise OSError(f"ActivateAudioInterfaceAsync {hr:#x}")
        if not bitti.wait(5.0) or sonuc.get("hata") or sonuc.get("hr", 1) != 0:
            raise OSError(f"process loopback etkinleşmedi: {sonuc}")
        istemci = sonuc["arayuz"].QueryInterface(IAudioClient)
        fmt = WAVEFORMATEX(3, 2, 48000, 48000 * 8, 8, 32, 0)        # IEEE float 32 bit stereo 48 kHz
        LOOPBACK_BAYRAK, OLAY_BAYRAK, OTOMATIK = 0x00020000, 0x00040000, 0x80000000 | 0x08000000
        istemci.Initialize(0, LOOPBACK_BAYRAK | OLAY_BAYRAK | OTOMATIK, 2_000_000, 0, byref(fmt), None)
        olay = ctypes.windll.kernel32.CreateEventW(None, False, False, None)
        istemci.SetEventHandle(olay)
        ptr = istemci.GetService(byref(IAudioCaptureClient._iid_))
        self._yakalayici = ctypes.cast(ptr, POINTER(IAudioCaptureClient))
        istemci.Start()
        self._istemci, self._olay = istemci, olay

    def oku(self) -> np.ndarray:
        """En az 250 ms'lik blok döndürür (16 kHz mono)."""
        k32 = ctypes.windll.kernel32
        hedef = int(self._sr * 0.25)
        parcalar = [self._artik]
        toplam = len(self._artik)
        while toplam < hedef:
            k32.WaitForSingleObject(self._olay, 200)
            while True:
                n = self._yakalayici.GetNextPacketSize()
                if not n:
                    break
                veri, kare, bayrak, _, _ = self._yakalayici.GetBuffer()
                if bayrak & 0x2:     # AUDCLNT_BUFFERFLAGS_SILENT
                    a = np.zeros(kare, dtype=np.float32)
                else:
                    ham = np.ctypeslib.as_array(veri, shape=(kare * 8,)).view("<f4").astype(np.float32)
                    a = ham.reshape(-1, 2).mean(axis=1)
                self._yakalayici.ReleaseBuffer(kare)
                parcalar.append(a)
                toplam += len(a)
        tum = np.concatenate(parcalar)
        self._artik = tum[hedef:]
        blok = tum[:hedef]
        n = int(len(blok) * SR / self._sr)
        return np.interp(np.linspace(0, len(blok) - 1, n), np.arange(len(blok)), blok).astype(np.float32)

    def kapat(self) -> None:
        try:
            if self._istemci is not None:
                self._istemci.Stop()
            if self._olay:
                ctypes.windll.kernel32.CloseHandle(self._olay)
        except Exception:   # noqa: BLE001
            pass
        self._istemci = self._yakalayici = None


class GirisYakalama:
    """Yakalama kartının ses girişi (USB/line-in). YALNIZ kullanıcının adıyla açıkça seçtiği aygıt açılır;
    varsayılan giriş (mikrofon) asla kendiliğinden açılmaz."""

    def __init__(self, ad: str) -> None:
        self.ad = ad
        self._ctx: Any = None
        self._kayit: Any = None

    def ac(self) -> None:
        if not self.ad:
            raise OSError("giriş seçilmedi")
        import soundcard as sc
        aygit = sc.get_microphone(id=self.ad, include_loopback=False)
        self._ctx = aygit.recorder(samplerate=SR, channels=1)
        self._kayit = self._ctx.__enter__()

    def oku(self) -> np.ndarray:
        return self._kayit.record(numframes=BLOK // 2)[:, 0].astype(np.float32)

    def kapat(self) -> None:
        try:
            if self._ctx is not None:
                self._ctx.__exit__(None, None, None)
        except Exception:   # noqa: BLE001
            pass


def girisleri_listele() -> list[dict[str, str]]:
    """Ses girişlerinin YALNIZ adları (hiçbiri açılmaz). Yakalama kartına benzeyenler işaretlenir."""
    try:
        import soundcard as sc
        out = []
        for m in sc.all_microphones(include_loopback=False):
            ad = str(m.name)
            kart = any(k in ad.lower() for k in ("capture", "elgato", "avermedia", "cam link", "hdmi", "usb video",
                                                 "game capture", "live gamer", "razer ripsaw", "digital audio interface"))
            out.append({"ad": ad, "kimlik": str(m.id), "kart": kart})
        return out
    except Exception:   # noqa: BLE001
        return []


class Ps5Ses:
    """PROTOKOL §15.8: gizli PS5 bağlantısının sesi. Ana programın 127.0.0.1'deki kapısına bağlanır,
    anahtarı yollar, 16 kHz mono 16 bit PCM okur. PS5 sesi bilgisayarda çalınmaz (TV çalar)."""

    def __init__(self, kapi: int, anahtar: str, zaman_asimi: float = 2.0) -> None:
        self.kapi, self.anahtar, self.zaman_asimi = int(kapi), str(anahtar), zaman_asimi
        self._s: Any = None
        self._artik = b""

    def ac(self) -> None:
        import socket
        self._s = socket.create_connection(("127.0.0.1", self.kapi), timeout=5)
        self._s.sendall(self.anahtar.encode() + b"\n")
        self._s.settimeout(self.zaman_asimi)

    def oku(self) -> np.ndarray:
        import socket
        gerekli = BLOK * 2
        veri = self._artik
        son = time.monotonic() + self.zaman_asimi
        while len(veri) < gerekli and time.monotonic() < son:
            try:
                parca = self._s.recv(gerekli - len(veri))
            except socket.timeout:
                break
            if not parca:
                raise OSError("PS5 ses kanalı kapandı")
            veri += parca
        if len(veri) % 2:
            veri, self._artik = veri[:-1], veri[-1:]
        else:
            self._artik = b""
        if not veri:   # akış durdu (PS5 bağlantısı bekliyor): sessizlik ver, döngü dönsün
            return np.zeros(BLOK, dtype=np.float32)
        return np.frombuffer(veri, dtype="<i2").astype(np.float32) / 32768.0

    def kapat(self) -> None:
        try:
            if self._s is not None:
                self._s.close()
        except OSError:
            pass


class SistemLoopback:
    """Yedek: varsayılan hoparlörün loopback'i (soundcard). Mikrofon aygıtı ASLA istenmez."""

    def __init__(self) -> None:
        self._kayit: Any = None
        self._ctx: Any = None

    def ac(self) -> None:
        from ...ses import kaynak_ac
        self._ctx = kaynak_ac().recorder(samplerate=SR, channels=1)
        self._kayit = self._ctx.__enter__()

    def oku(self) -> np.ndarray:
        return self._kayit.record(numframes=BLOK)[:, 0].astype(np.float32)

    def kapat(self) -> None:
        try:
            if self._ctx is not None:
                self._ctx.__exit__(None, None, None)
        except Exception:   # noqa: BLE001
            pass


# ---------- oyun sesi kısma (işçide; pycaw) ----------

class OturumSesi:
    """Belirli bir sürecin (ya da tanınan oyun uygulamalarının) ses oturumunu kısar/geri açar."""

    def __init__(self, pid: int | None) -> None:
        self.pid = pid
        self._eski: list[tuple[Any, float]] = []

    def _oturumlar(self) -> list[Any]:
        try:
            from pycaw.pycaw import AudioUtilities
        except Exception:
            return []
        benim = os.getpid()
        out = []
        for o in AudioUtilities.GetAllSessions():
            try:
                pid = int(o.ProcessId or 0)
                if pid and pid != benim and (self.pid is None or pid == self.pid):
                    out.append(o)
            except Exception:   # noqa: BLE001
                continue
        return out

    def kis(self, oran: float) -> None:
        if self._eski:
            return
        for o in self._oturumlar():
            try:
                v = o.SimpleAudioVolume
                self._eski.append((v, float(v.GetMasterVolume())))
            except Exception:   # noqa: BLE001
                continue
        for adim in range(1, 7):
            for v, eski in self._eski:
                try:
                    v.SetMasterVolume(max(0.0, eski + (eski * oran - eski) * adim / 6), None)
                except Exception:   # noqa: BLE001
                    pass
            time.sleep(0.025)

    def ayarla(self, deger: float) -> None:
        """Kalibrasyon için: eski değerleri saklayıp oturum(lar)ı doğrudan `deger`e çeker."""
        if not self._eski:
            for o in self._oturumlar():
                try:
                    v = o.SimpleAudioVolume
                    self._eski.append((v, float(v.GetMasterVolume())))
                except Exception:   # noqa: BLE001
                    continue
        for v, _ in self._eski:
            try:
                v.SetMasterVolume(max(0.0, min(1.0, deger)), None)
            except Exception:   # noqa: BLE001
                pass

    def geri_ac(self) -> None:
        eski, self._eski = self._eski, []
        for v, deger in eski:
            try:
                v.SetMasterVolume(deger, None)
            except Exception:   # noqa: BLE001
                pass


# ---------- canlı yakalama ----------

class CanliYakalama:
    def __init__(self, gonder: Callable[[dict[str, Any]], None], pid: int | None = None,
                 ayirici: Callable[[np.ndarray, int], tuple[np.ndarray, np.ndarray]] | None = None,
                 tamamen_turkce: bool = False, kaynak_fabrika: Callable[[], Any] | None = None,
                 giris: str = "", ps5_ses: dict[str, Any] | None = None) -> None:
        self.ps5_ses = ps5_ses
        self.gonder = gonder
        self.pid = int(pid) if pid else None
        self.ayirici = ayirici
        self.tamamen_turkce = tamamen_turkce
        self.kaynak_fabrika = kaynak_fabrika
        self.giris = giris
        self.kaynak_turu = "sistem"
        self.arka_ms: deque[float] = deque(maxlen=50)
        self._dur = threading.Event()
        self._is: threading.Thread | None = None
        self._kaynak: Any = None
        self._oturum: OturumSesi | None = None
        self._arka_kuyruk: queue.Queue = queue.Queue(maxsize=8)
        self._arka_oynatici: Any = None
        self.tamamen_aktif = False

    def _kaynak_ac(self) -> Any:
        if self.kaynak_fabrika is not None:
            k = self.kaynak_fabrika()
            k.ac()
            return k
        if self.ps5_ses:        # gizli PS5 bağlantısı (§15.8)
            k = Ps5Ses(int(self.ps5_ses.get("kapi") or 0), str(self.ps5_ses.get("anahtar") or ""))
            k.ac()
            self.kaynak_turu = "ps5"
            return k
        if self.giris:          # yakalama kartı: kullanıcının açıkça seçtiği giriş
            k = GirisYakalama(self.giris)
            k.ac()
            self.kaynak_turu = "giris"
            return k
        if self.pid and surec_loopback_destek():
            try:
                k = SurecLoopback(self.pid)
                k.ac()
                self.kaynak_turu = "surec"
                return k
            except Exception as e:   # noqa: BLE001
                log.warning("Süreç loopback açılamadı (%s); tüm sistem sesi dinlenecek", e)
        k = SistemLoopback()
        k.ac()
        self.kaynak_turu = "sistem"
        return k

    def baslat(self) -> dict[str, Any]:
        self._kaynak = self._kaynak_ac()
        if self.tamamen_turkce and self.ayirici is not None and self.kaynak_turu in ("surec", "giris"):
            self._oturum = OturumSesi(self.pid)
            self.tamamen_aktif = True        # Remote Play: kalibrasyon döngüde (TamamenKalibrasyon)
            if self.kaynak_turu == "giris" and self.pid:
                self._oturum.ayarla(0.0)     # kartın görüntü programının (OBS vb.) sesi kapanır; biz çalarız
        self._dur.clear()
        self._is = threading.Thread(target=self._dongu, daemon=True, name="isci-canli")
        self._is.start()
        neden = None
        if self.tamamen_turkce and not self.tamamen_aktif:
            neden = "surec_loopback_yok" if self.kaynak_turu != "surec" else "ayirici_yok"
        return {"kaynak": self.kaynak_turu, "tamamen_turkce": self.tamamen_aktif, "tamamen_neden": neden}

    def durdur(self) -> None:
        self._dur.set()
        if self._oturum is not None:
            self._oturum.geri_ac()
            self._oturum = None
        self.tamamen_aktif = False
        if self._arka_oynatici is not None:
            self._arka_oynatici.kapat()
            self._arka_oynatici = None
        if self._is is not None:
            self._is.join(timeout=2)
        if self._kaynak is not None:
            self._kaynak.kapat()
            self._kaynak = None

    def _dongu(self) -> None:
        from .mantik import AkisAyirici, UyarlamaliVAD
        kal = TamamenKalibrasyon() if self.tamamen_aktif and self.kaynak_turu == "surec" else None
        akis = AkisAyirici(self._olcerek_ayir, SR, ARKA_BAGLAM_SN) if self.ayirici is not None else None
        vad = UyarlamaliVAD(SR)
        try:
            while not self._dur.is_set():
                blok = self._kaynak.oku()
                arka_cal = self.tamamen_aktif
                if kal is not None and self.tamamen_aktif:
                    karar = kal.besle(blok, self._oturum)
                    if karar == "basarisiz":
                        self._tamamen_birak("tamamen_turkce_olculemedi")
                        kal = None
                    elif karar in ("once", "telafi"):
                        self.gonder({"olay": "gunluk", "seviye": "bilgi", "kod": "tamamen_turkce_hazir", "mod": karar})
                    if kal is not None and not kal.bitti:
                        arka_cal = False                 # ölçüm sürerken arka plan çalınmaz
                    elif kal is not None:
                        blok = blok * kal.kazanc         # kısılmış sesi görüyorsak geri büyüt
                if akis is not None:
                    try:
                        konusma, arka = akis.besle(blok)
                    except Exception as e:   # noqa: BLE001 — ayıramazsak ham sesle devam
                        log.info("canlı ayırma başarısız: %s", type(e).__name__)
                        konusma, arka = blok, blok
                    if arka_cal:
                        self._arka_ekle(arka)
                else:
                    konusma = blok
                sonuc = vad.besle(konusma, blok)
                if sonuc is None:
                    continue
                k, h = sonuc
                olay: dict[str, Any] = {"olay": "parca", "sr": SR, "sure_sn": len(h) / SR,
                                        "kaynak": self.kaynak_turu, "an": time.monotonic(), "pcm": protokol.pcm_kodla(h)}
                if akis is not None:
                    olay["temiz"] = protokol.pcm_kodla(k)
                self.gonder(olay)
        except Exception as e:   # noqa: BLE001 — aygıt koptu vb.
            log.warning("Canlı yakalama durdu: %s", e)
            self.gonder({"olay": "canli_hata", "hata": "dublaj_ses_kaynagi", "ayrinti": type(e).__name__})

    def _olcerek_ayir(self, pcm: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
        t0 = time.monotonic()
        k, a = self.ayirici(pcm, sr)
        self.arka_ms.append((time.monotonic() - t0) * 1000)
        if len(self.arka_ms) == self.arka_ms.maxlen:
            self.gonder({"olay": "olcum", "ayirma_ms": round(float(np.median(self.arka_ms)), 1),
                         "blok_ms": int(len(pcm) and BLOK * 1000 / SR)})
            self.arka_ms.clear()
        return k, a

    def _arka_ekle(self, arka: np.ndarray) -> None:
        try:
            if self._arka_oynatici is None:
                self._arka_oynatici = ArkaOynatici()
            self._arka_oynatici.ekle(np.asarray(arka, dtype=np.float32))
        except Exception as e:   # noqa: BLE001
            log.info("arka plan çalınamadı: %s", type(e).__name__)

    def _tamamen_birak(self, neden: str) -> None:
        if self._oturum is not None:
            self._oturum.geri_ac()
            self._oturum = None
        self.tamamen_aktif = False
        self.gonder({"olay": "gunluk", "seviye": "uyari", "mesaj": neden, "kod": "tamamen_turkce_kapandi"})


class SiraliOynatici:
    """Parçaları arka arkaya, boşluksuz çalan çıkış akışı (akışlı seslendirme için)."""

    def __init__(self, sr: int) -> None:
        import sounddevice as sd
        self._tampon = np.zeros(0, dtype=np.float32)
        self._kilit = threading.Lock()
        self._akis = sd.OutputStream(samplerate=sr, channels=1, dtype="float32", callback=self._geri,
                                     latency="low")
        self._akis.start()

    def ekle(self, pcm: np.ndarray) -> None:
        with self._kilit:
            self._tampon = np.concatenate([self._tampon, pcm.astype(np.float32)])

    def bitti(self) -> bool:
        with self._kilit:
            return len(self._tampon) == 0

    def _geri(self, cikis: Any, kare: int, zaman: Any, durum: Any) -> None:
        with self._kilit:
            n = min(kare, len(self._tampon))
            cikis[:n, 0] = self._tampon[:n]
            cikis[n:, 0] = 0.0
            self._tampon = self._tampon[n:]

    def kapat(self) -> None:
        try:
            time.sleep(0.1)
            self._akis.stop()
            self._akis.close()
        except Exception:   # noqa: BLE001
            pass


class ArkaOynatici:
    """Kesintisiz çalan ayrı bir çıkış akışı (Türkçe sesin `sd.play`ini kesmez)."""

    def __init__(self) -> None:
        import sounddevice as sd
        self._tampon = np.zeros(0, dtype=np.float32)
        self._kilit = threading.Lock()
        self._akis = sd.OutputStream(samplerate=SR, channels=1, dtype="float32", callback=self._geri)
        self._akis.start()

    def ekle(self, pcm: np.ndarray) -> None:
        with self._kilit:
            self._tampon = np.concatenate([self._tampon[-SR * 6:], pcm])

    def _geri(self, cikis: Any, kare: int, zaman: Any, durum: Any) -> None:
        with self._kilit:
            n = min(kare, len(self._tampon))
            cikis[:n, 0] = self._tampon[:n]
            cikis[n:, 0] = 0.0
            self._tampon = self._tampon[n:]

    def kapat(self) -> None:
        try:
            self._akis.stop()
            self._akis.close()
        except Exception:   # noqa: BLE001
            pass


def oynat(pcm: np.ndarray, sr: int, seviye: float, kis: float, pid: int | None, canli: Any, is_: Any) -> dict[str, Any]:
    """Türkçe sesi varsayılan ÇIKIŞ aygıtından çalar; çalarken oyunun sesini `kis` oranına indirir."""
    try:
        import sounddevice as sd
    except (ImportError, OSError) as e:
        from .sunucu import IsciHatasi
        raise IsciHatasi("dublaj_cikis_yok", type(e).__name__) from e
    veri = np.clip(pcm * seviye, -1.0, 1.0).astype(np.float32)
    tamamen = bool(canli is not None and getattr(canli, "tamamen_aktif", False))
    oturum = OturumSesi(pid) if (kis < 1.0 and not tamamen and sys.platform == "win32") else None
    if oturum:
        oturum.kis(kis)
    try:
        sd.play(veri, sr)
        bitis = time.monotonic() + len(veri) / sr + 0.2
        while time.monotonic() < bitis:
            if is_.iptal.is_set():
                sd.stop()
                break
            time.sleep(0.05)
    finally:
        if oturum:
            oturum.geri_ac()
    return {"sure_sn": len(veri) / sr}


class TamamenKalibrasyon:
    """"Tamamen Türkçe"nin ölçümü: process loopback, oyunun ses oturumu kısılınca da sesi görüyor mu?

    1) Oturum açıkken ~1,5 sn sesli ortalama düzey ölçülür (oyun sessizse beklenir).
    2) Oturum 0'a çekilir, ~1,5 sn daha ölçülür.
    - Düzey korunduysa (oran > 0,3): yakalama kısmadan ÖNCE alınıyor → oyun tamamen susar, kazanç 1.
    - Düzey düştüyse: oturum −30 dB'e (0,03) çekilir ve yakalanan ses 1/0,03 ile büyütülür
      (float yakalama hassasiyet kaybetmez); oyunun kendi sesi çok kısık bir iz olarak kalır.
    - 20 sn içinde ölçülecek ses yoksa ya da oran anlamsızsa "basarisiz" → "kıs" moduna dönülür.
    """

    def __init__(self, sr: int = SR, saat: Callable[[], float] = time.monotonic) -> None:
        self.sr = sr
        self.saat = saat
        self.evre = "acik"
        self.bitti = False
        self.kazanc = 1.0
        self.mod: str | None = None
        self._acik: list[float] = []
        self._kapali: list[float] = []
        self._bas = saat()
        self._evre_sn = 0.0

    def basla(self, oturum: Any) -> None:
        self._bas = self.saat()

    def besle(self, blok: np.ndarray, oturum: Any) -> str | None:
        if self.bitti:
            return None
        r = float(np.sqrt(np.mean(np.square(blok, dtype=np.float64)))) if len(blok) else 0.0
        sure = len(blok) / self.sr
        if self.evre == "acik":
            if r > 2e-3:
                self._acik.append(r)
                self._evre_sn += sure
            if self._evre_sn >= KALIBRASYON_SN:
                oturum.ayarla(0.0)
                self.evre, self._evre_sn = "kapali", 0.0
            elif self.saat() - self._bas > 20.0:
                return "basarisiz"
            return None
        self._kapali.append(r)
        self._evre_sn += sure
        if self._evre_sn < KALIBRASYON_SN:
            return None
        once = float(np.median(self._acik)) if self._acik else 0.0
        sonra = float(np.median(self._kapali)) if self._kapali else 0.0
        oran = sonra / once if once > 0 else 0.0
        if oran > 0.3:
            self.mod, self.kazanc = "once", 1.0
        else:
            oturum.ayarla(TELAFI_SES)
            self.mod, self.kazanc = "telafi", 1.0 / TELAFI_SES
        self.bitti = True
        return self.mod
