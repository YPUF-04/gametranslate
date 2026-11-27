# SPDX-License-Identifier: AGPL-3.0-only
"""Dublaj hafızası (PROTOKOL 21): depo, anında çalma, oyun sesinden tanıma, ön hazırlık. Sahte saat ve motorlarla."""
import asyncio

import numpy as np
import pytest

from kopru import ayarlar
from kopru import dublaj as dublaj_mod
from kopru.ceviri.temel import Ceviri
from kopru.dublaj import tanima as T
from kopru.dublaj.hafiza import DublajHafizasi, anahtar, hepsini_sil
from kopru.dublaj.hafiza_canli import HafizaOturumu, wav_coz, wav_kodla
from kopru.dublaj.isleyici import Isleyici
from kopru.yayin import Yayin

SR = 16000


class Saat:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _wav(sn=1.0, sr=24000):
    pcm = (0.2 * np.sin(2 * np.pi * 200 * np.arange(int(sn * sr)) / sr)).astype(np.float32)
    return wav_kodla(pcm, sr)[0]


# ---------- depo ----------

def test_kaydet_bul_benzer_ve_konusansiz(tmp_path):
    h = DublajHafizasi(tmp_path / "h")
    k = h.kaydet("Where were you last night?", "Ellie", "Dün gece neredeydin?", ses=_wav(), bicim="wav", sr=24000,
                 sure_sn=1.0, cinsiyet="k", profil="Ellie", puan=0.5)
    assert h.bul("where were you last night", "ellie")["id"] == k
    assert h.bul("Where were you last night?", None)["id"] == k            # konuşan okunamadı
    assert h.bul("Where were you last nigth?", "Ellie")["id"] == k         # OCR harf hatası: benzerlik
    assert h.bul("Get in the car", "Ellie") is None
    s = h.getir(k)
    assert s["sesli"] and s["tr"] == "Dün gece neredeydin?" and s["cinsiyet"] == "k"
    assert anahtar("  Hello,  there! ", "Joel") == "hello,  there|joel" or anahtar("Hello there", "Joel").endswith("|joel")


def test_kullanici_metni_ve_yuksek_puanli_ses_korunur(tmp_path):
    h = DublajHafizasi(tmp_path / "h")
    k = h.kaydet("Run!", None, "Koş!", ses=_wav(), bicim="wav", sr=24000, sure_sn=1.0, puan=0.8)
    h.kaydet("Run!", None, "Koş!", ses=_wav(2.0), bicim="wav", sr=24000, sure_sn=2.0, puan=0.3)
    assert h.getir(k)["sure_sn"] == 1.0                                    # düşük puanlı ses ezmez
    assert h.metin_duzelt(k, "Kaç!")
    s = h.getir(k)
    assert s["tr"] == "Kaç!" and s["tr_kaynak"] == "kullanici" and not s["sesli"]
    h.kaydet("Run!", None, "Koş!", tr_kaynak="en_iyi", ses=_wav(), bicim="wav", sr=24000, sure_sn=1.0, puan=0.9)
    assert h.getir(k)["tr"] == "Kaç!" and not h.getir(k)["sesli"]         # kullanıcı metni başka kaynakla ezilmez
    h.kaydet("Run!", None, "Kaç!", tr_kaynak="kullanici", ses=_wav(), bicim="wav", sr=24000, sure_sn=1.0)
    assert h.getir(k)["sesli"]


def test_lru_siniri_en_eski_kullanilanin_sesini_siler(tmp_path):
    saat = Saat(0)
    h = DublajHafizasi(tmp_path / "h", saat=saat)
    kimlik = []
    for i in range(4):
        saat.t = i
        kimlik.append(h.kaydet(f"line {i}", None, f"satır {i}", ses=b"x" * 400_000, bicim="ogg", sr=24000, sure_sn=1.0))
    saat.t = 10
    h.ses_al(kimlik[0])                                                    # 0 yeniden kullanıldı
    silinen = h.sinirla(1.0)                                               # 1 MB: 2 ses kalır
    assert silinen == [kimlik[1], kimlik[2]]
    assert h.getir(kimlik[1])["tr"] == "satır 1" and not h.getir(kimlik[1])["sesli"]   # metin kalır
    assert h.istatistik()["sesli"] == 2


