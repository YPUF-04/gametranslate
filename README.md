# AltYazıKöprüsü — oyun çeviri ve canlı altyazı çevirisi

[![Lisans: AGPL-3.0](https://img.shields.io/github/license/YPUF-04/gametranslate?color=blue)](LICENSE)
[![Son sürüm](https://img.shields.io/github/v/release/YPUF-04/gametranslate?display_name=tag&label=son%20s%C3%BCr%C3%BCm)](https://github.com/YPUF-04/gametranslate/releases/latest)
[![Yıldız](https://img.shields.io/github/stars/YPUF-04/gametranslate?style=flat)](https://github.com/YPUF-04/gametranslate/stargazers)

**Yabancı oyunları Türkçe oynayın: PS5 Remote Play, Xbox veya PC oyunlarındaki altyazı, menü ve görev yazılarını canlı olarak Türkçeye çevirir (OCR ile ekranı okur) ve LG webOS TV'nizde oyunun üstünde gösterir. Türkçe yaması olmayan oyunlar için ücretsiz, açık kaynaklı bir Türkçe yama alternatifi.**

*English: Free, open-source **game translator** with **real-time subtitle translation** (OCR) for **PS5 Remote Play**, Xbox and PC games, shown on your **LG webOS** TV over the game. [Full English README](docs/README.en.md).*

[![İndir: Windows kurucusu](https://img.shields.io/badge/%C4%B0ndir-Windows%20kurucusu-2EC4B6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/YPUF-04/gametranslate/releases/latest)

## Neden AltYazıKöprüsü?

- **Tek tuşla kurulum:** Windows kurucusunu indir, çift tıkla; yönetici izni gerekmez.
- **Tek tuşla güncelleme:** Yeni sürüm çıkınca programın içinden tek düğmeyle güncellenir.
- **Tek tuşla LG TV kurulumu:** TV'ye uygulamayı bilgisayardan kendisi yükler; ek program gerekmez.
- **Türkçe dublaj (deneysel, isteğe bağlı):** Karakterler kendi sesine benzer bir sesle Türkçe konuşur; yalnız oyun sesi dinlenir, mikrofon açılmaz, hiçbir şey kaydedilmez. Bkz. [docs/kullanim/turkce-dublaj.md](docs/kullanim/turkce-dublaj.md).
- **Canlı çeviri:** Altyazı, menü ve görev yazıları; oyun hafızası aynı cümleyi hep aynı çevirir, isimlerini bozmaz.
- **Ücretsiz ve gizli:** Takip yok, reklam yok, sunucu yok. Yerel motorla internetsiz bile çalışır.
- **Oyunun üstünde:** LG webOS TV uygulaması yazıyı oyunun üstüne basar (TV tarayıcısı ve OBS yedek yollardır).

> ⚠️ **Dürüst durum notu:** Proje geliştirme aşamasındadır. Henüz gerçek cihazlarda (TV, PS5, Xbox) denenmemiştir; aşağıdaki tabloda her akışın test durumu açıkça yazılıdır. Windows kurucusu, tek tuşla güncelleme ve tek tuşla LG TV kurulumu da gerçek bir bilgisayar/TV üzerinde henüz denenmemiştir.

## Neleri çeviriyor?

- **Altyazılar** (oyun içi diyalog yazıları)
- **Menüler** ve ayarlar ekranları
- **Ekrandaki tüm yazılar** (görev listesi, bilgi kutuları, tabelalar); istersen görevlere kısa açıklama da eklenir
- **Oyun sesi** (deneysel, varsayılan olarak kapalı): konuşmayı yazıya çevirip çevirir

> 🎮📺 **PS5 + laptop + LG TV (altyazı + Türkçe dublaj) ile ilk deneme mi?** Her şey tek sayfada, sırayla: **[İlk deneme rehberi](docs/kurulum/ilk-deneme.md)** — hangi hesapları açacağın (ikinci PSN hesabı, LG geliştirici hesabı, Gemini anahtarı), PS5 / laptop / LG TV ayarları ve dublaj.
> PS5'e artık **gizli bağlanıyoruz**: pencere açılmaz, PS5'e kol tuşu gönderilmez, TV'deki kolun oyunda kalır ([PS5 kurulumu](docs/kurulum/ps5-remote-play.md)).

## Kurulum — adım adım (Windows)

> Hiç bilgisayar bilgisi gerekmez. Her adımda ne yapacağın yazıyor.

### A) Programı kur (2 dakika)
1. [**Son sürüm sayfasını aç**](https://github.com/YPUF-04/gametranslate/releases/latest).
2. Sayfanın altındaki **Assets** bölümünde `AltYaziKoprusu-Windows-Kur.exe` dosyasına tıkla, iner.
3. İnen dosyaya **çift tıkla**.
4. Mavi bir pencere çıkarsa (**"Windows bilgisayarınızı korudu"**): **Ek bilgi** → **Yine de çalıştır**. Program imzasız olduğu için bu uyarı normaldir.
5. Kurucu kendiliğinden kurar. Masaüstüne logolu simge gelir, tarayıcında kontrol paneli açılır.

### B) Hazırlık (1 dakika)
- **Oyunun ayarlarında** görüntü modunu **"Pencereli tam ekran"** ya da **"Kenarlıksız"** yap. (Yoksa çeviri oyunun üstünde görünmeyebilir.)
- **Ücretsiz Gemini anahtarı** (önerilen): [aistudio.google.com](https://aistudio.google.com) → Google hesabınla gir → **Get API key → Create API key** → çıkan yazıyı kopyala.
  İnternetsiz istersen anahtar gerekmez: kurulumda **Çevrimdışı** seçip **İndir**'e bas (yaklaşık 100 MB, bir kez).

### C) Paneldeki 6 adım (oyun açıkken yap)
| Adım | Ne yapacaksın | Doğru giderse |
|---|---|---|
| 1. **Görüntü** | "Bu bilgisayarda"yı seç, listeden **oyunun penceresini** seç | Oyunun resmi görünür ✓ |
| 2. **Yazı okuma** | Oyunda yazı olan bir ekran açıkken **Ekrandaki yazıları oku** | Yazılar kutu içinde görünür ✓ |
| 3. **Çeviri** | **Gemini** → anahtarı yapıştır → **Dene** | "Merhaba, nasılsın?" çıkar ✓ |
| 4. **Nerede göreyim?** | **Bu bilgisayarın ekranında** → **Ekranda dene** | Ekranda deneme yazısı çıkar ✓ |
| 5. **Neyi çevireyim?** | Fareyle altyazının ve görev yazısının olduğu yerlere **kare çiz** (en çok 6) | Kareler kaydedilir ✓ |
| 6. **Hazır** | **Başlat** | Oyundaki yazılar Türkçe görünür 🎉 |

**Bir adımda hata mı çıktı?** Hata kutusundaki **"Ayrıntı (bize gönder)"** yazısını aç, ekran görüntüsünü al ve [buradan bildir](https://github.com/YPUF-04/gametranslate/issues/new/choose).

### Güncelleme
Yeni sürüm çıkınca panelin üstünde **"Yeni sürüm hazır"** ve **Güncelle** düğmesi çıkar: bas, gerisini program yapar. **Güncellemeler artık sadece değişen parçaları indirir** (her seferinde baştan ~120 MB değil). Neler değiştiğini [**Sürüm notları**](SURUMLER.md) sayfasında görebilirsin.

### Mac
[Son sürüm sayfasından](https://github.com/YPUF-04/gametranslate/releases/latest) `.dmg` dosyasını indir, aç, simgeyi **Uygulamalar**'a sürükle. İlk açılış ve **Ekran Kaydı** izni için: [Mac kurulumu](docs/kurulum/mac.md).

### Kaynaktan çalıştırma (ileri düzey)

Python 3.11 veya üstü gerekir.

```bash
pip install -e ".[ocr-windows,tv]"
python -m kopru
```

## Desteklenen cihazlar

| Cihaz / akış | Durum | Açıklama |
|---|---|---|
| LG webOS TV (oyunun üstünde) | 🔧 test ediliyor | [Kurulum](docs/kurulum/lg-webos.md) |
| Tarayıcı / OBS ile gösterim | ⏳ test bekliyor | [Kurulum](docs/kurulum/tv-tarayici.md) |
| PS5 (gizli bağlantı: pencere yok, kol TV'de kalır; yedek: PS Remote Play penceresi) | ⏳ test bekliyor | [Kurulum](docs/kurulum/ps5-remote-play.md) |
| Xbox (Xbox uygulaması) | ⏳ test bekliyor | [Kurulum](docs/kurulum/xbox.md) |
| Yakalama kartı / OBS | ⏳ test bekliyor | [Kurulum](docs/kurulum/yakalama-karti.md) |
| PC oyunu | ⏳ test bekliyor | [Windows](docs/kurulum/windows.md) |
| Samsung (Tizen) TV | 🕒 yakında | [Not](docs/kurulum/samsung.md) |
| Android TV | 🕒 yakında | [Not](docs/kurulum/android-tv.md) |
| macOS | 🕒 sonra (beta) | [Not](docs/kurulum/mac.md) |

## Çeviri motorları

| Motor | Kısaca | Anahtar | Rehber |
|---|---|---|---|
| Gemini | Ücretsiz kullanım hakkı var (sınırlar değişebilir) | Gerekli | [Rehber](docs/anahtarlar/gemini.md) |
| DeepSeek | Çok ucuz | Gerekli | [Rehber](docs/anahtarlar/deepseek.md) |
| Claude | En doğal çeviri, ücretli. Abonelik girişi kullanılamaz, API anahtarı gerekir | Gerekli | [Rehber](docs/anahtarlar/claude.md) |
| Yerel | İnternetsiz, ücretsiz, biraz daha zayıf | Yok | — |
| DeepL | İsteğe bağlı | Gerekli | [Rehber](docs/anahtarlar/deepl.md) |

Fiyatlar değişebilir; ilgili sitenin kendi sayfasına bakın.

## Gizlilik özeti

Takip yok, istatistik yok. API anahtarların sadece bilgisayarının şifreli kasasında durur. Yazılar yalnızca seçtiğin çeviri motoruna gider; "Yerel" motor tamamen internetsizdir. Mikrofon asla açılmaz, ses kaydedilmez. Tamamı: [GIZLILIK.md](GIZLILIK.md)

## Katkı

Katkı vermek için [CONTRIBUTING.md](CONTRIBUTING.md). Yol haritası: [docs/YOL-HARITASI.md](docs/YOL-HARITASI.md).

## Lisans ve teşekkür

AltYazıKöprüsü, **AGPL-3.0-only** lisansıyla dağıtılır ([LICENSE](LICENSE)). Esinlendiğimiz projeler için teşekkürler: **GameTranslator** (Sefflex) ve **CouchSubs** (Sinan Yorulmaz). Ayrıntılar [NOTICE](NOTICE) dosyasında; kullanılan kütüphaneler [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) içinde.
