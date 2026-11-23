# SPDX-License-Identifier: AGPL-3.0-only
"""PROTOKOL 19: profesyonel altyazı — istem, hitap hafızası, ad öğrenme, iki aşamalı kalite, okuma temizliği."""
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

from kopru.ayarlar import VARSAYILAN
from kopru.ceviri import _http, claude, gemini, istem
from kopru.ceviri.temel import AgHatasi, Baglam, Ceviri
from kopru.ceviri.yonetici import CeviriYoneticisi, anlamli_fark
from kopru.isleme import Isleme, konusan_ayir, ocr_duzelt, satirlari_birlestir
from kopru.okuma import Satir
from kopru.yayin import Yayin

KOK = Path(__file__).resolve().parents[1]
BOLGE = (0.1, 0.8, 0.5, 0.05)


# ---------- 19.3 okuma temizliği ----------

@pytest.mark.parametrize("gir,cik", [
    ("l think l'm lost.", "I think I'm lost."),
    ("l'll be there, l've seen it, l'd go.", "I'll be there, I've seen it, I'd go."),
    ("| know.", "I know."),
    ("Health | Armor", "Health | Armor"),
    ("Y0U SH0ULD RUN", "YOU SHOULD RUN"),
    ("g0t it", "got it"),
    ("We need 100 men, R2 to aim, L1", "We need 100 men, R2 to aim, L1"),
    ("Get rnore rnoney, rnan.", "Get more money, man."),
    ("Rnission complete", "Mission complete"),
    ("Turn left at the corner, he was born in a barn.", "Turn left at the corner, he was born in a barn."),
    ("modern government return", "modern government return"),
])
def test_ocr_duzelt_temkinli(gir, cik):
    assert ocr_duzelt(gir) == cik


def test_ocr_duzelt_ingilizce_disinda_l_ve_rn_dokunulmaz():
    assert ocr_duzelt("l rnore", "fr") == "l rnore"


def test_satirlari_birlestir():
    assert satirlari_birlestir(["We need to get some-", "thing to eat."]) == "We need to get something to eat."
    assert satirlari_birlestir(["Go to the", "safehouse."]) == "Go to the safehouse."
    assert satirlari_birlestir(["- Hey!", "- What?"]) == "- Hey!\n- What?"
    assert satirlari_birlestir(["Spider-", "Man is here"]) == "Spider- Man is here"   # büyük harf: birleşmez


@pytest.mark.parametrize("gir,cik", [
    ("LUCIA: Hey", ("LUCIA", "Hey")),
    ("LUCIA:Hey there", ("LUCIA", "Hey there")),
    ("Lucia：Hey", (None, "Lucia：Hey")),
    ("LUCIA： Hey", ("LUCIA", "Hey")),
    ("[Jason] Move!", ("Jason", "Move!")),
    ("Lucia Caminos: Yo", ("Lucia Caminos", "Yo")),
    ("12:30 now", (None, "12:30 now")),
    ("Re:Zero", (None, "Re:Zero")),
])
def test_konusan_on_eki(gir, cik):
    assert konusan_ayir(gir) == cik


# ---------- 19.1 istem ----------

def test_istem_kurallari_ve_ornekler_kisa():
    s = istem.sabit_istem("otomatik", "tr", {"Vice City": "Vice City"}, False, Baglam(oyun_ad="GTA VI"))
    for parca in ("EXAMPLES", "Profanity keeps EXACTLY", "max 42 characters per line", "Street talk",
                  "Avoid calques", "500 dolar", "Siktir git arabamdan lan!", "GLOSSARY"):
        assert parca in s
    assert len(istem.ORNEKLER) == 8 and len(s) < 8000      # gecikme/maliyet için kısa


