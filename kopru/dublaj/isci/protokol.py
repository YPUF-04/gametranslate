# SPDX-License-Identifier: AGPL-3.0-only
"""İşçi kanalı: satır başına bir JSON nesnesi (PROTOKOL 14.2). Ses: base64 float32 (küçük-uçlu) mono."""
from __future__ import annotations

import base64
import json
from typing import Any

EN_COK_SATIR = 64 * 1024 * 1024


class ProtokolHatasi(Exception):
    pass


def kodla(nesne: dict[str, Any]) -> bytes:
    """Tek satır JSON (sonunda \\n). Türkçe harfler korunur."""
    return (json.dumps(nesne, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def coz(satir: bytes | str) -> dict[str, Any]:
    if isinstance(satir, bytes):
        if len(satir) > EN_COK_SATIR:
            raise ProtokolHatasi("satır çok uzun")
        satir = satir.decode("utf-8")
    try:
        v = json.loads(satir)
    except ValueError as e:
        raise ProtokolHatasi("bozuk JSON") from e
    if not isinstance(v, dict):
        raise ProtokolHatasi("nesne değil")
    return v


def pcm_kodla(pcm: Any) -> str:
    import numpy as np
    a = np.ascontiguousarray(np.asarray(pcm, dtype="<f4").reshape(-1))
    return base64.b64encode(a.tobytes()).decode("ascii")


def pcm_coz(veri: str) -> Any:
    import numpy as np
    ham = base64.b64decode(veri.encode("ascii"), validate=True)
    if len(ham) % 4:
        raise ProtokolHatasi("pcm boyu 4'ün katı değil")
    return np.frombuffer(ham, dtype="<f4").astype(np.float32)
