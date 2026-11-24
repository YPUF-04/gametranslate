# SPDX-License-Identifier: AGPL-3.0-only
"""PROTOKOL 20.5: oyun paketleri."""
import hashlib
import json

import pytest

from kopru import oyun_paketleri as op
from kopru import oyunlar, sozluk


def test_gomulu_paketler_gecerli_ve_dizin_guncel():
    d = op.gomulu_dizin()
    dizin = json.loads((d / "index.json").read_text(encoding="utf-8"))
    assert dizin == op.dizin_uret(d), "oyun-paketleri/index.json eski: python -m kopru.oyun_paketleri"
    kodlar = {p["kod"] for p in dizin["paketler"]}
    assert {"gta6", "gta5", "rdr2"} <= kodlar
    for kod in kodlar:
        p = op.dogrula(json.loads((d / f"{kod}.json").read_text(encoding="utf-8")))
        assert p and len(p["terimler"]) >= 30 and len(p["yerler"]) >= 10 and len(p["karakterler"]) >= 2
        assert (d / f"{kod}.json").stat().st_size <= op.EN_BUYUK


@pytest.mark.parametrize("ad,kod", [("GTA 6", "gta6"), ("Grand Theft Auto VI", "gta6"), ("gta v", "gta5"),
                                    ("Red Dead Redemption 2", "rdr2"), ("RDR 2", "rdr2")])
def test_oyun_adiyla_eslesir(ad, kod):
    assert op.bul(oyunlar.kod_uret(ad), ad)[0]["kod"] == kod


def test_eslesmeyen_ve_varsayilan_oyun():
    assert op.bul("varsayilan", "Varsayılan") is None
    assert op.bul("tlou", "The Last of Us") is None


def test_birlestirme_kullanici_kazanir_ve_dosyaya_yazilmaz():
    p, _ = op.bul("rdr2", "")
    bilgi = {"ad": "RDR2", "hitap": "sen", "karakterler": [{"ad": "Arthur Morgan", "cinsiyet": "e"}]}
    b, t = op.uygula(bilgi, {"Dead Eye": "Ölüm Gözü"}, p)
    assert t["Dead Eye"] == "Ölüm Gözü"                       # kullanıcının sözlüğü kazanır
    assert t["Eagle Eye"] == "Kartal Gözü" and "Valentine" in b["yerler"]
    assert sum(1 for k in b["karakterler"] if k["ad"] == "Arthur Morgan") == 1
    assert b["argo"] and b["notlar"] and b["paket"]["kod"] == "rdr2"
    assert bilgi == {"ad": "RDR2", "hitap": "sen", "karakterler": [{"ad": "Arthur Morgan", "cinsiyet": "e"}]}


def test_dogrulama_bozuk_paketi_reddeder():
    assert op.dogrula({"bicim": 2, "kod": "x", "surum": "1"}) is None
    assert op.dogrula({"bicim": 1, "kod": "Kötü Kod", "surum": "1"}) is None
    v = op.dogrula({"bicim": 1, "kod": "abc", "surum": "1", "terimler": [{"asil": "a" * 999, "ceviri": "b"}, 5],
                    "karakterler": [{"ad": "X", "cinsiyet": "z"}], "yerler": [None, "Yer"]})
    assert len(v["terimler"][0]["asil"]) == 300 and v["karakterler"] == [{"ad": "X", "cinsiyet": ""}] and v["yerler"] == ["Yer"]


def _sahte_github(dosyalar):
    istenen = []

    def getir(url, en_cok):
        istenen.append(url)
        assert op.url_izinli(url)
        ad = url[len(op.TABAN_URL):]
        if ad not in dosyalar:
            raise OSError("404")
        return dosyalar[ad]
    return getir, istenen


