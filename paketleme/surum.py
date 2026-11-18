# SPDX-License-Identifier: AGPL-3.0-only
"""Sürüm numarasını yazdırır; pyproject.toml, kopru.SURUM ve (verilirse) git etiketi aynı olmalı.

Kullanım: python paketleme/surum.py [v0.2.0]   -> "0.2.0" yazar; uyuşmazsa hata kodu 1 ile çıkar.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def surumler() -> tuple[str, str]:
    toml = tomllib.loads((KOK / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    m = re.search(r'^SURUM\s*=\s*"([^"]+)"', (KOK / "kopru" / "__init__.py").read_text(encoding="utf-8"), re.M)
    return toml, (m.group(1) if m else "")


def main(argv: list[str]) -> int:
    toml, kod = surumler()
    if toml != kod:
        print(f"Sürüm uyuşmuyor: pyproject.toml={toml}, kopru/__init__.py={kod}. İkisini aynı yapın.", file=sys.stderr)
        return 1
    if len(argv) > 1 and argv[1].lstrip("v") != toml:
        print(f"Etiket {argv[1]} ama program sürümü {toml}. Önce sürüm numarasını güncelleyin.", file=sys.stderr)
        return 1
    print(toml)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
