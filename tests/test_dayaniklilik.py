# SPDX-License-Identifier: AGPL-3.0-only
"""Dayanıklılık sınamaları: bozuk dosyalar, eşzamanlılık, güvenlik, kapı çakışması, çeviri hizalaması.

Her sınama gerçek bir hatanın gerileme (regression) denetimidir; hata ve düzeltmesi sınamanın
docstring'inde yazılıdır.
"""
import asyncio
import json
import os
import socket
import sqlite3
from datetime import date, datetime

import aiohttp
import sys

import pytest
from aiohttp import web
from PIL import Image

from kopru import anahtarlar, ayarlar, calistir, erisim as erisim_mod, guncelleme, sunucu
from kopru.ayarlar import VARSAYILAN
from kopru.ceviri import _http
from kopru.ceviri.sahte import SahteMotor
from kopru.ceviri.temel import AgHatasi, AnahtarHatasi, Ceviri, MotorHatasi
from kopru.ceviri.yonetici import CeviriYoneticisi
from kopru.hafiza import Hafiza, OneriDeposu
from kopru.isleme import Isleme
from kopru.okuma import Satir
from kopru.onbellek import Onbellek
from kopru.yakalama import YakalamaHatasi
from kopru.yayin import Yayin
from tests.conftest import sahte_fabrika


# ---------------------------------------------------------------- ayarlar

def test_bozuk_ayar_dosyasi_varsayilanla_acilir_ve_kopyasi_saklanir(tmp_path):
    """Hata: bozuk ayarlar.json sessizce yok sayılıyor, sonraki kayıt kullanıcının dosyasını eziyordu."""
    (tmp_path / "ayarlar.json").write_text('{"motor": "claude", "kapi": ', encoding="utf-8")
    a = ayarlar.yukle()
    assert a["motor"] == VARSAYILAN["motor"] and a["kapi"] == 8642
    kopyalar = list(tmp_path.glob("ayarlar.json.bozuk-*"))
    assert len(kopyalar) == 1 and "claude" in kopyalar[0].read_text(encoding="utf-8")


def test_ayar_dosyasi_json_ama_sozluk_degil_ya_da_ikili_veri(tmp_path):
    (tmp_path / "ayarlar.json").write_text("[1,2,3]", encoding="utf-8")
    assert ayarlar.yukle()["motor"] == VARSAYILAN["motor"]
    (tmp_path / "ayarlar.json").write_bytes(b"\xff\xfe\x00bozuk")
    assert ayarlar.yukle()["kapi"] == 8642   # UnicodeDecodeError de çökertmez


def test_yanlis_turdeki_ayar_alanlari_varsayilana_doner(tmp_path):
    """Hata: "kapi": "abc" / "gorunum": "x" gibi değerler başlangıçta KeyError/TypeError ile çöküyordu."""
    (tmp_path / "ayarlar.json").write_text(json.dumps({
        "kapi": "abc", "gorunum": "x", "motor": 5, "bolgeler": "yok", "dublaj": {"motor": "yok", "hiz_siniri": 99},
        "arayuz_dili": "fr", "hafiza_izni": "evet", "modeller": {"claude": 3, "gemini": "m"},
        "bolge_altyazi": {"x": "a"}, "erisim": [], "yedek_motor": None, "kaynak": "ekran:2"}), encoding="utf-8")
    a = ayarlar.yukle()
    assert a["kapi"] == 8642 and a["gorunum"] == VARSAYILAN["gorunum"] and a["motor"] == "gemini"
    assert a["bolgeler"] == [] and a["dublaj"]["motor"] == "kapali" and a["dublaj"]["hiz_siniri"] == 1.25
    assert a["arayuz_dili"] == "tr" and a["hafiza_izni"] is None
    assert a["modeller"] == {"gemini": "m"} and a["bolge_altyazi"] == VARSAYILAN["bolge_altyazi"]
    assert a["erisim"] == {"vast_adresi": "", "reklam_izni": None}
    assert a["yedek_motor"] is None and a["kaynak"] == "ekran:2"     # geçerli seçimler korunur


def test_atomik_yazim_kilitliyse_yeniden_dener(tmp_path, monkeypatch):
    """Hata: Windows'ta antivirüs/eşitleme dosyayı tutarken os.replace PermissionError verip ayar kaydını kaybettiriyordu."""
    gercek = os.replace
    sayac = {"n": 0}

    def kilitli(a, b):
        sayac["n"] += 1
        if sayac["n"] <= 3:
            raise PermissionError(13, "kilitli")
        return gercek(a, b)
    monkeypatch.setattr(os, "replace", kilitli)
    ayarlar.kaydet({**VARSAYILAN, "motor": "claude"})
    assert sayac["n"] == 4
    assert json.loads((tmp_path / "ayarlar.json").read_text(encoding="utf-8"))["motor"] == "claude"
    assert not list(tmp_path.glob("*.tmp"))


def test_atomik_yazim_surekli_kilitliyse_gecici_dosya_kalmaz(tmp_path, monkeypatch):
    def hep(a, b):
        raise PermissionError(13, "kilitli")
    monkeypatch.setattr(os, "replace", hep)
    with pytest.raises(PermissionError):
        ayarlar.atomik_yaz(tmp_path / "x.json", "{}", deneme=3)
    assert not list(tmp_path.glob("*.tmp"))


# ---------------------------------------------------------------- erişim sayacı

def test_bozuk_erisim_dosyasi_cokmez(tmp_path):
    """Hata: bozuk erisim.json (eski düz dosyadaki kod) her izin denetiminde ValueError veriyordu."""
    (tmp_path / "erisim.json").write_text("{bozuk", encoding="utf-8")
    e = erisim_mod.Erisim(lambda: dict(VARSAYILAN), cihaz=lambda: "ABCDEFGHJK")
    assert e.kalan_sn() == 0 and not e.dublaj_izni() and list(tmp_path.glob("erisim.json.bozuk-*"))
    (tmp_path / "erisim.json").write_text(json.dumps({"kullanilan": {"x": "abc"}, "kod": 12}), encoding="utf-8")
    e = erisim_mod.Erisim(lambda: dict(VARSAYILAN), cihaz=lambda: "ABCDEFGHJK")
    assert e.etkin_kod() is None and e.durum()["dublaj"]["kalan_dakika"] == 0