def test_guncelleme_sha_dogrular_ve_onbellege_yazar(tmp_path, monkeypatch):
    monkeypatch.setenv("KOPRU_AYAR_DIZINI", str(tmp_path))
    yeni = json.loads((op.gomulu_dizin() / "gta6.json").read_text(encoding="utf-8"))
    yeni["surum"] = "2099.01.01"
    yeni["terimler"].append({"asil": "Hurricane", "ceviri": "Kasırga"})
    ham = json.dumps(yeni, ensure_ascii=False).encode()
    kotu = dict(yeni, kod="gta5")
    ham_kotu = json.dumps(kotu).encode()
    dizin = {"bicim": 1, "paketler": [
        {"kod": "gta6", "surum": "2099.01.01", "sha256": hashlib.sha256(ham).hexdigest()},
        {"kod": "gta5", "surum": "2099.01.01", "sha256": "0" * 64},                 # SHA tutmaz
        {"kod": "rdr2", "surum": "2000.01.01", "sha256": "1" * 64}]}               # eski: indirilmez
    getir, istenen = _sahte_github({"index.json": json.dumps(dizin).encode(), "gta6.json": ham, "gta5.json": ham_kotu})
    g = op.Guncelleyici(lambda: {}, getir)
    assert g.denetle() == 1 and g.hata == "gecersiz"
    assert not any(u.endswith("rdr2.json") for u in istenen)
    p, kaynak = op.bul("gta6", "")
    assert kaynak == "indirilen" and p["surum"] == "2099.01.01"
    assert op.bul("gta5", "")[1] == "gomulu"
    assert (tmp_path / "oyun_paketleri" / "gta6.json").read_bytes() == ham


def test_guncelleme_yalniz_izinli_adres_ve_ag_yoksa_sessiz(tmp_path, monkeypatch):
    monkeypatch.setenv("KOPRU_AYAR_DIZINI", str(tmp_path))
    assert not op.url_izinli("http://raw.githubusercontent.com/YPUF-04/gametranslate/main/oyun-paketleri/x.json")
    assert not op.url_izinli("https://evil.example/oyun-paketleri/x.json")
    assert not op.url_izinli("https://raw.githubusercontent.com/baskasi/depo/main/x.json")
    g = op.Guncelleyici(lambda: {"oyun_paketleri_guncelle": False})
    assert g.gerekirse_denetle() is False
    g2 = op.Guncelleyici(lambda: {})
    assert g2.denetle() == 0 and g2.hata == "ag"   # conftest: ağ yok


@pytest.fixture
async def istemci(aiohttp_client, uygulama_ayari):
    from kopru import sunucu
    from tests.conftest import sahte_fabrika
    uygulama_ayari["motor"], uygulama_ayari["yedek_motor"] = "sahte", ""
    return await aiohttp_client(sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika))


async def test_sunucu_etkin_oyuna_paketi_katar(istemci):
    from kopru.sunucu import DURUM
    d = istemci.app[DURUM]
    kod = oyunlar.olustur("Red Dead Redemption 2")
    sozluk.kaydet(kod, [{"asil": "Dead Eye", "ceviri": "Ölüm Gözü"}])
    r = await istemci.post("/api/ayarlar", json={"aktif_oyun": kod})
    assert r.status == 200
    y = d.yonetici
    assert y.terimler["Dead Eye"] == "Ölüm Gözü" and y.terimler["Eagle Eye"] == "Kartal Gözü"
    assert "Valentine" in y.bilinen_adlar() and "Arthur" in y.bilinen_adlar()
    assert sozluk.yukle(kod) == [{"asil": "Dead Eye", "ceviri": "Ölüm Gözü"}]   # paket dosyaya yazılmadı
    j = await (await istemci.get("/api/oyun-paketleri")).json()
    assert j["etkin"] == "rdr2" and {p["kod"] for p in j["paketler"]} >= {"gta6", "gta5", "rdr2"}
    j = await (await istemci.post("/api/oyun-paketleri/denetle")).json()
    assert j["hata"] == "ag" and j["son_denetim"]
