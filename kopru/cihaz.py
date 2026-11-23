# SPDX-License-Identifier: AGPL-3.0-only
"""Cihaz numarası (PROTOKOL 17.5): kısa, kararlı, gizliliği koruyan bir bilgisayar kimliği.

Ham makine kimliği hiçbir yere gönderilmez ve gösterilmez; yalnız tuzlu SHA-256 özetinin ilk 50 biti
(10 harf Crockford base32) kullanılır. Sınırsız dublaj kodu bu numaraya bağlanır.
"""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Callable

from . import ayarlar

log = logging.getLogger("kopru.cihaz")

TUZ = b"AltYaziKoprusu/cihaz/v1"
UZUNLUK = 10
ALFABE = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"   # Crockford base32 (erisim.py ile aynı)


def _windows() -> str | None:
    try:
        import winreg  # type: ignore[import-not-found]
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                            winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)) as k:
            v, _ = winreg.QueryValueEx(k, "MachineGuid")
            return str(v)
    except Exception:   # noqa: BLE001
        return None


def _mac() -> str | None:
    try:
        cikti = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], capture_output=True, text=True,
                               timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for satir in cikti.splitlines():
        if "IOPlatformUUID" in satir:
            return satir.split("=", 1)[-1].strip().strip('"') or None
    return None


def _linux() -> str | None:
    for yol in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            v = Path(yol).read_text(encoding="ascii").strip()
        except (OSError, UnicodeDecodeError):
            continue
        if v:
            return v
    return None


def ham_kimlik() -> str | None:
    if sys.platform == "win32":
        return _windows()
    if sys.platform == "darwin":
        return _mac()
    return _linux()


def _yedek_kimlik() -> str:
    """Makine kimliği okunamazsa: bir kez rastgele üretilir ve ayar klasöründe saklanır."""
    yol = ayarlar.ayar_dizini() / "cihaz.json"
    try:
        v = json.loads(yol.read_text(encoding="utf-8")).get("kimlik")
        if isinstance(v, str) and len(v) >= 16:
            return v
    except (OSError, ValueError, AttributeError):
        pass
    v = secrets.token_hex(16)
    try:
        ayarlar.atomik_yaz(yol, json.dumps({"kimlik": v}))
    except OSError:
        log.warning("Cihaz kimliği kaydedilemedi")
    return v


def numara_uret(ham: str) -> str:
    """Ham kimlikten 10 harflik numara (gruplamasız)."""
    ozet = hashlib.sha256(TUZ + ham.strip().lower().encode("utf-8")).digest()
    sayi = int.from_bytes(ozet[:8], "big") >> (64 - 5 * UZUNLUK)
    return "".join(ALFABE[(sayi >> (5 * (UZUNLUK - 1 - i))) & 31] for i in range(UZUNLUK))


def gorunum(numara: str) -> str:
    return numara[:5] + "-" + numara[5:]


def temizle(metin: str) -> str:
    s = "".join(c for c in str(metin).upper() if c.isalnum())
    return "".join({"I": "1", "L": "1", "O": "0"}.get(c, c) for c in s)


def gecerli_mi(numara: str) -> bool:
    return len(numara) == UZUNLUK and all(c in ALFABE for c in numara)


_onbellek: str | None = None


def numara(kaynak: Callable[[], str | None] = ham_kimlik) -> str:
    """Bu bilgisayarın cihaz numarası (gruplamasız, 10 harf). Bir kez hesaplanır."""
    global _onbellek
    if _onbellek is None or kaynak is not ham_kimlik:
        ham = kaynak() or _yedek_kimlik()
        n = numara_uret(ham)
        if kaynak is not ham_kimlik:
            return n
        _onbellek = n
    return _onbellek
