# SPDX-License-Identifier: AGPL-3.0-only
"""Sunucusuz erişim kodu ve günlük ücretsiz süre sayacı (docs/PROTOKOL.md 7.3).

Kod: `AK1-` + Crockford base32(2 bayt yük uzunluğu + yük JSON + 64 bayt Ed25519 imzası).
Program yalnız açık anahtarı bilir; imza internetsiz doğrulanır.

Not: Program açık kaynaktır (AGPL); bu denetimi kaldıran kopyalar yapılabilir ve bu kabul
edilmiştir. Sistem dürüst kullanıcılar içindir, bir kilit değildir.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import tempfile
from datetime import date, datetime, timedelta
from typing import Any, Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from . import ayarlar, erisim_anahtar

log = logging.getLogger("kopru.erisim")

ONEK = "AK1"
ALFABE = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"   # Crockford base32
_TERS = {c: i for i, c in enumerate(ALFABE)}
_BENZER = {"I": "1", "L": "1", "O": "0"}   # okurken karışan harfler
EN_COK_GUN = 3650
VARSAYILAN_UCRETSIZ = 30
ADIM_SN_EN_COK = 30.0      # iki ölçüm arası bundan uzunsa (uyku, takılma) fazlası sayılmaz


class KodHatasi(Exception):
    """`kod`: gecersiz_kod | suresi_dolmus_kod (metinler.py'de dostça karşılıkları var)."""

    def __init__(self, kod: str) -> None:
        super().__init__(kod)
        self.kod = kod


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

def kod_uret(ozel: Ed25519PrivateKey, tur: str, gun: int | None = None, tarih: date | None = None) -> str:
    """Tek erişim kodu üretir. `tur`: "sinirsiz" ya da "gun" (gun sayısı gerekir)."""
    if tur not in ("sinirsiz", "gun"):
        raise ValueError("tur")
    yuk: dict[str, Any] = {"s": tur}
    if tur == "gun":
        if not isinstance(gun, int) or not 1 <= gun <= EN_COK_GUN:
            raise ValueError("gun")
        yuk["g"] = gun
    yuk["t"] = (tarih or date.today()).isoformat()
    yuk["n"] = "".join(secrets.choice(ALFABE) for _ in range(8))
    ham = json.dumps(yuk, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    imza = ozel.sign(ham)
    return gorunum(b32_yaz(len(ham).to_bytes(2, "big") + ham + imza))


# ---------- doğrulama ----------

def acik_anahtar_oku(b64: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(b64))


def kod_coz(kod: str, bugun: date, acik: Ed25519PublicKey | None = None) -> dict[str, Any]:
    """Kodu doğrular. {"tur","bitis"(YYYY-MM-DD|None),"tarih"} döner; olmazsa KodHatasi."""
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
        acik.verify(imza, yuk_bayt)
        yuk = json.loads(yuk_bayt.decode("utf-8"))
        tur = yuk["s"]
        tarih = date.fromisoformat(yuk["t"])
        if tur == "sinirsiz":
            return {"tur": "sinirsiz", "bitis": None, "tarih": tarih.isoformat()}
        gun = yuk["g"]
        if tur != "gun" or isinstance(gun, bool) or not isinstance(gun, int) or not 1 <= gun <= EN_COK_GUN:
            raise ValueError("yuk")
    except (InvalidSignature, ValueError, KeyError, TypeError, UnicodeDecodeError):
        raise KodHatasi("gecersiz_kod") from None
    bitis = tarih + timedelta(days=gun)
    if bugun > bitis:
        raise KodHatasi("suresi_dolmus_kod")
    return {"tur": "gun", "bitis": bitis.isoformat(), "tarih": tarih.isoformat()}


# ---------- süre sayacı ----------

class Erisim:
    """Günlük ücretsiz süre + girilen kod. Saat dışarıdan verilebilir (sınama için)."""

    def __init__(self, ayar_getir: Callable[[], dict[str, Any]],
                 simdi: Callable[[], datetime] = datetime.now,
                 acik: Ed25519PublicKey | None = None) -> None:
        self._ayar = ayar_getir
        self.simdi = simdi
        self._acik = acik
        self._son: datetime | None = None
        self._veri = self._oku()

    # -- dosya (ayar klasöründe erisim.json) --
    @staticmethod
    def _yol() -> Any:
        return ayarlar.ayar_dizini() / "erisim.json"

    def _oku(self) -> dict[str, Any]:
        try:
            v = json.loads(self._yol().read_text(encoding="utf-8"))
            if isinstance(v, dict):
                return {"kullanilan": dict(v.get("kullanilan") or {}), "kod": v.get("kod") or None}
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return {"kullanilan": {}, "kod": None}

    def _yaz(self) -> None:
        dizin = ayarlar.ayar_dizini()
        try:
            dizin.mkdir(parents=True, exist_ok=True)
            fd, gecici = tempfile.mkstemp(dir=dizin, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._veri, f, ensure_ascii=False)
            os.replace(gecici, self._yol())
        except OSError:
            log.warning("Erişim bilgisi yazılamadı")

    # -- süre --
    def bugun(self) -> date:
        return self.simdi().date()

    def ucretsiz_dakika(self) -> int:
        v = (self._ayar().get("erisim") or {}).get("ucretsiz_dakika_gun", VARSAYILAN_UCRETSIZ)
        return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else VARSAYILAN_UCRETSIZ

    def kullanilan_sn(self) -> float:
        return float(self._veri["kullanilan"].get(self.bugun().isoformat(), 0.0))

    def kalan_sn(self) -> float:
        return max(0.0, self.ucretsiz_dakika() * 60 - self.kullanilan_sn())

    def say(self, calisiyor: bool) -> None:
        """Düzenli çağrılır; yalnız çeviri çalışırken geçen süreyi bugüne ekler."""
        simdi = self.simdi()
        if calisiyor and self._son is not None and self._son.date() == simdi.date():   # gece yarısı aralığı atlanır
            fark = (simdi - self._son).total_seconds()
            if fark > 0:
                bugun = simdi.date().isoformat()
                k = self._veri["kullanilan"]
                k[bugun] = float(k.get(bugun, 0.0)) + min(fark, ADIM_SN_EN_COK)
                for eski in [g for g in k if g != bugun]:   # yalnız bugün tutulur
                    del k[eski]
                self._yaz()
        self._son = simdi

    # -- kod --
    def etkin_kod(self) -> dict[str, Any] | None:
        kod = self._veri.get("kod")
        if not kod:
            return None
        try:
            return kod_coz(kod, self.bugun(), self._acik)
        except KodHatasi:
            return None

    def kod_gir(self, kod: str) -> dict[str, Any]:
        bilgi = kod_coz(kod, self.bugun(), self._acik)   # KodHatasi yukarı gider
        self._veri["kod"] = gorunum(temizle(kod)[len(ONEK):])
        self._yaz()
        return bilgi

    def izin_var(self) -> bool:
        """Yeni motor çağrısına izin var mı (geçerli kod ya da kalan ücretsiz süre)."""
        return self.etkin_kod() is not None or self.kalan_sn() > 0

    def sinir(self) -> bool:
        return not self.izin_var()

    def durum(self) -> dict[str, Any]:
        k = self.etkin_kod()
        kalan = self.kalan_sn()
        return {"kalan_dakika": int(-(-kalan // 60)), "kod": k["tur"] if k else None,
                "bitis": k["bitis"] if k else None, "ucretsiz_dakika": self.ucretsiz_dakika()}
