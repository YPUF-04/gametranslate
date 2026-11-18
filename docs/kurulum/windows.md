# Windows'ta kurulum

> 📷 Resim: (sonra eklenecek) İndirilen zip dosyasının klasörde görünüşü.

## İndir ve aç

1. GitHub'daki **Releases** sayfasına git.
2. En üstteki sürümden **`AltYaziKoprusu-windows.zip`** dosyasını indir.
3. Dosyaya sağ tıkla, **Tümünü ayıkla**'ya bas.
4. **Ayıkla** düğmesine bas.

## Çalıştır

1. Açılan klasörde **`AltYaziKoprusu.exe`** dosyasına çift tıkla.
2. Mavi **"Windows bilgisayarınızı korudu"** ekranı çıkarsa **Ek bilgi**'ye bas.
3. **Yine de çalıştır**'a bas.

> 📷 Resim: (sonra eklenecek) SmartScreen uyarısı ve "Ek bilgi" / "Yine de çalıştır" düğmeleri.

Bu uyarı **normaldir**: Program henüz imzalı değil (imza sertifikası ücretli). Kaynak kodu açıktır, isteyen inceleyebilir.

3. Güvenlik duvarı "İzin ver" diye sorarsa **Özel ağlar**'ı işaretleyip **Erişime izin ver**'e bas. TV'nin bilgisayarı bulması için bu gerekir.
4. Tarayıcında panel açılır. Açılmazsa adres çubuğuna `http://127.0.0.1:8642` yaz.

## İlk ayar

Panelde 3 adımı izle: **oyunu seç**, **çeviri motorunu seç**, **test et**. Sonra **Başlat**.

## Sorun olursa

| Sorun | Ne yapmalı |
|---|---|
| Panel açılmıyor | Programı kapatıp yeniden aç. Adres: `http://127.0.0.1:8642` |
| TV bilgisayarı bulamıyor | Güvenlik duvarında izin ver; TV ve bilgisayar aynı ağda olsun |
| Kapı (8642) başka programda | Panelde **Gelişmiş** bölümünden kapı numarasını değiştir |

## Kaynaktan (ileri düzey)

Python 3.11+ kur, sonra klasörde: `pip install -e .[ocr-windows]` ve `python -m kopru`.
