# SPDX-License-Identifier: AGPL-3.0-only
"""Türkçe dublaj sınamaları: model indirmeden, sahte STT/çevirmen/ses motoru/saat ile."""
import asyncio
import builtins
import pathlib
import tempfile

import numpy as np
import pytest

from kopru import anahtarlar, ayarlar, ses as ses_mod, sunucu
from kopru import dublaj as dublaj_mod
from kopru.ceviri.istem import degisken_baglam, dublaj_ipucu, kullanici_metni
from kopru.ceviri.temel import Baglam, Ceviri
from kopru.ceviri.yonetici import CeviriYoneticisi
from kopru.dublaj import donanim, dsp
from kopru.dublaj.cikis import BilgisayarCikis, Kisici, SesDeposu, TvCikis
from kopru.dublaj.elevenlabs import ElevenLabsMotoru
from kopru.dublaj.isleyici import Isleyici
from kopru.dublaj.temel import DublajHatasi
from kopru.dublaj.yonetim import DublajYonetici
from kopru.yayin import Yayin
from tests.conftest import sahte_fabrika

SR = 16000


# ---------- sahte parçalar ----------

class Saat:
    def __init__(self, t=100.0):
        self.t = t

    def __call__(self):
        return self.t


def ses(f0, egim, sure, sr=SR):
    """Sentetik 'konuşmacı': farklı f0/tını = farklı parmak izi."""
    t = np.arange(int(sr * sure)) / sr
    x = sum((1 / (h ** egim)) * np.sin(2 * np.pi * f0 * h * t) for h in range(1, 25) if f0 * h < 7500)
    zarf = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * t) ** 2
    return (x * zarf / np.abs(x).max() * 0.5).astype(np.float32)


class Parca:
    def __init__(self, pcm, bitis, sr=SR):
        self.pcm, self.sr, self.bitis = pcm, sr, bitis
        self.bas = bitis - len(pcm) / sr


class SahteSTT:
    def __init__(self, metin="Where were you last night?"):
        self.metin, self.cagri = metin, []

    async def yaz(self, pcm, sr):
        self.cagri.append(len(pcm))
        return self.metin


class SahteYonetici:
    """CeviriYoneticisi yerine: dublaj_cevir çağrılarını kaydeder."""

    def __init__(self, cevaplar):
        self.cevaplar, self.cagrilar, self.satirlar = list(cevaplar), [], []

    async def dublaj_cevir(self, metin, kaynak, hedef, sure_sn, onceki=None):
        self.cagrilar.append({"metin": metin, "sure_sn": sure_sn, "onceki": onceki})
        return Ceviri(self.cevaplar.pop(0) if len(self.cevaplar) > 1 else self.cevaplar[0])

    def satir_kaydet(self, *a):
        self.satirlar.append(a)


class SahteMotor:
    """Süre = karakter sayısı * saniye_per_harf; yer tutucu 24 kHz sinüs."""
    kod, ad, yerel = "sahte", "Sahte", True

    def __init__(self, harf_sn=0.1):
        self.harf_sn, self.cagrilar = harf_sn, []

    def hazir(self):
        return True

    async def hazirla(self, cb=None):
        if cb:
            cb(100.0, "bitti")

    async def seslendir(self, metin, ref, sr):
        self.cagrilar.append((metin, len(ref), sr))
        n = int(24000 * len(metin) * self.harf_sn)
        return (0.3 * np.sin(2 * np.pi * 180 * np.arange(n) / 24000)).astype(np.float32), 24000


class SahteCikis:
    ad = "sahte"

    def __init__(self):
        self.calinan = []

    async def oynat(self, pcm, sr, ayar, yazi_id=None):
        self.calinan.append((len(pcm) / sr, yazi_id))

    def durdur(self):
        pass


def kur(yonetici, motor=None, cikis_ad="tv", stt=None, ek=None):
    saat = Saat()
    yayin = Yayin()
    q = yayin.abone_ol()
    ayar = {**ayarlar.VARSAYILAN, "dublaj": {**dublaj_mod.VARSAYILAN, "motor": "pocket", "cikis": cikis_ad, **(ek or {})}}
    motor = motor or SahteMotor()
    depo = SesDeposu(saat=saat)
    cikislar = {"tv": TvCikis(depo, yayin), "bilgisayar": SahteCikis()}
    isl = Isleyici(stt or SahteSTT(), yonetici, lambda: motor, lambda ad: cikislar[ad], yayin, lambda: ayar, saat)
    yayin.dinle(isl.olay)
    return isl, yayin, q, depo, motor, saat, cikislar


def bosalt(q):
    o = []
    while not q.empty():
        o.append(q.get_nowait())
    return o


# ---------- boru hattı ----------

