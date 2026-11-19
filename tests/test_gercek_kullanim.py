# SPDX-License-Identifier: AGPL-3.0-only
"""PROTOKOL 11 (sürüm 0.6): gerçek kullanımda görülen hatalar için gerileme sınamaları.

Hata özeti (Türkçe Windows, Dead by Daylight menüsü, bilgisayar ekranı kipi): katmanın kendi çevirisi
yeniden okunup çevrildi ("tek tek tek", "Parti: Parti:"); pencere seçilince bütün ekran çevrildi;
HUD sayıları çevrildi; ekran öğeleri dar kutuda harf harf sarıldı.
"""
import ctypes
import sys

import pytest
from PIL import Image

from kopru import ayarlar, yakalama
from kopru.ayarlar import VARSAYILAN
from kopru.ceviri.sahte import SahteMotor
from kopru.ceviri.temel import Ceviri
from kopru.ceviri.yonetici import CeviriYoneticisi
from kopru.isleme import (Isleme, altyazi_bandinda, altyazi_sec, boyut_hesapla, ocr_hazirla,
                          okuma_gurultusu_mu, tekrar_var_mi)
from kopru.katman import mantik, yonetim
from kopru.okuma import Satir
from kopru.yayin import Yayin

DT = 0.25
ALT = (0.3, 0.8, 0.4, 0.05)


class TrMotor:
    """Kaynak ne olursa olsun kaynaktan çok farklı bir Türkçe çeviri verir."""
    kod, ad, anahtar_gerekli, cevrimdisi = "tr", "Tr", False, True

    def __init__(self, harita=None):
        self.harita, self.cagrilar = harita or {}, []

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False, **kw):
        self.cagrilar.append(list(metinler))
        return [Ceviri(self.harita.get(m, "Merhaba dostum nasılsın bugün")) for m in metinler]


class Kare:
    """Her adımda (renk, satırlar); okuyucuya verilen kareyi de saklar (maske sınaması)."""

    def __init__(self, kareler, boyut=(100, 100)):
        self.kareler, self.i, self.boyut, self.gorulen = kareler, -1, boyut, []

    def kare(self):
        self.i += 1
        renk = self.kareler[min(self.i, len(self.kareler) - 1)][0]
        return Image.new("RGB", self.boyut, (renk, renk, renk))

    def oku(self, resim):
        self.gorulen.append(resim.copy())
        return self.kareler[min(self.i, len(self.kareler) - 1)][1]


async def kos(kareler, ayar=None, motor=None, boyut=(100, 100)):
    s = Kare(kareler, boyut)
    saat = {"t": 0.0}
    y = Yayin()
    q = y.abone_ol()
    a = {**VARSAYILAN, "ekrani_cevir": True, "kisa_aciklama": False, **(ayar or {})}
    m = motor or TrMotor()
    isl = Isleme(s.kare, s, CeviriYoneticisi(m, None, None), y, lambda: a, saat=lambda: saat["t"])
    for _ in kareler:
        await isl.adim()
        saat["t"] += DT
    olaylar = []
    while not q.empty():
        olaylar.append(q.get_nowait())
    return olaylar, m, s, isl


def yalniz(olaylar, ad):
    return [v for o, v in olaylar if o == ad]


# ---------- 11.1 geri besleme: metin süzgeci ----------

async def test_kendi_cevirisini_yeniden_okumaz_ve_tekrar_cevirmez():
    cevri = "Merhaba dostum nasılsın bugün"
    k = [(10, [Satir("Hello there my old friend", *ALT)])] * 3 + \
        [(20 + i, [Satir(cevri, *ALT)]) for i in range(6)] + \
        [(40 + i, [Satir("Merhaba dostum nasilsin bugun", 0.1, 0.3, 0.4, 0.05)]) for i in range(6)]   # OCR farkı, ekran öğesi yeri
    olaylar, motor, _, _ = await kos(k)
    assert motor.cagrilar == [["Hello there my old friend"]]     # çeviri yeniden çevrilmedi
    assert not yalniz(olaylar, "ekran")


async def test_tek_tek_tek_tekrari_atilir():
    k = [(10 + i, [Satir("tek tek tek tek single", *ALT)]) for i in range(6)] + \
        [(30 + i, [Satir("Parti: Parti: Parti:", 0.1, 0.3, 0.4, 0.05)]) for i in range(6)]
    olaylar, motor, _, _ = await kos(k)
    assert motor.cagrilar == [] and not yalniz(olaylar, "yazi") and not yalniz(olaylar, "ekran")