def test_sahne_grafigi_sonrakiler(tmp_path):
    h = DublajHafizasi(tmp_path / "h")
    a, b, c, d = (h.kaydet(f"l{i}", None, f"s{i}") for i in range(4))
    for _ in range(3):
        h.gecis_ekle(a, b, 2.0)
    h.gecis_ekle(a, c, 4.0)
    h.gecis_ekle(b, d, 1.0)
    assert [x["id"] for x in h.sonrakiler(a, 3)] == [b, c, d]


def test_silme_satir_oyun_hepsi(tmp_path):
    h = DublajHafizasi(tmp_path / "oyunlar" / "gta" / "dublaj_hafizasi")
    k = h.kaydet("a", None, "b", ses=_wav(), bicim="wav", sr=24000, sure_sn=1.0)
    dosya = h.kok / "sesler" / h.getir(k)["dosya"]
    assert dosya.exists() and h.sil(k) and not dosya.exists() and h.getir(k) is None
    h.kaydet("a", None, "b")
    h.kapat()
    assert hepsini_sil(tmp_path) == 1 and not (tmp_path / "oyunlar" / "gta" / "dublaj_hafizasi").exists()


def test_disa_ice_aktar_puani_yuksek_kalir(tmp_path):
    a = DublajHafizasi(tmp_path / "a")
    k = a.kaydet("Run!", "Joel", "Koş!", ses=_wav(), bicim="wav", sr=24000, sure_sn=1.0, puan=0.9, iz=[[5, 1], [6, -3]])
    k2 = a.kaydet("Stop.", "Joel", "Dur.", ses=_wav(), bicim="wav", sr=24000, sure_sn=1.0)
    a.gecis_ekle(k, k2, 1.5)
    yedek = tmp_path / "yedek.kdh"
    assert a.disa_aktar(yedek, "gta") == 2
    b = DublajHafizasi(tmp_path / "b")
    eski = b.kaydet("Run!", "Joel", "Kaç!", ses=_wav(2.0), bicim="wav", sr=24000, sure_sn=2.0, puan=0.2)
    sonuc = b.ice_aktar(yedek)
    assert sonuc == {"eklenen": 1, "guncellenen": 1}
    s = b.getir(eski)
    assert s["sure_sn"] == 1.0 and s["puan"] == 0.9 and b.iz_al(eski) == [[5, 1], [6, -3]]
    assert [x["asil"] for x in b.sonrakiler(eski)] == ["Stop."]


def test_ice_aktar_yabanci_dosyayi_reddeder(tmp_path):
    import zipfile
    y = tmp_path / "x.kdh"
    with zipfile.ZipFile(y, "w") as z:
        z.writestr("bilgi.json", '{"tur": "baska"}')
    with pytest.raises(ValueError):
        DublajHafizasi(tmp_path / "b").ice_aktar(y)


def test_wav_kodla_coz():
    pcm = np.linspace(-0.5, 0.5, 2400).astype(np.float32)
    x, sr = wav_coz(wav_kodla(pcm, 24000)[0])
    assert sr == 24000 and np.allclose(x, pcm, atol=1e-3)


# ---------- canlı: sahte boru hattı ----------

class Motor:
    kod, ad, yerel = "chatterbox", "C", True
    varsayilan_ses = True
    yerlesik_ses = True

    def __init__(self):
        self.cagrilar = []

    def hazir(self):
        return True

    async def hazirla(self, cb=None):
        pass

    async def seslendir(self, metin, ref, sr, **ek):
        self.cagrilar.append(metin)
        await asyncio.sleep(0.01)
        return (0.2 * np.sin(np.arange(24000) / 10)).astype(np.float32), 24000


class Yonetici:
    def __init__(self):
        self.cagrilar = []

    async def dublaj_cevir(self, metin, *a, **k):
        self.cagrilar.append(metin)
        return Ceviri("Türkçe")

    def satir_kaydet(self, *a):
        pass