def test_etkin_kod_imzayi_her_cagrida_yeniden_dogrulamaz(tmp_path, monkeypatch):
    """Hata: saf Python Ed25519 doğrulaması her izin denetiminde (saniyede birkaç kez) çalışıyordu."""
    e = erisim_mod.Erisim(lambda: dict(VARSAYILAN), cihaz=lambda: "ABCDEFGHJK")
    e._kod, e._kod_okundu = "AK1-ABC", True
    sayac = {"n": 0}

    def sahte(kod, bugun, acik=None, cihaz=None):
        sayac["n"] += 1
        return {"tur": "sinirsiz", "bitis": None, "tarih": "2026-01-01"}
    monkeypatch.setattr(erisim_mod, "kod_coz", sahte)
    for _ in range(10):
        assert e.dublaj_izni() and e.sinirsiz()
    assert sayac["n"] == 1


# ---------------------------------------------------------------- sqlite

def test_bozuk_onbellek_dosyasi_yeniden_kurulur(tmp_path):
    """Hata: bozuk onbellek.sqlite3 Onbellek() yapıcısında DatabaseError ile açılışı çökertiyordu."""
    yol = tmp_path / "onbellek.sqlite3"
    yol.write_bytes(b"bu bir sqlite dosyasi degil" * 100)
    o = Onbellek(yol)
    o.koy("Hello", "otomatik", "tr", "x", "Merhaba")
    assert o.al("hello", "otomatik", "tr", "x") == ("Merhaba", None)
    assert list(tmp_path.glob("onbellek.sqlite3.bozuk-*"))
    o.kapat()


def test_kapali_onbellek_hata_vermez():
    """Hata: ayar değişip önbellek kapatılırken uçuştaki çeviri ProgrammingError alıyordu."""
    o = Onbellek(":memory:")
    o.kapat()
    assert o.al("a", "x", "tr", "o") is None
    o.koy("a", "x", "tr", "o", "b")
    o.kapat()
    assert o.boyut() == 0


def test_bozuk_hafiza_dosyasi_ceviriyi_durdurmaz(tmp_path, monkeypatch):
    """Hata: izin açıkken bozuk hafiza.sqlite her kaydet() çağrısında istisna fırlatıp çeviriyi kırıyordu."""
    from kopru import oyunlar
    yol = oyunlar.oyun_dizini("varsayilan") / "hafiza.sqlite"
    yol.parent.mkdir(parents=True)
    yol.write_bytes(b"\x00bozuk" * 500)
    h = Hafiza("varsayilan", lambda: True)
    assert h.kaydet("Hello", "Merhaba", "motor", "gemini") is True
    assert h.bul("hello") == ("Merhaba", "motor")
    assert h.kalici_mi()   # yeni temiz dosya kuruldu
    h.kapat()
    assert list(yol.parent.glob("hafiza.sqlite.bozuk-*"))
    assert Hafiza("varsayilan").bul("Hello") == ("Merhaba", "motor")   # diskten geri okunur


def test_hafiza_disk_hatasinda_ram_ile_devam_eder(tmp_path, monkeypatch):
    h = Hafiza("varsayilan", lambda: True)
    assert h.kaydet("a b", "x", "motor")
    h._db.close()   # disk bağlantısı koptu
    assert h.kaydet("c d", "y", "motor")      # istisna yok
    assert h.bul("c d") == ("y", "motor") and h._db is None


@pytest.mark.parametrize("klasor", ["Ayşe Yılmaz", "oyun #1 %20", "a?b&c", "çğıöşü 100%"])
def test_hafiza_ozel_karakterli_klasorde_okunur(tmp_path, monkeypatch, klasor):
    if sys.platform == "win32" and "?" in klasor:
        pytest.skip("Windows klasör adlarında '?' kullanılamaz")
    """Hata: sqlite URI'si `file:{yol}` kaçışsızdı; '#', '%', '?' içeren kullanıcı klasörlerinde hafıza boş okunuyordu."""
    dizin = tmp_path / klasor
    monkeypatch.setenv("KOPRU_AYAR_DIZINI", str(dizin))
    h = Hafiza("varsayilan", lambda: True)
    h.kaydet("Hello there", "Merhaba", "kullanici")
    h.kapat()
    h2 = Hafiza("varsayilan")
    assert h2.bul("hello there") == ("Merhaba", "kullanici")


def test_oneri_deposu_disk_hatasi_ve_sinir(tmp_path, monkeypatch):
    from kopru import oyunlar
    o = OneriDeposu("varsayilan", lambda: True)

    def yaz(*a, **k):
        raise PermissionError("yazılamıyor")
    monkeypatch.setattr(oyunlar, "_yaz_json", yaz)
    assert o.ekle("Vice City", "Vice City")   # istisna yok
    for i in range(600):
        o.ekle(f"Kisi{i}", "x")
    assert len(o.liste()) <= 500


# ---------------------------------------------------------------- anahtar kasası önbelleği

def test_anahtar_onbellegi_kasayi_tekrar_tekrar_sormaz(ortam):
    """Hata: /api/ayarlar her çağrıda kasayı olay döngüsünde 4 kez okuyordu (kilitli Anahtar Zinciri her şeyi dondurur)."""
    anahtarlar._onbellegi_sifirla()
    sayac = {"n": 0}
    gercek = ortam.get_password

    def say(s, k):
        sayac["n"] += 1
        return gercek(s, k)
    ortam.get_password = say
    anahtarlar.yaz("claude", "sk-x")
    for _ in range(5):
        assert anahtarlar.kayitli_mi("claude") and anahtarlar.oku("claude") == "sk-x"
    assert sayac["n"] == 1
    anahtarlar.yaz("claude", "")          # silince önbellek eskimez
    assert not anahtarlar.kayitli_mi("claude")


# ---------------------------------------------------------------- çeviri yöneticisi

class Saymaca(SahteMotor):
    """Verilen listeyi eksik/fazla döndüren motor."""

    def __init__(self, hepsi=None, tek=None):
        super().__init__()
        self.hepsi = hepsi   # çoklu istekte döndürülecek (metinler) -> liste
        self.tek = tek

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False):
        self.cagrilar.append(list(metinler))
        if len(metinler) > 1 and self.hepsi is not None:
            return self.hepsi(metinler)
        if len(metinler) == 1 and self.tek is not None:
            return self.tek(metinler)
        return [Ceviri(f"[TR] {m}") for m in metinler]


async def test_motor_eksik_satir_dondururse_hizalama_kaymaz_ve_asilmaz():
    """Hata: motor 3 satıra 2 çeviri dönerse zip() kısaltıyor, üçüncünün Future'ı hiç çözülmeyip boru hattı sonsuza dek asılıyordu."""
    m = Saymaca(hepsi=lambda ms: [Ceviri("YANLIS-1"), Ceviri("YANLIS-2")])
    y = CeviriYoneticisi(m, None, None)
    sonuc = await asyncio.wait_for(y.cevir(["bir", "iki", "uc"]), 2)
    assert [c.metin for c in sonuc] == ["[TR] bir", "[TR] iki", "[TR] uc"]    # satır satır yeniden istendi
    assert m.cagrilar[0] == ["bir", "iki", "uc"] and m.cagrilar[1:] == [["bir"], ["iki"], ["uc"]]


