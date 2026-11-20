# Alınan kararlar (kullanıcıyla)

| Konu | Karar | Durum |
|---|---|---|
| Lisans | AGPL-3.0-only, GameTranslator/CouchSubs'a teşekkür NOTICE'de | Yapıldı |
| İlk hedef | Önce Windows bilgisayar + LG TV, sonra diğerleri | Sürüyor |
| Claude aboneliğiyle giriş | YOK (Anthropic kuralları). Sadece API anahtarı | Yapıldı |
| Oyun hafızası | Var; önce izin sorulur; sadece bu bilgisayarda | Sürüyor |
| Çeviri paketi paylaşımı | `.akpaket` dosyası, sadece cümleler | Sürüyor |
| Arayüz (premium, animasyonlu) | EN SONDA, Opus 5.5 ile | Bekliyor |
| İsim | "Gearly" ve "Subbly" dolu; arayüz aşamasında boş 3 isim önerilecek | Bekliyor |
| Reklam | İPTAL: proje kişisel/hobi amaçlı. Reklam ve hak sistemi yok; en fazla isteğe bağlı bağış bağlantısı. (Eski fikir: Model: ilk 30 dk ücretsiz çeviri, sonra reklam izle → süre kazan. Oyunun üstünde asla reklam yok. Takip/yorum karşılığı ödül YOK) | Karar |
| Maliyet | Geliştiriciye sıfır maliyet: çeviri kullanıcının bilgisayarında (yerel motor) ya da kullanıcının kendi anahtarıyla | Kural |
| Kurulum | Tek tuşla: Windows kurucu (.exe), panelden "TV'ye kur", tek tuşla güncelleme | Yazıldı, gerçek PC/TV'de denenmedi |
| Kod açık mı | AÇIK kalacak (AGPL). Güven + GitHub görünürlüğü | Karar |
| Cihaz sırası | Önce bilgisayarlar (Windows + Mac): bilgisayar çevirir, TV'de oyunun üstüne yansır. Telefon/tablet/iPhone sonra (beklemede) | Karar |
| Görünürlük | GitHub'da bulunabilirlik: README anahtar kelimeleri, konular (topics), sürümler, İngilizce tanıtım | Yapıldı (konuları sahibi elle girer: docs/GITHUB-GORUNURLUK.md) |
| Dağıtım / güncelleme | Yalnız GitHub Releases (sunucu yok, maliyet 0). Güncelleme günde en çok 1 kez, kimliksiz, kapatılabilir; indirilen dosya SHA256SUMS.txt ile doğrulanır | Kural |

## Reklam modeli için notlar (karar anında tekrar bakılacak)
- Google'ın "ödüllü reklam"ı (AdMob) telefon uygulamaları içindir; Windows masaüstü programında doğrudan yok.
  Bilgisayarda reklam için başka bir reklam ağı ya da telefondan "süre kazanma" gerekir — araştırılacak.
- AGPL açık kaynak: başkası kodu alıp reklamsız sürüm yayınlayabilir; bu yasal ve engellenemez.
- Reklam ağları veri toplayabilir; yalnız kişiselleştirilmemiş reklam seçilecek ve gizlilik belgesinde yazılacak.

## Türkçe dublaj 2 (canlı + video, ücretsiz yerel) — teknik kararlar (2026-11)
Hedef donanım: RTX 4060 dizüstü (8 GB ekran kartı belleği), Windows. Ayrıntılı sözleşme: PROTOKOL §14.

