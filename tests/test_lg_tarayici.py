# SPDX-License-Identifier: AGPL-3.0-only
"""PROTOKOL 20.2 (kısa adres, QR), 20.3 (LG ekranı kararmasın, sahte SSAP), 20.6 (görünüm), 20.7 (konsolsuz dene)."""
import asyncio
import json

import aiohttp
import pytest
from aiohttp import web

from kopru import kisa_adres, qr, sunucu
from kopru.tv_kurulum import lg_uyanik
from tests.conftest import sahte_fabrika


@pytest.fixture
async def istemci(aiohttp_client, uygulama_ayari):
    uygulama_ayari["motor"], uygulama_ayari["yedek_motor"] = "sahte", ""
    return await aiohttp_client(sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika))


# ---------------- 20.2 ----------------
async def test_kisa_adres_yalniz_yonlendirir(aiohttp_client):
    c = await aiohttp_client(kisa_adres.uygulama(8642))
    r = await c.get("/", allow_redirects=False, headers={"Host": "192.168.1.20"})
    assert r.status == 302 and r.headers["Location"] == "http://192.168.1.20:8642/tv"
    r = await c.get("/tv?hdmi=2", allow_redirects=False, headers={"Host": "192.168.1.20:80"})
    assert r.headers["Location"] == "http://192.168.1.20:8642/tv?hdmi=2"
    for yol in ("/api/durum", "/panel/panel.js", "/kopru/akis", "/statik/ortak.js"):
        assert (await c.get(yol, allow_redirects=False)).status == 404
    assert (await c.get("/", allow_redirects=False, headers={"Host": "evil host"})).status == 400


async def test_kisa_adres_kapi_doluysa_sessizce_kapali(unused_tcp_port):
    tutan = await asyncio.start_server(lambda r, w: None, "127.0.0.1", unused_tcp_port)
    k = kisa_adres.KisaAdres()
    try:
        d = await k.baslat(8642, kapi=unused_tcp_port, host="127.0.0.1")
        assert d == {"acik": False, "kapi": unused_tcp_port, "hata": "dolu"}
    finally:
        tutan.close()
        await tutan.wait_closed()
    k2 = kisa_adres.KisaAdres()
    d = await k2.baslat(8642, kapi=unused_tcp_port, host="127.0.0.1")
    assert d["acik"] is True
    async with aiohttp.ClientSession() as s:
        async with s.get(f"http://127.0.0.1:{unused_tcp_port}/", allow_redirects=False) as r:
            assert r.status == 302 and r.headers["Location"] == "http://127.0.0.1:8642/tv"
    await k2.durdur()


async def test_durum_tv_adresi_ve_qr(istemci):
    j = await (await istemci.get("/api/durum")).json()
    assert j["kisa_adres"]["acik"] is False and j["tv_adresi"].endswith("/tv") and j["demo"] is False
    r = await istemci.get("/api/qr", params={"metin": "http://192.168.1.20"})
    assert r.status == 200 and r.content_type == "image/svg+xml" and (await r.text()).startswith("<svg")
    assert (await istemci.get("/api/qr", params={"metin": "x" * 201})).status == 400


def test_qr_yapisi():
    m = qr.matris("http://192.168.1.20")
    assert len(m) == 25 and all(len(s) == 25 for s in m)          # sürüm 2
    assert m[0][:7] == [1] * 7 and m[6][:7] == [1] * 7             # bulucu desen
    assert [m[6][i] for i in range(8, 17)] == [1, 0, 1, 0, 1, 0, 1, 0, 1]   # zamanlama
    with pytest.raises(ValueError):
        qr.matris("x" * 300)


@pytest.mark.parametrize("metin", ["http://192.168.1.20", "http://192.168.1.20:8642/tv", "a" * 120, "b" * 213])
def test_qr_okunur(metin):
    zxingcpp = pytest.importorskip("zxingcpp")
    from PIL import Image
    m = qr.matris(metin)
    n, s, k = len(m), 6, 4
    im = Image.new("L", ((n + 2 * k) * s,) * 2, 255)
    for r in range(n):
        for c in range(n):
            if m[r][c]:
                im.paste(0, ((c + k) * s, (r + k) * s, (c + k + 1) * s, (r + k + 1) * s))
    sonuc = zxingcpp.read_barcodes(im)
    assert sonuc and sonuc[0].text == metin


