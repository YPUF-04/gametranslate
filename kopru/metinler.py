# SPDX-License-Identifier: AGPL-3.0-only
"""Kullanıcıya görünen metinler (tr + en). Ne oldu + ne yapmalı, tek cümle."""
from __future__ import annotations

HATALAR: dict[str, dict[str, str]] = {
    "yalniz_yerel": {
        "tr": "Bu sayfaya yalnızca bu bilgisayardan erişilebilir.",
        "en": "This page is only available from this computer."},
    "gecersiz_istek": {
        "tr": "İstek okunamadı, lütfen sayfayı yenileyip tekrar deneyin.",
        "en": "The request could not be read, please refresh the page and try again."},
    "gecersiz_ayar": {
        "tr": "Bu ayar değeri geçersiz, lütfen listeden bir seçenek seçin.",
        "en": "This setting value is invalid, please pick one from the list."},
    "bulunamadi": {
        "tr": "Aranan sayfa bulunamadı.", "en": "The requested page was not found."},
    "anahtar_yok": {
        "tr": "Bu çeviri motoru için anahtar girilmemiş, lütfen ayarlardan anahtarı ekleyin.",
        "en": "No key is saved for this translation engine, please add it in settings."},
    "anahtar_gecersiz": {
        "tr": "Anahtar kabul edilmedi, lütfen anahtarı kontrol edip yeniden girin.",
        "en": "The key was not accepted, please check it and enter it again."},
    "ag_hatasi": {
        "tr": "Çeviri servisine ulaşılamadı, internet bağlantınızı kontrol edin.",
        "en": "The translation service could not be reached, please check your internet connection."},
    "motor_hatasi": {
        "tr": "Çeviri motoru çalışmadı, başka bir motor seçmeyi deneyin.",
        "en": "The translation engine failed, please try another engine."},
    "kasa_yok": {
        "tr": "Bu bilgisayarda güvenli anahtar kasası bulunamadı, anahtar kaydedilemedi; "
              "işletim sisteminin parola/anahtarlık hizmetini açın ve tekrar deneyin.",
        "en": "No secure key vault was found on this computer so the key was not saved; "
              "enable the system keyring service and try again."},
    "kasa_hata": {
        "tr": "Anahtar kasasına erişilemedi, kasanın kilidini açıp tekrar deneyin.",
        "en": "The key vault could not be accessed, please unlock it and try again."},
    "yakalama_yok": {
        "tr": "Ekran görüntüsü alınamadı, ekran kaynağını ve izinleri kontrol edin.",
        "en": "The screen could not be captured, please check the source and permissions."},
    "kaynak_yok": {
        "tr": "Yakalanacak ekran seçilmemiş, lütfen listeden oyunun göründüğü ekranı seçin.",
        "en": "No screen is selected, please pick the screen that shows the game."},
    "okuma_yok": {
        "tr": "Ekrandaki yazıyı okuyacak bileşen kurulu değil, kurulum kılavuzuna bakın.",
        "en": "No text recognition component is installed, please see the setup guide."},
    "oyun_yok": {
        "tr": "Bu oyun bulunamadı, lütfen listeden mevcut bir oyun seçin ya da yeni oyun ekleyin.",
        "en": "This game was not found, please pick one from the list or add a new game."},
    "oyun_gecersiz": {
        "tr": "Oyun adı geçersiz, lütfen en fazla 100 karakterlik bir ad yazın.",
        "en": "The game name is invalid, please enter a name of up to 100 characters."},
    "paket_gecersiz": {
        "tr": "Bu dosya geçerli bir çeviri paketi değil, lütfen AltYazıKöprüsü'nden alınmış "
              ".akpaket dosyası seçin.",
        "en": "This file is not a valid translation pack, please choose an .akpaket file "
              "exported from AltYazıKöprüsü."},
    "paket_buyuk": {
        "tr": "Çeviri paketi çok büyük (en fazla 50 MB), lütfen daha küçük bir paket seçin.",
        "en": "The translation pack is too large (50 MB at most), please choose a smaller one."},
    "oneri_yok": {
        "tr": "Bu öneri artık listede yok, lütfen öneri listesini yenileyin.",
        "en": "This suggestion is no longer in the list, please refresh the suggestions."},
    "guncelleme_desteklenmiyor": {
        "tr": "Tek tuşla güncelleme yalnızca Windows'ta çalışır, yeni sürümü GitHub'dan indirin.",
        "en": "One-click update only works on Windows, please download the new version from GitHub."},
    "guncelleme_yok": {
        "tr": "Kurulacak yeni bir sürüm yok, programınız güncel.",
        "en": "There is no new version to install, your program is up to date."},
    "guncelleme_denetlenemedi": {
        "tr": "Yeni sürüm denetlenemedi, internet bağlantınızı kontrol edip tekrar deneyin.",
        "en": "The update check failed, please check your internet connection and try again."},
    "guncelleme_indirilemedi": {
        "tr": "Yeni sürüm indirilemedi, internet bağlantınızı kontrol edip tekrar deneyin.",
        "en": "The new version could not be downloaded, please check your internet connection and try again."},
    "guncelleme_dogrulanamadi": {
        "tr": "İndirilen dosya doğrulanamadı ve kurulmadı, lütfen sonra tekrar deneyin ya da GitHub'dan elle indirin.",
        "en": "The downloaded file could not be verified and was not installed, please try again later or download it from GitHub."},
    "guncelleme_adres": {
        "tr": "Güncelleme adresi güvenli görünmüyor ve kullanılmadı, lütfen yeni sürümü GitHub'dan elle indirin.",
        "en": "The update address does not look safe and was not used, please download the new version from GitHub."},
    "guncelleme_baslatilamadi": {
        "tr": "Kurucu başlatılamadı, indirilen dosyayı elle çalıştırmayı ya da GitHub'dan yeniden indirmeyi deneyin.",
        "en": "The installer could not be started, please run the downloaded file by hand or download it again from GitHub."},
    "tv_gecersiz_ip": {
        "tr": "TV adresi geçersiz görünüyor, TV'deki Developer Mode uygulamasında yazan adresi (örn. 192.168.1.30) yazın.",
        "en": "The TV address looks invalid, please enter the address shown in the TV's Developer Mode app (e.g. 192.168.1.30)."},
    "tv_gecersiz_parola": {
        "tr": "Kod boş ya da geçersiz, TV'deki Developer Mode uygulamasındaki 6 haneli kodu (Passphrase) yazın.",
        "en": "The code is empty or invalid, please enter the 6-character code (Passphrase) from the TV's Developer Mode app."},
    "tv_gecersiz_paket": {
        "tr": "Bilinmeyen paket seçildi, lütfen listeden bir seçenek seçin.",
        "en": "An unknown package was chosen, please pick one from the list."},
    "tv_mesgul": {
        "tr": "TV kurulumu zaten sürüyor, bitmesini bekleyin.",
        "en": "A TV install is already running, please wait for it to finish."},
    "tv_ulasilamadi": {
        "tr": "TV'ye ulaşamadım. TV açık mı ve bilgisayarla aynı ağda mı?",
        "en": "I could not reach the TV. Is it on and on the same network as this computer?"},
    "tv_anahtar_kapali": {
        "tr": "TV anahtarını vermedi. TV'deki Developer Mode uygulamasında Key Server'ı açıp tekrar deneyin.",
        "en": "The TV did not hand out its key. Turn Key Server on in the TV's Developer Mode app and try again."},
    "tv_parola_yanlis": {
        "tr": "Kod yanlış görünüyor. TV'deki Developer Mode uygulamasındaki 6 haneli kodu tekrar yazın.",
        "en": "The code looks wrong. Please type the 6-character code from the TV's Developer Mode app again."},
    "tv_oturum_bitti": {
        "tr": "TV'nin geliştirici modu kapanmış olabilir (50 saatte kapanır). TV'de Developer Mode uygulamasını açıp "
              "Dev Mode Status'u açın ve Extend ile süreyi uzatın, sonra tekrar deneyin.",
        "en": "The TV's developer mode may have expired (it closes after 50 hours). Open the Developer Mode app on the TV, "
              "turn Dev Mode Status on and press Extend, then try again."},
    "tv_paket_yok": {
        "tr": "Kurulacak TV paketi programın içinde bulunamadı, programı yeniden kurun.",
        "en": "The TV package was not found inside the program, please reinstall the program."},
    "tv_eklenti_yok": {
        "tr": "TV'ye kurulum bileşeni (paramiko) bu bilgisayarda yok, programı yeniden kurun.",
        "en": "The TV install component (paramiko) is missing on this computer, please reinstall the program."},
    "tv_yukleme_hatasi": {
        "tr": "Dosya TV'ye gönderilemedi, TV'de boş yer olduğundan emin olup tekrar deneyin.",
        "en": "The file could not be sent to the TV, make sure it has free space and try again."},
    "tv_kurulum_hatasi": {
        "tr": "TV uygulamayı kabul etmedi. Önce deneme uygulamasını kurmayı deneyin; olmazsa \"Ayrıntıyı göster\" yazısını bize gönderin.",
        "en": "The TV did not accept the app. Try the test app first; if that fails, send us the text under \"Show details\"."},
    "tv_hata": {
        "tr": "TV kurulumu tamamlanamadı. Tekrar deneyin; olmazsa \"Ayrıntıyı göster\" yazısını bize gönderin.",
        "en": "The TV install did not finish. Please try again; if it fails, send us the text under \"Show details\"."},
    "tv_asama_anahtar": {
        "tr": "TV'den anahtar alınıyor...", "en": "Getting the key from the TV..."},
    "tv_asama_baglaniyor": {
        "tr": "TV'ye bağlanılıyor...", "en": "Connecting to the TV..."},
    "tv_asama_yukleniyor": {
        "tr": "Uygulama TV'ye gönderiliyor...", "en": "Sending the app to the TV..."},
    "tv_asama_kuruluyor": {
        "tr": "TV uygulamayı kuruyor...", "en": "The TV is installing the app..."},
    "tv_bitti": {
        "tr": "Kuruldu. Uygulama TV'de açılıyor.", "en": "Installed. The app is opening on the TV."},
    "tv_bitti_acilmadi": {
        "tr": "Kuruldu. Uygulamayı TV'nin uygulamalar listesinden açın.",
        "en": "Installed. Open the app from the TV's app list."},
    "sunucu_hatasi": {
        "tr": "Beklenmeyen bir sorun oluştu, programı yeniden başlatmayı deneyin.",
        "en": "Something unexpected went wrong, please try restarting the program."},
}

DIGER: dict[str, dict[str, str]] = {
    "deneme_tr": {"tr": "Merhaba! Bu bir deneme altyazısıdır.", "en": "Hello! This is a test subtitle."},
    "tv_adres": {"tr": "TV'de bu adresi açın: {adres}", "en": "Open this address on the TV: {adres}"},
    "panel_adres": {"tr": "Kontrol paneli: {adres}", "en": "Control panel: {adres}"},
    "demo_acik": {"tr": "Deneme modu: örnek altyazılar gönderiliyor.",
                  "en": "Demo mode: sending sample subtitles."},
    "durdu": {"tr": "Kapatıldı.", "en": "Stopped."},
}


def mesaj(kod: str, dil: str = "tr") -> str:
    tablo = HATALAR.get(kod) or DIGER.get(kod) or HATALAR["sunucu_hatasi"]
    return tablo.get(dil) or tablo["tr"]
