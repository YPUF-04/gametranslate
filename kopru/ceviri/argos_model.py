# SPDX-License-Identifier: AGPL-3.0-only
"""Argos Translate dil dosyalarını (`.argosmodel`) indirir ve güvenle açar (PROTOKOL 10.4).

argostranslate/torch/stanza gerekmez: paketin içindeki CTranslate2 modeli ve SentencePiece modeli
doğrudan `ctranslate2` + `sentencepiece` ile kullanılır. Bu modül yalnız dosya işleriyle ilgilenir.
"""
from __future__ import annotations

import json
import os
import posixpath
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from .. import ayarlar

INDEKS_URL = "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json"
IZINLI_SUNUCULAR = ("raw.githubusercontent.com", "argos-net.com")   # tam ad ya da alt alan adı
ZAMAN_ASIMI = 30
INDEKS_ENFAZLA = 8 * 1024 * 1024
INDIRME_ENFAZLA = 1024 * 1024 * 1024        # indirilen zip için üst sınır
ACILMIS_ENFAZLA = 2 * 1024 * 1024 * 1024    # açılmış toplam boyut için üst sınır
DOSYA_ENFAZLA = 1536 * 1024 * 1024
GIRDI_ENFAZLA = 5000
ILERLEME = Callable[[int], None]


class ModelHatasi(Exception):
    """İndirme/açma sorunu; `kod` kısa makine kodudur (ag, gecersiz_paket, paket_yok, ...)."""

    def __init__(self, kod: str, ayrinti: str = ""):
        super().__init__(f"{kod}: {ayrinti}" if ayrinti else kod)
        self.kod = kod
        self.ayrinti = ayrinti


def modeller_dizini() -> Path:
    return ayarlar.ayar_dizini() / "modeller" / "argos"


def paket_dizini(kaynak: str, hedef: str) -> Path:
    for k in (kaynak, hedef):
        if not k or not k.replace("-", "").replace("_", "").isalnum():
            raise ModelHatasi("gecersiz_dil", k)
    return modeller_dizini() / f"{kaynak}_{hedef}"


def url_izinli_mi(url: str) -> bool:
    try:
        u = urlparse(url)
    except ValueError:
        return False
    ad = (u.hostname or "").lower()
    return u.scheme == "https" and any(ad == s or ad.endswith("." + s) for s in IZINLI_SUNUCULAR)


