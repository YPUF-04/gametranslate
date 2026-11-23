# SPDX-License-Identifier: AGPL-3.0-only
"""PROTOKOL 18: kendini güncelleyen LG başlatıcısı, TV kaydı ve geliştirici modu oturum uzatma."""
import json

from kopru import sunucu
from kopru.tv_kurulum import gelistirici as gm
from kopru.tv_kurulum import lg, uygulama
from tests.conftest import sahte_fabrika
from tests.test_tv_lg import ANAHTAR, IP, PAROLA, SahteOturum

BELIRTEC = "a1B2c3D4e5F6g7H8i9J0"


# ---------- 18.1/18.2 paket ----------

def test_paket_yapisi_ve_surum_kararli():
    p = uygulama.paket()
    assert p["uygulama"] == "altyazikoprusu-tv" and len(p["surum"]) == 12
    assert [a for a, _ in p["js"]] == ["marka.js", "i18n.js", "platform-webos.js", "ortak.js", "reklam.js", "app.js"]
    assert 'id="e-ara"' in p["html"] and "<script" not in p["html"]
    assert len(p["css"]) == 2 and "AYK Yazi" in p["css"][0]
    assert uygulama.paket()["surum"] == p["surum"]          # dosyalar değişmedikçe aynı
    assert p["yukleyici_en_az"] == uygulama.YUKLEYICI_EN_AZ


def test_paket_surumu_icerikle_degisir(tmp_path):
    import shutil
    kok = tmp_path / "tv"
    shutil.copytree(uygulama.KAYNAK, kok)
    a = uygulama.paket(kok)["surum"]
    (kok / "webos" / "app.js").write_text((kok / "webos" / "app.js").read_text(encoding="utf-8") + "\n// x\n",
                                          encoding="utf-8")
    assert uygulama.paket(kok)["surum"] != a


def test_yanit_ayni_eski_yukleyici_tam():
    p = uygulama.paket()
    assert uygulama.yanit("2", p["surum"]) == {"uygulama": "altyazikoprusu-tv", "surum": p["surum"], "ayni": True}
    assert uygulama.yanit("1", None)["eski_yukleyici"] is True
    assert uygulama.yanit("x", None)["eski_yukleyici"] is True
    tam = uygulama.yanit("2", "eskisurum000")
    assert tam["html"] and tam["js"]


def test_gomulu_js_gecerli_ve_kacisli():
    js = uygulama.gomulu_js({"uygulama": "altyazikoprusu-tv", "surum": "x", "html": "</script><b> ",
                             "css": [], "js": [["a.js", "1"]]})
    assert js.count("</script>") == 0 and " " not in js
    govde = js.split("window.AK_GOMULU_PAKET = ", 1)[1].rstrip().rstrip(";")
    assert json.loads(govde)["html"] == "</script><b> "


def test_tv_kaydi_durumlari():
    saat = {"t": 1000.0}
    k = uygulama.TvKaydi(saat=lambda: saat["t"])
    assert k.durum("s1")["durum"] == "bilinmiyor"
    k.gor("192.168.1.30", 2, "s0")
    d = k.durum("s1")
    assert d["durum"] == "guncel" and d["tvler"][0]["guncel"] is False    # başlatıcı yeni: kendini günceller
    k.gor("192.168.1.30", None, "s1")
    assert k.durum("s1")["tvler"][0] == {"adres": "192.168.1.30", "yukleyici": 2, "paket": "s1", "guncel": True,
                                         "son_gorulme_sn": 0}
    k.gor("192.168.1.31", 1, None)
    d = k.durum("s1")
    assert d["durum"] == "eski" and "yeniden kurun" in d["mesaj"]
    saat["t"] += 8 * 24 * 3600
    assert k.durum("s1")["durum"] == "bilinmiyor"


async def test_uc_nokta_paket_ve_kayit(aiohttp_client, uygulama_ayari):
    ist = await aiohttp_client(sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika))
    r = await ist.get("/kopru/tv/uygulama?yukleyici=2")
    assert r.status == 200 and r.headers["Access-Control-Allow-Origin"] == "*"
    p = await r.json()
    assert p["uygulama"] == "altyazikoprusu-tv" and p["html"]
    r = await ist.get(f"/kopru/tv/uygulama?yukleyici=2&surum={p['surum']}")
    assert (await r.json())["ayni"] is True
    d = await (await ist.get("/api/tv/uygulama")).json()
    assert d["paket_surum"] == p["surum"] and d["durum"] == "guncel" and d["tvler"][0]["yukleyici"] == 2
    assert d["tvler"][0]["guncel"] is True


