# SPDX-License-Identifier: AGPL-3.0-only
"""LG kurulumu: SSH/SFTP/HTTP katmanı sahte; gerçek TV yok."""
import io
import json
import logging

import pytest

from kopru import sunucu
from kopru.tv_kurulum import lg
from tests.conftest import sahte_fabrika

PAROLA = "XQ7Z9K"
ANAHTAR = "-----BEGIN RSA PRIVATE KEY-----\nGIZLI-ANAHTAR-ICERIGI\n-----END RSA PRIVATE KEY-----\n"
IP = "192.168.1.30"


class SahteOturum:
    """ParamikoOturumu ile aynı arayüz; TV gibi davranır."""
    kayit: list = []

    def __init__(self, kurulum=None, luna_satirlari=None, baglan_hatasi=None, launch_ok=True, md5_kotu=False):
        self.kurulum = kurulum
        self.luna = luna_satirlari or ['{"returnValue":true,"statusValue":1}',
                                       '{"returnValue":true,"details":{"state":"Installing"}}',
                                       '{"returnValue":true,"details":{"state":"installed"}}']
        self.baglan_hatasi, self.launch_ok, self.md5_kotu = baglan_hatasi, launch_ok, md5_kotu
        self.komutlar, self.yuklenen, self.kapandi, self.asamalar = [], [], False, []

    def _asama(self):
        self.asamalar.append(self.kurulum.durum()["asama"])

    def baglan(self, ip, anahtar_metni, parola):
        self._asama()
        assert (ip, anahtar_metni, parola) == (IP, ANAHTAR, PAROLA)
        if self.baglan_hatasi:
            raise self.baglan_hatasi

    def dosya_koy(self, yerel, uzak):
        self._asama()
        self.yuklenen.append((yerel.name, uzak))

    def calistir(self, komut, satir_cb=None, zaman_sn=120):
        self.komutlar.append(komut)
        if "md5sum" in komut:
            import hashlib
            n = int(komut.split("tail -c ")[1].split()[0])
            veri = (lg.paket_dizini() / self.yuklenen[0][0]).read_bytes()[-n:]
            return 0, ("0" * 32 if self.md5_kotu else hashlib.md5(veri).hexdigest()) + "  -\n"
        if "appInstallService" in komut:
            self._asama()
            for s in self.luna:
                if satir_cb and satir_cb(s):
                    break
            return 0, "\n".join(self.luna)
        if "applicationManager/launch" in komut:
            s = '{"returnValue":%s}' % ("true" if self.launch_ok else "false")
            satir_cb(s)
            return 0, s
        return 0, ""

    def kapat(self):
        self.kapandi = True


def yap(oturum, anahtar_al=None):
    k = lg.LgKurulum(lambda: {"arayuz_dili": "tr"}, anahtar_al=anahtar_al or (lambda ip: ANAHTAR),
                     oturum_fabrika=lambda: oturum, arka_planda=False)
    oturum.kurulum = k
    return k


def test_basarili_kurulum_asamalari_ve_komutlar():
    o = SahteOturum()
    gorulen = []
    k = yap(o, anahtar_al=lambda ip: (gorulen.append(k.durum()["asama"]), ANAHTAR)[1])
    assert k.baslat(IP, PAROLA, "asil") is None
    assert gorulen == ["anahtar"]
    assert o.asamalar == ["baglaniyor", "yukleniyor", "kuruluyor"]
    d = k.durum()
    assert d["asama"] == "bitti" and "açılıyor" in d["mesaj"] and d["ayrinti"] == ""
    # ares-install ile aynı yol, kimlik ve komutlar
    assert o.yuklenen == [("com.altyazikoprusu.tv_0.1.0_all.ipk", "/media/developer/temp/com.altyazikoprusu.tv_0.1.0_all.ipk")]
    install = [c for c in o.komutlar if "appInstallService" in c][0]
    assert install.startswith("/usr/bin/luna-send-pub -i luna://com.webos.appInstallService/dev/install '")
    assert json.loads(install.split("'")[1]) == {
        "id": "com.ares.defaultName", "ipkUrl": "/media/developer/temp/com.altyazikoprusu.tv_0.1.0_all.ipk",
        "subscribe": True}
    assert any(c.startswith("/usr/bin/test -d /media/developer/temp || /bin/mkdir -p") for c in o.komutlar)
    assert o.komutlar[-2].startswith('/bin/rm -f "/media/developer/temp/') or \
        any(c.startswith('/bin/rm -f "/media/developer/temp/') for c in o.komutlar)
    launch = [c for c in o.komutlar if "applicationManager/launch" in c][0]
    assert launch.startswith("/usr/bin/luna-send-pub -n 1 luna://com.webos.applicationManager/launch '")
    assert json.loads(launch.split("'")[1])["id"] == "com.altyazikoprusu.tv" and o.kapandi


