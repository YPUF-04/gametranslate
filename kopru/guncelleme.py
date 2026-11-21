# SPDX-License-Identifier: AGPL-3.0-only
"""Tek tuşla güncelleme: GitHub Sürümler'den yeni sürümü bulur, indirir, doğrular, kurar.

İki yol vardır (PROTOKOL 8):
  1. Velopack (Windows, Velopack kurucusuyla kurulmuş program): yalnız DEĞİŞEN parçalar (delta paketi)
     indirilir; Velopack kendi SHA256 denetimini yapar, uygular ve programı yeniden başlatır.
  2. Eski yol (geliştirme, macOS, taşınabilir zip, eski Inno kurulumu): tam kurucu indirilir, SHA256SUMS.txt
     ile doğrulanır ve sessizce çalıştırılır. Velopack'a geçiş de bu yolla bir kez yapılır (geçiş kurucusu).

Gizlilik: yalnız herkese açık GitHub adreslerine, kimliksiz ve genel bir User-Agent ile gider.
Hiçbir kimlik, ayar ya da kullanım bilgisi gönderilmez. Ayar `guncelleme_denetle` ile kapatılabilir.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import aiohttp
from yarl import URL

from . import SURUM, ayarlar, metinler

log = logging.getLogger("kopru.guncelleme")

SON_SURUM_ADRESI = "https://api.github.com/repos/YPUF-04/gametranslate/releases/latest"
SURUMLER_SAYFASI = "https://github.com/YPUF-04/gametranslate/releases/latest"
KULLANICI_AJANI = "AltYaziKoprusu-guncelleme"
IZINLI_SUNUCULAR = {"github.com", "api.github.com", "objects.githubusercontent.com",
                    "release-assets.githubusercontent.com"}
GUN_SN = 24 * 3600
HATA_BEKLEME_SN = 15 * 60   # başarısız denetimden sonra otomatik yeniden deneme aralığı (GitHub oran sınırı)
ZAMAN_ASIMI_SN = 5.0
KURUCU_DESENI = re.compile(r"^AltYaziKoprusu-Kur-.+\.exe$")
TOPLAM_ADI = "SHA256SUMS.txt"
KURUCU_ARGUMANLARI = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/GUNCELLEME=1"]
EN_FAZLA_YONLENDIRME = 5
NOT_UZUNLUGU = 800
DEPO_ADRESI = "https://github.com/YPUF-04/gametranslate"
YENIDEN_BASLAMA_BEKLEME_SN = 1.5   # panel "yeniden başlayacak" iletisini görsün, sonra uygula
_OTOMATIK = object()               # motor=_OTOMATIK: Velopack varsa kendiliğinden bulunur


class GuncellemeHatasi(Exception):
    """`kod` metinler.py içindeki bir hata koduyla aynıdır."""

    def __init__(self, kod: str) -> None:
        super().__init__(kod)
        self.kod = kod


# ---------- saf yardımcılar ----------

def adres_izinli_mi(adres: str) -> bool:
    """Yalnız https ve GitHub'ın kendi sunucuları."""
    try:
        u = urlparse(adres)
    except ValueError:
        return False
    return (u.scheme == "https" and (u.hostname or "").lower() in IZINLI_SUNUCULAR
            and u.username is None and u.port in (None, 443))


def surum_coz(metin: str) -> tuple[int, int, int, bool] | None:
    """'v0.3.0' -> (0, 3, 0, kararli). Ön sürüm ('0.3.0-beta.1') kararli=False olur."""
    m = re.fullmatch(r"v?(\d{1,6})\.(\d{1,6})\.(\d{1,6})(-[0-9A-Za-z.\-]+)?(\+[0-9A-Za-z.\-]+)?",
                     (metin or "").strip())
    if not m:
        return None
    return int(m[1]), int(m[2]), int(m[3]), m[4] is None