async def test_tek_satira_bos_liste_donerse_hata_olur_asilmaz():
    m = Saymaca(tek=lambda ms: [])
    y = CeviriYoneticisi(m, None, None)
    with pytest.raises(MotorHatasi):
        await asyncio.wait_for(y.cevir(["bir"]), 2)
    assert y._ucusta == {}   # uçuştaki kayıt sızmadı


async def test_fazla_satir_donerse_de_hizalanmaz():
    m = Saymaca(hepsi=lambda ms: [Ceviri("a"), Ceviri("b"), Ceviri("c")])
    y = CeviriYoneticisi(m, None, None)
    sonuc = await y.cevir(["bir", "iki"])
    assert [c.metin for c in sonuc] == ["[TR] bir", "[TR] iki"]


async def test_bos_ceviri_bos_altyazi_olmaz():
    m = Saymaca(tek=lambda ms: [Ceviri("")])
    y = CeviriYoneticisi(m, None, None)
    (c,) = await y.cevir(["Run!"])
    assert c.metin == "Run!"


async def test_dedupe_sahibi_iptal_edilince_bekleyen_iptal_edilmez():
    """Hata: önden çeviri (sahibi) iptal edilince aynı metni bekleyen istek CancelledError alıyor ve
    Isleme.calis döngüsü sessizce sonlanıyordu."""
    ac = asyncio.Event()

    class Yavas(SahteMotor):
        async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False):
            self.cagrilar.append(list(metinler))
            if len(self.cagrilar) == 1:
                await ac.wait()
            return [Ceviri(f"[TR] {m}") for m in metinler]
    m = Yavas()
    y = CeviriYoneticisi(m, None, None)
    sahip = asyncio.create_task(y.cevir(["Hello"]))
    await asyncio.sleep(0.01)
    bekleyen = asyncio.create_task(y.cevir(["Hello"]))
    await asyncio.sleep(0.01)
    sahip.cancel()
    (c,) = await asyncio.wait_for(bekleyen, 2)
    assert c.metin == "[TR] Hello" and not bekleyen.cancelled()


async def test_birincil_bozuk_yanit_bir_kez_yeniden_denenir_sonra_yedege_gecer():
    class Bozuk(SahteMotor):
        kod, cevrimdisi = "gemini", False

        async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False):
            self.cagrilar.append(metinler)
            raise MotorHatasi("JSON bozuk")
    b, ye = Bozuk(), SahteMotor()
    y = CeviriYoneticisi(b, ye, None)
    (c,) = await y.cevir(["Hi"])
    assert c.metin == "[TR] Hi" and len(b.cagrilar) == 2 and not y.yedekte   # bozuk yanıt kalıcı yedeğe geçirmez


async def test_yedek_de_calismiyorsa_yedekte_takili_kalmaz():
    """Hata: yedek (kurulu olmayan yerel motor) MotorHatasi verirken `yedekte=True` kalıyor, 60 sn boyunca
    birincil hiç denenmiyordu."""
    durum = {"ag": True}

    class Birincil(SahteMotor):
        kod, cevrimdisi = "gemini", False

        async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False):
            if durum["ag"]:
                raise AgHatasi("kesik")
            return [Ceviri("[B] " + m) for m in metinler]

    class Yedek(SahteMotor):
        async def cevir(self, *a, **k):
            raise MotorHatasi("argos yok")
    y = CeviriYoneticisi(Birincil(), Yedek(), None)
    with pytest.raises(AgHatasi):
        await y.cevir(["Hi"])
    assert not y.yedekte
    durum["ag"] = False
    (c,) = await y.cevir(["Hi"])
    assert c.metin == "[B] Hi"


# ---------------------------------------------------------------- motorlar / HTTP

async def _sunucu(aiohttp_server, gorev):
    app = web.Application()
    app.router.add_post("/x", gorev)
    s = await aiohttp_server(app)
    return str(s.make_url("/x"))


async def test_http_json_olmayan_govde_motor_hatasi_olur(aiohttp_server):
    """Hata: JSON olmayan 200 yanıtı (captive portal HTML'i) ham ValueError olarak sızıp 500/sessiz çökme yapıyordu."""
    async def h(r):
        return web.Response(text="<html>giris yapin</html>", content_type="text/html")
    with pytest.raises(MotorHatasi):
        await _http.post_json(await _sunucu(aiohttp_server, h), {}, {})


async def test_http_gemini_gecersiz_anahtar_400_anahtar_hatasi(aiohttp_server):
    """Hata: Gemini geçersiz anahtara HTTP 400 API_KEY_INVALID döner; 'ağ hatası' sanılıp sessizce yedeğe geçiliyordu."""
    async def h(r):
        return web.json_response({"error": {"status": "INVALID_ARGUMENT", "message": "API key not valid."}}, status=400)
    with pytest.raises(AnahtarHatasi):
        await _http.post_json(await _sunucu(aiohttp_server, h), {}, {})


async def test_http_429_ve_5xx_ag_hatasi(aiohttp_server):
    async def h(r):
        return web.Response(status=429)
    with pytest.raises(AgHatasi):
        await _http.post_json(await _sunucu(aiohttp_server, h), {}, {})


async def test_http_zaman_asimi_ag_hatasi(aiohttp_server):
    async def h(r):
        await asyncio.sleep(2)
        return web.json_response({})
    with pytest.raises(AgHatasi):
        await _http.post_json(await _sunucu(aiohttp_server, h), {}, {}, zaman_asimi=0.2)


async def test_claude_diger_api_hatalari_ag_hatasina_cevrilir():
    """Hata: 400/404 (model yok) gibi anthropic.APIStatusError ham sızıp yedek motora geçişi engelliyordu."""
    import types

    import anthropic
    from kopru.ceviri.claude import ClaudeMotoru

    def hata(cls, kod):
        # httpx sürümünden bağımsız: SDK yalnız bu alanlara bakar
        yanit = types.SimpleNamespace(status_code=kod, headers={}, request=object(), text="", json=lambda: {})
        return cls("x", response=yanit, body=None)

    class Mesajlar:
        def __init__(self, e):
            self.e = e

        async def create(self, **k):
            raise self.e

    class Istemci:
        def __init__(self, e):
            self.messages = Mesajlar(e)
    with pytest.raises(AgHatasi):
        await ClaudeMotoru("k", istemci=Istemci(hata(anthropic.NotFoundError, 404))).cevir(["a"], "en", "tr", {})
    with pytest.raises(AgHatasi):
        await ClaudeMotoru("k", istemci=Istemci(hata(anthropic.BadRequestError, 400))).cevir(["a"], "en", "tr", {})
    with pytest.raises(AnahtarHatasi):
        await ClaudeMotoru("k", istemci=Istemci(hata(anthropic.PermissionDeniedError, 403))).cevir(["a"], "en", "tr", {})


