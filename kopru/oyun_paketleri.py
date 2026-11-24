# SPDX-License-Identifier: AGPL-3.0-only
"""PROTOKOL 20.5: oyun paketleri — uygulama güncellemesi beklemeden güncellenen oyun sözlükleri.

Paket: terimler, adlar (karakter/yer), hitap, argo, çevirmen notları. Program gömülü bir kopyayla gelir; arka planda
yalnız GitHub'daki depodan (raw.githubusercontent.com, https) yenisi indirilir, SHA-256 dizinle karşılaştırılır.
Paketler yalnız bellekte birleştirilir; kullanıcının sözlük dosyasına yazılmaz.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from . import ayarlar, oyunlar

log = logging.getLogger("kopru.oyun_paketleri")

TABAN_URL = "https://raw.githubusercontent.com/YPUF-04/gametranslate/main/oyun-paketleri/"
IZINLI_SUNUCU = "raw.githubusercontent.com"
ZAMAN_ASIMI = 15
EN_BUYUK = 256 * 1024
DIZIN_EN_BUYUK = 64 * 1024
GUN_SN = 24 * 3600
_SURUM = re.compile(r"[0-9A-Za-z.\-]{1,32}")
_SHA = re.compile(r"[0-9a-f]{64}")


def gomulu_dizin() -> Path:
    """Geliştirmede <depo>/oyun-paketleri; PyInstaller'da <paket>/oyun-paketleri (--add-data)."""
    return Path(__file__).resolve().parents[1] / "oyun-paketleri"


def onbellek_dizini() -> Path:
    return ayarlar.ayar_dizini() / "oyun_paketleri"


def anahtar(ad: str) -> str:
    return oyunlar.kod_uret(ad)


def _metin(v: Any, n: int) -> str:
    return " ".join(str(v).split())[:n] if isinstance(v, (str, int, float)) and not isinstance(v, bool) else ""


