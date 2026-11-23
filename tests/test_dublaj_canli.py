# SPDX-License-Identifier: AGPL-3.0-only
"""Canlı Türkçe dublaj 2 (PROTOKOL 14.3/14.5): saf hesaplar, işçinin canlı yakalaması (sahte kaynak),
altyazıyla önden hazırlık, TV'ye erken çalma, ses profili, ayarlar ve API. torch gerekmez."""
import asyncio
import json

import numpy as np
import pytest

from kopru import ayarlar, sunucu
from kopru import dublaj as dublaj_mod
from kopru.ceviri.temel import Ceviri
from kopru.dublaj import donanim
from kopru.dublaj.cikis import SesDeposu, TvCikis
from kopru.dublaj.isci import mantik, protokol
from kopru.dublaj.isci.canli import CanliYakalama, TamamenKalibrasyon
from kopru.dublaj.isleyici import Isleyici
from kopru.dublaj.ortam import DublajOrtami
from kopru.dublaj.profil import SesProfilleri
from kopru.yayin import Yayin
from tests.conftest import sahte_fabrika

SR = 16000


def ton(f0, sure, sr=SR, genlik=0.5):
    t = np.arange(int(sr * sure)) / sr
    x = sum((1 / h) * np.sin(2 * np.pi * f0 * h * t) for h in range(1, 12))
    return (x / np.abs(x).max() * genlik).astype(np.float32)


# ---------- saf hesaplar ----------

def test_satirlara_bol_sessizlik_noktalama_ve_azami_sure():
    k = [{"k": "Where", "b": 0.0, "s": 0.3}, {"k": "were", "b": 0.35, "s": 0.5}, {"k": "you?", "b": 0.55, "s": 1.3},
         {"k": "I", "b": 1.4, "s": 1.5}, {"k": "was", "b": 1.55, "s": 1.8}, {"k": "home.", "b": 1.85, "s": 2.2},
         {"k": "Okay", "b": 3.5, "s": 3.9}, {"k": "", "b": 4.0, "s": 4.1}]
    s = mantik.satirlara_bol(k)
    assert [x.metin for x in s] == ["Where were you?", "I was home.", "Okay"]
    assert s[2].bas == 3.5 and s[0].sure == pytest.approx(1.3)
    uzun = [{"k": f"w{i}", "b": i * 0.5, "s": i * 0.5 + 0.4} for i in range(30)]
    assert all(x.sure <= 8.0 for x in mantik.satirlara_bol(uzun))


def test_konusmaci_kumeleme_ayni_kisiyi_birlestirir():
    rng = np.random.default_rng(1)
    a, b, c = rng.normal(size=256), rng.normal(size=256), rng.normal(size=256)
    izler = [a + 0.1 * rng.normal(size=256), b + 0.1 * rng.normal(size=256), a + 0.1 * rng.normal(size=256),
             c + 0.1 * rng.normal(size=256), b + 0.1 * rng.normal(size=256)]
    assert mantik.kumele(np.array(izler)) == [0, 1, 0, 2, 1]
    assert mantik.kumele(np.zeros((0, 4))) == []


def test_referans_en_temiz_ve_uzun_satirlardan_secilir():
    s = [mantik.Satir(0, 2, "a", 0), mantik.Satir(3, 9, "b", 0), mantik.Satir(10, 12, "c", 1), mantik.Satir(13, 20, "d", 0)]
    r = mantik.referans_araliklari(s, [5.0, 20.0, 10.0, 1.0], hedef_sn=8.0)
    assert (3, 9) in r[0] and (13, 20) not in r[0] and sum(b - a for a, b in r[0]) <= 10.0 and r[1] == [(10, 12)]


