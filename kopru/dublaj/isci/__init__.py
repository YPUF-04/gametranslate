# SPDX-License-Identifier: AGPL-3.0-only
"""Dublaj işçi süreci (PROTOKOL 14.2).

Bu paket, dublaj paketinin kendi Python'unda `python -E -s -m kopru.dublaj.isci` ile çalışır.
Ana programdan bağımsızdır: yalnız standart kütüphaneyi, numpy'ı ve (tembel) ağır paketleri kullanır.
`protokol`, `mantik` ve `sunucu` saf modüllerdir (torch gerekmez) ve testlerde doğrudan sınanır.
"""
SURUM = "1"
