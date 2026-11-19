# SPDX-License-Identifier: AGPL-3.0-only
"""Oyun başına çeviri hafızası (sqlite) ve yeni terim önerileri.

İZİN: hafiza_izni true değilse diske HİÇBİR ŞEY yazılmaz; kayıtlar yalnız RAM'de durur.
Yalnız metin çiftleri tutulur (anahtar, ekran görüntüsü, ses yok).
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable

from . import oyunlar
from .onbellek import normallestir, sqlite_ac

log = logging.getLogger("kopru.hafiza")

DISK_HATA_BEKLEME_SN = 30.0
EN_COK_ONERI = 500          # kontrolsüz büyümesin; kabul/ret ile eritilir
ONCELIK = {"motor": 1, "paket": 2, "kullanici": 3}  # kullanıcı düzeltmesi her zaman kazanır
_SAYAC_TOPLU = 25


def _yol(kod: str) -> Path:
    return oyunlar.oyun_dizini(kod) / "hafiza.sqlite"


def _satir(asil: str, ceviri: str, kaynak: str, motor: str | None, sayac: int, tarih: str) -> dict[str, Any]:
    return {"asil": asil, "ceviri": ceviri, "kaynak": kaynak, "motor": motor,
            "sayac": sayac, "tarih": tarih}


def _salt_oku(kod: str) -> list[dict[str, Any]]:
    """Dosya varsa satırları okur; dosya yoksa oluşturmaz."""
    yol = _yol(kod)
    if not yol.exists():
        return []
    try:
        # as_uri: boşluk, Türkçe harf, '#', '%' içeren klasör adları için doğru kaçışlı adres
        db = sqlite3.connect(f"{yol.resolve().as_uri()}?mode=ro", uri=True, timeout=1.0)
        try:
            return [_satir(*r) for r in db.execute(
                "SELECT asil, ceviri, kaynak, motor, sayac, tarih FROM h")]
        finally:
            db.close()
    except sqlite3.Error:
        return []


def dosyada_say(kod: str) -> int:
    return len(_salt_oku(kod)) if oyunlar.gecerli_kod(kod) else 0


def dosyadan_oku(kod: str) -> list[dict[str, Any]]:
    return _salt_oku(kod) if oyunlar.gecerli_kod(kod) else []


class Hafiza:
    def __init__(self, oyun_kodu: str, izin: Callable[[], bool] = lambda: False) -> None:
        self.kod = oyun_kodu
        self._izin = izin
        self._kilit = threading.RLock()
        self._ram: dict[str, dict[str, Any]] = {}
        self._db: sqlite3.Connection | None = None
        self._bekleyen = 0
        self._disk_hatasi = -1e9    # son disk hatasının zamanı: kısa süre yeniden denenmez
        for r in _salt_oku(oyun_kodu):
            n = normallestir(r["asil"])
            if n:
                self._ram[n] = r

    # -- disk (yalnız izinle) --
    def _disk_hata(self, e: Exception) -> None:
        """Disk sorunu (kilit, dolu disk, bozuk dosya) çeviriyi durdurmaz: kayıtlar RAM'de kalır."""
        log.warning("Hafıza dosyasına yazılamadı (%s); RAM ile devam", type(e).__name__)
        self._disk_hatasi = time.monotonic()
        self._kapat_db()

    def _db_hazir(self) -> sqlite3.Connection | None:
        if not self._izin() or time.monotonic() - self._disk_hatasi < DISK_HATA_BEKLEME_SN:
            return None
        if self._db is None:
            try:
                db = sqlite_ac(_yol(self.kod),
                               "CREATE TABLE IF NOT EXISTS h (asil TEXT NOT NULL, ceviri TEXT NOT NULL,"
                               " kaynak TEXT NOT NULL, motor TEXT, sayac INTEGER NOT NULL, tarih TEXT NOT NULL,"
                               " n TEXT PRIMARY KEY)")
                # izin gelmeden önce RAM'de birikenler şimdi kalıcılaşır
                db.executemany(
                    "INSERT OR REPLACE INTO h (asil, ceviri, kaynak, motor, sayac, tarih, n)"
                    " VALUES (?,?,?,?,?,?,?)",
                    [(r["asil"], r["ceviri"], r["kaynak"], r["motor"], r["sayac"], r["tarih"], n)
                     for n, r in self._ram.items()])
                db.commit()
            except (sqlite3.Error, OSError) as e:
                self._disk_hata(e)
                return None
            self._db = db
        return self._db

    def _diske(self, n: str, r: dict[str, Any], commit: bool = True) -> None:
        db = self._db_hazir()
        if db is None:
            return
        try:
            db.execute("INSERT OR REPLACE INTO h (asil, ceviri, kaynak, motor, sayac, tarih, n)"
                       " VALUES (?,?,?,?,?,?,?)",
                       (r["asil"], r["ceviri"], r["kaynak"], r["motor"], r["sayac"], r["tarih"], n))
            if commit:
                db.commit()
        except sqlite3.Error as e:
            self._disk_hata(e)

    # -- okuma/yazma --
    def bul(self, asil: str) -> tuple[str, str] | None:
        n = normallestir(asil)
        with self._kilit:
            r = self._ram.get(n)
            if r is None:
                return None
            r["sayac"] += 1
            if self._db is not None and self._izin():
                try:
                    self._db.execute("UPDATE h SET sayac=? WHERE n=?", (r["sayac"], n))
                    self._bekleyen += 1
                    if self._bekleyen >= _SAYAC_TOPLU:
                        self._db.commit()
                        self._bekleyen = 0
                except sqlite3.Error as e:
                    self._disk_hata(e)
            return r["ceviri"], r["kaynak"]

    def _koy(self, asil: str, ceviri: str, kaynak: str, motor: str | None, commit: bool) -> bool:
        asil, ceviri = asil.strip(), ceviri.strip()
        n = normallestir(asil)
        if not n or not ceviri or kaynak not in ONCELIK:
            return False
        var = self._ram.get(n)
        if var is not None:
            if ONCELIK[var["kaynak"]] > ONCELIK[kaynak]:
                return False  # kullanıcı düzeltmesi motoru/paketi, paket motoru yener
            if var["ceviri"] == ceviri and var["kaynak"] == kaynak:
                return False
        r = _satir(asil, ceviri, kaynak, motor, var["sayac"] if var else 0, date.today().isoformat())
        self._ram[n] = r
        self._diske(n, r, commit)
        return True

    def kaydet(self, asil: str, ceviri: str, kaynak: str = "motor", motor: str | None = None) -> bool:
        """Kaydeder; daha öncelikli kayıt varsa dokunmaz ve False döner."""
        with self._kilit:
            return self._koy(asil, ceviri, kaynak, motor, True)

    def kaydet_cok(self, ciftler: list[tuple[str, str]], kaynak: str) -> tuple[int, int]:
        """(eklenen, atlanan). Tek işlemde yazar."""
        eklenen = atlanan = 0
        with self._kilit:
            for asil, ceviri in ciftler:
                if self._koy(asil, ceviri, kaynak, None, False):
                    eklenen += 1
                else:
                    atlanan += 1
            if self._db is not None:
                try:
                    self._db.commit()
                except sqlite3.Error as e:
                    self._disk_hata(e)
        return eklenen, atlanan

    def say(self) -> int:
        with self._kilit:
            return len(self._ram)

    def kalici_mi(self) -> bool:
        return self._db is not None and self._izin()

    def hepsi(self) -> list[dict[str, Any]]:
        with self._kilit:
            return sorted((dict(r) for r in self._ram.values()),
                          key=lambda r: (-ONCELIK[r["kaynak"]], -r["sayac"], r["asil"]))

    def temizle(self) -> None:
        """RAM'i ve (varsa) diskteki dosyayı siler; izinden bağımsız her zaman yapılabilir."""
        with self._kilit:
            self._ram.clear()
            self._kapat_db()
            yol = _yol(self.kod)
            for ek in ("", "-journal", "-wal", "-shm"):
                try:
                    Path(str(yol) + ek).unlink()
                except OSError:
                    pass

    def _kapat_db(self) -> None:
        if self._db is not None:
            try:
                self._db.commit()
                self._db.close()
            except sqlite3.Error:
                pass
            self._db = None

    def kapat(self) -> None:
        with self._kilit:
            self._kapat_db()