async def test_segment_once_yazi_sonra_ses_ve_bellekten_sunulur():
    y = SahteYonetici(["Dün gece neredeydin?"])
    isl, yayin, q, depo, motor, saat, _ = kur(y)
    s = await isl.isle(Parca(ses(150, 1.2, 3.0), saat()))
    olaylar = bosalt(q)
    assert [o for o, _ in olaylar] == ["yazi", "ses"]          # altyazı HER ZAMAN sesten önce
    yazi, sesv = olaylar[0][1], olaylar[1][1]
    assert yazi["metin"] == "Dün gece neredeydin?" and yazi["tur"] == "konusma" and yazi["sure_ms"] >= 1800
    assert sesv["yazi_id"] == yazi["id"] and sesv["url"] == f"/kopru/ses/{sesv['id']}.wav" and sesv["sure_ms"] > 0
    assert depo.al(sesv["id"]).startswith(b"RIFF")             # bellekten sunulacak WAV
    assert s.referans == "kendi" and y.satirlar and y.satirlar[0][2] == "Dün gece neredeydin?"
    assert "dublaj" not in str(y.cagrilar[0]["metin"]).lower()  # çeviriye asıl metin gider


async def test_ekrandaki_altyazi_varsa_onun_metni_ve_kimligi_kullanilir():
    y = SahteYonetici(["Dün gece neredeydin?"])
    isl, yayin, q, depo, motor, saat, _ = kur(y, stt=SahteSTT("where were you last nite"))
    yayin.yayinla("yazi", {"id": "a7", "metin": "Dün gece neredeydin?", "asil": "Where were you last night?",
                           "tur": "altyazi", "konusan": "Ellie", "sure_ms": 3000})
    bosalt(q)
    await isl.isle(Parca(ses(150, 1.2, 3.0), saat() + 1.0))
    olaylar = bosalt(q)
    assert [o for o, _ in olaylar] == ["ses"]                  # zaten altyazı var: yenisi yayınlanmaz
    assert olaylar[0][1]["yazi_id"] == "a7"
    # altyazının hazır Türkçesi seslendirilir (ikinci çeviri isteği yok); OCR metni STT'den iyi
    assert not y.cagrilar and motor.cagrilar[-1][0] == "Dün gece neredeydin?"


async def test_uzak_ya_da_benzemeyen_altyazi_eslesmez():
    y = SahteYonetici(["Merhaba"])
    isl, yayin, q, depo, motor, saat, _ = kur(y, stt=SahteSTT("Hello there friend"))
    yayin.yayinla("yazi", {"id": "a1", "metin": "x", "asil": "Where were you last night?", "sure_ms": 3000})
    bosalt(q)
    await isl.isle(Parca(ses(150, 1.2, 2.0), saat() + 1))
    assert [o for o, _ in bosalt(q)] == ["yazi", "ses"]        # benzemiyor -> kendi altyazısını yayınlar
    isl2, yayin2, q2, _, _, saat2, _ = kur(SahteYonetici(["Merhaba"]), stt=SahteSTT("Where were you last night?"))
    yayin2.yayinla("yazi", {"id": "a1", "metin": "x", "asil": "Where were you last night?", "sure_ms": 3000})
    bosalt(q2)
    await isl2.isle(Parca(ses(150, 1.2, 2.0), saat2() + 10))    # 3 sn penceresi dışında
    assert [o for o, _ in bosalt(q2)] == ["yazi", "ses"]


def test_referans_uc_saniye_ve_ustuyse_kendi_sesi():
    isl, *_ = kur(SahteYonetici(["x"]))
    pcm = np.concatenate([np.zeros(SR), ses(150, 1.2, 4.0), np.zeros(SR)])
    ref, sr, tur = isl.referans_sec(pcm, SR)
    assert tur == "kendi" and sr == SR and 3.0 <= len(ref) / sr < 5.0   # sessizlik kırpıldı
    ref2, _, _ = isl.referans_sec(ses(150, 1.2, 14.0), SR)
    assert len(ref2) / SR <= 10.0 + 1e-6                                # en çok 10 sn


def test_kisa_parca_icin_en_benzer_yakin_konusmacı_ornegi():
    isl, *_ = kur(SahteYonetici(["x"]))
    a, b = ses(110, 1.0, 3.5), ses(240, 2.2, 3.5)
    isl.referans_sec(a, SR)
    isl.referans_sec(b, SR)
    ref, sr, tur = isl.referans_sec(ses(112, 1.05, 1.4), SR)           # A'ya benzeyen kısa parça
    assert tur == "benzer" and len(ref) > 3 * SR
    assert dsp.benzerlik(dsp.parmak_izi(ref, SR), dsp.parmak_izi(a, SR)) > 0.99     # B değil, A seçildi
    ref2, _, tur2 = isl.referans_sec(ses(112, 1.05, 1.4), SR)
    assert np.array_equal(ref, ref2)
    # banka yalnız B içeriyorsa A benzeri kısa parça yanlış kişiye bağlanmaz: kendi kısa örneği kullanılır
    isl2, *_ = kur(SahteYonetici(["x"]))
    isl2.referans_sec(b, SR)
    _, _, tur3 = isl2.referans_sec(ses(112, 1.05, 1.4), SR)
    assert tur3 == "kisa_kendi"


async def test_zaman_sigdirma_siniri_asmazsa_hizlandirir_yeniden_istemez():
    y = SahteYonetici(["a" * 24])            # 2.4 sn ses, parça 2.0 sn
    isl, _, q, depo, motor, saat, _ = kur(y)
    s = await isl.isle(Parca(ses(150, 1.2, 2.0), saat()))
    assert len(y.cagrilar) == 1 and not s.kisaltildi
    assert 1.15 < s.hiz < 1.25 and abs(s.sure_sn - 2.0) < 0.1


