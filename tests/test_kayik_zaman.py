# SPDX-License-Identifier: AGPL-3.0-only
"""PROTOKOL §13.4: oyunla aynı süre (kayık zamanlama).

Sahte saat + sahte kare/OCR + gecikmeli sahte motor. Motor beklemesi gerçek uyku değil, sahte saatin
ilerlemesini bekler; böylece kare döngüsü ve silme zamanlayıcısı gerçekteki gibi (çeviri beklerken
döngü bloklanır, zamanlayıcı yine çalışır) birlikte yürür.
"""
import asyncio

import pytest
from PIL import Image

from kopru import ayarlar, isleme
from kopru.ayarlar import VARSAYILAN
from kopru.ceviri.temel import Ceviri
from kopru.ceviri.yonetici import CeviriYoneticisi
from kopru.isleme import Isleme, en_az_ms_ayari
from kopru.okuma import Satir

DT = 0.25      # kare aralığı
TIK = 0.05     # sahte saat adımı
ALT = (0.1, 0.8, 0.5, 0.05)   # altyazı bölgesinde


class Saat:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Kayit:
    """Yayin yerine: (an, olay, veri)."""

    def __init__(self, saat):
        self.saat, self.liste = saat, []

    def yayinla(self, ad, veri=None):
        self.liste.append((self.saat.t, ad, veri if veri is not None else {}))

    def olay(self, ad):
        return [(t, v) for t, o, v in self.liste if o == ad]


class GecikmeliMotor:
    kod, ad, anahtar_gerekli, cevrimdisi = "gecikmeli", "Gecikmeli", False, True

    def __init__(self, saat, gecikme=0.6, ozel=None):
        self.saat, self.gecikme, self.ozel = saat, gecikme, ozel or {}

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False, **kw):
        bitis = self.saat.t + max(self.ozel.get(m, self.gecikme) for m in metinler)
        while self.saat.t < bitis - 1e-9:
            await asyncio.sleep(0)
        return [Ceviri(f"[TR] {m}") for m in metinler]


class Kaynak:
    """segmentler: [(bas, bitis, metin | Satir)]; kare her segment değişiminde değişir (parmak izi)."""

    def __init__(self, saat, segmentler):
        self.saat, self.segmentler = saat, segmentler
        self.an = 0.0

    def _aktif(self, t):
        return [(i, s) for i, (b, e, s) in enumerate(self.segmentler) if b <= t < e]

    def kare(self):
        self.an = self.saat.t
        renk = (sum((i + 1) * 37 for i, _ in self._aktif(self.an)) % 200) + 20
        return Image.new("RGB", (64, 36), (renk, renk, renk))

    def oku(self, resim):
        out = []
        for _, s in self._aktif(self.an):
            out.append(s if isinstance(s, Satir) else Satir(s, *ALT))
        return out


async def _satir_ici_thread(fn, *a, **k):
    return fn(*a, **k)


async def kos(monkeypatch, segmentler, sure, gecikme=0.6, ozel=None, ayar=None):
    monkeypatch.setattr(isleme.asyncio, "to_thread", _satir_ici_thread)
    monkeypatch.setattr(isleme, "SPEK_BEKLEME_SN", 0)
    saat = Saat()
    kayit = Kayit(saat)
    kaynak = Kaynak(saat, segmentler)
    a = {**VARSAYILAN, "ekrani_cevir": False, "kaynak": "pencere:1", **(ayar or {})}
    isl = Isleme(kaynak.kare, kaynak, CeviriYoneticisi(GecikmeliMotor(saat, gecikme, ozel), None, None),
                 kayit, lambda: a, saat=saat)
    gorev, sonraki = None, 0.0
    while saat.t <= sure + 1e-9:
        isl.silmeleri_isle()      # gerçekte call_later çalıştırır
        if (gorev is None or gorev.done()) and saat.t >= sonraki - 1e-9:
            if gorev is not None:
                gorev.result()
            gorev = asyncio.ensure_future(isl.adim())
            sonraki = saat.t + DT
        for _ in range(10):
            await asyncio.sleep(0)
        saat.t = round(saat.t + TIK, 10)
    if gorev is not None and gorev.done():
        gorev.result()
    return kayit


def gorunenler(kayit):
    """[(id, goruldu, kalktı)] — yeni id'li yazı öncekini yer değiştirir; yazi-sil o id'yi kaldırır."""
    out = []   # [id, bas, son]
    for t, ad, v in kayit.liste:
        if ad == "yazi":
            if out and out[-1][2] is None and out[-1][0] != v["id"]:
                out[-1][2] = t
            if not out or out[-1][0] != v["id"]:
                out.append([v["id"], t, None])
        elif ad == "yazi-sil":
            kim = v.get("id")
            for o in out:
                if o[2] is None and (kim is None or o[0] == kim):
                    o[2] = t
    return out


