# SPDX-License-Identifier: AGPL-3.0-only
"""Ekran katmanı: saf mantık (pencere açmadan) ve sunucu tarafı süreç yönetimi."""
import asyncio
import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

from kopru import sunucu
from kopru.katman import mantik, yonetim
from tests.conftest import SahteSurec, sahte_fabrika


# ---------- zamanlama durum makinesi ----------

def zam():
    return mantik.Zamanlayici(saat=lambda: 0.0)


def yazi(id_="a1", metin="Merhaba dünya", sure=2000, **ek):
    return {"id": id_, "metin": metin, "asil": "Hello", "tur": "altyazi", "konusan": None, "sure_ms": sure, **ek}


def test_yazi_sure_dolunca_kalkar():
    z = zam()
    z.olay("yazi", yazi(), 0)
    assert not z.adim(1.9) and z.goruntu(1.9).yazi["metin"] == "Merhaba dünya"
    assert z.adim(2.1) and z.goruntu(2.1).yazi is None


def test_yazi_sil_en_az_gosterim_dolana_kadar_bekler():
    z = zam()
    z.olay("yazi", yazi(sure=5000), 0)
    z.olay("yazi-sil", {}, 0.5)
    assert not z.adim(1.0)                 # en az 1800 ms dolmadı
    assert z.adim(1.9) and z.goruntu(1.9).yazi is None


def test_yazi_sil_sure_dolduysa_hemen():
    z = zam()
    z.olay("yazi", yazi(sure=5000), 0)
    z.olay("yazi-sil", {}, 3.0)
    assert z.adim(3.0)


def test_devam_yerinde_guncellenir_ve_sure_uzar():
    z = zam()
    z.olay("yazi", yazi(metin="Hel"), 0)
    z.olay("yazi", yazi(id_="baska", metin="Hello th", devam=True), 1.0)
    g = z.goruntu(1.0)
    assert g.yazi["metin"] == "Hello th" and g.onceki is None
    z.olay("yazi", yazi(id_="baska", metin="Hello there", sure=3000), 1.5)    # aynı id
    assert z.yazi["bitis"] == 4.5 and z.goruntu(1.5).onceki is None


def test_yeni_cumle_onceki_satir_2_5_sn():
    z = zam()
    z.olay("yazi", yazi("a1", "Birinci"), 0)
    z.olay("yazi", yazi("a2", "İkinci", sure=6000), 1.0)
    assert z.goruntu(1.1).onceki == "Birinci"
    assert z.goruntu(3.6).onceki is None
    z2 = zam()
    z2.olay("gorunum", {"onceki_goster": False}, 0)
    z2.olay("yazi", yazi("a1", "Birinci"), 0)
    z2.olay("yazi", yazi("a2", "İkinci"), 1.0)
    assert z2.goruntu(1.1).onceki is None


def test_yazi_sil_sonra_devam_canlandirir():
    z = zam()
    z.olay("yazi", yazi(sure=5000), 0)
    z.olay("yazi-sil", {}, 3.0)
    z.olay("yazi", yazi(metin="Merhaba dünya!", devam=True), 3.0)
    assert not z.adim(3.5) and z.yazi["metin"] == "Merhaba dünya!"


def test_ekran_ogeleri_yerinde_guncelle_ve_1sn_sonra_kalk():
    z = zam()
    o = {"id": "o1", "x": 0.1, "y": 0.1, "g": 0.2, "y2": 0.05, "metin": "Ana kamp"}
    z.olay("ekran", {"ogeler": [o]}, 0)
    z.olay("ekran", {"ogeler": [{**o, "metin": "Ana kampa dön"}]}, 1.0)
    assert [e["metin"] for e in z.goruntu(1.0).ogeler] == ["Ana kampa dön"]
    z.olay("ekran", {"ogeler": []}, 2.0)
    assert not z.adim(2.9) and len(z.goruntu(2.9).ogeler) == 1
    assert z.adim(3.1) and z.goruntu(3.1).ogeler == []


