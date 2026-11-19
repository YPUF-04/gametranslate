# SPDX-License-Identifier: AGPL-3.0-only
"""Oyun bilgisi hazırlama (PROTOKOL 12.3): oyunun adından kısa açıklama, hitap ve terim sözlüğü önerisi.

LLM motoru (Gemini/Claude/DeepSeek) `serbest_istem(sistem, kullanici) -> str` ile çağrılır; yanıt doğrulanır ve
temizlenir. Sonuç YALNIZ öneridir: kullanıcı onaylayınca `birlestir` ile sözlüğe işlenir.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

EN_COK_ACIKLAMA = 200
EN_AZ_TERIM, EN_COK_TERIM = 20, 80
EN_COK_TERIM_UZUNLUK = 60

SISTEM = (
    "You prepare reference data for a game-subtitle translator (English -> Turkish).\n"
    "Given the name of a video game (and maybe an existing description), reply with ONE JSON object and nothing else:\n"
    '{"aciklama": string, "hitap": "sen" | "siz", "terimler": [{"asil": string, "ceviri": string}]}\n'
    "Rules:\n"
    "- aciklama: at most 200 characters, Turkish, plain factual sentence(s) about the game's setting and tone.\n"
    '- hitap: "sen" if characters mostly speak informally, "siz" if the tone is formal/period/military.\n'
    "- terimler: between 20 and 80 PROPER NOUNS from the game: character names, places, factions, items, "
    "abilities, spells, organisations. No common words, no sentences, no UI words.\n"
    "- asil is the name exactly as written in the game (English). ceviri is the Turkish form to use in subtitles.\n"
    "- Keep names UNTRANSLATED (ceviri == asil) unless an OFFICIAL Turkish localization term is well known.\n"
    "- Do not invent names. If you do not know the game, return an empty list and an empty aciklama.\n"
    "- Never add comments, markdown or text outside the JSON."
)


def kullanici_metni(ad: str, mevcut_aciklama: str = "") -> str:
    return json.dumps({"oyun": ad[:100], "mevcut_aciklama": (mevcut_aciklama or "")[:500]}, ensure_ascii=False)


def _temiz(metin: Any, en_cok: int) -> str:
    s = "".join(c for c in str(metin) if unicodedata.category(c)[0] != "C" or c == " ")
    return " ".join(s.split())[:en_cok].strip()


def _json_bul(ham: str) -> Any:
    """Yanıttan JSON nesnesini çıkarır (kod bloğu / önsöz toleransı)."""
    ham = (ham or "").strip()
    ham = re.sub(r"^```(?:json)?\s*|\s*```$", "", ham, flags=re.IGNORECASE)
    try:
        return json.loads(ham)
    except ValueError:
        pass
    a, b = ham.find("{"), ham.rfind("}")
    if a >= 0 and b > a:
        return json.loads(ham[a:b + 1])
    raise ValueError("JSON yok")


def temizle_terimler(ham: Any) -> list[dict[str, str]]:
    """Terim listesini doğrular: metin olmayan/boş/çok uzun atılır, büyük-küçük harf duyarsız tekilleştirilir, en çok 80."""
    out: list[dict[str, str]] = []
    goruldu: set[str] = set()
    if not isinstance(ham, list):
        return out
    for t in ham:
        if not isinstance(t, dict) or not isinstance(t.get("asil"), str):
            continue
        asil = _temiz(t["asil"], EN_COK_TERIM_UZUNLUK + 1)
        if not asil or len(asil) > EN_COK_TERIM_UZUNLUK or "[[" in asil or asil.casefold() in goruldu:
            continue
        ceviri = t.get("ceviri")
        ceviri = _temiz(ceviri, EN_COK_TERIM_UZUNLUK) if isinstance(ceviri, str) else ""
        goruldu.add(asil.casefold())
        out.append({"asil": asil, "ceviri": ceviri or asil})
        if len(out) >= EN_COK_TERIM:
            break
    return out


def yaniti_coz(ham: str) -> dict[str, Any]:
    """LLM yanıtını {"aciklama","hitap","terimler"} önerisine çevirir. Okunamazsa ValueError."""
    v = _json_bul(ham)
    if not isinstance(v, dict):
        raise ValueError("nesne değil")
    aciklama = _temiz(v.get("aciklama", ""), EN_COK_ACIKLAMA) if isinstance(v.get("aciklama", ""), str) else ""
    hitap = v.get("hitap") if v.get("hitap") in ("sen", "siz") else "sen"
    terimler = temizle_terimler(v.get("terimler"))
    if not aciklama and not terimler:
        raise ValueError("boş öneri")
    return {"aciklama": aciklama, "hitap": hitap, "terimler": terimler}


def birlestir(mevcut: list[dict[str, str]], yeni: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    """Yeni terimleri mevcut sözlüğe ekler; aynı terim (büyük-küçük harf duyarsız) varsa KULLANICININ değeri kalır.
    Dönen: (birleşik liste, eklenen sayısı)."""
    sonuc = [dict(t) for t in mevcut]
    var = {t["asil"].casefold() for t in sonuc}
    eklenen = 0
    for t in temizle_terimler(yeni):
        if t["asil"].casefold() in var:
            continue
        var.add(t["asil"].casefold())
        sonuc.append(t)
        eklenen += 1
    return sonuc, eklenen