L1, L2, L3, L4 = "We should head back to the camp now", "Watch out, they are coming for us", \
    "Get down behind the wall", "Run to the old bridge"


async def test_dort_satir_oyundaki_sureyle_kayik_gorunur(monkeypatch):
    # oyunda 2.0 / 2.0 / 1.3 / 1.0 sn, aralarında boşluk yok
    seg = [(0.0, 2.0, L1), (2.0, 4.0, L2), (4.0, 5.3, L3), (5.3, 6.3, L4)]
    k = await kos(monkeypatch, seg, 10.0)
    g = gorunenler(k)
    assert len(g) == 4 and all(son is not None for _, _, son in g)
    for (kimlik, bas, son), (b, e, _) in zip(g, seg):
        assert abs((son - bas) - (e - b)) <= DT + TIK + 1e-9, (kimlik, son - bas, e - b)   # aynı süre (±1 kare)
        assert abs(bas - b - 0.6) <= DT + TIK + 1e-9, (kimlik, bas - b)                     # ≈0,6 sn kayık
    # çakışma yok, boşluk yok: her biri öncekinin bittiği anda başlar
    for onceki, sonraki in zip(g, g[1:]):
        assert onceki[2] == sonraki[1]
    # yalnız sonuncu silinir ve doğru id ile
    silmeler = k.olay("yazi-sil")
    assert len(silmeler) == 1 and silmeler[0][1] == {"id": g[-1][0]}
    assert [i for i, _, _ in g] == [v["id"] for _, v in k.olay("yazi") if not v["devam"]]


async def test_cok_kisa_satir_en_az_800ms_gorunur(monkeypatch):
    k = await kos(monkeypatch, [(1.0, 1.3, "Quick one over there")], 6.0)
    (kimlik, bas, son), = gorunenler(k)
    assert abs((son - bas) - 0.8) <= TIK + 1e-9


async def test_en_az_ms_ayari_gecerli(monkeypatch):
    k = await kos(monkeypatch, [(1.0, 1.3, "Quick one over there")], 6.0, ayar={"gorunum": {**ayarlar.VARSAYILAN_GORUNUM, "en_az_ms": 2000}})
    (kimlik, bas, son), = gorunenler(k)
    assert abs((son - bas) - 2.0) <= TIK + 1e-9
    k = await kos(monkeypatch, [(1.0, 1.3, "Quick one over there")], 6.0, ayar={"gorunum": {**ayarlar.VARSAYILAN_GORUNUM, "en_az_ms": 0}})
    (kimlik, bas, son), = gorunenler(k)
    assert son - bas < 0.8   # taban yok: oyundaki (kayık) süre


async def test_uzun_satir_kaynak_gidince_hemen_okuma_suresi_beklemeden_kalkar(monkeypatch):
    metin = "We should really head back to the base before it gets dark and cold"
    k = await kos(monkeypatch, [(0.0, 3.0, metin)], 10.0)
    (kimlik, bas, son), = gorunenler(k)
    assert abs((son - bas) - 3.0) <= DT + TIK + 1e-9    # eski kural: okuma süresi/1800 ms tabanı yok


async def test_yeni_cumle_gec_gelirse_eskisi_bosluk_birakmadan_yerinde_kalir(monkeypatch):
    # ikinci cümlenin çevirisi 1.2 sn sürer (ilkinin L'si 0.4): eskisi yenisi gelene dek kalır
    seg = [(0.0, 1.0, L1), (1.0, 4.0, L2)]
    k = await kos(monkeypatch, seg, 9.0, gecikme=0.4, ozel={L2: 1.2})
    g = gorunenler(k)
    assert len(g) == 2 and g[0][2] == g[1][1]
    # t_git + L(0,4) = ~1,55 olsa da, yeni 2,3 civarında gelene kadar silinmemiş olmalı
    assert g[1][1] > g[0][1] + 1.5
    assert [v for _, v in k.olay("yazi-sil")] == [{"id": g[1][0]}]


async def test_eski_silme_yeni_yaziyi_silmez_id_ile(monkeypatch):
    # kaynak arada kaybolur (eskinin silmesi planlı), sonra yeni cümle gelir: silme yalnız eski id'yi hedefler
    seg = [(0.0, 1.0, L1), (1.6, 4.0, L2)]
    k = await kos(monkeypatch, seg, 9.0)
    g = gorunenler(k)
    assert len(g) == 2
    for _, v in k.olay("yazi-sil"):
        assert v["id"] in {g[0][0], g[1][0]}
    assert g[0][2] is not None and g[0][2] <= g[1][1] + 1e-9     # çakışma yok
    assert g[1][2] is not None and g[1][2] > g[1][1]


