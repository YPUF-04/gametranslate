# SPDX-License-Identifier: AGPL-3.0-only
"""Video dublajı (PROTOKOL 14.4): aşamalar sahte işçiyle (dosya yazan), sürdürme, adlandırma, API."""
import asyncio
import json
from pathlib import Path

import numpy as np
import pytest

from kopru import sunucu
from kopru.dublaj import donanim
from kopru.dublaj.ortam import DublajOrtami
from kopru.dublaj.temel import DublajHatasi
from kopru.dublaj.video import ASAMALAR, VideoIsi, cikti_yolu, video_gecerli
from kopru.ceviri.istem import video_dublaj_ipucu
from tests.conftest import sahte_fabrika


class SahteIsci:
    """İşçi komutlarını taklit eder; dosya isteyenlere küçük dosyalar yazar."""

    def __init__(self, sure=1.0, durdur_komut=None):
        self.komutlar, self.sure, self.durdur_komut = [], sure, durdur_komut
        self.tts_uzun = {}          # metin -> süre

    async def iste(self, komut, veri=None, ilerleme=None, **_):
        v = veri or {}
        self.komutlar.append((komut, v))
        if ilerleme:
            ilerleme(50.0, "")
        if komut == self.durdur_komut:
            await asyncio.sleep(10)
        if komut == "video_cikar":
            Path(v["cikis"]).write_bytes(b"wav")
            return {"sure_sn": 20.0}
        if komut == "ayir":
            Path(v["ses_cikis"]).write_bytes(b"s")
            Path(v["arka_cikis"]).write_bytes(b"a")
            return {}
        if komut == "yaziya":
            k = [{"k": "Where", "b": 1.0, "s": 1.3}, {"k": "were", "b": 1.35, "s": 1.6}, {"k": "you?", "b": 1.65, "s": 2.2},
                 {"k": "Shut", "b": 5.0, "s": 5.3}, {"k": "up!", "b": 5.35, "s": 5.8},
                 {"k": "Let's", "b": 9.0, "s": 9.3}, {"k": "go.", "b": 9.35, "s": 10.0}]
            return {"kelimeler": k, "dil": "en"}
        if komut == "izler":
            a, b = np.eye(4)[0], np.eye(4)[1]
            return {"izler": [a.tolist(), b.tolist(), a.tolist()], "puanlar": [10.0, 5.0, 8.0], "rms": [0.1] * 3,
                    "duygular": [{"canlilik": 0.5, "cfg": 0.5}, {"canlilik": 1.0, "cfg": 0.35}, {"canlilik": 0.5, "cfg": 0.5}]}
        if komut == "referans_kaydet":
            Path(v["cikis"]).write_bytes(b"ref")
            return {"sure_sn": 3.0}
        if komut == "seslendir":
            Path(v["cikis"]).write_bytes(b"tts")
            return {"sure_sn": self.tts_uzun.get(v["metin"], 0.8)}
        if komut == "hizlandir":
            Path(v["cikis"]).write_bytes(b"hiz")
            return {"sure_sn": 1.0}
        if komut == "karistir":
            Path(v["cikis"]).write_bytes(b"mix")
            return {}
        if komut == "video_birlestir":
            Path(v["cikis"]).write_bytes(b"MP4")
            return {}
        raise DublajHatasi("dublaj_isci_komut", komut)


class SahteCevirmen:
    def __init__(self):
        self.cagrilar = []

    async def video_cevir(self, metinler, sureler, kaynak, hedef, konusanlar=None, onceki=None, kisalt=None):
        self.cagrilar.append({"metinler": metinler, "sureler": sureler, "konusanlar": konusanlar, "kisalt": kisalt})
        if kisalt:
            return ["Kısa."]
        tablo = {"Where were you?": "Neredeydin?", "Shut up!": "Kes sesini!", "Let's go.": "Hadi gidelim, hemen şimdi."}
        return [tablo[m] for m in metinler]


def ayar():
    return {"kaynak_dil": "en", "hedef_dil": "tr", "dublaj": {"hiz_siniri": 1.25, "video_motor": "chatterbox", "video_srt": True}}


@pytest.fixture
def video(tmp_path):
    v = tmp_path / "kayit" / "gta6.mp4"
    v.parent.mkdir()
    v.write_bytes(b"orijinal video")
    return v


