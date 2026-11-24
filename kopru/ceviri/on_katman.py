# SPDX-License-Identifier: AGPL-3.0-only
"""PROTOKOL 20.4: çeviri motorundan önce ve sonra çalışan temizlik katmanı (her motor için).

Saf işlevler; ağ ve disk yok. Sıra: (OCR düzeltme, konuşan ayırma §19.3) -> HUD süzgeci -> bölünmüş cümle
birleştirme -> bağırma (BÜYÜK HARF) düzeltme -> ad koruma -> MOTOR -> Türkçe ek uyumu -> düğme/sözlük denetimi.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from .. import dugmeler

# ---------------------------------------------------------------------------------------------------------------
# HUD: pusula, süre, para, cephane, sayaç — asla çevrilmez (§16.3'e ek)
_PUSULA = r"(?:N|S|E|W|NE|NW|SE|SW|NNE|ENE|ESE|SSE|SSW|WSW|WNW|NNW)"
_HUD_DESENLERI = [
    re.compile(rf"^{_PUSULA}(?:\s*\d{{1,3}}\s*°?)?$"),                       # N, NW, "N 245°"
    re.compile(rf"^\d{{1,3}}\s*°\s*{_PUSULA}?$"),                              # 245° NW
    re.compile(r"^[+\-]?\s*[$€£¥₺]\s*[\d.,]+\s*[KkMm]?$"),                    # $1,250  +$500  $2.5M
    re.compile(r"^[\d.,]+\s*[$€£¥₺]$"),                                       # 1.250 ₺
    re.compile(r"^\d{1,4}\s*[/|]\s*\d{1,4}$"),                                # 30/120  30 | 120
    re.compile(r"^[xX×]\s*\d{1,4}$|^\d{1,4}\s*[xX×]$"),                       # x3  3x
    re.compile(r"^\d{1,3}(?::\d{2}){1,2}(?:\.\d{1,3})?$"),                    # 02:15  1:02:33
    re.compile(r"^\d{1,3}(?:[.,]\d+)?\s*%$"),                                 # 85%
    re.compile(r"^(?:HP|MP|XP|SP|AP|LV|LVL|Lv|Lvl|Lv\.)\s*\.?\s*\d{1,6}(?:\s*/\s*\d{1,6})?$"),  # HP 100, Lv. 12
    re.compile(r"^\d{1,6}\s*(?:HP|XP|SP|AP|RP)$"),                            # 250 XP
    re.compile(r"^\d{1,4}(?:[.,]\d)?\s*(?:mi|km|m|ft|mph|km/h|kmh)$", re.IGNORECASE),  # 1.2 mi  45 mph
]


def hud_mu(metin: str) -> bool:
    """Pusula/süre/para/cephane/sayaç gibi HUD yazısı mı (çevrilmez)?"""
    t = " ".join(metin.split())
    return bool(t) and any(d.match(t) for d in _HUD_DESENLERI)


# ---------------------------------------------------------------------------------------------------------------
# Bölünmüş cümle: "I told you we should" + "never have come here."
_CUMLE_SONU = re.compile(r"[.!?…\"”)\]]\s*$|\.\.\.\s*$")
_BAGLAC = frozenset({"and", "but", "or", "so", "because", "cause", "'cause", "if", "when", "then", "than", "that",
                     "which", "who", "to", "of", "with", "for", "in", "on", "at", "the", "a", "an"})


def bolunmus_mu(onceki: str, yeni: str) -> bool:
    """İki ardışık altyazı kartı tek cümlenin parçaları mı?

    Önceki kart cümle sonu noktalamasıyla bitmiyor ve yeni kart küçük harfle (ya da bağlaçla) başlıyorsa evet.
    Virgül/kısa çizgiyle biten önceki kart da devam sayılır. Konuşmacı çizgisiyle başlayan kart ("- Who?") hayır.
    """
    a, b = onceki.strip(), yeni.strip()
    if not a or not b or _CUMLE_SONU.search(a) or b.startswith(("-", "–", "—")):
        return False
    if a.endswith((",", "-", "–", "—", ";", ":")):
        return True
    ilk = b.split()[0]
    harf = next((c for c in ilk if c.isalpha()), "")
    if not harf:
        return False
    if harf.islower():
        return True
    return ilk.strip(".,!?\"'").casefold() in _BAGLAC and ilk != "I" and not bagirma_mi(b)


def birlestir(onceki: str, yeni: str) -> str:
    """Kartları tek cümle yapar (sonda kalan kısa çizgi kelime bölmesiyse bitiştirir)."""
    a, b = onceki.rstrip(), yeni.lstrip()
    if a.endswith("-") and not a.endswith(" -") and b[:1].islower():
        return a[:-1] + b
    return f"{a} {b}"


# ---------------------------------------------------------------------------------------------------------------
# Bağırma: "GET DOWN! THEY'RE SHOOTING!" -> "Get down! They're shooting!"
KISALTMALAR = frozenset({
    "FBI", "CIA", "NSA", "DEA", "ATF", "IRS", "NYPD", "LAPD", "LSPD", "LCPD", "VCPD", "NOOSE", "FIB", "IAA", "SWAT",
    "USA", "UK", "EU", "GPS", "ATM", "SUV", "RPG", "SMG", "TV", "PC", "PS5", "PS4", "DNA",
    "NPC", "HP", "XP", "VIP", "CEO", "GTA", "RDR", "DJ", "EMS", "HQ",
})
_KELIME = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)
_CUMLE_BASI = re.compile(r"(^|[.!?…]\s+|[\"“(]\s*)([^\W\d_])")


def bagirma_mi(metin: str) -> bool:
    """Düğme belirteçleri dışındaki harflerin hepsi büyük ve en az 4 harf / 1 uzun kelime mi?"""
    kelimeler = [t for t in metin.split() if not dugmeler.dugme_mi(t)]
    harfler = [c for t in kelimeler for c in t if c.isalpha()]
    if len(harfler) < 4 or not all(c.isupper() for c in harfler):
        return False
    uzun = [w for w in _KELIME.findall(" ".join(kelimeler)) if len(w) >= 2]
    if not uzun:
        return False
    # yalnız kısaltmalardan oluşan satır ("FBI", "GPS ON") bağırma değildir
    return not all(w.upper() in KISALTMALAR for w in uzun)


def cumle_duzeni(metin: str, adlar: Iterable[str] = ()) -> str:
    """BÜYÜK HARF metni cümle düzenine çevirir; bilinen adları, kısaltmaları, düğmeleri ve "I"yı korur."""
    adharita: dict[str, str] = {}
    cok_kelimeli: list[str] = []
    for ad in adlar:
        ad = " ".join(str(ad).split())
        if not ad:
            continue
        if " " in ad:
            cok_kelimeli.append(ad)
        else:
            adharita.setdefault(ad.casefold(), ad)

    def kelime(m: re.Match[str]) -> str:
        w = m.group(0)
        if w.upper() in KISALTMALAR:
            return w.upper()
        bulunan = adharita.get(w.casefold())
        if bulunan:
            return bulunan
        k = w.lower()
        if k == "i" or k.startswith(("i'", "i’")):
            return "I" + k[1:]
        return k

    parcalar = []
    for t in re.split(r"(\s+)", metin):
        parcalar.append(t if (not t.strip() or dugmeler.dugme_mi(t)) else _KELIME.sub(kelime, t))
    sonuc = "".join(parcalar)
    for ad in cok_kelimeli:   # "VICE CITY" -> "Vice City"
        sonuc = re.sub(r"(?<!\w)" + r"\s+".join(re.escape(p) for p in ad.split()) + r"(?!\w)",
                       lambda _m, a=ad: a, sonuc, flags=re.IGNORECASE)
    return _CUMLE_BASI.sub(lambda m: m.group(1) + m.group(2).upper(), sonuc)


def bagirma_duzelt(metin: str, adlar: Iterable[str] = ()) -> tuple[str, bool]:
    """(düzeltilmiş metin, bağırma mıydı). Vurgu kalsın: sonunda noktalama yoksa "!" eklenir."""
    if not bagirma_mi(metin):
        return metin, False
    s = cumle_duzeni(metin, adlar).rstrip()
    if not re.search(r"[.!?…]\W*$", s):
        s += "!"
    return s, True


# ---------------------------------------------------------------------------------------------------------------
# Ad koruma: "Hope", "Rook", "Grace", "Dutch", "Valentine", "Mercy" hem ad hem sözcük
_AD_DISI = frozenset({
    "I", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "January", "February",
    "March", "April", "May", "June", "July", "August", "September", "October", "November", "December", "God",
    "Lord", "Mr", "Mrs", "Ms", "Dr", "Sir", "Miss", "Madam", "Ma'am", "Christmas", "English", "American", "OK",
    "Okay", "Mister", "Mom", "Dad", "Mama", "Papa", "Uncle", "Aunt", "Boss", "Captain", "Sheriff", "Officer",
    "Agent", "Detective", "Doctor", "Professor", "Hey", "Oh", "Yes", "No", "Please", "Thanks", "Sorry",
})
# Cümle başında bilinen ad gelirse ve ardından bunlardan biri gelirse sözcüktür: "Hope you're right."
_SOZCUK_ISARETI = frozenset({"you", "you're", "you'll", "we", "we're", "i", "i'm", "it", "it's", "that", "so",
                             "not", "they", "this", "there", "to", "for", "the", "a", "an", "of", "on", "me",
                             "him", "her", "us", "them"})
_BUYUK_KELIME = re.compile(r"(?<![\w'’])([A-Z][a-z]+(?:['’-][A-Za-z]+)?)(?![\w])")


def _cumle_basi_mi(metin: str, i: int) -> bool:
    once = metin[:i].rstrip(" \"“‘'(«")
    return not once or once[-1] in ".!?…:\n"


def adlari_bul(metin: str, bilinen: Iterable[str] = ()) -> list[str]:
    """Metinde ad olarak geçenler: bilinen adlar (büyük harfle ve sözcük kullanımı değilse) + cümle ortasında
    büyük harfle yazılmış (yaygın istisnalar dışında) kelimeler. Sıra korunur, tekrar yok."""
    bulunan: dict[str, int] = {}   # ad -> metindeki ilk konumu

    if bagirma_mi(metin):
        return []
    for ad in sorted({" ".join(str(a).split()) for a in bilinen if str(a).strip()}, key=len, reverse=True):
        for m in re.finditer(r"(?<![\w'’])" + re.escape(ad) + r"(?![\w])", metin):
            if _cumle_basi_mi(metin, m.start()) and " " not in ad:
                sonraki = metin[m.end():].split()
                ilk = sonraki[0].strip(".,!?;:\"'").casefold() if sonraki else ""
                if ilk in _SOZCUK_ISARETI:
                    continue
            if not any(ad in a for a in bulunan):
                bulunan[ad] = m.start()
            break
    for m in _BUYUK_KELIME.finditer(metin):
        w = m.group(1)
        if w in _AD_DISI or _cumle_basi_mi(metin, m.start()) or any(w in a.split() for a in bulunan):
            continue
        bulunan.setdefault(w, m.start())
    return sorted(bulunan, key=lambda a: bulunan[a])


# ---------------------------------------------------------------------------------------------------------------
# Türkçe ek uyumu: "Ölü Göz'yu" -> "Ölü Göz'ü", "Vice City'da" -> "Vice City'de"
_UNLU = "aeıioöuü"
_KALIN = "aıou"
_YUVARLAK = "oöuü"
_SERT = "fstkçşhp"


def _tr_kucuk(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


def _okunus(kelime: str) -> str:
    """Kaba okunuş: İngilizce adların sondaki okunmayan e'si atılır (Grace -> grac, Mike -> mik)."""
    k = _tr_kucuk(re.sub(r"[^\w]", "", kelime))
    if len(k) >= 4 and k.endswith("e") and k[-2] not in _UNLU and any(c in _UNLU for c in k[:-1]) \
            and not re.search(r"[çğışöü]", k):
        k = k[:-1]
    if len(k) >= 3 and k.endswith("y") and k[-2] not in _UNLU:   # Strawberry, Lucky: son ses "i"
        k = k[:-1] + "i"
    return k


