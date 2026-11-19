# SPDX-License-Identifier: AGPL-3.0-only
from PIL import Image

from kopru.ayarlar import VARSAYILAN
from kopru.ceviri.sahte import SahteMotor
from kopru.ceviri.yonetici import CeviriYoneticisi
from kopru import ayarlar
from kopru.isleme import Isleme, devam_mi, sure_ms
from kopru.okuma import Satir
from kopru.yayin import Yayin

BOLGE = (0.1, 0.8, 0.5, 0.05)  # altyazı bölgesi içinde


class Senaryo:
    """Her adımda bir (resim_rengi, satirlar) döndürür."""

    def __init__(self, kareler):
        self.kareler = kareler
        self.i = -1

    def kare(self):
        self.i += 1
        renk, _ = self.kareler[min(self.i, len(self.kareler) - 1)]
        return Image.new("RGB", (64, 36), (renk, renk, renk))

    def oku(self, resim):
        return self.kareler[min(self.i, len(self.kareler) - 1)][1]


def altyazi(metin):
    return [Satir(metin, *BOLGE)]


async def kos(kareler, ayar=None):
    s = Senaryo(kareler)
    saat = {"t": 0.0}
    y = Yayin()
    q = y.abone_ol()
    ayar = {**VARSAYILAN, "ekrani_cevir": False, **(ayar or {})}
    motor = SahteMotor()
    isl = Isleme(s.kare, s, CeviriYoneticisi(motor, None, None), y, lambda: ayar,
                 saat=lambda: saat["t"])
    for _ in kareler:
        await isl.adim()
        saat["t"] += 0.25
    olaylar = []
    while not q.empty():
        olaylar.append(q.get_nowait())
    return olaylar, motor


async def test_daktilo_yazisi_yayinlanmaz_kararli_bir_kez():
    kareler = [(10, altyazi("Hel")), (20, altyazi("Hello wo")), (30, altyazi("Hello world")),
               (30, altyazi("Hello world")), (30, altyazi("Hello world"))]
    olaylar, motor = await kos(kareler)
    yazilar = [v for o, v in olaylar if o == "yazi"]
    assert len(yazilar) == 1
    assert yazilar[0]["asil"] == "Hello world" and yazilar[0]["metin"] == "[TR] Hello world"
    assert yazilar[0]["sure_ms"] == sure_ms("[TR] Hello world")
    assert motor.cagrilar == [["Hello world"]]


async def test_yazi_sil_kaybolunca():
    k = [(10, altyazi("Run!"))] * 3 + [(50, [])] * 12
    olaylar, _ = await kos(k)
    adlar = [o for o, _ in olaylar]
    assert adlar == ["yazi", "yazi-sil"]


async def test_kisa_kesinti_silmez():
    k = [(10, altyazi("Run!"))] * 3 + [(50, [])] + [(10, altyazi("Run!"))] * 3
    olaylar, _ = await kos(k)
    assert "yazi-sil" not in [o for o, _ in olaylar]
    assert len({v["id"] for o, v in olaylar}) == 1  # yenilemeler aynı id ile


async def test_konusan_ayrilir():
    k = [(10, altyazi("Ellie: Stay close."))] * 3
    olaylar, _ = await kos(k)
    v = [v for o, v in olaylar if o == "yazi"][0]
    assert v["konusan"] == "Ellie" and v["asil"] == "Stay close."


async def test_ekran_ogeleri_ve_aciklama():
    gorev = Satir("Return to the base camp quickly", 0.02, 0.05, 0.3, 0.04)
    menu = Satir("Continue", 0.45, 0.4, 0.1, 0.04)
    k = [(10, [gorev, menu])] * 3 + [(50, [])] * 10
    olaylar, motor = await kos(k, {"ekrani_cevir": True, "kisa_aciklama": True, "kaynak": "pencere:1"})
    e = [v for o, v in olaylar if o == "ekran"]
    assert len(e) == 1
    turler = {o["metin"]: o["tur"] for o in e[0]["ogeler"]}
    assert turler["[TR] Return to the base camp quickly"] == "gorev"
    assert turler["[TR] Continue"] == "menu"
    ac = {o["tur"]: o.get("aciklama") for o in e[0]["ogeler"]}
    assert ac["gorev"] and not ac["menu"]
    assert [o for o, _ in olaylar][-1] == "ekran-sil"


