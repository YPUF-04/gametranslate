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
BAYAT_SN = 8.0                # altyazı göründükten bu kadar sonra hâlâ seslendirilmemişse atlanır (geride kalınmasın)
TV_SIRA_SN = 8.0              # TV'de bu kadar saniyelik ses sırada bekliyorsa yeni satır seslendirilmez (yetişme)
TV_BAYAT_PAY_MS = 4000        # TV: sesin, önündeki sıranın bitişinden sonra en çok bu kadar gecikmesine izin
SESLI_ORAN_EN_AZ = 0.35       # klon örneği: konuşmalı çerçevelerin en az bu kadarı net perdeli olmalı (müzik/gürültü değil)
KONUSAN_REF_HEDEF_SN = 8.0    # bir karakterin örneği zamanla birikerek bu süreye tamamlanır (en çok 10 sn)
ANLIK_SN = 1.5                # altyazı görününce yakalanan son konuşma (cinsiyet/kimlik tahmini için)


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
    cins: str | None = None      # perdeden tahmin: "k" | "e" | None
    puan: float = 0.0            # sesli oran (temizlik)


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
        self._konusan_puan: dict[str, float] = {}
        self._tts_sira = asyncio.Lock()                    # önden seslendirme altyazı sırasıyla (FIFO)
        self._cal_kuyruk: asyncio.Queue = asyncio.Queue()  # önden hazır sesler: parça kuyruğundan ayrı, atılmaz
        self._tv_bitis = 0.0                               # TV'deki ses sırasının tahmini bitişi (saat)
        self.anlik_ses: Callable[[float], Any] | None = None   # işçiden son ~1,5 sn konuşma (varsa)
        self.cihaz_bilgisi: Callable[[], dict[str, Any] | None] = lambda: None
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

    def _yazi_ani(self, kimlik: str) -> float | None:
        for an, k, _, _ in reversed(self._yazilar):
            if k == kimlik:
                return an
        return None

    def _istenen_cinsiyet(self, konusan: str | None) -> str | None:
        f = getattr(self.yonetici, "konusan_cinsiyeti", None)
        try:
            return f(konusan) if callable(f) and konusan else None
        except Exception:   # noqa: BLE001
            return None

    async def _anlik_ornek(self) -> tuple[np.ndarray, int] | None:
        if self.anlik_ses is None:
            return None
        try:
            return await asyncio.wait_for(self.anlik_ses(ANLIK_SN), 0.5)
        except Exception:   # noqa: BLE001 — işçi meşgul/yok: tahminsiz devam
            return None

    async def _erken_referans(self, konusan: str | None) -> tuple[np.ndarray, int, Any, str, str | None, str | None]:
        """Önden seslendirmenin örneği: (pcm, sr, iz, tür, cinsiyet, yerleşik ses isteği).

        Sıra: 1) adı bilinen karakterin biriktirilmiş örneği; 2) şu an konuşanın sesi (işçiden son 1,5 sn)
        bankadaki bir örneğe benziyorsa o; 3) cinsiyeti (oyun bilgisinden ya da o anki perdeden) tutan son örnek;
        4) o cinsiyetin yerleşik yedek sesi; 5) cinsiyet bilinmiyorsa son duyulan örnek / motorun kendi sesi."""
        if konusan and konusan in self._konusan_ref:
            pcm, sr, iz = self._konusan_ref[konusan]
            return pcm, sr, iz, "konusan", self._istenen_cinsiyet(konusan), None
        cins = self._istenen_cinsiyet(konusan)
        anlik = await self._anlik_ornek()
        if anlik is not None and len(anlik[0]) >= int(0.6 * anlik[1]):
            from .isci.mantik import cinsiyet_tahmini
            a_pcm, a_sr = anlik
            tahmin, _ = await asyncio.to_thread(cinsiyet_tahmini, a_pcm, a_sr)
            cins = cins or tahmin
            iz = await asyncio.to_thread(dsp.parmak_izi, a_pcm, a_sr)
            en, secilen = BENZERLIK_ESIGI, None
            for k in list(self._banka):
                b = dsp.benzerlik(iz, k.iz)
                if b >= en and (cins is None or getattr(k, "cins", None) in (None, cins)):
                    en, secilen = b, k
            if secilen is not None:
                return secilen.pcm, secilen.sr, secilen.iz, "benzer", getattr(secilen, "cins", None) or cins, None
        for k in reversed(list(self._banka)):
            if cins is None or getattr(k, "cins", None) == cins:
                return k.pcm, k.sr, k.iz, "banka", getattr(k, "cins", None), None
        bos = np.zeros(0, dtype=np.float32)
        if cins in ("k", "e"):
            return bos, 24000, None, f"yerlesik_{cins}", cins, cins
        return bos, 24000, None, "notr", None, None

    def _olcum_ekle(self, o: dict[str, Any]) -> None:
        self.olcumler.append(o)

    async def _erken_hazirla(self, kimlik: str, asil: str, konusan: str | None,
                             hazir_tr: str | None = None) -> _Erken | None:
        olcum: dict[str, Any] = {"erken": True, "yazi_id": kimlik, "bekleme_ms": None}
        try:
            ayar = self.ayar()
            motor = self.motor_getir()
            t0 = self.saat()
            yazi_an = self._yazi_ani(kimlik) or t0
            tahmini = max(1.0, len(asil) / 15.0)            # İngilizce ~15 karakter/sn
            if hazir_tr and not self.yonetici_dublaj_izni():
                return None                                  # dublaj süresi yok (PROTOKOL 17.2)
            tr = hazir_tr or await self._cevir(asil, ayar, tahmini)
            e = _Erken(kimlik, asil, tr, ceviri_ms=int((self.saat() - t0) * 1000))
            olcum["ceviri_ms"] = e.ceviri_ms
            cal = self._erken_cal_mi(ayar)
            if not tr or motor is None:
                return e
            pcm, rsr, iz, tur, cins, varsayilan = await self._erken_referans(konusan)
            if len(pcm) == 0 and not (getattr(motor, "varsayilan_ses", False) and cal):
                return e                                     # örnek yok ve önden çalınmayacak: parça beklenir
            olcum.update(ref_tur=tur, ref_sn=round(len(pcm) / max(1, rsr), 1), cinsiyet=cins)
            async with self._tts_sira:                      # satırlar altyazı sırasıyla seslendirilir
                gecikmis = self.saat() - yazi_an
                kuyruk = max(0.0, self._tv_bitis - self.saat())
                if cal and (gecikmis > BAYAT_SN or kuyruk > TV_SIRA_SN):
                    olcum["atildi"] = "gecikme" if gecikmis > BAYAT_SN else "tv_sirasi"
                    log.info("Dublaj satırı atlandı (%s): altyazıdan %.1f sn sonra, TV sırası %.1f sn",
                             olcum["atildi"], gecikmis, kuyruk)
                    self._erken_calinan.add(kimlik)          # parça gelince de çalınmasın (eskidi)
                    self._olcum_ekle(olcum)
                    return e
                parcalar = self._parcala(tr) if cal else [tr]
                t1 = self.saat()
                sesler = []
                for i, p in enumerate(parcalar):
                    ses, sr = await self._seslendir(motor, p, pcm, rsr, None, varsayilan)
                    ses = dsp.mono_float(ses)
                    sesler.append(ses)
                    if i == 0:
                        olcum["ilk_ses_ms"] = int((self.saat() - yazi_an) * 1000)   # altyazı → ilk Türkçe ses hazır
                        self._uretim_bilgisi(motor, olcum)
                    if cal:
                        if i == 0:
                            self._erken_calinan.add(kimlik)
                        self._cal_kuyruk.put_nowait(("erken", _Erken(kimlik, asil, p, ses, sr, iz),
                                                     olcum if i == len(parcalar) - 1 else None))
                e.ses = np.concatenate(sesler) if sesler else None
                e.sr, e.iz, e.ses_ms = sr, (iz if iz is not None else np.zeros(13)), int((self.saat() - t1) * 1000)
                olcum["ses_ms"] = e.ses_ms
            if not cal:
                self._olcum_ekle(olcum)
            return e
        except asyncio.CancelledError:
            if "ilk_ses_ms" not in olcum and olcum.get("ref_tur"):
                olcum["atildi"] = "iptal"
                self._olcum_ekle(olcum)
            raise
        except Exception as ex:   # noqa: BLE001 — önden hazırlık başarısızsa normal yol çalışır
            log.info("önden hazırlık başarısız: %s: %s", type(ex).__name__, ex)
            olcum["atildi"] = "hata"
            self._olcum_ekle(olcum)
            return None

    @staticmethod
    def _parcala(tr: str) -> list[str]:
        """Akışlı: ilk cümlecik kısa (ilk ses erken çıksın), sonrakiler arkasından (TV sırayla çalar)."""
        from .isci.mantik import cumlecik_bol
        return cumlecik_bol(tr) or [tr]

    @staticmethod
    def _uretim_bilgisi(motor: Any, olcum: dict[str, Any]) -> None:
        m = getattr(motor, "son_uretim", None)
        if isinstance(m, dict):
            for k in ("cihaz", "uretim_ms", "kosul"):
                if m.get(k) is not None:
                    olcum[k] = m[k]

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
                         duygu: dict[str, float] | None, varsayilan: str | None = None) -> tuple[Any, int]:
        ek: dict[str, Any] = {}
        if varsayilan and getattr(motor, "yerlesik_ses", False):
            ek["varsayilan"] = varsayilan          # örnek yok: istenen cinsiyetin yerleşik sesi
        if getattr(motor, "duygu_destekli", False):
            return await motor.seslendir(metin, ref, sr, duygu=duygu, **ek)
        return await motor.seslendir(metin, ref, sr, **ek)

    async def _erken_cal(self, e: _Erken, olcum: dict[str, Any] | None = None) -> None:
        ayar = self.ayar()
        d = ayar.get("dublaj") or {}
        cikis = self.cikis_getir(d.get("cikis", "bilgisayar"))
        self._yapilan_yazilar.add(e.yazi_id)
        bas = self.saat()
        sure = len(e.ses) / e.sr if e.sr else 0.0
        self.oynuyor = True
        try:
            if getattr(cikis, "ad", "") == "tv":
                # TV sırası: bu ses, önündekiler bitince çalar; TV o kadar (+pay) beklemiş sesi atmasın
                kuyruk = max(0.0, self._tv_bitis - bas)
                self._tv_bitis = bas + kuyruk + sure
                await cikis.oynat(e.ses, e.sr, ayar, e.yazi_id, bayat_ms=int(kuyruk * 1000) + TV_BAYAT_PAY_MS)
            else:
                await cikis.oynat(e.ses, e.sr, ayar, e.yazi_id)
        finally:
            self.oynuyor = False
            self._susturma.append((bas, self.saat()))
        if olcum is not None:
            self._olcum_ekle(olcum)

    async def _cal_dongusu(self) -> None:
        while True:
            _, e, olcum = await self._cal_kuyruk.get()
            try:
                await self._erken_cal(e, olcum)
            except asyncio.CancelledError:
                raise
            except (DublajHatasi, SesHatasi) as ex:
                self.son_hata = ex.kod
            except Exception:   # noqa: BLE001
                log.exception("Önden hazır dublaj çalınamadı")

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

    def _pencere_yazisi(self, bas: float, bitis: float) -> tuple[str, str, str | None] | None:
        """Konuşma parçası sürerken (ya da hemen öncesinde) ekrana gelmiş, önden seslendirilen altyazı."""
        en, sonuc = None, None
        for an, kimlik, asil, konusan in self._yazilar:
            if kimlik in self._erken_calinan and bas - YAZI_ESLEME_SN <= an <= bitis + 0.5:
                fark = abs(an - bas)
                if en is None or fark < en:
                    en, sonuc = fark, (kimlik, asil, konusan)
        return sonuc

    # -- konuşmacı örneği --
    def referans_sec(self, pcm: np.ndarray, sr: int) -> tuple[np.ndarray, int, str]:
        """3-10 sn kendi sesi; kısaysa en benzer yakın konuşmacı örneği (ucuz parmak izi)."""
        kes = dsp.sessizlik_kirp(pcm, sr)
        sure = len(kes) / sr
        if sure >= REFERANS_EN_AZ_SN:
            from .isci.mantik import cinsiyet_tahmini, sesli_oran
            kes = dsp.en_iyi_pencere(kes, sr, REFERANS_EN_COK_SN)
            puan = sesli_oran(kes, sr)
            if puan >= SESLI_ORAN_EN_AZ:     # müzik/efekt ağırlıklı parça bankaya girmez (robotik klon olmasın)
                self._banka.append(_Klip(kes, sr, dsp.parmak_izi(kes, sr), cinsiyet_tahmini(kes, sr)[0], puan))
                return kes, sr, "kendi"
            return kes, sr, "kendi_zayif"
        if len(kes) == 0:
            kes = pcm
        iz = dsp.parmak_izi(kes, sr)
        en, secilen = BENZERLIK_ESIGI, None
        for k in list(self._banka):
            b = dsp.benzerlik(iz, k.iz)
            if b >= en:
                en, secilen = b, k
        if secilen is not None:
            return secilen.pcm, secilen.sr, "benzer"
        return kes, sr, "kisa_kendi"

    def _konusan_biriktir(self, ad: str, ref: np.ndarray, sr: int) -> None:
        """Adı bilinen karakterin örneği zamanla birikir: 8 sn'ye dek yeni temiz parçalar eklenir (araya 0,15 sn
        sessizlik), sonra yalnız daha temiz (sesli oranı yüksek) bir parça eskisinin yerini alır. En çok 10 sn."""
        puan = self._banka[-1].puan if self._banka else 0.0
        eski = self._konusan_ref.get(ad)
        if eski is not None and eski[1] == sr and len(eski[0]) / sr < KONUSAN_REF_HEDEF_SN:
            yeni = np.concatenate([eski[0], np.zeros(int(0.15 * sr), np.float32), ref])[:int(REFERANS_EN_COK_SN * sr)]
            puan = min(puan, self._konusan_puan.get(ad, puan))
        elif eski is not None and puan <= self._konusan_puan.get(ad, 0.0):
            return
        else:
            yeni = ref
        self._konusan_ref[ad] = (yeni, sr, dsp.parmak_izi(yeni, sr))
        self._konusan_puan[ad] = puan
        if self.profil_kaydet is not None:      # yalnız kullanıcı "Ses profili"ne izin verdiyse (§14.5)
            try:
                self.profil_kaydet(ad, yeni, sr)
            except Exception:   # noqa: BLE001
                log.debug("ses profili kaydedilemedi", exc_info=True)

    def temizle(self) -> None:
        """Oturum bitti: konuşmacı örnekleri ve ekran altyazısı hafızası silinir."""
        self._banka.clear()
        self._konusan_ref.clear()
        self._konusan_puan.clear()
        self._tv_bitis = 0.0
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
        # 0) altyazıyla önden çalınan kipte (TV / İngilizce çıkarılmış): bu konuşmanın altyazısı zaten seslendirildi
        #    ya da seslendiriliyor. Yazıya çevirme (Whisper) HİÇ çalıştırılmaz (işçide seslendirmenin önünü
        #    tıkamasın); parça yalnız karakterin ses örneği olarak kullanılır.
        if self._erken_cal_mi(ayar) and d.get("erken_seslendir", True):
            yakin = self._pencere_yazisi(parca.bas, parca.bitis)
            if yakin is not None:
                ref, ref_sr, ref_tur = await asyncio.to_thread(self.referans_sec, konusma, sr)
                if yakin[2] and ref_tur == "kendi":
                    self._konusan_biriktir(yakin[2], ref, ref_sr)
                return None
        # 1) konuşma -> yazı (ekranda aynı cümlenin altyazısı varsa o tercih edilir)
        t = self.saat()
        stt_metin = (await self.stt.yaz(konusma, sr) or "").strip()
        olcum["stt_ms"] = int((self.saat() - t) * 1000)
        if not stt_metin:
            return None
        esle = self._eslesen_yazi(stt_metin, parca.bas, parca.bitis, calinanlar_dahil=True)
        if esle and esle[0] in self._erken_calinan:
            # bu satır altyazıyla önden çalındı; yine de karakterin sesi bir sonraki satırlar için örneklenir
            ref, ref_sr, ref_tur = await asyncio.to_thread(self.referans_sec, konusma, sr)
            if esle[2] and ref_tur == "kendi":
                self._konusan_biriktir(esle[2], ref, ref_sr)
            return None
        kaynak_metin = esle[1] if esle else stt_metin
        yazi_id = esle[0] if esle else None
        # 2) ses örneği (temiz konuşmadan) + duygu
        ref, ref_sr, ref_tur = await asyncio.to_thread(self.referans_sec, konusma, sr)
        if esle and esle[2] and ref_tur == "kendi":
            self._konusan_biriktir(esle[2], ref, ref_sr)
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
        calici = asyncio.get_running_loop().create_task(self._cal_dongusu())
        try:
            await self._parca_dongusu()
        finally:
            calici.cancel()

    async def _parca_dongusu(self) -> None:
        while True:
            parca = await self._kuyruk.get()
            try:
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
