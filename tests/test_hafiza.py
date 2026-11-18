# SPDX-License-Identifier: AGPL-3.0-only
"""Oyun hafızası, izin, paket, bağlam, kalite, önden çeviri, düzeltme (PROTOKOL 6)."""
import asyncio
import io
import json
import time
import zipfile

import aiohttp
import pytest

from kopru import ayarlar, hafiza as hafiza_mod, oyunlar, paket, sozluk, sunucu
from kopru.ceviri import istem, model_sec, motor_olustur
from kopru.ceviri.claude import ClaudeMotoru
from kopru.ceviri.temel import Baglam, Ceviri
from kopru.ceviri.yonetici import CeviriYoneticisi
from kopru.hafiza import Hafiza, OneriDeposu
from kopru.isleme import Isleme
from kopru.okuma import Satir
from kopru.onbellek import Onbellek
from kopru.ayarlar import VARSAYILAN
from kopru.yayin import Yayin
from tests.conftest import sahte_fabrika
from tests.test_cekirdek import SahteIstemci, _yanit
from tests.test_isleme import Senaryo, altyazi
from tests.test_sunucu import sse_oku


def dosyalar(kok):
    return sorted(p.name for p in kok.rglob("*") if p.is_file())


@pytest.fixture
async def istemci(aiohttp_client, uygulama_ayari):
    uygulama_ayari["motor"] = "sahte"
    uygulama_ayari["yedek_motor"] = ""
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika)
    return await aiohttp_client(app)


# ---------- oyun kayıt defteri ----------

def test_kod_uretimi_ve_goc(tmp_path):
    assert oyunlar.kod_uret("GTA 6") == "gta6"
    assert oyunlar.kod_uret("Çılgın Şöför: Ğüzel İş") == "cilginsoforguzelis"
    assert oyunlar.kod_uret("???") == "oyun"
    assert not oyunlar.gecerli_kod("../x")
    eski = tmp_path / "sozlukler"
    eski.mkdir()
    (eski / "Last_of_Us.json").write_text(json.dumps(
        {"oyun": "Last of Us", "terimler": [{"asil": "Ellie", "ceviri": "Ellie"}]}))
    assert oyunlar.goc_et() == 1
    assert sozluk.yukle("lastofus")[0]["asil"] == "Ellie"
    assert (tmp_path / "oyunlar" / "lastofus" / "sozluk.json").exists()
    assert not eski.exists()
    assert oyunlar.oku("lastofus")["ad"] == "Last of Us"


def test_olustur_benzersiz_kod():
    a = oyunlar.olustur("GTA 6", "argo bol", "siz")
    b = oyunlar.olustur("GTA 6")
    assert a == "gta6" and b != a
    assert oyunlar.oku(a)["hitap"] == "siz"
    with pytest.raises(ValueError):
        oyunlar.oyun_dizini("../kacis")


# ---------- hafıza + izin ----------

def test_izin_yokken_diske_yazilmaz(tmp_path):
    h = Hafiza("gta6", lambda: False)
    assert h.kaydet("Hello there", "Selam", "motor", "sahte")
    assert h.bul("hello there!") == ("Selam", "motor")   # aynı normalleştirme
    assert not (tmp_path / "oyunlar").exists()
    OneriDeposu("gta6", lambda: False).ekle("Vice City", "Vice City")
    assert dosyalar(tmp_path) == []


def test_izin_gelince_ram_kayitlari_kalicilasir(tmp_path):
    izin = {"v": False}
    h = Hafiza("gta6", lambda: izin["v"])
    h.kaydet("Hello", "Selam", "kullanici")
    izin["v"] = True
    h.kaydet("Run", "Koş", "motor", "x")
    h.kapat()
    assert "hafiza.sqlite" in dosyalar(tmp_path)
    h2 = Hafiza("gta6", lambda: True)
    assert h2.bul("hello") == ("Selam", "kullanici") and h2.bul("run") == ("Koş", "motor")


