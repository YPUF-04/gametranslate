# SPDX-License-Identifier: AGPL-3.0-only
"""Tk penceresi: kenarlıksız, en önde, tıklamaları geçiren, saydam ekran katmanı (yalnız stdlib)."""
from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import threading
import time
import urllib.request
from typing import Any

from . import mantik

ANAHTAR_RENK = "#010203"      # Windows renk anahtarı (saydam yapılan renk)
KUTU_RENK = "#12121a"
SOLUK_RENK = "#B8B8C4"
BEKLEME_ILK, BEKLEME_EN_COK = 0.5, 5.0


def dpi_farkindaligi() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:   # noqa: BLE001 — eski Windows
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:   # noqa: BLE001
        pass


def monitorleri_bul(tk_kok: Any = None) -> list[mantik.Monitor]:
    """Önce mss (yakalama ile aynı numaralar), sonra Windows EnumDisplayMonitors, sonra Tk birincil ekranı."""
    try:
        import mss
        with (getattr(mss, "MSS", None) or mss.mss)() as sct:
            m = mantik.mss_monitorleri(list(sct.monitors))
            if m:
                return m
    except Exception:   # noqa: BLE001
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            rects: list[tuple[int, int, int, int]] = []
            Proc = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC,
                                      ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

            def cb(_h, _dc, r, _p):   # noqa: ANN001
                rects.append((r.contents.left, r.contents.top, r.contents.right, r.contents.bottom))
                return 1
            ctypes.windll.user32.EnumDisplayMonitors(None, None, Proc(cb), 0)
            m = mantik.dikdortgen_monitorleri(rects)
            if m:
                return m
        except Exception:   # noqa: BLE001
            pass
    if tk_kok is not None:
        return [mantik.Monitor(1, 0, 0, tk_kok.winfo_screenwidth(), tk_kok.winfo_screenheight(), True)]
    return []


def ebeveyn_canli(pid: int) -> bool:
    if pid <= 0:
        return True
    if sys.platform == "win32":
        try:
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)   # SYNCHRONIZE-benzeri sorgu
            if not h:
                return False
            kod = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(kod))
            ctypes.windll.kernel32.CloseHandle(h)
            return bool(ok) and kod.value == 259   # STILL_ACTIVE
        except Exception:   # noqa: BLE001
            return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True


class AkisDinleyici(threading.Thread):
    """SSE akışını okur, olayları kuyruğa koyar; kopunca artan beklemeyle yeniden bağlanır."""

    def __init__(self, url: str, kuyruk: "queue.Queue[tuple[str, dict[str, Any]]]") -> None:
        super().__init__(daemon=True)
        self.url, self.kuyruk, self.dur = url, kuyruk, threading.Event()

    def run(self) -> None:
        bekleme = BEKLEME_ILK
        acici = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # yerel istek: vekil yok
        while not self.dur.is_set():
            try:
                with acici.open(self.url, timeout=45) as y:
                    bekleme = BEKLEME_ILK
                    for ad, veri in mantik.sse_olaylari(iter(y.readline, b"")):
                        if self.dur.is_set():
                            return
                        self.kuyruk.put((ad, veri))
            except Exception:   # noqa: BLE001 — ağ/sunucu hatası: bekle, yeniden dene
                pass
            self.dur.wait(bekleme)
            bekleme = min(BEKLEME_EN_COK, bekleme * 2)


def _yazi_ailesi(tkfont: Any, kok: Any) -> str:
    var = set(tkfont.families(kok))
    sira = {"win32": ["Segoe UI"], "darwin": ["SF Pro Text", "Helvetica Neue"]}.get(
        sys.platform, ["Noto Sans", "DejaVu Sans"])
    for a in sira:
        if a in var:
            return a
    return "TkDefaultFont"


