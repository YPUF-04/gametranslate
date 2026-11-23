# SPDX-License-Identifier: AGPL-3.0-only
"""aiohttp sunucusu: SSE akışı, panel API'si, statik sayfalar."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import socket
import sys
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from aiohttp import web

from . import (PROTOKOL, SURUM, ayarlar, anahtarlar, erisim as erisim_mod, guncelleme as guncelleme_mod, hafiza as hafiza_mod,
               metinler, oyunlar, paket as paket_mod, sozluk as sozluk_mod)
from . import oyun_bilgisi
from .ceviri import BILGI, _http, motor_olustur
from .ceviri.temel import AgHatasi, AnahtarHatasi, MotorHatasi
from .ceviri.yonetici import CeviriYoneticisi
from . import dublaj as dublaj_mod
from . import kisayol as kisayol_mod
from .dublaj.temel import DublajHatasi
from .dublaj.yonetim import DublajYonetici
from .isleme import Isleme
from .katman import yonetim as katman_yonetim
from .okuma import OkumaHatasi
from .onbellek import Onbellek, normallestir
from .tv_kurulum.lg import LgKurulum
from .yakalama import YakalamaHatasi
from .yayin import Yayin, sse_bicim

log = logging.getLogger("kopru.sunucu")
WEB = Path(__file__).parent / "web"
NABIZ_SN = 15.0
KATMAN_SN = 2.0   # ekran katmanı süreç denetimi
ERISIM_SN = 5.0   # süre sayacı adımı
DURUM_SN = 20.0  # EventSource yorum satırını görmez; gerçek olay gerekir
KAYNAK_ONBELLEK_SN = 3.0   # pencere listesi (uyarı için) en çok bu sıklıkta yenilenir
YEREL = {"127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"}
YEREL_ADLAR = {"127.0.0.1", "localhost", "[::1]", "::1"}   # Host/Origin'de görünebilecek yerel adlar
EN_COK_AKIS = 64            # aynı anda en çok bu kadar akış (SSE) istemcisi
YAZMA_ZAMAN_ASIMI_SN = 15.0  # donmuş istemciye yazma bu süreyi aşarsa bağlantı kapatılır
DURUM = web.AppKey("durum", object)
GUNCELLEME = web.AppKey("guncelleme", object)
LG_KURULUM = web.AppKey("lg_kurulum", object)
PSN_ISTEK = web.AppKey("psn_istek", object)   # testlerde sahte Sony istemcisi


def uzak_adres(request: web.Request) -> str | None:
    return request.remote


def lan_adresleri() -> list[str]:
    """Bu bilgisayarın yerel ağ IPv4 adresleri."""
    bulunan: list[str] = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # paket gönderilmez, yalnız yol seçilir
        bulunan.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    # Not: gethostname() üzerinden ad çözme macOS'ta 30 sn'ye kadar takılabiliyor; kullanılmaz.
    return [ip for ip in bulunan if not ip.startswith("127.") and ip != "0.0.0.0"]


class Durum:
    """Uygulamanın çalışma durumu."""

    def __init__(self, ayar: dict[str, Any], motor_fabrika: Callable[[str, dict], Any] = motor_olustur,
                 kare_fabrika: Callable[[str], Callable[[], Any]] | None = None,
                 okuyucu_fabrika: Callable[[], Any] | None = None,
                 erisim: erisim_mod.Erisim | None = None,
                 dublaj_fabrikalari: dict[str, Any] | None = None,
                 katman_baslatici: Callable[[list[str]], Any] | None = None,
                 katman_destek: Callable[[], bool] | None = None,
                 kisayol_dinleyici: Callable[[], Any] | None = None,
                 kisayol_destek: bool | None = None,
                 dosya_secici: Callable[[], Awaitable[str | None]] | None = None,
                 klasorde_goster: Callable[[str], None] | None = None,
                 video_is_koku: Path | None = None,
                 ps5_satir: Callable[[str], list[str]] | None = None) -> None:
        from . import dosya_sec as dosya_sec_mod
        self.dosya_secici = dosya_secici or dosya_sec_mod.sec
        self.klasorde_goster = klasorde_goster or dosya_sec_mod.klasorde_goster
        self.video_is_koku = video_is_koku
        self.ayar = ayar
        self.erisim = erisim or erisim_mod.Erisim(lambda: self.ayar)
        self.yayin = Yayin()
        self.motor_fabrika = motor_fabrika
        self.kare_fabrika = kare_fabrika
        self.okuyucu_fabrika = okuyucu_fabrika
        oyunlar.goc_et()  # eski sozlukler/ klasörünü oyunlar/<kod>/ altına taşır
        self.onbellek: Onbellek | None = None
        self._onbellek_kalici = False
        self.hafiza: hafiza_mod.Hafiza | None = None
        self.oneriler: hafiza_mod.OneriDeposu | None = None
        self.gecmis: Any = None
        self.isleme: Isleme | None = None
        self._onbellek_kur()
        self.yonetici = self._yonetici_kur()
        self.gorev: asyncio.Task | None = None
        self.calisan_kapi: int | None = None   # gerçekten dinlenen kapı (8642 doluysa farklı olabilir)
        # Türkçe dublaj (PROTOKOL 9): varsayılan kapalı; yalnız ayar açıksa ve Başlat basılıysa çalışır
        self.dublaj = DublajYonetici(lambda: self.ayar, self.yayin, lambda: self.yonetici,
                                     **(dublaj_fabrikalari or {}))
        self.dublaj.izin = self.erisim.dublaj_izni   # PROTOKOL 17.2: yalnız dublaj süreli
        self.reklam_istemci = 0   # reklam gösterebilen TV istemcisi sayısı (/kopru/akis?reklam=1)
        # bilgisayar ekranı katmanı (PROTOKOL 10.3): ayrı süreç
        self.katman = katman_yonetim.KatmanYonetici(
            lambda: self.ayar, self.yayin, self.calisiyor, lambda: self.calisan_kapi or self.ayar["kapi"],
            katman_baslatici, katman_destek)
        # PS5 gizli bağlantı (PROTOKOL §15): oturum ayrı iş parçacığında; olaylar döngüye güvenle aktarılır
        from . import uzaktan as uzaktan_mod
        self._dongu: asyncio.AbstractEventLoop | None = None
        self.ps5 = uzaktan_mod.Ps5Yonetici(lambda: self.ayar, self._ps5_yayinla, satir=ps5_satir)
        uzaktan_mod.kaydet_etkin(self.ps5)
        self.yerel_indirme: dict[str, Any] = {"durum": "yok", "yuzde": 0, "mesaj": None, "ayrinti": None}
        self._yerel_gorev: asyncio.Task | None = None
        self._okuma_dene_okuyucu: Any = None
        self._kaynak_onbellek: tuple[float, list[dict[str, Any]], str] | None = None
        self.yayin.yayinla("gorunum", ayar["gorunum"])
        # genel kısayol tuşları (PROTOKOL §13.1): yalnız Windows; testlerde sahte dinleyici verilir
        self.kisayol = kisayol_mod.Kisayollar(
            {"baslat_durdur": self.kisayol_baslat_durdur, "gizle_goster": self.kisayol_gizle_goster,
             "yeniden_oku": self.kisayol_yeniden_oku}, kisayol_dinleyici, kisayol_destek)

    def _ps5_yayinla(self, govde: dict[str, Any]) -> None:
        dongu = self._dongu
        if dongu is not None and not dongu.is_closed():
            try:
                dongu.call_soon_threadsafe(self.yayin.yayinla, "ps5", govde)
            except RuntimeError:
                pass

    # -- kısayol eylemleri (§13.1) --
    def bildir(self, kod: str) -> None:
        """Durum olayına kısa bir `bildirim` metni ekleyip yayınlar (katman 1,5 sn'lik küçük bildirim gösterir)."""
        self.yayin.yayinla("durum", {**self.durum_olayi(), "bildirim": metinler.mesaj(kod, self.dil)})

    async def baslat_guvenli(self) -> str | None:
        """Başlatır; hata kodu ("kaynak_yok" | "yakalama_yok" | "okuma_yok") ya da None."""
        if not self.ayar.get("kaynak"):
            return "kaynak_yok"
        if self.calisiyor():
            return None
        try:
            okuyucu = await asyncio.to_thread(self.okuyucu_olustur)
            self.baslat(okuyucu)
        except YakalamaHatasi:
            return "yakalama_yok"
        except OkumaHatasi:
            return "okuma_yok"
        return None

    async def kisayol_baslat_durdur(self) -> None:
        if self.calisiyor():
            self.durdur()
            self.bildir("bildirim_durdu")
            return
        if not self.ayar.get("kurulum_tamam") or not self.ayar.get("kaynak"):
            self.bildir("bildirim_kurulum_gerek")
            return
        hata_kodu = await self.baslat_guvenli()
        self.bildir("bildirim_baslamadi" if hata_kodu else "bildirim_basladi")

    def kisayol_gizle_goster(self) -> None:
        if self.yayin.katman_gizli:
            self.yayin.yayinla("katman-goster", {})
            self.bildir("bildirim_gosteriliyor")
        else:
            self.yayin.yayinla("katman-gizle", {})
            self.bildir("bildirim_gizlendi")

    def kisayol_yeniden_oku(self) -> None:
        if self.isleme is not None and self.calisiyor():
            self.isleme.yeniden_oku()
        else:
            self.yayin.yayinla("yazi-sil", {})
            self.yayin.yayinla("ekran-sil", {})
        self.bildir("bildirim_yeniden_oku")

    def kisayol_bilgisi(self) -> dict[str, Any]:
        b = self.kisayol.bilgi()
        b["hata"] = {e: metinler.mesaj(f"kisayol_{k}", self.dil) for e, k in b["hata"].items()}
        return b

    @property
    def dil(self) -> str:
        return self.ayar.get("arayuz_dili", "tr")

    def izin(self) -> bool:
        """Hafıza izni açıkça verildi mi (null/false iken diske oyun verisi yazılmaz)."""
        return self.ayar.get("hafiza_izni") is True

    @property
    def oyun_kodu(self) -> str:
        return oyunlar.kod_coz(str(self.ayar.get("aktif_oyun") or oyunlar.VARSAYILAN_KOD))

    def _onbellek_kur(self) -> None:
        """İzin yoksa önbellek yalnız RAM'de (":memory:") durur."""
        kalici = self.izin()
        if self.onbellek is not None and kalici == self._onbellek_kalici:
            return
        if self.onbellek is not None:
            self.onbellek.kapat()
        self._onbellek_kalici = kalici
        self.onbellek = Onbellek(ayarlar.ayar_dizini() / "onbellek.sqlite3" if kalici else ":memory:")

    def bilgi_yenile(self) -> None:
        kod = self.oyun_kodu
        self.yonetici.oyun_bilgisi = oyunlar.oku(kod) or {}
        self.yonetici.terimler = sozluk_mod.sozluk_dict(sozluk_mod.yukle(kod))

    def _yonetici_kur(self) -> CeviriYoneticisi:
        a = self.ayar
        kod = self.oyun_kodu
        if self.hafiza is None or self.hafiza.kod != kod:   # aynı oyunsa RAM kayıtları korunur
            if self.hafiza:
                self.hafiza.kapat()
            if self.oneriler:
                self.oneriler.bitir()
            self.hafiza = hafiza_mod.Hafiza(kod, self.izin)
            self.oneriler = hafiza_mod.OneriDeposu(kod, self.izin)
        yedek_kod = a.get("yedek_motor") or None
        y = CeviriYoneticisi(self.motor_fabrika(a["motor"], a),
                             self.motor_fabrika(yedek_kod, a) if yedek_kod and yedek_kod != a["motor"] else None,
                             self.onbellek, self.yayin.yayinla, kod, self.hafiza, self.oneriler)
        if self.gecmis is not None:
            y.gecmis = self.gecmis
        self.gecmis = y.gecmis
        y.dublaj_izni = self.erisim.dublaj_izni   # altyazı çevirisi sınırsız (PROTOKOL 17.1)
        y.oyun_bilgisi = oyunlar.oku(kod) or {}
        y.terimler = sozluk_mod.sozluk_dict(sozluk_mod.yukle(kod))
        return y

    def yeniden_kur(self) -> None:
        self._onbellek_kur()
        self.yonetici = self._yonetici_kur()
        if self.gorev and not self.gorev.done():
            okuyucu = self.isleme.okuyucu if self.isleme else None   # modeli yeniden yükleme
            self.durdur()
            self.baslat(okuyucu)

    def duzelt(self, asil: str, ceviri: str) -> bool:
        """Kullanıcı düzeltmesi: hafızaya (kaynak=kullanici); ekrandaysa TV'de hemen güncellenir."""
        self.hafiza.kaydet(asil, ceviri, "kullanici")
        self.yonetici.duzeltildi(asil, ceviri)
        if self.isleme:
            self.isleme.duzeltildi(asil, ceviri)
        y = self.yayin.son_yazi
        kalan = self.yayin.kalan_ms()
        if y and kalan > 0 and normallestir(y.get("asil", "")) == normallestir(asil):
            self.yayin.yayinla("yazi", {**y, "metin": ceviri, "sure_ms": max(kalan, 1500), "devam": True})
            return True
        return False

    def durum_olayi(self) -> dict[str, Any]:
        motor = self.yonetici.yedek if self.yonetici.yedekte and self.yonetici.yedek else self.yonetici.birincil
        olay = {"calisiyor": self.calisiyor(), "motor": motor.ad, "yedek": bool(self.yonetici.yedekte),
                **self.yonetici.durum_ek()}
        if self.dublaj_durdu():
            olay["dublaj_sinir"] = True   # dublaj süresi bitti; altyazı sürer (PROTOKOL 17.2)
        return olay

    def dublaj_durdu(self) -> bool:
        """Kullanıcı dublaj istiyor ama süre bitti (kod yok)."""
        return self.dublaj.istenen() and not self.erisim.dublaj_izni()

    def erisim_say(self) -> None:
        """Sayaç adımı: yalnız dublaj gerçekten çalışırken süre düşer; izin değişirse dublaj durur/sürer."""
        once = self.erisim.dublaj_izni()
        self.erisim.say(self.dublaj.etkin())
        if self.erisim.dublaj_izni() != once:
            self.dublaj_izin_degisti()

    def dublaj_izin_degisti(self) -> None:
        try:
            self.dublaj.senkronla()
        except RuntimeError:   # döngü yok (sınama)
            pass
        self.yayin.yayinla("durum", self.durum_olayi())

    def kare_al(self) -> Any:
        """Seçili kaynaktan şu anki kare (PIL.Image). Diske yazılmaz."""
        if self.kare_fabrika is None:
            from . import yakalama
            return yakalama.kare_al(self.ayar["kaynak"])
        return self.kare_fabrika(self.ayar["kaynak"])()

    def calisiyor(self) -> bool:
        return bool(self.gorev and not self.gorev.done())

    async def kaynak_uyarisi(self) -> dict[str, str] | None:
        """§12.2: cihaz ps5/xbox/kart, uygun bir pencere var ama kaynak tüm ekran ise sakin bir uyarı."""
        cihaz = self.ayar.get("cihaz")
        if cihaz not in ("ps5", "xbox", "kart") or not str(self.ayar.get("kaynak") or "").startswith("ekran:"):
            return None
        simdi = time.monotonic()
        onbellek = self._kaynak_onbellek
        if onbellek is None or simdi - onbellek[0] > KAYNAK_ONBELLEK_SN or onbellek[2] != cihaz:
            try:
                from . import yakalama
                liste = await asyncio.to_thread(yakalama.kaynaklar, cihaz)
            except Exception:   # noqa: BLE001 — yakalama yoksa uyarı da yok
                liste = []
            onbellek = self._kaynak_onbellek = (simdi, liste, cihaz)
        if not any(k.get("onerilen") for k in onbellek[1]):
            return None
        return {"kod": "tum_ekran", "mesaj": metinler.mesaj(f"uyari_tum_ekran_{cihaz}", self.dil)}

    def okuyucu_olustur(self) -> Any:
        """OCR okuyucusunu seçer. Ağır içe aktarmalar yapabilir: olay döngüsü dışında çağrılır."""
        if self.okuyucu_fabrika is None:
            from . import okuma
            return okuma.sec()
        return self.okuyucu_fabrika()

    def baslat(self, okuyucu: Any = None) -> None:
        if self.calisiyor():
            return
        if self.kare_fabrika is None:
            from . import yakalama
            kare = lambda: yakalama.kare_al(self.ayar["kaynak"])  # noqa: E731
            yakalama.kare_al  # erken hata: modül yüklü mü
        else:
            kare = self.kare_fabrika(self.ayar["kaynak"])
        if okuyucu is None:
            okuyucu = self.okuyucu_olustur()
        isleme = Isleme(kare, okuyucu, self.yonetici, self.yayin, lambda: self.ayar)
        self.isleme = isleme
        self.gorev = asyncio.get_running_loop().create_task(isleme.calis())
        self.gorev.add_done_callback(self._gorev_bitti)
        self.yayin.yayinla("durum", {"calisiyor": True, "motor": self.yonetici.birincil.ad,
                                     "yedek": False})
        self.dublaj.senkronla(True)   # dublaj kapalıysa hiçbir şey yapmaz
        self.katman.senkronla(kullanici_istegi=True)

    def _gorev_bitti(self, gorev: asyncio.Task) -> None:
        """Boru hattı kendi kendine ölürse sessizce "çalışıyor" görünmesin."""
        if gorev.cancelled() or gorev is not self.gorev:
            return
        e = gorev.exception()
        log.error("Boru hattı beklenmedik biçimde durdu: %r", e)
        self.gorev = None
        self.yayin.yayinla("durum", {"calisiyor": False, "motor": self.yonetici.birincil.ad,
                                     "yedek": False, "hata": "genel"})

    def durdur(self) -> None:
        self.dublaj.senkronla(False)
        if self.gorev:
            self.gorev.cancel()
            self.gorev = None
        self.katman.kapat()
        self.yayin.yayinla("yazi-sil", {})
        self.yayin.yayinla("ekran-sil", {})
        self.yayin.yayinla("durum", {"calisiyor": False, "motor": self.yonetici.birincil.ad,
                                     "yedek": False})

    async def kapat(self) -> None:
        """Program kapanırken: bütün arka plan işleri iptal edilir ve beklenir, dosyalar kapanır."""
        gorev, self.gorev = self.gorev, None
        if gorev:
            gorev.cancel()
        self.dublaj.durdur()
        self.katman.kapat()
        try:
            await asyncio.to_thread(self.ps5.kapat)
        except Exception:   # noqa: BLE001
            log.debug("PS5 oturumu kapatılamadı", exc_info=True)
        gorevler = [t for t in (gorev, self._yerel_gorev, self.dublaj._gorev, self.dublaj._hazirla_gorevi) if t]
        for t in gorevler:
            t.cancel()
        if gorevler:
            await asyncio.gather(*gorevler, return_exceptions=True)
        try:
            await self.dublaj.kapat_tum()     # işçi süreci, kurulum ve video işi
        except Exception:   # noqa: BLE001 — kapanışta temizlik hatası önemsiz
            log.debug("dublaj kapatılamadı", exc_info=True)
        self.onbellek.kapat()
        self.hafiza.kapat()
        self.oneriler.bitir()


# ---------- ara katmanlar ----------

def _ad_yerel_mi(deger: str | None) -> bool:
    """`Host` / `Origin` içindeki ad bu bilgisayarın yerel adı mı (kapı numarası yok sayılır)."""
    if not deger:
        return False
    d = deger.strip().lower()
    if "://" in d:
        d = d.split("://", 1)[1]
    d = d.split("/", 1)[0]
    if d.startswith("["):
        d = d.split("]", 1)[0] + "]"
    else:
        d = d.rsplit(":", 1)[0] if d.count(":") == 1 else d
    return d in YEREL_ADLAR


@web.middleware
async def yerel_katman(request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]):
    yol = request.path
    if yol == "/" or yol.startswith(("/panel/", "/api/")) or yol == "/panel":
        if uzak_adres(request) not in YEREL:
            return hata("yalniz_yerel", 403, request)
        # DNS yeniden bağlama ve siteler arası istek (CSRF) koruması: yalnız yerel adla, yalnız
        # yerel kökenden. (Başka sitedeki bir sayfa tarayıcınız üzerinden ayarları değiştiremez.)
        if not _ad_yerel_mi(request.headers.get("Host")):
            return hata("yalniz_yerel", 403, request)
        koken = request.headers.get("Origin")
        if koken is not None and not _ad_yerel_mi(koken):
            return hata("yalniz_yerel", 403, request)
    return await handler(request)


