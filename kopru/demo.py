# SPDX-License-Identifier: AGPL-3.0-only
"""PROTOKOL 20.7: "Konsolsuz dene" — kendi çizdiğimiz örnek oyun karesi ve birkaç İngilizce satır.

Kare kaynağı ve okuyucu olarak Isleme'ye verilir: temizlik katmanı, motor, kuyruk, örtü ve yayın gerçek akıştır.
Okuma adımı karede çizili yazıları (biliyoruz) döndürür; OCR kurulu olmayan bilgisayarda da çalışsın diye.
"""
from __future__ import annotations

import io
import time
from typing import Any, Callable

from .okuma import Satir

GEN, YUK = 1280, 720
# (süre sn, konuşan, İngilizce satır) — kendi yazdığımız örnekler: konuşan, bölünmüş cümle, bağırma, ad, düğme
SAHNE: tuple[tuple[float, str | None, str], ...] = (
    (3.5, "MARCUS", "We need to get out of here before the cops show up."),
    (2.6, None, "I told you we should"),
    (2.6, None, "never have come here."),
    (3.0, None, "GET DOWN! THEY'RE SHOOTING AT US"),
    (3.4, None, "Tell Hope we are on our way to the ranch."),
    (3.2, None, "Press ✕ to open the door."),
)
GOREV = ("Return to the safehouse", 0.035, 0.06, 0.25, 0.04)
PARA = ("$1,250", 0.86, 0.06, 0.1, 0.04)
ALT_Y, ALT_Y2 = 0.84, 0.055
EN_COK_SN = 60.0


def _yazi_tipi(px: int) -> Any:
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=px)
    except TypeError:   # eski Pillow
        return ImageFont.load_default()


class Sahne:
    """kare() o anki kareyi çizer; oku() aynı karenin yazılarını verir."""

    def __init__(self, saat: Callable[[], float] = time.monotonic, sahne: tuple = SAHNE) -> None:
        self.saat = saat
        self.sahne = sahne
        self.bas = saat()
        self.toplam_sn = sum(s for s, _, _ in sahne) + 1.5
        self._satir: tuple[str | None, str] | None = None
        self._son_resim: Any = None

    def _anki(self) -> tuple[str | None, str] | None:
        t = self.saat() - self.bas
        for sure, konusan, metin in self.sahne:
            if t < sure:
                return konusan, metin
            t -= sure
        return None

    def bitti(self) -> bool:
        return self.saat() - self.bas >= self.toplam_sn

    def _metin(self, k: tuple[str | None, str]) -> str:
        return f"{k[0]}: {k[1]}" if k[0] else k[1]

    def ciz(self, satir: tuple[str | None, str] | None) -> Any:
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (GEN, YUK))
        d = ImageDraw.Draw(im)
        for y in range(YUK):   # gökyüzü -> ufuk -> yol
            v = y / YUK
            renk = (int(32 + 70 * v), int(58 + 60 * v), int(104 + 40 * v)) if v < 0.58 else \
                (int(54 - 24 * v), int(56 - 22 * v), int(50 - 20 * v))
            d.line([(0, y), (GEN, y)], fill=renk)
        for i, (x, w, h) in enumerate(((60, 140, 230), (230, 110, 300), (380, 180, 190), (900, 160, 260), (1090, 130, 210))):
            d.rectangle((x, int(YUK * 0.58) - h, x + w, int(YUK * 0.58)), fill=(28 + i * 6, 34 + i * 5, 50 + i * 4))
            for wy in range(int(YUK * 0.58) - h + 16, int(YUK * 0.58) - 10, 28):
                for wx in range(x + 12, x + w - 12, 26):
                    d.rectangle((wx, wy, wx + 10, wy + 12), fill=(236, 196, 110) if (wx + wy) % 3 else (60, 70, 90))
        d.polygon([(560, YUK), (720, YUK), (660, int(YUK * 0.58)), (620, int(YUK * 0.58))], fill=(70, 70, 72))
        f_hud = _yazi_tipi(26)
        for metin, x, y, _g, y2 in (GOREV, PARA):
            d.text((int(x * GEN), int((y + y2 * 0.1) * YUK)), metin, font=f_hud,
                   fill=(255, 214, 120) if metin is GOREV[0] else (150, 230, 150))
        if satir:
            f = _yazi_tipi(32)
            m = self._metin(satir)
            gen = d.textlength(m, font=f)
            x0 = (GEN - gen) / 2
            d.rectangle((x0 - 18, int(ALT_Y * YUK) - 6, x0 + gen + 18, int((ALT_Y + ALT_Y2) * YUK) + 6), fill=(12, 14, 18))
            d.text((x0, int(ALT_Y * YUK)), m, font=f, fill=(240, 240, 236))
        return im

    # Isleme arayüzü
    def kare(self) -> Any:
        self._satir = self._anki()
        self._son_resim = self.ciz(self._satir)
        return self._son_resim

    def oku(self, resim: Any) -> list[Satir]:
        out = [Satir(GOREV[0], *GOREV[1:]), Satir(PARA[0], *PARA[1:])]
        if self._satir:
            m = self._metin(self._satir)
            g = min(0.9, len(m) * 0.0135)
            out.append(Satir(m, 0.5 - g / 2, ALT_Y, g, ALT_Y2))
        return out

    def jpeg(self) -> bytes:
        b = io.BytesIO()
        self.ciz(None).save(b, "JPEG", quality=82)
        return b.getvalue()