async def test_tek_kareli_titreme_gosterilmez_ve_silme_yok(monkeypatch):
    k = await kos(monkeypatch, [(1.0, 1.1, "Flash")], 5.0)
    assert not k.olay("yazi") and not k.olay("yazi-sil")


async def test_t_gel_stabilizator_ikinci_kareyi_beklese_de_ilk_gorulmedir(monkeypatch):
    # gecikme 0: çeviri anında hazır, yine de L = t_hazir - t_gel = 1 kare; kaynak 2 sn -> ~2 sn görünür
    k = await kos(monkeypatch, [(1.0, 3.0, L1)], 8.0, gecikme=0.0)
    (kimlik, bas, son), = gorunenler(k)
    assert abs(bas - 1.25) <= TIK + 1e-9
    assert abs((son - bas) - 2.0) <= DT + TIK + 1e-9


def _oge(metin, y):
    return Satir(metin, 0.02, y, 0.3, 0.04)


async def test_ekran_ogesi_ayni_kayik_kuralla_kalkar(monkeypatch):
    a, b = "Collect three herbs near river", "Return to the base camp quickly"
    seg = [(0.0, 2.0, _oge(a, 0.1)), (0.0, 7.0, _oge(b, 0.3))]
    k = await kos(monkeypatch, seg, 10.0, ayar={"ekrani_cevir": True})
    ekranlar = k.olay("ekran")
    assert ekranlar, "ekran olayı yok"
    t_ilk, ilk = ekranlar[0]
    ids = {o["metin"]: o["id"] for o in ilk["ogeler"]}
    assert set(ids) == {f"[TR] {a}", f"[TR] {b}"}
    # a öğesi oyunda 2 sn görünüyordu: bizde de ~2 sn (±1 kare), doğru id kalkar, b kalır
    kalkis = [(t, v) for t, v in ekranlar if len(v["ogeler"]) == 1]
    assert kalkis, "a öğesi hiç kalkmadı"
    t_kalk, v = kalkis[0]
    assert v["ogeler"][0]["id"] == ids[f"[TR] {b}"]
    assert abs((t_kalk - t_ilk) - 2.0) <= DT + 2 * TIK + 1e-9
    # b de sonunda kendi süresiyle (7 sn) kalkar
    (t_sil, _), = k.olay("ekran-sil")
    assert abs((t_sil - t_ilk) - 7.0) <= DT + 2 * TIK + 1e-9


async def test_ekran_ogesi_kisa_ise_en_az_gosterim(monkeypatch):
    seg = [(0.0, 0.4, _oge("Quick menu entry", 0.3))]
    k = await kos(monkeypatch, seg, 8.0, gecikme=0.0, ayar={"ekrani_cevir": True})
    (t_ilk, _), = k.olay("ekran")
    (t_sil, _), = k.olay("ekran-sil")
    assert abs((t_sil - t_ilk) - 0.8) <= TIK + 1e-9 or t_sil - t_ilk >= 0.8 - 1e-9


# ---------- ayar ----------

def test_en_az_ms_ayari_aralik():
    g = lambda v: {"gorunum": {"en_az_ms": v}}   # noqa: E731
    assert en_az_ms_ayari({}) == 800
    assert en_az_ms_ayari(g(0)) == 0 and en_az_ms_ayari(g(3000)) == 3000
    assert en_az_ms_ayari(g(3001)) == 800 and en_az_ms_ayari(g(-1)) == 800
    assert en_az_ms_ayari(g("x")) == 800 and en_az_ms_ayari(g(True)) == 800


def test_ayarlar_duzelt_en_az_ms():
    assert ayarlar.VARSAYILAN_GORUNUM["en_az_ms"] == 800
    import copy

    def d(v):
        a = copy.deepcopy(VARSAYILAN)
        a["gorunum"]["en_az_ms"] = v
        return ayarlar.duzelt(a)["gorunum"]["en_az_ms"]
    assert d(9999) == 800 and d(-3) == 800 and d("x") == 800
    assert d(1500) == 1500 and d(0) == 0


def test_sunucu_gorunum_en_az_ms_dogrulama():
    from kopru import sunucu
    assert sunucu._gorunum_gecerli({"en_az_ms": 0}) and sunucu._gorunum_gecerli({"en_az_ms": 3000})
    assert not sunucu._gorunum_gecerli({"en_az_ms": 3001}) and not sunucu._gorunum_gecerli({"en_az_ms": -5})
    assert not sunucu._gorunum_gecerli({"en_az_ms": "800"})
