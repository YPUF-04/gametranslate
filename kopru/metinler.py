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
    "model_yok": {
        "tr": "Çeviri modeli bulunamadı (servis bu modeli kapatmış olabilir), ayarlardan modeli varsayılana alın ya da başka bir motor seçin.",
        "en": "The translation model was not found (the service may have retired it), reset the model to default in settings or pick another engine."},
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
    "tv_oturum_acildi": {
        "tr": "TV bağlandı: geliştirici modu artık her gün kendiliğinden uzatılacak.",
        "en": "TV connected: its Developer Mode session will now be extended automatically every day."},
    "tv_oturum_okunamadi": {
        "tr": "TV'ye bağlanıldı ama oturum belirteci okunamadı; süreyi TV'deki Developer Mode uygulamasından uzatın.",
        "en": "Connected to the TV but the session token could not be read; extend the session in the TV's Developer Mode app."},
    "tv_bitti_acilmadi": {
        "tr": "Kuruldu. Uygulamayı TV'nin uygulamalar listesinden açın.",
        "en": "Installed. Open the app from the TV's app list."},
    "gecersiz_kod": {
        "tr": "Bu kod geçerli değil. Harfleri kontrol edip tekrar deneyin.",
        "en": "This code is not valid. Please check the letters and try again."},
    "suresi_dolmus_kod": {
        "tr": "Bu kodun süresi dolmuş. Yeni bir kod isteyin ya da \"+30 dk ekle\" ile devam edin.",
        "en": "This code has expired. Ask for a new one, or continue with \"+30 min\"."},
    "baska_cihaz_kodu": {
        "tr": "Bu kod başka bir bilgisayar için yapılmış. Bu bilgisayarın cihaz numarasını gönderip yeni kod isteyin.",
        "en": "This code was made for another computer. Send this computer's device number and ask for a new code."},
    "dublaj_suresi_bitti": {
        "tr": "Dublaj süresi bitti, dublaj durakladı. Altyazılar devam ediyor. \"+30 dk ekle\"ye basarak devam edebilirsin.",
        "en": "Dubbing time is up, so dubbing paused. Subtitles keep going. Press \"+30 min\" to continue."},
    "dublaj_suresi_yok": {
        "tr": "Dublaj için süre yok. Önce \"+30 dk ekle\"ye bas.",
        "en": "There is no dubbing time left. Press \"+30 min\" first."},
    "dublaj_sure_dolu": {
        "tr": "Dublaj süresi zaten en fazla (4 saat). Biraz kullandıktan sonra yeniden ekleyebilirsin.",
        "en": "Dubbing time is already at the maximum (4 hours). You can add more after using some."},
    "dublaj_sinirsiz": {
        "tr": "Bu bilgisayarda dublaj zaten sınırsız. Süre eklemen gerekmiyor.",
        "en": "Dubbing is already unlimited on this computer. No need to add time."},
    "reklam_erken": {
        "tr": "Reklam daha bitmedi. Birkaç saniye sonra süre eklenecek.",
        "en": "The ad has not finished yet. Time will be added in a few seconds."},
    "reklam_yok": {
        "tr": "Bu reklamın süresi zaten eklendi ya da reklam iptal oldu. \"+30 dk ekle\"ye yeniden bas.",
        "en": "Time for this ad was already added, or the ad was cancelled. Press \"+30 min\" again."},
    "hafiza_izin_yok": {
        "tr": "Dublaj hafızası kapalı. Önce \"Dublaj hafızası\" kartında izni aç.",
        "en": "Dubbing memory is off. Turn on its permission in the \"Dubbing memory\" card first."},
    "hafiza_yedek_gecersiz": {
        "tr": "Bu dosya bir dublaj hafızası yedeği değil ya da bozuk.",
        "en": "This file is not a dubbing memory backup, or it is damaged."},
    "dublaj_kodla_hata": {
        "tr": "Ses sıkıştırılamadı; dublaj paketini onarmayı deneyin.",
        "en": "The audio could not be compressed; try repairing the dubbing package."},
    "dublaj_paket_onay": {
        "tr": "Dublaj paketini kurmak (ya da kaldırmak) için önce onay kutusunu işaretleyin.",
        "en": "Please tick the confirmation box first to install (or remove) the dubbing package."},
    "dublaj_paket_desteklenmiyor": {
        "tr": "Dublaj paketi bu bilgisayarda desteklenmiyor (64 bit Windows, Linux ya da Apple Silicon Mac gerekir).",
        "en": "The dubbing package is not supported on this computer (64-bit Windows, Linux or an Apple Silicon Mac is needed)."},
    "dublaj_paket_indirme": {
        "tr": "Dublaj paketi indirilemedi, internet bağlantınızı kontrol edip \"Kur\"a yeniden basın (kaldığı yerden sürer).",
        "en": "The dubbing package could not be downloaded, check your internet connection and press \"Install\" again (it resumes)."},
    "dublaj_paket_dogrulama": {
        "tr": "İndirilen dosya doğrulanamadı ve kurulmadı, lütfen biraz sonra yeniden deneyin.",
        "en": "The downloaded file could not be verified and was not installed, please try again later."},
    "dublaj_paket_bozuk": {
        "tr": "İndirilen paket bozuk ya da güvensiz göründüğü için açılmadı, lütfen yeniden deneyin.",
        "en": "The downloaded package looked broken or unsafe and was not opened, please try again."},
    "dublaj_paket_pip": {
        "tr": "Dublaj paketinin bir parçası kurulamadı, \"Kur\"a yeniden basın; olmazsa kurulum günlüğünü bize gönderin.",
        "en": "Part of the dubbing package could not be installed, press \"Install\" again; if it keeps failing, send us the install log."},
    "dublaj_paket_hata": {
        "tr": "Dublaj paketi kurulurken beklenmeyen bir sorun oldu, \"Kur\"a yeniden basın.",
        "en": "Something unexpected went wrong while installing the dubbing package, press \"Install\" again."},
    "dublaj_isci_hata": {
        "tr": "Dublaj motoru açılamadı ya da kapandı, biraz bekleyip yeniden deneyin; sürerse dublaj paketini kaldırıp yeniden kurun.",
        "en": "The dubbing engine could not start or stopped, wait a moment and try again; if it persists, remove and reinstall the dubbing package."},
    "dublaj_isci_zaman": {
        "tr": "Dublaj motoru zamanında yanıt vermedi, lütfen yeniden deneyin.",
        "en": "The dubbing engine did not answer in time, please try again."},
    "dublaj_bellek": {
        "tr": "Ekran kartının belleği yetmedi, \"Hafif mod\"u açıp yeniden deneyin.",
        "en": "The graphics card ran out of memory, turn on \"Light mode\" and try again."},
    "dublaj_ffmpeg_yok": {
        "tr": "Video aracı (ffmpeg) bulunamadı, dublaj paketini kaldırıp yeniden kurun.",
        "en": "The video tool (ffmpeg) was not found, remove and reinstall the dubbing package."},
    "dublaj_ffmpeg_hata": {
        "tr": "Video okunamadı ya da yazılamadı; dosyanın bozuk olmadığından ve diskte yer olduğundan emin olun.",
        "en": "The video could not be read or written; make sure the file is not broken and there is free disk space."},
    "video_gecersiz": {
        "tr": "Bu dosya dublajlanamaz, lütfen bir video dosyası seçin (mp4, mkv, mov, webm ya da avi).",
        "en": "This file cannot be dubbed, please pick a video file (mp4, mkv, mov, webm or avi)."},
    "video_suruyor": {
        "tr": "Bir video zaten dublajlanıyor, bitmesini bekleyin ya da durdurun.",
        "en": "A video is already being dubbed, wait for it to finish or stop it."},
    "video_canli_acik": {
        "tr": "Canlı dublaj açıkken video dublajlanamaz (aynı ekran kartı), önce çeviriyi durdurun.",
        "en": "A video cannot be dubbed while live dubbing is on (same graphics card), stop translating first."},
    "iptal": {
        "tr": "İşlem durduruldu.", "en": "Stopped."},
    "dublaj_motor_yok": {
        "tr": "Önce dublaj için bir ses motoru seçin (Chatterbox, Pocket veya ElevenLabs), sonra tekrar deneyin.",
        "en": "First pick a voice engine for dubbing (Chatterbox, Pocket or ElevenLabs), then try again."},
    "dublaj_paket_yok": {
        "tr": "Dublaj paketi kurulu değil. Türkçe dublaj kartında \"Dublaj paketini kur\"a basın.",
        "en": "The dubbing package is not installed. Press \"Install dubbing package\" in the Turkish dubbing card."},
    "dublaj_hazir_degil": {
        "tr": "Ses motoru henüz hazır değil, lütfen önce \"Hazırla\" düğmesine basın ve bitmesini bekleyin.",
        "en": "The voice engine is not ready yet, please press \"Prepare\" first and wait until it finishes."},
    "dublaj_indirme_hata": {
        "tr": "Ses modeli indirilemedi, internet bağlantınızı kontrol edip \"Hazırla\" düğmesine tekrar basın.",
        "en": "The voice model could not be downloaded, please check your internet connection and press \"Prepare\" again."},
    "dublaj_yukleme_hata": {
        "tr": "Ses modeli yüklenemedi, bellek yetmemiş olabilir; daha hafif olan Pocket motorunu deneyin.",
        "en": "The voice model could not be loaded, memory may be too low; try the lighter Pocket engine."},
    "dublaj_onar_calisirken": {
        "tr": "Onarım için önce çeviriyi durdurun (dublaj çalışırken ses motoru yeniden kurulamaz).",
        "en": "Stop translation first to repair (the voice engine cannot be reinstalled while dubbing runs)."},
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
    "bilgi_cevrimdisi": {
        "tr": "Oyun bilgisini hazırlamak için internetteki bir çeviri motoru gerekir; ayarlardan Gemini, Claude ya da DeepSeek seçip anahtarını girin, sonra tekrar deneyin.",
        "en": "Preparing game info needs an online translation engine; pick Gemini, Claude or DeepSeek in settings, enter its key, then try again."},
    "bilgi_okunamadi": {
        "tr": "Motor oyun bilgisini anlaşılır biçimde veremedi. Oyunun adını kontrol edip tekrar deneyin ya da bilgiyi elle yazın.",
        "en": "The engine could not return the game info in a usable form. Check the game name and try again, or type the info by hand."},
    "uyari_tum_ekran_ps5": {
        "tr": "Tüm ekran seçili; PS Remote Play penceresini seçersen yalnız oyunu okurum.",
        "en": "The whole screen is selected; if you pick the PS Remote Play window I will read only the game."},
    "uyari_tum_ekran_xbox": {
        "tr": "Tüm ekran seçili; Xbox penceresini seçersen yalnız oyunu okurum.",
        "en": "The whole screen is selected; if you pick the Xbox window I will read only the game."},
    "uyari_tum_ekran_kart": {
        "tr": "Tüm ekran seçili; yakalama kartının penceresini seçersen yalnız oyunu okurum.",
        "en": "The whole screen is selected; if you pick the capture card window I will read only the game."},
    "sunucu_hatasi": {
        "tr": "Beklenmeyen bir sorun oluştu, programı yeniden başlatmayı deneyin.",
        "en": "Something unexpected went wrong, please try restarting the program."},
}