@web.middleware
async def kopru_katman(request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]):
    """/kopru/* için CORS; bütün beklenmeyen hatalar JSON olur."""
    if request.method == "OPTIONS" and request.path.startswith("/kopru/"):
        yanit: web.StreamResponse = web.Response(status=204)
    else:
        try:
            yanit = await handler(request)
        except web.HTTPException as e:
            if e.status == 404:
                yanit = hata("bulunamadi", 404, request)
            elif e.status in (400, 413) and request.path.startswith("/api/"):
                yanit = hata("gecersiz_istek", e.status, request)   # bozuk/çok büyük gövde de JSON olsun
            else:
                raise
        except Exception:
            log.exception("Beklenmeyen hata: %s", request.path)
            yanit = hata("sunucu_hatasi", 500, request)
    if request.path.startswith("/kopru/"):
        yanit.headers["Access-Control-Allow-Origin"] = "*"
        yanit.headers["Access-Control-Allow-Headers"] = "*"
    return yanit


def hata(kod: str, durum: int, request: web.Request | None = None, ayrinti: str | None = None) -> web.Response:
    dil = "tr"
    if request is not None:
        d = request.app.get(DURUM)
        dil = d.dil if d else "tr"
    govde: dict[str, Any] = {"hata": kod, "mesaj": metinler.mesaj(kod, dil)}
    if ayrinti:
        govde["ayrinti"] = ayrinti[:300]
    return web.json_response(govde, status=durum)


