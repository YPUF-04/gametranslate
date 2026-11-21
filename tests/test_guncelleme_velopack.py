# SPDX-License-Identifier: AGPL-3.0-only
"""Velopack ile güncelleme: Velopack sahtesi konur; gerçek ağa ve gerçek güncelleyiciye çıkılmaz."""
import asyncio
import sys
import threading
import types
from pathlib import PureWindowsPath

import pytest

from kopru import ayarlar, calistir
from kopru import guncelleme as g
from kopru.dublaj import ortam
from tests.test_guncelleme import SahteHttp, yap

MB = 1024 * 1024


class SahteVarlik:
    def __init__(self, surum, boyut, notlar=""):
        self.Version, self.Size, self.NotesMarkdown = surum, boyut, notlar


class SahteBilgi:
    def __init__(self, hedef, deltalar):
        self.TargetFullRelease, self.DeltasToTarget = hedef, deltalar


class SahteYonetici:
    """velopack.UpdateManager yerine: hangi çağrılar hangi sırayla yapıldı."""

    def __init__(self, bilgi=None):
        self.bilgi, self.cagrilar, self.hata = bilgi, [], None
        self.durak = None
        self.kaynak = None

    def check_for_updates(self):
        self.cagrilar.append("kontrol")
        if self.hata == "kontrol":
            raise RuntimeError("ağ yok")
        return self.bilgi

    def download_updates(self, bilgi, ilerleme=None):
        self.cagrilar.append("indir")
        assert bilgi is self.bilgi
        for p in (10, 55):
            ilerleme(p)
        if self.durak:
            self.durak.wait(2)
        if self.hata == "indir":
            raise RuntimeError("yarıda kesildi")
        ilerleme(100)

    def apply_updates_and_restart(self, bilgi):
        self.cagrilar.append("uygula")
        assert bilgi is self.bilgi
        if self.hata == "uygula":
            raise RuntimeError("Update.exe yok")


def sahte_modul(yonetici, kurulu=True):
    m = types.SimpleNamespace(GithubSource=lambda adres, *a, **k: ("kaynak", adres))

    def yonetici_yap(kaynak):
        if not kurulu:
            raise RuntimeError("This application is not properly installed")
        yonetici.kaynak = kaynak
        return yonetici
    m.UpdateManager = yonetici_yap
    return m


def delta_bilgi():
    return SahteBilgi(SahteVarlik("0.3.0", 120 * MB, "## Yenilikler\n- hızlı"),
                      [SahteVarlik("0.2.1", 200_000), SahteVarlik("0.3.0", 300_000)])


def tam_bilgi():
    return SahteBilgi(SahteVarlik("0.3.0", 120 * MB), [])


def motorlu(tmp_path, yonetici, **kw):
    gu, c = yap(tmp_path, SahteHttp(), **kw)
    gu.motor = g.VelopackMotoru(sahte_modul(yonetici))
    gu.bekleme = 0
    return gu, c


async def test_delta_boyutu_gosterilir_ve_eski_yola_gidilmez(tmp_path):
    y = SahteYonetici(delta_bilgi())
    gu, _ = motorlu(tmp_path, y)
    await gu.denetle()
    d = gu.durum()
    assert d["var"] is True and d["surum"] == "0.3.0" and d["yalniz_degisenler"] is True
    assert d["boyut_bayt"] == 500_000 and d["boyut_mb"] == 1          # 120 MB DEĞİL: yalnız delta toplamı
    assert "Yenilikler" in d["notlar"]
    assert gu.http.istekler == []                                      # eski (tam kurucu) yolu çağrılmadı
    assert y.kaynak == ("kaynak", g.DEPO_ADRESI)


async def test_delta_yoksa_tam_paket_boyutu(tmp_path):
    gu, _ = motorlu(tmp_path, SahteYonetici(tam_bilgi()))
    await gu.denetle()
    d = gu.durum()
    assert d["yalniz_degisenler"] is False and d["boyut_mb"] == 120


