# SPDX-License-Identifier: AGPL-3.0-only
"""aiohttp sunucusu: SSE akışı, panel API'si, statik sayfalar."""
from __future__ import annotations

import asyncio
import logging
import socket
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from aiohttp import web

from . import PROTOKOL, SURUM, ayarlar, anahtarlar, metinler, sozluk as sozluk_mod
from .ceviri import BILGI, motor_olustur
from .ceviri.temel import AgHatasi, AnahtarHatasi, MotorHatasi
from .ceviri.yonetici import CeviriYoneticisi
from .isleme import Isleme
from .okuma import OkumaHatasi
from .onbellek import Onbellek
from .yakalama import YakalamaHatasi
from .yayin import Yayin, sse_bicim

log = logging.getLogger("kopru.sunucu")
WEB = Path(__file__).parent / "web"
NABIZ_SN = 15.0
DURUM_SN = 20.0  # EventSource yorum satırını görmez; gerçek olay gerekir
YEREL = {"127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"}
DURUM = web.AppKey("durum", object)


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
    try:
        for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = a[4][0]
            if not ip.startswith("127.") and ip not in bulunan:
                bulunan.append(ip)
    except OSError:
        pass
    return [ip for ip in bulunan if not ip.startswith("127.") and ip != "0.0.0.0"]


class Durum:
    """Uygulamanın çalışma durumu."""

    def __init__(self, ayar: dict[str, Any], motor_fabrika: Callable[[str, dict], Any] = motor_olustur,
                 kare_fabrika: Callable[[str], Callable[[], Any]] | None = None,
                 okuyucu_fabrika: Callable[[], Any] | None = None) -> None:
        self.ayar = ayar
        self.yayin = Yayin()
        self.motor_fabrika = motor_fabrika
        self.kare_fabrika = kare_fabrika
        self.okuyucu_fabrika = okuyucu_fabrika
        self.onbellek = Onbellek(ayarlar.ayar_dizini() / "onbellek.sqlite3")
        self.yonetici = self._yonetici_kur()
        self.gorev: asyncio.Task | None = None
        self.yayin.yayinla("gorunum", ayar["gorunum"])

    @property
    def dil(self) -> str:
        return self.ayar.get("arayuz_dili", "tr")

    def _yonetici_kur(self) -> CeviriYoneticisi:
        a = self.ayar
        yedek_kod = a.get("yedek_motor") or None
        y = CeviriYoneticisi(self.motor_fabrika(a["motor"], a),
                             self.motor_fabrika(yedek_kod, a) if yedek_kod and yedek_kod != a["motor"] else None,
                             self.onbellek, self.yayin.yayinla, a["aktif_oyun"])
        y.terimler = sozluk_mod.sozluk_dict(sozluk_mod.yukle(a["aktif_oyun"]))
        return y

    def yeniden_kur(self) -> None:
        self.yonetici = self._yonetici_kur()
        if self.gorev and not self.gorev.done():
            self.durdur()
            self.baslat()

    def durum_olayi(self) -> dict[str, Any]:
        motor = self.yonetici.yedek if self.yonetici.yedekte and self.yonetici.yedek else self.yonetici.birincil
        return {"calisiyor": self.calisiyor(), "motor": motor.ad, "yedek": bool(self.yonetici.yedekte)}

    def calisiyor(self) -> bool:
        return bool(self.gorev and not self.gorev.done())

    def baslat(self) -> None:
        if self.calisiyor():
            return
        if self.kare_fabrika is None:
            from . import yakalama
            kare = lambda: yakalama.kare_al(self.ayar["kaynak"])  # noqa: E731
            yakalama.kare_al  # erken hata: modül yüklü mü
        else:
            kare = self.kare_fabrika(self.ayar["kaynak"])
        if self.okuyucu_fabrika is None:
            from . import okuma
            okuyucu = okuma.sec()
        else:
            okuyucu = self.okuyucu_fabrika()
        isleme = Isleme(kare, okuyucu, self.yonetici, self.yayin, lambda: self.ayar)
        self.gorev = asyncio.get_running_loop().create_task(isleme.calis())
        self.yayin.yayinla("durum", {"calisiyor": True, "motor": self.yonetici.birincil.ad,
                                     "yedek": False})

    def durdur(self) -> None:
        if self.gorev:
            self.gorev.cancel()
            self.gorev = None
        self.yayin.yayinla("yazi-sil", {})
        self.yayin.yayinla("ekran-sil", {})
        self.yayin.yayinla("durum", {"calisiyor": False, "motor": self.yonetici.birincil.ad,
                                     "yedek": False})


# ---------- ara katmanlar ----------

