# SPDX-License-Identifier: AGPL-3.0-only
"""Genel kısayol tuşları (PROTOKOL §13.1): ayrıştırma, çakışma, eylem dağıtımı, yeniden kayıt (sahte kayıtçı)."""
import asyncio

import pytest

from kopru import kisayol, sunucu
from tests.conftest import sahte_fabrika
from kopru.kisayol import MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, Kisayollar, ayristir


@pytest.mark.parametrize("metin,beklenen", [
    ("ctrl+shift+t", (MOD_CONTROL | MOD_SHIFT, ord("T"))),
    ("Ctrl+Shift+T", (MOD_CONTROL | MOD_SHIFT, ord("T"))),
    ("alt+f9", (MOD_ALT, 0x78)),
    ("ctrl+alt+1", (MOD_CONTROL | MOD_ALT, ord("1"))),
    ("win+shift+z", (MOD_WIN | MOD_SHIFT, ord("Z"))),
    ("f12", (0, 0x7B)),
    ("f1", (0, 0x70)),
])
def test_ayristir_gecerli(metin, beklenen):
    assert ayristir(metin) == beklenen


@pytest.mark.parametrize("metin", ["", "t", "ctrl", "ctrl+", "ctrl+shift", "ctrl+f13", "ctrl+f0", "ctrl+ğ",
                                   "ctrl+ctrl+t", "meta+t", "ctrl+tab", "ctrl+shift+ab", "+t", None, 5, "ctrl++t"])
def test_ayristir_gecersiz(metin):
    assert ayristir(metin) is None


def test_kisayollar_gecerli_dogrulamasi():
    assert kisayol.kisayollar_gecerli({"baslat_durdur": "ctrl+shift+t", "gizle_goster": ""})
    assert kisayol.kisayollar_gecerli({})
    assert not kisayol.kisayollar_gecerli({"bilinmeyen": "ctrl+t"})
    assert not kisayol.kisayollar_gecerli({"baslat_durdur": "t"})
    assert not kisayol.kisayollar_gecerli({"baslat_durdur": 5})
    assert not kisayol.kisayollar_gecerli("ctrl+t")


class SahteDinleyici:
    """Windows'a dokunmadan RegisterHotKey/mesaj döngüsü yerine geçer."""
    ornekler: list = []

    def __init__(self, dolu=()):
        self.dolu = set(dolu)      # (mod, vk) başka programda kullanımda
        self.kayitlar = {}
        self.gelince = None
        self.durdu = False
        SahteDinleyici.ornekler.append(self)

    def baslat(self, kayitlar, gelince):
        self.kayitlar, self.gelince = dict(kayitlar), gelince
        return {k: ("kullanimda" if v in self.dolu else None) for k, v in kayitlar.items()}

    def dur(self):
        self.durdu = True


@pytest.fixture(autouse=True)
def _temiz():
    SahteDinleyici.ornekler = []
    yield


VARSAYILAN = {"baslat_durdur": "ctrl+shift+t", "gizle_goster": "ctrl+shift+h", "yeniden_oku": "ctrl+shift+r"}


def kur(dolu=(), cagrilar=None, destek=True):
    cagrilar = [] if cagrilar is None else cagrilar
    eylemler = {e: (lambda e=e: cagrilar.append(e)) for e in kisayol.EYLEMLER}
    return Kisayollar(eylemler, lambda: SahteDinleyici(dolu), destek), cagrilar


async def test_kayit_ve_eylem_dagitimi_dongu_uzerinden():
    k, cagrilar = kur()
    k.baslat(asyncio.get_running_loop(), VARSAYILAN)
    d = SahteDinleyici.ornekler[-1]
    assert k.kayitli == {e: True for e in kisayol.EYLEMLER} and k.hata == {}
    assert sorted(d.kayitlar.values()) == sorted(ayristir(t) for t in VARSAYILAN.values())
    kimlik = next(i for i, v in d.kayitlar.items() if v == ayristir("ctrl+shift+h"))
    # dinleyici iş parçacığı yerine başka bir iş parçacığından tetikle
    await asyncio.to_thread(d.gelince, kimlik)
    await asyncio.sleep(0.05)
    assert cagrilar == ["gizle_goster"]