class _YonlendirmeDenetimi(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        if not url_izinli_mi(newurl):
            raise ModelHatasi("izinsiz_adres", newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _ac(url: str):
    if not url_izinli_mi(url):
        raise ModelHatasi("izinsiz_adres", url)
    acici = urllib.request.build_opener(_YonlendirmeDenetimi())
    istek = urllib.request.Request(url, headers={"User-Agent": "AltYaziKoprusu"})
    try:
        return acici.open(istek, timeout=ZAMAN_ASIMI)
    except ModelHatasi:
        raise
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ModelHatasi("ag", str(e)) from e


def _surum_anahtari(p: dict) -> tuple:
    parcalar = []
    for x in str(p.get("package_version", "0")).replace("-", ".").split("."):
        parcalar.append((0, int(x), "") if x.isdigit() else (-1, 0, x))
    return tuple(parcalar)


def paket_sec(indeks: object, kaynak: str, hedef: str) -> dict:
    """İndeksten kaynak->hedef çeviri paketini (en yeni sürüm) seçer."""
    if not isinstance(indeks, list):
        raise ModelHatasi("gecersiz_indeks")
    adaylar = [p for p in indeks if isinstance(p, dict) and p.get("from_code") == kaynak
               and p.get("to_code") == hedef and p.get("type", "translate") == "translate"
               and isinstance(p.get("links"), list) and p["links"]]
    if not adaylar:
        raise ModelHatasi("paket_yok", f"{kaynak}->{hedef}")
    return max(adaylar, key=_surum_anahtari)


def indeksi_getir() -> object:
    with _ac(INDEKS_URL) as r:
        veri = r.read(INDEKS_ENFAZLA + 1)
    if len(veri) > INDEKS_ENFAZLA:
        raise ModelHatasi("gecersiz_indeks", "çok büyük")
    try:
        return json.loads(veri.decode("utf-8"))
    except ValueError as e:
        raise ModelHatasi("gecersiz_indeks", str(e)) from e


def indir(url: str, hedef_dosya: Path, ilerleme: ILERLEME | None = None) -> int:
    """url'yi dosyaya indirir (yalnız izinli https sunucular); yüzde ilerlemesi bildirir. Boyutu döndürür."""
    toplam_bayt = 0
    with _ac(url) as r, open(hedef_dosya, "wb") as f:
        try:
            uzunluk = int(r.headers.get("Content-Length") or 0)
        except ValueError:
            uzunluk = 0
        if uzunluk > INDIRME_ENFAZLA:
            raise ModelHatasi("cok_buyuk")
        son = -1
        while True:
            try:
                parca = r.read(256 * 1024)
            except (OSError, urllib.error.URLError) as e:
                raise ModelHatasi("ag", str(e)) from e
            if not parca:
                break
            toplam_bayt += len(parca)
            if toplam_bayt > INDIRME_ENFAZLA:
                raise ModelHatasi("cok_buyuk")
            f.write(parca)
            if ilerleme and uzunluk:
                y = min(99, toplam_bayt * 100 // uzunluk)
                if y != son:
                    son = y
                    ilerleme(y)
    if uzunluk and toplam_bayt < uzunluk:
        raise ModelHatasi("ag", "indirme yarım kaldı")
    return toplam_bayt


def _guvenli_ad(ad: str) -> str | None:
    """Zip girdi adı güvenliyse normalleştirilmiş göreli yolu, değilse None döndürür."""
    if not ad or "\\" in ad or "\x00" in ad or ad.startswith("/") or (len(ad) > 1 and ad[1] == ":"):
        return None
    norm = posixpath.normpath(ad)
    if norm.startswith("..") or norm == "." or any(p == ".." for p in norm.split("/")):
        return None
    return norm


def guvenli_ac(zip_yolu: Path, hedef: Path) -> None:
    """Zip'i hedef klasöre açar: mutlak/.. yolları, sembolik bağları ve aşırı boyutu reddeder.

    Cümle bölücü verisi (stanza/) çeviri için gerekmediğinden açılmaz.
    """
    try:
        z = zipfile.ZipFile(zip_yolu)
    except (zipfile.BadZipFile, OSError) as e:
        raise ModelHatasi("gecersiz_paket", "zip değil") from e
    with z:
        girdiler = z.infolist()
        if len(girdiler) > GIRDI_ENFAZLA:
            raise ModelHatasi("gecersiz_paket", "çok fazla dosya")
        toplam = 0
        isler: list[tuple[zipfile.ZipInfo, str]] = []
        for g in girdiler:
            ad = _guvenli_ad(g.filename.rstrip("/") if g.is_dir() else g.filename)
            # Windows'ta zipfile '\\' karakterini sessizce '/' yapar; asıl adla da denetle (her sistemde aynı sonuç)
            if "\\" in getattr(g, "orig_filename", g.filename):
                ad = None
            if ad is None:
                raise ModelHatasi("gecersiz_paket", f"güvensiz yol: {g.filename!r}")
            if (g.external_attr >> 16) & 0o170000 == 0o120000:
                raise ModelHatasi("gecersiz_paket", "sembolik bağ")
            if g.is_dir() or "stanza" in ad.split("/")[:2]:
                continue
            if g.file_size > DOSYA_ENFAZLA:
                raise ModelHatasi("gecersiz_paket", "dosya çok büyük")
            toplam += g.file_size
            if toplam > ACILMIS_ENFAZLA:
                raise ModelHatasi("gecersiz_paket", "açılmış boyut çok büyük")
            isler.append((g, ad))
        hedef.mkdir(parents=True, exist_ok=True)
        kok = hedef.resolve()
        yazilan = 0
        for g, ad in isler:
            yol = (hedef / ad).resolve()
            if kok != yol and kok not in yol.parents:
                raise ModelHatasi("gecersiz_paket", "dizin dışına yazma")
            yol.parent.mkdir(parents=True, exist_ok=True)
            with z.open(g) as kaynak, open(yol, "wb") as cikti:
                while True:
                    parca = kaynak.read(1024 * 1024)
                    if not parca:
                        break
                    yazilan += len(parca)
                    if yazilan > ACILMIS_ENFAZLA or yazilan > toplam + 1024:   # başlıkta yalan söyleyen zip
                        raise ModelHatasi("gecersiz_paket", "açılmış boyut beklenenden büyük")
                    cikti.write(parca)


def modeli_bul(klasor: Path) -> tuple[Path, Path] | None:
    """Açılmış paketin içinde (CTranslate2 model klasörü, SentencePiece modeli) çiftini arar."""
    if not klasor.is_dir():
        return None
    for bin_yolu in sorted(klasor.rglob("model.bin")):
        model = bin_yolu.parent
        for aday in (model / "sentencepiece.model", model.parent / "sentencepiece.model"):
            if aday.is_file():
                return model, aday
        sp = sorted(klasor.rglob("sentencepiece.model"))
        if sp:
            return model, sp[0]
    return None


def hazir_mi(kaynak: str, hedef: str) -> bool:
    try:
        return modeli_bul(paket_dizini(kaynak, hedef)) is not None
    except ModelHatasi:
        return False


def boyut_mb(kaynak: str, hedef: str) -> int | None:
    try:
        d = paket_dizini(kaynak, hedef)
    except ModelHatasi:
        return None
    if not d.is_dir():
        return None
    toplam = sum(p.stat().st_size for p in d.rglob("*") if p.is_file())
    return max(1, round(toplam / (1024 * 1024)))


def kur(kaynak: str, hedef: str, ilerleme: ILERLEME | None = None,
        indeks: object | None = None) -> Path:
    """Dil dosyasını indirip `modeller/argos/<kaynak>_<hedef>/` altına kurar (zaten kuruluysa dokunmaz)."""
    son = paket_dizini(kaynak, hedef)
    if modeli_bul(son):
        if ilerleme:
            ilerleme(100)
        return son
    if ilerleme:
        ilerleme(0)
    paket = paket_sec(indeks if indeks is not None else indeksi_getir(), kaynak, hedef)
    url = next((str(u) for u in paket["links"] if url_izinli_mi(str(u))), None)
    if url is None:
        raise ModelHatasi("izinsiz_adres", str(paket["links"][0]))
    kok = modeller_dizini()
    kok.mkdir(parents=True, exist_ok=True)
    # mkstemp açık bir dosya tutamağı da döndürür; Windows'ta açık dosya taşınamaz/silinemez -> hemen kapat
    _fd, _yol = tempfile.mkstemp(prefix=f"{kaynak}_{hedef}-", suffix=".indiriliyor", dir=kok)
    os.close(_fd)
    gecici_zip = Path(_yol)
    gecici_klasor = Path(tempfile.mkdtemp(prefix=f"{kaynak}_{hedef}-", suffix=".aciliyor", dir=kok))
    try:
        indir(url, gecici_zip, (lambda y: ilerleme(min(95, y))) if ilerleme else None)
        if not zipfile.is_zipfile(gecici_zip):
            raise ModelHatasi("gecersiz_paket", "indirilen dosya zip değil")
        guvenli_ac(gecici_zip, gecici_klasor)
        if modeli_bul(gecici_klasor) is None:
            raise ModelHatasi("gecersiz_paket", "model.bin / sentencepiece.model yok")
        if son.exists():   # bozuk/eksik eski kurulum
            shutil.rmtree(son, ignore_errors=True)
        os.replace(gecici_klasor, son)   # atomik: ya tam kurulu ya hiç
    except ModelHatasi:
        raise
    except OSError as e:
        raise ModelHatasi("disk", str(e)) from e
    finally:
        gecici_zip.unlink(missing_ok=True)
        shutil.rmtree(gecici_klasor, ignore_errors=True)
    if ilerleme:
        ilerleme(100)
    return son
