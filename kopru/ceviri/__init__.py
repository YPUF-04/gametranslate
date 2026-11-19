# SPDX-License-Identifier: AGPL-3.0-only
"""Çeviri motorları."""
from __future__ import annotations

from typing import Any

from .. import anahtarlar
from .claude import ClaudeMotoru
from .deepl import DeepLMotoru
from .deepseek import DeepSeekMotoru
from .gemini import ESKI_MODELLER as ESKI_GEMINI, GeminiMotoru
from .sahte import SahteMotor
from .temel import CeviriMotoru
from .yerel import YerelMotor

BILGI = [
    ("claude", "Claude", True, False, False),
    ("gemini", "Gemini", True, False, True),
    ("deepseek", "DeepSeek", True, False, False),
    ("deepl", "DeepL", True, False, True),
    ("yerel", "Çevrimdışı (yerel)", False, True, True),
]


# kalite -> model (bkz. PROTOKOL 6.5). Gemini'de kalite yalnız Flash'ı seçer.
KALITE_MODEL = {
    "claude": {"en_iyi": "claude-opus-5-5", "dengeli": "claude-sonnet-5-5",
               "hizli": "claude-haiku-5-5"},
    "gemini": {"en_iyi": "gemini-3.8-flash", "dengeli": "gemini-3.8-flash",
               "hizli": "gemini-3.5-flash-lite"},
    "deepseek": {"en_iyi": "deepseek-chat", "dengeli": "deepseek-chat", "hizli": "deepseek-chat"},
}
# Eski sürümler bu değerleri ayar dosyasına varsayılan diye yazdı; seçim sayılmaz.
ESKI_VARSAYILAN = {"claude": {"claude-opus-5-5"}, "gemini": set(ESKI_GEMINI),
                   "deepseek": {"deepseek-chat"}}


def model_sec(kod: str, ayar: dict[str, Any]) -> str:
    """Açıkça yazılmış `modeller` değeri kalite modunu ezer; yoksa kalite seçer."""
    ozel = (ayar.get("modeller") or {}).get(kod)
    if isinstance(ozel, str) and ozel.strip() and ozel.strip() not in ESKI_VARSAYILAN.get(kod, ()):
        return ozel.strip()
    tablo = KALITE_MODEL.get(kod, {})
    return tablo.get(ayar.get("kalite") or "en_iyi", tablo.get("en_iyi", ""))


def motor_olustur(kod: str, ayar: dict[str, Any]) -> CeviriMotoru:
    if kod == "claude":
        return ClaudeMotoru(anahtarlar.oku("claude"), model_sec("claude", ayar))
    if kod == "gemini":
        return GeminiMotoru(anahtarlar.oku("gemini"), model_sec("gemini", ayar))
    if kod == "deepseek":
        return DeepSeekMotoru(anahtarlar.oku("deepseek"), model_sec("deepseek", ayar))
    if kod == "deepl":
        return DeepLMotoru(anahtarlar.oku("deepl"))
    if kod == "sahte":
        return SahteMotor()
    return YerelMotor()