async def test_zaman_sigdirma_sinir_asilirsa_bir_kez_kisa_ceviri_ister():
    y = SahteYonetici(["a" * 30, "a" * 22])   # 3.0 sn (oran 1.5) -> kısa: 2.2 sn
    isl, _, q, depo, motor, saat, _ = kur(y)
    s = await isl.isle(Parca(ses(150, 1.2, 2.0), saat()))
    assert len(y.cagrilar) == 2 and y.cagrilar[1]["onceki"] == "a" * 30     # tam bir kez daha, öncekiyle
    assert s.kisaltildi and s.metin == "a" * 22 and len(motor.cagrilar) == 2
    assert abs(s.sure_sn - 2.0) < 0.1


async def test_kisa_ceviri_de_uzunsa_en_cok_siniri_kadar_hizlanir_ucuncu_istek_yok():
    y = SahteYonetici(["a" * 30, "a" * 29])   # kısa hâli de 2.9 sn
    isl, _, q, depo, motor, saat, _ = kur(y)
    s = await isl.isle(Parca(ses(150, 1.2, 2.0), saat()))
    assert len(y.cagrilar) == 2
    assert s.hiz == pytest.approx(1.25) and s.sure_sn == pytest.approx(2.9 / 1.25, abs=0.08)


async def test_kisa_ceviri_istegi_daha_uzun_donerse_yoksayilir():
    y = SahteYonetici(["a" * 30, "a" * 40])
    isl, _, q, depo, motor, saat, _ = kur(y)
    s = await isl.isle(Parca(ses(150, 1.2, 2.0), saat()))
    assert s.metin == "a" * 30 and len(motor.cagrilar) == 1 and s.hiz == pytest.approx(1.25)


async def test_boru_hatti_hicbir_dosya_yazmaz(monkeypatch):
    """open / tempfile hiç çağrılmamalı (WAV da, referans da yalnız bellekte)."""
    cagrilar = []
    gercek_open = builtins.open

    def izli_open(*a, **k):
        cagrilar.append(("open", a[:1]))
        return gercek_open(*a, **k)
    for ad in ("mkstemp", "mkdtemp", "NamedTemporaryFile", "TemporaryFile", "SpooledTemporaryFile", "TemporaryDirectory"):
        monkeypatch.setattr(tempfile, ad, lambda *a, _ad=ad, **k: cagrilar.append(("tempfile", _ad)))
    monkeypatch.setattr(pathlib.Path, "write_bytes", lambda *a, **k: cagrilar.append(("write_bytes",)))
    monkeypatch.setattr(pathlib.Path, "write_text", lambda *a, **k: cagrilar.append(("write_text",)))
    y = SahteYonetici(["a" * 30, "a" * 22])
    isl, yayin, q, depo, motor, saat, cikislar = kur(y)
    monkeypatch.setattr(builtins, "open", izli_open)
    await isl.isle(Parca(ses(150, 1.2, 2.0), saat()))                    # tv
    isl2, *_ = kur(SahteYonetici(["a" * 20]), cikis_ad="bilgisayar")
    await isl2.isle(Parca(ses(150, 1.2, 2.0), saat()))                   # bilgisayar
    assert cagrilar == []


async def test_kendi_caldigimiz_dublaj_geri_dinlenmez():
    y = SahteYonetici(["a" * 15])
    isl, _, q, depo, motor, saat, cikislar = kur(y, cikis_ad="bilgisayar")
    saat.t = 100.0
    await isl.isle(Parca(ses(150, 1.2, 2.0), saat()))
    n = len(isl.stt.cagri)
    saat.t = 100.2                                                       # çalma sırasında yakalanmış parça (loopback)
    assert await isl.isle(Parca(ses(150, 1.2, 1.0), saat())) is None
    assert len(isl.stt.cagri) == n
    saat.t = 110.0                                                       # çok sonra: normal
    assert await isl.isle(Parca(ses(150, 1.2, 1.0), saat())) is not None


async def test_cok_kisa_parca_ve_bos_stt_atlanir():
    isl, *_ = kur(SahteYonetici(["x"]))
    assert await isl.isle(Parca(ses(150, 1.2, 0.3), 100.0)) is None
    isl2, *_ = kur(SahteYonetici(["x"]), stt=SahteSTT("  "))
    assert await isl2.isle(Parca(ses(150, 1.2, 2.0), 100.0)) is None


async def test_kuyruk_geride_kalinca_eski_parcalari_atar():
    isl, *_ = kur(SahteYonetici(["x"]))
    for i in range(6):
        isl.kuyruga_at(i)
    assert isl._kuyruk.qsize() == 3
    assert [isl._kuyruk.get_nowait() for _ in range(3)] == [3, 4, 5]


async def test_oturum_bitince_konusmaci_ornekleri_silinir():
    isl, *_ = kur(SahteYonetici(["x"]))
    isl.referans_sec(ses(150, 1.2, 4.0), SR)
    assert len(isl._banka) == 1
    isl.temizle()
    assert len(isl._banka) == 0


# ---------- DSP ----------

def test_wsola_sureyi_kisaltir_perdeyi_korur():
    x = ses(150, 1.3, 4.0)
    y = dsp.wsola(x, SR, 1.25)
    assert len(y) / SR == pytest.approx(3.2, abs=0.05)
    f = lambda a: np.argmax(np.abs(np.fft.rfft(a))) * SR / len(a)       # noqa: E731
    assert f(y) == pytest.approx(f(x), abs=3.0)
    assert dsp.hizlandir(x, SR, 1.0) is x


