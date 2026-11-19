# Alınan kararlar (kullanıcıyla)

| Konu | Karar | Durum |
|---|---|---|
| Lisans | AGPL-3.0-only, GameTranslator/CouchSubs'a teşekkür NOTICE'de | Yapıldı |
| İlk hedef | Önce Windows bilgisayar + LG TV, sonra diğerleri | Sürüyor |
| Claude aboneliğiyle giriş | YOK (Anthropic kuralları). Sadece API anahtarı | Yapıldı |
| Oyun hafızası | Var; önce izin sorulur; sadece bu bilgisayarda | Sürüyor |
| Çeviri paketi paylaşımı | `.akpaket` dosyası, sadece cümleler | Sürüyor |
| Arayüz (premium, animasyonlu) | EN SONDA, Opus 5.5 ile | Bekliyor |
| İsim | "Gearly" ve "Subbly" dolu; arayüz aşamasında boş 3 isim önerilecek | Bekliyor |
| Reklam | İPTAL: proje kişisel/hobi amaçlı. Reklam ve hak sistemi yok; en fazla isteğe bağlı bağış bağlantısı. (Eski fikir: Model: ilk 30 dk ücretsiz çeviri, sonra reklam izle → süre kazan. Oyunun üstünde asla reklam yok. Takip/yorum karşılığı ödül YOK) | Karar |
| Maliyet | Geliştiriciye sıfır maliyet: çeviri kullanıcının bilgisayarında (yerel motor) ya da kullanıcının kendi anahtarıyla | Kural |
| Kurulum | Tek tuşla: Windows kurucu (.exe), panelden "TV'ye kur", tek tuşla güncelleme | Yazıldı, gerçek PC/TV'de denenmedi |
| Kod açık mı | AÇIK kalacak (AGPL). Güven + GitHub görünürlüğü | Karar |
| Cihaz sırası | Önce bilgisayarlar (Windows + Mac): bilgisayar çevirir, TV'de oyunun üstüne yansır. Telefon/tablet/iPhone sonra (beklemede) | Karar |
| Görünürlük | GitHub'da bulunabilirlik: README anahtar kelimeleri, konular (topics), sürümler, İngilizce tanıtım | Yapıldı (konuları sahibi elle girer: docs/GITHUB-GORUNURLUK.md) |
| Dağıtım / güncelleme | Yalnız GitHub Releases (sunucu yok, maliyet 0). Güncelleme günde en çok 1 kez, kimliksiz, kapatılabilir; indirilen dosya SHA256SUMS.txt ile doğrulanır | Kural |

## Reklam modeli için notlar (karar anında tekrar bakılacak)
- Google'ın "ödüllü reklam"ı (AdMob) telefon uygulamaları içindir; Windows masaüstü programında doğrudan yok.
  Bilgisayarda reklam için başka bir reklam ağı ya da telefondan "süre kazanma" gerekir — araştırılacak.
- AGPL açık kaynak: başkası kodu alıp reklamsız sürüm yayınlayabilir; bu yasal ve engellenemez.
- Reklam ağları veri toplayabilir; yalnız kişiselleştirilmemiş reklam seçilecek ve gizlilik belgesinde yazılacak.
