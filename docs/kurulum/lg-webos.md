# LG TV (webOS) kurulumu

LG TV'de yazı oyunun **üstünde** görünür. Bunun için küçük TV uygulamasını TV'ne kurman gerekir. Bu rehber adım adım gider.

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

## 2. Bilgisayara kurulum aracını yükle

Kurulum için LG'nin aracı gerekir. İki yol var; **birini** seç.

**A) Komut satırı (önerilen)**

1. Bilgisayarına [Node.js](https://nodejs.org) (LTS) kur.
2. **Başlat** menüsünde **Komut İstemi**'ni aç.
3. Şunu yaz: `npm install -g @webos-tools/cli`
4. TV'ni tanıt: `ares-setup-device --add tv --info "{'host':'TV_IP','port':'9922','username':'prisoner'}"` (`TV_IP` yerine TV'nin IP'sini yaz)
5. Anahtarı al: `ares-novacom --device tv --getkey` ve ekrandaki Passphrase'i gir.

**B) webOS Dev Manager** adlı görsel program da kullanılabilir (LG'nin geliştirici sitesinde). Aynı IP ve Passphrase bilgileri gerekir.

## 3. ÖNCE deneme uygulamasını kur

Gerçek uygulamadan önce küçük **deneme uygulamasını** kur. Böylece kurulum yolunun çalıştığını görürsün.

1. Sürüm sayfasından **`com.altyazikoprusu.deneme_*.ipk`** dosyasını indir.
2. Komut İstemi'nde: `ares-install --device tv com.altyazikoprusu.deneme_1.0.0_all.ipk` (dosya adını indirdiğinle aynı yaz)
3. `Success` yazarsa TV'nde uygulamalar listesinde **AltYazıKöprüsü Deneme** çıkar. Aç; yazı görürsen kurulum yolu çalışıyor.

## 4. Gerçek uygulamayı kur

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
