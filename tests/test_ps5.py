# SPDX-License-Identifier: AGPL-3.0-only
"""PS5 gizli bağlantı (PROTOKOL §15): gerçek PS5 yok; sahte yardımcı (tests/sahte_uzaktan.py) ve sahte Sony ile."""
import base64
import json
import re
import socket
import sys
import time
from pathlib import Path

import pytest

from kopru import sunucu, uzaktan
from kopru.uzaktan import kayit, psn
from kopru.uzaktan.yardimci import CerceveCozucu, kare_coz
from tests.conftest import sahte_fabrika

KOK = Path(__file__).resolve().parents[1]
SAHTE = Path(__file__).with_name("sahte_uzaktan.py")


def sahte_satir(komut):
    return [sys.executable, str(SAHTE), komut]


@pytest.fixture
def sahte_ps5(monkeypatch, tmp_path):
    def kur(**ayar):
        ayar.setdefault("gunluk", str(tmp_path / "sahte.log"))
        monkeypatch.setenv("SAHTE_PS5", json.dumps(ayar))
        return tmp_path / "sahte.log"
    kur()
    return kur


def bekle(kosul, sure=10.0):
    son = time.monotonic() + sure
    while time.monotonic() < son:
        if kosul():
            return True
        time.sleep(0.05)
    return False


# ---------- PSN hesap kimliği ----------

def test_giris_adresi_resmi_remote_play_istemcisi():
    a = psn.giris_adresi()
    assert a.startswith("https://auth.api.sonyentertainmentnetwork.com/2.0/oauth/authorize?")
    assert "client_id=ba495a24-818c-472b-b12d-ff231c1b5745" in a and "prompt=always" in a
    assert "redirect_uri=https%3A%2F%2Fremoteplay.dl.playstation.net%2Fremoteplay%2Fredirect" in a


@pytest.mark.parametrize("metin,kod", [
    ("https://remoteplay.dl.playstation.net/remoteplay/redirect?code=AbC123&cid=x", "AbC123"),
    ("  remoteplay.dl.playstation.net/remoteplay/redirect?code=v3.XyZ  ", "v3.XyZ"),
    ("v3.ABCDEF", "v3.ABCDEF"),
])
def test_kod_cikar(metin, kod):
    assert psn.kod_cikar(metin) == kod


@pytest.mark.parametrize("metin,hata", [
    ("", "psn_kod_yok"),
    ("https://remoteplay.dl.playstation.net/remoteplay/redirect?foo=1", "psn_kod_yok"),
    ("https://remoteplay.dl.playstation.net/remoteplay/redirect?error=access_denied&error_description=Denied", "psn_reddetti"),
    ("https://x/?error=too_many_requests", "psn_cok_deneme"),
    ("şifrem bu değil mi", "psn_kod_yok"),
])
def test_kod_cikar_hatalar(metin, hata):
    with pytest.raises(psn.PsnHatasi) as e:
        psn.kod_cikar(metin)
    assert e.value.kod == hata


class SahteSony:
    def __init__(self, belirtec=(200, {"access_token": "tok/1"}), bilgi=(200, {"user_id": "1234567890123456789"})):
        self.belirtec, self.bilgi, self.istekler = belirtec, bilgi, []

    def __call__(self, yontem, adres, basliklar, govde):
        self.istekler.append((yontem, adres, basliklar, govde))
        durum, v = self.belirtec if yontem == "POST" else self.bilgi
        return durum, json.dumps(v).encode()


def test_hesap_kimligi_akisi():
    sony = SahteSony()
    b64 = psn.hesap_kimligi("KOD", sony)
    assert base64.b64decode(b64) == (1234567890123456789).to_bytes(8, "little")
    (y1, a1, b1, g1), (y2, a2, b2, g2) = sony.istekler
    assert y1 == "POST" and a1 == psn.BELIRTEC_ADRESI and b"grant_type=authorization_code" in g1 and b"code=KOD" in g1
    assert b1["Authorization"].startswith("Basic ") and b1["Content-Type"] == "application/x-www-form-urlencoded"
    assert y2 == "GET" and a2 == psn.BELIRTEC_ADRESI + "/tok%2F1" and g2 is None


