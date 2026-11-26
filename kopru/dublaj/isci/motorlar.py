# SPDX-License-Identifier: AGPL-3.0-only
"""İşçinin gerçek motorları: ayırma (HT-Demucs-ft), yazıya çevirme (faster-whisper), seslendirme
(Chatterbox çok dilli / Pocket), konuşmacı izi, karıştırma, ffmpeg, canlı yakalama/çalma.

Ağır paketler (torch, chatterbox, demucs, faster_whisper, soundfile...) YALNIZ gerektiğinde içe
aktarılır. Bu dosya testlerde içe aktarılabilir; gerçek modeller dublaj paketinde çalışır.
Video modunda dosyalar yalnız ana programın verdiği iş klasörüne yazılır; canlı modda hiçbir ses diske yazılmaz.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Callable

import numpy as np

from . import mantik, protokol
from .sunucu import IsciHatasi, Is

log = logging.getLogger("kopru.isci")

DEMUCS_MODEL = "htdemucs_ft"
DEMUCS_SR = 44100
STT_SR = 16000
TTS_REF_SR = 24000
WHISPER_NORMAL = "large-v3-turbo"
WHISPER_HAFIF = "small"
# Yerleşik yedek sesler (karakterin sesi henüz yakalanamadıysa; cinsiyete göre). VCTK derlemi (Edinburgh
# Üniversitesi, CC BY 4.0), Kyutai'nin tts-voices deposundaki temizlenmiş kayıtlar; sürümü sabit (bkz. THIRD-PARTY-NOTICES).
HAZIR_SES_DEPO = "kyutai/tts-voices"
HAZIR_SES_SURUM = "323332d33f997de8394f24a193e1a76df720e01a"
HAZIR_SESLER = {"k": "vctk/p228_023_enhanced.wav", "e": "vctk/p226_023_enhanced.wav"}
KOSUL_ONBELLEK = 8        # Chatterbox konuşmacı koşulları (prepare_conditionals pahalı): son 8 ses bellekte
BLOK_SN = 60.0            # uzun videolarda ayırma blok boyu (RAM ve VRAM sınırlı kalsın)
BLOK_PAY_SN = 2.0         # blok kenarlarında bağlam payı


def _ffmpeg() -> str:
    yol = os.environ.get("KOPRU_FFMPEG")
    if yol and os.path.exists(yol):
        return yol
    try:
        import imageio_ffmpeg  # macOS/Linux dublaj paketinde
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    yol = shutil.which("ffmpeg")
    if not yol:
        raise IsciHatasi("dublaj_ffmpeg_yok", "ffmpeg bulunamadı")
    return yol


def _calistir(komut: list[str], is_: Is | None = None, sure_sn: float = 0.0) -> None:
    """ffmpeg'i çalıştırır; `-progress pipe:1` çıktısından ilerleme bildirir, iptal edilirse durdurur."""
    bayrak = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    s = subprocess.Popen(komut, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                         text=True, errors="replace", creationflags=bayrak)
    hata_satirlari: list[str] = []

    def hata_oku() -> None:
        assert s.stderr is not None
        for satir in s.stderr:
            hata_satirlari.append(satir.rstrip())
            del hata_satirlari[:-20]
    threading.Thread(target=hata_oku, daemon=True).start()
    assert s.stdout is not None
    for satir in s.stdout:
        if is_ is not None:
            if is_.iptal.is_set():
                s.kill()
                break
            if satir.startswith("out_time_ms=") and sure_sn > 0:
                try:
                    is_.ilerleme(min(99.0, int(satir.split("=")[1]) / 1e6 / sure_sn * 100))
                except (ValueError, Exception):
                    pass
    kod = s.wait()
    if is_ is not None:
        is_.denetle()
    if kod != 0:
        raise IsciHatasi("dublaj_ffmpeg_hata", " | ".join(hata_satirlari[-3:]))


def _ses_oku(yol: str) -> tuple[np.ndarray, int]:
    import soundfile as sf
    veri, sr = sf.read(yol, dtype="float32", always_2d=True)
    return veri.T.copy(), int(sr)        # (kanal, n)


def _ses_yaz(yol: str, veri: np.ndarray, sr: int) -> None:
    import soundfile as sf
    a = np.atleast_2d(veri)
    sf.write(yol, a.T, sr, subtype="FLOAT")


def _yeniden_ornekle(pcm: np.ndarray, sr: int, hedef: int) -> np.ndarray:
    if sr == hedef or len(pcm) == 0:
        return pcm.astype(np.float32)
    try:
        import soxr  # librosa ile gelir; kaliteli
        return np.asarray(soxr.resample(pcm, sr, hedef), dtype=np.float32)
    except Exception:
        n = max(1, int(round(len(pcm) * hedef / sr)))
        return np.interp(np.linspace(0, len(pcm) - 1, n), np.arange(len(pcm)), pcm).astype(np.float32)


