# SPDX-License-Identifier: AGPL-3.0-only
"""Çeviri motorları."""
from __future__ import annotations

from typing import Any

from .. import anahtarlar
from .claude import ClaudeMotoru
from .deepl import DeepLMotoru
from .deepseek import DeepSeekMotoru
from .gemini import GeminiMotoru
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


def motor_olustur(kod: str, ayar: dict[str, Any]) -> CeviriMotoru:
    modeller = ayar.get("modeller", {})
    if kod == "claude":
        return ClaudeMotoru(anahtarlar.oku("claude"), modeller.get("claude", "claude-opus-5-5"))
    if kod == "gemini":
        return GeminiMotoru(anahtarlar.oku("gemini"), modeller.get("gemini", "gemini-2.5-flash"))
    if kod == "deepseek":
        return DeepSeekMotoru(anahtarlar.oku("deepseek"), modeller.get("deepseek", "deepseek-chat"))
    if kod == "deepl":
        return DeepLMotoru(anahtarlar.oku("deepl"))
    if kod == "sahte":
        return SahteMotor()
    return YerelMotor()
