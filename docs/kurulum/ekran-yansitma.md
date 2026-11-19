# Ekranı TV'ye ve monitöre bağlama (kolay rehber)

Çeviriyi nerede görmek istediğine göre en kolay yolu seç. Aynı rehberler programın içinde de var: ana ekranda **Bağlantı rehberleri** (ya da **Görünüm** menüsü).

## 1. Bu bilgisayarın ekranı (ya da monitör)
**Ne işe yarar?** Çeviri, oyunun üstünde saydam yazı olarak çıkar. Ek kurulum yok; en kolay yol bu.
1. Oyunun ayarlarında ekran modunu **Kenarlıksız** ya da **Pencereli tam ekran** yap.
2. Sihirbazda "Çeviriyi nerede göreyim?" adımında **Bu bilgisayarın ekranında** seç.
3. Birden fazla ekranın varsa oyunun açık olduğu ekranı seç; "Dene" ile deneme yazısı gönderilir.

**Sorun mu var?** Yazı yoksa oyunu Kenarlıksız moda al (özel tam ekranda yazı çıkamaz). Başka ekranda çıkıyorsa doğru ekranı seç. Yazı çok büyük/küçükse ekran yazı büyüklüğünü ayarla.

## 2. LG TV
**Ne işe yarar?** Küçük uygulamamızı LG TV'ye bir kez kurarsın; yazılar TV'de oyunun üstünde görünür.
1. TV ve bilgisayar aynı Wi-Fi'de olsun.
2. TV'de **Developer Mode** uygulamasını aç; Dev Mode Status ve Key Server açık olsun, ekrandaki kodu not et.
3. TV'nin IP adresini ve kodu panelde yaz.
4. **Kur**'a bas ve bekle.

**Sorun mu var?** Kod yanlışsa TV'deki kodu aynen tekrar yaz. TV bulunamıyorsa IP'yi TV Ayarlar > Ağ'dan kontrol et. Kurulmazsa TV'yi kapat-aç, Developer Mode'u yeniden aç. Ayrıntı: [lg-webos.md](lg-webos.md).

## 3. Samsung TV ve 4. Android / Google TV — ekranı yansıt
**Ne işe yarar?** Bilgisayar ekranını TV'ye yansıtırsın; oyun ve yazılar TV'de görünür. Küçük bir gecikme (yarım saniye kadar) olur; çok hızlı oyunlarda HDMI kablosu daha iyidir.
1. TV açık ve bilgisayarla **aynı Wi-Fi**'de olsun; TV'de ekran yansıtma açık olsun.
2. Bilgisayarda **Win + K**'ya bas (Yansıt / Cast listesi açılır).
3. Listeden TV'ni seç; TV onay sorarsa "İzin ver".
4. **Win + P** > **Çoğalt**; oyun hem bilgisayarda hem TV'de görünür.
5. Oyunu aç, çeviriyi "Bu bilgisayarın ekranında" göster.

**Alternatif (ayrı ekran):** TV'nin tarayıcısına `http://BİLGİSAYARIN-IP'Sİ:8642/tv` yaz. Yazı oyunun üstünde değil, ayrı bir ekranda görünür. Adresi program Bağlantı rehberleri'nde hazır gösterir.

**Sorun mu var?** TV listede yoksa Samsung'da Kaynak > Ekran Yansıtma'yı, Android/Google TV'de yerleşik Chromecast'i kontrol et (Chrome: menü > Kaydet, paylaş ve yayınla > Yayınla > Ekranı yayınla). Gecikme çoksa HDMI kablosunu dene. Ayrıntı: [samsung.md](samsung.md), [android-tv.md](android-tv.md), [tv-tarayici.md](tv-tarayici.md).

## 5. Apple TV (dürüst anlatım)
Windows'ta yerleşik AirPlay yok, Apple TV'de de internet tarayıcısı yok; bu yüzden adres yöntemi Apple TV'de çalışmaz.
1. **En kolayı:** bilgisayarı TV'ye HDMI kabloyla bağla (aşağıdaki 6. bölüm). Gecikme olmaz.
2. Ya da çeviriyi bilgisayarın ekranında göster.
3. AirPlay denemek istersen Windows için üçüncü taraf bir AirPlay gönderici gerekir (ör. AirParrot). Güvendiğin bir program seç; gecikme olur, hızlı oyunlar için önerilmez.
4. Telefon/tablet tarayıcısına `/tv` adresini yazarsan çeviri onda ayrı ekranda görünür.

## 6. Monitör / HDMI kablosu ile TV
**Ne işe yarar?** TV, bilgisayarın ikinci (ya da aynı) ekranı olur; yazılar TV'de oyunun üstünde görünür. Gecikme ve kurulum yok; en sağlam yol.
1. HDMI kablosunu bilgisayardan TV'ye tak.
2. TV kumandasında Kaynak/Input ile o girişi seç.
3. **Win + P**: aynı görüntü için **Çoğalt**, ayrı ekran için **Genişlet**.
4. Sihirbazda "Bu bilgisayarın ekranında"yı seç; birden fazla ekranda TV'nin ekranını işaretle.

**Sorun mu var?** Görüntü yoksa girişi yeniden seç, kabloyu çıkarıp tak. Bulanıksa çözünürlüğü TV'nin önerdiğine getir. Yazı TV'de çıkmıyorsa oyunu Kenarlıksız moda al ve doğru ekranı seç.