# ---------- PROTOKOL 7.2: akıcı gösterim kuralları (sahte saatle) ----------

DT = 0.25


async def kos_zamanli(kareler, ayar=None, motor=None, senaryo=None):
    """(zaman, olay, veri) listesi döndürür; her kare 0,25 sn sürer."""
    s = senaryo or Senaryo(kareler)
    saat = {"t": 0.0}
    y = Yayin()
    q = y.abone_ol()
    ayar = {**VARSAYILAN, "ekrani_cevir": False, **(ayar or {})}
    isl = Isleme(s.kare, s, CeviriYoneticisi(motor or SahteMotor(), None, None), y, lambda: ayar,
                 saat=lambda: saat["t"])
    out = []
    for _ in kareler:
        await isl.adim()
        while not q.empty():
            o, v = q.get_nowait()
            out.append((saat["t"], o, v))
        saat["t"] += DT
    return out


def yalniz(olaylar, ad):
    return [(t, v) for t, o, v in olaylar if o == ad]


def test_sure_en_az_1800():
    assert sure_ms("Hi") == 1800
    assert sure_ms("x" * 40) == 800 + 40 * 55
    assert sure_ms("x" * 500) == 9000


async def test_1_2_karelik_titreme_silmez():
    for bosluk in (1, 2):
        k = [(10, altyazi("Run!"))] * 3 + [(50, [])] * bosluk + [(10, altyazi("Run!"))] * 3 + [(50, [])] * 14
        olaylar = await kos_zamanli(k)
        assert [o for _, o, _ in olaylar].count("yazi-sil") == 1, bosluk
        assert len({v["id"] for _, v in yalniz(olaylar, "yazi")}) == 1


async def test_en_az_gosterim_suresi_korunur():
    k = [(10, altyazi("Hi"))] * 2 + [(50, [])] * 20
    olaylar = await kos_zamanli(k)
    (t_yazi, v), = yalniz(olaylar, "yazi")
    (t_sil, _), = yalniz(olaylar, "yazi-sil")
    assert v["sure_ms"] == 1800
    # §13.2: kaynak gidince (ilk boş kare 2*DT) en çok 1500 ms kalır; en az süre bunu uzatmaz
    assert t_sil - 2 * DT <= 1.5 + 1e-9


async def test_uzun_yazinin_okuma_suresi_korunur():
    metin = "We should really head back to the base before it gets dark"
    k = [(10, altyazi(metin))] * 2 + [(50, [])] * 40
    olaylar = await kos_zamanli(k)
    (t_yazi, v), = yalniz(olaylar, "yazi")
    (t_sil, _), = yalniz(olaylar, "yazi-sil")
    assert v["sure_ms"] > 1800
    assert t_sil - 2 * DT <= 1.5 + 1e-9   # §13.2: uzun okuma süresi bile kaynak gidince en çok 1500 ms


async def test_gittikten_sonra_700ms_daha_kalir():
    # kaynak 12 kare (3 sn) görünür: en az süre çoktan dolmuş
    k = [(10, altyazi("Run!"))] * 12 + [(50, [])] * 12
    olaylar = await kos_zamanli(k)
    (t_sil, _), = yalniz(olaylar, "yazi-sil")
    ilk_bos = 12 * DT
    gitti = ilk_bos + 2 * DT                     # 3. boş karede "gitti" sayılır
    assert t_sil >= gitti + 0.7 - 1e-9
    assert t_sil < gitti + 0.7 + DT + 1e-9


async def test_gitti_sayilmadan_silinmez():
    # kaynak kayboldu ama sadece 2 kare: sil yok, yazi canlı
    k = [(10, altyazi("Run!"))] * 12 + [(50, [])] * 2 + [(10, altyazi("Run!"))] * 4
    olaylar = await kos_zamanli(k)
    assert not yalniz(olaylar, "yazi-sil")


async def test_devam_ayni_id_devam_true():
    k = [(10, altyazi("We should head back"))] * 3 + \
        [(20, altyazi("We should head back to the base camp"))] * 3
    olaylar = await kos_zamanli(k)
    y = [v for _, v in yalniz(olaylar, "yazi") if v["metin"].startswith("[TR] We")]
    assert len(y) == 2
    assert y[0]["devam"] is False and y[1]["devam"] is True
    assert y[0]["id"] == y[1]["id"]
    assert y[1]["metin"] == "[TR] We should head back to the base camp"
    assert not yalniz(olaylar, "yazi-sil")


