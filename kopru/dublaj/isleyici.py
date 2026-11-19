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


@dataclass
class _Klip:
    pcm: np.ndarray
    sr: int
    iz: np.ndarray


@dataclass
class DublajSonucu:
    yazi_id: str
    metin: str
    sure_sn: float
    hiz: float                 # uygulanan hızlandırma (1.0 = yok)
    kisaltildi: bool           # ikinci (daha kısa) çeviri istendi mi
    referans: str              # "kendi" | "benzer" | "kisa_kendi"


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

    # -- ekran altyazısı bilgisi (Yayin dinleyicisi) --
    def olay(self, olay: str, veri: dict[str, Any]) -> None:
        """Yayın dinleyicisi: ekrana gelen altyazıları eşleme için hatırlar."""
        if olay == "yazi" and veri.get("asil") and not str(veri.get("id", "")).startswith("d"):
            self._yazilar.append((self.saat(), str(veri.get("id", "")), str(veri["asil"]), veri.get("konusan")))

    def _eslesen_yazi(self, metin: str, bas: float, bitis: float) -> tuple[str, str, str | None] | None:
        """±3 sn içinde ekrana gelmiş, benzer içerikli altyazı (varsa en benzeri)."""
        n = normallestir(metin)
        en, sonuc = YAZI_BENZERLIK, None
        for an, kimlik, asil, konusan in self._yazilar:
            if kimlik in self._yapilan_yazilar or not (bas - YAZI_ESLEME_SN <= an <= bitis + YAZI_ESLEME_SN):
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
        sure_sn = len(pcm) / sr
        if motor is None or sure_sn < EN_AZ_PARCA_SN:
            return None
        if d.get("cikis", "bilgisayar") == "bilgisayar" and self._susturulmus(parca.bas, parca.bitis):
            return None   # kendi çaldığımız dublaj: geri dinleme yok
        # 1) konuşma -> yazı (ekranda aynı cümlenin altyazısı varsa o tercih edilir)
        stt_metin = (await self.stt.yaz(pcm, sr) or "").strip()
        if not stt_metin:
            return None
        esle = self._eslesen_yazi(stt_metin, parca.bas, parca.bitis)
        kaynak_metin = esle[1] if esle else stt_metin
        yazi_id = esle[0] if esle else None
        # 2) çeviri (söylenebilir, süreye sığan kısa Türkçe)
        tr = await self._cevir(kaynak_metin, ayar, sure_sn)
        if not tr:
            return None
        # 3) ses örneği + seslendirme
        ref, ref_sr, ref_tur = self.referans_sec(pcm, sr)
        ses, ses_sr = await motor.seslendir(tr, ref, ref_sr)
        ses = dsp.mono_float(ses)
        # 4) süreye sığdır: <= hiz_siniri kadar hızlandır; yetmezse BİR kez daha kısa çeviri iste
        hedef_sn = max(1.0, sure_sn)
        sinir = float(d.get("hiz_siniri", 1.25))
        kisaltildi = False
        oran = (len(ses) / ses_sr) / hedef_sn
        if oran > sinir and not kisaltildi:
            kisaltildi = True
            try:
                kisa = await self._cevir(kaynak_metin, ayar, sure_sn, onceki=tr)
            except (AgHatasi, AnahtarHatasi, MotorHatasi, ErisimSiniri):
                kisa = ""
            if kisa and len(kisa) < len(tr):
                ses2, ses_sr2 = await motor.seslendir(kisa, ref, ref_sr)
                tr, ses, ses_sr = kisa, dsp.mono_float(ses2), ses_sr2
                oran = (len(ses) / ses_sr) / hedef_sn
        hiz = 1.0
        if oran > HIZ_TOLERANS:
            hiz = min(oran, sinir)
            ses = dsp.hizlandir(ses, ses_sr, hiz)
        # 5) altyazı HER ZAMAN sesten önce: ekranda eşleşen yoksa dublaj metnini altyazı olarak göster
        if yazi_id is None:
            self._sayac += 1
            yazi_id = f"d{self._sayac}"
            self.yonetici.satir_kaydet(yazi_id, kaynak_metin, tr, "motor")
            self.yayin.yayinla("yazi", {"id": yazi_id, "metin": tr, "asil": kaynak_metin, "tur": "konusma",
                                        "konusan": None, "sure_ms": sure_ms(tr)})
        self._yapilan_yazilar.add(yazi_id)
        # 6) çal
        cikis = self.cikis_getir(d.get("cikis", "bilgisayar"))
        bas = self.saat()
        self.oynuyor = True
        try:
            await cikis.oynat(ses, ses_sr, ayar, yazi_id)
        finally:
            self.oynuyor = False
            if d.get("cikis", "bilgisayar") == "bilgisayar":
                self._susturma.append((bas, self.saat()))
        self.son_sonuc = DublajSonucu(yazi_id, tr, len(ses) / ses_sr, hiz, kisaltildi, ref_tur)
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
                await self.isle(parca)
                self.son_hata = None
            except asyncio.CancelledError:
                raise
            except DublajHatasi as e:
                self.son_hata = e.kod
                log.warning("Dublaj hatası: %s %s", e.kod, e.ayrinti)
            except ErisimSiniri:
                self.son_hata = "ucretsiz_bitti"
            except (AgHatasi, AnahtarHatasi, MotorHatasi) as e:
                self.son_hata = {AgHatasi: "ag_hatasi", AnahtarHatasi: "anahtar_yok"}.get(type(e), "motor_hatasi")
            except Exception:
                self.son_hata = "sunucu_hatasi"
                log.exception("Dublaj parçası işlenemedi")