def test_wav_bellekte_uretilir_ve_gecerlidir():
    import io
    import wave
    b = dsp.wav_bayt(ses(150, 1.2, 0.5), SR)
    w = wave.open(io.BytesIO(b))
    assert w.getframerate() == SR and w.getnchannels() == 1 and w.getnframes() == SR // 2


# ---------- çıkış: ducking ve TV deposu ----------

class SahteArkaUc:
    def __init__(self):
        self.hacim = {"oyun": 0.8, "tarayici": 0.5}
        self.gunluk = []

    def bul(self):
        return ["oyun"]                     # yalnız oyunun oturumu

    def al(self, o):
        return self.hacim[o]

    def ayarla(self, o, v):
        self.hacim[o] = v
        self.gunluk.append((o, round(v, 4)))


def test_kisici_yumusakca_kisar_ve_tam_eski_degere_doner():
    ark = SahteArkaUc()
    k = Kisici(ark, uyku=lambda s: None)
    k.kis(0.25)
    assert ark.hacim["oyun"] == pytest.approx(0.2) and ark.hacim["tarayici"] == 0.5   # yalnız oyun
    assert len({v for _, v in ark.gunluk}) > 2                                         # ani değil, kademeli
    k.geri_ac()
    assert ark.hacim["oyun"] == pytest.approx(0.8)
    k.geri_ac()                                                                        # ikinci çağrı zarar vermez


async def test_bilgisayar_cikisi_calarken_kisar_hata_olsa_da_geri_acar():
    ark = SahteArkaUc()
    calan = []

    def oynatici(pcm, sr):
        calan.append(ark.hacim["oyun"])
        raise DublajHatasi("dublaj_cikis_yok")
    c = BilgisayarCikis(lambda kaynak: Kisici(ark, uyku=lambda s: None), oynatici)
    with pytest.raises(DublajHatasi):
        await c.oynat(np.zeros(2400, np.float32), 24000, {"dublaj": {"oyun_sesi_kis": 0.25, "ses_seviyesi": 1.0}})
    assert calan == [pytest.approx(0.2)] and ark.hacim["oyun"] == pytest.approx(0.8)


def test_ses_deposu_60_sn_sonra_siler():
    saat = Saat(0.0)
    d = SesDeposu(saat=saat)
    k = d.koy(b"RIFF")
    saat.t = 59.0
    assert d.al(k) == b"RIFF"
    saat.t = 60.1
    assert d.al(k) is None and len(d) == 0


# ---------- API ----------

@pytest.fixture
async def istemci(aiohttp_client, uygulama_ayari):
    uygulama_ayari["motor"] = "sahte"
    uygulama_ayari["yedek_motor"] = ""
    saat = Saat(0.0)
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika, dublaj_fabrikalari={
        "saat": saat, "donanim_fn": lambda: donanim.Donanim("cuda", "NVIDIA RTX 3060", 12.0, 16.0),
        "motor_fabrika": lambda kod, ayar: SahteMotor()})
    c = await aiohttp_client(app)
    c.saat = saat
    c.durum = app[sunucu.DURUM]
    return c


async def test_varsayilan_dublaj_kapali_ve_dogrulama(istemci):
    a = await (await istemci.get("/api/ayarlar")).json()
    assert a["dublaj"]["motor"] == "kapali" and a["dublaj"]["hiz_siniri"] == 1.25 and a["dublaj"]["cikis"] == "bilgisayar"
    for kotu in ({"motor": "sihirli"}, {"cikis": "uzay"}, {"oyun_sesi_kis": 2}, {"ses_seviyesi": -1},
                 {"hiz_siniri": 3}, {"bilinmeyen": 1}, {"elevenlabs_onay": "evet"}, "pocket", {"oyun_sesi_kis": True}):
        r = await istemci.post("/api/ayarlar", json={"dublaj": kotu})
        assert r.status == 400 and (await r.json())["hata"] == "gecersiz_ayar", kotu
    assert (await istemci.post("/api/ayarlar", json={"dublaj": {"oyun_sesi_kis": 0.5}})).status == 200
    assert (await (await istemci.get("/api/ayarlar")).json())["dublaj"]["oyun_sesi_kis"] == 0.5


async def test_ses_dosyasi_bellekten_sunulur_60_sn_sonra_404(istemci):
    d = istemci.durum
    kimlik = d.dublaj.depo.koy(dsp.wav_bayt(ses(150, 1.2, 0.3), SR))
    r = await istemci.get(f"/kopru/ses/{kimlik}.wav")
    assert r.status == 200 and r.headers["Content-Type"] == "audio/wav" and r.headers["Access-Control-Allow-Origin"] == "*"
    assert (await r.read()).startswith(b"RIFF")
    istemci.saat.t = 61.0
    r = await istemci.get(f"/kopru/ses/{kimlik}.wav")
    assert r.status == 404 and (await r.json())["hata"] == "bulunamadi"
    assert (await istemci.get("/kopru/ses/yok.wav")).status == 404


