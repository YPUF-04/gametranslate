# SPDX-License-Identifier: AGPL-3.0-only
"""Gerçek test (0.1.3, PS5 → HDMI → LG TV, gizli Remote Play): "altyazıyı hiç çevirmiyor".

Neden: altyazı isteği Gemini'ye `thinkingLevel:"minimal"` ile gidiyordu; varsayılan model gemini-3.8-flash bu
düzeyi TANIMAZ (HTTP 400). Yedek yol düşünme ayarını tamamen kaldırıyordu → model varsayılan "medium" düşünmeyle
yanıt verir; altyazının 8 sn sınırı aşılınca satır atlanır. Burada gerçek HTTP ile (yerel sahte Gemini) uçtan uca
sınanır: kare → okuma (kelime kutulu, "LUCIA: ..." ön ekli) → süzgeç → sıralı kuyruk → Gemini → `yazi` + `ortu`.
Ayrıca: takılan çeviri kuyruğu tıkamaz, dışarıdan iptal edilen önden çeviri satırı askıda bırakmaz, kopmuş
keep-alive bağlantısı bir kez yinelenir, zaman aşımında hızlı model (Flash-Lite) denenir, konuşan ve cinsiyeti istemde.
"""
import asyncio
import json
import time

import aiohttp
import pytest
from aiohttp import web
from PIL import Image

from kopru import isleme
from kopru.ayarlar import VARSAYILAN
from kopru.ceviri import _http, gemini
from kopru.ceviri.temel import AgHatasi, Ceviri
from kopru.ceviri.yonetici import CeviriYoneticisi
from kopru.isleme import Isleme
from kopru.okuma import Satir
from kopru.yayin import Yayin

YAVAS_SN = 1.2     # düşünme ayarı olmadan (varsayılan "medium") yanıt süresi: altyazı sınırını aşar
HIZLI_SN = 0.05    # "low" ile


def _yanit(metinler):
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(
        {"ceviriler": [f"TR<{m}>" for m in metinler], "yeni_terimler": []}, ensure_ascii=False)}]}}]}


@pytest.fixture
async def sahte_gemini(aiohttp_server, monkeypatch):
    """Gemini REST'ini taklit eder: 3.8-flash "minimal"e gerçek API gibi 400 döner, düşünmesiz yavaştır."""
    istekler = []

    async def uret(req):
        model = req.match_info["m"].split(":")[0]
        g = await req.json()
        assert req.headers.get("x-goog-api-key") == "k"
        assert set(g) == {"systemInstruction", "contents", "generationConfig"}
        assert g["generationConfig"]["responseMimeType"] == "application/json"
        tc = g["generationConfig"].get("thinkingConfig")
        istekler.append((model, tc, g["contents"][0]["parts"][0]["text"]))
        if tc is not None:
            assert set(tc) == {"thinkingLevel"} and tc["thinkingLevel"] in ("minimal", "low", "medium", "high")
            desteklenen = {"gemini-3.8-flash": ("low", "medium", "high")}.get(
                model, ("minimal", "low", "medium", "high"))
            if tc["thinkingLevel"] not in desteklenen:
                return web.json_response({"error": {"code": 400, "status": "INVALID_ARGUMENT", "message":
                                         f"Thinking level {tc['thinkingLevel'].upper()} is not supported for this model."}},
                                         status=400)
        await asyncio.sleep(HIZLI_SN if tc is not None else YAVAS_SN)
        metin = g["contents"][0]["parts"][0]["text"]
        return web.json_response(_yanit(json.loads(metin[metin.rfind("["):])))

    app = web.Application()
    app.router.add_post("/v1beta/models/{m}", uret)
    sunucu = await aiohttp_server(app)
    monkeypatch.setattr(gemini, "URL", str(sunucu.make_url("/v1beta/models/")) + "{model}:generateContent")
    monkeypatch.setattr(gemini, "ALTYAZI_SN", 0.8)        # gerçekte 8 sn; ölçek küçültüldü
    monkeypatch.setattr(gemini, "HIZLI_YEDEK_SN", 0.8)
    yield istekler
    await _http.ortak_kapat()


SAHNE = [(0.10, 0.9, "LUCIA: Hey, you good? We gotta move."),
         (0.95, 1.8, "JASON: Yeah... I'm fine. Let's go."),
         (1.9, 2.7, "Press ✕ to enter the car")]


