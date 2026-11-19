# SPDX-License-Identifier: AGPL-3.0-only
"""Sunucu tarafı: ekran katmanı sürecini başlatır, durdurur, çökerse (dakikada en çok 3) yeniden başlatır."""
from __future__ import annotations

import importlib.util
import logging
import os
import subprocess
import sys
import time
from collections import deque
from typing import Any, Callable

log = logging.getLogger("kopru.katman")

YENIDEN_SINIR = 3          # dakikada en çok bu kadar (yeniden) başlatma
YENIDEN_PENCERE_SN = 60.0
DENEME_SN = 8.0            # deneme altyazısından sonra, başka sebep yoksa katman bu kadar sonra kapanır


def komut(url: str, ekran: int, pencere: int | None = None) -> list[str]:
    """Paketli programda `exe --katman ...` (calistir.py dağıtır), değilse `python -m kopru.katman ...`."""
    args = ["--url", url, "--ekran", str(ekran), "--ebeveyn", str(os.getpid())]
    if pencere:
        args += ["--pencere", str(pencere)]   # katman yalnız bu pencerenin üstüne konumlanır (PROTOKOL 11.2)
    if getattr(sys, "frozen", False):
        return [sys.executable, "--katman", *args]
    return [sys.executable, "-m", "kopru.katman", *args]


def surec_baslat(cmd: list[str]) -> Any:
    bayraklar = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    return subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, creationflags=bayraklar)


def destek_var_mi() -> bool:
    try:
        return importlib.util.find_spec("tkinter") is not None
    except (ImportError, ValueError):
        return False


def ekranlari_listele() -> list[dict[str, Any]]:
    """[{"no":1,"ad":"Ekran 1 (1920×1080)"}]; yakalama kütüphanesi yoksa tek ekran varsayılır."""
    try:
        from .. import yakalama
        out = []
        for k in yakalama.kaynaklar():
            if k["kod"].startswith("ekran:"):
                out.append({"no": int(k["kod"].split(":")[1]), "ad": k["ad"]})
        if out:
            return out
    except Exception:   # noqa: BLE001
        pass
    return [{"no": 1, "ad": "Ekran 1"}]


class KatmanYonetici:
    def __init__(self, ayar_al: Callable[[], dict[str, Any]], yayin: Any, calisiyor: Callable[[], bool],
                 kapi_al: Callable[[], int], baslatici: Callable[[list[str]], Any] | None = None,
                 destek: Callable[[], bool] | None = None, saat: Callable[[], float] = time.monotonic) -> None:
        self.ayar_al, self.yayin, self.calisiyor, self.kapi_al = ayar_al, yayin, calisiyor, kapi_al
        self.baslatici = baslatici or surec_baslat
        self.destek = destek or destek_var_mi
        self.saat = saat
        self.surec: Any = None
        self._ekran: int | None = None
        self._pencere: int | None = None
        self._baslamalar: deque[float] = deque()
        self.vazgecildi = False       # üst üste çöktü: kullanıcı yeniden isteyene dek denenmez
        self.deneme_bitis = 0.0
        self.son_hata: str | None = None

    # -- durum --
    def acik(self) -> bool:
        return self.surec is not None and self.surec.poll() is None

    def istenen(self) -> bool:
        deneme = self.saat() < self.deneme_bitis
        return deneme or (self.ayar_al().get("gosterim") == "bilgisayar" and bool(self.calisiyor()))

    def istenen_pencere(self) -> int | None:
        """`kaynak = "pencere:<hwnd>"` ise hwnd (yalnız Windows'ta; katman o pencerenin üstüne konur)."""
        if sys.platform != "win32":
            return None
        from .. import yakalama
        return yakalama.pencere_kodu(str(self.ayar_al().get("kaynak") or ""))

    def url(self) -> str:
        return f"http://127.0.0.1:{self.kapi_al()}/kopru/akis"

    # -- süreç --
    def _baslat(self) -> bool:
        if not self.destek():
            self.son_hata = "katman_destek_yok"
            return False
        simdi = self.saat()
        while self._baslamalar and simdi - self._baslamalar[0] > YENIDEN_PENCERE_SN:
            self._baslamalar.popleft()
        if len(self._baslamalar) >= YENIDEN_SINIR:
            self.vazgecildi, self.son_hata = True, "katman_coktu"
            log.warning("Ekran katmanı dakikada %d kezden çok kapandı; yeniden denenmiyor", YENIDEN_SINIR)
            return False
        self._baslamalar.append(simdi)
        self._ekran = int(self.ayar_al().get("katman_ekran", 1))
        self._pencere = self.istenen_pencere()
        try:
            self.surec = self.baslatici(komut(self.url(), self._ekran, self._pencere))
        except Exception as e:   # noqa: BLE001
            log.warning("Ekran katmanı başlatılamadı: %s", e)
            self.surec, self.son_hata = None, "katman_destek_yok"
            return False
        self.son_hata = None
        return True

    def durdur_surec(self) -> None:
        s, self.surec = self.surec, None
        if s is None:
            return
        try:
            self.yayin.yayinla("katman-kapat", {})
        except Exception:   # noqa: BLE001
            pass
        try:
            if s.poll() is None:
                s.terminate()
        except Exception:   # noqa: BLE001
            pass

    def senkronla(self, kullanici_istegi: bool = False) -> None:
        """İstenen duruma getirir (başlat/durdur/ekran değişti). Çöküp vazgeçilmişse yalnız kullanıcı isteği açar."""
        if kullanici_istegi:
            self.vazgecildi = False
            self._baslamalar.clear()
        if not self.istenen():
            self.durdur_surec()
            return
        if self.acik():
            if self._ekran != int(self.ayar_al().get("katman_ekran", 1)) \
                    or self._pencere != self.istenen_pencere():
                self.durdur_surec()
                self._baslat()
            return
        if not self.vazgecildi:
            self._baslat()

    def izle(self) -> None:
        """Periyodik: çöken süreci yeniden başlatır (sınırlı), deneme süresi bitince kapatır."""
        if self.surec is not None and self.surec.poll() is not None:
            self.surec = None
        self.senkronla()

    def dene(self) -> bool:
        """Deneme altyazısı için katmanı (gerekirse) açar; açıksa True."""
        self.deneme_bitis = self.saat() + DENEME_SN
        self.senkronla(kullanici_istegi=True)
        return self.acik()

    def kapat(self) -> None:
        self.deneme_bitis = 0.0
        self.durdur_surec()

    def bilgi(self) -> dict[str, Any]:
        return {"destek": bool(self.destek()), "acik": self.acik(), "hata": self.son_hata}
