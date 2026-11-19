# SPDX-License-Identifier: AGPL-3.0-only
"""Genel kısayol tuşları (PROTOKOL §13.1): oyun odaktayken de çalışır (yalnız Windows, `RegisterHotKey`).

Windows dışında `destek` yanlıştır ve hiçbir şey kaydedilmez. Windows'a özgü kısım `WindowsDinleyici`dir;
testler aynı arayüzü taşıyan sahte bir dinleyiciyle çalışır (gerçek Windows gerekmez).
"""
from __future__ import annotations

import asyncio
import logging
import re
import sys
import threading
from typing import Any, Callable

log = logging.getLogger("kopru.kisayol")

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012

EYLEMLER = ("baslat_durdur", "gizle_goster", "yeniden_oku")
VARSAYILAN: dict[str, str] = {"baslat_durdur": "ctrl+shift+t", "gizle_goster": "ctrl+shift+h",
                              "yeniden_oku": "ctrl+shift+r"}
_MODLAR = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT, "win": MOD_WIN}
_ANAHTAR = re.compile(r"^(?:[a-z0-9]|f(?:[1-9]|1[0-2]))$")


def ayristir(metin: Any) -> tuple[int, int] | None:
    """"ctrl+shift+t" -> (değiştirici bayrakları, sanal tuş kodu); geçersizse None.
    İzinli tuşlar: a-z, 0-9, f1-f12. Değiştirici: ctrl/alt/shift/win; F tuşu dışında en az bir değiştirici gerekir."""
    if not isinstance(metin, str):
        return None
    parcalar = [p.strip().lower() for p in metin.split("+")]
    if len(parcalar) < 1 or any(not p for p in parcalar):
        return None
    tus, modlar = parcalar[-1], parcalar[:-1]
    if not _ANAHTAR.match(tus):
        return None
    bayrak = 0
    for m in modlar:
        if m not in _MODLAR or bayrak & _MODLAR[m]:
            return None   # bilinmeyen ya da yinelenen değiştirici
        bayrak |= _MODLAR[m]
    if bayrak == 0 and not tus.startswith("f"):
        return None
    if tus.startswith("f") and len(tus) > 1:
        vk = 0x70 + int(tus[1:]) - 1       # VK_F1 = 0x70
    else:
        vk = ord(tus.upper())              # 'A'-'Z' ve '0'-'9' sanal tuş kodu = ASCII
    return bayrak, vk


def kisayol_gecerli(metin: Any) -> bool:
    return metin in ("", None) or ayristir(metin) is not None


def kisayollar_gecerli(v: Any) -> bool:
    """Ayar `kisayollar`: bilinen eylem adları, boş (kapalı) ya da geçerli tuş dizesi."""
    return isinstance(v, dict) and all(k in EYLEMLER and isinstance(t, str) and kisayol_gecerli(t)
                                       for k, t in v.items())


def normallestir(metin: str) -> str:
    """Aynı tuşun farklı yazımları ("Shift+Ctrl+T", "ctrl+shift+t") çakışma denetiminde eşit sayılsın."""
    r = ayristir(metin)
    return "" if r is None else f"{r[0]}:{r[1]}"


class WindowsDinleyici:
    """Kendi mesaj döngüsü olan bir iş parçacığı: `RegisterHotKey(None, ...)` + `GetMessageW`.
    `baslat` kayıtları iş parçacığında yapar (kayıt ile döngü aynı iş parçacığında olmak zorundadır) ve
    sonuçları ({kimlik: None | hata kodu}) döndürür; `dur` döngüyü WM_QUIT ile sonlandırır."""

    def __init__(self) -> None:
        self._is: threading.Thread | None = None
        self._tid = 0

    def baslat(self, kayitlar: dict[int, tuple[int, int]], gelince: Callable[[int], None]) -> dict[int, str | None]:
        self.dur()
        sonuc: dict[int, str | None] = {}
        hazir = threading.Event()

        def kos() -> None:
            import ctypes
            from ctypes import wintypes
            u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32   # type: ignore[attr-defined]
            self._tid = k32.GetCurrentThreadId()
            kayitli: list[int] = []
            try:
                for kimlik, (mod, vk) in kayitlar.items():
                    if u32.RegisterHotKey(None, kimlik, mod | MOD_NOREPEAT, vk):
                        kayitli.append(kimlik)
                        sonuc[kimlik] = None
                    else:
                        sonuc[kimlik] = "kullanimda"
            finally:
                hazir.set()
            msg = wintypes.MSG()
            try:
                while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    if msg.message == WM_HOTKEY:
                        try:
                            gelince(int(msg.wParam))
                        except Exception:   # noqa: BLE001
                            log.exception("Kısayol işlenemedi")
            finally:
                for kimlik in kayitli:
                    u32.UnregisterHotKey(None, kimlik)

        self._is = threading.Thread(target=kos, name="kisayol", daemon=True)
        self._is.start()
        hazir.wait(5.0)
        return sonuc

    def dur(self) -> None:
        is_, self._is = self._is, None
        if is_ is None:
            return
        try:
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)   # type: ignore[attr-defined]
        except Exception:   # noqa: BLE001
            pass
        is_.join(2.0)