def test_kullanici_duzeltmesi_motoru_ve_paketi_yener():
    h = Hafiza("gta6", lambda: False)
    h.kaydet("Hello", "Merhaba", "motor", "claude")
    assert h.kaydet("Hello", "Selam", "paket")          # paket motoru yener
    assert h.kaydet("Hello", "Naber", "kullanici")      # kullanıcı hepsini yener
    assert not h.kaydet("Hello", "Başka", "motor", "claude")
    assert not h.kaydet("Hello", "Paket", "paket")
    assert h.bul("Hello") == ("Naber", "kullanici")
    assert h.kaydet("Hello", "Yeni düzeltme", "kullanici")


def test_sayac_artar():
    h = Hafiza("a", lambda: False)
    h.kaydet("Hi", "Selam", "motor")
    h.bul("hi"); h.bul("hi")
    assert h.hepsi()[0]["sayac"] == 2


async def test_yonetici_hafizadan_cevirir_ve_motoru_atlar():
    class Say:
        kod, ad, anahtar_gerekli, cevrimdisi = "say", "Say", False, True
        n = 0

        async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False):
            Say.n += 1
            return [Ceviri("M:" + m) for m in metinler]

    h = Hafiza("a", lambda: False)
    h.kaydet("Hello", "Düzeltilmiş", "kullanici")
    y = CeviriYoneticisi(Say(), None, None, hafiza=h)
    (c,) = await y.cevir(["hello!"])
    assert c.metin == "Düzeltilmiş" and c.kaynak == "kullanici" and Say.n == 0
    (c2,) = await y.cevir(["Other"])
    assert c2.metin == "M:Other" and h.bul("other") == ("M:Other", "motor")


async def test_izin_yokken_hicbir_oyun_verisi_diske_gitmez(istemci, tmp_path):
    assert (await istemci.get("/api/ayarlar")).status == 200
    j = await (await istemci.get("/api/ayarlar")).json()
    assert j["hafiza_izni"] is None and j["kalite"] == "en_iyi" and j["aktif_oyun"] == "varsayilan"
    d = istemci.server.app[sunucu.DURUM]
    await d.yonetici.cevir(["Hello there"])
    assert (await istemci.post("/api/duzelt", json={"asil": "Hello there", "ceviri": "Selam"})).status == 200
    kod = (await (await istemci.post("/api/oyunlar", json={"ad": "GTA 6"})).json())["kod"]
    assert (await istemci.post("/api/oyun-sec", json={"kod": kod})).status == 200
    (c,) = await d.yonetici.cevir(["Hello there"])
    await d.yonetici.cevir(["Another line"])
    ad = dosyalar(tmp_path)
    assert "hafiza.sqlite" not in ad and "onbellek.sqlite3" not in ad
    assert not list(tmp_path.rglob("*.sqlite*"))
    # izin verilince kalıcılaşır
    await istemci.post("/api/ayarlar", json={"hafiza_izni": True})
    await istemci.post("/api/duzelt", json={"asil": "Hello there", "ceviri": "Selam"})
    assert "hafiza.sqlite" in dosyalar(tmp_path)


async def test_izin_false_da_yazmaz(istemci, tmp_path):
    await istemci.post("/api/ayarlar", json={"hafiza_izni": False})
    await istemci.post("/api/duzelt", json={"asil": "A line", "ceviri": "Bir satır"})
    assert not list(tmp_path.rglob("*.sqlite*"))
    assert (await istemci.post("/api/ayarlar", json={"hafiza_izni": "evet"})).status == 400
    assert (await istemci.post("/api/ayarlar", json={"kalite": "süper"})).status == 400


# ---------- paket ----------

def _paket_hazirla(tmp_path):
    kod = oyunlar.olustur("GTA 6", "suç oyunu", "siz", [{"ad": "Lucia", "cinsiyet": "k"}])
    sozluk.kaydet(kod, [{"asil": "Vice City", "ceviri": "Vice City"}])
    h = Hafiza(kod, lambda: False)
    h.kaydet("Hello", "Merhaba", "motor", "claude")
    h.kaydet("Run!", "Koş!", "kullanici")
    return kod, h


