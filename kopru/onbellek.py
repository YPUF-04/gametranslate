# SPDX-License-Identifier: AGPL-3.0-only
"""Çeviri önbelleği (sqlite). Anahtar motordan bağımsızdır."""
from __future__ import annotations

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


class Onbellek:
    def __init__(self, yol: Path | str, azami: int = 5000) -> None:
        self.azami = azami
        if str(yol) != ":memory:":   # RAM önbelleği: diske hiçbir şey yazılmaz
            Path(yol).parent.mkdir(parents=True, exist_ok=True)
        self._kilit = threading.Lock()
        self._db = sqlite3.connect(str(yol), check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS c (k TEXT PRIMARY KEY, metin TEXT NOT NULL,"
            " aciklama TEXT, son REAL NOT NULL)")
        self._db.commit()

    @staticmethod
    def _anahtar(metin: str, kaynak: str, hedef: str, oyun: str, aciklama: bool) -> str:
        return "\x1f".join((normallestir(metin), kaynak, hedef, oyun, "1" if aciklama else "0"))

    def al(self, metin: str, kaynak: str, hedef: str, oyun: str,
           aciklama: bool = False) -> tuple[str, str | None] | None:
        k = self._anahtar(metin, kaynak, hedef, oyun, aciklama)
        with self._kilit:
            satir = self._db.execute("SELECT metin, aciklama FROM c WHERE k=?", (k,)).fetchone()
            if satir:
                self._db.execute("UPDATE c SET son=? WHERE k=?", (time.time(), k))
                self._db.commit()
                return satir[0], satir[1]
        return None

    def koy(self, metin: str, kaynak: str, hedef: str, oyun: str, ceviri: str,
            aciklama_metni: str | None = None, aciklama: bool = False) -> None:
        k = self._anahtar(metin, kaynak, hedef, oyun, aciklama)
        with self._kilit:
            self._db.execute("INSERT OR REPLACE INTO c VALUES (?,?,?,?)",
                             (k, ceviri, aciklama_metni, time.time()))
            n = self._db.execute("SELECT COUNT(*) FROM c").fetchone()[0]
            if n > self.azami:  # en eski %10'u at
                self._db.execute(
                    "DELETE FROM c WHERE k IN (SELECT k FROM c ORDER BY son ASC LIMIT ?)",
                    (max(1, self.azami // 10),))
            self._db.commit()

    def boyut(self) -> int:
        with self._kilit:
            return self._db.execute("SELECT COUNT(*) FROM c").fetchone()[0]

    def kapat(self) -> None:
        self._db.close()