async def test_ses_dosyasi_yerel_agdan_okunabilir(istemci, monkeypatch):
    kimlik = istemci.durum.dublaj.depo.koy(b"RIFFxxxx")
    monkeypatch.setattr(sunucu, "uzak_adres", lambda req: "192.168.1.50")        # TV
    assert (await istemci.get(f"/kopru/ses/{kimlik}.wav")).status == 200
    assert (await istemci.get("/api/dublaj")).status == 403                      # panel API'si yerel kalır
    assert (await istemci.post("/api/dublaj/dene", json={})).status == 403


async def test_api_dublaj_durum_oneri_ve_ayar(istemci):
    j = await (await istemci.get("/api/dublaj")).json()
    assert j["motor"] == "kapali" and j["onerilen"] == "chatterbox" and j["ekran_karti"] == "NVIDIA RTX 3060"
    assert j["indirme"]["durum"] == "bosta"
    r = await istemci.post("/api/dublaj", json={"motor": "pocket", "cikis": "tv"})
    assert r.status == 200
    j = await (await istemci.get("/api/dublaj")).json()
    assert j["motor"] == "pocket" and j["hazir"] is True
    assert (await istemci.post("/api/dublaj", json={"motor": "yok"})).status == 400


async def test_api_hazirla_ilerleme_ve_dene(istemci):
    assert (await istemci.post("/api/dublaj/hazirla")).status == 400                 # motor kapalı
    await istemci.post("/api/dublaj", json={"motor": "pocket", "cikis": "tv"})
    r = await istemci.post("/api/dublaj/hazirla")
    assert r.status == 200
    for _ in range(50):
        if (await (await istemci.get("/api/dublaj")).json())["indirme"]["durum"] == "bitti":
            break
        await asyncio.sleep(0.02)
    assert (await (await istemci.get("/api/dublaj")).json())["indirme"] == {"durum": "bitti", "yuzde": 100, "hata": None}
    q = istemci.durum.yayin.abone_ol()
    r = await istemci.post("/api/dublaj/dene", json={"metin": "Merhaba, nasılsın?"})
    j = await r.json()
    assert r.status == 200 and j["tamam"] and j["cikis"] == "tv" and j["sure_ms"] > 0
    (olay, veri) = q.get_nowait()
    assert olay == "ses" and veri["yazi_id"] is None
    assert (await istemci.get(veri["url"])).status == 200                           # yakalanmış ses yok: sentetik referans
    assert (await istemci.post("/api/dublaj/dene", json={"metin": ""})).status == 400


async def test_dene_motor_hazir_degilse_dostca_hata(istemci):
    r = await istemci.post("/api/dublaj/dene", json={"metin": "Merhaba"})
    j = await r.json()
    assert r.status == 409 and j["hata"] == "dublaj_hazir_degil" and "Hazırla" in j["mesaj"]


async def test_elevenlabs_birinci_onay_olmadan_secilemez_ikinci_onay_ayri(istemci):
    r = await istemci.post("/api/dublaj", json={"motor": "elevenlabs"})
    assert r.status == 400 and (await r.json())["hata"] == "dublaj_onay_gerekli"
    r = await istemci.post("/api/ayarlar", json={"dublaj": {"motor": "elevenlabs"}})
    assert r.status == 400
    # klon onayı birinci onay olmadan kaydedilemez (sessizce düşer)
    await istemci.post("/api/dublaj", json={"elevenlabs_klon_onay": True})
    assert istemci.durum.ayar["dublaj"]["elevenlabs_klon_onay"] is False
    r = await istemci.post("/api/dublaj", json={"motor": "elevenlabs", "elevenlabs_onay": True})
    assert r.status == 200 and istemci.durum.ayar["dublaj"]["elevenlabs_klon_onay"] is False
    await istemci.post("/api/dublaj", json={"elevenlabs_klon_onay": True})
    assert istemci.durum.ayar["dublaj"]["elevenlabs_klon_onay"] is True
    # onay geri alınınca klon da düşer ve motor kapanır
    await istemci.post("/api/dublaj", json={"elevenlabs_onay": False})
    d = istemci.durum.ayar["dublaj"]
    assert d["elevenlabs_klon_onay"] is False and d["motor"] == "kapali"


async def test_elevenlabs_anahtari_kasaya_gider_ayara_degil(istemci):
    assert (await istemci.post("/api/anahtar", json={"motor": "elevenlabs", "anahtar": "xi-GIZLI"})).status == 200
    assert anahtarlar.oku("elevenlabs") == "xi-GIZLI"
    j = await (await istemci.get("/api/ayarlar")).json()
    assert j["anahtarlar"]["elevenlabs"] is True and "xi-GIZLI" not in str(j)
    assert (await (await istemci.get("/api/dublaj")).json())["elevenlabs_anahtar"] is True


# ---------- ElevenLabs ----------

class SahteIstek:
    def __init__(self, voice_id="v-klon"):
        self.cagrilar, self.voice_id = [], voice_id

    async def __call__(self, yontem, yol, json=None, veri=None, sorgu=None):
        self.cagrilar.append((yontem, yol))
        if yol == "/v1/voices/add":
            return 200, ('{"voice_id": "%s"}' % self.voice_id).encode()
        if yol.startswith("/v1/text-to-speech/"):
            return 200, (np.ones(2400) * 1000).astype("<i2").tobytes()
        return 200, b"{}"


