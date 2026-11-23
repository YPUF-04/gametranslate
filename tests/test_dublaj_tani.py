# SPDX-License-Identifier: AGPL-3.0-only
"""Gerçek test (0.1.3, RTX 4060 Laptop, PS5 → HDMI → LG TV, gizli Remote Play, Chatterbox, diyalog %10-20):
"ses robotik, neredeyse hiç dublaj yok, ~10 sn gecikme, kadın karaktere erkek sesi".

Sınananlar (torch gerekmez; sahte motor/saat): işçinin cihaz raporu (CUDA'sız torch → "Onar"), konuşmacı koşulu
önbelleği, yerleşik kadın/erkek yedek ses, cinsiyet tahmini, cinsiyete/kimliğe göre örnek seçimi, altyazı sırasıyla
ve parça parça (akışlı) TV'ye gönderme, geciken satırın atlanması, TV'nin göreli bekleme sınırı, TV kipinde
Whisper'ın hiç çalışmaması, tanı raporu."""
import asyncio
import sys
import types

import numpy as np
import pytest

from kopru import ayarlar
from kopru import dublaj as dublaj_mod
from kopru.ceviri.temel import Ceviri
from kopru.dublaj import dsp
from kopru.dublaj.cikis import SesDeposu, TvCikis
from kopru.dublaj.isci import mantik
from kopru.dublaj.isci import motorlar
from kopru.dublaj.isleyici import Isleyici, _Klip
from kopru.dublaj.ortam import DublajOrtami
from kopru.yayin import Yayin
from tests.test_dublaj_canli import SR, Parca, Saat, SahteSTT, bosalt, ton


# ---------- cinsiyet tahmini (perde) ----------

@pytest.mark.parametrize("f0,beklenen", [(110, "e"), (125, "e"), (205, "k"), (230, "k")])
def test_cinsiyet_perdeden_kisik_seste_de(f0, beklenen):
    for genlik in (0.5, 0.02):          # oyunda diyalog %10-20: kısık
        assert mantik.cinsiyet_tahmini(ton(f0, 2.0, genlik=genlik), SR)[0] == beklenen


def test_cinsiyet_belirsiz_ve_kisa():
    assert mantik.cinsiyet_tahmini(ton(168, 2.0), SR)[0] is None
    assert mantik.cinsiyet_tahmini(ton(120, 0.3), SR)[0] is None
    gurultu = np.random.default_rng(0).normal(0, 0.1, SR * 3).astype(np.float32)
    assert mantik.sesli_oran(gurultu, SR) < 0.35 < mantik.sesli_oran(ton(150, 3.0), SR)


# ---------- işçi: cihaz raporu ----------

def _sahte_torch(cuda_var: bool, cuda_yapi: str | None):
    t = types.ModuleType("torch")
    t.__version__ = "2.6.0+" + ("cu124" if cuda_yapi else "cpu")
    t.version = types.SimpleNamespace(cuda=cuda_yapi)

    class Cuda:
        @staticmethod
        def is_available():
            return cuda_var

        @staticmethod
        def get_device_properties(i):
            return types.SimpleNamespace(total_memory=8 * 1024 ** 3)

        @staticmethod
        def get_device_name(i):
            return "NVIDIA GeForce RTX 4060 Laptop GPU"

        @staticmethod
        def is_bf16_supported():
            return True

        @staticmethod
        def init():
            raise RuntimeError("Torch not compiled with CUDA enabled")
    t.cuda = Cuda
    t.backends = types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: False),
                                       cudnn=types.SimpleNamespace(version=lambda: 90100))
    return t


