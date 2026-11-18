# SPDX-License-Identifier: AGPL-3.0-only
import asyncio
import json
import logging
from types import SimpleNamespace

import pytest

from kopru import anahtarlar, ayarlar, sozluk
from kopru.ceviri.claude import ClaudeMotoru
from kopru.ceviri.temel import AgHatasi, AnahtarHatasi, Ceviri
from kopru.ceviri.yonetici import CeviriYoneticisi
from kopru.onbellek import Onbellek, normallestir
from kopru.yayin import Yayin


def test_ayar_kaydet_yukle(tmp_path):
    a = ayarlar.yukle()
    assert a["kapi"] == 8642
    a["motor"] = "claude"
    ayarlar.kaydet(a)
    assert ayarlar.yukle()["motor"] == "claude"
    assert not list(tmp_path.glob("*.tmp"))


def test_onbellek(tmp_path):
    o = Onbellek(tmp_path / "c.db", azami=10)
    o.koy("Hello World!!", "en", "tr", "oyun", "Merhaba Dünya")
    assert o.al("  hello   world ", "en", "tr", "oyun") == ("Merhaba Dünya", None)
    assert o.al("hello world", "en", "tr", "baska") is None
    assert normallestir("...Hi  There?!") == "hi there"
    for i in range(30):
        o.koy(f"satir {i}", "en", "tr", "oyun", "x")
    assert o.boyut() <= 11


def test_sozluk_koruma(tmp_path):
    s = {"Ellie": "Ellie", "Fire Sword": "Ateş Kılıcı"}
    m, h = sozluk.koru("Ellie took the fire sword.", s)
    assert "Ellie" not in m and "fire sword" not in m
    assert sozluk.geri_koy(m.replace("[[T", "[[ T").replace("]]", " ]]"), h) == \
        "Ellie took the Ateş Kılıcı."
    sozluk.kaydet("oyun1", [{"asil": "Ellie", "ceviri": "Ellie"}])
    assert sozluk.yukle("oyun1")[0]["asil"] == "Ellie"
    assert sozluk.son_kontrol("x", "Fire Sword burada", s) == "Ateş Kılıcı burada"


def test_anahtar_kasa_ve_log(caplog):
    caplog.set_level(logging.DEBUG)
    anahtarlar.yaz("claude", "sk-gizli-123")
    assert anahtarlar.oku("claude") == "sk-gizli-123"
    anahtarlar.yaz("claude", "")
    assert anahtarlar.oku("claude") is None
    assert "sk-gizli" not in caplog.text


def test_kasa_yoksa_reddet(monkeypatch):
    import keyring
    from keyring.backends import fail
    onceki = keyring.get_keyring()
    keyring.set_keyring(fail.Keyring())
    try:
        with pytest.raises(anahtarlar.KasaHatasi):
            anahtarlar.yaz("claude", "sk-x")
    finally:
        keyring.set_keyring(onceki)


class Hatali:
    kod, ad, anahtar_gerekli, cevrimdisi = "hatali", "Hatalı", True, False

    def __init__(self):
        self.n = 0

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False):
        self.n += 1
        raise AgHatasi("x")


class Yedek:
    kod, ad, anahtar_gerekli, cevrimdisi = "yedek", "Yedek", False, True

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False):
        return [Ceviri("Y:" + m) for m in metinler]


async def test_yonetici_yedege_gecer(tmp_path):
    olaylar = []
    y = CeviriYoneticisi(Hatali(), Yedek(), Onbellek(tmp_path / "c.db"),
                         lambda o, v: olaylar.append((o, v)))
    (c,) = await y.cevir(["hello"])
    assert c.metin == "Y:hello"
    assert y.yedekte
    assert ("durum", {"calisiyor": True, "motor": "Yedek", "yedek": True}) in olaylar
    (c2,) = await y.cevir(["hello"])  # önbellekten
    assert c2.metin == "Y:hello"


async def test_yonetici_dedupe(tmp_path):
    class Yavas(Yedek):
        n = 0

        async def cevir(self, metinler, *a, **k):
            Yavas.n += 1
            await asyncio.sleep(0.05)
            return [Ceviri("T:" + m) for m in metinler]

    y = CeviriYoneticisi(Yavas(), None, None)
    r = await asyncio.gather(y.cevir(["a"]), y.cevir(["a"]))
    assert r[0][0].metin == r[1][0].metin == "T:a"
    assert Yavas.n == 1


async def test_yayin_son_durum():
    y = Yayin()
    y.yayinla("gorunum", {"a": 1})
    y.yayinla("yazi", {"id": "1", "metin": "m", "sure_ms": 5000})
    assert [o for o, _ in y.acilis_olaylari()] == ["gorunum", "yazi"]
    y.yayinla("yazi-sil", {})
    assert [o for o, _ in y.acilis_olaylari()] == ["gorunum"]
    q = y.abone_ol()
    assert y.istemci_sayisi == 1
    y.yayinla("ekran", {"id": "e1", "ogeler": []})
    assert q.get_nowait()[0] == "ekran"


class SahteIstemci:
    def __init__(self, yanit=None, hata=None):
        self.cagrilar = []
        self.yanit, self.hata = yanit, hata
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kw):
        self.cagrilar.append(kw)
        if self.hata:
            raise self.hata
        return self.yanit


def _yanit(metin, stop="end_turn"):
    return SimpleNamespace(stop_reason=stop, content=[
        SimpleNamespace(type="thinking", text="gizli"), SimpleNamespace(type="text", text=metin)])


async def test_claude_istek_sekli():
    ist = SahteIstemci(_yanit('["Merhaba","Dünya"]'))
    m = ClaudeMotoru("k", istemci=ist)
    r = await m.cevir(["Hello", "World"], "en", "tr", {"Ellie": "Ellie"})
    assert [x.metin for x in r] == ["Merhaba", "Dünya"]
    kw = ist.cagrilar[0]
    assert kw["model"] == "claude-opus-5-5"
    assert kw["output_config"] == {"effort": "low"}
    assert kw["max_tokens"] == 2000
    assert not {"thinking", "temperature"} & kw.keys()
    assert kw["messages"][-1]["role"] == "user"  # prefill yok
    assert "Ellie" in kw["system"]
    assert json.loads(kw["messages"][0]["content"]) == ["Hello", "World"]


async def test_claude_aciklama_ve_kod_blogu():
    ist = SahteIstemci(_yanit('```json\n[{"c":"Üsse dön","a":"Görev: üsse geri dön"}]\n```'))
    (r,) = await ClaudeMotoru("k", istemci=ist).cevir(["Return to base"], "en", "tr", {}, True)
    assert r.aciklama == "Görev: üsse geri dön"


async def test_claude_ret_ve_hatalar():
    import anthropic
    httpx = pytest.importorskip("httpx2")
    r = await ClaudeMotoru("k", istemci=SahteIstemci(_yanit("", "refusal"))).cevir(["x"], "en", "tr", {})
    assert r[0].metin == "x"
    req = httpx.Request("POST", "https://x")
    kimlik = anthropic.AuthenticationError("n", response=httpx.Response(401, request=req), body=None)
    with pytest.raises(AnahtarHatasi):
        await ClaudeMotoru("k", istemci=SahteIstemci(hata=kimlik)).cevir(["x"], "en", "tr", {})
    with pytest.raises(AgHatasi):
        await ClaudeMotoru("k", istemci=SahteIstemci(hata=anthropic.APIConnectionError(request=req))).cevir(["x"], "en", "tr", {})
    with pytest.raises(AnahtarHatasi):
        await ClaudeMotoru(None).cevir(["x"], "en", "tr", {})