async def test_elevenlabs_anahtar_ve_onay_olmadan_calismaz():
    istek = SahteIstek()
    m = ElevenLabsMotoru("ses-1", onay=True, istek=istek)
    assert m.hazir() is False                                         # anahtar yok
    with pytest.raises(DublajHatasi) as e:
        await m.seslendir("Merhaba", np.zeros(SR, np.float32), SR)
    assert e.value.kod == "dublaj_eleven_anahtar_yok" and istek.cagrilar == []
    anahtarlar.yaz("elevenlabs", "xi-test")
    assert m.hazir() is True
    onaysiz = ElevenLabsMotoru("ses-1", onay=False, istek=istek)
    assert onaysiz.hazir() is False
    with pytest.raises(DublajHatasi) as e:
        await onaysiz.hazirla()
    assert e.value.kod == "dublaj_eleven_onay_yok"
    sessiz = ElevenLabsMotoru("", onay=True, klon_onay=False, istek=istek)
    assert sessiz.hazir() is False
    with pytest.raises(DublajHatasi) as e:
        await sessiz.hazirla()
    assert e.value.kod == "dublaj_eleven_ses_yok"


async def test_elevenlabs_klon_onayi_yoksa_ses_ornegi_asla_yuklenmez():
    anahtarlar.yaz("elevenlabs", "xi-test")
    istek = SahteIstek()
    m = ElevenLabsMotoru("ses-1", klon_onay=False, onay=True, istek=istek)
    pcm, sr = await m.seslendir("Merhaba", ses(150, 1.2, 3.0), SR)
    assert sr == 24000 and len(pcm) == 2400
    assert istek.cagrilar == [("POST", "/v1/text-to-speech/ses-1")]    # yalnız metin; /voices/add YOK
    with pytest.raises(DublajHatasi) as e:                             # doğrudan çağrı bile reddedilir
        await m._klon_kimligi(ses(150, 1.2, 3.0), SR)
    assert e.value.kod == "dublaj_eleven_klon_onay_yok" and len(istek.cagrilar) == 1


async def test_elevenlabs_klon_ikinci_onayla_yuklenir_ve_oturum_bitince_silinir():
    anahtarlar.yaz("elevenlabs", "xi-test")
    istek = SahteIstek("v-klon")
    m = ElevenLabsMotoru("", klon_onay=True, onay=True, istek=istek)
    ornek = ses(150, 1.2, 3.0)
    await m.seslendir("Merhaba", ornek, SR)
    await m.seslendir("Tekrar", ornek, SR)                             # aynı örnek: yeniden yüklenmez
    assert [c for c in istek.cagrilar if c[1] == "/v1/voices/add"] == [("POST", "/v1/voices/add")]
    assert ("POST", "/v1/text-to-speech/v-klon") in istek.cagrilar
    await m.kapat()
    assert ("DELETE", "/v1/voices/v-klon") in istek.cagrilar


async def test_elevenlabs_hata_kodlari():
    anahtarlar.yaz("elevenlabs", "xi-test")

    async def kotu(yontem, yol, **k):
        return 401, b"{}"
    m = ElevenLabsMotoru("ses-1", onay=True, istek=kotu)
    with pytest.raises(DublajHatasi) as e:
        await m.seslendir("x", np.zeros(SR, np.float32), SR)
    assert e.value.kod == "dublaj_eleven_anahtar_gecersiz"


# ---------- donanım ----------

@pytest.mark.parametrize("d,beklenen", [
    (donanim.Donanim("cuda", "RTX 3060", 12.0), "chatterbox"),
    (donanim.Donanim("cuda", "RTX 4050", 6.0), "chatterbox"),         # sınır dahil
    (donanim.Donanim("cuda", "GTX 1050", 4.0), "pocket"),
    (donanim.Donanim("cuda", "?", None), "pocket"),
    (donanim.Donanim("mps", "Apple", None), "pocket"),
    (donanim.Donanim(), "pocket"),
])
def test_onerilen_motor(d, beklenen):
    assert donanim.onerilen(d) == beklenen


def test_algila_torch_yoksa_nvidia_smi_kullanir(monkeypatch):
    monkeypatch.setattr(donanim, "_torch_bak", lambda: None)
    monkeypatch.setattr(donanim, "_nvidia_smi", lambda: donanim.Donanim("cuda", "NVIDIA RTX 3060", 12.0))
    monkeypatch.setattr(donanim, "ram_gb", lambda: 32.0)
    d = donanim.algila()
    assert (d.tur, d.ekran_karti, d.vram_gb, d.ram_gb) == ("cuda", "NVIDIA RTX 3060", 12.0, 32.0)
    assert donanim.onerilen(d) == "chatterbox"
    monkeypatch.setattr(donanim, "_nvidia_smi", lambda: None)
    assert donanim.onerilen(donanim.algila()) == "pocket"


def test_nvidia_smi_yoksa_cokmez(monkeypatch):
    def yok(*a, **k):
        raise FileNotFoundError
    monkeypatch.setattr(donanim.subprocess, "run", yok)
    assert donanim._nvidia_smi() is None


# ---------- paketler eksikken çökmez ----------

