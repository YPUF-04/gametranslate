# SPDX-License-Identifier: AGPL-3.0-only
"""LG webOS TV'ye tek tuşla kurulum: LG'nin resmi `ares-install` aracının yaptığı işin Python karşılığı.

Akış (@webos-tools/cli lib/install.js + lib/base/novacom.js ile birebir):
  1. http://<TV>:9991/webos_rsa  -> TV'nin (parolalı) özel anahtarı
  2. SSH <TV>:9922, kullanıcı "prisoner", anahtar + TV ekranındaki parola (Passphrase)
  3. /media/developer/temp/ klasörüne SFTP ile .ipk
  4. luna-send-pub -i luna://com.webos.appInstallService/dev/install  (details.state: installed | FAILED)
  5. geçici .ipk silinir, uygulama luna://com.webos.applicationManager/launch ile açılır

Gizlilik: parola ve anahtar yalnız bellekte durur; ne diske yazılır ne günlüğe ne yanıta girer.
"""
from __future__ import annotations

import hashlib
import io
import ipaddress
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .. import metinler

log = logging.getLogger("kopru.tv.lg")

SSH_KAPI = 9922
ANAHTAR_KAPI = 9991
KULLANICI = "prisoner"
GECICI_DIZIN = "/media/developer/temp"
KURULUM_KIMLIGI = "com.ares.defaultName"      # ares-install'ın kullandığı sabit kimlik
LUNA = "/usr/bin/luna-send-pub"
INSTALL_ADRESI = "luna://com.webos.appInstallService/dev/install"
LAUNCH_ADRESI = "luna://com.webos.applicationManager/launch"
MD5_BAYT = 200
# Paket adları tv/paketler/ içindedir; yeniden paketlenince (scripts/lg-paketle.sh) burası güncellenir.
PAKETLER: dict[str, tuple[str, str]] = {
    "asil": ("com.altyazikoprusu.tv_0.1.0_all.ipk", "com.altyazikoprusu.tv"),
    "acgsiz": ("com.altyazikoprusu.tv_0.1.1_all.ipk", "com.altyazikoprusu.tv"),
    "deneme": ("com.altyazikoprusu.deneme_0.1.0_all.ipk", "com.altyazikoprusu.deneme"),
}
ASAMALAR = ("anahtar", "baglaniyor", "yukleniyor", "kuruluyor", "bitti", "hata")


class TvHatasi(Exception):
    """kod: metinler.py'deki ileti kodu; ayrinti: ham hata metni (kullanıcı bize gönderebilsin diye)."""

    def __init__(self, kod: str, ayrinti: str = "") -> None:
        super().__init__(kod)
        self.kod = kod
        self.ayrinti = ayrinti


def paket_dizini() -> Path:
    # Geliştirmede: <depo>/tv/paketler. PyInstaller'da: <paket>/tv/paketler (--add-data "tv/paketler;tv/paketler").
    return Path(__file__).resolve().parents[2] / "tv" / "paketler"


def ip_gecerli_mi(ip: Any) -> bool:
    """Yalnız yerel ağ adresi (özel ya da link-local IPv4); internet adresine gidilmez."""
    if not isinstance(ip, str):
        return False
    try:
        a = ipaddress.ip_address(ip.strip())
    except ValueError:
        return False
    return a.version == 4 and (a.is_private or a.is_link_local) and not a.is_loopback and not a.is_unspecified


def parola_gecerli_mi(parola: Any) -> bool:
    return isinstance(parola, str) and re.fullmatch(r"[A-Za-z0-9]{4,32}", parola.strip() or "") is not None


# ---------- 1. anahtar ----------

def anahtar_getir(ip: str) -> str:
    """TV'nin Key Server'ından özel anahtarı alır (parolayla şifreli PEM)."""
    adres = f"http://{ip}:{ANAHTAR_KAPI}/webos_rsa"
    acici = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # TV yerel ağda: vekil kullanma
    try:
        with acici.open(adres, timeout=8) as y:
            veri = y.read(32768)
    except urllib.error.HTTPError as e:
        raise TvHatasi("tv_anahtar_kapali", f"HTTP {e.code} {adres}") from None
    except (urllib.error.URLError, OSError) as e:
        neden = getattr(e, "reason", e)
        if isinstance(neden, ConnectionRefusedError):     # TV açık ama geliştirici modu/Key Server kapalı
            raise TvHatasi("tv_oturum_bitti", f"{type(neden).__name__}: {adres}") from None
        raise TvHatasi("tv_ulasilamadi", f"{type(neden).__name__}: {neden}") from None
    metin = veri.decode("utf-8", "replace")
    if "PRIVATE KEY" not in metin:
        raise TvHatasi("tv_anahtar_kapali", "Yanıt bir anahtar değil")
    return metin


