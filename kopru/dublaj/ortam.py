# SPDX-License-Identifier: AGPL-3.0-only
"""Dublaj paketi: ayrı çalışma ortamının indirilip kurulması (PROTOKOL 14.1).

Ana program küçük kalsın diye torch/chatterbox/faster-whisper ana pakette YOKTUR. Kullanıcı açıkça
onaylarsa bu modül şunları kendi klasörüne kurar: bağımsız bir Python, (Windows'ta) ffmpeg, pip
paketleri ve ses modelleri. Her şey dışarıdan verilebilir (indirici, komut çalıştırıcı, işçi
denetimi): testlerde sahteleriyle ağsız sınanır.

Güvenlik: yalnız `https` ve izinli adresler; arşivler SHA256 ile doğrulanmadan açılmaz; açarken
mutlak yol, `..`, dışarıyı gösteren bağlantı ve aygıt dosyası reddedilir.
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import logging
import os
import platform
import posixpath
import re
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Awaitable, Callable

log = logging.getLogger("kopru.dublaj.ortam")

MANIFEST_SURUMU = "1"
ASAMALAR = ("python", "ffmpeg", "paketler", "modeller", "denetim")
IZINLI_ADRESLER = {"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"}
YENIDEN_DENEME = 3
PARCA = 1 << 20   # indirmede okuma boyu (1 MB)


@dataclass(frozen=True)
class Arsiv:
    url: str
    sha256: str
    boyut_mb: int
    kok: str            # arşivin içindeki üst klasör (ör. "python")
    hedef: str          # paket klasöründeki yeri (ör. "python")


_PBS = "https://github.com/astral-sh/python-build-standalone/releases/download/20261110/"
PYTHON_ARSIVLERI: dict[tuple[str, str], Arsiv] = {
    ("win32", "x86_64"): Arsiv(_PBS + "cpython-3.13.18%2B20261110-x86_64-pc-windows-msvc-install_only_stripped.tar.gz",
                               "2e0fed09d48989f64c9305da9ff2d37a41c0d13ab2aa6283405b2b620dfbf805", 22, "python", "python"),
    ("linux", "x86_64"): Arsiv(_PBS + "cpython-3.13.18%2B20261110-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz",
                               "f2d2199eb25880e07863b391cf7124e7ffa1338b0d65600dfcec117c4223a7fb", 34, "python", "python"),
    ("darwin", "arm64"): Arsiv(_PBS + "cpython-3.13.18%2B20261110-aarch64-apple-darwin-install_only_stripped.tar.gz",
                               "7a2384641584ab9984221fcb0fc9265df465922af71be71410529e2a9c3f0540", 25, "python", "python"),
}
FFMPEG_WINDOWS = Arsiv("https://github.com/GyanD/codexffmpeg/releases/download/9.1/ffmpeg-9.1-essentials_build.zip",
                       "b9bbbb3acece000cbeec994f856649354e52c773807841e78908374b24d658fd", 114,
                       "ffmpeg-9.1-essentials_build", "ffmpeg")
TORCH_DIZINI = "https://download.pytorch.org/whl/cu124"
TORCH = ["torch==2.6.0", "torchaudio==2.6.0"]
PAKETLER = ["chatterbox-tts==0.1.7", "faster-whisper==1.2.1", "demucs==4.1.0", "pocket-tts==4.0.1",
            "soundfile==0.14.0", "sounddevice==0.5.6", "soundcard==0.4.6", "huggingface-hub",
            "setuptools<81"]   # resemble-perth (Chatterbox filigranı) hâlâ pkg_resources ister
PAKETLER_WINDOWS = ["pycaw==20260927", "comtypes==1.5.0", "psutil==7.2.2"]
PAKETLER_DIGER = ["imageio-ffmpeg==0.8.1"]
# Yaklaşık boyutlar (MB): panelde "~X GB indirilecek" demek için
PAKET_INDIRME_MB = {"cuda": 3300, "cpu": 900}
MODEL_INDIRME_MB = 3200 + 1600 + 330       # chatterbox çok dilli + whisper turbo + demucs-ft
DISK_CARPANI = 1.45                        # açılmış hâli indirmeden büyüktür


class OrtamHatasi(Exception):
    def __init__(self, kod: str, ayrinti: str = "") -> None:
        super().__init__(kod)
        self.kod = kod
        self.ayrinti = ayrinti


class Iptal(Exception):
    """Kullanıcı kurulumu durdurdu."""


# ---------- konum ve platform ----------

def ortam_dizini() -> Path:
    ozel = os.environ.get("KOPRU_DUBLAJ_ORTAMI")
    if ozel:
        return Path(ozel)
    if sys.platform == "win32":
        taban = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(taban) / "AltYaziKoprusu" / "dublaj-ortami"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AltyaziKoprusu" / "dublaj-ortami"
    taban = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(taban) / "altyazikoprusu" / "dublaj-ortami"


def platform_anahtari(sistem: str | None = None, makine: str | None = None) -> tuple[str, str]:
    sistem = sistem or sys.platform
    m = (makine or platform.machine() or "").lower()
    m = {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64"}.get(m, m)
    return ("linux" if sistem.startswith("linux") else sistem), m


def gelistirici_ortami() -> bool:
    """Programı çalıştıran Python'da dublaj paketleri zaten var mı (paketli exe'de asla)."""
    if getattr(sys, "frozen", False):
        return False
    try:
        return all(importlib.util.find_spec(ad) is not None for ad in ("torch", "chatterbox", "faster_whisper"))
    except (ImportError, ValueError):
        return False


# ---------- güvenli indirme ----------

def adres_izinli(url: str, ek: set[str] | None = None) -> bool:
    p = urllib.parse.urlparse(url)
    return p.scheme == "https" and (p.hostname or "") in (IZINLI_ADRESLER | (ek or set()))


class _GuvenliYonlendirme(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        if not adres_izinli(newurl):
            raise OrtamHatasi("dublaj_paket_indirme", f"izinsiz yönlendirme: {urllib.parse.urlparse(newurl).hostname}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _ac(url: str, bas: int) -> Any:
    """Gerçek HTTP: `bas` > 0 ise Range ile devam ister. Dönen nesnede `.status`, `.headers`, `.read(n)`."""
    istek = urllib.request.Request(url, headers={"User-Agent": "AltYaziKoprusu-dublaj"})
    if bas:
        istek.add_header("Range", f"bytes={bas}-")
    return urllib.request.build_opener(_GuvenliYonlendirme).open(istek, timeout=60)


Acici = Callable[[str, int], Any]


def indir(url: str, hedef: Path, sha256: str, ilerleme: Callable[[int, int], None], iptal: threading.Event,
          acici: Acici = _ac, uyku: Callable[[float], None] = time.sleep, beklenen: int = 0) -> Path:
    """`url`yi `hedef`e indirir; yarım `.part` varsa kaldığı yerden sürer; SHA256 tutmazsa siler ve hata verir."""
    if not adres_izinli(url):
        raise OrtamHatasi("dublaj_paket_indirme", "izinsiz adres")
    hedef.parent.mkdir(parents=True, exist_ok=True)
    if hedef.exists() and _sha256(hedef) == sha256:
        return hedef
    part = hedef.with_name(hedef.name + ".part")
    son_hata: Exception | None = None
    for deneme in range(YENIDEN_DENEME):
        if iptal.is_set():
            raise Iptal()
        bas = part.stat().st_size if part.exists() else 0
        try:
            yanit = acici(url, bas)
            with yanit:
                durum = int(getattr(yanit, "status", 200) or 200)
                if bas and durum != 206:          # sunucu devam etmeyi desteklemedi: baştan
                    bas = 0
                uzunluk = int(yanit.headers.get("Content-Length") or 0)
                toplam = (bas + uzunluk) if uzunluk else beklenen
                with open(part, "ab" if bas else "wb") as f:
                    inen = bas
                    while True:
                        if iptal.is_set():
                            raise Iptal()
                        veri = yanit.read(PARCA)
                        if not veri:
                            break
                        f.write(veri)
                        inen += len(veri)
                        ilerleme(inen, toplam)
            break
        except Iptal:
            raise
        except OrtamHatasi:
            raise
        except Exception as e:     # ağ kopması: artan beklemeyle yeniden dene (yarım dosya korunur)
            son_hata = e
            log.info("İndirme kesildi (%s), yeniden denenecek", type(e).__name__)
            if deneme < YENIDEN_DENEME - 1:
                uyku(2.0 * (deneme + 1))
    else:
        raise OrtamHatasi("dublaj_paket_indirme", f"{type(son_hata).__name__}: {son_hata}")
    if _sha256(part) != sha256:
        part.unlink(missing_ok=True)
        raise OrtamHatasi("dublaj_paket_dogrulama", hedef.name)
    os.replace(part, hedef)
    return hedef


def _sha256(yol: Path) -> str:
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for blok in iter(lambda: f.read(PARCA), b""):
            h.update(blok)
    return h.hexdigest()


# ---------- güvenli açma ----------

def _guvenli_ad(ad: str) -> PurePosixPath:
    ad = ad.replace("\\", "/")
    p = PurePosixPath(ad)
    if not ad or ad.startswith("/") or re.match(r"^[A-Za-z]:", ad) or any(k == ".." for k in p.parts):
        raise OrtamHatasi("dublaj_paket_bozuk", f"güvensiz yol: {ad[:80]}")
    return p


def _kok_cikar(p: PurePosixPath, kok: str) -> PurePosixPath | None:
    """Arşivdeki `kok/...` yolunu `...` yapar; kökün dışındakiler atlanır."""
    if not p.parts or p.parts[0] != kok:
        return None
    return PurePosixPath(*p.parts[1:]) if len(p.parts) > 1 else PurePosixPath(".")


def guvenli_ac(arsiv: Path, hedef: Path, kok: str) -> None:
    """tar.gz / zip'i `hedef`e açar (üst `kok` klasörü atılarak). Güvensiz öğe → OrtamHatasi."""
    gecici = hedef.with_name(hedef.name + ".aciliyor")
    shutil.rmtree(gecici, ignore_errors=True)
    gecici.mkdir(parents=True)
    try:
        if arsiv.name.endswith(".zip"):
            with zipfile.ZipFile(arsiv) as z:
                for bilgi in z.infolist():
                    p = _guvenli_ad(bilgi.filename)
                    ic = _kok_cikar(p, kok)
                    if ic is None or str(ic) == ".":
                        continue
                    if (bilgi.external_attr >> 16) & 0o170000 == 0o120000:
                        raise OrtamHatasi("dublaj_paket_bozuk", "zip içinde bağlantı")
                    yol = gecici / ic
                    if bilgi.is_dir():
                        yol.mkdir(parents=True, exist_ok=True)
                        continue
                    yol.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(bilgi) as kaynak, open(yol, "wb") as f:
                        shutil.copyfileobj(kaynak, f)
        else:
            with tarfile.open(arsiv, "r:*") as t:
                for uye in t.getmembers():
                    p = _guvenli_ad(uye.name)
                    ic = _kok_cikar(p, kok)
                    if ic is None or str(ic) == ".":
                        continue
                    yol = gecici / ic
                    if uye.isdir():
                        yol.mkdir(parents=True, exist_ok=True)
                    elif uye.isfile():
                        yol.parent.mkdir(parents=True, exist_ok=True)
                        kaynak = t.extractfile(uye)
                        assert kaynak is not None
                        with kaynak, open(yol, "wb") as f:
                            shutil.copyfileobj(kaynak, f)
                        if uye.mode & 0o111:
                            os.chmod(yol, 0o755)
                    elif uye.issym():
                        # yalnız arşivin İÇİNİ gösteren göreli bağlantılar (ör. bin/python3 -> python3.13)
                        bag = posixpath.normpath(posixpath.join(posixpath.dirname(uye.name), uye.linkname))
                        if (uye.linkname.startswith("/") or bag.startswith("..")
                                or _kok_cikar(PurePosixPath(bag), kok) is None):
                            raise OrtamHatasi("dublaj_paket_bozuk", "dışarıyı gösteren bağlantı")
                        yol.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            os.symlink(uye.linkname, yol)
                        except OSError:     # Windows'ta bağlantı izni yoksa: kopya
                            pass
                    else:
                        raise OrtamHatasi("dublaj_paket_bozuk", "desteklenmeyen arşiv öğesi")
        shutil.rmtree(hedef, ignore_errors=True)
        os.replace(gecici, hedef)
    finally:
        shutil.rmtree(gecici, ignore_errors=True)


