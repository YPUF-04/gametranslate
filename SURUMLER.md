# Sürüm notları

## 0.1.6 — Dublaj hafızası, LG'de kurulumsuz kullanım, daha iyi çeviri (2026-11-27)
- **Dublaj hafızası:** her cümlenin Türkçe sesi (iznini verirsen) bilgisayarında saklanır. Aynı cümle ya da sahne yeniden gelince Türkçe **beklemeden** çalar; program sahneyi **oyunun sesinden tanır** (mikrofon yok), altyazı okunmadan bile İngilizce cümlenin başında Türkçeyi başlatır. Sıradaki cümleler önceden hazırlanır.
- **Boşta iyileştirme:** oynamıyorken her cümle için birkaç Türkçe ses üretilir; en anlaşılır, karaktere en çok benzeyen, süreye en iyi uyan seçilir. Panelde dinle, yeniden seslendir, metni düzelt; "Bu sahneyi en iyi kaliteyle hazırla"; kişisel yedek.
- **LG'de kurulum yok:** TV'nin kendi internet tarayıcısına bilgisayarın adresini yaz (çoğu zaman yalnızca `http://192.168.1.20`), konsolun HDMI girişini seç; oyun sayfanın içinde açılır, Türkçe üstüne gelir. Geliştirici modu ve LG hesabı gerekmez. Açılmazsa sayfa açıkça söyler ve yazıyı siyah ekranda göstermeye devam eder.
- **Ana ekranda "TV'de göster":** büyük, kolay yazılan adres ve telefon için QR kodu.
- **TV ekranı kararmasın (LG):** bir kez TV'de "Kabul et" de; çeviri sürerken ekran koruyucu açılmaz.
- **Konsolsuz dene:** örnek bir oyun sahnesiyle Türkçe yazının TV'de nasıl göründüğünü konsolu bağlamadan gör.
- **Altyazı görünümü:** yer (üstünü ört / alt / üst), boy (otomatik … çok büyük), arka plan (kutu / şerit / gölge / yok), renk (beyaz / sarı / açık mavi), kalınlık, konuşan adı göster/gizle — canlı önizlemeyle, TV'de anında.
- **Daha iyi çeviri:** iki karta bölünmüş cümleler tek cümle çevrilir; BAĞIRAN büyük harfli satırlar düzgün çevrilir; "Hope", "Dutch", "Valentine" gibi hem ad hem sözcük olan adlar korunur; oyun terimleri doğru Türkçe ekle yazılır ("Ölü Göz'ü"); pusula, para, cephane, süre gibi ekran sayıları çevrilmez.
- **Oyun sözlükleri kendiliğinden güncellenir:** GTA 6, GTA 5 ve RDR2 için adlar, yerler, çeteler ve oyun terimleri; program güncellemesi beklemeden GitHub'dan yenilenir.
- **"Hang up" gibi kısa yazılar** bazen çevrilmeden aynen gösteriliyordu. Program artık çeviri İngilizcenin aynısı gelirse ve içinde sıradan İngilizce kelimeler varsa (isim değilse) "bu bir isim değil, mutlaka çevir" diyerek bir kez daha soruyor. "Vice City" gibi gerçek isimlere dokunulmuyor.

## 0.1.5 — Yeni arayüz, TV kendiliğinden güncellenir, daha iyi çeviri (2026-11-24)
- **Yepyeni arayüz:** üstte büyük durum alanı (Çalışıyor / Durdu, gecikme), son çevrilen cümle, bağlantı şeridi (Görüntü · Çeviri · Gösterim · Dublaj) ve sorun varsa tek tıkla **Düzelt**. Program yavaşlarsa ya da kapanırsa sakin bir uyarı çıkar.
- **TV uygulaması artık kendiliğinden güncellenir:** TV'ye **son bir kez** yeni uygulamayı kur (panelde **TV'ye kur**); sonra laptoptaki program güncellenince TV de güncellenir.
- **Geliştirici modu süresi kendiliğinden uzar:** program açıkken her gün yenilenir, TV'de "Extend"e basmana gerek kalmaz.
- **Daha iyi çeviri:** sahnedeki son 8 cümle ve konuşanlar hatırlanır, karakterler arası "sen/siz" tutarlı kalır, sokak ağzı doğal Türkçeye çevrilir.
- **Çeviri kalitesi ayarı:** Hızlı / **Dengeli (önerilen)** / En iyi. Dengeli'de ekranda uzun kalan cümleler arka planda daha iyi çevrilip yerinde düzeltilir.
- **Ekran okuma düzeltmeleri:** iki satıra bölünmüş cümleler birleşir, I/l ve 0/O karışıklıkları düzelir.