# ---------------------------------------------------------------- işleme hattı

BOLGE = (0.1, 0.8, 0.5, 0.05)


class Kareler:
    def __init__(self, metin="Hello world", hata=None):
        self.metin, self.hata, self.n = metin, hata, 0

    def kare(self):
        self.n += 1
        if self.hata:
            raise self.hata
        return Image.new("RGB", (64, 36), (10, 10, 10))

    def oku(self, resim):
        return [Satir(self.metin, *BOLGE)] if self.metin else []


def _isleme(kareler, motor, ayar=None):
    saat = {"t": 0.0}
    y = Yayin()
    q = y.abone_ol()
    a = {**VARSAYILAN, "ekrani_cevir": False, **(ayar or {})}
    isl = Isleme(kareler.kare, kareler, CeviriYoneticisi(motor, None, None), y, lambda: a,
                 saat=lambda: saat["t"])
    return isl, q, saat


def _bosalt(q):
    o = []
    while not q.empty():
        o.append(q.get_nowait())
    return o


async def test_beklenmeyen_motor_hatasi_sonraki_karelerde_yeniden_denenir():
    """Hata: önden çevirinin beklenmeyen istisnası (ör. ValueError) görevde saklı kalıyor; sonraki her karede aynı
    başarısız görev beklenip altyazı bir daha asla çevrilmiyordu."""
    cagri = {"n": 0}

    class Garip(SahteMotor):
        async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False):
            cagri["n"] += 1
            if cagri["n"] <= 1:
                raise ValueError("beklenmeyen")
            return [Ceviri(f"[TR] {m}") for m in metinler]
    k = Kareler()
    isl, q, saat = _isleme(k, Garip())
    for _ in range(8):
        await isl.adim()
        await asyncio.sleep(0.07)
        saat["t"] += 0.25
    yazilar = [v for o, v in _bosalt(q) if o == "yazi"]
    assert yazilar and yazilar[0]["metin"] == "[TR] Hello world"


async def test_yakalama_hatasi_panele_bildirilir_ve_duzelince_temizlenir():
    """Hata: izin yokken (macOS) her saniye tam izleme günlüğü basılıyor, panele hiçbir şey bildirilmiyordu."""
    k = Kareler(hata=YakalamaHatasi("izin yok"))
    isl, q, _ = _isleme(k, SahteMotor())
    gorev = asyncio.create_task(isl.calis())
    await asyncio.sleep(0.15)
    olaylar = _bosalt(q)
    assert [v.get("hata") for o, v in olaylar if o == "durum"] == ["yakalama"]
    k.hata = None
    await asyncio.sleep(1.4)
    gorev.cancel()
    await asyncio.gather(gorev, return_exceptions=True)
    sonrasi = [v for o, v in _bosalt(q) if o == "durum"]
    assert sonrasi and "hata" not in sonrasi[-1]


async def test_durdurulunca_onden_ceviri_iptal_edilir():
    """Hata: Durdur'a basınca Isleme görevi iptal ediliyor ama başlamış önden çeviri API'yi çağırmaya devam ediyordu."""
    ac = asyncio.Event()

    class Bekler(SahteMotor):
        async def cevir(self, *a, **k):
            await ac.wait()
            return [Ceviri("x")]
    k = Kareler()
    isl, q, saat = _isleme(k, Bekler())
    gorev = asyncio.create_task(isl.calis())
    await asyncio.sleep(0.2)
    assert isl._spek is not None
    spek = isl._spek
    gorev.cancel()
    await asyncio.gather(gorev, return_exceptions=True)
    await asyncio.sleep(0)
    assert spek.cancelled() or spek.done()


async def test_cok_uzun_okuma_metni_altyazi_sayilmaz_ceviriye_gitmez():
    k = Kareler(metin="kelime " * 400)
    m = SahteMotor()
    isl, q, saat = _isleme(k, m)
    for _ in range(5):
        await isl.adim()
        saat["t"] += 0.25
    assert m.cagrilar == []


async def test_bos_ocr_hicbir_sey_yayinlamaz():
    k = Kareler(metin="")
    m = SahteMotor()
    isl, q, saat = _isleme(k, m)
    for _ in range(5):
        await isl.adim()
    assert _bosalt(q) == [] and m.cagrilar == []


async def test_hizli_baslat_durdur_baslat_tek_gorev(aiohttp_client, uygulama_ayari):
    """Başlat/Durdur/Başlat art arda: hep tek görev, eski önden çeviriler sızmaz."""
    uygulama_ayari["motor"] = "sahte"
    uygulama_ayari["yedek_motor"] = ""
    k = Kareler()
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika,
                                  kare_fabrika=lambda kaynak: k.kare, okuyucu_fabrika=lambda: k)
    c = await aiohttp_client(app)
    d = app[sunucu.DURUM]
    for _ in range(5):
        assert (await c.post("/api/baslat")).status == 200
        eski = d.gorev
        assert (await c.post("/api/durdur")).status == 200
        await asyncio.sleep(0.01)
        assert eski.done() and d.gorev is None
    assert (await c.post("/api/baslat")).status == 200
    assert (await c.post("/api/baslat")).status == 200      # ikinci Başlat zararsız
    assert (await (await c.get("/api/durum")).json())["calisiyor"] is True
    await c.post("/api/durdur")


async def test_isleme_gorevi_olurse_calisiyor_gorunmez(aiohttp_client, uygulama_ayari, monkeypatch):
    """Hata: boru hattı görevi ölürse panel 'çalışıyor' diye sessiz kalıyordu."""
    uygulama_ayari["motor"] = "sahte"
    k = Kareler()

    async def olu(self):
        raise RuntimeError("öldü")
    monkeypatch.setattr(Isleme, "calis", olu)
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika,
                                  kare_fabrika=lambda kaynak: k.kare, okuyucu_fabrika=lambda: k)
    c = await aiohttp_client(app)
    d = app[sunucu.DURUM]
    await c.post("/api/baslat")
    await asyncio.sleep(0.05)
    assert d.calisiyor() is False
    assert d.yayin.son_durum["calisiyor"] is False and d.yayin.son_durum["hata"] == "genel"


# ---------------------------------------------------------------- sunucu: güvenlik

@pytest.fixture
async def istemci(aiohttp_client, uygulama_ayari):
    uygulama_ayari["motor"] = "sahte"
    uygulama_ayari["yedek_motor"] = ""
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika)
    return await aiohttp_client(app)