# ---------- komut çalıştırma (pip) ----------

Calistirici = Callable[[list[str], Callable[[str], None], threading.Event, dict[str, str] | None], int]


def calistir(komut: list[str], satir_cb: Callable[[str], None], iptal: threading.Event,
             env: dict[str, str] | None = None) -> int:
    bayrak = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    s = subprocess.Popen(komut, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         text=True, encoding="utf-8", errors="replace", creationflags=bayrak,
                         env={**os.environ, **(env or {})})
    assert s.stdout is not None

    def bekci() -> None:
        iptal.wait()
        if s.poll() is None:
            s.terminate()
    threading.Thread(target=bekci, daemon=True).start()
    for satir in s.stdout:
        satir_cb(satir.rstrip())
    kod = s.wait()
    if iptal.is_set():
        raise Iptal()
    return kod


_PIP_INDIR = re.compile(r"Downloading\s+(\S+)\s+\(([\d.]+)\s*(kB|MB|GB)\)")
_PIP_ILERLEME = re.compile(r"Progress\s+(\d+)\s+of\s+(\d+)")


class PipIlerleme:
    """pip `--progress-bar raw` çıktısından kabaca indirilen MB'ı izler."""

    def __init__(self, beklenen_mb: float) -> None:
        self.beklenen = max(1.0, beklenen_mb)
        self.biten_mb = 0.0
        self.simdiki_mb = 0.0
        self.simdiki_oran = 0.0
        self.son_satir = ""

    def satir(self, s: str) -> None:
        m = _PIP_INDIR.search(s)
        if m:
            self.biten_mb += self.simdiki_mb * 1.0
            carp = {"kB": 1 / 1024, "MB": 1.0, "GB": 1024.0}[m.group(3)]
            self.simdiki_mb, self.simdiki_oran = float(m.group(2)) * carp, 0.0
            self.son_satir = m.group(1)
            return
        m = _PIP_ILERLEME.search(s)
        if m and int(m.group(2)):
            self.simdiki_oran = int(m.group(1)) / int(m.group(2))

    def yuzde(self) -> float:
        inen = self.biten_mb + self.simdiki_mb * self.simdiki_oran
        return min(99.0, 100.0 * inen / self.beklenen)


