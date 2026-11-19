# SPDX-License-Identifier: AGPL-3.0-only
"""Dublajın yaşam döngüsü: motor seçimi/hazırlığı, ses dinleme, boru hattı, deneme (PROTOKOL 9.4)."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Callable

from .. import ses as ses_mod
from . import MOTORLAR, donanim, motor_olustur
from .cikis import BilgisayarCikis, SesDeposu, TvCikis
from .temel import DublajHatasi

if TYPE_CHECKING:
    from .isleyici import Isleyici

log = logging.getLogger("kopru.dublaj")



class DublajYonetici:
    def __init__(self, ayar_getir: Callable[[], dict[str, Any]], yayin: Any, yonetici_getir: Callable[[], Any],
                 motor_fabrika: Callable[[str, dict[str, Any]], Any] = motor_olustur,
                 stt_fabrika: Callable[[dict[str, Any]], Any] | None = None,
                 kaynak_fabrika: Callable[..., Any] | None = None,
                 bilgisayar_cikis: Any = None, saat: Callable[[], float] = time.monotonic,
                 donanim_fn: Callable[[], donanim.Donanim] = donanim.algila) -> None:
        self.ayar = ayar_getir
        self.yayin = yayin
        self.yonetici_getir = yonetici_getir
        self.motor_fabrika = motor_fabrika
        self.stt_fabrika = stt_fabrika or (lambda a: ses_mod.WhisperSTT("small", a.get("hedef_dil") or "tr"))
        self.kaynak_fabrika = kaynak_fabrika or ses_mod.SesKaynagi
        self.saat = saat
        self.donanim_fn = donanim_fn
        self.depo = SesDeposu(saat=saat)
        self._bilgisayar = bilgisayar_cikis or BilgisayarCikis()
        self._tv = TvCikis(self.depo, yayin)
        self._motor: Any = None
        self._motor_imza: tuple = ()
        self.indirme: dict[str, Any] = {"durum": "bosta", "yuzde": 0, "hata": None}
        self.isleyici: "Isleyici | None" = None
        self._kaynak: Any = None
        self._gorev: asyncio.Task | None = None
        self._kapat_gorevleri: set[asyncio.Task] = set()   # unutulmuş görev çöp toplanmasın
        self._hazirla_gorevi: asyncio.Task | None = None
        self._donanim: donanim.Donanim | None = None
        self._calisiyor = False       # çeviri (Başlat) çalışıyor mu
        self.son_hata: str | None = None

    # -- yardımcılar --
    def _d(self) -> dict[str, Any]:
        return self.ayar().get("dublaj") or {}

    def motor_kodu(self) -> str:
        return self._d().get("motor", "kapali")

    def motor(self) -> Any | None:
        """Seçili motor nesnesi (ayar değişince yeniden kurulur); kapalıysa None."""
        kod = self.motor_kodu()
        if kod == "kapali" or kod not in MOTORLAR:
            return None
        d = self._d()
        imza = (kod, d.get("elevenlabs_ses_kimligi"), d.get("elevenlabs_model"),
                d.get("elevenlabs_onay"), d.get("elevenlabs_klon_onay"))
        if self._motor is None or imza != self._motor_imza:
            self._motor_birak()
            self._motor = self.motor_fabrika(kod, self.ayar())
            self._motor_imza = imza
            self.indirme = {"durum": "bosta", "yuzde": 0, "hata": None}
        return self._motor

    def _motor_birak(self) -> None:
        m, self._motor = self._motor, None
        if m is not None and hasattr(m, "kapat"):
            self._kapat_baslat(m)   # ElevenLabs geçici klonlarını sil

    def _kapat_baslat(self, motor: Any) -> None:
        async def kapat() -> None:
            try:
                await motor.kapat()
            except Exception:   # noqa: BLE001 — temizlik hatası önemsiz
                log.debug("Dublaj motoru kapatılamadı", exc_info=True)
        try:
            t = asyncio.get_running_loop().create_task(kapat())
        except RuntimeError:
            return
        self._kapat_gorevleri.add(t)
        t.add_done_callback(self._kapat_gorevleri.discard)

    def donanim(self) -> donanim.Donanim:
        if self._donanim is None:
            self._donanim = self.donanim_fn()
        return self._donanim

    async def bilgi(self) -> dict[str, Any]:
        if self._donanim is None:
            self._donanim = await asyncio.to_thread(self.donanim_fn)
        dn = self._donanim
        m = self.motor()
        return {"motor": self.motor_kodu(), "hazir": bool(m and m.hazir()), "onerilen": donanim.onerilen(dn),
                "ekran_karti": dn.ekran_karti, "vram_gb": dn.vram_gb, "ram_gb": dn.ram_gb,
                "indirme": dict(self.indirme), "calisiyor": self._gorev is not None and not self._gorev.done(),
                "son_hata": self.son_hata or (self.isleyici.son_hata if self.isleyici else None)}

    # -- model hazırlama (indirme) --
    def _ilerleme(self, yuzde: float, durum: str) -> None:
        self.indirme.update(durum=durum, yuzde=round(yuzde), hata=None)

    async def _hazirla(self) -> None:
        m = self.motor()
        if m is None:
            return
        self.indirme = {"durum": "indiriliyor", "yuzde": 0, "hata": None}
        try:
            await m.hazirla(self._ilerleme)
            self.indirme = {"durum": "bitti", "yuzde": 100, "hata": None}
            self.son_hata = None
        except DublajHatasi as e:
            self.indirme = {"durum": "hata", "yuzde": self.indirme.get("yuzde", 0), "hata": e.kod, "ayrinti": e.ayrinti}
            self.son_hata = e.kod
            log.warning("Dublaj hazırlığı başarısız: %s %s", e.kod, e.ayrinti)
        except Exception as e:
            self.indirme = {"durum": "hata", "yuzde": 0, "hata": "dublaj_yukleme_hata", "ayrinti": type(e).__name__}
            self.son_hata = "dublaj_yukleme_hata"
        self.senkronla()

    def hazirla_baslat(self) -> None:
        """Arka planda modeli indirir/yükler; ilerleme `bilgi()["indirme"]`dadır."""
        if self._hazirla_gorevi and not self._hazirla_gorevi.done():
            return
        self._hazirla_gorevi = asyncio.get_running_loop().create_task(self._hazirla())

    # -- çalıştırma --
    def senkronla(self, calisiyor: bool | None = None) -> None:
        """Çeviri çalışıyor + dublaj açık + motor hazır ise boru hattını başlatır, değilse durdurur."""
        if calisiyor is not None:
            self._calisiyor = calisiyor
        istenen = self._calisiyor and self.motor_kodu() != "kapali"
        calisan = self._gorev is not None and not self._gorev.done()
        if istenen and not calisan:
            self._gorev = asyncio.get_running_loop().create_task(self._yurut())
        elif not istenen and calisan:
            self.durdur()

    def _hata(self, kod: str) -> None:
        self.son_hata = kod

    async def _yurut(self) -> None:
        """Boru hattını çalıştırır; beklenmeyen hata görevi sessizce öldürmez, `son_hata` olur."""
        try:
            await self._yurut_ic()
        except asyncio.CancelledError:
            raise
        except ses_mod.SesHatasi as e:
            self._hata(e.kod)
        except Exception:
            log.exception("Dublaj boru hattı çöktü")
            self._hata("sunucu_hatasi")

    async def _yurut_ic(self) -> None:
        loop = asyncio.get_running_loop()
        m = self.motor()
        if m is None:
            return
        if not m.hazir():
            self._hata("dublaj_hazir_degil")
            return
        try:
            await m.hazirla(None)     # önbellekteki modeli belleğe yükler (indirme gerekmez)
        except DublajHatasi as e:
            self._hata(e.kod)
            return
        self.son_hata = None
        try:
            from .isleyici import Isleyici    # tembel: numpy gerektirir
        except ImportError:
            self._hata("dublaj_paket_yok")
            return
        stt = self.stt_fabrika(self.ayar())
        isleyici = Isleyici(stt, self.yonetici_getir(), self.motor, self.cikis, self.yayin, self.ayar, self.saat)
        self.isleyici = isleyici
        self.yayin.dinle(isleyici.olay)
        kaynak = self.kaynak_fabrika(lambda p: loop.call_soon_threadsafe(isleyici.kuyruga_at, p), self.saat,
                                     hata_cb=lambda e: loop.call_soon_threadsafe(self._hata, e.kod))
        self._kaynak = kaynak
        try:
            kaynak.baslat(True)
        except ses_mod.SesHatasi as e:
            self._hata(e.kod)
            self.yayin.dinlemeyi_birak(isleyici.olay)
            return
        try:
            await isleyici.calis()
        finally:
            kaynak.durdur()
            self.yayin.dinlemeyi_birak(isleyici.olay)
            isleyici.temizle()

    def cikis(self, ad: str) -> Any:
        return self._tv if ad == "tv" else self._bilgisayar

    def durdur(self) -> None:
        self._calisiyor = False
        if self._kaynak is not None:
            self._kaynak.durdur()
            self._kaynak = None
        if self._gorev is not None:
            self._gorev.cancel()
            self._gorev = None
        for c in (self._bilgisayar, self._tv):
            try:
                c.durdur()
            except Exception:
                pass
        self.depo.bosalt()
        if self._motor is not None and hasattr(self._motor, "kapat"):
            self._kapat_baslat(self._motor)

    # -- "Dene" --
    async def dene(self, metin: str) -> dict[str, Any]:
        m = self.motor()
        if m is None:
            raise DublajHatasi("dublaj_hazir_degil", "kapali")
        if not m.hazir():
            raise DublajHatasi("dublaj_hazir_degil", m.kod)
        await m.hazirla(None)
        try:
            from . import dsp                  # tembel: numpy gerektirir
        except ImportError as e:
            raise DublajHatasi("dublaj_paket_yok", "numpy") from e
        banka = self.isleyici._banka if self.isleyici else None
        if banka:
            klip = banka[-1]
            ref, sr = klip.pcm, klip.sr      # oturumda yakalanmış son karakter sesi (yalnız RAM)
        else:
            sr = 24000
            ref = dsp.sentetik_referans(sr)  # yakalanmış ses yoksa küçük sentetik ses
        t0 = self.saat()
        pcm, psr = await m.seslendir(metin, ref, sr)
        pcm = dsp.mono_float(pcm)
        ayar = self.ayar()
        cikis = ayar["dublaj"].get("cikis", "bilgisayar")
        await self.cikis(cikis).oynat(pcm, psr, ayar, None)
        return {"tamam": True, "sure_ms": int(len(pcm) / psr * 1000), "uretim_ms": int((self.saat() - t0) * 1000),
                "cikis": cikis}
