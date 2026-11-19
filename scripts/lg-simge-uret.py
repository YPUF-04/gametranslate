#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# AltYazıKöprüsü simgesi (paneldeki SVG logonun aynısı, 64'lük ızgara):
# koyu lacivert degrade zemin, turkuaz köprü kemeri ve dikmeleri, altta sarı altyazı çubuğu. Yazı yok.
# Kullanım: python3 scripts/lg-simge-uret.py   (Pillow gerekir)
import math
import os
from PIL import Image, ImageDraw

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UST, ALT = (26, 50, 86), (12, 23, 41)               # zemin degradesi #1A3256 -> #0C1729
TURKUAZ, TURKUAZ_ACIK = (46, 196, 182), (107, 227, 215)
SARI, KOYU = (255, 209, 102, 255), (12, 23, 41)


def karis(a, b, k):
    return tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(3))


def ciz(boyut):
    s = 16                       # yumuşak kenar: büyük çiz, küçült
    n = boyut * s
    b = n / 64.0                 # SVG birimi -> piksel

    def p(v):
        return int(round(v * b))

    # zemin: dikey degrade, yuvarlak köşeli kare maske
    zemin = Image.new("RGBA", (n, n))
    zd = ImageDraw.Draw(zemin)
    for y in range(n):
        zd.line([(0, y), (n, y)], fill=karis(UST, ALT, y / (n - 1)) + (255,))
    maske = Image.new("L", (n, n), 0)
    ImageDraw.Draw(maske).rounded_rectangle([0, 0, n - 1, n - 1], radius=p(16), fill=255)
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    im.paste(zemin, (0, 0), maske)
    # ince iç çerçeve (cam kenarı)
    cerceve = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(cerceve).rounded_rectangle([p(.75), p(.75), n - 1 - p(.75), n - 1 - p(.75)], radius=p(15.25), outline=(255, 255, 255, 20), width=max(1, p(1.5)))
    im = Image.alpha_composite(im, cerceve)

    # dikmeler (kemerin altında, yarı saydam turkuaz)
    dik = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dik)
    for x, y0 in ((20, 26), (32, 23), (44, 26)):
        w = p(2.2)
        dd.rounded_rectangle([p(x) - w // 2, p(y0), p(x) + w // 2, p(36)], radius=w // 2, fill=TURKUAZ + (140,))
    im = Image.alpha_composite(im, dik)
    d = ImageDraw.Draw(im)

    # kemer: SVG "M8 33 A30 30 0 0 1 56 33" -> merkez (32,51), yarıçap 30, kalınlık 5; soldan sağa turkuaz -> açık turkuaz
    kemer = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    kd = ImageDraw.Draw(kemer)
    r, k, cy = 30, 5, 51
    a0 = math.degrees(math.atan2(33 - cy, 8 - 32)) % 360        # sol uç açısı
    a1 = math.degrees(math.atan2(33 - cy, 56 - 32)) % 360       # sağ uç açısı
    kd.arc([p(32 - r - k / 2), p(cy - r - k / 2), p(32 + r + k / 2), p(cy + r + k / 2)], a0, a1, fill=(255, 255, 255, 255), width=p(k))
    for x in (8, 56):            # yuvarlak uçlar
        kd.ellipse([p(x - k / 2), p(33 - k / 2), p(x + k / 2), p(33 + k / 2)], fill=(255, 255, 255, 255))
    renk = Image.new("RGBA", (n, n))
    rd = ImageDraw.Draw(renk)
    for x in range(n):
        rd.line([(x, 0), (x, n)], fill=karis(TURKUAZ, TURKUAZ_ACIK, x / (n - 1)) + (255,))
    kemer = Image.composite(renk, Image.new("RGBA", (n, n), (0, 0, 0, 0)), kemer.split()[3])
    im = Image.alpha_composite(im, kemer)
    d = ImageDraw.Draw(im)

    # altyazı çubuğu ve içindeki iki "satır"
    d.rounded_rectangle([p(10), p(37), p(54), p(48)], radius=p(5.5), fill=SARI)
    d.rounded_rectangle([p(17), p(41), p(34), p(44)], radius=p(1.5), fill=karis(SARI, KOYU, 0.72) + (255,))
    d.rounded_rectangle([p(37), p(41), p(47), p(44)], radius=p(1.5), fill=karis(SARI, KOYU, 0.72) + (255,))
    return im.resize((boyut, boyut), Image.LANCZOS)


for klasor in ("tv/webos", "tv/lg-test"):
    for ad, b in (("icon.png", 80), ("largeIcon.png", 130)):
        yol = os.path.join(KOK, klasor, ad)
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        ciz(b).save(yol, optimize=True)
        print("yazıldı:", yol)
