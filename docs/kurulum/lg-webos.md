# LG TV (webOS) kurulumu

LG TV'de yazı oyunun **üstünde** görünür. İki yol var:

- **Önerilen — kurulum yok (TV'nin kendi tarayıcısı):** aşağıdaki "0" bölümü. Geliştirici modu ya da LG hesabı gerekmez.
- **Alternatif — TV uygulaması:** 1. bölümden itibaren. Tarayıcı yolu senin TV'nde görüntüyü açamazsa bunu kullan.

## 0. Önerilen: TV'nin tarayıcısıyla (kurulumsuz)

1. TV ile bilgisayar aynı modeme bağlı olsun (misafir ağı olmasın).
2. AltYazıKöprüsü panelinde ana ekrandaki **TV'de göster** kartında adresi gör. Genelde kısa adrestir:
   `http://192.168.1.20` (bilgisayarının adresi). Kısa adres açılamadıysa uzun adres yazar: `http://192.168.1.20:8642/tv`.
3. LG kumandasında **Ev** tuşu → **Web Browser** (İnternet Tarayıcısı) aç, adresi yaz, OK'a bas. Bir kez **Yer İmlerine** ekle.
4. Sayfa **"Konsol hangi HDMI girişine takılı?"** diye sorar. Okla seç, OK'a bas. Konsolun görüntüsü sayfanın içinde açılır,
   Türkçe yazı üstüne gelir. Sonraki açılışta seçimin hatırlanır (5 sn sayaçla kendiliğinden açılır).
5. Oynarken kumandada **OK** küçük bir menü açar (giriş değiştir, yalnız yazı, yeniden dene). **Ev** ya da **Giriş (Input)**
   tuşu sayfayı kapatır: tarayıcıyı yeniden aç.

**Görüntü açılmazsa:** sayfa "Bu TV'nin tarayıcısı HDMI görüntüsünü sayfada açamadı" der ve yazıları siyah ekranda
göstermeye devam eder. Önce konsolda **120 Hz** ve **HDR**'yi kapatıp çözünürlüğü **4K 60** ya da **1080p** yap, **Yeniden dene**.
Yine olmazsa aşağıdaki TV uygulaması yolunu kullan. (Benzer bir ürün bu yolun 2016 ve sonrası LG'lerde — webOS 3+ —
çalıştığını, 2021 ve sonrasını önerdiğini söylüyor. Biz gerçek bir LG TV'de henüz deneyemedik.)

**Ekran kararmasın:** OLED'lerde kumandaya uzun süre dokunulmazsa ekran koruyucu açılabilir. Paneldeki **TV ekranı
kararmasın (LG)** anahtarını aç, **TV ile eşleştir**'e bas ve TV'de çıkan soruya kumandayla **Kabul et** de (yalnız bir kez).
Çeviri sürerken bilgisayar 2 dakikada bir imleci 1 piksel oynatır. Ayrıca TV ayarlarında **Quick Start+**'ı kapatmak iyi olur.

**Konsolsuz dene:** panelde **Konsolsuz dene**'ye bas; örnek bir oyun sahnesi çevrilir ve Türkçe yazının TV'de nasıl
göründüğünü konsolu bağlamadan görürsün.

> 🔧 Durum: test ediliyor. Gerçek TV'lerde henüz tam doğrulanmadı.

## Önce: TV modelini ve webOS sürümünü bul

1. Kumandada **Ayarlar** (dişli) tuşuna bas.
2. **Tüm Ayarlar**'a gir.
3. **Genel** → **Cihaz Bilgisi** (bazı modellerde **Bu TV hakkında**) seç.
4. Model adını ve webOS sürümünü bir kâğıda yaz. Sorun olursa lazım olur.

## 1. Geliştirici modunu aç

1. TV'nde **LG Content Store**'u aç.
2. Aramaya **Developer Mode** yaz.
3. **Developer Mode** uygulamasını yükle ve aç.
4. [developer.lge.com](https://webostv.developer.lge.com) adresinde ücretsiz bir **LG developer hesabı** aç.
5. TV'deki uygulamada aynı hesapla **Giriş yap**.
6. **Dev Mode Status**'ü **ON** yap. TV yeniden başlar.
7. Yeniden açılınca uygulamada **Key Server**'ı da **ON** yap.
8. Ekranda görünen **TV'nin IP adresini** ve **Passphrase** kodunu not al.

> 📷 Resim: (sonra eklenecek) Developer Mode uygulaması: "Dev Mode Status: ON", IP adresi ve Passphrase.

> ⏰ **50 saat kuralı:** Geliştirici modu oturumu yaklaşık 50 saat sonra kapanır. Uygulama TV'den silinmez ama çalışmayabilir. Developer Mode uygulamasını açıp **Extend** (uzat) düğmesine bas; süre yeniden dolar.

## 2. Tek tuşla kur (önerilen)

Ek program kurman gerekmez; AltYazıKöprüsü TV'ye uygulamayı kendisi yükler.

1. AltYazıKöprüsü panelini aç (sihirbazın son adımı ya da **Gelişmiş ayarlar** > **TV'ye tek tuşla kur**).
2. **TV'nin IP adresini** ve TV ekranındaki **kodu (Passphrase)** kutulara yaz.
3. Önce **Önce deneme uygulamasını kur**'a bas. TV'nde **AltYazıKöprüsü Deneme** çıkarsa kurulum yolu çalışıyor demektir.
4. Sonra **TV'ye kur**'a bas. Aşamalar ekranda görünür: anahtar, bağlanma, gönderme, kurulum, bitti. Bitince uygulama TV'de kendiliğinden açılır.
5. Hata çıkarsa yazılan açıklamayı izle. **Ayrıntıyı göster** yazısını kopyalayıp bize gönderirsen sorunu çözmemiz kolaylaşır. İlk paket kurulmazsa **Başka bir sürümü dene** düğmesi var.

> Not: Bu özellik gerçek bir LG TV'de henüz denenmemiştir; kod LG'nin resmi `ares-install` aracının yaptığı işi birebir izler. Çalışmazsa aşağıdaki elle yöntemi kullanabilirsin.

## 2b. Elle kurulum (komut satırı)

Kurulum için LG'nin aracı gerekir. İki yol var; **birini** seç.

**A) Komut satırı**

1. Bilgisayarına [Node.js](https://nodejs.org) (LTS) kur.
2. **Başlat** menüsünde **Komut İstemi**'ni aç.
3. Şunu yaz: `npm install -g @webos-tools/cli`
4. TV'ni tanıt: `ares-setup-device --add tv --info "{'host':'TV_IP','port':'9922','username':'prisoner'}"` (`TV_IP` yerine TV'nin IP'sini yaz)
5. Anahtarı al: `ares-novacom --device tv --getkey` ve ekrandaki Passphrase'i gir.

**B) webOS Dev Manager** adlı görsel program da kullanılabilir (LG'nin geliştirici sitesinde). Aynı IP ve Passphrase bilgileri gerekir.

## 3. (Elle yöntemde) ÖNCE deneme uygulamasını kur

Gerçek uygulamadan önce küçük **deneme uygulamasını** kur. Böylece kurulum yolunun çalıştığını görürsün.

1. Sürüm sayfasından **`com.altyazikoprusu.deneme_*.ipk`** dosyasını indir.
2. Komut İstemi'nde: `ares-install --device tv com.altyazikoprusu.deneme_1.0.0_all.ipk` (dosya adını indirdiğinle aynı yaz)
3. `Success` yazarsa TV'nde uygulamalar listesinde **AltYazıKöprüsü Deneme** çıkar. Aç; yazı görürsen kurulum yolu çalışıyor.

## 4. (Elle yöntemde) Gerçek uygulamayı kur

1. Sürüm sayfasından **`com.altyazikoprusu.app_*.ipk`** dosyasını indir.
2. Komut İstemi'nde: `ares-install --device tv com.altyazikoprusu.app_1.0.0_all.ipk`
3. TV'nde **AltYazıKöprüsü** uygulamasını aç.
4. Uygulama bilgisayarı otomatik bulur. Bulamazsa IP adresini kendin yaz (panelde gösterilir).

## Sorun giderme

| Ne oluyor | Ne yapmalı |
|---|---|
| `-5: ipk verified failed` | Önce **deneme uygulamasını** kur. O kuruluyorsa sorun gerçek paketdedir. **Diğer paket çeşidini** (varsa) dene. Hâlâ olmazsa `ares-install` komutunun **tüm çıktısını** ve TV modelini/webOS sürümünü bize gönder. |
| `Unable to connect` / bağlanamıyor | TV ve bilgisayar aynı ağda mı? Developer Mode **ON** mu? IP doğru mu? |
| Uygulama bir gün sonra açılmıyor | 50 saat doldu. Developer Mode uygulamasında **Extend** bas. |
| Passphrase hatası | Developer Mode uygulamasını aç, **Key Server**'ı ON yap, kodu yeniden oku. |
| TV yazıyı göstermiyor | Panelde **Test et** adımını yap; olmazsa [TV tarayıcısı](tv-tarayici.md) yolunu dene. |

Yardım isterken ekle: TV modeli, webOS sürümü, `ares-install` çıktısı.