@pytest.mark.parametrize("belirtec,hata", [
    ((400, {"error": "invalid_grant", "error_description": "Invalid authorization code"}), "psn_reddetti"),
    ((429, {"error": "x"}), "psn_cok_deneme"),
    ((500, {}), "psn_ag"),
    ((200, {"nope": 1}), "psn_yanit"),
])
def test_hesap_kimligi_hatalari(belirtec, hata):
    with pytest.raises(psn.PsnHatasi) as e:
        psn.hesap_kimligi("KOD", SahteSony(belirtec=belirtec))
    assert e.value.kod == hata


def test_kimlik_gecerli_ve_ozet():
    assert psn.kimlik_gecerli("AQIDBAUGBwg=")
    assert not psn.kimlik_gecerli("AQIDBAUGBw==") and not psn.kimlik_gecerli("hello") and not psn.kimlik_gecerli(None)
    assert psn.ozet("AQIDBAUGBwg=") == "AQID…" and psn.ozet(None) is None


# ---------- kayıt mantığı ----------

@pytest.mark.parametrize("metin,beklenen", [
    ("1234 5678", 12345678), ("1234-5678", 12345678), ("٠١٢٣٤٥٦٧", 1234567), (12345678, 12345678),
    ("1234567", None), ("12345678a", None), (None, None), (True, None),
])
def test_pin_coz(metin, beklenen):
    assert kayit.pin_coz(metin) == beklenen


def test_kayit_hata_kodlari():
    assert kayit.kayit_hata_kodu({"neden": 0x80108B09}) == "ps5_pin_yanlis"
    assert kayit.kayit_hata_kodu({"neden": 0x80108B02}) == "ps5_hesap_taninmadi"
    assert kayit.kayit_hata_kodu({"neden": 0x80108B10}) == "ps5_kullanimda"
    assert kayit.kayit_hata_kodu({"neden": 0, "satirlar": ["Regist timed out waiting for search response"]}) == "ps5_yanit_yok"
    assert kayit.kayit_hata_kodu({"neden": 0, "zaman_asimi": True}) == "ps5_yanit_yok"
    assert kayit.kayit_hata_kodu({"neden": 0}) == "ps5_kayit_hata"


def test_oturum_bitis_kodlari():
    assert kayit.oturum_bitis_kodu({"neden": "durdu"}) == (None, False)
    assert kayit.oturum_bitis_kodu({"neden": "reddedildi"}) == ("ps5_kayit_gecersiz", False)
    assert kayit.oturum_bitis_kodu({"neden": "kullanimda"}) == ("ps5_kullanimda", False)
    assert kayit.oturum_bitis_kodu({"neden": "erisilemedi"}) == ("ps5_erisilemedi", True)
    assert kayit.oturum_bitis_kodu({"neden": "ag"}) == ("ps5_baglanti_koptu", True)
    assert kayit.oturum_bitis_kodu({"neden": "diger", "neden_kodu": 0x80108B26}) == ("ps5_kayit_gecersiz", False)


def test_anahtar_bicimi_ve_uyandirma_kimligi():
    # Yardımcının verdiği: çözülmüş 16 bayt -> 32 hex. PS5'in ham "PS5-RegistKey" metni (16 hex) saklanamaz:
    # onu metin olarak saklamak oturumun 0x80108b26 ile reddedilmesine yol açar (GameTranslator'daki hata).
    assert kayit.anahtar_gecerli("31613262" + "0" * 24)
    assert not kayit.anahtar_gecerli("31613262abcdef01")
    assert not kayit.anahtar_gecerli("31613262" + "0" * 23 + "G")
    assert kayit.uyandirma_kimligi("31613262" + "0" * 24) == 0x1A2B


