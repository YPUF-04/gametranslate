# AltYazıKöprüsü

**AltYazıKöprüsü**, oyunun ekranındaki yabancı yazıları (ve istersen konuşmaları) canlı olarak Türkçeye çevirip TV'nde oyunun üstünde gösteren, ücretsiz ve ticari olmayan bir topluluk programıdır. Bilgisayarda çalışan küçük bir program ekranı okur, çevirir ve sonucu TV'ne gönderir.

*English: AltYazıKöprüsü ("SubtitleBridge") is a free, non-commercial community app. A small PC program reads foreign text from your game screen (PS5 Remote Play, Xbox app, capture card/OBS or a PC game), translates it live – mainly into Turkish, other languages are selectable – and shows it on your TV over the game.*

> ⚠️ **Dürüst durum notu:** Proje geliştirme aşamasındadır. Henüz gerçek cihazlarda (TV, PS5, Xbox) denenmemiştir; aşağıdaki tabloda her akışın test durumu açıkça yazılıdır.

## Neleri çeviriyor?

- **Altyazılar** (oyun içi diyalog yazıları)
- **Menüler** ve ayarlar ekranları
- **Ekrandaki tüm yazılar** (görev listesi, bilgi kutuları, tabelalar); istersen görevlere kısa açıklama da eklenir
- **Oyun sesi** (deneysel, varsayılan olarak kapalı): konuşmayı yazıya çevirip çevirir

## 10 dakikada başla (Windows)

1. [Son sürümü](../../releases) indir (`AltYaziKoprusu-windows.zip`).
2. Zip dosyasına sağ tıkla, **Tümünü ayıkla**'yı seç.
3. Açılan klasörde **`AltYaziKoprusu.exe`** dosyasına çift tıkla.
4. Mavi bir uyarı çıkarsa: Program imzasız olduğu için Windows **"Windows bilgisayarınızı korudu"** (SmartScreen) der. Bu normaldir. **Ek bilgi**'ye, sonra **Yine de çalıştır**'a bas.
5. Tarayıcında panel açılır. Ekrandaki 3 adımı izle: oyunu seç, çeviri motorunu seç, test et.
6. Panelde büyük **Başlat** düğmesine bas.

Ayrıntılar: [Windows kurulumu](docs/kurulum/windows.md) · [LG TV kurulumu](docs/kurulum/lg-webos.md) · [TV tarayıcısı / OBS](docs/kurulum/tv-tarayici.md)

### Kaynaktan çalıştırma (ileri düzey)

Python 3.11 veya üstü gerekir.

```bash
pip install -e .[ocr-windows]
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
