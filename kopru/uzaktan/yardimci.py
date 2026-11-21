# SPDX-License-Identifier: AGPL-3.0-only
"""`ayk-uzaktan` yardımcısıyla konuşma (PROTOKOL §15.3–15.4): bulma, tek seferlik komutlar, akış kanalı."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("kopru.uzaktan")

ADI = "ayk-uzaktan.exe" if sys.platform == "win32" else "ayk-uzaktan"
SIHIR = b"AY"
BASLIK = 8
EN_BUYUK_CERCEVE = 64 * 1024 * 1024


class YardimciHatasi(Exception):
    """`kod` metinler.py anahtarıdır."""

    def __init__(self, kod: str, ayrinti: str | None = None) -> None:
        super().__init__(ayrinti or kod)
        self.kod = kod
        self.ayrinti = ayrinti


def yardimci_yolu() -> Path | None:
    """Yardımcının yeri: ortam değişkeni, PyInstaller paketi (_internal/uzaktan), programın yanı, geliştirme derlemesi."""
    adaylar: list[Path] = []
    ortam = os.environ.get("KOPRU_UZAKTAN_YARDIMCI")
    if ortam:
        adaylar.append(Path(ortam))
    paket = getattr(sys, "_MEIPASS", None)
    if paket:
        adaylar.append(Path(paket) / "uzaktan" / ADI)
    exe = Path(sys.executable).resolve().parent
    adaylar += [exe / "_internal" / "uzaktan" / ADI, exe / "uzaktan" / ADI]
    kok = Path(__file__).resolve().parents[2]
    adaylar += [kok / "build" / "uzaktan-cikti" / ADI, kok / "build" / "uzaktan-is" / "derleme" / ADI]
    for a in adaylar:
        if a.is_file():
            return a
    return None


def komut_satiri(komut: str, yol: Path | None = None) -> list[str]:
    yol = yol or yardimci_yolu()
    if yol is None:
        raise YardimciHatasi("ps5_yardimci_yok")
    return [str(yol), komut]


def _pencere_yok() -> dict[str, Any]:
    if sys.platform == "win32":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}
    return {}


def _json_satirlari(metin: str) -> list[dict[str, Any]]:
    out = []
    for satir in metin.splitlines():
        satir = satir.strip()
        if not satir.startswith("{"):
            continue
        try:
            v = json.loads(satir)
        except ValueError:
            continue
        if isinstance(v, dict):
            out.append(v)
    return out


def calistir(komut: str, girdi: dict[str, Any] | None, zaman_asimi: float,
             satir: Callable[[str], list[str]] | None = None) -> list[dict[str, Any]]:
    """Tek seferlik komut (`bul`, `uyandir`, `kaydet`, `ozdenetim`). Gizli değerler stdin'den gider.
    `satir`: komut satırı üretici (testlerde sahte yardımcı). Dönen: JSON olayları."""
    cmd = (satir or komut_satiri)(komut)
    veri = (json.dumps(girdi) + "\n") if girdi is not None else ""
    try:
        r = subprocess.run(cmd, input=veri.encode(), capture_output=True, timeout=zaman_asimi, **_pencere_yok())
    except subprocess.TimeoutExpired as e:
        raise YardimciHatasi("ps5_yanit_yok", f"{komut}: {zaman_asimi:.0f} sn") from e
    except OSError as e:
        raise YardimciHatasi("ps5_yardimci_yok", type(e).__name__) from e
    hata = r.stderr.decode("utf-8", "replace")
    if hata.strip():
        log.debug("ayk-uzaktan %s: %s", komut, hata.strip()[-2000:])
    return _json_satirlari(r.stdout.decode("utf-8", "replace"))


class CerceveCozucu:
    """`AY` + tür + 0 + uint32 uzunluk + veri. Bozuk veri gelirse sonraki `AY`'a atlar."""

    def __init__(self) -> None:
        self._tampon = bytearray()

    def besle(self, veri: bytes) -> list[tuple[str, bytes]]:
        self._tampon += veri
        out: list[tuple[str, bytes]] = []
        t = self._tampon
        while True:
            if len(t) < BASLIK:
                break
            if t[:2] != SIHIR:
                i = t.find(SIHIR, 1)
                del t[: (i if i >= 0 else len(t) - 1)]
                continue
            n = int.from_bytes(t[4:8], "little")
            if n > EN_BUYUK_CERCEVE:
                del t[:2]
                continue
            if len(t) < BASLIK + n:
                break
            tur = chr(t[2])
            out.append((tur, bytes(t[BASLIK:BASLIK + n])))
            del t[: BASLIK + n]
        return out


class Kare:
    """BGRA kare (diskte değil, bellekte)."""

    def __init__(self, genislik: int, yukseklik: int, bgra: bytes) -> None:
        self.genislik, self.yukseklik, self.bgra = genislik, yukseklik, bgra

    def resim(self) -> Any:
        from PIL import Image
        return Image.frombuffer("RGB", (self.genislik, self.yukseklik), self.bgra, "raw", "BGRX", 0, 1)


