# SPDX-License-Identifier: AGPL-3.0-only
import asyncio
import json

import pytest

from kopru import anahtarlar, sunucu
from tests.conftest import sahte_fabrika


@pytest.fixture
async def istemci(aiohttp_client, uygulama_ayari):
    uygulama_ayari["motor"] = "sahte"
    uygulama_ayari["yedek_motor"] = ""
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika)
    return await aiohttp_client(app)


async def sse_oku(yanit, adet):
    olaylar, ad = [], None
    while len(olaylar) < adet:
        satir = (await asyncio.wait_for(yanit.content.readline(), 5)).decode()
        if satir.startswith("event:"):
            ad = satir[6:].strip()
        elif satir.startswith("data:"):
            olaylar.append((ad, json.loads(satir[5:])))
    return olaylar


async def test_merhaba(istemci):
    r = await istemci.get("/kopru/merhaba")
    j = await r.json()
    assert j["uygulama"] == "altyazikoprusu" and j["protokol"] == 1 and j["surum"] == "0.1.0"
    assert set(j) == {"uygulama", "surum", "protokol", "ad"}
    assert r.headers["Access-Control-Allow-Origin"] == "*"


async def test_sse_gorunum_ve_yazi(istemci):
    r = await istemci.get("/kopru/akis")
    assert r.headers["Content-Type"].startswith("text/event-stream")
    assert r.headers["Access-Control-Allow-Origin"] == "*"
    ilk = await sse_oku(r, 2)
    assert ilk[0][0] == "gorunum" and ilk[0][1]["konum"] == "alt"
    assert ilk[1][0] == "durum"  # bağlanınca gerçek durum olayı
    assert (await istemci.post("/api/deneme-yazi")).status == 200
    (olay,) = await sse_oku(r, 1)
    assert olay[0] == "yazi" and olay[1]["tur"] == "altyazi" and olay[1]["sure_ms"] > 0
    # yeni istemci son yazıyı da alır
    r2 = await istemci.get("/kopru/akis")
    assert [o for o, _ in await sse_oku(r2, 3)] == ["gorunum", "durum", "yazi"]
    r.close(); r2.close()


async def test_durum_olayi_periyodik_ve_nabiz(aiohttp_client, uygulama_ayari, monkeypatch):
    monkeypatch.setattr(sunucu, "DURUM_SN", 0.1)
    monkeypatch.setattr(sunucu, "NABIZ_SN", 0.05)
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika)
    c = await aiohttp_client(app)
    r = await c.get("/kopru/akis")
    govde = b""
    while govde.count(b"event: durum") < 3:  # bağlanma + en az 2 periyodik
        govde += await asyncio.wait_for(r.content.readline(), 5)
    assert b": nabiz" in govde
    r.close()


async def test_yerel_katman(istemci, monkeypatch):
    assert (await istemci.get("/api/durum")).status == 200
    monkeypatch.setattr(sunucu, "uzak_adres", lambda req: "192.168.1.50")
    for yol in ("/api/durum", "/api/ayarlar", "/", "/panel/x.js"):
        r = await istemci.get(yol)
        assert r.status == 403
        assert (await r.json())["hata"] == "yalniz_yerel"
    assert (await istemci.post("/api/baslat")).status == 403
    assert (await istemci.get("/kopru/merhaba")).status == 200  # TV erişimi serbest
    assert (await istemci.get("/tv")).status in (200, 404)


async def test_statik_yoksa_404_cokmez(istemci):
    assert (await istemci.get("/panel/yok.js")).status == 404
    assert (await istemci.get("/statik/../../ayarlar.json")).status in (404,)


async def test_anahtar_asla_donmez(istemci, ortam, caplog):
    r = await istemci.post("/api/anahtar", json={"motor": "claude", "anahtar": "sk-ant-GIZLI"})
    assert r.status == 200
    for yol in ("/api/ayarlar", "/api/motorlar", "/api/durum"):
        assert "sk-ant-GIZLI" not in await (await istemci.get(yol)).text()
    j = await (await istemci.get("/api/ayarlar")).json()
    assert j["anahtarlar"]["claude"] is True
    assert "sk-ant-GIZLI" not in caplog.text
    assert anahtarlar.oku("claude") == "sk-ant-GIZLI"
    ayar_dosyasi = (anahtarlar.__file__ and __import__("kopru.ayarlar", fromlist=["x"]).ayar_dizini() / "ayarlar.json")
    if ayar_dosyasi.exists():
        assert "sk-ant" not in ayar_dosyasi.read_text()
    m = await (await istemci.get("/api/motorlar")).json()
    assert [x for x in m if x["kod"] == "claude"][0]["anahtar_kayitli"] is True