def test_istem_sahne_baglami_hitap_ve_bilinen_adlar():
    b = Baglam(son_satirlar=[(f"LUCIA: a{i}", f"c{i}") for i in range(12)],
               hitaplar=[("Officer Reyes", "Jason", "siz"), ("Lucia", "Jason", "sen")],
               bilinen_adlar={"Port Gellhorn": "Port Gellhorn"})
    k = istem.kullanici_metni(["x"], b)
    assert "a3" not in k and "a4" in k and "a11" in k        # son 8 satır
    assert "Officer Reyes -> Jason: siz" in k and "Lucia -> Jason: sen" in k
    assert "KNOWN NAMES" in istem.sabit_istem("en", "tr", {}, False, b) and "Port Gellhorn" in \
        istem.sabit_istem("en", "tr", {}, False, b)
    # sözlükte olan ad ikinci kez yazılmaz
    assert "KNOWN NAMES" not in istem.sabit_istem("en", "tr", {"Port Gellhorn": "X"}, False, b)


@pytest.mark.parametrize("tr,f", [
    ("Araçtan inmeniz gerekiyor, beyefendi.", "siz"), ("Gelir misiniz?", "siz"), ("Sizinle konuşmalıyım.", "siz"),
    ("Ne yapıyorsun lan?", "sen"), ("Seni seviyorum.", "sen"), ("Hallederim.", None), ("Tamam.", None)])
def test_hitap_sez(tr, f):
    assert istem.hitap_sez(tr) == f


class KayitMotor:
    """Bağlamı kaydeder; istenirse yeni_terimler ve 'derin' yanıtı verir."""
    kod, ad, anahtar_gerekli, cevrimdisi, baglam_destekler = "kayit", "Kayıt", False, False, True
    iyilestirme_destekler = True

    def __init__(self, terimler=None, derin_yanit=None, derin_hata=None):
        self.baglamlar, self.cagrilar = [], []
        self.terimler = terimler or []
        self.derin_yanit, self.derin_hata = derin_yanit, derin_hata

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False, baglam=None):
        self.cagrilar.append(list(metinler))
        self.baglamlar.append(baglam)
        if baglam is not None and baglam.derin:
            if self.derin_hata:
                raise self.derin_hata
            return [Ceviri(self.derin_yanit(m) if callable(self.derin_yanit) else self.derin_yanit) for m in metinler]
        if baglam is not None:
            baglam.yeni_terimler.extend(self.terimler)
        return [Ceviri(f"TR {m}") for m in metinler]


async def test_hitap_hafizasi_konusan_ciftinden():
    m = KayitMotor()
    y = CeviriYoneticisi(m, None, None)
    y.satir_kaydet("a1", "License, sir.", "Ehliyetinizi verir misiniz?", konusan="Officer Reyes")   # önceki yok
    y.satir_kaydet("a2", "Sure.", "Tabii.", konusan="Jason")                                       # sezilemez
    y.satir_kaydet("a3", "Step out.", "Araçtan inin lütfen, beyefendi.", konusan="Officer Reyes")
    y.satir_kaydet("a4", "Whatever you say.", "Sen nasıl istersen.", konusan="Jason")
    assert dict(y.hitaplar) == {("Officer Reyes", "Jason"): "siz", ("Jason", "Officer Reyes"): "sen"}
    await y.cevir(["Hands up."], "en", "tr", konusan="Officer Reyes")
    assert ("Officer Reyes", "Jason", "siz") in m.baglamlar[-1].hitaplar
    assert "Address memory" in istem.kullanici_metni(["x"], m.baglamlar[-1])


async def test_ad_iki_kez_onerilince_ogrenilir():
    m = KayitMotor(terimler=[{"asil": "Port Gellhorn", "ceviri": "Port Gellhorn"}])
    y = CeviriYoneticisi(m, None, None)
    await y.cevir(["Meet me at Port Gellhorn."], "en", "tr")
    assert y.ogrenilen == {}
    await y.cevir(["Port Gellhorn is closed."], "en", "tr")
    assert y.ogrenilen == {"Port Gellhorn": "Port Gellhorn"}
    await y.cevir(["Anything else?"], "en", "tr")
    assert m.baglamlar[-1].bilinen_adlar == {"Port Gellhorn": "Port Gellhorn"}


