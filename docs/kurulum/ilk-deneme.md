# İlk deneme: PS5 + laptop + LG TV (altyazı ve Türkçe dublaj)

Bu rehber baştan sona **her şeyi** sırayla anlatır. Hiç bilgisayar bilgisi gerekmez.
Toplam süre: ilk seferde yaklaşık **1–2 saat** (çoğu indirme beklemesi). Sonraki seferlerde 1 dakika.

> ⚠️ **Dürüst not:** Bu düzen (PS5 + laptop + LG TV + dublaj) gerçek cihazlarda **henüz hiç denenmedi**.
> Takıldığın yerde ekranın fotoğrafını çekip gönder; birlikte düzeltiriz.

## Nasıl çalışıyor? (3 cümle)

1. **PS5 → HDMI kablosu → LG TV.** Oyunu her zamanki gibi TV'de, kendi kolunla oynarsın. Görüntü gecikmez.
2. **Laptop** arka planda PS5'e **ikinci bir PSN hesabıyla** (Remote Play) bağlanır, ekrandaki yazıları okur, Türkçeye çevirir ve Türkçe sesi üretir. **Her şey laptopta çalışır.**
3. **TV'deki küçük uygulama** sadece aracıdır: laptoptan gelen Türkçe altyazıyı oyunun üstüne yazar ve Türkçe sesi çalar. TV'de ayar paneli yoktur.

## Neye ihtiyacın var?

| Ne | Not |
|---|---|
| PS5 | HDMI kablosuyla LG TV'ye bağlı |
| LG TV (webOS) | PS5 ile **aynı ev ağında** (aynı modem / Wi-Fi) |
| Windows laptop | Aynı ev ağında. Dublaj için NVIDIA ekran kartı (RTX 4060 gibi) ve **en az 15 GB boş disk** |
| İkinci PSN hesabı | Ücretsiz. Ayrı bir e-posta adresi gerekir (aşağıda anlatılıyor) |
| LG geliştirici hesabı | Ücretsiz. TV'ye uygulama kurmak için (aşağıda anlatılıyor) |
| Gemini anahtarı | Ücretsiz. Çeviri için (aşağıda anlatılıyor) |

---

## Bölüm 1 — Hesapları aç (bir kere, ~15 dakika)