class Katman:
    def __init__(self, url: str, ekran: int, ebeveyn: int) -> None:
        import tkinter as tk
        from tkinter import font as tkfont
        self.tk, self.tkfont = tk, tkfont
        dpi_farkindaligi()
        self.kok = tk.Tk()
        self.kok.title("AltYazıKöprüsü")
        self.kok.overrideredirect(True)
        self.kok.attributes("-topmost", True)
        self.saydam = sys.platform in ("win32", "darwin")
        self.bg = ANAHTAR_RENK if sys.platform == "win32" else "systemTransparent" if sys.platform == "darwin" \
            else KUTU_RENK
        self.kok.configure(bg=self.bg)
        if sys.platform == "win32":
            self.kok.attributes("-transparentcolor", ANAHTAR_RENK)
        elif sys.platform == "darwin":
            for dene in (lambda: self.kok.attributes("-transparent", True),
                         lambda: self.kok.attributes("-alpha", 0.999)):
                try:
                    dene()
                    break
                except tk.TclError:
                    pass
        else:
            try:
                self.kok.attributes("-alpha", 0.92)
            except tk.TclError:
                pass
        m = mantik.ekran_sec(monitorleri_bul(self.kok), ekran) or mantik.Monitor(
            1, 0, 0, self.kok.winfo_screenwidth(), self.kok.winfo_screenheight(), True)
        self.mon, self.G, self.Y = m, m.g, m.y2
        self.kok.geometry(m.geometri())
        self.tuval = tk.Canvas(self.kok, bg=self.bg, highlightthickness=0, bd=0)
        self.tuval.pack(fill="both", expand=True)
        self.kok.update_idletasks()
        self.aile = _yazi_ailesi(tkfont, self.kok)
        self._tikla_gec()
        self.kuyruk: queue.Queue = queue.Queue()
        self.dinleyici = AkisDinleyici(url, self.kuyruk)
        self.zam = mantik.Zamanlayici()
        self.ebeveyn, self._son_imza, self._son_ebeveyn = ebeveyn, None, 0.0
        self._fontlar: dict[int, Any] = {}

    def _tikla_gec(self) -> None:
        if sys.platform == "win32":
            try:
                import ctypes
                u = ctypes.windll.user32
                hwnd = u.GetParent(self.kok.winfo_id()) or self.kok.winfo_id()
                stil = u.GetWindowLongW(hwnd, -20)
                # LAYERED | TRANSPARENT | TOOLWINDOW | NOACTIVATE
                u.SetWindowLongW(hwnd, -20, stil | 0x80000 | 0x20 | 0x80 | 0x08000000)
            except Exception:   # noqa: BLE001
                pass
        elif sys.platform == "darwin":
            for dene in (lambda: self.kok.attributes("-ignoremouseevents", True),
                         lambda: self.kok.tk.call("::tk::unsupported::MacWindowStyle", "style",
                                                  self.kok._w, "help", "noActivates")):
                try:
                    dene()
                except Exception:   # noqa: BLE001
                    pass

    def font(self, px: int, kalin: bool = False) -> Any:
        k = (px, kalin)
        if k not in self._fontlar:
            self._fontlar[k] = self.tkfont.Font(family=self.aile, size=-px, weight="bold" if kalin else "normal")
        return self._fontlar[k]

    # -- çizim --
    def _yuvarlak(self, x0: int, y0: int, x1: int, y1: int, r: int, renk: str) -> None:
        r = max(0, min(r, (x1 - x0) // 2, (y1 - y0) // 2))
        n = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
             x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        self.tuval.create_polygon(n, smooth=True, fill=renk, outline=renk)

    def _kutu_rengi(self, g: dict[str, Any]) -> str:
        a = max(0.0, min(1.0, float(g.get("arka_plan", 0.55))))
        t = int(18 + (1 - a) * 40)   # renk anahtarlı saydamlıkta gerçek yarı saydamlık yok: koyu düz kutu
        return f"#{t:02x}{t:02x}{t + 8:02x}"

    def ciz(self) -> None:
        z = self.zam.goruntu()
        g = z.gorunum
        self.tuval.delete("all")
        W, H = self.G, self.Y
        kutular: list[tuple[int, int, int, int]] = []
        boyut = max(14, int(g.get("yazi_boyutu", 44) * (H / 1080) * 1.0) or 14)
        for o in z.ogeler:
            p = mantik.ekran_ogesi_px(o, W, H)
            f = self.font(p["yazi_px"], True)
            metin = p["metin"] + (f"\n{p['aciklama']}" if p["aciklama"] else "")
            t = self.tuval.create_text(p["x"] + 6, p["y"] + 3, text=metin, anchor="nw", font=f,
                                       fill=g.get("yazi_rengi", "#FFFFFF"), width=max(60, p["g"]))
            bb = self.tuval.bbox(t)
            if bb:
                self.tuval.create_rectangle(bb[0] - 6, bb[1] - 3, bb[2] + 6, bb[3] + 3, fill=self._kutu_rengi(g),
                                            outline="")
                self.tuval.tag_raise(t)
                kutular.append((bb[0] - 6, bb[1] - 3, bb[2] + 6, bb[3] + 3))
        if z.yazi:
            y = z.yazi
            azami = W * 0.86
            f = self.font(boyut, True)
            kucuk = self.font(max(11, int(boyut * 0.6)))
            olc = f.measure
            while True:
                satirlar = mantik.satir_bol(y["metin"], olc, azami)
                if (max((olc(s) for s in satirlar), default=0) <= azami) or boyut <= 18:
                    break
                boyut = int(boyut * 0.9)
                f = self.font(boyut, True)
                olc = f.measure
            satir_y = f.metrics("linespace")
            ek: list[tuple[str, Any, str]] = []   # (metin, font, renk)
            if y.get("konusan"):
                ek.append((str(y["konusan"]), kucuk, g.get("konusan_rengi", "#FFD166")))
            if z.onceki:
                ek.insert(0, (z.onceki, kucuk, SOLUK_RENK))
            ek_y = sum(e[1].metrics("linespace") for e in ek)
            govde_g = max([olc(s) for s in satirlar] + [e[1].measure(e[0]) for e in ek] + [10])
            x0, y0, x1, y1 = mantik.altyazi_kutusu(W, H, g, govde_g, satir_y * len(satirlar) + ek_y)
            self._yuvarlak(x0, y0, x1, y1, 18, self._kutu_rengi(g))
            cy, cx = y0 + 16, W // 2
            for metin, ft, renk in ek:
                self.tuval.create_text(cx, cy, text=metin, font=ft, fill=renk, anchor="n")
                cy += ft.metrics("linespace")
            for s in satirlar:
                self.tuval.create_text(cx, cy, text=s, font=f, fill=g.get("yazi_rengi", "#FFFFFF"), anchor="n")
                cy += satir_y
            kutular.append((x0, y0, x1, y1))
        if not self.saydam:   # Linux: saydam yok; pencereyi yalnız içeriğin kapladığı alana küçült
            self._sigdir(kutular)

    def _sigdir(self, kutular: list[tuple[int, int, int, int]]) -> None:
        if not kutular:
            self.kok.withdraw()
            return
        x0 = min(k[0] for k in kutular); y0 = min(k[1] for k in kutular)
        x1 = max(k[2] for k in kutular); y1 = max(k[3] for k in kutular)
        self.kok.geometry(f"{x1 - x0}x{y1 - y0}{self.mon.x + x0:+d}{self.mon.y + y0:+d}")
        self.tuval.move("all", -x0, -y0)
        self.kok.deiconify()
        self.kok.attributes("-topmost", True)

    def _imza(self) -> str:
        z = self.zam.goruntu()
        return json.dumps([z.yazi and (z.yazi["id"], z.yazi["metin"], z.yazi["konusan"]), z.onceki,
                           z.ogeler, z.gorunum], sort_keys=True, default=str)

    def tik(self) -> None:
        degisti = False
        try:
            while True:
                ad, veri = self.kuyruk.get_nowait()
                degisti |= self.zam.olay(ad, veri)
        except queue.Empty:
            pass
        degisti |= self.zam.adim()
        if self.zam.kapat:
            self.bitir()
            return
        simdi = time.monotonic()
        if simdi - self._son_ebeveyn > 2.0:
            self._son_ebeveyn = simdi
            if not ebeveyn_canli(self.ebeveyn):
                self.bitir()
                return
        if degisti:
            imza = self._imza()
            if imza != self._son_imza:
                self._son_imza = imza
                self.ciz()
        self.kok.after(40, self.tik)

    def bitir(self) -> None:
        self.dinleyici.dur.set()
        try:
            self.kok.destroy()
        except Exception:   # noqa: BLE001
            pass

    def calis(self) -> None:
        self.dinleyici.start()
        self.kok.after(40, self.tik)
        self.kok.mainloop()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="kopru.katman", description="AltYazıKöprüsü ekran katmanı")
    p.add_argument("--url", required=True)
    p.add_argument("--ekran", type=int, default=1)
    p.add_argument("--ebeveyn", type=int, default=0, help="ana programın süreç numarası (ölünce çıkılır)")
    a = p.parse_args(argv)
    try:
        Katman(a.url, a.ekran, a.ebeveyn).calis()
    except Exception as e:   # noqa: BLE001 — Tk yok / ekran yok: sunucu yeniden deneme sınırını uygular
        print(f"katman hata: {e}", file=sys.stderr, flush=True)
        return 1
    return 0
