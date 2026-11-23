# SPDX-License-Identifier: AGPL-3.0-only
"""Erişim (docs/PROTOKOL.md §17): altyazı herkese sınırsız; yalnız Türkçe dublaj süreli.

- Dublaj süresi yalnız BELLEKTE tutulur (diske yazılmaz): program kapanınca gider, açılışta 0'dır.
  "+30 dk ekle" bir reklam (ya da destek ekranı) bitince süre ekler; süreyi istemci değil bu sınıf verir.
- Sunucusuz erişim kodu: `AK1-` + Crockford base32(2 bayt yük uzunluğu + yük JSON + 64 bayt Ed25519 imzası).
  Program yalnız açık anahtarı bilir; imza internetsiz doğrulanır. Yeni kod türü `sinirsiz_dublaj` bir
  cihaz numarasına bağlıdır (kopru/cihaz.py). Eski `sinirsiz` / `gun` kodları da sınırsız dublaj verir.

Not: Program açık kaynaktır (AGPL); bu denetimleri kaldıran kopyalar yapılabilir ve bu kabul
edilmiştir. Sistem dürüst kullanıcılar içindir, bir kilit değildir.
"""
from __future__ import annotations

import base64
import json
import logging
import secrets
import time
from datetime import date, datetime, timedelta
from typing import Any, Callable

from .ed25519_dogrula import AcikAnahtar

from . import anahtarlar, ayarlar, cihaz as cihaz_mod, erisim_anahtar, reklam_ayari

log = logging.getLogger("kopru.erisim")

ONEK = "AK1"
ALFABE = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"   # Crockford base32
_TERS = {c: i for i, c in enumerate(ALFABE)}
_BENZER = {"I": "1", "L": "1", "O": "0"}   # okurken karışan harfler
EN_COK_GUN = 3650
ADIM_SN_EN_COK = 30.0      # iki ölçüm arası bundan uzunsa (uyku, takılma) fazlası sayılmaz
EKLE_DAKIKA = 30           # "+30 dk ekle" (PROTOKOL 17.2)
EN_COK_DAKIKA = 240        # en çok 4 sa birikir
REKLAM_EN_AZ_SN = 15.0     # destek ekranı / en kısa reklam (17.3)
REKLAM_EN_UZUN_SN = 120.0  # istemcinin bildirdiği reklam süresi en çok bu kadar beklenir
REKLAM_PAYI_SN = 1.0
REKLAM_ZAMAN_ASIMI_SN = 120   # TV bu sürede bitirmezse panel kendisi bitirir
REKLAM_UNUT_SN = 600.0        # bu kadar bitmeyen reklam unutulur
KASA_ADI = "erisim_kodu"      # şifreli kasadaki ad (anahtarlar.SERVIS altında)
KOD_TURLERI = ("sinirsiz", "gun", "sinirsiz_dublaj")


class KodHatasi(Exception):
    """`kod`: gecersiz_kod | suresi_dolmus_kod | baska_cihaz_kodu (metinler.py'de dostça karşılıkları var)."""

    def __init__(self, kod: str) -> None:
        super().__init__(kod)
        self.kod = kod


class ReklamHatasi(Exception):
    """`kod`: dublaj_sure_dolu | dublaj_sinirsiz | reklam_yok | reklam_erken."""

    def __init__(self, kod: str, kalan_sn: float = 0.0) -> None:
        super().__init__(kod)
        self.kod = kod
        self.kalan_sn = kalan_sn


# ---------- base32 ----------

def b32_yaz(veri: bytes) -> str:
    sayi = int.from_bytes(veri, "big")
    bit = len(veri) * 8
    kalan = (-bit) % 5
    sayi <<= kalan
    adet = (bit + kalan) // 5
    return "".join(ALFABE[(sayi >> (5 * (adet - 1 - i))) & 31] for i in range(adet))


