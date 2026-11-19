# SPDX-License-Identifier: AGPL-3.0-only
"""python -m kopru"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import socket
import sys
import urllib.request
import webbrowser

from aiohttp import web

from . import ayarlar, metinler
from .sunucu import DURUM, GUNCELLEME, lan_adresleri, uygulama_olustur

log = logging.getLogger("kopru")

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


def ozdenetim_ceviri() -> int:
    """Çevrimdışı motoru uçtan uca dener: en->tr dil dosyasını geçici ayar klasörüne indirir ve çevirir (ağ gerekir)."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix="kopru-ozdenetim-") as gecici:
        os.environ["KOPRU_AYAR_DIZINI"] = gecici
        from .ceviri import yerel

        async def is_() -> str:
            await yerel.hazirla("en", "tr", lambda y: yaz(f"OZDENETIM indirme %{y}") if y % 25 == 0 else None)
            (c,) = await yerel.YerelMotor().cevir(["Hello, how are you?"], "en", "tr", {})
            return c.metin
        try:
            sonuc = asyncio.run(is_())
        except Exception as e:  # noqa: BLE001
            yaz(f"OZDENETIM HATA: cevrimdisi ceviri basarisiz: {type(e).__name__}: {e} {getattr(e, 'kod', '')}")
            return 1
    yaz(f"OZDENETIM ceviri={sonuc!r}")
    return 0 if sonuc.strip() and sonuc.strip().lower() != "hello, how are you?" else 1


def ozdenetim(ceviri: bool = False) -> int:
    """Paketin içinde ekran yazısı okuyucunun gerçekten çalıştığını dener (ekran gerekmez).

    ceviri=True: bunun yerine çevrimdışı çeviriyi dener (`--ozdenetim-ceviri`)."""
    if ceviri:
        return ozdenetim_ceviri()
    from PIL import Image, ImageDraw, ImageFont
    from . import okuma
    try:
        okuyucu = okuma.sec()
    except Exception as e:  # okuyucu yoksa açıkça söyle
        yaz(f"OZDENETIM HATA: okuyucu yok: {e}")
        return 1
    resim = Image.new("RGB", (900, 200), "black")
    try:
        yazi_tipi = ImageFont.load_default(size=64)
    except TypeError:
        yazi_tipi = ImageFont.load_default()
    ImageDraw.Draw(resim).text((30, 60), "HELLO WORLD", fill="white", font=yazi_tipi)
    try:
        satirlar = okuyucu.oku(resim)
    except Exception as e:
        yaz(f"OZDENETIM HATA: okuma basarisiz: {e}")
        return 1
    metin = " ".join(getattr(s, "metin", str(s)) for s in satirlar)
    yaz(f"OZDENETIM okuyucu={type(okuyucu).__module__} metin={metin!r}")
    return 0 if "HELLO" in metin.upper() else 1


def _konsolu_hazirla() -> None:
    # Windows konsolu Türkçe harflerde çökmesin; pencere yoksa (paketli .exe) sessiz geç.
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def yaz(metin: str) -> None:
    try:
        print(metin, flush=True)
    except Exception:
        pass


def gunluk_kur() -> None:
    """Konsol varsa konsola, yoksa (paketli pencere uygulaması) ayar klasöründeki dosyaya yazar."""
    bicim = "%(asctime)s %(name)s %(message)s"
    if sys.stderr is not None:
        logging.basicConfig(level=logging.INFO, format=bicim)
        return
    try:
        from logging.handlers import RotatingFileHandler
        dizin = ayarlar.ayar_dizini()
        dizin.mkdir(parents=True, exist_ok=True)
        isleyici = RotatingFileHandler(dizin / "kopru.log", maxBytes=512_000, backupCount=2, encoding="utf-8")
        logging.basicConfig(level=logging.INFO, format=bicim, handlers=[isleyici])
    except OSError:
        logging.basicConfig(level=logging.WARNING, handlers=[logging.NullHandler()])


KAPI_DENEME = 10   # ayarlı kapı doluysa bu kadar sonraki kapıya bakılır