def _yollar(app):
    """(yöntem, örnek yol) çiftleri: kayıtlı bütün yollar."""
    out = []
    for r in app.router.routes():
        if r.method == "HEAD":
            continue
        bilgi = r.resource.get_info()
        yol = bilgi.get("path") or bilgi.get("formatter")
        yol = yol.replace("{kod}", "varsayilan").replace("{kimlik}", "s1").replace("{yol", "{yol")
        import re
        yol = re.sub(r"\{yol[^}]*\}", "x.js", yol)
        yol = yol.replace("{", "").replace("}", "")
        out.append((r.method, yol))
    return out


async def test_her_yerel_yol_uzak_adresten_403(istemci, monkeypatch):
    """Her kayıtlı yol programatik taranır: /kopru/*, /tv, /obs, /statik/* dışındakilerin hepsi yalnız yerel olmalı.
    Yeni eklenen bir /api yolu katmanı unutursa bu sınama kırılır."""
    app = istemci.app
    ac = ("/kopru/", "/tv", "/obs", "/statik/")
    yerel_olmayan = [(m, y) for m, y in _yollar(app) if not y.startswith(ac)]
    assert len(yerel_olmayan) > 25
    # bilinen önek dışında yol eklenmişse bilinçli karar gerekir: sınama kırılsın
    for _, y in yerel_olmayan:
        assert y == "/" or y.startswith(("/api/", "/panel/")), f"beklenmeyen yol öneki: {y}"
    monkeypatch.setattr(sunucu, "uzak_adres", lambda req: "192.168.1.50")
    for m, y in yerel_olmayan:
        r = await istemci.request(m, y, json={})
        assert r.status == 403, (m, y, r.status)
        assert (await r.json())["hata"] == "yalniz_yerel"


async def test_yerel_olmayan_yollar_acik_listede_ve_cors_yalniz_kopruye(istemci):
    for yol in ("/api/durum", "/api/ayarlar", "/api/erisim"):
        r = await istemci.get(yol)
        assert "Access-Control-Allow-Origin" not in r.headers
    r = await istemci.get("/kopru/merhaba")
    assert r.headers["Access-Control-Allow-Origin"] == "*"
    r = await istemci.options("/kopru/akis")
    assert r.status == 204 and r.headers["Access-Control-Allow-Origin"] == "*"
    r = await istemci.options("/api/ayarlar")      # OPTIONS ön denetimi /api için CORS vermez
    assert "Access-Control-Allow-Origin" not in r.headers


async def test_dns_yeniden_baglama_ve_siteler_arasi_istek_engellenir(istemci):
    """Hata: yerel olmayan Host/Origin ile (DNS rebinding, başka sitedeki form) /api çağrılabiliyordu."""
    r = await istemci.post("/api/ayarlar", json={"motor": "sahte"}, headers={"Host": "evil.example.com"})
    assert r.status == 403
    r = await istemci.post("/api/ayarlar", data='{"motor":"claude"}', headers={"Origin": "https://evil.example.com",
                                                                               "Content-Type": "text/plain"})
    assert r.status == 403
    r = await istemci.get("/api/durum", headers={"Origin": "null"})
    assert r.status == 403
    for kok in ("http://localhost:8642", "http://127.0.0.1:8642", "http://[::1]:8642"):
        assert (await istemci.get("/api/durum", headers={"Origin": kok})).status == 200
    assert (await istemci.get("/api/durum", headers={"Host": "[::1]:8642"})).status == 200
    assert (await istemci.get("/api/durum", headers={"Host": "localhost"})).status == 200
    assert (await istemci.get("/api/durum")).status == 200
    # ayar değişmedi
    assert (await (await istemci.get("/api/ayarlar")).json())["motor"] == "sahte"


@pytest.mark.parametrize("yol", [
    "/panel/..%2f..%2f..%2fetc%2fpasswd", "/panel/%2e%2e/%2e%2e/pyproject.toml", "/statik/..%2f..%2fpanel%2findex.html",
    "/panel/%00", "/statik/%00.js", "/panel/..%5c..%5cpyproject.toml", "/panel/C:%5cWindows%5cwin.ini",
    "/panel/%2fetc%2fpasswd"])
async def test_yol_gecisi_engellenir(istemci, yol):
    """Hata: NUL baytlı yol Path.resolve() içinde ValueError verip 500 dönüyordu; geçiş denemeleri 404 olmalı."""
    r = await istemci.get(yol)
    assert r.status in (400, 404), (yol, r.status)
    govde = await r.read()
    assert b"root:" not in govde and b"[tool.setuptools" not in govde


async def test_ses_yolu_gecis_ve_bilinmeyen_kimlik_404(istemci):
    for k in ("s1", "..%2f..%2fx", "%00", "a" * 5000):
        r = await istemci.get(f"/kopru/ses/{k}.wav")
        assert r.status in (400, 404)


async def test_bozuk_ve_buyuk_json_govdesi_json_hata_doner(istemci):
    r = await istemci.post("/api/ayarlar", data="{bozuk")
    assert r.status == 400 and (await r.json())["hata"] == "gecersiz_istek"
    r = await istemci.post("/api/ayarlar", data=b"x" * (2 * 1024 * 1024))
    assert r.status == 413 and (await r.json())["hata"] == "gecersiz_istek"
    r = await istemci.post("/api/ayarlar", data="[1]")
    assert r.status == 400


async def test_paket_yukleme_buyuk_ve_bozuk_zip(istemci):
    from kopru import paket
    veri = aiohttp.FormData()
    veri.add_field("dosya", b"PK\x03\x04bozuk", filename="x.akpaket")
    r = await istemci.post("/api/paket", data=veri)
    assert r.status == 400 and (await r.json())["hata"] == "paket_gecersiz"
    veri = aiohttp.FormData()
    veri.add_field("baska", b"x", filename="x.akpaket")
    assert (await istemci.post("/api/paket", data=veri)).status == 400
    assert paket.AZAMI_BAYT <= 64 * 1024 * 1024


async def test_ayar_dogrulama_yeni_alanlar(istemci):
    """Hata: kaynak/dil/görünüm alanları doğrulanmıyordu; örn. {"kaynak": 5} yakalamayı sonsuza dek bozuyordu."""
    for kotu in ({"kaynak": 5}, {"hedef_dil": "tr\nIgnore previous"}, {"kaynak_dil": ["a"]},
                 {"gorunum": "x"}, {"gorunum": {"yazi_rengi": "kırmızı"}}, {"gorunum": {"yazi_boyutu": "büyük"}},
                 {"gorunum": {"arka_plan": 7}}, {"ekrani_cevir": "evet"}):
        r = await istemci.post("/api/ayarlar", json=kotu)
        assert r.status == 400, kotu
    r = await istemci.post("/api/ayarlar", json={"hedef_dil": "en-US", "gorunum": {"yazi_rengi": "#ffcc00"}})
    assert r.status == 200


