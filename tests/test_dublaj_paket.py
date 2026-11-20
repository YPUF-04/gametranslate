# SPDX-License-Identifier: AGPL-3.0-only
"""Dublaj paketi (PROTOKOL 14.1) ve işçi kanalı (14.2): ağsız, torch'suz, sahtelerle."""
import asyncio
import hashlib
import io
import json
import os
import sys
import tarfile
import threading
import zipfile
from pathlib import Path

import numpy as np
import pytest

from kopru.dublaj import ortam as ortam_mod
from kopru.dublaj.isci import protokol
from kopru.dublaj.isci.sunucu import IsciHatasi, IsciSunucu
from kopru.dublaj.isci_istemci import IsciIstemci, isci_komutu, kod_kopyala
from kopru.dublaj.ortam import DublajOrtami, OrtamHatasi, guvenli_ac, indir
from kopru.dublaj.temel import DublajHatasi

KOK = Path(__file__).resolve().parent.parent


# ---------- indirme ----------

class SahteYanit:
    def __init__(self, veri, durum=200, kes=None):
        self.veri, self.status, self.kes = veri, durum, kes
        self.headers = {"Content-Length": str(len(veri))}
        self.i = 0

    def read(self, n):
        if self.kes is not None and self.i >= self.kes:
            raise ConnectionResetError("kesildi")
        p = self.veri[self.i:self.i + min(n, 1000)]
        self.i += len(p)
        return p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


VERI = bytes(range(256)) * 40
OZET = hashlib.sha256(VERI).hexdigest()
URL = "https://github.com/x/y/releases/download/1/a.tar.gz"


def test_indirme_yarim_kalinca_kaldigi_yerden_surer_ve_dogrular(tmp_path):
    istekler = []

    def acici(url, bas):
        istekler.append(bas)
        if len(istekler) == 1:
            return SahteYanit(VERI, kes=3000)                    # 3000 bayttan sonra kopar
        return SahteYanit(VERI[bas:], durum=206)
    ilerleme = []
    yol = indir(URL, tmp_path / "a.tar.gz", OZET, lambda i, t: ilerleme.append((i, t)), threading.Event(),
                acici, uyku=lambda s: None)
    assert yol.read_bytes() == VERI and istekler == [0, 3000]
    assert ilerleme[-1] == (len(VERI), len(VERI)) and not (tmp_path / "a.tar.gz.part").exists()


def test_indirme_ozeti_tutmazsa_siler_ve_hata(tmp_path):
    with pytest.raises(OrtamHatasi) as e:
        indir(URL, tmp_path / "a.tar.gz", "0" * 64, lambda i, t: None, threading.Event(),
              lambda u, b: SahteYanit(VERI), uyku=lambda s: None)
    assert e.value.kod == "dublaj_paket_dogrulama"
    assert not (tmp_path / "a.tar.gz").exists() and not (tmp_path / "a.tar.gz.part").exists()


def test_indirme_izinsiz_adres_ve_http_reddedilir(tmp_path):
    for url in ("http://github.com/a", "https://kotu.example.com/a", "file:///etc/passwd"):
        with pytest.raises(OrtamHatasi):
            indir(url, tmp_path / "a", OZET, lambda i, t: None, threading.Event(), lambda u, b: SahteYanit(VERI))


def test_indirme_uc_kez_dener_sonra_hata(tmp_path):
    say = []

    def acici(u, b):
        say.append(b)
        raise OSError("ağ yok")
    with pytest.raises(OrtamHatasi) as e:
        indir(URL, tmp_path / "a", OZET, lambda i, t: None, threading.Event(), acici, uyku=lambda s: None)
    assert e.value.kod == "dublaj_paket_indirme" and len(say) == 3


def test_indirme_iptal(tmp_path):
    iptal = threading.Event()
    iptal.set()
    with pytest.raises(ortam_mod.Iptal):
        indir(URL, tmp_path / "a", OZET, lambda i, t: None, iptal, lambda u, b: SahteYanit(VERI))


# ---------- güvenli açma ----------

def _tar(yol, uyeler):
    with tarfile.open(yol, "w:gz") as t:
        for ad, veri, tur, hedef in uyeler:
            ti = tarfile.TarInfo(ad)
            if tur == "sym":
                ti.type, ti.linkname = tarfile.SYMTYPE, hedef
                t.addfile(ti)
            elif tur == "hard":
                ti.type, ti.linkname = tarfile.LNKTYPE, hedef
                t.addfile(ti)
            else:
                ti.size = len(veri)
                t.addfile(ti, io.BytesIO(veri))