# ---------- 2. SSH katmanı (testte yerine sahtesi konur) ----------

def _paramiko() -> Any:
    try:
        import paramiko
    except ImportError:
        raise TvHatasi("tv_eklenti_yok", "paramiko yüklü değil") from None
    return paramiko


def anahtar_yukle(metin: str, parola: str) -> Any:
    """Parolalı PEM'i çözer. Parola yanlışsa TvHatasi('tv_parola_yanlis')."""
    p = _paramiko()
    try:
        return p.RSAKey.from_private_key(io.StringIO(metin), password=parola)
    except (p.SSHException, ValueError, TypeError, IndexError):
        raise TvHatasi("tv_parola_yanlis", "Anahtar bu kodla açılamadı") from None


class ParamikoOturumu:
    """SSH + SFTP. Her metot bloklar; arka plan iş parçacığında çağrılır."""

    def __init__(self) -> None:
        self.istemci: Any = None

    def baglan(self, ip: str, anahtar_metni: str, parola: str) -> None:
        p = _paramiko()
        anahtar = anahtar_yukle(anahtar_metni, parola)
        # TV'deki eski SSH sunucusu (dropbear) "server-sig-algs" bildirmez; paramiko o zaman RSA anahtarını
        # rsa-sha2-512 ile imzalar ve eski sunucu girişi reddeder (AuthenticationException). LG'nin kendi aracı
        # (ares, ssh2) klasik "ssh-rsa" ile girer. Önce varsayılanla, reddedilirse yalnız ssh-rsa ile bir kez daha.
        denemeler: list[dict[str, Any]] = [{}, {"pubkeys": ["rsa-sha2-512", "rsa-sha2-256"]}]
        son: Exception | None = None
        for engelli in denemeler:
            self.istemci = p.SSHClient()
            self.istemci.set_missing_host_key_policy(p.AutoAddPolicy())   # ares de TV'nin anahtarını doğrulamaz
            try:
                self.istemci.connect(ip, port=SSH_KAPI, username=KULLANICI, pkey=anahtar, look_for_keys=False,
                                     allow_agent=False, timeout=10, banner_timeout=20, auth_timeout=20,
                                     disabled_algorithms=engelli or None)
                return
            except p.AuthenticationException as e:
                son = e
                log.info("TV SSH girişi reddedildi (%s); eski imza yöntemiyle yeniden deneniyor",
                         "varsayılan" if not engelli else "ssh-rsa")
                try:
                    self.istemci.close()
                except Exception:  # noqa: BLE001
                    pass
                continue
            except (OSError, p.SSHException) as e:    # kapı kapalı / zaman aşımı: anahtar alındı, yani TV ayakta
                raise TvHatasi("tv_oturum_bitti", f"{type(e).__name__}: {e}") from None
        raise TvHatasi("tv_oturum_bitti", f"{type(son).__name__} (ssh-rsa dahil)") from None

    def calistir(self, komut: str, satir_cb: Callable[[str], bool] | None = None,
                 zaman_sn: float = 120.0) -> tuple[int, str]:
        """Komutu çalıştırır; satir_cb her çıktı satırı için çağrılır, True dönerse erken bitirir."""
        kanal = self.istemci.get_transport().open_session()
        kanal.exec_command(komut)
        cikti, parca, bitis, bitti = [], "", time.monotonic() + zaman_sn, False
        try:
            while time.monotonic() < bitis and not bitti:
                if kanal.recv_ready() or kanal.recv_stderr_ready():
                    veri = (kanal.recv(4096) if kanal.recv_ready() else kanal.recv_stderr(4096))
                    parca += veri.decode("utf-8", "replace")
                    cikti.append(veri.decode("utf-8", "replace"))
                    *satirlar, parca = parca.split("\n")
                    for s in satirlar:
                        if satir_cb and satir_cb(s.rstrip("\r")):
                            bitti = True
                            break
                elif kanal.exit_status_ready():
                    if parca and satir_cb:
                        satir_cb(parca)
                    break
                else:
                    time.sleep(0.05)
            else:
                if not bitti:
                    raise TvHatasi("tv_hata", "Zaman aşımı: " + komut.split(" ")[0])
            kod = kanal.recv_exit_status() if kanal.exit_status_ready() else -1
        finally:
            kanal.close()
        return kod, "".join(cikti)

    def dosya_koy(self, yerel: Path, uzak: str) -> None:
        p = _paramiko()
        try:
            sftp = self.istemci.open_sftp()
        except (p.SSHException, OSError):
            sftp = None
        if sftp is not None:
            try:
                sftp.put(str(yerel), uzak)
                return
            except OSError as e:     # 14 ≈ boş yer yok (ares: NO_FREE_SPACE)
                raise TvHatasi("tv_yukleme_hatasi", f"SFTP: {e}") from None
            finally:
                sftp.close()
        # SFTP yoksa ares de `cat` ile akıtır
        kanal = self.istemci.get_transport().open_session()
        kanal.exec_command(f'/bin/cat > "{uzak}"')
        with open(yerel, "rb") as f:
            while blok := f.read(1 << 16):
                kanal.sendall(blok)
        kanal.shutdown_write()
        if kanal.recv_exit_status() != 0:
            raise TvHatasi("tv_yukleme_hatasi", "cat ile yazma başarısız")
        kanal.close()

    def kapat(self) -> None:
        try:
            if self.istemci:
                self.istemci.close()
        except Exception:   # noqa: BLE001 — kapatırken hata önemsiz
            pass


