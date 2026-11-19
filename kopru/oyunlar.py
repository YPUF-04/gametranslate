# SPDX-License-Identifier: AGPL-3.0-only
"""Oyun kayıt defteri: <ayar_dizini>/oyunlar/<kod>/ (oyun.json, sozluk.json, hafiza.sqlite)."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

from . import ayarlar

VARSAYILAN_KOD = "varsayilan"
_KOD = re.compile(r"[a-z0-9]{1,40}")
_TR = str.maketrans({"ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i", "I": "i",
                     "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u"})


def kod_uret(ad: str) -> str:
    """Oyun adından kod: Türkçe harfler ASCII'ye, harf/rakam dışı atılır ("GTA 6" -> "gta6")."""
    s = str(ad).translate(_TR)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]", "", s)[:40]
    return s or "oyun"


def gecerli_kod(kod: Any) -> bool:
    return isinstance(kod, str) and bool(_KOD.fullmatch(kod))


def kod_coz(oyun: str) -> str:
    """Zaten geçerli bir kodsa aynen, değilse addan üretir (eski ayarlar için)."""
    return oyun if gecerli_kod(oyun) else kod_uret(oyun or VARSAYILAN_KOD)


def kok() -> Path:
    return ayarlar.ayar_dizini() / "oyunlar"


def oyun_dizini(kod: str) -> Path:
    if not gecerli_kod(kod):
        raise ValueError("gecersiz oyun kodu")
    return kok() / kod


def sozluk_yolu(kod: str) -> Path:
    return oyun_dizini(kod) / "sozluk.json"


def _yaz_json(yol: Path, veri: Any) -> None:
    ayarlar.atomik_yaz(yol, json.dumps(veri, ensure_ascii=False, indent=2))


def _temiz_karakterler(k: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if isinstance(k, list):
        for e in k[:200]:
            if isinstance(e, dict) and isinstance(e.get("ad"), str) and e["ad"].strip():
                c = e.get("cinsiyet")
                out.append({"ad": e["ad"].strip()[:60], "cinsiyet": c if c in ("k", "e") else ""})
    return out


def varsayilan_bilgi(kod: str, ad: str | None = None) -> dict[str, Any]:
    return {"kod": kod, "ad": ad or kod, "aciklama": "", "hitap": "sen", "karakterler": [],
            "olusturma": date.today().isoformat()}


def var_mi(kod: str) -> bool:
    return kod == VARSAYILAN_KOD or (gecerli_kod(kod) and oyun_dizini(kod).is_dir())


def oku(kod: str) -> dict[str, Any] | None:
    """oyun.json (yoksa ama klasör varsa varsayılan bilgi); oyun yoksa None."""
    if not var_mi(kod):
        return None
    bilgi = varsayilan_bilgi(kod, "Varsayılan" if kod == VARSAYILAN_KOD else None)
    try:
        v = json.loads((oyun_dizini(kod) / "oyun.json").read_text(encoding="utf-8"))
        if isinstance(v, dict):
            bilgi.update({k: v[k] for k in ("ad", "aciklama", "hitap", "olusturma", "son_oynama")
                          if isinstance(v.get(k), str)})
            bilgi["karakterler"] = _temiz_karakterler(v.get("karakterler"))
    except (OSError, ValueError):
        pass
    if bilgi.get("hitap") not in ("sen", "siz"):
        bilgi["hitap"] = "sen"
    bilgi["kod"] = kod
    return bilgi


def _kaydet_bilgi(kod: str, bilgi: dict[str, Any]) -> None:
    _yaz_json(oyun_dizini(kod) / "oyun.json", bilgi)


def olustur(ad: str, aciklama: str = "", hitap: str = "sen",
            karakterler: Any = None) -> str:
    """Yeni oyun (kullanıcı eylemi). Aynı kod varsa 2, 3... eklenir."""
    taban = kod_uret(ad)
    kod, n = taban, 1
    while var_mi(kod) or kod == VARSAYILAN_KOD:
        n += 1
        kod = f"{taban[:37]}{n}"
    bilgi = varsayilan_bilgi(kod, ad.strip()[:100])
    bilgi.update({"aciklama": aciklama.strip()[:2000], "hitap": hitap,
                  "karakterler": _temiz_karakterler(karakterler)})
    _kaydet_bilgi(kod, bilgi)
    return kod


def guncelle(kod: str, kismi: dict[str, Any]) -> dict[str, Any] | None:
    bilgi = oku(kod)
    if bilgi is None:
        return None
    if isinstance(kismi.get("ad"), str) and kismi["ad"].strip():
        bilgi["ad"] = kismi["ad"].strip()[:100]
    if isinstance(kismi.get("aciklama"), str):
        bilgi["aciklama"] = kismi["aciklama"].strip()[:2000]
    if kismi.get("hitap") in ("sen", "siz"):
        bilgi["hitap"] = kismi["hitap"]
    if "karakterler" in kismi:
        bilgi["karakterler"] = _temiz_karakterler(kismi["karakterler"])
    _kaydet_bilgi(kod, bilgi)
    return bilgi


def oynandi_isaretle(kod: str) -> None:
    """Son oynama tarihini yazar (yalnız oyun klasörü zaten varsa)."""
    if kod != VARSAYILAN_KOD and not var_mi(kod):
        return
    bilgi = oku(kod)
    if bilgi:
        bilgi["son_oynama"] = date.today().isoformat()
        _kaydet_bilgi(kod, bilgi)


def kodlari_listele() -> list[str]:
    kodlar = {VARSAYILAN_KOD}
    try:
        for p in kok().iterdir():
            if p.is_dir() and gecerli_kod(p.name):
                kodlar.add(p.name)
    except OSError:
        pass
    return sorted(kodlar)


def goc_et() -> int:
    """Eski sozlukler/<oyun>.json dosyalarını oyunlar/<kod>/sozluk.json'a taşır."""
    eski = ayarlar.ayar_dizini() / "sozlukler"
    tasinan = 0
    try:
        dosyalar = sorted(eski.glob("*.json"))
    except OSError:
        return 0
    for p in dosyalar:
        try:
            ad = json.loads(p.read_text(encoding="utf-8")).get("oyun") or p.stem
        except (OSError, ValueError, AttributeError):
            ad = p.stem
        kod = kod_coz(str(ad))
        hedef = sozluk_yolu(kod)
        if hedef.exists():
            continue
        try:
            hedef.parent.mkdir(parents=True, exist_ok=True)
            p.replace(hedef)
            tasinan += 1
            if not (hedef.parent / "oyun.json").exists() and kod != VARSAYILAN_KOD:
                _kaydet_bilgi(kod, varsayilan_bilgi(kod, str(ad)))
        except OSError:
            continue
    try:
        eski.rmdir()  # boşsa kalkar
    except OSError:
        pass
    return tasinan
