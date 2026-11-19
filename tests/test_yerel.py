# SPDX-License-Identifier: AGPL-3.0-only
"""Çevrimdışı motor: dil dosyası indirme/açma, durum, hata kodları, sözlük yer tutucuları."""
import asyncio
import io
import tempfile
import zipfile
from pathlib import Path

import pytest

from kopru.ceviri import argos_model, yerel
from kopru.ceviri.temel import MotorHatasi


def _paket_zip(ekstra: dict[str, bytes] | None = None, model: bool = True) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        if model:
            z.writestr("translate-en_tr-1_5/model/model.bin", b"x" * 1000)
            z.writestr("translate-en_tr-1_5/sentencepiece.model", b"sp")
        z.writestr("translate-en_tr-1_5/stanza/buyuk.bin", b"y" * 500)
        for ad, v in (ekstra or {}).items():
            zi = zipfile.ZipInfo("x")
            zi.filename = ad   # adı olduğu gibi yaz (Windows'ta ZipInfo '\\'yi '/' yapardı)
            z.writestr(zi, v)
    return b.getvalue()


INDEKS = [{"from_code": "en", "to_code": "tr", "type": "translate", "package_version": "1.5",
           "links": ["https://argos-net.com/v1/translate-en_tr-1_5.argosmodel"]},
          {"from_code": "en", "to_code": "tr", "type": "translate", "package_version": "1.0",
           "links": ["https://evil.example/x.argosmodel"]}]


