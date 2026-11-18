# SPDX-License-Identifier: AGPL-3.0-only
"""Ortak istem (prompt) ve JSON yanıt ayrıştırma."""
from __future__ import annotations

import json
import re

from .temel import Ceviri

DIL_ADLARI = {"tr": "Turkish", "en": "English", "de": "German", "fr": "French",
              "es": "Spanish", "it": "Italian", "ru": "Russian", "ja": "Japanese",
              "ko": "Korean", "zh": "Chinese", "pt": "Portuguese", "pl": "Polish"}


def dil_adi(kod: str) -> str:
    return DIL_ADLARI.get(kod, kod)


def sistem_istemi(kaynak: str, hedef: str, sozluk: dict[str, str], aciklama: bool) -> str:
    kaynak_s = "the source language (auto-detect)" if kaynak in ("otomatik", "", "auto")         else dil_adi(kaynak)
    p = [
        f"You translate video game text from {kaynak_s} to {dil_adi(hedef)}.",
        "Write natural, short, subtitle-length text a player reads at a glance. "
        "Keep the meaning and tone; do not pad, over-compress, explain or add notes.",
        "Names, places and terms listed in the glossary must be used exactly as given.",
    ]
    if sozluk:
        p.append("Glossary (source => required form):\n" +
                 "\n".join(f"- {a} => {c}" for a, c in sozluk.items()))
    if aciklama:
        p.append('For each line also give a VERY short explanation in the target language '
                 '(max 60 characters, e.g. "Görev: üsse geri dön"). '
                 'If nothing useful can be said, use an empty string.')
    sekil = '{"c": "translation", "a": "explanation"}' if aciklama else '"translation"'
    p.append("The user sends a JSON array of strings. Reply ONLY with a JSON array of the "
             f"same length and order; each element is {sekil}. No markdown, no commentary.")
    return "\n\n".join(p)


def kullanici_metni(metinler: list[str]) -> str:
    return json.dumps(metinler, ensure_ascii=False)


def yaniti_coz(ham: str, adet: int, aciklama: bool) -> list[Ceviri]:
    """Modelin JSON dizisini esnek biçimde okur; sayı tutmazsa ValueError."""
    ham = ham.strip()
    ham = re.sub(r"^```(?:json)?\s*|\s*```$", "", ham)
    try:
        veri = json.loads(ham)
    except ValueError:
        i, j = ham.find("["), ham.rfind("]")
        if i < 0 or j <= i:
            raise ValueError("JSON dizisi bulunamadı") from None
        veri = json.loads(ham[i:j + 1])
    if isinstance(veri, dict):  # {"ceviriler":[...]}
        for v in veri.values():
            if isinstance(v, list):
                veri = v
                break
    if not isinstance(veri, list) or len(veri) != adet:
        raise ValueError("Beklenmeyen eleman sayısı")
    out: list[Ceviri] = []
    for e in veri:
        if isinstance(e, dict):
            m = str(e.get("c") or e.get("metin") or e.get("ceviri") or "")
            a = e.get("a") or e.get("aciklama")
            out.append(Ceviri(m, str(a)[:80] if (aciklama and a) else None))
        else:
            out.append(Ceviri(str(e)))
    return out