def test_kasa_saklama_ve_unut(ortam):
    kayit.hesap_yaz("AQIDBAUGBwg=")
    v = kayit.kayit_yaz("192.168.1.30", {"ad": "PS5-X", "kayit_anahtari": "31613262" + "0" * 24,
                                        "sabah": "00" * 16, "mac": "a1b2c3d4e5f6", "hedef": 1000100})
    assert kayit.hesap_oku() == "AQIDBAUGBwg=" and kayit.kayit_oku() == v
    # yalnız şifreli kasada; ayar dosyasında anahtar yok
    assert ("AltyaziKoprusu", "ps5_kayit") in ortam.veri
    kayit.unut()
    assert kayit.hesap_oku() is None and kayit.kayit_oku() is None


def test_bozuk_kasa_kaydi_kullanilmaz(ortam):
    ortam.veri[("AltyaziKoprusu", "ps5_kayit")] = json.dumps({"host": "1.2.3.4", "kayit_anahtari": "1a2b", "sabah": "x"})
    assert kayit.kayit_oku() is None


# ---------- kanal ----------

def test_cerceve_cozucu_parcali_ve_bozuk_veri():
    j = json.dumps({"olay": "bagli"}).encode()
    veri = b"cop" + b"AYJ\0" + len(j).to_bytes(4, "little") + j + b"AYS\0" + (4).to_bytes(4, "little") + b"\1\0\2\0"
    c = CerceveCozucu()
    out = []
    for i in range(0, len(veri), 3):
        out += c.besle(veri[i:i + 3])
    assert out == [("J", j), ("S", b"\1\0\2\0")]


def test_kare_coz():
    k = kare_coz((2).to_bytes(2, "little") + (1).to_bytes(2, "little") + bytes([1, 2, 3, 255, 4, 5, 6, 255]))
    assert (k.genislik, k.yukseklik) == (2, 1) and k.resim().getpixel((0, 0)) == (3, 2, 1)
    assert kare_coz(b"\0\0\0\0") is None and kare_coz(b"\2\0\1\0abc") is None


# ---------- yönetici, sahte yardımcıyla ----------

def _kayitli_yonetici(**kw):
    kayit.hesap_yaz("AQIDBAUGBwg=")
    ayar = {"ps5": {"host": "192.168.1.30", "cozunurluk": 720, "kodek": "h264"}}
    return uzaktan.Ps5Yonetici(lambda: ayar, satir=sahte_satir, **kw)


def test_kaydet_gizli_degerler_stdin_ile(sahte_ps5):
    gunluk = sahte_ps5(kayit="tamam")
    y = _kayitli_yonetici()
    v = y.kaydet("192.168.1.30", "1234 5678")
    assert v["ad"] == "PS5-SAHTE" and kayit.kayit_oku()["kayit_anahtari"] == "31613262" + "0" * 24
    satir = gunluk.read_text().splitlines()[0]
    assert satir.startswith("kaydet ") and '"pin": 12345678' in satir and '"hesap": "AQIDBAUGBwg="' in satir


@pytest.mark.parametrize("tur,kod", [("pin", "ps5_pin_yanlis"), ("hesap", "ps5_hesap_taninmadi"), ("sessiz", "ps5_yanit_yok")])
def test_kaydet_hatalari(sahte_ps5, tur, kod):
    sahte_ps5(kayit=tur)
    y = _kayitli_yonetici()
    with pytest.raises(uzaktan.YardimciHatasi) as e:
        y.kaydet("192.168.1.30", "12345678")
    assert e.value.kod == kod and kayit.kayit_oku() is None


def test_kaydet_hesapsiz_ve_kotu_pin(sahte_ps5):
    y = uzaktan.Ps5Yonetici(lambda: {}, satir=sahte_satir)
    with pytest.raises(uzaktan.YardimciHatasi) as e:
        y.kaydet("192.168.1.30", "123")
    assert e.value.kod == "ps5_pin_gecersiz"
    with pytest.raises(uzaktan.YardimciHatasi) as e:
        y.kaydet("192.168.1.30", "12345678")
    assert e.value.kod == "psn_hesap_yok"


