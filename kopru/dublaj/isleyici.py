# SPDX-License-Identifier: AGPL-3.0-only
"""Dublaj boru hattı (PROTOKOL 9.1): konuşma parçası -> yazı -> çeviri -> ses -> süreye sığdır -> çal.

Her şey dışarıdan verilebilir (STT, çevirmen, ses motoru, çıkış, saat): sahte parçalarla sınanır.
Gizlilik: ses ve konuşmacı örnekleri YALNIZ bellekte (RAM); bu modül dosya yazmaz.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Callable

import numpy as np

from ..ceviri.temel import AgHatasi, AnahtarHatasi, ErisimSiniri, MotorHatasi
from ..isleme import sure_ms
from ..onbellek import normallestir
from . import dsp
from ..ses import SesHatasi
from .temel import DublajHatasi

log = logging.getLogger("kopru.dublaj")

EN_AZ_PARCA_SN = 0.6          # bundan kısa konuşma parçası dublajlanmaz
REFERANS_EN_AZ_SN = 3.0       # kendi örneği bundan kısaysa benzer eski örnek aranır
REFERANS_EN_COK_SN = 10.0
BENZERLIK_ESIGI = 0.8         # "aynı konuşmacı sayılır" kosinüs eşiği (ucuz parmak izi)
BANKA_BOYUTU = 12             # RAM'de tutulan son konuşmacı örneği sayısı
YAZI_ESLEME_SN = 3.0          # ekran altyazısı ±3 sn içinde olmalı
YAZI_BENZERLIK = 0.55
SUSTURMA_PAYI_SN = 0.5        # kendi çaldığımız sesi geri dinlemeyelim (loopback)
EN_COK_BEKLEYEN = 3           # geride kalırsak eski parçalar atılır (gecikme birikmesin)
HIZ_TOLERANS = 1.03           # bu orana kadar uzun sayılmaz


HEDEF_RMS = 0.08


def _duzey_esitle(pcm: np.ndarray) -> np.ndarray:
    """Kısık konuşmayı (oyunda diyalog sesi düşük) yaklaşık sabit düzeye getirir; en çok 30 kat (+30 dB)."""
    if len(pcm) == 0:
        return pcm
    r = float(np.sqrt(np.mean(np.square(pcm, dtype=np.float64))))
    if r < 1e-5:
        return pcm
    k = min(30.0, HEDEF_RMS / r)
    if 0.8 < k < 1.25:
        return pcm
    return np.clip(pcm * k, -1.0, 1.0).astype(np.float32)


@dataclass
class _Klip:
    pcm: np.ndarray
    sr: int
    iz: np.ndarray


@dataclass
class _Erken:
    """Ekrandaki altyazı görünür görünmez hazırlanan dublaj (gecikmeyi kısaltır)."""
    yazi_id: str
    asil: str
    tr: str
    ses: Any = None             # float32 mono (ref yoksa None: yalnız çeviri hazır)
    sr: int = 0
    iz: Any = None              # kullanılan konuşmacı örneğinin parmak izi
    ceviri_ms: int = 0
    ses_ms: int = 0


@dataclass
class DublajSonucu:
    yazi_id: str
    metin: str
    sure_sn: float
    hiz: float                 # uygulanan hızlandırma (1.0 = yok)
    kisaltildi: bool           # ikinci (daha kısa) çeviri istendi mi
    referans: str              # "kendi" | "benzer" | "kisa_kendi"
    olcum: dict[str, Any] | None = None   # aşama süreleri (ms): stt, ceviri, ses, bekleme, ilk_ses


class Isleyici:
    def __init__(self, stt: Any, yonetici: Any, motor_getir: Callable[[], Any], cikis_getir: Callable[[str], Any],
                 yayin: Any, ayar_getir: Callable[[], dict[str, Any]],
                 saat: Callable[[], float] = time.monotonic) -> None:
        self.stt = stt
        self.yonetici = yonetici
        self.motor_getir = motor_getir
        self.cikis_getir = cikis_getir
        self.yayin = yayin
        self.ayar = ayar_getir
        self.saat = saat
        self._yazilar: deque[tuple[float, str, str, str | None]] = deque(maxlen=20)  # (an, id, asil, konusan)
        self._yapilan_yazilar: set[str] = set()
        self._banka: deque[_Klip] = deque(maxlen=BANKA_BOYUTU)    # konuşmacı örnekleri (yalnız RAM)
        self._susturma: deque[tuple[float, float]] = deque(maxlen=8)   # kendi çaldığımız zaman aralıkları
        self._sayac = 0
        self._kuyruk: asyncio.Queue = asyncio.Queue()
        self.son_hata: str | None = None
        self.son_sonuc: DublajSonucu | None = None
        self.oynuyor = False
        self._erken: dict[str, asyncio.Task] = {}          # yazi_id -> önden hazırlık
        self._erken_calinan: set[str] = set()              # parça gelmeden çalınmış altyazılar
        self._konusan_ref: dict[str, tuple[np.ndarray, int, np.ndarray]] = {}   # OCR'deki konuşan adı -> örnek
        self._rms: deque[float] = deque(maxlen=40)
        self.olcumler: deque[dict[str, Any]] = deque(maxlen=20)
        self.profil_kaydet: Callable[[str, np.ndarray, int], None] | None = None

    # -- ekran altyazısı bilgisi (Yayin dinleyicisi) --
    def olay(self, olay: str, veri: dict[str, Any]) -> None:
        """Yayın dinleyicisi: ekrana gelen altyazıları eşleme için hatırlar."""
        if olay == "yazi" and veri.get("asil") and not str(veri.get("id", "")).startswith("d"):
            kimlik = str(veri.get("id", ""))
            self._yazilar.append((self.saat(), kimlik, str(veri["asil"]), veri.get("konusan")))
            # Altyazının Türkçesi zaten hazır: dublaj onu seslendirir (ikinci bir çeviri isteği yok: daha hızlı
            # ve çeviri motorunun istek sınırı/kotası iki kat harcanmaz).
            tr = " ".join(str(veri.get("metin") or "").split())
            self._erken_baslat(kimlik, str(veri["asil"]), veri.get("konusan"), tr or None)

    # -- önden hazırlık: altyazı görünür görünmez çeviri + ses --
    def _erken_baslat(self, kimlik: str, asil: str, konusan: str | None, tr: str | None = None) -> None:
        d = self.ayar().get("dublaj") or {}
        if not d.get("erken_seslendir", True) or self.motor_getir() is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        eski = self._erken.pop(kimlik, None)
        if eski is not None:
            eski.cancel()                    # aynı kimlik, metin değişti (daktilo efekti): yeniden
        self._erken[kimlik] = loop.create_task(self._erken_hazirla(kimlik, asil, konusan, tr))
        while len(self._erken) > 6:
            self._erken.pop(next(iter(self._erken))).cancel()

    async def _erken_hazirla(self, kimlik: str, asil: str, konusan: str | None,
                             hazir_tr: str | None = None) -> _Erken | None:
        try:
            ayar = self.ayar()
            d = ayar.get("dublaj") or {}
            motor = self.motor_getir()
            t0 = self.saat()
            tahmini = max(1.0, len(asil) / 15.0)            # İngilizce ~15 karakter/sn
            if hazir_tr and not self.yonetici_dublaj_izni():
                return None                                  # dublaj süresi yok (PROTOKOL 17.2)
            tr = hazir_tr or await self._cevir(asil, ayar, tahmini)
            e = _Erken(kimlik, asil, tr, ceviri_ms=int((self.saat() - t0) * 1000))
            ref = self._konusan_ref.get(konusan or "") or (
                (self._banka[-1].pcm, self._banka[-1].sr, self._banka[-1].iz) if self._banka else None)
            if ref is None and getattr(motor, "varsayilan_ses", False) and self._erken_cal_mi(ayar):
                # hiç örnek yok (ör. oyunda diyalog sesi 0, profil yok): motorun nötr Türkçe sesi
                ref = (np.zeros(0, dtype=np.float32), 24000, None)
            if tr and ref is not None and motor is not None:
                t1 = self.saat()
                ses, sr = await self._seslendir(motor, tr, ref[0], ref[1], None)
                e.ses, e.sr, e.iz, e.ses_ms = dsp.mono_float(ses), sr, ref[2], int((self.saat() - t1) * 1000)
                if e.iz is None:
                    e.iz = np.zeros(13)
                if self._erken_cal_mi(ayar):
                    # İngilizce ses kısık/çıkarılmış: beklemeden çal (parça gelince tekrar çalınmaz)
                    self._erken_calinan.add(kimlik)
                    self._kuyruk.put_nowait(("erken", e))
            return e
        except asyncio.CancelledError:
            raise
        except Exception as ex:   # noqa: BLE001 — önden hazırlık başarısızsa normal yol çalışır
            log.debug("önden hazırlık başarısız: %s", type(ex).__name__)
            return None

    def yonetici_dublaj_izni(self) -> bool:
        f = getattr(self.yonetici, "dublaj_izni", None)
        try:
            return bool(f()) if callable(f) else True
        except Exception:   # noqa: BLE001
            return True

    def _erken_cal_mi(self, ayar: dict[str, Any]) -> bool:
        """Altyazıyla hazırlanan Türkçe ses, İngilizce cümle bitmeden çalınsın mı?

        Evet: ses TV'den çalıyorsa (kullanıcı oyunda diyalog sesini kısar, §14.3) ya da İngilizce ses
        bilgisayarda tamamen çıkarılıyorsa. Hayır: İngilizce tam sesle duyuluyorsa (üst üste binmesin).
        """
        d = ayar.get("dublaj") or {}
        from . import tamamen_turkce_mu
        return d.get("cikis", "bilgisayar") == "tv" or tamamen_turkce_mu(ayar)

    def profil_yukle(self, profiller: dict[str, tuple[np.ndarray, int]]) -> None:
        """Ses profili (izinle diske kaydedilmiş karakter örnekleri) oturum başında belleğe alınır."""
        for ad, (pcm, sr) in profiller.items():
            self._konusan_ref[ad] = (pcm, sr, dsp.parmak_izi(pcm, sr))

    async def _seslendir(self, motor: Any, metin: str, ref: np.ndarray, sr: int,
                         duygu: dict[str, float] | None) -> tuple[Any, int]:
        if getattr(motor, "duygu_destekli", False):
            return await motor.seslendir(metin, ref, sr, duygu=duygu)
        return await motor.seslendir(metin, ref, sr)

    async def _erken_cal(self, e: _Erken) -> None:
        ayar = self.ayar()
        d = ayar.get("dublaj") or {}
        cikis = self.cikis_getir(d.get("cikis", "bilgisayar"))
        self._yapilan_yazilar.add(e.yazi_id)
        bas = self.saat()
        self.oynuyor = True
        try:
            await cikis.oynat(e.ses, e.sr, ayar, e.yazi_id)
        finally:
            self.oynuyor = False
            self._susturma.append((bas, self.saat()))
        self.olcumler.append({"erken": True, "ceviri_ms": e.ceviri_ms, "ses_ms": e.ses_ms, "bekleme_ms": None})

    def _eslesen_yazi(self, metin: str, bas: float, bitis: float,
                      calinanlar_dahil: bool = False) -> tuple[str, str, str | None] | None:
        """±3 sn içinde ekrana gelmiş, benzer içerikli altyazı (varsa en benzeri)."""
        n = normallestir(metin)
        en, sonuc = YAZI_BENZERLIK, None
        for an, kimlik, asil, konusan in self._yazilar:
            atla = kimlik in self._yapilan_yazilar and not (calinanlar_dahil and kimlik in self._erken_calinan)
            if atla or not (bas - YAZI_ESLEME_SN <= an <= bitis + YAZI_ESLEME_SN):
                continue
            r = SequenceMatcher(None, n, normallestir(asil)).ratio()
            if r >= en:
                en, sonuc = r, (kimlik, asil, konusan)
        return sonuc

    # -- konuşmacı örneği --
    def referans_sec(self, pcm: np.ndarray, sr: int) -> tuple[np.ndarray, int, str]:
        """3-10 sn kendi sesi; kısaysa en benzer yakın konuşmacı örneği (ucuz parmak izi)."""
        kes = dsp.sessizlik_kirp(pcm, sr)
        sure = len(kes) / sr
        if sure >= REFERANS_EN_AZ_SN:
            kes = dsp.en_iyi_pencere(kes, sr, REFERANS_EN_COK_SN)
            self._banka.append(_Klip(kes, sr, dsp.parmak_izi(kes, sr)))
            return kes, sr, "kendi"
        if len(kes) == 0:
            kes = pcm
        iz = dsp.parmak_izi(kes, sr)
        en, secilen = BENZERLIK_ESIGI, None
        for k in self._banka:
            b = dsp.benzerlik(iz, k.iz)
            if b >= en:
                en, secilen = b, k
        if secilen is not None:
            return secilen.pcm, secilen.sr, "benzer"
        return kes, sr, "kisa_kendi"

    def temizle(self) -> None:
        """Oturum bitti: konuşmacı örnekleri ve ekran altyazısı hafızası silinir."""
        self._banka.clear()
        self._konusan_ref.clear()
        for t in self._erken.values():
            t.cancel()
        self._erken.clear()
        self._erken_calinan.clear()
        self._yazilar.clear()
        self._yapilan_yazilar.clear()
        self._susturma.clear()

    # -- ana akış --
    def _susturulmus(self, bas: float, bitis: float) -> bool:
        return any(bas < b + SUSTURMA_PAYI_SN and bitis > a for a, b in self._susturma)

    async def _cevir(self, metin: str, ayar: dict[str, Any], sure_sn: float, onceki: str | None = None) -> str:
        c = await self.yonetici.dublaj_cevir(metin, ayar["kaynak_dil"], ayar["hedef_dil"], sure_sn, onceki)
        return c.metin.strip()

    async def isle(self, parca: Any) -> DublajSonucu | None:
        """Tek konuşma parçasını baştan sona dublajlar. Çıktı çalındıktan sonra döner."""
        ayar = self.ayar()
        d = ayar.get("dublaj") or {}
        motor = self.motor_getir()
        pcm, sr = parca.pcm, parca.sr
        temiz = getattr(parca, "temiz", None)          # işçinin ayırdığı (arka plansız) konuşma
        konusma = dsp.mono_float(temiz) if temiz is not None and len(temiz) == len(pcm) else pcm
        konusma = _duzey_esitle(konusma)     # oyunda diyalog sesi kısıkken (%10-20) de klon/yazı için yeterli düzey
        sure_sn = len(pcm) / sr
        olcum: dict[str, Any] = {"kaynak": getattr(parca, "kaynak", None)}
        if motor is None or sure_sn < EN_AZ_PARCA_SN:
            return None
        if d.get("cikis", "bilgisayar") == "bilgisayar" and self._susturulmus(parca.bas, parca.bitis):
            return None   # kendi çaldığımız dublaj: geri dinleme yok
        # 1) konuşma -> yazı (ekranda aynı cümlenin altyazısı varsa o tercih edilir)
        t = self.saat()
        stt_metin = (await self.stt.yaz(konusma, sr) or "").strip()
        olcum["stt_ms"] = int((self.saat() - t) * 1000)
        if not stt_metin:
            return None
        esle = self._eslesen_yazi(stt_metin, parca.bas, parca.bitis, calinanlar_dahil=True)
        if esle and esle[0] in self._erken_calinan:
            # bu satır altyazıyla önden çalındı; yine de karakterin sesi bir sonraki satırlar için örneklenir
            ref, ref_sr, ref_tur = self.referans_sec(konusma, sr)
            if esle[2] and ref_tur == "kendi":
                self._konusan_ref[esle[2]] = (ref, ref_sr, self._banka[-1].iz)
                if self.profil_kaydet is not None:
                    try:
                        self.profil_kaydet(esle[2], ref, ref_sr)
                    except Exception:   # noqa: BLE001
                        log.debug("ses profili kaydedilemedi", exc_info=True)
            return None
        kaynak_metin = esle[1] if esle else stt_metin
        yazi_id = esle[0] if esle else None
        # 2) ses örneği (temiz konuşmadan) + duygu
        ref, ref_sr, ref_tur = self.referans_sec(konusma, sr)
        if esle and esle[2] and ref_tur == "kendi":
            self._konusan_ref[esle[2]] = (ref, ref_sr, self._banka[-1].iz)
            if self.profil_kaydet is not None:      # yalnız kullanıcı "Ses profili"ne izin verdiyse (§14.5)
                try:
                    self.profil_kaydet(esle[2], ref, ref_sr)
                except Exception:   # noqa: BLE001
                    log.debug("ses profili kaydedilemedi", exc_info=True)
        r = float(np.sqrt(np.mean(np.square(konusma)))) if len(konusma) else 0.0
        if r > 1e-4:
            self._rms.append(r)
        duygu = None
        if getattr(motor, "duygu_destekli", False):
            from .isci.mantik import duygu as duygu_hesapla
            duygu = duygu_hesapla(konusma, sr, float(np.median(self._rms)) if self._rms else None)
        # 3) önden hazırlanmış çeviri/ses var mı (altyazı görünür görünmez başlamıştı)
        erken: _Erken | None = None
        if yazi_id and yazi_id in self._erken:
            try:
                erken = await asyncio.wait_for(asyncio.shield(self._erken[yazi_id]), 4.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                erken = None
        tr = erken.tr if erken and erken.tr else ""
        ses = None
        ses_sr = 0
        if erken and erken.ses is not None and erken.iz is not None:
            if dsp.benzerlik(dsp.parmak_izi(ref, ref_sr), erken.iz) >= BENZERLIK_ESIGI:
                ses, ses_sr = erken.ses, erken.sr          # aynı konuşmacının sesiyle hazırdı
        if erken:
            olcum.update(erken=True, ceviri_ms=0, onceden_ceviri_ms=erken.ceviri_ms)
        if not tr:
            t = self.saat()
            tr = await self._cevir(kaynak_metin, ayar, sure_sn)
            olcum["ceviri_ms"] = int((self.saat() - t) * 1000)
        if not tr:
            return None
        hedef_sn = max(1.0, sure_sn)
        sinir = float(d.get("hiz_siniri", 1.25))
        kisaltildi = False
        hiz = 1.0
        cikis_ad = d.get("cikis", "bilgisayar")
        cikis = self.cikis_getir(cikis_ad)
        akisli = (ses is None and getattr(motor, "akisli", False) and getattr(cikis, "akisli", False))
        # 4) altyazı HER ZAMAN sesten önce: ekranda eşleşen yoksa dublaj metnini altyazı olarak göster
        def altyazi() -> str:
            nonlocal yazi_id
            if yazi_id is None:
                self._sayac += 1
                yazi_id = f"d{self._sayac}"
                self.yonetici.satir_kaydet(yazi_id, kaynak_metin, tr, "motor")
                self.yayin.yayinla("yazi", {"id": yazi_id, "metin": tr, "asil": kaynak_metin, "tur": "konusma",
                                            "konusan": None, "sure_ms": sure_ms(tr)})
            self._yapilan_yazilar.add(yazi_id)
            if len(self._yapilan_yazilar) > 200:   # sınırsız büyümesin
                self._yapilan_yazilar &= {k for _, k, _, _ in self._yazilar}
            return yazi_id
        if akisli:
            # 5a) akışlı: ilk cümlecik hazır olur olmaz çalmaya başlar (süre tahminle sığdırılır)
            altyazi()
            bas = self.saat()
            self.oynuyor = True
            try:
                sonuc = await motor.seslendir_ve_cal(tr, ref, ref_sr, duygu, hedef_sn, ayar)
            finally:
                self.oynuyor = False
                if cikis_ad == "bilgisayar":
                    self._susturma.append((bas, self.saat()))
            olcum.update(ses_ms=sonuc.get("toplam_ms"), ilk_ses_ms=sonuc.get("ilk_ses_ms"),
                         bekleme_ms=int((bas - parca.bitis) * 1000) + int(sonuc.get("ilk_ses_ms") or 0))
            self.olcumler.append(olcum)
            self.son_sonuc = DublajSonucu(yazi_id or "", tr, float(sonuc.get("sure_sn") or 0),
                                          float(sonuc.get("hiz") or 1.0), False, ref_tur, olcum)
            return self.son_sonuc
        # 5b) bütün ses: üret (ya da önden hazır olanı kullan) ve süreye sığdır
        if ses is None:
            t = self.saat()
            ses, ses_sr = await self._seslendir(motor, tr, ref, ref_sr, duygu)
            olcum["ses_ms"] = int((self.saat() - t) * 1000)
        ses = dsp.mono_float(ses)
        oran = (len(ses) / ses_sr) / hedef_sn
        if oran > sinir and not erken:
            kisaltildi = True
            try:
                kisa = await self._cevir(kaynak_metin, ayar, sure_sn, onceki=tr)
            except (AgHatasi, AnahtarHatasi, MotorHatasi, ErisimSiniri):
                kisa = ""
            if kisa and len(kisa) < len(tr):
                ses2, ses_sr2 = await self._seslendir(motor, kisa, ref, ref_sr, duygu)
                tr, ses, ses_sr = kisa, dsp.mono_float(ses2), ses_sr2
                oran = (len(ses) / ses_sr) / hedef_sn
        if oran > HIZ_TOLERANS:
            hiz = min(oran, sinir)
            ses = dsp.hizlandir(ses, ses_sr, hiz)
        altyazi()
        # 6) çal
        bas = self.saat()
        olcum["bekleme_ms"] = int((bas - parca.bitis) * 1000)
        self.oynuyor = True
        try:
            await cikis.oynat(ses, ses_sr, ayar, yazi_id)
        finally:
            self.oynuyor = False
            if cikis_ad == "bilgisayar":
                self._susturma.append((bas, self.saat()))
        self.olcumler.append(olcum)
        self.son_sonuc = DublajSonucu(yazi_id or "", tr, len(ses) / ses_sr, hiz, kisaltildi, ref_tur, olcum)
        return self.son_sonuc

    # -- kuyruk / döngü --
    def kuyruga_at(self, parca: Any) -> None:
        """Ses iş parçacığından `loop.call_soon_threadsafe` ile çağrılır."""
        while self._kuyruk.qsize() >= EN_COK_BEKLEYEN:   # gecikme birikmesin: en eskisini at
            try:
                self._kuyruk.get_nowait()
            except asyncio.QueueEmpty:
                break
        self._kuyruk.put_nowait(parca)

    async def calis(self) -> None:
        while True:
            parca = await self._kuyruk.get()
            try:
                if isinstance(parca, tuple) and parca and parca[0] == "erken":
                    await self._erken_cal(parca[1])
                    continue
                await self.isle(parca)
                self.son_hata = None
            except asyncio.CancelledError:
                raise
            except (DublajHatasi, SesHatasi) as e:
                self.son_hata = e.kod
                log.warning("Dublaj hatası: %s %s", e.kod, getattr(e, "ayrinti", ""))
            except ErisimSiniri:
                self.son_hata = "dublaj_suresi_bitti"   # PROTOKOL 17.2: sakin bilgi, hata değil
            except (AgHatasi, AnahtarHatasi, MotorHatasi) as e:
                self.son_hata = {AgHatasi: "ag_hatasi", AnahtarHatasi: "anahtar_yok"}.get(type(e), "motor_hatasi")
            except Exception:
                self.son_hata = "sunucu_hatasi"
                log.exception("Dublaj parçası işlenemedi")
