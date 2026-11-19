# SPDX-License-Identifier: AGPL-3.0-only
"""Bilgisayar ekranında oyunun üstünde çeviri gösteren ayrı süreç (PROTOKOL 10.3).

Çalıştırma: `python -m kopru.katman --url http://127.0.0.1:8642/kopru/akis --ekran 1`
Paketli programda: `AltyaziKoprusu.exe --katman --url ... --ekran 1` (calistir.py `main(argv)`'a yönlendirir).
Tk yalnız bu süreçte içe aktarılır; sunucu bu paketten yalnız `yonetim` ve `mantik` modüllerini kullanır.
"""
from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    from .pencere import main as _main
    return _main(argv)