async def test_yeni_cumle_yeni_id():
    k = [(10, altyazi("We should head back"))] * 3 + [(40, altyazi("Watch out, they are coming!"))] * 3
    olaylar = await kos_zamanli(k)
    y = [v for _, v in yalniz(olaylar, "yazi") if v["devam"] is False or True]
    ilk, ikinci = y[0], y[-1]
    assert ilk["id"] != ikinci["id"] and ikinci["devam"] is False
    assert [o for _, o, _ in olaylar].count("yazi-sil") == 0   # arada silme yok; TV çapraz geçer


class SabitMotor:
    """Kaynak ne olursa olsun aynı çeviriyi verir (çeviri sabit kalma kuralı)."""
    kod, ad, anahtar_gerekli, cevrimdisi = "sabit", "Sabit", False, True

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False, **kw):
        from kopru.ceviri.temel import Ceviri
        return [Ceviri("Selam dostum") for _ in metinler]


async def test_ceviri_sabitse_devam_sayilir():
    k = [(10, altyazi("Hello there my friend"))] * 3 + [(40, altyazi("Hey you, buddy of mine"))] * 3
    olaylar = await kos_zamanli(k, motor=SabitMotor())
    y = [v for _, v in yalniz(olaylar, "yazi")]
    assert y[0]["id"] == y[-1]["id"] and y[-1]["devam"] is True


def test_devam_mi():
    assert devam_mi("hello wo", "hello world")
    assert devam_mi("hello world", "oh hello world and more")
    assert devam_mi("hello world", "hel1o world")           # küçük OCR farkı
    assert not devam_mi("i can't do this", "i can't do that either")
    assert not devam_mi("run", "")


async def test_canli_tutma_ayni_id_yerinde():
    k = [(10, altyazi("Run!"))] * 30
    olaylar = await kos_zamanli(k)
    y = [v for _, v in yalniz(olaylar, "yazi")]
    assert len(y) >= 3 and len({v["id"] for v in y}) == 1
    assert all(v["devam"] is True for v in y[1:])
    assert not yalniz(olaylar, "yazi-sil")


# ---------- bölge seçimi (PROTOKOL 7.1) ----------

class BolgeOkuyucu:
    """Verilen kareyi değil kırpılan parçanın boyutunu kaydeder; kırpık içinde sabit satır döndürür."""

    def __init__(self, cevap):
        self.cevap = cevap          # {(g, y): [Satir...]} ya da fonksiyon(resim)
        self.boyutlar = []

    def oku(self, resim):
        self.boyutlar.append(resim.size)
        return self.cevap(resim)


class BolgeSenaryo:
    def __init__(self, okuyucu, boyut=(640, 360)):
        self.okuyucu, self.boyut = okuyucu, boyut

    def kare(self):
        return Image.new("RGB", self.boyut, (30, 30, 30))

    def oku(self, resim):
        return self.okuyucu.oku(resim)


async def bolgeli_kos(bolgeler, cevap, kare_sayisi=6, ekran=True):
    ok = BolgeOkuyucu(cevap)
    s = BolgeSenaryo(ok)
    y = Yayin()
    q = y.abone_ol()
    ayar = {**VARSAYILAN, "ekrani_cevir": ekran, "bolgeler": bolgeler}
    saat = {"t": 0.0}
    isl = Isleme(s.kare, s, CeviriYoneticisi(SahteMotor(), None, None), y, lambda: ayar,
                 saat=lambda: saat["t"])
    for _ in range(kare_sayisi):
        await isl.adim()
        saat["t"] += DT
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out, ok