def test_akis_kare_ve_ses(sahte_ps5):
    gunluk = sahte_ps5(kayit="tamam")
    y = _kayitli_yonetici()
    y.kaydet("192.168.1.30", "12345678")
    kanal = y.ses_kanali()
    try:
        resim = y.kare(zaman_asimi=10)
        assert resim.size == (64, 36) and resim.getpixel((0, 0)) == (200, 20, 10)
        assert y.durum()["durum"] == "bagli" and y.durum()["kare_boyutu"] == [64, 36]
        # ses: yalnız doğru anahtarı yollayan yerel dinleyiciye
        s = socket.create_connection(("127.0.0.1", kanal["kapi"]), timeout=5)
        s.sendall(kanal["anahtar"].encode() + b"\n")
        veri = b""
        while len(veri) < 640:
            veri += s.recv(4096)
        assert veri[:2] == (1000).to_bytes(2, "little", signed=True)
        s.close()
        yanlis = socket.create_connection(("127.0.0.1", kanal["kapi"]), timeout=5)
        yanlis.sendall(b"yanlis\n")
        yanlis.settimeout(5)
        assert yanlis.recv(10) == b""      # kapatıldı
        yanlis.close()
        assert len(y.onizleme_jpeg()) > 100
        # akış isteği: gizli değerler stdin'den, görüntü ayarları ayarlardan
        akis = [json.loads(s.split(" ", 1)[1]) for s in gunluk.read_text().splitlines() if s.startswith("akis ")][0]
        assert akis["kayit_anahtari"] == "31613262" + "0" * 24 and akis["ses"] is True and akis["cozunurluk"] == 720
    finally:
        y.kapat()
    assert y.durum()["durum"] == "kapali"


def test_uyku_modundaysa_uyandirir(sahte_ps5, tmp_path, monkeypatch):
    monkeypatch.setattr(uzaktan, "UYANMA_SN", 20.0)
    gunluk = sahte_ps5(kayit="tamam", durum="uyku", isaret=str(tmp_path / "uyandi"))
    y = _kayitli_yonetici()
    y.kaydet("192.168.1.30", "12345678")
    try:
        assert y.kare(zaman_asimi=20).size == (64, 36)
    finally:
        y.kapat()
    komutlar = [s.split(" ", 1)[0] for s in gunluk.read_text().splitlines()]
    assert "uyandir" in komutlar and komutlar.index("uyandir") < komutlar.index("akis")


def test_koparsa_yeniden_baglanir(sahte_ps5, tmp_path):
    sahte_ps5(kayit="tamam", akis="kop", isaret2=str(tmp_path / "koptu"))
    y = _kayitli_yonetici(beklemeler=(0.2,))
    y.kaydet("192.168.1.30", "12345678")
    yayin = []
    y.yayin_cb = yayin.append
    try:
        y.kare(zaman_asimi=10)                  # ilk oturum bu kareden sonra kopar
        assert bekle(lambda: any(g["durum"] == "bekliyor" for g in yayin))
        assert bekle(lambda: y.durum()["durum"] == "bagli" and y.durum()["deneme"] == 0)
        assert y.kare(zaman_asimi=10).size == (64, 36)
    finally:
        y.kapat()
    bekliyor = next(g for g in yayin if g["durum"] == "bekliyor")
    assert bekliyor["hata"] == "ps5_baglanti_koptu" and bekliyor["deneme"] == 1


def test_kayit_reddedilirse_yeniden_denemez(sahte_ps5):
    gunluk = sahte_ps5(kayit="tamam", akis="red")
    y = _kayitli_yonetici(beklemeler=(0.1,))
    y.kaydet("192.168.1.30", "12345678")
    with pytest.raises(uzaktan.YardimciHatasi) as e:
        y.kare(zaman_asimi=10)
    assert e.value.kod == "ps5_kayit_gecersiz"
    assert bekle(lambda: not y.calisiyor())
    assert y.durum()["durum"] == "hata" and "2. adımı" in y.durum()["mesaj"]
    assert sum(1 for s in gunluk.read_text().splitlines() if s.startswith("akis ")) == 1
    y.kapat()