# ---------- durum makinesi ----------

@dataclass
class _Asama:
    kod: str
    durum: str = "bekliyor"     # bekliyor | suruyor | bitti | hata
    yuzde: float = 0.0


@dataclass
class OrtamBilgisi:
    durum: str = "yok"          # yok | kuruluyor | hazir | hata | iptal | kaldiriliyor
    asama: str | None = None
    mesaj: str | None = None
    hata: str | None = None
    ayrinti: str | None = None
    asamalar: dict[str, _Asama] = field(default_factory=dict)


ModelIndirici = Callable[[Callable[[float, str], None]], Awaitable[None]]
IsciDenetci = Callable[[], Awaitable[dict[str, Any]]]


class DublajOrtami:
    """Dublaj paketinin kurulumu / kaldırılması ve işçinin hangi Python ile çalışacağı."""

    def __init__(self, kok: Path | None = None, acici: Acici = _ac, calistirici: Calistirici = calistir,
                 platform_: tuple[str, str] | None = None, gelistirici: bool | None = None,
                 uyku: Callable[[float], None] = time.sleep, cuda_var: Callable[[], bool] | None = None) -> None:
        self._kok = kok
        self.acici = acici
        self.calistirici = calistirici
        self.platform = platform_ or platform_anahtari()
        self.gelistirici = gelistirici_ortami() if gelistirici is None else gelistirici
        self.uyku = uyku
        self.cuda_var = cuda_var or _nvidia_var
        self.model_indirici: ModelIndirici | None = None     # DublajYonetici bağlar (işçi üzerinden)
        self.isci_denetci: IsciDenetci | None = None
        self.bilgi_ = OrtamBilgisi(asamalar={k: _Asama(k) for k in ASAMALAR})
        self.onarim: dict[str, Any] = {"durum": "yok", "mesaj": None}
        self._iptal = threading.Event()
        self._gorev: asyncio.Task | None = None
        self._durum_oku()

    # -- yollar --
    @property
    def kok(self) -> Path:
        return self._kok or ortam_dizini()

    def destek(self) -> tuple[bool, str | None]:
        if self.gelistirici:
            return True, None
        if self.platform not in PYTHON_ARSIVLERI:
            return False, "dublaj_paket_desteklenmiyor"
        return True, None

    def python_yolu(self) -> Path:
        if self.gelistirici:
            return Path(sys.executable)
        p = self.kok / "python"
        return p / "python.exe" if self.platform[0] == "win32" else p / "bin" / "python3"

    def ffmpeg_yolu(self) -> str | None:
        if self.platform[0] == "win32" and not self.gelistirici:
            y = self.kok / "ffmpeg" / "bin" / "ffmpeg.exe"
            return str(y) if y.exists() else None
        return shutil.which("ffmpeg")    # diğerlerinde işçi imageio-ffmpeg'i kendisi bulur

    def model_dizini(self) -> Path:
        return self.kok / "modeller"

    def _durum_yolu(self) -> Path:
        return self.kok / "durum.json"

    def _durum_oku(self) -> None:
        try:
            d = json.loads(self._durum_yolu().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        if not isinstance(d, dict) or d.get("surum") != MANIFEST_SURUMU:
            d = {}
        biten = d.get("asamalar") if isinstance(d.get("asamalar"), dict) else {}
        for k, a in self.bilgi_.asamalar.items():
            if biten.get(k) == "bitti":
                a.durum, a.yuzde = "bitti", 100.0
        if self.gelistirici:
            for k in ("python", "ffmpeg", "paketler"):
                self.bilgi_.asamalar[k].durum, self.bilgi_.asamalar[k].yuzde = "bitti", 100.0
        if self.kurulu():
            self.bilgi_.durum = "hazir"

    def _durum_yaz(self) -> None:
        self.kok.mkdir(parents=True, exist_ok=True)
        veri = {"surum": MANIFEST_SURUMU,
                "asamalar": {k: a.durum for k, a in self.bilgi_.asamalar.items() if a.durum == "bitti"}}
        gecici = self._durum_yolu().with_suffix(".tmp")
        gecici.write_text(json.dumps(veri), encoding="utf-8")
        os.replace(gecici, self._durum_yolu())

    def kurulu(self) -> bool:
        """Program parçaları hazır mı (python+ffmpeg+paketler). Modeller ilk kullanımda da inebilir."""
        a = self.bilgi_.asamalar
        if not all(a[k].durum == "bitti" for k in ("python", "ffmpeg", "paketler")):
            return False
        return self.gelistirici or self.python_yolu().exists()

    def tamamen_hazir(self) -> bool:
        return self.kurulu() and all(a.durum == "bitti" for a in self.bilgi_.asamalar.values())

    # -- boyut --
    def indirme_mb(self) -> int:
        a = self.bilgi_.asamalar
        mb = 0
        cuda = self.platform[0] != "darwin" and self.cuda_var()
        if a["python"].durum != "bitti":
            mb += PYTHON_ARSIVLERI.get(self.platform, Arsiv("", "", 30, "", "")).boyut_mb
        if a["ffmpeg"].durum != "bitti" and self.platform[0] == "win32":
            mb += FFMPEG_WINDOWS.boyut_mb
        if a["paketler"].durum != "bitti":
            mb += PAKET_INDIRME_MB["cuda" if cuda else "cpu"]
        if a["modeller"].durum != "bitti":
            mb += MODEL_INDIRME_MB
        return mb

    def bilgi(self) -> dict[str, Any]:
        b = self.bilgi_
        destek, neden = self.destek()
        asamalar = [{"kod": a.kod, "durum": a.durum, "yuzde": round(a.yuzde)} for a in b.asamalar.values()]
        toplam = sum(a.yuzde for a in b.asamalar.values()) / len(b.asamalar)
        ind = self.indirme_mb()
        return {"durum": b.durum, "kurulu": self.kurulu(), "tamam": self.tamamen_hazir(),
                "gelistirici": self.gelistirici, "indirme_mb": ind, "disk_mb": int(ind * DISK_CARPANI),
                "asama": b.asama, "asamalar": asamalar, "yuzde": round(toplam), "mesaj": b.mesaj,
                "hata": b.hata or neden, "ayrinti": b.ayrinti, "konum": str(self.kok), "destek": destek,
                "onarim": dict(self.onarim)}

    # -- kurulum --
    def kuruluyor(self) -> bool:
        return self._gorev is not None and not self._gorev.done()

    def kur_baslat(self) -> None:
        if self.kuruluyor():
            return
        self._iptal = threading.Event()
        self._gorev = asyncio.get_running_loop().create_task(self.kur())

    def iptal(self) -> None:
        self._iptal.set()
        if self._gorev is not None and not self._gorev.done():
            self._gorev.cancel()

    async def bekle(self) -> None:
        if self._gorev:
            await asyncio.gather(self._gorev, return_exceptions=True)

    async def kur(self) -> None:
        b = self.bilgi_
        destek, neden = self.destek()
        if not destek:
            b.durum, b.hata = "hata", neden
            return
        b.durum, b.hata, b.ayrinti, b.mesaj = "kuruluyor", None, None, None
        adimlar: dict[str, Callable[[], Awaitable[None]]] = {
            "python": self._python, "ffmpeg": self._ffmpeg, "paketler": self._paketler,
            "modeller": self._modeller, "denetim": self._denetim}
        try:
            for kod in ASAMALAR:
                a = b.asamalar[kod]
                if a.durum == "bitti":
                    continue
                b.asama, a.durum, a.yuzde = kod, "suruyor", 0.0
                await adimlar[kod]()
                a.durum, a.yuzde = "bitti", 100.0
                self._durum_yaz()
            b.durum, b.asama = "hazir", None
        except (Iptal, asyncio.CancelledError):
            if b.asama:
                b.asamalar[b.asama].durum = "bekliyor"
            b.durum, b.asama = "iptal", None
        except OrtamHatasi as e:
            if b.asama:
                b.asamalar[b.asama].durum = "hata"
            b.durum, b.hata, b.ayrinti = "hata", e.kod, e.ayrinti[:300]
            log.warning("Dublaj paketi kurulamadı: %s %s", e.kod, e.ayrinti)
        except Exception as e:   # beklenmeyen: program çökmesin
            if b.asama:
                b.asamalar[b.asama].durum = "hata"
            b.durum, b.hata, b.ayrinti = "hata", "dublaj_paket_hata", f"{type(e).__name__}: {e}"[:300]
            log.exception("Dublaj paketi kurulumu çöktü")

    def _ilerle(self, kod: str) -> Callable[[int, int], None]:
        def cb(inen: int, toplam: int) -> None:
            if toplam > 0:
                self.bilgi_.asamalar[kod].yuzde = min(99.0, 100.0 * inen / toplam)
        return cb

    async def _arsiv_kur(self, kod: str, arsiv: Arsiv) -> None:
        ad = urllib.parse.unquote(arsiv.url.rsplit("/", 1)[1])
        yol = self.kok / "indirilen" / ad
        await asyncio.to_thread(indir, arsiv.url, yol, arsiv.sha256, self._ilerle(kod), self._iptal,
                                self.acici, self.uyku, arsiv.boyut_mb << 20)
        await asyncio.to_thread(guvenli_ac, yol, self.kok / arsiv.hedef, arsiv.kok)
        yol.unlink(missing_ok=True)       # açıldıktan sonra arşive gerek yok

    async def _python(self) -> None:
        await self._arsiv_kur("python", PYTHON_ARSIVLERI[self.platform])
        if not self.python_yolu().exists():
            raise OrtamHatasi("dublaj_paket_bozuk", "python bulunamadı")

    async def _ffmpeg(self) -> None:
        if self.platform[0] == "win32":
            await self._arsiv_kur("ffmpeg", FFMPEG_WINDOWS)

    def torch_onar_komutu(self) -> list[str]:
        """NVIDIA kart varken paketteki torch CUDA'sız kalmışsa (ör. kurulumda kart algılanamadı): yalnız torch
        ve torchaudio CUDA yapısıyla yeniden kurulur (diğer paketlere dokunulmaz)."""
        return [str(self.python_yolu()), "-E", "-s", "-m", "pip", "install", "--disable-pip-version-check",
                "--no-warn-script-location", "--progress-bar", "raw", "--force-reinstall", "--no-deps",
                *TORCH, "--index-url", TORCH_DIZINI]

    async def torch_onar(self) -> bool:
        """PROTOKOL 14.1: "Onar" — torch'u CUDA yapısıyla yeniden kurar. Dönen: başarılı mı."""
        if self.gelistirici or self.platform[0] == "darwin":
            return False
        self.onarim = {"durum": "suruyor", "mesaj": None}
        son: list[str] = []

        def satir(x: str) -> None:
            son.append(x)
            del son[:-40]
        kod = await asyncio.to_thread(self.calistirici, self.torch_onar_komutu(), satir, self._iptal,
                                      {"PIP_NO_INPUT": "1", "HF_HOME": str(self.model_dizini())})
        try:
            with open(self.kok / "kurulum.log", "a", encoding="utf-8") as f:
                f.write("--- torch onarımı ---\n" + "\n".join(son) + "\n")
        except OSError:
            pass
        self.onarim = {"durum": "bitti" if kod == 0 else "hata", "mesaj": None if kod == 0 else (son[-1] if son else f"çıkış {kod}")}
        log.info("torch CUDA onarımı: %s", self.onarim["durum"])
        return kod == 0

    def pip_komutlari(self) -> list[tuple[list[str], float]]:
        """(komut, beklenen MB) listesi. torch önce, sonra kalanlar torch sabitiyle."""
        py = str(self.python_yolu())
        temel = [py, "-E", "-s", "-m", "pip", "install", "--disable-pip-version-check", "--no-warn-script-location",
                 "--progress-bar", "raw", "--prefer-binary"]
        cuda = self.platform[0] != "darwin" and self.cuda_var()
        torch = temel + TORCH + (["--index-url", TORCH_DIZINI] if cuda else [])
        sabit = self.kok / "sabit.txt"
        ek = PAKETLER_WINDOWS if self.platform[0] == "win32" else PAKETLER_DIGER
        kalan = temel + PAKETLER + ek + ["--constraint", str(sabit)]
        return [(torch, 2600.0 if cuda else 250.0), (kalan, 650.0)]

    async def _paketler(self) -> None:
        self.kok.mkdir(parents=True, exist_ok=True)
        (self.kok / "sabit.txt").write_text("\n".join(TORCH) + "\n", encoding="utf-8")
        komutlar = self.pip_komutlari()
        toplam = sum(mb for _, mb in komutlar)
        onceki = 0.0
        gunluk = self.kok / "kurulum.log"
        for komut, mb in komutlar:
            iz = PipIlerleme(mb)
            a = self.bilgi_.asamalar["paketler"]
            son: list[str] = []

            def satir(s: str, iz: PipIlerleme = iz, onceki: float = onceki) -> None:
                iz.satir(s)
                son.append(s)
                del son[:-40]
                a.yuzde = min(99.0, 100.0 * (onceki + mb * iz.yuzde() / 100.0) / toplam)
                if iz.son_satir:
                    self.bilgi_.mesaj = iz.son_satir
            kod = await asyncio.to_thread(self.calistirici, komut, satir, self._iptal,
                                          {"PIP_NO_INPUT": "1", "HF_HOME": str(self.model_dizini())})
            with open(gunluk, "a", encoding="utf-8") as f:
                f.write("\n".join(son) + "\n")
            if kod != 0:
                raise OrtamHatasi("dublaj_paket_pip", (son[-1] if son else f"çıkış {kod}"))
            onceki += mb
        self.bilgi_.mesaj = None

    async def _modeller(self) -> None:
        if self.model_indirici is None:
            raise OrtamHatasi("dublaj_paket_hata", "model indirici yok")
        a = self.bilgi_.asamalar["modeller"]

        def cb(yuzde: float, mesaj: str) -> None:
            a.yuzde = min(99.0, yuzde)
            self.bilgi_.mesaj = mesaj or None
            if self._iptal.is_set():
                raise Iptal()
        await self.model_indirici(cb)
        self.bilgi_.mesaj = None

    async def _denetim(self) -> None:
        if self.isci_denetci is None:
            return
        bilgi = await self.isci_denetci()
        if not bilgi.get("anahtar_dogru", True):
            raise OrtamHatasi("dublaj_isci_hata", "işçi doğrulanamadı")

    # -- kaldırma --
    async def kaldir(self) -> None:
        self.iptal()
        await self.bekle()
        self.bilgi_.durum = "kaldiriliyor"
        kok = self.kok
        # yalnız BİZİM klasörümüz: adı "dublaj-ortami" olmalı ya da kullanıcı açıkça KOPRU_DUBLAJ_ORTAMI verdi
        if kok.name != "dublaj-ortami" and not os.environ.get("KOPRU_DUBLAJ_ORTAMI") and self._kok is None:
            raise OrtamHatasi("dublaj_paket_hata", "beklenmeyen klasör")
        await asyncio.to_thread(shutil.rmtree, kok, True)
        self.bilgi_ = OrtamBilgisi(asamalar={k: _Asama(k) for k in ASAMALAR})
        if self.gelistirici:
            self._durum_oku()


_NVIDIA_ONBELLEK: dict[str, Any] = {}


def _nvidia_var() -> bool:
    """CUDA'lı torch indirilmeli mi: NVIDIA ekran kartı var mı (nvidia-smi). Panel sık sorar: sonuç
    önbelleklenir (var: hep; yok: 10 dk), nvidia-smi her sorguda (uyuyan kartta saniyelerce) çalıştırılmaz."""
    simdi = time.monotonic()
    k = _NVIDIA_ONBELLEK.get("v")
    if k is not None and (k[0] or simdi - k[1] < 600):
        return k[0]
    try:
        from . import donanim
        d = donanim._nvidia_smi()
        var = d is not None and d.tur == "cuda"
    except Exception:
        var = False
    _NVIDIA_ONBELLEK["v"] = (var, simdi)
    return var
