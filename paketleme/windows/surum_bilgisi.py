# SPDX-License-Identifier: AGPL-3.0-only
"""PyInstaller --version-file içeriğini üretir (exe'nin Ayrıntılar sekmesi: şirket, ürün adı, sürüm).

Kullanım: python paketleme/windows/surum_bilgisi.py 0.2.0 paketleme/windows/surum-bilgisi.txt
"""
import sys

SABLON = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers=({a}, {b}, {c}, 0), prodvers=({a}, {b}, {c}, 0), mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041F04B0', [
      StringStruct('CompanyName', 'AltYazıKöprüsü katkıcıları'),
      StringStruct('FileDescription', 'AltYazıKöprüsü'),
      StringStruct('FileVersion', '{s}'),
      StringStruct('InternalName', 'AltYaziKoprusu'),
      StringStruct('LegalCopyright', 'AGPL-3.0-only'),
      StringStruct('OriginalFilename', 'AltYaziKoprusu.exe'),
      StringStruct('ProductName', 'AltYazıKöprüsü'),
      StringStruct('ProductVersion', '{s}')])]),
    VarFileInfo([VarStruct('Translation', [0x041F, 1200])])
  ]
)
"""


def uret(surum: str) -> str:
    sayilar = [int("".join(ch for ch in p if ch.isdigit()) or 0) for p in surum.split("-")[0].split(".")][:3]
    sayilar += [0] * (3 - len(sayilar))
    return SABLON.format(a=sayilar[0], b=sayilar[1], c=sayilar[2], s=surum)


if __name__ == "__main__":
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(uret(sys.argv[1]))