def test_paket_gidis_donus(tmp_path, monkeypatch):
    kod, h = _paket_hazirla(tmp_path)
    veri = paket.olustur(oyunlar.oku(kod), sozluk.yukle(kod), h.hepsi())
    with zipfile.ZipFile(io.BytesIO(veri)) as z:
        assert sorted(z.namelist()) == ["hafiza.json", "oyun.json", "sozluk.json"]
        icerik = z.read("hafiza.json").decode()
        assert "sayac" not in icerik and "claude" not in icerik   # yalnız metin çiftleri
    # taze dizine içe al
    yeni = tmp_path / "yeni"
    monkeypatch.setenv("KOPRU_AYAR_DIZINI", str(yeni))
    p = paket.oku(veri)
    k2, ek, at, kalici = paket.uygula(p, None, lambda: False)
    assert (k2, ek, at, kalici) == ("gta6", 2, 0, False)
    assert oyunlar.oku("gta6")["hitap"] == "siz" and oyunlar.oku("gta6")["karakterler"][0]["ad"] == "Lucia"
    assert sozluk.yukle("gta6") == [{"asil": "Vice City", "ceviri": "Vice City"}]
    assert not list(yeni.rglob("*.sqlite*"))   # izin yok


def test_paket_kullanici_duzeltmesini_ezmez(tmp_path):
    kod, h = _paket_hazirla(tmp_path)
    veri = paket.olustur(oyunlar.oku(kod), sozluk.yukle(kod), h.hepsi())
    h2 = Hafiza(kod, lambda: False)
    h2.kaydet("Run!", "Benim düzeltmem", "kullanici")
    _, ek, at, _ = paket.uygula(paket.oku(veri), h2)
    assert (ek, at) == (1, 1)
    assert h2.bul("run") == ("Benim düzeltmem", "kullanici")
    assert h2.bul("hello") == ("Merhaba", "paket")


def _zip(**dosya):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for ad, v in dosya.items():
            z.writestr(ad.replace("__", "/").replace("_json", ".json") if not ad.startswith("..") else ad,
                       v if isinstance(v, (str, bytes)) else json.dumps(v))
    return b.getvalue()


OYUN = {"ad": "Test"}


def test_kotu_paketler_reddedilir():
    gecerli = _zip(oyun_json=OYUN, hafiza_json={"kayitlar": [{"asil": "a", "ceviri": "b"}]})
    assert paket.oku(gecerli).kayitlar == [("a", "b")]
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("oyun.json", json.dumps(OYUN))
        z.writestr("../kacis.json", "{}")
    kotu = [
        b.getvalue(),                                              # yol atlama
        _zip(oyun_json=OYUN, **{"fazla.exe": b"MZ"}),               # beklenmeyen dosya
        _zip(oyun_json=OYUN, **{"alt__hafiza_json": "{}"}),         # klasör içinde
        _zip(hafiza_json={"kayitlar": []}),                         # oyun.json yok
        _zip(oyun_json="[1,2]"),                                    # şema
        _zip(oyun_json={"ad": "x", "hitap": "abi"}),
        _zip(oyun_json=OYUN, hafiza_json={"kayitlar": [{"asil": 1, "ceviri": "b"}]}),
        _zip(oyun_json=OYUN, hafiza_json="bozuk{"),
        b"bu zip degil",
    ]
    for v in kotu:
        with pytest.raises(paket.PaketHatasi) as e:
            paket.oku(v)
        assert e.value.kod == "paket_gecersiz"


def test_buyuk_paket_reddedilir(monkeypatch):
    monkeypatch.setattr(paket, "AZAMI_BAYT", 1000)
    with pytest.raises(paket.PaketHatasi) as e:
        paket.oku(b"x" * 1001)
    assert e.value.kod == "paket_buyuk"
    monkeypatch.undo()
    monkeypatch.setattr(paket, "AZAMI_ACIK", 100)   # zip bombası: açılmış boyut sınırı
    with pytest.raises(paket.PaketHatasi) as e:
        paket.oku(_zip(oyun_json=OYUN, hafiza_json={"kayitlar": [{"asil": "a" * 90, "ceviri": "b"}]}))
    assert e.value.kod == "paket_buyuk"


