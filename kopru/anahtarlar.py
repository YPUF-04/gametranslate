# SPDX-License-Identifier: AGPL-3.0-only
"""API anahtarları: yalnız işletim sisteminin şifreli kasasında (keyring)."""
from __future__ import annotations

SERVIS = "AltyaziKoprusu"
MOTORLAR = ("claude", "gemini", "deepseek", "deepl")


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


def oku(motor: str) -> str | None:
    try:
        return _keyring().get_password(SERVIS, motor) or None
    except KasaHatasi:
        return None
    except Exception:  # kasa kilitli vb.
        return None


def kayitli_mi(motor: str) -> bool:
    return oku(motor) is not None


def yaz(motor: str, anahtar: str) -> None:
    """Boş anahtar = sil. Kasa yoksa KasaHatasi (düz metin ASLA yazılmaz)."""
    kr = _keyring()
    anahtar = anahtar.strip()
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
