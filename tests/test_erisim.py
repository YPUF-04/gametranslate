# SPDX-License-Identifier: AGPL-3.0-only
import importlib.util
import json
import re
import subprocess
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from kopru import erisim, sunucu
from kopru.ayarlar import VARSAYILAN
from kopru.ceviri.sahte import SahteMotor
from kopru.ceviri.temel import ErisimSiniri
from kopru.ceviri.yonetici import CeviriYoneticisi
from tests.conftest import sahte_fabrika

KOK = Path(__file__).resolve().parent.parent
BUGUN = date(2026, 11, 18)


@pytest.fixture
def anahtar():
    return Ed25519PrivateKey.generate()


def test_gidis_donus_sinirsiz_ve_gun(anahtar):
    a = anahtar.public_key()
    k = erisim.kod_uret(anahtar, "sinirsiz", tarih=BUGUN)
    assert k.startswith("AK1-") and re.fullmatch(r"AK1(-[0-9A-Z]{1,5})+", k)
    assert erisim.kod_coz(k, BUGUN, a) == {"tur": "sinirsiz", "bitis": None, "tarih": "2026-11-18"}
    g = erisim.kod_coz(erisim.kod_uret(anahtar, "gun", 30, BUGUN), BUGUN, a)
    assert g["tur"] == "gun" and g["bitis"] == "2026-12-18"


def test_yuk_bicimi(anahtar):
    k = erisim.kod_uret(anahtar, "gun", 7, BUGUN)
    ham = erisim.b32_oku(erisim.temizle(k)[3:])
    n = int.from_bytes(ham[:2], "big")
    yuk = json.loads(ham[2:2 + n])
    assert set(yuk) == {"s", "g", "t", "n"} and yuk["g"] == 7 and len(yuk["n"]) == 8
    assert len(ham) == 2 + n + 64
    assert set(json.loads(erisim.b32_oku(erisim.temizle(erisim.kod_uret(anahtar, "sinirsiz"))[3:])[2:-64])) == {"s", "t", "n"}


def test_bozulmus_kod_reddedilir(anahtar):
    a = anahtar.public_key()
    k = erisim.kod_uret(anahtar, "sinirsiz", tarih=BUGUN)
    s = erisim.temizle(k)
    for i in (5, 20, len(s) - 3):
        bozuk = s[:i] + ("1" if s[i] != "1" else "2") + s[i + 1:]
        with pytest.raises(erisim.KodHatasi) as e:
            erisim.kod_coz(bozuk, BUGUN, a)
        assert e.value.kod == "gecersiz_kod"
    for cop in ("", "abc", "AK1-", "AK1-AAAA", s[:-10], "XX1" + s[3:]):
        with pytest.raises(erisim.KodHatasi):
            erisim.kod_coz(cop, BUGUN, a)


def test_yanlis_anahtar_reddedilir(anahtar):
    baska = Ed25519PrivateKey.generate().public_key()
    with pytest.raises(erisim.KodHatasi):
        erisim.kod_coz(erisim.kod_uret(anahtar, "sinirsiz"), BUGUN, baska)


def test_buyuk_kucuk_bosluk_tire_fark_etmez(anahtar):
    a = anahtar.public_key()
    k = erisim.kod_uret(anahtar, "sinirsiz", tarih=BUGUN)
    for varyant in (k.lower(), k.replace("-", " "), k.replace("-", ""), "  " + k.lower().replace("-", " - ") + " \n"):
        assert erisim.kod_coz(varyant, BUGUN, a)["tur"] == "sinirsiz"
    # karışan harfler: O -> 0, I/L -> 1
    s = erisim.temizle(k)
    assert erisim.temizle(s.replace("0", "O").replace("1", "l")) == s


def test_gun_kodu_sure_dolumu(anahtar):
    a = anahtar.public_key()
    k = erisim.kod_uret(anahtar, "gun", 30, BUGUN)
    assert erisim.kod_coz(k, BUGUN + timedelta(days=30), a)["tur"] == "gun"   # son gün geçerli
    with pytest.raises(erisim.KodHatasi) as e:
        erisim.kod_coz(k, BUGUN + timedelta(days=31), a)
    assert e.value.kod == "suresi_dolmus_kod"
    assert erisim.kod_coz(erisim.kod_uret(anahtar, "sinirsiz", tarih=BUGUN), date(2099, 1, 1), a)


def test_uretim_girdi_denetimi(anahtar):
    for kotu in (("gun", None), ("gun", 0), ("gun", 99999), ("baska", 1)):
        with pytest.raises(ValueError):
            erisim.kod_uret(anahtar, *kotu)


CIHAZ = "ABCDEFGHJK"