@web.middleware
async def yerel_katman(request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]):
    yol = request.path
    if yol == "/" or yol.startswith(("/panel/", "/api/")) or yol == "/panel":
        if uzak_adres(request) not in YEREL:
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
            else:
                raise
        except Exception:
            log.exception("Beklenmeyen hata: %s", request.path)
            yanit = hata("sunucu_hatasi", 500, request)
    if request.path.startswith("/kopru/"):
        yanit.headers["Access-Control-Allow-Origin"] = "*"
        yanit.headers["Access-Control-Allow-Headers"] = "*"
    return yanit


def hata(kod: str, durum: int, request: web.Request | None = None) -> web.Response:
    dil = "tr"
    if request is not None:
        d = request.app.get(DURUM)
        dil = d.dil if d else "tr"
    return web.json_response({"hata": kod, "mesaj": metinler.mesaj(kod, dil)}, status=durum)


# ---------- TV uç noktaları ----------

async def merhaba(request: web.Request) -> web.Response:
    return web.json_response({"uygulama": "altyazikoprusu", "surum": SURUM,
                              "protokol": PROTOKOL, "ad": socket.gethostname().upper()})


async def akis(request: web.Request) -> web.StreamResponse:
    d: Durum = request.app[DURUM]
    r = web.StreamResponse(headers={
        "Content-Type": "text/event-stream", "Cache-Control": "no-cache",
        "Connection": "keep-alive", "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": "*"})
    await r.prepare(request)
    q = d.yayin.abone_ol()
    try:
        ilk = [(o, v) for o, v in d.yayin.acilis_olaylari() if o != "durum"]
        ilk.insert(1 if ilk and ilk[0][0] == "gorunum" else 0, ("durum", d.durum_olayi()))
        for olay, veri in ilk:
            await r.write(sse_bicim(olay, veri))
        while True:
            try:
                olay, veri = await asyncio.wait_for(q.get(), NABIZ_SN)
                await r.write(sse_bicim(olay, veri))
            except asyncio.TimeoutError:
                await r.write(b": nabiz\n\n")
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    finally:
        d.yayin.ayril(q)
    return r


def _dosya(yol: Path, kok: Path) -> web.StreamResponse:
    try:
        tam = yol.resolve()
        if kok.resolve() in tam.parents and tam.is_file():
            return web.FileResponse(tam, headers={"Cache-Control": "no-cache"})
    except OSError:
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
    return web.json_response({
        "calisiyor": d.calisiyor(), "motor": _motor_adi(d), "yedekte": d.yonetici.yedekte,
        "tv_sayisi": d.yayin.istemci_sayisi, "son_yazi": y["metin"] if y else "",
        "adresler": lan_adresleri(), "kapi": d.ayar["kapi"]})


def _ayar_gorunumu(d: Durum) -> dict[str, Any]:
    cikti = dict(d.ayar)
    cikti["anahtarlar"] = {m: anahtarlar.kayitli_mi(m) for m in anahtarlar.MOTORLAR}
    return cikti


async def api_ayarlar_al(request: web.Request) -> web.Response:
    return web.json_response(_ayar_gorunumu(request.app[DURUM]))


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
        for alan in ("ekrani_cevir", "kisa_aciklama", "ses_cevir", "kurulum_tamam"):
            if alan in k and not isinstance(k[alan], bool):
                return False
        g = k.get("gorunum")
        if g is not None:
            if not isinstance(g, dict) or g.get("konum", "alt") not in ("alt", "ust"):
                return False
        b = k.get("bolge_altyazi")
        if b is not None and not (isinstance(b, dict) and
                                  all(isinstance(b.get(f), (int, float)) and 0 <= b[f] <= 1
                                      for f in ("x", "y", "g", "y2"))):
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
    # üst düzey ekrani_cevir ile gorunum.ekran_cevir birlikte tutulur
    if "ekrani_cevir" in kismi:
        kismi.setdefault("gorunum", {})["ekran_cevir"] = kismi["ekrani_cevir"]
    elif isinstance(kismi.get("gorunum"), dict) and "ekran_cevir" in kismi["gorunum"]:
        kismi["ekrani_cevir"] = kismi["gorunum"]["ekran_cevir"]
    if not _dogrula(kismi):
        return hata("gecersiz_ayar", 400, request)
    d.ayar = ayarlar.guncelle(d.ayar, kismi)
    if "gorunum" in kismi:
        d.yayin.yayinla("gorunum", d.ayar["gorunum"])
    if {"motor", "yedek_motor", "modeller", "aktif_oyun"} & kismi.keys():
        d.yeniden_kur()
    return web.json_response({"tamam": True})


async def api_motorlar(request: web.Request) -> web.Response:
    return web.json_response([
        {"kod": k, "ad": ad, "anahtar_gerekli": ag, "anahtar_kayitli": anahtarlar.kayitli_mi(k) if ag else False,
         "cevrimdisi": cd, "ucretsiz": uc} for k, ad, ag, cd, uc in BILGI])


