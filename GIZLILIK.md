# Gizlilik

AltYazıKöprüsü ücretsiz, açık kaynaklı bir programdır; dublaj süresi reklamla desteklenir. Kısaca:

- **Takip yok.** İstatistik, telemetri, kullanıcı hesabı yoktur. Reklam yalnız sen **"+30 dk ekle"**ye bastığında oynar (aşağıdaki "Reklam" bölümü).
- **API anahtarların** sadece bilgisayarının **şifreli kasasında** saklanır (Windows Kimlik Bilgisi Yöneticisi, macOS Anahtar Zinciri, Linux Secret Service). Ayar dosyasına ve günlüklere **asla yazılmaz**.
- **Dışarı giden tek şey:** çevrilecek yazı, yalnızca **senin seçtiğin** çeviri motoruna (Claude, Gemini, DeepSeek) gider. **DeepL** sadece sen seçersen kullanılır. Ekran görüntüleri çevrimiçi hizmetlere gönderilmez; yazı okuma bilgisayarında yapılır.
- **Güncelleme denetimi:** Program günde en çok bir kez GitHub'ın herkese açık sürüm sayfasına "yeni sürüm var mı?" diye sorar. Kimlik, ayar ya da kullanım bilgisi gönderilmez. Gelişmiş ayarlardan kapatılabilir. Güncelleme dosyası yalnızca GitHub'dan indirilir ve kurulmadan önce SHA256 özetiyle doğrulanır.
- **TV'ye kurulum:** TV'nin kodu (Passphrase) ve anahtarı yalnızca o an bellekte durur; diske yazılmaz, günlüğe girmez, hiçbir yere gönderilmez. Yalnızca ev ağındaki TV'nizle konuşulur.
- **TV'nin geliştirici modu süresi:** TV'ye bağlanıldığında TV'nin LG geliştirici modu oturum belirteci okunur ve yalnızca işletim sisteminin şifreli kasasında saklanır. Program açıkken günde bir kez yalnızca LG'nin kendi adresine (`https://developer.lge.com`, oturumu uzatma ve kalan süreyi sorma) bu belirteçle istek atılır; başka hiçbir veri gönderilmez. Panelden kapatılabilir ya da belirteç silinebilir. (PROTOKOL 18.6)
- **Oyun sözlükleri (oyun paketleri):** Program günde en çok bir kez GitHub'daki depodan (`raw.githubusercontent.com`) oyun sözlüklerinin yenisini indirir (GTA 6, GTA 5, RDR2…). Hiçbir kimlik, ayar ya da kullanım bilgisi gönderilmez; inen dosya SHA256 ile doğrulanır. Gelişmiş ayarlardan kapatılabilir (`oyun_paketleri_guncelle`). (PROTOKOL 20.5)
- **LG ekranı kararmasın:** Açarsan bilgisayar yalnızca evdeki LG TV'ye (yerel ağ) bağlanır ve çeviri sürerken 2 dakikada bir imleci 1 piksel oynatır. TV'nin verdiği eşleşme anahtarı yalnızca işletim sisteminin şifreli kasasında saklanır; internete hiçbir şey gitmez. (PROTOKOL 20.3)
- **Kısa adres:** Program evdeki TV'nin tarayıcısı için kapı 80'de yalnızca yönlendiren küçük bir sayfa açar (yalnız yerel ağ). (PROTOKOL 20.2)
- **Yerel motor** tamamen internetsiz çalışır; hiçbir şey dışarı çıkmaz.
- **Ses özelliği** varsayılan olarak **kapalıdır**. Açarsan yalnızca **oyunun/sistemin sesi** işlenir. **Mikrofon asla kullanılmaz.** Ses **kaydedilmez**, diske yazılmaz.
- **Türkçe dublaj** (deneysel) varsayılan olarak **kapalıdır**. Yerel motorlarda (Chatterbox, Pocket) karakterin ses örneği yalnız bellekte durur, oturum bitince silinir, hiçbir yere gönderilmez. **ElevenLabs** (bulut) sadece sen seçersen ve iki ayrı onay verirsen kullanılır: birincisiyle çevrilen cümleler, ikincisiyle ayrıca ses örneği ElevenLabs'e gider. Ayrıntı: docs/kullanim/turkce-dublaj.md
- **Dublaj hafızası** varsayılan olarak **kapalıdır** ve yalnız sen **"Dublaj hafızasına izin ver"**i açarsan çalışır (açık rıza). Açıkken, karakterlerin sesiyle üretilen Türkçe sesler, satırların İngilizcesi/Türkçesi ve İngilizce satırların **ses parmak izleri** (sesin kendisi değil, sahneyi tanımaya yarayan küçük sayılar) yalnızca bu bilgisayarda, oyunun klasöründe saklanır (`oyunlar/<oyun>/dublaj_hafizasi`). Sahne tanıma yalnızca zaten dinlenen **oyun sesini** kullanır; **mikrofon asla açılmaz**. Hiçbir şey hiçbir yere **gönderilmez**, paylaşma özelliği yoktur. Boyut sınırı aşılınca en eski kullanılan sesler kendiliğinden silinir; panelden satır satır, oyun oyun ya da tamamen silebilirsin. "Yedeği indir" yalnız kendi bilgisayarların arasında taşımak içindir: oyun seslerini ve satırlarını başkalarıyla paylaşmak hak sahiplerinin haklarını ihlal edebilir. (PROTOKOL 21)
- **TV uygulamasında** mikrofon ve kamera yoktur. Sadece ev ağındaki bilgisayarınla konuşur.
- **İlk indirmeler:** Yerel çeviri veya konuşma tanıma modelleri, sadece sen bu özellikleri açtığında bir kez indirilir.
- **Panel** yalnızca bu bilgisayardan açılır; ağdaki diğer cihazlar panele ulaşamaz. TV'ler yalnızca altyazı akışını görebilir.

