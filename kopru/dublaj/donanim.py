# SPDX-License-Identifier: AGPL-3.0-only
"""Bilgisayarı tanır (ekran kartı, bellek) ve uygun ses motorunu önerir."""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass

CHATTERBOX_EN_AZ_VRAM_GB = 6.0


@dataclass
class Donanim:
    tur: str = "yok"                  # "cuda" | "mps" | "yok"
    ekran_karti: str | None = None    # ör. "NVIDIA GeForce RTX 3060"
    vram_gb: float | None = None
    ram_gb: float | None = None


def _torch_bak() -> Donanim | None:
    """torch kuruluysa ondan sor (en güvenilir yol); yoksa None."""
    try:
        import torch  # tembel ve isteğe bağlı
    except Exception:
        return None
    try:
        if torch.cuda.is_available():
            ozel = torch.cuda.get_device_properties(0)
            return Donanim("cuda", torch.cuda.get_device_name(0), round(ozel.total_memory / 1024 ** 3, 1))
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return Donanim("mps", "Apple Silicon (MPS)", None)
    except Exception:
        pass
    return Donanim()


def _nvidia_smi() -> Donanim | None:
    """torch yokken: `nvidia-smi` ile ekran kartı adı ve belleği."""
    try:
        cikti = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4, check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        ad, bellek = [p.strip() for p in cikti.strip().splitlines()[0].split(",", 1)]
        return Donanim("cuda", ad, round(float(bellek) / 1024.0, 1))
    except Exception:
        return None


def ram_gb() -> float | None:
    try:
        import psutil  # varsa
        return round(psutil.virtual_memory().total / 1024 ** 3, 1)
    except Exception:
        pass
    try:
        if sys.platform == "win32":
            import ctypes

            class _Bellek(ctypes.Structure):
                _fields_ = [("uzunluk", ctypes.c_ulong), ("yuk", ctypes.c_ulong),
                            ("toplam", ctypes.c_ulonglong), ("bos", ctypes.c_ulonglong),
                            ("sayfa_t", ctypes.c_ulonglong), ("sayfa_b", ctypes.c_ulonglong),
                            ("sanal_t", ctypes.c_ulonglong), ("sanal_b", ctypes.c_ulonglong),
                            ("ek", ctypes.c_ulonglong)]
            m = _Bellek()
            m.uzunluk = ctypes.sizeof(m)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):  # type: ignore[attr-defined]
                return round(m.toplam / 1024 ** 3, 1)
            return None
        return round(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 1024 ** 3, 1)
    except Exception:
        return None


def algila() -> Donanim:
    d = _torch_bak()
    if d is None or d.tur == "yok":
        smi = _nvidia_smi()   # torch var ama GPU görmüyorsa ya da hiç yoksa: kart yine de olabilir
        if smi is not None and (d is None or d.tur == "yok"):
            d = Donanim(smi.tur, smi.ekran_karti, smi.vram_gb)
    d = d or Donanim()
    d.ram_gb = ram_gb()
    return d


def onerilen(d: Donanim) -> str:
    """CUDA ve en az 6 GB ekran kartı belleği varsa chatterbox; değilse pocket."""
    if d.tur == "cuda" and d.vram_gb is not None and d.vram_gb >= CHATTERBOX_EN_AZ_VRAM_GB:
        return "chatterbox"
    return "pocket"


def cihaz_sec() -> str:
    """Motorların kullanacağı torch cihazı: cuda, yoksa mps, yoksa cpu."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"