def test_cihaza_bagli_kod(anahtar):
    a = anahtar.public_key()
    k = erisim.kod_uret(anahtar, "sinirsiz_dublaj", tarih=BUGUN, cihaz="abcde-fghjk")
    assert erisim.kod_coz(k, BUGUN, a, CIHAZ) == {"tur": "sinirsiz_dublaj", "bitis": None, "tarih": "2026-11-18"}
    assert erisim.kod_coz(k, date(2099, 1, 1), a, "ABCDE-FGHJK")["tur"] == "sinirsiz_dublaj"   # süresiz
    ham = erisim.b32_oku(erisim.temizle(k)[3:])
    yuk = json.loads(ham[2:2 + int.from_bytes(ham[:2], "big")])
    assert set(yuk) == {"s", "c", "t", "n"} and yuk["c"] == CIHAZ and len(yuk["n"]) == 8
    for baska in ("ABCDEFGHJM", None, ""):
        with pytest.raises(erisim.KodHatasi) as e:
            erisim.kod_coz(k, BUGUN, a, baska)
        assert e.value.kod == "baska_cihaz_kodu"
    with pytest.raises(erisim.KodHatasi) as e:   # imza bozuk: cihaz eşleşse de reddedilir
        erisim.kod_coz(k, BUGUN, Ed25519PrivateKey.generate().public_key(), CIHAZ)
    assert e.value.kod == "gecersiz_kod"
    for kotu in (None, "KISA", "ABCDEFGHJU"):     # U alfabede yok
        with pytest.raises(ValueError):
            erisim.kod_uret(anahtar, "sinirsiz_dublaj", cihaz=kotu)


def test_cihaz_numarasi_kararli_ve_gizli():
    from kopru import cihaz
    n1 = cihaz.numara(lambda: "1234-abcd-machine")
    assert n1 == cihaz.numara(lambda: "1234-ABCD-machine") and cihaz.gecerli_mi(n1) and len(n1) == 10
    assert n1 != cihaz.numara(lambda: "1234-abcd-machine2")
    assert "1234" not in n1 and cihaz.gorunum(n1) == n1[:5] + "-" + n1[5:]
    yedek = cihaz.numara(lambda: None)                      # kimlik yoksa ayar klasöründe bir kez üretilir
    assert yedek == cihaz.numara(lambda: None) and cihaz.gecerli_mi(yedek)
    assert cihaz.gecerli_mi(cihaz.numara())                 # gerçek makine


class Saat:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def ilerle(self, sn):
        self.t += sn


def sayac(anahtar=None, ayar=None):
    saat = Saat()
    e = erisim.Erisim(lambda: ayar or dict(VARSAYILAN), lambda: datetime(2026, 11, 18, 12),
                      anahtar.public_key() if anahtar else None, saat=saat, cihaz=lambda: CIHAZ)
    return e, saat


def reklam_izle(e, saat, sn=15.0, sure_sn=None):
    r = e.reklam_baslat(False)
    saat.ilerle(sn)
    return e.reklam_bitir(r["id"], sure_sn)


def test_baslangicta_sure_sifir_ve_altyazi_sinirsiz():
    e, _ = sayac()
    d = e.durum()
    assert e.kalan_sn() == 0 and not e.dublaj_izni()
    assert d["altyazi"] == "sinirsiz" and d["dublaj"]["kalan_dakika"] == 0 and d["dublaj"]["sinirsiz"] is False
    assert d["cihaz"] == "ABCDE-FGHJK" and d["reklam"] is None and d["dublaj"]["ekleyebilir"]


def test_reklam_ust_uste_eklenir_en_cok_4_saat():
    e, saat = sayac()
    for n in range(1, 9):
        assert reklam_izle(e, saat)["kalan_dakika"] == 30 * n
    assert e.kalan_sn() == 240 * 60 and not e.durum()["dublaj"]["ekleyebilir"]
    with pytest.raises(erisim.ReklamHatasi) as x:
        e.reklam_baslat(False)
    assert x.value.kod == "dublaj_sure_dolu"
    e.say(True); saat.ilerle(20); e.say(True)              # biraz kullanıldı: yine de 30 dk sığmaz
    with pytest.raises(erisim.ReklamHatasi):
        e.reklam_baslat(False)


def test_sure_yalniz_dublaj_calisirken_azalir():
    e, saat = sayac()
    reklam_izle(e, saat)
    e.say(False)
    saat.ilerle(100); e.say(False)          # dublaj kapalı/durmuş: azalmaz
    assert e.kalan_sn() == 1800
    for _ in range(6):
        saat.ilerle(10); e.say(True)
    assert e.kalan_sn() == 1740 and e.durum()["dublaj"]["kalan_dakika"] == 29 and e.durum()["dublaj"]["aktif"]
    saat.ilerle(10); e.say(False)           # durdu: o aralık sayılmaz
    assert e.kalan_sn() == 1740
    saat.ilerle(3600); e.say(True)          # uzun takılma en çok 30 sn sayılır
    assert e.kalan_sn() == 1710


