# SPDX-License-Identifier: AGPL-3.0-only
"""Saf Python Ed25519 imza DOĞRULAMA (RFC 8032, bölüm 5.1.7).

Neden: paketli programlarda (özellikle Intel Mac) dışarıdan gelen şifreleme kütüphanesi
işletim sisteminin kütüphanesiyle çakışabiliyor. Erişim kodunu doğrulamak için tek bir
imza kontrolü yeter; bunu kütüphanesiz yapıyoruz. İmza ÜRETMEZ (o yalnız geliştirici aracında).
Hız önemli değil: kod girildiğinde bir kez çalışır (birkaç milisaniye).
"""
from __future__ import annotations

import hashlib

_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_I = pow(2, (_P - 1) // 4, _P)  # -1'in karekökü


def _ters(x: int) -> int:
    return pow(x, _P - 2, _P)


def _topla(a: tuple, b: tuple) -> tuple:
    # Genişletilmiş koordinatlarda nokta toplama (X, Y, Z, T)
    x1, y1, z1, t1 = a
    x2, y2, z2, t2 = b
    A = (y1 - x1) * (y2 - x2) % _P
    B = (y1 + x1) * (y2 + x2) % _P
    C = 2 * t1 * t2 * _D % _P
    D = 2 * z1 * z2 % _P
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _P, G * H % _P, F * G % _P, E * H % _P)


def _carp(s: int, nokta: tuple) -> tuple:
    sonuc = (0, 1, 1, 0)  # birim nokta
    while s > 0:
        if s & 1:
            sonuc = _topla(sonuc, nokta)
        nokta = _topla(nokta, nokta)
        s >>= 1
    return sonuc


def _esit(a: tuple, b: tuple) -> bool:
    x1, y1, z1, _ = a
    x2, y2, z2, _ = b
    return (x1 * z2 - x2 * z1) % _P == 0 and (y1 * z2 - y2 * z1) % _P == 0


def _x_bul(y: int, isaret: int) -> int | None:
    if y >= _P:
        return None
    x2 = (y * y - 1) * _ters(_D * y * y + 1) % _P
    if x2 == 0:
        return None if isaret else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _I % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != isaret:
        x = _P - x
    return x


def _nokta_coz(b: bytes) -> tuple | None:
    if len(b) != 32:
        return None
    y = int.from_bytes(b, "little")
    isaret = y >> 255
    y &= (1 << 255) - 1
    x = _x_bul(y, isaret)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


_GY = 4 * _ters(5) % _P
_G = (_x_bul(_GY, 0), _GY, 1, _x_bul(_GY, 0) * _GY % _P)


class AcikAnahtar:
    """32 baytlık Ed25519 açık anahtarı. `verify` geçersizse ValueError fırlatır."""

    def __init__(self, ham: bytes) -> None:
        nokta = _nokta_coz(ham)
        if nokta is None:
            raise ValueError("gecersiz_acik_anahtar")
        self._ham = bytes(ham)
        self._A = nokta

    def public_bytes_raw(self) -> bytes:
        return self._ham

    def verify(self, imza: bytes, mesaj: bytes) -> None:
        if len(imza) != 64:
            raise ValueError("imza_uzunlugu")
        R = _nokta_coz(imza[:32])
        s = int.from_bytes(imza[32:], "little")
        if R is None or s >= _L:
            raise ValueError("gecersiz_imza")
        h = int.from_bytes(hashlib.sha512(imza[:32] + self._ham + mesaj).digest(), "little") % _L
        if not _esit(_carp(s, _G), _topla(R, _carp(h, self._A))):
            raise ValueError("gecersiz_imza")
