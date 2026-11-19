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
    "desteklenmiyor": {
        "tr": "Bu özellik yalnız Windows'ta var.",
        "en": "This feature is only available on Windows."},
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
        "tr": "TV'nin geliştirici modu kapalı ya da süresi dolmuş olabilir (50 saatte kapanır); TV'de Developer Mode "
              "uygulamasını açın, Dev Mode Status ve Key Server açık olsun, süre dolduysa Extend ile uzatıp tekrar deneyin.",
        "en": "The TV's developer mode may be off or expired (it closes after 50 hours); open the Developer Mode app on "
              "the TV, make sure Dev Mode Status and Key Server are on, press Extend if time ran out, then try again."},
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
    "gecersiz_kod": {
        "tr": "Bu kod geçerli değil. Harfleri kontrol edip tekrar deneyin.",
        "en": "This code is not valid. Please check the letters and try again."},
    "suresi_dolmus_kod": {
        "tr": "Bu kodun süresi dolmuş. Yeni bir kod isteyin ya da yarın ücretsiz süreyle devam edin.",
        "en": "This code has expired. Ask for a new one, or continue tomorrow with the free time."},
    "ucretsiz_bitti": {
        "tr": "Bugünkü ücretsiz süre doldu. Erişim kodunu girin ya da yarın devam edin.",
        "en": "Today's free time is used up. Enter an access code or continue tomorrow."},
    "dublaj_motor_yok": {
        "tr": "Önce dublaj için bir ses motoru seçin (Chatterbox, Pocket veya ElevenLabs), sonra tekrar deneyin.",
        "en": "First pick a voice engine for dubbing (Chatterbox, Pocket or ElevenLabs), then try again."},
    "dublaj_paket_yok": {
        "tr": "Dublaj için gereken ek paket kurulu değil. Komut satırında şunu çalıştırıp programı yeniden açın: "
              "pip install \"altyazikoprusu[dublaj]\"",
        "en": "The extra package needed for dubbing is not installed. Run this in a terminal and reopen the "
              "program: pip install \"altyazikoprusu[dublaj]\""},
    "dublaj_hazir_degil": {
        "tr": "Ses motoru henüz hazır değil, lütfen önce \"Hazırla\" düğmesine basın ve bitmesini bekleyin.",
        "en": "The voice engine is not ready yet, please press \"Prepare\" first and wait until it finishes."},
    "dublaj_indirme_hata": {
        "tr": "Ses modeli indirilemedi, internet bağlantınızı kontrol edip \"Hazırla\" düğmesine tekrar basın.",
        "en": "The voice model could not be downloaded, please check your internet connection and press \"Prepare\" again."},
    "dublaj_yukleme_hata": {
        "tr": "Ses modeli yüklenemedi, bellek yetmemiş olabilir; daha hafif olan Pocket motorunu deneyin.",
        "en": "The voice model could not be loaded, memory may be too low; try the lighter Pocket engine."},
    "dublaj_uretim_hata": {
        "tr": "Ses üretilemedi, birkaç saniye sonra tekrar deneyin; sürerse Pocket motorunu seçin.",
        "en": "The voice could not be generated, try again in a few seconds; if it keeps failing pick the Pocket engine."},
    "dublaj_cikis_yok": {
        "tr": "Ses çalınamadı, hoparlör ya da kulaklığın bağlı ve varsayılan çıkış olduğunu kontrol edin.",
        "en": "The sound could not be played, check that your speakers or headphones are connected and set as default."},
    "dublaj_ses_kaynagi": {
        "tr": "Oyunun sesi dinlenemedi, varsayılan ses çıkışını kontrol edin; mikrofon hiçbir zaman kullanılmaz.",
        "en": "The game audio could not be listened to, check the default sound output; the microphone is never used."},
    "dublaj_macos_ses": {
        "tr": "macOS'ta oyun sesini dinlemek için BlackHole gibi bir sanal ses aygıtı kurup sistem çıkışı yapın.",
        "en": "On macOS, install a virtual audio device such as BlackHole and set it as the system output to listen to game audio."},
    "dublaj_onay_gerekli": {
        "tr": "ElevenLabs için önce \"ses örneği ElevenLabs'e gider\" onayını işaretleyin.",
        "en": "For ElevenLabs, first tick the consent that the voice sample goes to ElevenLabs."},
    "dublaj_eleven_anahtar_yok": {
        "tr": "ElevenLabs anahtarı kayıtlı değil, lütfen kendi ElevenLabs anahtarınızı girin.",
        "en": "No ElevenLabs key is saved, please enter your own ElevenLabs key."},
    "dublaj_eleven_anahtar_gecersiz": {
        "tr": "ElevenLabs anahtarı kabul edilmedi, anahtarı kontrol edip yeniden girin.",
        "en": "The ElevenLabs key was not accepted, please check it and enter it again."},
    "dublaj_eleven_onay_yok": {
        "tr": "ElevenLabs için gerekli onay verilmemiş, kullanmak için paneldeki onay kutusunu işaretleyin.",
        "en": "The consent needed for ElevenLabs was not given, tick the consent box in the panel to use it."},
    "dublaj_eleven_klon_onay_yok": {
        "tr": "Ses klonlama için ikinci onay verilmemiş, ses örneği gönderilmedi; panelden onaylayın ya da hazır bir ses seçin.",
        "en": "The second consent for voice cloning was not given, no voice sample was sent; confirm it in the panel or choose a ready-made voice."},
    "dublaj_eleven_ses_yok": {
        "tr": "ElevenLabs için bir ses seçilmemiş, ses kimliğini (voice id) yazın ya da ses klonlamayı onaylayın.",
        "en": "No ElevenLabs voice is chosen, enter a voice ID or confirm voice cloning."},
    "dublaj_eleven_kota": {
        "tr": "ElevenLabs kullanım hakkınız dolmuş, hesabınızı kontrol edin ya da yerel bir motor seçin.",
        "en": "Your ElevenLabs quota is used up, check your account or pick a local engine."},
    "dublaj_eleven_ag": {
        "tr": "ElevenLabs'e ulaşılamadı, internet bağlantınızı kontrol edin.",
        "en": "ElevenLabs could not be reached, please check your internet connection."},
    "dublaj_eleven_hata": {
        "tr": "ElevenLabs isteği başarısız oldu, ses kimliğini ve hesabınızı kontrol edip tekrar deneyin.",
        "en": "The ElevenLabs request failed, check the voice ID and your account and try again."},
    "yerel_dil_dosyasi_yok": {
        "tr": "Çevrimdışı çeviri için dil dosyası henüz indirilmedi. 'İndir' düğmesine basın (yaklaşık 100 MB, bir kez).",
        "en": "The offline language file isn't downloaded yet. Press 'Download' (about 100 MB, once)."},
    "yerel_bilesen_yok": {
        "tr": "Çevrimdışı çeviri bileşeni (ctranslate2 / sentencepiece) bu kurulumda yok; programı yeniden kurun ya da başka bir çeviri motoru seçin.",
        "en": "The offline translation component (ctranslate2 / sentencepiece) is missing in this install; reinstall the program or pick another translation engine."},
    "yerel_indirme_hata": {
        "tr": "Dil dosyası indirilemedi. İnternet bağlantınızı ve boş disk alanını kontrol edip 'İndir' düğmesine tekrar basın.",
        "en": "The language file could not be downloaded. Check your internet connection and free disk space, then press 'Download' again."},
    "yerel_indirme_hatasi": {
        "tr": "Dil dosyası indirilemedi. İnternet bağlantınızı kontrol edip tekrar deneyin.",
        "en": "The language file could not be downloaded. Check your internet connection and try again."},
    "yerel_ceviri_hatasi": {
        "tr": "Çevrimdışı çeviri çalışmadı. Dil dosyası bozuk olabilir; yeniden indirmeyi deneyin.",
        "en": "Offline translation failed. The language file may be corrupt; try downloading it again."},
    "katman_destek_yok": {
        "tr": "Bu bilgisayarda ekran katmanı için gereken Tk bileşeni yok; çeviriyi TV'de ya da tarayıcıda göstermeyi seçin.",
        "en": "The Tk component needed for the on-screen overlay is missing on this computer; choose to show the translation on a TV or in a browser."},
    "katman_coktu": {
        "tr": "Ekran katmanı üst üste kapandı ve yeniden denenmedi; 'Deneme' düğmesine basarak tekrar başlatın ya da gösterimi TV/tarayıcıya alın.",
        "en": "The screen overlay kept closing and was not retried; press 'Test' to start it again or switch to TV/browser display."},
    "sunucu_hatasi": {
        "tr": "Beklenmeyen bir sorun oluştu, programı yeniden başlatmayı deneyin.",
        "en": "Something unexpected went wrong, please try restarting the program."},
}