async def api_anahtar(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    v = await _json(request)
    motor, anahtar = v.get("motor"), v.get("anahtar", "")
    if motor not in anahtarlar.MOTORLAR or not isinstance(anahtar, str):
        return hata("gecersiz_istek", 400, request)
    try:
        anahtarlar.yaz(motor, anahtar)
    except anahtarlar.KasaHatasi as e:
        kod = "kasa_yok" if str(e) == "kasa_yok" else "kasa_hata"
        return hata(kod, 503, request)
    d.yeniden_kur()
    return web.json_response({"tamam": True})


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
        (c,) = await motor.cevir([metin], d.ayar["kaynak_dil"], d.ayar["hedef_dil"],
                                 d.yonetici.terimler)
    except AnahtarHatasi:
        return hata("anahtar_yok" if not anahtarlar.kayitli_mi(kod) else "anahtar_gecersiz", 400, request)
    except AgHatasi:
        return hata("ag_hatasi", 502, request)
    except MotorHatasi:
        return hata("motor_hatasi", 502, request)
    return web.json_response({"ceviri": c.metin, "sure_ms": int((time.monotonic() - t0) * 1000)})


async def api_baslat(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    if not d.ayar.get("kaynak"):
        return hata("kaynak_yok", 400, request)
    try:
        d.baslat()
    except YakalamaHatasi:
        return hata("yakalama_yok", 400, request)
    except OkumaHatasi:
        return hata("okuma_yok", 400, request)
    return web.json_response({"calisiyor": True})


async def api_durdur(request: web.Request) -> web.Response:
    request.app[DURUM].durdur()
    return web.json_response({"calisiyor": False})


async def api_deneme_yazi(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    d.yayin.yayinla("yazi", {
        "id": f"d{int(time.time())}", "metin": metinler.mesaj("deneme_tr", "tr"),
        "asil": metinler.mesaj("deneme_tr", "en"), "tur": "altyazi",
        "konusan": None, "sure_ms": 4000})
    return web.json_response({"tamam": True, "tv_sayisi": d.yayin.istemci_sayisi})


async def api_kaynaklar(request: web.Request) -> web.Response:
    try:
        from . import yakalama
        return web.json_response(await asyncio.to_thread(yakalama.kaynaklar))
    except YakalamaHatasi:
        return hata("yakalama_yok", 400, request)


async def api_sozluk_al(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    oyun = request.query.get("oyun") or d.ayar["aktif_oyun"]
    return web.json_response({"oyun": oyun, "terimler": sozluk_mod.yukle(oyun)})


async def api_sozluk_yaz(request: web.Request) -> web.Response:
    d: Durum = request.app[DURUM]
    v = await _json(request)
    terimler = v.get("terimler")
    oyun = v.get("oyun") or d.ayar["aktif_oyun"]
    if not isinstance(oyun, str) or not isinstance(terimler, list) or \
            not all(isinstance(t, dict) and isinstance(t.get("asil"), str) for t in terimler):
        return hata("gecersiz_istek", 400, request)
    sozluk_mod.kaydet(oyun, terimler)
    if oyun == d.ayar["aktif_oyun"]:
        d.yonetici.terimler = sozluk_mod.sozluk_dict(sozluk_mod.yukle(oyun))
    return web.json_response({"oyun": oyun, "terimler": sozluk_mod.yukle(oyun)})


def uygulama_olustur(ayar: dict[str, Any] | None = None, **fabrikalar: Any) -> web.Application:
    app = web.Application(middlewares=[kopru_katman, yerel_katman])
    durum = Durum(ayar if ayar is not None else ayarlar.yukle(), **fabrikalar)
    app[DURUM] = durum
    r = app.router
    r.add_get("/kopru/merhaba", merhaba)
    r.add_get("/kopru/akis", akis)
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
    r.add_post("/api/baslat", api_baslat)
    r.add_post("/api/durdur", api_durdur)
    r.add_post("/api/deneme-yazi", api_deneme_yazi)
    r.add_get("/api/kaynaklar", api_kaynaklar)
    r.add_get("/api/sozluk", api_sozluk_al)
    r.add_post("/api/sozluk", api_sozluk_yaz)

    async def durum_dongusu() -> None:
        while True:
            await asyncio.sleep(DURUM_SN)
            durum.yayin.yayinla("durum", durum.durum_olayi())

    async def ac(_: web.Application) -> None:
        app["durum_gorevi"] = asyncio.create_task(durum_dongusu())

    async def kapat(_: web.Application) -> None:
        app["durum_gorevi"].cancel()
        durum.durdur()
        durum.onbellek.kapat()
    app.on_startup.append(ac)
    app.on_cleanup.append(kapat)
    return app
