# SPDX-License-Identifier: AGPL-3.0-only
"""Sürüm 0.7 (PROTOKOL §12): kendi panelini okumama, cihaza göre kaynak, oyun bilgisi hazırlama."""
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from kopru import oyun_bilgisi, oyunlar, sozluk, sunucu, yakalama
from kopru.ayarlar import VARSAYILAN
from kopru.ceviri.claude import ClaudeMotoru
from kopru.ceviri.deepseek import DeepSeekMotoru
from kopru.ceviri.gemini import GeminiMotoru
from kopru.ceviri.sahte import SahteMotor
from kopru.ceviri.temel import AgHatasi, AnahtarHatasi
from kopru.ceviri.yonetici import CeviriYoneticisi
from kopru.isleme import Isleme
from kopru.okuma import Satir
from kopru.yayin import Yayin
from tests.conftest import sahte_fabrika

# ---------- §12.1 kendi pencerelerini karartma ----------


@pytest.mark.parametrize("baslik", ["AltYazıKöprüsü - Panel - Google Chrome", "ALTYAZIKÖPRÜSÜ", "altyazikoprusu",
                                    "AltYaziKoprusu (8642)", "Panel | AltyazıKöprüsü — Mozilla Firefox"])
def test_marka_basligi_taninir(baslik):
    assert yakalama.marka_baslikli_mi(baslik)


@pytest.mark.parametrize("baslik", ["Cyberpunk 2077", "PS Remote Play", "AYK katmani", "", "Alt Yazı"])
def test_marka_olmayan_baslik_taninmaz(baslik):
    assert not yakalama.marka_baslikli_mi(baslik)


def test_marka_sabiti_panelin_marka_js_ile_ayni():
    from pathlib import Path
    js = (Path(yakalama.__file__).parent.parent / "web" / "panel" / "marka.js").read_text(encoding="utf-8")
    assert f'ad: "{yakalama.MARKA}"' in js


def test_ekrana_esle_monitor_ve_pencere_koordinatlari():
    panel = [(1900, 100, 2500, 700)]
    # ikinci monitör (1920,0) 1920x1080: panel kısmen içinde ve kırpılır, koordinatlar monitöre göre
    assert yakalama.ekrana_esle(panel, (1920, 0), (1920, 1080)) == [(0, 100, 580, 700)]
    # birinci monitör: yalnız sağ kenarda 20 px
    assert yakalama.ekrana_esle(panel, (0, 0), (1920, 1080)) == [(1900, 100, 1920, 700)]
    assert yakalama.ekrana_esle(panel, (5000, 0), (1920, 1080)) == []                 # kareyle kesişmiyor
    assert yakalama.ekrana_esle([(110, 160, 210, 260)], (100, 150), (400, 300)) == [(10, 10, 110, 110)]   # pencere iç alanı


def test_karart_kopyada_boyar_ve_kutu_yoksa_ayni_kare():
    r = Image.new("RGB", (100, 100), (200, 200, 200))
    assert yakalama.karart(r, []) is r
    k = yakalama.karart(r, [(10, 10, 40, 40)])
    assert k.getpixel((20, 20)) == (0, 0, 0) and k.getpixel((60, 60)) == (200, 200, 200)
    assert r.getpixel((20, 20)) == (200, 200, 200)                                   # özgün kare bozulmadı


def test_kendi_pencere_kutulari_yalniz_marka_yenileme_ve_haric_pid():
    t = {"t": 0.0}
    pen = [{"hwnd": 1, "baslik": "AltYazıKöprüsü - Chrome", "kutu": (0, 0, 10, 10), "pid": 7},
           {"hwnd": 2, "baslik": "Oyun", "kutu": (0, 0, 99, 99), "pid": 8},
           {"hwnd": 3, "baslik": "AltYazıKöprüsü katman", "kutu": (5, 5, 50, 50), "pid": 99}]
    sayac = {"n": 0}

    def liste():
        sayac["n"] += 1
        return pen
    yakalama._kendi_onbellek["an"] = -1e9
    bos_degil = yakalama.kendi_pencere_kutulari(haric_pid=99, saat=lambda: t["t"], liste=liste)
    assert bos_degil == [(0, 0, 10, 10)]                                              # oyun ve katman süreci sayılmaz
    assert yakalama.kendi_pencere_kutulari(saat=lambda: t["t"], liste=liste) == [(0, 0, 10, 10), (5, 5, 50, 50)]


