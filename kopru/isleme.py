# SPDX-License-Identifier: AGPL-3.0-only
"""Ana boru hattı: kare al -> değişim? -> OCR -> kararlılaştır -> çevir -> yayınla.

Akıcı gösterim kuralları docs/PROTOKOL.md 7.2'dedir; hepsi burada, saat dışarıdan verilebilir
(`saat`) olduğu için sahte saatle sınanır.
"""
from __future__ import annotations

import asyncio
import logging
import re
import statistics
import time
from collections import deque
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher
from typing import Any, Callable

from . import dugmeler
from .ayarlar import bolgeleri_temizle
from .ceviri.temel import AgHatasi, AnahtarHatasi, ErisimSiniri, MotorHatasi
from .onbellek import normallestir
from .okuma import Satir
from .sira import KARAKTER_MS_VARSAYILAN, GosterimSirasi, SiraSatiri
from .yakalama import YakalamaHatasi

log = logging.getLogger("kopru.isleme")

ARALIK_SN = 0.25
SPEK_BEKLEME_SN = 0.05  # §16.4: ilk görüldüğü karede çevrilmeye başlar; 50 ms içinde değişen (daktilo) metne istek atılmaz
HATA_TEKRAR_SN = 1.0    # çevirisi başarısız olan aynı satır en erken bu kadar sonra yeniden denenir
DEGISIM_ESIGI = 0.5  # küçültülmüş gri karelerde ortalama mutlak fark (0-255); §13.2: neredeyse her değişim yeniden okutur
HUCRE_ESIGI = 32     # ...ya da tek bir hücredeki fark bu kadarsa (küçük bir yazı gitti/geldi)
YENIDEN_OKU_SN = 1.0   # §13.2: kare değişmemiş görünse de en geç bu sıklıkta yeniden okunur (yazının gittiği anlaşılsın)
EN_AZ_GOSTERIM_MS = 1800   # eski kural; yalnız `sure_ms` (istemciye bilgi) için kalır
EN_AZ_MS_VARSAYILAN = 800  # §13.4: en az gösterim süresi (gorunum.en_az_ms)
KAYIP_KARE = 3             # 7.2/2: bu kadar kare üst üste görünmezse "gitti"
EKRAN_KAYIP_KARE = 2       # §13.2: ekran öğesi bu kadar kare üst üste görünmezse "gitti"
YENI_BEKLE_SN = 2.0        # §13.4: yeni cümlenin çevirisi gecikirse eskisi en çok bu kadar daha bekler (boşluk olmasın)
EN_KUCUK_OCR_YUKSEKLIK = 48  # daha küçük bölge okumadan önce büyütülür
EN_COK_ALTYAZI_KARAKTER = 600   # bundan uzun "altyazı" okuma gürültüsüdür; bütçeyi yakmasın
EN_COK_OGE_KARAKTER = 300
EN_COK_OGE = 24               # bir karede çevrilecek en çok ekran öğesi
HATA_LOG_SN = 60.0            # aynı hata günlüğe en çok dakikada bir
GERI_BESLEME_SN = 60.0         # §11.1: son 60 sn'de yayınlanan çevirilere benzeyen okumalar atılır
GERI_BESLEME_ESIK = 0.80
ALT_BANT_Y = 0.70              # §11.3: otomatik kipte altyazı yalnız alt-orta bandından
ALT_BANT_X = (0.2, 0.8)
BOYUT_MIN_PX, BOYUT_MAX_PX = 12.0, 22.0   # §12.4: 1080p'de ekran öğesi yazı boyu
BOYUT_ORANI = 0.75                        # §12.4: kaynak satır yüksekliğinin 0.75'i
_KELIME = re.compile(r"\w+", re.UNICODE)
_KONUSMA_TEKRARI = re.compile(r"\b(\w+), (\1)\b", re.UNICODE | re.IGNORECASE)
_KONUSAN = re.compile(r"^([A-ZÇĞİÖŞÜ][\w'. -]{0,24}):\s+(\S.*)$", re.UNICODE)


def en_az_ms_ayari(ayar: dict[str, Any]) -> int:
    """§13.4: gorunum.en_az_ms (0-3000, varsayılan 800); geçersizse varsayılan."""
    v = (ayar.get("gorunum") or {}).get("en_az_ms", EN_AZ_MS_VARSAYILAN)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 3000:
        return EN_AZ_MS_VARSAYILAN
    return int(v)


def karakter_ms_ayari(ayar: dict[str, Any]) -> int:
    """§16.4 gorunum.karakter_ms (40-120, varsayılan 60): okuma tabanının karakter başına süresi."""
    v = (ayar.get("gorunum") or {}).get("karakter_ms", KARAKTER_MS_VARSAYILAN)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not 40 <= v <= 120:
        return KARAKTER_MS_VARSAYILAN
    return int(v)


def okuma_suresi_ms(metin: str) -> int:
    return min(9000, 800 + len(metin) * 55)


def sure_ms(metin: str) -> int:
    """Altyazının en az ekranda kalma süresi: max(1800, okuma süresi)."""
    return max(EN_AZ_GOSTERIM_MS, okuma_suresi_ms(metin))


def _kelimeler(metin: str) -> list[str]:
    return _KELIME.findall(metin.casefold())


def tekrar_var_mi(metin: str) -> bool:
    """Aynı kelime üst üste 3 kez ("tek tek tek", "Parti: Parti: Parti:") ya da bütün kelimeler aynı.
    Virgülle ayrılıp ünlemle/noktayla biten tekrar gerçek konuşmadır ("Move, move, move!", "Go, go, go!")."""
    if _KONUSMA_TEKRARI.search(metin) and metin.rstrip()[-1:] in "!?.…":
        return False
    k = _kelimeler(metin)
    if len(k) >= 2 and len(set(k)) == 1:
        return True
    return any(k[i] == k[i + 1] == k[i + 2] for i in range(len(k) - 2))


def okuma_gurultusu_mu(metin: str) -> bool:
    """§11.3 + §16.3: çevrilmeyecek okuma: emoji/simgeler atıldıktan sonra <2 harf, çoğu rakam/simge (HUD
    sayıları), yalnız sayı/süre/koordinat, yalnız düğme simgeleri ya da tekrarlı kelime."""
    m = dugmeler.temizle(metin)
    if len("".join(m.split())) <= 1:
        return True
    return dugmeler.gurultu_mu(m) or tekrar_var_mi(m)


def altyazi_bandinda(s: Satir) -> bool:
    """Satırın merkezi ekranın alt-orta bandında mı (y>0.70, x 0.2-0.8)?"""
    cx, cy = s.x + s.g / 2, s.y + s.y2 / 2
    return cy > ALT_BANT_Y and ALT_BANT_X[0] <= cx <= ALT_BANT_X[1]


def _bitisik(a: Satir, b: Satir) -> bool:
    """Alt alta (aralık < satır yüksekliği) ve yatayda örtüşen iki satır."""
    ust, alt = (a, b) if a.y <= b.y else (b, a)
    bosluk = alt.y - (ust.y + ust.y2)
    yatay = min(a.x + a.g, b.x + b.g) - max(a.x, b.x)
    return bosluk < 0.9 * max(a.y2, b.y2) and yatay > 0


def altyazi_sec(satirlar: list[Satir]) -> list[Satir]:
    """Birbirine bitişik satırları kümeler (§11.3); en çok yazısı olan (eşitse en alttaki) küme altyazıdır."""
    kumeler: list[list[Satir]] = []
    for s in sorted(satirlar, key=lambda s: (s.y, s.x)):
        hedef = [k for k in kumeler if any(_bitisik(s, o) for o in k)]
        yeni = [s]
        for k in hedef:
            yeni += k
            kumeler.remove(k)
        kumeler.append(yeni)
    if not kumeler:
        return []
    en = max(kumeler, key=lambda k: (sum(len(x.metin) for x in k), max(x.y for x in k)))
    return sorted(en, key=lambda s: (round(s.y, 2), s.x))


