# Katkı rehberi

Katkıya açığız; her seviyeden. Kod yazmak şart değil: **test etmek, çeviri düzeltmek ve rehberleri sadeleştirmek** çok değerli.

## Nasıl yardım edebilirsin?

- **Gerçek cihazda dene** (LG, Samsung, PS5, Xbox) ve sonucu bir "issue" olarak yaz: model, ne yaptın, ne oldu.
- **Rehberleri düzelt:** Anlaşılmayan yeri sadeleştir. Tarz: "mala anlatır gibi", numaralı kısa adımlar, her adımda tek iş.
- **Arayüz çevirisi:** `kopru/web/panel/dil/` altındaki `tr.json` / `en.json` dosyalarını örnek alıp yeni dil ekle.
- **Kod:** Küçük, tek amaçlı değişiklikler gönder.

## Kurallar

1. Lisans **AGPL-3.0-only**; gönderdiğin kod bu lisansla paylaşılır.
2. Arayüzde teknik terim kullanma ("SSE", "OCR", "API" yok); kullanıcılar çoğunlukla teknik olmayan oyunculardır.
3. Telemetri, takip veya izinsiz ağ isteği ekleme. API anahtarları ve ses asla kaydedilmez/loglanmaz.
4. Yeni bağımlılık eklersen lisansını [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) dosyasına yaz.
5. Bağlantı sözleşmesine ([docs/PROTOKOL.md](docs/PROTOKOL.md)) uy; değişiklik gerekiyorsa önce "issue" aç.

## Panel testi

`node kopru/web/panel/test/panel.test.js` (Playwright ve Chromium gerekir).