async def test_paket_api_yukle_indir(istemci, tmp_path):
    kod = (await (await istemci.post("/api/oyunlar", json={"ad": "GTA 6", "hitap": "siz"})).json())["kod"]
    await istemci.post("/api/oyun-sec", json={"kod": kod})
    await istemci.post("/api/duzelt", json={"asil": "Hello", "ceviri": "Selam"})
    r = await istemci.get(f"/api/paket/{kod}")
    assert r.status == 200 and "gta6.akpaket" in r.headers["Content-Disposition"]
    veri = await r.read()
    d = istemci.server.app[sunucu.DURUM]
    d.hafiza.temizle()
    assert (await istemci.delete(f"/api/oyun/{kod}/hafiza")).status == 200
    form = aiohttp.FormData()
    form.add_field("dosya", veri, filename="x.akpaket", content_type="application/zip")
    j = await (await istemci.post("/api/paket", data=form)).json()
    assert j == {"tamam": True, "kod": "gta6", "eklenen": 1, "atlanan": 0, "kalici": False}
    assert d.hafiza.bul("hello") == ("Selam", "paket")
    kotu = aiohttp.FormData()
    kotu.add_field("dosya", b"zip degil", filename="x.akpaket")
    r = await istemci.post("/api/paket", data=kotu)
    assert r.status == 400 and (await r.json())["hata"] == "paket_gecersiz"
    assert (await istemci.get("/api/paket/yokboyle")).status == 404


async def test_oyunlar_api_ve_sozluk_aktif_oyunda(istemci, tmp_path):
    kod = (await (await istemci.post("/api/oyunlar", json={"ad": "Çılgın Oyun"})).json())["kod"]
    assert kod == "cilginoyun"
    assert (await istemci.post("/api/oyunlar", json={"ad": ""})).status == 400
    assert (await istemci.post("/api/oyun-sec", json={"kod": "yok"})).status == 404
    assert (await istemci.post("/api/oyun-sec", json={"kod": kod})).status == 200
    assert (await (await istemci.get("/api/ayarlar")).json())["aktif_oyun"] == kod
    await istemci.post("/api/sozluk", json={"terimler": [{"asil": "Ellie", "ceviri": "Ellie"}]})
    assert (tmp_path / "oyunlar" / kod / "sozluk.json").exists()
    liste = await (await istemci.get("/api/oyunlar")).json()
    g = [x for x in liste if x["kod"] == kod][0]
    assert g["terim_sayisi"] == 1 and "kayit_sayisi" in g and g["ad"] == "Çılgın Oyun"
    assert any(x["kod"] == "varsayilan" for x in liste)
    j = await (await istemci.post(f"/api/oyun/{kod}", json={"aciklama": "x", "hitap": "siz"})).json()
    assert j["hitap"] == "siz"
    assert (await (await istemci.get(f"/api/oyun/{kod}")).json())["aciklama"] == "x"
    assert (await istemci.delete("/api/oyun/yok/hafiza")).status == 404
    assert (await (await istemci.delete(f"/api/oyun/{kod}/hafiza")).json()) == {"tamam": True}


# ---------- bağlamlı istem ----------

def _baglam():
    return Baglam("GTA 6", "Açık dünya suç oyunu", "siz", [{"ad": "Lucia", "cinsiyet": "k"}],
                  [("Where is Jason?", "Jason nerede?"), ("Dunno, man.", "Bilmem ahbap.")])


def test_istem_baglam_sozluk_hitap():
    b = _baglam()
    sis = istem.sistem_istemi("en", "tr", {"Vice City": "Vice City"}, False, b)
    assert "GTA 6" in sis and "Vice City => Vice City" in sis and '"siz"' in sis
    assert "Lucia (female)" in sis and "42 characters" in sis and "ceviriler" in sis
    assert "Dunno" not in sis                      # değişken kısım sistemde değil
    kul = istem.kullanici_metni(["Hello"], b)
    assert "Where is Jason?" in kul and "Bilmem ahbap." in kul and '["Hello"]' in kul
    assert istem.kullanici_metni(["Hello"]) == '["Hello"]'
    ac = istem.sistem_istemi("en", "tr", {}, True, b)
    assert "60 characters" in ac
    b.son_satirlar = [(f"a{i}", f"c{i}") for i in range(10)]
    assert "a3" not in istem.kullanici_metni(["x"], b) and "a9" in istem.kullanici_metni(["x"], b)