@pytest.mark.parametrize("cuda_var,yapi,kart,durum", [
    (True, "12.4", None, "gpu"),
    (False, None, ("NVIDIA GeForce RTX 4060 Laptop GPU", 8.0), "cpu_torch_cpu"),   # paket CUDA'sız torch kurmuş
    (False, "12.4", ("NVIDIA GeForce RTX 4060 Laptop GPU", 8.0), "cpu_surucu"),   # sürücü/kart görülmüyor
    (False, None, None, "cpu"),
])
def test_isci_cihaz_raporu_ve_gunluk(monkeypatch, caplog, cuda_var, yapi, kart, durum):
    monkeypatch.setitem(sys.modules, "torch", _sahte_torch(cuda_var, yapi))
    monkeypatch.setattr(motorlar, "_nvidia_karti", lambda: kart)
    g = motorlar.GercekIsleyici.__new__(motorlar.GercekIsleyici)
    caplog.set_level("INFO", logger="kopru.isci")
    b = g.cihaz_bilgisi()
    assert b["durum"] == durum and b["torch_cuda"] == yapi
    assert g.cihaz == ("cuda" if cuda_var else "cpu")
    if cuda_var:
        assert b["ekran_karti"] == "NVIDIA GeForce RTX 4060 Laptop GPU" and b["vram_gb"] == 8.0 and b["bf16"] is True
    if durum == "cpu_torch_cpu":
        assert "Torch not compiled" in b["cuda_hata"]
    assert "Cihaz: " in caplog.text and f"durum={durum}" in caplog.text        # isci.log'a yazılır
    if durum.startswith("cpu_"):
        assert "İŞLEMCİDE" in caplog.text


# ---------- işçi: koşul önbelleği, yerleşik ses ----------