async def test_eylem_eszamansizsa_gorev_olarak_calisir():
    sonuc = []

    async def e():
        await asyncio.sleep(0)
        sonuc.append(1)
    k = Kisayollar({"baslat_durdur": e}, lambda: SahteDinleyici(), True)
    k.baslat(asyncio.get_running_loop(), {"baslat_durdur": "ctrl+shift+t"})
    d = SahteDinleyici.ornekler[-1]
    await asyncio.to_thread(d.gelince, next(iter(d.kayitlar)))
    await asyncio.sleep(0.05)
    assert sonuc == [1]


async def test_baska_programda_kullanilan_tus_raporlanir():
    k, _ = kur(dolu=[ayristir("ctrl+shift+h")])
    k.baslat(asyncio.get_running_loop(), VARSAYILAN)
    assert k.kayitli == {"baslat_durdur": True, "gizle_goster": False, "yeniden_oku": True}
    assert k.hata == {"gizle_goster": "kullanimda"}
    assert k.bilgi() == {"destek": True, "kayitli": k.kayitli, "hata": {"gizle_goster": "kullanimda"}}


async def test_ayni_tus_iki_eyleme_verilirse_ikincisi_cakisma():
    k, _ = kur()
    k.baslat(asyncio.get_running_loop(), {**VARSAYILAN, "yeniden_oku": "Shift+Ctrl+T"})
    assert k.kayitli["baslat_durdur"] is True and k.kayitli["yeniden_oku"] is False
    assert k.hata == {"yeniden_oku": "cakisma"}


async def test_bos_tus_kapali_sayilir():
    k, _ = kur()
    k.baslat(asyncio.get_running_loop(), {"baslat_durdur": "", "gizle_goster": "alt+f9"})
    assert k.kayitli == {"gizle_goster": True} and k.hata == {}


async def test_ayar_degisince_eskiler_birakilir_yenileri_kaydedilir():
    k, _ = kur()
    k.baslat(asyncio.get_running_loop(), VARSAYILAN)
    ilk = SahteDinleyici.ornekler[-1]
    k.uygula({**VARSAYILAN, "baslat_durdur": "ctrl+alt+1"})
    ikinci = SahteDinleyici.ornekler[-1]
    assert ilk.durdu and ikinci is not ilk
    assert ayristir("ctrl+alt+1") in ikinci.kayitlar.values()
    assert ayristir("ctrl+shift+t") not in ikinci.kayitlar.values()
    k.uygula({})                       # hepsi kapalı: dinleyici hiç başlamaz
    assert ikinci.durdu and k.kayitli == {}
    k.durdur()


def test_destek_yoksa_hicbir_sey_kaydedilmez():
    k, _ = kur(destek=False)
    k.uygula(VARSAYILAN)
    assert SahteDinleyici.ornekler == [] and k.bilgi() == {"destek": False, "kayitli": {}, "hata": {}}


def test_windows_disinda_destek_yanlis(monkeypatch):
    import sys
    monkeypatch.setattr(sys, "platform", "linux")
    assert Kisayollar({}).destek is False
    monkeypatch.setattr(sys, "platform", "win32")
    assert Kisayollar({}).destek is True


# ---------- sunucu: API, ayar doğrulama, eylemler ----------

@pytest.fixture
async def istemci(aiohttp_client, uygulama_ayari, katman_surec_yok):
    uygulama_ayari["motor"], uygulama_ayari["yedek_motor"] = "sahte", ""
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika, katman_destek=lambda: True,
                                  okuyucu_fabrika=lambda: None, kare_fabrika=lambda k: (lambda: None))
    return await aiohttp_client(app)


async def test_api_kisayollar_destek_yok(aiohttp_client, uygulama_ayari):
    istemci = await aiohttp_client(sunucu.uygulama_olustur(uygulama_ayari, kisayol_destek=False))
    r = await istemci.get("/api/kisayollar")
    j = await r.json()
    assert r.status == 200 and j["destek"] is False and j["kayitli"] == {} and j["hata"] == {}


async def test_ayar_dogrulama_kisayollar(istemci):
    for kotu in ({"kisayollar": {"baslat_durdur": "t"}}, {"kisayollar": {"x": "ctrl+t"}},
                 {"kisayollar": {"baslat_durdur": "ctrl+ğ"}}, {"kisayollar": "ctrl+t"}):
        assert (await istemci.post("/api/ayarlar", json=kotu)).status == 400
    r = await istemci.post("/api/ayarlar", json={"kisayollar": {"gizle_goster": "alt+f9"}})
    assert r.status == 200
    a = await (await istemci.get("/api/ayarlar")).json()
    assert a["kisayollar"] == {**VARSAYILAN, "gizle_goster": "alt+f9"}