def test_yanit_cozme_esnek():
    c, t = istem.yaniti_coz_tam('{"ceviriler":["A","B"],"yeni_terimler":[{"asil":"X","ceviri":"Y"},5]}', 2, False)
    assert [x.metin for x in c] == ["A", "B"] and t == [{"asil": "X", "ceviri": "Y"}]
    c, t = istem.yaniti_coz_tam('Tamam:\n```json\n{"ceviriler":[{"c":"A","a":"ipucu"}]}\n```', 1, True)
    assert c[0].aciklama == "ipucu" and t == []
    c, _ = istem.yaniti_coz_tam('["düz", "liste"]', 2, False)
    assert [x.metin for x in c] == ["düz", "liste"]
    with pytest.raises(ValueError):
        istem.yaniti_coz_tam('{"ceviriler":["A"]}', 2, False)


async def test_claude_onbellek_blogu_ve_baglam():
    ist = SahteIstemci(_yanit('{"ceviriler":["Merhaba"],"yeni_terimler":[]}'))
    b = _baglam()
    await ClaudeMotoru("k", istemci=ist).cevir(["Hello"], "en", "tr", {"Ellie": "Ellie"}, baglam=b)
    kw = ist.cagrilar[0]
    blok = kw["system"][0]
    assert blok["cache_control"] == {"type": "ephemeral"} and "Ellie => Ellie" in blok["text"]
    assert "Bilmem ahbap." not in blok["text"] and "Bilmem ahbap." in kw["messages"][0]["content"]
    assert kw["output_config"] == {"effort": "low"} and not {"thinking", "temperature"} & kw.keys()
    assert kw["messages"][-1]["role"] == "user"


def test_kalite_modeli():
    def m(kod, kalite, modeller=None):
        a = {**VARSAYILAN, "kalite": kalite, "modeller": modeller or {}}
        return motor_olustur(kod, a).model
    assert m("claude", "en_iyi") == "claude-opus-5-5"
    assert m("claude", "dengeli") == "claude-sonnet-5-5"
    assert m("claude", "hizli") == "claude-haiku-5-5"
    assert m("gemini", "en_iyi") == m("gemini", "hizli") == "gemini-2.5-flash"
    assert m("claude", "hizli", {"claude": "claude-sonnet-5-5"}) == "claude-sonnet-5-5"   # açık seçim ezer
    # eski ayar dosyasındaki varsayılan değer seçim sayılmaz
    assert m("claude", "hizli", {"claude": "claude-opus-5-5"}) == "claude-haiku-5-5"
    assert model_sec("claude", {}) == "claude-opus-5-5"


async def test_yeni_terimler_oneri_olur(istemci):
    ist = SahteIstemci(_yanit(json.dumps({"ceviriler": ["Vice City'ye gidiyoruz"], "yeni_terimler": [
        {"asil": "Vice City", "ceviri": "Vice City"}, {"asil": "Uydurma", "ceviri": "X"},
        {"asil": "Ellie", "ceviri": "Ellie"}]})))
    d = istemci.server.app[sunucu.DURUM]
    d.terimler = {}
    d.yonetici.birincil = ClaudeMotoru("k", istemci=ist)
    d.yonetici.terimler = {"Ellie": "Ellie"}
    await d.yonetici.cevir(["We are going to Vice City"])
    assert await (await istemci.get("/api/oneriler")).json() == [{"asil": "Vice City", "ceviri": "Vice City"}]
    assert not list(d.hafiza._ram) == []   # hafızada
    r = await istemci.post("/api/oneriler", json={"asil": "Vice City", "kabul": True})
    assert r.status == 200
    assert {"asil": "Vice City", "ceviri": "Vice City"} in (await (await istemci.get("/api/sozluk")).json())["terimler"]
    assert await (await istemci.get("/api/oneriler")).json() == []
    assert (await istemci.post("/api/oneriler", json={"asil": "Vice City", "kabul": False})).status == 404


# ---------- zamanlama ----------

class YavasMotor:
    kod, ad, anahtar_gerekli, cevrimdisi = "yavas", "Yavaş", False, True

    def __init__(self, gecikme):
        self.gecikme, self.baslayan, self.biten = gecikme, [], []

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False):
        self.baslayan.append(metinler[0])
        await asyncio.sleep(self.gecikme)
        self.biten.append(metinler[0])
        return [Ceviri("T:" + m) for m in metinler]