async def test_paketler_kurulu_degilse_acik_hata(monkeypatch):
    import sys
    for ad in ("pocket_tts", "chatterbox", "chatterbox.mtl_tts", "torch"):
        monkeypatch.setitem(sys.modules, ad, None)                    # import -> ImportError
    for kod in ("pocket", "chatterbox"):
        m = dublaj_mod.motor_olustur(kod, ayarlar.yukle())
        with pytest.raises(DublajHatasi) as e:
            await m.hazirla()
        assert e.value.kod == "dublaj_paket_yok"
        with pytest.raises(DublajHatasi) as e2:
            await m.seslendir("x", np.zeros(SR, np.float32), SR)
        assert e2.value.kod == "dublaj_hazir_degil"


# ---------- mikrofon asla ----------

class SahteHoparlor:
    name = "Hoparlor (Test)"


class SahteLoopback:
    isloopback = True

    class _Kayit:
        def __init__(self, bloklar, dur):
            self.bloklar, self.dur = list(bloklar), dur

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def record(self, numframes):
            if not self.bloklar:
                self.dur.set()
                return np.zeros((numframes, 1), np.float32)
            return self.bloklar.pop(0).reshape(-1, 1)

    def __init__(self, bloklar=(), dur=None):
        self.bloklar, self.dur, self.istekler = bloklar, dur, []

    def recorder(self, samplerate, channels):
        self.istekler.append((samplerate, channels))
        return self._Kayit(self.bloklar, self.dur)


class SahteSoundcard:
    def __init__(self, kaynak):
        self.kaynak, self.cagrilar = kaynak, []

    def default_speaker(self):
        self.cagrilar.append("default_speaker")
        return SahteHoparlor()

    def get_microphone(self, id, include_loopback=False):
        self.cagrilar.append(("get_microphone", id, include_loopback))
        return self.kaynak

    def default_microphone(self):
        raise AssertionError("MİKROFON İSTENDİ")

    def all_microphones(self, include_loopback=False):
        raise AssertionError("MİKROFON LİSTELENDİ")


def test_ses_kaynagi_yalniz_loopback_ister_mikrofon_asla():
    sc = SahteSoundcard(SahteLoopback())
    kaynak = ses_mod.kaynak_ac(sc)
    assert kaynak.isloopback is True
    assert sc.cagrilar == ["default_speaker", ("get_microphone", "Hoparlor (Test)", True)]
    gercek_mik = SahteLoopback()
    gercek_mik.isloopback = False                                      # loopback olmayan (gerçek mikrofon) reddedilir
    with pytest.raises(ses_mod.SesHatasi):
        ses_mod.kaynak_ac(SahteSoundcard(gercek_mik))


def test_ses_kaynagi_konusma_parcalarini_loopback_uzerinden_alir():
    import threading
    dur = threading.Event()
    sesli = (0.2 * np.sin(2 * np.pi * 200 * np.arange(4000) / SR)).astype(np.float32)
    sessiz = np.zeros(4000, np.float32)
    lb = SahteLoopback([sesli] * 3 + [sessiz] * 3, dur)
    alinan = []
    k = ses_mod.SesKaynagi(alinan.append, saat=lambda: 50.0, kaynak_fabrika=lambda: ses_mod.kaynak_ac(SahteSoundcard(lb)))
    k._dur = dur
    k._calis()
    assert lb.istekler == [(SR, 1)] and len(alinan) == 1
    assert alinan[0].sr == SR and alinan[0].bitis == 50.0 and len(alinan[0].pcm) > 0


def test_kaynak_kodunda_mikrofon_ve_dosya_yazimi_yok():
    """Kaynak taraması: mikrofon aygıtı çağrıları ve ses dosyası yazımı bulunmamalı."""
    kok = pathlib.Path(sunucu.__file__).parent
    yasak = ("default_microphone", "all_microphones", "InputStream", "sd.rec(", "sf.write", "soundfile.write",
             "wavfile.write", "torchaudio.save", ".save(")
    for yol in list((kok / "dublaj").glob("*.py")) + [kok / "ses" / "__init__.py"]:
        metin = yol.read_text(encoding="utf-8")
        kod = "\n".join(s for s in metin.splitlines() if not s.lstrip().startswith(("#", '"', "'")))
        for y in yasak:
            assert y not in kod, f"{yol.name}: {y}"


# ---------- çeviri ipucu ----------

class IpucuMotoru:
    kod, ad, anahtar_gerekli, cevrimdisi = "ipucu", "İpucu", False, True
    baglam_destekler = True

    def __init__(self):
        self.baglamlar = []

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False, baglam=None):
        self.baglamlar.append(baglam)
        return [Ceviri("Kısa Türkçe cümle") for _ in metinler]


async def test_dublaj_cevirisi_ipucu_ile_ve_hafiza_onbellege_dokunmadan():
    from kopru.onbellek import Onbellek
    onb = Onbellek(":memory:")
    motor = IpucuMotoru()
    y = CeviriYoneticisi(motor, None, onb)
    c = await y.dublaj_cevir("Where were you?", "otomatik", "tr", 2.0)
    assert c.metin == "Kısa Türkçe cümle"
    ip = motor.baglamlar[0].ipucu
    assert "SPOKEN ALOUD" in ip and "2.0 seconds" in ip and "söylenebilir" in ip
    assert onb.al("Where were you?", "otomatik", "tr", "varsayilan", False) is None   # önbelleğe yazılmadı
    await y.dublaj_cevir("Where were you?", "otomatik", "tr", 2.0, onceki="Çok uzun önceki cümle")
    assert "SHORTER" in motor.baglamlar[1].ipucu and "Çok uzun önceki cümle" in motor.baglamlar[1].ipucu
    # altyazı çevirisi ipucu taşımaz
    await y.cevir(["Hello"], "otomatik", "tr")
    assert motor.baglamlar[2].ipucu == ""