def b32_oku(metin: str) -> bytes:
    sayi, bit = 0, 0
    for c in metin:
        sayi = (sayi << 5) | _TERS[c]
        bit += 5
    kalan = bit % 8
    if kalan:
        if sayi & ((1 << kalan) - 1):   # artan bitler sıfır olmalı
            raise ValueError("artik_bit")
        sayi >>= kalan
        bit -= kalan
    return sayi.to_bytes(bit // 8, "big")


def temizle(kod: str) -> str:
    """Boşluk, tire ve harf boyu önemsiz; I/L -> 1, O -> 0."""
    s = "".join(ch for ch in str(kod).upper() if ch.isalnum())
    return "".join(_BENZER.get(c, c) for c in s)


def gorunum(govde: str) -> str:
    gruplar = [govde[i:i + 5] for i in range(0, len(govde), 5)]
    return ONEK + "-" + "-".join(gruplar)


# ---------- üretim (yalnız geliştirici aracı kullanır) ----------

def kod_uret(ozel: Any, tur: str, gun: int | None = None, tarih: date | None = None,
             cihaz: str | None = None) -> str:
    """Tek erişim kodu üretir. `tur`: "sinirsiz_dublaj" (cihaz numarası gerekir), "sinirsiz" ya da "gun"."""
    if tur not in KOD_TURLERI:
        raise ValueError("tur")
    yuk: dict[str, Any] = {"s": tur}
    if tur == "gun":
        if not isinstance(gun, int) or not 1 <= gun <= EN_COK_GUN:
            raise ValueError("gun")
        yuk["g"] = gun
    if tur == "sinirsiz_dublaj":
        c = cihaz_mod.temizle(cihaz or "")
        if not cihaz_mod.gecerli_mi(c):
            raise ValueError("cihaz")
        yuk["c"] = c
    yuk["t"] = (tarih or date.today()).isoformat()
    yuk["n"] = "".join(secrets.choice(ALFABE) for _ in range(8))
    ham = json.dumps(yuk, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    imza = ozel.sign(ham)
    return gorunum(b32_yaz(len(ham).to_bytes(2, "big") + ham + imza))


# ---------- doğrulama ----------

def acik_anahtar_oku(b64: str) -> AcikAnahtar:
    # Kütüphanesiz doğrulayıcı: paketli programlarda şifreleme kütüphanesi gerekmez.
    return AcikAnahtar(base64.b64decode(b64))


def kod_coz(kod: str, bugun: date, acik: Any = None, cihaz: str | None = None) -> dict[str, Any]:
    """Kodu doğrular. {"tur","bitis"(YYYY-MM-DD|None),"tarih"} döner; olmazsa KodHatasi.

    `cihaz`: bu bilgisayarın numarası; `sinirsiz_dublaj` kodu yalnız onunla eşleşirse geçerlidir.
    """
    acik = acik or acik_anahtar_oku(erisim_anahtar.ACIK_ANAHTAR)
    s = temizle(kod)
    if not s.startswith(ONEK) or len(s) < 20:
        raise KodHatasi("gecersiz_kod")
    try:
        ham = b32_oku(s[len(ONEK):])
        uzunluk = int.from_bytes(ham[:2], "big")
        yuk_bayt, imza = ham[2:2 + uzunluk], ham[2 + uzunluk:]
        if len(yuk_bayt) != uzunluk or len(imza) != 64:
            raise ValueError("uzunluk")
        try:
            acik.verify(imza, yuk_bayt)
        except Exception:
            raise ValueError("imza") from None
        yuk = json.loads(yuk_bayt.decode("utf-8"))
        tur = yuk["s"]
        tarih = date.fromisoformat(yuk["t"])
        if tur == "sinirsiz":
            return {"tur": "sinirsiz", "bitis": None, "tarih": tarih.isoformat()}
        if tur == "sinirsiz_dublaj":
            c = yuk["c"]
            if not isinstance(c, str) or not cihaz_mod.gecerli_mi(c):
                raise ValueError("cihaz")
            if cihaz is None or c != cihaz_mod.temizle(cihaz):
                raise KodHatasi("baska_cihaz_kodu")
            return {"tur": "sinirsiz_dublaj", "bitis": None, "tarih": tarih.isoformat()}
        gun = yuk["g"]
        if tur != "gun" or isinstance(gun, bool) or not isinstance(gun, int) or not 1 <= gun <= EN_COK_GUN:
            raise ValueError("yuk")
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        raise KodHatasi("gecersiz_kod") from None
    bitis = tarih + timedelta(days=gun)
    if bugun > bitis:
        raise KodHatasi("suresi_dolmus_kod")
    return {"tur": "gun", "bitis": bitis.isoformat(), "tarih": tarih.isoformat()}


def vast_gecerli(v: Any) -> bool:
    return isinstance(v, str) and len(v) <= 2000 and (v == "" or (v.startswith("https://") and " " not in v))


# ---------- erişim durumu ----------

class Erisim:
    """Girilen kod + bellekteki dublaj süresi + açık reklam. Saatler dışarıdan verilebilir (sınama için)."""

    def __init__(self, ayar_getir: Callable[[], dict[str, Any]],
                 simdi: Callable[[], datetime] = datetime.now,
                 acik: Any = None, saat: Callable[[], float] = time.monotonic,
                 cihaz: Callable[[], str] | None = None) -> None:
        self._ayar = ayar_getir
        self.simdi = simdi            # yalnız kodun TARİHİ için (gun kodları)
        self.saat = saat              # süre sayacı: monotonik (sistem saati değişse de oynamaz)
        self._acik = acik
        self._cihaz_fn = cihaz or cihaz_mod.numara
        self._cihaz: str | None = None
        self._kalan_sn = 0.0          # dublaj süresi: YALNIZ BELLEKTE (PROTOKOL 17.2)
        self._son: float | None = None
        self._kod: str | None = None
        self._kod_okundu = False
        self._kod_onbellek: tuple[str, date, dict[str, Any] | None] | None = None
        self._reklam: dict[str, Any] | None = None
        self.aktif_son = False

    # -- cihaz --
    def cihaz(self) -> str:
        if self._cihaz is None:
            try:
                self._cihaz = cihaz_mod.temizle(self._cihaz_fn())
            except Exception:   # noqa: BLE001 — numara yoksa kod eşleşmez ama program çalışır
                log.warning("Cihaz numarası alınamadı", exc_info=True)
                self._cihaz = ""
        return self._cihaz

    # -- kodun saklanması: şifreli kasa, yoksa erisim.json --
    @staticmethod
    def _yol() -> Any:
        return ayarlar.ayar_dizini() / "erisim.json"

    def _dosyadan_kod(self) -> str | None:
        yol = self._yol()
        try:
            v = json.loads(yol.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            ayarlar.bozuk_yedekle(yol)
            return None
        if not isinstance(v, dict):
            ayarlar.bozuk_yedekle(yol)
            return None
        kod = v.get("kod")
        return kod if isinstance(kod, str) and kod else None

    def isit(self) -> None:
        """Kasadaki kodu ve cihaz numarasını bir kez okur (olay döngüsü dışında çağrılır)."""
        self.cihaz()
        self._kod_yukle()

    def _kod_yukle(self) -> str | None:
        if not self._kod_okundu:
            self._kod = anahtarlar.oku(KASA_ADI) or self._dosyadan_kod()
            self._kod_okundu = True
        return self._kod

    def _kod_sakla(self, kod: str) -> None:
        self._kod, self._kod_okundu = kod, True
        try:
            anahtarlar.yaz(KASA_ADI, kod)
            try:
                self._yol().unlink()   # eski düz dosyadaki kod artık gereksiz
            except OSError:
                pass
            return
        except anahtarlar.KasaHatasi:
            pass
        try:   # kasa yok: kod gizli değildir (başka cihazda işe yaramaz), dosyaya yazılır
            ayarlar.atomik_yaz(self._yol(), json.dumps({"kod": kod}, ensure_ascii=False))
        except OSError:
            log.warning("Erişim kodu yazılamadı")

    # -- kod --
    def bugun(self) -> date:
        return self.simdi().date()

    def etkin_kod(self) -> dict[str, Any] | None:
        kod = self._kod_yukle()
        if not kod:
            return None
        bugun = self.bugun()
        if self._kod_onbellek is not None and self._kod_onbellek[:2] == (kod, bugun):
            return self._kod_onbellek[2]   # imza doğrulaması saf Python ve yavaş: gün başına bir kez
        try:
            bilgi = kod_coz(kod, bugun, self._acik, self.cihaz())
        except KodHatasi:
            bilgi = None
        self._kod_onbellek = (kod, bugun, bilgi)
        return bilgi

    def kod_gir(self, kod: str) -> dict[str, Any]:
        bilgi = kod_coz(kod, self.bugun(), self._acik, self.cihaz())   # KodHatasi yukarı gider
        temiz = gorunum(temizle(kod)[len(ONEK):])
        self._kod_sakla(temiz)
        self._kod_onbellek = (temiz, self.bugun(), bilgi)
        self._reklam = None
        return bilgi

    # -- dublaj süresi (yalnız bellek) --
    def sinirsiz(self) -> bool:
        """Geçerli bir kod var mı (sınırsız dublaj)."""
        return self.etkin_kod() is not None

    def kalan_sn(self) -> float:
        return self._kalan_sn

    def dublaj_izni(self) -> bool:
        """Dublaj çalışabilir mi: kod ya da kalan süre."""
        return self._kalan_sn > 0 or self.sinirsiz()

    def ekleyebilir(self) -> bool:
        return not self.sinirsiz() and self._kalan_sn + EKLE_DAKIKA * 60 <= EN_COK_DAKIKA * 60 + 0.5

    def say(self, aktif: bool) -> None:
        """Düzenli çağrılır; yalnız dublaj gerçekten çalışırken geçen süreyi düşer."""
        simdi = self.saat()
        self.aktif_son = bool(aktif)
        if aktif and self._son is not None and not self.sinirsiz():
            fark = simdi - self._son
            if fark > 0:
                self._kalan_sn = max(0.0, self._kalan_sn - min(fark, ADIM_SN_EN_COK))
        self._son = simdi

    def _sure_ekle(self) -> None:
        self._kalan_sn = min(EN_COK_DAKIKA * 60.0, self._kalan_sn + EKLE_DAKIKA * 60.0)

    # -- reklam (+30 dk) --
    def vast_adresi(self) -> str:
        v = (self._ayar().get("erisim") or {}).get("vast_adresi") or ""
        if vast_gecerli(v) and v:
            return v
        varsayilan = getattr(reklam_ayari, "VAST_ADRESI", "") or ""
        return varsayilan if vast_gecerli(varsayilan) else ""

    def reklam_izni(self) -> bool | None:
        v = (self._ayar().get("erisim") or {}).get("reklam_izni")
        return v if v in (True, False) else None

    def acik_reklam(self) -> dict[str, Any] | None:
        r = self._reklam
        if r is not None and self.saat() - r["baslangic"] > REKLAM_UNUT_SN:
            self._reklam = r = None
        return r

    def reklam_baslat(self, tv_var: bool, yer: str = "otomatik") -> dict[str, Any]:
        if self.sinirsiz():
            raise ReklamHatasi("dublaj_sinirsiz")
        if not self.ekleyebilir():
            raise ReklamHatasi("dublaj_sure_dolu")
        r = self.acik_reklam()
        if r is None:
            # izin yoksa yalnız kendi destek ekranımız (hiçbir yere bağlanmaz)
            vast = (self.vast_adresi() or None) if self.reklam_izni() is True else None
            r = {"id": "r" + secrets.token_hex(8), "baslangic": self.saat(), "vast": vast,
                 "hedef": "tv" if tv_var and yer != "panel" else "panel"}
            self._reklam = r
        return self.reklam_gorunum(r)

    def reklam_gorunum(self, r: dict[str, Any]) -> dict[str, Any]:
        return {"id": r["id"], "vast": r["vast"], "en_az_sn": int(REKLAM_EN_AZ_SN), "hedef": r["hedef"],
                "zaman_asimi_sn": REKLAM_ZAMAN_ASIMI_SN}

    def reklam_bitir(self, kimlik: Any, sure_sn: Any = None) -> dict[str, Any]:
        """İstemci "reklam bitti" der; süre yalnız sunucu saatine göre yeterince zaman geçtiyse verilir."""
        r = self.acik_reklam()
        if r is None or not isinstance(kimlik, str) or kimlik != r["id"]:
            raise ReklamHatasi("reklam_yok")
        try:
            bildirilen = float(sure_sn) if sure_sn is not None and not isinstance(sure_sn, bool) else 0.0
        except (TypeError, ValueError):
            bildirilen = 0.0
        if bildirilen != bildirilen:   # NaN
            bildirilen = 0.0
        gerekli = max(REKLAM_EN_AZ_SN, min(max(bildirilen, 0.0), REKLAM_EN_UZUN_SN)) - REKLAM_PAYI_SN
        gecen = self.saat() - r["baslangic"]
        if gecen < gerekli:
            raise ReklamHatasi("reklam_erken", gerekli - gecen)
        self._reklam = None
        if not self.ekleyebilir():
            raise ReklamHatasi("dublaj_sure_dolu")
        self._sure_ekle()
        return {"tamam": True, "id": r["id"], "kalan_dakika": self.kalan_dakika()}

    # -- görünüm --
    def kalan_dakika(self) -> int:
        return int(-(-self._kalan_sn // 60))

    def durum(self, dublaj_acik: bool = False, tv_reklam: bool = False) -> dict[str, Any]:
        k = self.etkin_kod()
        sinirsiz = k is not None
        r = self.acik_reklam()
        return {
            "altyazi": "sinirsiz",
            "dublaj": {"sinirsiz": sinirsiz, "kalan_sn": int(self._kalan_sn), "kalan_dakika": self.kalan_dakika(),
                       "aktif": bool(self.aktif_son), "durdu": bool(dublaj_acik and not self.dublaj_izni()),
                       "ekle_dakika": EKLE_DAKIKA, "en_cok_dakika": EN_COK_DAKIKA, "ekleyebilir": self.ekleyebilir()},
            "kod": k["tur"] if k else None, "bitis": k["bitis"] if k else None,
            "cihaz": cihaz_mod.gorunum(self.cihaz()) if self.cihaz() else "",
            "tv_reklam": bool(tv_reklam),
            "vast_var": bool(self.vast_adresi()), "reklam_izni": self.reklam_izni(),
            "reklam": None if r is None else {"id": r["id"], "hedef": r["hedef"], "en_az_sn": int(REKLAM_EN_AZ_SN),
                                              "gecen_sn": round(self.saat() - r["baslangic"], 1)},
        }
