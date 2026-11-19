# SPDX-License-Identifier: AGPL-3.0-only
"""Ayar dosyasını okur/yazar (anahtarlar burada TUTULMAZ)."""
from __future__ import annotations

import copy
import json
import logging
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .dublaj import VARSAYILAN as VARSAYILAN_DUBLAJ

log = logging.getLogger("kopru.ayarlar")

VARSAYILAN_GORUNUM: dict[str, Any] = {
    "yazi_boyutu": 44, "konum": "alt", "kenar_bosluk": 0.08, "arka_plan": 0.55,
    "yazi_rengi": "#FFFFFF", "konusan_rengi": "#FFD166",
    "asil_goster": False, "ekran_cevir": True, "onceki_goster": True,
    "ekran_olcek": 1.0,   # ekran öğelerinin genel yazı çarpanı, 0.6-2.0 (PROTOKOL 11.4)
}

VARSAYILAN: dict[str, Any] = {
    "arayuz_dili": "tr",
    "hedef_dil": "tr",
    "kaynak_dil": "otomatik",
    "motor": "gemini",
    "yedek_motor": "yerel",
    "modeller": {},          # boş = `kalite` modeli seçer; yazılan model kaliteyi ezer
    "kalite": "en_iyi",      # en_iyi | dengeli | hizli
    "hafiza_izni": None,     # None (sorulmadı) | True | False
    "guncelleme_denetle": True,  # günde en çok bir kez GitHub'a "yeni sürüm var mı" diye sorar

    "erisim": {"ucretsiz_dakika_gun": 30},   # günlük kodsuz çeviri süresi (PROTOKOL 7.3)

    "kaynak": "ekran:1",
    "bolge_altyazi": {"x": 0.1, "y": 0.72, "g": 0.8, "y2": 0.25},
    "bolgeler": [],  # boş = otomatik; doluysa yalnız bu kareler okunur (en çok 6, PROTOKOL 7.1/10.2)
    "ekrani_cevir": True,
    "kisa_aciklama": True,
    "ses_cevir": False,
    "dublaj": VARSAYILAN_DUBLAJ,   # Türkçe dublaj (PROTOKOL 9.3); varsayılan KAPALI
    "kapi": 8642,
    "aktif_oyun": "varsayilan",
    "kurulum_tamam": False,
    "gosterim": "bilgisayar",   # bilgisayar | tv | tarayici (PROTOKOL 10.2)
    "katman_ekran": 1,          # ekran katmanının açılacağı ekran numarası (1..n)
    "cihaz": None,   # ps5 | xbox | pc | kart
    "tv": None,      # lg | samsung | androidtv | yok
    "gorunum": VARSAYILAN_GORUNUM,
    # genel kısayol tuşları, yalnız Windows (PROTOKOL §13.1); boş dize = kapalı
    "kisayollar": {"baslat_durdur": "ctrl+shift+t", "gizle_goster": "ctrl+shift+h", "yeniden_oku": "ctrl+shift+r"},
}


GOSTERIMLER = ("bilgisayar", "tv", "tarayici")
EN_COK_EKRAN = 16
BOLGE_TURLERI = ("altyazi", "ust_yazi", "diger")
EN_COK_BOLGE = 6
EN_KUCUK_GENISLIK = 0.03
EN_KUCUK_YUKSEKLIK = 0.02
_BOLGE_AD = {"altyazi": "Altyazı", "ust_yazi": "Üstteki yazılar", "diger": "Diğer"}
HEDEF_ADLARI = ("ustune", "altyazi")
EN_KUCUK_OLCEK, EN_BUYUK_OLCEK = 0.6, 2.0