async def test_guncel_ise_var_false(tmp_path):
    gu, _ = motorlu(tmp_path, SahteYonetici(None))
    await gu.denetle()
    assert gu.durum()["var"] is False and gu.durum()["neden"] == "guncel"
    gu2, _ = motorlu(tmp_path, SahteYonetici(delta_bilgi()), surum="0.3.0")     # aynı sürüm: güncel sayılır
    await gu2.denetle()
    assert gu2.durum()["var"] is False


async def test_ayar_kapaliyken_velopack_da_istek_yapmaz(tmp_path):
    y = SahteYonetici(delta_bilgi())
    gu, _ = motorlu(tmp_path, y, ayar={"guncelleme_denetle": False})
    await gu.denetle()
    gu.arka_planda_denetle()
    assert y.cagrilar == [] and gu.durum()["neden"] == "kapali"
    await gu.denetle(elle=True)
    assert y.cagrilar == ["kontrol"]


async def test_kontrol_hatasi_sessizce_bildirilir(tmp_path):
    y = SahteYonetici(delta_bilgi())
    y.hata = "kontrol"
    gu, _ = motorlu(tmp_path, y)
    await gu.denetle(elle=True)
    assert gu.durum()["var"] is False and "denetlenemedi" in gu.durum()["denetim_hatasi"]


async def test_indir_uygula_yeniden_baslat(tmp_path):
    y = SahteYonetici(delta_bilgi())
    gu, c = motorlu(tmp_path, y)
    await gu.denetle()
    assert gu.kur_baslat() is None
    await gu.kur_gorevi
    assert y.cagrilar == ["kontrol", "indir", "uygula"]               # yeniden kontrol yok: bulunan nesne kullanıldı
    d = gu.durum()
    assert d["asama"] == "baslatiliyor" and d["ilerleme"] == 100 and c.kapandi
    assert c.komutlar == []                                           # Inno kurucusu hiç çalıştırılmadı


async def test_ilerleme_gorunur(tmp_path):
    y = SahteYonetici(delta_bilgi())
    y.durak = threading.Event()
    gu, c = motorlu(tmp_path, y)
    await gu.denetle()
    gu.kur_baslat()
    await asyncio.sleep(0.1)
    d = gu.durum()
    assert d["asama"] == "indiriliyor" and d["ilerleme"] == 55
    y.durak.set()
    await gu.kur_gorevi
    assert c.kapandi


async def test_yeniden_acilmis_programda_once_yeniden_bakar(tmp_path):
    y = SahteYonetici(delta_bilgi())
    gu, _ = motorlu(tmp_path, y)
    await gu.denetle()
    # program kapanıp açıldı: kayıtlı durum var ama Velopack nesnesi yok
    gu2, c2 = yap(tmp_path, SahteHttp())
    gu2.motor, gu2.bekleme = g.VelopackMotoru(sahte_modul(y)), 0
    gu2._durum_oku()
    assert gu2.durum()["var"] is True
    gu2.kur_baslat()
    await gu2.kur_gorevi
    assert y.cagrilar[-3:] == ["kontrol", "indir", "uygula"] and c2.kapandi


async def test_indirme_hatasi_uygulanmaz(tmp_path):
    y = SahteYonetici(delta_bilgi())
    y.hata = "indir"
    gu, c = motorlu(tmp_path, y)
    await gu.denetle()
    gu.kur_baslat()
    await gu.kur_gorevi
    d = gu.durum()
    assert d["asama"] == "hata" and d["hata"] == "guncelleme_indirilemedi"
    assert "uygula" not in y.cagrilar and not c.kapandi


async def test_uygulama_hatasi_program_acik_kalir(tmp_path):
    y = SahteYonetici(delta_bilgi())
    y.hata = "uygula"
    gu, c = motorlu(tmp_path, y)
    await gu.denetle()
    gu.kur_baslat()
    await gu.kur_gorevi
    assert gu.durum()["hata"] == "guncelleme_baslatilamadi" and not c.kapandi


