# SPDX-License-Identifier: AGPL-3.0-only
"""API anahtarları: yalnız işletim sisteminin şifreli kasasında (keyring)."""
from __future__ import annotations

import threading
import time
from typing import Any

SERVIS = "AltyaziKoprusu"
MOTORLAR = ("claude", "gemini", "deepseek", "deepl", "elevenlabs")   # son: dublaj ses servisi (çeviri motoru değil)


class KasaHatasi(Exception):
    """Güvenli kasa yok ya da erişilemiyor."""


def _keyring():
    try:
        import keyring
        from keyring.backends import fail
    except ImportError as e:
        raise KasaHatasi("kasa_yok") from e
    if isinstance(keyring.get_keyring(), fail.Keyring):
        raise KasaHatasi("kasa_yok")
    return keyring


# Kasa okuması bloklayabilir (macOS Anahtar Zinciri / Linux kilit penceresi): sonuçlar kısa süre
# RAM'de tutulur; ilk okuma `isit()` ile iş parçacığında önceden yapılır. Değer kasadan başka
# yerde değişirse en geç ONBELLEK_SN sonra görülür.
ONBELLEK_SN = 60.0
_onbellek: dict[str, tuple[float, str | None]] = {}
_onbellek_kasa: Any = None
_kilit = threading.Lock()


def _onbellegi_sifirla() -> None:
    with _kilit:
        _onbellek.clear()


def oku(motor: str) -> str | None:
    global _onbellek_kasa
    try:
        kr = _keyring()
    except KasaHatasi:
        return None
    with _kilit:
        if _onbellek_kasa is not kr.get_keyring():
            _onbellek.clear()
            _onbellek_kasa = kr.get_keyring()
        hit = _onbellek.get(motor)
        if hit is not None and time.monotonic() - hit[0] < ONBELLEK_SN:
            return hit[1]
    try:
        deger = kr.get_password(SERVIS, motor) or None
    except Exception:  # kasa kilitli vb.
        return None
    with _kilit:
        _onbellek[motor] = (time.monotonic(), deger)
    return deger


def isit() -> None:
    """Tüm anahtarları bir kez okuyup önbelleğe alır (olay döngüsü dışında çağrılır)."""
    for m in MOTORLAR:
        oku(m)


def kayitli_mi(motor: str) -> bool:
    return oku(motor) is not None


def yaz(motor: str, anahtar: str) -> None:
    """Boş anahtar = sil. Kasa yoksa KasaHatasi (düz metin ASLA yazılmaz)."""
    kr = _keyring()
    anahtar = anahtar.strip()
    _onbellegi_sifirla()
    try:
        if not anahtar:
            try:
                kr.delete_password(SERVIS, motor)
            except kr.errors.PasswordDeleteError:
                pass
        else:
            kr.set_password(SERVIS, motor, anahtar)
    except KasaHatasi:
        raise
    except Exception as e:
        raise KasaHatasi("kasa_hata") from e
    finally:
        _onbellegi_sifirla()