DIGER: dict[str, dict[str, str]] = {
    "bildirim_basladi": {"tr": "Çeviri başladı", "en": "Translation started"},
    "bildirim_durdu": {"tr": "Çeviri durdu", "en": "Translation stopped"},
    "bildirim_gizlendi": {"tr": "Yazılar gizlendi", "en": "Text hidden"},
    "bildirim_gosteriliyor": {"tr": "Yazılar gösteriliyor", "en": "Text shown"},
    "bildirim_yeniden_oku": {"tr": "Yeniden okunuyor", "en": "Reading again"},
    "bildirim_kurulum_gerek": {"tr": "Önce kurulumu bitirin", "en": "Finish setup first"},
    "bildirim_baslamadi": {"tr": "Çeviri başlatılamadı", "en": "Translation could not start"},
    "kisayol_kullanimda": {"tr": "Bu tuş başka bir programda kullanılıyor.",
                           "en": "This key is already used by another program."},
    "kisayol_cakisma": {"tr": "Bu tuş başka bir kısayola verilmiş.",
                        "en": "This key is already assigned to another shortcut."},
    "kisayol_gecersiz": {"tr": "Bu tuş birleşimi geçersiz.", "en": "This key combination is not valid."},
    "katman_deneme": {"tr": "Merhaba! Çeviriler burada, oyunun üstünde görünecek.",
                      "en": "Hello! Translations will appear here, on top of the game."},
    "deneme_tr": {"tr": "Merhaba! Bu bir deneme altyazısıdır.", "en": "Hello! This is a test subtitle."},
    "onizleme_tr": {"tr": "Hemen gitmemiz lazım, hadi!", "en": "We have to go, now!"},
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
    # ---- PS5 gizli bağlantı (PROTOKOL §15) ----
    "ps5_yardimci_yok": {
        "tr": "PS5 gizli bağlantı parçası bu kurulumda yok; programı son sürümle yeniden kurun ya da resmî PS Remote Play penceresini kaynak seçin.",
        "en": "The hidden PS5 connection component is missing; reinstall the latest version or pick the official PS Remote Play window as the source."},
    "ps5_yalniz_windows": {
        "tr": "PS5 gizli bağlantı şimdilik yalnız Windows'ta çalışır; bu bilgisayarda resmî PS Remote Play penceresini kaynak seçin.",
        "en": "The hidden PS5 connection currently works on Windows only; pick the official PS Remote Play window as the source here."},
    "ps5_pin_gecersiz": {
        "tr": "Kod 8 rakam olmalı; PS5'te Ayarlar → Sistem → Uzaktan Oynatma → Cihazı Bağla ekranındaki kodu yazın.",
        "en": "The code must be 8 digits; enter the code shown on PS5 Settings → System → Remote Play → Link Device."},
    "ps5_pin_yanlis": {
        "tr": "PS5 kodu kabul etmedi; Cihazı Bağla ekranını yeniden açıp yeni çıkan kodu yazın.",
        "en": "The PS5 did not accept the code; reopen the Link Device screen and enter the new code."},
    "psn_hesap_yok": {
        "tr": "Önce 1. adımda ikinci PSN hesabıyla giriş yapın.",
        "en": "First sign in with the second PSN account in step 1."},
    "ps5_hesap_taninmadi": {
        "tr": "PS5 bu PSN hesabını tanımadı; ikinci hesabın PS5'te bir kullanıcı olarak ekli olduğundan ve 1. adımda o hesapla girdiğinizden emin olun.",
        "en": "The PS5 did not recognize this PSN account; make sure the second account is added as a user on the PS5 and that you signed in with it in step 1."},
    "ps5_kullanimda": {
        "tr": "PS5'e şu an başka bir Remote Play bağlı (ör. resmî uygulama); onu kapatıp yeniden deneyin.",
        "en": "Another Remote Play client is connected to the PS5 (e.g. the official app); close it and try again."},
    "ps5_yanit_yok": {
        "tr": "PS5 yanıt vermedi; PS5'in açık, aynı ağda ve Cihazı Bağla ekranının açık olduğundan emin olun.",
        "en": "The PS5 did not answer; make sure it is on, on the same network and the Link Device screen is open."},
    "ps5_surum": {
        "tr": "PS5'in Remote Play sürümü bu programla uyuşmadı; PS5'i ve programı güncelleyip yeniden deneyin.",
        "en": "The PS5's Remote Play version did not match; update the PS5 and this program and try again."},
    "ps5_kayit_hata": {
        "tr": "PS5 bağlanamadı; Cihazı Bağla ekranını yeniden açıp yeni kodla tekrar deneyin.",
        "en": "Could not link the PS5; reopen the Link Device screen and try again with the new code."},
    "ps5_kayit_yok": {
        "tr": "PS5 henüz bu bilgisayara bağlanmadı; panelde 'PS5'e bağlan' adımlarını tamamlayın.",
        "en": "The PS5 is not linked to this computer yet; complete the 'Connect to PS5' steps in the panel."},
    "ps5_kayit_gecersiz": {
        "tr": "PS5 bu bilgisayarın kaydını kabul etmedi; 'PS5'e bağlan' adımlarından 2. adımı (8 haneli kod) yeniden yapın.",
        "en": "The PS5 rejected this computer's link; redo step 2 (the 8-digit code) of 'Connect to PS5'."},
    "ps5_erisilemedi": {
        "tr": "PS5'e ulaşılamadı; PS5 açık mı ve Ayarlar → Sistem → Uzaktan Oynatma açık mı? Yeniden deneniyor.",
        "en": "The PS5 could not be reached; is it on and is Remote Play enabled? Retrying."},
    "ps5_baglanti_koptu": {
        "tr": "PS5 bağlantısı koptu; kendiliğinden yeniden bağlanılıyor.",
        "en": "The PS5 connection dropped; reconnecting automatically."},
    "ps5_kare_yok": {
        "tr": "PS5'ten henüz görüntü gelmedi; birkaç saniye bekleyip yeniden deneyin.",
        "en": "No picture from the PS5 yet; wait a few seconds and try again."},
    "psn_kod_yok": {
        "tr": "Yapıştırılan adreste giriş kodu yok; Sony girişini bitirdikten sonra adres çubuğundaki adresin TAMAMINI kopyalayın.",
        "en": "The pasted address has no sign-in code; after finishing the Sony sign-in, copy the WHOLE address from the address bar."},
    "psn_reddetti": {
        "tr": "Sony girişi tamamlamadı ya da kodun süresi doldu; 'Sony girişini aç'a yeniden basıp hemen yapıştırın.",
        "en": "Sony did not complete the sign-in or the code expired; press 'Open Sony sign-in' again and paste right away."},
    "psn_cok_deneme": {
        "tr": "Sony çok fazla deneme olduğunu söyledi; birkaç dakika bekleyip yeniden deneyin.",
        "en": "Sony reported too many attempts; wait a few minutes and try again."},
    "psn_ag": {
        "tr": "Sony'ye ulaşılamadı; internet bağlantınızı kontrol edip yeniden deneyin.",
        "en": "Could not reach Sony; check your internet connection and try again."},
    "psn_yanit": {
        "tr": "Sony'nin yanıtı anlaşılamadı; biraz sonra yeniden deneyin.",
        "en": "Sony's answer could not be understood; try again a little later."},
    "psn_kimlik_gecersiz": {
        "tr": "Hesap kimliği geçersiz; 12 karakterlik base64 kimliği (ör. AbCdEfGhIjk=) olduğu gibi yapıştırın.",
        "en": "The account ID is invalid; paste the 12-character base64 ID (e.g. AbCdEfGhIjk=) as is."},
}


def mesaj(kod: str, dil: str = "tr") -> str:
    tablo = HATALAR.get(kod) or DIGER.get(kod) or HATALAR["sunucu_hatasi"]
    return tablo.get(dil) or tablo["tr"]
