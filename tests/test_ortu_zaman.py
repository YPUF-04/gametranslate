# SPDX-License-Identifier: AGPL-3.0-only
"""PROTOKOL §16: gerçek kullanım (PS5 → HDMI → LG TV) geri bildirimi.

1) Türkçe yazı İngilizcenin üstünü örter (kutu, zemin rengi, yazı boyu kutuya sığar).
2) Düğme simgeleri (✕ ○ △ □, [X], R2, okuma yanlışları ®/©/Δ) korunur; uçtaki gerçek simge örtülmez.
3) Emoji/HUD simgeleri ve sayılar çeviriye gitmez.
4) Hızlı diyalog (1, 1, 2, 1 sn; çeviri 1,5 sn): hiçbir satır atlanmaz, sırayla, okunur sürede görünür.
"""
import asyncio

import pytest
from PIL import Image

from kopru import ayarlar, dugmeler, isleme, sira
from kopru.ayarlar import VARSAYILAN
from kopru.ceviri import _http
from kopru.ceviri.gemini import GeminiMotoru
from kopru.ceviri.temel import AgHatasi, Ceviri
from kopru.ceviri.yonetici import CeviriYoneticisi
from kopru.isleme import Isleme, okuma_gurultusu_mu, ortu_kutusu, satir_temizle
from kopru.katman import mantik
from kopru.okuma import Satir
from kopru.sira import GosterimSirasi, SiraSatiri, okuma_tabani
from kopru.yayin import Yayin

from .test_kayik_zaman import DT, gorunenler, kos

# ---------- 3) okuma gürültüsü (gerçekçi OCR çıktıları) ----------

ATILIR = ["♥♥♥ 3/5", "12:45", "X: 120 Y: 45", "x3", "!!!", "HP ||||||||||| 80%", "⭐⭐⭐", "🎮 🔫 💰",
          "+250", "100%", "3/10", "● ● ●", "★ 1200", "▲▼◀▶", "✕ ○", "[X]", "- - -", "|||", "»»»", "1 2 3 4"]
KALIR = {"Press [X] to Accept": "Press [X] to Accept", "△ Back": "△ Back", "R2 Aim": "R2 Aim",
         "® Cancel 🎮": "○ Cancel", "Hello 😀 there": "Hello there", "✦ Quest Updated ✦": "Quest Updated",
         "Score: 1200 ⭐⭐⭐": "Score: 1200", "→ Next": "→ Next", "OK": "OK", "Δ Map": "△ Map",
         "Press ✕ to continue": "Press ✕ to continue", "Hold L2 to aim": "Hold L2 to aim",
         "Wait... what?!": "Wait... what?!", "Ellie's backpack": "Ellie's backpack",
         "Level 12": "Level 12", "Move, move, move!": "Move, move, move!", "❤️ Health restored": "Health restored", "© Options": "○ Options"}


@pytest.mark.parametrize("ham", ATILIR)
def test_gurultu_satiri_cevrilmez(ham):
    assert okuma_gurultusu_mu(ham), ham
    assert satir_temizle(Satir(ham, 0, 0, 0.1, 0.05)) is None


@pytest.mark.parametrize("ham,temiz", KALIR.items())
def test_kelime_kalir_simge_silinir(ham, temiz):
    assert not okuma_gurultusu_mu(ham), ham
    assert satir_temizle(Satir(ham, 0, 0, 0.1, 0.05)).metin == temiz


def test_dugme_belirteci_ve_yanlis_okumalar():
    for t, n in [("✕", "✕"), ("×", "✕"), ("®", "○"), ("©", "○"), ("@", "○"), ("Δ", "△"), ("☐", "□"),
                 ("[X]", "[X]"), ("<E>", "<E>"), ("(A)", "(A)"), ("[®]", "[○]"), ("R2", "R2"), ("OPTIONS", "OPTIONS"),
                 ("✕'e", "✕"), ("R2'ye", "R2"), ("[X]:", "[X]"), ("←", "←")]:
        assert dugmeler.belirtec(t) == n, t
    for t in ("X", "Press", "R2D2", "O", "[Space bar]", "a"):
        assert dugmeler.belirtec(t) is None, t


