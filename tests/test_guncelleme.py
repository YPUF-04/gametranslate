# SPDX-License-Identifier: AGPL-3.0-only
"""Güncelleme: HTTP sahte; gerçek ağa çıkılmaz."""
import asyncio
import hashlib

import pytest

from kopru import guncelleme as g
from kopru import sunucu
from tests.conftest import sahte_fabrika

KURUCU = "AltYaziKoprusu-Kur-0.3.0.exe"
ICERIK = b"MZ-sahte-kurucu" * 1000
GH = "https://github.com/YPUF-04/gametranslate/releases/download/v0.3.0/"


def surum_json(kurucu_adresi=GH + KURUCU, toplam_adresi=GH + "SHA256SUMS.txt", etiket="v0.3.0"):
    return {"tag_name": etiket, "body": "Yeni: tek tuşla güncelleme", "assets": [
        {"name": KURUCU, "browser_download_url": kurucu_adresi, "size": 48 * 1024 * 1024},
        {"name": "SHA256SUMS.txt", "browser_download_url": toplam_adresi, "size": 200}]}


class SahteHttp:
    def __init__(self, sj=None, icerik=ICERIK, toplam=None, durak=None):
        self.sj = sj or surum_json()
        self.icerik = icerik
        self.toplam = toplam if toplam is not None else f"{hashlib.sha256(icerik).hexdigest()}  {KURUCU}\n"
        self.istekler = []
        self.durak = durak          # indirme ortasında bekletmek için asyncio.Event

    async def json_al(self, adres):
        self.istekler.append(adres)
        return self.sj

    async def metin_al(self, adres, azami=65536):
        self.istekler.append(adres)
        return self.toplam

    async def indir(self, adres, hedef, ilerleme):
        self.istekler.append(adres)
        ilerleme(len(self.icerik) // 2, len(self.icerik))
        if self.durak:
            await self.durak.wait()
        hedef.write_bytes(self.icerik)
        ilerleme(len(self.icerik), len(self.icerik))


class Calistirici:
    def __init__(self):
        self.komutlar, self.kapandi = [], False

    def baslat(self, komut):
        self.komutlar.append(komut)

    def kapat(self):
        self.kapandi = True


def yap(tmp_path, http, ayar=None, platform="win32", surum="0.1.0"):
    c = Calistirici()
    (tmp_path / "gecici").mkdir(exist_ok=True)
    ayar = {"guncelleme_denetle": True, "arayuz_dili": "tr"} if ayar is None else ayar
    gu = g.Guncelleme(lambda: ayar, http=http, mevcut_surum=surum, platform=platform,
                      baslatici=c.baslat, kapatici=c.kapat, gecici_kok=tmp_path / "gecici")
    return gu, c


@pytest.mark.parametrize("aday,mevcut,beklenen", [
    ("v0.3.0", "0.1.0", True), ("0.1.1", "0.1.0", True), ("1.0.0", "0.9.9", True),
    ("0.10.0", "0.9.0", True), ("0.1.0", "0.1.0", False), ("0.0.9", "0.1.0", False),
    ("0.2.0-beta.1", "0.2.0", False), ("0.2.0", "0.2.0-beta.1", True),
    ("bozuk", "0.1.0", False), ("", "0.1.0", False), ("1.2", "0.1.0", False)])
def test_surum_karsilastirma(aday, mevcut, beklenen):
    assert g.daha_yeni_mi(aday, mevcut) is beklenen


@pytest.mark.parametrize("adres,izinli", [
    ("https://github.com/a/b/releases/download/v1/x.exe", True),
    ("https://objects.githubusercontent.com/x", True),
    ("https://release-assets.githubusercontent.com/x", True),
    ("https://api.github.com/repos/a/b/releases/latest", True),
    ("http://github.com/a/b", False), ("https://evil.example/x.exe", False),
    ("https://github.com.evil.example/x", False), ("https://evilgithub.com/x", False),
    ("https://user@github.com/x", False), ("https://github.com:8443/x", False),
    ("ftp://github.com/x", False), ("", False)])
def test_adres_izni(adres, izinli):
    assert g.adres_izinli_mi(adres) is izinli


def test_toplam_dosyasi_ayrisir():
    h = "a" * 64
    assert g.toplamlari_oku(f"{h}  a.exe\n{h.upper()} *b.zip\nçöp satır\n") == {"a.exe": h, "b.zip": h}


async def test_yeni_surum_bulunur(tmp_path):
    http = SahteHttp()
    gu, _ = yap(tmp_path, http)
    await gu.denetle()
    d = gu.durum()
    assert d["var"] is True and d["surum"] == "0.3.0" and d["boyut_mb"] == 48
    assert "güncelleme" in d["notlar"] and d["ilerleme"] == 0
    assert http.istekler == [g.SON_SURUM_ADRESI]


async def test_guncel_surumde_var_false(tmp_path):
    gu, _ = yap(tmp_path, SahteHttp(), surum="0.3.0")
    await gu.denetle()
    assert gu.durum()["var"] is False and gu.durum()["neden"] == "guncel"


async def test_kapali_ayar_istek_yapmaz(tmp_path):
    http = SahteHttp()
    gu, _ = yap(tmp_path, http, ayar={"guncelleme_denetle": False})
    await gu.denetle()
    gu.arka_planda_denetle()
    assert gu.denetim_gorevi is None and http.istekler == []
    assert gu.durum()["var"] is False and gu.durum()["neden"] == "kapali"
    await gu.denetle(elle=True)          # kullanıcı kendisi bastıysa bakılır
    assert http.istekler == [g.SON_SURUM_ADRESI]


async def test_acilista_bir_kez_sonra_aralikla(tmp_path):
    http, zaman = SahteHttp(), [1_000_000.0]
    c = Calistirici()
    gu = g.Guncelleme(lambda: {"guncelleme_denetle": True}, http=http, mevcut_surum="0.1.0", platform="win32",
                      baslatici=c.baslat, kapatici=c.kapat, simdi=lambda: zaman[0], gecici_kok=tmp_path)
    await gu.denetle()
    await gu.denetle()
    assert len(http.istekler) == 1
    zaman[0] += g.GUN_SN + 1
    await gu.denetle()
    assert len(http.istekler) == 2
    # program yeniden açılınca hemen bir kez daha bakar (kullanıcı isteği: yeni sürüm beklemeden görünsün)
    gu2 = g.Guncelleme(lambda: {"guncelleme_denetle": True}, http=http, mevcut_surum="0.1.0", platform="win32",
                       simdi=lambda: zaman[0] + 60)
    assert gu2.durum()["surum"] == "0.3.0"      # önceki sonuç hatırlanır
    await gu2.denetle()
    assert len(http.istekler) == 3
    await gu2.denetle()
    assert len(http.istekler) == 3              # aynı açılışta aralık dolmadan tekrar sorulmaz


def test_surum_bolumu_yalniz_o_surumun_notlarini_alir():
    metin = ("# Sürüm notları\n\n## 0.1.3 — Yenilikler\n- A geldi\n- B düzeldi\n\n"
             "## 0.1.2 — Eski\n- C\n\n## 0.1.0 — İlk\n- D\n")
    assert g.surum_bolumu(metin, "v0.1.3") == "## 0.1.3 — Yenilikler\n- A geldi\n- B düzeldi"
    assert g.surum_bolumu(metin, "0.1.2") == "## 0.1.2 — Eski\n- C"
    assert g.surum_bolumu(metin, "0.1.30").startswith("## 0.1.3 —")   # yoksa en üstteki bölüm
    assert g.surum_bolumu("düz metin", "0.1.3") == "düz metin"


async def test_windows_disinda_desteklenmiyor(tmp_path):
    http = SahteHttp()
    gu, _ = yap(tmp_path, http, platform="linux")
    await gu.denetle(elle=True)
    d = gu.durum()
    assert http.istekler == [] and d["var"] is False and d["neden"] == "desteklenmiyor"
    assert d["baglanti"].startswith("https://github.com/YPUF-04/gametranslate/releases")
    assert gu.kur_baslat() == "guncelleme_desteklenmiyor"


async def test_ag_hatasi_sessizce_bildirilir(tmp_path):
    class Bozuk(SahteHttp):
        async def json_al(self, adres):
            raise asyncio.TimeoutError()
    gu, _ = yap(tmp_path, Bozuk())
    await gu.denetle(elle=True)
    d = gu.durum()
    assert d["var"] is False and "denetlenemedi" in d["denetim_hatasi"]


async def test_kurulum_dogrulanir_ve_baslatilir(tmp_path):
    http = SahteHttp()
    gu, c = yap(tmp_path, http)
    await gu.denetle()
    assert gu.kur_baslat() is None
    await gu.kur_gorevi
    assert gu.durum()["asama"] == "baslatiliyor" and gu.durum()["ilerleme"] == 100
    (komut,) = c.komutlar
    assert komut[0].endswith(KURUCU)
    assert komut[1:] == ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/GUNCELLEME=1"]
    assert c.kapandi is True
    assert http.istekler[1:] == [GH + KURUCU, GH + "SHA256SUMS.txt"]


async def test_ilerleme_gorunur(tmp_path):
    durak = asyncio.Event()
    gu, c = yap(tmp_path, SahteHttp(durak=durak))
    await gu.denetle()
    gu.kur_baslat()
    await asyncio.sleep(0.05)
    d = gu.durum()
    assert d["asama"] == "indiriliyor" and 40 <= d["ilerleme"] <= 60
    durak.set()
    await gu.kur_gorevi
    assert c.kapandi


async def test_sag_toplam_uyusmazsa_reddedilir(tmp_path):
    kotu = f"{'0' * 64}  {KURUCU}\n"
    gu, c = yap(tmp_path, SahteHttp(toplam=kotu))
    await gu.denetle()
    gu.kur_baslat()
    await gu.kur_gorevi
    d = gu.durum()
    assert d["asama"] == "hata" and d["hata"] == "guncelleme_dogrulanamadi"
    assert "doğrulanamadı" in d["mesaj"] and "kurulmadı" in d["mesaj"]
    assert c.komutlar == [] and not c.kapandi
    assert list((tmp_path / "gecici").iterdir()) == []         # indirilen dosya silindi


async def test_toplam_dosyasinda_kurucu_yoksa_reddedilir(tmp_path):
    gu, c = yap(tmp_path, SahteHttp(toplam=f"{'a' * 64}  baska.zip\n"))
    await gu.denetle()
    gu.kur_baslat()
    await gu.kur_gorevi
    assert gu.durum()["hata"] == "guncelleme_dogrulanamadi" and c.komutlar == []


async def test_github_disi_adres_reddedilir(tmp_path):
    http = SahteHttp(sj=surum_json(kurucu_adresi="https://evil.example/" + KURUCU))
    gu, c = yap(tmp_path, http)
    await gu.denetle()
    assert gu.durum()["var"] is False               # güvenilmeyen varlık yok sayıldı
    assert gu.kur_baslat() == "guncelleme_yok"
    assert http.istekler == [g.SON_SURUM_ADRESI] and c.komutlar == []
    # kaydedilmiş durum elle bozulsa bile kurma anında yeniden denetlenir
    gu.surum, gu.kurucu_adresi, gu.toplam_adresi = "0.3.0", "http://github.com/x/" + KURUCU, GH + "SHA256SUMS.txt"
    assert gu.kur_baslat() == "guncelleme_adres"
    assert http.istekler == [g.SON_SURUM_ADRESI]


async def test_gercek_http_yonlendirme_izni(monkeypatch):
    """GitHubHttp her yönlendirme adımını denetler: github -> evil reddedilir."""
    class Y:
        status = 302
        headers = {"Location": "https://evil.example/x.exe"}
        url = g.URL(GH + KURUCU)

        def release(self):
            pass

    class O:
        async def get(self, adres, **kw):
            assert g.adres_izinli_mi(adres)
            return Y()
    with pytest.raises(g.GuncellemeHatasi) as e:
        await g.GitHubHttp()._ac(O(), GH + KURUCU)
    assert e.value.kod == "guncelleme_adres"


async def test_uc_nokta_json_ve_kur(aiohttp_client, uygulama_ayari, tmp_path):
    uygulama_ayari["motor"] = "sahte"
    uygulama_ayari["yedek_motor"] = ""
    gu, c = yap(tmp_path, SahteHttp(), ayar=uygulama_ayari)
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika, guncelleme=gu)
    ist = await aiohttp_client(app)
    d = await (await ist.get("/api/guncelleme")).json()
    assert d["var"] is False                       # henüz denetim bitmedi / başlıyor
    await gu.denetim_gorevi
    d = await (await ist.get("/api/guncelleme")).json()
    assert d["var"] is True and d["surum"] == "0.3.0" and d["boyut_mb"] == 48 and d["ilerleme"] == 0
    r = await ist.post("/api/guncelleme/kur")
    assert r.status == 200
    await gu.kur_gorevi
    d = await (await ist.get("/api/guncelleme")).json()
    assert d["ilerleme"] == 100 and c.kapandi
    r = await ist.post("/api/guncelleme/denetle")
    assert r.status == 200


async def test_uc_nokta_ayar_kapaliyken_istek_yok(aiohttp_client, uygulama_ayari, tmp_path):
    uygulama_ayari["motor"] = "sahte"
    uygulama_ayari["yedek_motor"] = ""
    http = SahteHttp()
    kutu = {}
    gu, _ = yap(tmp_path, http)
    gu.ayar_al = lambda: kutu["app"][sunucu.DURUM].ayar     # sunucudaki gerçek bağ gibi
    app = kutu["app"] = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika, guncelleme=gu)
    ist = await aiohttp_client(app)
    assert (await ist.post("/api/ayarlar", json={"guncelleme_denetle": False})).status == 200
    for _ in range(3):
        assert (await ist.get("/api/guncelleme")).status == 200
    assert http.istekler == []
    assert (await ist.post("/api/ayarlar", json={"guncelleme_denetle": "evet"})).status == 400
    r = await ist.post("/api/guncelleme/kur")
    assert r.status == 400 and (await r.json())["hata"] == "guncelleme_yok"