DIGER: dict[str, dict[str, str]] = {
    "katman_deneme": {"tr": "Merhaba! Çeviriler burada, oyunun üstünde görünecek.",
                      "en": "Hello! Translations will appear here, on top of the game."},
    "deneme_tr": {"tr": "Merhaba! Bu bir deneme altyazısıdır.", "en": "Hello! This is a test subtitle."},
    "tv_adres": {"tr": "TV'de bu adresi açın: {adres}", "en": "Open this address on the TV: {adres}"},
    "panel_adres": {"tr": "Kontrol paneli: {adres}", "en": "Control panel: {adres}"},
    "demo_acik": {"tr": "Deneme modu: örnek altyazılar gönderiliyor.",
                  "en": "Demo mode: sending sample subtitles."},
    "durdu": {"tr": "Kapatıldı.", "en": "Stopped."},
    "zaten_acik": {"tr": "AltYazıKöprüsü zaten açık; açık olan programın paneli açılıyor: {adres}",
                   "en": "AltYazıKöprüsü is already running; opening the panel of the running one: {adres}"},
    "kapi_dolu": {"tr": "{kapi} kapısı başka bir program tarafından kullanılıyor; {yeni} kapısı kullanılacak. "
                        "TV uygulaması 8642'yi tarar: TV'de bilgisayarın adresini kapı numarasıyla elle yazın "
                        "(http://<bilgisayar adresi>:{yeni}).",
                  "en": "Port {kapi} is used by another program; port {yeni} will be used. The TV app scans "
                        "8642: enter this computer's address with the port number on the TV by hand "
                        "(http://<computer address>:{yeni})."},
    "kapi_yok": {"tr": "{kapi} kapısı dolu ve yakında boş kapı bulunamadı. Ayarlardaki kapı numarasını değiştirip "
                       "yeniden açın.",
                 "en": "Port {kapi} is busy and no free port was found nearby. Change the port in settings and "
                       "start again."},
}


def mesaj(kod: str, dil: str = "tr") -> str:
    tablo = HATALAR.get(kod) or DIGER.get(kod) or HATALAR["sunucu_hatasi"]
    return tablo.get(dil) or tablo["tr"]