def test_tar_acilir_ust_klasor_atilir_ic_baglanti_korunur(tmp_path):
    a = tmp_path / "p.tar.gz"
    _tar(a, [("python/bin/python3.13", b"py", "f", None), ("python/bin/python3", b"", "sym", "python3.13"),
             ("baska/x", b"atla", "f", None)])
    guvenli_ac(a, tmp_path / "python", "python")
    assert (tmp_path / "python" / "bin" / "python3.13").read_bytes() == b"py"
    assert not (tmp_path / "baska").exists()
    if sys.platform != "win32":
        assert os.readlink(tmp_path / "python" / "bin" / "python3") == "python3.13"


@pytest.mark.parametrize("uye", [
    ("python/../../kacak", b"x", "f", None),
    ("/etc/kacak", b"x", "f", None),
    ("python/bin/kotu", b"", "sym", "../../../../etc/passwd"),
    ("python/bin/kotu", b"", "sym", "/etc/passwd"),
    ("python/bin/sabit", b"", "hard", "python/bin/x"),
])
def test_tar_yol_asimi_ve_disari_baglanti_reddedilir(tmp_path, uye):
    a = tmp_path / "k.tar.gz"
    _tar(a, [("python/ok", b"1", "f", None), uye])
    with pytest.raises(OrtamHatasi) as e:
        guvenli_ac(a, tmp_path / "hedef" / "python", "python")
    assert e.value.kod == "dublaj_paket_bozuk"
    assert not (tmp_path / "kacak").exists() and not (tmp_path / "hedef" / "python").exists()


def test_zip_yol_asimi_reddedilir_iyisi_acilir(tmp_path):
    iyi = tmp_path / "f.zip"
    with zipfile.ZipFile(iyi, "w") as z:
        z.writestr("ffmpeg-9.1-essentials_build/bin/ffmpeg.exe", b"MZ")
    guvenli_ac(iyi, tmp_path / "ffmpeg", "ffmpeg-9.1-essentials_build")
    assert (tmp_path / "ffmpeg" / "bin" / "ffmpeg.exe").read_bytes() == b"MZ"
    kotu = tmp_path / "k.zip"
    with zipfile.ZipFile(kotu, "w") as z:
        z.writestr("ffmpeg-9.1-essentials_build/../../kacak.exe", b"MZ")
    with pytest.raises(OrtamHatasi):
        guvenli_ac(kotu, tmp_path / "f2", "ffmpeg-9.1-essentials_build")
    assert not (tmp_path / "kacak.exe").exists()


# ---------- kurulum durum makinesi ----------

def _python_arsivi(tmp_path, windows=False):
    a = tmp_path / "kaynak.tar.gz"
    ad = "python/python.exe" if windows else "python/bin/python3"
    _tar(a, [(ad, b"#!py", "f", None)])
    return a.read_bytes()


class SahteAg:
    def __init__(self, dosyalar):
        self.dosyalar, self.istenen = dosyalar, []

    def __call__(self, url, bas):
        self.istenen.append(url)
        return SahteYanit(self.dosyalar[url][bas:], 206 if bas else 200)


def kurulum(tmp_path, platform_=("linux", "x86_64"), pip_kodu=0, model_hata=None):
    veri = _python_arsivi(tmp_path, platform_[0] == "win32")
    arsiv = ortam_mod.PYTHON_ARSIVLERI[platform_]
    ag = SahteAg({arsiv.url: veri})
    eski = ortam_mod.PYTHON_ARSIVLERI[platform_]
    ortam_mod.PYTHON_ARSIVLERI[platform_] = ortam_mod.Arsiv(eski.url, hashlib.sha256(veri).hexdigest(), 1, "python", "python")
    komutlar = []

    def calistirici(komut, satir_cb, iptal, env=None):
        komutlar.append((komut, env))
        for s in ("Collecting torch==2.6.0", "Downloading torch-2.6.0-cp313.whl (2.5 GB)",
                  "Progress 50 of 100", "Progress 100 of 100", "Successfully installed torch"):
            satir_cb(s)
        return pip_kodu
    o = DublajOrtami(kok=tmp_path / "dublaj-ortami", acici=ag, calistirici=calistirici, platform_=platform_,
                     gelistirici=False, uyku=lambda s: None, cuda_var=lambda: True)
    model_cagri = []

    async def modeller(cb):
        model_cagri.append(1)
        cb(50.0, "Chatterbox")
        if model_hata:
            raise model_hata

    async def denetci():
        return {"cihaz": "cuda", "anahtar_dogru": True}
    o.model_indirici, o.isci_denetci = modeller, denetci
    return o, ag, komutlar, model_cagri, eski


