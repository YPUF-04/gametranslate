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
_KONUSAN = re.compile(r"^([A-ZÇĞİÖŞÜ][\w'. -]{0,24}):\s+(\S.*)$", re.UNICODE)


def okuma_suresi_ms(metin: str) -> int:
    return min(9000, 800 + len(metin) * 55)


def sure_ms(metin: str) -> int:
    """Altyazının en az ekranda kalma süresi: max(1800, okuma süresi)."""
    return max(EN_AZ_GOSTERIM_MS, okuma_suresi_ms(metin))


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


def kirp(resim: Any, b: dict[str, Any]) -> tuple[Any, tuple[float, float, float, float]]:
    """Kareyi bölgeye göre keser. Dönen kutu, gerçekten kesilen pikselin 0-1 karşılığıdır."""
    w, h = resim.size
    x0 = min(max(int(round(b["x"] * w)), 0), w - 1)
    y0 = min(max(int(round(b["y"] * h)), 0), h - 1)
    x1 = max(x0 + 1, min(w, int(round((b["x"] + b["g"]) * w))))
    y1 = max(y0 + 1, min(h, int(round((b["y"] + b["y2"]) * h))))
    kes = resim.crop((x0, y0, x1, y1))
    if kes.size[1] < EN_KUCUK_OCR_YUKSEKLIK:   # çok ince bölgeyi okuyucular sevmez
        kat = min(4.0, EN_KUCUK_OCR_YUKSEKLIK / kes.size[1])
        kes = kes.resize((max(1, int(kes.size[0] * kat)), max(1, int(kes.size[1] * kat))))
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
        out.append(Satir(" ".join(s.metin for s in g), x1, y1, x2 - x1, y2 - y1))
    return out


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
    def _kare_hazirla(self, bolgeler: list[dict[str, Any]]) -> tuple[Any, list, bytes]:
        """İş parçacığında: kare al + bölgeleri kes + parmak izi (4K karede PIL işi olay döngüsünü tutmasın)."""
        resim = self.kare_kaynagi()
        parcalar = [(i, b, *kirp(resim, b)) for i, b in enumerate(bolgeler)]
        if parcalar:
            izi = b"".join(parmak_izi(p[2]) for p in parcalar)
        else:
            izi = parmak_izi(resim)
        return resim, parcalar, izi

    async def adim(self) -> None:
        ayar = self.ayar()
        bolgeler = bolgeleri_temizle(ayar.get("bolgeler"))
        resim, parcalar, izi = await asyncio.to_thread(self._kare_hazirla, bolgeler)
        anahtar = tuple((b["x"], b["y"], b["g"], b["y2"], b["tur"]) for b in bolgeler)
        if self._izi is None or anahtar != self._bolge_anahtari or fark(izi, self._izi) > DEGISIM_ESIGI:
            self._okuma = await asyncio.to_thread(self._oku, resim, parcalar)
        self._izi = izi  # değişmediyse son OCR sonucu yeniden kullanılır
        self._bolge_anahtari = anahtar
        satirlar = self._okuma.satirlar
        if bolgeler:
            altyazi = [s for _, tur, s in satirlar if tur == "altyazi"]
            diger = self._bolgeli_ogeler(satirlar)
        else:
            b = ayar["bolge_altyazi"]
            altyazi = [s for _, _, s in satirlar if bolgede_mi(s, b)]
            diger = [(None, o) for o in birlestir([s for _, _, s in satirlar if not bolgede_mi(s, b)]
                                                  ) if len(o.metin.strip()) >= 2]
        await self._altyazi_adimi(altyazi, ayar)
        if bolgeler or ayar.get("ekrani_cevir"):   # bölge seçildiyse açıkça istenmiştir
            await self._ekran_adimi(diger, ayar)
        elif self._ogeler:
            self._ogeler = []
            self._oge_adaylari = []
            self.yayin.yayinla("ekran-sil", {})

    @staticmethod
    def _bolgeli_ogeler(satirlar: list[tuple[int, str | None, Satir]]) -> list[tuple[str | None, Satir]]:
        """Altyazı dışındaki bölgelerin satırlarını, her bölge kendi içinde birleştirerek öğeye çevirir."""
        out: list[tuple[str | None, Satir]] = []
        for i in sorted({i for i, tur, _ in satirlar if tur != "altyazi"}):
            grup = [s for j, _, s in satirlar if j == i]
            tur = next(t for j, t, _ in satirlar if j == i)
            out += [(tur, o) for o in birlestir(grup) if len(o.metin.strip()) >= 2]
        return out

    # -- altyazı (7.2 kuralları) --
    async def _altyazi_adimi(self, satirlar: list[Satir], ayar: dict[str, Any]) -> None:
        a, simdi = self._y, self.saat()
        sirali = sorted(satirlar, key=lambda s: (round(s.y, 2), s.x))
        metin = " ".join(s.metin for s in sirali).strip()
        if len(metin) > EN_COK_ALTYAZI_KARAKTER:
            metin = ""     # ekranın yazı dolu bir yerine denk gelindi (menü/harita): altyazı sayılmaz
        aday = normallestir(metin)
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

    async def _ekran_adimi(self, gelen: list[tuple[str | None, Satir]], ayar: dict[str, Any]) -> None:
        simdi = self.saat()
        kullanilan: set[str] = set()
        yeniler: list[tuple[str | None, Satir, str]] = []
        gelen = [(t, o) for t, o in gelen if len(o.metin) <= EN_COK_OGE_KARAKTER][:EN_COK_OGE]
        for tur_ip, o in gelen:
            n = normallestir(o.metin)
            e = self._oge_bul(n, o, kullanilan)
            if e:
                kullanilan.add(e.id)
            elif n:
                yeniler.append((tur_ip, o, n))
        # yeni öğe iki kare üst üste aynı yerde görünürse kesinleşir (OCR titremesine karşı)
        kesin = [y for y in yeniler
                 if any(n == y[2] and _yakin(s, y[1]) for n, s in self._oge_adaylari)]
        self._oge_adaylari = [(n, o) for _, o, n in yeniler]
        sonuc: dict[int, Any] = {}
        if kesin:
            try:
                sonuc = await self._ekran_cevir(kesin, ayar)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._hata(e)
                self._oge_adaylari = [(n, o) for _, o, n in yeniler]
                return
        degisti = False
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
        for i, (tur_ip, o, n) in enumerate(kesin):
            c, tur = sonuc[i]
            eski = next((e for e in bos if _ortusme(e, o) >= 0.5), None)
            aciklama = c.aciklama[:60] if getattr(c, "aciklama", None) else None
            if eski is not None:
                bos.remove(eski)
                eski.norm, eski.asil, eski.metin, eski.aciklama, eski.tur = n, o.metin, c.metin, aciklama, tur
                eski.x, eski.y, eski.g, eski.y2 = o.x, o.y, o.g, o.y2
                eski.kayip, eski.gitti = 0, None
            else:
                self._ogeler.append(_Oge(self._yeni_id("o"), n, o.metin, o.x, o.y, o.g, o.y2, tur,
                                         c.metin, aciklama))
            degisti = True
        kalan = [e for e in self._ogeler if e.gitti is None or simdi - e.gitti < EKRAN_GITTI_SN]
        if len(kalan) != len(self._ogeler):
            self._ogeler, degisti = kalan, True
        if degisti:
            self._ekran_yayinla()

    async def _ekran_cevir(self, kesin: list[tuple[str | None, Satir, str]],
                           ayar: dict[str, Any]) -> dict[int, tuple[Any, str]]:
        turler = []
        for tur_ip, o, _ in kesin:
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
                   "y2": round(e.y2, 4), "metin": e.metin, "tur": e.tur}
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