def test_kendi_pencere_kutulari_yaklasik_1sn_onbellek(monkeypatch):
    t = {"t": 100.0}
    cagri = {"n": 0}

    def sahte():
        cagri["n"] += 1
        return [{"hwnd": 1, "baslik": "AltYazıKöprüsü", "kutu": (0, 0, 5, 5), "pid": 1}]
    monkeypatch.setattr(yakalama, "_pencere_ayrintilari", sahte)
    yakalama._kendi_onbellek.update(an=-1e9, pid=None, kutular=[])
    for _ in range(5):
        yakalama.kendi_pencere_kutulari(saat=lambda: t["t"])
    assert cagri["n"] == 1
    t["t"] += 1.1
    yakalama.kendi_pencere_kutulari(saat=lambda: t["t"])
    assert cagri["n"] == 2
    yakalama._kendi_onbellek.update(an=-1e9, pid=None, kutular=[])


def test_kare_marka_penceresi_siyaha_boyanir(monkeypatch):
    monkeypatch.setattr(yakalama, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(yakalama, "kendi_pencere_kutulari", lambda *a, **k: [(300, 50, 500, 150)])
    kare = Image.new("RGB", (400, 300), (180, 180, 180))
    out = yakalama.kendi_pencerelerini_karart(kare, (200, 0))                      # monitör (200,0)'da başlıyor
    assert out.getpixel((150, 100)) == (0, 0, 0) and out.getpixel((10, 10)) == (180, 180, 180)


# ---------- §12.1 tam ekranda yalnız altyazı bandı ----------

DT = 0.25


class Kare:
    def __init__(self, kareler):
        self.kareler, self.i = kareler, -1

    def kare(self):
        self.i += 1
        r = self.kareler[min(self.i, len(self.kareler) - 1)][0]
        return Image.new("RGB", (64, 36), (r, r, r))

    def oku(self, resim):
        return self.kareler[min(self.i, len(self.kareler) - 1)][1]


async def kos(kareler, ayar):
    s = Kare(kareler)
    saat = {"t": 0.0}
    y = Yayin()
    q = y.abone_ol()
    a = {**VARSAYILAN, "ekrani_cevir": True, "kisa_aciklama": False, **ayar}
    isl = Isleme(s.kare, s, CeviriYoneticisi(SahteMotor(), None, None), y, lambda: a, saat=lambda: saat["t"])
    for _ in kareler:
        await isl.adim()
        saat["t"] += DT
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


def _paneli_okur_gibi():
    """Masaüstünde açık panel: kelime kelime dağılmış yazılar + gerçek altyazı."""
    panel = [Satir("sitesi", 0.1 + i * 0.05, 0.2, 0.04, 0.03) for i in range(4)] + \
            [Satir("Yeni dosya aç", 0.5, 0.3, 0.1, 0.03), Satir("Settings and options", 0.1, 0.5, 0.2, 0.03)]
    altyazi = Satir("Stay close to me please", 0.3, 0.85, 0.4, 0.05)
    return panel + [altyazi]


async def test_tam_ekran_bolgesiz_yalniz_altyazi_bandi_ekran_ogesi_yok():
    k = [(10, _paneli_okur_gibi())] * 8
    olaylar = await kos(k, {"kaynak": "ekran:1"})
    assert not [v for o, v in olaylar if o == "ekran"]
    (y,) = {v["asil"] for o, v in olaylar if o == "yazi"}
    assert y == "Stay close to me please"


async def test_pencere_kaynaginda_ekran_ogeleri_eskisi_gibi_calisir():
    k = [(10, _paneli_okur_gibi())] * 8
    olaylar = await kos(k, {"kaynak": "pencere:12345"})
    assert [v for o, v in olaylar if o == "ekran"]


async def test_tam_ekran_bolge_varsa_yalniz_bolgede_ekran_ogesi():
    b = [{"x": 0.0, "y": 0.45, "g": 0.4, "y2": 0.2, "tur": "diger", "ad": "Menü"}]
    # kare tamamen 64x36: bölge kesiti OCR'a gider; sahte okuyucu bölge kesiti için de aynı satırları döndürür,
    # bu yüzden yalnız bölgeye düşenler (merkezi bölge içinde) çevrilir.
    satirlar = [Satir("Continue", 0.1, 0.1, 0.5, 0.5), Satir("Options", 0.1, 0.6, 0.5, 0.3)]
    olaylar = await kos([(10, satirlar)] * 8, {"kaynak": "ekran:1", "bolgeler": b})
    e = [v for o, v in olaylar if o == "ekran"]
    assert e and all(ogeler["metin"].startswith("[TR]") for v in e for ogeler in v["ogeler"])
    assert not [v for o, v in olaylar if o == "yazi"]


# ---------- §12.2 cihaza göre kaynak ----------

LISTE = [
    {"kod": "ekran:1", "ad": "Ekran 1 (1920×1080)"},
    {"kod": "pencere:1", "ad": "AltYazıKöprüsü - Panel - Google Chrome"},
    {"kod": "pencere:2", "ad": "Spotify"},
    {"kod": "pencere:3", "ad": "PS Remote Play"},
    {"kod": "pencere:4", "ad": "Xbox"},
    {"kod": "pencere:5", "ad": "Windowed Projector (Source) - OBS Studio"},
    {"kod": "pencere:6", "ad": "PS Remote Play rehberi - Mozilla Firefox"},
    {"kod": "pencere:7", "ad": "Notlar", "exe": "chrome.exe"},
    {"kod": "pencere:8", "ad": "chiaki-ng"},
    {"kod": "pencere:9", "ad": "Elgato 4K Capture Utility"},
]


def _isaret(cihaz):
    return {k["kod"]: k for k in yakalama.kaynaklari_isaretle(LISTE, cihaz)}


def test_cihaz_ps5_eslesmesi_tarayici_ve_marka_haric():
    m = _isaret("ps5")
    assert m["pencere:3"]["onerilen"] and m["pencere:8"]["onerilen"]
    assert not m["pencere:6"]["onerilen"] and m["pencere:6"]["haric"]            # tarayıcı sekmesi: önerilmez
    assert not m["pencere:1"]["onerilen"] and m["pencere:1"]["haric"]            # marka penceresi
    assert not m["pencere:7"]["onerilen"] and m["pencere:7"]["haric"]            # exe adından tarayıcı
    assert not m["pencere:4"]["onerilen"] and not m["pencere:5"]["onerilen"]


def test_cihaz_xbox_kart_pc():
    assert [k for k, v in _isaret("xbox").items() if v["onerilen"]] == ["pencere:4"]
    assert sorted(k for k, v in _isaret("kart").items() if v["onerilen"]) == ["pencere:5", "pencere:9"]
    assert not [k for k, v in _isaret("pc").items() if v["onerilen"]]
    assert not [k for k, v in _isaret(None).items() if v["onerilen"]]


def test_siralama_ekran_onerilen_digerleri_en_sonda_haric_ve_tur():
    s = yakalama.kaynaklari_isaretle(LISTE, "ps5")
    kodlar = [k["kod"] for k in s]
    assert kodlar[0] == "ekran:1" and s[0]["tur"] == "ekran" and s[1]["tur"] == "pencere"
    assert kodlar[1:3] == ["pencere:3", "pencere:8"]                              # önerilenler hemen ekranlardan sonra
    assert set(kodlar[-3:]) == {"pencere:1", "pencere:6", "pencere:7"}            # tarayıcılar/marka en sonda
    assert all(isinstance(k["onerilen"], bool) for k in s)
    assert not yakalama.cihaz_eslesir_mi("kart", "Jobs Observer")     # "obs" yalnız tam kelime


class _Mss:
    monitors = [{}, {"left": 0, "top": 0, "width": 1920, "height": 1080}]

    class MSS:
        def __enter__(self):
            return SimpleNamespace(monitors=_Mss.monitors)

        def __exit__(self, *a):
            return False


def _kaynak_yamala(monkeypatch):
    monkeypatch.setattr(yakalama, "_mss", lambda: _Mss)
    monkeypatch.setattr(yakalama, "_pencereler", lambda: [(int(k["kod"].split(":")[1]), k["ad"]) for k in LISTE[1:]])
    monkeypatch.setattr(yakalama, "_pencere_exe", lambda h: "chrome.exe" if h == 7 else "")


async def test_api_kaynaklar_onerilen_ve_tur(aiohttp_client, uygulama_ayari, monkeypatch):
    _kaynak_yamala(monkeypatch)
    uygulama_ayari["cihaz"] = "ps5"
    c = await aiohttp_client(sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika))
    liste = await (await c.get("/api/kaynaklar")).json()
    assert liste[0] == {"kod": "ekran:1", "ad": "Ekran 1 (1920×1080)", "tur": "ekran", "onerilen": False}
    assert [k["kod"] for k in liste if k["onerilen"]] == ["pencere:3", "pencere:8"]
    assert liste[-1]["haric"] is True