# ---------- TV uç noktaları ----------

async def merhaba(request: web.Request) -> web.Response:
    return web.json_response({"uygulama": "altyazikoprusu", "surum": SURUM,
                              "protokol": PROTOKOL, "ad": socket.gethostname().upper()})


async def _yaz(r: web.StreamResponse, veri: bytes) -> None:
    """Donmuş (okumayan) istemci sonsuza dek beklemesin."""
    await asyncio.wait_for(r.write(veri), YAZMA_ZAMAN_ASIMI_SN)


async def akis(request: web.Request) -> web.StreamResponse:
    d: Durum = request.app[DURUM]
    if d.yayin.istemci_sayisi >= EN_COK_AKIS:
        return web.json_response({"hata": "cok_istemci"}, status=503, headers={"Retry-After": "5"})
    r = web.StreamResponse(headers={
        "Content-Type": "text/event-stream", "Cache-Control": "no-cache",
        "Connection": "keep-alive", "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": "*"})
    await r.prepare(request)
    q = d.yayin.abone_ol()
    reklam = request.query.get("reklam") == "1"   # PROTOKOL 17.3: bu istemci reklam oynatabilir (TV uygulaması)
    if reklam:
        d.reklam_istemci += 1
    try:
        ilk = [(o, v) for o, v in d.yayin.acilis_olaylari() if o != "durum"]
        ilk.insert(1 if ilk and ilk[0][0] == "gorunum" else 0, ("durum", d.durum_olayi()))
        for olay, veri in ilk:
            await _yaz(r, sse_bicim(olay, veri))
        dongu = asyncio.get_running_loop()
        son_yazma = dongu.time()
        bekleme = min(1.0, NABIZ_SN)   # kopan istemci en geç ~1 sn'de fark edilir (abonelik/bellek sızmaz)
        while True:
            try:
                olay, veri = await asyncio.wait_for(q.get(), bekleme)
            except asyncio.TimeoutError:
                if request.transport is None or request.transport.is_closing():
                    break
                if dongu.time() - son_yazma >= NABIZ_SN:
                    await _yaz(r, b": nabiz\n\n")
                    son_yazma = dongu.time()
                continue
            await _yaz(r, sse_bicim(olay, veri))
            son_yazma = dongu.time()
    except (ConnectionError, asyncio.CancelledError, asyncio.TimeoutError):
        # ConnectionError: Windows'ta istemci kopması ConnectionAbortedError (WinError 10053) de olur
        pass
    finally:
        d.yayin.ayril(q)
        if reklam:
            d.reklam_istemci -= 1
    return r


def _dosya(yol: Path, kok: Path) -> web.StreamResponse:
    try:
        tam = yol.resolve()
        if kok.resolve() in tam.parents and tam.is_file():
            return web.FileResponse(tam, headers={"Cache-Control": "no-cache"})
    except (OSError, ValueError):   # ValueError: yolda NUL baytı gibi geçersiz karakter
        pass
    raise web.HTTPNotFound()


async def panel_ana(request: web.Request) -> web.StreamResponse:
    return _dosya(WEB / "panel" / "index.html", WEB / "panel")


async def panel_dosya(request: web.Request) -> web.StreamResponse:
    return _dosya(WEB / "panel" / request.match_info["yol"], WEB / "panel")


async def tv_sayfa(request: web.Request) -> web.StreamResponse:
    return _dosya(WEB / "tv" / "tv.html", WEB / "tv")


async def obs_sayfa(request: web.Request) -> web.StreamResponse:
    return _dosya(WEB / "tv" / "obs.html", WEB / "tv")


async def statik(request: web.Request) -> web.StreamResponse:
    return _dosya(WEB / "tv" / request.match_info["yol"], WEB / "tv")


# ---------- panel API'si ----------

async def _json(request: web.Request) -> dict[str, Any]:
    try:
        v = await request.json()
    except ValueError:
        raise web.HTTPBadRequest() from None
    if not isinstance(v, dict):
        raise web.HTTPBadRequest()
    return v


def _motor_adi(d: Durum) -> str:
    return d.yonetici.birincil.kod


