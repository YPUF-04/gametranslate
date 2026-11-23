# SPDX-License-Identifier: AGPL-3.0-only
"""LG TV uygulaması paketi (PROTOKOL 18): başlatıcı bunu bilgisayardan alır, TV bir daha yeniden kurulmaz.

Paket = webOS uygulamasının değişen her şeyi (gövde işaretlemesi, CSS, JS) tek bir JSON'da. Sürüm içeriğin özetidir.
Aynı modül paketleme anında başlatıcıya gömülecek `gomulu.js`'i de üretir (`python -m kopru.tv_kurulum.uygulama`).
"""
from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

KAYNAK = Path(__file__).resolve().parents[1] / "web" / "tv"
UYGULAMA = "altyazikoprusu-tv"
YUKLEYICI_GUNCEL = 2          # bu depodaki tv/webos/yukleyici.js'in sürümü
YUKLEYICI_EN_AZ = 2           # paketin çalışması için gereken en eski başlatıcı
HTML = "webos/govde.html"
CSS = ("ortak.css", "webos/style.css")      # eski index.html sırası: style.css ortak.css'in üstüne yazar
JS = ("marka.js", "webos/i18n.js", "webos/platform-webos.js", "ortak.js", "reklam.js", "webos/app.js")
EN_COK_TV = 16
UNUTMA_SN = 7 * 24 * 3600

_kilit = threading.Lock()
_onbellek: tuple[tuple, dict[str, Any]] | None = None


def _imza(kok: Path) -> tuple:
    out = []
    for ad in (HTML, *CSS, *JS):
        st = (kok / ad).stat()
        out.append((ad, st.st_mtime_ns, st.st_size))
    return tuple(out)


def paket(kok: Path | None = None, kopru_surum: str = "") -> dict[str, Any]:
    """Tam paket (dosyalar değişmedikçe bellekten)."""
    global _onbellek
    kok = kok or KAYNAK
    imza = (str(kok), kopru_surum) + _imza(kok)
    with _kilit:
        if _onbellek and _onbellek[0] == imza:
            return _onbellek[1]
    oku = lambda ad: (kok / ad).read_text(encoding="utf-8")   # noqa: E731
    css = [oku(ad) for ad in CSS]
    js = [[Path(ad).name, oku(ad)] for ad in JS]
    html = oku(HTML)
    h = hashlib.sha256()
    for parca in [html, *css, *(a + "\0" + k for a, k in js)]:
        h.update(parca.encode("utf-8"))
        h.update(b"\x1e")
    p = {"uygulama": UYGULAMA, "surum": h.hexdigest()[:12], "yukleyici_en_az": YUKLEYICI_EN_AZ,
         "kopru_surum": kopru_surum, "html": html, "css": css, "js": js}
    with _kilit:
        _onbellek = (imza, p)
    return p


def yanit(yukleyici: Any, surum: Any, kopru_surum: str = "", kok: Path | None = None) -> dict[str, Any]:
    """`GET /kopru/tv/uygulama` gövdesi (PROTOKOL 18.2)."""
    p = paket(kok, kopru_surum)
    try:
        y = int(yukleyici)
    except (TypeError, ValueError):
        y = 0
    if y < p["yukleyici_en_az"]:
        return {"uygulama": UYGULAMA, "eski_yukleyici": True, "yukleyici_en_az": p["yukleyici_en_az"]}
    if isinstance(surum, str) and surum == p["surum"]:
        return {"uygulama": UYGULAMA, "surum": p["surum"], "ayni": True}
    return p


def gomulu_js(p: dict[str, Any]) -> str:
    """Başlatıcıya gömülen yedek paket (bilgisayar hiç bulunamazsa bu açılır)."""
    veri = json.dumps(p, ensure_ascii=False, separators=(",", ":"))
    veri = veri.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return ("// SPDX-License-Identifier: AGPL-3.0-only\n// Üretildi: python -m kopru.tv_kurulum.uygulama"
            " (elle değiştirmeyin; PROTOKOL 18.1)\nwindow.AK_GOMULU_PAKET = " + veri + ";\n")


class TvKaydi:
    """PROTOKOL 18.5: görülen TV'ler (yalnız RAM)."""

    def __init__(self, saat: Any = time.time) -> None:
        self.saat = saat
        self._tv: dict[str, dict[str, Any]] = {}
        self._kilit = threading.Lock()

    def gor(self, adres: str | None, yukleyici: int | None, paket_surum: str | None) -> None:
        if not adres:
            return
        with self._kilit:
            e = self._tv.get(adres) or {}
            if yukleyici is not None:
                e["yukleyici"] = yukleyici
            if paket_surum:
                e["paket"] = str(paket_surum)[:32]
            e["son"] = self.saat()
            self._tv[adres] = e
            if len(self._tv) > EN_COK_TV:
                en_eski = min(self._tv, key=lambda k: self._tv[k]["son"])
                del self._tv[en_eski]

    def durum(self, paket_surum: str, dil: str = "tr") -> dict[str, Any]:
        simdi = self.saat()
        with self._kilit:
            tvler = [(a, dict(e)) for a, e in self._tv.items() if simdi - e["son"] < UNUTMA_SN]
        liste = []
        for a, e in sorted(tvler, key=lambda x: -x[1]["son"]):
            y = e.get("yukleyici")
            liste.append({"adres": a, "yukleyici": y, "paket": e.get("paket"),
                          "guncel": bool(y and y >= YUKLEYICI_GUNCEL and e.get("paket") == paket_surum),
                          "son_gorulme_sn": int(simdi - e["son"])})
        if not liste:
            d = "bilinmiyor"
        elif any((t["yukleyici"] or 0) < YUKLEYICI_EN_AZ for t in liste):
            d = "eski"
        else:
            d = "guncel"
        return {"paket_surum": paket_surum, "yukleyici_guncel": YUKLEYICI_GUNCEL, "durum": d,
                "mesaj": MESAJ[d]["en" if dil == "en" else "tr"], "tvler": liste}


MESAJ = {
    "guncel": {"tr": "TV uygulaması güncel: program güncellendikçe TV de kendiliğinden güncellenir.",
               "en": "TV app is up to date: it updates itself whenever the program updates."},
    "eski": {"tr": "TV uygulaması eski: bir kez yeniden kurun, sonra hep kendiliğinden güncellenir.",
             "en": "TV app is outdated: reinstall it once; after that it always updates itself."},
    "bilinmiyor": {"tr": "Henüz bağlanan bir TV görülmedi.", "en": "No TV has connected yet."},
}


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "--gomulu":
        Path(argv[2]).write_text(gomulu_js(paket()), encoding="utf-8")
        return 0
    if len(argv) == 3 and argv[1] == "--json":
        Path(argv[2]).write_text(json.dumps(paket(), ensure_ascii=False), encoding="utf-8")
        return 0
    if len(argv) == 2 and argv[1] == "--surum":
        print(paket()["surum"])
        return 0
    print("kullanım: python -m kopru.tv_kurulum.uygulama --gomulu <dosya.js> | --surum", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