def test_duygu_bagirma_canli_fisilti_sakin():
    normal = mantik.duygu(ton(140, 2, genlik=0.1), SR, 0.07)
    bagir = mantik.duygu(ton(220, 2, genlik=0.9), SR, 0.07)
    fisilti = mantik.duygu(ton(140, 2, genlik=0.01), SR, 0.07)
    assert bagir["canlilik"] > normal["canlilik"] > fisilti["canlilik"]
    assert fisilti["canlilik"] <= 0.35 and bagir["cfg"] < normal["cfg"]
    for d in (normal, bagir, fisilti):
        # diller arası klon: abartı en çok 0,9, cfg düşük (0,2-0,45; aksan/robotik okuma azalır)
        assert 0.25 <= d["canlilik"] <= 0.9 and 0.2 <= d["cfg"] <= 0.45


def test_sigdirma_karari():
    assert mantik.sigdir_karari(2.0, 2.0) == ("tamam", 1.0)
    assert mantik.sigdir_karari(2.4, 2.0)[0] == "hizlandir"
    assert mantik.sigdir_karari(3.0, 2.0) == ("kisalt", 1.5)
    assert mantik.sigdir_karari(3.0, 2.0, kisaltma_denendi=True) == ("hizlandir", 1.25)


def test_cumlecik_bolme_ilk_parca_kisa_hic_kelime_kaybolmaz():
    m = "Bak, sana bir şey söyleyeceğim. Dün gece o adamı limanda gördüm ve bence bizi izliyordu, dikkatli ol."
    p = mantik.cumlecik_bol(m)
    assert " ".join(p).split() == m.split() and len(p) >= 2 and len(p[0]) <= len(m) // 2
    assert mantik.cumlecik_bol("") == [] and mantik.cumlecik_bol("Tamam.") == ["Tamam."]


def test_hiz_tahmini_ve_hafif_mod():
    assert mantik.hiz_tahmini(1.0, 10, 30, 2.0) == 1.25           # 3 sn tahmin / 2 sn → sınırda
    assert mantik.hiz_tahmini(1.0, 10, 20, 2.5) == 1.0
    assert mantik.hafif_mi("acik", 24.0) and not mantik.hafif_mi("kapali", 4.0)
    assert mantik.hafif_mi("otomatik", 8.0) and not mantik.hafif_mi("otomatik", 12.0)


def test_parca_plani_ve_bindirmeli_birlestirme_kayipsiz():
    x = np.random.default_rng(2).normal(size=(2, 10_000)).astype(np.float32)
    plan = mantik.parca_plani(10_000, 3000, 0.25)
    assert plan[0][0] == 0 and plan[-1][1] == 10_000
    y = mantik.bindirmeli_birlestir(((b, s, x[:, b:s]) for b, s in plan), 10_000)
    assert np.allclose(y, x, atol=1e-5)


def test_blok_plani_bosluksuz_kaplar():
    from kopru.dublaj.isci.motorlar import blok_plani
    p = blok_plani(1000, 300, 20)
    assert [(yb, ys) for _, _, yb, ys in p] == [(0, 300), (300, 600), (600, 900), (900, 1000)]
    assert p[1][:2] == (280, 620) and p[0][0] == 0 and p[-1][1] == 1000


def test_karistirma_konusmada_arka_plani_kisar_ve_sinirlar():
    sr = 1000
    arka = np.full((2, 4000), 0.5, dtype=np.float32)
    ses = np.full(1000, 0.9, dtype=np.float32)
    y = mantik.karistir(arka, [(ses, 2000)], sr, kis_db=-6.0)
    assert y.shape == (2, 4000) and np.abs(y).max() <= 0.97 + 1e-6
    assert y[0, 500] == pytest.approx(0.5, abs=1e-3)                      # konuşma yok: dokunulmaz
    z = mantik.kisma_zarfi(4000, [(2000, 3000)], sr, -6.0)
    assert z[2500] == pytest.approx(10 ** (-6 / 20)) and z[1000] == 1.0 and 0.5 < z[1950] < 1.0


def test_srt_bicimi():
    assert mantik.srt([(1.5, 3.25, "Merhaba."), (3661.0, 3662.0, "Bay")]) == \
        "1\n00:00:01,500 --> 00:00:03,250\nMerhaba.\n\n2\n01:01:01,000 --> 01:01:02,000\nBay\n"