# ---------- 19.2 iki aşamalı kalite ----------

def test_anlamli_fark():
    assert not anlamli_fark("Hiç kafana takma.", "Hiç kafana takma")       # noktalama
    assert not anlamli_fark("Tamam", "tamam")
    assert anlamli_fark("Kapı kilitli.", "Kapı kilitlenmiş, başka yol bulalım.")


async def test_iyilestir_bir_kez_derin_ve_hafizaya():
    m = KayitMotor(derin_yanit="Hiç kafana takma, ben hallederim.")
    y = CeviriYoneticisi(m, None, None)
    c = await y.iyilestir("Don't even trip, I got this.", "Yolculuk yapma, bende.", "en", "tr", "Lucia")
    assert c is not None and c.metin == "Hiç kafana takma, ben hallederim." and c.kaynak == "motor"
    b = m.baglamlar[-1]
    assert b.derin is True and "REVIEW MODE" in b.ipucu and "Yolculuk yapma, bende." in b.ipucu and "Lucia" in b.ipucu
    assert await y.iyilestir("Don't even trip, I got this.", "x", "en", "tr") is None   # oturumda bir kez
    assert len(m.cagrilar) == 1 and y.iyilestirme_istek == 1 and y.iyilestirilen_sayi == 1


async def test_iyilestirme_dakika_siniri_ve_429_arasi():
    from kopru.ceviri import yonetici as ym
    m = KayitMotor(derin_yanit=lambda x: "farklı bir çeviri " + x)
    y = CeviriYoneticisi(m, None, None)
    for i in range(ym.IYILESTIRME_DAKIKA):
        assert y.iyilestirebilir_mi()
        await y.iyilestir(f"line {i}", "taslak")
    assert not y.iyilestirebilir_mi()
    y2 = CeviriYoneticisi(KayitMotor(derin_hata=AgHatasi("HTTP 429")), None, None)
    assert await y2.iyilestir("a", "b") is None and not y2.iyilestirebilir_mi()


async def test_iyilestir_ayni_ya_da_hata_none():
    m = KayitMotor(derin_yanit="Kapı kilitli")
    y = CeviriYoneticisi(m, None, None)
    assert await y.iyilestir("The door is locked.", "Kapı kilitli.") is None      # aynı (yeniden yayın yok)
    m.derin_hata = AgHatasi("HTTP 503")
    assert await y.iyilestir("Run!", "Koş!") is None                               # hata dışarı taşmaz
    y.yedekte = True
    assert await y.iyilestir("Other", "Diğer") is None and len(m.cagrilar) == 2      # yedekteyken istenmez


class Senaryo:
    def __init__(self, kareler):
        self.kareler, self.i = kareler, -1

    def kare(self):
        self.i += 1
        c = (self.i * 37) % 200 + 20   # her kare farklı: her karede yeniden okunur
        return Image.new("RGB", (64, 36), (c, c, c))

    def oku(self, resim):
        return self.kareler[min(self.i, len(self.kareler) - 1)]


async def _kos(kareler, motor, ayar=None, dt=0.25):
    import asyncio
    s = Senaryo(kareler)
    saat = {"t": 0.0}
    yay = Yayin()
    q = yay.abone_ol()
    a = {**VARSAYILAN, "ekrani_cevir": False, **(ayar or {})}
    isl = Isleme(s.kare, s, CeviriYoneticisi(motor, None, None), yay, lambda: a, saat=lambda: saat["t"])
    out = []
    for _ in kareler:
        await isl.adim()
        for _ in range(5):
            await asyncio.sleep(0)
        while not q.empty():
            o, v = q.get_nowait()
            out.append((saat["t"], o, v))
        saat["t"] += dt
    return out, isl