def test_sifira_inince_izin_kalkar_yeni_reklamla_geri_gelir():
    e, saat = sayac()
    reklam_izle(e, saat)
    e.say(True)
    for _ in range(70):
        saat.ilerle(30); e.say(True)
    assert e.kalan_sn() == 0 and not e.dublaj_izni()
    assert e.durum(dublaj_acik=True)["dublaj"]["durdu"] is True
    assert e.durum(dublaj_acik=False)["dublaj"]["durdu"] is False
    reklam_izle(e, saat)
    assert e.dublaj_izni() and e.kalan_sn() == 1800


def test_sure_diske_yazilmaz_yeniden_acilis_sure_vermez(tmp_path):
    e, saat = sayac()
    reklam_izle(e, saat); reklam_izle(e, saat)
    assert e.kalan_sn() == 3600
    assert not list(tmp_path.glob("erisim*"))              # hiçbir dosya yazılmadı
    e2, _ = sayac()                                         # "program yeniden açıldı"
    assert e2.kalan_sn() == 0 and not e2.dublaj_izni()


def test_reklam_erken_bitirilemez_ve_iki_kez_sure_vermez():
    e, saat = sayac()
    r = e.reklam_baslat(False)
    assert r["hedef"] == "panel" and r["en_az_sn"] == 15 and r["vast"] is None
    assert e.reklam_baslat(False)["id"] == r["id"]          # açıkken yenisi açılmaz
    saat.ilerle(5)
    with pytest.raises(erisim.ReklamHatasi) as x:
        e.reklam_bitir(r["id"])
    assert x.value.kod == "reklam_erken" and 9 <= x.value.kalan_sn <= 10
    saat.ilerle(10)
    with pytest.raises(erisim.ReklamHatasi):                # 30 sn'lik reklam bildirildi: 30 sn beklenir
        e.reklam_bitir(r["id"], 30)
    with pytest.raises(erisim.ReklamHatasi):
        e.reklam_bitir("yanlis", 0)
    saat.ilerle(15)
    assert e.reklam_bitir(r["id"], 30)["kalan_dakika"] == 30
    with pytest.raises(erisim.ReklamHatasi) as x:
        e.reklam_bitir(r["id"], 30)
    assert x.value.kod == "reklam_yok" and e.kalan_sn() == 1800
    r2 = e.reklam_baslat(True)                              # çok uzun bildirilen reklam en çok 120 sn bekletir
    saat.ilerle(119.5)
    assert e.reklam_bitir(r2["id"], 9999)["kalan_dakika"] == 60
    r3 = e.reklam_baslat(True)
    assert r3["hedef"] == "tv" and e.reklam_baslat(True, "panel")["id"] == r3["id"]
    saat.ilerle(10)
    for kotu in ("abc", float("nan"), -50, True):            # bozuk süre: en az 15 sn kuralı geçerli
        with pytest.raises(erisim.ReklamHatasi):
            e.reklam_bitir(r3["id"], kotu)
    saat.ilerle(5)
    assert e.reklam_bitir(r3["id"], "abc")["kalan_dakika"] == 90


def test_unutulan_reklam_ve_vast_ayari(monkeypatch):
    ayar = {**VARSAYILAN, "erisim": {"vast_adresi": ""}}
    e, saat = sayac(ayar=ayar)
    r = e.reklam_baslat(False)
    saat.ilerle(601)
    assert e.acik_reklam() is None and e.reklam_baslat(False)["id"] != r["id"]
    monkeypatch.setattr(erisim.reklam_ayari, "VAST_ADRESI", "https://ornek.test/vast?c=[CACHEBUSTING]")
    assert e.vast_adresi() == "https://ornek.test/vast?c=[CACHEBUSTING]"
    ayar["erisim"]["vast_adresi"] = "https://baska.test/v"
    assert e.vast_adresi() == "https://baska.test/v"
    ayar["erisim"]["vast_adresi"] = "http://guvensiz.test/v"   # yalnız https
    assert e.vast_adresi() == "https://ornek.test/vast?c=[CACHEBUSTING]"
    assert not erisim.vast_gecerli("javascript:alert(1)") and erisim.vast_gecerli("")


