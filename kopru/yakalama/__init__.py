# SPDX-License-Identifier: AGPL-3.0-only
"""Ekran/pencere yakalama (ağır bağımlılıklar tembel yüklenir)."""
from __future__ import annotations

import re
import sys
import time
from typing import Any, Callable


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


# Marka adı: kopru/web/panel/marka.js içindeki `window.MARKA.ad` ile AYNI olmalı (ad değişirse ikisi birlikte).
MARKA = "AltYazıKöprüsü"
MARKA_ADLARI = (MARKA, "AltYaziKoprusu")
_TR = str.maketrans({"ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i", "I": "i",
                     "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u"})


def _duz(metin: str) -> str:
    """Büyük/küçük harf ve Türkçe harf farkını siler ("AltYazıKöprüsü" == "altyazikoprusu")."""
    return str(metin or "").translate(_TR).lower()


_MARKA_DUZ = tuple(_duz(m) for m in MARKA_ADLARI)


def marka_baslikli_mi(baslik: str) -> bool:
    """§12.1: başlığında marka adı geçen pencere (panelin açık olduğu tarayıcı sekmesi dahil)."""
    d = _duz(baslik)
    return any(m in d for m in _MARKA_DUZ)


Kutu = tuple[int, int, int, int]   # (sol, üst, sağ, alt)


