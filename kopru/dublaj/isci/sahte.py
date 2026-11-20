# SPDX-License-Identifier: AGPL-3.0-only
"""Sahte işçi (yalnız testler ve deneme için): ağır paket gerektirmeden kanalı uçtan uca sınar.

`KOPRU_ISCI_SAHTE=1` ile `python -m kopru.dublaj.isci` bu işleyiciyi kullanır.
"""
from __future__ import annotations

import os
import time
from typing import Any, Callable

from .sunucu import IsciHatasi, Is


class SahteIsleyici:
    def __init__(self) -> None:
        self._gonder: Callable[[dict[str, Any]], None] = lambda n: None

    def gonder_bagla(self, gonder: Callable[[dict[str, Any]], None]) -> None:
        self._gonder = gonder

    def cihaz_bilgisi(self) -> dict[str, Any]:
        print("kütüphane gürültüsü: bu satır kanalı bozmamalı")   # stdout'a yazan kütüphaneleri taklit eder
        return {"cihaz": "cpu", "ekran_karti": None, "vram_gb": None, "sahte": True}

    def k_merhaba(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        return self.cihaz_bilgisi()

    def k_yanki(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        return {"metin": v.get("metin"), "pcm": v.get("pcm")}

    def k_yavas(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        for i in range(int(v.get("adim", 50))):
            is_.ilerleme(i * 2, f"adım {i}")
            time.sleep(0.02)
        return {"bitti": True}

    def k_hata(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        raise IsciHatasi("dublaj_uretim_hata", "sahte hata")

    def k_coz(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        os._exit(3)    # çökme taklidi

    def k_parca_yolla(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        self._gonder({"olay": "parca", "pcm": v.get("pcm", ""), "sr": 16000, "sure_sn": 1.0, "kaynak": "surec"})
        return {}