async def test_tum_asamalar_karakter_sesi_duygu_sigdirma_ve_cikti(video, tmp_path):
    isci, cev = SahteIsci(), SahteCevirmen()
    isci.tts_uzun = {"Hadi gidelim, hemen şimdi.": 2.0, "Kısa.": 1.2}   # 1 sn'lik satıra sığmaz → kısa çeviri, sonra hızlanır
    olaylar = []
    isl = VideoIsi(video, isci, cev, ayar, tmp_path / "isler", yayinla=olaylar.append)
    await isl.calis()
    b = isl.bilgi()
    assert b["durum"] == "bitti", b
    assert [a["durum"] for a in b["asamalar"]] == ["bitti"] * len(ASAMALAR) and b["yuzde"] == 100
    assert video.read_bytes() == b"orijinal video"                               # asıl video değişmez
    cikti = video.with_name("gta6 - Türkçe dublaj.mp4")
    assert b["cikti"] == str(cikti) and cikti.read_bytes() == b"MP4"
    assert not list(video.parent.glob("*.yaziliyor*"))
    srt = video.with_name("gta6 - Türkçe dublaj.srt").read_text(encoding="utf-8")
    assert "Neredeydin?" in srt and "Kes sesini!" in srt and "00:00:01,000 -->" in srt
    assert not isl.klasor.exists(), "ara dosyalar silinir"
    # konuşmacılar: 1. ve 3. satır aynı kişi, her kişinin kendi örneği
    ses = [v for k, v in isci.komutlar if k == "seslendir"]
    assert ses[0]["ref_yol"] == ses[2]["ref_yol"] != ses[1]["ref_yol"]
    assert ses[1]["duygu"] == {"canlilik": 1.0, "cfg": 0.35} and b["konusmaci_sayisi"] == 2
    # çeviri: bütün satırlar tek istekte, süre ve konuşanla; uzun satır için bir kez kısa çeviri
    assert cev.cagrilar[0]["metinler"] == ["Where were you?", "Shut up!", "Let's go."]
    assert cev.cagrilar[0]["konusanlar"] == ["K1", "K2", "K1"] and cev.cagrilar[1]["kisalt"] == {0: "Hadi gidelim, hemen şimdi."}
    assert [k for k, _ in isci.komutlar].count("hizlandir") == 1
    karis = next(v for k, v in isci.komutlar if k == "karistir")
    assert [round(s["bas"], 2) for s in karis["satirlar"]] == [1.0, 5.0, 9.0]
    assert karis["arka"].endswith("arka.wav")                                     # İngilizce ses tamamen çıkar
    assert olaylar and olaylar[-1]["durum"] == "bitti"


async def test_iptal_edilen_is_kaldigi_asamadan_surer(video, tmp_path):
    isci = SahteIsci(durdur_komut="karistir")
    isl = VideoIsi(video, isci, SahteCevirmen(), ayar, tmp_path / "isler")
    isl.baslat()
    for _ in range(200):
        if isl.asama == "karistir":
            break
        await asyncio.sleep(0.01)
    await isl.iptal()
    b = isl.bilgi()
    assert b["durum"] == "iptal" and b["devam_edilebilir"] and isl.klasor.exists()
    isci2 = SahteIsci()
    isl2 = VideoIsi(video, isci2, SahteCevirmen(), ayar, tmp_path / "isler")
    await isl2.calis()
    assert isl2.bilgi()["durum"] == "bitti"
    assert [k for k, _ in isci2.komutlar] == ["karistir", "video_birlestir"], "bitmiş aşamalar yeniden yapılmaz"


async def test_hata_durumu_ve_mesaj(video, tmp_path):
    class Bozuk(SahteIsci):
        async def iste(self, komut, veri=None, ilerleme=None, **_):
            if komut == "ayir":
                raise DublajHatasi("dublaj_bellek", "CUDA out of memory")
            return await super().iste(komut, veri, ilerleme)
    isl = VideoIsi(video, Bozuk(), SahteCevirmen(), ayar, tmp_path / "isler")
    await isl.calis()
    b = isl.bilgi()
    assert b["durum"] == "hata" and b["hata"] == "dublaj_bellek" and b["devam_edilebilir"]


def test_cikti_adi_asil_dosyayi_ezmez(tmp_path):
    v = tmp_path / "a.mp4"
    v.write_bytes(b"x")
    assert cikti_yolu(v).name == "a - Türkçe dublaj.mp4"
    (tmp_path / "a - Türkçe dublaj.mp4").write_bytes(b"eski")
    assert cikti_yolu(v).name == "a - Türkçe dublaj (2).mp4"