def test_ekran_cevir_kapaliysa_ogeler_cizilmez_ve_ekran_sil():
    z = zam()
    z.olay("ekran", {"ogeler": [{"id": "o1", "metin": "A", "x": 0, "y": 0, "g": .1, "y2": .1}]}, 0)
    z.olay("gorunum", {"ekran_cevir": False}, 0)
    assert z.goruntu(0).ogeler == []
    z.olay("gorunum", {"ekran_cevir": True}, 0)
    z.olay("ekran-sil", {}, 1)
    assert z.adim(2.1) and z.goruntu(2.1).ogeler == []


def test_kapat_olayi_ve_bos_yazi():
    z = zam()
    assert not z.olay("yazi", {"metin": "  "}, 0)
    z.olay("katman-kapat", {}, 0)
    assert z.kapat


# ---------- yerleşim ----------

def test_satir_bol_dengeli_ve_kelime_butun():
    olc = len
    assert mantik.satir_bol("Kısa", olc, 40) == ["Kısa"]
    a, b = mantik.satir_bol("Üsse geri dönmeliyiz çünkü hava kararıyor", olc, 25)
    assert a + " " + b == "Üsse geri dönmeliyiz çünkü hava kararıyor"
    assert len(a) <= len(b) + 8 and max(len(a), len(b)) <= 25
    assert mantik.satir_bol("Tekkelimeçokuzun", olc, 5) == ["Tekkelimeçokuzun"]


def test_altyazi_kutusu_tabani_sabit():
    g = {"konum": "alt", "kenar_bosluk": 0.08}
    k1 = mantik.altyazi_kutusu(1920, 1080, g, 600, 50)
    k2 = mantik.altyazi_kutusu(1920, 1080, g, 600, 100)
    assert k1[3] == k2[3]
    assert k2[1] < k1[1] and k1[0] == 1920 // 2 - (600 + 32) // 2
    ust = mantik.altyazi_kutusu(1920, 1080, {"konum": "ust", "kenar_bosluk": 0.1}, 600, 50)
    assert ust[1] == 108


def test_ekran_ogesi_pikselde_ekran_icinde():
    p = mantik.ekran_ogesi_px({"x": 0.5, "y": 0.25, "g": 0.2, "y2": 0.04, "metin": "Menü"}, 2000, 1000)
    assert (p["x"], p["y"], p["g"], p["y2"]) == (1000, 250, 400, 40)
    assert 13 <= p["yazi_px"] <= 40
    tasan = mantik.ekran_ogesi_px({"x": 0.95, "y": 0.99, "g": 0.5, "y2": 0.5, "metin": "x"}, 1000, 1000)
    assert tasan["x"] + tasan["g"] <= 1000 + 1 and tasan["y"] + tasan["y2"] <= 1000 + 12


# ---------- monitör geometrisi ----------

def test_monitor_ayristirma_mss():
    ham = [{"left": 0, "top": 0, "width": 4480, "height": 1440},
           {"left": 0, "top": 0, "width": 2560, "height": 1440},
           {"left": -1920, "top": 100, "width": 1920, "height": 1080}, {"bozuk": 1}]
    m = mantik.mss_monitorleri(ham)
    assert [x.no for x in m] == [1, 2] and m[0].birincil and not m[1].birincil
    assert m[1].geometri() == "1920x1080-1920+100" and m[0].ad == "Ekran 1 (2560×1440)"


def test_monitor_dikdortgen_ve_secim():
    m = mantik.dikdortgen_monitorleri([(0, 0, 1920, 1080), (1920, 0, 3840, 1080), (5, 5, 5, 5), "x"])
    assert len(m) == 2 and m[1].geometri() == "1920x1080+1920+0"
    assert mantik.ekran_sec(m, 2).no == 2
    assert mantik.ekran_sec(m, 9).no == 1          # yoksa birincil
    assert mantik.ekran_sec([], 1) is None


def test_sse_ayristirma():
    satirlar = [b": nabiz\n", b"\n", b"event: yazi\n", b'data: {"metin":"Merhaba"}\n', b"\n",
                b"event: bozuk\n", b"data: {x\n", b"\n", b"event: yazi-sil\n", b"data: {}\n", b"\n"]
    assert list(mantik.sse_olaylari(satirlar)) == [("yazi", {"metin": "Merhaba"}), ("yazi-sil", {})]


