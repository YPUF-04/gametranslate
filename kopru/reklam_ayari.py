# SPDX-License-Identifier: AGPL-3.0-only
"""Reklam ayarı (program sahibi doldurur; PROTOKOL 17.4).

"+30 dk ekle" düğmesine basılınca oynatılacak video reklamın VAST adresi. Boş bırakılırsa reklam yerine
15 saniyelik "destek" ekranı gösterilir ve süre yine eklenir. Gelişmiş ayarlardaki `erisim.vast_adresi`
bu değeri ezer. Yalnız `https://` ile başlayan adresler kullanılır.

Örnek (Google Ad Manager): "https://pubads.g.doubleclick.net/gampad/ads?iu=/1234/oyun_dublaj&sz=640x480&gdfp_req=1&output=vast&env=vp&unviewed_position_start=1&correlator=[TIMESTAMP]"
Nasıl alınır: docs/kullanim/reklam-ve-kodlar.md
"""
VAST_ADRESI = ""
