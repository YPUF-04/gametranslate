# SPDX-License-Identifier: AGPL-3.0-only
"""Dublaj hafızası (PROTOKOL 21.2): oyun başına, yalnız bu bilgisayarda; hazır Türkçe ses + İngilizce ses izi.

İZİN: bu sınıf yalnız `hafiza_izni:true` iken kurulur (DublajYonetici). Hiçbir şey dışarı gönderilmez.
Ses baytları dışarıda kodlanır (işçide Opus, yoksa WAV); burası yalnız saklar, bulur, sınırlar ve siler.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import threading
import time
import zipfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable

from ..onbellek import normallestir

log = logging.getLogger("kopru.dublaj.hafiza")

BICIMLER = ("ogg", "flac", "wav")
BENZERLIK = 0.92
SAYFA = 50
YEDEK_SURUM = 1
KAYNAK_ONCELIK = {"canli": 1, "video": 2, "en_iyi": 3, "kullanici": 4}

TABLO = """
CREATE TABLE IF NOT EXISTS satir (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  anahtar TEXT UNIQUE NOT NULL,
  asil TEXT NOT NULL, konusan TEXT, tr TEXT NOT NULL DEFAULT '', tr_kaynak TEXT NOT NULL DEFAULT 'canli',
  dosya TEXT, bicim TEXT, sr INTEGER, sure_sn REAL, en_sure_sn REAL, cinsiyet TEXT, profil TEXT,
  ayar TEXT, puanlar TEXT, puan REAL, duygu TEXT,
  olusma REAL NOT NULL, son_kullanim REAL NOT NULL, kullanim INTEGER NOT NULL DEFAULT 0, boyut INTEGER NOT NULL DEFAULT 0,
  iz BLOB, iz_sayisi INTEGER NOT NULL DEFAULT 0, iyilestirme REAL
);
CREATE TABLE IF NOT EXISTS gecis (
  onceki INTEGER NOT NULL, sonraki INTEGER NOT NULL, sayi INTEGER NOT NULL, ort_dt REAL,
  PRIMARY KEY (onceki, sonraki)
);
"""
ALANLAR = ("id", "anahtar", "asil", "konusan", "tr", "tr_kaynak", "dosya", "bicim", "sr", "sure_sn", "en_sure_sn",
           "cinsiyet", "profil", "ayar", "puanlar", "puan", "duygu", "olusma", "son_kullanim", "kullanim", "boyut",
           "iz_sayisi", "iyilestirme")


def anahtar(asil: str, konusan: str | None) -> str:
    return normallestir(asil) + "|" + (konusan or "").strip().casefold()


def kok_dizin(oyun: str, ayar_dizini: Path | None = None) -> Path:
    from .. import ayarlar
    return (ayar_dizini or ayarlar.ayar_dizini()) / "oyunlar" / oyun / "dublaj_hafizasi"


def hepsini_sil(ayar_dizini: Path | None = None) -> int:
    """Tüm oyunların dublaj hafızası (panel "Hepsini sil")."""
    from .. import ayarlar
    kok = (ayar_dizini or ayarlar.ayar_dizini()) / "oyunlar"
    n = 0
    if kok.is_dir():
        for d in kok.iterdir():
            h = d / "dublaj_hafizasi"
            if h.is_dir():
                shutil.rmtree(h, ignore_errors=True)
                n += 1
    return n


class DublajHafizasi:
    def __init__(self, kok: Path, saat: Callable[[], float] = time.time) -> None:
        self.kok = kok
        self.saat = saat
        self._kilit = threading.RLock()
        (kok / "sesler").mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(kok / "hafiza.sqlite"), check_same_thread=False, timeout=5)
        self._db.executescript(TABLO)
        self._db.commit()
        self._anahtarlar: dict[str, int] | None = None     # benzerlik araması için (RAM)

    # -- yardımcılar --
    def _satir(self, r: tuple | None) -> dict[str, Any] | None:
        if r is None:
            return None
        d = dict(zip(ALANLAR, r))
        for k in ("ayar", "puanlar", "duygu"):
            try:
                d[k] = json.loads(d[k]) if d[k] else None
            except ValueError:
                d[k] = None
        d["sesli"] = bool(d.get("dosya"))
        return d

    def _sec(self, nerede: str, *a: Any) -> dict[str, Any] | None:
        r = self._db.execute(f"SELECT {', '.join(ALANLAR)} FROM satir WHERE {nerede}", a).fetchone()
        return self._satir(r)

    def getir(self, kimlik: int) -> dict[str, Any] | None:
        with self._kilit:
            return self._sec("id = ?", int(kimlik))

    def _anahtar_listesi(self) -> dict[str, int]:
        if self._anahtarlar is None:
            self._anahtarlar = dict(self._db.execute("SELECT anahtar, id FROM satir").fetchall())
        return self._anahtarlar

    # -- bulma --
    def bul(self, asil: str, konusan: str | None = None, benzer: bool = True) -> dict[str, Any] | None:
        """Tam anahtar → konuşansız anahtar → (aynı oyunda) benzerlik ≥ 0,92."""
        if not asil or not asil.strip():
            return None
        with self._kilit:
            for a in ([anahtar(asil, konusan)] if konusan else []) + [anahtar(asil, None)]:
                s = self._sec("anahtar = ?", a)
                if s:
                    return s
            if konusan:   # konuşan adı bu sefer okunamadıysa ya da farklı okunduysa: aynı metinli tek satır
                rows = self._db.execute("SELECT id FROM satir WHERE anahtar LIKE ? ESCAPE '\\' LIMIT 2",
                                        (normallestir(asil).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "|%",)).fetchall()
                if len(rows) == 1:
                    return self.getir(rows[0][0])
            if not benzer:
                return None
            n = normallestir(asil)
            en, sec = BENZERLIK, None
            for a, kimlik in self._anahtar_listesi().items():
                m = a.rsplit("|", 1)[0]
                if abs(len(m) - len(n)) > max(4, len(n) * 0.1):
                    continue
                sm = SequenceMatcher(None, n, m)
                if sm.real_quick_ratio() < en or sm.quick_ratio() < en:
                    continue
                r = sm.ratio()
                if r >= en:
                    en, sec = r, kimlik
            return self.getir(sec) if sec is not None else None

    # -- yazma --
    def kaydet(self, asil: str, konusan: str | None, tr: str, tr_kaynak: str = "canli", ses: bytes | None = None,
               bicim: str | None = None, sr: int | None = None, sure_sn: float | None = None,
               en_sure_sn: float | None = None, cinsiyet: str | None = None, profil: str | None = None,
               ayar: dict[str, Any] | None = None, puanlar: dict[str, Any] | None = None, puan: float | None = None,
               iz: list[list[int]] | None = None, duygu: dict[str, Any] | None = None, zorla: bool = False) -> int:
        """Satırı ekler/günceller. Kullanıcının düzelttiği metin kullanıcı dışında bir kaynakla ezilmez; daha yüksek
        puanlı ses, düşük puanlı yeni bir sesle ezilmez (`zorla` değilse). Dönüş: satır kimliği."""
        if bicim is not None and bicim not in BICIMLER:
            raise ValueError("bicim")
        simdi = self.saat()
        a = anahtar(asil, konusan)
        with self._kilit:
            eski = self._sec("anahtar = ?", a)
            if eski is None:
                cur = self._db.execute(
                    "INSERT INTO satir (anahtar, asil, konusan, tr, tr_kaynak, olusma, son_kullanim) VALUES (?,?,?,?,?,?,?)",
                    (a, asil.strip(), (konusan or None), tr.strip(), tr_kaynak, simdi, simdi))
                kimlik = int(cur.lastrowid)
                if self._anahtarlar is not None:
                    self._anahtarlar[a] = kimlik
                eski = {"id": kimlik, "tr": "", "tr_kaynak": tr_kaynak, "dosya": None, "puan": None, "tr_yeni": True}
            kimlik = int(eski["id"])
            metin_tut = (eski.get("tr_kaynak") == "kullanici" and tr_kaynak != "kullanici" and eski.get("tr")
                         and not eski.get("tr_yeni"))
            yeni_tr = eski["tr"] if metin_tut else tr.strip()
            if not metin_tut:
                self._db.execute("UPDATE satir SET tr = ?, tr_kaynak = ? WHERE id = ?", (yeni_tr, tr_kaynak, kimlik))
            metin_degisti = yeni_tr != eski.get("tr")
            if ses is not None and not (metin_tut and yeni_tr != tr.strip()):
                eski_puan = eski.get("puan")
                ez = zorla or metin_degisti or not eski.get("dosya") or eski_puan is None or (puan or 0) >= eski_puan
                if ez:
                    self._ses_yaz(kimlik, eski.get("dosya"), ses, bicim or "wav", sr, sure_sn)
                    self._db.execute("UPDATE satir SET cinsiyet = ?, profil = ?, ayar = ?, puanlar = ?, puan = ? WHERE id = ?",
                                     (cinsiyet, profil, json.dumps(ayar or {}, ensure_ascii=False),
                                      json.dumps(puanlar or {}, ensure_ascii=False), puan, kimlik))
            elif metin_degisti and eski.get("dosya"):
                self._ses_sil(kimlik)          # metin değişti: eski ses artık doğru değil
            if ses is None and (cinsiyet or profil):
                self._db.execute("UPDATE satir SET cinsiyet = COALESCE(?, cinsiyet), profil = COALESCE(?, profil) "
                                 "WHERE id = ?", (cinsiyet, profil, kimlik))
            if iz is not None:
                self._iz_yaz(kimlik, iz, en_sure_sn, duygu)
            elif en_sure_sn is not None:
                self._db.execute("UPDATE satir SET en_sure_sn = ? WHERE id = ?", (en_sure_sn, kimlik))
            self._db.commit()
            return kimlik

    def _ses_yaz(self, kimlik: int, eski_dosya: str | None, ses: bytes, bicim: str, sr: int | None,
                 sure_sn: float | None) -> None:
        dosya = f"{kimlik}.{bicim}"
        yol = self.kok / "sesler" / dosya
        g = yol.with_suffix(".tmp")
        g.write_bytes(ses)
        os.replace(g, yol)
        if eski_dosya and eski_dosya != dosya:
            try:
                (self.kok / "sesler" / eski_dosya).unlink()
            except OSError:
                pass
        self._db.execute("UPDATE satir SET dosya = ?, bicim = ?, sr = ?, sure_sn = ?, boyut = ?, son_kullanim = ? WHERE id = ?",
                         (dosya, bicim, sr, sure_sn, len(ses), self.saat(), kimlik))

    def _ses_sil(self, kimlik: int) -> None:
        r = self._db.execute("SELECT dosya FROM satir WHERE id = ?", (kimlik,)).fetchone()
        if r and r[0]:
            try:
                (self.kok / "sesler" / r[0]).unlink()
            except OSError:
                pass
        self._db.execute("UPDATE satir SET dosya = NULL, bicim = NULL, boyut = 0, puan = NULL WHERE id = ?", (kimlik,))

    def _iz_yaz(self, kimlik: int, iz: list[list[int]], en_sure_sn: float | None, duygu: dict[str, Any] | None) -> None:
        from .tanima import iz_bayt
        self._db.execute("UPDATE satir SET iz = ?, iz_sayisi = ?, en_sure_sn = COALESCE(?, en_sure_sn), "
                         "duygu = COALESCE(?, duygu) WHERE id = ?",
                         (iz_bayt(iz), len(iz), en_sure_sn, json.dumps(duygu) if duygu else None, kimlik))

    def iz_ekle(self, kimlik: int, iz: list[list[int]], en_sure_sn: float | None = None,
                duygu: dict[str, Any] | None = None, ustune: bool = False) -> bool:
        """İngilizce satırın ses izi (ilk duyuluşunda). Zaten varsa `ustune` değilse dokunulmaz."""
        with self._kilit:
            r = self._db.execute("SELECT iz_sayisi FROM satir WHERE id = ?", (kimlik,)).fetchone()
            if r is None or (r[0] and not ustune) or not iz:
                return False
            self._iz_yaz(kimlik, iz, en_sure_sn, duygu)
            self._db.commit()
            return True

    def metin_duzelt(self, kimlik: int, tr: str) -> bool:
        """Kullanıcı Türkçeyi düzeltti: metin kullanıcının olur, eski ses silinir (yeniden seslendirilecek)."""
        with self._kilit:
            s = self.getir(kimlik)
            if s is None:
                return False
            self._db.execute("UPDATE satir SET tr = ?, tr_kaynak = 'kullanici', iyilestirme = NULL WHERE id = ?",
                             (tr.strip(), kimlik))
            self._ses_sil(kimlik)
            self._db.commit()
            return True

    def iyilestirildi(self, kimlik: int) -> None:
        with self._kilit:
            self._db.execute("UPDATE satir SET iyilestirme = ? WHERE id = ?", (self.saat(), kimlik))
            self._db.commit()

    def oncelik_ver(self, kimlikler: list[int]) -> None:
        """"Bu sahneyi en iyi kaliteyle hazırla": bu satırların iyileştirme işareti silinir (sıraya girer)."""
        with self._kilit:
            self._db.executemany("UPDATE satir SET iyilestirme = NULL WHERE id = ?", [(int(k),) for k in kimlikler])
            self._db.commit()

    # -- okuma --
    def ses_al(self, kimlik: int, kullan: bool = True) -> tuple[bytes, str, int] | None:
        with self._kilit:
            r = self._db.execute("SELECT dosya, bicim, sr FROM satir WHERE id = ?", (kimlik,)).fetchone()
            if not r or not r[0]:
                return None
            try:
                veri = (self.kok / "sesler" / r[0]).read_bytes()
            except OSError:
                self._ses_sil(kimlik)
                self._db.commit()
                return None
            if kullan:
                self.kullanildi(kimlik)
            return veri, r[1], int(r[2] or 24000)

    def kullanildi(self, kimlik: int) -> None:
        with self._kilit:
            self._db.execute("UPDATE satir SET son_kullanim = ?, kullanim = kullanim + 1 WHERE id = ?",
                             (self.saat(), kimlik))
            self._db.commit()

    def tum_izler(self) -> list[tuple[int, list[list[int]]]]:
        from .tanima import bayt_iz
        with self._kilit:
            return [(int(k), bayt_iz(b)) for k, b in
                    self._db.execute("SELECT id, iz FROM satir WHERE iz_sayisi > 0 AND dosya IS NOT NULL")]

    def iz_al(self, kimlik: int) -> list[list[int]]:
        from .tanima import bayt_iz
        with self._kilit:
            r = self._db.execute("SELECT iz FROM satir WHERE id = ?", (kimlik,)).fetchone()
            return bayt_iz(r[0]) if r else []

    # -- sahne grafiği --
    def gecis_ekle(self, onceki: int, sonraki: int, dt: float | None = None) -> None:
        if onceki == sonraki:
            return
        with self._kilit:
            r = self._db.execute("SELECT sayi, ort_dt FROM gecis WHERE onceki = ? AND sonraki = ?", (onceki, sonraki)).fetchone()
            if r is None:
                self._db.execute("INSERT INTO gecis VALUES (?,?,?,?)", (onceki, sonraki, 1, dt))
            else:
                n, ort = r
                yeni = dt if ort is None else (ort if dt is None else (ort * n + dt) / (n + 1))
                self._db.execute("UPDATE gecis SET sayi = ?, ort_dt = ? WHERE onceki = ? AND sonraki = ?",
                                 (n + 1, yeni, onceki, sonraki))
            self._db.commit()

    def sonrakiler(self, kimlik: int, adet: int = 3, derinlik: int = 2) -> list[dict[str, Any]]:
        """En olası sonraki satırlar (önce doğrudan geçişler, sonra onların ardılları)."""
        with self._kilit:
            sonuc: list[int] = []
            sinir = [kimlik]
            for _ in range(derinlik):
                yeni = []
                for k in sinir:
                    for (s,) in self._db.execute("SELECT sonraki FROM gecis WHERE onceki = ? ORDER BY sayi DESC LIMIT ?",
                                                 (k, adet)):
                        if s != kimlik and s not in sonuc:
                            sonuc.append(s)
                            yeni.append(s)
                if len(sonuc) >= adet:
                    break
                sinir = yeni[:1]
            return [x for x in (self.getir(k) for k in sonuc[:adet]) if x]

    # -- panel --
    def istatistik(self) -> dict[str, Any]:
        with self._kilit:
            satir, sesli, sn, boyut = self._db.execute(
                "SELECT COUNT(*), COUNT(dosya), COALESCE(SUM(CASE WHEN dosya IS NOT NULL THEN sure_sn END), 0), "
                "COALESCE(SUM(boyut), 0) FROM satir").fetchone()
            kar = self._db.execute("SELECT COALESCE(konusan, ''), COUNT(*), COUNT(dosya) FROM satir GROUP BY 1 "
                                   "ORDER BY 2 DESC LIMIT 30").fetchall()
            return {"satir": satir, "sesli": sesli, "dakika": round(float(sn) / 60, 1),
                    "boyut_mb": round(boyut / 1048576, 2),
                    "karakterler": [{"ad": a or None, "satir": n, "sesli": s} for a, n, s in kar]}

    def liste(self, ara: str = "", sayfa: int = 0, adet: int = SAYFA) -> tuple[list[dict[str, Any]], int]:
        with self._kilit:
            kosul, arg = "", []
            if ara.strip():
                kosul = "WHERE asil LIKE ? OR tr LIKE ? OR konusan LIKE ?"
                q = f"%{ara.strip()}%"
                arg = [q, q, q]
            toplam = self._db.execute(f"SELECT COUNT(*) FROM satir {kosul}", arg).fetchone()[0]
            rows = self._db.execute(f"SELECT {', '.join(ALANLAR)} FROM satir {kosul} ORDER BY son_kullanim DESC "
                                    "LIMIT ? OFFSET ?", arg + [adet, max(0, sayfa) * adet]).fetchall()
            return [self._ozet(self._satir(r)) for r in rows], toplam

    @staticmethod
    def _ozet(s: dict[str, Any] | None) -> dict[str, Any]:
        assert s is not None
        return {"id": s["id"], "asil": s["asil"], "konusan": s["konusan"], "tr": s["tr"], "tr_kaynak": s["tr_kaynak"],
                "puan": None if s["puan"] is None else round(s["puan"], 2), "sesli": s["sesli"],
                "sure_sn": None if s["sure_sn"] is None else round(s["sure_sn"], 1), "kullanim": s["kullanim"],
                "tanima": s["iz_sayisi"] > 0}

    def son_kullanilanlar(self, dakika: float) -> list[int]:
        with self._kilit:
            alt = self.saat() - dakika * 60
            return [k for (k,) in self._db.execute("SELECT id FROM satir WHERE son_kullanim >= ? OR olusma >= ? "
                                                   "ORDER BY son_kullanim", (alt, alt))]

    def iyilestirilecekler(self, adet: int = 10) -> list[dict[str, Any]]:
        """Henüz iyileştirilmemiş satırlar: puansız/düşük puanlı önce, sonra en çok kullanılan."""
        with self._kilit:
            rows = self._db.execute(f"SELECT {', '.join(ALANLAR)} FROM satir WHERE iyilestirme IS NULL AND tr != '' "
                                    "ORDER BY (puan IS NOT NULL), puan, kullanim DESC LIMIT ?", (adet,)).fetchall()
            return [x for x in (self._satir(r) for r in rows) if x]

    # -- silme ve sınır --
    def sil(self, kimlik: int) -> bool:
        with self._kilit:
            s = self.getir(kimlik)
            if s is None:
                return False
            self._ses_sil(kimlik)
            self._db.execute("DELETE FROM satir WHERE id = ?", (kimlik,))
            self._db.execute("DELETE FROM gecis WHERE onceki = ? OR sonraki = ?", (kimlik, kimlik))
            self._db.commit()
            if self._anahtarlar is not None:
                self._anahtarlar.pop(s["anahtar"], None)
            return True

    def sinirla(self, sinir_mb: float) -> list[int]:
        """Toplam ses boyutu sınırı aşıyorsa en uzun süre kullanılmayanların sesi silinir (metin ve iz kalır)."""
        with self._kilit:
            toplam = self._db.execute("SELECT COALESCE(SUM(boyut), 0) FROM satir").fetchone()[0]
            sinir = int(sinir_mb * 1048576)
            silinen: list[int] = []
            if toplam <= sinir:
                return silinen
            for k, b in self._db.execute("SELECT id, boyut FROM satir WHERE dosya IS NOT NULL ORDER BY son_kullanim").fetchall():
                if toplam <= sinir:
                    break
                self._ses_sil(k)
                toplam -= b
                silinen.append(k)
            self._db.commit()
            return silinen

    def kapat(self) -> None:
        with self._kilit:
            try:
                self._db.close()
            except sqlite3.Error:
                pass

    def oyunu_sil(self) -> None:
        self.kapat()
        shutil.rmtree(self.kok, ignore_errors=True)

    # -- kişisel yedek (PROTOKOL 21.8) --
    def disa_aktar(self, hedef: Path, oyun: str = "") -> int:
        with self._kilit:
            rows = [self._satir(r) for r in self._db.execute(f"SELECT {', '.join(ALANLAR)} FROM satir")]
            izler = dict(self._db.execute("SELECT id, iz FROM satir WHERE iz IS NOT NULL").fetchall())
            gecisler = self._db.execute("SELECT onceki, sonraki, sayi, ort_dt FROM gecis").fetchall()
        g = hedef.with_suffix(".tmp")
        with zipfile.ZipFile(g, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("bilgi.json", json.dumps({"tur": "altyazikoprusu-dublaj-hafizasi", "surum": YEDEK_SURUM,
                                                 "oyun": oyun, "not": "Kişisel yedek: yalnız kendi bilgisayarların "
                                                 "arasında taşımak içindir. Oyun seslerini/satırlarını paylaşma."},
                                                ensure_ascii=False))
            satirlar = []
            for s in rows:
                assert s is not None
                d = {k: s[k] for k in ALANLAR if k not in ("boyut", "iz_sayisi")}
                b = izler.get(s["id"])
                d["iz"] = b.hex() if b else None
                if s["dosya"]:
                    try:
                        z.write(self.kok / "sesler" / s["dosya"], f"sesler/{s['dosya']}", compress_type=zipfile.ZIP_STORED)
                    except OSError:
                        d["dosya"] = None
                satirlar.append(d)
            z.writestr("satirlar.json", json.dumps(satirlar, ensure_ascii=False))
            z.writestr("gecisler.json", json.dumps(gecisler))
        os.replace(g, hedef)
        return len(rows)

    def ice_aktar(self, kaynak: Path) -> dict[str, int]:
        """Kendi yedeğini geri yükler; aynı satırda puanı yüksek (ya da kullanıcı metni) kalır."""
        from .tanima import bayt_iz
        sonuc = {"eklenen": 0, "guncellenen": 0}
        with zipfile.ZipFile(kaynak) as z:
            bilgi = json.loads(z.read("bilgi.json"))
            if bilgi.get("tur") != "altyazikoprusu-dublaj-hafizasi" or int(bilgi.get("surum") or 0) > YEDEK_SURUM:
                raise ValueError("yedek_gecersiz")
            satirlar = json.loads(z.read("satirlar.json"))
            eski_yeni: dict[int, int] = {}
            for d in satirlar:
                if not isinstance(d, dict) or not d.get("asil"):
                    continue
                var = self.bul(d["asil"], d.get("konusan"), benzer=False)
                ses = None
                if d.get("dosya") and d.get("bicim") in BICIMLER:
                    ad = str(d["dosya"])
                    if "/" in ad or "\\" in ad or ".." in ad:
                        continue
                    try:
                        ses = z.read(f"sesler/{ad}")
                    except KeyError:
                        ses = None
                if var and var.get("puan") is not None and (d.get("puan") or 0) < var["puan"]:
                    ses = None
                kimlik = self.kaydet(d["asil"], d.get("konusan"), d.get("tr") or "", d.get("tr_kaynak") or "canli",
                                     ses, d.get("bicim") if ses else None, d.get("sr"), d.get("sure_sn"),
                                     d.get("en_sure_sn"), d.get("cinsiyet"), d.get("profil"), d.get("ayar"),
                                     d.get("puanlar"), d.get("puan") if ses else None,
                                     bayt_iz(bytes.fromhex(d["iz"])) if d.get("iz") and not (var and var.get("iz_sayisi")) else None,
                                     d.get("duygu"))
                eski_yeni[int(d.get("id") or 0)] = kimlik
                sonuc["guncellenen" if var else "eklenen"] += 1
            try:
                for a, b, n, dt in json.loads(z.read("gecisler.json")):
                    if a in eski_yeni and b in eski_yeni:
                        for _ in range(max(1, min(int(n), 20))):
                            self.gecis_ekle(eski_yeni[a], eski_yeni[b], dt)
            except KeyError:
                pass
        return sonuc
