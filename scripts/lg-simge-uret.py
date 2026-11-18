#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# AltYazıKöprüsü simgesi: lacivert zemin, üstte turkuaz köprü kemeri, altta altyazı çubuğu. Yazı yok.
# Kullanım: python3 scripts/lg-simge-uret.py   (Pillow gerekir)
import os
from PIL import Image, ImageDraw

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LACIVERT, TURKUAZ, SARI = (14, 26, 43, 255), (46, 196, 182, 255), (255, 209, 102, 255)


def ciz(boyut):
    s = 8  # yumuşak kenar için büyük çiz, küçült
    n = boyut * s
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=int(n * 0.2), fill=LACIVERT)
    kalin = int(n * 0.07)
    # kemer (köprü)
    d.arc([int(n * .14), int(n * .20), int(n * .86), int(n * .92)], 180, 360, fill=TURKUAZ, width=kalin)
    # kemerin ayakları ve güverte
    d.rectangle([int(n * .14), int(n * .56), int(n * .14) + kalin, int(n * .66)], fill=TURKUAZ)
    d.rectangle([int(n * .86) - kalin, int(n * .56), int(n * .86), int(n * .66)], fill=TURKUAZ)
    d.rounded_rectangle([int(n * .10), int(n * .62), int(n * .90), int(n * .62) + kalin], radius=kalin // 2, fill=TURKUAZ)
    # kemerden inen dikmeler
    for x in (.32, .50, .68):
        d.rectangle([int(n * x) - kalin // 4, int(n * .36), int(n * x) + kalin // 4, int(n * .62)], fill=TURKUAZ)
    # altyazı çubuğu
    d.rounded_rectangle([int(n * .16), int(n * .74), int(n * .84), int(n * .86)], radius=int(n * .04), fill=(255, 255, 255, 255))
    d.rounded_rectangle([int(n * .22), int(n * .78), int(n * .46), int(n * .82)], radius=int(n * .02), fill=SARI)
    d.rounded_rectangle([int(n * .50), int(n * .78), int(n * .78), int(n * .82)], radius=int(n * .02), fill=LACIVERT)
    return im.resize((boyut, boyut), Image.LANCZOS)


for klasor in ("tv/webos", "tv/lg-test"):
    for ad, b in (("icon.png", 80), ("largeIcon.png", 130)):
        yol = os.path.join(KOK, klasor, ad)
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        ciz(b).save(yol)
        print("yazıldı:", yol)