class Ps5Kare:
    """Gizli bağlantının 1280×720 karesi + winocr benzeri okuma (satır + kelime kutuları)."""

    def __init__(self, sahne, kelimesiz=False):
        self.sahne, self.kelimesiz, self.t0 = sahne, kelimesiz, time.monotonic()

    def _simdiki(self):
        t = time.monotonic() - self.t0
        return next((i for i, (b, s, _) in enumerate(self.sahne) if b <= t < s), None)

    def kare(self):
        """Altyazı değişince kare de değişir (alt bantta beyaz yazı şeridi; sahneye göre konumu)."""
        r = Image.new("RGB", (1280, 720), (40, 60, 80))
        i = self._simdiki()
        if i is not None:
            from PIL import ImageDraw
            ImageDraw.Draw(r).rectangle((352 + 40 * i, 619, 880, 644), fill=(235, 235, 235))
        return r

    def oku(self, resim):
        i = self._simdiki()
        for b, s, m in self.sahne[i:i + 1] if i is not None else []:
            if True:
                kel, x = [], 0.275
                for k in m.split():
                    g = len(k) * 0.009
                    kel.append((k, x, 0.86, g, 0.035))
                    x += g + 0.006
                return [Satir(m, 0.275, 0.86, x - 0.281, 0.035, kelimeler=() if self.kelimesiz else tuple(kel))]
        return []


async def _oynat(motor, sahne=SAHNE, sure=4.4, kelimesiz=False, yonetici=None):
    y = Yayin()
    q = y.abone_ol()
    ayar = {**VARSAYILAN, "kaynak": "ps5:gizli", "motor": "gemini"}
    k = Ps5Kare(sahne, kelimesiz)
    yon = yonetici or CeviriYoneticisi(motor, None, None)
    isl = Isleme(k.kare, k, yon, y, lambda: ayar)
    g = asyncio.create_task(isl.calis())
    await asyncio.sleep(sure)
    g.cancel()
    await asyncio.gather(g, return_exceptions=True)
    olaylar = []
    while not q.empty():
        olaylar.append(q.get_nowait())
    return [v for o, v in olaylar if o == "yazi"], olaylar, isl


async def test_gizli_ps5_altyazi_uctan_uca_gemini_38_flash(sahte_gemini):
    yazilar, _, isl = await _oynat(gemini.GeminiMotoru("k", "gemini-3.8-flash"))
    asil = [v["asil"] for v in yazilar if not v["devam"]]
    assert asil == ["Hey, you good? We gotta move.", "Yeah... I'm fine. Let's go.", "Press ✕ to enter the car"]
    assert all(v["metin"].startswith(("TR<", "✕")) and v.get("ortu") for v in yazilar)   # örtü ile, üstüne
    assert [v["konusan"] for v in yazilar if not v["devam"]] == ["LUCIA", "JASON", None]
    # 3.8-flash'a "minimal" hiç gitmez (400 almaz), "low" gider; hiçbir satır atlanmaz
    assert {(m, tc["thinkingLevel"] if tc else None) for m, tc, _ in sahte_gemini} == {("gemini-3.8-flash", "low")}
    assert isl.gecikme_bilgisi()["atlanan"] == 0


async def test_eski_davranis_minimal_400_sonra_dusunmesiz_yavas_hic_altyazi_yok(sahte_gemini, monkeypatch):
    """0.1.3'ün davranışı (minimal → 400 → düşünmesiz, yavaş): sınır aşılır, satırlar atlanır (hatanın kendisi)."""
    monkeypatch.setattr(gemini, "dusunme_duzeyi", lambda model: "minimal")
    monkeypatch.setattr(gemini, "HIZLI_YEDEK_MODEL", "gemini-3.8-flash")   # 0.1.3'te hızlı model yedeği yoktu
    yazilar, _, isl = await _oynat(gemini.GeminiMotoru("k", "gemini-3.8-flash"))
    assert yazilar == [] and isl.gecikme_bilgisi()["atlanan"] >= 1


async def test_flash_yanit_vermezse_satir_flash_lite_ile_kurtarilir(sahte_gemini, monkeypatch):
    monkeypatch.setattr(gemini, "dusunme_duzeyi", lambda model: None if model == "gemini-3.8-flash" else "minimal")
    yazilar, _, _ = await _oynat(gemini.GeminiMotoru("k", "gemini-3.8-flash"), sahne=SAHNE[:1], sure=2.4)
    assert [v["asil"] for v in yazilar] == ["Hey, you good? We gotta move."]
    assert ("gemini-3.5-flash-lite", {"thinkingLevel": "minimal"}) in [(m, tc) for m, tc, _ in sahte_gemini]