async def test_durum_uyari_tum_ekran_yalniz_uygun_pencere_varken(aiohttp_client, uygulama_ayari, monkeypatch):
    _kaynak_yamala(monkeypatch)
    uygulama_ayari.update(cihaz="ps5", kaynak="ekran:1")
    c = await aiohttp_client(sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika))
    d = await (await c.get("/api/durum")).json()
    assert d["uyari"] == {"kod": "tum_ekran", "mesaj": "Tüm ekran seçili; PS Remote Play penceresini seçersen yalnız oyunu okurum."}
    await c.post("/api/ayarlar", json={"arayuz_dili": "en"})
    assert "PS Remote Play window" in (await (await c.get("/api/durum")).json())["uyari"]["mesaj"]
    await c.post("/api/ayarlar", json={"kaynak": "pencere:3"})                      # pencere seçildi: uyarı yok
    assert "uyari" not in await (await c.get("/api/durum")).json()
    await c.post("/api/ayarlar", json={"kaynak": "ekran:1", "cihaz": "pc"})         # pc: uyarı yok
    assert "uyari" not in await (await c.get("/api/durum")).json()


async def test_durum_uyari_yok_uygun_pencere_yoksa(aiohttp_client, uygulama_ayari, monkeypatch):
    _kaynak_yamala(monkeypatch)
    monkeypatch.setattr(yakalama, "_pencereler", lambda: [(2, "Spotify")])
    uygulama_ayari.update(cihaz="ps5", kaynak="ekran:1")
    c = await aiohttp_client(sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika))
    assert "uyari" not in await (await c.get("/api/durum")).json()


