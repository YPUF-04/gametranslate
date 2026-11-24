# TV tarayıcısı ve OBS (yedek yol)

Uygulama kurmadan da çeviriyi görebilirsin.

> ✅ **LG TV'de** tarayıcı sayfası konsolun HDMI görüntüsünü kendi içinde açar ve yazıyı **oyunun üstünde** gösterir
> (kurulum gerekmez): bkz. [LG kurulumu, bölüm 0](lg-webos.md). Diğer TV'lerin tarayıcıları yazıyı **ayrı bir ekranda**
> gösterir; o zaman telefonu/tableti yanına koyup bakmak ya da OBS kullanmak en iyisidir.

## TV tarayıcısı ile

1. Panelin ana ekranındaki **TV'de göster** kartında adresi gör. Kısa adres açıksa `http://192.168.1.20`, değilse
   `http://192.168.1.20:8642/tv`. Telefonda açmak için kartın yanındaki QR kodu okut.
2. TV'nin **web tarayıcısını** aç.
3. Adres çubuğuna bu adresi yaz.
4. Siyah bir sayfa açılır. Panelde **Örnek altyazıyı gönder**'e bas; yazıyı görmelisin.

> 📷 Resim: (sonra eklenecek) TV tarayıcısında siyah sayfada örnek altyazı.

Görünmüyorsa: TV ve bilgisayar aynı ağda mı? Güvenlik duvarı izin veriyor mu?

## OBS ile (oyunun üstüne bindirme)

OBS'te yakalama kartının görüntüsünün üstüne çeviriyi ekleyebilirsin.

1. OBS'te **Kaynaklar** bölümünde **+** düğmesine bas.
2. **Tarayıcı** seç, **Tamam**'a bas.
3. **URL** kutusuna `http://127.0.0.1:8642/obs` yaz.
4. Genişlik **1920**, yükseklik **1080** yaz. **Tamam**'a bas.
5. Bu kaynağı oyun görüntüsünün **üstüne** sürükle.

`/obs` sayfasının arka planı saydamdır; sadece yazı görünür.