def test_tekrar_ve_gurultu_kurallari():
    assert tekrar_var_mi("tek tek tek tek single") and tekrar_var_mi("Parti: Parti: Parti:")
    assert tekrar_var_mi("go go") and not tekrar_var_mi("no no, I said no")
    assert not tekrar_var_mi("Press X to continue")
    for atilir in ("358", "30 30", "988", "x", "A", "12:45 / 100", "- - -", "Parti Parti", "1 2 3 4"):
        assert okuma_gurultusu_mu(atilir), atilir
    for kalir in ("Press X", "Level 12", "Ok", "Dead by Daylight", "Return to base"):
        assert not okuma_gurultusu_mu(kalir), kalir


async def test_kaynagina_benzeyen_ceviri_geri_besleme_sayilmaz():
    """Özel isim çevirisi aynıysa ("Vice City") oyunun kendi yazısı atılmamalı."""
    m = TrMotor({"Vice City": "Vice City"})
    k = [(10 + (i % 2), [Satir("Vice City", *ALT)]) for i in range(10)]
    olaylar, _, _, isl = await kos(k, motor=m)
    assert yalniz(olaylar, "yazi") and not isl.geri_besleme_mi("Totally different text here") 
    assert not isl._ceviriler


async def test_geri_besleme_60sn_sonra_unutulur():
    m = TrMotor()
    k = [(10, [Satir("Hello there my old friend", *ALT)])] * 3
    _, _, _, isl = await kos(k, motor=m)
    assert isl.geri_besleme_mi("Merhaba dostum nasılsın bugün")
    isl.saat = lambda: 1000.0
    assert not isl.geri_besleme_mi("Merhaba dostum nasılsın bugün")


# ---------- 11.1 geri besleme: maske ----------

async def test_maske_katmanin_kendi_alanlarini_karartir():
    # özel hedefli bölge: çeviri kaynaktan ayrı bir yerde çizilir -> o alan okumadan önce siyah
    b = {"x": 0.05, "y": 0.05, "g": 0.3, "y2": 0.1, "tur": "diger", "ad": "m",
         "hedef": {"x": 0.55, "y": 0.4, "g": 0.3, "y2": 0.1}}
    k = [(200 + i, [Satir("Return to the base camp", 0.0, 0.0, 1.0, 1.0)]) for i in range(8)]
    olaylar, _, s, isl = await kos(k, {"bolgeler": [b], "gosterim": "bilgisayar", "kaynak": "ekran:1",
                                       "katman_ekran": 1}, boyut=(200, 200))
    assert yalniz(olaylar, "ekran")
    maske = isl.maske_kutulari({**VARSAYILAN, "gosterim": "bilgisayar", "kaynak": "ekran:1"})
    assert maske and maske[0][0] == pytest.approx(0.55) and maske[0][1] == pytest.approx(0.4)
    # kaynak bölgeye karşılık gelen kesitlerde maske yok; ama tam kare okunan kipte hedef alan siyah olurdu
    kare = Image.new("RGB", (200, 200), (200, 200, 200))
    boyali = Isleme._maskele(kare, maske)
    assert boyali.getpixel((int(0.56 * 200), int(0.42 * 200))) == (0, 0, 0)
    assert boyali.getpixel((10, 10)) == (200, 200, 200)
    assert kare.getpixel((int(0.56 * 200), int(0.42 * 200))) == (200, 200, 200)   # özgün kare bozulmadı


async def test_maske_yalniz_ayni_ekran_ve_bilgisayar_kipinde():
    b = {"x": 0.05, "y": 0.05, "g": 0.3, "y2": 0.1, "tur": "diger", "ad": "m",
         "hedef": {"x": 0.55, "y": 0.4, "g": 0.3, "y2": 0.1}}
    k = [(200 + i, [Satir("Return to the base camp", 0.0, 0.0, 1.0, 1.0)]) for i in range(8)]
    _, _, _, isl = await kos(k, {"bolgeler": [b]}, boyut=(200, 200))
    ayar = {**VARSAYILAN, "kaynak": "ekran:1", "katman_ekran": 1}
    assert isl.maske_kutulari({**ayar, "gosterim": "bilgisayar"})
    assert not isl.maske_kutulari({**ayar, "gosterim": "tv"})
    assert not isl.maske_kutulari({**ayar, "gosterim": "bilgisayar", "kaynak": "ekran:2"})     # başka ekran
    assert isl.maske_kutulari({**ayar, "gosterim": "bilgisayar", "kaynak": "pencere:123"})


