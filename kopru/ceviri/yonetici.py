# SPDX-License-Identifier: AGPL-3.0-only
"""Çeviri yöneticisi: hafıza -> önbellek -> motor (bağlamla) -> yedek."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, Callable

from .. import dugmeler
from .. import sozluk as sozluk_mod
from ..hafiza import Hafiza, OneriDeposu
from ..onbellek import normallestir
from ..onbellek import Onbellek
from .istem import SON_SATIR_ADEDI, dublaj_ipucu, video_dublaj_ipucu
from .temel import AgHatasi, Baglam, Ceviri, CeviriMotoru, ErisimSiniri, ModelBulunamadi, MotorHatasi

log = logging.getLogger("kopru.ceviri")
YENIDEN_DENEME_SN = 60.0


class _Iptal(Exception):
    """Dedupe sahibi iptal edildi; bekleyen isteği yeniden yapar (iç kullanım)."""


class CeviriYoneticisi:
    def __init__(self, birincil: CeviriMotoru, yedek: CeviriMotoru | None,
                 onbellek: Onbellek | None, yayinla: Callable[[str, dict], None] | None = None,
                 oyun: str = "varsayilan", hafiza: Hafiza | None = None,
                 oneriler: OneriDeposu | None = None) -> None:
        self.birincil = birincil
        self.yedek = yedek
        self.onbellek = onbellek
        self.hafiza = hafiza
        self.oneriler = oneriler
        self._yayinla = yayinla or (lambda o, v: None)
        self.oyun = oyun
        # PROTOKOL 17: altyazı sınırsız; yalnız dublaj çevirisi süreye bağlı (Durum, erişime bağlar)
        self.dublaj_izni: Callable[[], bool] = lambda: True
        self.oyun_bilgisi: dict[str, Any] = {}      # ad, aciklama, hitap, karakterler
        self.yedekte = False
        self.yedek_neden: dict[str, str] | None = None   # yedeğe geçilme sebebi {"kod","mesaj"} (panel gösterir)
        self._yedek_zamani = 0.0
        self._ucusta: dict[tuple, asyncio.Future] = {}
        # Motorun bu oturumda (güncel istemle) bilerek çevirmeden bıraktığı satırlar: gerçek isim sayılır.
        self._degismez_onayli: set[str] = set()
        self.terimler: dict[str, str] = {}
        self.son_satirlar: deque[tuple[str, str]] = deque(maxlen=SON_SATIR_ADEDI)
        self.gecmis: deque[dict[str, str]] = deque(maxlen=30)   # /api/son-ceviriler (yalnız RAM)

    def _durum(self) -> None:
        motor = self.yedek if self.yedekte and self.yedek else self.birincil
        self._yayinla("durum", {"calisiyor": True, "motor": motor.ad, "yedek": self.yedekte,
                                **self.durum_ek()})

    def durum_ek(self) -> dict[str, Any]:
        """Yedekteyken `yedek_neden` (durum olayına/API'ye eklenir); değilken boş."""
        return {"yedek_neden": dict(self.yedek_neden)} if self.yedekte and self.yedek_neden else {}

    def _neden(self, motor: CeviriMotoru, e: Exception, yedek: CeviriMotoru) -> dict[str, str]:
        if isinstance(e, ModelBulunamadi):
            kod, sebep = "model_yok", "model bulunamadı"
        elif isinstance(e, AgHatasi) and "429" in str(e):
            kod, sebep = "hiz_siniri", "istek sınırı aşıldı"
        elif isinstance(e, AgHatasi):
            kod, sebep = "ag", "ağ ya da sunucu hatası"
        else:
            kod, sebep = "yanit", "yanıt okunamadı"
        hedef = "çevrimdışı" if getattr(yedek, "cevrimdisi", False) else yedek.ad
        return {"kod": kod, "mesaj": f"{motor.ad} çalışmadı ({sebep}), {hedef} çeviriye geçildi."}

    # -- bağlam ve geçmiş --
    def _baglam(self) -> Baglam:
        b = self.oyun_bilgisi
        return Baglam(oyun_ad=b.get("ad", ""), aciklama=b.get("aciklama", ""),
                      hitap=b.get("hitap", "sen"), karakterler=list(b.get("karakterler", [])),
                      son_satirlar=list(self.son_satirlar))

    def satir_kaydet(self, id_: str, asil: str, ceviri: str, kaynak: str = "motor") -> None:
        """Yayınlanan altyazıyı bağlama ve son-çeviriler listesine ekler."""
        self.son_satirlar.append((asil, ceviri))
        self.gecmis.append({"id": id_, "asil": asil, "ceviri": ceviri, "kaynak": kaynak})

    def satir_guncelle(self, id_: str, asil: str, ceviri: str, kaynak: str = "motor") -> None:
        """Aynı cümlenin devamı: son-çeviriler listesinde yeni satır açmadan günceller."""
        for g in reversed(self.gecmis):
            if g["id"] == id_:
                eski = g["asil"]
                g["asil"], g["ceviri"], g["kaynak"] = asil, ceviri, kaynak
                self.son_satirlar = deque(((asil, ceviri) if a == eski else (a, c)
                                           for a, c in self.son_satirlar), maxlen=SON_SATIR_ADEDI)
                return
        self.satir_kaydet(id_, asil, ceviri, kaynak)

    def duzeltildi(self, asil: str, ceviri: str) -> None:
        """Kullanıcı düzeltmesini geçmişe ve bağlam satırlarına yansıtır."""
        from ..onbellek import normallestir
        n = normallestir(asil)
        for g in self.gecmis:
            if normallestir(g["asil"]) == n:
                g["ceviri"], g["kaynak"] = ceviri, "kullanici"
        self.son_satirlar = deque(((a, ceviri if normallestir(a) == n else c)
                                   for a, c in self.son_satirlar), maxlen=SON_SATIR_ADEDI)

    # -- motor çağrısı --
    async def _cagir_ham(self, motor: CeviriMotoru, metinler: list[str], kaynak: str, hedef: str,
                         aciklama: bool, baglam: Baglam) -> list[Ceviri]:
        if getattr(motor, "baglam_destekler", False):
            return await motor.cevir(metinler, kaynak, hedef, self.terimler, aciklama, baglam=baglam)
        return await motor.cevir(metinler, kaynak, hedef, self.terimler, aciklama)

    async def _cagir(self, motor: CeviriMotoru, metinler: list[str], kaynak: str, hedef: str,
                     aciklama: bool, baglam: Baglam) -> list[Ceviri]:
        """Motoru çağırır; dönen liste istenenle AYNI uzunlukta olmak zorundadır.

        Sayı tutmazsa çeviriler yanlış satıra oturabilir: asla eşlenmez. Çoklu istekte satır
        satır yeniden denenir; tek satırda MotorHatasi fırlatılır.
        """
        sonuc = await self._cagir_ham(motor, metinler, kaynak, hedef, aciklama, baglam)
        if isinstance(sonuc, list) and len(sonuc) == len(metinler) and all(isinstance(c, Ceviri) for c in sonuc):
            return sonuc
        if len(metinler) > 1:
            log.warning("Motor %d satır istenince %s döndürdü; satır satır deneniyor",
                        len(metinler), len(sonuc) if isinstance(sonuc, list) else "geçersiz")
            tek: list[Ceviri] = []
            for m in metinler:
                (c,) = await self._cagir(motor, [m], kaynak, hedef, aciklama, baglam)
                tek.append(c)
            return tek
        raise MotorHatasi("Motor yanıtındaki satır sayısı istekle uyuşmuyor")

    async def _motorla(self, metinler: list[str], kaynak: str, hedef: str,
                       aciklama: bool, ipucu: str = "") -> tuple[list[Ceviri], str | None]:
        """(sonuç, motor kodu); yedek motor kullanıldıysa kod None (hafızaya yazılmaz)."""
        baglam = self._baglam()
        baglam.ipucu = ipucu
        # yedekteyken belirli aralıkla birincili yeniden dene
        if self.yedekte and self.yedek and time.monotonic() - self._yedek_zamani < YENIDEN_DENEME_SN:
            try:
                return await self._cagir(self.yedek, metinler, kaynak, hedef, aciklama, baglam), None
            except MotorHatasi:
                # yedek de çalışmıyor (ör. kurulu değil): birincil düzelmiş olabilir, yeniden dene
                self.yedekte = False
                self._durum()
        try:
            try:
                sonuc = await self._cagir(self.birincil, metinler, kaynak, hedef, aciklama, baglam)
            except MotorHatasi:
                if getattr(self.birincil, "cevrimdisi", False):
                    raise
                # model bozuk/yarım JSON döndürdü (geçici olabilir): bir kez daha dene
                baglam.yeni_terimler.clear()
                sonuc = await self._cagir(self.birincil, metinler, kaynak, hedef, aciklama, baglam)
        except (AgHatasi, MotorHatasi) as e:
            if not self.yedek:
                raise
            log.warning("Birincil motor çalışmadı (%s), yedeğe geçildi", type(e).__name__)
            kalici = isinstance(e, AgHatasi)   # ağ/hız sınırı: bir süre yedekte kal; bozuk yanıt: yalnız bu istek
            if kalici:
                self.yedek_neden = self._neden(self.birincil, e, self.yedek)
                self.yedekte = True
                self._yedek_zamani = time.monotonic()
                self._durum()
            try:
                return await self._cagir(self.yedek, metinler, kaynak, hedef, aciklama, baglam), None
            except MotorHatasi:
                if kalici:
                    self.yedekte = False   # yedek de yok: panel "yedekte" yazmasın, sonraki istek birincili dener
                    self._durum()
                raise e from None
        if self.yedekte:
            self.yedekte = False
            self.yedek_neden = None
            self._durum()
        self._terimleri_isle(baglam.yeni_terimler, metinler)
        return sonuc, getattr(self.birincil, "kod", None)

    def _terimleri_isle(self, terimler: list[dict], metinler: list[str]) -> None:
        """Motorun bulduğu yeni özel isimleri öneri olarak saklar (sözlüğe kendiliğinden girmez)."""
        if not self.oneriler:
            return
        bilinen = {a.casefold() for a in self.terimler}
        govde = " ".join(metinler).casefold()
        for t in terimler[:10]:
            asil, ceviri = str(t.get("asil", "")).strip(), str(t.get("ceviri", "")).strip()
            # kısa, metinde gerçekten geçen ve bilinmeyen terimler
            if 0 < len(asil) <= 60 and 0 < len(ceviri) <= 60 and \
                    asil.casefold() not in bilinen and asil.casefold() in govde:
                self.oneriler.ekle(asil, ceviri)

    # -- arama / çeviri --
    def _cevrilmemis(self, metin: str, ceviri: str) -> bool:
        """Kayıtlı çeviri asıl metnin aynısı mı (ör. eski sürümün "KILLER" => "KILLER" hatası)?
        Sözlükteki terimler ve bu oturumda motorun yeniden onayladığı isimler sayılmaz."""
        n = normallestir(metin)
        return (bool(n) and normallestir(ceviri) == n and n not in self._degismez_onayli
                and metin.strip().casefold() not in {a.casefold() for a in self.terimler})

    def ara(self, metin: str, kaynak: str, hedef: str, aciklama: bool = False) -> Ceviri | None:
        """Hafıza/önbellekte varsa anında sonuç (motor çağrılmaz). Çevrilmeden saklanmış satırlar
        (kullanıcı düzeltmesi değilse) yok sayılır: motor bir kez daha sorulur."""
        if self.hafiza and not aciklama:
            vur = self.hafiza.bul(metin)
            if vur and (vur[1] == "kullanici" or not self._cevrilmemis(metin, vur[0])):
                return Ceviri(vur[0], None, vur[1])
        if self.onbellek:
            vur = self.onbellek.al(metin, kaynak, hedef, self.oyun, aciklama)
            if vur and not self._cevrilmemis(metin, vur[0]):
                return Ceviri(vur[0], vur[1])
        return None

    async def cevir(self, metinler: list[str], kaynak: str = "otomatik", hedef: str = "tr",
                    aciklama: bool = False) -> list[Ceviri]:
        sonuc: list[Ceviri | None] = [None] * len(metinler)
        eksik: list[int] = []
        for i, m in enumerate(metinler):
            vur = self.ara(m, kaynak, hedef, aciklama)
            if vur:
                sonuc[i] = vur
            else:
                eksik.append(i)
        if eksik:
            ayri = list(dict.fromkeys(metinler[i] for i in eksik))
            gelen = await self._ucustaki(ayri, kaynak, hedef, aciklama)
            for i in eksik:
                c = gelen.get(metinler[i])
                if c is None:
                    raise MotorHatasi("Çeviri eşlenemedi")
                if not c.metin.strip() and metinler[i].strip():
                    c = Ceviri(metinler[i], c.aciklama)   # motor boş döndü: boş altyazı yerine asıl metin
                sonuc[i] = c
        if any(s is None for s in sonuc):   # asla kayarak eşleme yapma
            raise MotorHatasi("Çeviri eşlenemedi")
        return sonuc  # type: ignore[return-value]

    async def _ucustaki(self, ayri: list[str], kaynak: str, hedef: str,
                        aciklama: bool) -> dict[str, Ceviri]:
        """Aynı anda aynı metin için tek istek (dedupe)."""
        bekleyen: dict[str, asyncio.Future] = {}
        yeni: list[str] = []
        for m in ayri:
            anahtar = (m, kaynak, hedef, aciklama)
            f = self._ucusta.get(anahtar)
            if f is None:
                f = asyncio.get_running_loop().create_future()
                self._ucusta[anahtar] = f
                yeni.append(m)
            bekleyen[m] = f
        if yeni:
            try:
                ceviriler, motor_kodu = await self._motorla(yeni, kaynak, hedef, aciklama)
                if len(ceviriler) != len(yeni):   # savunma: zip sessizce kısaltırdı ve bekleyenler sonsuza dek asılırdı
                    raise MotorHatasi("Çeviri sayısı uyuşmuyor")
                for m, c in zip(yeni, ceviriler):
                    c = Ceviri(dugmeler.dugme_koru(m, sozluk_mod.son_kontrol(m, c.metin, self.terimler)), c.aciklama)
                    if normallestir(c.metin) == normallestir(m):
                        self._degismez_onayli.add(normallestir(m))
                    if self.onbellek and c.metin:
                        self.onbellek.koy(m, kaynak, hedef, self.oyun, c.metin, c.aciklama, aciklama)
                    if self.hafiza and c.metin and not aciklama and motor_kodu:
                        self.hafiza.kaydet(m, c.metin, "motor", motor_kodu)
                    self._ucusta.pop((m, kaynak, hedef, aciklama)).set_result(c)
            except BaseException as e:
                for m in yeni:
                    f = self._ucusta.pop((m, kaynak, hedef, aciklama), None)
                    if f and not f.done():
                        if isinstance(e, asyncio.CancelledError):
                            # sahibi iptal edildi (ör. atılan önden çeviri): bekleyenler iptal EDİLMEZ,
                            # kendi isteklerini yeniden yapar
                            f.set_exception(_Iptal())
                        else:
                            f.set_exception(e)
                        f.exception()  # "never retrieved" uyarısını önle
                raise
        sonuc: dict[str, Ceviri] = {}
        for m, f in bekleyen.items():
            try:
                sonuc[m] = await f
            except _Iptal:
                (sonuc[m],) = (await self._ucustaki([m], kaynak, hedef, aciklama)).values()
        return sonuc

    async def video_cevir(self, metinler: list[str], sureler: list[float], kaynak: str, hedef: str,
                          konusanlar: list[str] | None = None, onceki: list[tuple[str, str]] | None = None,
                          kisalt: dict[int, str] | None = None) -> list[str]:
        """Video dublajı için bir grup satırı tek istekte çevirir (PROTOKOL 14.4/6).

        Altyazı hafızası/önbelleği okunmaz/yazılmaz (dublaj metni farklıdır). Sözlük ve oyun bilgisi kullanılır.
        """
        if not metinler:
            return []
        ipucu = video_dublaj_ipucu(sureler, konusanlar, onceki, kisalt)
        sonuc, _ = await self._motorla(list(metinler), kaynak, hedef, False, ipucu)
        if len(sonuc) != len(metinler):
            raise MotorHatasi("Çeviri sayısı uyuşmuyor")
        return [sozluk_mod.son_kontrol(m, " ".join(c.metin.split()), self.terimler) for m, c in zip(metinler, sonuc)]

    async def dublaj_cevir(self, metin: str, kaynak: str, hedef: str, sure_sn: float,
                           onceki: str | None = None) -> Ceviri:
        """Dublaj için kısa, söylenebilir çeviri (PROTOKOL 9.1/3).

        Altyazı çevirisinden FARKLIDIR; bu yüzden hafıza/önbellek ne okunur ne yazılır.
        `onceki`: önceki denemenin metni (süreye sığmadıysa "daha kısa" istenir).
        """
        if not self.dublaj_izni():
            raise ErisimSiniri()
        ipucu = dublaj_ipucu(max(0.5, sure_sn), onceki)
        sonuc, _ = await self._motorla([metin], kaynak, hedef, False, ipucu)
        c = sonuc[0]
        return Ceviri(sozluk_mod.son_kontrol(metin, " ".join(c.metin.split()), self.terimler), None)
