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
    "asil_goster": False, "ekran_cevir": True,
}

VARSAYILAN: dict[str, Any] = {
    "arayuz_dili": "tr",
    "hedef_dil": "tr",
    "kaynak_dil": "otomatik",
    "motor": "gemini",
    "yedek_motor": "yerel",
    "modeller": {"claude": "claude-opus-5-5", "gemini": "gemini-2.5-flash",
                 "deepseek": "deepseek-chat"},
    "kaynak": "ekran:1",
    "bolge_altyazi": {"x": 0.1, "y": 0.72, "g": 0.8, "y2": 0.25},
    "ekrani_cevir": True,
    "kisa_aciklama": True,
    "ses_cevir": False,
    "kapi": 8642,
    "aktif_oyun": "varsayilan",
    "gorunum": VARSAYILAN_GORUNUM,
}


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