def _pencere_ayrintilari() -> list[dict[str, Any]]:
    """Yalnız Windows: görünür, simge durumunda olmayan, DWM'in gizlemediği üst düzey pencereler:
    [{"hwnd","baslik","kutu":(l,t,r,b),"pid"}]. Dikdörtgen: gölgesiz görünür çerçeve (yoksa GetWindowRect)."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    bulunan: list[dict[str, Any]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def geri(hwnd: int, _: int) -> bool:
        try:
            if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                return True
            n = user32.GetWindowTextLengthW(hwnd)
            if not n:
                return True
            tampon = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, tampon, n + 1)
            gizli = ctypes.c_int(0)   # DWMWA_CLOAKED=14: başka sanal masaüstündeki/askıdaki pencere
            try:
                ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(gizli), ctypes.sizeof(gizli))
            except Exception:   # noqa: BLE001
                pass
            if gizli.value:
                return True
            r = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
                return True
            try:   # DWMWA_EXTENDED_FRAME_BOUNDS=9: Win10/11'de görünmez gölge payı olmadan
                r2 = wintypes.RECT()
                if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r2), ctypes.sizeof(r2)) == 0:
                    r = r2
            except Exception:   # noqa: BLE001
                pass
            pid = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if r.right > r.left and r.bottom > r.top:
                bulunan.append({"hwnd": int(hwnd), "baslik": tampon.value,
                                "kutu": (int(r.left), int(r.top), int(r.right), int(r.bottom)),
                                "pid": int(pid.value)})
        except Exception:   # noqa: BLE001 — tek pencere hatası döngüyü bozmasın
            pass
        return True

    user32.EnumWindows(geri, 0)
    return bulunan


KENDI_YENILE_SN = 1.0
_kendi_onbellek: dict[str, Any] = {"an": -1e9, "pid": None, "kutular": []}


def kendi_pencere_kutulari(haric_pid: int | None = None, saat: Callable[[], float] = time.monotonic,
                           liste: Callable[[], list[dict[str, Any]]] | None = None) -> list[Kutu]:
    """§12.1: başlığında marka adı geçen görünür pencerelerin ekran koordinatlı dikdörtgenleri.
    ~1 sn'de bir yenilenir (ucuz). `haric_pid`: o sürecin pencereleri (ör. katmanın kendisi) sayılmaz.
    Windows dışında boş."""
    simdi = saat()
    c = _kendi_onbellek
    if liste is None and simdi - c["an"] < KENDI_YENILE_SN and c["pid"] == haric_pid:
        return list(c["kutular"])
    kaynak = liste or _pencere_ayrintilari
    try:
        kutular = [p["kutu"] for p in kaynak()
                   if marka_baslikli_mi(p.get("baslik", "")) and (haric_pid is None or p.get("pid") != haric_pid)]
    except Exception:   # noqa: BLE001
        kutular = []
    if liste is None:
        c["an"], c["pid"], c["kutular"] = simdi, haric_pid, kutular
    return list(kutular)


def ekrana_esle(kutular: list[Kutu], baslangic: tuple[int, int], boyut: tuple[int, int]) -> list[Kutu]:
    """Ekran koordinatlı dikdörtgenleri, sol-üst köşesi `baslangic` ekran noktasında olan `boyut` (g, y)
    boyutlu kareye (ekran: monitör, pencere: iç alan) eşler; kareyle kesişmeyenler atılır, kalanlar kırpılır."""
    ox, oy = baslangic
    g, y = boyut
    out: list[Kutu] = []
    for l, t, r, b in kutular:
        a = (max(0, l - ox), max(0, t - oy), min(g, r - ox), min(y, b - oy))
        if a[2] > a[0] and a[3] > a[1]:
            out.append(a)
    return out


def karart(resim: Any, kutular: list[Kutu]) -> Any:
    """Kareyi bozmadan (kopyada) piksel dikdörtgenlerini siyaha boyar; kutu yoksa kare aynen döner."""
    if not kutular:
        return resim
    from PIL import ImageDraw
    kopya = resim.copy()
    d = ImageDraw.Draw(kopya)
    for l, t, r, b in kutular:
        d.rectangle((l, t, r, b), fill=(0, 0, 0))
    return kopya


def kendi_pencerelerini_karart(resim: Any, baslangic: tuple[int, int]) -> Any:
    """Yakalanan karede marka pencerelerini siyaha boyar (Windows; başka yerde kare olduğu gibi)."""
    if sys.platform != "win32":
        return resim
    try:
        kutular = ekrana_esle(kendi_pencere_kutulari(), baslangic, resim.size)
        return karart(resim, kutular)
    except Exception:   # noqa: BLE001 — maske başarısızsa kareyi yine de ver
        return resim


# ---------- cihaza göre kaynak önerisi (§12.2) ----------

CIHAZ_DESENLERI: dict[str, tuple[str, ...]] = {
    "ps5": (r"ps remote play", r"\bchiaki"),
    "xbox": (r"\bxbox",),
    "kart": (r"windowed projector", r"projekt", r"\bobs\b", r"elgato", r"4k capture utility", r"recentral"),
}
TARAYICI_DESENLERI = (r"google chrome", r"microsoft.? edge", r"mozilla firefox", r"\bbrave\b", r"\bopera\b",
                      r"\bvivaldi\b")
TARAYICI_EXE = ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe")


def tarayici_mi(baslik: str, exe: str = "") -> bool:
    d = _duz(baslik)
    return str(exe or "").lower() in TARAYICI_EXE or any(re.search(p, d) for p in TARAYICI_DESENLERI)


def cihaz_eslesir_mi(cihaz: str | None, baslik: str) -> bool:
    d = _duz(baslik)
    return any(re.search(p, d) for p in CIHAZ_DESENLERI.get(cihaz or "", ()))


def kaynaklari_isaretle(liste: list[dict[str, Any]], cihaz: str | None) -> list[dict[str, Any]]:
    """Her öğeye `tur` ("ekran"|"pencere") ve `onerilen` ekler; pencereleri sıralar: önerilenler, diğerleri,
    en sonda tarayıcılar ve marka pencereleri (`haric: true`, asla önerilmez). Ekranlar başta kalır."""
    ekranlar: list[dict[str, Any]] = []
    uygun: list[dict[str, Any]] = []
    digerleri: list[dict[str, Any]] = []
    haric: list[dict[str, Any]] = []
    for k in liste:
        o = dict(k)
        o["tur"] = "pencere" if str(o.get("kod", "")).startswith("pencere:") else "ekran"
        o["onerilen"] = False
        if o["tur"] == "ekran":
            ekranlar.append(o)
            continue
        ad = str(o.get("ad", ""))
        if marka_baslikli_mi(ad) or tarayici_mi(ad, str(o.get("exe", ""))):
            o["haric"] = True
            haric.append(o)
        elif cihaz_eslesir_mi(cihaz, ad):
            o["onerilen"] = True
            uygun.append(o)
        else:
            digerleri.append(o)
    return ekranlar + uygun + digerleri + haric


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


def _pencere_exe(hwnd: int) -> str:
    """Yalnız Windows: pencerenin program dosya adı ("chrome.exe"); bulunamazsa boş."""
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        from ctypes import wintypes
        pid = wintypes.DWORD(0)
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = wintypes.HANDLE
        h = k32.OpenProcess(0x1000, False, pid.value)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ""
        try:
            tampon = ctypes.create_unicode_buffer(520)
            n = wintypes.DWORD(520)
            if k32.QueryFullProcessImageNameW(h, 0, tampon, ctypes.byref(n)):
                return tampon.value.replace("/", "\\").rsplit("\\", 1)[-1].lower()
        finally:
            k32.CloseHandle(h)
    except Exception:   # noqa: BLE001
        pass
    return ""


def kaynaklar(cihaz: str | None = None) -> list[dict[str, Any]]:
    """[{"kod":"ekran:1","ad":"Ekran 1 (1920×1080)","tur":"ekran","onerilen":false}, ...] (§12.2).
    Pencereler önerilenler önce, tarayıcılar ve marka pencereleri en sonda (`haric: true`)."""
    mss = _mss()
    dpi_farkindaligi()
    out: list[dict[str, Any]] = []
    try:
        with (getattr(mss, "MSS", None) or mss.mss)() as sct:
            for i, m in enumerate(sct.monitors[1:], start=1):
                out.append({"kod": f"ekran:{i}", "ad": f"Ekran {i} ({m['width']}×{m['height']})"})
    except Exception as e:
        raise YakalamaHatasi("Ekran listesi alınamadı. Görüntü sunucusu çalışıyor mu?") from e
    for hwnd, baslik in _pencereler():
        out.append({"kod": f"pencere:{hwnd}", "ad": baslik[:80], "exe": _pencere_exe(hwnd)})
    return kaynaklari_isaretle(out, cihaz)


def kare_al(kaynak: str) -> Any:
    """Kaynaktan bir PIL.Image (RGB) döndürür. "pencere:<hwnd>" için yalnız o pencerenin iç alanı.
    Windows'ta başlığında marka adı geçen pencereler (§12.1) karede siyaha boyanır."""
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
                    kutu = pencere_istemci_kutusu(hwnd)
                    resim = pencere_kare_al(hwnd, grab)
                    if kutu is not None:
                        resim = kendi_pencerelerini_karart(resim, (kutu["left"], kutu["top"]))
                    return resim
                raise YakalamaHatasi("Pencere yakalama yalnız Windows'ta desteklenir. Ekranı seçin.")
            mon = sct.monitors[int(no or 1)]
            return kendi_pencerelerini_karart(grab(mon), (int(mon["left"]), int(mon["top"])))
    except YakalamaHatasi:
        raise
    except (ValueError, IndexError) as e:
        raise YakalamaHatasi("Seçilen ekran bulunamadı. Kaynağı yeniden seçin.") from e
    except Exception as e:
        raise YakalamaHatasi("Ekran görüntüsü alınamadı. Görüntü erişimi izni verildi mi?") from e