def _isleme(kareler, motor, hafiza=None):
    s = Senaryo(kareler)
    y = Yayin()
    q = y.abone_ol()
    ayar = {**VARSAYILAN, "ekrani_cevir": False}
    isl = Isleme(s.kare, s, CeviriYoneticisi(motor, None, None, hafiza=hafiza), y, lambda: ayar)
    return isl, q


async def test_onden_ceviri_gecikmesi_max_ve_toplam_degil():
    motor = YavasMotor(0.4)
    isl, q = _isleme([(10, altyazi("Stay close to me"))] * 3, motor)
    t0 = time.monotonic()
    await isl.adim()                 # 1. kare: önden çeviri başlar
    assert q.empty()
    await asyncio.sleep(0.2)         # kare aralığı
    await isl.adim()                 # 2. kare: aynı metin -> kalanı bekler, yayınlar
    gecen = time.monotonic() - t0
    olay, v = q.get_nowait()
    assert olay == "yazi" and v["metin"] == "T:Stay close to me"
    assert gecen < 0.55              # toplam olsaydı >= 0.6; max(0.2, 0.4+bekleme) ~ 0.45
    assert motor.baslayan == ["Stay close to me"]


async def test_onden_ceviri_degisirse_atilir():
    motor = YavasMotor(0.3)
    isl, q = _isleme([(10, altyazi("Run away now")), (50, altyazi("Hide behind the car"))] +
                     [(90, altyazi("Hide behind the car"))] * 2, motor)
    await isl.adim()
    await asyncio.sleep(0.15)        # çeviri başladı ama bitmedi
    await isl.adim()                 # metin değişti: eski önden çeviri çöpe
    assert q.empty() and "Run away now" not in motor.biten
    await asyncio.sleep(0.1)
    await isl.adim()
    olay, v = q.get_nowait()
    assert v["asil"] == "Hide behind the car" and "Run away now" not in motor.biten


async def test_hafiza_vurusu_ilk_karede_yayinlanir():
    h = Hafiza("a", lambda: False)
    h.kaydet("Stay close", "Yakın dur", "kullanici")
    motor = YavasMotor(5)
    isl, q = _isleme([(10, altyazi("Stay close"))] * 2, motor, h)
    await isl.adim()
    olay, v = q.get_nowait()
    assert v["metin"] == "Yakın dur" and motor.baslayan == []
    assert isl.yonetici.gecmis[-1]["kaynak"] == "kullanici"


# ---------- düzeltme ----------

async def test_duzelt_ekrandaki_satiri_ayni_id_ile_gunceller(istemci):
    r = await istemci.get("/kopru/akis")
    await sse_oku(r, 2)
    await istemci.post("/api/deneme-yazi")
    (olay,) = await sse_oku(r, 1)
    id_ = olay[1]["id"]
    j = await (await istemci.post("/api/duzelt", json={"asil": olay[1]["asil"], "ceviri": "Düzgün hâli"})).json()
    assert j["ekranda"] is True
    (yeni,) = await sse_oku(r, 1)
    assert yeni[0] == "yazi" and yeni[1]["id"] == id_ and yeni[1]["metin"] == "Düzgün hâli"
    j = await (await istemci.post("/api/duzelt", json={"asil": "Baska satir", "ceviri": "x"})).json()
    assert j["ekranda"] is False
    assert (await istemci.post("/api/duzelt", json={"asil": "", "ceviri": "x"})).status == 400
    r.close()


async def test_son_ceviriler_otuzla_sinirli(istemci):
    d = istemci.server.app[sunucu.DURUM]
    for i in range(40):
        d.yonetici.satir_kaydet(f"a{i}", f"s{i}", f"t{i}")
    liste = await (await istemci.get("/api/son-ceviriler")).json()
    assert len(liste) == 30 and liste[0]["id"] == "a39"
    assert set(liste[0]) == {"id", "asil", "ceviri", "kaynak"}
    await istemci.post("/api/duzelt", json={"asil": "s39", "ceviri": "Düzeltildi"})
    assert (await (await istemci.get("/api/son-ceviriler")).json())[0]["kaynak"] == "kullanici"