def test_kod_sinirsiz_dublaj_verir_eski_kodlar_dahil(anahtar, ortam):
    from kopru import anahtarlar
    for tur, gun in (("sinirsiz_dublaj", None), ("sinirsiz", None), ("gun", 2)):
        ortam.veri.clear(); anahtarlar._onbellegi_sifirla()
        e, saat = sayac(anahtar)
        assert not e.dublaj_izni()
        bilgi = e.kod_gir(erisim.kod_uret(anahtar, tur, gun, BUGUN, cihaz=CIHAZ))
        assert bilgi["tur"] == tur and e.dublaj_izni() and e.sinirsiz()
        e.say(True); saat.ilerle(30); e.say(True)
        assert e.kalan_sn() == 0 and e.dublaj_izni()           # geri sayım yok
        with pytest.raises(erisim.ReklamHatasi) as x:
            e.reklam_baslat(False)
        assert x.value.kod == "dublaj_sinirsiz"
        d = e.durum()
        assert d["kod"] == tur and d["dublaj"]["sinirsiz"] and not d["dublaj"]["ekleyebilir"]
        e2, _ = sayac(anahtar)                                  # kod kalıcı (kasada)
        assert e2.sinirsiz()


def test_kod_kasada_saklanir_kasa_yoksa_dosyada(anahtar, ortam, tmp_path, monkeypatch):
    e, _ = sayac(anahtar)
    k = erisim.kod_uret(anahtar, "sinirsiz_dublaj", tarih=BUGUN, cihaz=CIHAZ)
    e.kod_gir(k)
    assert ortam.veri[("AltyaziKoprusu", "erisim_kodu")] == erisim.gorunum(erisim.temizle(k)[3:])
    assert not (tmp_path / "erisim.json").exists()
    ortam.veri.clear()
    from kopru import anahtarlar
    anahtarlar._onbellegi_sifirla()

    def kasa_yok(*a, **k):
        raise anahtarlar.KasaHatasi("kasa_yok")
    monkeypatch.setattr(anahtarlar, "yaz", kasa_yok)
    e2, _ = sayac(anahtar)
    e2.kod_gir(k)
    assert json.loads((tmp_path / "erisim.json").read_text())["kod"].startswith("AK1-")
    e3, _ = sayac(anahtar)
    assert e3.sinirsiz()                                        # eski düz dosyadaki kod da okunur


def test_baska_cihazin_kodu_ve_gecersiz_kod_kaydedilmez(anahtar):
    e, _ = sayac(anahtar)
    with pytest.raises(erisim.KodHatasi) as x:
        e.kod_gir(erisim.kod_uret(anahtar, "sinirsiz_dublaj", cihaz="ZZZZZZZZZZ"))
    assert x.value.kod == "baska_cihaz_kodu"
    with pytest.raises(erisim.KodHatasi):
        e.kod_gir("AK1-ABCDE-FGHJK-MNPQR-STVWX-YZ012-34567-89ABC-DEFGH")
    with pytest.raises(erisim.KodHatasi):
        e.kod_gir(erisim.kod_uret(anahtar, "gun", 1, date(2020, 1, 1)))
    assert e.durum()["kod"] is None and not e.dublaj_izni()


# ---------- çeviri: altyazı sınırsız, dublaj süreli ----------

async def test_altyazi_cevirisi_hic_sinirlanmaz_dublaj_cevirisi_sinirlanir():
    motor = SahteMotor()
    y = CeviriYoneticisi(motor, None, None)
    y.dublaj_izni = lambda: False
    assert not hasattr(y, "erisim_izni")
    (c,) = await y.cevir(["Fresh line"])
    assert c.metin == "[TR] Fresh line"
    assert await y.video_cevir(["Hi"], [1.0], "en", "tr") == ["[TR] Hi"]   # video: başlarken denetlenir
    with pytest.raises(ErisimSiniri):
        await y.dublaj_cevir("Hello", "en", "tr", 2.0)
    y.dublaj_izni = lambda: True
    assert (await y.dublaj_cevir("Hello", "en", "tr", 2.0)).metin


async def test_dublaj_suresizken_durur_sure_gelince_kendiliginden_surer(uygulama_ayari):
    import asyncio
    from kopru.dublaj.yonetim import DublajYonetici
    from kopru.yayin import Yayin
    uygulama_ayari["dublaj"] = {**uygulama_ayari["dublaj"], "motor": "pocket"}
    y = DublajYonetici(lambda: uygulama_ayari, Yayin(), lambda: None)
    izin = {"v": False}
    y.izin = lambda: izin["v"]
    calisti = []

    async def sahte_yurut():
        calisti.append(1)
        await asyncio.sleep(3600)
    y._yurut = sahte_yurut
    y.senkronla(True)
    await asyncio.sleep(0)
    assert not y.etkin() and y.istenen() and calisti == []
    izin["v"] = True
    y.senkronla()
    await asyncio.sleep(0)
    assert y.etkin() and calisti == [1]
    izin["v"] = False
    y.senkronla()
    await asyncio.sleep(0)
    assert not y.etkin() and y.istenen()          # sakince durakladı; kullanıcının isteği korunur
    izin["v"] = True
    y.senkronla()
    await asyncio.sleep(0)
    assert y.etkin()
    y.senkronla(False)
    assert not y.istenen()
    from kopru.dublaj.temel import DublajHatasi
    y.ortam.kurulu = lambda: True
    izin["v"] = False
    with pytest.raises(DublajHatasi) as x:
        y.video_baslat(KOK / "README.md", None)
    assert x.value.kod == "dublaj_suresi_yok"


