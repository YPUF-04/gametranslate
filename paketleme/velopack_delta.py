# SPDX-License-Identifier: AGPL-3.0-only
"""Velopack delta paketini sürüm dosyalarına ekler (CI'nin Linux işi; PROTOKOL §8, KARARLAR "Delta üretimi").

Windows'taki `vpk pack` delta adımı, paketin içindeki Türkçe adlı başlatıcıyı (`AltYazıKöprüsü_ExecutionStub.exe`)
Windows zstd.exe'si açamadığı için düşer (velopack#1105; 1.2.161'de var, düzeltmesi yalnız ön sürümde). Windows işi bu
durumda delta'sız paketler. Linux işi aynı vpk 1.2.161 ile `vpk delta generate` çalıştırır (Linux'ta zstd UTF-8 dosya
adlarını sorunsuz açar) ve bu betik üretilen delta'yı sürüm dosyalarına işler:

- `AltYaziKoprusu.Program-<sürüm>-delta.nupkg` yayın klasörüne kopyalanır,
- `releases.<kanal>.json`: aynı sürümün Full kaydının hemen arkasına Delta kaydı (SHA1, SHA256, boyut, notlar),
- `assets.<kanal>.json`: başa `{"RelativeFileName": ..., "Type": "Delta"}` (vpk'nın yazdığı sırayla),
- `RELEASES` değişmez (vpk 1.2.161 de delta'yı oraya yazmaz),
- `SHA256SUMS.txt` yeniden yazılır ("<küçük harfli özet>  <ad>", ada göre sıralı, BOM'suz UTF-8).

Kullanım: python paketleme/velopack_delta.py <yayin_klasoru> <delta.nupkg> <surum> [--paket AltYaziKoprusu.Program] [--kanal win]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

PAKET = "AltYaziKoprusu.Program"
KANAL = "win"
OZET = "SHA256SUMS.txt"


def _ozet(yol: Path, ad: str) -> str:
    h = hashlib.new(ad)
    with yol.open("rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()


def _json_oku(yol: Path) -> Any:
    return json.loads(yol.read_text(encoding="utf-8-sig"))


def _json_yaz(yol: Path, veri: Any) -> None:
    # vpk ile aynı biçim: boşluksuz, BOM'suz
    yol.write_text(json.dumps(veri, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def delta_ekle(yayin: Path, delta: Path, surum: str, paket: str = PAKET, kanal: str = KANAL) -> Path:
    """Delta'yı yayın klasörüne işler; hedef dosya yolunu döndürür. Tam paket kaydı yoksa ValueError."""
    ad = f"{paket}-{surum}-delta.nupkg"
    hedef = yayin / ad
    if delta.resolve() != hedef.resolve():
        shutil.copyfile(delta, hedef)
    rj = yayin / f"releases.{kanal}.json"
    veri = _json_oku(rj)
    varliklar: list[dict[str, Any]] = veri["Assets"]
    tam = next((a for a in varliklar if a.get("Type") == "Full" and a.get("Version") == surum), None)
    if tam is None:
        raise ValueError(f"{rj.name} içinde {surum} tam paket kaydı yok")
    kayit = {"PackageId": tam.get("PackageId", paket), "Version": surum, "Type": "Delta", "FileName": ad,
             "SHA1": _ozet(hedef, "sha1").upper(), "SHA256": _ozet(hedef, "sha256").upper(),
             "Size": hedef.stat().st_size, "NotesMarkdown": tam.get("NotesMarkdown", ""),
             "NotesHTML": tam.get("NotesHTML", "")}
    varliklar[:] = [a for a in varliklar if not (a.get("Type") == "Delta" and a.get("Version") == surum)]
    varliklar.insert(varliklar.index(tam) + 1, kayit)
    _json_yaz(rj, veri)
    aj = yayin / f"assets.{kanal}.json"
    if aj.exists():
        liste = [a for a in _json_oku(aj) if a.get("RelativeFileName") != ad]
        liste.insert(0, {"RelativeFileName": ad, "Type": "Delta"})
        _json_yaz(aj, liste)
    ozetleri_yaz(yayin)
    return hedef


def ozetleri_yaz(yayin: Path) -> None:
    """SHA256SUMS.txt: eski güncelleyicinin okuduğu biçim (Windows işindeki PowerShell adımıyla aynı)."""
    satirlar = [f"{_ozet(p, 'sha256')}  {p.name}" for p in sorted(yayin.iterdir(), key=lambda p: p.name.lower())
                if p.is_file() and p.name != OZET]
    (yayin / OZET).write_bytes(("\n".join(satirlar) + "\n").encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("yayin", type=Path)
    a.add_argument("delta", type=Path)
    a.add_argument("surum")
    a.add_argument("--paket", default=PAKET)
    a.add_argument("--kanal", default=KANAL)
    g = a.parse_args(argv)
    hedef = delta_ekle(g.yayin, g.delta, g.surum, g.paket, g.kanal)
    print(f"Delta eklendi: {hedef.name} ({hedef.stat().st_size} bayt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