async def api_durum(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    y = d.yayin.son_yazi
    yanit = {
        "calisiyor": d.calisiyor(), "motor": _motor_adi(d), "yedekte": d.yonetici.yedekte,
        "tv_sayisi": d.yayin.istemci_sayisi, "son_yazi": y["metin"] if y else "",
        "adresler": lan_adresleri(), "kapi": d.calisan_kapi or d.ayar["kapi"],
        **d.yonetici.durum_ek()}
    if d.dublaj_durdu():
        yanit["dublaj_sinir"] = True
    if d.isleme is not None and d.calisiyor():   # §16.4: aşama aşama gecikme
        yanit["gecikme"] = d.isleme.gecikme_bilgisi()
    uyari = await d.kaynak_uyarisi()
    if uyari:
        yanit["uyari"] = uyari
    return web.json_response(yanit)


def _ayar_gorunumu(d: Durum) -> dict[str, Any]:
    cikti = dict(d.ayar)
    cikti["anahtarlar"] = {m: anahtarlar.kayitli_mi(m) for m in anahtarlar.MOTORLAR}
    return cikti


async def api_ayarlar_al(request: web.Request) -> web.Response:
    # kasa okuması bloklayabilir (kilitli Anahtar Zinciri): olay döngüsünü tutmasın
    return web.json_response(await asyncio.to_thread(_ayar_gorunumu, request.app[DURUM]))


_RENK = re.compile(r"#[0-9a-fA-F]{6}")


def _gorunum_gecerli(g: dict[str, Any]) -> bool:
    """TV'ye giden görünüm alanlarının türü/aralığı (bilinmeyen alanlar serbest)."""
    def sayi(v: Any, lo: float, hi: float) -> bool:
        return isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi
    for alan, (lo, hi) in {"yazi_boyutu": (8, 300), "kenar_bosluk": (0, 0.5), "arka_plan": (0, 1),
                           "ekran_olcek": (ayarlar.EN_KUCUK_OLCEK, ayarlar.EN_BUYUK_OLCEK),
                           "en_az_ms": (0, 3000), "karakter_ms": (40, 120)}.items():
        if alan in g and not sayi(g[alan], lo, hi):
            return False
    for alan in ("yazi_rengi", "konusan_rengi"):
        if alan in g and not (isinstance(g[alan], str) and _RENK.fullmatch(g[alan])):
            return False
    if "yerlesim" in g and g["yerlesim"] not in ayarlar.YERLESIMLER:
        return False
    for alan in ("asil_goster", "ekran_cevir", "onceki_goster"):
        if alan in g and not isinstance(g[alan], bool):
            return False
    return True


def _dogrula(k: dict[str, Any]) -> bool:
    kodlar = {b[0] for b in BILGI}
    try:
        if "motor" in k and k["motor"] not in kodlar:
            return False
        if "yedek_motor" in k and k["yedek_motor"] not in kodlar | {"", None}:
            return False
        if "kapi" in k and not (isinstance(k["kapi"], int) and 1024 <= k["kapi"] <= 65535):
            return False
        if "arayuz_dili" in k and k["arayuz_dili"] not in ("tr", "en"):
            return False
        if "cihaz" in k and k["cihaz"] not in (None, "ps5", "xbox", "pc", "kart"):
            return False
        if "tv" in k and k["tv"] not in (None, "lg", "samsung", "androidtv", "yok"):
            return False
        if "hafiza_izni" in k and k["hafiza_izni"] not in (None, True, False):
            return False
        if "hafiza_izni" in k and k["hafiza_izni"] is not None and not isinstance(k["hafiza_izni"], bool):
            return False
        if "kalite" in k and k["kalite"] not in ("en_iyi", "dengeli", "hizli"):
            return False
        if "gosterim" in k and k["gosterim"] not in ayarlar.GOSTERIMLER:
            return False
        if "katman_ekran" in k and not (isinstance(k["katman_ekran"], int) and not isinstance(k["katman_ekran"], bool)
                                        and 1 <= k["katman_ekran"] <= ayarlar.EN_COK_EKRAN):
            return False
        if "kaynak" in k and not (isinstance(k["kaynak"], str) and len(k["kaynak"]) <= 200):
            return False
        for alan in ("kaynak_dil", "hedef_dil"):   # istem metnine girer: kısa, harf/tire
            if alan in k and not (isinstance(k[alan], str) and re.fullmatch(r"[A-Za-z]{2,12}(-[A-Za-z0-9]{1,8})?", k[alan])):
                return False
        if "aktif_oyun" in k and not (isinstance(k["aktif_oyun"], str) and
                                      0 < len(k["aktif_oyun"].strip()) <= 100):
            return False
        for alan in ("ekrani_cevir", "kisa_aciklama", "ses_cevir", "kurulum_tamam", "guncelleme_denetle"):
            if alan in k and not isinstance(k[alan], bool):
                return False
        e = k.get("erisim")
        if e is not None:
            if not isinstance(e, dict) or not erisim_mod.vast_gecerli(e.get("vast_adresi", "")):
                return False
        g = k.get("gorunum")
        if g is not None:
            if not isinstance(g, dict) or g.get("konum", "alt") not in ("alt", "ust"):
                return False
            if not _gorunum_gecerli(g):
                return False
        if "bolgeler" in k and not ayarlar.bolgeler_gecerli(k["bolgeler"]):
            return False
        if "dublaj" in k and not dublaj_mod.ayar_gecerli(k["dublaj"]):
            return False
        if "kisayollar" in k and not kisayol_mod.kisayollar_gecerli(k["kisayollar"]):
            return False
        b = k.get("bolge_altyazi")
        if b is not None and not (isinstance(b, dict) and
                                  all(isinstance(b.get(f), (int, float)) and 0 <= b[f] <= 1
                                      for f in ("x", "y", "g", "y2"))):
            return False
        if "ps5" in k:   # panelden yalnız görüntü ayarları; konsol/anahtarlar /api/ps5/* ile
            p5 = k["ps5"]
            if not (isinstance(p5, dict) and set(p5) <= {"cozunurluk", "kodek"}
                    and p5.get("cozunurluk", 720) in ayarlar.PS5_COZUNURLUKLER and p5.get("kodek", "h264") in ("h264", "hevc")):
                return False
        if "modeller" in k and not (isinstance(k["modeller"], dict) and
                                     all(isinstance(v, str) for v in k["modeller"].values())):
            return False
    except TypeError:
        return False
    return True


async def api_ayarlar_yaz(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    kismi = await _json(request)
    if "bolgeler" in kismi and ayarlar.bolgeler_gecerli(kismi["bolgeler"]):
        kismi["bolgeler"] = ayarlar.bolgeleri_temizle(kismi["bolgeler"])
    # üst düzey ekrani_cevir ile gorunum.ekran_cevir birlikte tutulur
    if "gorunum" in kismi and not isinstance(kismi["gorunum"], dict):
        return hata("gecersiz_ayar", 400, request)
    if "ekrani_cevir" in kismi:
        kismi.setdefault("gorunum", {})["ekran_cevir"] = kismi["ekrani_cevir"]
    elif isinstance(kismi.get("gorunum"), dict) and "ekran_cevir" in kismi["gorunum"]:
        kismi["ekrani_cevir"] = kismi["gorunum"]["ekran_cevir"]
    if not _dogrula(kismi):
        return hata("gecersiz_ayar", 400, request)
    if "dublaj" in kismi:
        duzgun, kod = dublaj_mod.ayar_duzelt(d.ayar["dublaj"], kismi["dublaj"])
        if kod:
            return hata(kod, 400, request)
        kismi["dublaj"] = duzgun
    d.ayar = ayarlar.guncelle(d.ayar, kismi)
    if "dublaj" in kismi:
        d.dublaj.senkronla()
    if "gorunum" in kismi:
        d.yayin.yayinla("gorunum", d.ayar["gorunum"])
    if "kisayollar" in kismi:
        d.kisayol.uygula(d.ayar["kisayollar"])   # tuşlar değişti: eskileri bırak, yenileri kaydet
    if {"gosterim", "katman_ekran", "kaynak"} & kismi.keys():
        d.katman.senkronla(kullanici_istegi=True)   # gösterim/ekran değişti: aç, kapat ya da yeni ekrana taşı
    if {"motor", "yedek_motor", "modeller", "aktif_oyun", "kalite", "hafiza_izni"} & kismi.keys():
        d.yeniden_kur()
    return web.json_response({"tamam": True})


def _motor_listesi() -> list[dict[str, Any]]:
    return [{"kod": k, "ad": ad, "anahtar_gerekli": ag, "anahtar_kayitli": anahtarlar.kayitli_mi(k) if ag else False,
             "cevrimdisi": cd, "ucretsiz": uc} for k, ad, ag, cd, uc in BILGI]


async def api_motorlar(request: web.Request) -> web.Response:
    return web.json_response(await asyncio.to_thread(_motor_listesi))


async def api_anahtar(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    v = await _json(request)
    motor, anahtar = v.get("motor"), v.get("anahtar", "")
    if motor not in anahtarlar.MOTORLAR or not isinstance(anahtar, str):
        return hata("gecersiz_istek", 400, request)
    try:
        await asyncio.to_thread(anahtarlar.yaz, motor, anahtar)
    except anahtarlar.KasaHatasi as e:
        kod = "kasa_yok" if str(e) == "kasa_yok" else "kasa_hata"
        return hata(kod, 503, request)
    d.yeniden_kur()
    return web.json_response({"tamam": True})


def _bilinen_kod(e: BaseException) -> str | None:
    """Hatanın bilinen bir kullanıcı mesajı kodu var mı (`e.kod` ya da ilk argüman)?"""
    for aday in (getattr(e, "kod", None), e.args[0] if e.args else None):
        if isinstance(aday, str) and aday in metinler.HATALAR:
            return aday
    return None


def _ayrinti(e: BaseException) -> str:
    ek = getattr(e, "ayrinti", None)
    return f"{type(e).__name__}: {ek or e}"[:300]


async def api_dene(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    v = await _json(request)
    metin = v.get("metin")
    if not isinstance(metin, str) or not metin.strip():
        return hata("gecersiz_istek", 400, request)
    kod = v.get("motor") or d.ayar["motor"]
    if kod not in {b[0] for b in BILGI} | {"sahte"}:
        return hata("gecersiz_istek", 400, request)
    motor = d.motor_fabrika(kod, d.ayar)
    t0 = time.monotonic()
    try:
        gelen = await motor.cevir([metin], d.ayar["kaynak_dil"], d.ayar["hedef_dil"],
                                  d.yonetici.terimler)
        if len(gelen) != 1:
            raise MotorHatasi("sayi")
        c = gelen[0]
    except AnahtarHatasi as e:
        return hata(_bilinen_kod(e) or ("anahtar_yok" if not anahtarlar.kayitli_mi(kod) else "anahtar_gecersiz"),
                    400, request, _ayrinti(e))
    except AgHatasi as e:
        return hata(_bilinen_kod(e) or "ag_hatasi", 502, request, _ayrinti(e))
    except MotorHatasi as e:
        return hata(_bilinen_kod(e) or "motor_hatasi", 502, request, _ayrinti(e))
    except Exception as e:   # noqa: BLE001 — gerçekten bilinmeyen: genel mesaj + ayrıntı
        log.exception("Çeviri denemesi beklenmedik biçimde başarısız")
        return hata("motor_hatasi", 502, request, _ayrinti(e))
    yanit = {"ceviri": c.metin, "sure_ms": int((time.monotonic() - t0) * 1000)}
    if getattr(motor, "model", None):
        yanit["model"] = motor.model   # asıl motorun gerçekten kullandığı model (yedek motor DEĞİL)
    return web.json_response(yanit)


def _erisim_durumu(d: Durum) -> dict[str, Any]:
    return d.erisim.durum(dublaj_acik=d.dublaj.istenen(), tv_reklam=d.reklam_istemci > 0)


async def api_erisim_al(request: web.Request) -> web.Response:
    return web.json_response(_erisim_durumu(request.app[DURUM]))


REKLAM_DURUMLARI = {"dublaj_sure_dolu": 409, "dublaj_sinirsiz": 409, "reklam_yok": 404, "reklam_erken": 409}


def _reklam_hata(e: erisim_mod.ReklamHatasi, request: web.Request) -> web.Response:
    y = hata(e.kod, REKLAM_DURUMLARI.get(e.kod, 400), request)
    if e.kod == "reklam_erken":
        govde = json.loads(y.body)
        govde["kalan_sn"] = round(e.kalan_sn, 1)
        y = web.json_response(govde, status=409)
    return y


async def api_reklam_baslat(request: web.Request) -> web.Response:
    """PROTOKOL 17.3: "+30 dk ekle" — reklam (ya da destek ekranı) başlar; TV bağlıysa orada oynar."""
    d: Durum = request.app[DURUM]
    try:
        v = await request.json()
    except ValueError:
        v = {}
    yer = v.get("yer") if isinstance(v, dict) else None
    try:
        r = d.erisim.reklam_baslat(d.reklam_istemci > 0, yer if yer in ("otomatik", "panel") else "otomatik")
    except erisim_mod.ReklamHatasi as e:
        return _reklam_hata(e, request)
    if r["hedef"] == "tv":
        d.yayin.yayinla("reklam", {"id": r["id"], "vast": r["vast"], "en_az_sn": r["en_az_sn"],
                                   "bitti": "/kopru/reklam/bitti"})
    return web.json_response(r)


async def _reklam_bitti(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    v = await _json(request)
    try:
        sonuc = d.erisim.reklam_bitir(v.get("id"), v.get("sure_sn"))
    except erisim_mod.ReklamHatasi as e:
        return _reklam_hata(e, request)
    d.yayin.yayinla("reklam-bitti", {"id": sonuc["id"]})
    d.dublaj_izin_degisti()   # duraklamış dublaj kendiliğinden sürer
    return web.json_response(sonuc)


async def api_reklam_bitti(request: web.Request) -> web.Response:
    return await _reklam_bitti(request)


async def kopru_reklam_bitti(request: web.Request) -> web.Response:
    """TV uygulaması reklamı bitirdi (yerel ağ). Süreyi yine sunucu saati belirler."""
    return await _reklam_bitti(request)


async def api_erisim_yaz(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    v = await _json(request)
    kod = v.get("kod")
    if not isinstance(kod, str) or not kod.strip() or len(kod) > 600:
        return hata("gecersiz_kod", 400, request)
    try:
        bilgi = d.erisim.kod_gir(kod)
    except erisim_mod.KodHatasi as e:
        return hata(e.kod, 400, request)
    d.dublaj_izin_degisti()   # dublaj duraklamışsa sürer; panel/TV hemen öğrensin
    return web.json_response({"tamam": True, "tur": bilgi["tur"]})


async def api_baslat(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    if not d.ayar.get("kaynak"):
        return hata("kaynak_yok", 400, request)
    if d.calisiyor():
        return web.json_response({"calisiyor": True})
    # OCR paketlerini içe aktarmak saniyeler sürebilir: olay döngüsü (SSE, panel) donmasın
    kod = await d.baslat_guvenli()
    if kod:
        return hata(kod, 400, request)
    return web.json_response({"calisiyor": True})


async def api_kisayollar(request: web.Request) -> web.Response:
    return web.json_response(request.app[DURUM].kisayol_bilgisi())


async def api_durdur(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    d.durdur()
    if d.ayar.get("kaynak") == "ps5:gizli" and d.ps5.calisiyor():
        # §15: çeviri durunca PS5 oturumu da kapanır (ikinci kullanıcı PS5'te açık kalmasın)
        await asyncio.to_thread(d.ps5.kes)
    return web.json_response({"calisiyor": False})


async def api_kapat(request: web.Request) -> web.Response:
    """Paneldeki 'Programı kapat': konsol penceresi gizli olduğundan kapatmanın yolu budur."""
    d: Durum = request.app[DURUM]
    try:
        d.durdur()
    except Exception:   # noqa: BLE001
        pass

    def _cik() -> None:
        import os
        os._exit(0)
    asyncio.get_running_loop().call_later(0.6, _cik)
    return web.json_response({"tamam": True})


async def api_deneme_yazi(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    d.yayin.yayinla("yazi", {
        "id": f"d{int(time.time())}", "metin": metinler.mesaj("deneme_tr", "tr"),
        "asil": metinler.mesaj("deneme_tr", "en"), "tur": "altyazi",
        "konusan": None, "sure_ms": 4000, "otomatik_sil": True})
    return web.json_response({"tamam": True, "tv_sayisi": d.yayin.istemci_sayisi})


async def api_kaynaklar(request: web.Request) -> web.Response:
    try:
        from . import yakalama
        d: Durum = request.app[DURUM]
        return web.json_response(await asyncio.to_thread(yakalama.kaynaklar, d.ayar.get("cihaz")))
    except YakalamaHatasi:
        return hata("yakalama_yok", 400, request)


KARE_AZAMI_GENISLIK = 1280


def _kare_jpeg(d: Durum) -> bytes:
    import io
    resim = d.kare_al().convert("RGB")
    if resim.width > KARE_AZAMI_GENISLIK:
        resim = resim.resize((KARE_AZAMI_GENISLIK, max(1, round(resim.height * KARE_AZAMI_GENISLIK / resim.width))))
    tampon = io.BytesIO()
    resim.save(tampon, "JPEG", quality=80)
    return tampon.getvalue()


async def api_kare(request: web.Request) -> web.Response:
    """Bölge çizmek için anlık görüntü: yalnız bellekte, diske yazılmaz, önbelleğe alınmaz (PROTOKOL 7.1)."""
    d: Durum = request.app[DURUM]
    if not d.ayar.get("kaynak"):
        return hata("kaynak_yok", 400, request)
    try:
        veri = await asyncio.to_thread(_kare_jpeg, d)
    except YakalamaHatasi:
        return hata("yakalama_yok", 400, request)
    except Exception:
        log.exception("Kare alınamadı")
        return hata("yakalama_yok", 400, request)
    return web.Response(body=veri, content_type="image/jpeg", headers={"Cache-Control": "no-store"})


async def api_sozluk_al(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    oyun = request.query.get("oyun") or d.oyun_kodu
    return web.json_response({"oyun": oyun, "terimler": sozluk_mod.yukle(oyun)})


async def api_sozluk_yaz(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    v = await _json(request)
    terimler = v.get("terimler")
    oyun = v.get("oyun") or d.oyun_kodu
    if not isinstance(oyun, str) or not isinstance(terimler, list) or \
            not all(isinstance(t, dict) and isinstance(t.get("asil"), str) for t in terimler):
        return hata("gecersiz_istek", 400, request)
    sozluk_mod.kaydet(oyun, terimler)
    if oyunlar.kod_coz(oyun) == d.oyun_kodu:
        d.bilgi_yenile()
    return web.json_response({"oyun": oyun, "terimler": sozluk_mod.yukle(oyun)})


# ---------- oyun hafızası (sürüm 0.2) ----------

def _kayit_sayisi(d: Durum, kod: str) -> int:
    return d.hafiza.say() if kod == d.oyun_kodu else hafiza_mod.dosyada_say(kod)


async def api_oyunlar_al(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    liste = []
    for kod in oyunlar.kodlari_listele():
        b = oyunlar.oku(kod) or {}
        liste.append({"kod": kod, "ad": b.get("ad", kod), "kayit_sayisi": _kayit_sayisi(d, kod),
                      "terim_sayisi": len(sozluk_mod.yukle(kod)),
                      "son_oynama": b.get("son_oynama"), "aktif": kod == d.oyun_kodu})
    return web.json_response(liste)


def _oyun_alanlari(v: dict[str, Any]) -> bool:
    return (isinstance(v.get("aciklama", ""), str) and len(v.get("aciklama", "")) <= 2000
            and v.get("hitap", "sen") in ("sen", "siz")
            and isinstance(v.get("karakterler", []), list))


async def api_oyunlar_yaz(request: web.Request) -> web.Response:
    v = await _json(request)
    ad = v.get("ad")
    if not isinstance(ad, str) or not (0 < len(ad.strip()) <= 100):
        return hata("oyun_gecersiz", 400, request)
    if not _oyun_alanlari(v):
        return hata("gecersiz_istek", 400, request)
    kod = oyunlar.olustur(ad, v.get("aciklama", ""), v.get("hitap", "sen"), v.get("karakterler"))
    return web.json_response({"kod": kod})


async def api_oyun_sec(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    kod = (await _json(request)).get("kod")
    if not isinstance(kod, str) or not oyunlar.gecerli_kod(kod) or not oyunlar.var_mi(kod):
        return hata("oyun_yok", 404, request)
    d.ayar = ayarlar.guncelle(d.ayar, {"aktif_oyun": kod})
    if d.izin():
        oyunlar.oynandi_isaretle(kod)  # yalnız izinle (oyun verisi diske yazılır)
    d.yeniden_kur()
    return web.json_response({"kod": kod})


def _kod_al(request: web.Request) -> str | None:
    kod = request.match_info["kod"]
    return kod if oyunlar.gecerli_kod(kod) and oyunlar.var_mi(kod) else None


async def api_oyun_al(request: web.Request) -> web.Response:
    kod = _kod_al(request)
    if kod is None:
        return hata("oyun_yok", 404, request)
    return web.json_response(oyunlar.oku(kod))


async def api_oyun_yaz(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    kod = _kod_al(request)
    if kod is None:
        return hata("oyun_yok", 404, request)
    v = await _json(request)
    if not _oyun_alanlari(v) or ("ad" in v and not (isinstance(v["ad"], str) and len(v["ad"]) <= 100)):
        return hata("gecersiz_istek", 400, request)
    bilgi = oyunlar.guncelle(kod, v)
    if kod == d.oyun_kodu:
        d.bilgi_yenile()
    return web.json_response(bilgi)


BILGI_ZAMAN_ASIMI_SN = 60.0


async def api_oyun_bilgi_hazirla(request: web.Request) -> web.Response:
    """§12.3: seçili LLM motoruyla oyunun adından açıklama + hitap + terim önerisi. Kaydetmez."""
    d: Durum = request.app[DURUM]
    kod = _kod_al(request)
    if kod is None:
        return hata("oyun_yok", 404, request)
    motor = d.yonetici.birincil
    istem = getattr(motor, "serbest_istem", None)
    if not callable(istem) or getattr(motor, "cevrimdisi", False):
        return hata("bilgi_cevrimdisi", 400, request)
    bilgi = oyunlar.oku(kod) or {}
    try:
        ham = await asyncio.wait_for(
            istem(oyun_bilgisi.SISTEM, oyun_bilgisi.kullanici_metni(str(bilgi.get("ad") or kod),
                                                                     str(bilgi.get("aciklama") or ""))),
            BILGI_ZAMAN_ASIMI_SN)
        oneri = oyun_bilgisi.yaniti_coz(ham)
    except AnahtarHatasi as e:
        return hata(_bilinen_kod(e) or ("anahtar_yok" if not anahtarlar.kayitli_mi(motor.kod) else "anahtar_gecersiz"),
                    400, request, _ayrinti(e))
    except (AgHatasi, asyncio.TimeoutError) as e:
        return hata(_bilinen_kod(e) or "ag_hatasi", 502, request, _ayrinti(e))
    except (MotorHatasi, ValueError) as e:
        return hata("bilgi_okunamadi", 502, request, _ayrinti(e))
    except Exception as e:   # noqa: BLE001
        log.exception("Oyun bilgisi hazırlanamadı")
        return hata("bilgi_okunamadi", 502, request, _ayrinti(e))
    return web.json_response(oneri)


async def api_oyun_bilgi_kaydet(request: web.Request) -> web.Response:
    """§12.3: onaylanan öneriyi kaydeder: açıklama/hitap oyun bilgisine, terimler sözlüğe (kullanıcının terimleri kalır)."""
    d: Durum = request.app[DURUM]
    kod = _kod_al(request)
    if kod is None:
        return hata("oyun_yok", 404, request)
    v = await _json(request)
    aciklama, hitap, terimler = v.get("aciklama", ""), v.get("hitap", "sen"), v.get("terimler", [])
    if not (isinstance(aciklama, str) and len(aciklama) <= 2000 and hitap in ("sen", "siz")
            and isinstance(terimler, list) and len(terimler) <= 500):
        return hata("gecersiz_istek", 400, request)
    kismi: dict[str, Any] = {"hitap": hitap}
    if aciklama.strip():
        kismi["aciklama"] = aciklama
    oyun = oyunlar.guncelle(kod, kismi)
    birlesik, eklenen = oyun_bilgisi.birlestir(sozluk_mod.yukle(kod), terimler)
    if eklenen:
        sozluk_mod.kaydet(kod, birlesik)
    if kod == d.oyun_kodu:
        d.bilgi_yenile()
    return web.json_response({"oyun": oyun, "terimler": birlesik, "eklenen": eklenen})


async def api_hafiza_sil(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    kod = _kod_al(request)
    if kod is None:
        return hata("oyun_yok", 404, request)
    if kod == d.oyun_kodu:
        d.hafiza.temizle()
    else:
        h = hafiza_mod.Hafiza(kod)
        try:
            h.temizle()
        finally:
            h.kapat()
    return web.json_response({"tamam": True})


async def api_son_ceviriler(request: web.Request) -> web.Response:
    return web.json_response(list(reversed(request.app[DURUM].yonetici.gecmis)))  # en yeni başta


async def api_duzelt(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    v = await _json(request)
    asil, ceviri = v.get("asil"), v.get("ceviri")
    if not (isinstance(asil, str) and isinstance(ceviri, str) and asil.strip() and ceviri.strip()
            and len(asil) <= 1000 and len(ceviri) <= 1000):
        return hata("gecersiz_istek", 400, request)
    ekranda = d.duzelt(asil, ceviri)
    return web.json_response({"tamam": True, "ekranda": ekranda})


async def api_paket_indir(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    kod = _kod_al(request)
    if kod is None:
        return hata("oyun_yok", 404, request)
    satirlar = d.hafiza.hepsi() if kod == d.oyun_kodu else hafiza_mod.dosyadan_oku(kod)
    veri = paket_mod.olustur(oyunlar.oku(kod) or {}, sozluk_mod.yukle(kod), satirlar)
    return web.Response(body=veri, content_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{kod}.akpaket"'})


async def api_paket_yukle(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    try:
        okuyucu = await request.multipart()
        veri = None
        while (parca := await okuyucu.next()) is not None:
            if parca.name == "dosya":
                tampon = bytearray()
                while True:
                    blok = await parca.read_chunk(1 << 20)
                    if not blok:
                        break
                    tampon += blok
                    if len(tampon) > paket_mod.AZAMI_BAYT:
                        return hata("paket_buyuk", 413, request)
                veri = bytes(tampon)
                break
    except (AssertionError, ValueError, KeyError):
        return hata("paket_gecersiz", 400, request)
    if veri is None:
        return hata("paket_gecersiz", 400, request)
    try:
        p = await asyncio.to_thread(paket_mod.oku, veri)
        kod, eklenen, atlanan, kalici = await asyncio.to_thread(
            paket_mod.uygula, p, d.hafiza, d.izin)
    except paket_mod.PaketHatasi as e:
        return hata(e.kod, 413 if e.kod == "paket_buyuk" else 400, request)
    if kod == d.oyun_kodu:
        d.bilgi_yenile()
    return web.json_response({"tamam": True, "kod": kod, "eklenen": eklenen,
                              "atlanan": atlanan, "kalici": kalici})


async def api_oneriler_al(request: web.Request) -> web.Response:
    return web.json_response(request.app[DURUM].oneriler.liste())


async def api_oneriler_yaz(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    v = await _json(request)
    asil, kabul = v.get("asil"), v.get("kabul")
    if not isinstance(asil, str) or not isinstance(kabul, bool):
        return hata("gecersiz_istek", 400, request)
    oneri = d.oneriler.al(asil)
    if oneri is None:
        return hata("oneri_yok", 404, request)
    if kabul:
        ceviri = v.get("ceviri") if isinstance(v.get("ceviri"), str) and v["ceviri"].strip() else oneri
        mevcut = sozluk_mod.yukle(d.oyun_kodu)
        if not any(t["asil"].casefold() == asil.strip().casefold() for t in mevcut):
            sozluk_mod.kaydet(d.oyun_kodu, mevcut + [{"asil": asil.strip(), "ceviri": ceviri.strip()}])
        d.bilgi_yenile()
    else:
        d.oneriler.reddet(asil)
    return web.json_response({"tamam": True})


# ---------- Türkçe dublaj (PROTOKOL 9.4) ----------

DUBLAJ_DURUMLARI = {"dublaj_hazir_degil": 409, "dublaj_paket_yok": 400, "dublaj_motor_yok": 400,
                    "dublaj_onay_gerekli": 400, "dublaj_eleven_anahtar_yok": 400,
                    "dublaj_eleven_onay_yok": 400, "dublaj_eleven_klon_onay_yok": 400,
                    "dublaj_eleven_ses_yok": 400, "dublaj_eleven_anahtar_gecersiz": 400,
                    "video_suruyor": 409, "video_canli_acik": 409, "dublaj_isci_hata": 502}


def _dublaj_hata(e: DublajHatasi, request: web.Request) -> web.Response:
    return hata(e.kod, DUBLAJ_DURUMLARI.get(e.kod, 502), request)


async def api_dublaj_al(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    b = await d.dublaj.bilgi()
    b["elevenlabs_anahtar"] = await asyncio.to_thread(anahtarlar.kayitli_mi, "elevenlabs")
    b["motorlar"] = [{"kod": k, "ad": ad, "yerel": k != "elevenlabs"} for k, ad in
                     dublaj_mod.MOTOR_ADLARI.items()]
    if b.get("son_hata"):
        b["son_hata_mesaj"] = metinler.mesaj(b["son_hata"], d.dil)
    if b["indirme"].get("hata"):
        b["indirme"]["mesaj"] = metinler.mesaj(b["indirme"]["hata"], d.dil)
    return web.json_response(b)


async def api_dublaj_yaz(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    v = await _json(request)
    parca = v.get("dublaj", v) if isinstance(v.get("dublaj", v), dict) else {}
    if not parca or not dublaj_mod.ayar_gecerli(parca):
        return hata("gecersiz_ayar", 400, request)
    duzgun, kod = dublaj_mod.ayar_duzelt(d.ayar["dublaj"], parca)
    if kod:
        return hata(kod, 400, request)
    d.ayar = ayarlar.guncelle(d.ayar, {"dublaj": duzgun})
    d.dublaj.senkronla()
    return web.json_response({"tamam": True, "dublaj": d.ayar["dublaj"]})


async def api_dublaj_hazirla(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    if d.dublaj.motor() is None:
        return hata("dublaj_motor_yok", 400, request)
    d.dublaj.hazirla_baslat()
    await asyncio.sleep(0)   # ElevenLabs gibi anında biten hazırlıklar ilk yanıtta görünsün
    return web.json_response(await d.dublaj.bilgi())


async def api_dublaj_dene(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    v = await _json(request)
    metin = v.get("metin", "Merhaba, nasılsın?")
    if not isinstance(metin, str) or not metin.strip() or len(metin) > 300:
        return hata("gecersiz_istek", 400, request)
    try:
        return web.json_response(await d.dublaj.dene(metin.strip()))
    except DublajHatasi as e:
        return _dublaj_hata(e, request)


# ---------- dublaj paketi ve video dublajı (PROTOKOL 14) ----------

def _paket_bilgi(d: Durum) -> dict[str, Any]:
    b = d.dublaj.ortam.bilgi()
    if b.get("hata"):
        b["mesaj_hata"] = metinler.mesaj(b["hata"], d.dil)
    return b


async def api_paket_al(request: web.Request) -> web.Response:
    return web.json_response(_paket_bilgi(request.app[DURUM]))


async def api_paket_kur(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    v = await _json(request)
    if v.get("onay") is not True:
        return hata("dublaj_paket_onay", 400, request)
    if not d.dublaj.ortam.destek()[0]:
        return hata("dublaj_paket_desteklenmiyor", 400, request)
    d.dublaj.ortam.kur_baslat()
    await asyncio.sleep(0)
    return web.json_response(_paket_bilgi(d))


async def api_paket_iptal(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    d.dublaj.ortam.iptal()
    await d.dublaj.ortam.bekle()
    return web.json_response(_paket_bilgi(d))


async def api_paket_kaldir(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    v = await _json(request)
    if v.get("onay") is not True:
        return hata("dublaj_paket_onay", 400, request)
    d.dublaj.durdur()
    await d.dublaj.isci.kapat()
    await d.dublaj.ortam.kaldir()
    return web.json_response(_paket_bilgi(d))


async def api_dublaj_girisler(request: web.Request) -> web.Response:
    """Yakalama kartı sesi için girişlerin YALNIZ adları (hiçbiri açılmaz)."""
    d: Durum = request.app[DURUM]
    try:
        return web.json_response({"girisler": await d.dublaj.girisler()})
    except DublajHatasi as e:
        return _dublaj_hata(e, request)


async def api_profiller_al(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    p = d.dublaj.profiller()
    return web.json_response({"izin": bool(d.ayar["dublaj"].get("ses_profili_izni")),
                              "oyun": d.ayar.get("aktif_oyun"), "profiller": await asyncio.to_thread(p.liste)})


async def api_profiller_sil(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    ad = request.query.get("ad") or None
    n = await asyncio.to_thread(d.dublaj.profiller().sil, ad)
    return web.json_response({"tamam": True, "silinen": n})


async def api_dosya_sec(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    from .dublaj import video as video_mod
    yol = await d.dosya_secici()
    if not yol:
        return web.json_response({"yol": None})
    p = video_mod.video_gecerli(yol)
    if p is None:
        return hata("video_gecersiz", 400, request)
    return web.json_response({"yol": str(p), "ad": p.name, "boyut_mb": round(p.stat().st_size / 1048576)})


async def api_video_al(request: web.Request) -> web.Response:
    return web.json_response(request.app[DURUM].dublaj.video_bilgi())


async def api_video_baslat(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    from .dublaj import video as video_mod
    v = await _json(request)
    p = video_mod.video_gecerli(v.get("yol"))
    if p is None:
        return hata("video_gecersiz", 400, request)
    try:
        b = d.dublaj.video_baslat(p, d.yonetici, d.video_is_koku)
    except DublajHatasi as e:
        if e.kod == "dublaj_suresi_yok":
            return hata(e.kod, 402, request)
        return hata(e.kod, 409 if e.kod in ("dublaj_paket_yok", "video_suruyor", "video_canli_acik") else 400, request)
    return web.json_response(b)


async def api_video_iptal(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    await d.dublaj.video_iptal()
    return web.json_response(d.dublaj.video_bilgi())


async def api_video_goster(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    b = d.dublaj.video_bilgi()
    if not b.get("cikti"):
        return hata("bulunamadi", 404, request)
    await asyncio.to_thread(d.klasorde_goster, b["cikti"])
    return web.json_response({"tamam": True})


async def kopru_ses(request: web.Request) -> web.Response:
    """TV için dublaj sesi: yalnız bellekten, 60 sn sonra 404 (PROTOKOL 9.4)."""
    d: Durum = request.app[DURUM]
    veri = d.dublaj.depo.al(request.match_info["kimlik"])
    if veri is None:
        raise web.HTTPNotFound()
    return web.Response(body=veri, content_type="audio/wav", headers={"Cache-Control": "no-store"})


# ---------- güncelleme ve TV kurulumu ----------

async def api_guncelleme_al(request: web.Request) -> web.Response:
    g: guncelleme_mod.Guncelleme = request.app[GUNCELLEME]
    g.arka_planda_denetle()    # ayar kapalıysa ya da bugün bakıldıysa hiçbir şey yapmaz
    return web.json_response(g.durum())


async def api_guncelleme_denetle(request: web.Request) -> web.Response:
    """Kullanıcı "Güncellemeleri denetle"ye bastı: ayar kapalı olsa da bu kez bakılır."""
    g: guncelleme_mod.Guncelleme = request.app[GUNCELLEME]
    if g.destekli:
        await g.denetle(elle=True)
    return web.json_response(g.durum())


async def api_guncelleme_kur(request: web.Request) -> web.Response:
    g: guncelleme_mod.Guncelleme = request.app[GUNCELLEME]
    kod = g.kur_baslat()
    if kod:
        return hata(kod, 400, request)
    return web.json_response(g.durum())


async def api_tv_lg_kur(request: web.Request) -> web.Response:
    lg: LgKurulum = request.app[LG_KURULUM]
    v = await _json(request)
    kod = lg.baslat(v.get("ip"), v.get("parola"), v.get("paket", "asil"))
    if kod:
        return hata(kod, 409 if kod == "tv_mesgul" else 400, request)
    return web.json_response(lg.durum())


async def api_tv_lg_durum(request: web.Request) -> web.Response:
    return web.json_response(request.app[LG_KURULUM].durum())


# ---------- ekran katmanı, okuma denemesi, çevrimdışı motor (PROTOKOL 10.2) ----------

async def api_katman_al(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    ekranlar = await asyncio.to_thread(katman_yonetim.ekranlari_listele)
    b = d.katman.bilgi()
    cikti = {"destek": b["destek"], "acik": b["acik"], "ekran": d.ayar.get("katman_ekran", 1),
             "ekranlar": ekranlar}
    hata_kodu = b["hata"] if b["hata"] else (None if b["destek"] else "katman_destek_yok")
    if hata_kodu:
        cikti["hata"], cikti["mesaj"] = hata_kodu, metinler.mesaj(hata_kodu, d.dil)
    return web.json_response(cikti)


async def api_katman_dene(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    if not d.katman.destek():
        return hata("katman_destek_yok", 400, request)
    acik = await asyncio.to_thread(d.katman.dene)
    if not acik:
        return hata(d.katman.son_hata or "katman_destek_yok", 400, request)
    sure = 4000
    d.yayin.yayinla("yazi", {
        "id": f"k{int(time.time())}", "metin": metinler.mesaj("katman_deneme", "tr"),
        "asil": metinler.mesaj("katman_deneme", "en"), "tur": "altyazi",
        "konusan": None, "sure_ms": sure, "devam": False, "otomatik_sil": True})
    return web.json_response({"tamam": True, "acik": True, "sure_ms": sure})


def _okuma_dene(d: Durum) -> dict[str, Any]:
    t0 = time.monotonic()
    kare = d.kare_al()
    if d._okuma_dene_okuyucu is None:
        d._okuma_dene_okuyucu = d.okuyucu_olustur()
    okuyucu = d._okuma_dene_okuyucu
    satirlar = okuyucu.oku(kare)
    return {"satirlar": [{"metin": s.metin, "x": round(s.x, 4), "y": round(s.y, 4),
                          "g": round(s.g, 4), "y2": round(s.y2, 4)} for s in satirlar if s.metin.strip()],
            "sure_ms": int((time.monotonic() - t0) * 1000),
            "okuyucu": str(getattr(okuyucu, "ad", type(okuyucu).__name__))}


async def api_okuma_dene(request: web.Request) -> web.Response:
    """Bir kare al, bütün karede yazıları oku, normalize kutularıyla döndür (sihirbaz adım 2)."""
    d: Durum = request.app[DURUM]
    if not d.ayar.get("kaynak"):
        return hata("kaynak_yok", 400, request)
    try:
        return web.json_response(await asyncio.to_thread(_okuma_dene, d))
    except YakalamaHatasi as e:
        return hata("yakalama_yok", 400, request, _ayrinti(e))
    except OkumaHatasi as e:
        d._okuma_dene_okuyucu = None
        return hata("okuma_yok", 400, request, _ayrinti(e))
    except Exception as e:   # noqa: BLE001
        log.exception("Okuma denemesi başarısız")
        d._okuma_dene_okuyucu = None
        return hata("okuma_yok", 500, request, _ayrinti(e))


async def api_okuma_diller(request: web.Request) -> web.Response:
    """Windows'ta kurulu yazı okuma dilleri; İngilizce paket yoksa panel kurmayı önerir."""
    if sys.platform != "win32":
        return web.json_response({"destek": False, "kurulu": [], "ingilizce": True})
    from .okuma import windows as wocr
    kurulu = await asyncio.to_thread(wocr.kurulu_diller)
    return web.json_response({"destek": True, "kurulu": kurulu, "ingilizce": wocr.ingilizce_var(kurulu),
                              "kullanilan": wocr.dil_sec(kurulu)})


async def api_okuma_ingilizce_kur(request: web.Request) -> web.Response:
    """İngilizce OCR paketini Windows'un kendi aracıyla kurar; Windows yönetici izni (UAC) penceresi açılır."""
    if sys.platform != "win32":
        return hata("desteklenmiyor", 400, request)
    from .okuma import windows as wocr
    import subprocess
    komut = ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
             "Start-Process powershell -Verb RunAs -WindowStyle Hidden -ArgumentList "
             "'-NoProfile','-Command','" + wocr.EN_PAKETI_KOMUTU.replace("'", "''") + "'"]
    try:
        await asyncio.to_thread(subprocess.Popen, komut, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as e:
        return hata("okuma_yok", 500, request, _ayrinti(e))
    return web.json_response({"tamam": True, "baslatildi": True})


_DIL = re.compile(r"[A-Za-z]{2,12}(-[A-Za-z0-9]{1,8})?")


def _yerel_diller(d: Durum, v: dict[str, Any] | None = None) -> tuple[str, str]:
    v = v or {}
    kaynak = v.get("kaynak") or d.ayar.get("kaynak_dil") or "en"
    if kaynak in ("otomatik", "auto"):
        kaynak = "en"
    hedef = v.get("hedef") or d.ayar.get("hedef_dil") or "tr"
    if not (isinstance(kaynak, str) and _DIL.fullmatch(kaynak) and isinstance(hedef, str) and _DIL.fullmatch(hedef)):
        return "en", "tr"
    return kaynak, hedef


async def _yerel_durum_json(d: Durum, kaynak: str, hedef: str) -> dict[str, Any]:
    from .ceviri import yerel as yerel_mod
    try:
        b = dict(await asyncio.to_thread(yerel_mod.durum, kaynak, hedef))
    except Exception as e:   # noqa: BLE001 — durum okunamadı: "hazır değil" de, ayrıntıyı ver
        b = {"hazir": False, "boyut_mb": None, "ayrinti": _ayrinti(e)}
    ind = dict(d.yerel_indirme)
    if ind["durum"] == "yok" and isinstance(b.get("indirme"), dict):
        ind = b["indirme"]
    b["indirme"] = {"durum": ind.get("durum", "yok"), "yuzde": ind.get("yuzde", 0), "mesaj": ind.get("mesaj"),
                    **({"ayrinti": ind["ayrinti"]} if ind.get("ayrinti") else {})}
    b.setdefault("hazir", False)
    b.setdefault("boyut_mb", None)
    if not b["hazir"] and b["indirme"]["durum"] in ("yok", "hata") and not b["indirme"]["mesaj"]:
        b["mesaj"] = metinler.mesaj("yerel_dil_dosyasi_yok", d.dil)
    return b


async def api_yerel_al(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    return web.json_response(await _yerel_durum_json(d, *_yerel_diller(d)))


async def _yerel_hazirla(d: Durum, kaynak: str, hedef: str) -> None:
    from .ceviri import yerel as yerel_mod
    ind = d.yerel_indirme

    def ilerleme(*a: Any) -> None:
        try:
            ind["yuzde"] = max(0, min(99, int(float(a[0]))))
        except (IndexError, TypeError, ValueError):
            pass
    ind.update(durum="iniyor", yuzde=0, mesaj=None, ayrinti=None)
    try:
        await yerel_mod.hazirla(kaynak, hedef, ilerleme)
        ind.update(durum="bitti", yuzde=100)
    except asyncio.CancelledError:
        raise
    except Exception as e:   # noqa: BLE001
        kod = _bilinen_kod(e) or ("yerel_bilesen_yok" if isinstance(e, ImportError) else "yerel_indirme_hatasi")
        log.warning("Çevrimdışı dil dosyası hazırlanamadı: %s", e)
        ind.update(durum="hata", mesaj=metinler.mesaj(kod, d.dil), ayrinti=_ayrinti(e), kod=kod)


async def api_yerel_hazirla(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    try:
        v = await request.json() if request.can_read_body else {}
    except ValueError:
        v = {}
    kaynak, hedef = _yerel_diller(d, v if isinstance(v, dict) else {})
    if not (d._yerel_gorev and not d._yerel_gorev.done()):
        d._yerel_gorev = asyncio.get_running_loop().create_task(_yerel_hazirla(d, kaynak, hedef))
        d.yerel_indirme.update(durum="iniyor", yuzde=0, mesaj=None, ayrinti=None)
        await asyncio.sleep(0)
    return web.json_response(await _yerel_durum_json(d, kaynak, hedef))


# ---------- PS5 gizli bağlantı (PROTOKOL §15.7) ----------

def _ps5_govde(d: Durum) -> dict[str, Any]:
    from .uzaktan import kayit as kayit_mod, psn as psn_mod
    ok, neden = d.ps5.destek()
    hesap = kayit_mod.hesap_oku()
    kayit = kayit_mod.kayit_oku()
    a = d.ps5.ayar()
    konsol = None
    if kayit or a.get("host"):
        konsol = {"host": a.get("host") or (kayit or {}).get("host"), "ad": a.get("ad") or (kayit or {}).get("ad"),
                  "kayitli": kayit is not None}
    return {"destek": ok, "neden": neden, "hesap": {"var": bool(hesap), "ozet": psn_mod.ozet(hesap)},
            "konsol": konsol, "baglanti": d.ps5.durum(), "kol_tv": a.get("kol_tv"),
            "kaynak_secili": d.ayar.get("kaynak") == "ps5:gizli"}


def _ps5_hata(e: BaseException, request: web.Request, durum: int = 502) -> web.Response:
    kod = getattr(e, "kod", None) or "ps5_kayit_hata"
    if kod in ("ps5_pin_gecersiz", "psn_kod_yok", "psn_reddetti", "psn_kimlik_gecersiz"):
        durum = 400
    elif kod in ("psn_hesap_yok", "ps5_kayit_yok", "ps5_yardimci_yok", "ps5_yalniz_windows"):
        durum = 409
    elif kod == "psn_cok_deneme":
        durum = 429
    return hata(kod, durum, request, getattr(e, "ayrinti", None))


async def api_ps5_al(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    return web.json_response(await asyncio.to_thread(_ps5_govde, d))


async def api_ps5_psn_adres(request: web.Request) -> web.Response:
    from .uzaktan import psn as psn_mod
    return web.json_response({"adres": psn_mod.giris_adresi()})


async def _ps5_hesap_yaz(d: Durum, request: web.Request, b64: str) -> web.Response:
    from .uzaktan import kayit as kayit_mod, psn as psn_mod
    try:
        await asyncio.to_thread(kayit_mod.hesap_yaz, b64)
    except anahtarlar.KasaHatasi as e:
        return hata("kasa_yok" if str(e) == "kasa_yok" else "kasa_hata", 503, request)
    return web.json_response({"tamam": True, "ozet": psn_mod.ozet(b64)})


async def api_ps5_psn_kod(request: web.Request) -> web.Response:
    from .uzaktan import psn as psn_mod
    d: Durum = request.app[DURUM]
    v = await _json(request)
    istek = request.app.get(PSN_ISTEK)
    try:
        kod = psn_mod.kod_cikar(str(v.get("adres") or ""))
        b64 = await asyncio.to_thread(psn_mod.hesap_kimligi, kod, istek)
    except psn_mod.PsnHatasi as e:
        return _ps5_hata(e, request)
    return await _ps5_hesap_yaz(d, request, b64)


async def api_ps5_psn_elle(request: web.Request) -> web.Response:
    from .uzaktan import psn as psn_mod
    d: Durum = request.app[DURUM]
    v = await _json(request)
    kimlik = v.get("kimlik")
    if not psn_mod.kimlik_gecerli(kimlik):
        return hata("psn_kimlik_gecersiz", 400, request)
    return await _ps5_hesap_yaz(d, request, str(kimlik).strip())


_IPV4 = re.compile(r"(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}")


async def api_ps5_bul(request: web.Request) -> web.Response:
    from .uzaktan import YardimciHatasi
    d: Durum = request.app[DURUM]
    v = await _json(request) if request.can_read_body else {}
    host = str(v.get("host") or "").strip() or None
    if host and not _IPV4.fullmatch(host):
        return hata("gecersiz_istek", 400, request)
    try:
        konsollar = await asyncio.to_thread(d.ps5.bul, host)
    except YardimciHatasi as e:
        return _ps5_hata(e, request)
    return web.json_response({"konsollar": konsollar})


async def api_ps5_kaydet(request: web.Request) -> web.Response:
    from .uzaktan import YardimciHatasi
    d: Durum = request.app[DURUM]
    v = await _json(request)
    host = str(v.get("host") or "").strip()
    if not _IPV4.fullmatch(host):
        return hata("gecersiz_istek", 400, request)
    try:
        sonuc = await asyncio.to_thread(d.ps5.kaydet, host, v.get("pin"))
    except YardimciHatasi as e:
        return _ps5_hata(e, request)
    except anahtarlar.KasaHatasi as e:
        return hata("kasa_yok" if str(e) == "kasa_yok" else "kasa_hata", 503, request)
    d.ayar = ayarlar.guncelle(d.ayar, {"ps5": {"host": host, "ad": sonuc.get("ad") or "PS5"}})
    return web.json_response({"tamam": True, "ad": sonuc.get("ad")})


async def api_ps5_baglan(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    ok, neden = d.ps5.destek()
    if not ok:
        return hata("ps5_yardimci_yok" if neden == "yardimci_yok" else "ps5_yalniz_windows", 409, request)
    await asyncio.to_thread(d.ps5.baglan)
    return web.json_response(await asyncio.to_thread(_ps5_govde, d))


async def api_ps5_kes(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    await asyncio.to_thread(d.ps5.kes)
    return web.json_response({"tamam": True})


async def api_ps5_uyandir(request: web.Request) -> web.Response:
    from .uzaktan import YardimciHatasi
    d: Durum = request.app[DURUM]
    try:
        ok = await asyncio.to_thread(d.ps5.uyandir)
    except YardimciHatasi as e:
        return _ps5_hata(e, request)
    return web.json_response({"tamam": bool(ok)})


async def api_ps5_onizleme(request: web.Request) -> web.Response:
    from .uzaktan import YardimciHatasi
    d: Durum = request.app[DURUM]
    try:
        veri = await asyncio.to_thread(d.ps5.onizleme_jpeg)
    except YardimciHatasi:
        return hata("ps5_kare_yok", 404, request)
    return web.Response(body=veri, content_type="image/jpeg", headers={"Cache-Control": "no-store"})


async def api_ps5_kol(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    v = await _json(request)
    if not isinstance(v.get("calisiyor"), bool):
        return hata("gecersiz_istek", 400, request)
    d.ayar = ayarlar.guncelle(d.ayar, {"ps5": {"kol_tv": v["calisiyor"]}})
    return web.json_response({"tamam": True})


async def api_ps5_giris_pin(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    v = await _json(request)
    pin = str(v.get("pin") or "")
    if not (pin.isdigit() and len(pin) == 4):
        return hata("gecersiz_istek", 400, request)
    await asyncio.to_thread(d.ps5.giris_pin, pin)
    return web.json_response({"tamam": True})


async def api_ps5_unut(request: web.Request) -> web.Response:
    from .uzaktan import kayit as kayit_mod
    d: Durum = request.app[DURUM]
    await asyncio.to_thread(d.ps5.kes)
    await asyncio.to_thread(kayit_mod.unut)
    yeni = {"ps5": {"host": "", "ad": "", "kol_tv": None}}
    if d.ayar.get("kaynak") == "ps5:gizli":
        yeni["kaynak"] = "ekran:1"
    d.ayar = ayarlar.guncelle(d.ayar, yeni)
    return web.json_response({"tamam": True})


def uygulama_olustur(ayar: dict[str, Any] | None = None, guncelleme: Any = None, lg_kurulum: Any = None,
                     psn_istek: Any = None, **fabrikalar: Any) -> web.Application:
    app = web.Application(middlewares=[kopru_katman, yerel_katman])
    app[PSN_ISTEK] = psn_istek
    durum = Durum(ayar if ayar is not None else ayarlar.yukle(), **fabrikalar)
    app[DURUM] = durum
    app[GUNCELLEME] = guncelleme or guncelleme_mod.Guncelleme(lambda: durum.ayar)
    app[LG_KURULUM] = lg_kurulum or LgKurulum(lambda: durum.ayar)
    r = app.router
    r.add_get("/kopru/merhaba", merhaba)
    r.add_get("/kopru/akis", akis)
    r.add_get("/kopru/ses/{kimlik}.wav", kopru_ses)
    r.add_get("/", panel_ana)
    r.add_get("/panel/{yol:.+}", panel_dosya)
    r.add_get("/tv", tv_sayfa)
    r.add_get("/obs", obs_sayfa)
    r.add_get("/statik/{yol:.+}", statik)
    r.add_get("/api/durum", api_durum)
    r.add_get("/api/ayarlar", api_ayarlar_al)
    r.add_post("/api/ayarlar", api_ayarlar_yaz)
    r.add_get("/api/motorlar", api_motorlar)
    r.add_post("/api/anahtar", api_anahtar)
    r.add_post("/api/dene", api_dene)
    r.add_get("/api/erisim", api_erisim_al)
    r.add_post("/api/erisim", api_erisim_yaz)
    r.add_post("/api/erisim/reklam", api_reklam_baslat)
    r.add_post("/api/erisim/reklam/bitti", api_reklam_bitti)
    r.add_post("/kopru/reklam/bitti", kopru_reklam_bitti)
    r.add_post("/api/baslat", api_baslat)
    r.add_post("/api/durdur", api_durdur)
    r.add_get("/api/kisayollar", api_kisayollar)
    r.add_post("/api/deneme-yazi", api_deneme_yazi)
    r.add_get("/api/kaynaklar", api_kaynaklar)
    r.add_get("/api/kare", api_kare)
    r.add_get("/api/sozluk", api_sozluk_al)
    r.add_post("/api/sozluk", api_sozluk_yaz)
    r.add_get("/api/oyunlar", api_oyunlar_al)
    r.add_post("/api/oyunlar", api_oyunlar_yaz)
    r.add_post("/api/oyun-sec", api_oyun_sec)
    r.add_get("/api/oyun/{kod}", api_oyun_al)
    r.add_post("/api/oyun/{kod}", api_oyun_yaz)
    r.add_post("/api/oyun/{kod}/bilgi-hazirla", api_oyun_bilgi_hazirla)
    r.add_post("/api/oyun/{kod}/bilgi-kaydet", api_oyun_bilgi_kaydet)
    r.add_delete("/api/oyun/{kod}/hafiza", api_hafiza_sil)
    r.add_get("/api/son-ceviriler", api_son_ceviriler)
    r.add_post("/api/duzelt", api_duzelt)
    r.add_get("/api/paket/{kod}", api_paket_indir)
    r.add_post("/api/paket", api_paket_yukle)
    r.add_get("/api/guncelleme", api_guncelleme_al)
    r.add_post("/api/guncelleme/denetle", api_guncelleme_denetle)
    r.add_post("/api/guncelleme/kur", api_guncelleme_kur)
    r.add_post("/api/tv/lg/kur", api_tv_lg_kur)
    r.add_get("/api/tv/lg/durum", api_tv_lg_durum)
    r.add_get("/api/oneriler", api_oneriler_al)
    r.add_post("/api/oneriler", api_oneriler_yaz)
    r.add_get("/api/ekran-katmani", api_katman_al)
    r.add_post("/api/ekran-katmani/dene", api_katman_dene)
    r.add_get("/api/okuma-dene", api_okuma_dene)
    r.add_get("/api/okuma/diller", api_okuma_diller)
    r.add_post("/api/kapat", api_kapat)
    r.add_post("/api/okuma/ingilizce-kur", api_okuma_ingilizce_kur)
    r.add_get("/api/motor/yerel", api_yerel_al)
    r.add_post("/api/motor/yerel/hazirla", api_yerel_hazirla)
    r.add_get("/api/dublaj", api_dublaj_al)
    r.add_post("/api/dublaj", api_dublaj_yaz)
    r.add_post("/api/dublaj/hazirla", api_dublaj_hazirla)
    r.add_post("/api/dublaj/dene", api_dublaj_dene)
    r.add_get("/api/dublaj/paket", api_paket_al)
    r.add_post("/api/dublaj/paket/kur", api_paket_kur)
    r.add_post("/api/dublaj/paket/iptal", api_paket_iptal)
    r.add_post("/api/dublaj/paket/kaldir", api_paket_kaldir)
    r.add_get("/api/dublaj/girisler", api_dublaj_girisler)
    r.add_get("/api/dublaj/ses-profilleri", api_profiller_al)
    r.add_delete("/api/dublaj/ses-profilleri", api_profiller_sil)
    r.add_post("/api/dublaj/dosya-sec", api_dosya_sec)
    r.add_get("/api/dublaj/video", api_video_al)
    r.add_post("/api/dublaj/video", api_video_baslat)
    r.add_post("/api/dublaj/video/iptal", api_video_iptal)
    r.add_post("/api/dublaj/video/goster", api_video_goster)
    r.add_get("/api/ps5", api_ps5_al)
    r.add_delete("/api/ps5", api_ps5_unut)
    r.add_post("/api/ps5/psn/adres", api_ps5_psn_adres)
    r.add_post("/api/ps5/psn/kod", api_ps5_psn_kod)
    r.add_post("/api/ps5/psn/elle", api_ps5_psn_elle)
    r.add_post("/api/ps5/bul", api_ps5_bul)
    r.add_post("/api/ps5/kaydet", api_ps5_kaydet)
    r.add_post("/api/ps5/baglan", api_ps5_baglan)
    r.add_post("/api/ps5/kes", api_ps5_kes)
    r.add_post("/api/ps5/uyandir", api_ps5_uyandir)
    r.add_get("/api/ps5/onizleme", api_ps5_onizleme)
    r.add_post("/api/ps5/kol", api_ps5_kol)
    r.add_post("/api/ps5/giris-pin", api_ps5_giris_pin)

    async def durum_dongusu() -> None:
        while True:
            await asyncio.sleep(DURUM_SN)
            try:
                durum.yayin.yayinla("durum", durum.durum_olayi())
            except Exception:   # bir hata döngüyü öldürüp durum akışını sessizce kesmesin
                log.exception("Durum yayını başarısız")

    async def erisim_dongusu() -> None:
        while True:
            await asyncio.sleep(ERISIM_SN)
            try:
                durum.erisim_say()
            except Exception:   # sayaç hatası (ör. disk) döngüyü öldürüp süreyi donduramaz
                log.exception("Erişim sayacı adımı başarısız")

    async def katman_dongusu() -> None:
        while True:
            await asyncio.sleep(KATMAN_SN)
            try:
                durum.katman.izle()
            except Exception:   # noqa: BLE001
                log.exception("Ekran katmanı denetimi başarısız")

    async def ac(_: web.Application) -> None:
        durum._dongu = asyncio.get_running_loop()
        await asyncio.to_thread(anahtarlar.isit)
        await asyncio.to_thread(durum.erisim.isit)   # kasadaki kod + cihaz numarası (döngüyü tutmasın)
        durum.kisayol.baslat(asyncio.get_running_loop(), durum.ayar.get("kisayollar") or {})
        app["katman_gorevi"] = asyncio.create_task(katman_dongusu())   # kasa ilk okuması olay döngüsünü tutmasın
        app["durum_gorevi"] = asyncio.create_task(durum_dongusu())
        app["erisim_gorevi"] = asyncio.create_task(erisim_dongusu())

    async def kapat(_: web.Application) -> None:
        arka = [app[k] for k in ("durum_gorevi", "erisim_gorevi", "katman_gorevi") if k in app]
        for t in arka:
            t.cancel()
        await asyncio.gather(*arka, return_exceptions=True)
        durum.kisayol.durdur()
        await durum.kapat()
        await app[GUNCELLEME].kapat()
        await _http.ortak_kapat()   # §16.4: açık tutulan çeviri bağlantıları
    app.on_startup.append(ac)
    app.on_cleanup.append(kapat)
    return app
