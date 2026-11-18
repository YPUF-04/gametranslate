# TV tarayıcısı ve OBS (yedek yol)

Uygulama kurmadan da çeviriyi görebilirsin.

> ⚠️ **Önemli fark:** TV'nin tarayıcısı yazıyı **ayrı bir ekranda** gösterir; oyunun **üstünde** değil. En iyisi telefonu/tableti yanına koyup bakmak ya da OBS kullanmaktır. Oyunun üstünde gösterim için [LG kurulumu](lg-webos.md).

## TV tarayıcısı ile

1. Panelin **Test et** adımında TV adresini gör. Şuna benzer: `http://192.168.1.20:8642/tv`
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