# ---------------- 20.3: sahte SSAP (LG TV) ----------------
class SahteTV:
    def __init__(self, kabul=True):
        self.kabul, self.anahtar = kabul, "istemci-anahtari-123"
        self.kayitlar, self.hareketler, self.istekler = [], [], []

    def uygulama(self):
        async def ana(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            async for m in ws:
                v = json.loads(m.data)
                if v["type"] == "register":
                    self.kayitlar.append(v["payload"])
                    if v["payload"].get("client-key") != self.anahtar:
                        await ws.send_str(json.dumps({"type": "response", "id": v["id"], "payload": {"pairingType": "PROMPT"}}))
                        if not self.kabul:
                            await ws.send_str(json.dumps({"type": "error", "id": v["id"], "error": "403 cancelled"}))
                            continue
                    await ws.send_str(json.dumps({"type": "registered", "id": v["id"], "payload": {"client-key": self.anahtar}}))
                elif v["type"] == "request":
                    self.istekler.append(v["uri"])
                    yol = f"ws://127.0.0.1:{request.url.port}/imlec"
                    await ws.send_str(json.dumps({"type": "response", "id": v["id"], "payload": {"socketPath": yol}}))
            return ws

        async def imlec(request):
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            async for m in ws:
                self.hareketler.append(m.data)
            return ws
        app = web.Application()
        app.router.add_get("/", ana)
        app.router.add_get("/imlec", imlec)
        return app


async def _tv(aiohttp_server, kabul=True):
    tv = SahteTV(kabul)
    srv = await aiohttp_server(tv.uygulama())
    return tv, srv


async def test_lg_eslesme_ve_uyanik_tutma(aiohttp_server, ortam):
    tv, srv = await _tv(aiohttp_server)
    ayar = {"lg_uyanik": {"acik": True, "adres": ""}}
    calisiyor = [False]
    u = lg_uyanik.LgUyanik(lambda: ayar, lambda: calisiyor[0], lambda: "192.168.1.30",
                           adresler=lambda ip: [f"ws://127.0.0.1:{srv.port}/"])
    assert u.bilgi()["eslesti"] is False and "eşleş" in u.bilgi()["mesaj"].lower()
    assert await u.esle() == "tamam"
    assert tv.kayitlar[0]["pairingType"] == "PROMPT" and "client-key" not in tv.kayitlar[0]
    assert tv.kayitlar[0]["manifest"]["signed"]["permissions"]          # imzalı bildirim gönderildi
    assert ortam.veri[("AltyaziKoprusu", "lg_ssap")] == "istemci-anahtari-123"   # şifreli kasada
    await u.adim()                      # çeviri çalışmıyor: dokunmaz
    assert tv.hareketler == [] and u.durum == "bekliyor"
    calisiyor[0] = True
    await u.adim()
    assert u.durum == "calisiyor" and u.son_dokunus
    assert tv.kayitlar[-1]["client-key"] == "istemci-anahtari-123"      # ikinci kez soru çıkmaz
    assert tv.istekler == [lg_uyanik.IMLEC]
    assert tv.hareketler == ["type:move\ndx:1\ndy:0\ndown:0\n\n", "type:move\ndx:-1\ndy:0\ndown:0\n\n"]
    b = u.bilgi()
    assert b["eslesti"] and b["durum"] == "calisiyor" and "istemci-anahtari" not in json.dumps(b)
    ayar["lg_uyanik"]["acik"] = False
    await u.adim()
    assert u.durum == "kapali" and len(tv.hareketler) == 2


async def test_lg_eslesme_reddi_ve_ulasilamayan_tv(aiohttp_server, ortam, unused_tcp_port):
    tv, srv = await _tv(aiohttp_server, kabul=False)
    u = lg_uyanik.LgUyanik(lambda: {"lg_uyanik": {"acik": True}}, lambda: True, lambda: "192.168.1.30",
                           adresler=lambda ip: [f"ws://127.0.0.1:{srv.port}/"])
    assert await u.esle() == "reddedildi" and u.bilgi()["hata"] == "reddedildi"
    u2 = lg_uyanik.LgUyanik(lambda: {"lg_uyanik": {"acik": True}}, lambda: True, lambda: "192.168.1.30",
                            adresler=lambda ip: [f"ws://127.0.0.1:{unused_tcp_port}/"])
    assert await u2.esle() == "ag"
    u3 = lg_uyanik.LgUyanik(lambda: {"lg_uyanik": {"acik": True}}, lambda: True, lambda: None)
    assert await u3.esle() == "adres_yok"


async def test_lg_uyanik_api(istemci):
    j = await (await istemci.get("/api/tv/lg/uyanik")).json()
    assert j["acik"] is False and j["durum"] == "kapali"
    r = await istemci.post("/api/tv/lg/uyanik", json={"acik": True, "adres": "192.168.1.30"})
    j = await r.json()
    assert j["acik"] is True and j["adres"] == "192.168.1.30"
    assert istemci.app[sunucu.DURUM].ayar["lg_uyanik"] == {"acik": True, "adres": "192.168.1.30"}
    assert (await istemci.post("/api/tv/lg/uyanik", json={"adres": "8.8.8.8"})).status == 400
    assert (await istemci.post("/api/tv/lg/uyanik", json={"acik": "evet"})).status == 400


async def test_webos_tarayicisi_adresi_hatirlanir(istemci, monkeypatch):
    monkeypatch.setattr(sunucu, "uzak_adres", lambda req: "192.168.1.44")
    await istemci.get("/tv", headers={"User-Agent": "Mozilla/5.0 (Web0S; Linux/SmartTV) AppleWebKit/537.36"})
    assert istemci.app[sunucu.DURUM].son_lg_adresi == "192.168.1.44"
    assert istemci.app[sunucu.LG_UYANIK].adres() == "192.168.1.44"


# ---------------- 20.6 ----------------
async def test_gorunum2_alanlari_dogrulanir(istemci):
    ok = {"konusan_goster": False, "boyut": "buyuk", "zemin": "serit", "kalinlik": "normal", "yazi_rengi": "#FFE45C"}
    assert (await istemci.post("/api/ayarlar", json={"gorunum": ok})).status == 200
    g = istemci.app[sunucu.DURUM].ayar["gorunum"]
    assert {k: g[k] for k in ok} == ok
    for kotu in ({"boyut": "dev"}, {"zemin": "pembe"}, {"kalinlik": 700}, {"konusan_goster": "hayir"}):
        assert (await istemci.post("/api/ayarlar", json={"gorunum": kotu})).status == 400


async def test_onizleme_yazisi_konusanli_ve_calisirken_gonderilmez(istemci):
    d = istemci.app[sunucu.DURUM]
    olaylar = []
    eski = d.yayin.yayinla
    d.yayin.yayinla = lambda ad, v=None: (olaylar.append((ad, v)), eski(ad, v))[1]
    j = await (await istemci.post("/api/deneme-yazi", json={"onizleme": True})).json()
    assert j["tamam"] is True
    yazi = [v for a, v in olaylar if a == "yazi"][-1]
    assert yazi["konusan"] and yazi["otomatik_sil"] is True and yazi["onizleme"] is True


# ---------------- 20.7 ----------------
async def test_konsolsuz_dene_tam_hat(istemci, monkeypatch):
    from kopru import demo as demo_mod
    d = istemci.app[sunucu.DURUM]
    olaylar = []
    eski = d.yayin.yayinla
    d.yayin.yayinla = lambda ad, v=None: (olaylar.append((ad, v)), eski(ad, v))[1]
    monkeypatch.setattr(demo_mod, "SAHNE", tuple((1.3, k, m) for _, k, m in demo_mod.SAHNE))
    monkeypatch.setattr(demo_mod.Sahne.__init__, "__defaults__", (demo_mod.time.monotonic, demo_mod.SAHNE))
    j = await (await istemci.post("/api/demo", json={"acik": True})).json()
    assert j["acik"] is True and (await (await istemci.get("/api/durum")).json())["demo"] is True
    for _ in range(150):
        await asyncio.sleep(0.1)
        if not d.demo_acik():
            break
    adlar = [a for a, _ in olaylar]
    assert ("demo", {"acik": True, "kare": "/kopru/demo/kare.jpg"}) in olaylar and ("demo", {"acik": False}) in olaylar
    yazilar = [v for a, v in olaylar if a == "yazi"]
    asillar = " | ".join(v["asil"] for v in yazilar)
    assert "Get down! They're shooting at us!" in asillar                   # bağırma düzeltildi
    assert "I told you we should never have come here." in asillar          # bölünmüş cümle birleşti
    assert any(v.get("konusan") == "MARCUS" for v in yazilar)
    ekran = [v for a, v in olaylar if a == "ekran"]
    assert ekran and any("safehouse" in str(e).lower() or "[TR]" in str(e) for e in ekran)
    assert not any("$1,250" in o.get("metin", "") and "[TR]" in o.get("metin", "")
                   for e in ekran for o in e["ogeler"])                       # HUD çevrilmez
    assert "durum" in adlar and d.demo is None
    r = await istemci.get("/kopru/demo/kare.jpg")
    assert r.status == 200 and (await r.read())[:2] == b"\xff\xd8"