# ---------- §12.3 oyun bilgisi ----------

def _terimler(n=30):
    return [{"asil": f"Ad{i}", "ceviri": f"Ad{i}"} for i in range(n)]


class SahteLlm:
    """serbest_istem'i olan sahte motor."""
    kod, ad, anahtar_gerekli, cevrimdisi, ucretsiz = "gemini", "Sahte LLM", True, False, True

    def __init__(self, yanit=None, hata=None):
        self.yanit, self.hata, self.cagrilar = yanit, hata, []

    async def serbest_istem(self, sistem, kullanici):
        self.cagrilar.append((sistem, kullanici))
        if self.hata:
            raise self.hata
        return self.yanit

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False):
        raise AssertionError("çeviri çağrılmamalı")


def _oneri(**ek):
    v = {"aciklama": "Açık dünya korsan oyunu.", "hitap": "siz", "terimler": [{"asil": "Kenway", "ceviri": "Kenway"}] + _terimler()}
    v.update(ek)
    return json.dumps(v, ensure_ascii=False)


async def _istemci(aiohttp_client, uygulama_ayari, motor):
    uygulama_ayari["motor"] = "gemini"
    uygulama_ayari["yedek_motor"] = ""
    c = await aiohttp_client(sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=lambda k, a: motor))
    kod = (await (await c.post("/api/oyunlar", json={"ad": "Assassin's Creed Black Flag"})).json())["kod"]
    return c, kod


async def test_bilgi_hazirla_oneri_doner_ve_kaydetmez(aiohttp_client, uygulama_ayari):
    llm = SahteLlm(_oneri())
    c, kod = await _istemci(aiohttp_client, uygulama_ayari, llm)
    r = await c.post(f"/api/oyun/{kod}/bilgi-hazirla")
    j = await r.json()
    assert r.status == 200 and j["hitap"] == "siz" and len(j["terimler"]) == 31 and j["aciklama"].startswith("Açık")
    assert "Assassin's Creed Black Flag" in llm.cagrilar[0][1] and "JSON" in llm.cagrilar[0][0]
    assert sozluk.yukle(kod) == [] and (await (await c.get(f"/api/oyun/{kod}")).json())["aciklama"] == ""    # otomatik kaydedilmedi


