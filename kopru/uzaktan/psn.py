# SPDX-License-Identifier: AGPL-3.0-only
"""İkinci PSN hesabının hesap kimliği (PROTOKOL §15.5).

Akış, chiaki-ng'nin belgelediği resmî Remote Play girişidir (Remote Play istemcisinin herkese açık
istemci bilgileri chiaki-ng'nin gui/include/psnaccountid.h dosyasındaki değerlerdir). Kullanıcının
şifresi bu programa hiç girmez: giriş Sony'nin sayfasında yapılır; program yalnız yönlendirme
adresindeki tek kullanımlık kodu alır, belirteci hesap kimliğine çevirir ve belirteci SAKLAMAZ.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Any, Callable
from urllib.parse import parse_qs, quote, urlencode, urlsplit

ISTEMCI_KIMLIGI = "ba495a24-818c-472b-b12d-ff231c1b5745"
ISTEMCI_SIRRI = "mvaiZkRsAsI1IBkY"
YETKI_ADRESI = "https://auth.api.sonyentertainmentnetwork.com/2.0/oauth/authorize"
BELIRTEC_ADRESI = "https://auth.api.sonyentertainmentnetwork.com/2.0/oauth/token"
YONLENDIRME = "https://remoteplay.dl.playstation.net/remoteplay/redirect"
KAPSAM = ("psn:clientapp referenceDataService:countryConfig.read pushNotification:webSocket.desktop.connect "
          "sessionManager:remotePlaySession.system.update")
ZAMAN_ASIMI_SN = 30.0

# istek(yontem, adres, basliklar, govde) -> (durum_kodu, gövde baytları). Testlerde sahtesi verilir.
Istek = Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]]


class PsnHatasi(Exception):
    """`kod` metinler.py anahtarıdır: psn_kod_yok | psn_reddetti | psn_cok_deneme | psn_ag | psn_yanit."""

    def __init__(self, kod: str, ayrinti: str | None = None) -> None:
        super().__init__(ayrinti or kod)
        self.kod = kod
        self.ayrinti = ayrinti


def giris_adresi() -> str:
    """Tarayıcıda açılacak Sony giriş sayfası (her seferinde yeniden giriş ister: prompt=always)."""
    return YETKI_ADRESI + "?" + urlencode({
        "service_entity": "urn:service-entity:psn", "response_type": "code", "client_id": ISTEMCI_KIMLIGI,
        "redirect_uri": YONLENDIRME, "scope": KAPSAM, "request_locale": "en_US", "ui": "pr",
        "service_logo": "ps", "layout_type": "popup", "smcid": "remoteplay", "prompt": "always",
        "PlatformPrivacyWs1": "minimal"}, quote_via=quote)


def _cok_deneme_mi(metin: str | None) -> bool:
    m = (metin or "").lower()
    return "too many" in m or "too_many" in m or "rate limit" in m


def kod_cikar(metin: str) -> str:
    """Yapıştırılan yönlendirme adresinden (ya da yalnız koddan) tek kullanımlık kodu çıkarır."""
    metin = (metin or "").strip().strip('"').strip("'")
    if not metin:
        raise PsnHatasi("psn_kod_yok")
    if "://" in metin or metin.startswith(("remoteplay.", "?")) or "code=" in metin or "error=" in metin:
        sorgu = urlsplit(metin if "://" in metin else "https://x/" + metin.lstrip("?")).query or metin.split("?", 1)[-1]
        q = parse_qs(sorgu)
        if q.get("code") and q["code"][0].strip():
            return q["code"][0].strip()
        if q.get("error"):
            ayr = " ".join(x for x in (q["error"][0], (q.get("error_description") or [""])[0]) if x)
            raise PsnHatasi("psn_cok_deneme" if _cok_deneme_mi(ayr) else "psn_reddetti", ayr[:200])
        raise PsnHatasi("psn_kod_yok")
    if re.fullmatch(r"[A-Za-z0-9._~-]{4,512}", metin):
        return metin
    raise PsnHatasi("psn_kod_yok")


def kimlik_baytlari(user_id: Any) -> bytes:
    """Sony'nin ondalık `user_id`'si -> 8 baytlık little-endian dizi."""
    try:
        sayi = int(str(user_id).strip())
    except (TypeError, ValueError) as e:
        raise PsnHatasi("psn_yanit", "user_id sayı değil") from e
    if not 0 < sayi < 2 ** 64:
        raise PsnHatasi("psn_yanit", "user_id aralık dışında")
    return sayi.to_bytes(8, "little")


def kimlik_b64(baytlar: bytes) -> str:
    return base64.b64encode(baytlar).decode("ascii")


def kimlik_gecerli(b64: Any) -> bool:
    """Elle girilen hesap kimliği: base64, tam 8 bayt."""
    if not isinstance(b64, str) or not 8 <= len(b64.strip()) <= 16:
        return False
    try:
        return len(base64.b64decode(b64.strip(), validate=True)) == 8
    except (binascii.Error, ValueError):
        return False


def ozet(b64: str | None) -> str | None:
    """Panelde gösterilen kısa özet: ilk 4 karakter + '…' (tam kimlik gösterilmez)."""
    return (b64[:4] + "…") if b64 else None


def _urllib_istek(yontem: str, adres: str, basliklar: dict[str, str], govde: bytes | None) -> tuple[int, bytes]:
    import urllib.error
    import urllib.request
    istek = urllib.request.Request(adres, data=govde, method=yontem, headers=basliklar)
    try:
        with urllib.request.urlopen(istek, timeout=ZAMAN_ASIMI_SN) as y:   # noqa: S310 — sabit https adresi
            return int(y.status), y.read()
    except urllib.error.HTTPError as e:
        return int(e.code), e.read() or b""
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise PsnHatasi("psn_ag", type(e).__name__) from e


def _sony_hatasi(govde: bytes) -> str | None:
    try:
        v = json.loads(govde.decode("utf-8", "replace"))
    except ValueError:
        return govde.decode("utf-8", "replace").strip()[:200] or None
    if isinstance(v, dict) and v.get("error"):
        return " ".join(str(x) for x in (v.get("error"), v.get("error_description"), v.get("error_code")) if x)[:200]
    return None


def _json(istek: Istek, yontem: str, adres: str, basliklar: dict[str, str], govde: bytes | None) -> dict[str, Any]:
    durum, veri = istek(yontem, adres, basliklar, govde)
    if durum >= 400:
        ayr = _sony_hatasi(veri)
        if durum == 429 or _cok_deneme_mi(ayr):
            raise PsnHatasi("psn_cok_deneme", ayr)
        if durum in (400, 401, 403):
            raise PsnHatasi("psn_reddetti", ayr)
        raise PsnHatasi("psn_ag", f"HTTP {durum}")
    try:
        v = json.loads(veri.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise PsnHatasi("psn_yanit", "JSON değil") from e
    if not isinstance(v, dict):
        raise PsnHatasi("psn_yanit", "JSON nesnesi değil")
    return v


def hesap_kimligi(kod: str, istek: Istek | None = None) -> str:
    """Kodu belirtece, belirteci hesap kimliğine çevirir. Dönen: base64 hesap kimliği. Belirteç saklanmaz."""
    istek = istek or _urllib_istek
    yetki = "Basic " + base64.b64encode(f"{ISTEMCI_KIMLIGI}:{ISTEMCI_SIRRI}".encode()).decode()
    govde = urlencode({"grant_type": "authorization_code", "code": kod, "scope": KAPSAM,
                       "redirect_uri": YONLENDIRME}, quote_via=quote).encode()
    belirtec = _json(istek, "POST", BELIRTEC_ADRESI,
                     {"Authorization": yetki, "Content-Type": "application/x-www-form-urlencoded"}, govde)
    erisim = belirtec.get("access_token")
    if not isinstance(erisim, str) or not erisim:
        ayr = _sony_hatasi(json.dumps(belirtec).encode())
        raise PsnHatasi("psn_reddetti" if ayr else "psn_yanit", ayr)
    bilgi = _json(istek, "GET", BELIRTEC_ADRESI + "/" + quote(erisim, safe=""), {"Authorization": yetki}, None)
    if "user_id" not in bilgi:
        raise PsnHatasi("psn_yanit", "user_id yok")
    return kimlik_b64(kimlik_baytlari(bilgi["user_id"]))
