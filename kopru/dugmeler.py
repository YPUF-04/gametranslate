# SPDX-License-Identifier: AGPL-3.0-only
"""Düğme simgeleri (PROTOKOL §16.2) ve okuma gürültüsü süzgeci (§16.3). Saf işlevler; çeviriden önce çalışır."""
from __future__ import annotations

import re
import unicodedata

# OCR'ın PlayStation simgelerini sık okuduğu biçimler -> doğru simge (yalnız tek başına duran belirteçte)
YANLIS_OKUMA = {"×": "✕", "✖": "✕", "⨯": "✕", "®": "○", "©": "○", "◯": "○", "⭘": "○", "@": "○",
                "Δ": "△", "▵": "△", "◻": "□", "▢": "□", "☐": "□"}
PS_SIMGE = "✕○△□"
OKLAR = "←→↑↓◀▶▲▼⬅➡⬆⬇"
DUGME_ADLARI = frozenset({"L1", "L2", "L3", "R1", "R2", "R3", "OPTIONS", "CREATE", "SHARE", "PS",
                          "LB", "RB", "LT", "RT", "LS", "RS"})
_PARANTEZLI = re.compile(r"^(?:\[[A-Za-z0-9]{1,6}\]|<[A-Za-z0-9]{1,6}>|\([A-Z0-9]\))$")
_UC_NOKTALAMA = ".,:;!?"
# kelime içinde de kalan noktalama ve semboller (emoji/piktogram ve süs simgeleri DEĞİL)
_IZINLI = set(".,!?;:'\"-–—…()%/&+#’‘“”«»¡¿*[]<>_$€£¥₺")
_TEK_IZINLI = {"-", "–", "—", "…", "...", "&", "/", "+"}
_SAYISAL = re.compile(r"^[\d\s:.,/%+\-xX×]*$")
_SIL = {0x200D, 0x20E3} | set(range(0xFE00, 0xFE10)) | set(range(0x1F3FB, 0x1F400))


def _govde(t: str) -> tuple[str, str, str]:
    """Belirteci baş/son noktalamadan ayırır: ("(", "✕", ":")."""
    i, j = 0, len(t)
    while i < j and t[i] in "\"'“‘«":
        i += 1
    while j > i and t[j - 1] in _UC_NOKTALAMA + "\"'”’»":
        j -= 1
    return t[:i], t[i:j], t[j:]


_EK = re.compile(r"^(.+?)['’][^\W\d_]{1,5}$")


def belirtec(t: str) -> str | None:
    """`t` (boşluksuz parça) bir düğme belirteciyse normalize hâlini döndürür, değilse None.
    Türkçe ek almış belirteç de sayılır ("✕'e", "R2'ye")."""
    _, g, _ = _govde(t)
    if not g:
        return None
    m = _EK.match(g)
    if m and _belirtec(m.group(1)):
        return _belirtec(m.group(1))
    return _belirtec(g)


def _belirtec(g: str) -> str | None:
    if len(g) == 1 and (g in PS_SIMGE or g in OKLAR):
        return g
    if len(g) == 1 and g in YANLIS_OKUMA:
        return YANLIS_OKUMA[g]
    if g in DUGME_ADLARI:
        return g
    if _PARANTEZLI.match(g):
        ic = g[1:-1]
        if len(ic) == 1 and ic in YANLIS_OKUMA:
            return g[0] + YANLIS_OKUMA[ic] + g[-1]
        return g
    if len(g) == 3 and g[0] in "[(<" and g[2] in "])>" and (g[1] in PS_SIMGE or g[1] in YANLIS_OKUMA):
        return g[0] + YANLIS_OKUMA.get(g[1], g[1]) + g[2]
    return None


def dugme_mi(t: str) -> bool:
    return belirtec(t) is not None


def _karakter_kalir(c: str) -> bool:
    if ord(c) in _SIL:
        return False
    k = unicodedata.category(c)
    if k[0] in "LNM":
        return not (k == "Mn" and 0xFE00 <= ord(c) <= 0xFE0F)
    return c in _IZINLI


def _parca_temizle(t: str) -> str:
    """Düğme olmayan parçadan emoji/simgeleri atar; yalnız noktalamadan oluşan yığınları siler."""
    b = belirtec(t)
    if b is not None:
        on, _, son = _govde(t)
        return on + b + son
    s = "".join(c for c in t if _karakter_kalir(c))
    if not s:
        return ""
    if not any(c.isalnum() for c in s):
        return s if s in _TEK_IZINLI else ""
    return s


def temizle(metin: str) -> str:
    """§16.3: emoji, piktogram, süs simgeleri ve simge yığınları silinir; harf, rakam, noktalama ve
    düğme belirteçleri (normalize edilmiş) kalır. Boşluklar teklenir."""
    parcalar = [_parca_temizle(t) for t in (metin or "").split()]
    return " ".join(p for p in parcalar if p)


def dugmeleri_ayir(metin: str) -> tuple[list[str], list[str]]:
    """(düğme belirteçleri, kalan parçalar)."""
    d, k = [], []
    for t in metin.split():
        (d if dugme_mi(t) else k).append(t)
    return d, k


def gurultu_mu(metin: str) -> bool:
    """§16.3: temizlenmiş satır çevrilmeye değmez mi? (az harf, çoğu rakam/simge, yalnız sayı/süre/koordinat,
    yalnız düğme simgeleri)."""
    dugmeler_, kalan = dugmeleri_ayir(metin)
    govde = "".join(kalan)
    if not govde:
        return True
    harf = sum(1 for c in govde if c.isalpha())
    if harf < 2 or harf / len(govde) < 0.5:
        return True
    return bool(_SAYISAL.match(" ".join(kalan)))


def dugme_koru(asil: str, ceviri: str) -> str:
    """Kaynaktaki düğme belirteçleri çeviride yoksa kaynaktaki yerine göre başa ya da sona eklenir (§16.2)."""
    kaynak = asil.split()
    var = [belirtec(t) for t in ceviri.split()]
    sayac: dict[str, int] = {}
    for b in var:
        if b:
            sayac[b] = sayac.get(b, 0) + 1
    bas, son = [], []
    for i, t in enumerate(kaynak):
        b = belirtec(t)
        if not b:
            continue
        if sayac.get(b, 0) > 0:
            sayac[b] -= 1
            continue
        (bas if i < len(kaynak) / 2 else son).append(b)
    if not bas and not son:
        return ceviri
    return " ".join(bas + [ceviri.strip()] + son).strip()


def uc_belirtecleri(metin: str) -> tuple[str | None, str | None]:
    """Satırın başındaki ve sonundaki düğme belirteci (yoksa None)."""
    p = metin.split()
    if not p:
        return None, None
    ilk = belirtec(p[0])
    sonuncu = belirtec(p[-1]) if len(p) > 1 else None
    return ilk, sonuncu


def uctan_cikar(metin: str, bas: str | None, son: str | None) -> str:
    """Örtünün dışında kalan uç simgeyi çevirinin aynı ucundan çıkarır (gerçek simge görünür, ikinci kez yazılmaz)."""
    p = metin.split()
    if bas and p and belirtec(p[0]) == bas:
        p = p[1:]
    if son and p and belirtec(p[-1]) == son:
        p = p[:-1]
    return " ".join(p) if p else metin