def kare_coz(veri: bytes) -> Kare | None:
    if len(veri) < 4:
        return None
    g, y = int.from_bytes(veri[0:2], "little"), int.from_bytes(veri[2:4], "little")
    if g == 0 or y == 0 or len(veri) - 4 != g * y * 4:
        return None
    return Kare(g, y, veri[4:])


class AkisSureci:
    """`ayk-uzaktan akis` süreci: olaylar, istek üzerine kareler, sürekli ses.

    Geri çağrılar okuyucu iş parçacığında gelir: `olay_cb(dict)`, `ses_cb(bytes)` (16 kHz mono s16le)."""

    def __init__(self, ayar: dict[str, Any], olay_cb: Callable[[dict[str, Any]], None],
                 ses_cb: Callable[[bytes], None] | None = None,
                 satir: Callable[[str], list[str]] | None = None) -> None:
        self.ayar = ayar
        self.olay_cb = olay_cb
        self.ses_cb = ses_cb
        self.satir = satir or komut_satiri
        self._surec: subprocess.Popen | None = None
        self._okuyucu: threading.Thread | None = None
        self._kare_kilit = threading.Lock()      # aynı anda tek kare isteği
        self._kare_olay = threading.Event()
        self._kare: Kare | None = None
        self._yazma = threading.Lock()
        self.bitti = threading.Event()

    def baslat(self) -> None:
        cmd = self.satir("akis")
        try:
            self._surec = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, bufsize=0, **_pencere_yok())
        except OSError as e:
            raise YardimciHatasi("ps5_yardimci_yok", type(e).__name__) from e
        self._yaz(json.dumps(self.ayar) + "\n")
        self._okuyucu = threading.Thread(target=self._oku, daemon=True, name="ps5-akis")
        self._okuyucu.start()
        threading.Thread(target=self._gunluk, daemon=True, name="ps5-gunluk").start()

    def _yaz(self, metin: str) -> bool:
        s = self._surec
        if s is None or s.stdin is None:
            return False
        with self._yazma:
            try:
                s.stdin.write(metin.encode())
                s.stdin.flush()
                return True
            except (OSError, ValueError):
                return False

    def _gunluk(self) -> None:
        s = self._surec
        if s is None or s.stderr is None:
            return
        for satir in iter(s.stderr.readline, b""):
            log.info("ayk-uzaktan: %s", satir.decode("utf-8", "replace").rstrip())

    def _oku(self) -> None:
        s = self._surec
        cozucu = CerceveCozucu()
        bitti_geldi = False
        try:
            assert s is not None and s.stdout is not None
            while True:
                veri = os.read(s.stdout.fileno(), 1 << 20)
                if not veri:
                    break
                for tur, govde in cozucu.besle(veri):
                    if tur == "J":
                        try:
                            olay = json.loads(govde.decode("utf-8"))
                        except ValueError:
                            continue
                        if olay.get("olay") == "bitti":
                            bitti_geldi = True
                        self.olay_cb(olay)
                    elif tur == "V":
                        self._kare = kare_coz(govde)
                        self._kare_olay.set()
                    elif tur == "S" and self.ses_cb is not None:
                        self.ses_cb(govde)
        except Exception:   # noqa: BLE001 — okuyucu ölürse süreç bitmiş sayılır
            log.exception("PS5 akış kanalı okunamadı")
        finally:
            if not bitti_geldi:
                self.olay_cb({"olay": "bitti", "neden": "diger", "ayrinti": "yardımcı süreç kapandı"})
            self.bitti.set()
            self._kare_olay.set()

    def kare(self, azami_genislik: int = 0, zaman_asimi: float = 3.0) -> Kare | None:
        """Son çözülmüş kareyi ister; henüz kare yoksa None."""
        with self._kare_kilit:
            if self.bitti.is_set():
                return None
            self._kare_olay.clear()
            self._kare = None
            if not self._yaz(f"kare {int(azami_genislik)}\n"):
                return None
            self._kare_olay.wait(zaman_asimi)
            return self._kare

    def giris_pin(self, pin: str) -> None:
        if pin.isdigit() and len(pin) == 4:
            self._yaz(f"giris_pin {pin}\n")

    def durdur(self, bekle: float = 5.0) -> None:
        s = self._surec
        if s is None:
            return
        self._yaz("dur\n")
        try:
            if s.stdin:
                s.stdin.close()
        except OSError:
            pass
        try:
            s.wait(timeout=bekle)
        except subprocess.TimeoutExpired:
            s.kill()
            try:
                s.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        self.bitti.set()
        self._kare_olay.set()

    def calisiyor(self) -> bool:
        return self._surec is not None and self._surec.poll() is None and not self.bitti.is_set()