def test_ceviride_kaybolan_dugme_geri_konur():
    assert dugmeler.dugme_koru("Press ✕ to Accept", "Kabul etmek için ✕'e bas") == "Kabul etmek için ✕'e bas"
    assert dugmeler.dugme_koru("△ Back", "Geri") == "△ Geri"
    assert dugmeler.dugme_koru("Aim R2", "Nişan al") == "Nişan al R2"
    assert dugmeler.dugme_koru("Hello there", "Merhaba") == "Merhaba"


async def test_yonetici_dugmeyi_korur():
    class Unutkan:
        kod, ad, anahtar_gerekli, cevrimdisi = "u", "U", False, True

        async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False):
            return [Ceviri("Geri dön") for _ in metinler]
    (c,) = await CeviriYoneticisi(Unutkan(), None, None).cevir(["△ Go back"])
    assert c.metin == "△ Geri dön"


def test_istem_dugme_kurali_var():
    from kopru.ceviri import istem
    s = istem.sistem_istemi("en", "tr", {}, False, None)
    assert "BUTTON PROMPTS" in s and "✕ ○ △ □" in s


# ---------- 4) sıra: hiçbir satır atlanmaz ----------

def _benzet(gel, git, metinler, gecikme, son=None, en_az=0.8, adim=0.05):
    """Saf kuyruk benzetimi: satır i, gel[i]'de görülür, git[i]'de gider; çevirisi gecikme[i] sonra hazır."""
    q = GosterimSirasi(en_az)
    ss, olay, t = [], [], 0.0
    son = son if son is not None else max(git) + 10
    while t <= son + 1e-9:
        for i in range(len(gel)):
            if abs(t - gel[i]) < 1e-6:
                if ss and ss[-1].git is None:
                    ss[-1].git, ss[-1].git_tur = t, "yeni"
                ss.append(q.ekle(SiraSatiri(f"a{i}", gel[i])))
            if abs(t - (gel[i] + gecikme[i])) < 1e-6:
                ss[i].hazir, ss[i].metin = t, metinler[i]
            if abs(t - git[i]) < 1e-6 and ss[i].git is None and (i + 1 >= len(gel) or gel[i + 1] > git[i] + 1e-6):
                ss[i].git, ss[i].git_tur = t, "kayip"
        for e, s in q.adim(t):
            olay.append((round(t, 3), e, s.id))
        t = round(t + adim, 6)
    return olay


def _gorunum_sureleri(olay):
    """[(id, baş, son)] — 'goster' öncekini kapatır, 'sil' kapatır."""
    out = []
    for t, e, kim in olay:
        if e == "goster":
            if out and out[-1][2] is None:
                out[-1][2] = t
            out.append([kim, t, None])
        elif e == "sil":
            for o in out:
                if o[0] == kim and o[2] is None:
                    o[2] = t
    return out


def test_bir_bir_iki_bir_saniye_ceviri_bir_bucuk_saniye_hepsi_sirayla():
    metinler = ["Get down!", "Move, move!", "They're flanking us", "Go now!"]
    olay = _benzet([0, 1, 2, 4], [1, 2, 4, 5], metinler, [1.5] * 4)
    g = _gorunum_sureleri(olay)
    assert [k for k, _, _ in g] == ["a0", "a1", "a2", "a3"]                      # hepsi, sırayla
    for (k, bas, bit), m in zip(g, metinler):
        assert bit is not None and bit - bas >= okuma_tabani(m, 0.8) - 1e-6 >= 1.2 - 1e-6, (k, bit - bas)
    for a, b in zip(g, g[1:]):
        assert abs(a[2] - b[1]) < 1e-6                                          # boşluk yok, çakışma yok
    assert [e for _, e, _ in olay].count("sil") == 1                             # yalnız sonuncu silinir


