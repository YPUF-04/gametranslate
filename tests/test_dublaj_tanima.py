# SPDX-License-Identifier: AGPL-3.0-only
"""Oyun sesinden sahne tanıma (PROTOKOL 21.4): numpy ile sentezlenmiş konuşma + müzik + düzey değişimi."""
from __future__ import annotations

import numpy as np
import pytest

from kopru.dublaj import tanima as T

SR = 16000


def _sahne(tohumlar, muzik=None, muzik_db=0.0, kazanc=1.0, bosluk_tohum=0, sure=2.5):
    r = np.random.default_rng(bosluk_tohum)
    parca, baslar, t = [np.zeros(int(1.5 * SR), np.float32)], [], 1.5
    for k in tohumlar:
        s = T.sentetik_konusma(k, sure)
        baslar.append(t)
        parca.append(s)
        t += len(s) / SR
        g = r.uniform(0.5, 1.5)
        parca.append(np.zeros(int(g * SR), np.float32))
        t += g
    x = np.concatenate(parca)
    if muzik is not None:
        x = x + T.sentetik_muzik(muzik, len(x) / SR + 0.1)[:len(x)] * 10 ** (muzik_db / 20)
    return (x * kazanc).astype(np.float32), baslar


def _akit(x, dizin):
    tn = T.Tanici(dizin)
    olay = []
    for i in range(0, len(x), SR // 4):
        for e in tn.besle(x[i:i + SR // 4]):
            olay.append((min(len(x), i + SR // 4) / SR, e))
    return olay


@pytest.fixture(scope="module")
def kayitli():
    tohumlar = list(range(100, 116))
    x, baslar = _sahne(tohumlar, bosluk_tohum=1)
    d = T.Dizin()
    for i, b in enumerate(baslar):
        d.ekle(i, T.iz_cikar(x, SR, b, b + 2.5))
    return tohumlar, d


def test_akis_ve_toplu_iz_ayni():
    x = T.sentetik_konusma(5, 3.0)
    a = T.AkisIz()
    akis = []
    for i in range(0, len(x), 4000):
        akis += a.besle(x[i:i + 4000])
    akis += a.besle(np.zeros(1600, np.float32), son=True)
    toplu = T.iz_cikar(x, SR, 0.0, None)
    assert sorted((h, t) for t, h in akis) == sorted((h, t) for h, t in toplu)
    assert len(toplu) > 100


def test_ses_duzeyinden_bagimsiz():
    x = T.sentetik_konusma(7, 2.0)
    a = {tuple(v) for v in T.iz_cikar(x, SR)}
    b = {tuple(v) for v in T.iz_cikar(x * 0.8, SR)}
    c = {tuple(v) for v in T.iz_cikar(x * 1.2, SR)}
    assert len(a & b) / len(a) > 0.95 and len(a & c) / len(a) > 0.95


@pytest.mark.parametrize("muzik,db,kazanc,en_az", [(None, 0, 1.0, 16), (None, 0, 0.8, 16), (7, -6, 1.2, 14), (8, 0, 0.85, 14)])
def test_tanima_dogru_hizada(kayitli, muzik, db, kazanc, en_az):
    tohumlar, d = kayitli
    x, baslar = _sahne(tohumlar, muzik, db, kazanc, bosluk_tohum=5)
    olay = _akit(x, d)
    dogru = {e.kimlik for an, e in olay if abs((an - baslar[e.kimlik]) - e.ofset_sn) < 0.15}
    yanlis = [e for an, e in olay if abs((an - baslar[e.kimlik]) - e.ofset_sn) >= 0.15]
    assert not yanlis
    assert len(dogru) >= en_az
    gecikme = [an - baslar[e.kimlik] for an, e in olay]
    assert np.mean(gecikme) < 1.3


def test_yanlis_pozitif_yok(kayitli):
    _, d = kayitli
    x, _ = _sahne(list(range(500, 530)), 9, -3, bosluk_tohum=9)
    assert _akit(x, d) == []
    assert _akit(T.sentetik_muzik(11, 60), d) == []


def test_ara_sahnede_satirdan_once_taninabilir(kayitli):
    tohumlar, d = kayitli
    x, baslar = _sahne(tohumlar, kazanc=0.9, bosluk_tohum=1)       # aynı zamanlama (ara sahne)
    olay = _akit(x, d)
    gec = [an - baslar[e.kimlik] for an, e in olay]
    assert len({e.kimlik for _, e in olay}) == len(tohumlar)
    assert np.mean(gec) < 0.8


def test_dizin_sil_ve_df_siniri():
    d = T.Dizin()
    ortak = [[12345, i] for i in range(3)]
    for k in range(8):
        d.ekle(k, ortak + [[k * 1000 + 7, 0]])
    assert d.ara(12345) == []                 # 8 satırda geçiyor: yok sayılır
    assert d.ara(7) == [(0, 0)]
    d.sil(0)
    assert d.ara(7) == [] and len(d) == 7
    d.ekle(1, [[5, 1]] * 9)                   # satır içinde çok tekrar: yok sayılır
    assert d.ara(5) == []


def test_iz_bayt_gidis_donus():
    iz = [[1, -3], [2 ** 22, 40]]
    assert T.bayt_iz(T.iz_bayt(iz)) == iz
    assert T.bayt_iz(None) == []
