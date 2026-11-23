# SPDX-License-Identifier: AGPL-3.0-only
"""Kullanıcı hatası (0.1.5): "Hang up" çevrilmeden "Hang up" olarak gösteriliyordu."""
from __future__ import annotations

import asyncio

from kopru.ceviri import ingilizce
from kopru.ceviri.temel import Ceviri
from kopru.ceviri.yonetici import CeviriYoneticisi


class Motor:
    kod = "m"
    ad = "M"
    anahtar_gerekli = False
    cevrimdisi = False
    ucretsiz = True
    baglam_destekler = True

    def __init__(self, ilk, ikinci):
        self.ilk, self.ikinci, self.istekler = ilk, ikinci, []

    async def cevir(self, metinler, kaynak, hedef, sozluk, aciklama=False, baglam=None, **_):
        ipucu = getattr(baglam, "ipucu", "") or ""
        self.istekler.append((list(metinler), ipucu))
        tablo = self.ikinci if "MUST translate" in ipucu else self.ilk
        return [Ceviri(tablo.get(m, m)) for m in metinler]


def test_siradan_ingilizce_tanima():
    assert ingilizce.siradan_ingilizce_mi("Hang up")
    assert ingilizce.siradan_ingilizce_mi("Call back")
    assert ingilizce.siradan_ingilizce_mi("SKIP")
    assert not ingilizce.siradan_ingilizce_mi("Vice City")
    assert not ingilizce.siradan_ingilizce_mi("Lucia")
    assert not ingilizce.siradan_ingilizce_mi("R2")


def test_cevrilmeden_donen_satir_zorla_yeniden_sorulur():
    m = Motor(ilk={"Where are you?": "Neredesin?"}, ikinci={"Hang up": "Telefonu kapat"})
    y = CeviriYoneticisi(m, None, None)
    r = asyncio.run(y.cevir(["Hang up", "Where are you?", "Vice City"]))
    assert [c.metin for c in r] == ["Telefonu kapat", "Neredesin?", "Vice City"]
    assert len(m.istekler) == 2 and m.istekler[1][0] == ["Hang up"]   # isim yeniden sorulmaz


def test_ikinci_deneme_de_aynıysa_ilk_sonuc_kalir_ve_sozluk_dokunulmaz():
    m = Motor(ilk={}, ikinci={})
    y = CeviriYoneticisi(m, None, None)
    y.terimler = {"Skip": "Skip"}
    r = asyncio.run(y.cevir(["Skip", "Hang up"]))
    assert [c.metin for c in r] == ["Skip", "Hang up"]
    assert m.istekler[1][0] == ["Hang up"]