def test_geride_kalinca_satir_atmadan_yetisir():
    # ilk çeviri 4 sn (yavaş istek), sonrakiler 0,6 sn: arkadakiler hazır bekler, hiçbiri atlanmaz,
    # her biri okuma tabanı kadar görünür ve kuyruk kısa aralarla yetişir (gecikme azalır)
    gel = [0, 1, 2, 3, 4, 5, 14]
    git = [1, 2, 3, 4, 5, 6, 17]
    metinler = ["Line number one here", "Second one", "Third line of dialogue", "Four", "Five is short",
                "Six six six six", "Seven, the last one in a long scene"]
    olay = _benzet(gel, git, metinler, [4.0, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6])
    g = _gorunum_sureleri(olay)
    assert [k for k, _, _ in g] == [f"a{i}" for i in range(7)]
    for (k, bas, bit), m in zip(g, metinler):
        assert bit - bas >= okuma_tabani(m, 0.8) - 1e-6, (k, bit - bas)
    gecikme = [bas - gel[int(k[1:])] for k, bas, _ in g]
    assert gecikme[0] == pytest.approx(4.0) and gecikme[-1] < 1.0                # yetişti


def test_tek_satir_en_az_ms_ve_sifir():
    assert _gorunum_sureleri(_benzet([1], [1.3], ["Quick"], [0.2]))[0][2] - 1.2 == pytest.approx(0.8)
    g = _gorunum_sureleri(_benzet([1], [1.3], ["Quick"], [0.2], en_az=0.0))
    assert g[0][2] - g[0][1] == pytest.approx(0.3)                               # taban yok: oyundaki süre
    assert okuma_tabani("x" * 200, 0.8) == sira.OKUMA_EN_COK_S and okuma_tabani("x", 0.0) == 0.0


def test_cevirisi_basarisiz_satir_kuyrugu_tikamaz():
    q = GosterimSirasi(0.8)
    a, b = q.ekle(SiraSatiri("a1", 0.0)), q.ekle(SiraSatiri("a2", 1.0))
    a.git, a.git_tur = 1.0, "yeni"
    a.hata = True
    b.hazir, b.metin = 1.5, "İkinci"
    assert [(e, s.id) for e, s in q.adim(1.5)] == [("goster", "a2")]


async def test_kare_dongusu_ceviriyi_beklemez_hizli_diyalog_hepsi_gorunur(monkeypatch):
    # gerçek boru hattı (sahte saat): 1, 1, 2, 1 sn'lik satırlar, her çeviri 1,5 sn
    L = ["Get down right now!", "Move, move, move!", "They're flanking us from the left", "Go now!"]
    seg = [(0.0, 1.0, L[0]), (1.0, 2.0, L[1]), (2.0, 4.0, L[2]), (4.0, 5.0, L[3])]
    k = await kos(monkeypatch, seg, 12.0, gecikme=1.5)
    g = gorunenler(k)
    assert [v["asil"] for _, v in k.olay("yazi") if not v["devam"]] == L          # hiçbiri atlanmadı, sırayla
    for kim, bas, son in g:
        assert son is not None and son - bas >= 1.2 - 1e-9, (kim, son - bas)
    for a, b in zip(g, g[1:]):
        assert a[2] == b[1]
    assert g[0][1] - 0.0 <= 1.5 + DT + 0.1                                       # ilk satır ~1,5 sn gecikmeyle


# ---------- 1/2) örtü ----------

class Ekran:
    """Düz renkli kare + istenen satırlar."""

    def __init__(self, satirlar, renk=(200, 200, 200)):
        self.satirlar, self.renk = satirlar, renk

    def kare(self):
        return Image.new("RGB", (320, 180), self.renk)

    def oku(self, resim):
        return list(self.satirlar)