async def test_altyazi_kutusu_kaynakla_cakismiyorsa_maskelenir():
    k = [(10, [Satir("Hello there my old friend", 0.0, 0.0, 1.0, 0.5)])] * 3   # altyazı bölgesi üstte, kutu altta
    olaylar, _, _, isl = await kos(k, {"bolgeler": [_b(x=0.1, y=0.1, g=0.8, y2=0.3, tur="altyazi")]})
    assert yalniz(olaylar, "yazi")
    maske = isl.maske_kutulari({**VARSAYILAN, "gosterim": "bilgisayar"})
    assert maske and maske[0][1] > 0.6


async def test_altyazi_kaynagin_ustundeyse_maskelenmez():
    k = [(10, [Satir("Hello there my old friend", *ALT)])] * 3
    _, _, _, isl = await kos(k)
    assert isl.maske_kutulari({**VARSAYILAN, "gosterim": "bilgisayar"}) == []   # kaynağı da karartırdı


# ---------- 11.2 pencere yakalama (sahte ctypes) ----------

class SahteUser32:
    def __init__(self, g=40, y=30, simge=False, printwindow=1):
        self.g, self.y, self.simge, self.pw = g, y, simge, printwindow
        self.printwindow_bayraklari = []

    def IsWindow(self, h): return 1
    def IsIconic(self, h): return int(self.simge)
    def IsWindowVisible(self, h): return 1

    def GetClientRect(self, h, ref):
        ref._obj.left, ref._obj.top, ref._obj.right, ref._obj.bottom = 0, 0, self.g, self.y
        return 1

    def ClientToScreen(self, h, ref):
        ref._obj.x, ref._obj.y = 100, 50
        return 1

    def GetWindowDC(self, h): return 7
    def ReleaseDC(self, h, dc): return 1

    def PrintWindow(self, h, dc, bayrak):
        self.printwindow_bayraklari.append(bayrak)
        return self.pw


class SahteGdi32:
    def __init__(self, dolu=True):
        self.dolu, self.silinen = dolu, []

    def CreateCompatibleDC(self, dc): return 8
    def CreateCompatibleBitmap(self, dc, g, y): return 9
    def SelectObject(self, dc, nesne): return 5

    def GetDIBits(self, dc, bmp, ilk, satir, tampon, bi, kullanim):
        if self.dolu:
            ctypes.memset(tampon, 0x80, len(tampon))
        return satir

    def DeleteObject(self, n): self.silinen.append(("bmp", n)); return 1
    def DeleteDC(self, n): self.silinen.append(("dc", n)); return 1


def _grab(cagrilar):
    def f(kutu):
        cagrilar.append(kutu)
        return Image.new("RGB", (kutu["width"], kutu["height"]), (1, 2, 3))
    return f


def test_pencere_istemci_kutusu_ekran_koordinatli():
    assert yakalama.pencere_istemci_kutusu(5, SahteUser32()) == {"left": 100, "top": 50, "width": 40, "height": 30}
    assert yakalama.pencere_istemci_kutusu(5, SahteUser32(simge=True)) is None     # simge durumu


def test_printwindow_basarili_ekran_goruntusune_dusmez():
    u, g, cagrilar = SahteUser32(), SahteGdi32(), []
    r = yakalama.pencere_kare_al(5, _grab(cagrilar), u, g)
    assert r.size == (40, 30) and r.getpixel((3, 3)) == (0x80, 0x80, 0x80) and cagrilar == []
    assert u.printwindow_bayraklari == [3]            # PW_RENDERFULLCONTENT (2) | PW_CLIENTONLY (1)
    assert ("bmp", 9) in g.silinen and ("dc", 8) in g.silinen    # GDI nesneleri sızmaz


def test_printwindow_siyahsa_istemci_alani_ekrandan_kirpilir():
    cagrilar = []
    r = yakalama.pencere_kare_al(5, _grab(cagrilar), SahteUser32(), SahteGdi32(dolu=False))
    assert cagrilar == [{"left": 100, "top": 50, "width": 40, "height": 30}]
    assert r.getpixel((0, 0)) == (1, 2, 3)