def test_kayitsiz_baglanti_hatasi(sahte_ps5):
    y = uzaktan.Ps5Yonetici(lambda: {}, satir=sahte_satir)
    with pytest.raises(uzaktan.YardimciHatasi) as e:
        y.kare(zaman_asimi=5)
    assert e.value.kod == "ps5_kayit_yok"


def test_yakalama_ps5_kaynagi(sahte_ps5):
    from kopru import yakalama
    sahte_ps5(kayit="tamam")
    y = _kayitli_yonetici()
    y.kaydet("192.168.1.30", "12345678")
    uzaktan.kaydet_etkin(y)
    try:
        assert yakalama.kare_al("ps5:gizli").size == (64, 36)
        oge = yakalama.ps5_kaynak_ogesi("ps5")
        assert oge == {"kod": "ps5:gizli", "ad": "PS5 (gizli bağlantı)", "tur": "ps5", "onerilen": True, "kayitli": True}
    finally:
        y.kapat()
        uzaktan.kaydet_etkin(None)


def test_yakalama_ps5_yardimci_yoksa_turkce_hata():
    from kopru import yakalama
    y = uzaktan.Ps5Yonetici(lambda: {}, platform="win32")
    uzaktan.kaydet_etkin(y)
    try:
        with pytest.raises(yakalama.YakalamaHatasi, match="gizli bağlantı parçası"):
            yakalama.kare_al("ps5:gizli")
        assert yakalama.ps5_kaynak_ogesi("ps5") is None
    finally:
        uzaktan.kaydet_etkin(None)


def test_isci_ps5_ses_kaynagi(sahte_ps5):
    import numpy as np
    from kopru.dublaj.isci.canli import BLOK, CanliYakalama
    sahte_ps5(kayit="tamam")
    y = _kayitli_yonetici()
    y.kaydet("192.168.1.30", "12345678")
    try:
        y.baglan()
        assert bekle(lambda: y.durum()["durum"] == "bagli")
        c = CanliYakalama(lambda o: None, ps5_ses=y.ses_kanali())
        k = c._kaynak_ac()
        try:
            assert c.kaynak_turu == "ps5"
            assert bekle(lambda: y._rol.dinleyici_sayisi() == 1)
            blok = k.oku()
            assert blok.dtype == np.float32 and len(blok) <= BLOK and abs(float(blok[0]) - 1000 / 32768) < 1e-6
        finally:
            k.kapat()
    finally:
        y.kapat()


# ---------- değişmez kural: hiçbir girdi gönderilmez (§15.2) ----------

def test_yardimci_kol_girdisi_gondermez():
    kaynak = (KOK / "uzaktan" / "ayk_uzaktan.c").read_text(encoding="utf-8")
    kod = re.sub(r"/\*.*?\*/", "", kaynak, flags=re.S)       # yorumlar atılır
    kod = re.sub(r"//[^\n]*", "", kod)
    assert "chiaki_session_set_controller_state" not in kod
    for yasak in ("chiaki_session_connect_microphone", "chiaki_session_toggle_microphone", "chiaki_session_keyboard_",
                  "chiaki_session_go_home", "chiaki_session_goto_bed"):
        assert yasak not in kod
    assert "bilgi.enable_keyboard = false;" in kod and "bilgi.enable_dualsense = false;" in kod


# ---------- panel API'si ----------

@pytest.fixture
async def ps5_istemci(aiohttp_client, uygulama_ayari, sahte_ps5):
    uygulama_ayari["motor"] = "sahte"
    uygulama_ayari["yedek_motor"] = ""
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika, ps5_satir=sahte_satir,
                                  psn_istek=SahteSony())
    c = await aiohttp_client(app)
    yield c
    app[sunucu.DURUM].ps5.kapat()
    uzaktan.kaydet_etkin(None)


