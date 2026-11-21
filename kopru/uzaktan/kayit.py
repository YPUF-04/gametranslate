# SPDX-License-Identifier: AGPL-3.0-only
"""PS5 kaydı (Cihazı Bağla kodu) ve gizli bilgilerin şifreli kasada saklanması (PROTOKOL §15.3, §15.6)."""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from .. import anahtarlar

KASA_HESAP = "ps5_hesap"
KASA_KAYIT = "ps5_kayit"

# PS5'in bildirdiği nedenler (libchiaki session.h / regist.c)
NEDEN_PIN = 0x80108B09        # REGIST_FAILED: büyük olasılıkla yanlış kod
NEDEN_HESAP = 0x80108B02      # INVALID_PSN_ID: hesap kimliği tanınmadı
NEDEN_KULLANIMDA = 0x80108B10
NEDEN_SURUM = 0x80108B11
NEDEN_COKME = 0x80108B15
NEDEN_ANAHTAR_BICIMI = 0x80108B26   # oturum: anahtar yanlış saklanmış (GameTranslator'ın bulduğu hata)

_HEX32 = re.compile(r"[0-9a-f]{32}")


def pin_coz(metin: Any) -> int | None:
    """PS5'in "Cihazı Bağla" ekranındaki 8 haneli kod. Boşluk, tire, nokta atlanır; başka yazı
    sistemlerinin rakamları da kabul edilir. 8 hane değilse None."""
    if isinstance(metin, int) and not isinstance(metin, bool):
        metin = f"{metin:08d}" if 0 <= metin <= 99999999 else ""
    if not isinstance(metin, str):
        return None
    hane = []
    for k in metin:
        if k.isspace() or k in "-–._":
            continue
        if unicodedata.category(k) != "Nd":
            return None
        hane.append(str(unicodedata.digit(k)))
    return int("".join(hane)) if len(hane) == 8 else None


def anahtar_gecerli(hex_: Any) -> bool:
    """Yardımcının verdiği anahtar: 16 baytın küçük harf onaltılık yazımı (32 karakter)."""
    return isinstance(hex_, str) and bool(_HEX32.fullmatch(hex_))


def uyandirma_kimligi(kayit_anahtari: str) -> int:
    """§15.3: kayıt anahtarı baytlarının (sondaki sıfırlar atılmış) ASCII metni 16 tabanında sayı.
    (Yardımcı aynısını C'de yapar; burada sınama ve tanı içindir.)"""
    b = bytes.fromhex(kayit_anahtari).rstrip(b"\0")
    try:
        return int(b.decode("ascii"), 16)
    except (UnicodeDecodeError, ValueError):
        return 0


def kayit_hata_kodu(sonuc: dict[str, Any]) -> str:
    """`kaydet` komutunun başarısız sonucunu Türkçe hata koduna (metinler.py) çevirir."""
    neden = int(sonuc.get("neden") or 0)
    if neden == NEDEN_PIN:
        return "ps5_pin_yanlis"
    if neden == NEDEN_HESAP:
        return "ps5_hesap_taninmadi"
    if neden == NEDEN_KULLANIMDA:
        return "ps5_kullanimda"
    if neden == NEDEN_SURUM:
        return "ps5_surum"
    satirlar = " ".join(str(s) for s in sonuc.get("satirlar") or [])
    if sonuc.get("zaman_asimi") or any(k in satirlar for k in (
            "search response", "refused the registration search", "connect for search", "Regist search failed",
            "connect for request", "Regist connect failed", "getaddrinfo")):
        return "ps5_yanit_yok"
    return "ps5_kayit_hata"


def kayit_sonucu_gecerli(sonuc: dict[str, Any]) -> bool:
    return bool(sonuc.get("tamam")) and anahtar_gecerli(sonuc.get("kayit_anahtari")) and anahtar_gecerli(sonuc.get("sabah"))


def oturum_bitis_kodu(olay: dict[str, Any]) -> tuple[str | None, bool]:
    """Akış `bitti` olayı -> (hata kodu ya da None, yeniden denensin mi)."""
    neden = str(olay.get("neden") or "diger")
    if neden == "durdu":
        return None, False
    if neden == "reddedildi":
        return "ps5_kayit_gecersiz", False
    if neden == "kullanimda":
        return "ps5_kullanimda", False
    if neden == "surum":
        return "ps5_surum", False
    if neden == "erisilemedi":
        return "ps5_erisilemedi", True
    if int(olay.get("neden_kodu") or 0) in (NEDEN_ANAHTAR_BICIMI, NEDEN_HESAP, NEDEN_PIN):
        return "ps5_kayit_gecersiz", False
    return "ps5_baglanti_koptu", True


# ---------- şifreli kasa ----------

def hesap_oku() -> str | None:
    return anahtarlar.oku(KASA_HESAP)


def hesap_yaz(b64: str) -> None:
    """Boş = sil. Kasa yoksa anahtarlar.KasaHatasi (düz dosyaya ASLA yazılmaz)."""
    anahtarlar.yaz(KASA_HESAP, b64)


def kayit_oku() -> dict[str, Any] | None:
    ham = anahtarlar.oku(KASA_KAYIT)
    if not ham:
        return None
    try:
        v = json.loads(ham)
    except ValueError:
        return None
    if not isinstance(v, dict) or not anahtar_gecerli(v.get("kayit_anahtari")) or not anahtar_gecerli(v.get("sabah")):
        return None
    return v


def kayit_yaz(host: str, sonuc: dict[str, Any]) -> dict[str, Any]:
    v = {"host": host, "ad": str(sonuc.get("ad") or "PS5")[:40], "kayit_anahtari": sonuc["kayit_anahtari"],
         "sabah": sonuc["sabah"], "mac": str(sonuc.get("mac") or "")[:12], "hedef": int(sonuc.get("hedef") or 1000100)}
    anahtarlar.yaz(KASA_KAYIT, json.dumps(v, separators=(",", ":")))
    return v


def unut() -> None:
    for ad in (KASA_HESAP, KASA_KAYIT):
        try:
            anahtarlar.yaz(ad, "")
        except anahtarlar.KasaHatasi:
            pass