# ---------- komut ----------

def test_komut_paketli_ve_degil(monkeypatch):
    c = yonetim.komut("http://127.0.0.1:8642/kopru/akis", 2)
    assert c[:3] == [sys.executable, "-m", "kopru.katman"] and c[c.index("--ekran") + 1] == "2"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    c = yonetim.komut("http://x/kopru/akis", 1)
    assert c[:2] == [sys.executable, "--katman"] and "-m" not in c


# ---------- süreç yönetimi (sahte başlatıcı) ----------

class Saat:
    t = 100.0

    def __call__(self):
        return self.t


def yonetici_kur(gosterim="bilgisayar", calisiyor=True, destek=True):
    ayar = {"gosterim": gosterim, "katman_ekran": 1}
    surecler, olaylar, durum = [], [], {"calisiyor": calisiyor}

    class Yayin:
        def yayinla(self, ad, veri=None):
            olaylar.append(ad)
    saat = Saat()
    y = yonetim.KatmanYonetici(lambda: ayar, Yayin(), lambda: durum["calisiyor"], lambda: 8642,
                               lambda cmd: surecler.append(SahteSurec(cmd)) or surecler[-1],
                               lambda: destek, saat)
    return y, ayar, surecler, olaylar, durum, saat


def test_baslayinca_acilir_durdurunca_kapanir():
    y, ayar, surecler, olaylar, durum, _ = yonetici_kur()
    y.senkronla(True)
    assert len(surecler) == 1 and y.acik() and "--katman" not in surecler[0].cmd
    y.senkronla()
    assert len(surecler) == 1                       # zaten açık: ikinci süreç yok
    durum["calisiyor"] = False
    y.senkronla()
    assert surecler[0].kapandi and "katman-kapat" in olaylar and not y.acik()


def test_gosterim_tv_ise_acilmaz_ve_ayar_degisince_kapanir():
    y, ayar, surecler, *_ = yonetici_kur(gosterim="tv")
    y.senkronla(True)
    assert surecler == []
    ayar["gosterim"] = "bilgisayar"
    y.senkronla(True)
    assert len(surecler) == 1
    ayar["gosterim"] = "tarayici"
    y.senkronla(True)
    assert surecler[0].kapandi


def test_ekran_degisince_yeniden_baslar():
    y, ayar, surecler, *_ = yonetici_kur()
    y.senkronla(True)
    ayar["katman_ekran"] = 2
    y.senkronla(True)
    assert surecler[0].kapandi and len(surecler) == 2
    assert surecler[1].cmd[surecler[1].cmd.index("--ekran") + 1] == "2"


def test_coken_surec_yeniden_baslar_en_cok_3_kez():
    y, ayar, surecler, olaylar, durum, saat = yonetici_kur()
    y.senkronla(True)
    for _ in range(2):
        surecler[-1].cikis = 1
        y.izle()
    assert len(surecler) == 3 and y.acik()
    surecler[-1].cikis = 1
    y.izle()
    assert len(surecler) == 3 and y.vazgecildi and y.son_hata == "katman_coktu"
    y.izle()
    assert len(surecler) == 3
    saat.t += 61                                    # pencere geçti: kullanıcı isteği olmadan da dener
    y.vazgecildi = False
    y.izle()
    assert len(surecler) == 4


def test_destek_yoksa_baslatmaz():
    y2, _a, surecler, *_ = yonetici_kur(destek=False)
    y2.senkronla(True)
    assert surecler == [] and y2.son_hata == "katman_destek_yok"


def test_dene_acar_ve_sure_bitince_kapanir():
    y, ayar, surecler, olaylar, durum, saat = yonetici_kur(gosterim="tv", calisiyor=False)
    assert y.dene() and len(surecler) == 1
    saat.t += yonetim.DENEME_SN + 1
    y.izle()
    assert surecler[0].kapandi


# ---------- sunucu uç noktaları ----------