def test_deneme_uygulamasi_ve_acgsiz_paketleri():
    for paket, kimlik in (("deneme", "com.altyazikoprusu.deneme"), ("acgsiz", "com.altyazikoprusu.tv")):
        o = SahteOturum()
        k = yap(o)
        assert k.baslat(IP, PAROLA, paket) is None and k.durum()["asama"] == "bitti"
        launch = [c for c in o.komutlar if "applicationManager/launch" in c][0]
        assert json.loads(launch.split("'")[1])["id"] == kimlik
    assert (lg.paket_dizini() / lg.PAKETLER["acgsiz"][0]).is_file()    # paketler gerçekten var


def test_kurulum_hatasi_metni_aynen_gecer():
    satirlar = ['{"returnValue":true,"details":{"state":"Installing"}}',
                '{"returnValue":true,"details":{"state":"FAILED","reason":"FAILED_IPK_INSTALL -5 ipk verified failed"}}']
    o = SahteOturum(luna_satirlari=satirlar)
    k = yap(o)
    k.baslat(IP, PAROLA, "asil")
    d = k.durum()
    assert d["asama"] == "hata" and "TV uygulamayı kabul etmedi" in d["mesaj"]
    assert "-5 ipk verified failed" in d["ayrinti"] and "FAILED_IPK_INSTALL" in d["ayrinti"]
    assert any(c.startswith("/bin/rm -f") for c in o.komutlar) and o.kapandi    # temizlik yine yapıldı


def test_luna_returnvalue_false_hatasi():
    o = SahteOturum(luna_satirlari=['{"returnValue":false,"errorText":"Denied method call"}'])
    k = yap(o)
    k.baslat(IP, PAROLA, "asil")
    assert k.durum()["asama"] == "hata" and "Denied method call" in k.durum()["ayrinti"]


def test_launch_basarisiz_olsa_da_kuruldu():
    o = SahteOturum(launch_ok=False)
    k = yap(o)
    k.baslat(IP, PAROLA, "asil")
    d = k.durum()
    assert d["asama"] == "bitti" and "uygulamalar listesinden" in d["mesaj"]


def test_md5_uyusmazligi_yuklemeyi_reddeder():
    o = SahteOturum(md5_kotu=True)
    k = yap(o)
    k.baslat(IP, PAROLA, "asil")
    d = k.durum()
    assert d["asama"] == "hata" and "gönderilemedi" in d["mesaj"] and not any("appInstallService" in c for c in o.komutlar)


@pytest.mark.parametrize("hata,parca", [
    (lg.TvHatasi("tv_ulasilamadi", "timeout"), "TV'ye ulaşamadım. TV açık mı ve bilgisayarla aynı ağda mı?"),
    (lg.TvHatasi("tv_oturum_bitti", "refused"), "50 saatte kapanır"),
    (lg.TvHatasi("tv_anahtar_kapali", "HTTP 404"), "Key Server"),
    (lg.TvHatasi("tv_parola_yanlis"), "Kod yanlış görünüyor. TV'deki Developer Mode uygulamasındaki 6 haneli kodu tekrar yazın."),
])
def test_dostca_hata_mesajlari(hata, parca):
    def al(ip):
        raise hata
    o = SahteOturum()
    k = yap(o, anahtar_al=al)
    k.baslat(IP, PAROLA, "asil")
    d = k.durum()
    assert d["asama"] == "hata" and parca in d["mesaj"]
    assert o.komutlar == []


def test_baglanti_hatasi_gecer_ve_oturum_kapanir():
    o = SahteOturum(baglan_hatasi=lg.TvHatasi("tv_oturum_bitti", "AuthenticationException"))
    k = yap(o)
    k.baslat(IP, PAROLA, "asil")
    assert k.durum()["asama"] == "hata" and "Extend" in k.durum()["mesaj"] and o.kapandi


def test_ingilizce_mesaj():
    o = SahteOturum()
    k = lg.LgKurulum(lambda: {"arayuz_dili": "en"}, anahtar_al=lambda ip: ANAHTAR,
                     oturum_fabrika=lambda: o, arka_planda=False)
    o.kurulum = k
    k.baslat(IP, PAROLA, "asil")
    assert k.durum()["mesaj"].startswith("Installed")


