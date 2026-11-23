# SPDX-License-Identifier: AGPL-3.0-only
"""LG geliştirici modu oturumunu kendiliğinden uzatma (PROTOKOL 18.6).

LG'nin Developer Mode uygulaması oturum süresini LG'nin sunucusunda sayar; süre dolunca TV açılışta geliştirici
modunu ve kurulu uygulamaları siler. Süre, TV'deki oturum belirteciyle LG'nin kendi adresinden sıfırlanır
(webosbrew dev-manager ve topluluk betiklerinin kullandığı yol):

    https://developer.lge.com/secure/ResetDevModeSession.dev?sessionToken=<belirteç>
    https://developer.lge.com/secure/CheckDevModeSession.dev?sessionToken=<belirteç>   (kalan: errorMsg "SSS:DD:SS")

Gizlilik: belirteç yalnız işletim sisteminin şifreli kasasında durur; yalnız bu iki https adresine, başka hiçbir
veri olmadan gönderilir. Durum dosyasında belirteç YOKTUR.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .. import anahtarlar
from ..ayarlar import ayar_dizini

log = logging.getLogger("kopru.tv.lg.gelistirici")

KASA_ADI = "lg_devmode"
BELIRTEC_DOSYASI = "/var/luna/preferences/devmode_enabled"
HOST = "developer.lge.com"
SIFIRLA = f"https://{HOST}/secure/ResetDevModeSession.dev"
DENETLE = f"https://{HOST}/secure/CheckDevModeSession.dev"
_BELIRTEC = re.compile(r"[A-Za-z0-9_\-]{8,256}")
_KALAN = re.compile(r"^\s*(\d{1,5}):([0-5]?\d):([0-5]?\d)\s*$")
GUN_SN = 24 * 3600
HATA_TEKRAR_SN = 3600
ELLE_EN_SIK_SN = 300
HATIRLAT_SN = 40 * 3600

MESAJLAR = {
    "tamam": {"tr": "TV'nin geliştirici modu her gün kendiliğinden uzatılıyor.",
              "en": "The TV's Developer Mode session is extended automatically every day."},
    "kapali": {"tr": "Geliştirici modu uzatma kapalı. TV'deki Developer Mode uygulamasından süreyi elle uzatın.",
               "en": "Automatic extension is off. Extend the session in the TV's Developer Mode app."},
    "belirtec_yok": {"tr": "Oturum belirteci yok: TV'yi bir kez panelden bağlayın (kurulum ya da \"Oturum uzatmayı aç\").",
                     "en": "No session token: connect the TV once from the panel (install or \"Enable session extension\")."},
    "ag": {"tr": "LG'nin sunucusuna ulaşılamadı; bir saat sonra yeniden denenecek.",
           "en": "Could not reach LG's server; will retry in an hour."},
    "gecersiz": {"tr": "LG oturum belirtecini kabul etmedi (TV'de geliştirici modu yeniden açılmış olabilir). "
                       "TV'yi bir kez daha bağlayın.",
                 "en": "LG rejected the session token (Developer Mode may have been re-enabled). Connect the TV again."},
    "kasa_yok": {"tr": "Bu bilgisayarda güvenli kasa yok: belirteç saklanamadı, süreyi TV'den elle uzatın.",
                 "en": "No secure vault on this computer: the token cannot be stored; extend the session on the TV."},
    "gecersiz_belirtec": {"tr": "Belirteç geçersiz görünüyor.", "en": "The token looks invalid."},
    "cok_sik": {"tr": "Az önce uzatıldı; birkaç dakika sonra yeniden deneyin.",
                "en": "Just extended; try again in a few minutes."},
}


def belirtec_gecerli_mi(b: Any) -> bool:
    return isinstance(b, str) and _BELIRTEC.fullmatch(b.strip()) is not None


def kalan_coz(metin: Any) -> int | None:
    """CheckDevModeSession `errorMsg` → kalan saniye ("999:58:40")."""
    m = _KALAN.match(str(metin or ""))
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))


class _YonlendirmeYok(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a: Any, **k: Any) -> None:   # noqa: D401 — yönlendirme izlenmez
        return None


def lg_iste(adres: str, belirtec: str, zaman_sn: float = 15.0) -> dict[str, Any]:
    """Yalnız sabit LG adresleri, yalnız https; yönlendirme izlenmez. Hata: OSError/ValueError."""
    u = urllib.parse.urlsplit(adres)
    if u.scheme != "https" or u.hostname != HOST or adres not in (SIFIRLA, DENETLE):
        raise ValueError("izin verilmeyen adres")
    tam = adres + "?" + urllib.parse.urlencode({"sessionToken": belirtec})
    acici = urllib.request.build_opener(_YonlendirmeYok())
    istek = urllib.request.Request(tam, headers={"User-Agent": "AltYaziKoprusu", "Accept": "application/json"})
    with acici.open(istek, timeout=zaman_sn) as y:
        if y.status != 200:
            raise OSError(f"HTTP {y.status}")
        veri = json.loads(y.read(65536).decode("utf-8", "replace"))
    if not isinstance(veri, dict):
        raise ValueError("beklenmeyen yanıt")
    return veri


class GelistiriciModu:
    ILK_BEKLEME_SN = 90.0      # açılışta önce program yerleşsin
    DENETIM_SN = 3600.0        # saatte bir bakılır; günde bir uzatılır

    def __init__(self, ayar_al: Callable[[], dict[str, Any]] = lambda: {},
                 istek: Callable[[str, str], dict[str, Any]] = lg_iste,
                 kasa_oku: Callable[[str], str | None] = anahtarlar.oku,
                 kasa_yaz: Callable[[str, str], None] = anahtarlar.yaz,
                 dosya: Path | None = None, saat: Callable[[], float] = time.time) -> None:
        self.ayar_al = ayar_al
        self.istek = istek
        self.kasa_oku = kasa_oku
        self.kasa_yaz = kasa_yaz
        self._dosya = dosya
        self.saat = saat
        self._kilit = threading.Lock()

    # --- durum dosyası (belirteç YOK) ---
    @property
    def dosya(self) -> Path:
        return self._dosya or (ayar_dizini() / "lg_devmode.json")

    def _oku(self) -> dict[str, Any]:
        try:
            v = json.loads(self.dosya.read_text(encoding="utf-8"))
            return v if isinstance(v, dict) else {}
        except (OSError, ValueError):
            return {}

    def _yaz(self, v: dict[str, Any]) -> None:
        try:
            self.dosya.parent.mkdir(parents=True, exist_ok=True)
            self.dosya.write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
        except OSError:
            log.info("lg_devmode.json yazılamadı")

    def _guncelle(self, **alanlar: Any) -> dict[str, Any]:
        with self._kilit:
            v = self._oku()
            v.update(alanlar)
            self._yaz(v)
            return v

    def _dil(self) -> str:
        return "en" if self.ayar_al().get("arayuz_dili") == "en" else "tr"

    def mesaj(self, kod: str) -> str:
        return MESAJLAR.get(kod, MESAJLAR["ag"])[self._dil()]

    def _belirtec(self) -> str | None:
        try:
            b = self.kasa_oku(KASA_ADI)
        except Exception:   # noqa: BLE001 — kasa kilitli vb.
            return None
        return b if belirtec_gecerli_mi(b) else None

    # --- dışarı ---
    def durum(self) -> dict[str, Any]:
        v = self._oku()
        var = self._belirtec() is not None
        otomatik = v.get("otomatik", True) is not False
        hata = v.get("hata")
        if not var:
            kod = "kasa_yok" if hata == "kasa_yok" else "belirtec_yok"
        elif not otomatik:
            kod = "kapali"
        else:
            kod = hata if hata in ("ag", "gecersiz") else "tamam"
        kurulum = v.get("son_kurulum")
        hatirlat = (not var or hata == "gecersiz" or not otomatik) and bool(kurulum) and \
            self.saat() - float(kurulum) >= HATIRLAT_SN
        return {"belirtec_var": var, "otomatik": otomatik, "son_uzatma": v.get("son_uzatma"),
                "kalan_sn": v.get("kalan_sn"), "bitis_tahmini": v.get("bitis_tahmini"),
                "hata": (hata if var else ("kasa_yok" if hata == "kasa_yok" else None)),
                "durum": kod, "mesaj": self.mesaj(kod), "hatirlatma": hatirlat, "tv": v.get("tv")}

    def otomatik_ayarla(self, acik: bool) -> None:
        self._guncelle(otomatik=bool(acik))

    def belirtec_kaydet(self, belirtec: str, tv: str | None = None) -> str | None:
        """Kasaya yazar (boş = sil). Hata kodu ya da None."""
        b = belirtec.strip()
        if b and not belirtec_gecerli_mi(b):
            return "gecersiz_belirtec"
        try:
            self.kasa_yaz(KASA_ADI, b)
        except anahtarlar.KasaHatasi:
            self._guncelle(hata="kasa_yok")
            return "kasa_yok"
        alan: dict[str, Any] = {"hata": None, "son_kurulum": self.saat()} if b else \
            {"hata": None, "son_uzatma": None, "kalan_sn": None, "bitis_tahmini": None}
        if tv:
            alan["tv"] = tv
        self._guncelle(**alan)
        return None

    def kurulumdan(self, belirtec_ham: str, tv: str) -> bool:
        """LG kurulumu SSH'tan dosyayı okudu: kaydet ve hemen bir kez uzat (arka planda çağrılır)."""
        b = (belirtec_ham or "").strip()
        if not belirtec_gecerli_mi(b):
            self._guncelle(son_kurulum=self.saat(), tv=tv)
            return False
        if self.belirtec_kaydet(b, tv):
            return False
        if self._oku().get("otomatik", True) is not False:
            self.uzat()
        return True

    def elle_uzat(self) -> str | None:
        v = self._oku()
        if self.saat() - float(v.get("son_deneme") or 0) < ELLE_EN_SIK_SN:
            return "cok_sik"
        return self.uzat()

    def gerekirse_uzat(self) -> str | None:
        """Döngü adımı: otomatik açık, belirteç var ve son uzatmadan 24 sa geçtiyse uzatır."""
        v = self._oku()
        if v.get("otomatik", True) is False:
            return None
        simdi = self.saat()
        son_ok = float(v.get("son_uzatma") or 0)
        son_deneme = float(v.get("son_deneme") or 0)
        if simdi - son_ok < GUN_SN:
            return None
        if v.get("hata") and simdi - son_deneme < HATA_TEKRAR_SN:
            return None
        if v.get("hata") == "gecersiz" and simdi - son_deneme < GUN_SN:
            return None   # geçersiz belirteçle LG'yi sık rahatsız etme
        if self._belirtec() is None:
            return None
        return self.uzat()

    def uzat(self) -> str | None:
        """Reset + Check. Hata kodu ("ag" | "gecersiz" | "belirtec_yok") ya da None."""
        b = self._belirtec()
        if b is None:
            return "belirtec_yok"
        simdi = self.saat()
        try:
            r = self.istek(SIFIRLA, b)
        except (OSError, ValueError, urllib.error.URLError) as e:
            log.info("LG oturum uzatma: ağ hatası (%s)", type(e).__name__)
            self._guncelle(son_deneme=simdi, hata="ag")
            return "ag"
        if str(r.get("result", "")).lower() != "success":
            log.info("LG oturum uzatma reddedildi: %s", str(r.get("errorCode", ""))[:20])
            self._guncelle(son_deneme=simdi, hata="gecersiz")
            return "gecersiz"
        kalan: int | None = None
        try:
            c = self.istek(DENETLE, b)
            if str(c.get("result", "")).lower() == "success":
                kalan = kalan_coz(c.get("errorMsg"))
        except (OSError, ValueError, urllib.error.URLError):
            pass
        self._guncelle(son_deneme=simdi, son_uzatma=simdi, hata=None, kalan_sn=kalan,
                       bitis_tahmini=(simdi + kalan) if kalan is not None else None)
        log.info("LG geliştirici modu oturumu uzatıldı (kalan: %s)", kalan)
        return None
