# SPDX-License-Identifier: AGPL-3.0-only
"""PROTOKOL 20.4: çeviri öncesi/sonrası temizlik katmanı (her motor için)."""
import pytest

from kopru import sozluk as sozluk_mod
from kopru.ceviri import on_katman
from kopru.ceviri.temel import Baglam, Ceviri
from kopru.ceviri.yonetici import CeviriYoneticisi
from kopru.isleme import okuma_gurultusu_mu
from tests.test_kayik_zaman import gorunenler, kos


class Kayitci:
    """Talimat almayan motor (yerel/DeepL gibi): gelen metni ve sözlüğü kaydeder, yer tutucuyu korur."""
    kod, ad, anahtar_gerekli, cevrimdisi = "kayitci", "Kayıtçı", False, True

    def __init__(self, cevap=None):
        self.gelen, self.sozlukler, self.cevap = [], [], cevap or {}

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False):
        self.gelen += list(metinler)
        self.sozlukler.append(sozluk)
        out = []
        for m in metinler:
            korunan, harita = sozluk_mod.koru(m, sozluk)
            out.append(Ceviri(sozluk_mod.geri_koy(self.cevap.get(korunan, f"[TR] {korunan}"), harita)))
        return out


class BaglamliKayitci(Kayitci):
    baglam_destekler = True

    def __init__(self, cevap=None):
        super().__init__(cevap)
        self.baglamlar = []

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False, baglam=None):
        self.baglamlar.append(baglam)
        self.gelen += list(metinler)
        return [Ceviri(self.cevap.get(m, f"[TR] {m}")) for m in metinler]


# ---------------- saf işlevler ----------------
@pytest.mark.parametrize("metin", ["N", "NW", "SE 120°", "$1,250", "+$500", "30/120", "24 | 120", "x3", "02:15",
                                   "1:02:33", "85%", "HP 100", "Lv. 12", "250 XP", "1.2 mi", "45 mph"])
def test_hud_cevrilmez(metin):
    assert on_katman.hud_mu(metin) and okuma_gurultusu_mu(metin)


@pytest.mark.parametrize("metin", ["Hope", "North Point", "Get to the boat", "Ammo Shop", "New Austin"])
def test_hud_olmayan_yazi_cevrilir(metin):
    assert not on_katman.hud_mu(metin) and not okuma_gurultusu_mu(metin)


@pytest.mark.parametrize("a,b,beklenen", [
    ("I told you we should", "never have come here.", True),
    ("If you see Dutch,", "Tell him I'm gone.", True),
    ("We have to go and", "and find the others.", True),
    ("I told you.", "never mind.", False),
    ("Where were you?", "I was at the ranch.", False),
    ("We need to talk", "- Not now.", False),
    ("We need to talk", "I know.", False),
])
def test_bolunmus_cumle_sezgisi(a, b, beklenen):
    assert on_katman.bolunmus_mu(a, b) is beklenen


def test_bagirma_cumle_duzenine_adlar_ve_kisaltmalar_korunur():
    assert on_katman.bagirma_duzelt("GET DOWN! THEY'RE SHOOTING AT US") == ("Get down! They're shooting at us!", True)
    s, b = on_katman.bagirma_duzelt("DUTCH, I'M TELLING YOU, THE FBI IS IN VICE CITY", ["Dutch", "Vice City"])
    assert b and s == "Dutch, I'm telling you, the FBI is in Vice City!"
    assert on_katman.bagirma_duzelt("PRESS ✕ TO OPEN THE DOOR.")[0] == "Press ✕ to open the door."
    assert on_katman.bagirma_duzelt("Get down!") == ("Get down!", False)
    assert on_katman.bagirma_duzelt("FBI")[1] is False and on_katman.bagirma_duzelt("FBI, SWAT")[1] is False


def test_ad_olan_sozcukler():
    bilinen = ["Hope", "Rook", "Grace", "Dutch", "Valentine", "Mercy"]
    assert on_katman.adlari_bul("Tell Hope we are leaving.", bilinen) == ["Hope"]
    assert on_katman.adlari_bul("Hope is waiting at the ranch.", bilinen) == ["Hope"]
    assert on_katman.adlari_bul("Hope you are right.", bilinen) == []           # sözcük kullanımı
    assert on_katman.adlari_bul("There is no hope left.", bilinen) == []         # küçük harf: sözcük
    assert on_katman.adlari_bul("We ride to Valentine at dawn.", bilinen) == ["Valentine"]
    assert on_katman.adlari_bul("Show some mercy, Mercy.", bilinen) == ["Mercy"]
    assert on_katman.adlari_bul("I met Grace and Rook on Monday.", []) == ["Grace", "Rook"]   # cümle ortası büyük harf
    assert on_katman.adlari_bul("THEY ARE COMING", bilinen) == []


@pytest.mark.parametrize("terim,ek,beklenen", [
    ("Ölü Göz", "yu", "ü"), ("Ölü Göz", "a", "e"), ("Ölü Göz", "da", "de"), ("Ölü Göz", "la", "le"),
    ("Vice City", "da", "de"), ("Rook", "dan", "tan"), ("Arthur", "nın", "un"), ("Kasaba", "ı", "yı"),
    ("Kasaba", "de", "da"), ("Saint Denis", "a", "e"), ("Grace", "yi", "i"), ("Ölü Göz", "DA", "DE"),
    ("Kamp", "teki", "taki"), ("Ölü Göz", "xyz", "xyz"),
])
def test_turkce_ek_uyumu(terim, ek, beklenen):
    assert on_katman.ek_kur(terim, ek) == beklenen


