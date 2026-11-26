# SPDX-License-Identifier: AGPL-3.0-only
"""Video dublajı (PROTOKOL 14.4): kayıtlı oyun videosundan Türkçe dublajlı kopya.

Ağır işleri işçi yapar; bu modül aşamaları sırayla yürütür, her aşamanın çıktısını iş klasörüne
kaydeder (iptalden sonra kaldığı yerden sürer), çeviriyi ana programın çeviri yöneticisiyle yapar
ve ilerleme/kalan süre tahmini tutar. İşçi ve çevirmen dışarıdan verilir: sahteleriyle sınanır.

Asıl video ASLA değişmez. Orijinal İngilizce sesler tamamen çıkarılır (yalnız arka plan izi kalır).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from .isci.mantik import Satir, kumele, sacma_uzun_mu, referans_araliklari, satirlara_bol, sigdir_karari, srt, yer_ayarla
from .temel import DublajHatasi

log = logging.getLogger("kopru.dublaj.video")

UZANTILAR = (".mp4", ".mkv", ".mov", ".webm", ".avi")
ASAMALAR = ("cikar", "ayir", "yazi", "bol", "konusmaci", "cevir", "seslendir", "karistir", "birlestir")
# kaba hız tahmini: video süresinin kaç katı (RTX 4060 dizüstü için tahmin; ölçüldükçe düzeltilir)
TAHMINI_ORAN = {"cikar": 0.01, "ayir": 0.08, "yazi": 0.06, "bol": 0.0, "konusmaci": 0.03, "cevir": 0.03,
                "seslendir": 0.9, "karistir": 0.02, "birlestir": 0.02}
CEVIRI_GRUBU = 40
KONUSMACI_ESIGI = 0.72


def is_kimligi(yol: Path) -> str:
    s = yol.stat()
    return hashlib.sha256(f"{yol.resolve()}|{s.st_size}|{int(s.st_mtime)}".encode()).hexdigest()[:16]


def cikti_yolu(video: Path, uzanti: str = ".mp4") -> Path:
    """`<ad> - Türkçe dublaj.mp4`; doluysa ` (2)`, ` (3)`... Asıl dosyanın üstüne asla yazmaz."""
    taban = video.with_name(f"{video.stem} - Türkçe dublaj{uzanti}")
    n = 2
    yol = taban
    while yol.exists() or yol.resolve() == video.resolve():
        yol = taban.with_name(f"{video.stem} - Türkçe dublaj ({n}){uzanti}")
        n += 1
    return yol


def video_gecerli(yol: Any) -> Path | None:
    if not isinstance(yol, str) or not yol.strip() or len(yol) > 1000 or "\x00" in yol:
        return None
    p = Path(yol)
    try:
        if not p.is_file() or p.suffix.lower() not in UZANTILAR:
            return None
    except OSError:
        return None
    return p


class VideoIsi:
    def __init__(self, video: Path, isci: Any, cevirmen: Any, ayar_fn: Callable[[], dict[str, Any]],
                 is_koku: Path | None = None, saat: Callable[[], float] = time.monotonic,
                 yayinla: Callable[[dict[str, Any]], None] | None = None,
                 hafiza_yaz: Callable[[list[dict[str, Any]]], Any] | None = None) -> None:
        self.video = video
        # PROTOKOL 21.7: izinliyse iş sonunda satırlar (İngilizce, Türkçe, ses, orijinal sesin izi) hafızaya
        self.hafiza_yaz = hafiza_yaz
        self.hafiza_satir = 0
        self.isci = isci                  # .iste(komut, veri, ilerleme=...) -> dict
        self.cevirmen = cevirmen          # .video_cevir(metinler, sureler, kaynak, hedef, konusanlar, onceki, kisalt)
        self.ayar_fn = ayar_fn
        self.saat = saat
        self.yayinla = yayinla or (lambda d: None)
        self.kimlik = is_kimligi(video)
        self.klasor = (is_koku or Path(tempfile.gettempdir()) / "AltYaziKoprusu-dublaj") / self.kimlik
        self.durum = "bosta"
        self.asama: str | None = None
        self.asama_yuzde: dict[str, float] = {a: 0.0 for a in ASAMALAR}
        self.sure_sn = 0.0
        self.satir_bitti = 0
        self.satir_toplam = 0
        self.konusmaci_sayisi = 0
        self.cikti: Path | None = None
        self.srt_yolu: Path | None = None
        self.hata: str | None = None
        self.ayrinti: str | None = None
        self._olcum: dict[str, float] = {}     # aşama -> gerçek süre / video süresi
        self._asama_bas = 0.0
        self._gorev: asyncio.Task | None = None
        self._iptal = False

    # -- durum --
    def _p(self, ad: str) -> Path:
        return self.klasor / ad

    def _bitti_mi(self, a: str) -> bool:
        return self._p(f"{a}.bitti").exists()

    def _isaretle(self, a: str) -> None:
        self._p(f"{a}.bitti").write_text("1", encoding="utf-8")

    def _json_yaz(self, ad: str, veri: Any) -> None:
        g = self._p(ad + ".tmp")
        g.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
        os.replace(g, self._p(ad))

    def _json_oku(self, ad: str) -> Any:
        return json.loads(self._p(ad).read_text(encoding="utf-8"))

    def kalan_sn(self) -> int | None:
        if self.durum != "calisiyor" or self.sure_sn <= 0:
            return None
        kalan = 0.0
        for a in ASAMALAR:
            oran = self._olcum.get(a, TAHMINI_ORAN[a])
            kalan += oran * self.sure_sn * (1 - self.asama_yuzde[a] / 100.0)
        if self.asama and self.asama_yuzde[self.asama] > 5:   # süren aşama: ölçülen hızla
            gecen = self.saat() - self._asama_bas
            tahmin = gecen / (self.asama_yuzde[self.asama] / 100.0) - gecen
            kalan += tahmin - TAHMINI_ORAN[self.asama] * self.sure_sn * (1 - self.asama_yuzde[self.asama] / 100)
        return max(0, int(kalan))

    def bilgi(self) -> dict[str, Any]:
        agirlik = {a: TAHMINI_ORAN[a] + 0.01 for a in ASAMALAR}
        toplam = sum(agirlik.values())
        yuzde = sum(agirlik[a] * self.asama_yuzde[a] for a in ASAMALAR) / toplam
        return {"durum": self.durum, "ad": self.video.name, "yol": str(self.video), "asama": self.asama,
                "asamalar": [{"kod": a, "durum": "bitti" if self.asama_yuzde[a] >= 100 else
                              ("suruyor" if a == self.asama else "bekliyor"), "yuzde": round(self.asama_yuzde[a])}
                             for a in ASAMALAR],
                "yuzde": round(yuzde), "kalan_sn": self.kalan_sn(),
                "satir": {"bitti": self.satir_bitti, "toplam": self.satir_toplam},
                "konusmaci_sayisi": self.konusmaci_sayisi, "sure_sn": round(self.sure_sn, 1),
                "hafiza_satir": self.hafiza_satir,
                "cikti": str(self.cikti) if self.cikti else None, "srt": str(self.srt_yolu) if self.srt_yolu else None,
                "hata": self.hata, "ayrinti": self.ayrinti,
                "devam_edilebilir": self.durum in ("iptal", "hata") and self.klasor.exists()}

    def _yuzde(self, a: str) -> Callable[[float, str], None]:
        def cb(y: float, mesaj: str = "") -> None:
            self.asama_yuzde[a] = max(self.asama_yuzde[a], min(99.0, float(y)))
            self.yayinla(self.bilgi())
        return cb

    # -- çalıştırma --
    def calisiyor(self) -> bool:
        return self._gorev is not None and not self._gorev.done()

    def baslat(self) -> None:
        if self.calisiyor():
            return
        self._iptal = False
        self.durum = "calisiyor"
        self._gorev = asyncio.get_running_loop().create_task(self.calis())

    async def iptal(self) -> None:
        self._iptal = True
        if self._gorev and not self._gorev.done():
            self._gorev.cancel()
            await asyncio.gather(self._gorev, return_exceptions=True)

    async def calis(self) -> None:
        self.durum, self.hata, self.ayrinti = "calisiyor", None, None
        self.klasor.mkdir(parents=True, exist_ok=True)
        adimlar = {"cikar": self._cikar, "ayir": self._ayir, "yazi": self._yazi, "bol": self._bol,
                   "konusmaci": self._konusmaci, "cevir": self._cevir, "seslendir": self._seslendir,
                   "karistir": self._karistir, "birlestir": self._birlestir}
        try:
            for a in ASAMALAR:
                if self._bitti_mi(a):
                    self.asama_yuzde[a] = 100.0
                    if a == "cikar":
                        self.sure_sn = float(self._json_oku("bilgi.json")["sure_sn"])
                    continue
                self.asama, self._asama_bas = a, self.saat()
                self.yayinla(self.bilgi())
                await adimlar[a]()
                if self.sure_sn > 0:
                    self._olcum[a] = (self.saat() - self._asama_bas) / self.sure_sn
                self.asama_yuzde[a] = 100.0
                self._isaretle(a)
            await self._hafizaya()
            self.durum, self.asama = "bitti", None
            shutil.rmtree(self.klasor, ignore_errors=True)    # ara dosyalar silinir; çıktı kullanıcının
        except asyncio.CancelledError:
            self.durum = "iptal"
        except DublajHatasi as e:
            self.durum, self.hata, self.ayrinti = "hata", e.kod, e.ayrinti[:300]
            log.warning("Video dublajı durdu: %s %s", e.kod, e.ayrinti)
        except Exception as e:   # noqa: BLE001 — program çökmesin
            self.durum, self.hata, self.ayrinti = "hata", "sunucu_hatasi", f"{type(e).__name__}: {e}"[:300]
            log.exception("Video dublajı çöktü")
        self.yayinla(self.bilgi())

    async def _hafizaya(self) -> None:
        """Dublaj hafızasını doldurur (PROTOKOL 21.7). Başarısız olursa video yine biter (hata yalnız günlükte)."""
        if self.hafiza_yaz is None:
            return
        try:
            satirlar = self._satirlar()
            ceviri: list[str] = self._json_oku("ceviri.json")
            biten = json.loads(self._p("seslendirme.json").read_text(encoding="utf-8"))
            k = self._json_oku("konusmaci.json")
            idx = [i for i in range(len(satirlar)) if biten.get(str(i))]
            if not idx:
                return
            r = await self.isci.iste("parmak_izleri", {"giris": str(self._p("asil.wav")),
                                                       "araliklar": [[satirlar[i].bas, satirlar[i].son] for i in idx]})
            izler = r.get("izler") or [[] for _ in idx]
            kayitlar = []
            for i, iz in zip(idx, izler):
                b = biten[str(i)]
                kod = await self.isci.iste("ses_kodla", {"giris": b["yol"]})
                kayitlar.append({"asil": satirlar[i].metin, "tr": b.get("metin") or (ceviri[i] if i < len(ceviri) else ""),
                                 "veri": kod["veri"], "bicim": kod["bicim"], "sr": kod["sr"],
                                 "sure_sn": kod.get("sure_sn") or b.get("sure"), "en_sure_sn": satirlar[i].sure, "iz": iz,
                                 "duygu": k["duygular"][i] if i < len(k.get("duygular") or []) else None})
            self.hafiza_satir = int(await self.hafiza_yaz(kayitlar) or 0)
        except Exception as e:   # noqa: BLE001
            log.warning("Video satırları dublaj hafızasına yazılamadı: %s", e)

    # -- aşamalar --
    async def _cikar(self) -> None:
        r = await self.isci.iste("video_cikar", {"video": str(self.video), "cikis": str(self._p("asil.wav"))},
                                 ilerleme=self._yuzde("cikar"))
        self.sure_sn = float(r.get("sure_sn") or 0)
        self._json_yaz("bilgi.json", {"sure_sn": self.sure_sn, "video": str(self.video)})

    async def _ayir(self) -> None:
        await self.isci.iste("ayir", {"giris": str(self._p("asil.wav")), "ses_cikis": str(self._p("ses.wav")),
                                      "arka_cikis": str(self._p("arka.wav"))}, ilerleme=self._yuzde("ayir"))

    async def _yazi(self) -> None:
        r = await self.isci.iste("yaziya", {"giris": str(self._p("ses.wav"))}, ilerleme=self._yuzde("yazi"))
        self._json_yaz("kelimeler.json", {"kelimeler": r.get("kelimeler") or [], "dil": r.get("dil")})

    async def _bol(self) -> None:
        k = self._json_oku("kelimeler.json")["kelimeler"]
        satirlar = satirlara_bol(k)
        self._json_yaz("satirlar.json", [s.sozluk() for s in satirlar])

    def _satirlar(self) -> list[Satir]:
        return [Satir(d["bas"], d["son"], d["metin"], d.get("konusan", 0)) for d in self._json_oku("satirlar.json")]

    async def _konusmaci(self) -> None:
        satirlar = self._satirlar()
        if not satirlar:
            self._json_yaz("konusmaci.json", {"duygular": [], "referanslar": {}})
            return
        r = await self.isci.iste("izler", {"giris": str(self._p("ses.wav")), "arka": str(self._p("arka.wav")),
                                           "araliklar": [[s.bas, s.son] for s in satirlar]},
                                 ilerleme=lambda y, m: self._yuzde("konusmaci")(y * 0.7, m))
        import numpy as np
        etiket = kumele(np.asarray(r["izler"], dtype=float), KONUSMACI_ESIGI)
        for s, e in zip(satirlar, etiket):
            s.konusan = e
        self._json_yaz("satirlar.json", [s.sozluk() for s in satirlar])
        araliklar = referans_araliklari(satirlar, r.get("puanlar") or [0.0] * len(satirlar))
        refler = {}
        for k, ar in araliklar.items():
            yol = self._p(f"ref_{k}.wav")
            await self.isci.iste("referans_kaydet", {"giris": str(self._p("ses.wav")), "araliklar": ar, "cikis": str(yol)})
            refler[str(k)] = str(yol)
        self.konusmaci_sayisi = len(refler)
        self._json_yaz("konusmaci.json", {"duygular": r.get("duygular") or [{}] * len(satirlar), "referanslar": refler})

    async def _cevir(self) -> None:
        satirlar = self._satirlar()
        ayar = self.ayar_fn()
        sonuc: list[str] = []
        onceki: list[tuple[str, str]] = []
        for i in range(0, len(satirlar), CEVIRI_GRUBU):
            grup = satirlar[i:i + CEVIRI_GRUBU]
            tr = await self.cevirmen.video_cevir([s.metin for s in grup], [s.sure for s in grup],
                                                 ayar.get("kaynak_dil") or "otomatik", ayar.get("hedef_dil") or "tr",
                                                 [f"K{s.konusan + 1}" for s in grup], onceki)
            sonuc += tr
            onceki += list(zip([s.metin for s in grup], tr))
            self._yuzde("cevir")(100.0 * len(sonuc) / len(satirlar))
        self._json_yaz("ceviri.json", sonuc)

    async def _seslendir(self) -> None:
        satirlar = self._satirlar()
        ceviri: list[str] = self._json_oku("ceviri.json")
        k = self._json_oku("konusmaci.json")
        d = self.ayar_fn().get("dublaj") or {}
        sinir = float(d.get("hiz_siniri", 1.25))
        motor = d.get("video_motor", "chatterbox")
        ayar = self.ayar_fn()
        self.satir_toplam = len(satirlar)
        sonuc_yolu = self._p("seslendirme.json")
        biten: dict[str, Any] = json.loads(sonuc_yolu.read_text(encoding="utf-8")) if sonuc_yolu.exists() else {}
        for i, s in enumerate(satirlar):
            if str(i) in biten:
                continue
            metin = ceviri[i].strip() if i < len(ceviri) else ""
            if not metin:
                biten[str(i)] = None
                continue
            ref = k["referanslar"].get(str(s.konusan))
            duygu = k["duygular"][i] if i < len(k["duygular"]) else {}
            ham = self._p(f"tts_{i}.wav")
            r = await self.isci.iste("seslendir", {"metin": metin, "ref_yol": ref, "duygu": duygu, "motor": motor,
                                                   "cikis": str(ham)})
            if sacma_uzun_mu(float(r["sure_sn"]), metin):    # uydurma: bir kez yeniden üret
                r = await self.isci.iste("seslendir", {"metin": metin, "ref_yol": ref, "duygu": {**duygu, "canlilik": 0.4},
                                                       "motor": motor, "cikis": str(ham)})
            karar, oran = sigdir_karari(float(r["sure_sn"]), s.sure, sinir)
            if karar == "kisalt":
                try:
                    kisa = (await self.cevirmen.video_cevir([s.metin], [s.sure], ayar.get("kaynak_dil") or "otomatik",
                                                            ayar.get("hedef_dil") or "tr", None, None, {0: metin}))[0]
                except Exception:   # noqa: BLE001 — kısa çeviri alınamazsa sınırda hızlanır
                    kisa = ""
                if kisa and len(kisa) < len(metin):
                    metin = kisa
                    r = await self.isci.iste("seslendir", {"metin": metin, "ref_yol": ref, "duygu": duygu,
                                                           "motor": motor, "cikis": str(ham)})
                karar, oran = sigdir_karari(float(r["sure_sn"]), s.sure, sinir, kisaltma_denendi=True)
            sure = float(r["sure_sn"])
            yol = ham
            if karar == "hizlandir" and oran > 1.0:
                yol = self._p(f"hiz_{i}.wav")
                sure = float((await self.isci.iste("hizlandir", {"giris": str(ham), "cikis": str(yol), "oran": oran}))["sure_sn"])
            biten[str(i)] = {"yol": str(yol), "sure": sure, "metin": metin, "hiz": round(oran if karar == "hizlandir" else 1.0, 3)}
            g = sonuc_yolu.with_suffix(".tmp")
            g.write_text(json.dumps(biten, ensure_ascii=False), encoding="utf-8")
            os.replace(g, sonuc_yolu)        # her satırdan sonra kaydet: iptalde kaldığı yerden
            self.satir_bitti = len(biten)
            self._yuzde("seslendir")(100.0 * (i + 1) / max(1, len(satirlar)))

    async def _karistir(self) -> None:
        satirlar = self._satirlar()
        biten = json.loads(self._p("seslendirme.json").read_text(encoding="utf-8"))
        idx = [i for i in range(len(satirlar)) if biten.get(str(i))]
        baslar = yer_ayarla([satirlar[i].bas for i in idx], [biten[str(i)]["sure"] for i in idx], self.sure_sn)
        await self.isci.iste("karistir", {"arka": str(self._p("arka.wav")), "cikis": str(self._p("dublaj.wav")),
                                          "satirlar": [{"yol": biten[str(i)]["yol"], "bas": b} for i, b in zip(idx, baslar)]},
                             ilerleme=self._yuzde("karistir"))
        self._json_yaz("altyazi.json", [[b, b + biten[str(i)]["sure"], biten[str(i)]["metin"]] for i, b in zip(idx, baslar)])

    async def _birlestir(self) -> None:
        hedef = cikti_yolu(self.video)
        gecici = hedef.with_name(hedef.stem + ".yaziliyor" + hedef.suffix)
        try:
            await self.isci.iste("video_birlestir", {"video": str(self.video), "ses": str(self._p("dublaj.wav")),
                                                     "cikis": str(gecici), "sure_sn": self.sure_sn},
                                 ilerleme=self._yuzde("birlestir"))
            os.replace(gecici, hedef)
        finally:
            if gecici.exists():
                gecici.unlink()
        self.cikti = hedef
        if (self.ayar_fn().get("dublaj") or {}).get("video_srt", True):
            s = hedef.with_suffix(".srt")
            s.write_text(srt([tuple(x) for x in self._json_oku("altyazi.json")]), encoding="utf-8")
            self.srt_yolu = s