async def test_bolge_kirpma_koordinatlari_tam_kareye_doner():
    bolgeler = [
        {"x": 0.0, "y": 0.0, "g": 0.5, "y2": 0.2, "tur": "ust_yazi", "ad": "Görev"},
        {"x": 0.1, "y": 0.7, "g": 0.8, "y2": 0.2, "tur": "altyazi", "ad": "Altyazı"},
    ]

    def cevap(resim):
        if resim.size == (320, 72):      # üst bölge
            return [Satir("Return to base", 0.1, 0.25, 0.5, 0.5)]
        return [Satir("Stay close", 0.25, 0.5, 0.5, 0.4)]    # altyazı bölgesi (512x72)

    olaylar, ok = await bolgeli_kos(bolgeler, cevap)
    assert sorted(set(ok.boyutlar)) == [(320, 72), (512, 72)]       # yalnız bölgeler okundu, tam kare değil
    ekran = [v for o, v in olaylar if o == "ekran"][0]["ogeler"]
    assert len(ekran) == 1
    e = ekran[0]
    assert (e["x"], e["y"], e["g"], e["y2"]) == (0.05, 0.05, 0.25, 0.1)
    assert e["tur"] == "gorev" and e["metin"] == "[TR] Return to base"
    y = [v for o, v in olaylar if o == "yazi"][0]
    assert y["asil"] == "Stay close" and y["tur"] == "altyazi"
    assert {v["id"] for o, v in olaylar if o == "yazi"} == {y["id"]}   # ekran öğesi yazı olayı olmadı


async def test_bolge_disindaki_yazi_okunmaz_otomatik_kipte_ekran_gelirdi():
    bolgeler = [{"x": 0.1, "y": 0.7, "g": 0.8, "y2": 0.2, "tur": "altyazi", "ad": "A"}]
    olaylar, ok = await bolgeli_kos(bolgeler, lambda r: [Satir("Hello there", 0.1, 0.1, 0.5, 0.5)])
    assert {o for o, _ in olaylar} == {"yazi"}
    assert all(b != (640, 360) for b in ok.boyutlar)


async def test_bolge_kirpma_ince_bolgede_buyutur_ama_koordinat_dogru():
    bolgeler = [{"x": 0.0, "y": 0.9, "g": 1.0, "y2": 0.05, "tur": "diger", "ad": "Ince"}]   # 18 px yüksek
    olaylar, ok = await bolgeli_kos(bolgeler, lambda r: [Satir("Continue", 0.5, 0.0, 0.25, 1.0)])
    assert ok.boyutlar[0][1] >= 48
    e = [v for o, v in olaylar if o == "ekran"][0]["ogeler"][0]
    assert abs(e["x"] - 0.5) < 1e-3 and abs(e["y"] - 0.9) < 1e-3 and abs(e["y2"] - 0.05) < 2e-3


async def test_bolge_degisince_yeniden_okur_ve_bos_liste_otomatik():
    s = BolgeSenaryo(BolgeOkuyucu(lambda r: []))
    ayar = {**VARSAYILAN, "ekrani_cevir": False, "bolgeler": []}
    isl = Isleme(s.kare, s, CeviriYoneticisi(SahteMotor(), None, None), Yayin(), lambda: ayar)
    await isl.adim()
    assert s.okuyucu.boyutlar == [(640, 360)]                 # otomatik: tam kare
    ayar["bolgeler"] = [{"x": 0.1, "y": 0.7, "g": 0.8, "y2": 0.2, "tur": "altyazi", "ad": "A"}]
    await isl.adim()                                          # kare değişmedi ama bölge değişti
    assert s.okuyucu.boyutlar[-1] == (512, 72)


def _b(**ek):
    return {"x": 0.1, "y": 0.1, "g": 0.3, "y2": 0.1, "tur": "altyazi", "ad": "A", **ek}


def test_bolge_dogrulama():
    assert ayarlar.bolgeler_gecerli([])
    assert ayarlar.bolgeler_gecerli([_b(), _b(tur="ust_yazi"), _b(tur="diger")])
    assert ayarlar.bolgeler_gecerli([_b()] * 6)
    assert not ayarlar.bolgeler_gecerli([_b()] * 7)                    # en çok 6
    assert not ayarlar.bolgeler_gecerli([_b(x=-0.1)])
    assert not ayarlar.bolgeler_gecerli([_b(x=0.8, g=0.3)])             # ekran dışına taşar
    assert not ayarlar.bolgeler_gecerli([_b(g=0.01)])                   # çok küçük
    assert not ayarlar.bolgeler_gecerli([_b(y2=0.005)])
    assert not ayarlar.bolgeler_gecerli([_b(tur="menu")])
    assert not ayarlar.bolgeler_gecerli([_b(ad="x" * 31)])
    assert ayarlar.bolgeler_gecerli([_b(ad="x" * 30)])
    assert not ayarlar.bolgeler_gecerli([_b(x=True)])
    assert not ayarlar.bolgeler_gecerli("yok")
    assert not ayarlar.bolgeler_gecerli([5])
    assert ayarlar.bolgeleri_temizle([_b(), {"bozuk": 1}])[0]["ad"] == "A"