@pytest.fixture
async def istemci(aiohttp_client, uygulama_ayari, katman_surec_yok):
    uygulama_ayari["motor"], uygulama_ayari["yedek_motor"] = "sahte", ""
    uygulama_ayari["gosterim"] = "bilgisayar"
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika, katman_destek=lambda: True,
                                  okuyucu_fabrika=lambda: None, kare_fabrika=lambda k: (lambda: None))
    c = await aiohttp_client(app)
    c.surecler = katman_surec_yok
    return c


async def test_katman_durumu(istemci, monkeypatch):
    monkeypatch.setattr(yonetim, "ekranlari_listele", lambda: [{"no": 1, "ad": "Ekran 1 (1920×1080)"}])
    j = await (await istemci.get("/api/ekran-katmani")).json()
    assert j == {"destek": True, "acik": False, "ekran": 1, "ekranlar": [{"no": 1, "ad": "Ekran 1 (1920×1080)"}]}


async def test_dene_katmani_acar_ve_yazi_yayinlar(istemci):
    r = await istemci.post("/api/ekran-katmani/dene")
    assert r.status == 200 and (await r.json())["acik"] is True
    assert len(istemci.surecler) == 1
    from kopru.sunucu import DURUM
    y = istemci.app[DURUM].yayin.son_yazi
    assert y["metin"].startswith("Merhaba! Çeviriler burada") and y["sure_ms"] == 4000
    assert (await (await istemci.get("/api/ekran-katmani")).json())["acik"] is True


async def test_dene_destek_yoksa_hata(aiohttp_client, uygulama_ayari):
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika, katman_destek=lambda: False)
    c = await aiohttp_client(app)
    r = await c.post("/api/ekran-katmani/dene")
    assert r.status == 400 and (await r.json())["hata"] == "katman_destek_yok"
    assert (await (await c.get("/api/ekran-katmani")).json())["destek"] is False


async def test_baslat_katmani_acar_durdur_kapatir(istemci):
    r = await istemci.post("/api/baslat")
    assert r.status == 200 and len(istemci.surecler) == 1
    await istemci.post("/api/durdur")
    assert istemci.surecler[0].kapandi


async def test_baslat_gosterim_tv_katman_acmaz(istemci):
    assert (await istemci.post("/api/ayarlar", json={"gosterim": "tv"})).status == 200
    await istemci.post("/api/baslat")
    assert istemci.surecler == []
    await istemci.post("/api/durdur")


async def test_ayar_dogrulama_gosterim_ekran(istemci):
    assert (await istemci.post("/api/ayarlar", json={"gosterim": "tarayici", "katman_ekran": 2})).status == 200
    for kotu in ({"gosterim": "radyo"}, {"katman_ekran": 0}, {"katman_ekran": "1"}, {"katman_ekran": True}):
        assert (await istemci.post("/api/ayarlar", json=kotu)).status == 400
    j = await (await istemci.get("/api/ayarlar")).json()
    assert j["gosterim"] == "tarayici" and j["katman_ekran"] == 2


def test_varsayilan_gosterim_bilgisayar():
    from kopru import ayarlar
    assert ayarlar.yukle()["gosterim"] == "bilgisayar" and ayarlar.yukle()["katman_ekran"] == 1


# ---------- gerçek pencere (yalnız Tk + Xvfb varsa) ----------

@pytest.mark.skipif(importlib.util.find_spec("tkinter") is None or not shutil.which("xvfb-run"),
                    reason="tkinter ya da xvfb-run yok: gerçek pencere denenmedi")
def test_gercek_pencere_kisa_duman():
    kod = ("from kopru.katman import pencere;import sys;"
           "k=pencere.Katman('http://127.0.0.1:9/x',1,0);k.zam.olay('yazi',{'id':'a','metin':'Merhaba Ğüşiöç',"
           "'sure_ms':2000});k.zam.olay('ekran',{'ogeler':[{'id':'o','x':.1,'y':.1,'g':.2,'y2':.05,'metin':'Menü'}]});"
           "k.ciz();k.kok.update();k.bitir();print('TAMAM')")
    r = subprocess.run(["xvfb-run", "-a", sys.executable, "-c", kod], capture_output=True, text=True, timeout=60,
                       cwd=os.path.dirname(os.path.dirname(__file__)))
    assert "TAMAM" in r.stdout, r.stderr