async def test_bilgi_hazirla_cevrimdisi_motor_dostca_hata(aiohttp_client, uygulama_ayari):
    c, kod = await _istemci(aiohttp_client, uygulama_ayari, SahteMotor())
    r = await c.post(f"/api/oyun/{kod}/bilgi-hazirla")
    j = await r.json()
    assert r.status == 400 and j["hata"] == "bilgi_cevrimdisi" and "Gemini" in j["mesaj"]


@pytest.mark.parametrize("hata,durum,kod", [
    (AnahtarHatasi("gemini"), 400, "anahtar_yok"), (AgHatasi("HTTP 500"), 502, "ag_hatasi")])
async def test_bilgi_hazirla_motor_hatalari(aiohttp_client, uygulama_ayari, hata, durum, kod):
    c, oyun = await _istemci(aiohttp_client, uygulama_ayari, SahteLlm(hata=hata))
    r = await c.post(f"/api/oyun/{oyun}/bilgi-hazirla")
    assert r.status == durum and (await r.json())["hata"] == kod


async def test_bilgi_hazirla_bozuk_yanit_ve_olmayan_oyun(aiohttp_client, uygulama_ayari):
    c, kod = await _istemci(aiohttp_client, uygulama_ayari, SahteLlm("üzgünüm bilmiyorum"))
    r = await c.post(f"/api/oyun/{kod}/bilgi-hazirla")
    assert r.status == 502 and (await r.json())["hata"] == "bilgi_okunamadi"
    assert (await c.post("/api/oyun/yokboyle/bilgi-hazirla")).status == 404


def test_yaniti_coz_temizler_ve_sinirlar():
    ham = "```json\n" + json.dumps({
        "aciklama": "x" * 500, "hitap": "belki",
        "terimler": [{"asil": "Edward", "ceviri": "Edward"}, {"asil": "edward", "ceviri": "başka"},   # tekrar
                     {"asil": "Havana"}, {"asil": ""}, {"asil": "a" * 80}, {"asil": 5}, "bozuk",
                     {"asil": "Kötü [[T1]]"}, {"asil": "Jackdaw\n\x00", "ceviri": "  Jackdaw  "}]
                     + [{"asil": f"N{i}", "ceviri": f"T{i}"} for i in range(200)]}) + "\n```"
    o = oyun_bilgisi.yaniti_coz(ham)
    assert len(o["aciklama"]) == 200 and o["hitap"] == "sen"
    assert len(o["terimler"]) == oyun_bilgisi.EN_COK_TERIM == 80
    asiller = [t["asil"] for t in o["terimler"]]
    assert asiller[:3] == ["Edward", "Havana", "Jackdaw"] and o["terimler"][1]["ceviri"] == "Havana"
    assert "[[T1]]" not in " ".join(asiller) and len(set(a.casefold() for a in asiller)) == 80
    with pytest.raises(ValueError):
        oyun_bilgisi.yaniti_coz('{"aciklama":"","terimler":[]}')
    with pytest.raises(ValueError):
        oyun_bilgisi.yaniti_coz("[1,2]")


async def test_bilgi_kaydet_kullanici_terimleri_kazanir(aiohttp_client, uygulama_ayari):
    c, kod = await _istemci(aiohttp_client, uygulama_ayari, SahteLlm(_oneri()))
    sozluk.kaydet(kod, [{"asil": "Kenway", "ceviri": "Kenvey"}, {"asil": "Benim", "ceviri": "Benim terimim"}])
    r = await c.post(f"/api/oyun/{kod}/bilgi-kaydet", json={
        "aciklama": "Korsanlar.", "hitap": "siz",
        "terimler": [{"asil": "kenway", "ceviri": "YANLIŞ"}, {"asil": "Havana", "ceviri": "Havana"}]})
    j = await r.json()
    assert r.status == 200 and j["eklenen"] == 1
    kayit = {t["asil"]: t["ceviri"] for t in sozluk.yukle(kod)}
    assert kayit == {"Kenway": "Kenvey", "Benim": "Benim terimim", "Havana": "Havana"}
    bilgi = oyunlar.oku(kod)
    assert bilgi["aciklama"] == "Korsanlar." and bilgi["hitap"] == "siz"
    assert (await c.post(f"/api/oyun/{kod}/bilgi-kaydet", json={"hitap": "abi"})).status == 400
    assert (await c.post("/api/oyun/yokboyle/bilgi-kaydet", json={})).status == 404