# ---------- API ----------

@pytest.fixture
async def istemci(aiohttp_client, uygulama_ayari, anahtar):
    uygulama_ayari["motor"] = "sahte"
    uygulama_ayari["yedek_motor"] = ""
    saat = Saat()
    e = erisim.Erisim(lambda: uygulama_ayari, lambda: datetime(2026, 11, 18, 12), anahtar.public_key(),
                      saat=saat, cihaz=lambda: CIHAZ)
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika, erisim=e)
    c = await aiohttp_client(app)
    c.anahtar, c.saat = anahtar, saat
    return c


async def test_api_erisim_ilk_durum(istemci):
    j = await (await istemci.get("/api/erisim")).json()
    assert j["altyazi"] == "sinirsiz" and j["kod"] is None and j["cihaz"] == "ABCDE-FGHJK"
    assert j["dublaj"] == {"sinirsiz": False, "kalan_sn": 0, "kalan_dakika": 0, "aktif": False, "durdu": False,
                           "ekle_dakika": 30, "en_cok_dakika": 240, "ekleyebilir": True}
    assert j["reklam"] is None and j["tv_reklam"] is False
    assert "sinir" not in await (await istemci.get("/api/durum")).json()


async def test_api_altyazi_suresiz_calisir(istemci):
    r = await istemci.post("/api/dene", json={"metin": "Hi"})
    assert r.status == 200
    d = istemci.server.app[sunucu.DURUM]
    (c,) = await d.yonetici.cevir(["no limit"])
    assert c.metin and "sinir" not in d.durum_olayi() and "dublaj_sinir" not in d.durum_olayi()


async def test_api_kod_girisi(istemci):
    r = await istemci.post("/api/erisim", json={"kod": "AK1-YANLIS"})
    j = await r.json()
    assert r.status == 400 and j["hata"] == "gecersiz_kod"
    assert j["mesaj"] == "Bu kod geçerli değil. Harfleri kontrol edip tekrar deneyin."
    eski = erisim.kod_uret(istemci.anahtar, "gun", 1, date(2020, 1, 1))
    assert (await (await istemci.post("/api/erisim", json={"kod": eski})).json())["hata"] == "suresi_dolmus_kod"
    baska = erisim.kod_uret(istemci.anahtar, "sinirsiz_dublaj", cihaz="ZZZZZ-ZZZZZ")
    r = await istemci.post("/api/erisim", json={"kod": baska})
    j = await r.json()
    assert r.status == 400 and j["hata"] == "baska_cihaz_kodu" and "başka bir bilgisayar" in j["mesaj"]
    assert (await istemci.post("/api/erisim", json={"kod": 5})).status == 400
    assert (await istemci.post("/api/erisim", data="x")).status == 400
    k = erisim.kod_uret(istemci.anahtar, "sinirsiz_dublaj", cihaz=CIHAZ)
    r = await istemci.post("/api/erisim", json={"kod": k.lower().replace("-", " ")})
    assert r.status == 200 and await r.json() == {"tamam": True, "tur": "sinirsiz_dublaj"}
    j = await (await istemci.get("/api/erisim")).json()
    assert j["kod"] == "sinirsiz_dublaj" and j["dublaj"]["sinirsiz"] is True
    r = await istemci.post("/api/erisim/reklam", json={})
    assert r.status == 409 and (await r.json())["hata"] == "dublaj_sinirsiz"