async def test_sunucu_sahte_dinleyiciyle_kaydeder_ve_hata_metni_doner(aiohttp_client, uygulama_ayari):
    uyg = sunucu.uygulama_olustur(
        uygulama_ayari, kisayol_destek=True,
        kisayol_dinleyici=lambda: SahteDinleyici(dolu=[ayristir("ctrl+shift+r")]))
    c = await aiohttp_client(uyg)
    j = await (await c.get("/api/kisayollar")).json()
    assert j["destek"] is True and j["kayitli"]["baslat_durdur"] is True and j["kayitli"]["yeniden_oku"] is False
    assert "başka bir programda" in j["hata"]["yeniden_oku"]
    # ayar değişince yeniden kaydolur
    n = len(SahteDinleyici.ornekler)
    await c.post("/api/ayarlar", json={"kisayollar": {"yeniden_oku": "ctrl+alt+r"}})
    assert len(SahteDinleyici.ornekler) == n + 1
    j = await (await c.get("/api/kisayollar")).json()
    assert j["kayitli"]["yeniden_oku"] is True and j["hata"] == {}


async def test_gizle_goster_olay_ve_bildirim(aiohttp_client, uygulama_ayari):
    uyg = sunucu.uygulama_olustur(uygulama_ayari)
    d = uyg[sunucu.DURUM]
    q = d.yayin.abone_ol()
    d.kisayol.calistir("gizle_goster")
    d.kisayol.calistir("gizle_goster")
    olaylar = []
    while not q.empty():
        olaylar.append(q.get_nowait())
    adlar = [o for o, _ in olaylar]
    assert adlar == ["katman-gizle", "durum", "katman-goster", "durum"]
    assert olaylar[1][1]["bildirim"] == "Yazılar gizlendi" and olaylar[3][1]["bildirim"] == "Yazılar gösteriliyor"


async def test_baslat_durdur_kisayolu(aiohttp_client, uygulama_ayari):
    ayar = {**uygulama_ayari, "kurulum_tamam": True}
    uyg = sunucu.uygulama_olustur(ayar, okuyucu_fabrika=lambda: object(),
                                  kare_fabrika=lambda kaynak: (lambda: None))
    d = uyg[sunucu.DURUM]
    c = await aiohttp_client(uyg)
    q = d.yayin.abone_ol()

    def bildirimler():
        out = []
        while not q.empty():
            o, v = q.get_nowait()
            if o == "durum" and "bildirim" in v:
                out.append(v["bildirim"])
        return out
    await d.kisayol.calistir("baslat_durdur")
    assert d.calisiyor() and bildirimler() == ["Çeviri başladı"]
    await d.kisayol.calistir("baslat_durdur")
    assert not d.calisiyor() and bildirimler() == ["Çeviri durdu"]


async def test_baslat_durdur_kurulum_bitmediyse_baslatmaz(aiohttp_client, uygulama_ayari):
    uyg = sunucu.uygulama_olustur({**uygulama_ayari, "kurulum_tamam": False}, okuyucu_fabrika=lambda: object())
    d = uyg[sunucu.DURUM]
    await aiohttp_client(uyg)
    q = d.yayin.abone_ol()
    await d.kisayol.calistir("baslat_durdur")
    assert not d.calisiyor()
    olaylar = []
    while not q.empty():
        olaylar.append(q.get_nowait())
    assert olaylar and olaylar[-1][1]["bildirim"] == "Önce kurulumu bitirin"


async def test_yeniden_oku_kisayolu_temizler(aiohttp_client, uygulama_ayari):
    uyg = sunucu.uygulama_olustur(uygulama_ayari)
    d = uyg[sunucu.DURUM]
    q = d.yayin.abone_ol()
    d.kisayol.calistir("yeniden_oku")
    adlar = []
    while not q.empty():
        adlar.append(q.get_nowait()[0])
    assert adlar == ["yazi-sil", "ekran-sil", "durum"]


def test_bildirim_metinleri_tr_en():
    from kopru import metinler
    for kod in ("bildirim_basladi", "bildirim_durdu", "bildirim_gizlendi", "bildirim_gosteriliyor",
                "kisayol_kullanimda", "kisayol_cakisma"):
        assert metinler.mesaj(kod, "tr") != metinler.mesaj(kod, "en")
