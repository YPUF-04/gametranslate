# SPDX-License-Identifier: AGPL-3.0-only
"""Bu bilgisayarda yerel "Dosya aç" penceresi (video dublajı için) ve "Klasörde göster".

Pencere ayrı bir süreçte açılır (tkinter ana iş parçacığı ister; sunucuyu bloklamasın):
paketli programda `exe --dosya-sec`, değilse `python -m kopru.dosya_sec`. Seçilen yol stdout'a JSON yazılır.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys

UZANTI_DESENI = "*.mp4 *.mkv *.mov *.webm *.avi"


def komut() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--dosya-sec"]
    return [sys.executable, "-m", "kopru.dosya_sec"]


async def sec() -> str | None:
    bayrak = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    try:
        s = await asyncio.create_subprocess_exec(*komut(), stdout=asyncio.subprocess.PIPE,
                                                 stderr=asyncio.subprocess.DEVNULL, creationflags=bayrak)
        cikti, _ = await asyncio.wait_for(s.communicate(), 600)
        v = json.loads(cikti.decode("utf-8") or "{}")
        return v.get("yol") or None
    except Exception:   # noqa: BLE001 — pencere açılamadı: "seçilmedi" say
        return None


def pencere_ac() -> str | None:
    import tkinter as tk
    from tkinter import filedialog
    kok = tk.Tk()
    kok.withdraw()
    kok.attributes("-topmost", True)
    yol = filedialog.askopenfilename(title="Türkçe dublajlanacak oyun videosunu seçin",
                                     filetypes=[("Video", UZANTI_DESENI), ("Tüm dosyalar", "*.*")])
    kok.destroy()
    return yol or None


def klasorde_goster(yol: str) -> None:
    bayrak = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", os.path.normpath(yol)], creationflags=bayrak)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", yol])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(yol) or "."])


def main() -> int:
    try:
        yol = pencere_ac()
    except Exception:   # noqa: BLE001
        yol = None
    sys.stdout.write(json.dumps({"yol": yol}, ensure_ascii=False))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