class TrMotor:
    kod, ad, anahtar_gerekli, cevrimdisi = "tr", "Tr", False, True

    def __init__(self, sozluk=None):
        self.sozluk = sozluk or {}

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False):
        return [Ceviri(self.sozluk.get(m, "Türkçe " + m)) for m in metinler]


async def _calistir(satirlar, ayar=None, renk=(200, 200, 200), motor=None, kare=3):
    e = Ekran(satirlar, renk)
    y = Yayin()
    q = y.abone_ol()
    saat = {"t": 0.0}
    a = {**VARSAYILAN, "ekrani_cevir": False, "kaynak": "pencere:1", **(ayar or {})}
    isl = Isleme(e.kare, e, CeviriYoneticisi(motor or TrMotor(), None, None), y, lambda: a, saat=lambda: saat["t"])
    for _ in range(kare):
        await isl.adim()
        saat["t"] += DT
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out, isl


async def test_altyazi_orijinalin_ustunu_orter_kutu_zemin_renk():
    s = Satir("We have to go now", 0.3, 0.8, 0.4, 0.05)
    olaylar, _ = await _calistir([s], renk=(230, 230, 230))
    (v,) = [v for o, v in olaylar if o == "yazi"]
    o = v["ortu"]
    assert o["x"] < 0.3 and o["y"] < 0.8 and o["x"] + o["g"] > 0.7 and o["y"] + o["y2"] > 0.85   # kaynağı tümüyle kaplar
    assert o["g"] < 0.43 and o["y2"] < 0.07                                                        # ama yalnız biraz dolgulu
    assert o["zemin"] == "#E6E6E6" and o["renk"] == "#111111"          # açık zemin -> koyu yazı
    assert o["metin"] == v["metin"] and o["opaklik"] >= 0.9 and o["satir"] == 1


async def test_koyu_zeminde_kullanici_yazi_rengi_ve_cubuk_kipinde_ortu_yok():
    s = Satir("We have to go now", 0.3, 0.8, 0.4, 0.05)
    olaylar, _ = await _calistir([s], renk=(10, 12, 20))
    (v,) = [v for o, v in olaylar if o == "yazi"]
    assert v["ortu"]["renk"] == "#FFFFFF" and v["ortu"]["zemin"] == "#0A0C14"
    cubuk = {**VARSAYILAN["gorunum"], "yerlesim": "cubuk"}
    olaylar, _ = await _calistir([s], ayar={"gorunum": cubuk})
    (v,) = [v for o, v in olaylar if o == "yazi"]
    assert "ortu" not in v                                              # eski çubuk yerleşimi aynen


async def test_bas_ve_son_dugme_ortunun_disinda_kalir():
    # winocr kelime kutuları: "△" ve "R2" gerçek simge, örtülmez; metinde de ikinci kez yazılmaz
    kel = (("△", 0.30, 0.80, 0.02, 0.05), ("Back", 0.33, 0.80, 0.06, 0.05), ("to", 0.40, 0.80, 0.03, 0.05),
           ("menu", 0.44, 0.80, 0.06, 0.05), ("R2", 0.52, 0.80, 0.03, 0.05))
    s = Satir("△ Back to menu R2", 0.30, 0.80, 0.25, 0.05, kelimeler=kel)
    m = TrMotor({"△ Back to menu R2": "△ Menüye dön R2"})
    olaylar, _ = await _calistir([s], motor=m)
    (v,) = [v for o, v in olaylar if o == "yazi"]
    o = v["ortu"]
    assert o["x"] >= 0.32 and o["x"] + o["g"] <= 0.52 + 1e-9            # simgelerin arasında
    assert v["metin"] == "△ Menüye dön R2" and o["metin"] == "Menüye dön"


