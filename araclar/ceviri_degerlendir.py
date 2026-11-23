# SPDX-License-Identifier: AGPL-3.0-only
"""Altyazı çevirisi değerlendirmesi (PROTOKOL 19.4).

    python araclar/ceviri_degerlendir.py            # çevrimdışı: istem yapısı + sahte model (referanslar) kurallara uyuyor mu
    GEMINI_API_KEY=... python araclar/ceviri_degerlendir.py --canli [--iyilestir]   # gerçek Gemini ile puanlar

Örnekler: tests/ceviri_ornekleri.json. Her satır aynı sahnenin önceki satırlarıyla (konuşan adıyla) bağlam alır,
tıpkı programda olduğu gibi (CeviriYoneticisi). Canlı kısım CI'da çalışmaz (anahtar yok).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

KOK = Path(__file__).resolve().parents[1]
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from kopru.ceviri import istem  # noqa: E402
from kopru.ceviri.temel import Ceviri  # noqa: E402
from kopru.ceviri.yonetici import CeviriYoneticisi  # noqa: E402

ORNEK_DOSYASI = KOK / "tests" / "ceviri_ornekleri.json"
SATIR_EN_COK = 42
EN_COK_SATIR = 2


def ornekleri_yukle(yol: Path = ORNEK_DOSYASI) -> dict[str, Any]:
    return json.loads(yol.read_text(encoding="utf-8"))


def kurallari_denetle(ornek: dict[str, Any], ceviri: str) -> list[str]:
    """Bir çevirinin PROTOKOL 19.1 kurallarına aykırılıkları (boş liste = temiz)."""
    sorun: list[str] = []
    k = ornek.get("kurallar") or {}
    metin = ceviri.replace("\\n", "\n")
    satirlar = [s for s in metin.split("\n")]
    sinir = int(k.get("en_cok_karakter") or SATIR_EN_COK)
    if not metin.strip():
        sorun.append("boş çeviri")
    if len(satirlar) > EN_COK_SATIR:
        sorun.append(f"{len(satirlar)} satır (en çok {EN_COK_SATIR})")
    for s in satirlar:
        if len(s) > sinir:
            sorun.append(f"satır {len(s)} karakter (en çok {sinir}): {s!r}")
    for t in k.get("korunacak", []):
        if t not in metin:
            sorun.append(f"korunmadı: {t!r}")
    for t in k.get("yasak", []):
        if t.casefold() in metin.casefold():
            sorun.append(f"kelimesi kelimesine/yanlış: {t!r}")
    birini = k.get("icermeli_birini") or []
    if birini and not any(t in metin for t in birini):
        sorun.append(f"beklenen ton/hitap yok (biri olmalı: {birini})")
    if k.get("buyuk_harf") and metin != metin.upper():
        sorun.append("BÜYÜK HARF korunmadı")
    if " ".join(metin.split()).casefold() == " ".join(ornek["asil"].split()).casefold():
        sorun.append("çevrilmemiş")
    if ornek.get("konusan") and metin.lstrip().lower().startswith(str(ornek["konusan"]).lower() + ":"):
        sorun.append("konuşan adı çeviriye eklenmiş")
    return sorun


def yonetici_kur(veri: dict[str, Any], motor: Any) -> CeviriYoneticisi:
    y = CeviriYoneticisi(motor, None, None)
    y.oyun_bilgisi = dict(veri.get("oyun") or {})
    y.terimler = dict(veri.get("sozluk") or {})
    return y


class SahteModel:
    """Çevrimdışı: istemi kaydeder, referans çeviriyi döndürür (istem yapısı + kural denetiminin kendisi sınanır)."""
    kod = "sahte-degerlendirme"
    ad = "Sahte"
    anahtar_gerekli = False
    cevrimdisi = False
    baglam_destekler = True

    def __init__(self, referanslar: dict[str, str]) -> None:
        self.referanslar = referanslar
        self.istemler: list[tuple[str, str]] = []

    async def cevir(self, metinler: list[str], kaynak: str, hedef: str, sozluk: dict[str, str],
                    aciklama: bool = False, baglam: Any = None) -> list[Ceviri]:
        self.istemler.append((istem.sistem_istemi(kaynak, hedef, sozluk, aciklama, baglam),
                              istem.kullanici_metni(metinler, baglam)))
        return [Ceviri(self.referanslar.get(m, m)) for m in metinler]


def istem_yapisini_denetle(sistem: str, kullanici: str) -> list[str]:
    sorun = []
    for parca in ("EXAMPLES", "Profanity keeps EXACTLY the same intensity", "max 42 characters per line",
                  "Street talk", "Avoid calques", "GAME INFO", "GLOSSARY", "OUTPUT FORMAT", "BUTTON PROMPTS"):
        if parca not in sistem:
            sorun.append(f"sistem isteminde yok: {parca}")
    if len(sistem) > 9000:
        sorun.append(f"sistem istemi çok uzun ({len(sistem)} karakter): gecikme/maliyet")
    return sorun


async def calistir(veri: dict[str, Any], motor: Any, iyilestir: bool = False) -> list[dict[str, Any]]:
    """Her sahne kendi yöneticisinde (sahne bağlamı), satırlar sırayla çevrilir ve 'gösterilir'."""
    sonuc: list[dict[str, Any]] = []
    sahneler: dict[str, CeviriYoneticisi] = {}
    for o in veri["ornekler"]:
        y = sahneler.setdefault(o.get("sahne") or "-", yonetici_kur(veri, motor))
        aciklama = False
        (c,) = await y.cevir([o["asil"]], "en", "tr", aciklama, konusan=o.get("konusan"))
        metin = c.metin
        if iyilestir:
            daha = await y.iyilestir(o["asil"], metin, "en", "tr", o.get("konusan"))
            metin = daha.metin if daha else metin
        y.satir_kaydet(o["id"], o["asil"], metin, "motor", o.get("konusan"))
        sonuc.append({"id": o["id"], "asil": o["asil"], "ceviri": metin, "sorunlar": kurallari_denetle(o, metin)})
    return sonuc


def cevrimdisi(veri: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    motor = SahteModel({o["asil"]: o["referans"] for o in veri["ornekler"]})
    sonuc = asyncio.run(calistir(veri, motor))
    yapi: list[str] = []
    for sistem, kullanici in motor.istemler:
        yapi += istem_yapisini_denetle(sistem, kullanici)
    return sonuc, sorted(set(yapi))


def rapor(sonuc: list[dict[str, Any]]) -> int:
    temiz = sum(1 for r in sonuc if not r["sorunlar"])
    for r in sonuc:
        isaret = "ok " if not r["sorunlar"] else "!! "
        print(f"{isaret}{r['id']:7} {r['asil']}\n        => {r['ceviri']!r}")
        for s in r["sorunlar"]:
            print(f"        - {s}")
    print(f"\n{temiz}/{len(sonuc)} satır kurallara uydu")
    return temiz


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--canli", action="store_true", help="GEMINI_API_KEY ile gerçek modelde çalıştır")
    ap.add_argument("--iyilestir", action="store_true", help="ikinci (derin) geçişi de çalıştır (PROTOKOL 19.2)")
    ap.add_argument("--model", default=None)
    a = ap.parse_args(argv)
    veri = ornekleri_yukle()
    if not a.canli:
        sonuc, yapi = cevrimdisi(veri)
        for s in yapi:
            print("!! " + s)
        temiz = rapor(sonuc)
        return 0 if not yapi and temiz == len(sonuc) else 1
    anahtar = os.environ.get("GEMINI_API_KEY")
    if not anahtar:
        print("GEMINI_API_KEY yok: canlı değerlendirme atlandı.")
        return 0
    from kopru.ceviri.gemini import VARSAYILAN_MODEL, GeminiMotoru
    motor = GeminiMotoru(anahtar, a.model or VARSAYILAN_MODEL)
    sonuc = asyncio.run(calistir(veri, motor, a.iyilestir))
    rapor(sonuc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