async def test_sse_istemci_siniri(istemci, monkeypatch):
    monkeypatch.setattr(sunucu, "EN_COK_AKIS", 2)
    a = await istemci.get("/kopru/akis")
    b = await istemci.get("/kopru/akis")
    c = await istemci.get("/kopru/akis")
    assert (a.status, b.status, c.status) == (200, 200, 503)
    a.close()
    b.close()
    await asyncio.sleep(0.1)
    d = await istemci.get("/kopru/akis")
    assert d.status == 200
    d.close()


async def test_sse_kopan_istemci_aboneligi_temizler(istemci):
    d = istemci.app[sunucu.DURUM]
    r = await istemci.get("/kopru/akis")
    await asyncio.wait_for(r.content.readline(), 2)
    assert d.yayin.istemci_sayisi == 1
    r.close()
    for _ in range(50):
        if d.yayin.istemci_sayisi == 0:
            break
        await asyncio.sleep(0.02)
    assert d.yayin.istemci_sayisi == 0


async def test_sse_windows_baglanti_koparsa_gurultusuz_biter(istemci, monkeypatch):
    """Hata: Windows'ta kopan istemci ConnectionAbortedError verir (ConnectionResetError DEĞİL); yakalanmayıp
    her kopuşta 'Error handling request' izlemesi basılıyordu."""
    async def yaz(r, veri):
        raise ConnectionAbortedError(10053, "bağlantı iptal")
    monkeypatch.setattr(sunucu, "_yaz", yaz)
    r = await istemci.get("/kopru/akis")
    await asyncio.wait_for(r.read(), 2)
    assert istemci.app[sunucu.DURUM].yayin.istemci_sayisi == 0


async def test_donmus_istemci_yazma_zaman_asimiyla_dusurulur(istemci, monkeypatch):
    monkeypatch.setattr(sunucu, "YAZMA_ZAMAN_ASIMI_SN", 0.05)
    gercek = web.StreamResponse.write
    sayac = {"n": 0}

    async def yavas(self, veri):
        sayac["n"] += 1
        if sayac["n"] > 1:
            await asyncio.sleep(5)
        return await gercek(self, veri)
    monkeypatch.setattr(web.StreamResponse, "write", yavas)
    r = await istemci.get("/kopru/akis")
    await asyncio.wait_for(r.read(), 3)
    assert istemci.app[sunucu.DURUM].yayin.istemci_sayisi == 0


async def test_yayin_yavas_istemci_kuyrugu_sinirli():
    y = Yayin()
    q = y.abone_ol()
    for i in range(5000):
        y.yayinla("durum", {"i": i})
    assert q.qsize() == 200 and q.get_nowait()[1]["i"] == 4800   # eskiler atıldı, bellek büyümedi


# ---------------------------------------------------------------- arka plan görevleri

async def test_durum_ve_erisim_donguleri_hatada_olmez(aiohttp_client, uygulama_ayari, monkeypatch):
    """Hata: durum_olayi()/erisim_say() bir kez istisna atsa döngü sonsuza dek ölüyor, süre sayacı donuyordu."""
    monkeypatch.setattr(sunucu, "DURUM_SN", 0.02)
    monkeypatch.setattr(sunucu, "ERISIM_SN", 0.02)
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika)
    d = app[sunucu.DURUM]
    sayac = {"durum": 0, "say": 0}
    gercek_d, gercek_s = d.durum_olayi, d.erisim_say

    def durum_olayi():
        sayac["durum"] += 1
        if sayac["durum"] == 1:
            raise RuntimeError("bir kerelik")
        return gercek_d()

    def say():
        sayac["say"] += 1
        if sayac["say"] == 1:
            raise OSError("disk")
        return gercek_s()
    monkeypatch.setattr(d, "durum_olayi", durum_olayi)
    monkeypatch.setattr(d, "erisim_say", say)
    await aiohttp_client(app)
    await asyncio.sleep(0.25)
    assert sayac["durum"] >= 3 and sayac["say"] >= 3
    assert not app["durum_gorevi"].done() and not app["erisim_gorevi"].done()


async def test_kapanista_arka_plan_gorevleri_beklenir(aiohttp_client, uygulama_ayari):
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika)
    c = await aiohttp_client(app)
    g = [app["durum_gorevi"], app["erisim_gorevi"]]
    await c.close()
    assert all(t.done() for t in g)


async def test_kapanista_guncelleme_gorevleri_iptal_edilir():
    ac = asyncio.Event()

    class Takili:
        async def json_al(self, adres):
            await ac.wait()

    g = guncelleme.Guncelleme(lambda: {"guncelleme_denetle": True}, http=Takili(), platform="win32")
    g.arka_planda_denetle()
    await asyncio.sleep(0.01)
    assert not g.denetim_gorevi.done()
    await g.kapat()
    assert g.denetim_gorevi.done()


async def test_guncelleme_beklenmeyen_yanit_sekli_gorevi_sessizce_oldurmez_ve_sik_denemez():
    """Hata: GitHub'dan liste gibi beklenmeyen JSON gelince görev yakalanmamış istisnayla ölüyor; başarısız denetim
    her panel yenilemesinde yeniden deneniyordu (GitHub saatlik sınırı)."""
    cagri = {"n": 0}

    class Bozuk:
        async def json_al(self, adres):
            cagri["n"] += 1
            return [1, 2, 3]
    saat = {"t": 10_000_000.0}
    g = guncelleme.Guncelleme(lambda: {"guncelleme_denetle": True}, http=Bozuk(), platform="win32",
                              simdi=lambda: saat["t"])
    await g.denetle(elle=True)
    assert g.denetim_hatasi == "guncelleme_denetlenemedi"
    g.arka_planda_denetle()
    await asyncio.sleep(0.01)
    assert cagri["n"] == 1                 # bekleme süresi içinde otomatik yeniden deneme yok
    saat["t"] += guncelleme.HATA_BEKLEME_SN + 1
    g.arka_planda_denetle()
    await asyncio.sleep(0.01)
    assert cagri["n"] == 2


def test_guncelleme_durum_dosyasi_liste_ise_cokmez(tmp_path):
    (tmp_path / "guncelleme.json").write_text("[]", encoding="utf-8")
    g = guncelleme.Guncelleme(lambda: {})
    assert g.surum is None


