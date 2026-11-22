# Sürüm notları

## 0.1.3 — Çeviri İngilizcenin üstünü kaplar, cümle atlamaz (2026-11-22)
- **Çeviri İngilizce yazının tam üstüne gelir** ve onu kaplar; yazı kutuya sığacak boyutta olur. (Eski görünüm için: Ayarlar → Yazı nerede? → Altta.)
- **Kol tuşları kapanmaz:** ✕ ○ △ □, R2, OPTIONS gibi tuş işaretleri olduğu gibi kalır.
- **Simgeler ve emojiler çevrilmez:** yalnız gerçek kelimeler çevrilir; can barı, sayaç, koordinat gibi şeyler atlanır.
- **Hızlı konuşmada cümle atlamaz:** çeviriler sırayla ve daha hızlı gelir; her cümle okunacak kadar ekranda kalır.
- **Güncelleme bildirimi:** yeni sürüm çıkınca en üstte "Yeni sürüm var, indirmek ister misin?" ve "Neler yeni?" listesi çıkar.
- **Küçük güncellemeler:** bundan sonraki güncellemeler yalnız değişen parçaları indirir.
- **LG TV uygulamasını bir kez yeniden kur:** yeni görünüm için panelde **TV'ye kur**'a bir kez daha bas.

## 0.1.2 — LG TV kurulum düzeltmesi (2026-11-22)
(0.1.1'in kurulum dosyaları üretilemedi; aynı düzeltme bu sürümle geliyor.)
- **LG TV'ye tek tuşla kurulum:** bazı LG TV'lerde "AuthenticationException" hatasıyla bağlantı reddediliyordu. TV'nin eski bağlantı sistemi yeni imza yöntemini tanımıyordu; program artık reddedilince TV'nin anladığı eski yöntemle yeniden dener.
- Bu sürüm programın içinden gelir: panelde **Güncelle**'ye basman yeter. Bu sefer güncelleme **tam paket** (~80 MB) iner; küçük parça (delta) dosyası henüz üretilemiyor (programın Türkçe harfli adı paketleme aracını şaşırtıyor), sonraki sürümde düzeltilecek.

## 0.1.0 — İlk sürüm (2026-11-21)

**İlk deneme sürümü.** Gerçek cihazlarda (PS5, LG TV) ilk kez kullanılacak; hata görürsen lütfen [bildir](https://github.com/YPUF-04/gametranslate/issues/new/choose).
Adım adım kurulum: **[İlk deneme rehberi](https://github.com/YPUF-04/gametranslate/blob/main/docs/kurulum/ilk-deneme.md)** (PS5 + laptop + LG TV).

### Hangi dosyayı indireyim?
- **İlk kez kuruyorsan:** `AltYaziKoprusu-Windows-Kur.exe`
- **Daha önce deneme sürümü kurduysan:** `AltYaziKoprusu-Kur-0.1.0.exe` (eskisini kaldırıp yeni güncelleme sistemine geçirir; ayarların ve dublaj paketin korunur)
- Mac: `.dmg`

### Neler var?
- **PS5'e gizli bağlantı:** laptop PS5'e ikinci PSN hesabıyla, pencere açmadan ve hiçbir tuş göndermeden bağlanır; sen TV'de kendi kolunla oynarsın. (Sony'nin Remote Play penceresi yedek yol olarak duruyor.)
- **LG webOS TV uygulaması:** Türkçe altyazıyı oyunun üstüne yazar, Türkçe dublajı çalar; panelden **tek tuşla kurulum**. Kurmadan TV tarayıcısıyla da açılır.
- **Türkçe dublaj (deneysel):** karakterler kendi seslerine benzer bir sesle Türkçe konuşur. Altyazı ekrana düştüğü anda hazırlanır. Ses yapay zekâsı bilgisayarında çalışır (ücretsiz, NVIDIA ekran kartı önerilir); ~8–9 GB'lık dublaj paketi panelden, onayınla bir kez iner.
- **Video dublajı:** kayıtlı oyun videonu seç; İngilizce sesler silinir, müzik/efekt kalır, herkes kendi sesine benzer sesle Türkçe konuşur.
- **Kurulum sihirbazı + sade ana ekran:** ilk açılışta adım adım kurulum, sonra her ayarın yanında tek **Değiştir** düğmesi.
- **Kısayol tuşları:** Ctrl+Shift+T başlat/durdur, Ctrl+Shift+Y gizle/göster, Ctrl+Shift+R yeniden oku (değiştirilebilir).
- **Oyundaki kadar ekranda kalır:** çeviri, oyundaki yazı ne kadar duruyorsa o kadar durur; yazı gidince çeviri de gider.
- **Daha iyi çeviri:** "KILLER" gibi tek, büyük harfli kelimeler ve menü yazıları da çevrilir; yalnız gerçek isimler aynen kalır.
- **Çevrilecek yerleri kendin seç**, **oyun hafızası** (Düzelt ile kalıcı düzeltme), çeviri motorları: Gemini, Claude, DeepSeek, DeepL ve **internetsiz** motor.
- **Küçük güncellemeler:** sonraki sürümlerde program yalnız değişen parçaları indirir; dublaj paketin ve ayarların hiç yeniden inmez.
- **Gizlilik:** takip yok, reklam yok; anahtarlar şifreli kasada; mikrofon asla açılmaz; PSN şifren programa hiç girmez.

### Bilinen sınırlar
- Tam ekran (exclusive fullscreen) oyunlarda çeviri penceresi görünmeyebilir → oyunu "Pencereli tam ekran" yap.
- Netflix/Disney+ gibi korumalı videolar ekrandan okunamaz.
- PS5 gizli bağlantı, LG TV uygulaması, TV'den dublaj sesi ve Xbox akışı gerçek cihazda **henüz denenmedi**.
- Küçük güncellemeler bir sonraki sürümden (0.1.1) itibaren başlar; bu ilk sürüm tam iner.
