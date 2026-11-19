# SPDX-License-Identifier: AGPL-3.0-only
"""Adım adım kurulum uç noktaları: okuma denemesi, çevrimdışı motor, /api/dene hata kodları, bölge sınırı."""
import asyncio

import pytest

from kopru import sunucu
from kopru.ceviri import yerel
from kopru.ceviri.temel import AgHatasi, AnahtarHatasi, Ceviri, MotorHatasi
from kopru.okuma import OkumaHatasi, Satir
from kopru.yakalama import YakalamaHatasi
from tests.conftest import sahte_fabrika


class SahteOkuyucu:
    ad = "Sahte OCR"

    def oku(self, resim):
        return [Satir("Press X", 0.1, 0.8, 0.2, 0.04), Satir("  ", 0, 0, 0.1, 0.1)]


def kur(aiohttp_client, ayar, **kw):
    ayar["motor"], ayar["yedek_motor"] = "sahte", ""
    kw.setdefault("katman_destek", lambda: False)
    return aiohttp_client(sunucu.uygulama_olustur(ayar, motor_fabrika=kw.pop("motor_fabrika", sahte_fabrika), **kw))


async def test_okuma_dene_satirlar(aiohttp_client, uygulama_ayari):
    c = await kur(aiohttp_client, uygulama_ayari, okuyucu_fabrika=SahteOkuyucu, kare_fabrika=lambda k: (lambda: object()))
    r = await c.get("/api/okuma-dene")
    j = await r.json()
    assert r.status == 200 and j["satirlar"] == [{"metin": "Press X", "x": 0.1, "y": 0.8, "g": 0.2, "y2": 0.04}]
    assert j["okuyucu"] == "Sahte OCR" and isinstance(j["sure_ms"], int)


@pytest.mark.parametrize("hata,kod", [(YakalamaHatasi("ekran yok"), "yakalama_yok"),
                                      (OkumaHatasi("ocr yok"), "okuma_yok")])
async def test_okuma_dene_dostca_hata(aiohttp_client, uygulama_ayari, hata, kod):
    def kare(k):
        def al():
            raise hata
        return al
    c = await kur(aiohttp_client, uygulama_ayari, okuyucu_fabrika=SahteOkuyucu, kare_fabrika=kare)
    if kod == "okuma_yok":
        def fab():
            raise hata
        c = await kur(aiohttp_client, uygulama_ayari, okuyucu_fabrika=fab, kare_fabrika=lambda k: (lambda: object()))
    r = await c.get("/api/okuma-dene")
    j = await r.json()
    assert r.status == 400 and j["hata"] == kod and j["mesaj"] and j["ayrinti"]


async def test_okuma_dene_kaynak_yok(aiohttp_client, uygulama_ayari):
    uygulama_ayari["kaynak"] = ""
    c = await kur(aiohttp_client, uygulama_ayari)
    assert (await (await c.get("/api/okuma-dene")).json())["hata"] == "kaynak_yok"


# ---------- çevrimdışı motor ----------

async def test_yerel_durum_ve_hazirla(aiohttp_client, uygulama_ayari, monkeypatch):
    cagrilar, dur = [], asyncio.Event()

    def durum(k, h):
        return {"hazir": False, "boyut_mb": 95, "indirme": {"durum": "yok", "yuzde": 0, "mesaj": None}}

    async def hazirla(k, h, cb):
        cagrilar.append((k, h))
        cb(40)
        await dur.wait()
    monkeypatch.setattr(yerel, "durum", durum, raising=False)
    monkeypatch.setattr(yerel, "hazirla", hazirla, raising=False)
    c = await kur(aiohttp_client, uygulama_ayari)
    j = await (await c.get("/api/motor/yerel")).json()
    assert j["hazir"] is False and j["boyut_mb"] == 95 and j["indirme"]["durum"] == "yok"
    assert "100 MB" in j["mesaj"]
    j = await (await c.post("/api/motor/yerel/hazirla")).json()
    assert j["indirme"]["durum"] == "iniyor" and j["indirme"]["yuzde"] == 40
    await c.post("/api/motor/yerel/hazirla")        # ikinci basış: yeni indirme başlatmaz
    assert cagrilar == [("en", "tr")]               # otomatik -> en
    dur.set()
    await asyncio.sleep(0.05)
    j = await (await c.get("/api/motor/yerel")).json()
    assert j["indirme"]["durum"] == "bitti" and j["indirme"]["yuzde"] == 100