@pytest.mark.parametrize("ip,parola,paket,kod", [
    ("8.8.8.8", PAROLA, "asil", "tv_gecersiz_ip"), ("127.0.0.1", PAROLA, "asil", "tv_gecersiz_ip"),
    ("tv.local", PAROLA, "asil", "tv_gecersiz_ip"), (None, PAROLA, "asil", "tv_gecersiz_ip"),
    (IP, "", "asil", "tv_gecersiz_parola"), (IP, "A B", "asil", "tv_gecersiz_parola"),
    (IP, PAROLA, "bilinmeyen", "tv_gecersiz_paket")])
def test_girdi_denetimi(ip, parola, paket, kod):
    o = SahteOturum()
    k = yap(o)
    assert k.baslat(ip, parola, paket) == kod and k.durum()["asama"] == "bosta"


def test_mesgulken_ikinci_kurulum_reddedilir():
    k = lg.LgKurulum(arka_planda=False)
    k._calisiyor = True
    assert k.baslat(IP, PAROLA, "asil") == "tv_mesgul"


def test_parola_ve_anahtar_asla_sizmaz(caplog):
    caplog.set_level(logging.DEBUG)
    # hata metnine parola/anahtar kaçıran kötü bir katman bile temizlenir
    class Kacirir(SahteOturum):
        def dosya_koy(self, yerel, uzak):
            raise RuntimeError(f"parola={PAROLA} anahtar={ANAHTAR}")
    o = Kacirir()
    k = yap(o)
    k.baslat(IP, PAROLA, "asil")
    d = k.durum()
    govde = json.dumps(d, ensure_ascii=False)
    assert d["asama"] == "hata"
    for gizli in (PAROLA, "GIZLI-ANAHTAR-ICERIGI"):
        assert gizli not in govde and gizli not in caplog.text
    # başarılı akışta da günlüğe girmez
    caplog.clear()
    o2 = SahteOturum()
    k2 = yap(o2)
    k2.baslat(IP, PAROLA, "asil")
    assert PAROLA not in caplog.text and "GIZLI" not in caplog.text and PAROLA not in json.dumps(k2.durum())


def test_parola_diske_yazilmaz(tmp_path):
    o = SahteOturum()
    k = yap(o)
    k.baslat(IP, PAROLA, "asil")
    for f in tmp_path.rglob("*"):
        if f.is_file():
            ic = f.read_bytes()
            assert PAROLA.encode() not in ic and b"GIZLI-ANAHTAR" not in ic


def test_gercek_anahtar_dosyasi_parolayla_acilir():
    paramiko = pytest.importorskip("paramiko")
    anahtar = paramiko.RSAKey.generate(2048)
    cikti = io.StringIO()
    anahtar.write_private_key(cikti, password=PAROLA)
    metin = cikti.getvalue()
    assert "ENCRYPTED" in metin
    assert lg.anahtar_yukle(metin, PAROLA).get_fingerprint() == anahtar.get_fingerprint()
    with pytest.raises(lg.TvHatasi) as e:
        lg.anahtar_yukle(metin, "YANLIS1")
    assert e.value.kod == "tv_parola_yanlis"
    assert "YANLIS1" not in e.value.ayrinti


async def test_uc_noktalar(aiohttp_client, uygulama_ayari):
    uygulama_ayari["motor"] = "sahte"
    uygulama_ayari["yedek_motor"] = ""
    o = SahteOturum()
    k = yap(o)
    ist = await aiohttp_client(sunucu.uygulama_olustur(uygulama_ayari, motor_fabrika=sahte_fabrika, lg_kurulum=k))
    d = await (await ist.get("/api/tv/lg/durum")).json()
    assert d["asama"] == "bosta"
    r = await ist.post("/api/tv/lg/kur", json={"ip": "8.8.8.8", "parola": PAROLA, "paket": "asil"})
    assert r.status == 400 and (await r.json())["hata"] == "tv_gecersiz_ip"
    r = await ist.post("/api/tv/lg/kur", json={"ip": IP, "parola": PAROLA, "paket": "deneme"})
    assert r.status == 200
    govde = await (await ist.get("/api/tv/lg/durum")).text()
    assert json.loads(govde)["asama"] == "bitti" and PAROLA not in govde
    assert set(json.loads(govde)) == {"asama", "mesaj", "ayrinti"}