## Reklam ve kişisel veriler (KVKK)

- **Ne zaman:** Yalnız sen Türkçe dublaj için **"+30 dk ekle"**ye bastığında. Altyazı çevirisinde reklam yoktur. Program kendiliğinden reklam açmaz.
- **İki seçenek var:**
  1. **Kendi teşekkür ekranımız** (15 saniye): **hiçbir yere bağlanmaz, hiçbir bilgi göndermez.** İzin vermezsen hep bu çıkar.
  2. **Reklam şirketinin video reklamı:** yalnız sen **"Kabul et ve reklamı izle"** dersen. Bu durumda reklam şirketinin
     sunucusuna bağlanılır. O şirket kendi gizlilik kurallarına göre şunları alabilir: **IP adresin**, cihaz/tarayıcı
     türü, dil, reklamın gösterilip izlendiği (başladı, yarısı, bitti). **Adın, e-postan, oyunların, çevirilerin,
     ekran görüntülerin, sesin, API anahtarların ve cihaz numaran reklam şirketine GÖNDERİLMEZ.** Program reklam
     isteğinde çerez göndermez.
- **Kim:** Reklamı gösteren şirket, programın sahibinin anlaştığı reklam ağıdır (adı bu belgeye yazılır; henüz
  anlaşma yoksa reklam şirketine hiç bağlanılmaz, herkes teşekkür ekranını görür).
- **Neden:** Programı ücretsiz tutmak ve dublaj geliştirmesini desteklemek için.
- **Hukuki dayanak:** Açık rızan. Rıza vermek zorunda değilsin; vermezsen de dublaj süresi aynı şekilde eklenir.
- **İzni geri alma:** Panel → **Gelişmiş ayarlar → Reklam → "Reklam şirketinin reklamlarına izin ver"** anahtarını kapat.
  Hemen geçerli olur. Reklam şirketinin elindeki bilgiler için o şirkete başvurabilirsin.
- **Dublaj süresi** yalnız bilgisayarının belleğinde tutulur; kaydedilmez, hiçbir yere gönderilmez.
- **Cihaz numarası:** Bilgisayarının kimliğinden tek yönlü (geri çevrilemez) üretilen 10 harflik bir numaradır.
  Yalnız sen kopyalayıp program sahibine gönderirsen paylaşılır; program onu hiçbir yere göndermez.

Kaynak kodu açıktır (AGPL-3.0-only); isteyen denetleyebilir. Sorular için GitHub'da bir "issue" açabilirsin.

*English summary: The app is free and open source; dubbing time is supported by ads. Ads play only when you press "+30 min". Without your explicit consent only our own 15-second thank-you screen is shown, which contacts nobody; with consent an ad company may receive your IP address, device type and ad-viewing events under its own policy (nothing else). Withdraw consent any time in Advanced settings → Ads. No telemetry. The update check asks GitHub's public releases page at most once a day without sending any identifier and can be turned off; update files are verified by SHA256 before install. The TV install code and key stay in memory only. API keys live only in your OS encrypted keychain and never in logs. Only the text to translate is sent, and only to the engine you chose (DeepL only if chosen); the local engine is fully offline. Audio is off by default, uses only game/system audio, never the microphone, and nothing is recorded. The TV app has no mic/camera. Models are downloaded only when you enable those features. Turkish dubbing is experimental and off by default; local engines keep speaker samples in RAM only, and ElevenLabs (cloud) is used only with two separate explicit consents.*
