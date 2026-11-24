# SPDX-License-Identifier: AGPL-3.0-only
"""Çevrimdışı motor: Argos dil dosyası + ctranslate2 + sentencepiece (PROTOKOL 10.4).

Dil dosyası yalnız kullanıcı "İndir"e basınca indirilir (`hazirla`); çeviri sırasında ağ kullanılmaz.
Hatalar `MotorHatasi` olarak fırlar; `kod` (ör. "yerel_dil_dosyasi_yok"), `mesaj_tr` ve `mesaj_en`
öznitelikleri taşır (sınıf aynı kalır: yönetici/işleme `type(e)` ile ayırır).
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import logging
import os
import re
import threading
from typing import Any, Callable

from .. import sozluk as sozluk_mod
from . import argos_model
from .temel import Ceviri, MotorHatasi

log = logging.getLogger("kopru.yerel")

MESAJLAR = {
    "yerel_dil_dosyasi_yok": (
        "Çevrimdışı çeviri için dil dosyası henüz indirilmedi. 'İndir' düğmesine basın (yaklaşık 100 MB, bir kez).",
        "The offline translation language file has not been downloaded yet. Press 'Download' (about 100 MB, one time)."),
    "yerel_bilesen_yok": (
        "Çevrimdışı çeviri bileşeni bu kurulumda bulunamadı. Programı yeniden kurun.",
        "The offline translation component is missing from this installation. Please reinstall the program."),
    "yerel_ceviri_hatasi": (
        "Çevrimdışı çeviri çalışmadı. Dil dosyası bozuk olabilir; yeniden indirmeyi deneyin.",
        "Offline translation failed. The language file may be corrupt; try downloading it again."),
    "yerel_indirme_hatasi": (
        "Dil dosyası indirilemedi. İnternet bağlantınızı kontrol edip tekrar deneyin.",
        "The language file could not be downloaded. Check your internet connection and try again."),
}


def yerel_hata(kod: str) -> MotorHatasi:
    tr, en = MESAJLAR[kod]
    e = MotorHatasi(tr)
    e.kod = kod  # type: ignore[attr-defined]
    e.mesaj_tr, e.mesaj_en = tr, en  # type: ignore[attr-defined]
    return e


def _kod_ayarla(kaynak: str, hedef: str) -> tuple[str, str]:
    k = "en" if kaynak in ("otomatik", "", "auto", None) else kaynak
    return k, hedef


# ---- indirme durumu (süreç içi; aynı çift için tek indirme) -----------------------------------
_kilit = threading.Lock()
_isler: dict[tuple[str, str], concurrent.futures.Future] = {}
_durumlar: dict[tuple[str, str], dict[str, Any]] = {}


def _durum_kaydi(anahtar: tuple[str, str]) -> dict[str, Any]:
    return _durumlar.setdefault(anahtar, {"durum": "yok", "yuzde": 0, "mesaj": None})


def durum(kaynak: str = "en", hedef: str = "tr") -> dict[str, Any]:
    """Panel için: {"hazir", "boyut_mb", "indirme": {"durum","yuzde","mesaj"}} (ağ kullanmaz, hızlıdır)."""
    k, h = _kod_ayarla(kaynak, hedef)
    hazir = argos_model.hazir_mi(k, h)
    with _kilit:
        kayit = dict(_durum_kaydi((k, h)))
    if hazir and kayit["durum"] != "iniyor":
        kayit = {"durum": "bitti" if kayit["durum"] == "bitti" else "yok", "yuzde": 100, "mesaj": None}
    return {"hazir": hazir, "boyut_mb": argos_model.boyut_mb(k, h) if hazir else None, "indirme": kayit}


def _indir_isi(k: str, h: str) -> None:
    anahtar = (k, h)

    def ilerleme(y: int) -> None:
        with _kilit:
            _durum_kaydi(anahtar).update(durum="iniyor", yuzde=int(y), mesaj=None)

    try:
        ilerleme(0)
        argos_model.kur(k, h, ilerleme)
    except argos_model.ModelHatasi as e:
        log.warning("Dil dosyası indirilemedi: %s", e)
        with _kilit:
            _durum_kaydi(anahtar).update(durum="hata", mesaj=MESAJLAR["yerel_indirme_hatasi"][0] if e.kod in ("ag", "disk")
                                          else _hata_mesaji(e))
        raise
    except Exception as e:   # noqa: BLE001
        log.warning("Dil dosyası kurulamadı: %s", e)
        with _kilit:
            _durum_kaydi(anahtar).update(durum="hata", mesaj=MESAJLAR["yerel_indirme_hatasi"][0])
        raise
    with _kilit:
        _durum_kaydi(anahtar).update(durum="bitti", yuzde=100, mesaj=None)


def _hata_mesaji(e: argos_model.ModelHatasi) -> str:
    if e.kod == "paket_yok":
        return "Bu dil çifti için çevrimdışı dil dosyası bulunamadı."
    if e.kod in ("gecersiz_paket", "izinsiz_adres", "gecersiz_indeks", "cok_buyuk"):
        return "İndirilen dil dosyası geçersiz; daha sonra tekrar deneyin."
    return MESAJLAR["yerel_indirme_hatasi"][0]


async def hazirla(kaynak: str = "en", hedef: str = "tr",
                  ilerleme_cb: Callable[[int], Any] | None = None) -> dict[str, Any]:
    """Dil dosyasını indirir (yoksa). Eşzamanlı çağrılar tek indirmeyi paylaşır; kuruluysa hemen döner.

    `ilerleme_cb(yuzde)` olay döngüsünde çağrılır (düz fonksiyon ya da coroutine olabilir).
    Başarısızlıkta MotorHatasi (kod "yerel_indirme_hatasi") fırlatır; sonucu `durum()` ile okuyun.
    """
    k, h = _kod_ayarla(kaynak, hedef)
    anahtar = (k, h)
    if argos_model.hazir_mi(k, h):
        with _kilit:
            _durum_kaydi(anahtar).update(durum="bitti", yuzde=100, mesaj=None)
        if ilerleme_cb:
            await _bildir(ilerleme_cb, 100)
        return durum(k, h)
    with _kilit:
        is_ = _isler.get(anahtar)
        if is_ is None or is_.done():
            is_ = concurrent.futures.Future()
            _isler[anahtar] = is_
            _durum_kaydi(anahtar).update(durum="iniyor", yuzde=0, mesaj=None)
            yeni = True
        else:
            yeni = False
    if yeni:
        def calis() -> None:
            try:
                _indir_isi(k, h)
                is_.set_result(True)
            except BaseException as e:   # noqa: BLE001
                is_.set_exception(e)
        threading.Thread(target=calis, daemon=True, name=f"argos-indir-{k}-{h}").start()
    bekle = asyncio.wrap_future(is_)
    son = -1
    while not bekle.done():
        await asyncio.wait({bekle}, timeout=0.2)
        with _kilit:
            y = _durum_kaydi(anahtar)["yuzde"]
        if ilerleme_cb and y != son:
            son = y
            await _bildir(ilerleme_cb, y)
    try:
        await bekle
    except Exception as e:   # noqa: BLE001
        raise yerel_hata("yerel_indirme_hatasi") from e
    if ilerleme_cb and son != 100:
        await _bildir(ilerleme_cb, 100)
    return durum(k, h)


async def _bildir(cb: Callable[[int], Any], y: int) -> None:
    try:
        r = cb(y)
        if inspect.isawaitable(r):
            await r
    except Exception:   # noqa: BLE001 — bildirim hatası indirmeyi bozmasın
        log.debug("ilerleme bildirimi başarısız", exc_info=True)


# ---- çeviri ----------------------------------------------------------------------------------
_YER_DESEN = re.compile(r"\[\s*\[\s*T(\d+)\s*\]\s*\]")


def _hepsi_buyuk(m: str) -> bool:
    harfler = [c for c in m if c.isalpha()]
    return len(harfler) >= 2 and all(c.isupper() for c in harfler)


def _tr_buyuk(s: str) -> str:
    return s.replace("i", "İ").replace("ı", "I").upper()
_CUMLE_DESEN = re.compile(r"(?<=[.!?…])\s+")
_cevirici_onbellek: dict[str, tuple[Any, Any]] = {}
_cevirici_kilit = threading.Lock()


def cumlelere_bol(metin: str) -> list[list[str]]:
    """Satırlara, sonra cümlelere böler: [[cümle,...] her satır için]; boş satırlar boş liste olur."""
    return [[c for c in _CUMLE_DESEN.split(satir.strip()) if c.strip()] for satir in metin.split("\n")]


def _yukle(model_dizini: str, sp_yolu: str) -> tuple[Any, Any]:
    """(Translator, SentencePieceProcessor); yüklenenler önbelleğe alınır."""
    with _cevirici_kilit:
        bulundu = _cevirici_onbellek.get(model_dizini)
        if bulundu:
            return bulundu
        try:
            import ctranslate2
            import sentencepiece
        except Exception as e:   # noqa: BLE001 — eksik ya da bozuk kurulum (ImportError, DLL/OSError)
            h = yerel_hata("yerel_bilesen_yok")
            h.ayrinti = f"{type(e).__name__}: {e}"[:300]   # kullanıcı "Ayrıntı"da görür, bize gönderebilir
            raise h from e
        cevirici = ctranslate2.Translator(model_dizini, device="cpu", inter_threads=1,
                                          intra_threads=max(1, (os.cpu_count() or 2) // 2))
        sp = sentencepiece.SentencePieceProcessor()
        sp.Load(sp_yolu)
        _cevirici_onbellek[model_dizini] = (cevirici, sp)
        return cevirici, sp


def _cumleleri_cevir(cevirici: Any, sp: Any, cumleler: list[str]) -> list[str]:
    if not cumleler:
        return []
    parcalar = [sp.encode(c, out_type=str) for c in cumleler]
    sonuclar = cevirici.translate_batch(
        parcalar, beam_size=2, max_decoding_length=max(64, min(512, max(len(p) for p in parcalar) * 3)),
        max_batch_size=32)
    cikti = []
    for s in sonuclar:
        jetonlar = s.hypotheses[0] if hasattr(s, "hypotheses") else s["hypotheses"][0]
        cikti.append(sp.decode(list(jetonlar)).strip())
    return cikti


def metni_cevir(cevirici: Any, sp: Any, metin: str) -> str:
    satirlar = cumlelere_bol(metin)
    duz = [c for s in satirlar for c in s]
    ceviri = iter(_cumleleri_cevir(cevirici, sp, duz))
    return "\n".join(" ".join(next(ceviri) for _ in s) for s in satirlar)


class YerelMotor:
    kod = "yerel"
    ad = "Çevrimdışı (yerel)"
    anahtar_gerekli = False
    cevrimdisi = True
    ucretsiz = True

    @staticmethod
    def kurulu_mu() -> bool:
        """ctranslate2 ve sentencepiece içe aktarılabiliyor mu (dil dosyasından bağımsız)."""
        try:
            import ctranslate2   # noqa: F401
            import sentencepiece   # noqa: F401
            return True
        except Exception:   # noqa: BLE001
            return False

    @staticmethod
    def hazirla(kaynak: str = "en", hedef: str = "tr") -> None:
        """Eşzamanlı (engelleyen) indirme; yeni kodda modül düzeyindeki `hazirla` kullanılır."""
        k, h = _kod_ayarla(kaynak, hedef)
        try:
            argos_model.kur(k, h)
        except argos_model.ModelHatasi as e:
            raise yerel_hata("yerel_indirme_hatasi") from e

    def _cevir_senkron(self, metinler: list[str], kaynak: str, hedef: str,
                       sozluk: dict[str, str]) -> list[str]:
        k, h = _kod_ayarla(kaynak, hedef)
        try:
            model = argos_model.modeli_bul(argos_model.paket_dizini(k, h))
        except argos_model.ModelHatasi:
            model = None
        if model is None:
            raise yerel_hata("yerel_dil_dosyasi_yok")
        cevirici, sp = _yukle(str(model[0]), str(model[1]))
        out = []
        try:
            for m in metinler:
                buyuk = _hepsi_buyuk(m)
                if buyuk:   # "KILLER" gibi büyük harfli yazıyı model isim sanmasın: küçült, çevir, büyüt
                    m = m.lower().capitalize()
                m, vekil = _adlari_vekille(m, sozluk)
                korunan, harita = sozluk_mod.koru(m, {a: c for a, c in sozluk.items() if a not in vekil.values()})
                s = metni_cevir(cevirici, sp, korunan)
                if harita and not all(_yer_var(s, y) for y in harita):
                    # model yer tutucuyu bozdu: korumasız çevir, terimleri sonradan düzelt
                    s = sozluk_mod.son_kontrol(m, metni_cevir(cevirici, sp, m), sozluk)
                else:
                    s = sozluk_mod.geri_koy(_YER_DESEN.sub(lambda x: f"[[T{x.group(1)}]]", s), harita)
                s = _vekilleri_geri_koy(s.replace(" ⁇", "").replace("⁇", ""), vekil)   # ⁇: modelin bilinmeyen simgesi
                out.append(_tr_buyuk(s) if buyuk and hedef == "tr" else s.upper() if buyuk else s)
        except MotorHatasi:
            raise
        except Exception as e:   # noqa: BLE001
            log.warning("Çevrimdışı çeviri hatası: %s", e)
            raise yerel_hata("yerel_ceviri_hatasi") from e
        return out

    async def cevir(self, metinler: list[str], kaynak: str, hedef: str,
                    sozluk: dict[str, str], aciklama: bool = False) -> list[Ceviri]:
        # model yükleme ve çeviri CPU işi: olay döngüsü dışında
        sonuc = await asyncio.to_thread(self._cevir_senkron, metinler, kaynak, hedef, sozluk)
        return [Ceviri(s) for s in sonuc]


# PROTOKOL 20.4: Argos modeli "[[T0]]" yer tutucusunu çoğu zaman bozar ("Âyet-i kerime'nin…"). Korunacak ADLAR yerine
# modelin hep aynen bıraktığı sıradan bir ad konur; çeviriden sonra asıl ad, eki ses uyumuna göre yeniden kurularak döner.
VEKIL_ADLAR = ("Joe", "Max", "Tom", "Sam", "Ben", "Dan", "Bob", "Tim")


def _adlari_vekille(metin: str, sozluk: dict[str, str]) -> tuple[str, dict[str, str]]:
    """{vekil: asıl ad}. Yalnız Sozluk.adlar (büyük/küçük harfe duyarlı) için."""
    adlar = [a for a in getattr(sozluk, "adlar", ()) if sozluk.get(a) == a]
    vekil: dict[str, str] = {}
    bos = [v for v in VEKIL_ADLAR if not re.search(r"(?<!\w)" + v + r"(?!\w)", metin)]
    for ad in sorted(adlar, key=len, reverse=True):
        desen = re.compile(r"(?<![\w'’])" + re.escape(ad) + r"(?![\w])")
        if not bos or not desen.search(metin):
            continue
        v = bos.pop(0)
        metin = desen.sub(v, metin)
        vekil[v] = ad
    return metin, vekil


def _vekilleri_geri_koy(metin: str, vekil: dict[str, str]) -> str:
    from . import on_katman
    for v, ad in vekil.items():
        metin = re.sub(r"(?<![\w])" + v + r"(?:(['’])([^\W\d_]{1,6}))?(?![\w])",
                       lambda m, a=ad: a + (m.group(1) + on_katman.ek_kur(a, m.group(2)) if m.group(2) else ""), metin)
    return metin


def _yer_var(metin: str, yer: str) -> bool:
    num = yer[3:-2]
    return re.search(r"\[\s*\[\s*T" + num + r"\s*\]\s*\]", metin) is not None
