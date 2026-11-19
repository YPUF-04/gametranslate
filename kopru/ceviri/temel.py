# SPDX-License-Identifier: AGPL-3.0-only
"""Çeviri motoru arayüzü ve ortak hatalar."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class AgHatasi(Exception):
    """Ağ/sunucu sorunu: yönetici yedek motora geçer."""


class ModelBulunamadi(AgHatasi):
    """Servis modeli tanımıyor (HTTP 404): model kapatılmış ya da adı yanlış."""
    kod = "model_yok"


class AnahtarHatasi(Exception):
    """API anahtarı yok ya da geçersiz."""


class ErisimSiniri(Exception):
    """Günlük ücretsiz süre doldu ve geçerli kod yok: yeni motor çağrısı yapılmaz."""


class MotorHatasi(Exception):
    """Motor kullanılamıyor (kurulu değil vb.)."""


@dataclass
class Ceviri:
    metin: str
    aciklama: str | None = None
    kaynak: str = "motor"   # "motor" | "kullanici" | "paket" (hafızadan gelenler)


@dataclass
class Baglam:
    """Motora her istekte verilen oyun bağlamı (bkz. PROTOKOL 6.3)."""
    oyun_ad: str = ""
    aciklama: str = ""
    hitap: str = "sen"
    karakterler: list[dict] = field(default_factory=list)   # [{"ad":..,"cinsiyet":"k"|"e"}]
    son_satirlar: list[tuple[str, str]] = field(default_factory=list)  # (asil, ceviri)
    yeni_terimler: list[dict] = field(default_factory=list)  # motor doldurur: [{"asil","ceviri"}]
    ipucu: str = ""   # dublaj: "söylenebilir, süreye sığan kısa Türkçe" isteği (her istekte değişir)


class CeviriMotoru(Protocol):
    kod: str
    ad: str
    anahtar_gerekli: bool
    cevrimdisi: bool

    # baglam_destekler=True olan motorlar cevir(..., baglam=Baglam) de kabul eder
    async def cevir(self, metinler: list[str], kaynak: str, hedef: str,
                    sozluk: dict[str, str], aciklama: bool = False) -> list[Ceviri]: ...
