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
| Chatterbox Multilingual ağırlıkları (`ResembleAI/chatterbox`) | Paket MIT'dir; model kartındaki lisans metni yayından önce model sayfasından doğrulanacak |
| Pocket TTS Türkçe topluluk modeli (`kaanhgunay/pocket-tts-tr`, sürüm `v0.1-base`) | Lisansı model sayfasından doğrulanacak (bu ortamdan model kartına ulaşılamadı, bu yüzden tahmin yazılmadı) |
| Kyutai Pocket TTS ana model ağırlıkları | Lisansı model sayfasından doğrulanacak. Kyutai'nin belgesindeki "Prohibited use" bölümü, açık ve yasal onay olmadan ses taklidi/klonlamayı yasaklar; bu yüzden dublaj yalnız kişisel kullanım içindir (bkz. docs/kullanim/turkce-dublaj.md) |
| faster-whisper için Whisper modelleri | MIT (OpenAI Whisper) |

ElevenLabs bir bulut hizmetidir (kullanıcının kendi hesabı ve anahtarı); kullanım koşulları ElevenLabs'e aittir.

Dil/ses/OCR modelleri (Argos Translate dil paketleri, Whisper modelleri, RapidOCR modelleri) kendi lisanslarıyla ayrıca indirilir; yayından önce bunlar da gözden geçirilmelidir.

Esinlenilen projeler için bkz. [NOTICE](NOTICE): GameTranslator (Sefflex), CouchSubs (Sinan Yorulmaz).
