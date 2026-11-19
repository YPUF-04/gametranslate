# Türkçe dublaj: karakterler kendi sesleriyle Türkçe konuşsun

Bu özellik **deneyseldir** ve **başta kapalıdır**.

## Ne yapar?

Oyundaki karakter İngilizce konuşurken, aynı karakterin sesine benzeyen bir sesle **Türkçe** duyarsın. Altyazı her zaman önce ekrana gelir. Türkçe ses biraz sonra gelir.

## Gizlilik (önemli)

- Sadece **oyunun sesi** dinlenir. **Mikrofon asla açılmaz.**
- Hiçbir ses **diske kaydedilmez**. Her şey bellekte kalır.
- Karakterin ses örneği sadece o oyun oturumunda bellekte durur. Programı durdurunca silinir.
- Yerel motorlarda (Chatterbox, Pocket) ses örneği **hiçbir yere gönderilmez**.
- Ünlü kişilerin sesini taklit eden hazır ses paketi **yoktur**. Program sadece oyunun o anki kendi sesini örnek alır.

## Neye ihtiyacın var?

1. Çalışan AltYazıKöprüsü (altyazı çevirisi çalışıyor olmalı).
2. Ek paketler. Komut satırında bir kere şunu yaz: `pip install "altyazikoprusu[dublaj]"`
3. Bir ses motoru (aşağıda).
4. İlk seferde model indirmek için internet ve boş disk alanı (birkaç GB olabilir).
5. macOS'ta oyun sesini dinlemek için BlackHole gibi sanal bir ses aygıtı gerekir.

## Hangi ses motorunu seçeyim?

Program bilgisayarına bakıp birini **"Bilgisayarın için önerilen"** diye işaretler.

| Motor | Ne zaman | Not |
|---|---|---|
| **Chatterbox** | NVIDIA ekran kartın var (en az 6 GB bellek) | En iyi kalite. Güçlü ekran kartı ister. Kartın yoksa çok yavaştır. |
| **Pocket** | Her bilgisayar | Ekran kartı gerekmez. Kalite biraz daha düşüktür. |
| **ElevenLabs** | İnternetten ücretli servis kullanmak istersen | En doğal. Ücretlidir. Kendi anahtarını girersin. Cümleler ElevenLabs'e gider. |

Emin değilsen önerilen motoru seç.

## Nasıl açarım?

1. Paneli aç. Ana ekranda **"Türkçe dublaj (deneysel)"** kartını bul.
2. Bir ses motoru seç.
3. **"Hazırla"** düğmesine bas. Model indirilir. Yüzdeyi görürsün. Bitince "Hazır ✓" yazar.
4. **"Dene"** düğmesine bas. Kısa bir Türkçe cümle çalar. Ses geliyorsa tamamdır.
5. İstersen **"Oyun sesini ne kadar kıssın"** ve **"Dublaj ses seviyesi"** çubuklarını ayarla.
6. **"Türkçe ses nereden çalsın"** için **Bilgisayar** ya da **TV** seç.
7. Ana ekranda **"Başlat"**'a bas. Dublaj, çeviri çalışırken devreye girer.

Kapatmak için motoru **"Kapalı"** yap.

### ElevenLabs'i açmak

1. ElevenLabs'te kendi hesabından bir anahtar al ve kutuya yaz. **"Anahtarı kaydet"**'e bas. Anahtar sadece bilgisayarının şifreli kasasında durur.
2. Birinci onay kutusunu işaretle. Bununla çevrilen **cümlelerin** ElevenLabs'e gideceğini kabul edersin.
3. Ses için iki yol var:
   - **Hazır ses:** ElevenLabs hesabındaki bir sesin kimliğini (voice id) yaz. Bu yolda ses örneği **gönderilmez**.
   - **Klonlama:** İkinci onay kutusunu da işaretlersen karakterin **ses örneği** ElevenLabs'e yüklenir ve orada geçici bir klon oluşur. Program bunu oturum bitince siler. Program aniden kapanırsa klon kalabilir. O zaman ElevenLabs hesabındaki "Voices" listesinden elle silebilirsin.
4. Onayları sonra istediğin zaman geri alabilirsin. Onay geri alınınca ElevenLabs kapanır.

## Oyun sesi nasıl kısılır?

- **Windows:** Sadece oyunun ya da Remote Play uygulamasının sesi kısılır. Başka uygulamalara dokunulmaz. Türkçe ses bitince oyun sesi yavaşça geri açılır.
- **macOS / Linux:** Uygulama bazında kısma yok. Bilgisayarın genel sesi kısılır ve sonra eski haline döner (olmazsa hiçbir şey kısılmaz).
- **TV'de çalınca:** Oyun sesi kısılmaz. İstersen TV'nin sesini kendin ayarla.

## Dürüst notlar

- **Gecikme:** Karakter konuşmayı bitirdikten yaklaşık **2–3 saniye** sonra Türkçe ses gelir. Altyazı bundan önce görünür.
- **Kalite ekran kartına bağlıdır.** Güçlü kartta daha iyi ve daha hızlıdır. Zayıf bilgisayarda Pocket'i seç.
- Türkçe ses, İngilizce konuşmadan uzunsa biraz hızlandırılır (en çok 1,25 kat). Yine de sığmazsa program daha kısa bir çeviri ister.
- Karakter sesi çok kısa ya da gürültülüyse benzerlik düşer. Yakın zamanda duyulan, benzer sesli bir örnek kullanılabilir.
- Oyunun müziği ya da gürültüsü çok yüksekse konuşma yanlış anlaşılabilir.
- Chatterbox'ın ürettiği sese, kulakla duyulmayan bir filigran eklenir (Resemble AI'ın kendi özelliği).

## Haklar ve sorumluluk

- Dublaj **kişisel kullanım** içindir.
- Ürettiğin sesi **kaydedip yayınlamak** oyunun yapımcılarının ve **seslendirme sanatçılarının** haklarına tabidir. Önce izin almalısın.
- Bazı ses modellerinin kullanım koşulları, açık ve yasal onay olmadan başkasının sesini klonlamayı yasaklar. Kullandığın modelin sayfasındaki koşulları oku.
- Program, gerçek kişilerin (ünlü, yayıncı) seslerini taklit eden hazır paket sunmaz.

## Sorun olursa

- **"Dublaj için gereken ek paket kurulu değil":** Komut satırında `pip install "altyazikoprusu[dublaj]"` yaz, programı yeniden aç.
- **Model inmiyor:** İnternetini kontrol et, "Hazırla"ya tekrar bas.
- **Ses gelmiyor:** Bilgisayarının varsayılan hoparlörünü kontrol et. "Dene" çalışıyor mu bak.
- **Çok yavaş:** Pocket motorunu seç.
- **Ses çok düşük ya da çok yüksek:** "Dublaj ses seviyesi" çubuğunu ayarla.

*English summary: Optional, off by default. Characters speak Turkish in a voice similar to their own, about 2–3 seconds after they speak; the subtitle always shows first. Only game/system audio is listened to (never the microphone), nothing is written to disk, and speaker samples live in RAM for the session only. Engines: Chatterbox (best, needs a strong GPU), Pocket (any PC, a bit lower quality), ElevenLabs (paid, cloud; the text goes there and, only with a second explicit consent, the voice sample too). Install with `pip install "altyazikoprusu[dublaj]"`. For personal use; recording or publishing is subject to the rights of the game and the voice actors. No celebrity voice packs.*
