# SPDX-License-Identifier: AGPL-3.0-only
"""Çeviri önbelleği (sqlite). Anahtar motordan bağımsızdır."""
from __future__ import annotations

import logging
import re
import sqlite3
import threading
import time
from pathlib import Path

_BOSLUK = re.compile(r"\s+")
_KENAR = re.compile(r"^[\W_]+|[\W_]+$", re.UNICODE)


def normallestir(metin: str) -> str:
    """Boşlukları sadeleştirir, kenardaki noktalama gürültüsünü ve büyük/küçük farkını atar."""
    m = _BOSLUK.sub(" ", metin).strip()
    m = _KENAR.sub("", m).casefold()
    return m


log = logging.getLogger("kopru.onbellek")


def sqlite_ac(yol: Path | str, tablo_sql: str) -> sqlite3.Connection:
    """sqlite dosyasını açar; bozuksa kopyasını saklayıp temiz bir dosya kurar, olmazsa RAM'e düşer."""
    ram = str(yol) == ":memory:"
    if not ram:
        Path(yol).parent.mkdir(parents=True, exist_ok=True)
    for deneme in range(2):
        db = None
        try:
            db = sqlite3.connect(str(yol), check_same_thread=False, timeout=5)
            db.execute(tablo_sql)
            db.commit()
            return db
        except sqlite3.Error:
            if db is not None:
                try:
                    db.close()
                except sqlite3.Error:
                    pass
            if ram or deneme == 1:
                break
            log.warning("%s bozuk görünüyor; yedeklenip yeniden kuruluyor", Path(yol).name)
            p = Path(yol)
            try:
                p.replace(p.with_name(p.name + f".bozuk-{int(time.time())}"))
            except OSError:
                break
            for ek in ("-journal", "-wal", "-shm"):
                try:
                    Path(str(p) + ek).unlink()
                except OSError:
                    pass
    log.warning("%s açılamadı; yalnız bellekte çalışılacak", Path(str(yol)).name)
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute(tablo_sql)
    return db


class Onbellek:
    def __init__(self, yol: Path | str, azami: int = 5000) -> None:
        self.azami = azami
        self._kilit = threading.Lock()
        self._kapali = False
        self._db = sqlite_ac(yol, "CREATE TABLE IF NOT EXISTS c (k TEXT PRIMARY KEY, metin TEXT NOT NULL,"
                                  " aciklama TEXT, son REAL NOT NULL)")
        try:
            self._db.execute("PRAGMA synchronous=OFF")   # önbellek harcanabilir: her isabette disk beklenmez
        except sqlite3.Error:
            pass

    @staticmethod
    def _anahtar(metin: str, kaynak: str, hedef: str, oyun: str, aciklama: bool) -> str:
        return "\x1f".join((normallestir(metin), kaynak, hedef, oyun, "1" if aciklama else "0"))

    def al(self, metin: str, kaynak: str, hedef: str, oyun: str,
           aciklama: bool = False) -> tuple[str, str | None] | None:
        k = self._anahtar(metin, kaynak, hedef, oyun, aciklama)
        with self._kilit:
            if self._kapali:
                return None
            try:
                satir = self._db.execute("SELECT metin, aciklama FROM c WHERE k=?", (k,)).fetchone()
                if satir:
                    self._db.execute("UPDATE c SET son=? WHERE k=?", (time.time(), k))
                    self._db.commit()
                    return satir[0], satir[1]
            except sqlite3.Error:   # önbellek hatası çeviriyi durdurmaz: yokmuş gibi davranılır
                log.warning("Önbellek okunamadı")
        return None

    def koy(self, metin: str, kaynak: str, hedef: str, oyun: str, ceviri: str,
            aciklama_metni: str | None = None, aciklama: bool = False) -> None:
        k = self._anahtar(metin, kaynak, hedef, oyun, aciklama)
        with self._kilit:
            if self._kapali:
                return
            try:
                self._db.execute("INSERT OR REPLACE INTO c VALUES (?,?,?,?)",
                                 (k, ceviri, aciklama_metni, time.time()))
                n = self._db.execute("SELECT COUNT(*) FROM c").fetchone()[0]
                if n > self.azami:  # en eski %10'u at
                    self._db.execute(
                        "DELETE FROM c WHERE k IN (SELECT k FROM c ORDER BY son ASC LIMIT ?)",
                        (max(1, self.azami // 10),))
                self._db.commit()
            except sqlite3.Error:
                log.warning("Önbelleğe yazılamadı")

    def boyut(self) -> int:
        with self._kilit:
            if self._kapali:
                return 0
            return self._db.execute("SELECT COUNT(*) FROM c").fetchone()[0]

    def kapat(self) -> None:
        with self._kilit:
            if not self._kapali:
                self._kapali = True
                try:
                    self._db.close()
                except sqlite3.Error:
                    pass
