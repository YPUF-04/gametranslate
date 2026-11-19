# SPDX-License-Identifier: AGPL-3.0-only
"""Ekran katmanının saf mantığı (pencere yok): zamanlama, yerleşim, monitör geometrisi, SSE ayrıştırma.

Tk burada içe aktarılmaz; böylece testler pencere açmadan çalışır.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator

EN_AZ_MS = 1800
ONCEKI_SN = 2.5          # §7.2/7: önceki satır küçük ve soluk kalır
EKRAN_GITTI_SN = 1.0     # §7.2/8: ekrandan giden öğe 1 sn sonra kalkar
VARSAYILAN_GORUNUM: dict[str, Any] = {
    "yazi_boyutu": 44, "konum": "alt", "kenar_bosluk": 0.08, "arka_plan": 0.55,
    "yazi_rengi": "#FFFFFF", "konusan_rengi": "#FFD166",
    "asil_goster": False, "ekran_cevir": True, "onceki_goster": True,
}


def okuma_suresi_ms(metin: str) -> int:
    return min(9000, 800 + len(metin) * 55)


def en_az_ms(metin: str) -> int:
    return max(EN_AZ_MS, okuma_suresi_ms(metin))


# ---------- zamanlama durum makinesi ----------

@dataclass
class Goruntu:
    yazi: dict[str, Any] | None
    onceki: str | None
    ogeler: list[dict[str, Any]]
    gorunum: dict[str, Any] = field(default_factory=dict)


class Zamanlayici:
    """SSE olaylarından "şu an ne çizilecek"i çıkarır (PROTOKOL 7.2, istemci tarafı)."""

    def __init__(self, saat: Callable[[], float] = time.monotonic) -> None:
        self.saat = saat
        self.gorunum: dict[str, Any] = dict(VARSAYILAN_GORUNUM)
        self.yazi: dict[str, Any] | None = None
        self._onceki: tuple[str, float] | None = None
        self._ogeler: dict[str, dict[str, Any]] = {}
        self.kapat = False

    # -- olaylar --
    def olay(self, ad: str, veri: dict[str, Any] | None, simdi: float | None = None) -> bool:
        """Olayı işler; çizimin değişmesi gerekiyorsa True."""
        simdi = self.saat() if simdi is None else simdi
        veri = veri if isinstance(veri, dict) else {}
        if ad == "gorunum":
            self.gorunum = {**VARSAYILAN_GORUNUM, **veri}
            return True
        if ad == "yazi":
            return self._yazi(veri, simdi)
        if ad == "yazi-sil":
            if self.yazi is not None:
                self.yazi["sil_an"] = max(simdi, self.yazi["min_bitis"])
            return True
        if ad == "ekran":
            return self._ekran(veri, simdi)
        if ad == "ekran-sil":
            for o in self._ogeler.values():
                if o["gitti"] is None:
                    o["gitti"] = simdi
            return True
        if ad == "katman-kapat":
            self.kapat = True
            return True
        return False

    def _yazi(self, v: dict[str, Any], simdi: float) -> bool:
        metin = str(v.get("metin") or "")
        if not metin.strip():
            return False
        sure = v.get("sure_ms")
        sure = int(sure) if isinstance(sure, (int, float)) and not isinstance(sure, bool) and sure > 0 \
            else en_az_ms(metin)
        bitis = simdi + sure / 1000
        y = self.yazi
        ayni = y is not None and (v.get("id") == y["id"] or v.get("devam") is True)
        if ayni:   # yerinde güncelle: zıplama, sönme yok
            y.update(metin=metin, asil=str(v.get("asil") or ""), konusan=v.get("konusan"),
                     bitis=max(y["bitis"], bitis), sil_an=None)
            if v.get("id"):
                y["id"] = v["id"]
            return True
        if y is not None and self.gorunum.get("onceki_goster", True):
            self._onceki = (y["metin"], simdi + ONCEKI_SN)
        else:
            self._onceki = None
        self.yazi = {"id": v.get("id") or f"y{simdi}", "metin": metin, "asil": str(v.get("asil") or ""),
                     "konusan": v.get("konusan"), "tur": v.get("tur", "altyazi"), "ilk": simdi,
                     "min_bitis": simdi + min(sure, en_az_ms(metin)) / 1000, "bitis": bitis, "sil_an": None}
        return True

    def _ekran(self, v: dict[str, Any], simdi: float) -> bool:
        gelen: dict[str, dict[str, Any]] = {}
        for i, o in enumerate(v.get("ogeler") or []):
            if not isinstance(o, dict) or not str(o.get("metin") or "").strip():
                continue
            kimlik = str(o.get("id") or f"{o.get('x', 0):.3f},{o.get('y', 0):.3f}")
            gelen[kimlik] = o
        for kimlik, o in gelen.items():
            eski = self._ogeler.get(kimlik)
            if eski is not None:
                eski["oge"] = o
                eski["gitti"] = None
            else:
                self._ogeler[kimlik] = {"oge": o, "gitti": None}
        for kimlik, e in self._ogeler.items():
            if kimlik not in gelen and e["gitti"] is None:
                e["gitti"] = simdi
        return True

    # -- zaman --
    def adim(self, simdi: float | None = None) -> bool:
        """Süresi dolanları kaldırır; çizimin değişmesi gerekiyorsa True."""
        simdi = self.saat() if simdi is None else simdi
        degisti = False
        y = self.yazi
        if y is not None and (simdi >= y["bitis"] or (y["sil_an"] is not None and simdi >= y["sil_an"])):
            self.yazi, self._onceki = None, None
            degisti = True
        if self._onceki is not None and simdi >= self._onceki[1]:
            self._onceki = None
            degisti = True
        for k in [k for k, e in self._ogeler.items()
                  if e["gitti"] is not None and simdi - e["gitti"] >= EKRAN_GITTI_SN]:
            del self._ogeler[k]
            degisti = True
        return degisti

    def goruntu(self, simdi: float | None = None) -> Goruntu:
        simdi = self.saat() if simdi is None else simdi
        onceki = self._onceki[0] if (self._onceki and self.yazi and simdi < self._onceki[1]
                                     and self.gorunum.get("onceki_goster", True)) else None
        ogeler = []
        if self.gorunum.get("ekran_cevir", True):
            ogeler = [{**e["oge"], "id": k} for k, e in self._ogeler.items()]
        yazi = dict(self.yazi) if self.yazi else None
        return Goruntu(yazi, onceki, ogeler, self.gorunum)


# ---------- yerleşim ----------

def satir_bol(metin: str, olc: Callable[[str], float], azami: float, en_cok: int = 2) -> list[str]:
    """En çok 2 satır, dengeli (ilk satır biraz kısa), kelime ortasından bölmeden."""
    metin = " ".join(metin.split())
    if not metin or olc(metin) <= azami or en_cok < 2:
        return [metin] if metin else []
    kelimeler = metin.split(" ")
    if len(kelimeler) < 2:
        return [metin]
    en_iyi, en_iyi_puan = None, None
    for i in range(1, len(kelimeler)):
        a, b = " ".join(kelimeler[:i]), " ".join(kelimeler[i:])
        wa, wb = olc(a), olc(b)
        tasma = max(0.0, wa - azami) + max(0.0, wb - azami)
        puan = (tasma, max(wa, wb), 0 if wa <= wb else 1)   # sığan, dengeli, ilk satır kısa
        if en_iyi_puan is None or puan < en_iyi_puan:
            en_iyi, en_iyi_puan = [a, b], puan
    return en_iyi or [metin]


def _sinirla(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def altyazi_kutusu(w: int, h: int, gorunum: dict[str, Any], metin_g: float, metin_y: float,
                   dolgu: float = 16.0) -> tuple[int, int, int, int]:
    """Altyazı kutusu (x0, y0, x1, y1). Alttaysa alt kenar, üsttteyse üst kenar sabit; kutu yönüne büyür."""
    kg = _sinirla(metin_g + 2 * dolgu, 0, w * 0.96)
    ky = metin_y + 2 * dolgu
    x0 = (w - kg) / 2
    kenar = float(gorunum.get("kenar_bosluk", 0.08)) * h
    if gorunum.get("konum", "alt") == "ust":
        y0 = kenar
    else:
        y0 = h - kenar - ky
    return int(x0), int(y0), int(x0 + kg), int(y0 + ky)


def ekran_ogesi_px(o: dict[str, Any], w: int, h: int) -> dict[str, Any]:
    """Normalize ekran öğesini piksele çevirir (ekran içinde kalır); yazı boyutu kutu yüksekliğinden."""
    def oran(k: str, vars_: float) -> float:
        v = o.get(k, vars_)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else vars_
    x, y = _sinirla(oran("x", 0), 0, 1), _sinirla(oran("y", 0), 0, 1)
    g = _sinirla(oran("g", 0.2), 0.02, 1 - x if x < 1 else 0.02)
    y2 = _sinirla(oran("y2", 0.04), 0.01, max(0.01, 1 - y))
    return {"x": int(x * w), "y": int(y * h), "g": max(20, int(g * w)), "y2": max(12, int(y2 * h)),
            "yazi_px": int(_sinirla(round(y2 * h * 0.62), 13, 40)),
            "metin": str(o.get("metin") or ""), "aciklama": str(o.get("aciklama") or ""),
            "tur": o.get("tur", "diger")}


# ---------- monitör geometrisi ----------

@dataclass
class Monitor:
    no: int
    x: int
    y: int
    g: int
    y2: int
    birincil: bool = False

    @property
    def ad(self) -> str:
        return f"Ekran {self.no} ({self.g}×{self.y2})"

    def geometri(self) -> str:
        return f"{self.g}x{self.y2}{self.x:+d}{self.y:+d}"


def mss_monitorleri(ham: list[dict[str, Any]]) -> list[Monitor]:
    """mss `monitors` listesi (0. öğe tüm ekranların birleşimi; atlanır). Numaralar yakalama ile aynı."""
    out = []
    for i, m in enumerate(ham[1:], start=1):
        try:
            out.append(Monitor(i, int(m["left"]), int(m["top"]), int(m["width"]), int(m["height"]), i == 1))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def dikdortgen_monitorleri(rects: Iterable[tuple[int, int, int, int]], birincil: int = 0) -> list[Monitor]:
    """(sol, üst, sağ, alt) dörtlüleri (EnumDisplayMonitors sırası); geçersizler atlanır."""
    out = []
    for i, r in enumerate(rects):
        try:
            l, t, rt, b = (int(v) for v in r)
        except (TypeError, ValueError):
            continue
        if rt > l and b > t:
            out.append(Monitor(len(out) + 1, l, t, rt - l, b - t, i == birincil))
    return out


def ekran_sec(monitorler: list[Monitor], no: int) -> Monitor | None:
    """İstenen numara yoksa birincil, o da yoksa ilk monitör."""
    for m in monitorler:
        if m.no == no:
            return m
    for m in monitorler:
        if m.birincil:
            return m
    return monitorler[0] if monitorler else None


# ---------- SSE ----------

def sse_olaylari(satirlar: Iterable[bytes | str]) -> Iterator[tuple[str, dict[str, Any]]]:
    """SSE satırlarından (olay adı, JSON verisi) üretir; yorum ve bozuk veri atlanır."""
    ad, veri = "message", []
    for ham in satirlar:
        satir = ham.decode("utf-8", "replace") if isinstance(ham, bytes) else ham
        satir = satir.rstrip("\r\n")
        if satir == "":
            if veri:
                try:
                    j = json.loads("\n".join(veri))
                    yield ad, j if isinstance(j, dict) else {}
                except ValueError:
                    pass
            ad, veri = "message", []
        elif satir.startswith(":"):
            continue
        elif satir.startswith("event:"):
            ad = satir[6:].strip()
        elif satir.startswith("data:"):
            veri.append(satir[5:].lstrip(" "))