def _oran(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1


def olcek_gecerli(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and EN_KUCUK_OLCEK <= v <= EN_BUYUK_OLCEK


def _kutu_gecerli(b: Any) -> bool:
    if not isinstance(b, dict) or not all(_oran(b.get(f)) for f in ("x", "y", "g", "y2")):
        return False
    if b["g"] < EN_KUCUK_GENISLIK or b["y2"] < EN_KUCUK_YUKSEKLIK:
        return False
    return b["x"] + b["g"] <= 1.0001 and b["y"] + b["y2"] <= 1.0001


def hedef_gecerli(h: Any) -> bool:
    """Bölge hedefi (PROTOKOL 11.4): yok | "ustune" | "altyazi" | kullanıcının çizdiği {x,y,g,y2} kutusu."""
    if h is None:
        return True
    if isinstance(h, str):
        return h in HEDEF_ADLARI
    return _kutu_gecerli(h)


def varsayilan_hedef(tur: str) -> str:
    return "altyazi" if tur == "altyazi" else "ustune"


def bolge_gecerli(b: Any) -> bool:
    """Tek bölge: 0-1 oranlar, ekran içinde, en küçük boyutun üstünde, türü bilinen, adı en çok 30 karakter."""
    if not isinstance(b, dict) or not all(_oran(b.get(f)) for f in ("x", "y", "g", "y2")):
        return False
    if b["g"] < EN_KUCUK_GENISLIK or b["y2"] < EN_KUCUK_YUKSEKLIK:
        return False
    if b["x"] + b["g"] > 1.0001 or b["y"] + b["y2"] > 1.0001:
        return False
    if b.get("tur") not in BOLGE_TURLERI:
        return False
    ad = b.get("ad", "")
    if not (isinstance(ad, str) and len(ad) <= 30):
        return False
    if "hedef" in b and not hedef_gecerli(b["hedef"]):
        return False
    return "olcek" not in b or b["olcek"] is None or olcek_gecerli(b["olcek"])


def bolgeler_gecerli(v: Any) -> bool:
    return isinstance(v, list) and len(v) <= EN_COK_BOLGE and all(bolge_gecerli(b) for b in v)


def bolgeleri_temizle(v: Any) -> list[dict[str, Any]]:
    """Geçerli bölgeleri yalnız bilinen alanlarla döndürür (bozuk kayıt sessizce atılır)."""
    if not isinstance(v, list):
        return []
    out = []
    for b in v[:EN_COK_BOLGE]:
        if bolge_gecerli(b):
            h = b.get("hedef")
            if isinstance(h, dict):
                h = {f: float(h[f]) for f in ("x", "y", "g", "y2")}
            elif h is None:
                h = varsayilan_hedef(b["tur"])
            olcek = b.get("olcek")
            out.append({"x": float(b["x"]), "y": float(b["y"]), "g": float(b["g"]), "y2": float(b["y2"]),
                        "tur": b["tur"], "ad": b.get("ad") or _BOLGE_AD[b["tur"]], "hedef": h,
                        "olcek": float(olcek) if olcek is not None else 1.0})
    return out


def ayar_dizini() -> Path:
    """İşletim sistemine göre ayar klasörü (KOPRU_AYAR_DIZINI öncelikli)."""
    ozel = os.environ.get("KOPRU_AYAR_DIZINI")
    if ozel:
        return Path(ozel)
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / "AltyaziKoprusu"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AltyaziKoprusu"
    taban = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(taban) / "altyazikoprusu"


def _birlestir(taban: dict[str, Any], ek: dict[str, Any]) -> dict[str, Any]:
    """İç içe sözlükleri birleştirir; bilinmeyen üst alanlar korunur."""
    sonuc = copy.deepcopy(taban)
    for k, v in ek.items():
        if isinstance(v, dict) and isinstance(sonuc.get(k), dict):
            sonuc[k] = _birlestir(sonuc[k], v)
        else:
            sonuc[k] = v
    return sonuc


EN_COK_YEDEK = 5


def bozuk_yedekle(yol: Path) -> Path | None:
    """Okunamayan dosyayı silmeden yanına kopyalar (`<ad>.bozuk-<an>`); en çok 5 yedek tutulur."""
    try:
        hedef = yol.with_name(f"{yol.name}.bozuk-{time.strftime('%Y%m%d-%H%M%S')}")
        n = 1
        while hedef.exists():
            n += 1
            hedef = yol.with_name(f"{yol.name}.bozuk-{time.strftime('%Y%m%d-%H%M%S')}-{n}")
        shutil.copy2(yol, hedef)
        eskiler = sorted(yol.parent.glob(f"{yol.name}.bozuk-*"))
        for e in eskiler[:-EN_COK_YEDEK]:
            try:
                e.unlink()
            except OSError:
                pass
        log.warning("%s okunamadı; kopyası %s olarak saklandı, varsayılanlarla devam ediliyor", yol.name, hedef.name)
        return hedef
    except OSError:
        return None


def atomik_yaz(yol: Path, metin: str, deneme: int = 8) -> None:
    """Geçici dosya + os.replace. Windows'ta hedef başka bir program (antivirüs, eşitleme) tarafından
    kilitliyse (PermissionError) kısa aralıklarla yeniden dener."""
    yol.parent.mkdir(parents=True, exist_ok=True)
    fd, gecici = tempfile.mkstemp(dir=yol.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(metin)
        for i in range(deneme):
            try:
                os.replace(gecici, yol)
                return
            except PermissionError:
                if i == deneme - 1:
                    raise
                time.sleep(0.02 * (i + 1))
    except BaseException:
        try:
            os.unlink(gecici)
        except OSError:
            pass
        raise


def _tip_duzelt(deger: Any, taban: Any) -> Any:
    """Dosyadan gelen değeri varsayılanın türüne uydurur; uymuyorsa varsayılanı verir."""
    if isinstance(taban, dict):
        if not isinstance(deger, dict):
            return copy.deepcopy(taban)
        out = dict(deger)
        for k, t in taban.items():
            if k in out:
                out[k] = _tip_duzelt(out[k], t)
        return out
    if isinstance(taban, bool):
        return deger if isinstance(deger, bool) else taban
    if isinstance(taban, (int, float)):
        return deger if isinstance(deger, (int, float)) and not isinstance(deger, bool) else taban
    if isinstance(taban, str):
        return deger if isinstance(deger, str) else taban
    if isinstance(taban, list):
        return deger if isinstance(deger, list) else copy.deepcopy(taban)
    return deger   # None: herhangi bir değer olabilir


def duzelt(ayar: dict[str, Any]) -> dict[str, Any]:
    """Bozuk ya da elle yanlış yazılmış değerler çökertmesin: türü/aralığı tutmayan alan varsayılana döner."""
    s = _tip_duzelt(ayar, VARSAYILAN)
    v = VARSAYILAN
    if isinstance(ayar, dict) and "yedek_motor" in ayar and ayar["yedek_motor"] is None:
        s["yedek_motor"] = None    # "yedek yok" geçerli bir seçimdir
    if not (isinstance(s["kapi"], int) and 1024 <= s["kapi"] <= 65535):
        s["kapi"] = v["kapi"]
    if s["arayuz_dili"] not in ("tr", "en"):
        s["arayuz_dili"] = v["arayuz_dili"]
    if s["gosterim"] not in GOSTERIMLER:
        s["gosterim"] = v["gosterim"]
    if not (isinstance(s["katman_ekran"], int) and 1 <= s["katman_ekran"] <= EN_COK_EKRAN):
        s["katman_ekran"] = v["katman_ekran"]
    if s["kalite"] not in ("en_iyi", "dengeli", "hizli"):
        s["kalite"] = v["kalite"]
    for alan in ("motor",):
        if not s[alan].strip():
            s[alan] = v[alan]
    if s["hafiza_izni"] not in (None, True, False):
        s["hafiza_izni"] = None
    if not s["aktif_oyun"].strip():
        s["aktif_oyun"] = v["aktif_oyun"]
    s["modeller"] = {str(k): m for k, m in s["modeller"].items() if isinstance(m, str)}
    s["bolgeler"] = bolgeleri_temizle(s["bolgeler"])
    b = s["bolge_altyazi"]
    if not all(_oran(b.get(f)) for f in ("x", "y", "g", "y2")):
        s["bolge_altyazi"] = copy.deepcopy(v["bolge_altyazi"])
    if not olcek_gecerli(s["gorunum"].get("ekran_olcek")):
        s["gorunum"]["ekran_olcek"] = v["gorunum"]["ekran_olcek"]
    if s["gorunum"].get("konum") not in ("alt", "ust"):
        s["gorunum"]["konum"] = v["gorunum"]["konum"]
    if s["erisim"].get("ucretsiz_dakika_gun") is not None and not (
            isinstance(s["erisim"]["ucretsiz_dakika_gun"], int) and 0 <= s["erisim"]["ucretsiz_dakika_gun"] <= 1440):
        s["erisim"]["ucretsiz_dakika_gun"] = v["erisim"]["ucretsiz_dakika_gun"]
    from . import kisayol
    for k, t in list(s["kisayollar"].items()):
        if not (k in kisayol.EYLEMLER and kisayol.kisayol_gecerli(t)):
            s["kisayollar"][k] = v["kisayollar"].get(k, "")
    from . import dublaj as dublaj_mod
    d = s["dublaj"]
    for k in list(d):
        if k in v["dublaj"] and not dublaj_mod.ayar_gecerli({k: d[k]}):
            d[k] = v["dublaj"][k]
    return s


def yukle() -> dict[str, Any]:
    """Ayarları okur. Dosya yok/bozuk/eksikse program yine açılır: bozuk dosyanın kopyası saklanır."""
    yol = ayar_dizini() / "ayarlar.json"
    okunan: dict[str, Any] = {}
    try:
        ham = yol.read_text(encoding="utf-8")
    except FileNotFoundError:
        ham = None
    except (OSError, UnicodeDecodeError):
        ham = None
        bozuk_yedekle(yol)
    if ham is not None:
        try:
            v = json.loads(ham)
            if not isinstance(v, dict):
                raise ValueError("sozluk degil")
            okunan = v
        except ValueError:
            bozuk_yedekle(yol)
    return duzelt(_birlestir(VARSAYILAN, okunan))


def kaydet(ayar: dict[str, Any]) -> None:
    """Atomik yazım: geçici dosya + os.replace (Windows'ta kilitliyse yeniden dener)."""
    atomik_yaz(ayar_dizini() / "ayarlar.json", json.dumps(ayar, ensure_ascii=False, indent=2))


def guncelle(ayar: dict[str, Any], kismi: dict[str, Any]) -> dict[str, Any]:
    """Gelen alanları birleştirir (yalnız bilinen üst alanlar), kaydeder."""
    bilinen = {k: v for k, v in kismi.items() if k in VARSAYILAN}
    yeni = _birlestir(ayar, bilinen)
    kaydet(yeni)
    return yeni