async def test_surum_yokken_kurulmaz(tmp_path):
    gu, _ = motorlu(tmp_path, SahteYonetici(None))
    assert gu.kur_baslat() == "guncelleme_yok"


# ---------- Velopack yoksa eski yol ----------

def test_velopack_kurulu_degilse_motor_yok(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "velopack", sahte_modul(SahteYonetici(), kurulu=False))
    assert g.velopack_motoru() is None                              # zip / geliştirme / eski Inno kurulumu
    monkeypatch.setitem(sys.modules, "velopack", None)               # paket hiç yok (import hatası)
    assert g.velopack_motoru() is None


def test_velopack_kuruluysa_motor_var(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "velopack", sahte_modul(SahteYonetici()))
    assert isinstance(g.velopack_motoru(), g.VelopackMotoru)


def test_windows_disinda_motor_yok(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setitem(sys.modules, "velopack", sahte_modul(SahteYonetici()))
    assert g.velopack_motoru() is None


async def test_motor_yoksa_eski_kurucu_yolu_calisir(tmp_path):
    gu, c = yap(tmp_path, SahteHttp())     # motor otomatik: bu Linux'ta None
    assert gu.motor is None
    await gu.denetle()
    assert gu.durum()["yalniz_degisenler"] is False
    gu.kur_baslat()
    await gu.kur_gorevi
    assert c.komutlar and c.komutlar[0][1] == "/VERYSILENT"


# ---------- giriş noktası kancası ----------

class KancaIzi:
    def __init__(self):
        self.cagrildi = 0

    def App(self):
        iz = self

        class A:
            def run(self):
                iz.cagrildi += 1
        return A()


@pytest.mark.parametrize("platform,donmus,argv,beklenen", [
    ("win32", True, ["x.exe"], 1),
    ("win32", True, ["x.exe", "--ozdenetim"], 1),
    ("win32", True, ["x.exe", "--veloapp-install", "1.0"], 1),
    ("win32", True, ["x.exe", "--katman", "--url", "u"], 0),        # alt süreç: kanca yok
    ("win32", True, ["x.exe", "--dosya-sec"], 0),
    ("win32", False, ["x.exe"], 0),                                 # geliştirme: atla
    ("darwin", True, ["x.exe"], 0),
])
def test_velopack_kancasi_ne_zaman_calisir(monkeypatch, platform, donmus, argv, beklenen):
    iz = KancaIzi()
    monkeypatch.setitem(sys.modules, "velopack", iz)
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(sys, "frozen", donmus, raising=False)
    monkeypatch.setattr(sys, "argv", argv)
    calistir.velopack_baslat()
    assert iz.cagrildi == beklenen


def test_velopack_paketi_yoksa_kanca_sessiz(monkeypatch):
    monkeypatch.setitem(sys.modules, "velopack", None)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "argv", ["x.exe"])
    calistir.velopack_baslat()            # ImportError yutulur


def test_kullanici_verisi_velopack_klasorunun_disinda(monkeypatch):
    """Velopack kökü %LOCALAPPDATA%\\AltYaziKoprusu.Program (kurulum/kaldırma onu siler); veri başka yerlerde."""
    kok = PureWindowsPath("C:/Users/u/AppData/Local/AltYaziKoprusu.Program")
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("KOPRU_AYAR_DIZINI", raising=False)
    monkeypatch.delenv("KOPRU_DUBLAJ_ORTAMI", raising=False)
    monkeypatch.setenv("APPDATA", "C:/Users/u/AppData/Roaming")
    monkeypatch.setenv("LOCALAPPDATA", "C:/Users/u/AppData/Local")
    for yol in (PureWindowsPath(str(ayarlar.ayar_dizini())), PureWindowsPath(str(ortam.ortam_dizini()))):
        assert kok not in yol.parents and yol != kok
