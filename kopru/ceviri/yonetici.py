# SPDX-License-Identifier: AGPL-3.0-only
"""Çeviri yöneticisi: hafıza -> önbellek -> motor (bağlamla) -> yedek."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict, deque
from difflib import SequenceMatcher
from typing import Any, Callable

from .. import dugmeler
from .. import sozluk as sozluk_mod
from ..hafiza import Hafiza, OneriDeposu
from ..onbellek import normallestir
from ..onbellek import Onbellek
from . import ingilizce
from .istem import SON_SATIR_ADEDI, dublaj_ipucu, hitap_sez, iyilestirme_ipucu, video_dublaj_ipucu
from .temel import AgHatasi, Baglam, Ceviri, CeviriMotoru, ErisimSiniri, ModelBulunamadi, MotorHatasi

log = logging.getLogger("kopru.ceviri")
YENIDEN_DENEME_SN = 60.0
EN_COK_HITAP = 40          # PROTOKOL 19.1: hitap hafızası (konuşan -> dinleyen) çift sayısı
EN_COK_OGRENILEN = 60      # oturumda öğrenilen ad sayısı
OGRENME_ESIGI = 2          # aynı ad aynı biçimle bu kadar kez önerilirse "bilinen ad" olur
ANLAMLI_FARK = 0.98        # PROTOKOL 19.2: iyileştirme ancak benzerlik bundan küçükse uygulanır
IYILESTIRME_DAKIKA = 8     # dakikada en çok bu kadar iyileştirme isteği (ücretsiz kota ilk çeviriye kalsın)
IYILESTIRME_DURAK_SN = 60.0   # iyileştirme 429 alırsa bu kadar ara verilir


def anlamli_fark(eski: str, yeni: str) -> bool:
    """İyileştirilmiş çeviri taslaktan anlamlı biçimde farklı mı (aynı metni yeniden yayınlama, titreme yok)."""
    a, b = normallestir(eski), normallestir(yeni)
    return bool(b) and a != b and SequenceMatcher(None, a, b).ratio() < ANLAMLI_FARK


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
        # PROTOKOL 19.1/19.2 (yalnız RAM, oyun başına; oyun değişince yönetici yeniden kurulur)
        self.hitaplar: OrderedDict[tuple[str, str], str] = OrderedDict()
        self._son_konusan: str | None = None
        self.ogrenilen: dict[str, str] = {}
        self._terim_sayac: dict[tuple[str, str], int] = {}
        self._iyilestirilen: set[str] = set()
        self.iyilestirme_istek = 0
        self.iyilestirilen_sayi = 0
        self._iyi_zamanlar: deque[float] = deque(maxlen=IYILESTIRME_DAKIKA)
        self._iyi_durak = 0.0

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
                      son_satirlar=list(self.son_satirlar),
                      hitaplar=[(a, d, f) for (a, d), f in self.hitaplar.items()],
                      bilinen_adlar=dict(self.ogrenilen))

    def _hitap_ogren(self, konusan: str | None, ceviri: str) -> None:
        """PROTOKOL 19.1: konuşan -> önceki farklı konuşan çiftinin hitabı (sen/siz)."""
        if not konusan:
            return
        k = " ".join(konusan.split())[:40]
        onceki = self._son_konusan
        self._son_konusan = k
        if not onceki or onceki.casefold() == k.casefold():
            return
        f = hitap_sez(ceviri)
        if f is None:
            return
        anahtar = (k, onceki)
        self.hitaplar.pop(anahtar, None)
        self.hitaplar[anahtar] = f
        while len(self.hitaplar) > EN_COK_HITAP:
            self.hitaplar.popitem(last=False)

    # -- konuşan (altyazıdaki "AD:" ön eki) --
    konusan_destekli = True

    def konusan_cinsiyeti(self, ad: str | None) -> str | None:
        """Oyun bilgisindeki karakter listesinden konuşanın cinsiyeti: "k" | "e" | None (büyük/küçük harf ve
        yalnız ilk ad da eşleşir: "LUCIA" = "Lucia Caminos")."""
        if not ad:
            return None
        a = " ".join(str(ad).split()).casefold()
        for k in self.oyun_bilgisi.get("karakterler") or []:
            if not isinstance(k, dict):
                continue
            kad = " ".join(str(k.get("ad") or "").split()).casefold()
            if kad and (kad == a or kad.split(" ")[0] == a or a.split(" ")[0] == kad):
                c = k.get("cinsiyet")
                return c if c in ("k", "e") else None
        return None

    def konusan_ipucu(self, konusan: str | None) -> str:
        if not konusan:
            return ""
        cins = {"k": "female", "e": "male"}.get(self.konusan_cinsiyeti(konusan) or "")
        return (f"Speaker of the line(s) to translate: {konusan}" + (f" ({cins})" if cins else "") +
                ". Use this only for gendered words and tone; do not add the name to the translation.")

    @staticmethod
    def _baglam_asil(asil: str, konusan: str | None) -> str:
        return f"{konusan}: {asil}" if konusan else asil

    def satir_kaydet(self, id_: str, asil: str, ceviri: str, kaynak: str = "motor",
                     konusan: str | None = None) -> None:
        """Yayınlanan altyazıyı bağlama ve son-çeviriler listesine ekler (bağlamda konuşan adıyla)."""
        self.son_satirlar.append((self._baglam_asil(asil, konusan), ceviri))
        self._hitap_ogren(konusan, ceviri)
        g = {"id": id_, "asil": asil, "ceviri": ceviri, "kaynak": kaynak}
        if konusan:
            g["konusan"] = konusan
        self.gecmis.append(g)

    def satir_guncelle(self, id_: str, asil: str, ceviri: str, kaynak: str = "motor",
                       konusan: str | None = None) -> None:
        """Aynı cümlenin devamı: son-çeviriler listesinde yeni satır açmadan günceller."""
        for g in reversed(self.gecmis):
            if g["id"] == id_:
                eski = self._baglam_asil(g["asil"], g.get("konusan"))
                g["asil"], g["ceviri"], g["kaynak"] = asil, ceviri, kaynak
                if konusan:
                    g["konusan"] = konusan
                yeni = self._baglam_asil(asil, g.get("konusan"))
                self.son_satirlar = deque(((yeni, ceviri) if a == eski else (a, c)
                                           for a, c in self.son_satirlar), maxlen=SON_SATIR_ADEDI)
                return
        self.satir_kaydet(id_, asil, ceviri, kaynak, konusan)

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
        if not self.oneriler:
            for t in baglam.yeni_terimler[:10]:   # öneri deposu yoksa (hafıza izni yok) yalnız oturumda öğren
                a, c = str(t.get("asil", "")).strip(), str(t.get("ceviri", "")).strip()
                if 0 < len(a) <= 60 and 0 < len(c) <= 60 and a.casefold() in " ".join(metinler).casefold():
                    self._ad_ogren(a, c)
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
                self._ad_ogren(asil, ceviri)

    def _ad_ogren(self, asil: str, ceviri: str) -> None:
        """PROTOKOL 19.1: aynı ad aynı biçimle OGRENME_ESIGI kez önerildiyse oturumun "bilinen ad"ı olur."""
        if asil in self.ogrenilen or len(self.ogrenilen) >= EN_COK_OGRENILEN:
            return
        k = (asil.casefold(), ceviri)
        self._terim_sayac[k] = self._terim_sayac.get(k, 0) + 1
        if self._terim_sayac[k] >= OGRENME_ESIGI:
            self.ogrenilen[asil] = ceviri

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
                    aciklama: bool = False, konusan: str | None = None) -> list[Ceviri]:
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
            gelen = await self._ucustaki(ayri, kaynak, hedef, aciklama, self.konusan_ipucu(konusan))
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

    async def _cevrilmeyenleri_zorla(self, metinler: list[str], ceviriler: list[Ceviri], kaynak: str, hedef: str,
                                     aciklama: bool, ipucu: str) -> list[Ceviri]:
        """Motor sıradan İngilizce bir satırı aynen döndürdüyse ("Hang up" => "Hang up") bir kez daha,
        "bunlar isim değil, mutlaka çevir" uyarısıyla sorar. Hedef Türkçe değilse ya da satır sözlükte /
        bilinen isimlerdeyse dokunmaz. İkinci deneme de aynıysa ilk sonuç kalır."""
        if hedef != "tr":
            return ceviriler
        bilinen = {a.casefold() for a in self.terimler}
        supheli = [i for i, (m, c) in enumerate(zip(metinler, ceviriler))
                   if normallestir(c.metin) == normallestir(m) and m.strip().casefold() not in bilinen
                   and ingilizce.siradan_ingilizce_mi(m)]
        if not supheli:
            return ceviriler
        try:
            ek = "\n\n".join(x for x in (ipucu, ingilizce.ZORUNLU_CEVIR_IPUCU) if x)
            ikinci, _ = await self._motorla([metinler[i] for i in supheli], kaynak, hedef, aciklama, ek)
        except Exception:   # noqa: BLE001 — ikinci deneme olmazsa ilk sonuç kalır, altyazı akışı durmaz
            log.info("Çevrilmeden gelen satırlar yeniden sorulamadı")
            return ceviriler
        sonuc = list(ceviriler)
        for i, c in zip(supheli, ikinci):
            if c.metin.strip() and normallestir(c.metin) != normallestir(metinler[i]):
                sonuc[i] = c
        return sonuc

    async def _ucustaki(self, ayri: list[str], kaynak: str, hedef: str,
                        aciklama: bool, ipucu: str = "") -> dict[str, Ceviri]:
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
                ceviriler, motor_kodu = await self._motorla(yeni, kaynak, hedef, aciklama, ipucu)
                if len(ceviriler) != len(yeni):   # savunma: zip sessizce kısaltırdı ve bekleyenler sonsuza dek asılırdı
                    raise MotorHatasi("Çeviri sayısı uyuşmuyor")
                ceviriler = await self._cevrilmeyenleri_zorla(yeni, ceviriler, kaynak, hedef, aciklama, ipucu)
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
                (sonuc[m],) = (await self._ucustaki([m], kaynak, hedef, aciklama, ipucu)).values()
        return sonuc

    # -- PROTOKOL 19.2: iki aşamalı kalite (iyileştirme) --
    def iyilestirebilir_mi(self) -> bool:
        """Motor destekliyor, yedekte değil, 429 arası yok ve dakikalık sınır dolmadı."""
        if not getattr(self.birincil, "iyilestirme_destekler", False) or self.yedekte:
            return False
        simdi = time.monotonic()
        if simdi < self._iyi_durak:
            return False
        return len(self._iyi_zamanlar) < IYILESTIRME_DAKIKA or simdi - self._iyi_zamanlar[0] >= 60.0

    async def iyilestir(self, metin: str, taslak: str, kaynak: str = "otomatik", hedef: str = "tr",
                        konusan: str | None = None) -> Ceviri | None:
        """Derin ikinci geçiş. Anlamlı biçimde daha farklı (iyi) bir çeviri dönerse onu, yoksa None.
        Her satır oturumda en çok bir kez; sonuç hafızaya/önbelleğe yazılır. Hata hiçbir zaman dışarı taşmaz."""
        n = normallestir(metin)
        if not n or n in self._iyilestirilen or not self.iyilestirebilir_mi():
            return None
        self._iyilestirilen.add(n)
        self.iyilestirme_istek += 1
        self._iyi_zamanlar.append(time.monotonic())
        baglam = self._baglam()
        baglam.derin = True
        baglam.ipucu = "\n\n".join(x for x in (self.konusan_ipucu(konusan), iyilestirme_ipucu(taslak)) if x)
        try:
            (c,) = await self._cagir(self.birincil, [metin], kaynak, hedef, False, baglam)
        except asyncio.CancelledError:
            raise
        except Exception as e:   # noqa: BLE001 — iyileştirme isteğe bağlıdır: ilk çeviri kalır
            log.info("İyileştirme yapılamadı (%s)", type(e).__name__)
            if isinstance(e, AgHatasi) and "429" in str(e):
                self._iyi_durak = time.monotonic() + IYILESTIRME_DURAK_SN
            return None
        yeni = dugmeler.dugme_koru(metin, sozluk_mod.son_kontrol(metin, c.metin, self.terimler))
        if not yeni.strip() or normallestir(yeni) == n or not anlamli_fark(taslak, yeni):
            return None
        if self.onbellek:
            self.onbellek.koy(metin, kaynak, hedef, self.oyun, yeni, None, False)
        if self.hafiza:
            self.hafiza.kaydet(metin, yeni, "motor", getattr(self.birincil, "kod", None))
        for g in self.gecmis:
            if normallestir(g["asil"]) == n and g.get("kaynak") == "motor":
                g["ceviri"] = yeni
        self.son_satirlar = deque(((a, yeni if c2 == taslak and normallestir(a).endswith(n) else c2)
                                   for a, c2 in self.son_satirlar), maxlen=SON_SATIR_ADEDI)
        self.iyilestirilen_sayi += 1
        return Ceviri(yeni, None, "motor")

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