def test_printwindow_basarisizsa_kirpmaya_duser():
    cagrilar = []
    yakalama.pencere_kare_al(5, _grab(cagrilar), SahteUser32(printwindow=0), SahteGdi32())
    assert len(cagrilar) == 1


def test_pencere_simgedeyse_hata():
    with pytest.raises(yakalama.YakalamaHatasi):
        yakalama.pencere_kare_al(5, _grab([]), SahteUser32(simge=True), SahteGdi32())


def test_pencere_kodu():
    assert yakalama.pencere_kodu("pencere:1234") == 1234
    assert yakalama.pencere_kodu("ekran:1") is None and yakalama.pencere_kodu("pencere:x") is None


def test_katman_komutu_pencere_alir(monkeypatch):
    assert "--pencere" not in yonetim.komut("http://x/akis", 1)
    c = yonetim.komut("http://x/akis", 1, 4242)
    assert c[c.index("--pencere") + 1] == "4242"
    monkeypatch.setattr(sys, "platform", "win32")
    ayar = {"kaynak": "pencere:77", "katman_ekran": 1, "gosterim": "bilgisayar"}
    y = yonetim.KatmanYonetici(lambda: ayar, Yayin(), lambda: True, lambda: 8642)
    assert y.istenen_pencere() == 77
    ayar["kaynak"] = "ekran:1"
    assert y.istenen_pencere() is None


def test_pencere_monitoru():
    m = mantik.pencere_monitoru({"left": 100, "top": 50, "width": 800, "height": 600})
    assert (m.x, m.y, m.g, m.y2) == (100, 50, 800, 600) and m.geometri() == "800x600+100+50"
    assert mantik.pencere_monitoru(None) is None and mantik.pencere_monitoru({"left": 0, "top": 0, "width": 0, "height": 5}) is None


# ---------- 11.3 süzgeç ----------