async def test_ortadaki_dugme_ortulur_metinde_kalir():
    kel = (("Press", 0.30, 0.80, 0.06, 0.05), ("✕", 0.37, 0.80, 0.02, 0.05), ("to", 0.40, 0.80, 0.03, 0.05),
           ("Accept", 0.44, 0.80, 0.08, 0.05))
    s = Satir("Press × to Accept", 0.30, 0.80, 0.22, 0.05, kelimeler=kel)      # OCR ✕'yi × okudu
    m = TrMotor({"Press ✕ to Accept": "Kabul etmek için ✕'e bas"})
    olaylar, _ = await _calistir([s], motor=m)
    (v,) = [v for o, v in olaylar if o == "yazi"]
    assert v["asil"] == "Press ✕ to Accept" and v["ortu"]["metin"] == "Kabul etmek için ✕'e bas"
    assert v["ortu"]["x"] < 0.30


def test_ortu_kutusu_cok_satir_ve_resimsiz():
    a, b = Satir("first line", 0.2, 0.7, 0.5, 0.04), Satir("second line", 0.25, 0.75, 0.4, 0.04)
    k = ortu_kutusu([a, b], None)
    assert k["satir"] == 2 and k["zemin"] == isleme.ORTU_ZEMIN_YEDEK and k["bas"] is None
    assert k["x"] < 0.2 and k["y"] < 0.7 and k["x"] + k["g"] > 0.7 and k["y"] + k["y2"] > 0.79


async def test_ekran_ogesi_ortusu():
    s = Satir("Collect three herbs near river", 0.05, 0.1, 0.3, 0.04)
    e = Ekran([s], (40, 40, 40))
    y = Yayin()
    q = y.abone_ol()
    saat = {"t": 0.0}
    a = {**VARSAYILAN, "ekrani_cevir": True, "kisa_aciklama": False, "kaynak": "pencere:1"}
    isl = Isleme(e.kare, e, CeviriYoneticisi(TrMotor(), None, None), y, lambda: a, saat=lambda: saat["t"])
    for _ in range(4):
        await isl.adim()
        saat["t"] += DT
    ekran = []
    while not q.empty():
        o, v = q.get_nowait()
        if o == "ekran":
            ekran.append(v)
    oge = ekran[-1]["ogeler"][0]
    assert oge["ortu"]["zemin"] == "#282828" and oge["ortu"]["x"] < 0.05 and oge["ortu"]["metin"] == oge["metin"]


def test_ortu_yerlesim_kutuya_sigar_sigmazsa_buyur():
    olc = lambda t, px: len(t) * px * 0.5   # noqa: E731
    r = mantik.ortu_yerlesim("Hadi gidelim", olc, 400, 60, 1, 16)
    assert not r["buyudu"] and len(r["satirlar"]) == 1 and r["px"] <= 48 and olc(r["satirlar"][0], r["px"]) <= 400
    r = mantik.ortu_yerlesim("Bu çok uzun bir Türkçe çeviri cümlesi ve kutuya sığmaz", olc, 200, 40, 1, 16)
    assert r["buyudu"] and r["px"] == 16 and r["y2"] > 40 and all(olc(s, 16) <= 200 or " " not in s for s in r["satirlar"])
    assert " ".join(r["satirlar"]) == "Bu çok uzun bir Türkçe çeviri cümlesi ve kutuya sığmaz"   # kelime bölünmez


def test_katman_zamanlayici_ortuyu_tasir():
    z = mantik.Zamanlayici(saat=lambda: 0.0)
    o = {"x": 0.1, "y": 0.8, "g": 0.4, "y2": 0.06, "zemin": "#101010", "renk": "#FFFFFF", "metin": "Merhaba"}
    z.olay("yazi", {"id": "a1", "metin": "Merhaba", "ortu": o}, 0.0)
    assert z.goruntu(0.0).yazi["ortu"] == o
    z.olay("yazi", {"id": "a1", "metin": "Merhaba!", "ortu": {"x": "bozuk"}, "devam": True}, 0.1)
    assert z.goruntu(0.1).yazi["ortu"] is None


# ---------- ayarlar / API ----------