class _Dizi:
    def __init__(self, a):
        self.a = a

    def squeeze(self):
        return self

    def detach(self):
        return self

    def float(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self.a


class SahteChatterbox:
    sr = 24000

    def __init__(self):
        self.hazirlanan, self.uretilen, self.conds = 0, [], None

    def prepare_conditionals(self, f, exaggeration=0.5):
        self.hazirlanan += 1
        self.conds = object()

    def generate(self, metin, language_id, exaggeration, cfg_weight, temperature):
        self.uretilen.append((metin, self.conds, exaggeration, cfg_weight))
        return _Dizi(np.zeros(2400, np.float32))


def _isci():
    g = motorlar.GercekIsleyici.__new__(motorlar.GercekIsleyici)
    import threading
    g._kilit = threading.RLock()
    g._tts, g._tts_kod, g._ref_ozet, g._kosullar, g._hazir_ses = SahteChatterbox(), "chatterbox", "", {}, {}
    g._yari, g._son_uretim, g._son_kullanim, g._gpu_disinda, g.cihaz, g._canli = None, {}, 0.0, False, "cuda", None
    g._varsayilan_kosul = None
    return g


def test_konusmaci_kosulu_her_satirda_yeniden_hazirlanmaz(monkeypatch):
    monkeypatch.setitem(sys.modules, "soundfile", types.SimpleNamespace(write=lambda *a, **k: None))
    g = _isci()
    a, b = ton(120, 3.0), ton(210, 3.0)
    for ref in (a, a, b, a, b):
        g._uret("Merhaba.", ref, SR, {})
    assert g._tts.hazirlanan == 2                                    # A ve B birer kez; sonra önbellekten
    assert g._son_uretim["kosul"] == "onbellek" and g._son_uretim["uretim_ms"] >= 0
    # diller arası klon: düşük cfg (aksan/robotik okuma azalır), abartı sınırlı
    _, _, abarti, cfg = g._tts.uretilen[-1]
    assert cfg == pytest.approx(0.3) and abarti == pytest.approx(0.5)


def test_yerlesik_ses_cinsiyete_gore(monkeypatch):
    g = _isci()
    kadin, erkek = ton(210, 4.0), ton(115, 4.0)
    monkeypatch.setattr(g, "_hazir_ses_al", lambda c: {"k": (kadin, SR), "e": (erkek, SR)}.get(c))
    assert g._ref_sec({"varsayilan": "k"})[0] is kadin
    assert g._ref_sec({"varsayilan": "e"})[0] is erkek
    assert len(g._ref_sec({})[0]) == 0                                # cinsiyet bilinmiyor: motorun kendi sesi
    assert motorlar.HAZIR_SESLER == {"k": "vctk/p228_023_enhanced.wav", "e": "vctk/p226_023_enhanced.wav"}
    assert len(motorlar.HAZIR_SES_SURUM) == 40                        # sürüm sabit (lisans/kaynak izlenebilir)


def test_canli_dublaj_surerken_model_ekran_kartindan_indirilmez():
    import inspect
    assert "self._canli is None" in inspect.getsource(motorlar.GercekIsleyici._bosta_bekci)


# ---------- ana program: örnek seçimi, akış, atlama ----------

class CinsiyetliYonetici:
    def __init__(self, harita=None):
        self.harita, self.cagrilar = harita or {}, []

    def konusan_cinsiyeti(self, ad):
        return self.harita.get(str(ad).casefold()) if ad else None

    async def dublaj_cevir(self, metin, kaynak, hedef, sure_sn, onceki=None):
        self.cagrilar.append(metin)
        return Ceviri("Çeviri")

    def satir_kaydet(self, *a):
        pass


class KayitMotoru:
    kod, ad, yerel = "chatterbox", "C", True
    duygu_destekli = True
    varsayilan_ses = True
    yerlesik_ses = True

    def __init__(self, bekle=0.0):
        self.cagrilar, self.bekle = [], bekle
        self.son_uretim = {"cihaz": "cuda", "uretim_ms": 420, "kosul": "onbellek"}

    def hazir(self):
        return True

    async def hazirla(self, cb=None):
        pass

    async def seslendir(self, metin, ref, sr, duygu=None, varsayilan=None):
        self.cagrilar.append({"metin": metin, "ref": len(ref), "varsayilan": varsayilan})
        if self.bekle:
            await asyncio.sleep(self.bekle)
        return np.zeros(int(24000 * 0.4), np.float32), 24000


def kur(motor=None, yon=None, cikis="tv"):
    saat, yayin = Saat(), Yayin()
    q = yayin.abone_ol()
    ayar = {**ayarlar.VARSAYILAN, "dublaj": {**dublaj_mod.VARSAYILAN, "motor": "chatterbox", "cikis": cikis}}
    motor = motor or KayitMotoru()
    yon = yon or CinsiyetliYonetici({"lucia": "k", "jason": "e"})
    stt = SahteSTT("Hey")
    isl = Isleyici(stt, yon, lambda: motor, lambda ad: TvCikis(SesDeposu(saat=saat), yayin), yayin, lambda: ayar, saat)
    yayin.dinle(isl.olay)
    return isl, yayin, q, motor, yon, stt, saat


async def _sesler(q, n=1, sure=1.0):
    out = []
    for _ in range(int(sure / 0.01)):
        out += [v for o, v in bosalt(q) if o == "ses"]
        if len(out) >= n:
            break
        await asyncio.sleep(0.01)
    return out


def _klip(f0, sn=4.0):
    pcm = ton(f0, sn)
    return _Klip(pcm, SR, dsp.parmak_izi(pcm, SR), mantik.cinsiyet_tahmini(pcm, SR)[0], mantik.sesli_oran(pcm, SR))


async def test_kadin_karakter_ornek_yokken_kadin_yerlesik_sesle_konusur_ceviri_istegi_yok():
    isl, yayin, q, motor, yon, stt, saat = kur()
    g = asyncio.create_task(isl.calis())
    try:
        isl._banka.append(_klip(115))     # son duyulan ses bir erkek (Jason): Lucia'ya verilmez
        yayin.yayinla("yazi", {"id": "a1", "metin": "Hadi, gidelim.", "asil": "Come on, let's go.", "konusan": "LUCIA",
                               "tur": "altyazi", "sure_ms": 2000})
        sesler = await _sesler(q)
        assert sesler and sesler[0]["yazi_id"] == "a1" and sesler[0]["bayat_ms"] >= 4000
        assert motor.cagrilar[0] == {"metin": "Hadi, gidelim.", "ref": 0, "varsayilan": "k"} and not yon.cagrilar
        o = isl.olcumler[-1]
        assert o["ref_tur"] == "yerlesik_k" and o["cinsiyet"] == "k" and o["ilk_ses_ms"] >= 0 and o["cihaz"] == "cuda"
    finally:
        g.cancel()


async def test_ayni_cinsiyetteki_son_ornek_secilir_ve_anlik_sesle_kimlik():
    isl, yayin, q, motor, yon, stt, saat = kur(yon=CinsiyetliYonetici({}))
    kadin, erkek = _klip(210), _klip(115)
    isl._banka.extend([kadin, erkek])
    isl.anlik_ses = lambda sn: _hazir((ton(212, 1.5), SR))         # şu an konuşan kadın (adı altyazıda yok)
    e = await isl._erken_referans(None)
    assert e[0] is kadin.pcm and e[3] == "benzer" and e[4] == "k"
    isl.anlik_ses = None
    e = await isl._erken_referans(None)
    assert e[0] is erkek.pcm and e[3] == "banka"                    # bilgi yok: son duyulan
    yon.harita = {"lucia": "k"}
    assert (await isl._erken_referans("LUCIA"))[0] is kadin.pcm    # oyun bilgisi: Lucia kadın


async def _hazir(v):
    return v


async def test_uzun_satir_parca_parca_ve_altyazi_sirasiyla_gider():
    motor = KayitMotoru(bekle=0.02)
    isl, yayin, q, motor, yon, stt, saat = kur(motor=motor)
    g = asyncio.create_task(isl.calis())
    try:
        uzun = "Bunu yapmak zorundayız, başka çaremiz yok. Hemen arabaya bin ve beni bekle, tamam mı?"
        yayin.yayinla("yazi", {"id": "a1", "metin": uzun, "asil": "x", "konusan": "JASON", "tur": "altyazi", "sure_ms": 4000})
        yayin.yayinla("yazi", {"id": "a2", "metin": "Tamam.", "asil": "Okay.", "konusan": "LUCIA", "tur": "altyazi", "sure_ms": 1000})
        parcalar = mantik.cumlecik_bol(uzun)
        sesler = await _sesler(q, len(parcalar) + 1, 3.0)
        assert len(parcalar) >= 2
        assert [s["yazi_id"] for s in sesler] == ["a1"] * len(parcalar) + ["a2"]    # akışlı ve sırayla
        assert [c["metin"] for c in motor.cagrilar] == parcalar + ["Tamam."]
        # TV sırası: arkadaki parça önündekilerin süresi kadar daha bekleyebilir (atılmasın)
        assert sesler[1]["bayat_ms"] > sesler[0]["bayat_ms"]
    finally:
        g.cancel()


async def test_cok_geciken_satir_atlanir_ve_taniya_yazilir():
    isl, yayin, q, motor, yon, stt, saat = kur()
    g = asyncio.create_task(isl.calis())
    try:
        yayin.yayinla("yazi", {"id": "a1", "metin": "Geç kaldık.", "asil": "We're late.", "konusan": "JASON",
                               "tur": "altyazi", "sure_ms": 2000})
        saat.t += 9.0          # seslendirme sırası gelmeden 9 sn geçti (yavaş ekran kartı/işlemci)
        await asyncio.sleep(0.05)
        assert not [o for o, _ in bosalt(q) if o == "ses"] and not motor.cagrilar
        assert isl.olcumler[-1]["atildi"] == "gecikme" and "a1" in isl._erken_calinan
    finally:
        g.cancel()


async def test_tv_kipinde_parca_whisperdan_gecmez_yalniz_ornek_olur():
    isl, yayin, q, motor, yon, stt, saat = kur()
    g = asyncio.create_task(isl.calis())
    try:
        yayin.yayinla("yazi", {"id": "a1", "metin": "Hadi.", "asil": "Come on.", "konusan": "LUCIA", "tur": "altyazi",
                               "sure_ms": 2000})
        await _sesler(q)
        await isl.isle(Parca(ton(210, 4.0), saat() + 4.0))
        assert stt.girdi == []                                        # Whisper hiç çalışmadı
        assert "LUCIA" in isl._konusan_ref and len(isl._konusan_ref["LUCIA"][0]) >= 3 * SR
        await isl.isle(Parca(ton(210, 4.0), saat() + 4.5))
        assert len(isl._konusan_ref["LUCIA"][0]) > 6 * SR             # örnek zamanla birikir
    finally:
        g.cancel()


async def test_muzikli_parca_ornek_bankasina_girmez():
    isl, *_ = kur()
    gurultu = np.random.default_rng(0).normal(0, 0.2, SR * 4).astype(np.float32)
    assert isl.referans_sec(gurultu, SR)[2] == "kendi_zayif" and not isl._banka
    assert isl.referans_sec(ton(120, 4.0), SR)[2] == "kendi" and isl._banka[-1].cins == "e"


async def test_tv_bayat_siniri_sinirlanir():
    saat, yayin = Saat(), Yayin()
    q = yayin.abone_ol()
    await TvCikis(SesDeposu(saat=saat), yayin).oynat(np.zeros(100, np.float32), 24000, {"dublaj": {}}, "a1", bayat_ms=99999)
    await TvCikis(SesDeposu(saat=saat), yayin).oynat(np.zeros(100, np.float32), 24000, {"dublaj": {}}, "a2")
    v = [v for o, v in bosalt(q) if o == "ses"]
    assert v[0]["bayat_ms"] == 30000 and "bayat_ms" not in v[1]


# ---------- paket onarımı ve tanı ----------

def test_torch_onar_komutu_cuda_yapisini_zorla_kurar(tmp_path):
    o = DublajOrtami(kok=tmp_path, platform_=("win32", "x86_64"), gelistirici=False, cuda_var=lambda: True)
    k = o.torch_onar_komutu()
    assert "--force-reinstall" in k and "--no-deps" in k and "torch==2.6.0" in k
    assert k[k.index("--index-url") + 1] == "https://download.pytorch.org/whl/cu124"


async def test_kurulum_denetimi_cudasiz_torchu_onarir(tmp_path):
    from kopru.dublaj.yonetim import DublajYonetici
    cagri = []

    class Isci:
        bilgi = None

        def __init__(self):
            self.n = 0

        async def baslat(self):
            self.n += 1
            self.bilgi = {"cihaz": "cpu", "durum": "cpu_torch_cpu", "ekran_karti": "RTX 4060"} if self.n == 1 else \
                {"cihaz": "cuda", "durum": "gpu", "ekran_karti": "RTX 4060"}
            return self.bilgi

        async def kapat(self):
            cagri.append("kapat")

        def calisiyor(self):
            return True
    o = DublajOrtami(kok=tmp_path, platform_=("win32", "x86_64"), gelistirici=False, cuda_var=lambda: True,
                     calistirici=lambda komut, satir, iptal, env: cagri.append(komut) or 0)
    y = DublajYonetici(lambda: {**ayarlar.VARSAYILAN}, Yayin(), lambda: None, ortam=o, isci=Isci())
    b = await y._isci_denetle()
    assert b["cihaz"] == "cuda" and "--force-reinstall" in cagri[0] and cagri[1] == "kapat"
    assert o.onarim["durum"] == "bitti"


def test_tani_islemci_uyarisi_ve_son_satirlar(tmp_path):
    from kopru.dublaj.yonetim import DublajYonetici
    o = DublajOrtami(kok=tmp_path, platform_=("win32", "x86_64"), gelistirici=False, cuda_var=lambda: True)
    o.kurulu = lambda: True

    class Isci:
        bilgi = {"cihaz": "cpu", "durum": "cpu_torch_cpu", "ekran_karti": "NVIDIA GeForce RTX 4060 Laptop GPU",
                 "torch": "2.6.0+cpu", "torch_cuda": None}
    ayar = {**ayarlar.VARSAYILAN, "dublaj": {**dublaj_mod.VARSAYILAN, "motor": "chatterbox"}}
    y = DublajYonetici(lambda: ayar, Yayin(), lambda: None, ortam=o, isci=Isci())
    t = y.tani()
    assert t["uyari"] == "cpu_torch_cpu" and t["onarilabilir"] and t["cihaz"]["ekran_karti"].startswith("NVIDIA")
    assert t["satirlar"] == []


# ---------- gizli PS5 bağlantısının sesi canlı dublajın kaynağı olur ----------

async def test_ps5_gizli_kaynakta_isci_ps5_sesini_dinler(monkeypatch):
    from kopru import uzaktan
    from kopru.dublaj.isci_istemci import IsciSesKaynagi

    class Ps5:
        baglandi = False

        def ses_kanali(self):
            return {"kapi": 50123, "anahtar": "gizli"}

        def calisiyor(self):
            return False

        def baglan(self):
            Ps5.baglandi = True
    monkeypatch.setattr(uzaktan, "etkin", lambda: Ps5())
    istekler = []

    class Isci:
        def dinle(self, cb):
            pass

        async def iste(self, komut, veri, **k):
            istekler.append((komut, veri))
            return {"kaynak": "ps5"}
    ayar = {**ayarlar.VARSAYILAN, "kaynak": "ps5:gizli",
            "dublaj": {**dublaj_mod.VARSAYILAN, "motor": "chatterbox", "cikis": "tv"}}
    k = IsciSesKaynagi(lambda p: None, Saat(), Isci(), lambda: ayar, lambda: None)
    k.baslat(True)
    await asyncio.sleep(0.01)
    assert istekler[0][0] == "canli_baslat" and istekler[0][1]["ps5_ses"] == {"kapi": 50123, "anahtar": "gizli"}
    assert Ps5.baglandi and istekler[0][1]["tamamen_turkce"] is False


def test_canli_ayirma_parca_basina_bir_kez_ve_anlik_ses():
    """Tamamen Türkçe değilse ayırıcı her 250 ms'de değil, konuşma parçası başına BİR kez çalışır; son 1,5 sn
    konuşma da (altyazı anında kimin konuştuğu) istenebilir."""
    import time
    from kopru.dublaj.isci import protokol
    from kopru.dublaj.isci.canli import CanliYakalama
    from tests.test_dublaj_canli import SahteKaynak
    olaylar, cagri = [], []

    def ayir(p, sr):
        cagri.append(len(p))
        return p * 0.5, p * 0.5
    bloklar = [np.zeros(SR // 4, np.float32)] * 4 + [ton(150, 0.25, genlik=0.3)] * 8 + [np.zeros(SR // 4, np.float32)] * 4
    c = CanliYakalama(olaylar.append, parca_ayirici=ayir, kaynak_fabrika=lambda: SahteKaynak(bloklar))
    c.baslat()
    for _ in range(200):
        if any(o.get("olay") == "parca" for o in olaylar):
            break
        time.sleep(0.01)
    son = c.son_ses(1.5)
    c.durdur()
    p = next(o for o in olaylar if o.get("olay") == "parca")
    assert len(cagri) == 1 and cagri[0] == len(protokol.pcm_coz(p["pcm"]))
    assert np.allclose(protokol.pcm_coz(p["temiz"]), protokol.pcm_coz(p["pcm"]) * 0.5, atol=1e-6)
    assert len(son) == int(1.5 * SR)
