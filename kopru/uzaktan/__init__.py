# SPDX-License-Identifier: AGPL-3.0-only
"""PS5 gizli bağlantı (PROTOKOL §15): pencere açmayan, kol göndermeyen Remote Play istemcisi.

Ağır iş `ayk-uzaktan` yardımcısındadır (libchiaki + FFmpeg). Bu modül onu yönetir: kayıt, uyandırma,
oturum, otomatik yeniden bağlanma, kareleri OCR'a ve sesi dublaj işçisine verme.
"""
from __future__ import annotations

import io
import logging
import secrets
import socket
import sys
import threading
import time
from typing import Any, Callable

from . import kayit as kayit_mod
from . import psn
from . import yardimci as yardimci_mod
from .yardimci import AkisSureci, Kare, YardimciHatasi, calistir, komut_satiri

log = logging.getLogger("kopru.uzaktan")

KAYNAK_KODU = "ps5:gizli"
KAYNAK_ADI = "PS5 (gizli bağlantı)"
BEKLEMELER = (2.0, 4.0, 8.0, 15.0, 30.0)
UYANMA_SN = 40.0
ILK_KARE_SN = 15.0
ONIZLEME_GENISLIK = 480
VARSAYILAN_AYAR = {"host": "", "ad": "", "cozunurluk": 720, "kodek": "h264", "kol_tv": None}

__all__ = ["KAYNAK_KODU", "Ps5Yonetici", "YardimciHatasi", "etkin", "kaynak_ogesi", "kayit_mod", "psn"]


class SesRolesi:
    """PS5 sesini (16 kHz mono s16le) yalnız 127.0.0.1'deki, anahtarı bilen dinleyicilere (dublaj işçisi) iletir."""

    def __init__(self) -> None:
        self.anahtar = secrets.token_hex(32)
        self._sunucu = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sunucu.bind(("127.0.0.1", 0))
        self._sunucu.listen(4)
        self.kapi = int(self._sunucu.getsockname()[1])
        self._istemciler: list[socket.socket] = []
        self._kilit = threading.Lock()
        self._kapali = False
        threading.Thread(target=self._kabul, daemon=True, name="ps5-ses-rolesi").start()

    def _kabul(self) -> None:
        while not self._kapali:
            try:
                s, adres = self._sunucu.accept()
            except OSError:
                return
            threading.Thread(target=self._dogrula, args=(s, adres), daemon=True).start()

    def _dogrula(self, s: socket.socket, adres: Any) -> None:
        try:
            if adres[0] != "127.0.0.1":
                s.close()
                return
            s.settimeout(5)
            alinan = b""
            while not alinan.endswith(b"\n") and len(alinan) < 200:
                parca = s.recv(200 - len(alinan))
                if not parca:
                    break
                alinan += parca
            if not secrets.compare_digest(alinan.strip(), self.anahtar.encode()):
                s.close()
                return
            s.settimeout(0.5)
            with self._kilit:
                self._istemciler.append(s)
        except OSError:
            try:
                s.close()
            except OSError:
                pass

    def ilet(self, pcm: bytes) -> None:
        with self._kilit:
            istemciler = list(self._istemciler)
        for s in istemciler:
            try:
                s.sendall(pcm)
            except OSError:   # yavaş/kopmuş dinleyici: bırakılır
                with self._kilit:
                    if s in self._istemciler:
                        self._istemciler.remove(s)
                try:
                    s.close()
                except OSError:
                    pass

    def dinleyici_sayisi(self) -> int:
        with self._kilit:
            return len(self._istemciler)

    def kapat(self) -> None:
        self._kapali = True
        try:
            self._sunucu.close()
        except OSError:
            pass
        with self._kilit:
            for s in self._istemciler:
                try:
                    s.close()
                except OSError:
                    pass
            self._istemciler.clear()