class AniCikis:
    """İşçinin `ani_cal`ı yerine: ne zaman, hangi gecikmeyle çalınmak istendiğini kaydeder."""
    ad = "bilgisayar"

    def __init__(self, saat):
        self.saat, self.ani, self.normal = saat, [], []

    async def ani_oynat(self, pcm, sr, ayar, kimlik, gecikme_sn=0.0):
        self.ani.append((self.saat(), kimlik, gecikme_sn, len(pcm) / sr))

    async def oynat(self, pcm, sr, ayar, yazi_id=None, **k):
        self.normal.append((self.saat(), yazi_id))


class Parca:
    def __init__(self, pcm, bas, iz=None):
        self.pcm, self.sr, self.bas, self.bitis, self.iz, self.temiz = pcm, SR, bas, bas + len(pcm) / SR, iz, None


def kur(tmp_path, saat=None, ek=None):
    saat = saat or Saat()
    yayin = Yayin()
    ayar = {**ayarlar.VARSAYILAN, "dublaj": {**dublaj_mod.VARSAYILAN, "motor": "chatterbox", "cikis": "bilgisayar",
                                              "orijinal_ses": "tamamen_turkce", "hafiza_izni": True, **(ek or {})}}
    motor, y = Motor(), Yonetici()
    cikis = AniCikis(saat)
    eklenen = []

    async def tanima_ekle(k, iz):
        eklenen.append((k, iz))
    isl = Isleyici(type("S", (), {"yaz": staticmethod(lambda p, s: asyncio.sleep(0, "x"))})(), y, lambda: motor,
                   lambda ad: cikis, yayin, lambda: ayar, saat)
    isl.hafiza = HafizaOturumu(DublajHafizasi(tmp_path / "h", saat=lambda: saat.t), tanima_ekle=tanima_ekle)
    yayin.dinle(isl.olay)
    return isl, yayin, motor, y, cikis, saat, eklenen


async def _bekle(kosul, n=200):
    for _ in range(n):
        if kosul():
            return True
        await asyncio.sleep(0.01)
    return False


async def test_ilk_gecis_kaydeder_ikinci_gecis_seslendirmeden_aninda_calar(tmp_path):
    isl, yayin, motor, y, cikis, saat, eklenen = kur(tmp_path)
    cal = asyncio.create_task(isl._cal_dongusu())
    try:
        yayin.yayinla("yazi", {"id": "a1", "asil": "Get in the car, now!", "metin": "Arabaya bin, hemen!",
                               "konusan": "Ellie", "tur": "altyazi"})
        assert await _bekle(lambda: isl._yazi_satir.get("a1"))
        kimlik = isl._yazi_satir["a1"]
        s = isl.hafiza.depo.getir(kimlik)
        assert s["sesli"] and s["tr"] == "Arabaya bin, hemen!" and s["asil"] == "Get in the car, now!"
        assert isl.olcumler[-1]["hafiza"] == "iskalama"
        # konuşma parçası gelir: İngilizce satırın ses izi bağlanır, tanıma dizinine gider
        konusma = T.sentetik_konusma(3, 2.0)
        await isl.isle(Parca(konusma, saat() - 2.0, iz=T.iz_cikar(konusma)))
        assert isl.hafiza.depo.getir(kimlik)["iz_sayisi"] > 50 and eklenen and eklenen[-1][0] == kimlik
        isl.temizle()
        # ikinci geçiş (başka gün): altyazı görünür görünmez kayıtlı ses; seslendirme yok
        n = len(motor.cagrilar)
        saat.t += 3600
        yayin.yayinla("yazi", {"id": "b1", "asil": "Get in the car, now!", "metin": "Arabaya bin, hemen!",
                               "konusan": "Ellie", "tur": "altyazi"})
        assert await _bekle(lambda: cikis.ani)
        assert cikis.ani[-1][1] == f"h{kimlik}" and cikis.ani[-1][2] == 0.0
        await asyncio.sleep(0.05)
        assert len(motor.cagrilar) == n and "b1" not in isl._erken
        o = isl.olcumler[-1]
        assert o["hafiza"] == "isabet" and o["ilk_ses_ms"] == 0 and isl.hafiza.olcum()["hafiza_isabet_ms"] == 0
        # o satırın konuşma parçası yeniden dublajlanmaz
        assert await isl.isle(Parca(konusma, saat() + 0.1)) is None
    finally:
        cal.cancel()


