# SPDX-License-Identifier: AGPL-3.0-only
"""Gemini model yedekleme (404), yedek motor sebebi ve Türkçe çıktı isteği."""
import json

import pytest

from kopru.ceviri import _http, gemini
from kopru.ceviri.sahte import SahteMotor
from kopru.ceviri.temel import AgHatasi, ModelBulunamadi
from kopru.ceviri.yonetici import CeviriYoneticisi


def _yanit(metin="Merhaba"):
    ic = json.dumps({"ceviriler": [metin], "yeni_terimler": []})
    return {"candidates": [{"content": {"parts": [{"text": ic}]}}]}


async def test_gemini_404da_siradaki_modeli_dener_ve_hatirlar(monkeypatch):
    denenen = []

    async def sahte(url, govde, basliklar, **kw):
        model = url.split("/models/")[1].split(":")[0]
        denenen.append(model)
        if model != "gemini-3.5-flash-lite":
            raise ModelBulunamadi("HTTP 404")
        return _yanit()
    monkeypatch.setattr(_http, "post_json", sahte)
    m = gemini.GeminiMotoru("k", "gemini-2.5-flash")
    (c,) = await m.cevir(["Hello"], "en", "tr", {})
    assert c.metin == "Merhaba"
    assert denenen == ["gemini-2.5-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"]
    assert m.model == "gemini-3.5-flash-lite"
    denenen.clear()
    await m.cevir(["Hello"], "en", "tr", {})
    assert denenen == ["gemini-3.5-flash-lite"]          # çalışan hatırlandı


async def test_gemini_hepsi_404_ise_model_bulunamadi(monkeypatch):
    async def sahte(url, govde, basliklar, **kw):
        raise ModelBulunamadi("HTTP 404")
    monkeypatch.setattr(_http, "post_json", sahte)
    with pytest.raises(ModelBulunamadi):
        await gemini.GeminiMotoru("k").cevir(["Hello"], "en", "tr", {})


async def test_gemini_istegi_turkce_ister(monkeypatch):
    govdeler = []

    async def sahte(url, govde, basliklar, **kw):
        govdeler.append(govde)
        return _yanit()
    monkeypatch.setattr(_http, "post_json", sahte)
    await gemini.GeminiMotoru("k").cevir(["Hello"], "en", "tr", {})
    sistem = govdeler[0]["systemInstruction"]["parts"][0]["text"]
    assert "into Turkish" in sistem and "MUST be written in Turkish ONLY" in sistem


async def test_http_404_model_bulunamadi(aiohttp_server):
    from aiohttp import web

    async def h(r):
        return web.Response(status=404, text="{}")
    app = web.Application()
    app.router.add_post("/x", h)
    s = await aiohttp_server(app)
    with pytest.raises(ModelBulunamadi):
        await _http.post_json(str(s.make_url("/x")), {}, {})


class Bozuk:
    kod, ad, cevrimdisi, baglam_destekler = "gemini", "Gemini", False, False

    def __init__(self, hata):
        self.hata = hata

    async def cevir(self, *a, **k):
        raise self.hata


async def test_yedege_gecince_neden_durum_olayinda():
    olaylar = []
    yedek = SahteMotor()
    yedek.cevrimdisi, yedek.ad = True, "Çevrimdışı (yerel)"
    y = CeviriYoneticisi(Bozuk(ModelBulunamadi("HTTP 404")), yedek, None, lambda o, v: olaylar.append((o, v)))
    (c,) = await y.cevir(["Hello"], "en", "tr")
    assert c.metin
    assert y.yedekte and y.yedek_neden["kod"] == "model_yok"
    assert y.yedek_neden["mesaj"] == "Gemini çalışmadı (model bulunamadı), çevrimdışı çeviriye geçildi."
    durum = [v for o, v in olaylar if o == "durum"][-1]
    assert durum["yedek"] is True and durum["yedek_neden"]["kod"] == "model_yok"
    assert y.durum_ek()["yedek_neden"]["mesaj"].startswith("Gemini çalışmadı")


async def test_ag_hatasi_nedeni_ve_duzelince_temizlenir():
    y = CeviriYoneticisi(Bozuk(AgHatasi("HTTP 429")), SahteMotor(), None)
    await y.cevir(["Hello"], "en", "tr")
    assert y.yedek_neden["kod"] == "hiz_siniri"
    y.birincil = SahteMotor()
    y._yedek_zamani = -1e9
    await y.cevir(["Another"], "en", "tr")
    assert not y.yedekte and y.durum_ek() == {}


async def test_api_dene_birincil_gercek_hatayi_gosterir_yedege_gecmez(aiohttp_client, uygulama_ayari):
    from kopru import sunucu
    uygulama_ayari["motor"] = "gemini"
    uygulama_ayari["yedek_motor"] = "sahte"

    def fabrika(kod, ayar):
        return Bozuk(ModelBulunamadi("HTTP 404")) if kod == "gemini" else SahteMotor()
    c = await aiohttp_client(sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=fabrika))
    r = await c.post("/api/dene", json={"metin": "Hello"})
    assert r.status == 502
    j = await r.json()
    assert j["hata"] == "model_yok" and "bulunamadı" in j["mesaj"]
    d = await (await c.get("/api/durum")).json()
    assert d["yedekte"] is False and "yedek_neden" not in d