def ogenin_ekran_kutusu(metin: str, boyut_px: float, hedef: tuple[float, float, float, float]
                        ) -> tuple[float, float, float, float]:
    """Ekran öğesinin katmanda kaplayacağı alanın kaba tahmini (0-1): hedefin sol-üstünden, metne göre
    genişleyen (en çok %35, en çok 2 satır, §12.4) kutu. Maske için; gerçek çizim katmandadır."""
    doğal = max(1.0, len(metin) * boyut_px * 0.55 + 2 * 0.4 * boyut_px) / 1920
    g = min(0.35, doğal)
    satir = min(2, max(1, int(-(-doğal // 0.35))))
    y2 = (satir * boyut_px * 1.25 + 0.5 * boyut_px) / 1080
    x, y = hedef[0], hedef[1]
    return (x, y, min(g, 1 - x), min(y2, 1 - y))


def yazinin_ekran_kutusu(metin: str, gorunum: dict[str, Any]) -> tuple[float, float, float, float]:
    """Altyazı kutusunun kaba tahmini (0-1): yatay ortalı, alttan (ya da üstten) sabit, önceki satır payıyla."""
    boyut = float(gorunum.get("yazi_boyutu", 44) or 44)
    doğal = len(metin) * boyut * 0.55 / 1920 + 0.04
    g = min(0.96, doğal)
    satir = 1 if doğal <= 0.86 else 2
    y2 = (satir * boyut * 1.34 + 0.8 * boyut + boyut * 0.6) / 1080 + 0.02   # + önceki satır + dolgu
    kenar = float(gorunum.get("kenar_bosluk", 0.08) or 0.08)
    y = kenar if gorunum.get("konum") == "ust" else 1 - kenar - y2
    return ((1 - g) / 2, max(0.0, y), g, min(y2, 1.0))


def konusan_ayir(metin: str) -> tuple[str | None, str]:
    m = _KONUSAN.match(metin)
    return (m.group(1), m.group(2)) if m else (None, metin)


def devam_mi(eski: str, yeni: str) -> bool:
    """Yeni (normalize) metin eskisinin devamı mı? (daktilo, ekleme, küçük OCR farkı)"""
    if not eski or not yeni:
        return False
    if yeni.startswith(eski):
        return True
    if len(eski) >= 8 and eski in yeni and len(eski) * 5 >= len(yeni) * 2:
        return True
    return SequenceMatcher(None, eski, yeni).ratio() >= 0.88


def ceviri_benzer(a: str, b: str) -> bool:
    """İki çeviri aynı ya da neredeyse aynı mı (kaynak OCR'ı oynasa da çeviri sabit kalır)."""
    a, b = normallestir(a), normallestir(b)
    return bool(a) and (a == b or SequenceMatcher(None, a, b).ratio() >= 0.92)


def _sessiz(gorev: "asyncio.Task") -> None:
    """Atılan önden çevirinin hatası "hiç okunmadı" uyarısı vermesin."""
    if not gorev.cancelled():
        gorev.exception()


def parmak_izi(resim: Any) -> bytes:
    """Hızlı değişim algısı için 32x18 gri küçük kare."""
    return resim.convert("L").resize((32, 18)).tobytes()


def fark(a: bytes, b: bytes) -> float:
    if len(a) != len(b):
        return 255.0
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def degisti_mi(a: bytes, b: bytes) -> bool:
    """§13.2: kare değişti mi? Ortalama fark küçük olsa bile tek hücre belirgin değiştiyse (küçük yazı gitti) evet."""
    if len(a) != len(b):
        return True
    toplam, en_cok = 0, 0
    for x, y in zip(a, b):
        d = x - y if x > y else y - x
        toplam += d
        if d > en_cok:
            en_cok = d
    return toplam / len(a) > DEGISIM_ESIGI or en_cok >= HUCRE_ESIGI


def bolgede_mi(s: Satir, b: dict[str, float]) -> bool:
    cx, cy = s.x + s.g / 2, s.y + s.y2 / 2
    return b["x"] <= cx <= b["x"] + b["g"] and b["y"] <= cy <= b["y"] + b["y2"]


def ocr_hazirla(kes: Any) -> Any:
    """§11/6: küçük kesiti (<60 px yüksek) en az ×2 büyütür (stilize yazı tiplerini okumak kolaylaşır),
    gri tona çevirip kontrastı açar. Boyut değişir ama okuyucu normalize koordinat döndürür."""
    from PIL import Image, ImageOps
    if kes.size[1] < 60:
        kat = min(4.0, max(2.0, EN_KUCUK_OCR_YUKSEKLIK / kes.size[1]))
        kes = kes.resize((max(1, int(kes.size[0] * kat)), max(1, int(kes.size[1] * kat))), Image.LANCZOS)
    try:
        return ImageOps.autocontrast(kes.convert("L")).convert("RGB")
    except Exception:   # noqa: BLE001 — kontrast uygulanamazsa ham kesit
        return kes


def kirp(resim: Any, b: dict[str, Any]) -> tuple[Any, tuple[float, float, float, float]]:
    """Kareyi bölgeye göre keser. Dönen kutu, gerçekten kesilen pikselin 0-1 karşılığıdır."""
    w, h = resim.size
    x0 = min(max(int(round(b["x"] * w)), 0), w - 1)
    y0 = min(max(int(round(b["y"] * h)), 0), h - 1)
    x1 = max(x0 + 1, min(w, int(round((b["x"] + b["g"]) * w))))
    y1 = max(y0 + 1, min(h, int(round((b["y"] + b["y2"]) * h))))
    kes = ocr_hazirla(resim.crop((x0, y0, x1, y1)))
    return kes, (x0 / w, y0 / h, (x1 - x0) / w, (y1 - y0) / h)


def tam_kareye(satirlar: list[Satir], kutu: tuple[float, float, float, float]) -> list[Satir]:
    """Bölge içindeki 0-1 koordinatları tam karenin 0-1 koordinatlarına çevirir."""
    bx, by, bg, bh = kutu
    return [Satir(s.metin, bx + s.x * bg, by + s.y * bh, s.g * bg, s.y2 * bh, s.satir,
                  tuple((m, bx + x * bg, by + y * bh, g * bg, y2 * bh) for m, x, y, g, y2 in s.kelimeler))
            for s in satirlar]


def birlestir(satirlar: list[Satir]) -> list[Satir]:
    """Yakın satırları (alt alta, aynı hizada) tek öğede toplar."""
    sirali = sorted(satirlar, key=lambda s: (s.y, s.x))
    gruplar: list[list[Satir]] = []
    for s in sirali:
        for g in gruplar:
            son = g[-1]
            if 0 <= s.y - (son.y + son.y2) < son.y2 * 0.8 and abs(s.x - son.x) < 0.05 \
                    and abs(s.y2 - son.y2) < son.y2 * 0.5:
                g.append(s)
                break
        else:
            gruplar.append([s])
    out: list[Satir] = []
    for g in gruplar:
        x1 = min(s.x for s in g)
        y1 = min(s.y for s in g)
        x2 = max(s.x + s.g for s in g)
        y2 = max(s.y + s.y2 for s in g)
        out.append(Satir(" ".join(s.metin for s in g), x1, y1, x2 - x1, y2 - y1, sum(s.satir for s in g),
                         tuple(k for s in g for k in s.kelimeler)))
    return out


def satir_temizle(s: Satir) -> Satir | None:
    """§16.3: emoji/simgeleri siler, düğme belirteçlerini normalize eder; çevrilmeyecek satırda None.
    Kelime kutuları da temizlenir (boş kalan kelime atılır)."""
    if okuma_gurultusu_mu(s.metin):
        return None
    metin = dugmeler.temizle(s.metin)
    kel = tuple((m2, x, y, g, y2) for m, x, y, g, y2 in s.kelimeler for m2 in [dugmeler.temizle(m)] if m2)
    if metin == s.metin and kel == s.kelimeler:
        return s
    return replace(s, metin=metin, kelimeler=kel)


ORTU_DOLGU = 0.15          # §16.1: örtü kutusu her yöne yazı yüksekliğinin bu kadarı genişler
ORTU_ZEMIN_YEDEK = "#0B0F18"
ORTU_OPAKLIK = 0.94


def _renk(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, int(c))) for c in rgb))


def parlaklik(renk: str) -> float:
    r, g, b = (int(renk[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def zemin_ornekle(resim: Any, kutu: tuple[float, float, float, float], kalinlik: float) -> str:
    """Kutunun hemen dışındaki şeridin (üst/alt/sol/sağ) piksel ortancası: oyunun kendi arka planı (§16.1)."""
    if resim is None:
        return ORTU_ZEMIN_YEDEK
    W, H = resim.size
    x, y, g, y2 = kutu
    k = max(2, int(round(kalinlik * H)))
    x0, y0 = max(0, int(x * W)), max(0, int(y * H))
    x1, y1 = min(W, int((x + g) * W) + 1), min(H, int((y + y2) * H) + 1)
    seritler = [(x0, max(0, y0 - k), x1, y0), (x0, y1, x1, min(H, y1 + k)),
                (max(0, x0 - k), y0, x0, y1), (x1, y0, min(W, x1 + k), y1)]
    pikseller: list[tuple[int, int, int]] = []
    for a, b, c, d in seritler:
        if c - a < 1 or d - b < 1:
            continue
        p = resim.crop((a, b, c, d)).convert("RGB")
        p = p.resize((max(1, min(64, p.size[0])), max(1, min(8, p.size[1]))))
        ham = p.tobytes()
        pikseller.extend(tuple(ham[i:i + 3]) for i in range(0, len(ham) - 2, 3))
    if not pikseller:
        return ORTU_ZEMIN_YEDEK
    return _renk(tuple(sorted(c[i] for c in pikseller)[len(pikseller) // 2] for i in range(3)))


def ortu_kutusu(satirlar: list[Satir], resim: Any) -> dict[str, Any]:
    """§16.1/16.2: kaynak yazının örtü kutusu (0-1, dolgulu) + zemin rengi + örtü dışında kalan uç düğmeler."""
    x = min(s.x for s in satirlar)
    y = min(s.y for s in satirlar)
    x2 = max(s.x + s.g for s in satirlar)
    y2 = max(s.y + s.y2 for s in satirlar)
    satir = max(1, sum(max(1, s.satir) for s in satirlar))
    h = (y2 - y) / satir
    oran = (resim.size[1] / resim.size[0]) if resim is not None and resim.size[0] else 9 / 16
    dy = max(0.002, h * ORTU_DOLGU)
    dx = dy * oran
    sol, sag = x - dx, x2 + dx
    bas = son = None
    if len(satirlar) == 1 and satirlar[0].kelimeler and len(satirlar[0].kelimeler) > 1:
        k = satirlar[0].kelimeler
        b0, b1 = dugmeler.belirtec(k[0][0]), dugmeler.belirtec(k[-1][0])
        if b0:   # baştaki gerçek simge görünür kalsın: örtü onun sağından başlar
            bas, sol = b0, k[0][1] + k[0][3] + dx * 0.5
        if b1:
            son, sag = b1, k[-1][1] - dx * 0.5
        if sag - sol < 0.01:
            bas = son = None
            sol, sag = x - dx, x2 + dx
    kutu = (max(0.0, sol), max(0.0, y - dy), min(1.0, sag) - max(0.0, sol), min(1.0, y2 + dy) - max(0.0, y - dy))
    zemin = zemin_ornekle(resim, kutu, h * 0.3)
    return {"x": round(kutu[0], 4), "y": round(kutu[1], 4), "g": round(kutu[2], 4), "y2": round(kutu[3], 4),
            "zemin": zemin, "satir": satir, "bas": bas, "son": son}


def ortu_olaya(k: dict[str, Any], metin: str, gorunum: dict[str, Any]) -> dict[str, Any]:
    """Olaya giden `ortu` (§16.1): yazı rengi zemine göre, uçtaki düğme metinden çıkarılmış."""
    zemin = k.get("zemin") or ORTU_ZEMIN_YEDEK
    renk = "#111111" if parlaklik(zemin) > 0.55 else str(gorunum.get("yazi_rengi") or "#FFFFFF")
    return {"x": k["x"], "y": k["y"], "g": k["g"], "y2": k["y2"], "zemin": zemin, "renk": renk,
            "opaklik": ORTU_OPAKLIK, "satir": k.get("satir", 1),
            "metin": dugmeler.uctan_cikar(metin, k.get("bas"), k.get("son"))}


def boyut_hesapla(o: Satir, olcek: float, genel: float) -> float:
    """§12.4: kaynak yazının satır yüksekliğinin (1080p) 0.75'i, 12-22 px'e sıkıştırılır; sonra bölge ve genel
    ölçekle çarpılır."""
    satir_h = o.y2 * 1080 / max(1, o.satir)
    taban = max(BOYUT_MIN_PX, min(BOYUT_MAX_PX, satir_h * BOYUT_ORANI))
    return round(taban * olcek * genel, 1)


def tur_bul(o: Satir) -> str:
    n = len(o.metin)
    if o.x < 0.4 and o.y < 0.25 and n >= 25:
        return "gorev"
    if abs((o.x + o.g / 2) - 0.5) < 0.2 and n <= 24:
        return "menu"
    if n >= 40:
        return "bilgi"
    if n <= 24:
        return "menu"
    return "diger"


def _yakin(a: Satir | Any, b: Satir | Any, esik: float = 0.03) -> bool:
    return abs(a.x - b.x) < esik and abs(a.y - b.y) < esik


def _ortusme(a: Any, b: Any) -> float:
    """Kesişim alanı / küçük olanın alanı."""
    gx = min(a.x + a.g, b.x + b.g) - max(a.x, b.x)
    gy = min(a.y + a.y2, b.y + b.y2) - max(a.y, b.y)
    if gx <= 0 or gy <= 0:
        return 0.0
    return gx * gy / max(1e-9, min(a.g * a.y2, b.g * b.y2))


@dataclass
class _K:
    """Kutu (örtüşme hesabı için)."""
    x: float
    y: float
    g: float
    y2: float


def _altyazi_bolgesi(b: dict[str, Any]) -> bool:
    """§11.4: altyazı türündeki bölge ya da hedefi "altyazi" olan bölge `yazi` olayına gider."""
    return b.get("tur") == "altyazi" or b.get("hedef") == "altyazi"


def _hedef_kutusu(o: Satir, hedef: Any) -> tuple[float, float, float, float]:
    """Çizim kutusu: özel hedef varsa o, yoksa kaynağın kendi kutusu ("ustune")."""
    if hedef is not None:
        return (float(hedef[0]), float(hedef[1]), float(hedef[2]), float(hedef[3]))
    return (o.x, o.y, o.g, o.y2)


def tam_ekran_mi(ayar: dict[str, Any]) -> bool:
    """`kaynak` bütün bir ekran mı ("ekran:N")? Orada kendi panelimiz de görünür: bölgesiz yalnız altyazı bandı okunur."""
    return str(ayar.get("kaynak") or "").startswith("ekran:")


def _genel_olcek(ayar: dict[str, Any]) -> float:
    v = (ayar.get("gorunum") or {}).get("ekran_olcek", 1.0)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and 0.6 <= v <= 2.0 else 1.0


@dataclass
class _Oge:
    """Ekranda gösterilen bir yazı öğesi."""
    id: str
    norm: str
    asil: str
    x: float
    y: float
    g: float
    y2: float
    tur: str
    metin: str
    aciklama: str | None = None
    kayip: int = 0
    gel: float = 0.0            # ilk görülme (kare anı)
    hazir: float = 0.0          # listeye girdiği an
    ilk_kayip: float | None = None   # ilk kez görünmediği kare anı (t_git)
    sil_an: float | None = None      # §13.4: t_git + L (en az gösterim dahil); None = ekranda
    hedef: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)   # çizileceği kutu (0-1)
    ozel: bool = False          # kullanıcının çizdiği hedef (kaynağın üstü değil)
    boyut_px: float = 14.0
    ortu: dict[str, Any] | None = None   # §16.1: kaynağın üstüne çizilirken örtü kutusu ve zemin


@dataclass
class _Okuma:
    """Bir kare okumasının sonucu: (bölge sırası, bölge türü, satır). Otomatik kipte tür None."""
    satirlar: list[tuple[int, str | None, Satir]] = field(default_factory=list)


class Isleme:
    def __init__(self, kare_kaynagi: Callable[[], Any], okuyucu: Any, yonetici: Any,
                 yayin: Any, ayar_getir: Callable[[], dict[str, Any]],
                 saat: Callable[[], float] = time.monotonic) -> None:
        self.kare_kaynagi = kare_kaynagi
        self.okuyucu = okuyucu
        self.yonetici = yonetici
        self.yayin = yayin
        self.ayar = ayar_getir
        self.saat = saat
        self._izi: bytes | None = None
        self._son_ocr = -1e9    # son gerçek okumanın zamanı (§13.2: en geç YENIDEN_OKU_SN'de bir)
        self._bolge_anahtari: tuple = ()
        self._okuma = _Okuma()
        self._sira = GosterimSirasi(EN_AZ_MS_VARSAYILAN / 1000)   # §16.4 altyazı kuyruğu
        self._aday_onceki = ""      # önceki karedeki altyazı adayı (normalize)
        self._kayip = 0             # kaynağı açık satırın üst üste görünmeyen kare sayısı
        self._ilk_kayip: float | None = None
        self._son_satirlar: list[Satir] = []   # son okunan altyazı satırları (örtü kutusu için)
        self._son_resim: Any = None
        self._altyazi_cubuk = False   # bu karedeki altyazı yalnız "çubuğa yaz" bölgelerinden mi (örtü yok)
        self._gorevler: set[asyncio.Task] = set()   # süren altyazı çevirileri (paralel, §16.4)
        self._ekran_gorevi: asyncio.Task | None = None
        self._olcumler: deque[dict[str, float]] = deque(maxlen=20)
        self._olcum_kare = {"kare_ms": 0.0, "okuma_ms": 0.0}
        self._basarisiz = 0
        self._hatali: tuple[str, float] | None = None   # son çevrilemeyen satır (normalize, an)
        self._ogeler: list[_Oge] = []
        self._oge_adaylari: list[tuple[str, Satir, float]] = []   # önceki karede görülen yeni öğeler
        self._sayac = {"a": 0, "e": 0, "o": 0}
        self.durum_hatasi: str | None = None
        self._spek: asyncio.Task | None = None   # önden başlatılmış çeviri (6.4)
        self._spek_aday = ""
        self._spek_gitti = False
        self._son_hata_logu = -1e9
        self._adim_hatali = False
        self._ceviriler: deque[tuple[float, str]] = deque(maxlen=200)   # (an, normalize çeviri): geri besleme süzgeci
        self._son_kutu: tuple[float, float, float, float] | None = None
        self._en_az_ms = EN_AZ_MS_VARSAYILAN
        self._ag_norm = ""          # §13.4: şu an görülen kaynak metin ve ilk görüldüğü kare anı (t_gel)
        self._ag_t = 0.0
        self._ag_kayip = 0
        self._gercek_saat = saat is time.monotonic   # gerçek saatte call_later ile uyandırılır; sahte saatte dışarıdan
        self._uyanis: asyncio.TimerHandle | None = None
        self._gorunum: dict[str, Any] = {}

    def yeniden_oku(self) -> None:
        """§13.1 yeniden_oku: bekleyen/ekrandaki yazıları siler, hemen yeni kare okutur."""
        self._spek_iptal()
        self._gorevleri_iptal()
        self._sira.temizle()
        self._aday_onceki, self._kayip, self._ilk_kayip = "", 0, None
        self._ogeler = []
        self._oge_adaylari = []
        self._ag_norm, self._ag_kayip = "", 0
        if self._uyanis is not None:
            self._uyanis.cancel()
            self._uyanis = None
        self._izi = None
        self._okuma = _Okuma()
        self.yayin.yayinla("yazi-sil", {})
        self.yayin.yayinla("ekran-sil", {})

    def _gorevleri_iptal(self) -> None:
        for g in list(self._gorevler):
            g.cancel()
        self._gorevler.clear()
        if self._ekran_gorevi is not None and not self._ekran_gorevi.done():
            self._ekran_gorevi.cancel()
        self._ekran_gorevi = None

    # -- önden (speculative) çeviri --
    def _spek_iptal(self) -> None:
        if self._spek is not None:
            self._spek.cancel()
            self._spek = None
        self._spek_aday = ""

    def _spek_basla(self, govde: str, aday: str, ayar: dict[str, Any]) -> None:
        self._spek_iptal()
        self._spek_aday = aday
        self._spek_gitti = False
        self._spek = asyncio.get_running_loop().create_task(
            self._spek_cevir(govde, ayar["kaynak_dil"], ayar["hedef_dil"]))
        self._spek.add_done_callback(_sessiz)

    async def _spek_cevir(self, govde: str, kaynak: str, hedef: str) -> Any:
        if SPEK_BEKLEME_SN > 0:
            await asyncio.sleep(SPEK_BEKLEME_SN)
        self._spek_gitti = True   # istek yola çıktı (kesinleşince beklenir; çıkmadıysa hemen yenisi atılır)
        (c,) = await self.yonetici.cevir([govde], kaynak, hedef)
        return c

    def duzeltildi(self, asil: str, ceviri: str) -> None:
        """Kullanıcı ekrandaki satırı düzeltti: canlı tutma yenilemesi de yeni metni yollasın."""
        s = self._sira.gosterilen
        if s is not None and normallestir(s.ek.get("govde", "")) == normallestir(asil):
            s.metin = ceviri
        self._ceviri_kaydet(asil, ceviri)

    # -- geri besleme süzgeci (§11.1) --
    def _ceviri_kaydet(self, asil: str, ceviri: str) -> None:
        """Yayınlanan çeviriyi son 60 sn'lik listeye ekler. Kaynağa zaten benzeyen çeviriler (özel isimler,
        "Vice City") eklenmez: yoksa oyunun kendi yazısı "kendi çevirimiz" sanılıp atılırdı."""
        n, a = normallestir(ceviri), normallestir(asil)
        if len(n) >= 2 and SequenceMatcher(None, n, a).ratio() < GERI_BESLEME_ESIK:
            self._ceviriler.append((self.saat(), n))

    def geri_besleme_mi(self, metin: str) -> bool:
        """Okunan satır, son 60 sn'de yayınladığımız bir çeviriye ≥%80 benziyor mu (kendi katmanımızı okuduk)?"""
        simdi = self.saat()
        while self._ceviriler and simdi - self._ceviriler[0][0] > GERI_BESLEME_SN:
            self._ceviriler.popleft()
        n = normallestir(metin)
        if not n:
            return False
        for _, c in self._ceviriler:
            if SequenceMatcher(None, n, c).ratio() >= GERI_BESLEME_ESIK:
                return True
            if len(n) >= 8 and n in c:                      # kutunun bir satırı: çevirinin parçası
                return True
            if len(c) >= 8 and c in n and len(c) * 2 >= len(n):   # çeviri + başka bir şey birlikte okunmuş
                return True
        return False

    def _suz(self, satirlar: list[tuple[int, str | None, Satir]]) -> list[tuple[int, str | None, Satir]]:
        """Emoji/simge gürültüsünü siler (§16.3), gürültü (§11.3) ve kendi çevirimiz (§11.1) olan satırları atar."""
        out = []
        for i, t, s in satirlar:
            temiz = satir_temizle(s)
            if temiz is not None and not self.geri_besleme_mi(temiz.metin):
                out.append((i, t, temiz))
        return out

    # -- katman maskesi (§11.1: WDA_EXCLUDEFROMCAPTURE yoksa yedek) --
    def maske_kutulari(self, ayar: dict[str, Any]) -> list[tuple[float, float, float, float]]:
        """Katmanın YALNIZ kendi çizdiği, kaynak yazıyla çakışmayan alanlar (0-1). Kaynağın üstüne çizilen
        kutular maskelenmez (oyunun kendi yazısı da kaybolurdu); onları metin süzgeci yakalar."""
        if ayar.get("gosterim") != "bilgisayar":
            return []
        kaynak = str(ayar.get("kaynak") or "")
        try:
            ayni = kaynak.startswith("pencere:") or kaynak == f"ekran:{int(ayar.get('katman_ekran', 1))}"
        except (TypeError, ValueError):
            ayni = False
        if not ayni:
            return []
        out: list[tuple[float, float, float, float]] = []
        a = self._sira.gosterilen
        ortulu = a is not None and a.ek.get("ortu") and (ayar.get("gorunum") or {}).get("yerlesim", "ustune") == "ustune"
        if a is not None and a.metin and not ortulu:   # örtü kaynağın üstündedir: maskelenmez (§16.1)
            kutu = yazinin_ekran_kutusu(a.metin, ayar.get("gorunum") or {})
            k = a.ek.get("kutu")
            if k is None or _ortusme(_K(*kutu), _K(*k)) < 0.1:
                out.append(kutu)
        for e in self._ogeler:
            if e.ozel:
                kutu = ogenin_ekran_kutusu(e.metin, e.boyut_px, e.hedef)
                if _ortusme(_K(*kutu), _K(e.x, e.y, e.g, e.y2)) < 0.1:
                    out.append(kutu)
        return out

    # -- yardımcılar --
    def _yeni_id(self, on: str) -> str:
        self._sayac[on] += 1
        return f"{on}{self._sayac[on]}"

    def _yedek_ek(self) -> dict[str, Any]:
        f = getattr(self.yonetici, "durum_ek", None)
        return f() if callable(f) else {}

    def _hata(self, e: Exception) -> None:
        if isinstance(e, ErisimSiniri):   # hata değil: sakin bir "ücretsiz süre doldu" bilgisi
            if self.durum_hatasi != "sinir":
                self.durum_hatasi = "sinir"
                self.yayin.yayinla("durum", {"calisiyor": True, "motor": self.yonetici.birincil.ad,
                                             "yedek": bool(self.yonetici.yedekte),
                                         **self._yedek_ek(), "sinir": True})
            return
        kod = {AnahtarHatasi: "anahtar", AgHatasi: "ag", MotorHatasi: "motor"}.get(type(e), "genel")
        if kod != self.durum_hatasi:
            self.durum_hatasi = kod
            log.warning("Çeviri hatası: %s", type(e).__name__)
            self.yayin.yayinla("durum", {"calisiyor": True, "motor": self.yonetici.birincil.ad,
                                         "yedek": bool(self.yonetici.yedekte),
                                         **self._yedek_ek(), "hata": kod})

    # -- okuma (otomatik ya da seçili bölgeler) --
    def _oku(self, resim: Any, parcalar: list[tuple[int, dict, Any, tuple]]) -> _Okuma:
        o = _Okuma()
        if not parcalar:
            for s in self.okuyucu.oku(resim):
                o.satirlar.append((-1, None, s))
            return o
        for i, b, kes, kutu in parcalar:
            for s in tam_kareye(self.okuyucu.oku(kes), kutu):
                o.satirlar.append((i, b["tur"], s))
        return o

    # -- bir adım --
    @staticmethod
    def _maskele(resim: Any, maske: list[tuple[float, float, float, float]]) -> Any:
        """Katmanın kendi çizdiği alanları kareyi bozmadan (kopyada) siyaha boyar."""
        from PIL import ImageDraw
        resim = resim.copy()
        w, h = resim.size
        d = ImageDraw.Draw(resim)
        for x, y, g, y2 in maske:
            d.rectangle((int((x - 0.005) * w), int((y - 0.005) * h),
                         int((x + g + 0.005) * w) + 1, int((y + y2 + 0.005) * h) + 1), fill=(0, 0, 0))
        return resim

    def _kare_hazirla(self, bolgeler: list[dict[str, Any]],
                      maske: list[tuple[float, float, float, float]] | None = None) -> tuple[Any, list, bytes]:
        """İş parçacığında: kare al + maske + bölgeleri kes + parmak izi (4K karede PIL işi olay döngüsünü tutmasın)."""
        resim = self.kare_kaynagi()
        if maske:
            resim = self._maskele(resim, maske)
        parcalar = [(i, b, *kirp(resim, b)) for i, b in enumerate(bolgeler)]
        if parcalar:
            izi = b"".join(parmak_izi(p[2]) for p in parcalar)
        else:
            izi = parmak_izi(resim)
        return resim, parcalar, izi

    async def adim(self) -> None:
        ayar = self.ayar()
        self._en_az_ms = en_az_ms_ayari(ayar)
        self._gorunum = ayar.get("gorunum") or {}
        self.silmeleri_isle()
        bolgeler = bolgeleri_temizle(ayar.get("bolgeler"))
        maske = self.maske_kutulari(ayar)
        kare_an = self.saat()   # §13.4: t_gel / t_git bu karenin alındığı andır (OCR süresi sayılmaz)
        t0 = time.monotonic()
        resim, parcalar, izi = await asyncio.to_thread(self._kare_hazirla, bolgeler, maske)
        t1 = time.monotonic()
        self._olcum_kare["kare_ms"] = (t1 - t0) * 1000
        anahtar = tuple((b["x"], b["y"], b["g"], b["y2"], b["tur"]) for b in bolgeler)
        simdi = self.saat()
        if (self._izi is None or anahtar != self._bolge_anahtari or degisti_mi(izi, self._izi)
                or simdi - self._son_ocr >= YENIDEN_OKU_SN):
            self._okuma = await asyncio.to_thread(self._oku, resim, parcalar)
            self._son_ocr = simdi
            self._olcum_kare["okuma_ms"] = (time.monotonic() - t1) * 1000
        self._izi = izi  # değişmediyse son OCR sonucu yeniden kullanılır
        self._bolge_anahtari = anahtar
        self._son_resim = resim
        satirlar = self._suz(self._okuma.satirlar)
        genel = _genel_olcek(ayar)
        if bolgeler:
            secilen = [(i, s) for i, _, s in satirlar if i < len(bolgeler) and _altyazi_bolgesi(bolgeler[i])]
            altyazi = [s for _, s in secilen]
            # yalnız "çubuğa yaz" (hedef altyazi) istenmiş altyazı dışı bölgeler: örtü yok, çubuk (§16.1)
            self._altyazi_cubuk = bool(secilen) and all(bolgeler[i]["tur"] != "altyazi" for i, _ in secilen)
            diger = self._bolgeli_ogeler(satirlar, bolgeler, genel)
        else:
            self._altyazi_cubuk = False
            b = ayar["bolge_altyazi"]
            altyazi = [s for _, _, s in satirlar if bolgede_mi(s, b) and altyazi_bandinda(s)]
            if tam_ekran_mi(ayar):
                diger = []   # §12.1: tüm ekranda bölgesiz yalnız altyazı bandı okunur; menü/görev yalnız kullanıcı bölgesinde
            else:
                diger = [(None, o, (None, boyut_hesapla(o, 1.0, genel)))
                         for o in birlestir([s for _, _, s in satirlar if not bolgede_mi(s, b)])
                         if len(o.metin.strip()) >= 2]
        altyazi = altyazi_sec(altyazi)
        await self._altyazi_adimi(altyazi, ayar, kare_an)
        if bolgeler or ayar.get("ekrani_cevir"):   # bölge seçildiyse açıkça istenmiştir
            # §16.4: ekran öğesi çevirisi de kare döngüsünü bekletmez (altyazı satırları kaçmasın)
            if self._ekran_gorevi is None or self._ekran_gorevi.done():
                self._ekran_gorevi = asyncio.get_running_loop().create_task(
                    self._ekran_adimi_guvenli(diger, ayar, kare_an))
                await self._kisa_bekle([self._ekran_gorevi])
        elif self._ogeler:
            self._ogeler = []
            self._oge_adaylari = []
            self.yayin.yayinla("ekran-sil", {})
        self.silmeleri_isle()

    async def _ekran_adimi_guvenli(self, diger: list, ayar: dict[str, Any], kare_an: float) -> None:
        try:
            await self._ekran_adimi(diger, ayar, kare_an)
        except asyncio.CancelledError:
            raise
        except Exception as e:   # noqa: BLE001 — görevde kalan hata adımı bozmasın, döngü gibi bildirilsin
            self._adim_hatasi(e)

    @staticmethod
    def _bolgeli_ogeler(satirlar: list[tuple[int, str | None, Satir]], bolgeler: list[dict[str, Any]],
                        genel: float = 1.0) -> list[tuple[str | None, Satir, tuple[Any, float]]]:
        """Altyazı dışındaki bölgelerin satırlarını öğeye çevirir (PROTOKOL 11.4). Çıktı: (tür, satır,
        (hedef kutusu | None, boyut_px)); hedef None = kaynağın üstüne. Kullanıcı hedef kutusu çizdiyse
        bölgenin bütün satırları tek öğede toplanır (üst üste binmesin)."""
        out: list[tuple[str | None, Satir, tuple[Any, float]]] = []
        for i in sorted({i for i, tur, _ in satirlar if tur != "altyazi" and i < len(bolgeler)
                         and not _altyazi_bolgesi(bolgeler[i])}):
            b = bolgeler[i]
            grup = [s for j, _, s in satirlar if j == i]
            tur = b["tur"]
            hedef = b.get("hedef")
            olcek = float(b.get("olcek") or 1.0)
            if isinstance(hedef, dict) and grup:
                sirali = sorted(grup, key=lambda s: (round(s.y, 2), s.x))
                x1, y1 = min(s.x for s in sirali), min(s.y for s in sirali)
                x2, y2 = max(s.x + s.g for s in sirali), max(s.y + s.y2 for s in sirali)
                tek = Satir(" ".join(s.metin for s in sirali), x1, y1, x2 - x1, y2 - y1, len(sirali))
                if len(tek.metin.strip()) >= 2:
                    out.append((tur, tek, ((hedef["x"], hedef["y"], hedef["g"], hedef["y2"]),
                                           boyut_hesapla(tek, olcek, genel))))
                continue
            out += [(tur, o, (None, boyut_hesapla(o, olcek, genel))) for o in birlestir(grup)
                    if len(o.metin.strip()) >= 2]
        return out

    # -- altyazı (§16.4 sıralı kuyruk; §13.4 kayık zamanlama, 7.2/4-7) --
    def _en_az_s(self) -> float:
        return self._en_az_ms / 1000

    def _gel_izle(self, aday: str, t: float) -> None:
        """t_gel: kaynak metnin ilk görüldüğü kare. Aynı satırın büyümesi/küçük OCR farkı onu değiştirmez;
        stabilizatör 2 kare istese de t_gel ilk görülmedir."""
        p = self._ag_norm
        if not p or not (aday == p or devam_mi(p, aday) or devam_mi(aday, p)):
            self._ag_t = t
        self._ag_norm, self._ag_kayip = aday, 0

    def _acik_satir(self) -> SiraSatiri | None:
        """Kaynağı hâlâ ekranda sayılan (t_git'i belli olmayan) son satır."""
        s = self._sira.son()
        return s if s is not None and s.git is None else None

    async def _altyazi_adimi(self, satirlar: list[Satir], ayar: dict[str, Any], kare_an: float | None = None) -> None:
        simdi = self.saat()
        t = simdi if kare_an is None else min(kare_an, simdi)
        self._gorunum = ayar.get("gorunum") or {}
        self._sira.en_az_s = self._en_az_s()
        self._sira.karakter_ms = karakter_ms_ayari(ayar)
        sirali = sorted(satirlar, key=lambda s: (round(s.y, 2), s.x))
        metin = " ".join(s.metin for s in sirali).strip()
        if len(metin) > EN_COK_ALTYAZI_KARAKTER:
            metin = ""     # ekranın yazı dolu bir yerine denk gelindi (menü/harita): altyazı sayılmaz
        aday = normallestir(metin)
        if sirali and aday:
            self._son_kutu = (min(s.x for s in sirali), min(s.y for s in sirali),
                              max(s.x + s.g for s in sirali) - min(s.x for s in sirali),
                              max(s.y + s.y2 for s in sirali) - min(s.y for s in sirali))
            self._son_satirlar = sirali
        son = self._sira.son()
        if aday and son is not None and son.git_tur == "kayip" and son is self._sira.gosterilen \
                and aday == son.ek.get("norm"):
            son.git, son.git_tur = None, ""   # kaynak silinmeden geri geldi: aynı yazı kalır
        acik = self._acik_satir()
        if aday:
            self._gel_izle(aday, t)
            self._kayip, self._ilk_kayip = 0, None
            if acik is not None and aday == acik.ek.get("norm"):
                self._canli_tut(acik, simdi)
            elif self._hatali is not None and aday == self._hatali[0] and simdi - self._hatali[1] < HATA_TEKRAR_SN:
                pass   # az önce çevrilemedi: her karede yeniden istek atılmaz
            elif aday == self._aday_onceki:
                self._kesinlestir(metin, aday, ayar)
            else:
                self._ilk_gorulme(metin, aday, ayar)
        else:
            self._spek_iptal()
            self._ag_kayip += 1
            if self._ag_kayip >= KAYIP_KARE:
                self._ag_norm = ""
            if acik is not None:
                self._kayip += 1
                if self._ilk_kayip is None:
                    self._ilk_kayip = t
                if self._kayip >= KAYIP_KARE:   # §13.4: t_git = kaynağın ilk görünmediği kare
                    acik.git, acik.git_tur = self._ilk_kayip, "kayip"
        self._aday_onceki = aday
        self._sira_isle()
        await self._kisa_bekle()

    async def _kisa_bekle(self, ek: list[asyncio.Task] | None = None) -> None:
        """Anında biten çeviriler (hafıza, önbellek, yerel motor) aynı adımda yayınlansın; ağdakiler beklenmez."""
        for _ in range(6):
            bekleyen = [g for g in list(self._gorevler) + (ek or []) if not g.done()]
            if not bekleyen:
                return
            await asyncio.sleep(0)

    def _canli_tut(self, s: SiraSatiri, simdi: float) -> None:
        """Kaynak hâlâ ekranda: yazıyı canlı tut (aynı id, yerinde; istemcinin güvenlik süresi dolmasın)."""
        if s is self._sira.gosterilen and simdi > s.ek.get("bitis", 0.0) - 0.8:
            s.ek["bitis"] = simdi + 2.0
            self._yayinla_satir(s, True, 2000)

    def _ilk_gorulme(self, metin: str, aday: str, ayar: dict[str, Any]) -> None:
        """Yeni metin ilk karede: hafızada varsa hemen kesinleşir, yoksa önden çeviri hemen başlar (§16.4)."""
        onceki = self._aday_onceki
        if onceki and (aday.startswith(onceki) or onceki.startswith(aday)):
            self._spek_iptal()  # daktilo gibi yazılıyor: kararlı olunca çevrilecek
            return
        _, govde = konusan_ayir(metin)
        if self.yonetici.ara(govde, ayar["kaynak_dil"], ayar["hedef_dil"]):
            self._spek_iptal()
            self._kesinlestir(metin, aday, ayar)
        else:
            self._spek_basla(govde, aday, ayar)

    def _kesinlestir(self, metin: str, aday: str, ayar: dict[str, Any]) -> None:
        """Satır kararlı: kuyruğa eklenir (ya da açık satırın devamıysa o satır yerinde yenilenir)."""
        konusan, govde = konusan_ayir(metin)
        simdi = self.saat()
        gorev = self._spek if self._spek_aday == aday and self._spek_gitti else None
        if gorev is not None:
            self._spek, self._spek_aday = None, ""   # önden çeviri satıra devredildi
        else:
            self._spek_iptal()   # henüz yola çıkmadıysa beklemesiz yenisi atılır
        ek = {"norm": aday, "govde": govde, "konusan": konusan, "kesin": simdi,
              "kutu": self._son_kutu, "ortu": self._ortu_kaynagi()}
        acik = self._acik_satir()
        if acik is not None and devam_mi(acik.ek.get("norm", ""), aday):
            eski = acik.ek.get("gorev")
            if eski is not None and not eski.done():
                eski.cancel()
            acik.ek.update(ek)
            if acik is not self._sira.gosterilen:
                acik.hazir, acik.metin = None, None
            self._cevir_baslat(acik, govde, ayar, gorev)
            return
        if acik is not None:   # kaynak hiç kaybolmadan değişti (§13.4): eskisinin t_git'i yeni cümlenin t_gel'idir
            acik.git, acik.git_tur = self._ag_t, "yeni"
        self._kayip, self._ilk_kayip = 0, None
        s = self._sira.ekle(SiraSatiri(self._yeni_id("a"), gel=self._ag_t, ek=ek))
        self._cevir_baslat(s, govde, ayar, gorev)

    def _cevir_baslat(self, s: SiraSatiri, govde: str, ayar: dict[str, Any], gorev: asyncio.Task | None) -> None:
        s.ek["istek"] = self.saat()
        if gorev is None:
            vur = self.yonetici.ara(govde, ayar["kaynak_dil"], ayar["hedef_dil"])
            if vur:
                self._hazir(s, govde, vur)
                return
        g = asyncio.get_running_loop().create_task(self._cevir_gorevi(s, govde, ayar, gorev))
        s.ek["gorev"] = g
        self._gorevler.add(g)
        g.add_done_callback(self._gorevler.discard)
        g.add_done_callback(_sessiz)

    async def _cevir_gorevi(self, s: SiraSatiri, govde: str, ayar: dict[str, Any], gorev: asyncio.Task | None) -> None:
        try:
            if gorev is not None:
                c = await gorev          # önden başlamıştı: yalnız kalanı bekler
            else:
                (c,) = await self.yonetici.cevir([govde], ayar["kaynak_dil"], ayar["hedef_dil"])
        except asyncio.CancelledError:
            raise
        except Exception as e:   # bilinen motor hataları ve beklenmeyenler: satır kuyruktan çıkar
            if s.ek.get("govde") == govde:
                if s is self._sira.gosterilen:
                    pass             # gösterilen satırın devamı çevrilemedi: eski çevirisi kalır
                else:
                    s.hata = True
                    self._basarisiz += 1
                    self._hatali = (s.ek.get("norm", ""), self.saat())
                self._hata(e)
                self._sira_isle()
            return
        if s.ek.get("govde") != govde:
            return   # bu arada satır büyüdü; yeni çeviri bekleniyor
        self.durum_hatasi = None
        self._hazir(s, govde, c)

    def _hazir(self, s: SiraSatiri, govde: str, c: Any) -> None:
        s.ek["ceviri"] = c
        s.ek["kaynak_tur"] = getattr(c, "kaynak", "motor")
        if s is self._sira.gosterilen:
            if c.metin != s.metin:
                s.metin, s.guncel = c.metin, True
            s.hazir = s.hazir if s.hazir is not None else self.saat()
        else:
            s.metin, s.hazir = c.metin, self.saat()
        self._sira_isle()

    def _benzerleri_birlestir(self) -> None:
        """Gösterilenin hemen ardılı (kaynak boşalmadan gelen) neredeyse aynı çeviriyse ayrı satır değildir
        (OCR oynaması): yerinde güncellenir, zıplama yok (7.2/4)."""
        cur = self._sira.gosterilen
        if cur is None or cur.git_tur != "yeni":
            return
        nxt = next((s for s in self._sira.satirlar if s is not cur and not s.hata), None)
        if nxt is None or nxt.metin is None or abs(nxt.gel - (cur.git or -1)) > 1e-9:
            return
        if not (ceviri_benzer(cur.metin or "", nxt.metin) or devam_mi(cur.ek.get("norm", ""), nxt.ek.get("norm", ""))):
            return
        self._sira.satirlar.remove(nxt)
        kesin = cur.ek.get("kesin")
        cur.ek.update({k: v for k, v in nxt.ek.items() if k != "kesin"})
        cur.ek["kesin"] = kesin
        cur.git, cur.git_tur = nxt.git, nxt.git_tur
        if nxt.metin != cur.metin:
            cur.metin, cur.guncel = nxt.metin, True

    def _sira_isle(self) -> None:
        """Kuyruğun vakti gelen kararlarını yayınlar (göster / yerinde güncelle / sil)."""
        self._benzerleri_birlestir()
        for eylem, s in self._sira.adim(self.saat()):
            if eylem == "goster":
                self._yayinla_satir(s, False)
                self._ceviri_kaydet(s.ek.get("govde", ""), s.metin or "")
                self.yonetici.satir_kaydet(s.id, s.ek.get("govde", ""), s.metin or "", s.ek.get("kaynak_tur", "motor"))
                self._olcum_kaydet(s)
            elif eylem == "devam":
                self._yayinla_satir(s, True)
                self._ceviri_kaydet(s.ek.get("govde", ""), s.metin or "")
                if hasattr(self.yonetici, "satir_guncelle"):
                    self.yonetici.satir_guncelle(s.id, s.ek.get("govde", ""), s.metin or "",
                                                 s.ek.get("kaynak_tur", "motor"))
            else:
                self.yayin.yayinla("yazi-sil", {"id": s.id})
        self._uyan_kur()

    def _olcum_kaydet(self, s: SiraSatiri) -> None:
        g = s.goster or 0.0
        kesin, istek = s.ek.get("kesin", s.gel), s.ek.get("istek", s.gel)
        self._olcumler.append({"kararlilik_ms": (kesin - s.gel) * 1000,
                               "ceviri_ms": max(0.0, ((s.hazir or g) - istek) * 1000),
                               "bekleme_ms": max(0.0, (g - (s.hazir or g)) * 1000),
                               "toplam_ms": max(0.0, (g - s.gel) * 1000)})

    def gecikme_bilgisi(self) -> dict[str, Any]:
        """§16.4: aşama aşama gecikme (son 20 satırın ortancası, ms) — /api/durum `gecikme`."""
        def orta(k: str) -> int | None:
            v = [o[k] for o in self._olcumler]
            return int(round(statistics.median(v))) if v else None
        return {"kare_ms": int(round(self._olcum_kare["kare_ms"])), "okuma_ms": int(round(self._olcum_kare["okuma_ms"])),
                "kararlilik_ms": orta("kararlilik_ms"), "ceviri_ms": orta("ceviri_ms"),
                "bekleme_ms": orta("bekleme_ms"), "toplam_ms": orta("toplam_ms"),
                "kuyruk": len(self._sira.bekleyenler()), "atlanan": self._basarisiz, "olcum": len(self._olcumler)}

    # -- örtü (§16.1/16.2) --
    def _ortu_kaynagi(self) -> dict[str, Any] | None:
        """Kesinleşen satırın örtü kutusu ve zemin rengi (yazı yerleşimi `ustune` iken kullanılır)."""
        if self._altyazi_cubuk or not self._son_satirlar:
            return None
        try:
            return ortu_kutusu(self._son_satirlar, self._son_resim)
        except Exception:   # noqa: BLE001 — örtü hesaplanamazsa eski çizim (çubuk) kullanılır
            log.debug("örtü kutusu hesaplanamadı", exc_info=True)
            return None

    def _ortu(self, s: SiraSatiri) -> dict[str, Any] | None:
        k = s.ek.get("ortu")
        if not k or self._gorunum.get("yerlesim", "ustune") != "ustune":
            return None
        return ortu_olaya(k, s.metin or "", self._gorunum)

    def _yayinla_satir(self, s: SiraSatiri, devam: bool, sure: int | None = None) -> None:
        metin = s.metin or ""
        sure = sure_ms(metin) if sure is None else sure
        s.ek["bitis"] = self.saat() + sure / 1000
        veri = {"id": s.id, "metin": metin, "asil": s.ek.get("govde", ""), "tur": "altyazi",
                "konusan": s.ek.get("konusan"), "sure_ms": sure, "devam": devam}
        o = self._ortu(s)
        if o:
            veri["ortu"] = o
        self.yayin.yayinla("yazi", veri)

    def silmeleri_isle(self) -> None:
        """Vakti gelen kararları yapar (altyazı kuyruğu, ekran öğesi silme). Gerçek saatte call_later çağırır,
        her adımda da çağrılır; sahte saatli testlerde dışarıdan çağrılabilir."""
        simdi = self.saat()
        self._sira_isle()
        kalkan = [e for e in self._ogeler if e.sil_an is not None and simdi >= e.sil_an - 1e-9]
        if kalkan:
            self._ogeler = [e for e in self._ogeler if e not in kalkan]
            self._ekran_yayinla()
        self._uyan_kur()

    def _sonraki_an(self) -> float | None:
        adaylar = [e.sil_an for e in self._ogeler if e.sil_an is not None]
        an = self._sira.sonraki_an()
        if an is not None:
            adaylar.append(an)
        return min(adaylar) if adaylar else None

    def _uyan_kur(self) -> None:
        if not self._gercek_saat:
            return
        if self._uyanis is not None:
            self._uyanis.cancel()
            self._uyanis = None
        an = self._sonraki_an()
        if an is None:
            return
        try:
            dongu = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._uyanis = dongu.call_later(max(0.02, an - self.saat() + 0.005), self.silmeleri_isle)

    # -- ekran öğeleri (7.2/8) --
    def _oge_bul(self, norm: str, o: Satir, kullanilan: set[str]) -> _Oge | None:
        for e in self._ogeler:
            if e.id not in kullanilan and e.norm == norm and _yakin(e, o):
                return e
        return None

    async def _ekran_adimi(self, gelen: list[tuple[str | None, Satir, tuple[Any, float]]],
                           ayar: dict[str, Any], kare_an: float | None = None) -> None:
        simdi = self.saat()
        t = simdi if kare_an is None else min(kare_an, simdi)
        kullanilan: set[str] = set()
        yeniler: list[tuple[str | None, Satir, tuple[Any, float], str, float]] = []
        degisti = False
        gelen = [g for g in gelen if len(g[1].metin) <= EN_COK_OGE_KARAKTER][:EN_COK_OGE]
        for tur_ip, o, hz in gelen:
            n = normallestir(o.metin)
            e = self._oge_bul(n, o, kullanilan)
            if e:
                kullanilan.add(e.id)
                ozel = hz[0] is not None   # bölge hedefi/ölçeği sonradan değiştiyse yerinde güncelle
                kutu = _hedef_kutusu(o, hz[0]) if ozel else e.hedef   # kaynağın üstündekinde OCR titremesi yok sayılır
                if abs(hz[1] - e.boyut_px) >= 2.0 or ozel != e.ozel or (ozel and kutu != e.hedef):
                    e.hedef, e.boyut_px, e.ozel = kutu, hz[1], ozel
                    degisti = True
            elif n:
                # t_gel: ilk görüldüğü kare (önceki karede aday olduysa onun anı)
                eski_t = next((tt for nn, s, tt in self._oge_adaylari if nn == n and _yakin(s, o)), t)
                yeniler.append((tur_ip, o, hz, n, eski_t))
        # yeni öğe iki kare üst üste aynı yerde görünürse kesinleşir (OCR titremesine karşı)
        kesin = [y for y in yeniler
                 if any(n == y[3] and _yakin(s, y[1]) for n, s, _ in self._oge_adaylari)]
        self._oge_adaylari = [(n, o, tt) for _, o, _, n, tt in yeniler]
        sonuc: dict[int, Any] = {}
        if kesin:
            try:
                sonuc = await self._ekran_cevir(kesin, ayar)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._hata(e)
                self._oge_adaylari = [(n, o, tt) for _, o, _, n, tt in yeniler]
                return
        # görünmeyen öğeler (§13.2/§13.4): 2 kare kayıp (bölge tamamen boşsa 1) -> t_git = ilk görünmediği kare;
        # öğe t_git + L'de kalkar (en az gösterim dahil). Kalkmadan geri gelirse silme iptal olur.
        bos = [e for e in self._ogeler if e.id not in kullanilan]
        tum_bos = not gelen
        for e in bos:
            e.kayip += 1
            if e.ilk_kayip is None:
                e.ilk_kayip = t
            if (e.kayip >= EKRAN_KAYIP_KARE or tum_bos) and e.sil_an is None:
                e.sil_an = max(e.ilk_kayip + max(0.0, e.hazir - e.gel), e.hazir + self._en_az_s())
        for e in self._ogeler:
            if e.id in kullanilan:
                e.kayip, e.ilk_kayip, e.sil_an = 0, None, None
        # kesinleşen öğe, aynı yerdeki eski öğenin yerine geçer (yerinde güncelleme); yoksa eklenir
        hazir_an = self.saat()
        for i, (tur_ip, o, hz, n, gel_t) in enumerate(kesin):
            c, tur = sonuc[i]
            eski = next((e for e in bos if _ortusme(e, o) >= 0.5), None)
            aciklama = c.aciklama[:60] if getattr(c, "aciklama", None) else None
            kutu, ozel = _hedef_kutusu(o, hz[0]), hz[0] is not None
            if eski is not None:
                bos.remove(eski)
                eski.norm, eski.asil, eski.metin, eski.aciklama, eski.tur = n, o.metin, c.metin, aciklama, tur
                eski.x, eski.y, eski.g, eski.y2 = o.x, o.y, o.g, o.y2
                eski.hedef, eski.ozel, eski.boyut_px = kutu, ozel, hz[1]
                eski.ortu = None if ozel else self._oge_ortusu(o)
                eski.kayip, eski.ilk_kayip, eski.sil_an = 0, None, None
                eski.gel, eski.hazir = gel_t, hazir_an
            else:
                self._ogeler.append(_Oge(self._yeni_id("o"), n, o.metin, o.x, o.y, o.g, o.y2, tur,
                                         c.metin, aciklama, gel=gel_t, hazir=hazir_an, hedef=kutu,
                                         ozel=ozel, boyut_px=hz[1], ortu=None if ozel else self._oge_ortusu(o)))
            self._ceviri_kaydet(o.metin, c.metin)
            degisti = True
        kalan = [e for e in self._ogeler if e.sil_an is None or self.saat() < e.sil_an - 1e-9]
        if len(kalan) != len(self._ogeler):
            self._ogeler, degisti = kalan, True
        if degisti:
            self._ekran_yayinla()
        self._uyan_kur()

    def _oge_ortusu(self, o: Satir) -> dict[str, Any] | None:
        try:
            return ortu_kutusu([o], self._son_resim)
        except Exception:   # noqa: BLE001
            return None

    async def _ekran_cevir(self, kesin: list[tuple[str | None, Satir, tuple[Any, float], str]],
                           ayar: dict[str, Any]) -> dict[int, tuple[Any, str]]:
        turler = []
        for tur_ip, o, *_ in kesin:
            turler.append("gorev" if tur_ip == "ust_yazi" else tur_bul(o))
        acik = bool(ayar.get("kisa_aciklama"))
        # açıklama yalnız görev/bilgi öğeleri için istenir
        acikli = [i for i, t in enumerate(turler) if acik and t in ("gorev", "bilgi")]
        duz = [i for i in range(len(kesin)) if i not in acikli]
        sonuc: dict[int, Any] = {}
        for idx, ac in ((duz, False), (acikli, True)):
            if idx:
                gelen = await self.yonetici.cevir([kesin[i][1].metin for i in idx],
                                                  ayar["kaynak_dil"], ayar["hedef_dil"], ac)
                sonuc.update(zip(idx, gelen))
        self.durum_hatasi = None
        return {i: (sonuc[i], turler[i]) for i in range(len(kesin))}

    def _ekran_yayinla(self) -> None:
        if not self._ogeler:
            self.yayin.yayinla("ekran-sil", {})
            return
        liste = []
        for e in self._ogeler:
            oge = {"id": e.id, "x": round(e.x, 4), "y": round(e.y, 4), "g": round(e.g, 4),
                   "y2": round(e.y2, 4), "metin": e.metin, "tur": e.tur,
                   "hedef": {"x": round(e.hedef[0], 4), "y": round(e.hedef[1], 4),
                             "g": round(e.hedef[2], 4), "y2": round(e.hedef[3], 4)},
                   "boyut_px": e.boyut_px}
            if e.aciklama:
                oge["aciklama"] = e.aciklama
            if e.ortu and not e.ozel and self._gorunum.get("yerlesim", "ustune") == "ustune":
                oge["ortu"] = ortu_olaya(e.ortu, e.metin, self._gorunum)
            liste.append(oge)
        self.yayin.yayinla("ekran", {"id": self._yeni_id("e"), "ogeler": liste})

    # -- döngü --
    def _adim_hatasi(self, e: Exception) -> None:
        """Yakalama/OCR hatası: günlüğü doldurmadan (dakikada bir) ve panel "hata" görsün diye bildirir."""
        kod = "yakalama" if isinstance(e, YakalamaHatasi) else "genel"
        simdi = time.monotonic()
        if kod != self.durum_hatasi or simdi - self._son_hata_logu >= HATA_LOG_SN:
            self._son_hata_logu = simdi
            if isinstance(e, YakalamaHatasi):
                log.warning("Ekran yakalanamadı: %s", e)
            else:
                log.exception("Boru hattı adımı başarısız")
        self._adim_hatali = True
        if kod != self.durum_hatasi:
            self.durum_hatasi = kod
            self.yayin.yayinla("durum", {"calisiyor": True, "motor": self.yonetici.birincil.ad,
                                         "yedek": bool(self.yonetici.yedekte),
                                         **self._yedek_ek(), "hata": kod})

    async def calis(self) -> None:
        try:
            while True:
                t0 = time.monotonic()
                try:
                    await self.adim()
                    if self._adim_hatali:   # yakalama/OCR düzeldi
                        self._adim_hatali = False
                        self.durum_hatasi = None
                        self.yayin.yayinla("durum", {"calisiyor": True, "motor": self.yonetici.birincil.ad,
                                                     "yedek": bool(self.yonetici.yedekte),
                                         **self._yedek_ek()})
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self._adim_hatasi(e)
                    await asyncio.sleep(1.0)
                await asyncio.sleep(max(0.0, ARALIK_SN - (time.monotonic() - t0)))
        finally:
            self._spek_iptal()   # durdurulunca önden/süren çeviriler boşuna sürmesin
            self._gorevleri_iptal()