def kapi_bos_mu(kapi: int) -> bool:
    """Kapıya bağlanabiliyor muyuz (asyncio ile aynı soket seçenekleri: POSIX'te SO_REUSEADDR, Windows'ta yok)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if sys.platform != "win32":
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", kapi))
        return True
    except OSError:
        return False
    finally:
        s.close()


def bizim_mi(kapi: int) -> bool:
    """Kapıda zaten çalışan bir AltYazıKöprüsü var mı (TV'nin de sorduğu /kopru/merhaba)."""
    try:
        acici = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # yerel istek: vekil kullanma
        with acici.open(f"http://127.0.0.1:{kapi}/kopru/merhaba", timeout=1) as y:
            return json.loads(y.read(4096)).get("uygulama") == "altyazikoprusu"
    except Exception:   # noqa: BLE001 — cevap vermeyen/başka program: bizim değil
        return False


def kapi_sec(kapi: int) -> tuple[str, int | None]:
    """("kullan", kapi) | ("zaten_acik", kapi) | ("yok", None)."""
    if kapi_bos_mu(kapi):
        return "kullan", kapi
    if bizim_mi(kapi):
        return "zaten_acik", kapi
    for yeni in range(kapi + 1, min(kapi + 1 + KAPI_DENEME, 65536)):
        if kapi_bos_mu(yeni):
            return "kullan", yeni
    return "yok", None


def main() -> None:
    # Ekran katmanı ayrı süreç olarak aynı programla açılır (paketli .exe'de -m kullanılamaz)
    if len(sys.argv) > 1 and sys.argv[1] == "--katman":
        _konsolu_hazirla()
        from .katman import main as katman_main
        raise SystemExit(katman_main(sys.argv[2:]))
    _konsolu_hazirla()
    p = argparse.ArgumentParser(prog="kopru", description="AltYazıKöprüsü")
    p.add_argument("--demo", action="store_true", help="örnek altyazıları döngüyle gönder")
    p.add_argument("--tarayici-acma", action="store_true", help="paneli tarayıcıda açma")
    p.add_argument("--ozdenetim", action="store_true", help="yazı okumayı dener ve çıkar (paket testi)")
    p.add_argument("--ozdenetim-ceviri", action="store_true",
                   help="çevrimdışı çeviriyi dener (dil dosyasını indirir) ve çıkar (paket testi)")
    a = p.parse_args()
    if a.ozdenetim_ceviri:
        raise SystemExit(ozdenetim(ceviri=True))
    if a.ozdenetim:
        raise SystemExit(ozdenetim())
    gunluk_kur()
    ayar = ayarlar.yukle()
    dil, ayarli_kapi = ayar["arayuz_dili"], ayar["kapi"]
    durum, kapi = kapi_sec(ayarli_kapi)
    if durum == "zaten_acik":
        # ikinci kez açıldı: yenisini başlatma, açık olanın panelini göster
        panel = f"http://127.0.0.1:{kapi}/"
        yaz(metinler.mesaj("zaten_acik", dil).format(adres=panel))
        if not a.tarayici_acma:
            webbrowser.open(panel)
        return
    if kapi is None:
        yaz(metinler.mesaj("kapi_yok", dil).format(kapi=ayarli_kapi))
        sys.exit(1)
    if kapi != ayarli_kapi:
        yaz(metinler.mesaj("kapi_dolu", dil).format(kapi=ayarli_kapi, yeni=kapi))
    app = uygulama_olustur(ayar)
    app[DURUM].calisan_kapi = kapi

    if a.demo:
        async def baslat(app: web.Application) -> None:
            app["demo"] = asyncio.create_task(demo_dongusu(app))

        async def durdur(app: web.Application) -> None:
            app["demo"].cancel()
        app.on_startup.append(baslat)
        app.on_cleanup.append(durdur)
        yaz(metinler.mesaj("demo_acik", dil))

    async def guncelleme_bak(app: web.Application) -> None:
        app[GUNCELLEME].arka_planda_denetle()   # günde en çok bir kez; ayar kapalıysa hiç
    app.on_startup.append(guncelleme_bak)

    for ip in lan_adresleri():
        yaz(metinler.mesaj("tv_adres", dil).format(adres=f"http://{ip}:{kapi}/tv"))
    panel = f"http://127.0.0.1:{kapi}/"
    yaz(metinler.mesaj("panel_adres", dil).format(adres=panel))
    if not a.tarayici_acma:
        def tarayici_ac() -> None:
            try:
                webbrowser.open(panel)
            except Exception:   # noqa: BLE001 — tarayıcı açılamazsa adres zaten yazıldı
                pass

        async def ac(_: web.Application) -> None:
            # sunucu dinlemeye başladıktan sonra; webbrowser.open bloklayabilir: yürütücüde
            asyncio.get_running_loop().call_later(
                0.6, lambda: asyncio.get_running_loop().run_in_executor(None, tarayici_ac))
        app.on_startup.append(ac)
    try:
        web.run_app(app, host="0.0.0.0", port=kapi, print=None, access_log=None)
    except KeyboardInterrupt:
        pass
    except OSError as e:   # kapı denetimi ile bağlama arasında biri kapıyı aldı
        log.error("Sunucu başlatılamadı: %s", e)
        yaz(metinler.mesaj("kapi_yok", dil).format(kapi=kapi))
        sys.exit(1)
    yaz(metinler.mesaj("durdu", dil))


if __name__ == "__main__":
    main()