async def test_guncelleme_ozet_hesabi_olay_dongusunu_tutmaz(tmp_path, monkeypatch):
    """Hata: onlarca MB'lık SHA256 doğrudan olay döngüsünde hesaplanıyordu (SSE/panel donuyordu)."""
    ana = asyncio.get_running_loop()
    kimlikler = []
    import threading
    gercek = guncelleme.dosya_ozeti

    def izle(yol):
        kimlikler.append(threading.current_thread() is threading.main_thread())
        return gercek(yol)
    monkeypatch.setattr(guncelleme, "dosya_ozeti", izle)

    class Http:
        async def indir(self, adres, hedef, ilerleme):
            hedef.write_bytes(b"x")

        async def metin_al(self, adres):
            return "0" * 64 + "  AltYaziKoprusu-Kur-0.9.0.exe\n"
    g = guncelleme.Guncelleme(lambda: {}, http=Http(), platform="win32", mevcut_surum="0.1.0",
                              baslatici=lambda k: None, kapatici=lambda: None, gecici_kok=tmp_path)
    g._surum_ata("0.9.0", "", 1, "https://github.com/x/AltYaziKoprusu-Kur-0.9.0.exe", "https://github.com/x/SHA256SUMS.txt",
                 "AltYaziKoprusu-Kur-0.9.0.exe")
    assert g.kur_baslat() is None
    await g.kur_gorevi
    assert kimlikler == [False] and g.hata_kodu == "guncelleme_dogrulanamadi"
    assert ana is asyncio.get_running_loop()


# ---------------------------------------------------------------- kapı çakışması / ikinci kopya

def _dinleyici():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 0))
    s.listen(1)
    return s


def test_kapi_bos_ise_kullanilir():
    s = _dinleyici()
    kapi = s.getsockname()[1]
    s.close()
    assert calistir.kapi_sec(kapi) == ("kullan", kapi)


def test_kapi_baska_programda_ise_sonraki_bos_kapi_secilir():
    """Hata: 8642 doluysa program OSError izlemesiyle çöküyordu."""
    s = _dinleyici()
    kapi = s.getsockname()[1]
    try:
        durum, yeni = calistir.kapi_sec(kapi)
        assert durum == "kullan" and yeni != kapi and kapi < yeni <= kapi + calistir.KAPI_DENEME
    finally:
        s.close()


async def test_kapi_bizim_programdaysa_zaten_acik(uygulama_ayari):
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 0)
    await site.start()
    kapi = runner.addresses[0][1]
    try:
        sonuc = await asyncio.to_thread(calistir.kapi_sec, kapi)
        assert sonuc == ("zaten_acik", kapi)
    finally:
        await runner.cleanup()


def test_hic_bos_kapi_yoksa_yok(monkeypatch):
    monkeypatch.setattr(calistir, "kapi_bos_mu", lambda k: False)
    monkeypatch.setattr(calistir, "bizim_mi", lambda k: False)
    assert calistir.kapi_sec(8642) == ("yok", None)


def test_ikinci_kopya_paneli_acar_yeni_sunucu_baslatmaz(monkeypatch, capsys):
    acilan = []
    monkeypatch.setattr(calistir.webbrowser, "open", lambda u: acilan.append(u))
    monkeypatch.setattr(calistir, "kapi_sec", lambda k: ("zaten_acik", k))
    monkeypatch.setattr(calistir.web, "run_app", lambda *a, **k: pytest.fail("ikinci sunucu başlatılmamalı"))
    monkeypatch.setattr("sys.argv", ["kopru"])
    calistir.main()
    assert acilan == ["http://127.0.0.1:8642/"]
    assert "zaten açık" in capsys.readouterr().out


def test_kapi_dolu_mesaji_ve_calisan_kapi(monkeypatch, capsys):
    gorulen = {}

    def calistir_app(app, **k):
        gorulen.update(k, kapi_durumu=app[sunucu.DURUM].calisan_kapi)
    monkeypatch.setattr(calistir, "kapi_sec", lambda k: ("kullan", k + 1))
    monkeypatch.setattr(calistir.web, "run_app", calistir_app)
    monkeypatch.setattr("sys.argv", ["kopru", "--tarayici-acma"])
    calistir.main()
    assert gorulen["port"] == 8643 and gorulen["kapi_durumu"] == 8643
    assert "8643" in capsys.readouterr().out


def test_run_app_kapi_kapilirsa_dostca_cikis(monkeypatch, capsys):
    def patla(*a, **k):
        raise OSError(98, "Address already in use")
    monkeypatch.setattr(calistir, "kapi_sec", lambda k: ("kullan", k))
    monkeypatch.setattr(calistir.web, "run_app", patla)
    monkeypatch.setattr("sys.argv", ["kopru", "--tarayici-acma"])
    with pytest.raises(SystemExit):
        calistir.main()
    assert "kapı" in capsys.readouterr().out.lower()


async def test_api_durum_gercek_kapiyi_bildirir(istemci):
    istemci.app[sunucu.DURUM].calisan_kapi = 8650
    assert (await (await istemci.get("/api/durum")).json())["kapi"] == 8650


def test_konsolsuz_calismada_gunluk_dosyaya_yazilir(tmp_path, monkeypatch):
    import logging
    import sys
    monkeypatch.setattr(sys, "stderr", None)
    eski = logging.getLogger().handlers[:]
    for h in eski:
        logging.getLogger().removeHandler(h)
    try:
        calistir.gunluk_kur()
        logging.getLogger("kopru.deneme").warning("Türkçe ğüşiöç")
        for h in logging.getLogger().handlers:
            h.flush()
        assert "Türkçe ğüşiöç" in (tmp_path / "kopru.log").read_text(encoding="utf-8")
    finally:
        for h in logging.getLogger().handlers[:]:
            logging.getLogger().removeHandler(h)
            h.close()
        for h in eski:
            logging.getLogger().addHandler(h)


# ---------------------------------------------------------------- dublaj yönetimi

async def test_dublaj_boru_hatti_beklenmeyen_hatada_sessiz_olmez():
    """Hata: _yurut görevi beklenmeyen istisnayla ölüyor, panelde hiçbir hata görünmüyordu."""
    from kopru import dublaj as dublaj_mod
    from kopru.dublaj import donanim
    from kopru.dublaj.yonetim import DublajYonetici

    class Motor:
        kod = "pocket"

        def hazir(self):
            return True

        async def hazirla(self, cb=None):
            return None
    ayar = {**VARSAYILAN, "dublaj": {**dublaj_mod.VARSAYILAN, "motor": "pocket"}}

    def stt(a):
        raise RuntimeError("model yüklenemedi")
    yon = DublajYonetici(lambda: ayar, Yayin(), lambda: None, motor_fabrika=lambda k, a: Motor(), stt_fabrika=stt,
                         donanim_fn=lambda: donanim.Donanim())
    yon.senkronla(True)
    await asyncio.sleep(0.05)
    assert yon.son_hata == "sunucu_hatasi" and yon._gorev.done()
    assert yon._gorev.exception() is None      # "Task exception was never retrieved" olmaz


