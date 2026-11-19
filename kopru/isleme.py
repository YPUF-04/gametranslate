# SPDX-License-Identifier: AGPL-3.0-only
"""Ana boru hattı: kare al -> değişim? -> OCR -> kararlılaştır -> çevir -> yayınla.

Akıcı gösterim kuralları docs/PROTOKOL.md 7.2'dedir; hepsi burada, saat dışarıdan verilebilir
(`saat`) olduğu için sahte saatle sınanır.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Callable

from .ayarlar import bolgeleri_temizle
from .ceviri.temel import AgHatasi, AnahtarHatasi, ErisimSiniri, MotorHatasi
from .onbellek import normallestir
from .okuma import Satir
from .yakalama import YakalamaHatasi

log = logging.getLogger("kopru.isleme")

ARALIK_SN = 0.25
SPEK_BEKLEME_SN = 0.05  # önden çeviri kısa bir an bekler: hemen değişen metne boşuna istek atılmaz
DEGISIM_ESIGI = 3.0  # küçültülmüş gri karelerde ortalama mutlak fark (0-255)
EN_AZ_GOSTERIM_MS = 1800   # 7.2/1: bir altyazı en az bu kadar kalır
KAYIP_KARE = 3             # 7.2/2: bu kadar kare üst üste görünmezse "gitti"
GITTI_SONRA_SN = 0.7       # 7.2/3: süre dolmuşsa gittikten sonra bu kadar daha kalır
EKRAN_GITTI_SN = 1.0       # 7.2/8: ekran öğesi gidince bu kadar sonra kalkar
EN_KUCUK_OCR_YUKSEKLIK = 48  # daha küçük bölge okumadan önce büyütülür
EN_COK_ALTYAZI_KARAKTER = 600   # bundan uzun "altyazı" okuma gürültüsüdür; bütçeyi yakmasın
EN_COK_OGE_KARAKTER = 300
EN_COK_OGE = 24               # bir karede çevrilecek en çok ekran öğesi
HATA_LOG_SN = 60.0            # aynı hata günlüğe en çok dakikada bir
GERI_BESLEME_SN = 60.0         # §11.1: son 60 sn'de yayınlanan çevirilere benzeyen okumalar atılır
GERI_BESLEME_ESIK = 0.80
ALT_BANT_Y = 0.70              # §11.3: otomatik kipte altyazı yalnız alt-orta bandından
ALT_BANT_X = (0.2, 0.8)
BOYUT_MIN_PX, BOYUT_MAX_PX = 14.0, 30.0   # §11.5: 1080p'de ekran öğesi yazı boyu
_KELIME = re.compile(r"\w+", re.UNICODE)
_KONUSAN = re.compile(r"^([A-ZÇĞİÖŞÜ][\w'. -]{0,24}):\s+(\S.*)$", re.UNICODE)


def okuma_suresi_ms(metin: str) -> int:
    return min(9000, 800 + len(metin) * 55)


def sure_ms(metin: str) -> int:
    """Altyazının en az ekranda kalma süresi: max(1800, okuma süresi)."""
    return max(EN_AZ_GOSTERIM_MS, okuma_suresi_ms(metin))


def _kelimeler(metin: str) -> list[str]:
    return _KELIME.findall(metin.casefold())


def tekrar_var_mi(metin: str) -> bool:
    """Aynı kelime üst üste 3 kez ("tek tek tek", "Parti: Parti: Parti:") ya da bütün kelimeler aynı."""
    k = _kelimeler(metin)
    if len(k) >= 2 and len(set(k)) == 1:
        return True
    return any(k[i] == k[i + 1] == k[i + 2] for i in range(len(k) - 2))


def okuma_gurultusu_mu(metin: str) -> bool:
    """§11.3: çevrilmeyecek okuma: <2 harf, tek karakter, çoğu rakam/simge (HUD sayıları), tekrarlı kelime."""
    m = "".join(metin.split())
    if len(m) <= 1:
        return True
    harf = sum(1 for c in m if c.isalpha())
    if harf < 2 or (len(m) - harf) / len(m) > 0.5:
        return True
    return tekrar_var_mi(metin)


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
    genişleyen (en çok %45) kutu. Maske için; gerçek çizim katmandadır."""
    doğal = max(1.0, len(metin) * boyut_px * 0.55 + 24) / 1920
    g = min(0.45, doğal)
    satir = max(1, int(-(-doğal // 0.45)))
    y2 = (satir * boyut_px * 1.3 + 12) / 1080
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
    return [Satir(s.metin, bx + s.x * bg, by + s.y * bh, s.g * bg, s.y2 * bh) for s in satirlar]


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
        out.append(Satir(" ".join(s.metin for s in g), x1, y1, x2 - x1, y2 - y1, sum(s.satir for s in g)))
    return out


def boyut_hesapla(o: Satir, olcek: float, genel: float) -> float:
    """§11.5: kaynak yazının satır yüksekliğinden (1080p) yazı boyu: 14-30 px, sonra bölge ve genel ölçekle çarpılır."""
    satir_h = o.y2 * 1080 / max(1, o.satir)
    taban = max(BOYUT_MIN_PX, min(BOYUT_MAX_PX, satir_h * 0.8))
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


def _genel_olcek(ayar: dict[str, Any]) -> float:
    v = (ayar.get("gorunum") or {}).get("ekran_olcek", 1.0)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and 0.6 <= v <= 2.0 else 1.0


@dataclass
class _Yazi:
    """Altyazının gösterim durumu (7.2)."""
    aktif: bool = False
    id: str = ""
    norm: str = ""              # şu an yayındaki kaynak (normalize)
    asil: str = ""
    metin: str = ""
    konusan: str | None = None
    tur: str = "altyazi"
    min_bitis: float = 0.0      # en az gösterim süresinin sonu
    bitis: float = 0.0          # TV'deki zamanlayıcının tahmini sonu (canlı tutma için)
    kayip: int = 0              # üst üste görünmeyen kare sayısı
    gitti: float | None = None  # "gitti" sayıldığı an
    onceki: str = ""            # önceki karedeki aday
    kutu: tuple[float, float, float, float] | None = None   # kaynak yazının kutusu (maske için)


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
    gitti: float | None = None
    hedef: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)   # çizileceği kutu (0-1)
    ozel: bool = False          # kullanıcının çizdiği hedef (kaynağın üstü değil)
    boyut_px: float = 14.0


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
        self._bolge_anahtari: tuple = ()
        self._okuma = _Okuma()
        self._y = _Yazi()
        self._ogeler: list[_Oge] = []
        self._oge_adaylari: list[tuple[str, Satir]] = []   # önceki karede görülen yeni öğeler
        self._sayac = {"a": 0, "e": 0, "o": 0}
        self.durum_hatasi: str | None = None
        self._spek: asyncio.Task | None = None   # önden başlatılmış çeviri (6.4)
        self._spek_aday = ""
        self._son_hata_logu = -1e9
        self._adim_hatali = False
        self._ceviriler: deque[tuple[float, str]] = deque(maxlen=200)   # (an, normalize çeviri): geri besleme süzgeci
        self._son_kutu: tuple[float, float, float, float] | None = None

    # -- önden (speculative) çeviri --
    def _spek_iptal(self) -> None:
        if self._spek is not None:
            self._spek.cancel()
            self._spek = None
        self._spek_aday = ""

    def _spek_basla(self, govde: str, aday: str, ayar: dict[str, Any]) -> None:
        self._spek_iptal()
        self._spek_aday = aday
        self._spek = asyncio.get_running_loop().create_task(
            self._spek_cevir(govde, ayar["kaynak_dil"], ayar["hedef_dil"]))
        self._spek.add_done_callback(_sessiz)

    async def _spek_cevir(self, govde: str, kaynak: str, hedef: str) -> Any:
        await asyncio.sleep(SPEK_BEKLEME_SN)
        (c,) = await self.yonetici.cevir([govde], kaynak, hedef)
        return c

    def duzeltildi(self, asil: str, ceviri: str) -> None:
        """Kullanıcı ekrandaki satırı düzeltti: canlı tutma yenilemesi de yeni metni yollasın."""
        if self._y.asil and normallestir(self._y.asil) == normallestir(asil):
            self._y.metin = ceviri
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
        """Gürültü (§11.3) ve kendi çevirimiz (§11.1) olan satırları atar."""
        return [(i, t, s) for i, t, s in satirlar
                if not okuma_gurultusu_mu(s.metin) and not self.geri_besleme_mi(s.metin)]

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
        a, simdi = self._y, self.saat()
        if a.aktif and simdi < a.bitis and a.metin:
            kutu = yazinin_ekran_kutusu(a.metin, ayar.get("gorunum") or {})
            if a.kutu is None or _ortusme(_K(*kutu), _K(*a.kutu)) < 0.1:
                out.append(kutu)
        for e in self._ogeler:
            if e.ozel and e.gitti is None:
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
        bolgeler = bolgeleri_temizle(ayar.get("bolgeler"))
        maske = self.maske_kutulari(ayar)
        resim, parcalar, izi = await asyncio.to_thread(self._kare_hazirla, bolgeler, maske)
        anahtar = tuple((b["x"], b["y"], b["g"], b["y2"], b["tur"]) for b in bolgeler)
        if self._izi is None or anahtar != self._bolge_anahtari or fark(izi, self._izi) > DEGISIM_ESIGI:
            self._okuma = await asyncio.to_thread(self._oku, resim, parcalar)
        self._izi = izi  # değişmediyse son OCR sonucu yeniden kullanılır
        self._bolge_anahtari = anahtar
        satirlar = self._suz(self._okuma.satirlar)
        genel = _genel_olcek(ayar)
        if bolgeler:
            altyazi = [s for i, _, s in satirlar if i < len(bolgeler) and _altyazi_bolgesi(bolgeler[i])]
            diger = self._bolgeli_ogeler(satirlar, bolgeler, genel)
        else:
            b = ayar["bolge_altyazi"]
            altyazi = [s for _, _, s in satirlar if bolgede_mi(s, b) and altyazi_bandinda(s)]
            diger = [(None, o, (None, boyut_hesapla(o, 1.0, genel)))
                     for o in birlestir([s for _, _, s in satirlar if not bolgede_mi(s, b)])
                     if len(o.metin.strip()) >= 2]
        altyazi = altyazi_sec(altyazi)
        await self._altyazi_adimi(altyazi, ayar)
        if bolgeler or ayar.get("ekrani_cevir"):   # bölge seçildiyse açıkça istenmiştir
            await self._ekran_adimi(diger, ayar)
        elif self._ogeler:
            self._ogeler = []
            self._oge_adaylari = []
            self.yayin.yayinla("ekran-sil", {})

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

    # -- altyazı (7.2 kuralları) --
    async def _altyazi_adimi(self, satirlar: list[Satir], ayar: dict[str, Any]) -> None:
        a, simdi = self._y, self.saat()
        sirali = sorted(satirlar, key=lambda s: (round(s.y, 2), s.x))
        metin = " ".join(s.metin for s in sirali).strip()
        if len(metin) > EN_COK_ALTYAZI_KARAKTER:
            metin = ""     # ekranın yazı dolu bir yerine denk gelindi (menü/harita): altyazı sayılmaz
        aday = normallestir(metin)
        if sirali and aday:
            self._son_kutu = (min(s.x for s in sirali), min(s.y for s in sirali),
                              max(s.x + s.g for s in sirali) - min(s.x for s in sirali),
                              max(s.y + s.y2 for s in sirali) - min(s.y for s in sirali))
        if aday:
            a.kayip, a.gitti = 0, None
            if a.aktif and aday == a.norm:
                if simdi > a.bitis - 0.8:   # kaynak hâlâ ekranda: yazıyı canlı tut (aynı id, yerinde)
                    a.bitis = simdi + 2.0
                    self._yayinla_yazi(2000, True)
            elif aday == a.onceki:
                await self._altyazi_yayinla(metin, aday, ayar, simdi)
            else:
                await self._ilk_gorulme(metin, aday, ayar, simdi)
        else:
            self._spek_iptal()
            if a.aktif:
                a.kayip += 1
                if a.kayip >= KAYIP_KARE and a.gitti is None:
                    a.gitti = simdi
                if a.gitti is not None:
                    # süre dolmadıysa dolana kadar, dolduysa 700 ms daha
                    sil_an = a.min_bitis if a.gitti < a.min_bitis else a.gitti + GITTI_SONRA_SN
                    if simdi >= sil_an:
                        self._yazi_sil()
        a.onceki = aday

    def _yazi_sil(self) -> None:
        a = self._y
        a.aktif, a.norm, a.gitti, a.kayip = False, "", None, 0
        self.yayin.yayinla("yazi-sil", {})

    def _yayinla_yazi(self, sure: int, devam: bool) -> None:
        a = self._y
        self.yayin.yayinla("yazi", {"id": a.id, "metin": a.metin, "asil": a.asil, "tur": a.tur,
                                    "konusan": a.konusan, "sure_ms": sure, "devam": devam})

    async def _ilk_gorulme(self, metin: str, aday: str, ayar: dict[str, Any], simdi: float) -> None:
        """Yeni metin ilk karede: hafızada varsa hemen göster, yoksa önden çeviriyi başlat."""
        onceki = self._y.onceki
        if onceki and (aday.startswith(onceki) or onceki.startswith(aday)):
            self._spek_iptal()  # daktilo gibi yazılıyor: kararlı olunca çevrilecek
            return
        konusan, govde = konusan_ayir(metin)
        vur = self.yonetici.ara(govde, ayar["kaynak_dil"], ayar["hedef_dil"])
        if vur:
            self._spek_iptal()
            self._goster(govde, konusan, aday, vur, simdi)
        else:
            self._spek_basla(govde, aday, ayar)

    async def _altyazi_yayinla(self, metin: str, aday: str, ayar: dict[str, Any], simdi: float) -> None:
        konusan, govde = konusan_ayir(metin)
        gorev = self._spek if self._spek_aday == aday else None
        try:
            if gorev is not None:
                c = await gorev           # önden başlamıştı: yalnız kalanı bekler
            else:
                (c,) = await self.yonetici.cevir([govde], ayar["kaynak_dil"], ayar["hedef_dil"])
        except asyncio.CancelledError:
            raise
        except Exception as e:   # bilinen motor hataları ve beklenmeyenler: başarısız önden çeviri tekrar kullanılmaz
            self._spek_iptal()
            self._hata(e)
            return
        self._spek = None
        self._spek_aday = ""
        self.durum_hatasi = None
        self._goster(govde, konusan, aday, c, simdi)

    def _goster(self, govde: str, konusan: str | None, aday: str, c: Any, simdi: float) -> None:
        a = self._y
        devam = a.aktif and (devam_mi(a.norm, aday) or ceviri_benzer(a.metin, c.metin))
        s = sure_ms(c.metin)
        if not devam:
            a.id = self._yeni_id("a")
        a.asil, a.metin, a.konusan, a.tur = govde, c.metin, konusan, "altyazi"
        a.aktif, a.norm, a.kayip, a.gitti = True, aday, 0, None
        a.kutu = self._son_kutu
        self._ceviri_kaydet(govde, c.metin)
        a.min_bitis = a.bitis = simdi + s / 1000
        kaynak = getattr(c, "kaynak", "motor")
        if devam and hasattr(self.yonetici, "satir_guncelle"):
            self.yonetici.satir_guncelle(a.id, govde, c.metin, kaynak)
        else:
            self.yonetici.satir_kaydet(a.id, govde, c.metin, kaynak)
        self._yayinla_yazi(s, devam)

    # -- ekran öğeleri (7.2/8) --
    def _oge_bul(self, norm: str, o: Satir, kullanilan: set[str]) -> _Oge | None:
        for e in self._ogeler:
            if e.id not in kullanilan and e.norm == norm and _yakin(e, o):
                return e
        return None

    async def _ekran_adimi(self, gelen: list[tuple[str | None, Satir, tuple[Any, float]]],
                           ayar: dict[str, Any]) -> None:
        simdi = self.saat()
        kullanilan: set[str] = set()
        yeniler: list[tuple[str | None, Satir, tuple[Any, float], str]] = []
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
                yeniler.append((tur_ip, o, hz, n))
        # yeni öğe iki kare üst üste aynı yerde görünürse kesinleşir (OCR titremesine karşı)
        kesin = [y for y in yeniler
                 if any(n == y[3] and _yakin(s, y[1]) for n, s in self._oge_adaylari)]
        self._oge_adaylari = [(n, o) for _, o, _, n in yeniler]
        sonuc: dict[int, Any] = {}
        if kesin:
            try:
                sonuc = await self._ekran_cevir(kesin, ayar)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._hata(e)
                self._oge_adaylari = [(n, o) for _, o, _, n in yeniler]
                return
        # görünmeyen öğeler: 3 kare kayıp -> gitti -> 1 sn sonra kalkar
        bos = [e for e in self._ogeler if e.id not in kullanilan]
        for e in bos:
            e.kayip += 1
            if e.kayip >= KAYIP_KARE and e.gitti is None:
                e.gitti = simdi
        for e in self._ogeler:
            if e.id in kullanilan:
                e.kayip, e.gitti = 0, None
        # kesinleşen öğe, aynı yerdeki eski öğenin yerine geçer (yerinde güncelleme); yoksa eklenir
        for i, (tur_ip, o, hz, n) in enumerate(kesin):
            c, tur = sonuc[i]
            eski = next((e for e in bos if _ortusme(e, o) >= 0.5), None)
            aciklama = c.aciklama[:60] if getattr(c, "aciklama", None) else None
            kutu, ozel = _hedef_kutusu(o, hz[0]), hz[0] is not None
            if eski is not None:
                bos.remove(eski)
                eski.norm, eski.asil, eski.metin, eski.aciklama, eski.tur = n, o.metin, c.metin, aciklama, tur
                eski.x, eski.y, eski.g, eski.y2 = o.x, o.y, o.g, o.y2
                eski.hedef, eski.ozel, eski.boyut_px = kutu, ozel, hz[1]
                eski.kayip, eski.gitti = 0, None
            else:
                self._ogeler.append(_Oge(self._yeni_id("o"), n, o.metin, o.x, o.y, o.g, o.y2, tur,
                                         c.metin, aciklama, hedef=kutu, ozel=ozel, boyut_px=hz[1]))
            self._ceviri_kaydet(o.metin, c.metin)
            degisti = True
        kalan = [e for e in self._ogeler if e.gitti is None or simdi - e.gitti < EKRAN_GITTI_SN]
        if len(kalan) != len(self._ogeler):
            self._ogeler, degisti = kalan, True
        if degisti:
            self._ekran_yayinla()

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
            self._spek_iptal()   # durdurulunca önden çeviri boşuna sürmesin