def _ciftler(liste: Any, en_cok: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    gorulen: set[str] = set()
    for t in liste if isinstance(liste, list) else []:
        if not isinstance(t, dict):
            continue
        a, c = _metin(t.get("asil"), 300), _metin(t.get("ceviri"), 300)
        if a and c and a.casefold() not in gorulen:
            gorulen.add(a.casefold())
            out.append({"asil": a, "ceviri": c})
        if len(out) >= en_cok:
            break
    return out


def dogrula(veri: Any) -> dict[str, Any] | None:
    """Şemayı denetler ve temizler; geçersizse None."""
    if not isinstance(veri, dict) or veri.get("bicim") != 1:
        return None
    kod = veri.get("kod")
    surum = veri.get("surum")
    if not oyunlar.gecerli_kod(kod) or not isinstance(surum, str) or not _SURUM.fullmatch(surum):
        return None
    karakterler = []
    for k in veri.get("karakterler") or []:
        if isinstance(k, dict) and _metin(k.get("ad"), 60):
            c = k.get("cinsiyet")
            karakterler.append({"ad": _metin(k.get("ad"), 60), "cinsiyet": c if c in ("k", "e") else ""})
    return {
        "bicim": 1, "kod": kod, "surum": surum, "ad": _metin(veri.get("ad"), 100) or kod,
        "adlar": [a for a in (_metin(x, 100) for x in (veri.get("adlar") or [])[:20]) if a],
        "hitap": veri.get("hitap") if veri.get("hitap") in ("sen", "siz") else "",
        "notlar": _metin(veri.get("notlar"), 1000),
        "karakterler": karakterler[:300],
        "yerler": [y for y in (_metin(x, 60) for x in (veri.get("yerler") or [])[:500]) if y],
        "terimler": _ciftler(veri.get("terimler"), 2000),
        "argo": _ciftler(veri.get("argo"), 200),
    }


def _oku(yol: Path) -> dict[str, Any] | None:
    try:
        if yol.stat().st_size > EN_BUYUK:
            return None
        return dogrula(json.loads(yol.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def _klasor(d: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            if p.name == "index.json":
                continue
            v = _oku(p)
            if v and p.stem == v["kod"]:
                out[v["kod"]] = v
    return out


def hepsi() -> dict[str, tuple[dict[str, Any], str]]:
    """kod -> (paket, "gomulu" | "indirilen"). İndirilen geçerli kopya varsa (sürümü daha yeni ya da eşitse) o."""
    out = {k: (v, "gomulu") for k, v in _klasor(gomulu_dizin()).items()}
    for k, v in _klasor(onbellek_dizini()).items():
        if k not in out or v["surum"] >= out[k][0]["surum"]:
            out[k] = (v, "indirilen")
    return out


def bul(oyun_kod: str, oyun_ad: str = "") -> tuple[dict[str, Any], str] | None:
    """Etkin oyuna uyan paket: oyun kodu ya da adı, paketin kodu ya da adlarından biriyle aynı (normalize)."""
    aranan = {anahtar(x) for x in (oyun_kod, oyun_ad) if x and anahtar(x) != "oyun"}
    aranan.discard(oyunlar.VARSAYILAN_KOD)
    if not aranan:
        return None
    for kod, (p, kaynak) in hepsi().items():
        if aranan & ({kod, anahtar(p["ad"])} | {anahtar(a) for a in p["adlar"]}):
            return p, kaynak
    return None


def uygula(bilgi: dict[str, Any], terimler: dict[str, str], paket: dict[str, Any] | None,
           hitap_acik: bool = False) -> tuple[dict[str, Any], dict[str, str]]:
    """Paketi oyun bilgisine ve sözlüğe (yalnız bellekte) katar; kullanıcının verisi kazanır."""
    if not paket:
        return bilgi, terimler
    b = dict(bilgi)
    mevcut = {str(k.get("ad", "")).casefold() for k in b.get("karakterler") or [] if isinstance(k, dict)}
    b["karakterler"] = list(b.get("karakterler") or []) + [k for k in paket["karakterler"]
                                                         if k["ad"].casefold() not in mevcut]
    b["yerler"] = list(dict.fromkeys(list(b.get("yerler") or []) + paket["yerler"]))
    b["argo"] = [(t["asil"], t["ceviri"]) for t in paket["argo"]]
    b["notlar"] = paket["notlar"]
    b["paket"] = {"kod": paket["kod"], "surum": paket["surum"]}
    if paket["hitap"] and not hitap_acik:
        b["hitap"] = paket["hitap"]
    if not b.get("aciklama") and paket["ad"]:
        b.setdefault("ad", paket["ad"])
    t = {x["asil"]: x["ceviri"] for x in paket["terimler"]}
    kucuk = {a.casefold() for a in terimler}
    t = {a: c for a, c in t.items() if a.casefold() not in kucuk}
    t.update(terimler)
    return b, t


# ---- arka planda güncelleme ----------------------------------------------------------------------------------
class _Yonlendirme(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise urllib.error.URLError("yönlendirme izlenmez")


def url_izinli(url: str) -> bool:
    u = urllib.parse.urlsplit(url)
    return u.scheme == "https" and u.hostname == IZINLI_SUNUCU and url.startswith(TABAN_URL)


def _getir(url: str, en_cok: int) -> bytes:
    if not url_izinli(url):
        raise ValueError("izinsiz adres")
    acici = urllib.request.build_opener(_Yonlendirme())
    istek = urllib.request.Request(url, headers={"User-Agent": "AltYaziKoprusu"})
    with acici.open(istek, timeout=ZAMAN_ASIMI) as y:
        veri = y.read(en_cok + 1)
    if len(veri) > en_cok:
        raise ValueError("çok büyük")
    return veri


class Guncelleyici:
    """Dizini indirir, sürümü farklı paketleri doğrulayıp önbelleğe yazar. Ağ yoksa sessizce vazgeçer."""
    ILK_BEKLEME_SN = 30.0
    DENETIM_SN = 3600.0

    def __init__(self, ayar: Callable[[], dict[str, Any]], getir: Callable[[str, int], bytes] | None = None):
        self._ayar = ayar
        self._getir = getir or _getir
        self._kilit = threading.Lock()
        self.son_denetim: float | None = None
        self.hata: str | None = None
        self.indirilen = 0

    def acik_mi(self) -> bool:
        return self._ayar().get("oyun_paketleri_guncelle", True) is not False

    def gerekirse_denetle(self) -> bool:
        if not self.acik_mi() or (self.son_denetim and time.time() - self.son_denetim < GUN_SN):
            return False
        self.denetle()
        return True

    def denetle(self) -> int:
        """Eşzamanlı (engelleyen). Yeni yazılan paket sayısını döndürür."""
        with self._kilit:
            self.son_denetim = time.time()
            yeni = 0
            try:
                dizin = json.loads(self._getir(TABAN_URL + "index.json", DIZIN_EN_BUYUK).decode("utf-8"))
            except (OSError, ValueError, urllib.error.URLError) as e:
                log.info("Oyun paketi dizini alınamadı: %s", e)
                self.hata = "ag"
                return 0
            if not isinstance(dizin, dict) or dizin.get("bicim") != 1 or not isinstance(dizin.get("paketler"), list):
                self.hata = "gecersiz"
                return 0
            self.hata = None
            elde = hepsi()
            for g in dizin["paketler"][:100]:
                if not isinstance(g, dict):
                    continue
                kod, surum, sha = g.get("kod"), g.get("surum"), g.get("sha256")
                if not (oyunlar.gecerli_kod(kod) and isinstance(surum, str) and _SURUM.fullmatch(surum)
                        and isinstance(sha, str) and _SHA.fullmatch(sha)):
                    continue
                if kod in elde and elde[kod][0]["surum"] >= surum:
                    continue
                try:
                    ham = self._getir(TABAN_URL + f"{kod}.json", EN_BUYUK)
                except (OSError, ValueError, urllib.error.URLError) as e:
                    log.info("Oyun paketi indirilemedi (%s): %s", kod, e)
                    self.hata = "ag"
                    continue
                if hashlib.sha256(ham).hexdigest() != sha:
                    log.warning("Oyun paketi SHA-256 tutmadı: %s", kod)
                    self.hata = "gecersiz"
                    continue
                try:
                    p = dogrula(json.loads(ham.decode("utf-8")))
                except ValueError:
                    p = None
                if p is None or p["kod"] != kod or p["surum"] != surum:
                    self.hata = "gecersiz"
                    continue
                onbellek_dizini().mkdir(parents=True, exist_ok=True)
                ayarlar.atomik_yaz(onbellek_dizini() / f"{kod}.json", ham.decode("utf-8"))
                yeni += 1
            self.indirilen += yeni
            return yeni

    def bilgi(self, etkin: str | None = None) -> dict[str, Any]:
        return {"paketler": [{"kod": k, "ad": p["ad"], "surum": p["surum"], "kaynak": kaynak,
                              "terim": len(p["terimler"])} for k, (p, kaynak) in sorted(hepsi().items())],
                "etkin": etkin, "son_denetim": int(self.son_denetim) if self.son_denetim else None,
                "hata": self.hata}


def dizin_uret(klasor: Path | None = None) -> dict[str, Any]:
    """Geliştirici aracı: klasördeki paketlerden index.json içeriği (sha256, boyut)."""
    d = klasor or gomulu_dizin()
    out = []
    for p in sorted(d.glob("*.json")):
        if p.name == "index.json":
            continue
        ham = p.read_bytes()
        v = dogrula(json.loads(ham.decode("utf-8")))
        if v is None:
            raise ValueError(f"geçersiz paket: {p.name}")
        out.append({"kod": v["kod"], "ad": v["ad"], "surum": v["surum"],
                    "sha256": hashlib.sha256(ham).hexdigest(), "boyut": len(ham)})
    return {"bicim": 1, "paketler": out}


if __name__ == "__main__":   # python -m kopru.oyun_paketleri  -> oyun-paketleri/index.json'u yeniden yazar
    yol = gomulu_dizin() / "index.json"
    yol.write_text(json.dumps(dizin_uret(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(yol)
