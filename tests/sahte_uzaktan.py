# SPDX-License-Identifier: AGPL-3.0-only
"""Sınamalar için sahte `ayk-uzaktan` (PROTOKOL §15.3–15.4). Gerçek PS5 yok; aynı kanal biçimini konuşur.

Davranış SAHTE_PS5 ortam değişkeniyle seçilir (JSON): {"kayit":"tamam"|"pin"|"hesap"|"sessiz",
"akis":"normal"|"kop"|"red"|"erisilemedi", "durum":"acik"|"uyku", "gunluk": "<dosya>"}.
"""
import json
import os
import struct
import sys
import threading
import time

AYAR = json.loads(os.environ.get("SAHTE_PS5") or "{}")


def gunluge(satir):
    yol = AYAR.get("gunluk")
    if yol:
        with open(yol, "a", encoding="utf-8") as f:
            f.write(satir + "\n")


def yaz_satir(o):
    sys.stdout.write(json.dumps(o) + "\n")
    sys.stdout.flush()


kilit = threading.Lock()


def cerceve(tur, veri):
    with kilit:
        sys.stdout.buffer.write(b"AY" + tur.encode() + b"\0" + struct.pack("<I", len(veri)) + veri)
        sys.stdout.buffer.flush()


def olay(o):
    cerceve("J", json.dumps(o).encode())


def main():
    komut = sys.argv[1]
    if komut == "ozdenetim":
        yaz_satir({"olay": "ozdenetim", "tamam": True})
        print("OZDENETIM uzaktan=tamam")
        return 0
    girdi = json.loads(sys.stdin.readline() or "{}")
    gunluge(komut + " " + json.dumps(girdi, sort_keys=True))
    if komut == "bul":
        durum = AYAR.get("durum", "acik")
        isaret = AYAR.get("isaret")
        if durum == "uyku" and isaret and os.path.exists(isaret):
            durum = "acik"      # uyandırıldı
        yaz_satir({"olay": "konsol", "host": (girdi.get("hedefler") or ["192.168.1.30"])[0].replace("255.255.255.255", "192.168.1.30"),
                   "ad": "PS5-SAHTE", "durum": durum, "kimlik": "abc", "oyun": None})
        yaz_satir({"olay": "bitti", "bulunan": 1})
        return 0
    if komut == "uyandir":
        if AYAR.get("isaret"):
            open(AYAR["isaret"], "w").close()
        yaz_satir({"olay": "uyandir", "tamam": True})
        return 0
    if komut == "kaydet":
        tur = AYAR.get("kayit", "tamam")
        if tur == "tamam":
            yaz_satir({"olay": "kayit", "tamam": True, "ad": "PS5-SAHTE", "kayit_anahtari": "31613262" + "0" * 24,
                       "sabah": "00112233445566778899aabbccddeeff", "mac": "a1b2c3d4e5f6", "hedef": 1000100})
            return 0
        neden = {"pin": 0x80108B09, "hesap": 0x80108B02}.get(tur, 0)
        satirlar = ["Regist timed out waiting for search response"] if tur == "sessiz" else []
        yaz_satir({"olay": "kayit", "tamam": False, "neden": neden, "zaman_asimi": False, "satirlar": satirlar})
        return 2
    if komut == "akis":
        return akis()
    return 1


def akis():
    tur = AYAR.get("akis", "normal")
    isaret = AYAR.get("isaret2")
    if tur == "kop" and isaret and os.path.exists(isaret):
        tur = "normal"      # ikinci denemede düzelir
    olay({"olay": "baslatildi"})
    if tur == "red":
        olay({"olay": "bitti", "neden": "reddedildi", "ayrinti": "Regist failed", "neden_kodu": 0x80108B26})
        return 0
    if tur == "erisilemedi":
        olay({"olay": "bitti", "neden": "erisilemedi", "ayrinti": "refused", "neden_kodu": 0})
        return 0
    olay({"olay": "bagli"})
    dur = threading.Event()

    def ses():
        n = 0
        while not dur.is_set():
            cerceve("S", struct.pack("<160h", *([1000] * 160)))
            n += 1
            time.sleep(0.01)

    threading.Thread(target=ses, daemon=True).start()
    kare_sayisi = 0
    for satir in sys.stdin:
        satir = satir.strip()
        if satir.startswith("kare"):
            parca = satir.split()
            azami = int(parca[1]) if len(parca) > 1 else 0
            g, y = (64, 36)
            if azami and g > azami:
                g, y = azami, max(1, 36 * azami // 64)
            cerceve("V", struct.pack("<HH", g, y) + bytes([10, 20, 200, 255]) * (g * y))
            kare_sayisi += 1
            if tur == "kop" and kare_sayisi >= 1:
                if isaret:
                    open(isaret, "w").close()
                dur.set()
                olay({"olay": "bitti", "neden": "ag", "ayrinti": "Remote disconnected", "neden_kodu": 0})
                return 0
        elif satir.startswith("giris_pin"):
            gunluge(satir)
        elif satir == "dur":
            break
    dur.set()
    olay({"olay": "bitti", "neden": "durdu", "ayrinti": "stopped", "neden_kodu": 0})
    return 0


if __name__ == "__main__":
    sys.exit(main())