async def test_sahne_tanima_altyazidan_once_satir_basinda_calar(tmp_path):
    """Gerçek tanıyıcıyla: ilk geçişte kaydedilen iz, ikinci geçişte (müzik + %15 kısık) OCR'dan önce tanınır."""
    isl, yayin, motor, y, cikis, saat, _ = kur(tmp_path)
    satirlar = [(11, "We need to go."), (12, "They are coming!"), (13, "Hold on.")]
    parcalar, baslar, t = [np.zeros(SR, np.float32)], [], 1.0
    for tohum, _ in satirlar:
        s = T.sentetik_konusma(tohum, 2.2)
        baslar.append(t)
        parcalar += [s, np.zeros(int(0.8 * SR), np.float32)]
        t += 3.0
    sahne = np.concatenate(parcalar)
    # 1. geçiş: hafızaya ses + iz
    for (tohum, asil), b in zip(satirlar, baslar):
        await isl.hafiza.kaydet(asil, "Joel", "tr " + asil, np.zeros(24000, np.float32) + 0.1, 24000,
                                iz=T.iz_cikar(sahne, SR, b, b + 2.2), en_sure_sn=2.2)
    dizin = T.Dizin()
    for k, iz in await isl.hafiza.tum_izler():
        dizin.ekle(k, iz)
    # 2. geçiş: işçinin akışı taklit edilir (250 ms bloklar, sahte saat oyun saatini izler)
    canli = (sahne + T.sentetik_muzik(4, len(sahne) / SR + 1)[:len(sahne)] * 0.5) * 0.85
    tn = T.Tanici(dizin)
    bas0 = saat.t
    for i in range(0, len(canli), SR // 4):
        saat.t = bas0 + (i + SR // 4) / SR
        for e in tn.besle(canli[i:i + SR // 4]):
            isl.tanima_olayi(e.sozluk())
        await _bekle(lambda: not isl._gorevler)       # sahte saat, işler bitmeden ilerlemesin
    assert await _bekle(lambda: len(cikis.ani) == 3), cikis.ani
    for (an, kimlik, gecikme, _), b in zip(cikis.ani, baslar):
        cal_an = an + gecikme - bas0
        assert -0.1 <= cal_an - b <= 1.3                                 # satırın başıyla birlikte (≤ 1,3 sn)
    assert all(o["hafiza"] == "tanima" for o in list(isl.olcumler)[-3:])
    # altyazı sonradan gelir: yeniden çalınmaz, seslendirilmez
    yayin.yayinla("yazi", {"id": "z", "asil": "Hold on.", "metin": "tr Hold on.", "konusan": "Joel", "tur": "altyazi"})
    await asyncio.sleep(0.1)
    assert len(cikis.ani) == 3 and not motor.cagrilar


async def test_on_hazirlik_sonraki_satiri_seslendirip_kaydeder(tmp_path):
    isl, yayin, motor, y, cikis, saat, _ = kur(tmp_path)
    d = isl.hafiza.depo
    a = d.kaydet("A line", None, "A satırı", ses=wav_kodla(np.zeros(2400, np.float32) + 0.1, 24000)[0], bicim="wav",
                 sr=24000, sure_sn=0.1)
    b = d.kaydet("B line", None, "B satırı", cinsiyet="e")              # yalnız metin (ör. oyun paketinden)
    c = d.kaydet("C line", None, "C satırı", ses=wav_kodla(np.zeros(2400, np.float32), 24000)[0], bicim="wav",
                 sr=24000, sure_sn=0.1)
    d.gecis_ekle(a, b, 2.0)
    d.gecis_ekle(a, c, 3.0)
    await isl._hafiza_cal(d.getir(a), "isabet", yazi_id="y1", tetik_an=saat())
    assert await _bekle(lambda: d.getir(b)["sesli"])
    # C'nin belleğe alınması da arka planda: yavaş makinede (Windows CI) B'den sonra bitebilir
    assert await _bekle(lambda: isl.hafiza.bellekte(c))
    assert motor.cagrilar == ["B satırı"]


async def test_izin_yoksa_hafiza_yok_ve_dosya_yazilmaz(tmp_path, monkeypatch):
    from kopru.dublaj.yonetim import DublajYonetici
    ayar = {**ayarlar.VARSAYILAN, "dublaj": dict(dublaj_mod.VARSAYILAN)}
    dy = DublajYonetici(lambda: ayar, Yayin(), lambda: None, ortam=type("O", (), {"kurulu": lambda s: False})())
    dy.hafiza_kok = lambda oyun: tmp_path / oyun
    assert dy.hafiza() is None and not any(tmp_path.iterdir())
    ayar["dublaj"]["hafiza_izni"] = True
    assert dy.hafiza() is not None and (tmp_path / "varsayilan" / "hafiza.sqlite").exists()


def test_ayar_dogrulama():
    assert dublaj_mod.ayar_gecerli({"hafiza_izni": True, "hafiza_kullan": False, "bosta_iyilestir": True,
                                    "hafiza_sinir_mb": 500})
    for kotu in ({"hafiza_izni": 1}, {"hafiza_sinir_mb": 10}, {"hafiza_sinir_mb": True}, {"hafiza_sinir_mb": 1.5}):
        assert not dublaj_mod.ayar_gecerli(kotu)


# ---------- işçi tarafı ----------

def test_isci_canli_yakalama_tanima_olayi_ve_parca_izi():
    import time
    from kopru.dublaj.isci.canli import CanliYakalama
    from kopru.dublaj.isci.motorlar import GercekIsleyici
    from tests.test_dublaj_canli import SahteKaynak
    konusma = T.sentetik_konusma(21, 2.0)
    sessiz = np.zeros(SR, np.float32)
    isl = GercekIsleyici.__new__(GercekIsleyici)          # model yüklemeden yalnız hafıza komutları
    isl._dizin = None
    sahne = np.concatenate([sessiz, konusma, sessiz])
    isl.k_tanima_yukle({"girdiler": [{"kimlik": 7, "iz": T.iz_cikar(sahne, SR, 1.0, 3.0)}], "sifirla": True}, None)
    canli = sahne * 0.8
    bloklar = [canli[i:i + SR // 4] for i in range(0, len(canli), SR // 4)] + [np.zeros(SR // 4, np.float32)] * 8
    olaylar = []
    c = CanliYakalama(olaylar.append, kaynak_fabrika=lambda: SahteKaynak(bloklar), tanici=T.Tanici(isl._dizin))
    c.baslat()
    for _ in range(300):
        if any(o.get("olay") == "parca" for o in olaylar) and any(o.get("olay") == "tanima" for o in olaylar):
            break
        time.sleep(0.01)
    c.durdur()
    tn = next(o for o in olaylar if o.get("olay") == "tanima")
    assert tn["kimlik"] == 7 and -0.2 < tn["ofset_sn"] < 1.5
    p = next(o for o in olaylar if o.get("olay") == "parca")
    assert len(p["iz"]) > 30 and all(isinstance(t, int) for _, t in p["iz"])
    assert isl.k_tanima_sil({"kimlik": 7}, None) == {"satir": 0}


def test_isci_anlik_komutlar_seslendirmeyi_beklemez():
    from kopru.dublaj.isci.sunucu import ANINDA
    assert {"tanima_yukle", "tanima_sil", "ani_cal", "ani_durdur", "ses_kodla", "ses_coz"} <= set(ANINDA)
    from kopru.dublaj.isci_istemci import KOPYALANACAK
    assert "dublaj/tanima.py" in KOPYALANACAK


# ---------- boşta iyileştirme (PROTOKOL 21.6) ----------

def test_wer_sure_temizlik_toplam():
    from kopru.dublaj import iyilestir as I
    assert I.wer("Dün gece neredeydin?", "dün gece neredeydin") == 0.0
    assert I.wer("Arabaya bin hemen", "arabaya bir hemen") == pytest.approx(1 / 3)
    assert I.wer("İyi misin", "iyi misin") == 0.0                    # Türkçe büyük İ
    assert I.sure_uyumu(2.0, 2.0) == 1.0 and I.sure_uyumu(3.2, 2.0) == 0.0 and I.sure_uyumu(2.0, None) == 0.7
    sr = 24000
    temiz = T.sentetik_konusma(3, 2.0, sr)
    kirpik = np.clip(temiz * 20, -1, 1)
    bosluklu = np.concatenate([temiz[:sr // 2], np.zeros(sr * 2, np.float32), temiz[sr // 2:]])
    assert I.temizlik(temiz, sr, "Dün gece neredeydin?") > 0.9
    assert I.temizlik(kirpik, sr) < 0.5 and I.temizlik(bosluklu, sr) < I.temizlik(temiz, sr)
    assert I.toplam({"anlasilirlik": 1, "benzerlik": None, "sure": 1, "temizlik": 1, "duygu": 1}) == 1.0


def test_cila_yukseklik_hedefi_tepe_ve_yumusak_uclar():
    from kopru.dublaj import iyilestir as I
    sr = 24000
    for kazanc in (0.05, 0.9):
        x = I.cila(T.sentetik_konusma(4, 2.0, sr) * kazanc + 0.05, sr)
        assert abs(I._yukseklik_db(x, sr) - I.HEDEF_LUFS) < 1.5        # karakterler arası tutarlı düzey
        assert np.abs(x).max() <= 0.951 and abs(x[0]) < 1e-3 and abs(x[-1]) < 1e-3
        assert abs(float(np.mean(x))) < 1e-3                            # DC / 80 Hz altı kesildi


async def test_iyilestirici_en_iyi_adayi_secer_cevirir_cilalar_ve_yazar(tmp_path):
    from kopru.dublaj.iyilestir import Iyilestirici
    from kopru.dublaj.hafiza_canli import WavKodlayici
    d = DublajHafizasi(tmp_path / "h")
    k = d.kaydet("Get in the car!", "Ellie", "Arabaya gir!", ses=_wav(), bicim="wav", sr=24000, sure_sn=1.0,
                 en_sure_sn=1.4, puan=0.2, duygu={"canlilik": 0.7, "cfg": 0.3})
    sr = 24000

    class M:
        duygu_destekli = True
        yerlesik_ses = True

        def __init__(self):
            self.ayarlar = []

        async def seslendir(self, metin, ref, rsr, duygu=None, **ek):
            self.ayarlar.append(duygu)
            sure = {11: 3.0, 23: 1.4, 37: 1.0}[duygu["tohum"]]                # yalnız 23 süreye uyar
            return T.sentetik_konusma(duygu["tohum"], sure, sr), sr

    async def olc(pcm, psr, ref, rsr):
        return ("arabaya bin hemen" if len(pcm) / psr < 2 else "araba"), 0.85

    async def cevir(asil, taslak, konusan):
        return "Arabaya bin hemen!"
    m = M()
    iy = Iyilestirici(d, WavKodlayici(), lambda: m, olc, cevir, lambda ad: (np.zeros(sr, np.float32) + 0.1, sr),
                      lambda: True)
    r = await iy.satir(d.getir(k))
    s = d.getir(k)
    assert len(m.ayarlar) == 3 and len({a["tohum"] for a in m.ayarlar}) == 3
    assert r["yazildi"] and s["tr"] == "Arabaya bin hemen!" and s["tr_kaynak"] == "en_iyi"
    assert s["ayar"]["tohum"] == 23 and s["puan"] == r["puan"] > 0.8 and s["puanlar"]["sure"] == 1.0
    assert abs(s["sure_sn"] - 1.4) < 0.01
    # daha kötü bir tur eskisini ezmez; kullanıcı metni yeniden çevrilmez
    d.metin_duzelt(k, "Bin!")
    r2 = await iy.satir(d.getir(k))
    assert d.getir(k)["tr"] == "Bin!" and r2["tr"] == "Bin!"


async def test_iyilestirici_canli_baslayinca_birakir(tmp_path):
    from kopru.dublaj.iyilestir import Iyilestirici, Kesildi
    from kopru.dublaj.hafiza_canli import WavKodlayici
    d = DublajHafizasi(tmp_path / "h")
    k = d.kaydet("a", None, "b")
    bos = [True]

    class M:
        async def seslendir(self, metin, ref, rsr, **e):
            bos[0] = False                                                   # canlı dublaj başladı
            return np.zeros(24000, np.float32), 24000

    async def olc(*a):
        return "", None
    iy = Iyilestirici(d, WavKodlayici(), lambda: M(), olc, None, lambda ad: None, lambda: bos[0])
    with pytest.raises(Kesildi):
        await iy.satir(d.getir(k))
    assert not d.getir(k)["sesli"]


async def test_video_dublaji_hafizayi_doldurur(tmp_path):
    import base64
    from tests.test_dublaj_video import SahteCevirmen, SahteIsci, ayar
    from kopru.dublaj.video import VideoIsi
    v = tmp_path / "kayit" / "gorev.mp4"
    v.parent.mkdir()
    v.write_bytes(b"video")

    class Isci(SahteIsci):
        async def iste(self, komut, veri=None, ilerleme=None, **k):
            if komut == "parmak_izleri":
                self.komutlar.append((komut, veri))
                return {"izler": [[[i, 0], [i + 1, 5]] for i in range(len(veri["araliklar"]))]}
            if komut == "ses_kodla":
                return {"veri": base64.b64encode(_wav(0.8)).decode(), "bicim": "wav", "sr": 24000, "sure_sn": 0.8}
            return await super().iste(komut, veri, ilerleme, **k)
    d = DublajHafizasi(tmp_path / "h")

    async def yaz(kayitlar):
        for x in kayitlar:
            d.kaydet(x["asil"], None, x["tr"], "video", base64.b64decode(x["veri"]), x["bicim"], x["sr"], x["sure_sn"],
                     x["en_sure_sn"], iz=x["iz"], duygu=x["duygu"])
        return len(kayitlar)
    isl = VideoIsi(v, Isci(), SahteCevirmen(), ayar, tmp_path / "isler", hafiza_yaz=yaz)
    await isl.calis()
    assert isl.bilgi()["durum"] == "bitti" and isl.bilgi()["hafiza_satir"] == 3
    s = d.bul("Where were you?", "Joel")                      # canlıda konuşan adı olsa da bulunur
    assert s and s["tr"] == "Neredeydin?" and s["tr_kaynak"] == "video" and s["sesli"] and s["iz_sayisi"] == 2
    assert s["duygu"] == {"canlilik": 0.5, "cfg": 0.5}
    # izinsiz: hiçbir şey yazılmaz
    isl2 = VideoIsi(v, Isci(), SahteCevirmen(), ayar, tmp_path / "isler2")
    await isl2.calis()
    assert isl2.bilgi()["hafiza_satir"] == 0


# ---------- API (PROTOKOL 21.8) ----------

@pytest.fixture
async def istemci(aiohttp_client, uygulama_ayari):
    from kopru import sunucu
    from tests.conftest import sahte_fabrika
    uygulama_ayari["motor"] = "sahte"
    app = sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika)
    c = await aiohttp_client(app)
    c.durum = app[sunucu.DURUM]
    return c


async def test_api_izin_yokken_bos_ve_reddeder(istemci, tmp_path):
    j = await (await istemci.get("/api/dublaj/hafiza")).json()
    assert j["izin"] is False and j["istatistik"] is None and j["satirlar"] == []
    for yol, govde in (("/api/dublaj/hafiza/hazirla", {"dakika": 5}), ("/api/dublaj/hafiza/iyilestir", {"acik": True}),
                       ("/api/dublaj/hafiza/duzelt", {"id": 1, "tr": "x"})):
        r = await istemci.post(yol, json=govde)
        assert r.status == 400 and (await r.json())["hata"] == "hafiza_izin_yok"
    assert (await istemci.post("/api/dublaj/hafiza/ice", data=b"PK")).status == 400
    assert not list(tmp_path.rglob("hafiza.sqlite"))                      # izinsiz hiçbir dosya yok


async def test_api_liste_ara_ses_duzelt_sil_yedek(istemci, tmp_path):
    r = await istemci.post("/api/dublaj", json={"hafiza_izni": True})
    assert r.status == 200
    h = istemci.durum.dublaj.hafiza()
    k = h.kaydet("Where were you?", "Ellie", "Neredeydin?", ses=_wav(), bicim="wav", sr=24000, sure_sn=1.0, puan=0.7)
    h.kaydet("Get down!", "Joel", "Eğil!")
    j = await (await istemci.get("/api/dublaj/hafiza?ara=Ellie")).json()
    assert j["izin"] and j["toplam"] == 1 and j["satirlar"][0]["tr"] == "Neredeydin?" and j["satirlar"][0]["puan"] == 0.7
    assert j["istatistik"]["satir"] == 2 and j["istatistik"]["sesli"] == 1
    r = await istemci.get(f"/api/dublaj/hafiza/ses?id={k}")
    assert r.status == 200 and r.content_type == "audio/wav" and (await r.read())[:4] == b"RIFF"
    assert (await istemci.get("/api/dublaj/hafiza/ses?id=999")).status == 404
    r = await istemci.post("/api/dublaj/hafiza/duzelt", json={"id": k, "tr": "Nerelerdeydin?"})
    j = await r.json()
    assert r.status == 200 and j["seslendirildi"] is False            # motor kapalı: boşta yeniden üretilecek
    assert h.getir(k)["tr"] == "Nerelerdeydin?" and h.getir(k)["tr_kaynak"] == "kullanici"
    # yedek: dışa aktar, sil, geri yükle
    r = await istemci.get("/api/dublaj/hafiza/disa")
    yedek = await r.read()
    assert r.status == 200 and "attachment" in r.headers["Content-Disposition"] and yedek[:2] == b"PK"
    assert (await (await istemci.delete(f"/api/dublaj/hafiza?id={k}")).json())["silinen"] == 1
    j = await (await istemci.post("/api/dublaj/hafiza/ice", data=yedek)).json()
    assert j["tamam"] and j["eklenen"] == 1 and j["guncellenen"] == 1
    assert (await istemci.post("/api/dublaj/hafiza/ice", data=b"bozuk")).status == 400
    r = await istemci.post("/api/dublaj/hafiza/hazirla", json={"dakika": 30})
    assert r.status == 200 and (await r.json())["satir"] == 2
    assert (await istemci.post("/api/dublaj/hafiza/hazirla", json={"dakika": 0})).status == 400
    # oyunun hafızası silinir
    assert (await istemci.delete("/api/dublaj/hafiza?oyun=1")).status == 200
    j = await (await istemci.get("/api/dublaj/hafiza")).json()
    assert j["istatistik"]["satir"] == 0
    assert (await istemci.delete("/api/dublaj/hafiza?hepsi=1")).status == 200


async def test_turkce_calarken_gelen_ingilizce_parcanin_izi_baglanir_sistem_sesinde_baglanmaz(tmp_path):
    """Bilgisayar çıkışında kendi sesimiz susturma aralığındadır; PS5/süreç kaynağında parça yine de oyunun sesidir."""
    for kaynak, beklenen in (("ps5", True), ("sistem", False)):
        isl, yayin, motor, y, cikis, saat, eklenen = kur(tmp_path / kaynak)
        yayin.yayinla("yazi", {"id": "a1", "asil": "Run!", "metin": "Koş!", "konusan": "Joel", "tur": "altyazi"})
        assert await _bekle(lambda: isl._yazi_satir.get("a1"))
        isl._erken_calinan.add("a1")
        isl._susturma.append((saat() - 1.0, saat() + 3.0))            # Türkçe ses bu aralıkta çaldı
        konusma = T.sentetik_konusma(8, 1.5)
        p = Parca(konusma, saat() - 0.5, iz=T.iz_cikar(konusma))
        p.kaynak = kaynak
        assert await isl.isle(p) is None
        assert (isl.hafiza.depo.getir(isl._yazi_satir["a1"])["iz_sayisi"] > 0) is beklenen


async def test_altyazi_ve_tanima_ayni_anda_gelince_bir_kez_calar(tmp_path):
    isl, yayin, motor, y, cikis, saat, _ = kur(tmp_path)
    k = await isl.hafiza.kaydet("Run!", "Joel", "Koş!", np.zeros(24000, np.float32) + 0.1, 24000)
    isl.tanima_olayi({"kimlik": k, "ofset_sn": 0.4})
    yayin.yayinla("yazi", {"id": "a1", "asil": "Run!", "metin": "Koş!", "konusan": "Joel", "tur": "altyazi"})
    await _bekle(lambda: not isl._gorevler)
    await asyncio.sleep(0.05)
    assert len(cikis.ani) == 1 and "a1" in isl._yapilan_yazilar and not motor.cagrilar