def daha_yeni_mi(aday: str, mevcut: str) -> bool:
    a, m = surum_coz(aday), surum_coz(mevcut)
    if a is None or m is None:
        return False
    # (sayılar, kararlı) -> kararlı sürüm, aynı numaralı ön sürümden yenidir
    return (a[:3], a[3]) > (m[:3], m[3])


def toplamlari_oku(metin: str) -> dict[str, str]:
    """`sha256sum` çıktısı: '<64 hex>  dosya' ya da '<64 hex> *dosya'."""
    tablo: dict[str, str] = {}
    for satir in metin.splitlines():
        m = re.fullmatch(r"\s*([0-9a-fA-F]{64})\s+\*?(.+?)\s*", satir)
        if m:
            tablo[m[2].strip()] = m[1].lower()
    return tablo


def dosya_ozeti(yol: Path) -> str:
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def _kisalt(metin: str) -> str:
    metin = (metin or "").replace("\r\n", "\n").strip()
    return metin if len(metin) <= NOT_UZUNLUGU else metin[:NOT_UZUNLUGU].rstrip() + "…"


# ---------- ağ katmanı (testte yerine sahtesi konur) ----------

class GitHubHttp:
    """Yönlendirmeleri elle izler; her adım izinli adres listesinden geçmek zorundadır."""

    def _baslik(self) -> dict[str, str]:
        return {"User-Agent": KULLANICI_AJANI, "Accept": "application/vnd.github+json, */*"}

    async def _ac(self, oturum: aiohttp.ClientSession, adres: str):
        for _ in range(EN_FAZLA_YONLENDIRME + 1):
            if not adres_izinli_mi(adres):
                raise GuncellemeHatasi("guncelleme_adres")
            yanit = await oturum.get(adres, allow_redirects=False, headers=self._baslik())
            if yanit.status in (301, 302, 303, 307, 308) and yanit.headers.get("Location"):
                adres = str(yanit.url.join(URL(yanit.headers["Location"])))
                yanit.release()
                continue
            yanit.raise_for_status()
            return yanit
        raise GuncellemeHatasi("guncelleme_adres")

    async def json_al(self, adres: str) -> dict[str, Any]:
        zaman = aiohttp.ClientTimeout(total=ZAMAN_ASIMI_SN)
        async with aiohttp.ClientSession(timeout=zaman) as o:
            y = await self._ac(o, adres)
            async with y:
                return json.loads(await y.text())

    async def metin_al(self, adres: str, azami: int = 65536) -> str:
        zaman = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=zaman) as o:
            y = await self._ac(o, adres)
            async with y:
                veri = await y.content.read(azami + 1)
                if len(veri) > azami:
                    raise GuncellemeHatasi("guncelleme_dogrulanamadi")
                return veri.decode("utf-8", "replace")

    async def indir(self, adres: str, hedef: Path, ilerleme: Callable[[int, int | None], None]) -> None:
        zaman = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=30)
        async with aiohttp.ClientSession(timeout=zaman) as o:
            y = await self._ac(o, adres)
            async with y:
                toplam = y.content_length
                alinan = 0
                with open(hedef, "wb") as f:
                    async for blok in y.content.iter_chunked(1 << 18):
                        f.write(blok)
                        alinan += len(blok)
                        ilerleme(alinan, toplam)


