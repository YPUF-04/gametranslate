# SPDX-License-Identifier: AGPL-3.0-only
"""İşçi tarafı: stdin'den komut okur, işi sırayla yapar, stdout'a yanıt/olay yazar (PROTOKOL 14.2).

Komutlar tek bir iş parçacığında SIRAYLA çalışır (ekran kartı tek iş). `iptal`, `canli_durdur` ve
`kapat` ise okuyucu iş parçacığında HEMEN işlenir (uzun bir işi yarıda kesebilsin diye).
"""
from __future__ import annotations

import logging
import os
import queue
import sys
import threading
from typing import Any, BinaryIO, Callable

from . import SURUM, protokol

log = logging.getLogger("kopru.isci")
ANINDA = ("iptal", "canli_durdur", "kapat", "canli_son")   # canli_son: sıradaki seslendirmeyi beklemez


class IsciHatasi(Exception):
    def __init__(self, kod: str, ayrinti: str = "") -> None:
        super().__init__(kod)
        self.kod = kod
        self.ayrinti = ayrinti


class Iptal(Exception):
    pass


class Is:
    """Süren tek bir komutun bağlamı: ilerleme bildirir, iptal edildi mi söyler."""

    def __init__(self, no: int, gonder: Callable[[dict[str, Any]], None]) -> None:
        self.no = no
        self._gonder = gonder
        self.iptal = threading.Event()

    def ilerleme(self, yuzde: float, mesaj: str = "", **ek: Any) -> None:
        self.denetle()
        self._gonder({"olay": "ilerleme", "no": self.no, "yuzde": round(float(yuzde), 1), "mesaj": mesaj, **ek})

    def denetle(self) -> None:
        if self.iptal.is_set():
            raise Iptal()


class IsciSunucu:
    def __init__(self, giris: BinaryIO, cikis: BinaryIO, isleyici: Any, anahtar: str,
                 bilgi: Callable[[], dict[str, Any]] | None = None) -> None:
        self.giris = giris
        self.cikis = cikis
        self.isleyici = isleyici
        self.anahtar = anahtar
        self.bilgi = bilgi or (lambda: {})
        self._kilit = threading.Lock()
        self._kuyruk: queue.Queue = queue.Queue()
        self._isler: dict[int, Is] = {}
        self._bitti = threading.Event()
        if hasattr(isleyici, "gonder_bagla"):
            isleyici.gonder_bagla(self.gonder)

    def gonder(self, nesne: dict[str, Any]) -> None:
        veri = protokol.kodla(nesne)
        with self._kilit:
            try:
                self.cikis.write(veri)
                self.cikis.flush()
            except (OSError, ValueError):   # ana program gitti
                self._bitti.set()

    def _yanit(self, no: int, sonuc: Any = None, hata: str | None = None, ayrinti: str = "") -> None:
        if hata:
            self.gonder({"no": no, "tamam": False, "hata": hata, "ayrinti": ayrinti[:500]})
        else:
            self.gonder({"no": no, "tamam": True, "sonuc": sonuc if sonuc is not None else {}})

    def _calistir(self, no: int, komut: str, veri: dict[str, Any]) -> None:
        is_ = self._isler.setdefault(no, Is(no, self.gonder))
        try:
            fn = getattr(self.isleyici, "k_" + komut, None)
            if fn is None:
                raise IsciHatasi("dublaj_isci_komut", komut)
            is_.denetle()
            self._yanit(no, fn(veri, is_))
        except Iptal:
            self._yanit(no, hata="iptal")
        except IsciHatasi as e:
            self._yanit(no, hata=e.kod, ayrinti=e.ayrinti)
        except MemoryError:
            self._yanit(no, hata="dublaj_bellek", ayrinti="MemoryError")
        except Exception as e:      # noqa: BLE001 — işçi tek komut yüzünden ölmesin
            ad = type(e).__name__
            kod = "dublaj_bellek" if "OutOfMemory" in ad or "out of memory" in str(e).lower() else "dublaj_isci_hata"
            log.exception("Komut başarısız: %s", komut)
            self._yanit(no, hata=kod, ayrinti=f"{ad}: {e}")
        finally:
            self._isler.pop(no, None)

    def _is_dongusu(self) -> None:
        while True:
            oge = self._kuyruk.get()
            if oge is None:
                return
            self._calistir(*oge)

    def calis(self) -> None:
        self.gonder({"olay": "merhaba", "anahtar": self.anahtar, "surum": SURUM, "pid": os.getpid(), **self.bilgi()})
        isci = threading.Thread(target=self._is_dongusu, daemon=True, name="isci-is")
        isci.start()
        try:
            for satir in self.giris:
                if self._bitti.is_set():
                    break
                if not satir.strip():
                    continue
                try:
                    v = protokol.coz(satir)
                except protokol.ProtokolHatasi as e:
                    self.gonder({"olay": "gunluk", "seviye": "uyari", "mesaj": f"bozuk satır: {e}"})
                    continue
                no, komut = v.get("no"), v.get("komut")
                if not isinstance(no, int) or not isinstance(komut, str):
                    continue
                if komut == "iptal":
                    hedef = self._isler.get(v.get("hedef")) if isinstance(v.get("hedef"), int) else None
                    if hedef:
                        hedef.iptal.set()
                    else:
                        for i in list(self._isler.values()):
                            i.iptal.set()
                    self._yanit(no, {"iptal": True})
                elif komut == "kapat":
                    self._yanit(no, {})
                    break
                elif komut in ANINDA:
                    self._calistir(no, komut, v)
                else:
                    self._isler[no] = Is(no, self.gonder)
                    self._kuyruk.put((no, komut, v))
        finally:
            for i in list(self._isler.values()):
                i.iptal.set()
            if hasattr(self.isleyici, "kapat"):
                try:
                    self.isleyici.kapat()
                except Exception:   # noqa: BLE001
                    pass
            self._kuyruk.put(None)
            isci.join(timeout=5)


def ana() -> None:
    """Gerçek işçi: stdout'u kanal olarak ayırır, kütüphanelerin `print`'i stderr'e gider."""
    anahtar = os.environ.pop("KOPRU_ISCI_ANAHTAR", "")
    kanal = os.fdopen(os.dup(sys.stdout.fileno()), "wb", buffering=0)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())   # print() artık stderr'e
    sys.stdout = sys.stderr
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s isci %(levelname)s %(message)s")
    if os.environ.get("KOPRU_ISCI_SAHTE") == "1":
        from .sahte import SahteIsleyici
        isleyici: Any = SahteIsleyici()
    else:
        from .motorlar import GercekIsleyici
        isleyici = GercekIsleyici()
    IsciSunucu(sys.stdin.buffer, kanal, isleyici, anahtar, isleyici.cihaz_bilgisi).calis()
    os._exit(0)   # torch/CUDA iş parçacıkları kapanışı bekletmesin