async def test_hud_sayilari_ve_parcalar_cevrilmez():
    hud = [Satir("358", 0.1, 0.1, 0.05, 0.03), Satir("30 30", 0.3, 0.1, 0.05, 0.03),
           Satir("988", 0.5, 0.1, 0.05, 0.03), Satir("x", 0.6, 0.3, 0.02, 0.03),
           Satir("Return to base", 0.2, 0.5, 0.3, 0.04)]
    olaylar, motor, _, _ = await kos([(10 + i // 2, hud) for i in range(6)], {"kaynak": "pencere:1"})
    assert motor.cagrilar == [["Return to base"]]


async def test_otomatik_kipte_altyazi_yalniz_alt_orta_bantta():
    ust = Satir("Press the button to continue", 0.3, 0.2, 0.4, 0.05)      # üstte: altyazı değil, ekran öğesi
    sol = Satir("Hello there my old friend", 0.0, 0.85, 0.15, 0.05)       # altta ama köşede (merkez x<0.2)
    alt = Satir("Stay close to me please", 0.3, 0.85, 0.4, 0.05)
    olaylar, _, _, _ = await kos([(10 + i // 3, [ust, sol, alt]) for i in range(8)],
                                 {"bolge_altyazi": {"x": 0.0, "y": 0.6, "g": 1.0, "y2": 0.4}})
    (y,) = {v["asil"] for v in yalniz(olaylar, "yazi")}
    assert y == "Stay close to me please"


def test_altyazi_bandi_ve_bitisik_satirlar():
    assert altyazi_bandinda(Satir("a b", 0.3, 0.8, 0.4, 0.05))
    assert not altyazi_bandinda(Satir("a b", 0.3, 0.5, 0.4, 0.05))
    assert not altyazi_bandinda(Satir("a b", 0.0, 0.8, 0.2, 0.05))
    a, b = Satir("first line", 0.3, 0.80, 0.4, 0.04), Satir("second line", 0.32, 0.845, 0.36, 0.04)
    uzak = Satir("far away hint", 0.3, 0.95, 0.4, 0.03)
    yan = Satir("other column", 0.8, 0.82, 0.15, 0.04)
    sec = altyazi_sec([uzak, b, a, yan])
    assert [s.metin for s in sec] == ["first line", "second line"]      # bitişik + yatayda örtüşen birleşir


# ---------- 11.4 hedef ve ölçek ----------

def _b(**ek):
    return {"x": 0.1, "y": 0.1, "g": 0.3, "y2": 0.1, "tur": "diger", "ad": "A", **ek}


def test_bolge_hedef_olcek_dogrulama():
    assert ayarlar.bolgeler_gecerli([_b(), _b(hedef="ustune"), _b(hedef="altyazi", olcek=2.0),
                                     _b(hedef={"x": 0.5, "y": 0.5, "g": 0.2, "y2": 0.1}, olcek=0.6)])
    assert not ayarlar.bolgeler_gecerli([_b(hedef="ortaya")])
    assert not ayarlar.bolgeler_gecerli([_b(hedef={"x": 0.9, "y": 0.5, "g": 0.2, "y2": 0.1})])    # taşar
    assert not ayarlar.bolgeler_gecerli([_b(hedef=5)])
    assert not ayarlar.bolgeler_gecerli([_b(olcek=0.5)]) and not ayarlar.bolgeler_gecerli([_b(olcek=2.1)])
    assert not ayarlar.bolgeler_gecerli([_b(olcek="1")]) and not ayarlar.bolgeler_gecerli([_b(olcek=True)])


def test_bolge_eksik_alanlar_varsayilana_doner():
    t = ayarlar.bolgeleri_temizle([_b(tur="altyazi"), _b(tur="ust_yazi"), _b(tur="diger", hedef="altyazi", olcek=1.5)])
    assert [(x["hedef"], x["olcek"]) for x in t] == [("altyazi", 1.0), ("ustune", 1.0), ("altyazi", 1.5)]


def test_ekran_olcek_ayari_duzelir():
    a = ayarlar.duzelt({**VARSAYILAN, "gorunum": {**VARSAYILAN["gorunum"], "ekran_olcek": 9}})
    assert a["gorunum"]["ekran_olcek"] == 1.0
    assert ayarlar.duzelt({**VARSAYILAN, "gorunum": {"ekran_olcek": 1.5}})["gorunum"]["ekran_olcek"] == 1.5
    assert VARSAYILAN["gorunum"]["ekran_olcek"] == 1.0


async def test_sunucu_yeni_alanlari_dogrular(aiohttp_client, uygulama_ayari):
    from kopru import sunucu
    from tests.conftest import sahte_fabrika
    uygulama_ayari["motor"], uygulama_ayari["yedek_motor"] = "sahte", ""
    c = await aiohttp_client(sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika))
    assert (await c.post("/api/ayarlar", json={"gorunum": {"ekran_olcek": 0.5}})).status == 400
    assert (await c.post("/api/ayarlar", json={"gorunum": {"ekran_olcek": 2.5}})).status == 400
    assert (await c.post("/api/ayarlar", json={"gorunum": {"ekran_olcek": 1.4}})).status == 200
    assert (await c.post("/api/ayarlar", json={"bolgeler": [_b(hedef="x")]})).status == 400
    assert (await c.post("/api/ayarlar", json={"bolgeler": [_b(olcek=3)]})).status == 400
    ok = _b(hedef={"x": 0.5, "y": 0.5, "g": 0.2, "y2": 0.1}, olcek=1.2)
    assert (await c.post("/api/ayarlar", json={"bolgeler": [ok, _b(tur="altyazi")]})).status == 200
    kayit = (await (await c.get("/api/ayarlar")).json())["bolgeler"]
    assert kayit[0]["hedef"] == {"x": 0.5, "y": 0.5, "g": 0.2, "y2": 0.1} and kayit[0]["olcek"] == 1.2
    assert kayit[1]["hedef"] == "altyazi"


async def test_bolge_yonlendirme_ustune_ozel_ve_altyazi():
    bolgeler = [
        _b(x=0.0, y=0.0, g=0.5, y2=0.2, tur="ust_yazi"),                                               # ustune
        _b(x=0.5, y=0.0, g=0.45, y2=0.2, tur="diger", hedef={"x": 0.6, "y": 0.5, "g": 0.3, "y2": 0.1}, olcek=2.0),
        _b(x=0.0, y=0.3, g=0.4, y2=0.2, tur="diger", hedef="altyazi"),                                # altyazı çubuğuna
        _b(x=0.1, y=0.7, g=0.8, y2=0.2, tur="altyazi"),
    ]
    cevap = {500: [Satir("Return to base", 0.1, 0.25, 0.5, 0.5)],
             450: [Satir("Open the", 0.1, 0.1, 0.5, 0.3), Satir("treasure chest", 0.1, 0.5, 0.5, 0.3)],
             400: [Satir("Follow the leader", 0.1, 0.1, 0.5, 0.4)],
             800: [Satir("Stay close", 0.25, 0.5, 0.5, 0.4)]}

    class Okuyucu:
        def oku(self, resim):
            return cevap[resim.size[0]]

    y = Yayin()
    q = y.abone_ol()
    ayar = {**VARSAYILAN, "ekrani_cevir": True, "bolgeler": bolgeler, "kisa_aciklama": False}
    saat = {"t": 0.0}
    isl = Isleme(lambda: Image.new("RGB", (1000, 1000), (30, 30, 30)), Okuyucu(),
                 CeviriYoneticisi(TrMotor({"Return to base": "Üsse dön", "Open the treasure chest": "Sandığı aç"}),
                                  None, None), y, lambda: ayar, saat=lambda: saat["t"])
    for _ in range(6):
        await isl.adim()
        saat["t"] += DT
    olaylar = []
    while not q.empty():
        olaylar.append(q.get_nowait())
    yazilar = yalniz(olaylar, "yazi")
    asiller = {v["asil"] for v in yazilar}
    assert asiller and asiller <= {"Follow the leader", "Stay close"}   # altyazı bölgeleri yazi olayına gitti
    ogeler = yalniz(olaylar, "ekran")[-1]["ogeler"]
    assert len(ogeler) == 2                                         # altyazı bölgeleri ekran öğesi olmadı
    ust = next(o for o in ogeler if o["metin"] == "Üsse dön")
    ozel = next(o for o in ogeler if o["metin"] == "Sandığı aç")
    assert (ust["hedef"]["x"], ust["hedef"]["y"]) == (ust["x"], ust["y"])     # ustune: kaynağın kendi kutusu
    assert ozel["hedef"] == {"x": 0.6, "y": 0.5, "g": 0.3, "y2": 0.1}        # özel: kullanıcının kutusu
    assert ozel["x"] == pytest.approx(0.5 + 0.1 * 0.45)                       # kaynak kutusu ayrı kalır
    assert 14 <= ust["boyut_px"] <= 30 and ozel["boyut_px"] > ust["boyut_px"]  # olcek 2.0


def test_boyut_px_kaynak_yuksekligi_olcek_ve_genel_olcek():
    kucuk = Satir("a", 0, 0, 0.1, 0.01)        # 10.8 px yüksek * 0.75 = 8 -> 12'ye sıkışır (§12.4)
    buyuk = Satir("a", 0, 0, 0.1, 0.08)        # 86 px * 0.75 = 65 -> 22'ye sıkışır
    orta = Satir("a", 0, 0, 0.1, 0.02)         # 21.6 px * 0.75 = 16.2
    assert boyut_hesapla(kucuk, 1.0, 1.0) == 12.0 and boyut_hesapla(buyuk, 1.0, 1.0) == 22.0
    assert boyut_hesapla(orta, 1.0, 1.0) == pytest.approx(16.2, abs=0.1)
    assert boyut_hesapla(orta, 1.5, 1.2) == pytest.approx(16.2 * 1.8, abs=0.2)
    iki_satir = Satir("a b", 0, 0, 0.1, 0.04, 2)    # iki satırlık öğe: satır başına 0.02
    assert boyut_hesapla(iki_satir, 1.0, 1.0) == boyut_hesapla(orta, 1.0, 1.0)


async def test_ekran_olcek_ve_boyut_olayda():
    oge = Satir("Return to the base camp quickly", 0.02, 0.05, 0.3, 0.02)
    olaylar, _, _, _ = await kos([(10, [oge])] * 4, {"gorunum": {**VARSAYILAN["gorunum"], "ekran_olcek": 1.5},
                                                      "kaynak": "pencere:1"})
    (e,) = yalniz(olaylar, "ekran")
    assert e["ogeler"][0]["boyut_px"] == pytest.approx(16.2 * 1.5, abs=0.2)
    assert e["ogeler"][0]["hedef"] == {"x": 0.02, "y": 0.05, "g": 0.3, "y2": 0.02}


async def test_bolgeli_kipte_yalniz_altyazi_bolgesi_altyazi_olur():
    b = [_b(x=0.0, y=0.0, g=0.5, y2=0.2, tur="ust_yazi")]
    olaylar, _, _, _ = await kos([(10 + i, [Satir("Return to base", 0.2, 0.3, 0.5, 0.3)]) for i in range(6)],
                                 {"bolgeler": b})
    assert not yalniz(olaylar, "yazi") and yalniz(olaylar, "ekran")


# ---------- OCR öncesi iyileştirme ----------

def test_kucuk_kesit_buyutulur_gri_ve_kontrastli():
    r = Image.new("RGB", (100, 20), (100, 120, 140))
    r.putpixel((5, 5), (110, 130, 150))
    o = ocr_hazirla(r)
    assert o.size[1] >= 48 and o.size[0] >= 200 and o.mode == "RGB"
    assert len({p[0] for p in o.getdata()}) > 1 and all(p[0] == p[1] == p[2] for p in o.getdata())
    assert ocr_hazirla(Image.new("RGB", (100, 80), (5, 5, 5))).size == (100, 80)    # yeterince yüksek: boyut aynı


# ---------- 12.4 yerleşim (Tk'sız saf fonksiyon) ----------

def olc(t, px):
    return len(t) * px * 0.55


def _kelimeler_bozulmadi(lay, metin):
    assert " ".join(lay["satirlar"]).split() == metin.split()      # yalnız boşlukta kırıldı, kelime kaybolmadı/bölünmedi


def test_yerlesim_kelimeyi_asla_bolmez_ve_en_cok_yuzde_35_iki_satir():
    W, H = 1920, 1080
    metin = "Bu çok uzun bir görev açıklaması olup kutu"
    lay = mantik.ekran_ogesi_yerlesim(metin, "", olc, 22, (0.1, 0.2, 0.02, 0.03), W, H, kaynak_g=0.4)
    _kelimeler_bozulmadi(lay, metin)
    assert lay["g"] <= W * 0.35 + 1 and len(lay["satirlar"]) <= 2
    assert all(olc(s, lay["px"]) + 2 * lay["dolgu"] <= W * 0.35 + 1 for s in lay["satirlar"])


def test_yerlesim_kisa_metin_tek_satir_ve_hedefte():
    lay = mantik.ekran_ogesi_yerlesim("Parti:", "", olc, 24, (0.5, 0.25, 0.01, 0.01), 2000, 1000)
    assert lay["satirlar"] == ["Parti:"]                # harf harf ("Pa / r / ti:") sarılmadı
    assert (lay["x"], lay["y"]) == (1000, 250) and lay["g"] < 2000 * 0.35


def test_yerlesim_genislik_kaynagin_1_6_kati_ve_ekranin_35i():
    W, H = 1920, 1080
    metin = "Return to the base camp"
    dar = mantik.ekran_ogesi_yerlesim(metin, "", olc, 16, (0, 0, 0, 0), W, H, kaynak_g=0.10)   # 1.6 x 192 = 307 px
    assert dar["g"] <= 1.6 * 0.10 * W + 1 and len(dar["satirlar"]) <= 2
    genis = mantik.ekran_ogesi_yerlesim(metin * 8, "", olc, 16, (0, 0, 0, 0), W, H, kaynak_g=0.9)
    assert genis["g"] <= W * 0.35 + 1
    tek = mantik.ekran_ogesi_yerlesim(metin, "", olc, 16, (0, 0, 0, 0), W, H, kaynak_g=0.9)
    assert tek["satirlar"] == [metin]                      # sığıyorsa TEK satır


@pytest.mark.parametrize("metin", [
    "Return to the base camp before sunset", "Press X to continue your journey", "Speak with the old merchant near the gate",
    "Bu görevi tamamlamak için köydeki demirciyle konuş", "Yeni bir bölge keşfedildi", "Sitesi yeni yeni yeni",
])
@pytest.mark.parametrize("kaynak_g", [0.06, 0.12, 0.25, 0.5])
@pytest.mark.parametrize("boyut", [12, 16, 22, 44])
def test_yerlesim_normal_cumle_asla_kelime_kelime_yigilmaz(metin, kaynak_g, boyut):
    lay = mantik.ekran_ogesi_yerlesim(metin, "", olc, boyut, (0.1, 0.1, 0, 0), 1920, 1080, kaynak_g=kaynak_g)
    assert 1 <= len(lay["satirlar"]) <= 2
    if len(metin.split()) >= 4:     # "Return / to / the / base" gibi her kelime ayrı satırda yığılmaz
        assert len(lay["satirlar"][0].split()) >= 2
    assert lay["px"] >= 11


def test_yerlesim_sigmazsa_kucultur_sonra_uca_nokta_koyar():
    metin = "Bu çok uzun bir görev açıklaması olup kutu genişleyip sonra kelime sınırlarında alt satıra geçmelidir " * 3
    lay = mantik.ekran_ogesi_yerlesim(metin, "", olc, 22, (0.0, 0.0, 0, 0), 1920, 1080, kaynak_g=0.1)
    assert lay["px"] == 11 and lay["kirpildi"] and len(lay["satirlar"]) <= 2
    assert lay["satirlar"][-1].endswith("…")
    assert all(k in metin.split() for k in lay["satirlar"][0].split())     # kelime ortasından bölünmedi
    kucuk = mantik.ekran_ogesi_yerlesim("Konfigürasyonlarımızdan", "", olc, 30, (0, 0, 0.01, 0.01), 200, 1080)
    assert kucuk["px"] == 11 and kucuk["satirlar"][0].endswith("…")          # tek kelime bile sığmazsa kısaltılır


def test_yerlesim_uzun_kelime_yazi_kuculur_en_az_11px():
    metin = "Konfigürasyon"
    lay = mantik.ekran_ogesi_yerlesim(metin, "", olc, 30, (0.0, 0.0, 0.01, 0.01), 400, 1080)   # %35 = 140 px
    assert lay["satirlar"] == [metin]
    assert 11 <= lay["px"] < 30
    assert olc(metin, lay["px"]) + 2 * lay["dolgu"] <= 140 + 1


def test_yerlesim_ekran_disina_tasmaz_ve_1080_olcegi():
    lay = mantik.ekran_ogesi_yerlesim("Ana kampa dön", "Görev: üsse geri git", olc, 20, (0.98, 0.99, 0.01, 0.01), 1920, 1080)
    assert lay["x"] + lay["g"] <= 1920 and lay["y"] + lay["y2"] <= 1080 and lay["aciklama_satirlar"]
    kucuk = mantik.ekran_ogesi_yerlesim("Menü", "", olc, 20, (0, 0, 0, 0), 960, 540)
    assert kucuk["px"] == round(20 * 540 / 1080)     # 1080p ölçeğine göre yarı boy


def test_ekran_ogesi_boyut_kelepcesi_12_22():
    from kopru.isleme import boyut_hesapla
    for y2 in (0.005, 0.01, 0.02, 0.05, 0.2):
        b = boyut_hesapla(Satir("a b c", 0, 0, 0.1, y2), 1.0, 1.0)
        assert 12.0 <= b <= 22.0
    assert mantik.ekran_ogesi_hazirla({"x": 0, "y": 0, "y2": 0.5, "metin": "A"})["boyut_px"] == 22.0
    assert mantik.ekran_ogesi_hazirla({"x": 0, "y": 0, "y2": 0.001, "metin": "A"})["boyut_px"] == 12.0


def test_kutu_kesisir_kendi_pencereye_cizilmez():
    assert mantik.kutu_kesisir((10, 10, 50, 30), [(40, 20, 100, 100)])
    assert not mantik.kutu_kesisir((10, 10, 50, 30), [(50, 10, 100, 30), (0, 40, 100, 80)])    # yalnız değiyor
    assert not mantik.kutu_kesisir((10, 10, 50, 30), [])


def test_ekran_ogesi_hazirla_hedef_ve_boyut():
    p = mantik.ekran_ogesi_hazirla({"x": 0.1, "y": 0.2, "metin": "A", "hedef": {"x": 0.6, "y": 0.7, "g": 0.2, "y2": 0.1},
                                    "boyut_px": 22})
    assert (p["x"], p["y"], p["boyut_px"]) == (0.6, 0.7, 22.0)
    eski = mantik.ekran_ogesi_hazirla({"x": 0.1, "y": 0.2, "g": 0.2, "y2": 0.04, "metin": "A"})   # eski sunucu
    assert (eski["x"], eski["y"]) == (0.1, 0.2) and 12 <= eski["boyut_px"] <= 22
