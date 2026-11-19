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


_dpi_yapildi = False


def dpi_farkindaligi() -> None:
    """Yalnız Windows: işlemi DPI-duyarlı yapar; pencere/ekran koordinatları katmanla aynı piksel olur."""
    global _dpi_yapildi
    if _dpi_yapildi or sys.platform != "win32":
        return
    _dpi_yapildi = True
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:   # noqa: BLE001 — eski Windows ya da zaten ayarlanmış
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:   # noqa: BLE001
        pass


def pencere_kodu(kaynak: str) -> int | None:
    """"pencere:<hwnd>" -> hwnd (yoksa/geçersizse None)."""
    tur, _, no = (kaynak or "").partition(":")
    if tur != "pencere":
        return None
    try:
        return int(no)
    except ValueError:
        return None


def pencere_istemci_kutusu(hwnd: int, user32: Any = None) -> dict[str, int] | None:
    """Pencerenin İÇ alanının (başlık çubuğu/kenarlık yok) ekran koordinatlı dikdörtgeni
    {"left","top","width","height"}; pencere yok/simge durumunda/boyutsuzsa None. Yalnız Windows."""
    if user32 is None:
        if sys.platform != "win32":
            return None
        import ctypes
        user32 = ctypes.windll.user32
    import ctypes
    from ctypes import wintypes
    try:
        if not user32.IsWindow(hwnd) or user32.IsIconic(hwnd) or not user32.IsWindowVisible(hwnd):
            return None
        r = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.byref(r)):
            return None
        nokta = wintypes.POINT(0, 0)
        if not user32.ClientToScreen(hwnd, ctypes.byref(nokta)):
            return None
        g, y = r.right - r.left, r.bottom - r.top
        if g < 2 or y < 2:
            return None
        return {"left": int(nokta.x), "top": int(nokta.y), "width": int(g), "height": int(y)}
    except Exception:   # noqa: BLE001
        return None


def _siyah_mi(resim: Any) -> bool:
    """Tamamen (neredeyse) siyah kare: PrintWindow bazı oyunlarda (özel çizim) boş döner."""
    try:
        return all(hi <= 2 for _, hi in resim.convert("RGB").getextrema())
    except Exception:   # noqa: BLE001
        return False


def printwindow_al(hwnd: int, kutu: dict[str, int], user32: Any = None, gdi32: Any = None) -> Any:
    """PrintWindow (PW_RENDERFULLCONTENT=2) ile pencerenin istemci alanını PIL.Image (RGB) olarak alır.
    Başarısızsa YakalamaHatasi. `user32`/`gdi32` sınama için dışarıdan verilebilir."""
    import ctypes
    from ctypes import wintypes
    from PIL import Image
    if user32 is None or gdi32 is None:
        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    g, y = int(kutu["width"]), int(kutu["height"])
    pencere_dc = user32.GetWindowDC(hwnd)
    if not pencere_dc:
        raise YakalamaHatasi("Pencere görüntüsü alınamadı.")
    bellek_dc = bitmap = eski = None
    try:
        bellek_dc = gdi32.CreateCompatibleDC(pencere_dc)
        bitmap = gdi32.CreateCompatibleBitmap(pencere_dc, g, y)
        if not bellek_dc or not bitmap:
            raise YakalamaHatasi("Pencere görüntüsü alınamadı.")
        eski = gdi32.SelectObject(bellek_dc, bitmap)
        # PW_CLIENTONLY (1) | PW_RENDERFULLCONTENT (2): yalnız iç alan, GPU ile çizilen içerik de dahil
        if not user32.PrintWindow(hwnd, bellek_dc, 2 | 1):
            raise YakalamaHatasi("PrintWindow başarısız.")

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                        ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                        ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                        ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

        bi = BITMAPINFOHEADER()
        bi.biSize, bi.biWidth, bi.biHeight = ctypes.sizeof(BITMAPINFOHEADER), g, -y   # eksi: yukarıdan aşağıya
        bi.biPlanes, bi.biBitCount, bi.biCompression = 1, 32, 0
        tampon = ctypes.create_string_buffer(g * y * 4)
        if not gdi32.GetDIBits(bellek_dc, bitmap, 0, y, tampon, ctypes.byref(bi), 0):
            raise YakalamaHatasi("Pencere pikselleri okunamadı.")
        return Image.frombuffer("RGB", (g, y), bytes(tampon), "raw", "BGRX", 0, 1)
    finally:
        if eski:
            gdi32.SelectObject(bellek_dc, eski)
        if bitmap:
            gdi32.DeleteObject(bitmap)
        if bellek_dc:
            gdi32.DeleteDC(bellek_dc)
        user32.ReleaseDC(hwnd, pencere_dc)


def pencere_kare_al(hwnd: int, ekran_grab: Any, user32: Any = None, gdi32: Any = None) -> Any:
    """Windows: önce PrintWindow; boş/başarısızsa istemci alanını ekran görüntüsünden keser.
    `ekran_grab(kutu) -> PIL.Image` ekran yakalayıcıdır (mss)."""
    kutu = pencere_istemci_kutusu(hwnd, user32)
    if kutu is None:
        raise YakalamaHatasi("Pencere bulunamadı ya da simge durumunda. Oyun penceresi açık mı?")
    try:
        resim = printwindow_al(hwnd, kutu, user32, gdi32)
        if not _siyah_mi(resim):
            return resim
    except YakalamaHatasi:
        pass
    except Exception:   # noqa: BLE001 — ctypes/GDI beklenmedik hata: ekran kırpmaya düş
        pass
    return ekran_grab(kutu)


def kaynaklar() -> list[dict[str, str]]:
    """[{"kod":"ekran:1","ad":"Ekran 1 (1920×1080)"}, ...]"""
    mss = _mss()
    dpi_farkindaligi()
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
    """Kaynaktan bir PIL.Image (RGB) döndürür. "pencere:<hwnd>" için yalnız o pencerenin iç alanı."""
    from PIL import Image
    mss = _mss()
    dpi_farkindaligi()
    tur, _, no = kaynak.partition(":")
    try:
        with (getattr(mss, "MSS", None) or mss.mss)() as sct:
            def grab(kutu: Any) -> Any:
                ham = sct.grab(kutu)
                return Image.frombytes("RGB", ham.size, ham.bgra, "raw", "BGRX")

            if tur == "pencere":
                hwnd = int(no)
                if sys.platform == "win32":
                    return pencere_kare_al(hwnd, grab)
                raise YakalamaHatasi("Pencere yakalama yalnız Windows'ta desteklenir. Ekranı seçin.")
            return grab(sct.monitors[int(no or 1)])
    except YakalamaHatasi:
        raise
    except (ValueError, IndexError) as e:
        raise YakalamaHatasi("Seçilen ekran bulunamadı. Kaynağı yeniden seçin.") from e
    except Exception as e:
        raise YakalamaHatasi("Ekran görüntüsü alınamadı. Görüntü erişimi izni verildi mi?") from e
