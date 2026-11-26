# SPDX-License-Identifier: AGPL-3.0-only
"""Türkçe dublaj: karakterin kendi sesiyle (docs/PROTOKOL.md 9).

Ağır bağımlılıklar (torch, chatterbox, pocket-tts, faster-whisper...) yalnız gerektiğinde
ve tembel (lazy) yüklenir; kurulu değilse program çökmez, açık bir mesaj verir.
"""
from __future__ import annotations

from typing import Any

from .temel import DublajHatasi, SesMotoru

MOTORLAR = ("kapali", "chatterbox", "pocket", "elevenlabs")
MOTOR_ADLARI = {"chatterbox": "Chatterbox", "pocket": "Pocket TTS", "elevenlabs": "ElevenLabs"}
CIKISLAR = ("bilgisayar", "tv")
VARSAYILAN: dict[str, Any] = {
    "motor": "kapali", "oyun_sesi_kis": 0.25, "hiz_siniri": 1.25, "ses_seviyesi": 1.0,
    "cikis": "bilgisayar",
    # ElevenLabs: ses örneği o servise gittiği için iki ayrı onay (PROTOKOL 9.2)
    "elevenlabs_onay": False,        # 1) "ses örneğim ElevenLabs'e gidecek" onayı
    "elevenlabs_klon_onay": False,   # 2) kendi sesimin klonunu o hesapta oluştur (ikinci onay)
    "elevenlabs_ses_kimligi": "",    # kullanıcının seçtiği hazır ses (voice_id)
    "elevenlabs_model": "eleven_multilingual_v2",
    # PROTOKOL 14.5
    # "otomatik": PS5/Xbox Remote Play penceresi ya da yakalama kartı sesi varsa İngilizce ses tamamen
    # çıkarılır, yoksa kısılır | "kis" | "tamamen_turkce"
    "orijinal_ses": "otomatik",
    # Oyun konsolda (PS5) çalıştığı için ekran kartı boştur: varsayılan tam kalite. "acik": hafif modeller
    "hafif_mod": "kapali",
    "ses_girisi": "",
    # Ses profili (§14.5): izinle karakter örnekleri bu bilgisayarda saklanır (silinebilir). Varsayılan KAPALI
    "ses_profili_izni": False,                # yakalama kartının ses girişi (yalnız kullanıcı açıkça seçerse; mikrofon değil)
    "ayirma": True,                  # canlıda konuşmayı arka plandan ayır (temiz klon + yazı)
    "erken_seslendir": True,         # ekrandaki altyazı görünür görünmez Türkçe sesi hazırlamaya başla
    "video_srt": True,
    "video_motor": "chatterbox",
    # Dublaj hafızası (PROTOKOL 21.1): açık rıza ile klonlanmış Türkçe sesler + İngilizce ses izleri bu bilgisayarda
    "hafiza_izni": False,
    "hafiza_kullan": True,
    "bosta_iyilestir": False,
    "hafiza_sinir_mb": 1000,
}
ORIJINAL_SES = ("otomatik", "kis", "tamamen_turkce")
HAFIF_MOD = ("otomatik", "acik", "kapali")
VIDEO_MOTORLARI = ("chatterbox", "pocket")


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
        if k == "orijinal_ses" and v not in ORIJINAL_SES:
            return False
        if k == "hafif_mod" and v not in HAFIF_MOD:
            return False
        if k == "ses_girisi" and (not isinstance(v, str) or len(v) > 200):
            return False
        if k == "video_motor" and v not in VIDEO_MOTORLARI:
            return False
        if k == "hafiza_sinir_mb" and (isinstance(v, bool) or not isinstance(v, int) or not 50 <= v <= 20000):
            return False
        if k in ("elevenlabs_onay", "elevenlabs_klon_onay", "ayirma", "erken_seslendir", "video_srt",
                 "ses_profili_izni", "hafiza_izni", "hafiza_kullan", "bosta_iyilestir") \
                and not isinstance(v, bool):
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
                                klon_onay=bool(d.get("elevenlabs_klon_onay")),
                                onay=bool(d.get("elevenlabs_onay")))
    raise DublajHatasi("dublaj_motor_yok", kod)


__all__ = ["DublajHatasi", "SesMotoru", "MOTORLAR", "CIKISLAR", "VARSAYILAN",
           "ayar_gecerli", "motor_olustur"]


def ayar_duzelt(mevcut: dict[str, Any], parca: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """`mevcut` ayara gelen `parca`yı uygular ve gizlilik açısından tutarlı hâle getirir.

    Dönüş: (düzeltilmiş ayar, hata kodu | None). İstek ElevenLabs'i seçiyorsa birinci onay şarttır
    (yoksa hata). Onay geri alınırsa klon onayı da düşer ve ElevenLabs motoru kapanır (hiçbir şey gitmez).
    """
    d = {**mevcut, **parca}
    if not d.get("elevenlabs_onay"):
        d["elevenlabs_klon_onay"] = False
        if d.get("motor") == "elevenlabs":
            if parca.get("motor") == "elevenlabs":
                return d, "dublaj_onay_gerekli"
            d["motor"] = "kapali"
    return d, None


def tamamen_turkce_mu(ayar: dict[str, Any]) -> bool:
    """İngilizce sesin tamamen çıkarılması istenip istenmediği (PROTOKOL 14.3).

    "otomatik": ses bilgisayardan geçiyorsa evet: PS5/Xbox Remote Play penceresi seçili ya da
    yakalama kartının ses girişi seçili. Oyun bu bilgisayarda çalışıyorsa (pc) hayır: kısma.
    """
    d = ayar.get("dublaj") or {}
    secim = d.get("orijinal_ses", "otomatik")
    if secim != "otomatik":
        return secim == "tamamen_turkce"
    if d.get("ses_girisi"):
        return True
    return ayar.get("cihaz") in ("ps5", "xbox", "kart") and str(ayar.get("kaynak") or "").startswith("pencere:")
