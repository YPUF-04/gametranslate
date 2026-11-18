# SPDX-License-Identifier: AGPL-3.0-only
from PIL import Image

from kopru.ayarlar import VARSAYILAN
from kopru.ceviri.sahte import SahteMotor
from kopru.ceviri.yonetici import CeviriYoneticisi
from kopru.isleme import Isleme, sure_ms
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
    k = [(10, altyazi("Run!"))] * 3 + [(50, [])] * 5
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
    k = [(10, [gorev, menu])] * 3 + [(50, [])] * 5
    olaylar, motor = await kos(k, {"ekrani_cevir": True, "kisa_aciklama": True})
    e = [v for o, v in olaylar if o == "ekran"]
    assert len(e) == 1
    turler = {o["metin"]: o["tur"] for o in e[0]["ogeler"]}
    assert turler["[TR] Return to the base camp quickly"] == "gorev"
    assert turler["[TR] Continue"] == "menu"
    ac = {o["tur"]: o.get("aciklama") for o in e[0]["ogeler"]}
    assert ac["gorev"] and not ac["menu"]
    assert [o for o, _ in olaylar][-1] == "ekran-sil"
