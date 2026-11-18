# SPDX-License-Identifier: AGPL-3.0-only
"""Paylaşılabilir çeviri paketi (.akpaket = zip). Yalnız metin çiftleri; kişisel veri yok."""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from . import oyunlar, sozluk as sozluk_mod
from .hafiza import Hafiza

AZAMI_BAYT = 50 * 1024 * 1024        # sıkıştırılmış dosya
AZAMI_ACIK = 50 * 1024 * 1024        # açılmış toplam
DOSYALAR = ("oyun.json", "sozluk.json", "hafiza.json")
AZAMI_KAYIT = 500_000
SURUM = 1


class PaketHatasi(Exception):
    """kod: metinler.py'deki hata kodu (paket_gecersiz | paket_buyuk)."""

    def __init__(self, kod: str = "paket_gecersiz") -> None:
        super().__init__(kod)
        self.kod = kod


@dataclass
class Paket:
    bilgi: dict[str, Any]
    terimler: list[dict[str, str]] = field(default_factory=list)
    kayitlar: list[tuple[str, str]] = field(default_factory=list)


def olustur(bilgi: dict[str, Any], terimler: list[dict[str, str]],
            hafiza_satirlari: list[dict[str, Any]]) -> bytes:
    """Yalnız metin çiftlerini paketler (sayaç, motor, tarih, anahtar vb. YOK)."""
    oyun = {"surum": SURUM, "kod": bilgi.get("kod", ""), "ad": bilgi.get("ad", ""),
            "aciklama": bilgi.get("aciklama", ""), "hitap": bilgi.get("hitap", "sen"),
            "karakterler": bilgi.get("karakterler", []), "olusturma": date.today().isoformat()}
    hafiza = {"kayitlar": [{"asil": r["asil"], "ceviri": r["ceviri"]} for r in hafiza_satirlari]}
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        for ad, veri in (("oyun.json", oyun), ("sozluk.json", {"terimler": terimler}),
                         ("hafiza.json", hafiza)):
            z.writestr(ad, json.dumps(veri, ensure_ascii=False))
    return tampon.getvalue()


def _metin(v: Any, azami: int, bos_olur: bool = False) -> str:
    if not isinstance(v, str) or len(v) > azami or (not bos_olur and not v.strip()):
        raise PaketHatasi()
    return v


def _json_oku(z: zipfile.ZipFile, ad: str, kalan: list[int]) -> Any:
    with z.open(ad) as f:
        ham = f.read(kalan[0] + 1)
    kalan[0] -= len(ham)
    if kalan[0] < 0:
        raise PaketHatasi("paket_buyuk")
    try:
        return json.loads(ham.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise PaketHatasi() from None


def oku(veri: bytes) -> Paket:
    """Doğrular ve okur. Beklenmeyen her şey PaketHatasi."""
    if len(veri) > AZAMI_BAYT:
        raise PaketHatasi("paket_buyuk")
    try:
        z = zipfile.ZipFile(io.BytesIO(veri))
    except zipfile.BadZipFile:
        raise PaketHatasi() from None
    with z:
        bilgiler = z.infolist()
        adlar = [i.filename for i in bilgiler]
        # yalnız beklenen düz dosya adları (yol ayracı, "..", mutlak yol, klasör yok)
        if len(set(adlar)) != len(adlar) or any(a not in DOSYALAR for a in adlar) \
                or "oyun.json" not in adlar:
            raise PaketHatasi()
        if any(i.flag_bits & 0x1 for i in bilgiler):  # şifreli
            raise PaketHatasi()
        if sum(i.file_size for i in bilgiler) > AZAMI_ACIK:
            raise PaketHatasi("paket_buyuk")
        kalan = [AZAMI_ACIK]
        try:
            oyun = _json_oku(z, "oyun.json", kalan)
            sozluk = _json_oku(z, "sozluk.json", kalan) if "sozluk.json" in adlar else {}
            hafiza = _json_oku(z, "hafiza.json", kalan) if "hafiza.json" in adlar else {}
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError):
            raise PaketHatasi() from None
    return _dogrula(oyun, sozluk, hafiza)


def _dogrula(oyun: Any, sozluk: Any, hafiza: Any) -> Paket:
    if not all(isinstance(x, dict) for x in (oyun, sozluk, hafiza)):
        raise PaketHatasi()
    ad = _metin(oyun.get("ad"), 100).strip()
    hitap = oyun.get("hitap", "sen")
    if hitap not in ("sen", "siz"):
        raise PaketHatasi()
    karakterler = oyun.get("karakterler", [])
    if not isinstance(karakterler, list) or len(karakterler) > 200:
        raise PaketHatasi()
    temiz_k = []
    for k in karakterler:
        if not isinstance(k, dict) or k.get("cinsiyet", "") not in ("k", "e", "", None):
            raise PaketHatasi()
        temiz_k.append({"ad": _metin(k.get("ad"), 60).strip(), "cinsiyet": k.get("cinsiyet") or ""})
    bilgi = {"ad": ad, "aciklama": _metin(oyun.get("aciklama", ""), 2000, True),
             "hitap": hitap, "karakterler": temiz_k}
    terimler_ham = sozluk.get("terimler", [])
    if not isinstance(terimler_ham, list) or len(terimler_ham) > 20_000:
        raise PaketHatasi()
    terimler = []
    for t in terimler_ham:
        if not isinstance(t, dict):
            raise PaketHatasi()
        asil = _metin(t.get("asil"), 200).strip()
        terimler.append({"asil": asil, "ceviri": _metin(t.get("ceviri", asil), 200).strip() or asil})
    kayit_ham = hafiza.get("kayitlar", [])
    if not isinstance(kayit_ham, list) or len(kayit_ham) > AZAMI_KAYIT:
        raise PaketHatasi()
    kayitlar = []
    for r in kayit_ham:
        if not isinstance(r, dict):
            raise PaketHatasi()
        kayitlar.append((_metin(r.get("asil"), 1000), _metin(r.get("ceviri"), 1000)))
    return Paket(bilgi, terimler, kayitlar)


def uygula(paket: Paket, aktif: Hafiza | None = None,
           izin: Callable[[], bool] = lambda: False) -> tuple[str, int, int, bool]:
    """Paketi oyuna işler: (oyun_kodu, eklenen, atlanan, kalici).

    Oyun adı koda çevrilir (paketteki "kod" alanına güvenilmez). Kullanıcının kendi
    düzeltmeleri ve sözlük girdileri ezilmez. Hedef aktif oyunsa `aktif` hafıza
    kullanılır, değilse geçici açılır. İzin yoksa hafıza yalnız RAM'dedir (kalici=False).
    """
    kod = oyunlar.kod_uret(paket.bilgi["ad"])
    if not oyunlar.var_mi(kod):
        kod = oyunlar.olustur(paket.bilgi["ad"], paket.bilgi["aciklama"],
                              paket.bilgi["hitap"], paket.bilgi["karakterler"])
    mevcut = sozluk_mod.yukle(kod)
    var = {t["asil"].casefold() for t in mevcut}
    yeni = [t for t in paket.terimler if t["asil"].casefold() not in var]
    if yeni:
        sozluk_mod.kaydet(kod, mevcut + yeni)
    gecici = aktif is None or aktif.kod != kod
    h = Hafiza(kod, izin) if gecici else aktif
    try:
        eklenen, atlanan = h.kaydet_cok(paket.kayitlar, "paket")
        kalici = h.kalici_mi()
    finally:
        if gecici:
            h.kapat()
    return kod, eklenen, atlanan, kalici