# ---------- ekran öğeleri (7.2/8) ----------

def ekran_senaryo(satirlar, n, bos):
    return [(10, satirlar)] * n + [(50, [])] * bos


async def test_ekran_ogesi_degismeyince_yeniden_gonderilmez():
    gorev = Satir("Return to the base camp quickly", 0.02, 0.05, 0.3, 0.04)
    kaymis = Satir("Return to the base camp quickly", 0.025, 0.052, 0.3, 0.04)   # OCR titremesi
    k = [(10, [gorev])] * 4 + [(10, [kaymis])] * 4 + [(10, [gorev])] * 4
    olaylar = await kos_zamanli(k, {"ekrani_cevir": True, "kaynak": "pencere:1"})
    assert len(yalniz(olaylar, "ekran")) == 1
    assert not yalniz(olaylar, "ekran-sil")


async def test_ekran_ogesi_gidince_600ms_sonra_kalkar():
    menu = Satir("Continue", 0.45, 0.4, 0.1, 0.04)
    k = ekran_senaryo([menu], 4, 16)
    olaylar = await kos_zamanli(k, {"ekrani_cevir": True, "kaynak": "pencere:1"})
    (t_sil, _), = yalniz(olaylar, "ekran-sil")
    gitti = 4 * DT + 1 * DT          # 2 ardışık boş karenin ikincisi
    assert t_sil <= gitti + 0.6 + DT + 1e-9   # §13.2: tek öğe de olsa bölge boş: en geç ~600-800 ms


async def test_ekran_tek_kareli_titreme_ogeyi_kaldirmaz():
    menu = Satir("Continue", 0.45, 0.4, 0.1, 0.04)
    k = [(10, [menu])] * 3 + [(50, [])] * 1 + [(10, [menu])] * 8
    olaylar = await kos_zamanli(k, {"ekrani_cevir": True, "kaynak": "pencere:1"})
    assert len(yalniz(olaylar, "ekran")) == 1 and not yalniz(olaylar, "ekran-sil")


async def test_ekran_ogesi_yerinde_guncellenir_ayni_id():
    a = Satir("Collect 3 herbs", 0.02, 0.05, 0.3, 0.04)
    b = Satir("Collect 4 herbs", 0.02, 0.05, 0.3, 0.04)
    k = [(10, [a])] * 3 + [(20, [b])] * 6
    olaylar = await kos_zamanli(k, {"ekrani_cevir": True, "kaynak": "pencere:1"})
    e = yalniz(olaylar, "ekran")
    assert len(e) == 2
    assert [len(v["ogeler"]) for _, v in e] == [1, 1]           # eskisi yerinde değişti, yan yana ikilenmedi
    assert e[0][1]["ogeler"][0]["id"] == e[1][1]["ogeler"][0]["id"]
    assert e[1][1]["ogeler"][0]["metin"] == "[TR] Collect 4 herbs"


# ---------- PROTOKOL 13.2: kaynak yazı gidince çeviri de gitsin ----------

class SabitKareSenaryo:
    """Kare hiç değişmez (parmak izi aynı); yalnız okunan satırlar zamanla değişir."""

    def __init__(self, satirlar_at, saat):
        self.satirlar_at = satirlar_at   # t -> satırlar
        self.saat = saat
        self.oku_sayisi = 0
        self.oku_zamanlari = []

    def kare(self):
        return Image.new("RGB", (64, 36), (10, 10, 10))

    def oku(self, resim):
        self.oku_sayisi += 1
        self.oku_zamanlari.append(self.saat["t"])
        return self.satirlar_at(self.saat["t"])


async def _sabit_kos(satirlar_at, sure, ayar):
    saat = {"t": 0.0}
    s = SabitKareSenaryo(satirlar_at, saat)
    y = Yayin()
    q = y.abone_ol()
    ayar = {**VARSAYILAN, "ekrani_cevir": False, **ayar}
    isl = Isleme(s.kare, s, CeviriYoneticisi(SahteMotor(), None, None), y, lambda: ayar, saat=lambda: saat["t"])
    out = []
    for _ in range(int(sure / DT)):
        await isl.adim()
        while not q.empty():
            o, v = q.get_nowait()
            out.append((saat["t"], o, v))
        saat["t"] += DT
    return out, s


