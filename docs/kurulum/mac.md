# macOS kurulumu

Bu rehber Mac'e programı kurmayı, ilk kez açmayı ve ekran izni vermeyi anlatır. Hepsi birkaç tıklama.

> 🔧 Durum: **beta**. Henüz gerçek bir Mac'te tam denenmedi. Sorun olursa GitHub'da bir "issue" aç, ne olduğunu yaz.

## Önce bil: neden "tanınmayan geliştirici" uyarısı çıkıyor?

Apple'ın uygulama onayı (imza) ücretli bir üyelik ister. Bu proje ücretsiz ve gönüllü; o parayı vermiyoruz. Bu yüzden Mac "bu programı tanımıyorum" diyecek. Program güvenli; kaynak kodu GitHub'da herkese açık. Aşağıda uyarıyı bir kereliğine nasıl geçeceğin yazıyor.

Hangi dosyayı indireceğini seç:
- **Apple Silicon** (M1, M2, M3, M4 yazan Mac): `AltYaziKoprusu-<sürüm>-mac-arm64.dmg`
- **Intel** Mac: `AltYaziKoprusu-<sürüm>-mac-x86_64.dmg`
- Emin değilsen: ekranın sol üstündeki elma → **Bu Mac Hakkında**. "Çip: Apple M..." yazıyorsa Apple Silicon'dur; "İşlemci: Intel" yazıyorsa Intel'dir.

## 1. Kur

1. GitHub'daki **Releases** (Sürümler) sayfasından `.dmg` dosyasını indir.
2. İndirilenler'de `.dmg` dosyasına çift tıkla. Küçük bir pencere açılır.
3. Penceredeki **AltYazıKöprüsü** simgesini tutup yanındaki **Uygulamalar** klasörünün üstüne sürükle, bırak.
4. Pencereyi kapat. Sol taraftaki yan çubukta `AltYazıKöprüsü` diskinin yanındaki çıkar (⏏) düğmesine bas.

> 📷 Resim: (sonra eklenecek) .dmg penceresi: uygulama simgesi ve Uygulamalar klasörü.

## 2. İlk kez aç (yalnız bir kere)

Normal çift tıklama ilk seferde **çalışmaz**; uyarı çıkar. Şöyle aç:

1. **Finder**'ı aç (Dock'taki yüzlü simge).
2. Sol tarafta **Uygulamalar**'a tıkla.
3. **AltYazıKöprüsü**'nü bul. Üstüne **sağ tıkla** (iki parmakla dokun ya da Control tuşuna basılı tutup tıkla).
4. Çıkan listeden **Aç**'ı seç.
5. "Açmak istediğinden emin misin?" diye bir pencere çıkar. Yine **Aç**'a bas.

Bundan sonra normal çift tıklamayla açılır.

**Daha yeni macOS'ta (Sequoia ve sonrası) sağ tık yetmeyebilir.** O zaman:

1. Uygulamaya çift tıkla. "Açılamadı" uyarısı çıkar; **Tamam**'a bas.
2. **Sistem Ayarları**'nı aç (elma → Sistem Ayarları).
3. Soldan **Gizlilik ve Güvenlik**'e tıkla.
4. Aşağı kaydır. "AltYazıKöprüsü engellendi" gibi bir yazı göreceksin. Yanındaki **Yine de Aç** düğmesine bas.
5. Mac şifreni (ya da parmak izini) yaz. Sonra yine **Aç**'a bas.

Program açılınca tarayıcında panel kendiliğinden açılır. Açılmazsa tarayıcıya `http://127.0.0.1:8642/` yaz.

> 📷 Resim: (sonra eklenecek) Gizlilik ve Güvenlik sayfasında "Yine de Aç" düğmesi.

## 3. Ekran Kaydı iznini ver

Program oyunun ekranındaki yazıyı "görüp" okur. Mac, bir programın ekranı görmesine ancak sen izin verirsen izin verir. Bu izin olmadan **yazılar okunamaz**: panel çalışır ama çeviri çıkmaz; ekran boş ya da yalnızca duvar kâğıdı gibi görünür.

1. **Sistem Ayarları**'nı aç.
2. Soldan **Gizlilik ve Güvenlik**'e tıkla.
3. **Ekran ve Sistem Ses Kaydı**'na tıkla. (Eski macOS'ta adı **Ekran Kaydı**.)
4. Listede **AltYazıKöprüsü**'nü bul ve yanındaki düğmeyi **aç** (yeşil olsun). Listede yoksa önce programdan bir kez ekran okumayı dene; o zaman listeye eklenir. Yine yoksa alttaki **+** düğmesiyle Uygulamalar'dan ekle.
5. Mac şifreni yaz. "Şimdi Kapat" ya da "Çık ve Yeniden Aç" diye sorarsa kabul et.
6. **Programı tamamen kapat** (Dock'taki simgeye sağ tıkla → **Çık**) ve yeniden aç. İzin ancak yeniden açılınca geçerli olur.

> 📷 Resim: (sonra eklenecek) Ekran ve Sistem Ses Kaydı listesinde AltYazıKöprüsü açık.

## Olmuyor mu?

- **"Hasarlı" ya da "açılamıyor" diyor:** Terminal'i aç, şunu yaz, Enter'a bas, sonra 2. adımı tekrarla:
  `xattr -cr /Applications/AltYazıKöprüsü.app`
- **Yazılar okunmuyor:** 3. adımdaki izin açık mı ve program yeniden başlatıldı mı, kontrol et.
- **İndirdiğin dosya bozuk mu?** Sürüm sayfasındaki `SHA256SUMS-mac.txt` dosyasındaki özetle karşılaştır: Terminal'de `shasum -a 256 ~/Downloads/<dosya>.dmg`.

Programı kaldırmak için Uygulamalar'dan **AltYazıKöprüsü**'nü Çöp Kutusu'na sürükle.

## Merak edenler için: kaynaktan çalıştırma

Python 3.11+ gerekir. Terminal'de: `pip install -e ".[tv,ocr-mac]"` ve ardından `python -m kopru`.
