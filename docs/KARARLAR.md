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
| Reklam | DEĞİŞTİ (2026-11, sahibin kararı): program ücretsiz ve açık kaynak, **dublaj süresi reklamla desteklenir**. Altyazı herkese sınırsız; yalnız Türkçe dublaj süreli ("+30 dk ekle" = bir reklam ya da 15 sn destek ekranı). Oyunun üstünde reklam yalnız kullanıcı düğmeye basınca, kısa ve tam ekran oynar; kendiliğinden asla. Reklam şirketi reklamı yalnız açık izinle (KVKK). Ayrıntı aşağıda ve PROTOKOL §17 | Karar |
| Maliyet | Geliştiriciye sıfır maliyet: çeviri kullanıcının bilgisayarında (yerel motor) ya da kullanıcının kendi anahtarıyla | Kural |
| Kurulum | Tek tuşla: Windows kurucu (.exe), panelden "TV'ye kur", tek tuşla güncelleme | Yazıldı, gerçek PC/TV'de denenmedi |
| Kod açık mı | AÇIK kalacak (AGPL). Güven + GitHub görünürlüğü | Karar |
| Cihaz sırası | Önce bilgisayarlar (Windows + Mac): bilgisayar çevirir, TV'de oyunun üstüne yansır. Telefon/tablet/iPhone sonra (beklemede) | Karar |
| Görünürlük | GitHub'da bulunabilirlik: README anahtar kelimeleri, konular (topics), sürümler, İngilizce tanıtım | Yapıldı (konuları sahibi elle girer: docs/GITHUB-GORUNURLUK.md) |
| Dağıtım / güncelleme | Yalnız GitHub Releases (sunucu yok, maliyet 0). Güncelleme günde en çok 1 kez, kimliksiz, kapatılabilir; Windows'ta **Velopack**: yalnız değişen parçalar iner (aşağıdaki bölüm); eski yol/macOS'ta indirilen tam kurucu SHA256SUMS.txt ile doğrulanır | Kural |

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
| Gerçek deneme (2026-11-20, Linux CPU, GPU yok) | Gerçek işçi + gerçek modellerle (Chatterbox çok dilli, Whisper small, HT-Demucs-ft) 12 sn'lik sentetik İngilizce sahne (2 konuşmacı + müzik) uçtan uca Türkçe dublajlandı; çıktı Whisper'a göre Türkçe (0,88). Çeviri bu denemede LLM'siz sabit sözlükle yapıldı. Bulunanlar düzeltildi: `setuptools<81` (filigran paketi `pkg_resources` ister), STT'ye dosya yerine dizi verilir (PyAV sürüm farkı), sesler üst üste binmez, kısa metinde uydurma uzun ses bir kez yeniden üretilir. Konuşmacı gruplama bu denemede 2 kişiyi 3 küme yaptı (eşik ayarı gerçek oyun sesiyle denenmeli) | GPU/Windows/TV davranışı doğrulanmadı |

## Velopack ile "sıfırdan indirmeden" güncelleme (2026-11) — teknik kararlar
İstek: "güncellemeleri uygulama üzerinden yapalım, 0'dan hep indirmeyelim." Ayrıntı: PROTOKOL §8.