### 1.1 İkinci PSN hesabı
Neden: Laptop PS5'e bu hesapla bağlanır; böylece senin kolun TV'den kopmaz.
1. Bilgisayarda [playstation.com](https://www.playstation.com) → **Oturum aç** → **Yeni hesap oluştur**.
2. **Kendi hesabından farklı bir e-posta** kullan (yoksa ücretsiz bir Gmail aç).
3. E-postana gelen onay bağlantısına tıkla.

### 1.2 LG geliştirici hesabı (TV'deki "yönetici" kısmı budur)
Neden: LG, mağaza dışından uygulama kurmak için TV'de **Developer Mode** (geliştirici modu) ister. Bunun için ücretsiz bir LG hesabı lazım. TV'de başka bir "admin paneli" yoktur.
1. Bilgisayarda [webostv.developer.lge.com](https://webostv.developer.lge.com) → sağ üstte **Sign In** → **Create Account** (hesap oluştur).
2. E-postanı onayla. Kullanıcı adını ve şifreni bir yere yaz; TV'de lazım olacak.

### 1.3 Gemini anahtarı (çeviri için)
1. [aistudio.google.com](https://aistudio.google.com) → Google hesabınla gir.
2. **Get API key → Create API key** → çıkan uzun yazıyı kopyala. Panelde yapıştıracaksın.

---

## Bölüm 2 — PS5 ayarları (~5 dakika)

1. **Ayarlar → Sistem → Uzaktan Oynatma → "Uzaktan Oynatmayı Etkinleştir"** → **Açık**.
2. **Ayarlar → Sistem → Güç Tasarrufu → Dinlenme Modunda Mevcut Özellikler** → **İnternete Bağlı Kal** ve **Ağdan PS5'i Açmayı Etkinleştir** → **Açık**.
3. PS5 ana ekranında kullanıcı simgesi → **Kullanıcı Ekle** → 1.1'de açtığın **ikinci hesapla** giriş yap. Sonra kendi hesabına geri dön.

---

## Bölüm 3 — Laptop (~20 dakika + indirme)

1. **AltYazıKöprüsü'nü kur:** kurulum dosyasını indir → çift tıkla → **İleri → Kur → Bitir**.
   Mavi "Windows bilgisayarınızı korudu" penceresi çıkarsa: **Ek bilgi → Yine de çalıştır**.
2. **Güvenlik duvarı sorusu** çıkarsa: **"Özel ağlar"** kutusunu işaretle → **Erişime izin ver**. (Yoksa TV laptopa ulaşamaz.)
3. **PS Remote Play** uygulamasını Sony'nin sitesinden ([remoteplay.dl.playstation.net](https://remoteplay.dl.playstation.net)) indir ve kur.
4. PS Remote Play'i aç → **ikinci PSN hesabıyla** giriş yap → **PS5** → bağlanmasını bekle.
   Bağlanınca laptop ekranında PS5'in görüntüsü çıkar. Bu pencereyi **açık bırak, simge durumuna küçültme** (arkada kalabilir).

---

## Bölüm 4 — LG TV (~15 dakika)

### 4.1 Geliştirici modunu aç
1. TV'de **LG Content Store** (uygulama mağazası) → arama: **Developer Mode** → **Yükle** → **Aç**.
2. 1.2'deki LG geliştirici hesabınla **Giriş yap**.
3. **Dev Mode Status** → **ON**. TV yeniden başlar.
4. Developer Mode uygulamasını yeniden aç → **Key Server** → **ON**.
5. Ekranda yazan **IP adresini** (ör. `192.168.1.35`) ve **Passphrase** kodunu (ör. `A1B2C3`) bir kâğıda yaz.

> ⏰ Geliştirici modu yaklaşık **50 saatte** bir kapanır. Uygulama açılmazsa Developer Mode uygulamasını açıp **Extend** (uzat) düğmesine bas.

### 4.2 TV uygulamasını laptoptan tek tuşla kur
1. Laptopta AltYazıKöprüsü panelinde **TV'ye tek tuşla kur** bölümünü aç (kurulum sihirbazının son adımı ya da **Gelişmiş ayarlar**).
2. TV'nin **IP adresini** ve **Passphrase**'i yaz.
3. Önce **Önce deneme uygulamasını kur** → TV'de **AltYazıKöprüsü Deneme** çıkarsa yol çalışıyor demektir.
4. Sonra **TV'ye kur** → bitince TV'de **AltYazıKöprüsü** uygulaması açılır.

**Kurmak istemezsen (yedek yol):** TV'nin **Web Tarayıcısı**'nı aç → adres çubuğuna `http://LAPTOPUN-IP-ADRESİ:8642/tv` yaz (laptopun IP adresi panelde yazar) → tam ekran yap.

---

## Bölüm 5 — Paneldeki kurulum (oyun açıkken)

1. **Görüntü:** cihaz olarak **PS5**, pencere olarak **PS Remote Play** penceresini seç.
2. **Yazı okuma:** önizlemede yazılar kutularla gösterilir. Gerekirse "İngilizce okuma paketini kur"a bas.
3. **Çeviri:** **Gemini** seç → anahtarını yapıştır → **Dene**.
4. **Nerede göreyim?** → **LG TV**.
5. **Çevrilecek yerler:** altyazının çıktığı yeri bir kutuyla çiz.
6. **Başlat** (ya da **Ctrl+Shift+T**). TV'de oyunun üstünde Türkçe altyazı görünmeli.

---

## Bölüm 6 — Türkçe dublaj (~10 dakika + 8–9 GB indirme)

1. Panelde **Türkçe dublaj** kartı → **Dublaj paketini kur** → onay kutusu → **Kur**.
   ~8–9 GB indirir; diskte ~12,5 GB yer kaplar. Yarıda kalırsa kaldığı yerden devam eder.
2. **Ses çıkışı → TV**.
3. **Dene** düğmesine bas → **TV'den Türkçe bir cümle duymalısın.**
   - Duyuyorsan harika, devam et.
   - **Duymuyorsan bana hemen haber ver.** Yedek yol: çıkışı **Bilgisayar** yap ve laptopu bir Bluetooth hoparlöre ya da LG'nin **Sound Share** özelliğine bağla.
4. **GTA 6'da:** Ayarlar → Ses → **Diyalog sesi** → **%10–20**. TV'de İngilizce konuşma neredeyse duyulmaz olur; laptop yine de karakterin sesini duyup taklit eder.
5. Dublajı **Açık** yap ve oyna. Altyazı çıkınca 1–2 saniye içinde Türkçe ses gelmeli.
6. (İsteğe bağlı) **Karakter seslerini hatırla:** karakterlerin sesleri bu laptopta saklanır; yeterince toplanınca Diyalog sesini 0'a çekebilirsin. Panelden istediğin zaman silebilirsin.

---

## Kısayollar (oyun sırasında)

| Tuş | Ne yapar |
|---|---|
| **Ctrl+Shift+T** | Çeviriyi başlat / durdur |
| **Ctrl+Shift+Y** | Yazıları gizle / göster |
| **Ctrl+Shift+R** | Ekranı hemen yeniden oku |

## Bir şey ters giderse

| Ne oluyor | Ne yapmalı |
|---|---|
| TV uygulaması laptopu bulamıyor | Aynı Wi-Fi'da mısınız? Güvenlik duvarında "Özel ağlar"a izin verdin mi? |
| TV'de uygulama açılınca oyun görüntüsü kayboluyor | Fotoğrafını çekip gönder (en önemli test noktası). |
| Dublajda TV'den ses gelmiyor | Bölüm 6, adım 3'teki yedek yolu kullan ve bana haber ver. |
| Remote Play bağlanmıyor | PS5 açık ya da dinlenme modunda mı? Bölüm 2'deki ayarlar açık mı? |
| Kolum TV'den koptu | Laptopun **ikinci hesapla** bağlandığından emin ol. |
| Yazılar çevrilmiyor | Kutunun altyazıyı kapsadığından emin ol; İngilizce okuma paketini kur. |

**Bana gönderirken ekle:** TV modeli ve webOS sürümü (TV'de Ayarlar → Genel → Cihaz Bilgisi), ekranın fotoğrafı, panelde **Ayrıntıyı göster** yazısı.
