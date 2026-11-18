# SPDX-License-Identifier: AGPL-3.0-only
"""Ekran/pencere yakalama (ağır bağımlılıklar tembel yüklenir)."""
from __future__ import annotations

import sys
from typing import Any


class YakalamaHatasi(Exception):
    """Yakalama kullanılamıyor; mesaj Türkçe, kullanıcıya gösterilebilir."""


def _mss() -> Any:
    try:
        import mss
    except ImportError as e:
        raise YakalamaHatasi("Ekran yakalama için 'mss' paketi kurulu değil. "
                             "Kurulum: pip install mss") from e
    return mss


def _pencereler() -> list[tuple[int, str]]:
    """Yalnız Windows: görünür, başlıklı üst düzey pencereler (ctypes)."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    bulunan: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def geri(hwnd: int, _: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                tampon = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, tampon, n + 1)
                bulunan.append((int(hwnd), tampon.value))
        return True

    user32.EnumWindows(geri, 0)
    return bulunan


def _pencere_kutusu(hwnd: int) -> dict[str, int]:
    import ctypes
    from ctypes import wintypes
    r = wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r)):
        raise YakalamaHatasi("Pencere bulunamadı. Oyun penceresi açık mı?")
    return {"left": r.left, "top": r.top, "width": r.right - r.left, "height": r.bottom - r.top}


def kaynaklar() -> list[dict[str, str]]:
    """[{"kod":"ekran:1","ad":"Ekran 1 (1920×1080)"}, ...]"""
    mss = _mss()
    out: list[dict[str, str]] = []
    try:
        with (getattr(mss, "MSS", None) or mss.mss)() as sct:
            for i, m in enumerate(sct.monitors[1:], start=1):
                out.append({"kod": f"ekran:{i}", "ad": f"Ekran {i} ({m['width']}×{m['height']})"})
    except Exception as e:
        raise YakalamaHatasi("Ekran listesi alınamadı. Görüntü sunucusu çalışıyor mu?") from e
    for hwnd, baslik in _pencereler():
        out.append({"kod": f"pencere:{hwnd}", "ad": baslik[:80]})
    return out


def kare_al(kaynak: str) -> Any:
    """Kaynaktan bir PIL.Image (RGB) döndürür."""
    from PIL import Image
    mss = _mss()
    tur, _, no = kaynak.partition(":")
    try:
        with (getattr(mss, "MSS", None) or mss.mss)() as sct:
            if tur == "pencere":
                kutu = _pencere_kutusu(int(no))
            else:
                kutu = sct.monitors[int(no or 1)]
            ham = sct.grab(kutu)
            return Image.frombytes("RGB", ham.size, ham.bgra, "raw", "BGRX")
    except YakalamaHatasi:
        raise
    except (ValueError, IndexError) as e:
        raise YakalamaHatasi("Seçilen ekran bulunamadı. Kaynağı yeniden seçin.") from e
    except Exception as e:
        raise YakalamaHatasi("Ekran görüntüsü alınamadı. Görüntü erişimi izni verildi mi?") from e
