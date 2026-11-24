# SPDX-License-Identifier: AGPL-3.0-only
"""PROTOKOL 20.2: küçük QR kodu üretici (bayt kipi, hata düzeltme M, sürüm 1-10) -> SVG. Bağımlılık yok.

ISO/IEC 18004'ün yayımlanmış kurallarına göre yazıldı: Reed-Solomon (GF(256), 0x11D), hizalama desenleri,
biçim/sürüm bilgisi (BCH), 8 maskeden ceza puanı en düşük olanı.
"""
from __future__ import annotations

# sürüm -> (blok başına hata düzeltme kod sözcüğü, [(blok sayısı, blok başına veri kod sözcüğü)]) — düzey M
_BLOKLAR = {
    1: (10, [(1, 16)]), 2: (16, [(1, 28)]), 3: (26, [(1, 44)]), 4: (18, [(2, 32)]), 5: (24, [(2, 43)]),
    6: (16, [(4, 27)]), 7: (18, [(4, 31)]), 8: (22, [(2, 38), (2, 39)]), 9: (22, [(3, 36), (2, 37)]),
    10: (26, [(4, 43), (1, 44)]),
}
_HIZALAMA = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42],
             9: [6, 26, 46], 10: [6, 28, 50]}
_KALAN_BIT = {1: 0, 2: 7, 3: 7, 4: 7, 5: 7, 6: 7, 7: 0, 8: 0, 9: 0, 10: 0}
EN_COK_BAYT = 213   # sürüm 10-M bayt kipi