async def test_ayar_guncelle_ve_dogrula(istemci):
    r = await istemci.post("/api/ayarlar", json={"gorunum": {"yazi_boyutu": 60}, "kisa_aciklama": False})
    assert await r.json() == {"tamam": True}
    j = await (await istemci.get("/api/ayarlar")).json()
    assert j["gorunum"]["yazi_boyutu"] == 60 and j["gorunum"]["konum"] == "alt"
    assert j["kurulum_tamam"] is False and j["cihaz"] is None and j["tv"] is None
    assert (await istemci.post("/api/ayarlar", json={"kurulum_tamam": True, "cihaz": "ps5", "tv": "lg"})).status == 200
    j = await (await istemci.get("/api/ayarlar")).json()
    assert (j["kurulum_tamam"], j["cihaz"], j["tv"]) == (True, "ps5", "lg")
    assert (await istemci.post("/api/ayarlar", json={"cihaz": "atari"})).status == 400
    bad = await istemci.post("/api/ayarlar", json={"kapi": 5})
    assert bad.status == 400 and (await bad.json())["hata"] == "gecersiz_ayar"
    assert (await istemci.post("/api/ayarlar", json={"ekrani_cevir": False})).status == 200
    assert (await (await istemci.get("/api/ayarlar")).json())["gorunum"]["ekran_cevir"] is False


async def test_dene_sozluk_kaynaklar(istemci):
    j = await (await istemci.post("/api/dene", json={"metin": "Hello", "motor": "sahte"})).json()
    assert j["ceviri"] == "[TR] Hello" and "sure_ms" in j
    await istemci.post("/api/sozluk", json={"terimler": [{"asil": "Ellie", "ceviri": "Ellie"}]})
    s = await (await istemci.get("/api/sozluk")).json()
    assert s["oyun"] == "varsayilan" and s["terimler"][0]["asil"] == "Ellie"
    r = await istemci.get("/api/kaynaklar")
    assert r.status in (200, 400)


async def test_hata_dili(istemci):
    await istemci.post("/api/ayarlar", json={"arayuz_dili": "en"})
    r = await istemci.post("/api/ayarlar", json={"kapi": 1})
    assert "invalid" in (await r.json())["mesaj"]


async def test_kasa_yoksa_anahtar_reddi(istemci):
    import keyring
    from keyring.backends import fail
    onceki = keyring.get_keyring()
    keyring.set_keyring(fail.Keyring())
    try:
        r = await istemci.post("/api/anahtar", json={"motor": "claude", "anahtar": "sk-x"})
        assert r.status == 503 and (await r.json())["hata"] == "kasa_yok"
        assert "kasası" in (await r.json())["mesaj"]
    finally:
        keyring.set_keyring(onceki)


async def test_baslat_kaynaksiz(istemci):
    await istemci.post("/api/ayarlar", json={"kaynak": ""})
    r = await istemci.post("/api/baslat")
    assert r.status == 400 and (await r.json())["hata"] == "kaynak_yok"


# ---------- bölge seçimi ve /api/kare (PROTOKOL 7.1) ----------

def _kare_fabrika(kaynak):
    from PIL import Image
    return lambda: Image.new("RGB", (1920, 1080), (40, 90, 160))


async def test_api_kare_jpeg_kucuk_ve_onbellegesiz(aiohttp_client, uygulama_ayari, tmp_path):
    import io
    from PIL import Image
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika, kare_fabrika=_kare_fabrika)
    c = await aiohttp_client(app)
    once = sorted(p.name for p in tmp_path.rglob("*"))
    r = await c.get("/api/kare")
    assert r.status == 200 and r.content_type == "image/jpeg"
    assert r.headers["Cache-Control"] == "no-store"
    im = Image.open(io.BytesIO(await r.read()))
    assert im.size == (1280, 720)
    assert sorted(p.name for p in tmp_path.rglob("*")) == once      # diske hiçbir şey yazılmadı


async def test_api_kare_hata_dostca(aiohttp_client, uygulama_ayari):
    from kopru.yakalama import YakalamaHatasi

    def bozuk(kaynak):
        def al():
            raise YakalamaHatasi("yok")
        return al
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika, kare_fabrika=bozuk)
    c = await aiohttp_client(app)
    r = await c.get("/api/kare")
    j = await r.json()
    assert r.status == 400 and j["hata"] == "yakalama_yok" and "izin" in j["mesaj"]
    await c.post("/api/ayarlar", json={"kaynak": ""})
    assert (await (await c.get("/api/kare")).json())["hata"] == "kaynak_yok"


async def test_ayar_bolgeler_dogrulanir(istemci):
    b = {"x": 0.1, "y": 0.7, "g": 0.8, "y2": 0.2, "tur": "altyazi", "ad": "Altyazı", "fazla": 1}
    assert (await istemci.post("/api/ayarlar", json={"bolgeler": [b]})).status == 200
    kayit = (await (await istemci.get("/api/ayarlar")).json())["bolgeler"]
    assert kayit == [{"x": 0.1, "y": 0.7, "g": 0.8, "y2": 0.2, "tur": "altyazi", "ad": "Altyazı",
                      "hedef": "altyazi", "olcek": 1.0}]
    assert (await istemci.post("/api/ayarlar", json={"bolgeler": [b] * 7})).status == 400
    assert (await istemci.post("/api/ayarlar", json={"bolgeler": [b] * 6})).status == 200
    assert (await istemci.post("/api/ayarlar", json={"bolgeler": [{**b, "tur": "menu"}]})).status == 400
    assert (await istemci.post("/api/ayarlar", json={"bolgeler": []})).status == 200
    assert (await (await istemci.get("/api/ayarlar")).json())["bolgeler"] == []