async def test_api_destek_yok(aiohttp_client, uygulama_ayari):
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika)
    c = await aiohttp_client(app)
    j = await (await c.get("/api/ps5")).json()
    assert j["destek"] is False and j["neden"] in ("yalniz_windows", "yardimci_yok")
    assert j["hesap"] == {"var": False, "ozet": None} and j["konsol"] is None
    r = await c.post("/api/ps5/baglan")
    assert r.status == 409 and (await r.json())["hata"] in ("ps5_yalniz_windows", "ps5_yardimci_yok")
    uzaktan.kaydet_etkin(None)


async def test_api_tum_sihirbaz(ps5_istemci):
    c = ps5_istemci
    j = await (await c.get("/api/ps5")).json()
    assert j["destek"] is True and j["hesap"]["var"] is False
    adres = (await (await c.post("/api/ps5/psn/adres")).json())["adres"]
    assert adres.startswith(psn.YETKI_ADRESI)
    # 1) PSN: yapıştırılan yönlendirme adresi
    r = await c.post("/api/ps5/psn/kod", json={"adres": "https://remoteplay.dl.playstation.net/remoteplay/redirect?code=K"})
    assert r.status == 200 and (await r.json())["ozet"].endswith("…")
    r = await c.post("/api/ps5/psn/kod", json={"adres": "boş"})
    assert r.status == 400 and (await r.json())["hata"] == "psn_kod_yok"
    assert (await c.post("/api/ps5/psn/elle", json={"kimlik": "kısa"})).status == 400
    # 2) bul + kaydet
    konsollar = (await (await c.post("/api/ps5/bul", json={})).json())["konsollar"]
    assert konsollar[0]["host"] == "192.168.1.30" and konsollar[0]["kayitli"] is False
    assert (await c.post("/api/ps5/bul", json={"host": "kotu;host"})).status == 400
    r = await c.post("/api/ps5/kaydet", json={"host": "192.168.1.30", "pin": "12"})
    assert r.status == 400 and (await r.json())["hata"] == "ps5_pin_gecersiz"
    r = await c.post("/api/ps5/kaydet", json={"host": "192.168.1.30", "pin": "1234-5678"})
    assert r.status == 200 and (await r.json())["ad"] == "PS5-SAHTE"
    j = await (await c.get("/api/ps5")).json()
    assert j["konsol"] == {"host": "192.168.1.30", "ad": "PS5-SAHTE", "kayitli": True}
    ayar = await (await c.get("/api/ayarlar")).json()
    assert ayar["ps5"]["host"] == "192.168.1.30" and "kayit_anahtari" not in json.dumps(ayar)
    # 3) bağlantı testi: önizleme + kol sorusu
    assert (await c.post("/api/ps5/baglan")).status == 200
    r = None
    for _ in range(100):
        r = await c.get("/api/ps5/onizleme")
        if r.status == 200:
            break
        await __import__("asyncio").sleep(0.1)
    assert r.status == 200 and r.content_type == "image/jpeg"
    assert (await c.post("/api/ps5/kol", json={"calisiyor": "evet"})).status == 400
    assert (await c.post("/api/ps5/kol", json={"calisiyor": True})).status == 200
    assert (await (await c.get("/api/ps5")).json())["kol_tv"] is True
    assert (await c.post("/api/ps5/giris-pin", json={"pin": "12a4"})).status == 400
    # kaynak seçimi ve görüntü ayarı
    assert (await c.post("/api/ayarlar", json={"kaynak": "ps5:gizli", "ps5": {"cozunurluk": 1080}})).status == 200
    assert (await c.post("/api/ayarlar", json={"ps5": {"host": "1.2.3.4"}})).status == 400
    assert (await c.post("/api/ps5/kes")).status == 200
    # unut: kasa ve ayar temizlenir, kaynak ekrana döner
    assert (await c.delete("/api/ps5")).status == 200
    j = await (await c.get("/api/ps5")).json()
    assert j["hesap"]["var"] is False and j["konsol"] is None
    ayar = await (await c.get("/api/ayarlar")).json()
    assert ayar["kaynak"] == "ekran:1" and ayar["ps5"]["host"] == ""