| Konu | Karar | Neden |
|---|---|---|
| Araç | **Velopack** (MIT): python paketi `velopack==1.2.161` + `vpk` 1.2.161 (aynı sürüm, sabit) | PyInstaller `--onedir` ile çalışır, delta paket, GitHub Sürümleri kaynağı, sunucu gerekmez. PyPI'de `win_amd64` tekerleği var |
| Yeni kurulum | **Velopack Setup.exe** (Sürümlerde `AltYaziKoprusu-Windows-Kur.exe` adıyla). Inno Setup yeni kurulumda ARTIK kullanılmaz | Tek kurulum = tek güncelleme yolu: kurulum + güncelleyici + kaldırıcı Velopack'tan; iki ayrı mekanizma bakımı yok. Yönetici izni istemeyen, kullanıcı başına kurulum korunur |
| Inno'nun kalan işi | `paketleme/windows/gecis.iss`: yalnız **geçiş kurucusu**, `AltYaziKoprusu-Kur-<sürüm>.exe` adıyla | Eski sürümlerin güncelleyicisi tam bu adı arar, SHA256SUMS ile doğrular ve `/VERYSILENT` çalıştırır; içine Velopack Setup'ı koyup eski programı kaldırdığı için elle indirme gerekmez. Eski sürüm kalmadığında kaldırılabilir |
| Geçiş (bir kez) | Eski Inno kurulumu → "Güncelle" → tam boyutlu indirme (geçiş kurucusu ≈ Velopack Setup) → eski program kaldırılır, yenisi açılır. Sonraki güncellemeler delta | Bir kerelik tam indirme kabul edildi |
| `packId` | `AltYaziKoprusu.Program` (**`AltYaziKoprusu` DEĞİL**) | Velopack kökü `%LOCALAPPDATA%\<packId>`; Setup kurarken o klasörü SİLER ("Failed to remove existing application directory") ve kaldırırken kökü temizler. Dublaj paketi `%LOCALAPPDATA%\AltYaziKoprusu\dublaj-ortami` (çok GB, PROTOKOL §14) o kökün içinde kalırdı → farklı kimlik kullanıldı, veri yolları değişmedi |
| Kullanıcı verisi | Ayarlar `%APPDATA%\AltyaziKoprusu`; dublaj `%LOCALAPPDATA%\AltYaziKoprusu\dublaj-ortami`; anahtarlar Credential Manager. Hiçbiri `%LOCALAPPDATA%\AltYaziKoprusu.Program` altında değil (test: `test_kullanici_verisi_velopack_klasorunun_disinda`) | Güncelleme/kaldırma veriyi silemez; güncelleme dublaj paketini yeniden indirmez |
| Delta üretimi | CI: `vpk download github` ile önceki Sürüm indirilir, `vpk pack` aynı klasörde delta üretir; yalnız yeni sürümün dosyaları yüklenir | Velopack'ın önerdiği akış; önceki Velopack Sürümü yoksa (ilk Velopack sürümü) tam paket |
| Delta, Türkçe ad (2026-11) | Windows işi `vpk pack --delta BestSpeed` dener, olmazsa `--delta none`. Ayrı **Linux işi** (`delta`) aynı vpk 1.2.161 ile `vpk download github` → `vpk delta generate` → `vpk delta patch` ile doğrular (lib/ dosyaları birebir) → `paketleme/velopack_delta.py` `releases.win.json` (Full'ün arkasına Delta kaydı: SHA1/SHA256/boyut/notlar), `assets.win.json` ve `SHA256SUMS.txt`'yi günceller; `RELEASES` değişmez (vpk de yazmaz). Herhangi bir adım olmazsa dosyalar aynen geçer (sürüm delta'sız çıkar). `--packTitle "AltYazıKöprüsü"` (kısayol adı) korunur | vpk 1.2.158+ başlatıcıyı `--packTitle`'dan adlar (`AltYazıKöprüsü_ExecutionStub.exe`, velopack#985) ve Windows zstd.exe 1.5.5 ASCII dışı yolu açamaz (velopack#1105, zstd#3882); düzeltme yalnız 1.3 ön sürümünde (#1113), python `velopack==1.2.161` ile aynı sürüm şartı yüzünden yükseltilmedi. `--packTitle`'ı ASCII yapmak kısayol adını bozardı; `--noStub` 1.2.161'de yok ve taşınabilir sürümün başlatıcısını kaldırırdı. Linux zstd UTF-8 adları açar; Linux'ta gerçek 0.1.2 paketinden delta üretimi ve geri uygulama denendi |
| Yükleme | Mevcut `softprops/action-gh-release` ile Velopack dosyaları + SHA256SUMS.txt + not (`SURUMLER.md`) tek Sürüme konur; `vpk upload` kullanılmadı | Sürüm notu / ön sürüm bayrağı akışı korunur; yüklenen dosyalar `vpk upload`'unkilerle aynı |
| Doğrulama | Velopack her paketin SHA256'sını `releases.win.json`'dan denetler; SHA256SUMS.txt eski yol ve elle indirenler için durur | |
| Yedek yol | `velopack` yoksa / program Velopack'la kurulu değilse (geliştirme, macOS, zip) eski tam-kurucu yolu | Hiçbir senaryo güncellemesiz kalmaz |
| İmza | Velopack paketleri imzasız (sertifika yok); SmartScreen uyarısı eskisi gibi | |

## PS5 gizli bağlantı (2026-11) — teknik kararlar
Sözleşme: PROTOKOL §15. Neden: gerçek denemede resmî PS Remote Play uygulaması (laptopta İKİNCİ hesapla
açıkken bile) kontrolü laptopun klavyesine aldı, TV'deki DualSense oyunu kontrol edemedi.

| Konu | Karar | Neden |
|---|---|---|
| Nasıl bağlanıyoruz | chiaki-ng'nin `libchiaki`'si (AGPL-3.0, **v1.10.1**, commit `f30da0a`) üstüne **kendi küçük C yardımcımız** `ayk-uzaktan.exe` (`uzaktan/ayk_uzaktan.c`) | GameTranslator da libchiaki kullanır (GameTranslator.RemotePlay + yerel DLL); kodlarını kopyalamadık, yaklaşımı inceleyip kendimiz yazdık. chiaki-ng ve biz AGPL: kütüphaneyi kullanmak serbest |
| ctypes + DLL yerine ayrı süreç | Yardımcı ayrı bir **süreç**; Python onunla stdin/stdout borularıyla konuşur | libchiaki'nin iş parçacıkları/çökmesi ana programı düşürmez; geri çağrı (callback) ve yapı (struct) düzenini Python'da kopyalamak gerekmez (sürüm değişince sessizce bozulur); kolay yeniden başlatma = otomatik yeniden bağlanma; sahte yardımcıyla tam sınanabilir |
| Gizli değerler | Hesap kimliği, kayıt anahtarları, PIN **komut satırında değil stdin'de**; kasada (keyring) saklanır, ayar dosyasında yok | Başka süreçler komut satırını görebilir; API anahtarlarıyla aynı kural |
| Kareler | Yardımcı her kareyi çözer (H.264 akışı kesintisiz çözülmeli) ama **yalnız istenince** BGRA'ya çevirip yollar | OCR saniyede birkaç kare ister; 720p BGRA ≈ 3,7 MB, sürekli göndermek boşa yük |
| Görüntü | PS5'ten 720p/30 H.264 (ayar: 540/720/1080, h264/hevc) | Altyazı okumaya yeter, yazılımla çözmesi ucuz; dizüstünün ekran kartı dublaja kalır |
| Ses | Opus → 48 kHz stereo → **16 kHz mono** (yardımcıda) → ana programın 127.0.0.1 kapısı (oturum başına rastgele anahtar) → dublaj işçisi | İşçi zaten 16 kHz bekliyor; ses bilgisayarda çalınmaz (TV çalıyor) |
| FFmpeg | Kaynaktan, yalnız `h264`+`hevc` çözücü ve swscale, **LGPL** (`--enable-gpl` yok), statik | Tek dosya, ek DLL yok; lisans uyumlu |
| Windows derlemesi | GitHub Actions `windows-latest` + MSYS2 MINGW64, `-static` → **tek ~10 MB exe**, yalnız Windows sistem DLL'lerine bağlı; paketin `_internal/uzaktan/` klasöründe, Velopack paketlemesinden ÖNCE | CI'da `--help`, `ozdenetim` ve paketlenmiş programın `--ozdenetim-uzaktan` adımı çalışır |
| PSN hesap kimliği | chiaki-ng'nin belgelediği resmî Remote Play OAuth girişi; kullanıcı Sony sayfasında girer, yönlendirme adresini panele yapıştırır | Uygulama içi tarayıcımız yok (panel bir web sayfası); şifre programa hiç girmez, belirteç saklanmaz |
| Anahtar biçimi | Yardımcı libchiaki'nin çözülmüş 16 baytını 32 hex olarak verir; Python yalnız bu biçimi kabul eder | GameTranslator'ın düzelttiği hata: anahtarı metin olarak saklamak oturumu `0x80108b26` ile reddettirir |

### Kol (DualSense) neden TV'de kalmalı — bulgular ve kalan risk (dürüstçe)
- **libchiaki ne gönderir (kaynaktan doğrulandı):** `lib/src/feedbacksender.c` oturum boyunca en geç 200 ms'de bir
  "geri bildirim durumu" paketi yollar; içinde `chiaki_controller_state_set_idle` ile kurulmuş **boştaki kol** vardır.
  Kol durumu yalnız `chiaki_session_set_controller_state` çağrılınca değişir; yardımcımız bunu **hiç** çağırmaz
  (testle korunuyor: `tests/test_ps5.py::test_yardimci_kol_girdisi_gondermez`). Klavye ve DualSense özellikleri kapalı açılır.
  Yani PS5'e giden tek "kol" verisi: hiç tuşa basılmamış, çubukları ortada bir kol.
- **Resmî uygulamada neden kontrol kaydı (tahmin, doğrulanmadı):** resmî PC uygulaması klavyeyi/fareyi ve bağlı kolu
  gerçek bir DualSense gibi PS5'e yollar; pencere odaktayken her tuş gerçek girdidir. PS5 de son girdiyi veren uzak
  kullanıcıyı öne alabilir / oyun girdiyi "aktif" kola bağlayabilir. Bizim istemcide gerçek girdi hiç olmadığı için bu
  tetiklenmemeli. Ancak PS5'in oturum açılırken odağı uzaktaki kullanıcıya **kendiliğinden** verip vermediğini (ör. ikinci
  kullanıcıyı öne almak) Sony'nin kapalı yazılımı belirler; kaynak kodda göremeyiz.
- **GameTranslator'ın notu:** "İkinci hesap sayesinde kol kopmaz" der; ama Windows dağıtımı resmî chiaki-ng uygulamasını
  da paketliyor ve bu iddianın ölçümü yayınlanmamış. Bizim kullanıcımızın denemesi ikinci hesabın tek başına yetmediğini gösterdi.
- **Kalan risk:** gerçek PS5'te hiç denenmedi. Kol yine bırakırsa: panel bağlantı testinde sorar ("Kolun TV'de çalışıyor mu?"),
  "Hayır"da PS tuşu → ana hesap seçimini önerir. Sonraki deneme adımı: libchiaki'ye küçük bir yama ile geri bildirim
  paketlerini tamamen kapatmak (oturumun bunsuz açık kalıp kalmadığı da bilinmiyor; o yüzden şimdilik yapılmadı).


## Erişim 2: altyazı sınırsız, dublaj reklamla (2026-11) — PROTOKOL §17
| Konu | Karar | Neden |
|---|---|---|
| Ne sınırlı | Altyazı/ekran çevirisi herkese sınırsız. Yalnız Türkçe dublaj süreli | Sahibin kararı. Altyazı ana iş; dublaj ağır ve "ekstra" |
| Süre | "+30 dk ekle": her basış +30 dk, üst üste, en çok 4 sa. **Yalnız bellekte**: program kapanınca gider, açılışta 0 | Basit; kapatıp açarak süre kazanılmaz; diske yazılan sayaç kurcalanamaz |
| Ne zaman azalır | Yalnız dublaj gerçekten çalışırken (Başlat + dublaj açık / video işi). 0'da dublaj sakince duraklar, altyazı sürer | Kullanıcı boşa süre kaybetmesin |
| Süreyi kim verir | PC (sunucu saati). İstemci "bitti" der; reklam süresi (en az 15 sn) geçmeden kabul edilmez | İstemci kandırılamasın (aşağıdaki not geçerli) |
| Reklam oynatıcı | **Kendi küçük VAST 3/4 ayrıştırıcımız + `<video>`** (`kopru/web/tv/reklam.js`), Google IMA SDK DEĞİL | IMA'nın LG webOS desteği "seçili modeller, hesap yöneticinize sorun" düzeyinde (developers.google.com/interactive-media-ads/docs/sdks/other); IMA her açılışta Google'dan uzak betik yükler (paketli TV uygulaması file://'dan çalışır, panel dış betik yüklemez); IMA Google'a bağlıdır, bizimki her VAST ağıyla çalışır. Bedeli: VPAID/SIMID/OMID yok → bunları isteyen reklamlar "reklam gelmedi" sayılır, yerine destek ekranı |
| Reklam gelmezse | 15 sn kendi "destek" ekranımız, sonra yine +30 dk | Kullanıcı asla takılı kalmaz |
| Reklam nerede | TV uygulaması bağlıysa TV'de, oyunun üstünde tam ekran; değilse panelde. `/obs` asla | Kullanıcı TV'ye bakıyor; yayına reklam girmesin |
| Reklam izni (KVKK) | Reklam şirketinin reklamı ilk kez açılmadan önce izin ekranı; izin yoksa yalnız destek ekranı (hiçbir yere bağlanmaz). Ayarlardan geri alınır | Reklam ağı IP/cihaz bilgisi alabilir; açık rıza gerekir |
| Sınırsız kod | Cihaza bağlı (`sinirsiz_dublaj`, 10 harflik cihaz numarası, Ed25519 imzalı, sunucusuz). Eski `sinirsiz`/`gun` kodları geçerli | Sunucu yok, maliyet yok; kod başka bilgisayarda işe yaramaz |
| Dürüst not | Açık kaynak (AGPL): sınırlar kullanıcının bilgisayarında çalışır, kaldıran kopya yapılabilir; bu yasaldır | Sistem dürüst kullanıcılar içindir, kilit değildir |

## Model lisansları ve reklamlı (ticari sayılabilecek) dağıtım (2026-11-23 denetimi)
Reklam geliri olduğu için "ticari olmayan" şartı taşıyan bir model kullanılamaz. Durum:

| Model | Nereden | Lisans | Reklamlı dağıtım |
|---|---|---|---|
| Chatterbox Multilingual | `ResembleAI/chatterbox` | MIT | Uygun |
| Kyutai Pocket TTS | `kyutai/pocket-tts` | CC BY 4.0 (+ "yasak kullanım" koşulu: rızasız ses klonlama) | Uygun, **atıf gerekir**. Ses klonlama koşulu ayrıca dikkat ister (aşağı) |
| Pocket TTS Türkçe | `kaanhgunay/pocket-tts-tr` v0.1-base | CC BY 4.0 | Uygun, **atıf gerekir** (THIRD-PARTY-NOTICES.md'de yazılı) |
| Whisper (faster-whisper `large-v3-turbo`, `small`) | OpenAI / Systran / mobiuslabsgmbh | MIT (turbo dönüşümünde etiket yok, kaynak MIT) | Uygun |
| HT-Demucs-ft | `demucs` 4.1.0 | MIT | Uygun |
| RapidOCR modelleri | `rapidocr_onnxruntime` (PaddleOCR) | Apache-2.0 | Uygun |
| **Argos en↔tr 1.5** | `argos-net.com` | **Belirtilmemiş** (dizinde lisans alanı boş) | **İŞARETLİ: belirsiz.** Yazılım MIT/CC0 ama dil paketinin lisansı ve eğitim verisinin (OPUS) ticari kullanım şartı doğrulanamadı. Sahip, Argos geliştiricisine sormalı ya da yerel motoru reklamlı sürümde "kullanıcı kendisi indirir" diye açıkça belirtmeli |

- **Ses klonlama:** Kyutai'nin koşulu "açık ve yasal rıza olmadan ses taklidi/klonlama" yasaklar. Oyun karakterinin sesinden örnek almak bu açıdan gri alandır (seslendirme sanatçısının rızası yok). Reklam geliri bunu değiştirmez ama riski artırır; dublaj "kişisel kullanım" olarak sunulmaya devam etmeli (docs/kullanim/turkce-dublaj.md).
- ElevenLabs (bulut) kullanıcının kendi hesabı ve şartlarıyla çalışır; bizim dağıtımımız değildir.