async def test_bilgi_kaydet_aktif_oyunun_cevirisine_hemen_yansir(aiohttp_client, uygulama_ayari):
    c, kod = await _istemci(aiohttp_client, uygulama_ayari, SahteLlm(_oneri()))
    await c.post("/api/oyun-sec", json={"kod": kod})
    await c.post(f"/api/oyun/{kod}/bilgi-kaydet", json={"hitap": "siz", "terimler": [{"asil": "Jackdaw", "ceviri": "Jackdaw"}]})
    y = c.app[sunucu.DURUM].yonetici
    assert y.terimler.get("Jackdaw") == "Jackdaw" and y.oyun_bilgisi["hitap"] == "siz"


# ---------- serbest_istem: motorlar ----------

class SahteIstemci:
    def __init__(self, metin):
        self.cagrilar = []
        self.messages = SimpleNamespace(create=self._create)
        self.metin = metin

    async def _create(self, **kw):
        self.cagrilar.append(kw)
        return SimpleNamespace(stop_reason="end_turn", content=[
            SimpleNamespace(type="thinking", text="gizli"), SimpleNamespace(type="text", text=self.metin)])


async def test_claude_serbest_istem_kurallari():
    ist = SahteIstemci('{"a":1}')
    r = await ClaudeMotoru("k", istemci=ist).serbest_istem("SİSTEM", "KULLANICI")
    assert r == '{"a":1}'
    kw = ist.cagrilar[0]
    assert kw["output_config"] == {"effort": "low"} and kw["system"] == "SİSTEM"
    assert not {"thinking", "temperature"} & kw.keys()
    assert kw["messages"] == [{"role": "user", "content": "KULLANICI"}]               # ön doldurma yok
    assert kw["max_tokens"] >= 3000


async def test_gemini_ve_deepseek_serbest_istem(monkeypatch):
    from kopru.ceviri import _http
    gelen = []

    async def sahte_post(url, govde, basliklar, zaman_asimi=8.0, oturum=None):
        gelen.append((url, govde, zaman_asimi))
        if "deepseek" in url:
            return {"choices": [{"message": {"content": '{"d":1}'}}]}
        return {"candidates": [{"content": {"parts": [{"text": '{"g'}, {"text": '":1}'}]}}]}
    monkeypatch.setattr(_http, "post_json", sahte_post)
    assert await GeminiMotoru("k").serbest_istem("S", "K") == '{"g":1}'
    g = gelen[0][1]
    assert g["systemInstruction"]["parts"][0]["text"] == "S" and g["contents"][0]["parts"][0]["text"] == "K"
    assert g["generationConfig"] == {"responseMimeType": "application/json"} and gelen[0][2] > 8.0
    assert await DeepSeekMotoru("k").serbest_istem("S", "K") == '{"d":1}'
    assert gelen[1][1]["messages"][0] == {"role": "system", "content": "S"}
    with pytest.raises(AnahtarHatasi):
        await GeminiMotoru(None).serbest_istem("S", "K")
    with pytest.raises(AnahtarHatasi):
        await DeepSeekMotoru(None).serbest_istem("S", "K")
    with pytest.raises(AnahtarHatasi):
        await ClaudeMotoru(None).serbest_istem("S", "K")


def test_yeni_metinler_tr_en():
    from kopru import metinler
    for kod in ("bilgi_cevrimdisi", "bilgi_okunamadi", "uyari_tum_ekran_ps5", "uyari_tum_ekran_xbox", "uyari_tum_ekran_kart"):
        assert metinler.mesaj(kod, "tr") != metinler.mesaj(kod, "en")
        assert metinler.mesaj(kod, "tr") != metinler.mesaj("sunucu_hatasi", "tr")


def test_katman_penceresi_baslikta_marka_adi_tasimaz():
    from pathlib import Path
    from kopru import katman
    kaynak = (Path(katman.__file__).parent / "pencere.py").read_text(encoding="utf-8")
    baslik = [s for s in kaynak.splitlines() if "self.kok.title(" in s][0]
    assert not yakalama.marka_baslikli_mi(baslik.split("#")[0])
