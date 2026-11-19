#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Uygulama simgelerini üretir (Pillow): uygulama.ico (Windows), uygulama.icns (macOS), kurucu görselleri.

Çizim scripts/lg-simge-uret.py ile aynıdır (köprü kemeri + altyazı çubuğu).
Kullanım: python paketleme/simge/simge_uret.py [önizleme_klasörü]
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

BURASI = Path(__file__).resolve().parent
KOK = BURASI.parent.parent
BOYUTLAR = (16, 24, 32, 48, 64, 128, 256)


def _ciz_yukle():
    """lg-simge-uret.py yazı çıktısı/kayıt yan etkisi taşıdığından yalnız `ciz` işlevini alırız."""
    kaynak = (KOK / "scripts" / "lg-simge-uret.py").read_text(encoding="utf-8")
    kaynak = kaynak.split("for klasor in", 1)[0]
    ad = {"__name__": "simge", "__file__": str(KOK / "scripts" / "lg-simge-uret.py")}
    exec(compile(kaynak, "lg-simge-uret.py", "exec"), ad)
    return ad["ciz"]


def _kucuk_ciz(ciz, b):
    # çok küçük boyutlarda doğrudan o boyutta çiz (daha keskin); lg çizimi zaten süper-örnekler
    return ciz(b)


def kurulum_buyuk(ciz) -> Image.Image:
    """164x314 sihirbaz görseli: koyu lacivert degrade, ortada büyük logo, yazı yok."""
    w, h = 164, 314
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    ust, alt = (26, 50, 86), (10, 18, 33)
    for y in range(h):
        k = y / (h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(ust[i] + (alt[i] - ust[i]) * k) for i in range(3)))
    logo = ciz(128)
    im.paste(logo, ((w - 128) // 2, 70), logo)
    # altta ince turkuaz çizgi (köprü yansıması gibi)
    for i, a in enumerate((90, 45, 20)):
        d.line([(24, 232 + i * 4), (w - 24, 232 + i * 4)], fill=tuple(int(c * a / 255 + 12 * (1 - a / 255)) for c in (46, 196, 182)))
    return im


def kurulum_kucuk(ciz) -> Image.Image:
    """55x55 sihirbaz köşe simgesi (açık sayfa üstünde): logo, düz zemin."""
    im = Image.new("RGB", (55, 55), (255, 255, 255))
    logo = ciz(55)
    im.paste(logo, (0, 0), logo)
    return im


def uret(onizleme: Path | None = None) -> None:
    ciz = _ciz_yukle()
    img = {b: _kucuk_ciz(ciz, b) for b in BOYUTLAR}
    img[256].save(BURASI / "uygulama.ico", format="ICO", sizes=[(b, b) for b in BOYUTLAR],
                  append_images=[img[b] for b in BOYUTLAR if b != 256])
    # ICNS: Pillow 512/1024 de ister; büyük çizimden üretir
    ciz(1024).save(BURASI / "uygulama.icns", format="ICNS")
    kurulum_buyuk(ciz).save(BURASI / "kurulum-buyuk.bmp", format="BMP")
    kurulum_kucuk(ciz).save(BURASI / "kurulum-kucuk.bmp", format="BMP")
    ciz(512).save(BURASI / "uygulama.png")
    if onizleme:
        onizleme.mkdir(parents=True, exist_ok=True)
        sayfa = Image.new("RGB", (sum(b + 12 for b in BOYUTLAR) + 12, 280), (240, 240, 240))
        x = 12
        for b in BOYUTLAR:
            sayfa.paste(img[b], (x, 12), img[b])
            x += b + 12
        koyu = Image.new("RGB", sayfa.size, (30, 30, 30))
        x = 12
        for b in BOYUTLAR:
            koyu.paste(img[b], (x, 12), img[b])
            x += b + 12
        sayfa.save(onizleme / "simge-boyutlar-acik.png")
        koyu.save(onizleme / "simge-boyutlar-koyu.png")
        kurulum_buyuk(ciz).save(onizleme / "simge-kurulum-buyuk.png")
        kurulum_kucuk(ciz).save(onizleme / "simge-kurulum-kucuk.png")
        ico = Image.open(BURASI / "uygulama.ico")
        print("ico boyutları:", sorted(ico.info.get("sizes", [])))


if __name__ == "__main__":
    uret(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