async def test_kelime_kutusu_olmasa_da_ortu_ile_yayinlanir(sahte_gemini):
    yazilar, _, _ = await _oynat(gemini.GeminiMotoru("k", "gemini-3.8-flash"), sahne=SAHNE[:1], sure=1.4,
                                 kelimesiz=True)
    assert yazilar and yazilar[0]["ortu"]["g"] > 0 and yazilar[0]["ortu"]["y2"] > 0


async def test_konusan_ve_cinsiyeti_istemde_baglam_konusanli(sahte_gemini):
    m = gemini.GeminiMotoru("k", "gemini-3.8-flash")
    yon = CeviriYoneticisi(m, None, None)
    yon.oyun_bilgisi = {"ad": "GTA VI", "karakterler": [{"ad": "Lucia Caminos", "cinsiyet": "k"},
                                                         {"ad": "Jason", "cinsiyet": "e"}]}
    await _oynat(m, sahne=SAHNE[:2], sure=2.4, yonetici=yon)
    metinler = [t for _, _, t in sahte_gemini]
    assert any("Speaker of the line(s) to translate: LUCIA (female)" in t for t in metinler)
    assert any("JASON (male)" in t and "LUCIA: Hey, you good?" in t for t in metinler)   # önceki satır konuşanıyla


def test_dusunme_duzeyi_modele_gore():
    assert gemini.dusunme_duzeyi("gemini-3.8-flash") == "low"          # minimal desteklenmez
    assert gemini.dusunme_duzeyi("gemini-3.5-flash-lite") == "minimal"
    assert gemini.dusunme_duzeyi("gemini-3.1-flash-lite") == "minimal"
    assert gemini.dusunme_duzeyi("gemini-2.5-flash") is None            # eski: bütçe ister, düzey gönderilmez


# ---------- kuyruk asla tıkanmaz ----------

class TakilanMotor:
    """İlk satırın isteği hiç dönmez (takılan bağlantı / CPU'su dolu yerel motor); sonrakiler hemen."""
    kod, ad, anahtar_gerekli, cevrimdisi = "t", "T", False, False

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False, **kw):
        if any("good" in m for m in metinler):
            await asyncio.sleep(3600)
        return [Ceviri(f"TR<{m}>") for m in metinler]


async def test_takilan_ceviri_siradaki_satirlari_sonsuza_dek_bekletmez(monkeypatch):
    monkeypatch.setattr(isleme, "SATIR_EN_COK_SN", 0.5)
    yazilar, olaylar, isl = await _oynat(TakilanMotor(), sahne=SAHNE[:2], sure=2.6)
    assert [v["asil"] for v in yazilar] == ["Yeah... I'm fine. Let's go."]
    assert isl.gecikme_bilgisi()["atlanan"] == 1
    assert any(o == "durum" and v.get("hata") == "ag" for o, v in olaylar)


async def test_disaridan_iptal_edilen_onden_ceviri_satiri_askida_birakmaz():
    yon = CeviriYoneticisi(TakilanMotor(), None, None)
    y = Yayin()
    q = y.abone_ol()
    isl = Isleme(lambda: None, None, yon, y, lambda: VARSAYILAN)
    kopya = asyncio.get_running_loop().create_future()   # el değiştirmiş önden çeviri, sonra iptal edilir
    s = isl._sira.ekle(isleme.SiraSatiri("a1", gel=0.0, ek={"govde": "We go now", "norm": "we go now"}))
    isl._cevir_baslat(s, "We go now", VARSAYILAN, kopya)
    await asyncio.sleep(0)
    kopya.cancel()
    for _ in range(50):
        await asyncio.sleep(0.01)
        if s.hazir is not None:
            break
    assert s.metin == "TR<We go now>" and not s.hata
    yazilar = []
    while not q.empty():
        o, v = q.get_nowait()
        if o == "yazi":
            yazilar.append(v)
    assert yazilar and yazilar[0]["metin"] == "TR<We go now>"


# ---------- açık tutulan (keep-alive) bağlantı ----------