async def test_api_reklam_panelde_erken_bitti_reddedilir(istemci):
    d = istemci.server.app[sunucu.DURUM]
    q = d.yayin.abone_ol()
    r = await istemci.post("/api/erisim/reklam", json={"yer": "otomatik"})
    j = await r.json()
    assert r.status == 200 and j["hedef"] == "panel" and j["en_az_sn"] == 15 and j["vast"] is None
    assert q.empty()                                               # TV yok: SSE reklam olayı yok
    g = await (await istemci.get("/api/erisim")).json()
    assert g["reklam"]["id"] == j["id"] and g["reklam"]["hedef"] == "panel"
    istemci.saat.ilerle(3)
    r = await istemci.post("/api/erisim/reklam/bitti", json={"id": j["id"], "sure_sn": 0})
    assert r.status == 409 and (await r.json())["hata"] == "reklam_erken" and (await r.json())["kalan_sn"] > 10
    assert (await (await istemci.get("/api/erisim")).json())["dublaj"]["kalan_dakika"] == 0
    istemci.saat.ilerle(12)
    r = await istemci.post("/api/erisim/reklam/bitti", json={"id": j["id"], "sure_sn": 0})
    assert r.status == 200 and (await r.json())["kalan_dakika"] == 30
    r = await istemci.post("/api/erisim/reklam/bitti", json={"id": j["id"]})
    assert r.status == 404 and (await r.json())["hata"] == "reklam_yok"
    assert ("reklam-bitti", {"id": j["id"]}) in [q.get_nowait() for _ in range(q.qsize())]
    g = await (await istemci.get("/api/erisim")).json()
    assert g["dublaj"]["kalan_dakika"] == 30 and g["reklam"] is None


async def test_api_reklam_tvde_oynar_tv_bitirir(istemci, monkeypatch):
    d = istemci.server.app[sunucu.DURUM]
    monkeypatch.setattr(erisim.reklam_ayari, "VAST_ADRESI", "https://ornek.test/vast")
    g = await (await istemci.get("/api/erisim")).json()
    assert g["vast_var"] is True and g["reklam_izni"] is None
    j = await (await istemci.post("/api/erisim/reklam", json={})).json()
    assert j["vast"] is None            # izin yok: yalnız kendi destek ekranımız, kimseye bağlanmaz
    d.erisim._reklam = None
    assert (await istemci.post("/api/ayarlar", json={"erisim": {"reklam_izni": "evet"}})).status == 400
    assert (await istemci.post("/api/ayarlar", json={"erisim": {"reklam_izni": True}})).status == 200
    d.erisim._ayar = lambda: d.ayar
    q = d.yayin.abone_ol()
    d.reklam_istemci = 1
    j = await (await istemci.post("/api/erisim/reklam", json={})).json()
    assert j["hedef"] == "tv" and j["vast"] == "https://ornek.test/vast"
    assert q.get_nowait() == ("reklam", {"id": j["id"], "vast": "https://ornek.test/vast", "en_az_sn": 15,
                                         "bitti": "/kopru/reklam/bitti"})
    istemci.saat.ilerle(20)
    r = await istemci.post("/kopru/reklam/bitti", json={"id": j["id"], "sure_sn": 30})   # 30 sn'lik reklam
    assert r.status == 409 and r.headers["Access-Control-Allow-Origin"] == "*"
    istemci.saat.ilerle(10)
    r = await istemci.post("/kopru/reklam/bitti", json={"id": j["id"], "sure_sn": 30})
    assert r.status == 200 and (await r.json())["kalan_dakika"] == 30
    j2 = await (await istemci.post("/api/erisim/reklam", json={"yer": "panel"})).json()
    assert j2["hedef"] == "panel"                                  # "burada izle"
    d.reklam_istemci = 0


async def test_api_tv_akisi_reklam_yetenegini_bildirir(istemci):
    d = istemci.server.app[sunucu.DURUM]
    r = await istemci.get("/kopru/akis?reklam=1")
    for _ in range(50):
        if d.reklam_istemci == 1:
            break
        import asyncio
        await asyncio.sleep(0.02)
    assert d.reklam_istemci == 1
    assert (await (await istemci.get("/api/erisim")).json())["tv_reklam"] is True
    r.close()
    r2 = await istemci.get("/kopru/akis")
    import asyncio
    await asyncio.sleep(0.05)
    r2.close()


async def test_api_dublaj_suresi_bitince_duraklar_reklamla_surer(istemci, monkeypatch):
    d = istemci.server.app[sunucu.DURUM]
    monkeypatch.setattr(d.dublaj, "istenen", lambda: True)
    etkin = {"v": True}
    monkeypatch.setattr(d.dublaj, "etkin", lambda: etkin["v"])
    senk = []
    monkeypatch.setattr(d.dublaj, "senkronla", lambda *a: senk.append(d.erisim.dublaj_izni()))
    assert d.durum_olayi()["dublaj_sinir"] is True          # dublaj açık ama süre yok
    assert (await (await istemci.get("/api/durum")).json())["dublaj_sinir"] is True
    assert (await (await istemci.get("/api/erisim")).json())["dublaj"]["durdu"] is True
    j = await (await istemci.post("/api/erisim/reklam", json={})).json()
    istemci.saat.ilerle(15)
    assert (await istemci.post("/api/erisim/reklam/bitti", json={"id": j["id"]})).status == 200
    assert senk == [True] and "dublaj_sinir" not in d.durum_olayi()
    d.erisim_say()
    for _ in range(61):                                      # 61 x 30 sn çalışan dublaj
        istemci.saat.ilerle(30); d.erisim_say()
    assert d.erisim.kalan_sn() == 0 and senk == [True, False] and d.durum_olayi()["dublaj_sinir"] is True
    etkin["v"] = False                                       # çeviri durdu: sayaç durur
    j = await (await istemci.post("/api/erisim/reklam", json={})).json()
    istemci.saat.ilerle(15)
    await istemci.post("/api/erisim/reklam/bitti", json={"id": j["id"]})
    for _ in range(10):
        istemci.saat.ilerle(30); d.erisim_say()
    assert d.erisim.kalan_sn() == 1800


