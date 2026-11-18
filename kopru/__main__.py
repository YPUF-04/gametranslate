# SPDX-License-Identifier: AGPL-3.0-only
"""python -m kopru"""
from __future__ import annotations

import argparse
import asyncio
import logging
import webbrowser

from aiohttp import web

from . import ayarlar, metinler
from .sunucu import DURUM, GUNCELLEME, lan_adresleri, uygulama_olustur

ORNEKLER = [
    ("Hello! This is a test subtitle.", "Merhaba! Bu bir deneme altyazısıdır.", None),
    ("We should head back to the base.", "Üsse geri dönmeliyiz.", "Ellie"),
    ("Watch out, they're coming!", "Dikkat et, geliyorlar!", "Joel"),
]


async def demo_dongusu(app: web.Application) -> None:
    from .isleme import sure_ms
    d = app[DURUM]
    i = 0
    while True:
        asil, metin, kisi = ORNEKLER[i % len(ORNEKLER)]
        d.yayin.yayinla("yazi", {"id": f"demo{i}", "metin": metin, "asil": asil,
                                 "tur": "altyazi", "konusan": kisi, "sure_ms": sure_ms(metin)})
        i += 1
        await asyncio.sleep(sure_ms(metin) / 1000 + 1.5)


def main() -> None:
    p = argparse.ArgumentParser(prog="kopru", description="AltYazıKöprüsü")
    p.add_argument("--demo", action="store_true", help="örnek altyazıları döngüyle gönder")
    p.add_argument("--tarayici-acma", action="store_true", help="paneli tarayıcıda açma")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    ayar = ayarlar.yukle()
    dil, kapi = ayar["arayuz_dili"], ayar["kapi"]
    app = uygulama_olustur(ayar)

    if a.demo:
        async def baslat(app: web.Application) -> None:
            app["demo"] = asyncio.create_task(demo_dongusu(app))

        async def durdur(app: web.Application) -> None:
            app["demo"].cancel()
        app.on_startup.append(baslat)
        app.on_cleanup.append(durdur)
        print(metinler.mesaj("demo_acik", dil))

    async def guncelleme_bak(app: web.Application) -> None:
        app[GUNCELLEME].arka_planda_denetle()   # günde en çok bir kez; ayar kapalıysa hiç
    app.on_startup.append(guncelleme_bak)

    for ip in lan_adresleri():
        print(metinler.mesaj("tv_adres", dil).format(adres=f"http://{ip}:{kapi}/tv"))
    panel = f"http://127.0.0.1:{kapi}/"
    print(metinler.mesaj("panel_adres", dil).format(adres=panel))
    if not a.tarayici_acma:
        async def ac(_: web.Application) -> None:
            webbrowser.open(panel)
        app.on_startup.append(ac)
    try:
        web.run_app(app, host="0.0.0.0", port=kapi, print=None)
    except KeyboardInterrupt:
        pass
    print(metinler.mesaj("durdu", dil))


if __name__ == "__main__":
    main()