async def test_eski_uygulama_akistan_taninir_tarayici_sayfasi_sayilmaz(aiohttp_client, uygulama_ayari):
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika)
    ist = await aiohttp_client(app)
    r = await ist.get("/kopru/akis?reklam=1")           # tarayıcıdaki /tv: Origin yok
    r.close()
    assert app[sunucu.TV_KAYDI].durum("x")["durum"] == "bilinmiyor"
    r = await ist.get("/kopru/akis?reklam=1", headers={"Origin": "null"})   # 0.1.x paketli uygulama
    r.close()
    d = app[sunucu.TV_KAYDI].durum("x")
    assert d["durum"] == "eski" and d["tvler"][0]["yukleyici"] == 1


# ---------- 18.6 geliştirici modu ----------

class SahteLg:
    def __init__(self, sifirla=None, denetle=None, hata=None):
        self.cagrilar = []
        self.sifirla = sifirla or {"result": "success", "errorCode": "200", "errorMsg": "GNL"}
        self.denetle = denetle or {"result": "success", "errorCode": "200", "errorMsg": "999:58:40"}
        self.hata = hata

    def __call__(self, adres, belirtec):
        self.cagrilar.append((adres, belirtec))
        if self.hata:
            raise self.hata
        return self.sifirla if adres == gm.SIFIRLA else self.denetle


def yap_g(tmp_path, istek=None, saat=None):
    s = saat or {"t": 1_700_000_000.0}
    return gm.GelistiriciModu(lambda: {"arayuz_dili": "tr"}, istek=istek or SahteLg(),
                              dosya=tmp_path / "lg_devmode.json", saat=lambda: s["t"]), s


def test_kalan_coz():
    assert gm.kalan_coz("999:58:40") == 999 * 3600 + 58 * 60 + 40
    assert gm.kalan_coz("GNL") is None and gm.kalan_coz(None) is None


def test_adresler_sabit_https():
    import pytest
    for kotu in ("http://developer.lge.com/secure/ResetDevModeSession.dev", "https://evil.example/x",
                 "https://developer.lge.com/baska"):
        with pytest.raises(ValueError):
            gm.lg_iste(kotu, BELIRTEC)
    assert gm.SIFIRLA.startswith("https://developer.lge.com/") and gm.DENETLE.startswith("https://developer.lge.com/")


def test_kurulumdan_belirtec_kasaya_ve_hemen_uzatilir(tmp_path, ortam):
    lgs = SahteLg()
    g, s = yap_g(tmp_path, lgs)
    assert g.kurulumdan(BELIRTEC + "\n", IP) is True
    assert ortam.veri[("AltyaziKoprusu", "lg_devmode")] == BELIRTEC
    assert [a for a, _ in lgs.cagrilar] == [gm.SIFIRLA, gm.DENETLE] and lgs.cagrilar[0][1] == BELIRTEC
    d = g.durum()
    assert d["belirtec_var"] and d["son_uzatma"] == s["t"] and d["kalan_sn"] == 3599920
    assert d["bitis_tahmini"] == s["t"] + 3599920 and d["durum"] == "tamam" and not d["hatirlatma"]
    assert BELIRTEC not in (tmp_path / "lg_devmode.json").read_text()      # belirteç dosyada YOK


def test_gunde_bir_uzatir_hata_saatte_bir(tmp_path):
    lgs = SahteLg()
    g, s = yap_g(tmp_path, lgs)
    g.belirtec_kaydet(BELIRTEC)
    assert g.gerekirse_uzat() is None and len(lgs.cagrilar) == 2
    s["t"] += 3600
    g.gerekirse_uzat()
    assert len(lgs.cagrilar) == 2                       # 24 sa dolmadı
    s["t"] += 23 * 3600
    lgs.hata = OSError("ağ yok")
    assert g.gerekirse_uzat() == "ag" and g.durum()["durum"] == "ag"
    n = len(lgs.cagrilar)
    s["t"] += 600
    g.gerekirse_uzat()
    assert len(lgs.cagrilar) == n                       # 1 sa beklenir
    s["t"] += 3600
    lgs.hata = None
    assert g.gerekirse_uzat() is None and g.durum()["durum"] == "tamam"