def test_video_dogrulama(tmp_path):
    (tmp_path / "v.MKV").write_bytes(b"x")
    (tmp_path / "n.txt").write_bytes(b"x")
    assert video_gecerli(str(tmp_path / "v.MKV")) is not None
    for kotu in (str(tmp_path / "n.txt"), str(tmp_path), str(tmp_path / "yok.mp4"), "", None, 5, "a\x00.mp4"):
        assert video_gecerli(kotu) is None, kotu


def test_video_istemi_sure_konusan_ve_baglam():
    p = video_dublaj_ipucu([2.0, 0.5], ["K1", "K2"], [("Hi", "Selam")], {1: "Çok uzun bir deneme"})
    assert "#1: 2.0s, max ~26 chars, speaker K1" in p and "#2: 0.5s, max ~8 chars, speaker K2" in p
    assert "Çok uzun bir deneme" in p and "Hi => Selam" in p and "söylenebilir" in p


async def test_video_cevir_yoneticide_tek_istek_ve_sozluk():
    from kopru.ceviri.temel import Ceviri
    from kopru.ceviri.yonetici import CeviriYoneticisi

    class Motor:
        kod, ad, anahtar_gerekli, cevrimdisi = "m", "M", False, False
        baglam_destekler = True

        def __init__(self):
            self.cagri = []

        async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False, baglam=None):
            self.cagri.append((list(metinler), baglam.ipucu if baglam else ""))
            return [Ceviri(f"TR {m}") for m in metinler]
    m = Motor()
    y = CeviriYoneticisi(m, None, None)
    sonuc = await y.video_cevir(["Hello", "Bye"], [1.0, 2.0], "en", "tr", ["K1", "K1"])
    assert sonuc == ["TR Hello", "TR Bye"] and len(m.cagri) == 1 and "VIDEO DUBBING MODE" in m.cagri[0][1]


# ---------- API ----------

@pytest.fixture
async def istemci(aiohttp_client, uygulama_ayari, tmp_path):
    uygulama_ayari["motor"] = "sahte"
    ortam = DublajOrtami(kok=tmp_path / "dublaj-ortami", platform_=("linux", "x86_64"), gelistirici=False)
    secilen = {"yol": None}

    async def secici():
        return secilen["yol"]
    gosterilen = []
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika, dosya_secici=secici,
                                  klasorde_goster=gosterilen.append, video_is_koku=tmp_path / "isler",
                                  dublaj_fabrikalari={"donanim_fn": lambda: donanim.Donanim(), "ortam": ortam,
                                                      "isci": SahteIsci()})
    c = await aiohttp_client(app)
    c.durum, c.ortam, c.secilen, c.gosterilen = app[sunucu.DURUM], ortam, secilen, gosterilen
    return c


async def test_api_dosya_sec_vazgecti_gecersiz_gecerli(istemci, video):
    assert (await (await istemci.post("/api/dublaj/dosya-sec")).json()) == {"yol": None}
    istemci.secilen["yol"] = str(video.with_suffix(".txt"))
    assert (await istemci.post("/api/dublaj/dosya-sec")).status == 400
    istemci.secilen["yol"] = str(video)
    j = await (await istemci.post("/api/dublaj/dosya-sec")).json()
    assert j["ad"] == "gta6.mp4" and j["yol"] == str(video)


async def test_api_video_paket_yokken_409_sonra_calisir_ve_gosterir(istemci, video, monkeypatch):
    assert (await (await istemci.get("/api/dublaj/video")).json()) == {"durum": "bosta"}
    assert (await istemci.post("/api/dublaj/video", json={"yol": "/yok.mp4"})).status == 400
    r = await istemci.post("/api/dublaj/video", json={"yol": str(video)})
    assert r.status == 409 and (await r.json())["hata"] == "dublaj_paket_yok"
    assert (await istemci.post("/api/dublaj/video/goster")).status == 404
    monkeypatch.setattr(istemci.ortam, "kurulu", lambda: True)
    istemci.durum.yonetici.video_cevir = SahteCevirmen().video_cevir
    r = await istemci.post("/api/dublaj/video", json={"yol": str(video)})
    assert r.status == 200 and (await r.json())["durum"] == "calisiyor"
    assert (await istemci.post("/api/dublaj/video", json={"yol": str(video)})).status in (200, 409)
    for _ in range(200):
        j = await (await istemci.get("/api/dublaj/video")).json()
        if j["durum"] != "calisiyor":
            break
        await asyncio.sleep(0.01)
    assert j["durum"] == "bitti", j
    assert (await istemci.post("/api/dublaj/video/goster")).status == 200
    assert istemci.gosterilen == [j["cikti"]]