| Konu | Karar | Neden |
|---|---|---|
| Ana program / dublaj ayrımı | Ana exe küçük kalır; dublaj için ayrı **"Dublaj paketi"** (kendi Python'u + paketler + modeller) kullanıcı onayıyla `%LOCALAPPDATA%` altına kurulur, ağır işler **ayrı işçi sürecinde** (stdin/stdout JSON satırları + rastgele anahtar) | torch+CUDA ~3 GB; exe'ye konursa 120 MB → 3 GB+. İşçi çökse de program çökmez; VRAM yalnız işçide |
| Python | python-build-standalone `3.13.18+20261110` (SHA256 sabit) | Tek klasöre açılır, kurulum/yönetici izni istemez. 3.13: chatterbox-tts 0.1.7 burada numpy 2 ister → pocket-tts (numpy≥2) ile birlikte kurulabilir (3.11/3.12'de çakışır) |
| torch | `2.6.0+cu124` (PyTorch dizini) | chatterbox-tts 0.1.7, Python < 3.14 için `torch==2.6.0` sabitliyor; cu124 RTX 40 (sm_89) destekler, cuDNN 9 torch'un içinde gelir (faster-whisper/CTranslate2 de onu kullanır) |
| Ses motoru (varsayılan) | **Chatterbox Multilingual** (MIT, Türkçe dahil 23 dil, `exaggeration` ile duygu) | Türkçe sıfır-örnek klon + duygu denetimi + 8 GB'a sığıyor (~3–4 GB). Ağustos 2026'dan beri bakımı yok ama çalışıyor; sürüm sabitlendi |
| Değerlendirilen ama seçilmeyenler | VoxCPM2 (Apache-2.0, Türkçe var) ~8 GB VRAM ister → oyunla birlikte sığmaz; Higgs TTS 3 (9,3 GB) sığmaz; Fish Audio S2 Pro araştırma lisansı + büyük → eklenmedi | 8 GB dizüstünde oyunla yan yana çalışmalı; lisans temiz olmalı |
| Ayırma (konuşma / arka plan) | **HT-Demucs-ft konuşma uzmanı** (MIT), `demucs==4.1.0` ile **torch üzerinde** | ONNX sürümü onnxruntime-gpu ister; onnxruntime-gpu ile faster-whisper'ın onnxruntime'ı aynı modül adını paylaşır ve CUDA/cuDNN sürüm eşleşmesi Windows'ta kırılgan. torch zaten CUDA'lı → ek risk yok. Yalnız 4'lü torbanın konuşma modeli kullanılır (4 kat hızlı) |
| Konuşmadan yazıya | faster-whisper: video `large-v3-turbo` (kelime zamanlı), canlı `large-v3-turbo` / hafif modda `small` | turbo, large-v3 kalitesine yakın ve ~8 kat hızlı |
| Konuşmacı gruplama | Chatterbox'ın kendi ses kodlayıcısı (256 boyut) + kosinüs eşikli birleştirmeli kümeleme | Ek model yok; aynı kodlayıcı klonda da kullanılıyor |
| ffmpeg | Windows: gyan.dev `9.1 essentials` (SHA256 sabit); macOS/Linux: pip `imageio-ffmpeg` | Ana exe'ye girmez; sürüm sabit |
| Ses ayrımı ile canlı "tamamen Türkçe" | **Deneysel**, ayrı düğme. Windows'ta doğrulanmadı | Oyun sesini 0'a çekip ayrılmış arka planı ~2 sn gecikmeyle çalmak oyunu geciktirir; varsayılan "oyun sesini kıs" |
| Yasal | Dublaj kişisel kullanım içindir; yayınlamak hak sahiplerine tabidir (panelde ve PROTOKOL §14.6'da yazar). Ünlü/gerçek kişi ses paketi yok | Kural |
| Asıl kurulum (kullanıcı) | PS5 → HDMI → LG TV (görüntü + İngilizce ses TV'den); bilgisayar ikinci PSN hesabıyla Remote Play'den OCR + ses alır. Türkçe ses **TV uygulamasından** çalar (`cikis:"tv"`) | Altyazı zaten TV'de; dublaj aynı akışa eklenen ikinci katman |
| İngilizce sesi bastırma (TV kurulumu) | Oyunda **Diyalog sesi %10–20** (panelde adım). Program kısık sesi ayırıp düzeyini eşitler ve klon örneği yapar; izinli "Ses profili" ile sonra 0 yapılabilir (profilsiz karakter: nötr Türkçe ses) | TV'nin HDMI sesini bilgisayar silemez |
| Gecikme | Metin önce **ekrandaki altyazıdan**: altyazı belirdiği anda çeviri + seslendirme başlar, hazır olunca TV'ye gönderilir (cümlenin bitmesi beklenmez); Whisper yalnız altyazısız konuşmada. Akışlı seslendirme (ilk cümlecik çalar), modeller bellekte, karakter koşulları önbellekte | Kullanıcı 2 sn'yi uzun buldu |
| TV'de çalma | Web Audio sırası (öncekini kesmez; 6 sn'den eski atılır), yoksa `<audio>` sırası. Gerçek LG TV'de HDMI `<video>` üstünde ses çalma DOĞRULANMADI; çalmazsa yedek: bilgisayar çıkışı + Bluetooth hoparlör / LG Sound Share | Donanım yok |
| "Tamamen Türkçe" | Yalnız sesin bilgisayardan duyulduğu kurulumlar (Remote Play penceresi / yakalama kartı) için, deneysel; 0,25 sn bloklarla arka plan çalınır, Remote Play'de önce ölçülür (oturum sesi yakalamayı etkiliyor mu) | Windows'ta doğrulanmadı |
| Hafif mod | Varsayılan KAPALI: oyun PS5'te, dizüstünün ekran kartı boş. 180 sn boşta kalınca ses motoru ekran kartından indirilir | 8 GB'ı oyunla paylaşmıyoruz |
| Anka-TTS (F5, Türkçe) / OmniVoice | Değerlendirildi, şimdilik EKLENMEDİ: ağırlıklar CC-BY-NC (kişisel kullanım uygun ama lisans notu gerekir), Anka referans metni ister (canlıda İngilizce örnek + metin: diller arası kalite denenmedi), bu ortamdan Hugging Face'e erişim yoktu → denenemedi. İşçi ses motoru takılabilir (`motor` alanı), ileride "Sesleri karşılaştır" ile eklenebilir | Denenmeden varsayılan yapılmaz |