def test_gecersiz_belirtec_ve_kapali(tmp_path):
    lgs = SahteLg(sifirla={"result": "fail", "errorCode": "ERR_006", "errorMsg": "Check sessionToken"})
    g, s = yap_g(tmp_path, lgs)
    g.belirtec_kaydet(BELIRTEC)
    assert g.uzat() == "gecersiz" and g.durum()["durum"] == "gecersiz"
    s["t"] += 41 * 3600
    assert g.durum()["hatirlatma"] is True
    g.otomatik_ayarla(False)
    n = len(lgs.cagrilar)
    s["t"] += 48 * 3600
    assert g.gerekirse_uzat() is None and len(lgs.cagrilar) == n and g.durum()["durum"] == "kapali"
    assert g.belirtec_kaydet("kısa!") == "gecersiz_belirtec"


def test_belirtec_yok_ve_elle_siklik(tmp_path):
    g, s = yap_g(tmp_path)
    assert g.durum()["durum"] == "belirtec_yok" and g.uzat() == "belirtec_yok"
    g.belirtec_kaydet(BELIRTEC)
    assert g.elle_uzat() is None and g.elle_uzat() == "cok_sik"
    s["t"] += 301
    assert g.elle_uzat() is None


def test_lg_kurulum_belirteci_okur_ve_gizler():
    class O(SahteOturum):
        def calistir(self, komut, satir_cb=None, zaman_sn=120):
            if "devmode_enabled" in komut:
                self.komutlar.append(komut)
                return 0, BELIRTEC + "\n"
            return super().calistir(komut, satir_cb, zaman_sn)

    alinan = []
    o = O()
    k = lg.LgKurulum(lambda: {}, anahtar_al=lambda ip: ANAHTAR, oturum_fabrika=lambda: o, arka_planda=False,
                     belirtec_al=lambda b, ip: alinan.append((b, ip)) or True)
    o.kurulum = k
    assert k.baslat(IP, PAROLA, "asil") is None and k.durum()["asama"] == "bitti"
    assert alinan == [(BELIRTEC, IP)]
    assert any("/var/luna/preferences/devmode_enabled" in c for c in o.komutlar)
    # yalnız oturum: kurulum yok, yükleme yok
    o2 = O()
    k2 = lg.LgKurulum(lambda: {}, anahtar_al=lambda ip: ANAHTAR, oturum_fabrika=lambda: o2, arka_planda=False,
                      belirtec_al=lambda b, ip: True)
    o2.kurulum = k2
    assert k2.baslat(IP, PAROLA, "oturum") is None
    d = k2.durum()
    assert d["asama"] == "bitti" and "her gün" in d["mesaj"] and o2.yuklenen == []
    assert not any("appInstallService" in c for c in o2.komutlar)


async def test_gelistirici_api(aiohttp_client, uygulama_ayari, tmp_path):
    g, _ = yap_g(tmp_path)
    ist = await aiohttp_client(sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika, lg_gelistirici=g))
    d = await (await ist.get("/api/tv/lg/gelistirici")).json()
    assert d["belirtec_var"] is False and d["durum"] == "belirtec_yok"
    r = await ist.post("/api/tv/lg/gelistirici", json={"belirtec": BELIRTEC})
    d = await r.json()
    assert r.status == 200 and d["belirtec_var"] and BELIRTEC not in json.dumps(d)
    d = await (await ist.post("/api/tv/lg/gelistirici", json={"uzat": True})).json()
    assert d["kalan_sn"] == 3599920
    r = await ist.post("/api/tv/lg/gelistirici", json={"uzat": True})
    assert r.status == 429
    d = await (await ist.post("/api/tv/lg/gelistirici", json={"otomatik": False})).json()
    assert d["otomatik"] is False
    r = await ist.post("/api/tv/lg/gelistirici", json={"belirtec": "x"})
    assert r.status == 400