@pytest.mark.parametrize("hata,kod", [(MotorHatasi("x"), "yerel_indirme_hatasi"),
                                      (ImportError("ctranslate2"), "yerel_bilesen_yok")])
async def test_yerel_hazirla_hata(aiohttp_client, uygulama_ayari, monkeypatch, hata, kod):
    async def hazirla(k, h, cb):
        raise hata
    monkeypatch.setattr(yerel, "durum", lambda k, h: {"hazir": False, "boyut_mb": 95}, raising=False)
    monkeypatch.setattr(yerel, "hazirla", hazirla, raising=False)
    c = await kur(aiohttp_client, uygulama_ayari)
    await c.post("/api/motor/yerel/hazirla")
    await asyncio.sleep(0.05)
    j = await (await c.get("/api/motor/yerel")).json()
    assert j["indirme"]["durum"] == "hata" and j["indirme"]["mesaj"] and j["indirme"]["ayrinti"]


# ---------- /api/dene belirli hata kodları ----------

def hatali(e):
    class M:
        kod, ad = "x", "x"

        async def cevir(self, *a, **k):
            raise e
    return lambda kod, ayar: M()


def kodlu(kod):
    e = MotorHatasi("tr metin")
    e.kod = kod
    return e


@pytest.mark.parametrize("hata,durum,kod", [
    (kodlu("yerel_dil_dosyasi_yok"), 502, "yerel_dil_dosyasi_yok"),
    (kodlu("yerel_bilesen_yok"), 502, "yerel_bilesen_yok"),
    (kodlu("yerel_ceviri_hatasi"), 502, "yerel_ceviri_hatasi"),
    (MotorHatasi("yerel_indirme_hatasi"), 502, "yerel_indirme_hatasi"),
    (MotorHatasi("bilinmeyen"), 502, "motor_hatasi"),
    (AgHatasi("zaman asimi"), 502, "ag_hatasi"),
    (AnahtarHatasi("401"), 400, "anahtar_yok"),
    (RuntimeError("tuhaf"), 502, "motor_hatasi"),
])
async def test_dene_ozel_hata_kodlari(aiohttp_client, uygulama_ayari, hata, durum, kod):
    c = await kur(aiohttp_client, uygulama_ayari, motor_fabrika=hatali(hata))
    r = await c.post("/api/dene", json={"metin": "Hello", "motor": "sahte"})
    j = await r.json()
    assert r.status == durum and j["hata"] == kod and j["mesaj"] and j["ayrinti"]
    if kod.startswith("yerel_"):
        assert "Çeviri motoru çalışmadı" not in j["mesaj"]


async def test_bolgeler_en_cok_6(aiohttp_client, uygulama_ayari):
    c = await kur(aiohttp_client, uygulama_ayari)
    b = {"x": 0.1, "y": 0.7, "g": 0.2, "y2": 0.1, "tur": "diger", "ad": "A"}
    assert (await c.post("/api/ayarlar", json={"bolgeler": [b] * 6})).status == 200
    assert (await c.post("/api/ayarlar", json={"bolgeler": [b] * 7})).status == 400
    assert len((await (await c.get("/api/ayarlar")).json())["bolgeler"]) == 6


def test_windows_ocr_dil_secimi():
    """Türkçe Windows'ta İngilizce OCR paketi yoksa kurulu dille (tr-TR) okunur."""
    from kopru.okuma import windows as w
    assert w.dil_sec(["tr-TR"]) == "tr-TR"
    assert w.dil_sec(["tr-TR", "en-US"]) == "en-US"
    assert w.dil_sec(["en-GB"]) == "en-GB"
    assert w.dil_sec(["ja-JP"]) == "ja-JP"
    assert w.dil_sec([]) is None
    assert w.ingilizce_var(["tr-TR"]) is False and w.ingilizce_var(["en-US"]) is True