async def test_kurulum_tum_asamalar_ve_kalicilik(tmp_path):
    o, ag, komutlar, model, eski = kurulum(tmp_path)
    try:
        assert o.bilgi()["durum"] == "yok" and not o.kurulu() and o.bilgi()["indirme_mb"] > 3000
        await o.kur()
        b = o.bilgi()
        assert b["durum"] == "hazir" and b["kurulu"] and b["tamam"] and b["yuzde"] == 100, b
        assert [a["durum"] for a in b["asamalar"]] == ["bitti"] * 5
        torch_k, kalan_k = komutlar[0][0], komutlar[1][0]
        assert "torch==2.6.0" in torch_k and "https://download.pytorch.org/whl/cu124" in torch_k
        assert "chatterbox-tts==0.1.7" in kalan_k and "--constraint" in kalan_k and "-E" in kalan_k
        assert (tmp_path / "dublaj-ortami" / "sabit.txt").read_text().startswith("torch==2.6.0")
        assert not list((tmp_path / "dublaj-ortami" / "indirilen").glob("*")), "arşiv açıldıktan sonra silinir"
        # yeniden açılınca kurulu sayılır, bir daha indirilmez
        o2 = DublajOrtami(kok=tmp_path / "dublaj-ortami", platform_=("linux", "x86_64"), gelistirici=False,
                          cuda_var=lambda: True)
        assert o2.kurulu() and o2.bilgi()["durum"] == "hazir" and o2.indirme_mb() == 0
    finally:
        ortam_mod.PYTHON_ARSIVLERI[("linux", "x86_64")] = eski


async def test_kurulum_pip_hatasinda_hata_sonra_surdurulur(tmp_path):
    o, ag, komutlar, model, eski = kurulum(tmp_path, pip_kodu=1)
    try:
        await o.kur()
        b = o.bilgi()
        assert b["durum"] == "hata" and b["hata"] == "dublaj_paket_pip"
        assert [a["durum"] for a in b["asamalar"]][:3] == ["bitti", "bitti", "hata"]
        n = len(ag.istenen)
        o.calistirici = lambda k, cb, i, env=None: 0
        await o.kur()
        assert o.bilgi()["durum"] == "hazir" and len(ag.istenen) == n, "python yeniden indirilmez"
    finally:
        ortam_mod.PYTHON_ARSIVLERI[("linux", "x86_64")] = eski


async def test_kurulum_iptal_ve_kaldir(tmp_path):
    o, ag, komutlar, model, eski = kurulum(tmp_path, model_hata=ortam_mod.Iptal())
    try:
        await o.kur()
        assert o.bilgi()["durum"] == "iptal" and o.bilgi_.asamalar["modeller"].durum == "bekliyor"
        assert o.kurulu() and not o.tamamen_hazir()
        await o.kaldir()
        assert not (tmp_path / "dublaj-ortami").exists() and o.bilgi()["durum"] == "yok" and not o.kurulu()
    finally:
        ortam_mod.PYTHON_ARSIVLERI[("linux", "x86_64")] = eski


async def test_windows_ffmpeg_de_indirilir(tmp_path):
    veri = _python_arsivi(tmp_path, True)
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("ffmpeg-9.1-essentials_build/bin/ffmpeg.exe", b"MZ")
    ff = z.getvalue()
    p = ortam_mod.PYTHON_ARSIVLERI[("win32", "x86_64")]
    f = ortam_mod.FFMPEG_WINDOWS
    ortam_mod.PYTHON_ARSIVLERI[("win32", "x86_64")] = ortam_mod.Arsiv(p.url, hashlib.sha256(veri).hexdigest(), 1, "python", "python")
    ortam_mod.FFMPEG_WINDOWS = ortam_mod.Arsiv(f.url, hashlib.sha256(ff).hexdigest(), 1, f.kok, "ffmpeg")
    try:
        o = DublajOrtami(kok=tmp_path / "dublaj-ortami", acici=SahteAg({p.url: veri, f.url: ff}),
                         calistirici=lambda k, cb, i, env=None: 0, platform_=("win32", "x86_64"), gelistirici=False,
                         cuda_var=lambda: True)

        async def m(cb):
            return None
        o.model_indirici = m
        await o.kur()
        assert o.bilgi()["durum"] == "hazir"
        assert o.ffmpeg_yolu().endswith("ffmpeg.exe") and o.python_yolu().name == "python.exe"
        assert any("pycaw" in x for x in o.pip_komutlari()[1][0])
    finally:
        ortam_mod.PYTHON_ARSIVLERI[("win32", "x86_64")] = p
        ortam_mod.FFMPEG_WINDOWS = f