# ---------- 3. luna-send çıktısı ----------

def luna_satiri_coz(satir: str) -> dict[str, Any] | None:
    try:
        v = json.loads(satir)
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def kurulum_sonucu(nesne: dict[str, Any]) -> tuple[str | None, str | None]:
    """ares install.js ile aynı karar: ('tamam', None) | ('hata', metin) | (None, None) = bekle."""
    if nesne.get("returnValue") is False:
        return "hata", str(nesne.get("errorText") or nesne.get("errorMessage") or json.dumps(nesne, ensure_ascii=False))
    ayrinti = nesne.get("details")
    durum = ayrinti.get("state") if isinstance(ayrinti, dict) else None
    if not isinstance(durum, str):
        return None, None
    if re.search("FAILED", durum, re.I):
        neden = ayrinti.get("reason") or durum
        return "hata", f"{neden}\n{json.dumps(nesne, ensure_ascii=False)}"
    if re.search(r"installed|^SUCCESS", durum, re.I):
        return "tamam", None
    return None, None


def _json(nesne: dict[str, Any]) -> str:
    return json.dumps(nesne, separators=(",", ":"))


# ---------- ana sınıf ----------

class LgKurulum:
    def __init__(self, ayar_al: Callable[[], dict[str, Any]] = lambda: {},
                 anahtar_al: Callable[[str], str] = anahtar_getir,
                 oturum_fabrika: Callable[[], Any] = ParamikoOturumu,
                 paket_klasoru: Callable[[], Path] = paket_dizini,
                 arka_planda: bool = True) -> None:
        self.ayar_al = ayar_al
        self.anahtar_al = anahtar_al
        self.oturum_fabrika = oturum_fabrika
        self.paket_klasoru = paket_klasoru
        self.arka_planda = arka_planda
        self._kilit = threading.Lock()
        self._durum: dict[str, Any] = {"asama": "bosta", "kod": None, "ayrinti": ""}
        self._calisiyor = False

    # --- dışarı ---
    def durum(self) -> dict[str, Any]:
        dil = self.ayar_al().get("arayuz_dili", "tr")
        with self._kilit:
            d = dict(self._durum)
        mesaj = metinler.mesaj(d["kod"], dil) if d["kod"] else ""
        return {"asama": d["asama"], "mesaj": mesaj, "ayrinti": d["ayrinti"]}

    def baslat(self, ip: Any, parola: Any, paket: Any) -> str | None:
        """Hata kodu döner (yoksa None ve iş arka planda başlar)."""
        if not ip_gecerli_mi(ip):
            return "tv_gecersiz_ip"
        if not parola_gecerli_mi(parola):
            return "tv_gecersiz_parola"
        if paket not in PAKETLER:
            return "tv_gecersiz_paket"
        with self._kilit:
            if self._calisiyor:
                return "tv_mesgul"
            self._calisiyor = True
        self._ata("anahtar", "tv_asama_anahtar")
        arg = (ip.strip(), parola.strip(), paket)
        if self.arka_planda:
            threading.Thread(target=self._calis, args=arg, daemon=True, name="lg-kurulum").start()
        else:
            self._calis(*arg)
        return None

    # --- içeri ---
    def _ata(self, asama: str, kod: str | None, ayrinti: str = "") -> None:
        with self._kilit:
            self._durum = {"asama": asama, "kod": kod, "ayrinti": ayrinti}

    @staticmethod
    def _temizle(metin: str, *gizli: str) -> str:
        for g in sorted(filter(None, gizli), key=len, reverse=True):   # uzun olan önce
            metin = metin.replace(g, "***")
        return metin

    def _calis(self, ip: str, parola: str, paket: str) -> None:
        gizliler: list[str] = [parola]    # hata metinlerinden silinecek her şey
        oturum = None
        uzak = None
        try:
            ipk_adi, uygulama = PAKETLER[paket]
            yerel = self.paket_klasoru() / ipk_adi
            if not yerel.is_file():
                raise TvHatasi("tv_paket_yok", str(yerel.name))
            self._ata("anahtar", "tv_asama_anahtar")
            anahtar = self.anahtar_al(ip)
            gizliler += [anahtar] + [s.strip() for s in anahtar.splitlines() if len(s.strip()) >= 8]
            self._ata("baglaniyor", "tv_asama_baglaniyor")
            oturum = self.oturum_fabrika()
            oturum.baglan(ip, anahtar, parola)
            del anahtar       # artık gerekmiyor; bellekten bırak
            self._ata("yukleniyor", "tv_asama_yukleniyor")
            uzak = f"{GECICI_DIZIN}/{ipk_adi}"
            oturum.calistir(f"/usr/bin/test -d {GECICI_DIZIN} || /bin/mkdir -p {GECICI_DIZIN}")
            oturum.dosya_koy(yerel, uzak)
            self._yuklemeyi_dogrula(oturum, yerel, uzak)
            self._ata("kuruluyor", "tv_asama_kuruluyor")
            self._kur(oturum, uzak)
            acildi = self._ac(oturum, uygulama)
            self._ata("bitti", "tv_bitti" if acildi else "tv_bitti_acilmadi")
        except TvHatasi as e:
            log.info("LG kurulum durdu: %s", e.kod)
            self._ata("hata", e.kod, self._temizle(e.ayrinti, *gizliler))
        except Exception as e:   # noqa: BLE001 — her şey kullanıcıya dostça gösterilir
            log.info("LG kurulum beklenmeyen hata: %s", type(e).__name__)
            self._ata("hata", "tv_hata", self._temizle(f"{type(e).__name__}: {e}", *gizliler))
        finally:
            if oturum is not None:
                if uzak:
                    try:
                        oturum.calistir(f'/bin/rm -f "{uzak}"')
                    except Exception:   # noqa: BLE001
                        pass
                oturum.kapat()
            with self._kilit:
                self._calisiyor = False

    @staticmethod
    def _yuklemeyi_dogrula(oturum: Any, yerel: Path, uzak: str) -> None:
        """ares gibi: dosyanın son 200 baytının md5'i iki tarafta aynı olmalı."""
        veri = yerel.read_bytes()[-MD5_BAYT:]
        beklenen = hashlib.md5(veri).hexdigest()  # noqa: S324 — yalnız aktarım denetimi
        _, cikti = oturum.calistir(f'/usr/bin/tail -c {len(veri)} "{uzak}" | /usr/bin/md5sum')
        gelen = (cikti.strip().split("-")[0].strip().split() or [""])[0]
        if gelen and gelen != beklenen:
            raise TvHatasi("tv_yukleme_hatasi", f"md5 uyuşmadı: {gelen} != {beklenen}")

    @staticmethod
    def _kur(oturum: Any, uzak: str) -> None:
        param = {"id": KURULUM_KIMLIGI, "ipkUrl": uzak, "subscribe": True}
        sonuc: dict[str, str | None] = {"durum": None, "hata": None}
        gorulen: list[str] = []

        def satir(s: str) -> bool:
            if not s.strip():
                return False
            gorulen.append(s)
            nesne = luna_satiri_coz(s)
            if nesne is None:
                return False
            karar, metin = kurulum_sonucu(nesne)
            if karar:
                sonuc["durum"], sonuc["hata"] = karar, metin
                return True
            return False

        cikis, ham = oturum.calistir(f"{LUNA} -i {INSTALL_ADRESI} '{_json(param)}'", satir, zaman_sn=180)
        if sonuc["durum"] == "tamam":
            return
        raise TvHatasi("tv_kurulum_hatasi", sonuc["hata"] or (ham.strip() or f"luna-send çıkış kodu {cikis}"))

    @staticmethod
    def _ac(oturum: Any, uygulama: str) -> bool:
        param = {"id": uygulama, "subscribe": False, "params": {}}
        durum = {"tamam": False}

        def satir(s: str) -> bool:
            n = luna_satiri_coz(s)
            if n is None:
                return False
            durum["tamam"] = n.get("returnValue") is True
            return True
        try:
            oturum.calistir(f"{LUNA} -n 1 {LAUNCH_ADRESI} '{_json(param)}'", satir, zaman_sn=20)
        except TvHatasi:
            return False
        return durum["tamam"]