def test_yer_tutucuya_bitisen_ek_kesmeyle_ayrilir():
    assert sozluk_mod.geri_koy("[[T0]]u kullan", {"[[T0]]": "Ölü Göz"}) == "Ölü Göz'u kullan"
    assert sozluk_mod.geri_koy("[[T0]]da kal", {"[[T0]]": "kasaba"}) == "kasabada kal"


def test_ad_korumasi_buyuk_kucuk_harfe_duyarli():
    d = sozluk_mod.Sozluk({"Hope": "Hope"}, {"Hope"})
    korunan, harita = sozluk_mod.koru("hope you know Hope.", d)
    assert korunan == "hope you know [[T0]]." and harita == {"[[T0]]": "Hope"}


# ---------------- yönetici: her motor ----------------
async def test_terim_ekli_ceviri_dogru_ek_alir():
    m = BaglamliKayitci({"Use Dead Eye now.": "Hemen Dead Eye'ı kullan."})
    y = CeviriYoneticisi(m, None, None)
    y.terimler = {"Dead Eye": "Ölü Göz"}
    (c,) = await y.cevir(["Use Dead Eye now."], "en", "tr")
    assert c.metin == "Hemen Ölü Göz'ü kullan."


async def test_cevrimdisi_motorda_terim_yer_tutucu_ve_ek():
    m = Kayitci({"Use [[T0]] now.": "Hemen [[T0]]'yu kullan."})
    y = CeviriYoneticisi(m, None, None)
    y.terimler = {"Dead Eye": "Ölü Göz"}
    (c,) = await y.cevir(["Use Dead Eye now."], "en", "tr")
    assert c.metin == "Hemen Ölü Göz'ü kullan."


async def test_bilinen_ad_cevrimdisi_motorda_korunur_llmde_known_names():
    bilgi = {"karakterler": [{"ad": "Hope", "cinsiyet": "k"}, {"ad": "Dutch van der Linde", "cinsiyet": "e"}],
             "yerler": ["Valentine"]}
    m = Kayitci({"Tell [[T2]] to meet [[T1]] in [[T0]].": "[[T2]]'ya söyle, [[T0]]'te [[T1]] ile buluşsun."})
    y = CeviriYoneticisi(m, None, None)
    y.oyun_bilgisi = bilgi
    (c,) = await y.cevir(["Tell Hope to meet Dutch in Valentine."], "en", "tr")
    assert set(m.sozlukler[-1].adlar) == {"Hope", "Dutch", "Valentine"}
    assert "Hope" in c.metin and "Valentine'de" in c.metin and "Umut" not in c.metin
    (c2,) = await y.cevir(["Hope you are right."], "en", "tr")    # sözcük kullanımı: korunmaz
    assert m.sozlukler[-1] == {}
    llm = BaglamliKayitci()
    y2 = CeviriYoneticisi(llm, None, None)
    y2.oyun_bilgisi = bilgi
    await y2.cevir(["Tell Hope to meet Dutch in Valentine."], "en", "tr")
    assert llm.baglamlar[-1].satir_adlari == ["Hope", "Dutch", "Valentine"]
    from kopru.ceviri import istem
    metin = istem.kullanici_metni(["x"], llm.baglamlar[-1])
    assert "KNOWN NAMES" in metin and "Hope, Dutch, Valentine" in metin
    assert "Places, gangs" in istem.sabit_istem("en", "tr", {}, False, llm.baglamlar[-1])


async def test_dugme_belirteci_yerinde_kalir_ve_tekrar_onbellekten():
    from kopru.onbellek import Onbellek
    m = Kayitci({"Press ✕ to open the door.": "Kapıyı açmak için bas."})
    y = CeviriYoneticisi(m, None, Onbellek(":memory:"))
    (c,) = await y.cevir(["Press ✕ to open the door."], "en", "tr")
    assert "✕" in c.metin
    (c2,) = await y.cevir(["Press ✕ to open the door."], "en", "tr")
    assert c2.metin == c.metin and len(m.gelen) == 1    # tekrar eden satır motora gitmez


def test_altyazi_hazirla_bagirmada_bilinen_adlar():
    y = CeviriYoneticisi(Kayitci(), None, None)
    y.oyun_bilgisi = {"karakterler": [{"ad": "Arthur Morgan"}], "yerler": ["Saint Denis"]}
    assert y.altyazi_hazirla("ARTHUR, GET TO SAINT DENIS NOW") == "Arthur, get to Saint Denis now!"


# ---------------- uçtan uca (kare -> kuyruk -> yayın) ----------------
async def test_bolunmus_cumle_tek_ceviri_iki_kartta(monkeypatch):
    seg = [(0.0, 2.0, "I told you we should"), (2.0, 4.0, "never have come here.")]
    k = await kos(monkeypatch, seg, 7.0, gecikme=0.3)
    yazilar = [v for _, v in k.olay("yazi")]
    tam = "[TR] I told you we should never have come here."
    assert yazilar[-1]["metin"] == tam and yazilar[-1]["asil"] == "I told you we should never have come here."
    ilk_id = yazilar[0]["id"]
    # ilk kart ekrandayken birleşik çeviri gelince yerinde (devam) güncellenir: cümle iki kart boyunca tam görünür
    assert any(v["id"] == ilk_id and v["metin"] == tam and v["devam"] for v in yazilar)
    assert len(gorunenler(k)) == 1   # ikinci kart aynı metinle zıplamadan birleşti


async def test_bagirma_motora_cumle_duzeninde_gider(monkeypatch):
    seg = [(0.0, 2.0, "GET DOWN! THEY'RE SHOOTING AT US")]
    k = await kos(monkeypatch, seg, 4.0, gecikme=0.2)
    assert [v["metin"] for _, v in k.olay("yazi")][0] == "[TR] Get down! They're shooting at us!"
