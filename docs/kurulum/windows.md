# Windows'ta kurulum

## İndir ve kur (önerilen)

1. GitHub'daki **Releases** sayfasına git: <https://github.com/YPUF-04/gametranslate/releases/latest>
2. **`AltYaziKoprusu-Windows-Kur.exe`** dosyasını indir ve çift tıkla. Yönetici izni gerekmez.
3. Mavi **"Windows bilgisayarınızı korudu"** ekranı çıkarsa **Ek bilgi**'ye, sonra **Yine de çalıştır**'a bas.

> 📷 Resim: (sonra eklenecek) SmartScreen uyarısı ve "Ek bilgi" / "Yine de çalıştır" düğmeleri.

Bu uyarı **normaldir**: Program henüz imzalı değil (imza sertifikası ücretli). Kaynak kodu açıktır, isteyen inceleyebilir.

4. Kurucu kendiliğinden kurar ve programı açar; başka bir şey sorulmaz.
5. Güvenlik duvarı "İzin ver" diye sorarsa **Özel ağlar**'ı işaretleyip **Erişime izin ver**'e bas. TV'nin bilgisayarı bulması için bu gerekir.
6. Tarayıcında panel açılır. Açılmazsa adres çubuğuna `http://127.0.0.1:8642` yaz.

**Taşınabilir yol (kurulumsuz):** aynı sayfadaki `AltYaziKoprusu-Tasinabilir-….zip` dosyasına sağ tıkla, **Tümünü ayıkla**'yı seç, klasördeki `AltYaziKoprusu.exe`'ye çift tıkla.

**Dosyam bozuk mu?** Aynı sayfadaki `SHA256SUMS.txt` içinde her dosyanın özeti yazar. PowerShell'de `Get-FileHash dosya.exe` yazıp çıkan değeri karşılaştırabilirsin.

## Güncelleme

Yeni sürüm çıkınca panelin üstünde **"Yeni sürüm hazır"** yazısı ve **Güncelle** düğmesi çıkar. **Güncellemeler artık sadece değişen parçaları indirir** (çoğu zaman birkaç MB; her seferinde ~120 MB değil). Düğmeye basınca program değişen parçaları indirir, doğrular, uygular ve kendini yeniden başlatır; ayarların, oyun hafızan ve indirdiğin **dublaj paketi** korunur (güncelleme dublaj paketini asla yeniden indirmez). Program günde en çok bir kez GitHub'a "yeni sürüm var mı?" diye sorar, hiçbir bilgin gönderilmez. İstemezsen **Gelişmiş ayarlar** > **Güncelleme** bölümünden kapatabilirsin; yine de **Güncellemeleri denetle** düğmesiyle kendin bakabilirsin.

## Eski sürümden (0.2 ve öncesi) geçiş

Eski kurucuyla kurduysan **bir kez** güncelleme tam boyutlu iner: panelde **Güncelle**'ye bas, gerisini program yapar (eski program kaldırılır, yenisi açılır; ayarların ve dublaj paketin korunur). Sonraki güncellemeler yalnız değişen parçaları indirir. Elle indirip `AltYaziKoprusu-Windows-Kur.exe` çalıştırdıysan eski sürümü **Ayarlar > Uygulamalar**'dan kaldırabilirsin.

## Kaldırma

**Ayarlar > Uygulamalar** bölümünden AltYazıKöprüsü'nü kaldır. Ayarların, oyun hafızan ve dublaj paketin bilgisayarda kalır (program klasörünün dışındadır); tamamen silmek istersen `%APPDATA%\AltyaziKoprusu` ve `%LOCALAPPDATA%\AltYaziKoprusu` klasörlerini sen sil.

## İlk ayar

Panelde adımları izle: **oyunu seç**, **çeviri motorunu seç**, **TV'ni bağla**, **test et**. Sonra **Başlat**.

## Sorun olursa

| Sorun | Ne yapmalı |
|---|---|
| Panel açılmıyor | Programı kapatıp yeniden aç. Adres: `http://127.0.0.1:8642` |
| TV bilgisayarı bulamıyor | Güvenlik duvarında izin ver; TV ve bilgisayar aynı ağda olsun |
| Kapı (8642) başka programda | Panelde **Gelişmiş** bölümünden kapı numarasını değiştir |
| Kısa adres (`http://<bilgisayar>` ) açılmıyor | Kapı 80'i başka bir program (IIS, Skype eski sürüm, başka web sunucusu) kullanıyor olabilir; panel o zaman uzun adresi (`…:8642/tv`) gösterir. Güvenlik duvarı izni program için verildiyse 80'i de kapsar. |

## Kaynaktan (ileri düzey)

Python 3.11+ kur, sonra klasörde: `pip install -e ".[ocr-windows,tv]"` ve `python -m kopru`.