class Kisayollar:
    """Ayardaki kısayolları kaydeder; tuşa basılınca eylemi asyncio döngüsünde çalıştırır."""

    def __init__(self, eylemler: dict[str, Callable[[], Any]],
                 dinleyici_fabrika: Callable[[], Any] | None = None, destek: bool | None = None) -> None:
        self.eylemler = eylemler
        self._fabrika = dinleyici_fabrika or WindowsDinleyici
        self.destek = (sys.platform == "win32") if destek is None else destek
        self._dinleyici: Any = None
        self._dongu: asyncio.AbstractEventLoop | None = None
        self._kimlikler: dict[int, str] = {}
        self.kayitli: dict[str, bool] = {}
        self.hata: dict[str, str] = {}
        self._son: dict[str, str] | None = None

    # -- durum --
    def bilgi(self) -> dict[str, Any]:
        """`GET /api/kisayollar` yanıtı."""
        return {"destek": bool(self.destek), "kayitli": dict(self.kayitli), "hata": dict(self.hata)}

    # -- kayıt --
    def baslat(self, dongu: asyncio.AbstractEventLoop, ayar: dict[str, str]) -> None:
        self._dongu = dongu
        self.uygula(ayar)

    def uygula(self, ayar: dict[str, str] | None) -> None:
        """Ayar değişince eskileri bırakıp yenilerini kaydeder (idempotent)."""
        ayar = dict(ayar or {})
        self._son = ayar
        self.kayitli, self.hata = {}, {}
        self._birak()
        if not self.destek:
            return
        kayitlar: dict[int, tuple[int, int]] = {}
        gorulen: dict[str, str] = {}
        for i, eylem in enumerate(EYLEMLER, start=1):
            metin = ayar.get(eylem) or ""
            if not metin:
                continue                      # boş = kapalı
            r = ayristir(metin)
            if r is None:
                self.kayitli[eylem], self.hata[eylem] = False, "gecersiz"
                continue
            n = normallestir(metin)
            if n in gorulen:                  # aynı tuş iki eyleme verilmiş
                self.kayitli[eylem], self.hata[eylem] = False, "cakisma"
                continue
            gorulen[n] = eylem
            kayitlar[i] = r
            self._kimlikler[i] = eylem
        if not kayitlar:
            return
        try:
            self._dinleyici = self._fabrika()
            sonuc = self._dinleyici.baslat(kayitlar, self._basildi)
        except Exception as e:   # noqa: BLE001
            log.warning("Kısayol tuşları kaydedilemedi: %s", e)
            self._dinleyici = None
            for eylem in self._kimlikler.values():
                self.kayitli[eylem], self.hata[eylem] = False, "kullanimda"
            return
        for kimlik, eylem in self._kimlikler.items():
            h = sonuc.get(kimlik, "kullanimda")
            self.kayitli[eylem] = h is None
            if h is not None:
                self.hata[eylem] = h

    def _birak(self) -> None:
        d, self._dinleyici = self._dinleyici, None
        self._kimlikler = {}
        if d is not None:
            try:
                d.dur()
            except Exception:   # noqa: BLE001
                log.exception("Kısayol dinleyicisi durdurulamadı")

    def durdur(self) -> None:
        self._birak()
        self.kayitli = {}

    # -- tuşa basıldı (dinleyici iş parçacığından) --
    def _basildi(self, kimlik: int) -> None:
        eylem = self._kimlikler.get(kimlik)
        dongu = self._dongu
        if eylem is None or dongu is None or dongu.is_closed():
            return
        dongu.call_soon_threadsafe(self.calistir, eylem)

    def calistir(self, eylem: str) -> Any:
        """Olay döngüsünde: eylemi çalıştırır (eşzamansızsa görev olarak)."""
        f = self.eylemler.get(eylem)
        if f is None:
            return None
        try:
            r = f()
        except Exception:   # noqa: BLE001
            log.exception("Kısayol eylemi başarısız: %s", eylem)
            return None
        if asyncio.iscoroutine(r):
            t = asyncio.ensure_future(r)
            t.add_done_callback(self._gorev_bitti)
            return t
        return r

    @staticmethod
    def _gorev_bitti(t: "asyncio.Future[Any]") -> None:
        if not t.cancelled() and t.exception() is not None:
            log.error("Kısayol eylemi başarısız: %r", t.exception())