async def test_kopmus_keepalive_baglantisi_bir_kez_yinelenir(monkeypatch):
    sayac = {"n": 0}
    gercek = _http._post_json

    async def ilk_kopar(url, govde, basliklar, zaman_asimi, oturum):
        sayac["n"] += 1
        if sayac["n"] == 1:
            try:
                raise aiohttp.ServerDisconnectedError()
            except aiohttp.ServerDisconnectedError as e:
                raise AgHatasi(type(e).__name__) from e
        return {"tamam": True}
    monkeypatch.setattr(_http, "_post_json", ilk_kopar)
    assert await _http.post_json("http://x", {}, {}) == {"tamam": True} and sayac["n"] == 2
    monkeypatch.setattr(_http, "_post_json", gercek)
    await _http.ortak_kapat()


async def test_baska_hatalar_yinelenmez(monkeypatch):
    sayac = {"n": 0}

    async def zaman(url, govde, basliklar, zaman_asimi, oturum):
        sayac["n"] += 1
        try:
            raise asyncio.TimeoutError()
        except asyncio.TimeoutError as e:
            raise AgHatasi(type(e).__name__) from e
    monkeypatch.setattr(_http, "_post_json", zaman)
    with pytest.raises(AgHatasi):
        await _http.post_json("http://x", {}, {})
    assert sayac["n"] == 1
    await _http.ortak_kapat()


async def test_oturum_baska_olay_dongusunde_yenisi_acilir():
    """Döngüler arası paylaşım yok: başka iş parçacığının döngüsü kendi oturumunu açar, ilki bozulmaz."""
    a = _http.ortak_oturum()

    def baska():
        async def ic():
            b = _http.ortak_oturum()
            r = b is not a and not b.closed
            await _http.ortak_kapat()
            return r
        return asyncio.run(ic())
    assert await asyncio.to_thread(baska)
    assert _http.ortak_oturum() is a and not a.closed
    await _http.ortak_kapat()


async def test_gercek_400_govdesi_anahtar_hatasindan_ayrilir(aiohttp_server):
    async def h(req):
        return web.json_response({"error": {"code": 400, "message": "Thinking level MINIMAL is not supported"}}, status=400)
    app = web.Application()
    app.router.add_post("/x", h)
    s = await aiohttp_server(app)
    with pytest.raises(AgHatasi) as e:
        await _http.post_json(str(s.make_url("/x")), {}, {})
    assert str(e.value).startswith("HTTP 400") and "thinking level" in str(e.value)
    await _http.ortak_kapat()


# ---------- oyun bilgisi: karakterler + cinsiyet ----------

def test_oyun_bilgisi_karakter_ve_cinsiyet_onerir_kullanicininki_kalir():
    from kopru import oyun_bilgisi
    o = oyun_bilgisi.yaniti_coz(json.dumps({"aciklama": "Vice City.", "hitap": "sen", "terimler": [],
                                            "karakterler": [{"ad": "Lucia", "cinsiyet": "k"}, {"ad": "Jason", "cinsiyet": "e"},
                                                            {"ad": "lucia", "cinsiyet": "e"}, {"ad": "", "cinsiyet": "k"},
                                                            {"ad": "Cal", "cinsiyet": "x"}]}))
    assert o["karakterler"] == [{"ad": "Lucia", "cinsiyet": "k"}, {"ad": "Jason", "cinsiyet": "e"},
                                {"ad": "Cal", "cinsiyet": ""}]
    mevcut = [{"ad": "Jason", "cinsiyet": ""}, {"ad": "Lucia", "cinsiyet": "e"}]   # kullanıcı yanlış da girse onunki
    b = oyun_bilgisi.karakter_birlestir(mevcut, o["karakterler"])
    assert b == [{"ad": "Jason", "cinsiyet": "e"}, {"ad": "Lucia", "cinsiyet": "e"}, {"ad": "Cal", "cinsiyet": ""}]
    assert '"karakterler"' in oyun_bilgisi.SISTEM


def test_konusan_cinsiyeti_ad_eslesmesi():
    y = CeviriYoneticisi(TakilanMotor(), None, None)
    y.oyun_bilgisi = {"karakterler": [{"ad": "Lucia Caminos", "cinsiyet": "k"}, {"ad": "Boobie Ike", "cinsiyet": "e"}]}
    assert y.konusan_cinsiyeti("LUCIA") == "k" and y.konusan_cinsiyeti("lucia caminos") == "k"
    assert y.konusan_cinsiyeti("BOOBIE") == "e" and y.konusan_cinsiyeti("JASON") is None and y.konusan_cinsiyeti(None) is None
