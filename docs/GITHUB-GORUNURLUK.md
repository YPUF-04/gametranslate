# GitHub'da bulunabilirlik (depo sahibi için)

Bu sayfa yalnız depo sahibine: GitHub'da projenin daha kolay bulunması için **dürüst** yapılabilecekler. GitHub'daki sıralama satın alınamaz ve hileyle yükseltilemez; asıl etken gerçek kullanıcı ilgisidir.

## 1. Depo açıklamasını yazın (30 saniye)

1. GitHub'da depo sayfasını açın: `github.com/YPUF-04/gametranslate`.
2. Sağ üstteki **About** (Hakkında) kutusunun yanındaki **dişli** simgesine basın.
3. **Description** (açıklama) kutusuna şunu yapıştırın:

   > Oyun çeviri: PS5/Xbox/PC oyunlarındaki yazıları canlı Türkçeye çevirip LG webOS TV'de oyunun üstünde gösterir. Real-time game subtitle translator (OCR), free & open source.

4. **Website** kutusuna sürümler sayfasını yazın: `https://github.com/YPUF-04/gametranslate/releases/latest`
5. Aynı pencerede **Releases** ve **Packages** kutularından yalnız **Releases** işaretli kalsın (sağ sütunda son sürüm görünsün).

## 2. Konuları (Topics) ekleyin

Aynı **About** penceresinde **Topics** kutusuna aşağıdakileri tek tek yazıp boşluk ya da Enter'a basın (en çok 20 tane; küçük harf ve tire kullanılır):

`game-translation` `subtitles` `ocr` `translation` `turkish` `real-time` `ps5` `remote-play` `webos` `lg-tv` `xbox` `accessibility` `machine-translation` `llm` `claude`

İsterseniz ekleyebilirsiniz: `gemini`, `deepseek`, `game-translator`, `windows`, `aiohttp`, `python`. Sonra **Save changes** (Değişiklikleri kaydet).

## 3. Sosyal önizleme görseli

Biri bağlantıyı Discord, X, WhatsApp vb. yerde paylaşınca görünen resimdir.

1. Depo sayfasında **Settings** (Ayarlar) sekmesine girin.
2. **General** sayfasında aşağı inip **Social preview** bölümünü bulun.
3. **Edit** → **Upload an image** ile görsel yükleyin.
4. İpucu: **1280 × 640 piksel**, PNG, 1 MB'tan küçük. Üstünde logo, "AltYazıKöprüsü" adı ve tek cümlelik vaat ("Oyundaki yazılar canlı Türkçe") olsun. Yazılar büyük ve okunaklı olmalı; kenarlardan en az 40 piksel boşluk bırakın.

## 4. Sürüm (Release) yayınlayın

Bulunabilirlik için en önemli şey, indirilebilir bir **sürümdür**. Sürüm GitHub Actions ile kendiliğinden hazırlanır:

1. `pyproject.toml` içindeki `version` ile `kopru/__init__.py` içindeki `SURUM` aynı olmalı (ör. `0.2.0`).
2. Terminalde: `git tag v0.2.0` sonra `git push --tags`.
3. GitHub'da **Actions** sekmesinde **Windows paketi** işi çalışır (10-15 dakika). Testler geçerse kurucuyu (`AltYaziKoprusu-Kur-0.2.0.exe`), taşınabilir zip'i ve `SHA256SUMS.txt` dosyasını **Releases** sayfasına kendisi koyar.
4. **Releases** sayfasına gidip sürüm notlarını Türkçe olarak düzeltin (nelerin yeni olduğu 2-3 cümle). Bu notlar programın içindeki "Yeni sürüm hazır" kutusunda da görünür.
5. Etiket adı mutlaka `v` ile başlamalı (`v0.2.0`), yoksa iş çalışmaz. Ön sürümler için `v0.2.0-beta.1` gibi yazın; "son sürüm" olarak işaretlenmez.

Tek tuşla güncelleme yalnızca **son** sürümü ve yukarıdaki üç dosyayı kullanır; dosyaları elle silmeyin ya da adlarını değiştirmeyin.

## 5. Diğer dürüst adımlar

- **README'nin ilk cümlesi** insanların arayacağı kelimeleri doğal biçimde içersin (oyun çeviri, canlı altyazı çevirisi, PS5 Remote Play, LG webOS...). Bu yapıldı; değiştirirken de doğal kalın.
- **Ekran görüntüsü / kısa video:** README'ye panelin ve TV'deki çevirinin bir görüntüsünü ekleyin; insanlar önce görüntüye bakar.
- **Issue şablonları** hazır (`.github/ISSUE_TEMPLATE/`); hata bildirimi ve öneri kolayca açılır, bu da depoyu canlı gösterir.
- **Toplulukta paylaşın:** Türkçe oyun forumları, Reddit'te `r/Turkey`/`r/ps5`/`r/LGOLED`, Ekşi/Discord sunucuları. Yalnızca gerçek, yardımcı bir yazıyla ve topluluk kurallarına uyarak.
- **Düzenli küçük sürümler** ve cevaplanan issue'lar, depoyu "yaşayan proje" yapar.

## Yıldız ve etkinlik hakkında

GitHub'da arama ve öneri sıralaması büyük ölçüde **yıldız, indirme, fork, güncel etkinlik (commit, sürüm, issue yanıtı)** gibi gerçek ilgiye bakar. Bunlar kendiliğinden, kullanıcılar projeyi beğendikçe gelir.

**Sahte yıldız satın almayın, yıldız takası yapmayın, bot kullanmayın.** Bu, GitHub'ın kurallarına (Acceptable Use Policies) aykırıdır; hesap ve depo kısıtlanabilir ya da kapatılabilir ve proje güvenilirliğini kaybeder. Gerçek kullanıcıların işini kolaylaştırmak, uzun vadede tek işe yarayan yoldur.
