# SPDX-License-Identifier: AGPL-3.0-only
"""Ana program tarafı: dublaj işçisini başlatır ve onunla JSON satırlarıyla konuşur (PROTOKOL 14.2).

Ayrıca canlı dublajın parçalarını işçiye bağlayan bağdaştırıcılar: `IsciMotoru` (seslendirme),
`IsciSTT` (yazıya çevirme), `IsciSesKaynagi` (oyun sesini dinleme), `IsciCikis` (çalma + kısma).
İşçi yoksa ya da çökerse program ÇÖKMEZ: istekler `DublajHatasi` ile biter, sonraki istek yeniden başlatır.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import secrets
import shutil
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from .temel import DublajHatasi, IlerlemeCb

log = logging.getLogger("kopru.dublaj.isci")
EN_COK_SATIR = 64 * 1024 * 1024
MERHABA_SN = 240.0          # ilk açılışta torch + CUDA yüklemesi uzun sürebilir
YENIDEN_SINIR = 3           # dakikada en çok bu kadar başlatma
KOPYALANACAK = ["__init__.py", "ses/__init__.py", "dublaj/__init__.py", "dublaj/temel.py", "dublaj/dsp.py",
                "dublaj/isci/__init__.py", "dublaj/isci/__main__.py", "dublaj/isci/protokol.py",
                "dublaj/isci/sunucu.py", "dublaj/isci/mantik.py", "dublaj/isci/motorlar.py",
                "dublaj/isci/canli.py", "dublaj/isci/sahte.py"]


def pcm_kodla(pcm: Any) -> str:
    import numpy as np
    return base64.b64encode(np.ascontiguousarray(np.asarray(pcm, dtype="<f4").reshape(-1)).tobytes()).decode("ascii")


def pcm_coz(veri: str) -> Any:
    import numpy as np
    return np.frombuffer(base64.b64decode(veri), dtype="<f4").astype(np.float32)


def kod_kopyala(hedef_kok: Path, kaynak_kok: Path | None = None) -> Path:
    """İşçi kodunu dublaj paketine kopyalar (`<hedef>/kopru/...`); değişmeyen dosyaya dokunmaz."""
    kaynak_kok = kaynak_kok or Path(__file__).resolve().parent.parent
    for ad in KOPYALANACAK:
        k = kaynak_kok / ad
        h = hedef_kok / "kopru" / ad
        if not k.exists():
            continue
        if h.exists() and h.read_bytes() == k.read_bytes():
            continue
        h.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(k, h)
    return hedef_kok


@dataclass
class IsciKomutu:
    argv: list[str]
    cwd: str
    env: dict[str, str]
    gunluk: Path | None = None


async def _surec_baslat(k: IsciKomutu) -> Any:
    gunluk: Any = asyncio.subprocess.DEVNULL
    if k.gunluk is not None:
        try:
            k.gunluk.parent.mkdir(parents=True, exist_ok=True)
            if k.gunluk.exists() and k.gunluk.stat().st_size > 5_000_000:
                k.gunluk.unlink()
            gunluk = open(k.gunluk, "ab")   # noqa: SIM115 — süreç kapanana dek açık kalır
        except OSError:
            gunluk = asyncio.subprocess.DEVNULL
    bayrak = getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    return await asyncio.create_subprocess_exec(
        *k.argv, cwd=k.cwd, env=k.env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=gunluk, limit=EN_COK_SATIR, creationflags=bayrak)


class IsciIstemci:
    def __init__(self, komut_fn: Callable[[], IsciKomutu], baslatici: Callable[[IsciKomutu], Awaitable[Any]] = _surec_baslat,
                 saat: Callable[[], float] = time.monotonic) -> None:
        self.komut_fn = komut_fn
        self.baslatici = baslatici
        self.saat = saat
        self._surec: Any = None
        self._okuyucu: asyncio.Task | None = None
        self._bekleyen: dict[int, asyncio.Future] = {}
        self._ilerleme: dict[int, Callable[[float, str], None]] = {}
        self._no = 0
        self._dinleyiciler: list[Callable[[dict[str, Any]], None]] = []
        self._baslamalar: deque[float] = deque()
        self._kilit = asyncio.Lock()
        self.bilgi: dict[str, Any] | None = None
        self.son_hata: str | None = None

    # -- yaşam döngüsü --
    def calisiyor(self) -> bool:
        return self._surec is not None and self._surec.returncode is None and self.bilgi is not None

    def dinle(self, cb: Callable[[dict[str, Any]], None]) -> None:
        if cb not in self._dinleyiciler:
            self._dinleyiciler.append(cb)

    def birak(self, cb: Callable[[dict[str, Any]], None]) -> None:
        if cb in self._dinleyiciler:
            self._dinleyiciler.remove(cb)

    async def baslat(self) -> dict[str, Any]:
        async with self._kilit:
            if self.calisiyor():
                assert self.bilgi is not None
                return self.bilgi
            simdi = self.saat()
            while self._baslamalar and simdi - self._baslamalar[0] > 60.0:
                self._baslamalar.popleft()
            if len(self._baslamalar) >= YENIDEN_SINIR:
                raise DublajHatasi("dublaj_isci_hata", "işçi üst üste çöktü; bir dakika sonra yeniden denenecek")
            self._baslamalar.append(simdi)
            anahtar = secrets.token_hex(32)
            k = self.komut_fn()
            k.env = {**k.env, "KOPRU_ISCI_ANAHTAR": anahtar}
            try:
                self._surec = await self.baslatici(k)
            except (OSError, ValueError) as e:
                self.son_hata = "dublaj_isci_hata"
                raise DublajHatasi("dublaj_isci_hata", f"{type(e).__name__}: {e}") from e
            try:
                satir = await asyncio.wait_for(self._surec.stdout.readline(), MERHABA_SN)
                v = json.loads(satir.decode("utf-8")) if satir else {}
            except (asyncio.TimeoutError, ValueError, UnicodeDecodeError):
                v = {}
            if v.get("olay") != "merhaba" or not secrets.compare_digest(str(v.get("anahtar", "")), anahtar):
                await self._oldur()
                self.son_hata = "dublaj_isci_hata"
                raise DublajHatasi("dublaj_isci_hata", "işçi doğrulanamadı ya da açılmadı (isci.log'a bakın)")
            v.pop("anahtar", None)
            self.bilgi = v
            self.son_hata = None
            self._okuyucu = asyncio.get_running_loop().create_task(self._oku())
            return v

    async def _oku(self) -> None:
        surec = self._surec
        try:
            while True:
                satir = await surec.stdout.readline()
                if not satir:
                    break
                try:
                    v = json.loads(satir.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    continue
                if not isinstance(v, dict):
                    continue
                if "olay" in v:
                    if v["olay"] == "ilerleme" and v.get("no") in self._ilerleme:
                        try:
                            self._ilerleme[v["no"]](float(v.get("yuzde") or 0), str(v.get("mesaj") or ""))
                        except Exception:   # noqa: BLE001 — geri çağırma hatası okuyucuyu öldürmesin
                            log.debug("ilerleme geri çağırması başarısız", exc_info=True)
                    else:
                        for cb in list(self._dinleyiciler):
                            try:
                                cb(v)
                            except Exception:   # noqa: BLE001
                                log.exception("işçi olayı işlenemedi")
                    continue
                f = self._bekleyen.pop(v.get("no"), None)
                if f is not None and not f.done():
                    f.set_result(v)
        except asyncio.CancelledError:
            raise
        except Exception:   # noqa: BLE001
            log.exception("işçi okuyucusu durdu")
        finally:
            self.bilgi = None
            for f in self._bekleyen.values():
                if not f.done():
                    f.set_exception(DublajHatasi("dublaj_isci_hata", "işçi kapandı"))
            self._bekleyen.clear()
            for cb in list(self._dinleyiciler):
                try:
                    cb({"olay": "isci_kapandi"})
                except Exception:   # noqa: BLE001
                    pass

    async def _yaz(self, nesne: dict[str, Any]) -> None:
        veri = (json.dumps(nesne, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            self._surec.stdin.write(veri)
            await self._surec.stdin.drain()
        except (ConnectionError, OSError, AttributeError) as e:
            raise DublajHatasi("dublaj_isci_hata", f"işçiye yazılamadı: {type(e).__name__}") from e

    async def iste(self, komut: str, veri: dict[str, Any] | None = None, ilerleme: IlerlemeCb | None = None,
                   zaman_asimi: float | None = None, no_cb: Callable[[int], None] | None = None) -> dict[str, Any]:
        """Komutu gönderir, yanıtı bekler. Hata → DublajHatasi(kod). İptal edilirse işçiye de `iptal` gider."""
        await self.baslat()
        self._no += 1
        no = self._no
        f: asyncio.Future = asyncio.get_running_loop().create_future()
        self._bekleyen[no] = f
        if ilerleme:
            self._ilerleme[no] = ilerleme
        if no_cb:
            no_cb(no)
        try:
            await self._yaz({**(veri or {}), "no": no, "komut": komut})
            try:
                v = await asyncio.wait_for(asyncio.shield(f), zaman_asimi) if zaman_asimi else await f
            except asyncio.TimeoutError:
                await self.iptal(no)
                raise DublajHatasi("dublaj_isci_zaman", komut) from None
            except asyncio.CancelledError:
                try:
                    await self.iptal(no)
                except Exception:   # noqa: BLE001
                    pass
                raise
        finally:
            self._bekleyen.pop(no, None)
            self._ilerleme.pop(no, None)
        if not v.get("tamam"):
            raise DublajHatasi(str(v.get("hata") or "dublaj_isci_hata"), str(v.get("ayrinti") or ""))
        return v.get("sonuc") or {}

    async def iptal(self, hedef: int | None = None) -> None:
        if not self.calisiyor():
            return
        self._no += 1
        await self._yaz({"no": self._no, "komut": "iptal", **({"hedef": hedef} if hedef else {})})

    async def _oldur(self) -> None:
        s, self._surec = self._surec, None
        self.bilgi = None
        if s is None:
            return
        try:
            if s.returncode is None:
                s.kill()
            await asyncio.wait_for(s.wait(), 5)
        except Exception:   # noqa: BLE001
            pass

    async def kapat(self) -> None:
        if self.calisiyor():
            try:
                self._no += 1
                await self._yaz({"no": self._no, "komut": "kapat"})
                await asyncio.wait_for(self._surec.wait(), 5)
            except Exception:   # noqa: BLE001
                pass
        if self._okuyucu is not None:
            self._okuyucu.cancel()
            await asyncio.gather(self._okuyucu, return_exceptions=True)
            self._okuyucu = None
        await self._oldur()


# ---------- canlı dublaj bağdaştırıcıları ----------

class IsciMotoru:
    """SesMotoru: seslendirmeyi işçide yapar (Chatterbox / Pocket). Duygu bilgisini de taşır."""

    yerel = True
    duygu_destekli = True
    akisli = True            # seslendir_ve_cal: ilk cümlecik hazır olunca çalmaya başlar
    varsayilan_ses = True    # boş örnek → motorun nötr Türkçe sesi

    def __init__(self, kod: str, isci: IsciIstemci, hazir_fn: Callable[[], bool],
                 yukle_ayar: Callable[[], dict[str, Any]], model_indir: Callable[[IlerlemeCb | None], Awaitable[None]] | None = None,
                 pid_fn: Callable[[], int | None] | None = None) -> None:
        self.pid_fn = pid_fn or (lambda: None)
        self.kod = kod
        self.ad = {"chatterbox": "Chatterbox", "pocket": "Pocket TTS"}.get(kod, kod)
        self.isci = isci
        self._hazir_fn = hazir_fn
        self._yukle_ayar = yukle_ayar
        self._model_indir = model_indir
        self._yuklu: tuple | None = None

    def hazir(self) -> bool:
        return self._hazir_fn()

    async def hazirla(self, ilerleme_cb: IlerlemeCb | None = None) -> None:
        if not self._hazir_fn():
            raise DublajHatasi("dublaj_paket_yok", "dublaj paketi kurulu değil")
        ayar = {"tts": self.kod, **self._yukle_ayar()}
        imza = tuple(sorted(ayar.items()))
        if self._yuklu == imza and self.isci.calisiyor():
            return
        if self._model_indir is not None:
            await self._model_indir(ilerleme_cb)
        if ilerleme_cb:
            ilerleme_cb(100.0, "yukleniyor")
        await self.isci.iste("yukle", ayar)
        self._yuklu = imza
        if ilerleme_cb:
            ilerleme_cb(100.0, "bitti")

    async def seslendir(self, metin: str, referans_pcm: Any, sr: int, duygu: dict[str, float] | None = None) -> tuple[Any, int]:
        if not self.isci.calisiyor() or self._yuklu is None:
            await self.hazirla(None)
        r = await self.isci.iste("seslendir", {"metin": metin, "ref_pcm": pcm_kodla(referans_pcm), "ref_sr": int(sr),
                                               "duygu": duygu or {}, "motor": self.kod})
        return pcm_coz(r["pcm"]), int(r["sr"])

    async def seslendir_ve_cal(self, metin: str, referans_pcm: Any, sr: int, duygu: dict[str, float] | None,
                               hedef_sn: float, ayar: dict[str, Any]) -> dict[str, Any]:
        if not self.isci.calisiyor() or self._yuklu is None:
            await self.hazirla(None)
        d = ayar.get("dublaj") or {}
        return await self.isci.iste("seslendir_cal", {
            "metin": metin, "ref_pcm": pcm_kodla(referans_pcm), "ref_sr": int(sr), "duygu": duygu or {},
            "motor": self.kod, "hedef_sn": float(hedef_sn), "hiz_siniri": float(d.get("hiz_siniri", 1.25)),
            "seviye": float(d.get("ses_seviyesi", 1.0)), "kis": float(d.get("oyun_sesi_kis", 0.25)),
            "pid": self.pid_fn()})

    async def kapat(self) -> None:
        self._yuklu = None


class IsciSTT:
    def __init__(self, isci: IsciIstemci, atla_dil: str | None = "tr") -> None:
        self.isci = isci
        self.atla_dil = atla_dil
        self.dil: str | None = None

    async def yaz(self, pcm: Any, sr: int) -> str:
        r = await self.isci.iste("yaziya", {"pcm": pcm_kodla(pcm), "sr": int(sr)})
        self.dil = r.get("dil")
        if self.atla_dil and self.dil == self.atla_dil:
            return ""
        return str(r.get("metin") or "")


@dataclass
class IsciParca:
    pcm: Any
    sr: int
    bas: float
    bitis: float
    temiz: Any = None          # ayrılmış (arka plansız) konuşma sesi
    kaynak: str = "sistem"     # "surec" (yalnız oyun) | "sistem"


class IsciSesKaynagi:
    """`kopru.ses.SesKaynagi` yerine: oyun sesini işçi dinler, parçalar olay olarak gelir."""

    def __init__(self, parca_cb: Callable[[Any], None], saat: Callable[[], float], isci: IsciIstemci,
                 ayar_fn: Callable[[], dict[str, Any]], pid_fn: Callable[[], int | None],
                 hata_cb: Callable[[Any], None] | None = None) -> None:
        self.parca_cb, self.saat, self.isci = parca_cb, saat, isci
        self.ayar_fn, self.pid_fn, self.hata_cb = ayar_fn, pid_fn, hata_cb
        self._gorev: asyncio.Task | None = None
        self.bilgi: dict[str, Any] = {}

    def _olay(self, v: dict[str, Any]) -> None:
        if v.get("olay") == "parca" and v.get("pcm"):
            bitis = self.saat()
            sure = float(v.get("sure_sn") or 0)
            self.parca_cb(IsciParca(pcm_coz(v["pcm"]), int(v.get("sr") or 16000), bitis - sure, bitis,
                                    pcm_coz(v["temiz"]) if v.get("temiz") else None, str(v.get("kaynak") or "sistem")))
        elif v.get("olay") in ("canli_hata", "isci_kapandi") and self.hata_cb:
            from ..ses import SesHatasi
            self.hata_cb(SesHatasi("Oyun sesi dinlenemedi.", str(v.get("hata") or "dublaj_ses_kaynagi")))

    def baslat(self, dublaj: bool = True) -> None:
        self.isci.dinle(self._olay)
        ayar = self.ayar_fn()
        d = ayar.get("dublaj") or {}
        from . import tamamen_turkce_mu

        async def ac() -> None:
            try:
                self.bilgi = await self.isci.iste("canli_baslat", {
                    "pid": self.pid_fn(), "ayirma": bool(d.get("ayirma", True)),
                    "tamamen_turkce": tamamen_turkce_mu(ayar), "giris": str(d.get("ses_girisi") or "")})
            except DublajHatasi as e:
                if self.hata_cb:
                    from ..ses import SesHatasi
                    self.hata_cb(SesHatasi(e.ayrinti or e.kod, e.kod))
        self._gorev = asyncio.get_running_loop().create_task(ac())

    def durdur(self) -> None:
        self.isci.birak(self._olay)
        if self.isci.calisiyor():
            try:
                asyncio.get_running_loop().create_task(self.isci.iste("canli_durdur", {}))
            except RuntimeError:
                pass


class IsciCikis:
    """Bu bilgisayarın hoparlöründen işçi çalar; çalarken oyun sesini (yalnız o oyunu) kısar."""

    ad = "bilgisayar"
    akisli = True

    def __init__(self, isci: IsciIstemci, pid_fn: Callable[[], int | None]) -> None:
        self.isci = isci
        self.pid_fn = pid_fn

    async def oynat(self, pcm: Any, sr: int, ayar: dict[str, Any], yazi_id: str | None = None) -> Any:
        d = ayar.get("dublaj") or {}
        r = await self.isci.iste("oynat", {"pcm": pcm_kodla(pcm), "sr": int(sr), "seviye": float(d.get("ses_seviyesi", 1.0)),
                                           "kis": float(d.get("oyun_sesi_kis", 0.25)), "pid": self.pid_fn()})
        return r

    def durdur(self) -> None:
        if self.isci.calisiyor():
            try:
                asyncio.get_running_loop().create_task(self.isci.iptal())
            except RuntimeError:
                pass


def isci_komutu(python: Path, kod_kok: Path, model_dizini: Path, ffmpeg: str | None, gunluk: Path | None,
                ek_env: dict[str, str] | None = None) -> IsciKomutu:
    env = {k: v for k, v in os.environ.items() if not k.upper().endswith(("_API_KEY", "_TOKEN", "ANAHTAR"))}
    env.update({"HF_HOME": str(model_dizini), "HF_HUB_DISABLE_TELEMETRY": "1", "PYTHONNOUSERSITE": "1",
                "TOKENIZERS_PARALLELISM": "false"})
    if ffmpeg:
        env["KOPRU_FFMPEG"] = ffmpeg
    env.update(ek_env or {})
    return IsciKomutu([str(python), "-E", "-s", "-X", "utf8", "-m", "kopru.dublaj.isci"], str(kod_kok), env, gunluk)
