# SPDX-License-Identifier: AGPL-3.0-only
"""PyInstaller'ın ürettiği .app içindeki Info.plist'i düzeltir.

Kullanım: python paketleme/mac/bilgi_ekle.py <.app yolu> <sürüm>
Not: Ekran kaydı izni için Info.plist'te özel bir anahtar yoktur; macOS izni ilk yakalamada kendisi sorar
(açıklama docs/kurulum/mac.md içindedir).
"""
from __future__ import annotations

import plistlib
import sys
from pathlib import Path

KIMLIK = "com.altyazikoprusu.mac"
GORUNEN_AD = "AltYazıKöprüsü"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Kullanım: bilgi_ekle.py <.app yolu> <sürüm>", file=sys.stderr)
        return 2
    yol = Path(argv[1]) / "Contents" / "Info.plist"
    with yol.open("rb") as f:
        p = plistlib.load(f)
    p.update({
        "CFBundleIdentifier": KIMLIK,
        "CFBundleName": GORUNEN_AD,
        "CFBundleDisplayName": GORUNEN_AD,
        "CFBundleShortVersionString": argv[2],
        "CFBundleVersion": argv[2],
        "LSUIElement": False,
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
        "NSHumanReadableCopyright": "AGPL-3.0-only",
    })
    with yol.open("wb") as f:
        plistlib.dump(p, f)
    print(f"Info.plist güncellendi: {KIMLIK} {argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
