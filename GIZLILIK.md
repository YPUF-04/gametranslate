# Gizlilik

AltYazıKöprüsü ücretsiz, ticari olmayan bir topluluk programıdır. Kısaca:

- **Takip yok.** İstatistik, telemetri, reklam, kullanıcı hesabı yoktur.
- **API anahtarların** sadece bilgisayarının **şifreli kasasında** saklanır (Windows Kimlik Bilgisi Yöneticisi, macOS Anahtar Zinciri, Linux Secret Service). Ayar dosyasına ve günlüklere **asla yazılmaz**.
- **Dışarı giden tek şey:** çevrilecek yazı, yalnızca **senin seçtiğin** çeviri motoruna (Claude, Gemini, DeepSeek) gider. **DeepL** sadece sen seçersen kullanılır. Ekran görüntüleri çevrimiçi hizmetlere gönderilmez; yazı okuma bilgisayarında yapılır.
- **Yerel motor** tamamen internetsiz çalışır; hiçbir şey dışarı çıkmaz.
- **Ses özelliği** varsayılan olarak **kapalıdır**. Açarsan yalnızca **oyunun/sistemin sesi** işlenir. **Mikrofon asla kullanılmaz.** Ses **kaydedilmez**, diske yazılmaz.
- **TV uygulamasında** mikrofon ve kamera yoktur. Sadece ev ağındaki bilgisayarınla konuşur.
- **İlk indirmeler:** Yerel çeviri veya konuşma tanıma modelleri, sadece sen bu özellikleri açtığında bir kez indirilir.
- **Panel** yalnızca bu bilgisayardan açılır; ağdaki diğer cihazlar panele ulaşamaz. TV'ler yalnızca altyazı akışını görebilir.

Kaynak kodu açıktır (AGPL-3.0-only); isteyen denetleyebilir. Sorular için GitHub'da bir "issue" açabilirsin.

*English summary: No telemetry. API keys live only in your OS encrypted keychain and never in logs. Only the text to translate is sent, and only to the engine you chose (DeepL only if chosen); the local engine is fully offline. Audio is off by default, uses only game/system audio, never the microphone, and nothing is recorded. The TV app has no mic/camera. Models are downloaded only when you enable those features.*