async def test_api_yalniz_yerel(istemci, monkeypatch):
    monkeypatch.setattr(sunucu, "uzak_adres", lambda r: "10.0.0.5")
    assert (await istemci.get("/api/erisim")).status == 403
    assert (await istemci.post("/api/erisim", json={"kod": "x"})).status == 403
    assert (await istemci.post("/api/erisim/reklam", json={})).status == 403
    assert (await istemci.post("/api/erisim/reklam/bitti", json={"id": "r"})).status == 403
    assert (await istemci.post("/kopru/reklam/bitti", json={"id": "r"})).status == 404   # yerel ağdan: yalnız doğru kimlikle


async def test_api_ayar_vast_adresi(istemci):
    assert (await istemci.post("/api/ayarlar", json={"erisim": {"vast_adresi": "http://x"}})).status == 400
    assert (await istemci.post("/api/ayarlar", json={"erisim": {"vast_adresi": "https://ads.test/v"}})).status == 200
    d = istemci.server.app[sunucu.DURUM]
    assert d.ayar["erisim"]["vast_adresi"] == "https://ads.test/v"
    assert erisim.Erisim(lambda: d.ayar, cihaz=lambda: CIHAZ).vast_adresi() == "https://ads.test/v"


# ---------- depoda özel anahtar yok ----------

def test_depoda_ozel_anahtar_yok():
    dosyalar = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=KOK, text=True,
                              capture_output=True, check=True).stdout.splitlines()
    assert dosyalar
    sorunlu = []
    for ad in dosyalar:
        yol = KOK / ad
        if not yol.is_file() or yol.suffix in (".png", ".ico", ".icns", ".exe", ".dmg", ".zip") \
                or ad == "tests/test_erisim.py":
            continue
        try:
            icerik = yol.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # gerçek bir PEM gövdesi aranır (kodda "PRIVATE KEY" sözü geçebilir)
        if re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----\s*[A-Za-z0-9+/=]{20,}", icerik):
            sorunlu.append(ad)
    assert sorunlu == []
    ignore = (KOK / ".gitignore").read_text()
    assert "*.pem" in ignore and "ozel_anahtar*" in ignore


# ---------- kod_uret aracı ----------

