# SPDX-License-Identifier: AGPL-3.0-only
"""Ekran katmanının saf mantığı (pencere yok): zamanlama, yerleşim, monitör geometrisi, SSE ayrıştırma.

Tk burada içe aktarılmaz; böylece testler pencere açmadan çalışır.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator

GUVENLIK_SN = 15.0       # §13.4: sunucu silmeyi karar verir; bağlantı koparsa son güncellemeden bu kadar sonra kalkar
ONCEKI_SN = 2.5          # §7.2/7: önceki satır küçük ve soluk kalır
EKRAN_GITTI_SN = 0.0     # §13.2: sunucu öğeyi zaten 600 ms bekleyip listeden çıkarır; burada ek bekleme yok
BILDIRIM_SN = 1.5        # §13.1: küçük bildirim (toast) bu kadar görünür
VARSAYILAN_GORUNUM: dict[str, Any] = {
    "yazi_boyutu": 44, "konum": "alt", "kenar_bosluk": 0.08, "arka_plan": 0.55,
    "yazi_rengi": "#FFFFFF", "konusan_rengi": "#FFD166",
    "asil_goster": False, "ekran_cevir": True, "onceki_goster": True, "ekran_olcek": 1.0,
}
EKRAN_EN_AZ_PX = 11          # §12.4: sığmazsa yazı küçülür ama bundan küçük olmaz (1080p'ye göre)
EKRAN_EN_GENIS = 0.35        # §12.4: kutu en çok ekran genişliğinin %35'i kadar genişler
EKRAN_KAYNAK_CARPAN = 1.6    # §12.4: ...ve kaynak yazı genişliğinin en çok 1.6 katı kadar
EKRAN_EN_DAR = 0.12          # çok dar kaynakta ("OK" düğmesi) kutu ekranın en az %12'si kadar genişleyebilir
EKRAN_EN_COK_SATIR = 2       # §12.4
EKRAN_EN_AZ_BOYUT, EKRAN_EN_COK_BOYUT = 12.0, 22.0   # §12.4: kaynak boyu yoksa yazı boyu aralığı (1080p)



# ---------- zamanlama durum makinesi ----------

@dataclass
class Goruntu:
    yazi: dict[str, Any] | None
    onceki: str | None
    ogeler: list[dict[str, Any]]
    gorunum: dict[str, Any] = field(default_factory=dict)
    bildirim: str | None = None
    gizli: bool = False


class Zamanlayici:
    """SSE olaylarından "şu an ne çizilecek"i çıkarır (PROTOKOL 7.2, istemci tarafı)."""

    def __init__(self, saat: Callable[[], float] = time.monotonic) -> None:
        self.saat = saat
        self.gorunum: dict[str, Any] = dict(VARSAYILAN_GORUNUM)
        self.yazi: dict[str, Any] | None = None
        self._onceki: tuple[str, float] | None = None
        self._ogeler: dict[str, dict[str, Any]] = {}
        self.kapat = False
        self.gizli = False                                  # §13.1: katman-gizle / katman-goster
        self._bildirim: tuple[str, float] | None = None     # (metin, bitiş)

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
            kimlik = veri.get("id")
            if self.yazi is not None and (not kimlik or kimlik == self.yazi["id"]):
                # §13.4: silme kararı (t_git + L) sunucudadır; hemen kaldırılır. Başka id'li silme yeni yazıyı silmez.
                self.yazi["sil_an"] = simdi
            return True
        if ad == "ekran":
            return self._ekran(veri, simdi)
        if ad == "ekran-sil":
            degisti = bool(self._ogeler)
            self._ogeler.clear()   # §13.2: eski öğe tuvalde kalmasın
            return degisti
        if ad in ("katman-gizle", "katman-goster"):
            self.gizli = ad == "katman-gizle"
            return True
        if ad == "durum":
            b = veri.get("bildirim")
            if isinstance(b, str) and b.strip():
                self._bildirim = (b.strip(), simdi + BILDIRIM_SN)
                return True
            return False
        if ad == "katman-kapat":
            self.kapat = True
            return True
        return False

    def _yazi(self, v: dict[str, Any], simdi: float) -> bool:
        metin = str(v.get("metin") or "")
        if not metin.strip():
            return False
        # §13.4: süreyi sunucu yönetir (yazi-sil). Güvenlik zaman aşımı yalnız bağlantı kopması içindir;
        # `otomatik_sil: true` (deneme/öz denetim yazısı) sure_ms sonra kalkar.
        sure = v.get("sure_ms")
        if v.get("otomatik_sil") is True and isinstance(sure, (int, float)) and not isinstance(sure, bool) and sure > 0:
            bitis = simdi + sure / 1000
        else:
            bitis = simdi + GUVENLIK_SN
        y = self.yazi
        ayni = y is not None and (v.get("id") == y["id"] or v.get("devam") is True)
        if ayni:   # yerinde güncelle: zıplama, sönme yok
            y.update(metin=metin, asil=str(v.get("asil") or ""), konusan=v.get("konusan"),
                     bitis=bitis, sil_an=None)
            if v.get("id"):
                y["id"] = v["id"]
            return True
        if y is not None and self.gorunum.get("onceki_goster", True):
            self._onceki = (y["metin"], simdi + ONCEKI_SN)
        else:
            self._onceki = None
        self.yazi = {"id": v.get("id") or f"y{simdi}", "metin": metin, "asil": str(v.get("asil") or ""),
                     "konusan": v.get("konusan"), "tur": v.get("tur", "altyazi"), "ilk": simdi,
                     "bitis": bitis, "sil_an": None}
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
        if self._bildirim is not None and simdi >= self._bildirim[1]:
            self._bildirim = None
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
        bildirim = self._bildirim[0] if self._bildirim and simdi < self._bildirim[1] else None
        if self.gizli:   # §13.1: yazılar gizli (çeviri sürer); yalnız bildirim görünür
            return Goruntu(None, None, [], self.gorunum, bildirim, True)
        return Goruntu(yazi, onceki, ogeler, self.gorunum, bildirim, False)


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


def kutu_kesisir(kutu: tuple[float, float, float, float], digerleri: Iterable[tuple[float, float, float, float]]) -> bool:
    """(sol, üst, sağ, alt) `kutu`, `digerleri`nden biriyle kesişiyor mu? (§12.1: kendi panelimizin üstüne çizilmez)"""
    for l, t, r, b in digerleri:
        if kutu[0] < r and kutu[2] > l and kutu[1] < b and kutu[3] > t:
            return True
    return False


def kelime_sar(metin: str, olc: Callable[[str], float], azami: float) -> list[str]:
    """Yalnız boşluklarda satır kırar (kelime ortasından / harf harf ASLA). Azami genişlikten uzun
    tek bir kelime kendi satırında taşar; çağıran yazıyı küçültür."""
    satirlar: list[str] = []
    cur = ""
    for k in metin.split():
        deneme = f"{cur} {k}" if cur else k
        if cur and olc(deneme) > azami:
            satirlar.append(cur)
            cur = k
        else:
            cur = deneme
    if cur:
        satirlar.append(cur)
    return satirlar


def _iki_satir(metin: str, olc: Callable[[str], float], azami: float) -> list[str] | None:
    """Boşluktan iki satıra böl: ikisi de `azami`ye sığan en dengeli (en dar en geniş satırlı) bölme; yoksa None."""
    kelimeler = metin.split(" ")
    en_iyi: list[str] | None = None
    en_iyi_puan: tuple[float, int] | None = None
    for i in range(1, len(kelimeler)):
        a, b = " ".join(kelimeler[:i]), " ".join(kelimeler[i:])
        wa, wb = olc(a), olc(b)
        if wa > azami or wb > azami:
            continue
        puan = (max(wa, wb), 0 if wa >= wb else 1)   # dengeli; eşitse ilk satır uzun
        if en_iyi_puan is None or puan < en_iyi_puan:
            en_iyi, en_iyi_puan = [a, b], puan
    return en_iyi


def _satirlara(metin: str, olc: Callable[[str], float], azami: float, en_cok: int) -> list[str] | None:
    """Önce tek satır; olmazsa (en çok 2 satır ise) boşlukta iki satır; sığmazsa None."""
    if not metin:
        return []
    if olc(metin) <= azami:
        return [metin]
    if en_cok >= 2 and " " in metin:
        return _iki_satir(metin, olc, azami)
    return None


def _uca_nokta(metin: str, olc: Callable[[str], float], azami: float) -> str:
    """Metni `azami`ye sığacak kadar kısaltıp sonuna "…" koyar (önce sondaki kelimeler, tek kelimeyse harfler)."""
    if olc(metin) <= azami:
        return metin
    kelimeler = metin.split(" ")
    while len(kelimeler) > 1:
        kelimeler.pop()
        deneme = " ".join(kelimeler).rstrip(",;:.-") + "…"
        if olc(deneme) <= azami:
            return deneme
    k = kelimeler[0] if kelimeler else ""
    while len(k) > 1 and olc(k + "…") > azami:
        k = k[:-1]
    return k + "…"


def _kirp(metin: str, olc: Callable[[str], float], azami: float, en_cok: int) -> list[str]:
    """Sığmayan metin: dolu satırlar boşlukta kırılır, son satır "…" ile biter (kelime ortasından bölünmez,
    yalnız tek bir kelime satırdan uzunsa o kelime kısaltılır)."""
    kelimeler = metin.split(" ")
    satirlar: list[str] = []
    i = 0
    while len(satirlar) < en_cok - 1 and i < len(kelimeler):
        cur = kelimeler[i]
        if olc(cur) > azami:
            break
        j = i + 1
        while j < len(kelimeler) and olc(cur + " " + kelimeler[j]) <= azami:
            cur += " " + kelimeler[j]
            j += 1
        satirlar.append(cur)
        i = j
    kalan = " ".join(kelimeler[i:])
    if kalan:
        satirlar.append(_uca_nokta(kalan, olc, azami))
    return satirlar


def ekran_ogesi_yerlesim(metin: str, aciklama: str, olc: Callable[[str, int], float], boyut_px: float,
                         hedef: tuple[float, float, float, float], w: int, h: int,
                         kaynak_g: float | None = None, en_cok_satir: int = EKRAN_EN_COK_SATIR) -> dict[str, Any]:
    """Ekran öğesinin yerleşimi (saf, Tk'sız; PROTOKOL §12.4). `olc(metin, px)` yazının piksel genişliği.
    `boyut_px` 1080p'ye göre yazı boyu; `hedef` 0-1 oranlı (x, y, g, y2), sol-üst köşe kullanılır.
    Tek satıra sığmaya çalışır; genişlik metne göre, en çok min(kaynak genişliğinin 1.6 katı, ekranın %35'i)
    (kaynak_g: kaynak yazının 0-1 genişliği). Sığmazsa yalnız boşlukta, en çok 2 satıra bölünür; hâlâ
    sığmazsa yazı küçülür (en az 11 px*h/1080), o da yetmezse sona "…" konur.
    Dönen: {"x","y","g","y2","px","satirlar","aciklama_satirlar","aciklama_px","dolgu","dolgu_y","satir_y","kirpildi"}."""
    olcek = h / 1080.0
    taban_px = max(1, int(round(EKRAN_EN_AZ_PX * olcek)))
    metin = " ".join((metin or "").split())
    aciklama = " ".join((aciklama or "").split())
    azami = w * EKRAN_EN_GENIS
    if isinstance(kaynak_g, (int, float)) and not isinstance(kaynak_g, bool) and kaynak_g > 0:
        azami = min(azami, max(EKRAN_KAYNAK_CARPAN * kaynak_g * w, EKRAN_EN_DAR * w))
    p = max(taban_px, int(round(float(boyut_px) * olcek)))
    kirpildi = False
    while True:
        dolgu = max(2, int(round(p * 0.4)))
        ic = max(1.0, azami - 2 * dolgu)
        o = lambda t, p=p: olc(t, p)   # noqa: E731
        satirlar = _satirlara(metin, o, ic, en_cok_satir)
        if satirlar is not None:
            break
        if p <= taban_px:
            satirlar = _kirp(metin, o, ic, en_cok_satir)
            kirpildi = True
            break
        p = max(taban_px, int(p * 0.92) if int(p * 0.92) < p else p - 1)
    dolgu_y = max(2, int(round(p * 0.25)))
    ap = max(taban_px, int(round(p * 0.7)))
    oa = lambda t: olc(t, ap)   # noqa: E731
    asatirlar = (_satirlara(aciklama, oa, ic, en_cok_satir) or _kirp(aciklama, oa, ic, en_cok_satir)) if aciklama else []
    govde_g = max([o(s) for s in satirlar] + [oa(s) for s in asatirlar] + [1.0])
    kg = govde_g + 2 * dolgu
    satir_y = p * 1.25
    kh = len(satirlar) * satir_y + len(asatirlar) * ap * 1.25 + 2 * dolgu_y
    x = _sinirla(float(hedef[0]), 0, 1) * w
    y = _sinirla(float(hedef[1]), 0, 1) * h
    x = max(0.0, min(x, w - kg))        # ekran dışına taşmaz
    y = max(0.0, min(y, h - kh))
    return {"x": int(x), "y": int(y), "g": int(kg + 0.999), "y2": int(kh + 0.999), "px": p,
            "satirlar": satirlar, "aciklama_satirlar": asatirlar, "aciklama_px": ap, "dolgu": dolgu,
            "dolgu_y": dolgu_y, "satir_y": satir_y, "kirpildi": kirpildi}


def ekran_ogesi_hazirla(o: dict[str, Any]) -> dict[str, Any]:
    """Ekran öğesini çizime hazırlar. Konum: `hedef` kutusu varsa orası, yoksa kaynak kutusu (0-1 oran).
    Yazı boyu: `boyut_px` (1080p'ye göre; sunucu hesaplar) ya da yoksa kutu yüksekliğinden."""
    def sayi(d: dict[str, Any], k: str, vars_: float) -> float:
        v = d.get(k, vars_)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else vars_
    hd = o["hedef"] if isinstance(o.get("hedef"), dict) else o
    x, y = _sinirla(sayi(hd, "x", 0), 0, 1), _sinirla(sayi(hd, "y", 0), 0, 1)
    y2 = _sinirla(sayi(o, "y2", 0.04), 0.01, 1.0)
    bp = o.get("boyut_px")
    if isinstance(bp, (int, float)) and not isinstance(bp, bool) and bp > 0:
        boyut = float(bp)
    else:
        boyut = _sinirla(round(y2 * 1080 * 0.75), EKRAN_EN_AZ_BOYUT, EKRAN_EN_COK_BOYUT)
    kg = sayi(o, "g", 0.0)
    if isinstance(o.get("hedef"), dict):
        kg = max(kg, sayi(o["hedef"], "g", 0.0))
    return {"x": x, "y": y, "boyut_px": boyut, "kaynak_g": kg, "metin": str(o.get("metin") or ""),
            "aciklama": str(o.get("aciklama") or ""), "tur": o.get("tur", "diger")}


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


# ---------- pencereye konumlanma ----------

def pencere_monitoru(kutu: dict[str, int] | None, no: int = 1) -> Monitor | None:
    """Pencerenin iç dikdörtgeninden (ekran koordinatlı) katman geometrisi; yoksa None."""
    if not kutu:
        return None
    try:
        g, y = int(kutu["width"]), int(kutu["height"])
        if g < 2 or y < 2:
            return None
        return Monitor(no, int(kutu["left"]), int(kutu["top"]), g, y, False)
    except (KeyError, TypeError, ValueError):
        return None


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
