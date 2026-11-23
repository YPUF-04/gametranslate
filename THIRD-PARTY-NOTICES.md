# Üçüncü Taraf Bildirimleri

> ⚠️ **Yayından önce doğrula (verify before release):** Aşağıdaki lisanslar planlanan bağımlılıklar içindir. Sürüm yayınlanmadan önce her paketin gerçek lisansı, sürümü ve gerekli telif bildirimleri tek tek kontrol edilmelidir.

AltYazıKöprüsü AGPL-3.0-only lisanslıdır. Aşağıdaki kütüphaneler kendi lisanslarıyla kullanılır.

| Bileşen | Lisans |
|---|---|
| aiohttp | Apache-2.0 |
| anthropic (Python SDK) | MIT |
| keyring | MIT |
| platformdirs | MIT |
| Pillow | MIT-CMU (HPND) |
| mss | MIT |
| winocr | MIT |
| ocrmac | MIT |
| rapidocr-onnxruntime | Apache-2.0 |
| argostranslate | MIT |
| soundcard | BSD-3-Clause |
| numpy | BSD-3-Clause |
| chatterbox-tts (Resemble AI, Chatterbox Multilingual) | MIT (paketin METADATA'sından doğrulandı). Üretilen sese Resemble'ın Perth katmanı, kulakla duyulmayan bir filigran ekler. |
| pocket-tts (Kyutai) | MIT (paketin LICENSE dosyasından doğrulandı) |
| faster-whisper | MIT (paketin METADATA'sından doğrulandı) |
| pycaw (yalnız Windows) | MIT (paketin METADATA'sından doğrulandı) |
| sounddevice | MIT (paketin METADATA'sından doğrulandı) |
| librosa (isteğe bağlı) | ISC (paketin METADATA'sından doğrulandı) |
| psutil (yalnız Windows, pycaw için) | BSD-3-Clause |
| @webos-tools/cli | Apache-2.0 |

### Türkçe dublaj modelleri (isteğe bağlı, kullanıcı onayıyla indirilir)

| Model | Lisans |
|---|---|
| Chatterbox Multilingual ağırlıkları (`ResembleAI/chatterbox`) | MIT (Hugging Face model kartı etiketi, 2026-11-23 doğrulandı) |
| Pocket TTS Türkçe topluluk modeli (`kaanhgunay/pocket-tts-tr`, sürüm `v0.1-base`) | CC BY 4.0 (model kartı, 2026-11-23 doğrulandı). Atıf: Kaan Günay, Kyutai Pocket TTS'ten türetilmiştir; eğitim verisi: Serdar I. Çağlar, *Turkish TTS Audiobooks* (Hugging Face, 2026) |
| Kyutai Pocket TTS ana model ağırlıkları (`kyutai/pocket-tts`) | CC BY 4.0 (model kartı etiketi, 2026-11-23 doğrulandı; erişim koşul onaylı). Kyutai'nin belgesindeki "Prohibited use" bölümü, açık ve yasal onay olmadan ses taklidi/klonlamayı yasaklar; bu yüzden dublaj yalnız kişisel kullanım içindir (bkz. docs/kullanim/turkce-dublaj.md) |
| faster-whisper için Whisper modelleri (`large-v3-turbo`, `small`) | MIT (OpenAI Whisper; `Systran/faster-whisper-small` MIT etiketli; `mobiuslabsgmbh/faster-whisper-large-v3-turbo` dönüşümünde etiket yok, kaynak model MIT) |
| HT-Demucs-ft (`demucs` 4.1.0 ağırlıkları) | MIT |
| Yerleşik yedek dublaj sesleri: `vctk/p228_023_enhanced.wav` (kadın), `vctk/p226_023_enhanced.wav` (erkek) — `kyutai/tts-voices`, sürüm `323332d33f997de8394f24a193e1a76df720e01a` | CC BY 4.0 (depo README'si, 2026-11-23 doğrulandı). Kaynak: CSTR VCTK Corpus, Edinburgh Üniversitesi (Yamagishi, Veaux, MacDonald; https://datashare.ed.ac.uk/handle/10283/3443), `mic1` kaydı, 23. cümle; temizlenmiş sürüm Kyutai'nin (ai-coustics ile). Yalnız karakterin kendi sesi henüz yokken nötr yedek olarak kullanılır |
| Argos Translate en↔tr dil paketi 1.5 (`argos-net.com`) | Dizin lisans BELİRTMİYOR; Argos yazılımı MIT/CC0. Eğitim verisi OPUS derlemleri: bazıları ticari olmayan kullanım şartı taşıyabilir → bkz. docs/KARARLAR.md |

ElevenLabs bir bulut hizmetidir (kullanıcının kendi hesabı ve anahtarı); kullanım koşulları ElevenLabs'e aittir.

Dil/ses/OCR modelleri (Argos Translate dil paketleri, Whisper modelleri, RapidOCR modelleri) kendi lisanslarıyla ayrıca indirilir; yayından önce bunlar da gözden geçirilmelidir.

Esinlenilen projeler için bkz. [NOTICE](NOTICE): GameTranslator (Sefflex), CouchSubs (Sinan Yorulmaz).

## PS5 gizli bağlantı yardımcısı (`ayk-uzaktan.exe`, yalnız Windows paketi)

Kaynak: `uzaktan/` (AGPL-3.0-only). Derleme: `uzaktan/derle.sh` (sürümler commit özetiyle sabit). Statik bağlanan bileşenler:

| Bileşen | Sürüm | Lisans |
|---|---|---|
| chiaki-ng / libchiaki | v1.10.1 (`f30da0aaeb96fc0026cc03683153f682352e7d7c`) | AGPL-3.0-only (OpenSSL istisnalı) |
| FFmpeg (libavcodec, libswscale, libavutil; h264+hevc çözücü) | n7.1.1 (`db69d06eeeab4f46da15030a80d539efb4503ca8`) | LGPL-2.1-or-later |
| OpenSSL (libcrypto) | MSYS2 mingw-w64 paketi | Apache-2.0 |
| Opus | MSYS2 mingw-w64 paketi | BSD-3-Clause |
| json-c | MSYS2 mingw-w64 paketi | MIT |
| miniupnpc | MSYS2 mingw-w64 paketi | BSD-3-Clause |
| libevent | MSYS2 mingw-w64 paketi | BSD-3-Clause |
| curl (chiaki-ng alt modülü, Schannel) | chiaki-ng'deki sürüm | curl (MIT benzeri) |
| nanopb, Jerasure, gf-complete | chiaki-ng alt modülleri | zlib, BSD-3-Clause |

FFmpeg LGPL olduğu için kaynağı ve derleme ayarları `uzaktan/derle.sh` içinde açıktır; kullanıcı kendi FFmpeg'iyle yeniden derleyebilir.
