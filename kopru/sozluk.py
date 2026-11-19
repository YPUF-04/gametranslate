# SPDX-License-Identifier: AGPL-3.0-only
"""Oyun sözlüğü: terimleri motora talimat olarak verir, yer tutucuyla korur."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import ayarlar, oyunlar


def yol(oyun: str) -> Path:
    """oyunlar/<kod>/sozluk.json (oyun adı da verilebilir; koda çevrilir)."""
    return oyunlar.sozluk_yolu(oyunlar.kod_coz(oyun))


def yukle(oyun: str) -> list[dict[str, str]]:
    try:
        veri = json.loads(yol(oyun).read_text(encoding="utf-8"))
        return [{"asil": str(t["asil"]), "ceviri": str(t.get("ceviri", t["asil"]))}
                for t in veri.get("terimler", []) if t.get("asil")]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return []


def kaydet(oyun: str, terimler: list[dict[str, str]]) -> None:
    p = yol(oyun)
    temiz = [{"asil": str(t["asil"]).strip(), "ceviri": str(t.get("ceviri", t["asil"])).strip()}
             for t in terimler if str(t.get("asil", "")).strip()]
    ayarlar.atomik_yaz(p, json.dumps({"oyun": oyunlar.kod_coz(oyun), "terimler": temiz},
                                     ensure_ascii=False, indent=2))


def sozluk_dict(terimler: list[dict[str, str]]) -> dict[str, str]:
    return {t["asil"]: t["ceviri"] for t in terimler}


def _yer(i: int) -> str:
    return f"[[T{i}]]"


def koru(metin: str, sozluk: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Terimleri yer tutucuyla değiştirir (talimat alamayan motorlar için)."""
    harita: dict[str, str] = {}
    # uzun terimler önce
    for i, (asil, ceviri) in enumerate(sorted(sozluk.items(), key=lambda kv: -len(kv[0]))):
        desen = re.compile(r"(?<!\w)" + re.escape(asil) + r"(?!\w)", re.IGNORECASE)
        if desen.search(metin):
            yer = _yer(i)
            metin = desen.sub(yer, metin)
            harita[yer] = ceviri
    return metin, harita


def geri_koy(metin: str, harita: dict[str, str]) -> str:
    for yer, ceviri in harita.items():
        # motorlar bazen boşluk ekler: [[ T0 ]]
        num = yer[3:-2]
        metin = re.sub(r"\[\[\s*T" + num + r"\s*\]\]", lambda _m, c=ceviri: c, metin)
    return metin


def son_kontrol(asil: str, ceviri: str, sozluk: dict[str, str]) -> str:
    """Çeviride terim asıl haliyle kalmış ve karşılığı farklıysa değiştirir."""
    for a, c in sozluk.items():
        if a != c and re.search(r"(?<!\w)" + re.escape(a) + r"(?!\w)", ceviri):
            ceviri = re.sub(r"(?<!\w)" + re.escape(a) + r"(?!\w)", lambda _m, x=c: x, ceviri)
    return ceviri
