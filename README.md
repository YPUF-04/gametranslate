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

## 3 dakikada başla (Windows)

1. [**Son sürümü indir**](https://github.com/YPUF-04/gametranslate/releases/latest): `AltYaziKoprusu-Kur-….exe` dosyasını al.
2. Dosyaya çift tıkla ve **İleri**'lere bas. (Dil Türkçe/İngilizce seçilebilir; yönetici izni gerekmez.)
3. Mavi bir uyarı çıkarsa: Program imzasız olduğu için Windows **"Windows bilgisayarınızı korudu"** (SmartScreen) der. Bu normaldir. **Ek bilgi**'ye, sonra **Yine de çalıştır**'a bas.
4. Son sayfada **Programı şimdi başlat** kutusu işaretli kalsın, **Bitir**'e bas.
5. Tarayıcında panel açılır. Ekrandaki 4 adımı izle: oyunu seç, çeviri motorunu seç, TV'ni bağla, test et.
6. Panelde büyük **Başlat** düğmesine bas.

Kurulum istemezsen aynı sayfadaki `AltYaziKoprusu-Tasinabilir-….zip` dosyasını da kullanabilirsin (ayıkla, `AltYaziKoprusu.exe`'ye çift tıkla). İndirdiğin dosyanın bozulmadığını `SHA256SUMS.txt` ile doğrulayabilirsin.

**LG TV'ye kurulum:** TV'de Developer Mode uygulamasını aç, panelde **"TV'ye tek tuşla kur"** kartına TV'nin IP adresini ve ekrandaki kodu yaz, **Kur**'a bas. Ayrıntı: [LG TV kurulumu](docs/kurulum/lg-webos.md).

**Güncelleme:** Yeni sürüm çıkınca panelin üstünde "Yeni sürüm hazır" yazısı ve **Güncelle** düğmesi görünür. Program günde en çok bir kez GitHub'a "yeni sürüm var mı?" diye sorar (hiçbir bilgin gönderilmez); istersen Gelişmiş ayarlardan kapatabilirsin.

Ayrıntılar: [Windows kurulumu](docs/kurulum/windows.md) · [LG TV kurulumu](docs/kurulum/lg-webos.md) · [TV tarayıcısı / OBS](docs/kurulum/tv-tarayici.md)

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
| PS5 (PS Remote Play) | ⏳ test bekliyor | [Kurulum](docs/kurulum/ps5-remote-play.md) |
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