async def test_isleme_uzun_kalan_satir_yerinde_iyilesir():
    m = KayitMotor(derin_yanit=lambda x: "Hiç kafana takma, ben hallederim.")
    kare = [Satir("Don't even trip, I got this.", *BOLGE)]
    out, isl = await _kos([kare] * 20, m)          # 5 sn ekranda
    yazilar = [(t, v) for t, o, v in out if o == "yazi"]
    ilk = yazilar[0][1]
    assert ilk["metin"] == "TR Don't even trip, I got this." and not ilk["devam"]
    iyi = [(t, v) for t, v in yazilar if v["metin"] == "Hiç kafana takma, ben hallederim."]
    assert iyi and iyi[0][1]["id"] == ilk["id"] and iyi[0][1]["devam"] is True      # aynı id, yerinde
    assert iyi[0][0] - yazilar[0][0] >= 2.5 - 1e-9
    assert sum(1 for t, v in yazilar if v["metin"] == "Hiç kafana takma, ben hallederim." and not v["devam"]) == 0
    assert isl.gecikme_bilgisi()["iyilestirilen"] == 1


async def test_isleme_ayni_iyilestirme_yeniden_yayinlanmaz_ve_hizli_kapali():
    m = KayitMotor(derin_yanit=lambda x: "TR " + x)        # taslağın aynısı
    kare = [Satir("Stay close.", *BOLGE)]
    out, _ = await _kos([kare] * 16, m)
    metinler = [v["metin"] for t, o, v in out if o == "yazi" and not v.get("devam")]
    assert metinler == ["TR Stay close."]
    assert all(v["metin"] == "TR Stay close." for t, o, v in out if o == "yazi")    # titreme yok
    m2 = KayitMotor(derin_yanit="başka")
    await _kos([kare] * 16, m2, {"ceviri_kalitesi": "hizli"})
    assert not any(b is not None and b.derin for b in m2.baglamlar)


async def test_isleme_kisa_satir_dengelide_iyilestirilmez():
    m = KayitMotor(derin_yanit="başka")
    k1, k2 = [Satir("Go!", *BOLGE)], [Satir("Now!", *BOLGE)]
    await _kos([k1] * 6 + [k2] * 6 + [[]] * 4, m)        # her biri ~1,5 sn
    assert not any(b is not None and b.derin for b in m.baglamlar)


async def test_daktilo_bitmemis_cumle_bir_kare_daha_bekler():
    from kopru.ceviri.sahte import SahteMotor
    m = SahteMotor()
    kareler = [[Satir("We need", *BOLGE)], [Satir("We need to get", *BOLGE)], [Satir("We need to get out", *BOLGE)],
               [Satir("We need to get out", *BOLGE)], [Satir("We need to get out", *BOLGE)],
               [Satir("We need to get out of here!", *BOLGE)]]
    out, _ = await _kos(kareler, m)
    ilk = [(t, v) for t, o, v in out if o == "yazi"][0]
    assert ilk[1]["asil"] == "We need to get out"   # büyürken yarım cümle kesinleşmez
    assert ilk[0] == pytest.approx(1.0)            # 3. aynı karede (eskiden 2.)
    m2 = SahteMotor()
    out2, _ = await _kos([[Satir("Go.", *BOLGE)], [Satir("Go. Now!", *BOLGE)], [Satir("Go. Now!", *BOLGE)]], m2)
    assert [t for t, o, v in out2 if o == "yazi"][0] == pytest.approx(0.5)   # cümle bitti: 2 kare yeter


# ---------- motorların derin kipi ----------

