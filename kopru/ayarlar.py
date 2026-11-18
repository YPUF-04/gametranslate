# SPDX-License-Identifier: AGPL-3.0-only
"""Ayar dosyasını okur/yazar (anahtarlar burada TUTULMAZ)."""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

VARSAYILAN_GORUNUM: dict[str, Any] = {
    "yazi_boyutu": 44, "konum": "alt", "kenar_bosluk": 0.08, "arka_plan": 0.55,
    "yazi_rengi": "#FFFFFF", "konusan_rengi": "#FFD166",
    "asil_goster": False, "ekran_cevir": True, "onceki_goster": True,
}

VARSAYILAN: dict[str, Any] = {
    "arayuz_dili": "tr",
    "hedef_dil": "tr",
    "kaynak_dil": "otomatik",
    "motor": "gemini",
    "yedek_motor": "yerel",
    "modeller": {},          # boş = `kalite` modeli seçer; yazılan model kaliteyi ezer
    "kalite": "en_iyi",      # en_iyi | dengeli | hizli
    "hafiza_izni": None,     # None (sorulmadı) | True | False
    "guncelleme_denetle": True,  # günde en çok bir kez GitHub'a "yeni sürüm var mı" diye sorar

    "kaynak": "ekran:1",
    "bolge_altyazi": {"x": 0.1, "y": 0.72, "g": 0.8, "y2": 0.25},
    "bolgeler": [],  # boş = otomatik; doluysa yalnız bu kareler okunur (en çok 3, PROTOKOL 7.1)
    "ekrani_cevir": True,
    "kisa_aciklama": True,
    "ses_cevir": False,
    "kapi": 8642,
    "aktif_oyun": "varsayilan",
    "kurulum_tamam": False,
    "cihaz": None,   # ps5 | xbox | pc | kart
    "tv": None,      # lg | samsung | androidtv | yok
    "gorunum": VARSAYILAN_GORUNUM,
}


BOLGE_TURLERI = ("altyazi", "ust_yazi", "diger")
EN_COK_BOLGE = 3
EN_KUCUK_GENISLIK = 0.03
EN_KUCUK_YUKSEKLIK = 0.02
_BOLGE_AD = {"altyazi": "Altyazı", "ust_yazi": "Üstteki yazılar", "diger": "Diğer"}


def _oran(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1


def bolge_gecerli(b: Any) -> bool:
    """Tek bölge: 0-1 oranlar, ekran içinde, en küçük boyutun üstünde, türü bilinen, adı en çok 30 karakter."""
    if not isinstance(b, dict) or not all(_oran(b.get(f)) for f in ("x", "y", "g", "y2")):
        return False
    if b["g"] < EN_KUCUK_GENISLIK or b["y2"] < EN_KUCUK_YUKSEKLIK:
        return False
    if b["x"] + b["g"] > 1.0001 or b["y"] + b["y2"] > 1.0001:
        return False
    if b.get("tur") not in BOLGE_TURLERI:
        return False
    ad = b.get("ad", "")
    return isinstance(ad, str) and len(ad) <= 30


def bolgeler_gecerli(v: Any) -> bool:
    return isinstance(v, list) and len(v) <= EN_COK_BOLGE and all(bolge_gecerli(b) for b in v)


def bolgeleri_temizle(v: Any) -> list[dict[str, Any]]:
    """Geçerli bölgeleri yalnız bilinen alanlarla döndürür (bozuk kayıt sessizce atılır)."""
    if not isinstance(v, list):
        return []
    out = []
    for b in v[:EN_COK_BOLGE]:
        if bolge_gecerli(b):
            out.append({"x": float(b["x"]), "y": float(b["y"]), "g": float(b["g"]), "y2": float(b["y2"]),
                        "tur": b["tur"], "ad": b.get("ad") or _BOLGE_AD[b["tur"]]})
    return out


def ayar_dizini() -> Path:
    """İşletim sistemine göre ayar klasörü (KOPRU_AYAR_DIZINI öncelikli)."""
    ozel = os.environ.get("KOPRU_AYAR_DIZINI")
    if ozel:
        return Path(ozel)
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / "AltyaziKoprusu"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AltyaziKoprusu"
    taban = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(taban) / "altyazikoprusu"


def _birlestir(taban: dict[str, Any], ek: dict[str, Any]) -> dict[str, Any]:
    """İç içe sözlükleri birleştirir; bilinmeyen üst alanlar korunur."""
    sonuc = copy.deepcopy(taban)
    for k, v in ek.items():
        if isinstance(v, dict) and isinstance(sonuc.get(k), dict):
            sonuc[k] = _birlestir(sonuc[k], v)
        else:
            sonuc[k] = v
    return sonuc


def yukle() -> dict[str, Any]:
    yol = ayar_dizini() / "ayarlar.json"
    try:
        okunan = json.loads(yol.read_text(encoding="utf-8"))
        if not isinstance(okunan, dict):
            okunan = {}
    except (OSError, ValueError):
        okunan = {}
    return _birlestir(VARSAYILAN, okunan)


def kaydet(ayar: dict[str, Any]) -> None:
    """Atomik yazım: geçici dosya + os.replace."""
    dizin = ayar_dizini()
    dizin.mkdir(parents=True, exist_ok=True)
    fd, gecici = tempfile.mkstemp(dir=dizin, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(ayar, f, ensure_ascii=False, indent=2)
        os.replace(gecici, dizin / "ayarlar.json")
    except BaseException:
        try:
            os.unlink(gecici)
        except OSError:
            pass
        raise


def guncelle(ayar: dict[str, Any], kismi: dict[str, Any]) -> dict[str, Any]:
    """Gelen alanları birleştirir (yalnız bilinen üst alanlar), kaydeder."""
    bilinen = {k: v for k, v in kismi.items() if k in VARSAYILAN}
    yeni = _birlestir(ayar, bilinen)
    kaydet(yeni)
    return yeni
