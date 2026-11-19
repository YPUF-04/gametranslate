# SPDX-License-Identifier: AGPL-3.0-only
import importlib.util
import json
import re
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from PIL import Image

from kopru import erisim, sunucu
from kopru.ayarlar import VARSAYILAN
from kopru.ceviri.sahte import SahteMotor
from kopru.ceviri.temel import ErisimSiniri
from kopru.ceviri.yonetici import CeviriYoneticisi
from kopru.hafiza import Hafiza
from kopru.isleme import Isleme
from kopru.okuma import Satir
from kopru.yayin import Yayin
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


class Saat:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t

    def ilerle(self, sn):
        self.t += timedelta(seconds=sn)


def sayac(anahtar=None, dakika=30):
    saat = Saat(datetime(2026, 11, 18, 12, 0, 0))
    ayar = {**VARSAYILAN, "erisim": {"ucretsiz_dakika_gun": dakika}}
    return erisim.Erisim(lambda: ayar, saat, anahtar.public_key() if anahtar else None), saat


def test_sure_yalniz_calisirken_birikir():
    e, saat = sayac()
    e.say(False)
    saat.ilerle(10); e.say(False)           # durmuşken sayılmaz
    assert e.kullanilan_sn() == 0
    for _ in range(6):                      # 6 x 10 sn çalışıyor
        saat.ilerle(10); e.say(True)
    assert e.kullanilan_sn() == 60 and e.durum()["kalan_dakika"] == 29
    saat.ilerle(10); e.say(False)           # durdu: o aralık sayılmaz
    assert e.kullanilan_sn() == 60
    saat.ilerle(3600); e.say(True)          # uzun takılma en çok 30 sn sayılır
    assert e.kullanilan_sn() == 90


def test_kota_dolunca_sinir_ve_gece_yarisi_sifirlanir():
    e, saat = sayac(dakika=1)
    e.say(True)
    for _ in range(7):
        saat.ilerle(10); e.say(True)
    assert e.sinir() and e.durum()["kalan_dakika"] == 0
    # kalıcı: yeni örnek aynı dosyayı okur
    e2 = erisim.Erisim(lambda: {"erisim": {"ucretsiz_dakika_gun": 1}}, saat)
    assert e2.sinir()
    saat.t = datetime(2026, 11, 19, 0, 0, 1)   # gece yarısı geçti
    assert not e.sinir() and e.durum()["kalan_dakika"] == 1
    e.say(True); saat.ilerle(5); e.say(True)
    assert 4 <= e.kullanilan_sn() <= 5 and list(e._veri["kullanilan"]) == ["2026-11-19"]


def test_kod_gecerliyken_sinir_yok(anahtar):
    e, saat = sayac(anahtar, dakika=0)
    assert e.sinir()
    bilgi = e.kod_gir(erisim.kod_uret(anahtar, "gun", 2, saat().date()))
    assert bilgi["tur"] == "gun" and not e.sinir() and e.durum()["kod"] == "gun"
    assert e.durum()["bitis"] == "2026-11-20"
    e2 = erisim.Erisim(lambda: {"erisim": {"ucretsiz_dakika_gun": 0}}, saat, anahtar.public_key())
    assert not e2.sinir()                   # kod diskte kalıcı
    saat.t += timedelta(days=3)             # kodun günü bitti
    assert e.sinir() and e.durum()["kod"] is None
    e.kod_gir(erisim.kod_uret(anahtar, "sinirsiz", tarih=saat().date()))
    saat.t += timedelta(days=4000)
    assert not e.sinir() and e.durum()["kod"] == "sinirsiz"


def test_gecersiz_kod_kaydedilmez(anahtar):
    e, saat = sayac(anahtar)
    with pytest.raises(erisim.KodHatasi):
        e.kod_gir("AK1-ABCDE-FGHJK-MNPQR-STVWX-YZ012-34567-89ABC-DEFGH")
    with pytest.raises(erisim.KodHatasi):
        e.kod_gir(erisim.kod_uret(anahtar, "gun", 1, date(2020, 1, 1)))
    assert e.durum()["kod"] is None


# ---------- motor çağrısı ve hafıza ----------

async def test_kota_bitince_motor_reddedilir_hafiza_gosterilir():
    motor = SahteMotor()
    h = Hafiza("a", lambda: False)
    h.kaydet("Known line", "Bilinen cümle", "kullanici")
    y = CeviriYoneticisi(motor, None, None, hafiza=h)
    izin = {"v": True}
    y.erisim_izni = lambda: izin["v"]
    (c,) = await y.cevir(["Fresh line"])
    assert c.metin == "[TR] Fresh line" and len(motor.cagrilar) == 1
    izin["v"] = False
    with pytest.raises(ErisimSiniri):
        await y.cevir(["Another line"])
    (c,) = await y.cevir(["known line"])     # hafıza vuruşu
    assert c.metin == "Bilinen cümle"
    (c,) = await y.cevir(["Fresh line"])     # önbellek yok ama motor çağrısı olmamalı: hafıza motor çıktısını tuttu
    assert len(motor.cagrilar) == 1


