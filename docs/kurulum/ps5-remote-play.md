# PS5

PS5 → HDMI → TV kurulumunda bilgisayar oyunu **arka planda** izler: yazıları okur, çevirir, Türkçe sesi üretir.
Sen TV'de **kendi hesabın ve kendi kolunla** oynarsın.

> ⏳ Durum: gerçek PS5 ile henüz denenmedi. Program derleniyor ve kendi kendini sınıyor; PS5'le ilk deneme sizde.

## Önerilen yol: gizli bağlantı (pencere yok, kol göndermez)

Program PS5'e **ikinci bir PSN hesabıyla** kendisi bağlanır. Pencere açmaz, PS5'e **hiçbir kol/klavye tuşu göndermez**.
PS Remote Play uygulamasını kurmana gerek yoktur. (Yalnız Windows'ta.)

**Bir kez hazırlık:**
1. Ücretsiz **ikinci bir PSN hesabı** aç ve PS5'e **kullanıcı olarak ekle** (ana ekran → kullanıcı simgesi → Kullanıcı Ekle).
2. PS5'te **Ayarlar → Sistem → Uzaktan Oynatma → Uzaktan Oynatmayı Etkinleştir → Açık**.
3. (İsteğe bağlı) **Ayarlar → Sistem → Güç Tasarrufu → Dinlenme Modunda Mevcut Özellikler**:
   **İnternete Bağlı Kal** ve **Ağdan PS5'i Açmayı Etkinleştir** açık olsun; program PS5'i kendisi uyandırabilsin.

**Panelde (Görüntü adımı → cihaz: PS5 → "PS5'e gizli bağlan"):**
1. **İkinci hesapla giriş:** **Sony girişini aç** → Sony sayfasında **ikinci** hesapla gir → sayfa boş/hatalı görünebilir, normal →
   **adres çubuğundaki adresin tamamını** kopyala → panele yapıştır → **Kaydet**.
   Şifren yalnız Sony'ye gider. Program yalnız hesap kimliğini saklar (Windows'un şifreli kasasında).
2. **8 haneli kod:** PS5'te **ikinci kullanıcıya geç** → **Ayarlar → Sistem → Uzaktan Oynatma → Cihazı Bağla** →
   ekrandaki 8 haneli kodu panele yaz → **Bağla**. Sonra PS5'te **ana hesabına geri dön**.
3. **Bağlantı testi:** **Bağlan ve dene** → küçük canlı görüntü gelir →
   **"Kolun TV'de çalışmaya devam ediyor mu?"** → kolunla bir tuşa bas → **Evet** / **Hayır**.

Sonra **Başlat**'a bas. Bağlantı koparsa program kendisi yeniden bağlanır; PS5 dinlenme modundaysa uyandırır.
Türkçe dublaj açıksa oyunun sesi de bu bağlantıdan alınır (bilgisayarda çalınmaz; ses TV'den gelir).

### Kol TV'de çalışmazsa
- Kolundaki **PS tuşuna** bas, TV'de **ana hesabını** seç.
- PS5'te ikinci kullanıcı açık kaldıysa TV'de ana hesabına geç.
- Olmuyorsa panelde **Bağlantıyı kes**'e bas ve bize bildir (bu kısım gerçek PS5'te henüz doğrulanmadı).
  O arada aşağıdaki yedek yolu kullan.

## Yedek yol: resmî PS Remote Play penceresi

> ⚠️ Bir denemede resmî uygulama ikinci hesapla bile kontrolü laptopa aldı ve TV'deki kol çalışmadı.
> Bu yüzden yalnız gizli bağlantı çalışmazsa kullan.

1. Bilgisayara **PS Remote Play** uygulamasını kur (Sony'nin sitesinden), **ikinci hesapla** gir, PS5'e bağlan.
2. Panelde cihaz olarak **PS5**'i seç; listeden **PS Remote Play** penceresini seç.
3. Pencereyi **küçültme** (arkada kalabilir). Laptopta klavyeye/fareye dokunma: uygulama bunları PS5'e kol tuşu olarak gönderebilir.
4. Kol çalışmazsa PS tuşuna basıp ana hesabını seç.

## İpuçları
- TV'de gösterim için [LG kurulumu](lg-webos.md) veya [tarayıcı](tv-tarayici.md).
- Baştan sona rehber: [İlk deneme](ilk-deneme.md).