def _son_unlu(k: str) -> str:
    for c in reversed(k):
        if c in _UNLU:
            return c
    return "e"


def ek_kur(kelime: str, ek: str) -> str:
    """`kelime`ye gelen kesmeli eki (belirtme, yönelme, bulunma, ayrılma, ilgi, vasıta, çoğul) ses uyumuna göre
    yeniden kurar. Tanınmayan ek aynen döner. Büyük harfli ek büyük harfle döner."""
    son = kelime.split()[-1] if kelime.split() else kelime
    k = _okunus(son)
    if not k:
        return ek
    unlu = _son_unlu(_tr_kucuk(re.sub(r"[^\w]", "", son)))   # ünlü yazılıştan, son ses okunuştan
    kalin = unlu in _KALIN
    yuv = unlu in _YUVARLAK
    unluyle = k[-1] in _UNLU
    sert = k[-1] in _SERT
    iki = "a" if kalin else "e"
    dort = ("u" if kalin else "ü") if yuv else ("ı" if kalin else "i")
    e = _tr_kucuk(ek)
    buyuk = ek.isupper()
    yeni: str | None = None
    if re.fullmatch(r"y?[ıiuü]", e):                       # belirtme
        yeni = ("y" if unluyle else "") + dort
    elif re.fullmatch(r"n?[ıiuü]n", e):                    # ilgi
        yeni = ("n" if unluyle else "") + dort + "n"
    elif re.fullmatch(r"y?[ae]", e):                        # yönelme
        yeni = ("y" if unluyle else "") + iki
    elif m := re.fullmatch(r"[dt][ae](ki|n)?", e):          # bulunma (+ki) / ayrılma
        yeni = ("t" if sert else "d") + iki + (m.group(1) or "")
    elif re.fullmatch(r"y?l[ae]", e):                       # vasıta
        yeni = ("y" if unluyle else "") + "l" + iki
    elif re.fullmatch(r"l[ae]r", e):                        # çoğul
        yeni = "l" + iki + "r"
    if yeni is None:
        return ek
    return yeni.replace("i", "İ").upper() if buyuk else yeni


def ek_duzelt(metin: str, terimler: Iterable[str]) -> str:
    """Metinde geçen terimlerin (sözlük karşılıkları, korunan adlar) kesmeli eklerini uyumlu hâle getirir."""
    for t in sorted({str(x).strip() for x in terimler if str(x).strip()}, key=len, reverse=True):
        metin = re.sub(r"(?<![\w])(" + re.escape(t) + r")(['’])([^\W\d_]{1,5})(?![\w])",
                       lambda m: m.group(1) + m.group(2) + ek_kur(m.group(1), m.group(3)), metin)
    return metin