def test_uyarlamali_vad_kisik_diyalogu_yakalar():
    vad = mantik.UyarlamaliVAD(SR, sessizlik_sn=0.5)
    sessiz = np.random.default_rng(3).normal(scale=0.0005, size=SR // 4).astype(np.float32)
    for _ in range(12):
        assert vad.besle(sessiz) is None
    kisik = ton(150, 0.25, genlik=0.006)                              # %10-20 diyalog düzeyi (sabit eşiğin 0.01 altı)
    for _ in range(6):
        assert vad.besle(kisik) is None
    sonuc = None
    for _ in range(3):
        sonuc = vad.besle(sessiz) or sonuc
    assert sonuc is not None and len(sonuc[0]) >= 6 * SR // 4


def test_akis_ayirici_yalniz_yeni_kismi_dondurur():
    cagrilar = []

    def ayir(p, sr):
        cagrilar.append(len(p))
        return p * 0.25, p * 0.75
    a = mantik.AkisAyirici(ayir, SR, baglam_sn=1.0)
    for i in range(8):
        k, b = a.besle(np.full(SR // 4, i + 1, dtype=np.float32))
    assert k.shape == (SR // 4,) and np.allclose(k, 8 * 0.25) and np.allclose(b, 8 * 0.75)
    assert cagrilar[-1] == SR          # 1 sn bağlam


# ---------- tamamen Türkçe kalibrasyonu ----------

class SahteOturum:
    def __init__(self):
        self.ayarlar = []

    def ayarla(self, v):
        self.ayarlar.append(v)


def _kalibre(sonra_genlik):
    k = TamamenKalibrasyon(SR, saat=lambda: 0.0)
    o = SahteOturum()
    karar = None
    for _ in range(7):
        karar = k.besle(ton(200, 0.25, genlik=0.3), o) or karar
    for _ in range(7):
        karar = k.besle(ton(200, 0.25, genlik=sonra_genlik), o) or karar
    return k, o, karar


def test_kalibrasyon_yakalama_kismadan_once_ise_oyun_tamamen_susar():
    k, o, karar = _kalibre(0.3)
    assert karar == "once" and k.kazanc == 1.0 and o.ayarlar == [0.0]


def test_kalibrasyon_yakalama_kisilmis_sesi_goruyorsa_telafi():
    k, o, karar = _kalibre(0.0)
    assert karar == "telafi" and o.ayarlar == [0.0, 0.03] and k.kazanc == pytest.approx(1 / 0.03)


def test_kalibrasyon_ses_yoksa_basarisiz():
    t = [0.0]
    k = TamamenKalibrasyon(SR, saat=lambda: t[0])
    t[0] = 25.0
    assert k.besle(np.zeros(SR // 4, np.float32), SahteOturum()) == "basarisiz"


# ---------- işçinin canlı yakalaması (sahte kaynak) ----------

class SahteKaynak:
    def __init__(self, bloklar):
        self.bloklar, self.kapandi = list(bloklar), False

    def ac(self):
        pass

    def oku(self):
        import time
        if not self.bloklar:
            time.sleep(0.01)
            return np.zeros(SR // 4, np.float32)
        return self.bloklar.pop(0)

    def kapat(self):
        self.kapandi = True


def test_canli_yakalama_parca_ve_temiz_ses_yollar():
    import time
    olaylar = []
    bloklar = [np.zeros(SR // 4, np.float32)] * 4 + [ton(150, 0.25, genlik=0.3)] * 6 + [np.zeros(SR // 4, np.float32)] * 4
    kaynak = SahteKaynak(bloklar)
    c = CanliYakalama(olaylar.append, ayirici=lambda p, sr: (p * 0.5, p * 0.5), kaynak_fabrika=lambda: kaynak)
    bilgi = c.baslat()
    for _ in range(200):
        if any(o.get("olay") == "parca" for o in olaylar):
            break
        time.sleep(0.01)
    c.durdur()
    p = next(o for o in olaylar if o.get("olay") == "parca")
    ham, temiz = protokol.pcm_coz(p["pcm"]), protokol.pcm_coz(p["temiz"])
    assert len(ham) == len(temiz) and np.allclose(temiz, ham * 0.5, atol=1e-6) and kaynak.kapandi
    assert bilgi["tamamen_turkce"] is False


# ---------- işleyici: altyazıyla önden hazırlık ve TV'ye erken çalma ----------

class SahteSTT:
    def __init__(self, metin):
        self.metin, self.girdi = metin, []

    async def yaz(self, pcm, sr):
        self.girdi.append(pcm)
        return self.metin


class SahteYonetici:
    def __init__(self):
        self.cagrilar, self.satirlar = [], []

    async def dublaj_cevir(self, metin, kaynak, hedef, sure_sn, onceki=None):
        self.cagrilar.append(metin)
        await asyncio.sleep(0)
        return Ceviri("Dün gece neredeydin?")

    def satir_kaydet(self, *a):
        self.satirlar.append(a)


class DuyguluMotor:
    kod, ad, yerel = "chatterbox", "C", True
    duygu_destekli = True
    varsayilan_ses = True

    def __init__(self):
        self.cagrilar = []

    def hazir(self):
        return True

    async def hazirla(self, cb=None):
        pass

    async def seslendir(self, metin, ref, sr, duygu=None):
        self.cagrilar.append((metin, len(ref), duygu))
        return np.zeros(24000, np.float32), 24000


class Saat:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class Parca:
    def __init__(self, pcm, bitis, temiz=None):
        self.pcm, self.sr, self.bitis, self.bas, self.temiz = pcm, SR, bitis, bitis - len(pcm) / SR, temiz


def kur(cikis="tv", ek=None):
    saat, yayin = Saat(), Yayin()
    q = yayin.abone_ol()
    ayar = {**ayarlar.VARSAYILAN, "dublaj": {**dublaj_mod.VARSAYILAN, "motor": "chatterbox", "cikis": cikis, **(ek or {})}}
    motor, y, depo = DuyguluMotor(), SahteYonetici(), SesDeposu(saat=saat)
    stt = SahteSTT("Where were you last night?")
    isl = Isleyici(stt, y, lambda: motor, lambda ad: TvCikis(depo, yayin), yayin, lambda: ayar, saat)
    yayin.dinle(isl.olay)
    return isl, yayin, q, motor, y, stt, saat


def bosalt(q):
    o = []
    while not q.empty():
        o.append(q.get_nowait())
    return o


async def test_temiz_ses_yaziya_ve_klona_gider_duygu_motora_iletilir():
    isl, yayin, q, motor, y, stt, saat = kur(ek={"erken_seslendir": False})
    ham = ton(150, 3.0, genlik=0.4)
    temiz = ton(150, 3.0, genlik=0.004)                     # kısık diyalog: düzey eşitlenir
    s = await isl.isle(Parca(ham, saat(), temiz))
    assert s is not None and s.olcum["stt_ms"] >= 0 and "ceviri_ms" in s.olcum and "bekleme_ms" in s.olcum
    assert np.sqrt(np.mean(stt.girdi[0] ** 2)) > 0.04                               # kısık ses yükseltildi
    metin, ref_uz, duygu = motor.cagrilar[0]
    assert ref_uz > 0 and set(duygu) == {"canlilik", "cfg"}


async def test_altyazi_gorunur_gorunmez_tv_ye_erken_calar_parca_tekrar_calmaz():
    isl, yayin, q, motor, y, stt, saat = kur("tv")
    gorev = asyncio.create_task(isl.calis())
    try:
        # önce bir satırla karakterin sesi örneklenir (Ellie)
        yayin.yayinla("yazi", {"id": "a1", "metin": "x", "asil": "Where were you last night?", "tur": "altyazi",
                               "konusan": "Ellie", "sure_ms": 3000})
        await asyncio.sleep(0.05)
        bosalt(q)
        isl.kuyruga_at(Parca(ton(150, 3.0), saat() + 0.5))
        await asyncio.sleep(0.1)
        assert "Ellie" in isl._konusan_ref
        n_ceviri = len(y.cagrilar)
        # yeni altyazı: parça gelmeden ses TV'ye gider
        yayin.yayinla("yazi", {"id": "a2", "metin": "y", "asil": "Get in the car, now!", "tur": "altyazi",
                               "konusan": "Ellie", "sure_ms": 3000})
        for _ in range(50):
            olaylar = bosalt(q)
            if any(o == "ses" for o, _ in olaylar):
                break
            await asyncio.sleep(0.01)
        sesler = [v for o, v in olaylar if o == "ses"]
        assert sesler and sesler[0]["yazi_id"] == "a2" and "a2" in isl._erken_calinan
        # altyazının hazır Türkçesi seslendirildi: ikinci bir çeviri isteği YOK (hız + çeviri kotası)
        assert y.cagrilar[n_ceviri:] == [] and motor.cagrilar[-1][0] == "y"
        # aynı cümlenin konuşma parçası gelince: yeniden çevrilmez, yeniden çalınmaz
        stt.metin = "Get in the car now"
        await isl.isle(Parca(ton(150, 2.0), saat() + 1.0))
        assert not [o for o, _ in bosalt(q) if o == "ses"] and len(y.cagrilar) == n_ceviri
    finally:
        gorev.cancel()


async def test_ornek_yoksa_tv_de_notr_ses_bilgisayarda_beklenir():
    isl, yayin, q, motor, y, stt, saat = kur("tv")
    yayin.yayinla("yazi", {"id": "a5", "metin": "x", "asil": "Run!", "tur": "altyazi", "sure_ms": 2000})
    e = await isl._erken["a5"]
    assert e.ses is not None and motor.cagrilar[0][1] == 0          # boş örnek = motorun nötr sesi
    isl2, yayin2, q2, motor2, *_ = kur("bilgisayar", {"orijinal_ses": "kis"})
    yayin2.yayinla("yazi", {"id": "a6", "metin": "x", "asil": "Run!", "tur": "altyazi", "sure_ms": 2000})
    e2 = await isl2._erken["a6"]
    assert e2.tr and e2.ses is None and not motor2.cagrilar           # İngilizce tam sesle duyuluyor: erken çalınmaz


async def test_onden_hazirlanan_ses_parca_gelince_kullanilir():
    isl, yayin, q, motor, y, stt, saat = kur("bilgisayar", {"orijinal_ses": "kis"})
    isl._banka.append(type("K", (), {"pcm": ton(150, 4.0), "sr": SR, "iz": __import__("kopru.dublaj.dsp", fromlist=["x"]).parmak_izi(ton(150, 4.0), SR)})())
    yayin.yayinla("yazi", {"id": "a3", "metin": "x", "asil": "Where were you last night?", "tur": "altyazi", "sure_ms": 3000})
    await isl._erken["a3"]
    n = len(motor.cagrilar)
    calinan = []

    class Cikis:
        async def oynat(self, pcm, sr, ayar, yazi_id=None):
            calinan.append(yazi_id)
    isl.cikis_getir = lambda ad: Cikis()
    s = await isl.isle(Parca(ton(150, 3.0), saat() + 0.5))
    assert calinan == ["a3"] and s.olcum.get("erken") and len(y.cagrilar) == 0   # altyazının Türkçesi kullanıldı
    assert len(motor.cagrilar) == n                                   # aynı ses: yeniden üretilmedi


async def test_akisli_motor_ilk_parcayla_calar():
    isl, yayin, q, motor, y, stt, saat = kur("bilgisayar", {"erken_seslendir": False, "orijinal_ses": "kis"})
    istek = []

    async def seslendir_ve_cal(metin, ref, sr, duygu, hedef, ayar):
        istek.append((metin, hedef))
        return {"sure_sn": 2.0, "ilk_ses_ms": 420, "toplam_ms": 1500, "hiz": 1.1}
    motor.akisli, motor.seslendir_ve_cal = True, seslendir_ve_cal
    isl.cikis_getir = lambda ad: type("C", (), {"akisli": True})()
    s = await isl.isle(Parca(ton(150, 3.0), saat()))
    assert istek == [("Dün gece neredeydin?", 3.0)] and s.olcum["ilk_ses_ms"] == 420 and s.hiz == 1.1


# ---------- ses profili (izinle, yerel, silinebilir) ----------

def test_ses_profili_kaydet_yukle_sil(tmp_path):
    t = [0.0]
    p = SesProfilleri(tmp_path / "sesler", saat=lambda: t[0])
    assert p.kaydet("Lucia", ton(200, 3.0, 24000), 24000)
    assert not p.kaydet("Lucia", ton(200, 5.0, 24000), 24000)          # 30 sn dolmadan yazılmaz
    for i in range(1, 5):
        t[0] = 31.0 * i
        p.kaydet("Lucia", ton(200, 3.0 + i, 24000), 24000)
    li = p.liste()
    assert li[0]["ad"] == "Lucia" and li[0]["klip"] == 3 and li[0]["sure_sn"] == pytest.approx(5 + 6 + 7)
    pcm, sr = p.yukle()["Lucia"]
    assert sr == 24000 and len(pcm) == 12 * 24000
    assert p.sil("Lucia") == 1 and p.liste() == [] and not list((tmp_path / "sesler").glob("*.wav"))


async def test_profil_izni_yoksa_diske_hic_yazilmaz(tmp_path, monkeypatch):
    isl, yayin, q, motor, y, stt, saat = kur()
    assert isl.profil_kaydet is None


# ---------- ayarlar ----------

def test_yeni_ayarlar_dogrulama_ve_tamamen_turkce_karari():
    gecerli = {"orijinal_ses": "tamamen_turkce", "hafif_mod": "otomatik", "ayirma": False, "erken_seslendir": True,
               "video_srt": False, "video_motor": "pocket", "ses_girisi": "USB Capture", "ses_profili_izni": True}
    assert dublaj_mod.ayar_gecerli(gecerli)
    for kotu in ({"orijinal_ses": "sessiz"}, {"hafif_mod": True}, {"ayirma": "evet"}, {"video_motor": "x"},
                 {"ses_girisi": 5}, {"ses_profili_izni": None}):
        assert not dublaj_mod.ayar_gecerli(kotu), kotu
    t = dublaj_mod.tamamen_turkce_mu
    assert t({"cihaz": "ps5", "kaynak": "pencere:12", "dublaj": {}})          # Remote Play penceresi
    assert t({"cihaz": "pc", "kaynak": "ekran:1", "dublaj": {"ses_girisi": "Elgato"}})
    assert not t({"cihaz": "pc", "kaynak": "pencere:12", "dublaj": {}})       # oyun bu bilgisayarda: kıs
    assert not t({"cihaz": "ps5", "kaynak": "pencere:12", "dublaj": {"orijinal_ses": "kis"}})
    a = ayarlar.duzelt({**ayarlar.VARSAYILAN, "dublaj": {**dublaj_mod.VARSAYILAN, "orijinal_ses": "bozuk"}})
    assert a["dublaj"]["orijinal_ses"] == "otomatik" and a["dublaj"]["ses_profili_izni"] is False


# ---------- API ----------

@pytest.fixture
async def istemci(aiohttp_client, uygulama_ayari, tmp_path):
    uygulama_ayari["motor"] = "sahte"
    ortam = DublajOrtami(kok=tmp_path / "dublaj-ortami", platform_=("linux", "x86_64"), gelistirici=False,
                         calistirici=lambda k, cb, i, env=None: 0, cuda_var=lambda: True)
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika, dublaj_fabrikalari={
        "donanim_fn": lambda: donanim.Donanim("cuda", "NVIDIA GeForce RTX 4060 Laptop GPU", 8.0, 16.0), "ortam": ortam})
    c = await aiohttp_client(app)
    c.durum = app[sunucu.DURUM]
    c.ortam = ortam
    return c


async def test_api_paket_onaysiz_kurulmaz_durum_ve_boyut(istemci):
    j = await (await istemci.get("/api/dublaj/paket")).json()
    assert j["durum"] == "yok" and not j["kurulu"] and j["indirme_mb"] > 3000 and j["destek"]
    assert j["disk_mb"] > j["indirme_mb"] and "dublaj-ortami" in j["konum"]
    r = await istemci.post("/api/dublaj/paket/kur", json={})
    assert r.status == 400 and (await r.json())["hata"] == "dublaj_paket_onay"
    r = await istemci.post("/api/dublaj/paket/kaldir", json={"onay": "evet"})
    assert r.status == 400
    d = await (await istemci.get("/api/dublaj")).json()
    assert d["paket"]["durum"] == "yok" and d["isci"] is False and d["hafif"] is False and "gecikme" in d


async def test_api_paket_kur_iptal_kaldir(istemci):
    bekle = asyncio.Event()

    async def yavas():
        await bekle.wait()
    istemci.ortam._python = yavas
    r = await istemci.post("/api/dublaj/paket/kur", json={"onay": True})
    assert r.status == 200 and (await r.json())["durum"] == "kuruluyor"
    j = await (await istemci.post("/api/dublaj/paket/iptal", json={})).json()
    assert j["durum"] == "iptal"
    j = await (await istemci.post("/api/dublaj/paket/kaldir", json={"onay": True})).json()
    assert j["durum"] == "yok"


async def test_api_ayarlar_yeni_dublaj_alanlari(istemci):
    r = await istemci.post("/api/dublaj", json={"orijinal_ses": "tamamen_turkce", "ses_profili_izni": True})
    assert r.status == 200 and (await r.json())["dublaj"]["orijinal_ses"] == "tamamen_turkce"
    assert (await istemci.post("/api/dublaj", json={"orijinal_ses": "sessiz"})).status == 400


async def test_api_ses_profilleri_listele_sil(istemci):
    p = istemci.durum.dublaj.profiller()
    p.kaydet("Jason", ton(120, 3.0, 24000), 24000)
    j = await (await istemci.get("/api/dublaj/ses-profilleri")).json()
    assert j["izin"] is False and [x["ad"] for x in j["profiller"]] == ["Jason"]
    j = await (await istemci.delete("/api/dublaj/ses-profilleri")).json()
    assert j["silinen"] == 1
    assert (await (await istemci.get("/api/dublaj/ses-profilleri")).json())["profiller"] == []


async def test_api_girisler_paket_yokken_bos_ve_yerel_disi_403(istemci, monkeypatch):
    assert (await (await istemci.get("/api/dublaj/girisler")).json()) == {"girisler": []}
    monkeypatch.setattr(sunucu, "uzak_adres", lambda req: "192.168.1.50")
    for yol in ("/api/dublaj/paket", "/api/dublaj/video", "/api/dublaj/ses-profilleri"):
        assert (await istemci.get(yol)).status == 403
    assert (await istemci.post("/api/dublaj/paket/kur", json={"onay": True})).status == 403


def test_yer_ayarla_sesler_ust_uste_binmez_ve_uydurma_suresi():
    b = mantik.yer_ayarla([1.0, 2.0, 2.5], [1.5, 1.0, 1.0], 20.0)
    assert b[1] >= b[0] + 1.5 and b[2] >= b[1] + 1.0
    assert mantik.sacma_uzun_mu(4.0, "Tamam.") and not mantik.sacma_uzun_mu(2.0, "Dün gece neredeydin?")