def test_desteklenmeyen_platform_ve_gelistirici_kipi(tmp_path):
    o = DublajOrtami(kok=tmp_path / "d", platform_=("win32", "x86"), gelistirici=False)
    assert o.bilgi()["destek"] is False and o.bilgi()["hata"] == "dublaj_paket_desteklenmiyor"
    g = DublajOrtami(kok=tmp_path / "d", platform_=("linux", "x86_64"), gelistirici=True)
    assert g.kurulu() and g.python_yolu() == Path(sys.executable) and g.bilgi()["gelistirici"]
    assert not g.tamamen_hazir()     # modeller yine indirilmeli


def test_pip_ilerleme_okuyucu():
    iz = ortam_mod.PipIlerleme(1000)
    iz.satir("Downloading torch-2.6.0+cu124-cp313-cp313-win_amd64.whl (800.0 MB)")
    iz.satir("Progress 512 of 1024")
    assert 39 < iz.yuzde() < 41
    iz.satir("Downloading numpy-2.2.whl (12 MB)")
    assert iz.yuzde() > 80 - 1


def test_ortam_dizini_isletim_sistemine_gore(monkeypatch, tmp_path):
    monkeypatch.delenv("KOPRU_DUBLAJ_ORTAMI", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert ortam_mod.ortam_dizini() == tmp_path / "AltYaziKoprusu" / "dublaj-ortami"


def test_manifest_sabit_ve_https():
    for a in list(ortam_mod.PYTHON_ARSIVLERI.values()) + [ortam_mod.FFMPEG_WINDOWS]:
        assert ortam_mod.adres_izinli(a.url) and len(a.sha256) == 64 and int(a.sha256, 16) >= 0
    assert all("==" in p for p in ortam_mod.PAKETLER if p not in ("huggingface-hub", "setuptools<81"))


# ---------- işçi kanalı ----------

def test_protokol_pcm_gidis_donus_ve_bozuk_satir():
    a = (np.sin(np.arange(1000) / 7) * 0.5).astype(np.float32)
    assert np.array_equal(protokol.pcm_coz(protokol.pcm_kodla(a)), a)
    v = protokol.coz(protokol.kodla({"metin": "Dün gece neredeydin?"}))
    assert v["metin"] == "Dün gece neredeydin?"
    for kotu in (b"{bozuk", b"[1,2]", b"\xff\xfe"):
        with pytest.raises((protokol.ProtokolHatasi, UnicodeDecodeError)):
            protokol.coz(kotu)


class Isleyici:
    def __init__(self):
        self.sira = []

    def k_topla(self, v, is_):
        self.sira.append(v["a"])
        is_.ilerleme(50, "yarı")
        return {"t": v["a"] + v["b"]}

    def k_hata(self, v, is_):
        raise IsciHatasi("dublaj_uretim_hata", "x")

    def k_patla(self, v, is_):
        raise RuntimeError("CUDA out of memory")


def test_isci_sunucusu_sirali_yanit_ilerleme_hata():
    cikis = io.BytesIO()

    def giris():
        for x in [{"no": 1, "komut": "topla", "a": 1, "b": 2}, {"no": 2, "komut": "hata"}, {"no": 3, "komut": "yok"},
                  {"no": 4, "komut": "patla"}, {"komut": "eksik"}]:
            yield protokol.kodla(x)
        yield b"bozuk\n"
        import time
        for _ in range(200):     # ana program yanıtları alana dek kanal açık kalır
            if cikis.getvalue().count(b'"tamam"') >= 4:
                break
            time.sleep(0.01)
    isl = Isleyici()
    IsciSunucu(giris(), cikis, isl, "ANAHTAR", lambda: {"cihaz": "cpu"}).calis()
    satirlar = [json.loads(s) for s in cikis.getvalue().decode().splitlines()]
    assert satirlar[0] == {"olay": "merhaba", "anahtar": "ANAHTAR", "surum": "1", "pid": os.getpid(), "cihaz": "cpu"}
    yanit = {s["no"]: s for s in satirlar if "no" in s and "olay" not in s}
    assert yanit[1] == {"no": 1, "tamam": True, "sonuc": {"t": 3}}
    assert yanit[2]["hata"] == "dublaj_uretim_hata" and yanit[3]["hata"] == "dublaj_isci_komut"
    assert yanit[4]["hata"] == "dublaj_bellek"
    assert any(s.get("olay") == "ilerleme" and s["no"] == 1 and s["yuzde"] == 50 for s in satirlar)


def _komut(tmp_path, ek=None):
    return lambda: isci_komutu(Path(sys.executable), KOK, tmp_path / "m", None, tmp_path / "isci.log",
                               {"KOPRU_ISCI_SAHTE": "1", **(ek or {})})


async def test_gercek_surecle_kanal_iptal_cokme_ve_yeniden_baslama(tmp_path):
    c = IsciIstemci(_komut(tmp_path))
    try:
        b = await c.baslat()
        assert b["sahte"] and "anahtar" not in b                     # anahtar panele/günlüğe sızmaz
        pcm = np.linspace(-1, 1, 5000).astype(np.float32)
        r = await c.iste("yanki", {"metin": "Çalışıyor ğüşiöç", "pcm": protokol.pcm_kodla(pcm)})
        assert r["metin"] == "Çalışıyor ğüşiöç" and np.array_equal(protokol.pcm_coz(r["pcm"]), pcm)
        ilerleme = []
        gorev = asyncio.create_task(c.iste("yavas", {"adim": 500}, ilerleme=lambda y, m: ilerleme.append(y)))
        await asyncio.sleep(0.4)
        gorev.cancel()
        with pytest.raises(asyncio.CancelledError):
            await gorev
        assert ilerleme, "ilerleme olayı geldi"
        assert (await c.iste("yanki", {"metin": "sonra"}))["metin"] == "sonra"   # iptalden sonra sıradaki çalışır
        with pytest.raises(DublajHatasi) as e:
            await c.iste("hata")
        assert e.value.kod == "dublaj_uretim_hata"
        with pytest.raises(DublajHatasi) as e:
            await c.iste("coz")
        assert e.value.kod == "dublaj_isci_hata"
        assert (await c.iste("yanki", {"metin": "yeniden"}))["metin"] == "yeniden"   # kendiliğinden yeniden açıldı
        olaylar = []
        c.dinle(olaylar.append)
        await c.iste("parca_yolla", {"pcm": protokol.pcm_kodla(pcm[:100])})
        await asyncio.sleep(0.05)
        assert any(o.get("olay") == "parca" for o in olaylar)
        assert "KOPRU_ISCI_ANAHTAR" not in (tmp_path / "isci.log").read_text(errors="ignore")
    finally:
        await c.kapat()
    assert not c.calisiyor()


async def test_yanlis_anahtarli_isci_reddedilir(tmp_path):
    async def baslatici(k):
        k.env["KOPRU_ISCI_ANAHTAR"] = "baska"          # işçi başka anahtarla selam verir
        from kopru.dublaj.isci_istemci import _surec_baslat
        return await _surec_baslat(k)
    c = IsciIstemci(_komut(tmp_path), baslatici=baslatici)
    with pytest.raises(DublajHatasi) as e:
        await c.baslat()
    assert e.value.kod == "dublaj_isci_hata" and not c.calisiyor()


async def test_isci_dakikada_ucten_fazla_baslatilmaz(tmp_path):
    async def bozuk(k):
        raise OSError("python yok")
    c = IsciIstemci(_komut(tmp_path), baslatici=bozuk, saat=lambda: 0.0)
    for _ in range(3):
        with pytest.raises(DublajHatasi):
            await c.baslat()
    with pytest.raises(DublajHatasi) as e:
        await c.baslat()
    assert "bir dakika" in e.value.ayrinti


def test_isci_ortami_anahtar_degiskenlerini_tasimaz(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "gizli")
    monkeypatch.setenv("HF_TOKEN", "gizli")
    k = isci_komutu(Path("/py"), tmp_path, tmp_path / "m", "/ff", None)
    assert "GEMINI_API_KEY" not in k.env and "HF_TOKEN" not in k.env
    assert k.env["HF_HOME"] == str(tmp_path / "m") and k.env["KOPRU_FFMPEG"] == "/ff"
    assert k.argv[1:] == ["-E", "-s", "-X", "utf8", "-m", "kopru.dublaj.isci"]


def test_isci_kodu_pakete_kopyalanir_ve_bagimsiz_calisir(tmp_path):
    import subprocess
    kod_kopyala(tmp_path / "kod")
    assert (tmp_path / "kod" / "kopru" / "dublaj" / "isci" / "motorlar.py").exists()
    r = subprocess.run([sys.executable, "-E", "-s", "-c",
                        "import kopru.dublaj.isci.motorlar, kopru.dublaj.isci.canli, kopru.ses; print('TAMAM')"],
                       cwd=str(tmp_path / "kod"), capture_output=True, text=True, timeout=60)
    assert "TAMAM" in r.stdout, r.stderr