def test_ayar_yerlesim_ve_karakter_ms():
    import copy
    assert ayarlar.VARSAYILAN_GORUNUM["yerlesim"] == "ustune"
    a = copy.deepcopy(VARSAYILAN)
    a["gorunum"].update(yerlesim="yan", karakter_ms=500)
    d = ayarlar.duzelt(a)["gorunum"]
    assert d["yerlesim"] == "ustune" and d["karakter_ms"] == 60
    a["gorunum"].update(yerlesim="cubuk", karakter_ms=80)
    d = ayarlar.duzelt(a)["gorunum"]
    assert d["yerlesim"] == "cubuk" and d["karakter_ms"] == 80
    from kopru import sunucu
    assert sunucu._gorunum_gecerli({"yerlesim": "cubuk", "karakter_ms": 40})
    assert not sunucu._gorunum_gecerli({"yerlesim": "yan"}) and not sunucu._gorunum_gecerli({"karakter_ms": 10})


async def test_gecikme_bilgisi_asamalar():
    s = Satir("We have to go now", 0.3, 0.8, 0.4, 0.05)
    _, isl = await _calistir([s])
    g = isl.gecikme_bilgisi()
    assert g["olcum"] == 1 and g["kuyruk"] == 0 and g["atlanan"] == 0
    assert g["kararlilik_ms"] == 250 and g["toplam_ms"] == 250 and g["ceviri_ms"] == 0 and g["bekleme_ms"] == 0
    assert set(g) >= {"kare_ms", "okuma_ms"}


# ---------- motor: düşünmesiz istek + açık bağlantı ----------

async def test_gemini_dusunme_duzeyi_tanimazsa_bir_kez_onsuz(monkeypatch):
    """gemini-3.8-flash "minimal"i tanımaz (HTTP 400): artık "low" gider; yine de 400 gelirse onsuz denenir."""
    gelen = []

    async def sahte(url, govde, basliklar, zaman_asimi=8.0, oturum=None):
        gelen.append(govde["generationConfig"].get("thinkingConfig"))
        if govde["generationConfig"].get("thinkingConfig"):
            raise AgHatasi("HTTP 400")
        return {"candidates": [{"content": {"parts": [{"text": '{"ceviriler": ["Merhaba"], "yeni_terimler": []}'}]}}]}
    monkeypatch.setattr(_http, "post_json", sahte)
    m = GeminiMotoru("k")
    (c,) = await m.cevir(["Hello"], "en", "tr", {})
    assert c.metin == "Merhaba" and gelen == [{"thinkingLevel": "low"}, None] and m.dusunme_kapali is False
    await m.cevir(["Hello"], "en", "tr", {})
    assert gelen[-1] is None                       # hatırlandı: yeniden denenmez


async def test_http_oturumu_istekler_arasinda_acik_kalir():
    a, b = _http.ortak_oturum(), _http.ortak_oturum()
    assert a is b and not a.closed
    await _http.ortak_kapat()
    assert a.closed and _http.ortak_oturum() is not a
    await _http.ortak_kapat()
    await asyncio.sleep(0)


async def test_api_durum_gecikme_yalniz_calisirken(aiohttp_client, uygulama_ayari, monkeypatch):
    from kopru import sunucu
    from kopru.ceviri.sahte import SahteMotor
    uygulama_ayari["motor"], uygulama_ayari["yedek_motor"] = "sahte", ""
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=lambda kod, ayar: SahteMotor())
    ist = await aiohttp_client(app)
    d = app[sunucu.DURUM]
    assert "gecikme" not in await (await ist.get("/api/durum")).json()

    class SahteIsleme:
        def gecikme_bilgisi(self):
            return {"toplam_ms": 1700, "ceviri_ms": 1400, "olcum": 3, "kuyruk": 1}
    d.isleme = SahteIsleme()
    monkeypatch.setattr(d, "calisiyor", lambda: True)
    assert (await (await ist.get("/api/durum")).json())["gecikme"]["toplam_ms"] == 1700
