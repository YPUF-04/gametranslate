# SPDX-License-Identifier: AGPL-3.0-only
"""Ses profili (PROTOKOL 14.5): KULLANICI İZİN VERİRSE her karakterin en iyi ses örnekleri bu
bilgisayarda, oyunun klasöründe saklanır. Böylece yeterince ses toplanınca oyunda diyalog sesi 0
yapılsa bile karakterler kendi sesleriyle konuşur.

Bu, "ses örneği diske yazılmaz" kuralının TEK istisnasıdır: izinle, yalnız yerel, panelden silinebilir.
Hiçbir yere gönderilmez. Konum: `<ayar_dizini>/oyunlar/<oyun>/sesler/`.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable

EN_COK_KLIP = 3            # karakter başına
EN_COK_KLIP_SN = 10.0
KAYIT_ARALIGI_SN = 30.0    # aynı karakter için en sık bu aralıkla diske yazılır


def _guvenli_ad(ad: str) -> str:
    taban = re.sub(r"[^a-z0-9]+", "-", ad.lower()).strip("-")[:40] or "konusan"
    return f"{taban}-{hashlib.sha1(ad.encode('utf-8')).hexdigest()[:8]}"


class SesProfilleri:
    def __init__(self, kok: Path, saat: Callable[[], float] = time.monotonic) -> None:
        self.kok = kok
        self.saat = saat
        self._son: dict[str, float] = {}

    def _dizin_yolu(self) -> Path:
        return self.kok / "dizin.json"

    def _dizin(self) -> dict[str, Any]:
        try:
            v = json.loads(self._dizin_yolu().read_text(encoding="utf-8"))
            return v if isinstance(v, dict) else {}
        except (OSError, ValueError):
            return {}

    def _dizin_yaz(self, d: dict[str, Any]) -> None:
        self.kok.mkdir(parents=True, exist_ok=True)
        g = self._dizin_yolu().with_suffix(".tmp")
        g.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        os.replace(g, self._dizin_yolu())

    def liste(self) -> list[dict[str, Any]]:
        out = []
        for ad, v in self._dizin().items():
            out.append({"ad": ad, "sure_sn": round(sum(k["sure"] for k in v.get("klipler", [])), 1),
                        "klip": len(v.get("klipler", [])), "tarih": v.get("tarih")})
        return sorted(out, key=lambda x: x["ad"].lower())

    def kaydet(self, ad: str, pcm: Any, sr: int) -> bool:
        """Yeni örnek, karakterin en kısa klibinden uzunsa onun yerine geçer. Yazıldıysa True."""
        from . import dsp
        if not ad or len(ad) > 80:
            return False
        simdi = self.saat()
        if simdi - self._son.get(ad, -1e9) < KAYIT_ARALIGI_SN:
            return False
        sure = min(len(pcm) / sr, EN_COK_KLIP_SN)
        d = self._dizin()
        v = d.setdefault(ad, {"dosya": _guvenli_ad(ad), "klipler": []})
        klipler = v["klipler"]
        if len(klipler) >= EN_COK_KLIP:
            en_kisa = min(range(len(klipler)), key=lambda i: klipler[i]["sure"])
            if klipler[en_kisa]["sure"] >= sure:
                return False
            no = klipler[en_kisa]["no"]
            klipler.pop(en_kisa)
        else:
            no = max([k["no"] for k in klipler], default=-1) + 1
        self.kok.mkdir(parents=True, exist_ok=True)
        yol = self.kok / f"{v['dosya']}-{no}.wav"
        g = yol.with_suffix(".tmp")
        g.write_bytes(dsp.wav_bayt(dsp.mono_float(pcm)[:int(EN_COK_KLIP_SN * sr)], sr))
        os.replace(g, yol)
        klipler.append({"no": no, "sure": round(sure, 2), "sr": int(sr)})
        v["tarih"] = time.strftime("%Y-%m-%d")
        self._dizin_yaz(d)
        self._son[ad] = simdi
        return True

    def yukle(self) -> dict[str, tuple[Any, int]]:
        """{ad: (birleşik pcm, sr)}; en çok ~12 sn."""
        import numpy as np
        import wave
        out: dict[str, tuple[Any, int]] = {}
        for ad, v in self._dizin().items():
            parcalar, sr = [], 24000
            for k in sorted(v.get("klipler", []), key=lambda k: -k["sure"]):
                yol = self.kok / f"{v['dosya']}-{k['no']}.wav"
                try:
                    with wave.open(str(yol), "rb") as w:
                        sr = w.getframerate()
                        parcalar.append(np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768)
                except (OSError, wave.Error, EOFError):
                    continue
            if parcalar:
                pcm = np.concatenate(parcalar)[:int(12 * sr)]
                out[ad] = (pcm, sr)
        return out

    def sil(self, ad: str | None = None) -> int:
        d = self._dizin()
        silinen = 0
        for a in ([ad] if ad else list(d)):
            v = d.pop(a, None)
            if not v:
                continue
            for k in v.get("klipler", []):
                try:
                    (self.kok / f"{v['dosya']}-{k['no']}.wav").unlink()
                except OSError:
                    pass
            silinen += 1
        if d:
            self._dizin_yaz(d)
        else:
            try:
                self._dizin_yolu().unlink()
            except OSError:
                pass
        return silinen