class GercekIsleyici:
    """`k_<komut>(veri, is_)` yöntemleri sunucu tarafından çağrılır."""

    def __init__(self) -> None:
        self._gonder: Callable[[dict[str, Any]], None] = lambda n: None
        self._torch: Any = None
        self.cihaz = "cpu"
        self.hafif = False
        self._demucs: Any = None
        self._whisper: Any = None
        self._whisper_ad = ""
        self._tts: Any = None
        self._tts_kod = ""
        self._ref_ozet = ""
        self._kosullar: "dict[str, Any]" = {}     # ses özeti -> Chatterbox Conditionals (LRU, yalnız RAM)
        self._hazir_ses: dict[str, tuple[np.ndarray, int]] = {}
        self._yari: Any = None                     # T3'ün yarı hassas türü (torch.bfloat16 / float16) ya da None
        self._son_uretim: dict[str, Any] = {}
        self._canli: Any = None
        self._dizin: Any = None                    # dublaj hafızası: tanınacak satırların ses izleri (PROTOKOL 21.4)
        self._ani: Any = None                      # hafıza sesini sırasız çalan oynatıcı (21.3)
        self._kilit = threading.RLock()
        self._son_kullanim = time.monotonic()
        self._gpu_disinda = False          # boşta kalınca ses motoru ekran kartından indirildi mi
        self.bosta_sn = float(os.environ.get("KOPRU_BOSTA_SN", "180"))
        threading.Thread(target=self._bosta_bekci, daemon=True, name="isci-bosta").start()

    # ---------- boşta VRAM boşaltma (oyuna yer kalsın) ----------
    def _bosta_bekci(self) -> None:
        while True:
            time.sleep(15)
            try:
                if (self._tts is not None and self.cihaz == "cuda" and not self._gpu_disinda
                        and self._canli is None   # canlı dublaj sürerken model ekran kartında kalır (ilk satır yavaşlamasın)
                        and time.monotonic() - self._son_kullanim > self.bosta_sn):
                    with self._kilit:
                        self._tts_tasi("cpu")
                        self._gpu_disinda = True
                        self._torch.cuda.empty_cache()
                    log.info("Boşta: ses motoru ekran kartından indirildi")
            except Exception:   # noqa: BLE001
                log.debug("boşta boşaltma başarısız", exc_info=True)

    def _tts_tasi(self, cihaz: str) -> None:
        m = self._tts
        for ad in ("t3", "s3gen", "ve"):
            alt = getattr(m, ad, None)
            if alt is not None:
                alt.to(cihaz)
        if hasattr(m, "device"):
            m.device = cihaz
        self._ref_ozet = ""         # koşullar yeniden hazırlansın (doğru cihazda)
        self._kosullar.clear()

    def _kullan(self) -> None:
        self._son_kullanim = time.monotonic()
        if self._gpu_disinda and self._tts is not None:
            self._tts_tasi("cuda")
            self._gpu_disinda = False

    def gonder_bagla(self, gonder: Callable[[dict[str, Any]], None]) -> None:
        self._gonder = gonder

    # ---------- bilgi ----------
    def cihaz_bilgisi(self) -> dict[str, Any]:
        """El sıkışmada (merhaba) ana programa ve isci.log'a: hangi cihazda çalışıyoruz, neden.

        `durum`: "gpu" | "cpu_torch_cpu" (NVIDIA kart var ama kurulu torch CUDA'sız: paketin torch'u yanlış
        kurulmuş, onarılabilir) | "cpu_surucu" (torch CUDA'lı ama kart/sürücü görülmüyor) | "cpu" (NVIDIA yok) |
        "mps" | "torch_yok"."""
        bilgi: dict[str, Any] = {"cihaz": "cpu", "ekran_karti": None, "vram_gb": None, "python": sys.version.split()[0]}
        try:
            import torch
            self._torch = torch
            bilgi["torch"] = torch.__version__
            bilgi["torch_cuda"] = getattr(torch.version, "cuda", None)       # None: CPU yapısı
            if torch.cuda.is_available():
                p = torch.cuda.get_device_properties(0)
                bilgi.update(cihaz="cuda", ekran_karti=torch.cuda.get_device_name(0),
                             vram_gb=round(p.total_memory / 1024 ** 3, 1), durum="gpu")
                try:
                    bilgi["bf16"] = bool(torch.cuda.is_bf16_supported())
                    bilgi["cudnn"] = torch.backends.cudnn.version()
                except Exception:   # noqa: BLE001
                    pass
            elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
                bilgi.update(cihaz="mps", ekran_karti="Apple Silicon", durum="mps")
            else:
                kart = _nvidia_karti()
                if kart:
                    bilgi.update(ekran_karti=kart[0], vram_gb=kart[1])
                    bilgi["durum"] = "cpu_torch_cpu" if not bilgi["torch_cuda"] else "cpu_surucu"
                    try:
                        torch.cuda.init()
                    except Exception as e:   # noqa: BLE001 — sürücü/CUDA neden açılmadı
                        bilgi["cuda_hata"] = f"{type(e).__name__}: {e}"[:200]
                else:
                    bilgi["durum"] = "cpu"
        except Exception as e:   # torch yok/bozuk: yine de yanıt veririz
            bilgi["torch_hata"] = type(e).__name__
            bilgi["durum"] = "torch_yok"
        self.cihaz = bilgi["cihaz"]
        if not getattr(self, "_cihaz_yazildi", False):
            self._cihaz_yazildi = True
            log.info("Cihaz: %s | durum=%s | kart=%s | VRAM=%s GB | torch=%s (CUDA %s) | python=%s%s",
                     bilgi["cihaz"], bilgi.get("durum"), bilgi.get("ekran_karti"), bilgi.get("vram_gb"),
                     bilgi.get("torch"), bilgi.get("torch_cuda"), bilgi["python"],
                     f" | {bilgi['cuda_hata']}" if bilgi.get("cuda_hata") else "")
            if bilgi.get("durum") in ("cpu_torch_cpu", "cpu_surucu"):
                log.warning("NVIDIA ekran kartı var ama dublaj İŞLEMCİDE çalışacak (çok yavaş): %s", bilgi.get("durum"))
        return bilgi

    def k_merhaba(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        return self.cihaz_bilgisi()

    def k_bellek(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        t = self._torch
        if t is None or self.cihaz != "cuda":
            return {"bos_gb": None, "toplam_gb": None}
        bos, toplam = t.cuda.mem_get_info()
        return {"bos_gb": round(bos / 1024 ** 3, 2), "toplam_gb": round(toplam / 1024 ** 3, 2)}

    # ---------- model indirme / yükleme ----------
    def k_modeller(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        """Modelleri indirir (Hugging Face önbelleği = HF_HOME). Yükleme yapmaz."""
        from huggingface_hub import snapshot_download
        liste = v.get("liste") or ["tts", "stt", "ayirma"]
        isler: list[tuple[str, str, list[str] | None]] = []
        if "tts" in liste:
            isler.append(("Chatterbox çok dilli", "ResembleAI/chatterbox",
                          ["ve.pt", "t3_mtl23ls_v2.safetensors", "s3gen.pt", "grapheme_mtl_merged_expanded_v1.json",
                           "conds.pt", "Cangjie5_TC.json"]))
        if "stt" in liste:
            ad = v.get("stt") or WHISPER_NORMAL
            from faster_whisper.utils import _MODELS
            isler.append((f"Whisper {ad}", _MODELS.get(ad, ad), None))
        for i, (ad, repo, desen) in enumerate(isler):
            is_.ilerleme(100.0 * i / (len(isler) + 1), ad)
            snapshot_download(repo_id=repo, allow_patterns=desen)
        if "tts" in liste:
            for c in HAZIR_SESLER:          # yerleşik yedek sesler (küçük; olmazsa ilk kullanımda yeniden denenir)
                self._hazir_ses_al(c)
        if "ayirma" in liste:
            is_.ilerleme(100.0 * len(isler) / (len(isler) + 1), "HT-Demucs-ft")
            self._demucs_yukle(sadece_indir=True)
        return {"tamam": True}

    def k_yukle(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        self.cihaz_bilgisi()
        self.hafif = bool(v.get("hafif"))
        isinma_ms = None
        if v.get("tts"):
            is_.ilerleme(10, "ses motoru")
            t0 = time.monotonic()
            self._tts_yukle(str(v["tts"]))
            log.info("Ses motoru yüklendi: %s, %s%s, %d ms", v["tts"], self.cihaz,
                     f" (T3 {str(self._yari).replace('torch.', '')})" if self._yari is not None else "",
                     (time.monotonic() - t0) * 1000)
            if v.get("isit", True):
                is_.ilerleme(40, "ısınma")
                isinma_ms = self._isit()
        if v.get("stt"):
            is_.ilerleme(50, "konuşma tanıma")
            self._whisper_yukle(str(v["stt"]))
        if v.get("ayirma") and not self.hafif:
            is_.ilerleme(80, "ayırıcı")
            self._demucs_yukle()
        return {"cihaz": self.cihaz, "isinma_ms": isinma_ms, **self.k_bellek({}, is_)}

    def _isit(self) -> int | None:
        """Yüklemeden hemen sonra bir kısa üretim (CUDA çekirdekleri derlenir, bellek ayrılır) ve yerleşik yedek
        seslerin koşulları önceden hazırlanır: oyundaki ilk gerçek satır yavaş olmasın."""
        t0 = time.monotonic()
        try:
            if self._tts_kod == "pocket":    # Pocket örneksiz üretemez: yerleşik sesle ısınır
                hs = self._hazir_ses_al("e")
                if hs is None:
                    return None
                self._uret("Merhaba.", hs[0], hs[1], {})
                return int((time.monotonic() - t0) * 1000)
            self._uret("Merhaba.", np.zeros(0, np.float32), TTS_REF_SR, {})
            for c in ("k", "e"):
                hs = self._hazir_ses_al(c)
                if hs is not None:
                    with self._kilit:
                        self._referans_hazirla(hs[0], hs[1], 0.5)
        except Exception as e:   # noqa: BLE001 — ısınma olmazsa da çalışırız
            log.info("Isınma üretimi başarısız: %s", type(e).__name__)
            return None
        ms = int((time.monotonic() - t0) * 1000)
        log.info("Isınma: %d ms", ms)
        return ms

    def _hazir_ses_al(self, cinsiyet: str) -> tuple[np.ndarray, int] | None:
        """Yerleşik yedek ses ("k" | "e"): ilk kullanımda Hugging Face önbelleğine iner (sabit sürüm), sonra RAM'de."""
        if cinsiyet not in HAZIR_SESLER:
            return None
        if cinsiyet in self._hazir_ses:
            return self._hazir_ses[cinsiyet]
        try:
            from huggingface_hub import hf_hub_download
            yol = hf_hub_download(HAZIR_SES_DEPO, HAZIR_SESLER[cinsiyet], revision=HAZIR_SES_SURUM)
            pcm2, sr = _ses_oku(yol)
            pcm = _yeniden_ornekle(pcm2.mean(0), sr, TTS_REF_SR)
        except Exception as e:   # noqa: BLE001 — çevrimdışı vb.: motorun kendi sesi kullanılır
            log.info("Yerleşik %s ses alınamadı: %s", cinsiyet, type(e).__name__)
            return None
        self._hazir_ses[cinsiyet] = (pcm, TTS_REF_SR)
        return self._hazir_ses[cinsiyet]

    def k_birak(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        self._demucs = self._whisper = self._tts = None
        self._tts_kod = self._whisper_ad = self._ref_ozet = ""
        self._kosullar.clear()
        if self._torch is not None and self.cihaz == "cuda":
            self._torch.cuda.empty_cache()
        return {}

    # ---------- ayırma (HT-Demucs-ft, yalnız konuşma uzmanı) ----------
    def _demucs_yukle(self, sadece_indir: bool = False) -> Any:
        if self._demucs is not None:
            return self._demucs
        try:
            from demucs.pretrained import get_model
        except ImportError as e:
            raise IsciHatasi("dublaj_paket_yok", "demucs") from e
        torba = get_model(DEMUCS_MODEL)
        if sadece_indir:
            return None
        model = torba
        alt = getattr(torba, "models", None)
        if alt:   # torbadan konuşma (vocals) ağırlığı en yüksek alt model: 4 kat hızlı
            kaynaklar = list(torba.sources)
            vi = kaynaklar.index("vocals")
            agirlik = np.asarray(getattr(torba, "weights", [[1.0] * len(kaynaklar)] * len(alt)), dtype=float)
            model = alt[int(np.argmax(agirlik[:, vi]))]
        model.to(self.cihaz).eval()
        self._demucs = model
        return model

    def _ayir_dizi(self, mix: np.ndarray, is_: Is | None = None) -> tuple[np.ndarray, np.ndarray]:
        """(2, n) 44.1 kHz → (konuşma, arka plan) aynı biçimde."""
        torch = self._torch or __import__("torch")
        from demucs.apply import apply_model
        model = self._demucs_yukle()
        x = torch.from_numpy(np.ascontiguousarray(mix, dtype=np.float32))
        ort = x.mean(0)
        std = ort.std() + 1e-8
        x = (x - ort.mean()) / std
        with torch.inference_mode():
            cik = apply_model(model, x[None], device=self.cihaz, shifts=0, split=True, overlap=0.25,
                              progress=False, num_workers=0)[0]
        cik = cik * std + ort.mean()
        vi = list(model.sources).index("vocals")
        konusma = cik[vi].float().cpu().numpy()
        arka = mix - konusma
        return konusma.astype(np.float32), arka.astype(np.float32)

    def k_ayir(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        if "pcm" in v:     # canlı: kısa parça, bellekte
            sr = int(v["sr"])
            pcm = protokol.pcm_coz(v["pcm"])
            mix = _yeniden_ornekle(pcm, sr, DEMUCS_SR)
            konusma, arka = self._ayir_dizi(np.stack([mix, mix]))
            k = _yeniden_ornekle(konusma.mean(0), DEMUCS_SR, sr)
            a = _yeniden_ornekle(arka.mean(0), DEMUCS_SR, sr)
            return {"pcm": protokol.pcm_kodla(k), "arka": protokol.pcm_kodla(a), "sr": sr}
        import soundfile as sf
        bilgi = sf.info(v["giris"])
        n, sr = int(bilgi.frames), int(bilgi.samplerate)
        blok, pay = int(BLOK_SN * sr), int(BLOK_PAY_SN * sr)
        with sf.SoundFile(v["giris"]) as g, \
                sf.SoundFile(v["ses_cikis"], "w", sr, 2, subtype="FLOAT") as ks, \
                sf.SoundFile(v["arka_cikis"], "w", sr, 2, subtype="FLOAT") as ar:
            for i, (ob, os_, yb, ys) in enumerate(blok_plani(n, blok, pay)):
                is_.ilerleme(100.0 * yb / max(1, n), f"{int(yb / sr)} / {int(n / sr)} sn")
                g.seek(ob)
                parca = g.read(os_ - ob, dtype="float32", always_2d=True).T
                if parca.shape[0] == 1:
                    parca = np.repeat(parca, 2, axis=0)
                konusma, arka = self._ayir_dizi(parca[:2])
                ks.write(konusma[:, yb - ob:ys - ob].T)
                ar.write(arka[:, yb - ob:ys - ob].T)
                if self.cihaz == "cuda":
                    self._torch.cuda.empty_cache()
        return {"sure_sn": n / sr}

    # ---------- yazıya çevirme ----------
    def _whisper_yukle(self, ad: str) -> Any:
        if self._whisper is not None and self._whisper_ad == ad:
            return self._whisper
        try:
            if sys.platform == "win32" and self._torch is not None:   # cuDNN/cuBLAS DLL'leri torch'un içinde
                os.add_dll_directory(os.path.join(os.path.dirname(self._torch.__file__), "lib"))
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise IsciHatasi("dublaj_paket_yok", "faster-whisper") from e
        if self.cihaz == "cuda":
            self._whisper = WhisperModel(ad, device="cuda", compute_type="int8_float16")
        else:
            self._whisper = WhisperModel(ad, device="cpu", compute_type="int8")
        self._whisper_ad = ad
        return self._whisper

    def k_yaziya(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        self._son_kullanim = time.monotonic()
        model = self._whisper or self._whisper_yukle(WHISPER_HAFIF if self.hafif else WHISPER_NORMAL)
        dil = v.get("dil") or None
        if "pcm" in v:
            pcm = _yeniden_ornekle(protokol.pcm_coz(v["pcm"]), int(v["sr"]), STT_SR)
            parcalar, bilgi = model.transcribe(pcm, language=dil, vad_filter=True, beam_size=1)
            metin = " ".join(p.text.strip() for p in parcalar).strip()
            return {"metin": metin, "dil": getattr(bilgi, "language", None)}
        ses, ssr = _ses_oku(v["giris"])          # PyAV sürüm farklarına takılmamak için ses dosyasını kendimiz okuruz
        girdi = _yeniden_ornekle(ses.mean(0), ssr, STT_SR)
        parcalar, bilgi = model.transcribe(girdi, language=dil, vad_filter=True, word_timestamps=True,
                                           beam_size=5, condition_on_previous_text=False)
        sure = float(getattr(bilgi, "duration", 0.0) or 0.0)
        kelimeler = []
        for p in parcalar:
            is_.ilerleme(min(99.0, 100.0 * p.end / sure) if sure else 0.0)
            for k in (p.words or []):
                kelimeler.append({"k": k.word.strip(), "b": round(float(k.start), 3), "s": round(float(k.end), 3)})
        return {"kelimeler": kelimeler, "dil": getattr(bilgi, "language", None), "sure_sn": sure}

    # ---------- konuşmacı izleri + satır analizi ----------
    def _ses_kodlayici(self) -> Any:
        m = self._tts_yukle("chatterbox") if self._tts is None else self._tts
        return getattr(m, "ve", None)

    def _iz(self, pcm16k: np.ndarray) -> np.ndarray:
        ve = self._ses_kodlayici()
        if ve is not None and len(pcm16k) >= int(0.5 * STT_SR):
            try:
                e = np.asarray(ve.embeds_from_wavs([pcm16k], sample_rate=STT_SR), dtype=np.float64).reshape(-1)
                return e / max(np.linalg.norm(e), 1e-9)
            except Exception:
                log.debug("ses kodlayıcı izi alınamadı", exc_info=True)
        from .. import dsp   # yedek: ucuz MFCC izi
        e = dsp.parmak_izi(pcm16k, STT_SR)
        return e / max(np.linalg.norm(e), 1e-9)

    def k_izler(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        """Her satır için: konuşmacı izi, temizlik puanı, ses yüksekliği, duygu."""
        ses, sr = _ses_oku(v["giris"])
        arka, _ = _ses_oku(v["arka"]) if v.get("arka") else (None, sr)
        mono = ses.mean(0)
        araliklar = v["araliklar"]
        izler, puanlar, rmsler, parcalar = [], [], [], []
        for i, (b, s) in enumerate(araliklar):
            is_.ilerleme(100.0 * i / max(1, len(araliklar)))
            p = mono[int(b * sr):int(s * sr)]
            parcalar.append(p)
            rmsler.append(mantik.rms(p))
            puanlar.append(mantik.temizlik_puani(p, arka.mean(0)[int(b * sr):int(s * sr)]) if arka is not None else 0.0)
            izler.append(self._iz(_yeniden_ornekle(p, sr, STT_SR)).tolist())
        ref = float(np.median([r for r in rmsler if r > 1e-4])) if any(r > 1e-4 for r in rmsler) else None
        duygular = [mantik.duygu(p, sr, ref) for p in parcalar]
        return {"izler": izler, "puanlar": puanlar, "rms": rmsler, "duygular": duygular}

    def k_referans_kaydet(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        """Video: her karakter için seçilen aralıkları birleştirip iş klasörüne referans WAV yazar."""
        ses, sr = _ses_oku(v["giris"])
        mono = ses.mean(0)
        sessizlik = np.zeros(int(0.15 * sr), dtype=np.float32)
        parcalar = []
        for b, s in v["araliklar"]:
            parcalar += [mono[int(b * sr):int(s * sr)], sessizlik]
        pcm = np.concatenate(parcalar) if parcalar else np.zeros(sr, np.float32)
        tepe = float(np.abs(pcm).max()) or 1.0
        _ses_yaz(v["cikis"], _yeniden_ornekle(pcm / tepe * 0.8, sr, TTS_REF_SR), TTS_REF_SR)
        return {"sure_sn": len(pcm) / sr}

    # ---------- seslendirme ----------
    def _tts_yukle(self, kod: str) -> Any:
        if self._tts is not None and self._tts_kod == kod:
            return self._tts
        torch = self._torch or __import__("torch")
        self._torch = torch
        if kod == "pocket":
            try:
                from pocket_tts import TTSModel
            except ImportError as e:
                raise IsciHatasi("dublaj_paket_yok", "pocket-tts") from e
            self._tts = TTSModel.load_model(config="hf://kaanhgunay/pocket-tts-tr/config.yaml@v0.1-base")
        else:
            try:
                from chatterbox.mtl_tts import ChatterboxMultilingualTTS
            except ImportError as e:
                raise IsciHatasi("dublaj_paket_yok", "chatterbox-tts") from e
            self._tts = ChatterboxMultilingualTTS.from_pretrained(self.cihaz)
            c = getattr(self._tts, "conds", None)
            self._varsayilan_kosul = (c.t3, c.gen) if c is not None else None
            self._kosullar.clear()
            self._yari_hassas_kur(torch)
        self._tts_kod = kod
        self._ref_ozet = ""
        return self._tts

    def _yari_hassas_kur(self, torch: Any) -> None:
        """Ekran kartında YALNIZ konuşma dil modeli (T3, Llama tabanlı; sürenin çoğu) yarı hassas çalışır: bf16
        destekleniyorsa bf16 (fp16'nın taşma kaynaklı bozuk/robotik çıktısı olmaz), değilse fp16. Ses üreteci
        (S3Gen: akış eşleme + HiFiGAN) tam hassas kalır; eskiden tüm üretim fp16 autocast altındaydı ve
        vokoder fp16'da metalik/robotik ses verebiliyordu. KOPRU_TAM_HASSAS=1: hepsi fp32."""
        self._yari = None
        tur = os.environ.get("KOPRU_YARI_HASSAS_CIHAZ") or self.cihaz      # sınama: "cpu" ile bf16 yolu
        if tur not in ("cuda", "cpu") or (tur == "cpu" and self.cihaz != "cpu") or os.environ.get("KOPRU_TAM_HASSAS"):
            return
        if tur == "cpu" and not os.environ.get("KOPRU_YARI_HASSAS_CIHAZ"):
            return
        try:
            bf16 = tur == "cpu" or bool(torch.cuda.is_bf16_supported())
            tip = torch.bfloat16 if bf16 else torch.float16
            t3 = self._tts.t3
            t3.to(dtype=tip)
            ic = t3.inference

            def inference(*a: Any, **k: Any) -> Any:
                with torch.autocast(tur, dtype=tip):
                    return ic(*a, **k)
            t3.inference = inference
            self._t3_ic = ic
            self._yari = tip
        except Exception as e:   # noqa: BLE001
            log.info("T3 yarı hassasa çevrilemedi (%s); tam hassas", type(e).__name__)
            self._tam_hassasa_don()

    def _tam_hassasa_don(self) -> None:
        t3 = getattr(self._tts, "t3", None)
        if t3 is None:
            return
        try:
            t3.to(dtype=self._torch.float32)
            if getattr(self, "_t3_ic", None) is not None:
                t3.inference = self._t3_ic
        except Exception:   # noqa: BLE001
            pass
        self._yari = None

    def _referans_hazirla(self, pcm: np.ndarray, sr: int, canlilik: float) -> None:
        ozet = hashlib.sha1(pcm.tobytes()).hexdigest() + str(sr)
        if ozet == self._ref_ozet:
            return
        if len(pcm) == 0 and self._tts_kod != "pocket":   # örnek yok: modelin kendi (nötr) sesi
            if getattr(self, "_varsayilan_kosul", None) is not None:
                from chatterbox.mtl_tts import Conditionals
                t3, gen = self._varsayilan_kosul
                self._tts.conds = Conditionals(t3, gen)
            self._ref_ozet = ozet
            return
        if self._tts_kod != "pocket" and ozet in self._kosullar:   # bu ses daha önce hazırlandı: yeniden hesap yok
            self._tts.conds = self._kosullar.pop(ozet)
            self._kosullar[ozet] = self._tts.conds
            self._ref_ozet = ozet
            self._son_uretim["kosul"] = "onbellek"
            return
        t0 = time.monotonic()
        if len(pcm):   # kısık konuşma (oyunda diyalog sesi düşük): örneği sabit düzeye getir
            r = float(np.sqrt(np.mean(np.square(pcm, dtype=np.float64))))
            if r > 1e-5:
                pcm = np.clip(pcm * min(30.0, 0.08 / r), -1, 1).astype(np.float32)
        if self._tts_kod == "pocket":
            torch = self._torch
            ornek = _yeniden_ornekle(pcm, sr, int(self._tts.config.mimi.sample_rate))
            self._pocket_durum = self._tts.get_state_for_audio_prompt(torch.from_numpy(ornek).unsqueeze(0))
        else:
            import soundfile as sf
            tampon = io.BytesIO()
            sf.write(tampon, pcm, sr, format="WAV", subtype="FLOAT")   # bellekte; diske yazılmaz
            tampon.seek(0)
            self._tts.prepare_conditionals(tampon, exaggeration=canlilik)
            self._kosullar[ozet] = self._tts.conds
            while len(self._kosullar) > KOSUL_ONBELLEK:
                self._kosullar.pop(next(iter(self._kosullar)))
        self._son_uretim["kosul"] = int((time.monotonic() - t0) * 1000)
        self._ref_ozet = ozet

    def _uret(self, metin: str, ref: np.ndarray, ref_sr: int, duygu: dict[str, float]) -> tuple[np.ndarray, int]:
        # Diller arası klonda (İngilizce örnek → Türkçe) düşük cfg_weight İngilizce aksanın ve "okuma" havasının
        # Türkçeye taşınmasını azaltır (Chatterbox önerisi: dil aktarımında cfg düşük); canlılık 0,5 civarı doğal.
        canlilik = float(np.clip(duygu.get("canlilik", 0.5), 0.25, 1.0))
        cfg = float(np.clip(duygu.get("cfg", 0.3), 0.15, 0.6))
        sicaklik = float(np.clip(duygu.get("sicaklik", 0.8), 0.3, 1.2))
        tohum = duygu.get("tohum")              # iyileştirme adayları (PROTOKOL 21.6): tekrarlanabilir çeşitlilik
        with self._kilit:
            self._kullan()
            self._son_uretim = {"kosul": 0}
            self._referans_hazirla(ref, ref_sr, canlilik)
            if isinstance(tohum, int) and self._torch is not None:
                self._torch.manual_seed(tohum)
            t0 = time.monotonic()
            if self._tts_kod == "pocket":
                ses = self._tts.generate_audio(self._pocket_durum, metin)
                pcm = np.asarray(ses.detach().cpu().numpy(), dtype=np.float32).reshape(-1)
                sr = int(self._tts.sample_rate)
            else:
                def uret() -> Any:
                    return self._tts.generate(metin, language_id="tr", exaggeration=canlilik, cfg_weight=cfg,
                                              temperature=sicaklik)
                try:
                    wav = uret()
                except RuntimeError as e:
                    if self._yari is None:
                        raise
                    log.warning("Yarı hassas üretim başarısız (%s); tam hassasa dönülüyor", e)
                    self._tam_hassasa_don()
                    wav = uret()
                pcm = np.asarray(wav.squeeze().detach().float().cpu().numpy(), dtype=np.float32)
                sr = int(self._tts.sr)
            ms = int((time.monotonic() - t0) * 1000)
            self._son_uretim.update(uretim_ms=ms, ses_sn=round(len(pcm) / sr, 2), ref_sn=round(len(ref) / max(1, ref_sr), 1))
            log.info("Seslendirme: %d harf → %.1f sn ses, %d ms (%s; koşul %s; örnek %.1f sn)", len(metin),
                     len(pcm) / sr, ms, self.cihaz, self._son_uretim.get("kosul"), len(ref) / max(1, ref_sr))
            return pcm, sr

    def _ref_sec(self, v: dict[str, Any]) -> tuple[np.ndarray, int]:
        """İstekteki örnek; yoksa istenen cinsiyetin yerleşik yedek sesi; o da yoksa boş (motorun kendi sesi)."""
        if v.get("ref_pcm"):
            return protokol.pcm_coz(v["ref_pcm"]), int(v["ref_sr"])
        hs = self._hazir_ses_al(str(v.get("varsayilan") or "")) if v.get("varsayilan") else None
        if hs is not None:
            return hs
        return np.zeros(0, dtype=np.float32), TTS_REF_SR

    def k_seslendir(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        if self._tts is None or (v.get("motor") and v["motor"] != self._tts_kod):
            self._tts_yukle(str(v.get("motor") or "chatterbox"))
        metin = str(v.get("metin") or "").strip()
        if not metin:
            raise IsciHatasi("dublaj_uretim_hata", "boş metin")
        if v.get("ref_yol"):
            ref2, ref_sr = _ses_oku(v["ref_yol"])
            ref = ref2.mean(0)
        else:
            ref, ref_sr = self._ref_sec(v)
        pcm, sr = self._uret(metin, ref, ref_sr, v.get("duygu") or {})
        if v.get("cikis"):
            _ses_yaz(v["cikis"], pcm, sr)
            return {"sure_sn": len(pcm) / sr, "sr": sr}
        return {"pcm": protokol.pcm_kodla(pcm), "sr": sr, "sure_sn": len(pcm) / sr, "cihaz": self.cihaz,
                **{k: self._son_uretim.get(k) for k in ("uretim_ms", "kosul", "ref_sn")}}

    def k_seslendir_cal(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        """Canlı: metni parça parça seslendirir ve İLK parça hazır olur olmaz çalmaya başlar (akışlı).

        Sonraki parçalar önceki çalarken üretilir. Süreye sığdırma ilk parçanın hızından tahmin edilir.
        Dönüş: ölçümler (ilk_ses_ms = istekten ilk sesin hoparlöre gidişine kadar).
        """
        from .canli import SiraliOynatici, OturumSesi
        t0 = time.monotonic()
        if self._tts is None or (v.get("motor") and v["motor"] != self._tts_kod):
            self._tts_yukle(str(v.get("motor") or "chatterbox"))
        metin = str(v.get("metin") or "").strip()
        ref, ref_sr = self._ref_sec(v)
        duygu = v.get("duygu") or {}
        hedef = float(v.get("hedef_sn") or 0)
        sinir = float(v.get("hiz_siniri") or 1.25)
        parcalar = mantik.cumlecik_bol(metin) or [metin]
        tamamen = bool(self._canli is not None and getattr(self._canli, "tamamen_aktif", False))
        oturum = None if (tamamen or float(v.get("kis", 0.25)) >= 1.0 or sys.platform != "win32") else OturumSesi(v.get("pid"))
        oynatici = None
        ilk_ms = None
        hiz = 1.0
        toplam_sn = 0.0
        try:
            for i, p in enumerate(parcalar):
                is_.denetle()
                pcm, sr = self._uret(p, ref, ref_sr, duygu)
                if i == 0:
                    hiz = mantik.hiz_tahmini(len(pcm) / sr, len(p), len(metin), hedef, sinir)
                if hiz > 1.03:
                    pcm = self._esnet(pcm, sr, hiz)
                pcm = np.clip(pcm * float(v.get("seviye", 1.0)), -1, 1).astype(np.float32)
                if oynatici is None:
                    if oturum:
                        oturum.kis(float(v.get("kis", 0.25)))
                    oynatici = SiraliOynatici(sr)
                    ilk_ms = int((time.monotonic() - t0) * 1000)
                oynatici.ekle(pcm)
                toplam_sn += len(pcm) / sr
            if oynatici is not None:
                while not oynatici.bitti():
                    if is_.iptal.is_set():
                        break
                    time.sleep(0.03)
        finally:
            if oynatici is not None:
                oynatici.kapat()
            if oturum:
                oturum.geri_ac()
        return {"sure_sn": toplam_sn, "ilk_ses_ms": ilk_ms, "toplam_ms": int((time.monotonic() - t0) * 1000),
                "hiz": round(hiz, 3), "parca": len(parcalar)}

    def _esnet(self, pcm: np.ndarray, sr: int, oran: float) -> np.ndarray:
        try:
            import librosa
            return np.asarray(librosa.effects.time_stretch(pcm, rate=oran), dtype=np.float32)
        except Exception:
            from .. import dsp
            return dsp.wsola(pcm, sr, oran)

    def k_hizlandir(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        pcm2, sr = _ses_oku(v["giris"])
        pcm = pcm2.mean(0)
        yeni = self._esnet(pcm, sr, float(v["oran"]))
        _ses_yaz(v["cikis"], yeni, sr)
        return {"sure_sn": len(yeni) / sr}

    # ---------- karıştırma ve video ----------
    def k_karistir(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        arka, sr = _ses_oku(v["arka"])
        sesler = []
        for i, s in enumerate(v["satirlar"]):
            if i % 20 == 0:
                is_.ilerleme(100.0 * i / max(1, len(v["satirlar"])))
            p, psr = _ses_oku(s["yol"])
            sesler.append((_yeniden_ornekle(p.mean(0), psr, sr), int(float(s["bas"]) * sr)))
        cikis = mantik.karistir(arka, sesler, sr, float(v.get("kis_db", -6.0)), float(v.get("kazanc", 1.0)))
        _ses_yaz(v["cikis"], cikis, sr)
        return {"sure_sn": cikis.shape[1] / sr}

    def k_video_cikar(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        _calistir([_ffmpeg(), "-nostdin", "-y", "-v", "error", "-progress", "pipe:1", "-i", v["video"],
                   "-vn", "-ac", "2", "-ar", str(DEMUCS_SR), "-c:a", "pcm_f32le", v["cikis"]],
                  is_, float(v.get("sure_sn") or 0))
        import soundfile as sf
        b = sf.info(v["cikis"])
        return {"sure_sn": b.frames / b.samplerate}

    def k_video_birlestir(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        _calistir([_ffmpeg(), "-nostdin", "-y", "-v", "error", "-progress", "pipe:1", "-i", v["video"], "-i", v["ses"],
                   "-map", "0:v?", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                   "-metadata:s:a:0", "language=tur", "-shortest", "-movflags", "+faststart", v["cikis"]],
                  is_, float(v.get("sure_sn") or 0))
        return {"cikis": v["cikis"]}

    # ---------- canlı ----------
    def k_canli_baslat(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        from .canli import CanliYakalama
        if self._canli is not None:
            self._canli.durdur()
        tamamen = bool(v.get("tamamen_turkce"))
        ps5 = v.get("ps5_ses") if isinstance(v.get("ps5_ses"), dict) else None
        ayir = lambda pcm, sr: self._ayir_canli(pcm, sr)   # noqa: E731
        # akışlı ayırma yalnız "Tamamen Türkçe"de; yoksa konuşma parçası başına bir kez (klon örneği için). PS5
        # gizli bağlantıda oyun bu bilgisayarın ekran kartında değildir: hafif kipte de parça ayrılır.
        parca = bool(v.get("ayirma")) and not tamamen and (not self.hafif or ps5 is not None)
        tanici = None
        if v.get("parmak_izi"):          # yalnız dublaj hafızası izinliyken (PROTOKOL 21.4)
            from .. import tanima
            tanici = tanima.Tanici(self._dizin_al())
        self._canli = CanliYakalama(self._gonder, pid=v.get("pid"), ayirici=ayir if tamamen else None,
                                    tamamen_turkce=tamamen, giris=str(v.get("giris") or ""), ps5_ses=ps5,
                                    parca_ayirici=ayir if parca else None, tanici=tanici)
        return self._canli.baslat()

    def _ayir_canli(self, pcm: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
        with self._kilit:
            mix = _yeniden_ornekle(pcm, sr, DEMUCS_SR)
            k, a = self._ayir_dizi(np.stack([mix, mix]))
        return _yeniden_ornekle(k.mean(0), DEMUCS_SR, sr), _yeniden_ornekle(a.mean(0), DEMUCS_SR, sr)

    def k_girisler(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        from .canli import girisleri_listele
        return {"girisler": girisleri_listele()}

    def k_canli_son(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        """Son ~1,5 sn konuşma (anında; seslendirme sırasını beklemez). Canlı yakalama yoksa boş."""
        c = self._canli
        if c is None or not hasattr(c, "son_ses"):
            return {}
        pcm = c.son_ses(float(v.get("sn") or 1.5))
        return {"pcm": protokol.pcm_kodla(pcm), "sr": 16000} if len(pcm) else {}

    def k_canli_durdur(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        if self._canli is not None:
            self._canli.durdur()
            self._canli = None
        return {}

    def k_oynat(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        from .canli import oynat
        pcm = protokol.pcm_coz(v["pcm"])
        return oynat(pcm, int(v["sr"]), float(v.get("seviye", 1.0)), float(v.get("kis", 0.25)), v.get("pid"),
                     self._canli, is_)

    # ---------- dublaj hafızası (PROTOKOL 21) ----------
    def _dizin_al(self) -> Any:
        if self._dizin is None:
            from .. import tanima
            self._dizin = tanima.Dizin()
        return self._dizin

    def k_tanima_yukle(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        d = self._dizin_al()
        if v.get("sifirla"):
            d.temizle()
        for g in v.get("girdiler") or []:
            d.ekle(int(g["kimlik"]), g.get("iz") or [])
        return {"satir": len(d)}

    def k_tanima_sil(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        d = self._dizin_al()
        if v.get("kimlik") is None:
            d.temizle()
        else:
            d.sil(int(v["kimlik"]))
        return {"satir": len(d)}

    def k_ani_cal(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        from .canli import AniOynatici
        if self._ani is None:
            self._ani = AniOynatici()
        pcm = protokol.pcm_coz(v["pcm"])
        self._ani.cal(str(v.get("kimlik") or "h"), pcm, int(v["sr"]), float(v.get("gecikme_sn") or 0),
                      float(v.get("seviye", 1.0)), float(v.get("kis", 0.25)), v.get("pid"), self._canli)
        return {"planlandi": True, "sure_sn": len(pcm) / int(v["sr"])}

    def k_ani_durdur(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        if self._ani is not None:
            self._ani.durdur(v.get("kimlik"))
        return {}

    def k_ses_kodla(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        """Hafıza sesi: Ogg/Opus (~32 kbit/sn), Opus yoksa FLAC. Diske yazmaz (bellekte)."""
        import base64
        import soundfile as sf
        pcm = protokol.pcm_coz(v["pcm"])
        sr = int(v["sr"])
        for bicim, tur, alt in (("ogg", "OGG", "OPUS"), ("flac", "FLAC", "PCM_16")):
            try:
                if alt not in sf.available_subtypes(tur):
                    continue
                t = io.BytesIO()
                hedef_sr = 24000 if bicim == "ogg" else sr       # Opus 48/24/16/12/8 kHz ister
                sf.write(t, _yeniden_ornekle(pcm, sr, hedef_sr), hedef_sr, format=tur, subtype=alt)
                return {"veri": base64.b64encode(t.getvalue()).decode("ascii"), "bicim": bicim, "sr": hedef_sr}
            except Exception as e:   # noqa: BLE001
                log.info("hafıza sesi %s olarak kodlanamadı: %s", bicim, type(e).__name__)
        raise IsciHatasi("dublaj_kodla_hata", "soundfile")

    def k_ses_coz(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        import base64
        import soundfile as sf
        pcm, sr = sf.read(io.BytesIO(base64.b64decode(v["veri"])), dtype="float32", always_2d=True)
        return {"pcm": protokol.pcm_kodla(pcm.mean(1)), "sr": int(sr)}

    def k_aday_olc(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        """İyileştirme adayı (PROTOKOL 21.6): Türkçe geri yazım (Whisper) ve konuşmacı benzerliği (ses kodlayıcı)."""
        pcm = _yeniden_ornekle(protokol.pcm_coz(v["pcm"]), int(v["sr"]), STT_SR)
        model = self._whisper or self._whisper_yukle(WHISPER_HAFIF if self.hafif else WHISPER_NORMAL)
        parcalar, _ = model.transcribe(pcm, language="tr", vad_filter=False, beam_size=1)
        metin = " ".join(p.text.strip() for p in parcalar).strip()
        benzerlik = None
        if v.get("ref_pcm"):
            ref = _yeniden_ornekle(protokol.pcm_coz(v["ref_pcm"]), int(v["ref_sr"]), STT_SR)
            if len(ref) >= int(0.5 * STT_SR):
                benzerlik = float(np.dot(self._iz(pcm), self._iz(ref)))
        return {"metin": metin, "benzerlik": benzerlik}

    def k_parmak_izleri(self, v: dict[str, Any], is_: Is) -> dict[str, Any]:
        """Video: her satırın orijinal (karışık) sesinin 1 sn ön paylı izi (PROTOKOL 21.7)."""
        from .. import tanima
        ses, sr = _ses_oku(v["giris"])
        mono = _yeniden_ornekle(ses.mean(0), sr, STT_SR)
        izler = []
        for i, (b, s) in enumerate(v["araliklar"]):
            is_.ilerleme(100.0 * i / max(1, len(v["araliklar"])))
            izler.append(tanima.iz_cikar(mono, STT_SR, float(b), float(s)))
        return {"izler": izler}

    def kapat(self) -> None:
        if self._ani is not None:
            self._ani.durdur()
        if self._canli is not None:
            self._canli.durdur()


def blok_plani(n: int, blok: int, pay: int) -> list[tuple[int, int, int, int]]:
    """Uzun sesi bloklara böler: (okuma_bas, okuma_son, yazma_bas, yazma_son). Okuma bloğu iki yanda
    `pay` kadar bağlam içerir; yazılan aralıklar boşluksuz ve çakışmasız [0,n)'i kaplar."""
    plan = []
    yb = 0
    while yb < n:
        ys = min(n, yb + blok)
        plan.append((max(0, yb - pay), min(n, ys + pay), yb, ys))
        yb = ys
    return plan


def _nvidia_karti() -> tuple[str, float | None] | None:
    """torch CUDA görmediğinde: NVIDIA kart gerçekten var mı (nvidia-smi; dizüstünde uyanması sürebilir)."""
    adaylar = ["nvidia-smi"]
    if sys.platform == "win32":
        kok = os.environ.get("SystemRoot", r"C:\Windows")
        adaylar += [os.path.join(kok, "System32", "nvidia-smi.exe"),
                    os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "NVIDIA Corporation", "NVSMI",
                                 "nvidia-smi.exe")]
    for yol in adaylar:
        try:
            cikti = subprocess.run([yol, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=15, check=True,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            ad, bellek = [p.strip() for p in cikti.strip().splitlines()[0].split(",", 1)]
            try:
                return ad, round(float(bellek) / 1024.0, 1)
            except ValueError:
                return ad, None
        except Exception:   # noqa: BLE001
            continue
    return None


def _zaman_damgasi() -> float:
    return time.monotonic()