## 0.1.4 — Altyazı yeniden çevriliyor, dublaj hızlandı (2026-11-23)
- **Altyazı çevrilmiyordu, düzeltildi.** Gemini'ye gönderilen bir hız ayarı yeni modelde geçersizdi; her çeviri zaman aşımına uğruyordu. Artık her modele uygun ayar gidiyor; Gemini yoğunsa yedek modelle bir kez daha deneniyor.
- **Daha doğal çeviri:** konuşan karakterin adı ve kadın/erkek olduğu dikkate alınır; günlük konuşma Türkçesi kuralları eklendi.
- **Dublaj çok daha hızlı:** altyazının Türkçesi doğrudan seslendirilir (ikinci çeviri beklenmez), ses modeli ekran kartında hazır bekler, cümleler sırayla ve parça parça TV'ye gider.
- **Kadın karakter kadın sesiyle:** ses inceliğinden ve oyun bilgisinden kadın/erkek anlaşılır; karakterin sesi henüz toplanmadıysa uygun hazır ses kullanılır.
- **Daha az robot sesi:** ses ayarları Türkçe için yeniden ayarlandı.
- **Dublaj tanı:** dublaj kartında "Ekran kartında çalışıyor ✓" ya da "İşlemcide çalışıyor" yazar; işlemcideyse **Onar** düğmesiyle düzeltilir. Son 5 cümlenin gecikmesi de görünür.
- **Ses yapay zekâsının yüklenmesi** artık takılırsa sonsuza dek beklemez, açık hata verir.
- **LG TV uygulamasını bir kez yeniden kur** (panelde **TV'ye kur**).

## 0.1.3 — Altyazı sınırsız, dublaj "+30 dk", çeviri İngilizcenin üstünü kaplar (2026-11-23)
- **Altyazı çevirisi artık herkese sınırsız ve ücretsiz.** Günlük 30 dakika sınırı kalktı.
- **Türkçe dublaj süreyle çalışır:** panelde **"+30 dk ekle"**ye bas, kısa bir reklam (ya da 15 saniyelik teşekkür ekranı) izle, 30 dakika dublaj kazan. Üst üste ekleyebilirsin (en fazla 4 saat). Süre yalnız dublaj çalışırken azalır; program kapanınca silinir.
- **Reklam TV'de de oynar:** LG TV uygulaması açıksa reklam oyunun üstünde kısa süre tam ekran oynar. **LG TV uygulamasını bir kez yeniden kur** (panelde **TV'ye kur**).
- **Süre bitince** dublaj sakince durur, altyazılar devam eder.
- **Reklam izni:** reklam şirketinin reklamı yalnız izin verirsen açılır; vermezsen hiçbir yere bilgi göndermeyen teşekkür ekranı çıkar. Ayarlardan her an değiştirilebilir.
- **Sınırsız dublaj kodu:** Erişim kartındaki **cihaz numaranı** gönder, sana özel kodu yaz; o bilgisayarda dublaj kalıcı olarak sınırsız olur. Eski kodlar da çalışır.
- **Çeviri İngilizce yazının tam üstüne gelir** ve onu kaplar; yazı kutuya sığacak boyutta olur. (Eski görünüm için: Ayarlar → Yazı nerede? → Altta.)
- **Kol tuşları kapanmaz:** ✕ ○ △ □, R2, OPTIONS gibi tuş işaretleri olduğu gibi kalır.
- **Simgeler ve emojiler çevrilmez:** yalnız gerçek kelimeler çevrilir; can barı, sayaç, koordinat gibi şeyler atlanır.
- **Hızlı konuşmada cümle atlamaz:** çeviriler sırayla ve daha hızlı gelir; her cümle okunacak kadar ekranda kalır.
- **Güncelleme bildirimi:** yeni sürüm çıkınca en üstte "Yeni sürüm var, indirmek ister misin?" ve "Neler yeni?" listesi çıkar.
- **Küçük güncellemeler:** bundan sonraki güncellemeler yalnız değişen parçaları indirir.

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
