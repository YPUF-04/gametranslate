# Samsung (Tizen) - sırada, test cihazı yok

Henüz yapılmadı: elimizde denenecek Samsung TV yok. Plan:
1. `config.xml` yaz; `kopru/web/tv/ortak.js` ve `ortak.css` aynen kullanılır (tek kaynak).
2. `platform-tizen.js` yaz: `backKey`, `showHdmi(port, host, onStatus)` (AVPlay / webapis.avplay), `localAddress(cb)`, `exit()` - `tv/webos/platform-webos.js` ile aynı arayüz.
3. Arayüz mantığını (`tv/webos/app.js`, `i18n.js`, `style.css`) paylaş; Tizen Studio ile paketle, gerçek TV'de dene.
