# SPDX-License-Identifier: AGPL-3.0-only
"""Hugging Face modelini indirirken yüzde bildirir (en iyi çaba; olmazsa belirsiz ilerleme)."""
from __future__ import annotations

import asyncio
import fnmatch
from pathlib import Path
from typing import Any

from .temel import DublajHatasi, IlerlemeCb


def _onbellek_boyutu(repo_id: str) -> int:
    """Bu modelin Hugging Face önbelleğindeki (tamamlanmış + yarım) toplam bayt sayısı."""
    try:
        from huggingface_hub import constants
        kok = Path(constants.HF_HUB_CACHE) / ("models--" + repo_id.replace("/", "--")) / "blobs"
        return sum(f.stat().st_size for f in kok.iterdir() if f.is_file()) if kok.exists() else 0
    except Exception:
        return 0


def _beklenen_boyut(repo_id: str, desenler: list[str] | None) -> int:
    try:
        from huggingface_hub import HfApi
        bilgi: Any = HfApi().model_info(repo_id, files_metadata=True)
        return sum((s.size or 0) for s in bilgi.siblings
                   if not desenler or any(fnmatch.fnmatch(s.rfilename, d) for d in desenler))
    except Exception:
        return 0


async def indir(repo_id: str, desenler: list[str] | None, ilerleme_cb: IlerlemeCb | None,
                revizyon: str = "main") -> str:
    """`snapshot_download`u arka planda çalıştırır; bitince yerel klasör yolunu döndürür."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError as e:
        raise DublajHatasi("dublaj_paket_yok", "huggingface_hub") from e
    if ilerleme_cb:
        ilerleme_cb(0.0, "indiriliyor")
    toplam = await asyncio.to_thread(_beklenen_boyut, repo_id, desenler)
    basla = _onbellek_boyutu(repo_id)
    gorev = asyncio.get_running_loop().run_in_executor(
        None, lambda: snapshot_download(repo_id=repo_id, repo_type="model", revision=revizyon,
                                        allow_patterns=desenler))
    try:
        while not gorev.done():
            await asyncio.wait({gorev}, timeout=1.0)
            if ilerleme_cb and toplam > 0:
                inen = max(0, _onbellek_boyutu(repo_id) - basla)
                ilerleme_cb(min(99.0, 100.0 * inen / toplam), "indiriliyor")
        yol = await gorev
    except DublajHatasi:
        raise
    except Exception as e:
        raise DublajHatasi("dublaj_indirme_hata", f"{type(e).__name__}: {e}") from e
    if ilerleme_cb:
        ilerleme_cb(100.0, "indiriliyor")
    return str(yol)
