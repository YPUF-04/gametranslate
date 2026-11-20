# SPDX-License-Identifier: AGPL-3.0-only
"""Kullanıcı hatası: "KILLER" gibi tek, büyük harfli sıradan kelimeler isim sanılıp çevrilmiyordu."""
from __future__ import annotations

import asyncio

from kopru.ceviri.istem import sabit_istem
from kopru.ceviri.temel import Ceviri
from kopru.ceviri.yonetici import CeviriYoneticisi
from kopru.hafiza import Hafiza
from kopru.onbellek import Onbellek


def test_istem_tek_kelimeyi_ve_etiketleri_cevirtir():
    p = sabit_istem("en", "tr", {}, False)
    assert "KILLER => KATİL" in p and "A capital letter does NOT make a word a name" in p
    assert "single ordinary word is still translated" in p
    assert "Never list common words, roles, menu labels" in p


class Motor:
    kod = "m"
    ad = "M"
    anahtar_gerekli = False
    cevrimdisi = True
    ucretsiz = True

    def __init__(self, cevap):
        self.cevap = cevap
        self.cagri = 0

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False, **_):
        self.cagri += 1
        return [Ceviri(self.cevap.get(m, m)) for m in metinler]


def test_onbellekteki_cevrilmemis_satir_yeniden_sorulur(tmp_path):
    o = Onbellek(tmp_path / "c.db")
    o.koy("KILLER", "otomatik", "tr", "varsayilan", "KILLER", None, False)   # eski sürümün hatası
    m = Motor({"KILLER": "KATİL"})
    y = CeviriYoneticisi(m, None, o)
    r = asyncio.run(y.cevir(["KILLER"]))
    assert r[0].metin == "KATİL" and m.cagri == 1
    # artık önbellekten gelir
    assert asyncio.run(y.cevir(["KILLER"]))[0].metin == "KATİL" and m.cagri == 1


def test_gercek_isim_bir_kez_sorulur_sonra_onbellekten(tmp_path):
    o = Onbellek(tmp_path / "c.db")
    o.koy("Vice City", "otomatik", "tr", "varsayilan", "Vice City", None, False)
    m = Motor({})   # motor ismi aynen bırakır
    y = CeviriYoneticisi(m, None, o)
    assert asyncio.run(y.cevir(["Vice City"]))[0].metin == "Vice City" and m.cagri == 1
    assert asyncio.run(y.cevir(["Vice City"]))[0].metin == "Vice City" and m.cagri == 1


def test_sozlukteki_ve_kullanici_duzeltmesi_dokunulmaz(tmp_path):
    o = Onbellek(tmp_path / "c.db")
    o.koy("Lucia", "otomatik", "tr", "varsayilan", "Lucia", None, False)
    m = Motor({})
    y = CeviriYoneticisi(m, None, o)
    y.terimler = {"Lucia": "Lucia"}
    assert asyncio.run(y.cevir(["Lucia"]))[0].metin == "Lucia" and m.cagri == 0
    h = Hafiza("t", lambda: False)
    h.kaydet("OK", "OK", "kullanici")
    y2 = CeviriYoneticisi(m, None, None, hafiza=h)
    assert asyncio.run(y2.cevir(["OK"]))[0].metin == "OK" and m.cagri == 0