def arac():
    spec = importlib.util.spec_from_file_location("kod_uret", KOK / "araclar" / "kod_uret.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_arac_cli_kodlari_uygulama_kabul_eder(tmp_path, monkeypatch, capsys):
    yol = tmp_path / "gizli" / "ozel_anahtar.pem"
    monkeypatch.setenv("KOPRU_KOD_ANAHTARI", str(yol))
    m = arac()
    assert m.main(["--sinirsiz"]) == 2           # anahtar yokken dostça çıkar
    assert m.main(["--anahtar-olustur"]) == 0
    cikti = capsys.readouterr().out
    assert yol.is_file() and "yedekle" in cikti and "ACIK_ANAHTAR" in cikti
    once = yol.read_bytes()
    assert m.main(["--anahtar-olustur"]) == 0 and yol.read_bytes() == once   # eskisi ezilmez
    capsys.readouterr()
    assert m.main(["--sinirsiz", "--adet", "3"]) == 0
    kodlar = capsys.readouterr().out.split()
    assert len(kodlar) == 3 and len(set(kodlar)) == 3
    assert m.main(["--gun", "30"]) == 0
    gun_kodu = capsys.readouterr().out.strip()
    assert m.main(["--sinirsiz", "--adet", "101"]) == 2
    acik = serialization.load_pem_private_key(once, None).public_key()
    for k in kodlar:
        assert erisim.kod_coz(k, date.today(), acik)["tur"] == "sinirsiz"
    assert erisim.kod_coz(gun_kodu, date.today(), acik)["tur"] == "gun"
    # yapıştırılacak satır gerçekten bu anahtarı verir
    satir = [s for s in cikti.splitlines() if s.startswith("ACIK_ANAHTAR")][0]
    assert erisim.acik_anahtar_oku(satir.split('"')[1]).public_bytes_raw() == acik.public_bytes_raw()


def test_arac_web_sayfasi(tmp_path, monkeypatch):
    import threading
    from http.server import ThreadingHTTPServer
    monkeypatch.setenv("KOPRU_KOD_ANAHTARI", str(tmp_path / "k.pem"))
    m = arac()
    s = ThreadingHTTPServer(("127.0.0.1", 0), m.Isleyici)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    taban = "http://127.0.0.1:%d" % s.server_address[1]
    try:
        def al(yol, veri=None):
            return urllib.request.urlopen(urllib.request.Request(taban + yol, data=veri)).read().decode()
        assert "Anahtar oluştur" in al("/")
        s1 = al("/anahtar", b"")
        assert "kimseyle paylaşma" in s1 and "ACIK_ANAHTAR" in s1 and "Üret" in s1
        s2 = al("/uret", b"tur=gun&gun=30&adet=2")
        kodlar = re.findall(r"AK1-[0-9A-Z-]+", s2)
        assert len(kodlar) == 2 and "Kopyala" in s2 and "CSV indir" in s2
        acik = serialization.load_pem_private_key((tmp_path / "k.pem").read_bytes(), None).public_key()
        assert erisim.kod_coz(kodlar[0], date.today(), acik)["tur"] == "gun"
        csv = al(re.search(r'href="(/csv\?k=[^"]+)"', s2).group(1))
        assert csv.splitlines()[0] == "kod" and len(csv.splitlines()) == 3
        assert "kontrol et" in al("/uret", b"tur=gun&gun=abc&adet=2")
    finally:
        s.shutdown()
        s.server_close()


def test_saf_dogrulayici_cryptography_ile_uyumlu():
    """Uygulamadaki kütüphanesiz doğrulayıcı, gerçek Ed25519 imzalarını kabul etmeli, bozukları reddetmeli."""
    import os
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from kopru.ed25519_dogrula import AcikAnahtar
    for i in range(10):
        k = Ed25519PrivateKey.generate()
        m = os.urandom(i * 11)
        imza = k.sign(m)
        a = AcikAnahtar(k.public_key().public_bytes_raw())
        a.verify(imza, m)
        bozuk = bytearray(imza)
        bozuk[i] ^= 1
        with pytest.raises(ValueError):
            a.verify(bytes(bozuk), m)
        with pytest.raises(ValueError):
            a.verify(imza, m + b"!")


def test_uygulama_cryptography_yuklemez():
    import sys
    kod = "import sys, kopru.sunucu; print('cryptography' in sys.modules)"
    cikti = subprocess.run([sys.executable, "-c", kod], capture_output=True, text=True, check=True).stdout.strip()
    assert cikti == "False"


def test_arac_cihaza_bagli_kod(tmp_path, monkeypatch, capsys):
    import threading
    from http.server import ThreadingHTTPServer
    monkeypatch.setenv("KOPRU_KOD_ANAHTARI", str(tmp_path / "k.pem"))
    m = arac()
    assert m.main(["--anahtar-olustur"]) == 0
    capsys.readouterr()
    assert m.main(["--cihaz", "abcde-fghjk", "--adet", "2"]) == 0
    kodlar = capsys.readouterr().out.split()
    acik = serialization.load_pem_private_key((tmp_path / "k.pem").read_bytes(), None).public_key()
    assert len(kodlar) == 2
    for k in kodlar:
        assert erisim.kod_coz(k, date.today(), acik, CIHAZ)["tur"] == "sinirsiz_dublaj"
        with pytest.raises(erisim.KodHatasi):
            erisim.kod_coz(k, date.today(), acik, "ZZZZZZZZZZ")
    assert m.main(["--cihaz", "KISA"]) == 2
    s = ThreadingHTTPServer(("127.0.0.1", 0), m.Isleyici)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        taban = "http://127.0.0.1:%d" % s.server_address[1]
        sayfa = urllib.request.urlopen(taban + "/").read().decode()
        assert "Bir bilgisayara özel" in sayfa and "Cihaz numarası" in sayfa
        s2 = urllib.request.urlopen(urllib.request.Request(taban + "/uret", data=b"tur=sinirsiz_dublaj&cihaz=ABCDE-FGHJK&adet=1")).read().decode()
        (k,) = re.findall(r"AK1-[0-9A-Z-]+", s2)
        assert erisim.kod_coz(k, date.today(), acik, CIHAZ)["tur"] == "sinirsiz_dublaj"
        s3 = urllib.request.urlopen(urllib.request.Request(taban + "/uret", data=b"tur=sinirsiz_dublaj&cihaz=&adet=1")).read().decode()
        assert "cihaz numarası 10 harf" in s3
    finally:
        s.shutdown()
        s.server_close()
