# SPDX-License-Identifier: AGPL-3.0-only
"""paketleme/velopack_delta.py: Linux'ta üretilen delta'nın sürüm dosyalarına işlenmesi (CI "delta" işi).

Gerçek `vpk delta generate` / `vpk delta patch` (1.2.161) Linux benzetimiyle ayrıca doğrulandı (rapor); burada
dosya biçimleri vpk'nın yazdığı örnekle sınanır."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "paketleme"))
import velopack_delta as vd  # noqa: E402

TAM = "AltYaziKoprusu.Program-0.1.3-full.nupkg"


def _yayin(tmp_path: Path) -> Path:
    y = tmp_path / "yayin"
    y.mkdir()
    (y / TAM).write_bytes(b"tam paket")
    # vpk 1.2.161'in --delta none ile yazdığı biçim (BOM'suz, boşluksuz; önceki sürüm de listede)
    (y / "releases.win.json").write_text(json.dumps({"Assets": [
        {"PackageId": "AltYaziKoprusu.Program", "Version": "0.1.3", "Type": "Full", "FileName": TAM, "SHA1": "A",
         "SHA256": "B", "Size": 9, "NotesMarkdown": "# Notlar", "NotesHTML": "<h1>Notlar</h1>"},
        {"PackageId": "AltYaziKoprusu.Program", "Version": "0.1.2", "Type": "Full",
         "FileName": "AltYaziKoprusu.Program-0.1.2-full.nupkg", "SHA1": "C", "SHA256": "D", "Size": 1,
         "NotesMarkdown": "", "NotesHTML": ""}]}, separators=(",", ":")), encoding="utf-8")
    (y / "assets.win.json").write_text(json.dumps([{"RelativeFileName": "AltYaziKoprusu.Program-win-Setup.exe",
                                                    "Type": "Installer"}, {"RelativeFileName": TAM, "Type": "Full"}]),
                                       encoding="utf-8")
    (y / "RELEASES").write_bytes("﻿C AltYaziKoprusu.Program-0.1.2-full.nupkg 1\nA " .encode() + TAM.encode() + b" 9")
    (y / "AltYaziKoprusu-Windows-Kur.exe").write_bytes(b"kur")
    (y / "SHA256SUMS.txt").write_text("eski\n")
    return y


def test_delta_kaydi_sha_boyut_notlar_ve_ozetler(tmp_path):
    y = _yayin(tmp_path)
    d = tmp_path / "delta.nupkg"
    d.write_bytes(b"delta icerigi")
    releases_once = (y / "RELEASES").read_bytes()
    hedef = vd.delta_ekle(y, d, "0.1.3")
    assert hedef.name == "AltYaziKoprusu.Program-0.1.3-delta.nupkg" and hedef.read_bytes() == b"delta icerigi"
    a = json.loads((y / "releases.win.json").read_text(encoding="utf-8"))["Assets"]
    assert [(x["Version"], x["Type"]) for x in a] == [("0.1.3", "Full"), ("0.1.3", "Delta"), ("0.1.2", "Full")]
    de = a[1]
    assert de["SHA256"] == hashlib.sha256(b"delta icerigi").hexdigest().upper()
    assert de["SHA1"] == hashlib.sha1(b"delta icerigi").hexdigest().upper() and de["Size"] == 13
    assert de["NotesMarkdown"] == "# Notlar" and de["PackageId"] == "AltYaziKoprusu.Program"
    assert sorted(de) == sorted(a[0])                         # vpk'nın Full/Delta kayıtlarıyla aynı alanlar
    assert json.loads((y / "assets.win.json").read_text())[0] == {"RelativeFileName": hedef.name, "Type": "Delta"}
    assert (y / "RELEASES").read_bytes() == releases_once     # vpk 1.2.161 de delta'yı buraya yazmaz
    satirlar = (y / "SHA256SUMS.txt").read_text().splitlines()
    adlar = [s.split("  ", 1)[1] for s in satirlar]
    assert adlar == sorted(adlar, key=str.lower) and "SHA256SUMS.txt" not in adlar and hedef.name in adlar
    assert f"{hashlib.sha256(b'delta icerigi').hexdigest()}  {hedef.name}" in satirlar
    assert not (y / "SHA256SUMS.txt").read_bytes().startswith(b"\xef\xbb\xbf")


def test_iki_kez_calisinca_kayit_cogalmaz(tmp_path):
    y = _yayin(tmp_path)
    d = tmp_path / "delta.nupkg"
    d.write_bytes(b"x")
    vd.delta_ekle(y, d, "0.1.3")
    vd.main([str(y), str(y / "AltYaziKoprusu.Program-0.1.3-delta.nupkg"), "0.1.3"])
    a = json.loads((y / "releases.win.json").read_text())["Assets"]
    assert [x["Type"] for x in a].count("Delta") == 1
    assert [x["RelativeFileName"] for x in json.loads((y / "assets.win.json").read_text())].count(
        "AltYaziKoprusu.Program-0.1.3-delta.nupkg") == 1


def test_tam_paket_kaydi_yoksa_hata(tmp_path):
    y = _yayin(tmp_path)
    d = tmp_path / "delta.nupkg"
    d.write_bytes(b"x")
    with pytest.raises(ValueError):
        vd.delta_ekle(y, d, "9.9.9")


def test_is_akisi_delta_linux_isinde_ve_yayin_onu_bekliyor():
    """YAML ayrıştırıcısı bağımlılık değil: iş blokları metin olarak denetlenir."""
    m = (Path(__file__).resolve().parents[1] / ".github/workflows/windows-paket.yml").read_text(encoding="utf-8")
    bloklar = {}
    ad = None
    for satir in m.splitlines():
        if satir.startswith("  ") and not satir.startswith("   ") and satir.rstrip().endswith(":") and not satir.lstrip().startswith("#"):
            ad = satir.strip()[:-1]
            bloklar[ad] = []
        elif ad:
            bloklar[ad].append(satir)
    delta, yayin, paket = ("\n".join(bloklar[k]) for k in ("delta", "yayinla", "paket"))
    assert "runs-on: ubuntu-latest" in delta and "needs: paket" in delta
    assert "dotnet tool install --global vpk --version 1.2.161" in delta and "vpk delta generate" in delta
    assert "vpk delta patch" in delta and "paketleme/velopack_delta.py" in delta and "name: AltYaziKoprusu-Windows-son" in delta
    assert "needs: [paket, delta]" in yayin and "name: AltYaziKoprusu-Windows-son" in yayin
    assert "--delta none" in paket and "'--packTitle','AltYazıKöprüsü'" in paket   # Türkçe kısayol adı korunur
    assert "surum: ${{ steps.surum.outputs.surum }}" in paket