async def test_isleme_sinirda_durum_yayinlar_hafizadakini_gosterir():
    BOLGE = (0.1, 0.8, 0.5, 0.05)
    metin = {"m": "Never seen"}

    class Kaynak:
        def kare(self):
            c = 10 if metin["m"] == "Never seen" else 200   # kare değişince yeniden okunur
            return Image.new("RGB", (64, 36), (c, c, c))

        def oku(self, resim):
            return [Satir(metin["m"], *BOLGE)]

    k = Kaynak()
    h = Hafiza("a", lambda: False)
    h.kaydet("Saved line", "Kayıtlı satır", "kullanici")
    motor = SahteMotor()
    y = CeviriYoneticisi(motor, None, None, hafiza=h)
    y.erisim_izni = lambda: False
    yayin = Yayin()
    q = yayin.abone_ol()
    saat = {"t": 0.0}
    isl = Isleme(k.kare, k, y, yayin, lambda: {**VARSAYILAN, "ekrani_cevir": False}, saat=lambda: saat["t"])
    for _ in range(6):
        await isl.adim(); saat["t"] += 0.25
    olaylar = []
    while not q.empty():
        olaylar.append(q.get_nowait())
    assert motor.cagrilar == []
    assert [v for o, v in olaylar if o == "durum"] == [
        {"calisiyor": True, "motor": motor.ad, "yedek": False, "sinir": True}]   # tek kez
    assert not [1 for o, _ in olaylar if o == "yazi"]
    # hafızadaki cümle sınırda da gösterilir
    metin["m"] = "Saved line"
    for _ in range(6):
        await isl.adim(); saat["t"] += 0.25
    yazilar = []
    while not q.empty():
        o, v = q.get_nowait()
        if o == "yazi":
            yazilar.append(v)
    assert yazilar and yazilar[0]["metin"] == "Kayıtlı satır" and motor.cagrilar == []


# ---------- API ----------

@pytest.fixture
async def istemci(aiohttp_client, uygulama_ayari, anahtar):
    uygulama_ayari["motor"] = "sahte"
    uygulama_ayari["yedek_motor"] = ""
    uygulama_ayari["erisim"] = {"ucretsiz_dakika_gun": 12}
    saat = Saat(datetime(2026, 11, 18, 12, 0, 0))
    e = erisim.Erisim(lambda: uygulama_ayari, saat, anahtar.public_key())
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika, erisim=e)
    c = await aiohttp_client(app)
    c.anahtar, c.saat = anahtar, saat
    return c


async def test_api_erisim_ilk_durum(istemci):
    j = await (await istemci.get("/api/erisim")).json()
    assert j == {"kalan_dakika": 12, "kod": None, "bitis": None, "ucretsiz_dakika": 12}


async def test_api_kod_girisi(istemci):
    r = await istemci.post("/api/erisim", json={"kod": "AK1-YANLIS"})
    j = await r.json()
    assert r.status == 400 and j["hata"] == "gecersiz_kod"
    assert j["mesaj"] == "Bu kod geçerli değil. Harfleri kontrol edip tekrar deneyin."
    eski = erisim.kod_uret(istemci.anahtar, "gun", 1, date(2020, 1, 1))
    j = await (await istemci.post("/api/erisim", json={"kod": eski})).json()
    assert j["hata"] == "suresi_dolmus_kod"
    assert (await istemci.post("/api/erisim", json={"kod": 5})).status == 400
    assert (await istemci.post("/api/erisim", data="x")).status == 400
    k = erisim.kod_uret(istemci.anahtar, "sinirsiz")
    r = await istemci.post("/api/erisim", json={"kod": k.lower().replace("-", " ")})
    assert r.status == 200 and await r.json() == {"tamam": True, "tur": "sinirsiz"}
    j = await (await istemci.get("/api/erisim")).json()
    assert j["kod"] == "sinirsiz" and j["bitis"] is None


async def test_api_sinir_durumu_dene_ve_yayin(istemci):
    d = istemci.server.app[sunucu.DURUM]
    assert (await (await istemci.get("/api/durum")).json())["sinir"] is False
    d.erisim.say(True)
    istemci.saat.ilerle(30)
    for _ in range(30):
        d.erisim.say(True); istemci.saat.ilerle(30)
    assert d.erisim.sinir()
    assert (await (await istemci.get("/api/durum")).json())["sinir"] is True
    assert d.durum_olayi()["sinir"] is True
    r = await istemci.post("/api/dene", json={"metin": "Hi"})
    assert r.status == 402 and (await r.json())["hata"] == "ucretsiz_bitti"
    with pytest.raises(ErisimSiniri):
        await d.yonetici.cevir(["no way"])
    k = erisim.kod_uret(istemci.anahtar, "sinirsiz")
    assert (await istemci.post("/api/erisim", json={"kod": k})).status == 200
    assert "sinir" not in d.durum_olayi()
    assert (await istemci.post("/api/dene", json={"metin": "Hi"})).status == 200
    (c,) = await d.yonetici.cevir(["now fine"])
    assert c.metin


async def test_api_yalniz_yerel(istemci, monkeypatch):
    monkeypatch.setattr(sunucu, "uzak_adres", lambda r: "10.0.0.5")
    assert (await istemci.get("/api/erisim")).status == 403
    assert (await istemci.post("/api/erisim", json={"kod": "x"})).status == 403


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
    import subprocess, sys
    kod = "import sys, kopru.sunucu; print('cryptography' in sys.modules)"
    cikti = subprocess.run([sys.executable, "-c", kod], capture_output=True, text=True, check=True).stdout.strip()
    assert cikti == "False"
