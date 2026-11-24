# SPDX-License-Identifier: AGPL-3.0-only
"""Çeviri kalitesi ölçümü (PROTOKOL 20.8): chrF++ ile ham motor ve temizlik katmanlı yol.

    pip install sacrebleu                       # geliştirme bağımlılığı (pyproject: kalite)
    python araclar/kalite_olc.py                # çevrimdışı motor: ham vs katmanla (dil dosyası kurulu olmalı)
    GEMINI_API_KEY=... python araclar/kalite_olc.py --gemini   # + Gemini ham vs katmanla
    python araclar/kalite_olc.py --ayrinti      # satır satır çıktı

Ham: satır motora olduğu gibi gider (konuşan ön eki, BÜYÜK harf, okuma hatası, bölünmüş kartlar ayrı ayrı, HUD de
çevrilir). Katmanla: programın gerçek yolu — okuma düzeltme, konuşan ayırma, HUD süzgeci, bölünmüş cümle birleştirme,
bağırma düzeltme, ad koruma, oyun paketi, Türkçe ek uyumu, düğme koruma (CeviriYoneticisi).
Arayüz (HUD) satırları chrF'e katılmaz; ayrıca "aynen kaldı" oranı verilir.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

KOK = Path(__file__).resolve().parents[1]
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from kopru import oyun_paketleri  # noqa: E402
from kopru.ceviri import on_katman  # noqa: E402
from kopru.ceviri.temel import Ceviri  # noqa: E402
from kopru.ceviri.yonetici import CeviriYoneticisi  # noqa: E402
from kopru.isleme import konusan_ayir, ocr_duzelt, okuma_gurultusu_mu  # noqa: E402

ORNEK_DOSYASI = KOK / "tests" / "kalite" / "ornekler.json"


def ornekleri_yukle(yol: Path = ORNEK_DOSYASI) -> list[dict[str, Any]]:
    return json.loads(yol.read_text(encoding="utf-8"))["ornekler"]


def _girdi(o: dict[str, Any]) -> list[str]:
    return list(o.get("parcalar") or [o["en"]])


def _yonetici(motor: Any, o: dict[str, Any]) -> CeviriYoneticisi:
    y = CeviriYoneticisi(motor, None, None)
    bilgi: dict[str, Any] = {"karakterler": [{"ad": a} for a in o.get("karakterler", [])]}
    terimler: dict[str, str] = {}
    if o.get("oyun"):
        p = oyun_paketleri.bul(o["oyun"], "")
        if p:
            bilgi, terimler = oyun_paketleri.uygula(bilgi, {}, p[0])
    y.oyun_bilgisi, y.terimler = bilgi, terimler
    return y


async def ham(cevir: Callable[[list[str]], Awaitable[list[str]]], o: dict[str, Any]) -> str:
    """Motor olduğu gibi: kartlar ayrı ayrı çevrilip yan yana konur."""
    return " ".join(await cevir(_girdi(o)))


async def katmanla(motor: Any, o: dict[str, Any]) -> str:
    """Programın yolu (Isleme'nin altyazı adımı + CeviriYoneticisi)."""
    y = _yonetici(motor, o)
    parcalar = [ocr_duzelt(p, "en") for p in _girdi(o)]
    if len(parcalar) == 1 and okuma_gurultusu_mu(parcalar[0]):
        return parcalar[0]          # HUD: çevrilmez
    govdeler = []
    for p in parcalar:
        _, g = konusan_ayir(p)
        govdeler.append(y.altyazi_hazirla(g))
    metin = govdeler[0]
    for g in govdeler[1:]:
        metin = on_katman.birlestir(metin, g) if on_katman.bolunmus_mu(metin, g) else metin + " " + g
    (c,) = await y.cevir([metin], "en", "tr")
    return c.metin


def chrf(hipotezler: list[str], baslangiclar: list[str]) -> float:
    import sacrebleu
    return sacrebleu.CHRF(word_order=2).corpus_score(hipotezler, [baslangiclar]).score


async def olc(ad: str, ham_cevir: Callable[[list[str]], Awaitable[list[str]]], motor: Any,
              ornekler: list[dict[str, Any]], ayrinti: bool = False) -> dict[str, Any]:
    sonuc: dict[str, Any] = {"motor": ad}
    for kip in ("ham", "katmanla"):
        hip, ref, kats, ui = [], [], [], []
        for o in ornekler:
            h = await (ham(ham_cevir, o) if kip == "ham" else katmanla(motor, o))
            if ayrinti:
                print(f"[{ad}/{kip}/{o['kat']}] {o['en']}\n    => {h}\n    ref {o['tr']}")
            if o["kat"] == "arayuz":
                ui.append(h.strip() == o["tr"])
                continue
            hip.append(h)
            ref.append(o["tr"])
            kats.append(o["kat"])
        kat_puan = {}
        for k in dict.fromkeys(kats):
            i = [n for n, x in enumerate(kats) if x == k]
            kat_puan[k] = round(chrf([hip[n] for n in i], [ref[n] for n in i]), 1)
        sonuc[kip] = {"chrf": round(chrf(hip, ref), 1), "arayuz_aynen": f"{sum(ui)}/{len(ui)}", "kategori": kat_puan,
                      "satir": len(hip)}
    return sonuc


def _yerel() -> tuple[Callable[[list[str]], Awaitable[list[str]]], Any]:
    from kopru.ceviri import argos_model, yerel
    model = argos_model.modeli_bul(argos_model.paket_dizini("en", "tr"))
    if model is None:
        raise SystemExit("Çevrimdışı dil dosyası kurulu değil (programda 'Çevrimdışı motoru hazırla' ya da "
                         "python -c 'from kopru.ceviri import argos_model; argos_model.kur(\"en\",\"tr\")').")
    cevirici, sp = yerel._yukle(str(model[0]), str(model[1]))

    async def ciplak(metinler: list[str]) -> list[str]:   # motorun kendi büyük harf kuralı bile yok: çıplak model
        return [yerel.metni_cevir(cevirici, sp, m) for m in metinler]
    return ciplak, yerel.YerelMotor()


def _gemini() -> tuple[Callable[[list[str]], Awaitable[list[str]]], Any] | None:
    anahtar = os.environ.get("GEMINI_API_KEY")
    if not anahtar:
        return None
    from kopru.ceviri.gemini import GeminiMotoru
    motor = GeminiMotoru(anahtar)

    async def duz(metinler: list[str]) -> list[str]:
        out = []
        for m in metinler:
            (c,) = await motor.cevir([m], "en", "tr", {}, False)
            out.append(c.metin)
        return out
    return duz, motor


async def ana(argv: list[str] | None = None) -> list[dict[str, Any]]:
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--gemini", action="store_true", help="GEMINI_API_KEY varsa Gemini'yi de ölç")
    a.add_argument("--ayrinti", action="store_true")
    a.add_argument("--json", action="store_true")
    v = a.parse_args(argv)
    ornekler = ornekleri_yukle()
    sonuclar = []
    ciplak, motor = _yerel()
    sonuclar.append(await olc("cevrimdisi (Argos en->tr)", ciplak, motor, ornekler, v.ayrinti))
    if v.gemini:
        g = _gemini()
        if g is None:
            print("GEMINI_API_KEY yok: Gemini atlandı.", file=sys.stderr)
        else:
            sonuclar.append(await olc("gemini", g[0], g[1], ornekler, v.ayrinti))
    if v.json:
        print(json.dumps(sonuclar, ensure_ascii=False, indent=1))
    else:
        for s in sonuclar:
            print(f"{s['motor']}: chrF++ ham {s['ham']['chrf']} -> katmanla {s['katmanla']['chrf']} "
                  f"({s['ham']['satir']} satır); arayüz aynen: ham {s['ham']['arayuz_aynen']}, "
                  f"katmanla {s['katmanla']['arayuz_aynen']}")
            for k in s["ham"]["kategori"]:
                print(f"    {k:9s} {s['ham']['kategori'][k]:5.1f} -> {s['katmanla']['kategori'][k]:5.1f}")
    return sonuclar


if __name__ == "__main__":
    asyncio.run(ana())
