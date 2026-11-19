#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Erişim kodu üretici (yalnız geliştirici için). Hiçbir şey internete gönderilmez.

Kullanım:
  python araclar/kod_uret.py                       küçük bir sayfa açar (en kolay yol)
  python araclar/kod_uret.py --sinirsiz --adet 5   5 sınırsız kod yazdırır
  python araclar/kod_uret.py --gun 30 --adet 10    10 tane 30 günlük kod
  python araclar/kod_uret.py --anahtar-olustur     yalnız anahtar çiftini oluşturur

Özel anahtar: ~/.altyazikoprusu-kod/ozel_anahtar.pem (KOPRU_KOD_ANAHTARI ile değişir).
Bu dosyayı kimseyle paylaşma, GitHub'a koyma. Kaybedersen yeni kod üretemezsin; yedekle.
"""
from __future__ import annotations

import argparse
import base64
import csv
import html
import io
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from kopru import erisim  # noqa: E402

UYARI = ("Bu dosyayı kimseyle paylaşma, GitHub'a koyma. "
         "Kaybedersen yeni kod üretemezsin; yedekle.")


def anahtar_yolu() -> Path:
    ozel = os.environ.get("KOPRU_KOD_ANAHTARI")
    return Path(ozel) if ozel else Path.home() / ".altyazikoprusu-kod" / "ozel_anahtar.pem"


def anahtar_var() -> bool:
    return anahtar_yolu().is_file()


def anahtar_olustur() -> Path:
    """Yoksa yeni anahtar çifti yapar; VARSA dokunmaz (eski kodlar geçersiz kalmasın)."""
    yol = anahtar_yolu()
    if yol.exists():
        return yol
    yol.parent.mkdir(parents=True, exist_ok=True)
    k = Ed25519PrivateKey.generate()
    pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                          serialization.NoEncryption())
    # dosya baştan yalnız sahibine açık oluşur (yaz-sonra-chmod arasındaki açık pencere olmasın);
    # "x": var olan anahtarın üzerine asla yazılmaz
    fd = os.open(yol, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    return yol


def ozel_oku() -> Ed25519PrivateKey:
    k = serialization.load_pem_private_key(anahtar_yolu().read_bytes(), password=None)
    if not isinstance(k, Ed25519PrivateKey):
        raise ValueError("Bu dosya bir Ed25519 özel anahtarı değil.")
    return k


def acik_satir() -> str:
    """kopru/erisim_anahtar.py içine yapıştırılacak satır."""
    ham = ozel_oku().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return 'ACIK_ANAHTAR = "%s"' % base64.b64encode(ham).decode()


def uret(tur: str, adet: int, gun: int | None = None) -> list[str]:
    if not 1 <= adet <= 100:
        raise ValueError("Kod sayısı 1 ile 100 arasında olmalı.")
    k = ozel_oku()
    return [erisim.kod_uret(k, tur, gun) for _ in range(adet)]


# ---------- küçük yerel sayfa ----------

SAYFA = """<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Erişim kodu üret</title>
<style>body{font:18px/1.5 system-ui,sans-serif;max-width:680px;margin:32px auto;padding:0 16px;background:#0e1a2b;color:#eef3f8}
h1{font-size:1.5rem}.k{background:#16243a;border-radius:14px;padding:20px;margin:16px 0}
button,select,input{font:inherit;padding:10px 16px;border-radius:10px;border:0;margin:4px 4px 4px 0}
button{background:#2ec4b6;color:#04231f;font-weight:700;cursor:pointer}button.i{background:#2a3a55;color:#eef3f8}
textarea{width:100%;height:220px;font:15px monospace;background:#0b1424;color:#eef3f8;border:1px solid #2a3a55;border-radius:10px;padding:10px;box-sizing:border-box}
.u{background:#3a2f12;border-left:5px solid #ffd166;padding:12px 16px;border-radius:10px}code{word-break:break-all}</style>
<h1>Erişim kodu üret</h1>
<p>Her şey bu bilgisayarda olur; hiçbir şey internete gönderilmez.</p>
%GOVDE%"""

ANAHTAR_YOK = """<div class="k"><p>Henüz bir anahtarın yok. Önce bir kez oluştur.</p>
<form method="post" action="/anahtar"><button>Anahtar oluştur</button></form></div>"""

FORM = """%ACIK%<div class="k"><form method="post" action="/uret">
<label>Tür: <select name="tur" id="tur" onchange="g.hidden=this.value!='gun'">
<option value="sinirsiz">Sınırsız</option><option value="gun">Belirli gün</option></select></label>
<label id="g" hidden>Kaç gün: <input type="number" name="gun" value="30" min="1" max="3650"></label><br>
<label>Kaç kod: <input type="number" name="adet" value="1" min="1" max="100"></label>
<button>Üret</button></form></div>%SONUC%"""


def _acik_kutu(yeni: bool) -> str:
    giris = "<b>Anahtar oluşturuldu.</b> " if yeni else ""
    return ('<div class="u">%s<br>%s<br>Yayından önce şu satırı <code>kopru/erisim_anahtar.py</code> '
            'dosyasına yapıştır (eskisinin yerine):<br><code>%s</code><br>Dosya: <code>%s</code></div>'
            % (giris, html.escape(UYARI), html.escape(acik_satir()), html.escape(str(anahtar_yolu()))))


def _sonuc(kodlar: list[str]) -> str:
    metin = "\n".join(kodlar)
    return ('<div class="k"><textarea id="liste" readonly>%s</textarea><br>'
            '<button class="i" onclick="navigator.clipboard.writeText(liste.value);this.textContent=\'Kopyalandı\'">Kopyala</button>'
            '<a href="/csv?k=%s"><button class="i" type="button">CSV indir</button></a></div>'
            % (html.escape(metin), base64.urlsafe_b64encode(json.dumps(kodlar).encode()).decode()))


class Isleyici(BaseHTTPRequestHandler):
    yeni_anahtar = False

    def log_message(self, *a: object) -> None:
        pass

    def _yaz(self, kod: int, govde: bytes, tur: str = "text/html; charset=utf-8", ek: dict | None = None) -> None:
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(govde)))
        for k, v in (ek or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(govde)

    def _sayfa(self, sonuc: str = "", hata: str = "") -> None:
        if not anahtar_var():
            govde = ANAHTAR_YOK
        else:
            govde = FORM.replace("%ACIK%", _acik_kutu(Isleyici.yeni_anahtar)).replace("%SONUC%", sonuc)
        if hata:
            govde = '<div class="u">%s</div>' % html.escape(hata) + govde
        self._yaz(200, SAYFA.replace("%GOVDE%", govde).encode())

    def _yerel_mi(self) -> bool:
        """DNS yeniden bağlama / başka siteden gelen istekleri reddeder (yalnız 127.0.0.1 ya da localhost)."""
        def ad(v: str | None) -> str:
            v = (v or "").split("://", 1)[-1].split("/", 1)[0]
            return v.rsplit(":", 1)[0] if v.count(":") == 1 else v
        izinli = {"127.0.0.1", "localhost"}
        koken = self.headers.get("Origin")
        return ad(self.headers.get("Host")) in izinli and (koken is None or ad(koken) in izinli)

    def do_GET(self) -> None:
        if not self._yerel_mi():
            return self._yaz(403, b"")
        if self.path.startswith("/csv?k="):
            try:
                kodlar = json.loads(base64.urlsafe_b64decode(self.path[7:]))
                assert isinstance(kodlar, list) and all(isinstance(x, str) for x in kodlar)
            except (ValueError, AssertionError):
                return self._yaz(400, b"")
            b = io.StringIO()
            w = csv.writer(b)
            w.writerow(["kod"])
            w.writerows([[k] for k in kodlar])
            return self._yaz(200, b.getvalue().encode(), "text/csv; charset=utf-8",
                             {"Content-Disposition": 'attachment; filename="erisim-kodlari.csv"'})
        self._sayfa()

    def do_POST(self) -> None:
        if not self._yerel_mi():
            return self._yaz(403, b"")
        try:
            n = max(0, int(self.headers.get("Content-Length") or 0))
        except ValueError:
            return self._yaz(400, b"")
        from urllib.parse import parse_qs
        f = {k: v[0] for k, v in parse_qs(self.rfile.read(min(n, 4096)).decode()).items()}
        if self.path == "/anahtar":
            Isleyici.yeni_anahtar = not anahtar_var()
            anahtar_olustur()
            return self._sayfa()
        if self.path == "/uret" and anahtar_var():
            try:
                tur = f.get("tur", "sinirsiz")
                gun = int(f["gun"]) if tur == "gun" else None
                return self._sayfa(_sonuc(uret(tur, int(f.get("adet", "1")), gun)))
            except (ValueError, KeyError) as e:
                return self._sayfa(hata="Girdiğin sayıları kontrol et (kod sayısı 1-100, gün 1-3650). %s" % e)
        self._sayfa()


def sayfa_ac(tarayici: bool = True) -> None:
    sunucu = ThreadingHTTPServer(("127.0.0.1", 0), Isleyici)
    adres = "http://127.0.0.1:%d/" % sunucu.server_address[1]
    print("Sayfa açıldı: %s  (kapatmak için Ctrl+C)" % adres)
    if tarayici:
        threading.Timer(0.3, lambda: webbrowser.open(adres)).start()
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        sunucu.server_close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="AltYazıKöprüsü erişim kodu üretici")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--sinirsiz", action="store_true", help="sınırsız kod üret")
    g.add_argument("--gun", type=int, metavar="N", help="N günlük kod üret")
    p.add_argument("--adet", type=int, default=1, help="kaç kod (1-100)")
    p.add_argument("--anahtar-olustur", action="store_true", help="anahtar çiftini oluştur ve çık")
    p.add_argument("--acik-anahtar", action="store_true", help="yapıştırılacak açık anahtar satırını yazdır")
    a = p.parse_args(argv)
    if a.anahtar_olustur or a.acik_anahtar or a.sinirsiz or a.gun:
        yeni = not anahtar_var()
        if yeni and not (a.anahtar_olustur):
            print("Önce anahtar gerekir: python araclar/kod_uret.py --anahtar-olustur", file=sys.stderr)
            return 2
        if a.anahtar_olustur:
            anahtar_olustur()
            print("Özel anahtar: %s\n%s\nYayından önce bu satırı kopru/erisim_anahtar.py içine yapıştır:\n%s"
                  % (anahtar_yolu(), UYARI, acik_satir()))
            return 0
        if a.acik_anahtar:
            print(acik_satir())
            return 0
        try:
            for k in uret("gun" if a.gun else "sinirsiz", a.adet, a.gun):
                print(k)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        return 0
    sayfa_ac()
    return 0


if __name__ == "__main__":
    sys.exit(main())