async def test_dublaj_isleyici_ses_hatasini_kodlu_bildirir():
    from kopru.dublaj.isleyici import Isleyici
    from kopru.ses import SesHatasi

    class STT:
        async def yaz(self, pcm, sr):
            raise SesHatasi("faster-whisper yok", "dublaj_paket_yok")

    class P:
        pcm = __import__("numpy").zeros(16000 * 2, dtype="float32")
        sr, bas, bitis = 16000, 0.0, 2.0
    ayar = {**VARSAYILAN, "dublaj": {**VARSAYILAN["dublaj"], "motor": "pocket"}}
    isl = Isleyici(STT(), None, lambda: object(), lambda a: None, Yayin(), lambda: ayar)
    isl.kuyruga_at(P())
    gorev = asyncio.create_task(isl.calis())
    await asyncio.sleep(0.05)
    gorev.cancel()
    await asyncio.gather(gorev, return_exceptions=True)
    assert isl.son_hata == "dublaj_paket_yok"


# ---------------------------------------------------------------- başlangıçta bozuk veri

async def test_bozuk_dosyalarla_sunucu_acilir(aiohttp_client, tmp_path):
    """Hepsi bir arada: bozuk ayar, erişim, güncelleme, önbellek, hafıza, öneri dosyaları — uygulama yine açılır."""
    from kopru import oyunlar
    (tmp_path / "ayarlar.json").write_text("{{{", encoding="utf-8")
    (tmp_path / "erisim.json").write_text("\x00\x00", encoding="utf-8")
    (tmp_path / "guncelleme.json").write_text("[1]", encoding="utf-8")
    (tmp_path / "onbellek.sqlite3").write_bytes(b"x" * 4096)
    oyunlar.oyun_dizini("varsayilan").mkdir(parents=True)
    (oyunlar.oyun_dizini("varsayilan") / "hafiza.sqlite").write_bytes(b"y" * 4096)
    (oyunlar.oyun_dizini("varsayilan") / "oneriler.json").write_text("[[[", encoding="utf-8")
    (oyunlar.oyun_dizini("varsayilan") / "sozluk.json").write_text("{\"terimler\": 5}", encoding="utf-8")
    (oyunlar.oyun_dizini("varsayilan") / "oyun.json").write_text("[]", encoding="utf-8")
    a = ayarlar.yukle()
    a["hafiza_izni"] = True
    a["motor"], a["yedek_motor"] = "sahte", ""
    app = sunucu.uygulama_olustur(a, motor_fabrika=sahte_fabrika)
    c = await aiohttp_client(app)
    for yol in ("/api/durum", "/api/ayarlar", "/api/oyunlar", "/api/erisim", "/api/guncelleme", "/api/dublaj",
                "/api/oneriler", "/api/son-ceviriler", "/api/sozluk"):
        r = await c.get(yol)
        assert r.status == 200, (yol, r.status)
    r = await c.post("/api/dene", json={"metin": "Hello"})
    assert r.status == 200 and (await r.json())["ceviri"] == "[TR] Hello"


def test_saat_geri_giderse_say_sure_vermez(tmp_path):
    t = {"v": 100.0}
    e = erisim_mod.Erisim(lambda: dict(VARSAYILAN), saat=lambda: t["v"], cihaz=lambda: "ABCDEFGHJK")
    e._kalan_sn = 60.0
    e.say(True)
    t["v"] = 50.0    # saat geri gitti
    e.say(True)
    assert e.kalan_sn() == 60.0


def test_sqlite_dosya_kilitliyken_hafiza_okuma_cokmez(tmp_path):
    """Başka bir bağlantı yazarken salt-okunur açma 'locked' verse de Hafiza() yapıcısı çökmez."""
    from kopru import oyunlar
    yol = oyunlar.oyun_dizini("varsayilan") / "hafiza.sqlite"
    yol.parent.mkdir(parents=True)
    db = sqlite3.connect(str(yol))
    db.execute("CREATE TABLE h (asil TEXT, ceviri TEXT, kaynak TEXT, motor TEXT, sayac INTEGER, tarih TEXT, n TEXT)")
    db.execute("BEGIN EXCLUSIVE")
    try:
        Hafiza("varsayilan")
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------- geliştirici aracı (araclar/kod_uret.py)

def _arac():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "kod_uret_dayaniklilik", Path(__file__).resolve().parent.parent / "araclar" / "kod_uret.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_ozel_anahtar_bastan_yalniz_sahibine_acik_ve_uzerine_yazilmaz(tmp_path, monkeypatch):
    """Hata: anahtar önce herkese açık izinle yazılıp sonra chmod ediliyordu; var olan anahtar dosyası da korunmalı."""
    pytest.importorskip("cryptography")
    monkeypatch.setenv("KOPRU_KOD_ANAHTARI", str(tmp_path / "gizli" / "ozel.pem"))
    m = _arac()
    yol = m.anahtar_olustur()
    if os.name == "posix":
        assert (yol.stat().st_mode & 0o777) == 0o600
    ilk = yol.read_bytes()
    assert m.anahtar_olustur() == yol and yol.read_bytes() == ilk


def test_arac_sayfasi_yerel_olmayan_host_ve_koken_reddeder():
    pytest.importorskip("cryptography")
    m = _arac()

    class Sahte(m.Isleyici):
        def __init__(self, basliklar):
            self.headers = basliklar
    assert Sahte({"Host": "127.0.0.1:5000"})._yerel_mi()
    assert Sahte({"Host": "localhost:5000", "Origin": "http://localhost:5000"})._yerel_mi()
    assert not Sahte({"Host": "evil.com"})._yerel_mi()
    assert not Sahte({"Host": "127.0.0.1:5000", "Origin": "https://evil.com"})._yerel_mi()


async def test_sse_ham_soket_koparsa_en_gec_birkac_saniyede_abonelik_silinir(istemci):
    """Hata: istemci (curl, TV) sessizce kopunca abonelik, bir sonraki 15 sn'lik nabza kadar `tv_sayisi`nda
    görünmeye devam ediyordu; kopma artık ~1 sn'de fark edilir."""
    d = istemci.app[sunucu.DURUM]
    url = istemci.make_url("/kopru/akis")
    okuyucu, yazici = await asyncio.open_connection(url.host, url.port)
    yazici.write(b"GET /kopru/akis HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
    await yazici.drain()
    await asyncio.wait_for(okuyucu.readuntil(b"event: durum"), 2)
    assert d.yayin.istemci_sayisi == 1
    yazici.close()
    for _ in range(40):
        if d.yayin.istemci_sayisi == 0:
            break
        await asyncio.sleep(0.1)
    assert d.yayin.istemci_sayisi == 0