def test_istem_ipucu_degisken_kisimda():
    b = Baglam(oyun_ad="X", ipucu=dublaj_ipucu(3.0))
    assert "DUBBING MODE" in degisken_baglam(b) and "DUBBING MODE" in kullanici_metni(["Hi"], b)
    assert "DUBBING" not in kullanici_metni(["Hi"], Baglam())


# ---------- yönetici: uçtan uca (sahte ses kaynağı) ----------

class SahteKaynak:
    """kopru.ses.SesKaynagi yerine: başlatılınca bir konuşma parçası verir."""
    ornek = []

    def __init__(self, parca_cb, saat, hata_cb=None):
        self.parca_cb, self.saat, self.durdu = parca_cb, saat, False
        SahteKaynak.ornek.append(self)

    def baslat(self, dublaj=True):
        self.parca_cb(Parca(ses(150, 1.2, 2.5), self.saat()))

    def durdur(self):
        self.durdu = True


async def test_yonetici_baslat_parca_islenir_durdurulunca_temizlenir():
    saat = Saat()
    yayin = Yayin()
    q = yayin.abone_ol()
    ayar = {**ayarlar.VARSAYILAN, "dublaj": {**dublaj_mod.VARSAYILAN, "motor": "pocket", "cikis": "tv"}}
    y = SahteYonetici(["Dün gece neredeydin?"])
    ilerleme = []

    class IlerlemeliMotor(SahteMotor):
        async def hazirla(self, cb=None):
            if cb:
                cb(40.0, "indiriliyor")
                ilerleme.append(40)
                cb(100.0, "bitti")
    yon = DublajYonetici(lambda: ayar, yayin, lambda: y, motor_fabrika=lambda k, a: IlerlemeliMotor(),
                         stt_fabrika=lambda a: SahteSTT(), kaynak_fabrika=SahteKaynak, saat=saat,
                         donanim_fn=lambda: donanim.Donanim())
    yon.hazirla_baslat()
    for _ in range(50):
        if yon.indirme["durum"] == "bitti":
            break
        await asyncio.sleep(0.01)
    assert yon.indirme == {"durum": "bitti", "yuzde": 100, "hata": None} and ilerleme == [40]
    yon.senkronla(True)
    olaylar = []
    for _ in range(100):
        olaylar += bosalt(q)
        if any(o == "ses" for o, _ in olaylar):
            break
        await asyncio.sleep(0.02)
    assert [o for o, _ in olaylar] == ["yazi", "ses"]
    assert SahteKaynak.ornek[-1].durdu is False
    yon.durdur()
    await asyncio.sleep(0.02)
    assert SahteKaynak.ornek[-1].durdu is True and len(yon.depo) == 0


async def test_yonetici_kapaliyken_hicbir_sey_baslatmaz():
    yayin = Yayin()
    ayar = {**ayarlar.VARSAYILAN}
    SahteKaynak.ornek.clear()
    yon = DublajYonetici(lambda: ayar, yayin, lambda: None, kaynak_fabrika=SahteKaynak)
    yon.senkronla(True)
    await asyncio.sleep(0.02)
    assert SahteKaynak.ornek == [] and yon._gorev is None


async def test_yonetici_motor_hazir_degilse_dostca_hata_cokmez():
    yayin = Yayin()
    ayar = {**ayarlar.VARSAYILAN, "dublaj": {**dublaj_mod.VARSAYILAN, "motor": "pocket"}}

    class HazirDegil(SahteMotor):
        def hazir(self):
            return False
    yon = DublajYonetici(lambda: ayar, yayin, lambda: None, motor_fabrika=lambda k, a: HazirDegil(),
                         kaynak_fabrika=SahteKaynak, donanim_fn=lambda: donanim.Donanim())
    SahteKaynak.ornek.clear()
    yon.senkronla(True)
    await asyncio.sleep(0.05)
    assert yon.son_hata == "dublaj_hazir_degil" and SahteKaynak.ornek == []


def test_numpy_yokken_program_acilir_dublaj_kapali_kalir(tmp_path):
    """numpy (dublaj paketi) kurulu değilken sunucu içe aktarılabilmeli; çökme yok."""
    import os
    import subprocess
    import sys
    kod = ("import sys; sys.modules['numpy']=None\n"
           "import kopru.sunucu as s\n"
           "from kopru import ayarlar\n"
           "d = s.Durum(ayarlar.yukle())\n"
           "assert d.dublaj.motor_kodu() == 'kapali'\n"
           "print('TAMAM')\n")
    r = subprocess.run([sys.executable, "-c", kod], capture_output=True, text=True, timeout=60,
                       env={**os.environ, "KOPRU_AYAR_DIZINI": str(tmp_path)}, cwd=str(pathlib.Path(__file__).parent.parent))
    assert "TAMAM" in r.stdout, r.stderr