class _Yanit(io.BytesIO):
    def __init__(self, veri):
        super().__init__(veri)
        self.headers = {"Content-Length": str(len(veri))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture(autouse=True)
def temiz(monkeypatch):
    yerel._isler.clear()
    yerel._durumlar.clear()
    yerel._cevirici_onbellek.clear()
    yield


@pytest.fixture
def ag(monkeypatch):
    """Sahte indeks + sahte indirme; çağrı sayısını sayar."""
    s = {"veri": _paket_zip(), "indirme": 0}

    def ac(url):
        assert url.startswith("https://argos-net.com/")
        s["indirme"] += 1
        return _Yanit(s["veri"])
    monkeypatch.setattr(argos_model, "indeksi_getir", lambda: INDEKS)
    monkeypatch.setattr(argos_model, "_ac", ac)
    return s


def test_paket_secimi_en_yeni_ve_url_denetimi():
    assert argos_model.paket_sec(INDEKS, "en", "tr")["package_version"] == "1.5"
    with pytest.raises(argos_model.ModelHatasi):
        argos_model.paket_sec(INDEKS, "en", "xx")
    assert argos_model.url_izinli_mi("https://raw.githubusercontent.com/a/b")
    assert argos_model.url_izinli_mi("https://argos-net.com/v1/x")
    assert not argos_model.url_izinli_mi("http://argos-net.com/v1/x")
    assert not argos_model.url_izinli_mi("https://argos-net.com.evil.io/x")
    assert not argos_model.url_izinli_mi("https://example.com/x")


def test_kur_ve_durum(ag):
    assert yerel.durum() == {"hazir": False, "boyut_mb": None,
                             "indirme": {"durum": "yok", "yuzde": 0, "mesaj": None}}
    asyncio.run(yerel.hazirla("en", "tr"))
    d = yerel.durum("en", "tr")
    assert d["hazir"] and d["indirme"]["durum"] == "bitti" and d["indirme"]["yuzde"] == 100
    assert d["boyut_mb"] >= 1
    kok = argos_model.paket_dizini("en", "tr")
    model, sp = argos_model.modeli_bul(kok)
    assert (model / "model.bin").is_file() and sp.name == "sentencepiece.model"
    assert not list(kok.rglob("buyuk.bin"))   # stanza açılmaz
    assert not [p for p in kok.parent.iterdir() if p.name != "en_tr"]   # geçici dosya kalmadı
    # idempotent: ikinci çağrı yeniden indirmez
    asyncio.run(yerel.hazirla("en", "tr"))
    assert ag["indirme"] == 1


def test_ilerleme_bildirimi(ag):
    gelen = []
    asyncio.run(yerel.hazirla("en", "tr", gelen.append))
    assert gelen and gelen[-1] == 100 and all(0 <= y <= 100 for y in gelen)


def test_indirme_ilerlemesi_parca_parca(monkeypatch):
    veri = b"z" * (700 * 1024)
    monkeypatch.setattr(argos_model, "_ac", lambda url: _Yanit(veri))
    y = []
    hedef = Path(tempfile.mkdtemp()) / "a"
    assert argos_model.indir("https://argos-net.com/a", hedef, y.append) == len(veri)
    assert y == sorted(y) and y[-1] >= 90


def test_eszamanli_hazirla_tek_indirme(ag, monkeypatch):
    import time
    gercek = argos_model.kur

    def yavas(*a, **k):
        time.sleep(0.4)
        return gercek(*a, **k)
    monkeypatch.setattr(argos_model, "kur", yavas)

    async def dene():
        gorev = [asyncio.create_task(yerel.hazirla("en", "tr")) for _ in range(4)]
        await asyncio.sleep(0.1)
        assert yerel.durum()["indirme"]["durum"] == "iniyor"
        return await asyncio.gather(*gorev)
    sonuc = asyncio.run(dene())
    assert all(s["hazir"] for s in sonuc) and ag["indirme"] == 1


def test_bozuk_zip_reddedilir(ag):
    ag["veri"] = b"bu zip degil"
    with pytest.raises(MotorHatasi) as e:
        asyncio.run(yerel.hazirla("en", "tr"))
    assert e.value.kod == "yerel_indirme_hatasi"
    d = yerel.durum()
    assert not d["hazir"] and d["indirme"]["durum"] == "hata" and d["indirme"]["mesaj"]
    assert not list(argos_model.modeller_dizini().glob("*.indiriliyor"))
    assert not list(argos_model.modeller_dizini().glob("*.aciliyor"))


@pytest.mark.parametrize("ad", ["../kacak.txt", "/mutlak.txt", "a/../../kacak.txt", "C:/x.txt", "a\\b.txt"])
def test_yol_gecisi_reddedilir(ag, ad):
    ag["veri"] = _paket_zip({ad: b"kotu"})
    with pytest.raises(MotorHatasi):
        asyncio.run(yerel.hazirla("en", "tr"))
    assert not argos_model.hazir_mi("en", "tr")
    kok = argos_model.modeller_dizini().parent
    assert not (kok / "kacak.txt").exists()


def test_model_eksik_paket_reddedilir(ag):
    ag["veri"] = _paket_zip(model=False)
    with pytest.raises(MotorHatasi):
        asyncio.run(yerel.hazirla("en", "tr"))
    assert not argos_model.paket_dizini("en", "tr").exists()


def test_boyut_siniri(ag, monkeypatch):
    monkeypatch.setattr(argos_model, "ACILMIS_ENFAZLA", 100)
    with pytest.raises(MotorHatasi):
        asyncio.run(yerel.hazirla("en", "tr"))


def test_dil_dosyasi_yok_hatasi():
    with pytest.raises(MotorHatasi) as e:
        asyncio.run(yerel.YerelMotor().cevir(["Hello"], "en", "tr", {}))
    assert type(e.value) is MotorHatasi
    assert e.value.kod == "yerel_dil_dosyasi_yok"
    assert "İndir" in str(e.value) and "100 MB" in str(e.value)


def test_bilesen_yok_hatasi(ag, monkeypatch):
    import builtins
    asyncio.run(yerel.hazirla("en", "tr"))
    gercek = builtins.__import__

    def sahte(ad, *a, **k):
        if ad == "ctranslate2":
            raise ImportError("yok")
        return gercek(ad, *a, **k)
    monkeypatch.setattr(builtins, "__import__", sahte)
    with pytest.raises(MotorHatasi) as e:
        asyncio.run(yerel.YerelMotor().cevir(["Hello"], "en", "tr", {}))
    assert e.value.kod == "yerel_bilesen_yok"
    assert not yerel.YerelMotor.kurulu_mu()


class SahteSonuc:
    def __init__(self, jetonlar):
        self.hypotheses = [jetonlar]


class SahteCevirici:
    """Her cümleyi büyük harfe çevirir (jetonları aynen geçirir)."""
    def __init__(self):
        self.cagrilar = []

    def translate_batch(self, parcalar, **kw):
        self.cagrilar.append((parcalar, kw))
        return [SahteSonuc([j.upper() for j in p]) for p in parcalar]


class SahteSP:
    def encode(self, c, out_type=str):
        return c.split(" ")

    def decode(self, j):
        return " ".join(j)


def test_cumle_bolme_ve_batch():
    c, sp = SahteCevirici(), SahteSP()
    assert yerel.cumlelere_bol("Hi. Ok!\n\nYes?") == [["Hi.", "Ok!"], [], ["Yes?"]]
    assert yerel.metni_cevir(c, sp, "hi there. ok!\n\nyes?") == "HI THERE. OK!\n\nYES?"
    parcalar, kw = c.cagrilar[0]
    assert len(parcalar) == 3 and kw["beam_size"] == 2 and kw["max_decoding_length"] >= 64


def _motoru_hazirla(monkeypatch, ag, cevirici, sp):
    asyncio.run(yerel.hazirla("en", "tr"))
    monkeypatch.setattr(yerel, "_yukle", lambda m, s: (cevirici, sp))


def test_cevir_sozluk_korunur(ag, monkeypatch):
    _motoru_hazirla(monkeypatch, ag, SahteCevirici(), SahteSP())
    sonuc = asyncio.run(yerel.YerelMotor().cevir(["go to Hyrule now"], "en", "tr", {"Hyrule": "Hayrül"}))
    assert sonuc[0].metin == "GO TO Hayrül NOW"


def test_yer_tutucu_bozulursa_geri_donus(ag, monkeypatch):
    class Bozan(SahteCevirici):
        def translate_batch(self, parcalar, **kw):
            return [SahteSonuc([j for j in p if "T0" not in j and "[[" not in j]) for p in parcalar]
    _motoru_hazirla(monkeypatch, ag, Bozan(), SahteSP())
    sonuc = asyncio.run(yerel.YerelMotor().cevir(["go to Hyrule now"], "en", "tr", {"Hyrule": "Hayrül"}))
    assert sonuc[0].metin == "go to Hayrül now"


def test_ceviri_hatasi_kodu(ag, monkeypatch):
    class Patlayan:
        def translate_batch(self, *a, **k):
            raise RuntimeError("x")
    _motoru_hazirla(monkeypatch, ag, Patlayan(), SahteSP())
    with pytest.raises(MotorHatasi) as e:
        asyncio.run(yerel.YerelMotor().cevir(["Hi"], "en", "tr", {}))
    assert e.value.kod == "yerel_ceviri_hatasi"


def test_yer_tutucu_sentencepiece_ile(tmp_path):
    """Gerçek (küçük) SentencePiece modeli: [[T0]] jetonlanıp geri birleşince sağlam kalmalı."""
    spm = pytest.importorskip("sentencepiece")
    metin = tmp_path / "c.txt"
    metin.write_text("\n".join(["go to [[T0]] now and meet [[T1]] there", "the [[T0]] is far away",
                                "hello world this is a test of the bridge", "[[T0]] [[T1]] [[T2]]"] * 5), encoding="utf-8")
    spm.SentencePieceTrainer.Train(input=str(metin), model_prefix=str(tmp_path / "sp"), vocab_size=60,
                                   hard_vocab_limit=False, character_coverage=1.0)
    sp = spm.SentencePieceProcessor()
    sp.Load(str(tmp_path / "sp.model"))

    class Gecirici:   # jetonları aynen döndürür: tokenizer + detokenizer turu
        def translate_batch(self, parcalar, **kw):
            return [SahteSonuc(list(p)) for p in parcalar]
    from kopru import sozluk
    korunan, harita = sozluk.koru("Go to Hyrule now and meet Zelda there.", {"Hyrule": "Hayrül", "Zelda": "Zelda"})
    s = yerel.metni_cevir(Gecirici(), sp, korunan)
    assert all(yerel._yer_var(s, y) for y in harita)
    assert sozluk.geri_koy(yerel._YER_DESEN.sub(lambda m: f"[[T{m.group(1)}]]", s), harita) \
        == "Go to Hayrül now and meet Zelda there."
