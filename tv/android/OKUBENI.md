# Android TV - sırada, test cihazı yok

Henüz yapılmadı: elimizde denenecek Android TV cihazı yok. Plan:
1. Tek bir WebView etkinliği: `kopru/web/tv/tv.html` benzeri bindirme sayfasını yükler (`ortak.js`, `ortak.css` aynen).
2. HDMI girişi için TV Input Framework (`TvView`) ile canlı görüntü, üstüne şeffaf WebView.
3. Bilgisayarı bulmak için `/kopru/merhaba` alt ağ taraması (webOS uygulamasıyla aynı mantık) ve kumanda ile gezinme.