async def test_gemini_derin_kip_dusunme_medium_15sn(monkeypatch):
    gorulen = []

    async def sahte(url, govde, basliklar, zaman_asimi=8.0, oturum=None):
        gorulen.append((url, govde.get("generationConfig", {}).get("thinkingConfig"), zaman_asimi))
        return {"candidates": [{"content": {"parts": [{"text": json.dumps({"ceviriler": ["İyi"], "yeni_terimler": []})}]}}]}
    monkeypatch.setattr(_http, "post_json", sahte)
    g = gemini.GeminiMotoru("k", "gemini-3.8-flash")
    await g.cevir(["x"], "en", "tr", {}, baglam=Baglam(derin=True))
    await g.cevir(["x"], "en", "tr", {}, baglam=Baglam())
    assert gorulen[0][1] == {"thinkingLevel": "medium"} and gorulen[0][2] == 15.0
    assert gorulen[1][1] == {"thinkingLevel": "low"} and gorulen[1][2] == gemini.ALTYAZI_SN


async def test_claude_derin_kip_opus_medium():
    class Yanit:
        stop_reason = "end_turn"
        content = [type("B", (), {"type": "text", "text": json.dumps({"ceviriler": ["İyi"], "yeni_terimler": []})})()]

    class Mesajlar:
        def __init__(self):
            self.kw = []

        async def create(self, **kw):
            self.kw.append(kw)
            return Yanit()
    ist = type("I", (), {})()
    ist.messages = Mesajlar()
    c = claude.ClaudeMotoru("k", "claude-haiku-5-5", istemci=ist)
    await c.cevir(["x"], "en", "tr", {}, baglam=Baglam(derin=True))
    await c.cevir(["x"], "en", "tr", {}, baglam=Baglam())
    a, b = ist.messages.kw
    assert a["model"] == "claude-opus-5-5" and a["output_config"] == {"effort": "medium"} and a["timeout"] == 15.0
    assert b["model"] == "claude-haiku-5-5" and b["output_config"] == {"effort": "low"} and "timeout" not in b


def test_ayar_ceviri_kalitesi():
    from kopru import ayarlar
    assert ayarlar.VARSAYILAN["ceviri_kalitesi"] == "dengeli"
    assert ayarlar.duzelt({**ayarlar.VARSAYILAN, "ceviri_kalitesi": "uydurma"})["ceviri_kalitesi"] == "dengeli"


# ---------- 19.4 değerlendirme ----------

def test_ornekler_ve_cevrimdisi_degerlendirme():
    sys.path.insert(0, str(KOK / "araclar"))
    import ceviri_degerlendir as cd
    veri = cd.ornekleri_yukle()
    assert len(veri["ornekler"]) >= 40
    assert {o["tur"] for o in veri["ornekler"]} >= {"altyazi", "menu", "gorev"}
    sonuc, yapi = cd.cevrimdisi(veri)
    assert yapi == [], yapi
    assert all(not r["sorunlar"] for r in sonuc), [r for r in sonuc if r["sorunlar"]]
    # kural denetimi gerçekten yakalıyor
    o = {"asil": "Press ✕ to hotwire the car.", "konusan": None, "kurallar": {"korunacak": ["✕"], "yasak": ["sıcak tel"]}}
    assert cd.kurallari_denetle(o, "Arabayı sıcak tel yapmak için bas, çok uzun bir satır olacak şekilde yazılmış") != []


def test_canli_degerlendirme_anahtarsiz_atlanir(monkeypatch, capsys):
    sys.path.insert(0, str(KOK / "araclar"))
    import ceviri_degerlendir as cd
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert cd.main(["--canli"]) == 0 and "atlandı" in capsys.readouterr().out


async def test_api_ayar_ceviri_kalitesi(aiohttp_client, uygulama_ayari):
    from kopru import sunucu
    from tests.conftest import sahte_fabrika
    ist = await aiohttp_client(sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika))
    assert (await (await ist.get("/api/ayarlar")).json())["ceviri_kalitesi"] == "dengeli"
    r = await ist.post("/api/ayarlar", json={"ceviri_kalitesi": "en_iyi"})
    assert r.status == 200
    assert (await (await ist.get("/api/ayarlar")).json())["ceviri_kalitesi"] == "en_iyi"
    r = await ist.post("/api/ayarlar", json={"ceviri_kalitesi": "uydurma"})
    assert r.status == 400