def _ayrik_baslat(komut: list[str]) -> None:
    """Kurucu, bu program kapansa da yaşasın (Windows'ta ayrık süreç)."""
    bayrak = 0
    if sys.platform == "win32":
        bayrak = getattr(subprocess, "DETACHED_PROCESS", 0x8) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
    subprocess.Popen(komut, close_fds=True, creationflags=bayrak,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _sunucuyu_kapat() -> None:
    """aiohttp'nin run_app döngüsünü düzgünce bitirir."""
    from aiohttp import web

    def cik() -> None:
        raise web.GracefulExit()
    asyncio.get_running_loop().call_later(1.5, cik)


# ---------- Velopack (yalnız değişen parçaları indirir) ----------

class VelopackSurum:
    """Velopack'ın bulduğu güncelleme: gösterilecek bilgiler + Velopack'a geri verilecek ham nesne."""

    def __init__(self, surum: str, notlar: str, boyut: int, delta: bool, ham: Any) -> None:
        self.surum, self.notlar, self.boyut, self.delta, self.ham = surum, notlar, boyut, delta, ham


class VelopackMotoru:
    """`velopack.UpdateManager` üzerine ince sarmalayıcı. Yöntemler ENGELLEYİCİDİR (to_thread ile çağrılır).
    Testte yerine sahtesi konur. Kaynak her zaman bu deponun GitHub Sürümleri'dir (Velopack Flow kullanılmaz)."""

    def __init__(self, modul: Any, depo: str = DEPO_ADRESI) -> None:
        self.modul = modul
        # Velopack ile kurulmamışsa burada RuntimeError fırlar -> çağıran eski yola döner
        self.yonetici = modul.UpdateManager(modul.GithubSource(depo))

    def kontrol(self) -> VelopackSurum | None:
        bilgi = self.yonetici.check_for_updates()
        if bilgi is None:
            return None
        hedef = bilgi.TargetFullRelease
        deltalar = list(bilgi.DeltasToTarget or [])
        boyut = sum(int(d.Size) for d in deltalar) if deltalar else int(hedef.Size)
        return VelopackSurum(str(hedef.Version), str(hedef.NotesMarkdown or ""), boyut, bool(deltalar), bilgi)

    def indir(self, surum: VelopackSurum, ilerleme: Callable[[int], None]) -> None:
        self.yonetici.download_updates(surum.ham, ilerleme)

    def uygula(self, surum: VelopackSurum) -> None:
        self.yonetici.apply_updates_and_restart(surum.ham)


def velopack_motoru() -> VelopackMotoru | None:
    """Windows'ta ve program Velopack ile kuruluysa motoru verir; aksi halde None (eski yol)."""
    if sys.platform != "win32":
        return None
    try:
        import velopack
        return VelopackMotoru(velopack)
    except Exception:   # noqa: BLE001 — paket yok / program Velopack ile kurulmamış (zip, geliştirme, Inno)
        return None


# ---------- ana sınıf ----------

class Guncelleme:
    def __init__(self, ayar_al: Callable[[], dict[str, Any]], http: Any = None,
                 mevcut_surum: str = SURUM, platform: str | None = None,
                 baslatici: Callable[[list[str]], None] = _ayrik_baslat,
                 kapatici: Callable[[], None] = _sunucuyu_kapat,
                 simdi: Callable[[], float] = time.time,
                 gecici_kok: Path | None = None, motor: Any = _OTOMATIK,
                 yeniden_baslama_bekleme: float = YENIDEN_BASLAMA_BEKLEME_SN) -> None:
        self.ayar_al = ayar_al
        self.http = http or GitHubHttp()
        self.mevcut = mevcut_surum
        self.platform = platform or sys.platform
        self.baslatici = baslatici
        self.kapatici = kapatici
        self.simdi = simdi
        self.gecici_kok = gecici_kok
        self.motor = (velopack_motoru() if self.platform == "win32" else None) if motor is _OTOMATIK else motor
        self.bekleme = yeniden_baslama_bekleme
        self.delta = False       # indirilecek şey yalnız değişen parçalar mı (Velopack)
        self._ham: VelopackSurum | None = None
        self.surum: str | None = None
        self.notlar = ""
        self.boyut = 0
        self.kurucu_adresi: str | None = None
        self.toplam_adresi: str | None = None
        self.kurucu_adi: str | None = None
        self.son_denetim = 0.0
        self.son_hata_an = -1e9
        self.asama = "bosta"     # bosta | indiriliyor | dogrulaniyor | baslatiliyor | hata
        self.ilerleme = 0
        self.hata_kodu: str | None = None
        self.denetim_gorevi: asyncio.Task | None = None
        self.kur_gorevi: asyncio.Task | None = None
        self.denetim_hatasi: str | None = None
        self._durum_oku()

    # --- kalıcı (yalnız son denetim zamanı ve bulunan sürüm; kimlik YOK) ---
    def _dosya(self) -> Path:
        return ayarlar.ayar_dizini() / "guncelleme.json"

    def _durum_oku(self) -> None:
        try:
            v = json.loads(self._dosya().read_text(encoding="utf-8"))
            self.son_denetim = float(v.get("zaman", 0))
            self._surum_ata(v.get("surum"), v.get("notlar", ""), int(v.get("boyut", 0)),
                            v.get("kurucu_adresi"), v.get("toplam_adresi"), v.get("kurucu_adi"))
            self.delta = bool(v.get("delta", False)) and self.surum is not None and self.motor is not None
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def _durum_yaz(self) -> None:
        try:
            ayarlar.atomik_yaz(self._dosya(), json.dumps({
                "zaman": self.son_denetim, "surum": self.surum, "notlar": self.notlar, "boyut": self.boyut,
                "kurucu_adresi": self.kurucu_adresi, "toplam_adresi": self.toplam_adresi,
                "kurucu_adi": self.kurucu_adi, "delta": self.delta}, ensure_ascii=False))
        except OSError:
            log.warning("Güncelleme durumu yazılamadı")

    def _surum_ata(self, surum: Any, notlar: str, boyut: int, kurucu: Any, toplam: Any, ad: Any) -> None:
        eski_yol_tamam = isinstance(kurucu, str) and isinstance(toplam, str)
        if isinstance(surum, str) and daha_yeni_mi(surum, self.mevcut) and (eski_yol_tamam or self.motor is not None):
            self.surum, self.notlar, self.boyut = surum.lstrip("v"), _kisalt(notlar), boyut
            self.kurucu_adresi, self.toplam_adresi, self.kurucu_adi = kurucu, toplam, ad
        else:
            self.surum = None
            self.notlar, self.boyut, self.kurucu_adresi, self.toplam_adresi, self.kurucu_adi = "", 0, None, None, None
            self.delta, self._ham = False, None

    # --- koşullar ---
    @property
    def destekli(self) -> bool:
        return self.platform == "win32"

    def otomatik_acik(self) -> bool:
        return self.ayar_al().get("guncelleme_denetle", True) is not False

    def denetim_zamani_mi(self) -> bool:
        simdi = self.simdi()
        # panel her açıldığında/yenilendiğinde başarısız istek yağmasın
        return simdi - self.son_denetim >= GUN_SN and simdi - self.son_hata_an >= HATA_BEKLEME_SN

    # --- denetim ---
    async def denetle(self, elle: bool = False) -> None:
        """elle=False: ayar kapalıysa ya da bugün bakıldıysa HİÇ istek yapılmaz."""
        if not self.destekli:
            return
        if not elle and (not self.otomatik_acik() or not self.denetim_zamani_mi()):
            return
        self.denetim_hatasi = None
        if self.motor is not None:
            await self._velopack_denetle()
            return
        try:
            surum_json = await self.http.json_al(SON_SURUM_ADRESI)
            etiket = str(surum_json.get("tag_name", ""))
            kurucu = toplam = kurucu_adi = None
            boyut = 0
            for a in surum_json.get("assets", []) or []:
                ad, adres = str(a.get("name", "")), str(a.get("browser_download_url", ""))
                if KURUCU_DESENI.match(ad) and adres_izinli_mi(adres):
                    kurucu, kurucu_adi, boyut = adres, ad, int(a.get("size", 0))
                elif ad == TOPLAM_ADI and adres_izinli_mi(adres):
                    toplam = adres
            self._surum_ata(etiket, str(surum_json.get("body") or ""), boyut, kurucu, toplam, kurucu_adi)
            self.son_denetim = self.simdi()
            self._durum_yaz()
        except asyncio.CancelledError:
            raise
        except Exception:   # ağ, bozuk JSON, beklenmeyen şekil: arka plan görevi sessizce ölmesin
            log.info("Güncelleme denetlenemedi (ağ ya da yanıt hatası)")
            self.denetim_hatasi = "guncelleme_denetlenemedi"
            self.son_hata_an = self.simdi()

    async def _velopack_denetle(self) -> None:
        try:
            bulunan = await asyncio.to_thread(self.motor.kontrol)
            if bulunan is None or not daha_yeni_mi(bulunan.surum, self.mevcut):
                self._surum_ata(None, "", 0, None, None, None)
            else:
                self._surum_ata(bulunan.surum, bulunan.notlar, bulunan.boyut, None, None, None)
                self.delta, self._ham = bool(bulunan.delta), bulunan
            self.son_denetim = self.simdi()
            self._durum_yaz()
        except asyncio.CancelledError:
            raise
        except Exception:   # ağ, GitHub oran sınırı, bozuk yayın akışı: arka plan görevi sessizce ölmesin
            log.info("Güncelleme denetlenemedi (Velopack)")
            self.denetim_hatasi = "guncelleme_denetlenemedi"
            self.son_hata_an = self.simdi()

    def arka_planda_denetle(self, elle: bool = False) -> None:
        """Panelin takılmaması için denetim arka planda; ikisi birden çalışmaz."""
        if self.denetim_gorevi and not self.denetim_gorevi.done():
            return
        if not elle and (not self.destekli or not self.otomatik_acik() or not self.denetim_zamani_mi()):
            return
        self.denetim_gorevi = asyncio.get_running_loop().create_task(self.denetle(elle))

    # --- durum ---
    def _dil(self) -> str:
        return self.ayar_al().get("arayuz_dili", "tr")

    def durum(self) -> dict[str, Any]:
        dil = self._dil()
        taban = {"mevcut": self.mevcut, "denetim_acik": self.otomatik_acik(), "baglanti": SURUMLER_SAYFASI,
                 "ilerleme": self.ilerleme, "asama": self.asama,
                 "denetleniyor": bool(self.denetim_gorevi and not self.denetim_gorevi.done()),
                 "son_denetim": int(self.son_denetim) or None}
        if not self.destekli:
            return {**taban, "var": False, "neden": "desteklenmiyor",
                    "mesaj": metinler.mesaj("guncelleme_desteklenmiyor", dil)}
        if self.denetim_hatasi:
            taban["denetim_hatasi"] = metinler.mesaj(self.denetim_hatasi, dil)
        if self.hata_kodu:
            taban["hata"] = self.hata_kodu
            taban["mesaj"] = metinler.mesaj(self.hata_kodu, dil)
        if self.surum is None:
            neden = "guncel" if self.son_denetim else ("kapali" if not self.otomatik_acik() else "bekleniyor")
            return {**taban, "var": False, "neden": neden}
        return {**taban, "var": True, "surum": self.surum, "notlar": self.notlar,
                "boyut_mb": max(1, round(self.boyut / (1024 * 1024))) if self.boyut else None,
                "boyut_bayt": self.boyut or None, "yalniz_degisenler": self.delta}

    # --- kurulum ---
    def kur_baslat(self) -> str | None:
        """Hata kodu döner (yoksa None). İndirme arka planda sürer."""
        if not self.destekli:
            return "guncelleme_desteklenmiyor"
        if self.kur_gorevi and not self.kur_gorevi.done():
            return None
        if self.motor is not None:
            if self.surum is None:
                return "guncelleme_yok"
            self.asama, self.ilerleme, self.hata_kodu = "indiriliyor", 0, None
            self.kur_gorevi = asyncio.get_running_loop().create_task(self._velopack_kur())
            return None
        if self.surum is None or not self.kurucu_adresi or not self.toplam_adresi:
            return "guncelleme_yok"
        if not adres_izinli_mi(self.kurucu_adresi) or not adres_izinli_mi(self.toplam_adresi):
            return "guncelleme_adres"
        self.asama, self.ilerleme, self.hata_kodu = "indiriliyor", 0, None
        self.kur_gorevi = asyncio.get_running_loop().create_task(self._kur())
        return None

    def _hata(self, kod: str) -> None:
        self.asama, self.hata_kodu = "hata", kod

    async def kapat(self) -> None:
        """Program kapanırken arka plan görevlerini iptal eder ve bekler (geçici klasör temizlenir)."""
        gorevler = [t for t in (self.denetim_gorevi, self.kur_gorevi) if t and not t.done()]
        for t in gorevler:
            t.cancel()
        if gorevler:
            await asyncio.gather(*gorevler, return_exceptions=True)

    async def _velopack_kur(self) -> None:
        """Değişen parçaları indirir (Velopack SHA256'yı kendisi denetler), uygular, programı yeniden başlatır."""
        try:
            bulunan = self._ham
            if bulunan is None:     # program yeniden açılmış, kayıtlı durumdan geliyoruz: bir kez daha bak
                bulunan = await asyncio.to_thread(self.motor.kontrol)
                if bulunan is None:
                    raise GuncellemeHatasi("guncelleme_yok")

            def ilerle(yuzde: int) -> None:      # Velopack iş parçacığından çağrılır
                try:
                    self.ilerleme = max(0, min(95, int(yuzde)))
                except (TypeError, ValueError):
                    pass

            await asyncio.to_thread(self.motor.indir, bulunan, ilerle)
            self.asama, self.ilerleme = "baslatiliyor", 100
            await asyncio.sleep(self.bekleme)
            try:
                await asyncio.to_thread(self.motor.uygula, bulunan)
            except Exception:   # noqa: BLE001 — güncelleyici başlatılamadı
                log.exception("Velopack uygulaması başlatılamadı")
                raise GuncellemeHatasi("guncelleme_baslatilamadi") from None
            self.kapatici()     # Update.exe bu sürecin bitmesini bekler
        except GuncellemeHatasi as e:
            self._hata(e.kod)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Güncelleme beklenmeyen hata (Velopack)")
            self._hata("guncelleme_indirilemedi")

    async def _kur(self) -> None:
        dizin = Path(tempfile.mkdtemp(prefix="akp-guncelleme-", dir=self.gecici_kok))
        try:
            adi = Path(urlparse(self.kurucu_adresi or "").path).name or "kurucu.exe"
            if not KURUCU_DESENI.match(adi):
                raise GuncellemeHatasi("guncelleme_adres")
            dosya = dizin / adi

            def ilerle(alinan: int, toplam: int | None) -> None:
                bekl = toplam or self.boyut
                self.ilerleme = min(95, int(alinan * 95 / bekl)) if bekl else min(95, self.ilerleme + 1)

            await self.http.indir(self.kurucu_adresi, dosya, ilerle)
            self.asama, self.ilerleme = "dogrulaniyor", 96
            toplamlar = toplamlari_oku(await self.http.metin_al(self.toplam_adresi))
            beklenen = toplamlar.get(adi)
            # onlarca MB'lık özet hesabı olay döngüsünü (SSE, panel) tutmasın
            if not beklenen or await asyncio.to_thread(dosya_ozeti, dosya) != beklenen:
                raise GuncellemeHatasi("guncelleme_dogrulanamadi")
            self.asama, self.ilerleme = "baslatiliyor", 100
            try:
                self.baslatici([str(dosya), *KURUCU_ARGUMANLARI])
            except OSError:
                raise GuncellemeHatasi("guncelleme_baslatilamadi") from None
            self.kapatici()
            dizin = None   # kurucu bu klasörden çalışıyor; silinmez (Windows geçici klasörü temizler)
        except GuncellemeHatasi as e:
            self._hata(e.kod)
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            self._hata("guncelleme_indirilemedi")
        except Exception:
            log.exception("Güncelleme beklenmeyen hata")
            self._hata("guncelleme_indirilemedi")
        finally:
            if dizin is not None:
                shutil.rmtree(dizin, ignore_errors=True)
