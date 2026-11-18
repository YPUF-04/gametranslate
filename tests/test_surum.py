# SPDX-License-Identifier: AGPL-3.0-only
import importlib.util
from pathlib import Path

import kopru

yol = Path(__file__).resolve().parent.parent / "paketleme" / "surum.py"
belirtim = importlib.util.spec_from_file_location("surum_betigi", yol)
surum = importlib.util.module_from_spec(belirtim)
belirtim.loader.exec_module(surum)


def test_pyproject_ve_kod_ayni_surumde():
    toml, kod = surum.surumler()
    assert toml == kod == kopru.SURUM == kopru.__version__


def test_etiket_denetimi():
    assert surum.main(["x", "v" + kopru.SURUM]) == 0
    assert surum.main(["x", "v99.0.0"]) == 1