class OneriDeposu:
    """Motorun önerdiği yeni terimler. İzin yoksa yalnız RAM'de durur."""

    def __init__(self, oyun_kodu: str, izin: Callable[[], bool] = lambda: False) -> None:
        self.kod = oyun_kodu
        self._izin = izin
        self._oneriler: dict[str, str] = {}
        self._reddedilen: set[str] = set()
        try:
            v = json.loads((oyunlar.oyun_dizini(oyun_kodu) / "oneriler.json").read_text(encoding="utf-8"))
            for t in v.get("oneriler", []):
                self._oneriler[str(t["asil"])] = str(t["ceviri"])
            self._reddedilen = {str(x) for x in v.get("reddedilen", [])}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass

    def _diske(self) -> None:
        if not self._izin():
            return
        try:
            oyunlar._yaz_json(oyunlar.oyun_dizini(self.kod) / "oneriler.json", {
                "oneriler": [{"asil": a, "ceviri": c} for a, c in self._oneriler.items()],
                "reddedilen": sorted(self._reddedilen)})
        except OSError:   # öneri kaydı çeviriyi asla durdurmaz
            log.warning("Öneriler yazılamadı")

    def ekle(self, asil: str, ceviri: str) -> bool:
        asil, ceviri = asil.strip(), ceviri.strip()
        k = asil.casefold()
        if not asil or not ceviri or k in self._reddedilen or \
                any(k == a.casefold() for a in self._oneriler):
            return False
        if len(self._oneriler) >= EN_COK_ONERI:
            return False
        self._oneriler[asil] = ceviri
        self._diske()
        return True

    def liste(self) -> list[dict[str, str]]:
        return [{"asil": a, "ceviri": c} for a, c in self._oneriler.items()]

    def al(self, asil: str) -> str | None:
        """Öneriyi listeden çıkarır; çevirisini döndürür (yoksa None)."""
        for a in list(self._oneriler):
            if a.casefold() == asil.strip().casefold():
                c = self._oneriler.pop(a)
                self._diske()
                return c
        return None

    def reddet(self, asil: str) -> None:
        self._reddedilen.add(asil.strip().casefold())
        self._diske()

    def bitir(self) -> None:
        self._diske()