class Ps5Yonetici:
    """Tek PS5 oturumunu yönetir. İş parçacığı güvenlidir; engelleyen çağrılar olay döngüsü dışında yapılır."""

    def __init__(self, ayar_fn: Callable[[], dict[str, Any]], yayin_cb: Callable[[dict[str, Any]], None] | None = None,
                 satir: Callable[[str], list[str]] | None = None, beklemeler: tuple[float, ...] = BEKLEMELER,
                 platform: str | None = None) -> None:
        self.ayar_fn = ayar_fn
        self.yayin_cb = yayin_cb
        self.satir = satir
        self.beklemeler = beklemeler
        self.platform = platform or sys.platform
        self._kilit = threading.RLock()
        self._dur = threading.Event()
        self._is: threading.Thread | None = None
        self._surec: AkisSureci | None = None
        self._bagli = threading.Event()
        self._rol: SesRolesi | None = None
        self._son_bitti: dict[str, Any] | None = None
        self.baglanti: dict[str, Any] = {"durum": "kapali", "hata": None, "mesaj": None, "kare_boyutu": None,
                                         "kare_sayisi": 0, "ses": False, "deneme": 0, "giris_pin": False}

    # ---- durum ----
    def ayar(self) -> dict[str, Any]:
        return {**VARSAYILAN_AYAR, **(self.ayar_fn().get("ps5") or {})}

    def destek(self) -> tuple[bool, str | None]:
        if self.satir is not None:
            return True, None
        if self.platform != "win32" and yardimci_mod.yardimci_yolu() is None:
            return False, "yalniz_windows"
        if yardimci_mod.yardimci_yolu() is None:
            return False, "yardimci_yok"
        return True, None

    def _guncelle(self, **alanlar: Any) -> None:
        with self._kilit:
            degisti = any(self.baglanti.get(k) != v for k, v in alanlar.items())
            self.baglanti.update(alanlar)
            govde = dict(self.baglanti)
        if degisti and self.yayin_cb is not None:
            try:
                self.yayin_cb(govde)
            except Exception:   # noqa: BLE001
                log.exception("PS5 durum yayını başarısız")

    def durum(self) -> dict[str, Any]:
        with self._kilit:
            return dict(self.baglanti)

    def calisiyor(self) -> bool:
        return self._is is not None and self._is.is_alive()

    # ---- tek seferlik işler ----
    def _calistir(self, komut: str, girdi: dict[str, Any] | None, zaman_asimi: float) -> list[dict[str, Any]]:
        return calistir(komut, girdi, zaman_asimi, self.satir or komut_satiri)

    def bul(self, host: str | None = None, sure_ms: int = 3000) -> list[dict[str, Any]]:
        hedefler = [host] if host else ["255.255.255.255"]
        olaylar = self._calistir("bul", {"hedefler": hedefler, "sure_ms": sure_ms}, sure_ms / 1000 + 10)
        kayit = kayit_mod.kayit_oku()
        gorulen: dict[str, dict[str, Any]] = {}
        for o in olaylar:
            if o.get("olay") == "konsol" and o.get("host"):
                gorulen[str(o["host"])] = {"host": str(o["host"]), "ad": str(o.get("ad") or "PS5"),
                                           "durum": str(o.get("durum") or "bilinmiyor"), "oyun": o.get("oyun"),
                                           "kayitli": bool(kayit and kayit.get("host") == o["host"])}
        return list(gorulen.values())

    def uyandir(self) -> bool:
        kayit = kayit_mod.kayit_oku()
        if not kayit:
            raise YardimciHatasi("ps5_kayit_yok")
        host = self.ayar().get("host") or kayit["host"]
        olaylar = self._calistir("uyandir", {"host": host, "kayit_anahtari": kayit["kayit_anahtari"]}, 15)
        return any(o.get("olay") == "uyandir" and o.get("tamam") for o in olaylar)

    def kaydet(self, host: str, pin: Any) -> dict[str, Any]:
        p = kayit_mod.pin_coz(pin)
        if p is None:
            raise YardimciHatasi("ps5_pin_gecersiz")
        hesap = kayit_mod.hesap_oku()
        if not hesap:
            raise YardimciHatasi("psn_hesap_yok")
        olaylar = self._calistir("kaydet", {"host": host, "hesap": hesap, "pin": p}, 60)
        sonuc = next((o for o in olaylar if o.get("olay") == "kayit"), None)
        if sonuc is None:
            raise YardimciHatasi("ps5_kayit_hata", "yanıt yok")
        if not sonuc.get("tamam"):
            raise YardimciHatasi(kayit_mod.kayit_hata_kodu(sonuc), "; ".join(map(str, sonuc.get("satirlar") or []))[:300])
        if not kayit_mod.kayit_sonucu_gecerli(sonuc):
            raise YardimciHatasi("ps5_kayit_hata", "anahtar biçimi beklenmedik")
        return kayit_mod.kayit_yaz(host, sonuc)

    # ---- oturum ----
    def baglan(self) -> None:
        with self._kilit:
            if self.calisiyor():
                return
            self._dur.clear()
            self._bagli.clear()
            self._guncelle(durum="baglaniyor", hata=None, mesaj=None, deneme=0, giris_pin=False)
            self._is = threading.Thread(target=self._dongu, daemon=True, name="ps5-oturum")
            self._is.start()

    def kes(self) -> None:
        self._dur.set()
        s = self._surec
        if s is not None:
            s.durdur()
        is_ = self._is
        if is_ is not None and is_ is not threading.current_thread():
            is_.join(timeout=10)
        self._bagli.clear()
        self._guncelle(durum="kapali", giris_pin=False)

    def kapat(self) -> None:
        self.kes()
        if self._rol is not None:
            self._rol.kapat()
            self._rol = None

    def _hata(self, kod: str, ayrinti: str | None = None) -> None:
        from .. import metinler
        self._guncelle(durum="hata", hata=kod, mesaj=metinler.mesaj(kod, "tr"), ayrinti=ayrinti)

    def _uyanik_tut(self, host: str) -> None:
        """Konsol uykudaysa uyandırır ve açılmasını bekler. Bulunamazsa yine de bağlanmayı dener."""
        try:
            konsollar = self.bul(host, 1500)
        except YardimciHatasi:
            return
        if not konsollar or konsollar[0]["durum"] != "uyku":
            return
        self._guncelle(durum="uyandiriliyor")
        try:
            self.uyandir()
        except YardimciHatasi:
            return
        son = time.monotonic() + UYANMA_SN
        while time.monotonic() < son and not self._dur.is_set():
            if self._dur.wait(3):
                return
            try:
                k = self.bul(host, 1500)
            except YardimciHatasi:
                continue
            if k and k[0]["durum"] == "acik":
                self._dur.wait(2)
                return

    def _olay(self, olay: dict[str, Any]) -> None:
        ad = olay.get("olay")
        if ad == "bagli":
            self._bagli.set()
            self._guncelle(durum="bagli", hata=None, mesaj=None, deneme=0, giris_pin=False)
        elif ad == "giris_pin_gerekli":
            self._guncelle(giris_pin=True)
        elif ad == "bitti":
            self._son_bitti = olay
            self._bagli.clear()

    def _dongu(self) -> None:
        deneme = 0
        while not self._dur.is_set():
            kayit = kayit_mod.kayit_oku()
            hesap = kayit_mod.hesap_oku()
            if not kayit or not hesap:
                self._hata("ps5_kayit_yok")
                return
            a = self.ayar()
            host = a.get("host") or kayit["host"]
            self._guncelle(durum="baglaniyor", deneme=deneme)
            self._uyanik_tut(host)
            if self._dur.is_set():
                return
            self._son_bitti = None
            surec = AkisSureci({"host": host, "kayit_anahtari": kayit["kayit_anahtari"], "sabah": kayit["sabah"],
                                "hesap": hesap, "cozunurluk": int(a.get("cozunurluk") or 720), "fps": 30,
                                "kodek": "hevc" if a.get("kodek") == "hevc" else "h264", "ses": True},
                               self._olay, self._ses, self.satir or komut_satiri)
            try:
                surec.baslat()
            except YardimciHatasi as e:
                self._hata(e.kod, e.ayrinti)
                return
            self._surec = surec
            self._guncelle(ses=True)
            while not surec.bitti.is_set() and not self._dur.is_set():
                surec.bitti.wait(0.5)
            surec.durdur(bekle=3)
            self._surec = None
            if self._dur.is_set():
                return
            kod, tekrar = kayit_mod.oturum_bitis_kodu(self._son_bitti or {"neden": "diger"})
            if kod is None:
                self._guncelle(durum="kapali")
                return
            if not tekrar:
                self._hata(kod, str((self._son_bitti or {}).get("ayrinti") or "")[:200] or None)
                return
            bekle = self.beklemeler[min(deneme, len(self.beklemeler) - 1)]
            deneme += 1
            from .. import metinler
            self._guncelle(durum="bekliyor", hata=kod, mesaj=metinler.mesaj(kod, "tr"), deneme=deneme)
            if self._dur.wait(bekle):
                return

    def _ses(self, pcm: bytes) -> None:
        rol = self._rol
        if rol is not None:
            rol.ilet(pcm)

    def ses_kanali(self) -> dict[str, Any]:
        """Dublaj işçisinin bağlanacağı yerel ses kapısı (§15.8)."""
        with self._kilit:
            if self._rol is None:
                self._rol = SesRolesi()
            return {"kapi": self._rol.kapi, "anahtar": self._rol.anahtar}

    def giris_pin(self, pin: str) -> None:
        s = self._surec
        if s is not None:
            s.giris_pin(pin)

    def ham_kare(self, azami_genislik: int = 0, zaman_asimi: float = ILK_KARE_SN) -> Kare:
        """Son kare. Oturum kapalıysa açar ve ilk kareyi bekler. Olmazsa YardimciHatasi."""
        ok, neden = self.destek()
        if not ok:
            raise YardimciHatasi("ps5_yardimci_yok" if neden == "yardimci_yok" else "ps5_yalniz_windows")
        if not self.calisiyor():
            self.baglan()
        son = time.monotonic() + zaman_asimi
        while time.monotonic() < son:
            durum = self.durum()
            if durum["durum"] == "hata":
                raise YardimciHatasi(durum.get("hata") or "ps5_baglanti_koptu")
            s = self._surec
            if s is not None and self._bagli.is_set():
                k = s.kare(azami_genislik, zaman_asimi=2.0)
                if k is not None:
                    with self._kilit:
                        self.baglanti["kare_sayisi"] = int(self.baglanti.get("kare_sayisi") or 0) + 1
                        bas = [k.genislik, k.yukseklik]
                    if self.baglanti.get("kare_boyutu") != bas:
                        self._guncelle(kare_boyutu=bas)
                    return k
            time.sleep(0.2)
        durum = self.durum()
        raise YardimciHatasi(durum.get("hata") or "ps5_kare_yok")

    def kare(self, zaman_asimi: float = ILK_KARE_SN) -> Any:
        return self.ham_kare(0, zaman_asimi).resim()

    def onizleme_jpeg(self) -> bytes:
        if not self._bagli.is_set():
            raise YardimciHatasi("ps5_kare_yok")
        resim = self.ham_kare(ONIZLEME_GENISLIK, 3.0).resim()
        tampon = io.BytesIO()
        resim.save(tampon, "JPEG", quality=75)
        return tampon.getvalue()


_etkin: Ps5Yonetici | None = None
_etkin_kilit = threading.Lock()


def kaydet_etkin(y: Ps5Yonetici | None) -> None:
    global _etkin
    with _etkin_kilit:
        _etkin = y


def etkin() -> Ps5Yonetici:
    """Programın tek PS5 yöneticisi (sunucu kurar; yoksa ayar dosyasıyla bir tane oluşturulur)."""
    global _etkin
    with _etkin_kilit:
        if _etkin is None:
            from .. import ayarlar
            ayar = ayarlar.yukle()
            _etkin = Ps5Yonetici(lambda: ayar)
        return _etkin


def kaynak_ogesi(cihaz: str | None) -> dict[str, Any] | None:
    """`/api/kaynaklar` listesinin başına eklenen öğe (§15.6); yardımcı yoksa None."""
    y = etkin()
    ok, _ = y.destek()
    if not ok:
        return None
    kayitli = kayit_mod.kayit_oku() is not None
    return {"kod": KAYNAK_KODU, "ad": KAYNAK_ADI, "tur": "ps5", "onerilen": cihaz == "ps5" and kayitli,
            "kayitli": kayitli}