async def test_degismeyen_kare_en_az_saniyede_bir_yeniden_okunur():
    _, s = await _sabit_kos(lambda t: altyazi("Run!"), 6.0, {})
    araliklar = [b - a for a, b in zip(s.oku_zamanlari, s.oku_zamanlari[1:])]
    assert s.oku_sayisi >= 6 and max(araliklar) <= 1.0 + 1e-9
    assert s.oku_sayisi < 24      # her karede okunmaz (önbellek hâlâ işliyor)


async def test_sabit_karede_ekran_ogesi_gidince_kalkar():
    menu = Satir("Continue", 0.45, 0.4, 0.1, 0.04)
    gidis = 3.0
    olaylar, _ = await _sabit_kos(lambda t: [menu] if t < gidis else [], 8.0,
                                  {"ekrani_cevir": True, "kaynak": "pencere:1"})
    (t_sil, _), = yalniz(olaylar, "ekran-sil")
    assert gidis <= t_sil <= gidis + 1.0 + 3 * DT + 1e-9   # en geç 1 sn'lik yeniden okuma + 2 kare


async def test_ekran_ogesi_gidince_600ms_icinde_ekran_olayi_onu_cikarir():
    gorev = Satir("Return to the base camp quickly", 0.02, 0.05, 0.3, 0.04)
    menu = Satir("Continue", 0.45, 0.4, 0.1, 0.04)
    k = [(10, [gorev, menu])] * 4 + [(50, [gorev])] * 12          # menü gider, görev kalır
    olaylar = await kos_zamanli(k, {"ekrani_cevir": True, "kaynak": "pencere:1"})
    ekranlar = yalniz(olaylar, "ekran")
    assert len(ekranlar) == 2 and len(ekranlar[0][1]["ogeler"]) == 2 and len(ekranlar[1][1]["ogeler"]) == 1
    ilk_bos = 4 * DT
    assert ekranlar[1][0] - ilk_bos <= 0.6 + 2 * DT + 1e-9        # 2. boş kare + 600 ms (kare aralığı payıyla)
    assert ekranlar[1][0] - ilk_bos >= 0.6 - 1e-9


async def test_bolge_bosalinca_tum_ogeler_silinir():
    a = Satir("Collect 3 herbs", 0.02, 0.05, 0.3, 0.04)
    b = Satir("Return to camp", 0.02, 0.15, 0.3, 0.04)
    k = [(10, [a, b])] * 4 + [(50, [])] * 8
    olaylar = await kos_zamanli(k, {"ekrani_cevir": True, "kaynak": "pencere:1"})
    (t_sil, _), = yalniz(olaylar, "ekran-sil")
    assert t_sil - 4 * DT <= 2 * DT + 1e-9                        # 2 ardışık boş kare yeter


async def test_altyazi_kaynak_gidince_en_cok_1500ms_kalir():
    for okuma in ("Hi", "We should really head back to the base before it gets dark"):
        k = [(10, altyazi(okuma))] * 3 + [(50, [])] * 20
        olaylar = await kos_zamanli(k)
        (t_sil, _), = yalniz(olaylar, "yazi-sil")
        assert t_sil - 3 * DT <= 1.5 + 1e-9, okuma


async def test_yeniden_oku_her_seyi_siler_ve_hemen_okutur():
    s = Senaryo([(10, altyazi("Run!"))] * 12)
    saat = {"t": 0.0}
    y = Yayin()
    q = y.abone_ol()
    ayar = {**VARSAYILAN, "ekrani_cevir": False}
    isl = Isleme(s.kare, s, CeviriYoneticisi(SahteMotor(), None, None), y, lambda: ayar, saat=lambda: saat["t"])
    for _ in range(4):
        await isl.adim()
        saat["t"] += DT
    while not q.empty():
        q.get_nowait()
    isl.yeniden_oku()
    adlar = []
    while not q.empty():
        adlar.append(q.get_nowait()[0])
    assert adlar == ["yazi-sil", "ekran-sil"] and isl._izi is None