# GF(256) tabloları
_US = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _US[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _US[_i] = _US[_i - 255]


def _carp(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else _US[_LOG[a] + _LOG[b]]


def _rs(veri: list[int], n: int) -> list[int]:
    ureteci = [1]
    for i in range(n):
        yeni = [0] * (len(ureteci) + 1)
        for j, c in enumerate(ureteci):
            yeni[j] ^= c
            yeni[j + 1] ^= _carp(c, _US[i])
        ureteci = yeni
    kalan = list(veri) + [0] * n
    for i in range(len(veri)):
        c = kalan[i]
        if c:
            for j in range(1, len(ureteci)):
                kalan[i + j] ^= _carp(ureteci[j], c)
    return kalan[len(veri):]


def _surum_sec(n: int) -> int:
    for v in range(1, 11):
        ec, gruplar = _BLOKLAR[v]
        kapasite = sum(b * d for b, d in gruplar)
        sayac = 8 if v < 10 else 16
        if 4 + sayac + 8 * n <= kapasite * 8:
            return v
    raise ValueError("QR için metin çok uzun")


def _kod_sozcukleri(veri: bytes, v: int) -> list[int]:
    ec, gruplar = _BLOKLAR[v]
    kapasite = sum(b * d for b, d in gruplar)
    bitler: list[int] = []

    def ekle(deger: int, uzunluk: int) -> None:
        bitler.extend((deger >> (uzunluk - 1 - i)) & 1 for i in range(uzunluk))
    ekle(0b0100, 4)
    ekle(len(veri), 8 if v < 10 else 16)
    for b in veri:
        ekle(b, 8)
    ekle(0, min(4, kapasite * 8 - len(bitler)))
    while len(bitler) % 8:
        bitler.append(0)
    sozcuk = [int("".join(map(str, bitler[i:i + 8])), 2) for i in range(0, len(bitler), 8)]
    dolgu = (0xEC, 0x11)
    i = 0
    while len(sozcuk) < kapasite:
        sozcuk.append(dolgu[i % 2])
        i += 1
    bloklar, ecler, k = [], [], 0
    for adet, boy in gruplar:
        for _ in range(adet):
            b = sozcuk[k:k + boy]
            k += boy
            bloklar.append(b)
            ecler.append(_rs(b, ec))
    out = []
    for i in range(max(len(b) for b in bloklar)):
        out += [b[i] for b in bloklar if i < len(b)]
    for i in range(ec):
        out += [e[i] for e in ecler]
    return out


def _bch(deger: int, ureteci: int, derece: int) -> int:
    d = deger << derece
    while d.bit_length() > derece:
        d ^= ureteci << (d.bit_length() - ureteci.bit_length())
    return (deger << derece) | d


_MASKELER = [
    lambda r, c: (r + c) % 2 == 0, lambda r, c: r % 2 == 0, lambda r, c: c % 3 == 0, lambda r, c: (r + c) % 3 == 0,
    lambda r, c: (r // 2 + c // 3) % 2 == 0, lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
    lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0, lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
]


def _iskelet(v: int) -> tuple[list[list[int | None]], list[list[bool]]]:
    n = 17 + 4 * v
    m: list[list[int | None]] = [[None] * n for _ in range(n)]
    sabit = [[False] * n for _ in range(n)]

    def koy(r: int, c: int, d: int) -> None:
        if 0 <= r < n and 0 <= c < n:
            m[r][c] = d
            sabit[r][c] = True
    for r0, c0 in ((0, 0), (0, n - 7), (n - 7, 0)):   # bulucu desenler + ayırıcı
        for r in range(-1, 8):
            for c in range(-1, 8):
                ic = 0 <= r <= 6 and 0 <= c <= 6
                koyu = ic and (r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4))
                koy(r0 + r, c0 + c, 1 if koyu else 0)
    for i in range(8, n - 8):   # zamanlama
        koy(6, i, 1 if i % 2 == 0 else 0)
        koy(i, 6, 1 if i % 2 == 0 else 0)
    pos = _HIZALAMA[v]
    for r in pos:
        for c in pos:
            if (r, c) in ((pos[0], pos[0]), (pos[0], pos[-1]), (pos[-1], pos[0])):   # bulucu desenlerin üstü
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    koy(r + dr, c + dc, 1 if max(abs(dr), abs(dc)) != 1 else 0)
    koy(n - 8, 8, 1)   # karanlık modül
    for i in range(9):  # biçim bilgisi alanlarını ayır
        for r, c in ((8, i), (i, 8)):
            if not sabit[r][c]:
                koy(r, c, 0)
    for i in range(8):
        koy(8, n - 1 - i, 0)
        koy(n - 1 - i, 8, 0)
    if v >= 7:
        bilgi = _bch(v, 0x1F25, 12)
        for i in range(18):
            b = (bilgi >> i) & 1
            koy(i // 3, n - 11 + i % 3, b)
            koy(n - 11 + i % 3, i // 3, b)
    return m, sabit


def _yerlestir(m: list[list[int | None]], sabit: list[list[bool]], sozcukler: list[int], v: int) -> None:
    n = len(m)
    bitler = [(s >> (7 - i)) & 1 for s in sozcukler for i in range(8)] + [0] * _KALAN_BIT[v]
    k = 0
    c = n - 1
    yukari = True
    while c > 0:
        if c == 6:
            c -= 1
        for i in range(n):
            r = n - 1 - i if yukari else i
            for dc in (0, 1):
                cc = c - dc
                if not sabit[r][cc]:
                    m[r][cc] = bitler[k] if k < len(bitler) else 0
                    k += 1
        yukari = not yukari
        c -= 2


def _bicim_yaz(m: list[list[int]], maske: int) -> None:
    n = len(m)
    bilgi = _bch((0b00 << 3) | maske, 0x537, 10) ^ 0x5412   # düzey M = 00

    def bit(i: int) -> int:
        return (bilgi >> i) & 1
    for i in range(6):
        m[i][8] = bit(i)
    m[7][8], m[8][8], m[8][7] = bit(6), bit(7), bit(8)
    for i in range(9, 15):
        m[8][14 - i] = bit(i)
    for i in range(8):
        m[8][n - 1 - i] = bit(i)
    for i in range(8, 15):
        m[n - 15 + i][8] = bit(i)
    m[n - 8][8] = 1


def _ceza(m: list[list[int]]) -> int:
    n = len(m)
    p = 0
    for satirlar in (m, [list(x) for x in zip(*m)]):
        for s in satirlar:
            uzun, onceki = 1, s[0]
            for x in s[1:]:
                if x == onceki:
                    uzun += 1
                else:
                    if uzun >= 5:
                        p += uzun - 2
                    uzun, onceki = 1, x
            if uzun >= 5:
                p += uzun - 2
            dizi = "".join(map(str, s))
            p += 40 * (dizi.count("10111010000") + dizi.count("00001011101"))
    for r in range(n - 1):
        for c in range(n - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                p += 3
    koyu = sum(map(sum, m))
    p += 10 * (abs(koyu * 20 - n * n * 10) // (n * n))
    return p


def matris(metin: str) -> list[list[int]]:
    veri = metin.encode("utf-8")
    v = _surum_sec(len(veri))
    sozcukler = _kod_sozcukleri(veri, v)
    taban, sabit = _iskelet(v)
    _yerlestir(taban, sabit, sozcukler, v)
    en, en_p = None, None
    for k, f in enumerate(_MASKELER):
        m = [[(x ^ 1 if (not sabit[r][c] and f(r, c)) else x) for c, x in enumerate(satir)]
             for r, satir in enumerate(taban)]   # type: ignore[operator]
        _bicim_yaz(m, k)   # type: ignore[arg-type]
        p = _ceza(m)   # type: ignore[arg-type]
        if en_p is None or p < en_p:
            en, en_p = m, p
    return en   # type: ignore[return-value]


def svg(metin: str, kenar: int = 4) -> str:
    m = matris(metin)
    n = len(m) + 2 * kenar
    yol = "".join(f"M{c + kenar},{r + kenar}h1v1h-1z" for r, s in enumerate(m) for c, x in enumerate(s) if x)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" shape-rendering="crispEdges">'
            f'<rect width="{n}" height="{n}" fill="#fff"/><path d="{yol}" fill="#000"/></svg>')
