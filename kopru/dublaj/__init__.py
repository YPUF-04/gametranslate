# SPDX-License-Identifier: AGPL-3.0-only
"""Türkçe dublaj: karakterin kendi sesiyle (docs/PROTOKOL.md 9).

Ağır bağımlılıklar (torch, chatterbox, pocket-tts, faster-whisper...) yalnız gerektiğinde
ve tembel (lazy) yüklenir; kurulu değilse program çökmez, açık bir mesaj verir.
"""
from __future__ import annotations

from typing import Any

from .temel import DublajHatasi, SesMotoru

MOTORLAR = ("kapali", "chatterbox", "pocket", "elevenlabs")
CIKISLAR = ("bilgisayar", "tv")
VARSAYILAN: dict[str, Any] = {
    "motor": "kapali", "oyun_sesi_kis": 0.25, "hiz_siniri": 1.25, "ses_seviyesi": 1.0,
    "cikis": "bilgisayar",
    # ElevenLabs: ses örneği o servise gittiği için iki ayrı onay (PROTOKOL 9.2)
    "elevenlabs_onay": False,        # 1) "ses örneğim ElevenLabs'e gidecek" onayı
    "elevenlabs_klon_onay": False,   # 2) kendi sesimin klonunu o hesapta oluştur (ikinci onay)
    "elevenlabs_ses_kimligi": "",    # kullanıcının seçtiği hazır ses (voice_id)
    "elevenlabs_model": "eleven_multilingual_v2",
}


def ayar_gecerli(d: Any) -> bool:
    """`dublaj` ayarının (kısmi olabilir) doğrulaması."""
    if not isinstance(d, dict):
        return False
    for k, v in d.items():
        if k not in VARSAYILAN:
            return False
        if k == "motor" and v not in MOTORLAR:
            return False
        if k == "cikis" and v not in CIKISLAR:
            return False
        if k in ("oyun_sesi_kis", "ses_seviyesi", "hiz_siniri"):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return False
        if k == "oyun_sesi_kis" and not 0 <= v <= 1:
            return False
        if k == "ses_seviyesi" and not 0 <= v <= 2:
            return False
        if k == "hiz_siniri" and not 1.0 <= v <= 1.5:
            return False
        if k in ("elevenlabs_onay", "elevenlabs_klon_onay") and not isinstance(v, bool):
            return False
        if k in ("elevenlabs_ses_kimligi", "elevenlabs_model"):
            if not isinstance(v, str) or len(v) > 100 or (k == "elevenlabs_model" and not v.strip()):
                return False
    return True


def motor_olustur(kod: str, ayar: dict[str, Any]) -> SesMotoru:
    """Motor nesnesi; paketler burada değil, motorun `hazirla`sında yüklenir."""
    d = ayar.get("dublaj") or {}
    if kod == "chatterbox":
        from .chatterbox import ChatterboxMotoru
        return ChatterboxMotoru()
    if kod == "pocket":
        from .pocket import PocketMotoru
        return PocketMotoru()
    if kod == "elevenlabs":
        from .elevenlabs import ElevenLabsMotoru
        return ElevenLabsMotoru(d.get("elevenlabs_ses_kimligi", ""),
                                d.get("elevenlabs_model", "eleven_multilingual_v2"),
                                bool(d.get("elevenlabs_klon_onay")))
    raise DublajHatasi("dublaj_motor_yok", kod)


__all__ = ["DublajHatasi", "SesMotoru", "MOTORLAR", "CIKISLAR", "VARSAYILAN",
           "ayar_gecerli", "motor_olustur"]
