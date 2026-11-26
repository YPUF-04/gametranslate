# SPDX-License-Identifier: AGPL-3.0-only
"""Dublajın yaşam döngüsü: motor seçimi/hazırlığı, ses dinleme, boru hattı, deneme (PROTOKOL 9.4)."""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any, Callable

from .. import ses as ses_mod
from . import MOTORLAR, donanim, motor_olustur, tamamen_turkce_mu
from .cikis import BilgisayarCikis, SesDeposu, TvCikis, _pencere_islemi
from .isci_istemci import (IsciCikis, IsciIstemci, IsciKodlayici, IsciMotoru, IsciSesKaynagi, IsciSTT, anlik_ses,
                           isci_komutu, kod_kopyala, tanima_yukle)
from .ortam import DublajOrtami
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
                 donanim_fn: Callable[[], donanim.Donanim] = donanim.algila,
                 ortam: DublajOrtami | None = None, isci: IsciIstemci | None = None) -> None:
        self.ayar = ayar_getir
        self.yayin = yayin
        self.yonetici_getir = yonetici_getir
        # Dublaj paketi (PROTOKOL 14.1) ve işçi süreci (14.2). Testler kendi sahtelerini verir.
        self.ortam = ortam or DublajOrtami()
        self.isci = isci or IsciIstemci(self._isci_komutu)
        self.ortam.model_indirici = self._modelleri_indir
        self.ortam.isci_denetci = self._isci_denetle
        self._fabrika_verildi = motor_fabrika is not motor_olustur
        self.motor_fabrika = motor_fabrika if self._fabrika_verildi else self._varsayilan_motor
        self._stt_verildi = stt_fabrika is not None
        self.stt_fabrika = stt_fabrika or self._varsayilan_stt
        self._kaynak_verildi = kaynak_fabrika is not None
        self.kaynak_fabrika = kaynak_fabrika or self._varsayilan_kaynak
        self.saat = saat
        self.donanim_fn = donanim_fn
        self.depo = SesDeposu(saat=saat)
        self._bilgisayar_verildi = bilgisayar_cikis is not None
        self._bilgisayar = bilgisayar_cikis or BilgisayarCikis()
        self._isci_cikis = IsciCikis(self.isci, self._oyun_pid)
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
        # PROTOKOL 17.2: dublaj yalnız süre (ya da sınırsız kod) varken çalışır; Durum erişime bağlar
        self.izin: Callable[[], bool] = lambda: True
        self._hafiza_depo: Any = None               # (oyun, DublajHafizasi) — yalnız izinle açılır (PROTOKOL 21)
        self.hafiza_kok: Callable[[str], Path] | None = None   # testler: kök klasör
        self.iyilestirici: Any = None

    # -- dublaj paketi / işçi --
    def isci_kullan(self) -> bool:
        """Ağır işler işçide mi yapılsın: dublaj paketi kuruluysa evet."""
        return self.ortam.kurulu()

    def _isci_komutu(self) -> Any:
        o = self.ortam
        if o.gelistirici:
            kok = Path(__file__).resolve().parent.parent.parent      # depo kökü: kopru/ burada
        else:
            kok = kod_kopyala(o.kok / "kod")
        return isci_komutu(o.python_yolu(), kok, o.model_dizini(), o.ffmpeg_yolu(), o.kok / "isci.log")

    def hafif(self) -> bool:
        from .isci.mantik import hafif_mi
        return hafif_mi(self._d().get("hafif_mod", "kapali"), self._donanim.vram_gb if self._donanim else None)

    def _yukle_ayari(self) -> dict[str, Any]:
        h = self.hafif()
        return {"stt": "small" if h else "large-v3-turbo", "hafif": h,
                "ayirma": bool(self._d().get("ayirma", True)) or tamamen_turkce_mu(self.ayar())}

    async def _modelleri_indir(self, cb: Callable[[float, str], None] | None) -> None:
        await self.isci.iste("modeller", {"liste": ["tts", "stt", "ayirma"],
                                          "stt": self._yukle_ayari()["stt"]}, ilerleme=cb)

    async def _modeller_hazir_mi(self, cb: Callable[[float, str], None] | None) -> None:
        """Model aşaması bitmemişse (ör. geliştirici kipi) önce indirir."""
        if self.ortam.bilgi_.asamalar["modeller"].durum != "bitti":
            await self._modelleri_indir(cb)
            self.ortam.bilgi_.asamalar["modeller"].durum = "bitti"
            self.ortam._durum_yaz()

    async def _isci_denetle(self) -> dict[str, Any]:
        b = await self.isci.baslat()
        if b.get("durum") == "cpu_torch_cpu" and not self.ortam.gelistirici:
            # NVIDIA kart var ama pakete CUDA'sız torch kurulmuş (kurulumda kart algılanamadı): bir kez onar
            log.warning("Dublaj paketi CUDA'sız torch ile kurulmuş (%s); CUDA yapısı kuruluyor", b.get("ekran_karti"))
            if await self.ortam.torch_onar():
                await self.isci.kapat()
                b = await self.isci.baslat()
        return {**b, "anahtar_dogru": True}

    async def onar(self) -> dict[str, Any]:
        """Panel "Onar": torch'u CUDA yapısıyla yeniden kurar, işçiyi yeniden başlatır (§14.1)."""
        if self._gorev is not None and not self._gorev.done():
            raise DublajHatasi("dublaj_onar_calisirken")
        if self._motor is not None and hasattr(self._motor, "kapat"):
            await self._motor.kapat()
        await self.isci.kapat()
        tamam = await self.ortam.torch_onar()
        b = await self.isci.baslat() if tamam else (self.isci.bilgi or {})
        return {"tamam": tamam, "tani": self.tani(), "onarim": dict(self.ortam.onarim), "cihaz": b.get("cihaz")}

    def onar_baslat(self) -> None:
        """Onarımı arka planda başlatır (torch CUDA ~2,6 GB iner); durum `tani()["onarim"]`da."""
        if self._gorev is not None and not self._gorev.done():
            raise DublajHatasi("dublaj_onar_calisirken")
        if getattr(self, "_onar_gorevi", None) is not None and not self._onar_gorevi.done():
            return

        async def calis() -> None:
            try:
                await self.onar()
            except Exception:   # noqa: BLE001
                log.exception("Dublaj onarımı başarısız")
                self.ortam.onarim = {"durum": "hata", "mesaj": "beklenmeyen hata"}
        self.ortam.onarim = {"durum": "suruyor", "mesaj": None}
        self._onar_gorevi = asyncio.get_running_loop().create_task(calis())

    def tani(self) -> dict[str, Any]:
        """"Dublaj tanı" (§14.6): hangi cihazda çalışıyor + son 5 satırın gecikmesi, örneği, cinsiyeti, atılıp atılmadığı."""
        b = dict(self.isci.bilgi or {}) if self.isci_kullan() else {}
        cihaz = {k: b.get(k) for k in ("cihaz", "durum", "ekran_karti", "vram_gb", "torch", "torch_cuda", "cuda_hata",
                                         "bf16") if b.get(k) is not None} or None
        uyari = None
        if b.get("durum") in ("cpu_torch_cpu", "cpu_surucu"):
            uyari = b["durum"]
        elif b and b.get("cihaz") == "cpu" and self.motor_kodu() == "chatterbox":
            uyari = "cpu"
        m = self._motor
        satirlar = []
        for o in list(self.isleyici.olcumler if self.isleyici else [])[-5:]:
            satirlar.append({k: o.get(k) for k in ("yazi_id", "ilk_ses_ms", "bekleme_ms", "ceviri_ms", "ses_ms",
                                                   "uretim_ms", "ref_sn", "ref_tur", "cinsiyet", "atildi", "erken", "hafiza")
                             if o.get(k) is not None})
        return {"cihaz": cihaz, "uyari": uyari, "onarilabilir": uyari == "cpu_torch_cpu" and not self.ortam.gelistirici,
                "isinma_ms": getattr(m, "isinma_ms", None), "satirlar": satirlar, "onarim": dict(self.ortam.onarim)}

    def _oyun_pid(self) -> int | None:
        return _pencere_islemi(str(self.ayar().get("kaynak") or ""))

    def _varsayilan_motor(self, kod: str, ayar: dict[str, Any]) -> Any:
        if kod in ("chatterbox", "pocket") and self.isci_kullan():
            return IsciMotoru(kod, self.isci, self.ortam.kurulu, self._yukle_ayari, self._modeller_hazir_mi,
                              self._oyun_pid)
        return motor_olustur(kod, ayar)

    def _varsayilan_stt(self, ayar: dict[str, Any]) -> Any:
        if self.isci_kullan():
            return IsciSTT(self.isci, ayar.get("hedef_dil") or "tr")
        return ses_mod.WhisperSTT("small", ayar.get("hedef_dil") or "tr")

    def _varsayilan_kaynak(self, parca_cb: Any, saat: Any, hata_cb: Any = None) -> Any:
        if self.isci_kullan():
            return IsciSesKaynagi(parca_cb, saat, self.isci, self.ayar, self._oyun_pid, hata_cb)
        if str(self.ayar().get("kaynak") or "") == "ps5:gizli":   # §15.8: dublaj paketi olmadan da PS5 sesi
            return ses_mod.SesKaynagi(parca_cb, saat, kaynak_fabrika=ses_mod.ps5_kaynak, hata_cb=hata_cb)
        return ses_mod.SesKaynagi(parca_cb, saat, hata_cb=hata_cb)

    async def girisler(self) -> list[dict[str, Any]]:
        if not self.isci_kullan():
            return []
        return (await self.isci.iste("girisler", {})).get("girisler") or []

    def gecikme(self) -> dict[str, Any] | None:
        isl = self.isleyici
        if isl is None or not isl.olcumler:
            return None
        son = dict(isl.olcumler[-1])
        bekle = [o["bekleme_ms"] for o in isl.olcumler if o.get("bekleme_ms") is not None]
        ilk = [o["ilk_ses_ms"] for o in isl.olcumler if o.get("ilk_ses_ms") is not None and not o.get("atildi")]
        hf = isl.hafiza.olcum() if getattr(isl, "hafiza", None) is not None else {}
        return {"son": son, "ortalama_bekleme_ms": int(sum(bekle) / len(bekle)) if bekle else None,
                "ortalama_ilk_ses_ms": int(sum(ilk) / len(ilk)) if ilk else None, **hf,
                "atilan": sum(1 for o in isl.olcumler if o.get("atildi")), "olcum_sayisi": len(isl.olcumler)}

    def profiller(self) -> Any:
        from .. import ayarlar
        from .profil import SesProfilleri
        oyun = str(self.ayar().get("aktif_oyun") or "varsayilan")
        return SesProfilleri(ayarlar.ayar_dizini() / "oyunlar" / oyun / "sesler")

    # -- dublaj hafızası (PROTOKOL 21) --
    def hafiza_oyun(self) -> str:
        return str(self.ayar().get("aktif_oyun") or "varsayilan")

    def hafiza(self) -> Any:
        """Aktif oyunun dublaj hafızası; izin yoksa None (hiçbir dosya açılmaz/oluşturulmaz)."""
        if not self._d().get("hafiza_izni"):
            return None
        oyun = self.hafiza_oyun()
        if self._hafiza_depo is None or self._hafiza_depo[0] != oyun:
            from .hafiza import DublajHafizasi, kok_dizin
            if self._hafiza_depo is not None:
                self._hafiza_depo[1].kapat()
            kok = self.hafiza_kok(oyun) if self.hafiza_kok else kok_dizin(oyun)
            self._hafiza_depo = (oyun, DublajHafizasi(kok))
        return self._hafiza_depo[1]

    def hafiza_birak(self) -> None:
        if self._hafiza_depo is not None:
            self._hafiza_depo[1].kapat()
            self._hafiza_depo = None

    def hafiza_kodlayici(self) -> Any:
        if self.isci_kullan():
            return IsciKodlayici(self.isci)
        from .hafiza_canli import WavKodlayici
        return WavKodlayici()

    def _hafiza_oturumu(self, depo: Any) -> Any:
        from .hafiza_canli import HafizaOturumu
        isci = self.isci_kullan() and not self._kaynak_verildi

        async def ekle(k: int, iz: Any) -> None:
            await tanima_yukle(self.isci, [(k, iz)])

        async def sil(kimlikler: list[int]) -> None:
            for k in kimlikler:
                await self.isci.iste("tanima_sil", {"kimlik": k}, zaman_asimi=5.0)
        return HafizaOturumu(depo, self.hafiza_kodlayici(), ekle if isci else None,
                             lambda: float(self._d().get("hafiza_sinir_mb", 1000)), sil if isci else None)

    def isci_bos(self) -> bool:
        b = getattr(self.isci, "_bekleyen", None)
        return not b

    def bosta_mi(self) -> bool:
        """Boşta iyileştirme için: canlı dublaj ve video işi yok, işçi boş (PROTOKOL 21.6)."""
        canli = self._gorev is not None and not self._gorev.done()
        video = self.video_isi is not None and self.video_isi.calisiyor()
        return not canli and not video and self.isci_bos()

    def iyilestirici_al(self) -> Any:
        depo = self.hafiza()
        if depo is None:
            return None
        if self.iyilestirici is not None and self.iyilestirici.depo is depo:
            return self.iyilestirici
        from .iyilestir import Iyilestirici
        from .isci_istemci import pcm_kodla

        async def olc(pcm: Any, sr: int, ref: Any, ref_sr: int) -> tuple[str, float | None]:
            if not self.isci_kullan():
                return "", None
            v = {"pcm": pcm_kodla(pcm), "sr": int(sr)}
            if ref is not None:
                v.update(ref_pcm=pcm_kodla(ref), ref_sr=int(ref_sr))
            r = await self.isci.iste("aday_olc", v)
            return str(r.get("metin") or ""), r.get("benzerlik")

        async def cevir(asil: str, taslak: str, konusan: str | None) -> str | None:
            y = self.yonetici_getir()
            f = getattr(y, "iyilestir", None)
            if f is None:
                return None
            a = self.ayar()
            c = await f(asil, taslak, a.get("kaynak_dil") or "otomatik", a.get("hedef_dil") or "tr", konusan)
            return c.metin if c is not None else None

        profiller: dict[str, Any] = {}

        def referans(ad: str | None) -> Any:
            if not ad or not self._d().get("ses_profili_izni"):
                return None
            if not profiller:
                try:
                    profiller.update(self.profiller().yukle())
                except Exception:   # noqa: BLE001
                    return None
            return profiller.get(ad)
        if self.iyilestirici is not None:
            self.iyilestirici.durdur()
        self.iyilestirici = Iyilestirici(depo, self.hafiza_kodlayici(), self.motor, olc, cevir, referans, self.bosta_mi)
        return self.iyilestirici

    def iyilestirme_senkron(self) -> None:
        """`bosta_iyilestir` açık + izin varsa arka plan işi çalışır (yalnız boşta iş yapar), değilse durur."""
        istenen = bool(self._d().get("bosta_iyilestir")) and bool(self._d().get("hafiza_izni"))
        if istenen:
            i = self.iyilestirici_al()
            if i is not None:
                try:
                    i.baslat()
                except RuntimeError:
                    pass
        elif self.iyilestirici is not None:
            self.iyilestirici.durdur()

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
                "paket": self.ortam.bilgi(), "isci": bool(self.isci_kullan()),
                "tamamen_turkce": tamamen_turkce_mu(self.ayar()),
                "tamamen_turkce_destek": sys.platform == "win32" or bool(self._d().get("ses_girisi")),
                "hafif": self.hafif(), "gecikme": self.gecikme(), "tani": self.tani(),
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
        self.iyilestirme_senkron()
        istenen = self.istenen() and self.izin()
        calisan = self._gorev is not None and not self._gorev.done()
        if istenen and not calisan:
            self._gorev = asyncio.get_running_loop().create_task(self._yurut())
        elif not istenen and calisan:
            self._boru_durdur()   # süre bittiyse sakince duraklar; süre eklenince senkronla() yeniden başlatır

    def istenen(self) -> bool:
        """Kullanıcı dublajı istiyor mu (çeviri çalışıyor + dublaj açık), süreden bağımsız."""
        return self._calisiyor and self.motor_kodu() != "kapali"

    def etkin(self) -> bool:
        """Dublaj şu an gerçekten çalışıyor mu (süre bundan düşer): canlı boru hattı ya da video işi."""
        canli = self._gorev is not None and not self._gorev.done()
        video = self.video_isi is not None and self.video_isi.calisiyor()
        return bool(canli or video)

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
        if self.isci_kullan() and not self._kaynak_verildi:   # altyazı anında kim konuşuyor (cinsiyet / kimlik)
            isleyici.anlik_ses = lambda sn: anlik_ses(self.isci, sn)
        if self._d().get("ses_profili_izni"):       # yalnız izinle: karakter sesleri diskte (yerel, silinebilir)
            profiller = self.profiller()
            try:
                isleyici.profil_yukle(await asyncio.to_thread(profiller.yukle))
            except Exception:   # noqa: BLE001
                log.debug("ses profilleri okunamadı", exc_info=True)
            isleyici.profil_kaydet = profiller.kaydet
        depo = self.hafiza()
        if depo is not None:                         # yalnız izinle: dublaj hafızası (PROTOKOL 21)
            isleyici.hafiza = self._hafiza_oturumu(depo)
        self.isleyici = isleyici
        self.yayin.dinle(isleyici.olay)
        kaynak = self.kaynak_fabrika(lambda p: loop.call_soon_threadsafe(isleyici.kuyruga_at, p), self.saat,
                                     hata_cb=lambda e: loop.call_soon_threadsafe(self._hata, e.kod))
        self._kaynak = kaynak
        if isleyici.hafiza is not None and hasattr(kaynak, "tanima_cb"):
            kaynak.parmak_izi = True
            kaynak.tanima_cb = isleyici.tanima_olayi

            async def dizin_yukle() -> None:
                try:
                    await tanima_yukle(self.isci, await isleyici.hafiza.tum_izler(), sifirla=True)
                except Exception as e:   # noqa: BLE001 — tanıma olmadan da altyazı isabetleri çalışır
                    log.info("tanıma dizini yüklenemedi: %s", e)
            isleyici._gorev(dizin_yukle())
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
        if ad == "tv":
            return self._tv
        if not self._bilgisayar_verildi and self.isci_kullan():
            return self._isci_cikis
        return self._bilgisayar

    def durdur(self) -> None:
        self._calisiyor = False
        self._boru_durdur()

    def _boru_durdur(self) -> None:
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

    # -- video dublajı (PROTOKOL 14.4) --
    video_isi: Any = None

    def video_bilgi(self) -> dict[str, Any]:
        if self.video_isi is None:
            return {"durum": "bosta"}
        b = self.video_isi.bilgi()
        if b.get("hata"):
            from .. import metinler
            b["mesaj"] = metinler.mesaj(b["hata"], self.ayar().get("arayuz_dili") or "tr")
        return b

    def video_baslat(self, yol: Path, cevirmen: Any, is_koku: Path | None = None) -> dict[str, Any]:
        from .video import VideoIsi
        if self.video_isi is not None and self.video_isi.calisiyor():
            raise DublajHatasi("video_suruyor")
        if not self.isci_kullan():
            raise DublajHatasi("dublaj_paket_yok")
        if not self.izin():
            raise DublajHatasi("dublaj_suresi_yok")     # PROTOKOL 17.1: başlamak için süre ya da kod gerekir
        if self._gorev is not None and not self._gorev.done():
            raise DublajHatasi("video_canli_acik")     # tek ekran kartı: canlı dublaj açıkken video olmaz
        self.video_isi = VideoIsi(yol, self.isci, cevirmen, self.ayar, is_koku, self.saat,
                                  lambda b: self.yayin.yayinla("dublaj-video", b))
        self.video_isi.baslat()
        return self.video_bilgi()

    async def video_iptal(self) -> None:
        if self.video_isi is not None:
            await self.video_isi.iptal()
            if self.isci.calisiyor():
                await self.isci.iptal()

    async def kapat_tum(self) -> None:
        """Program kapanıyor: video işi, kurulum ve işçi süreci kapanır."""
        self.durdur()
        if self.iyilestirici is not None:
            self.iyilestirici.durdur()
        if self.video_isi is not None:
            await self.video_isi.iptal()
        self.ortam.iptal()
        await self.ortam.bekle()
        await self.isci.kapat()
