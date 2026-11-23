# Dublaj süresi, "+30 dk ekle", reklam ve kodlar

## Kullanıcı için (kısa)

- **Altyazı çevirisi sınırsız ve ücretsizdir.** Süre, sayaç yok.
- **Türkçe dublaj** süre ister. Panelde **Erişim** kartında **"+30 dk ekle"**ye bas:
  kısa bir reklam (ya da 15 saniyelik teşekkür ekranımız) oynar, bitince **30 dakika** dublaj süresi eklenir.
- Tekrar basarsan süre üst üste eklenir (30, 60, 90 dk …), en fazla **4 saat**.
- Süre **yalnız dublaj çalışırken** azalır. Çeviriyi durdurursan süre de durur.
- Süre bitince dublaj **durur**, altyazılar **devam eder**. "+30 dk ekle" ile kaldığın yerden devam edersin.
- Programı kapatınca kalan süre **silinir**. Sonraki açılışta yeniden eklersin.
- TV uygulaması açıksa reklam **TV'de**, oyunun üstünde oynar (birkaç saniye ile en fazla 2 dakika).
  TV bağlı değilse reklam bilgisayardaki panelde oynar. Panelde "Burada izle" ile reklamı bilgisayarda da izleyebilirsin.
- İlk reklamdan önce program sana sorar: reklamı bir **reklam şirketi** gösterir ve bu şirket cihazın hakkında
  bilgi alabilir. **"Reklamsız devam et"** dersen yalnız kendi teşekkür ekranımız çıkar; o ekran hiçbir yere bilgi
  göndermez. Kararını **Gelişmiş ayarlar → Reklam** bölümünden istediğin zaman değiştirebilirsin.

### Sınırsız dublaj kodu
1. Erişim kartında **"Kodum var"**a bas. **Cihaz numaran** görünür (örnek: `ABCDE-FGHJK`). **Kopyala**'ya bas.
2. Bu numarayı program sahibine gönder. Sana bir kod verir (`AK1-` ile başlar).
3. Kodu kutuya yapıştır, **Kaydet**'e bas. Bu bilgisayarda dublaj **kalıcı olarak sınırsız** olur: reklam yok, geri sayım yok.
- Kod **yalnız o bilgisayarda** çalışır. Başka bilgisayara yazarsan "Bu kod başka bir bilgisayar için yapılmış" der.
- Cihaz numarası bilgisayarının gerçek kimliğini göstermez; ondan geri çıkarılamaz.

## Program sahibi için

### 1) Anahtar oluştur (bir kez)
```
python araclar/kod_uret.py
```
Açılan sayfada **"Anahtar oluştur"**a bas. Sayfadaki `ACIK_ANAHTAR = "…"` satırını `kopru/erisim_anahtar.py`
dosyasına (eskisinin yerine) yapıştır ve programı öyle yayınla.
**Özel anahtar dosyasını** (`~/.altyazikoprusu-kod/ozel_anahtar.pem`) **kimseyle paylaşma, GitHub'a koyma, yedekle.**
Kaybedersen yeni kod üretemezsin; değiştirirsen eski kodlar çalışmaz.

### 2) Birine sınırsız dublaj kodu ver
Kullanıcı sana **cihaz numarasını** göndersin. Sayfada tür olarak **"Bir bilgisayara özel (sınırsız dublaj)"** seç,
cihaz numarasını yaz, **Üret**'e bas, çıkan kodu kullanıcıya gönder. Komutla:
```
python araclar/kod_uret.py --cihaz ABCDE-FGHJK
```
Eski tür kodlar (her bilgisayarda sınırsız, belirli gün) hâlâ çalışır ama önerilmez: biri paylaşırsa herkes kullanır.

### 3) Reklam adresi (VAST) — dürüst bilgi
Program her reklam şirketiyle çalışabilen **VAST** biçimini kullanır. Adresi `kopru/reklam_ayari.py` içindeki
`VAST_ADRESI = ""` satırına yazarsın (yalnız `https://`). Boş bırakırsan herkes 15 saniyelik teşekkür ekranını görür
ve süre yine eklenir; bu da sorunsuz çalışır.

VAST adresini **bir reklam ağından** alman gerekir. Bilmen gerekenler:
- **Hiçbiri anında değildir.** Reklam ağları başvuru ister ve **onaylamayabilir**. Genelde bir şirket ya da vergi
  bilgisi, ödeme bilgisi ve uygulamanın/sitenin incelenmesi gerekir; birkaç gün ile birkaç hafta sürebilir.
- **Google Ad Manager** (video için "video ad unit" + VAST etiketi): Google AdSense/Ad Manager hesabı ve onay gerekir.
  Google, kendi IMA aracını kullanmayan uygulamalara her zaman reklam vermeyebilir; az izlenen yeni uygulamalar
  çoğu zaman reddedilir.
- Diğer video reklam ağları (ör. programatik video ağları, Türkiye'deki yerel reklam ajansları) da VAST etiketi verir;
  her birinin kendi başvuru şartları vardır.
- Reklam gelmezse (ağ reklam bulamazsa, VPAID gibi desteklemediğimiz bir biçim gönderirse) program kullanıcıyı
  bekletmez: teşekkür ekranını gösterir ve süreyi yine ekler. Bu yüzden ilk günlerde gelir düşük olabilir.
- Kişiselleştirilmemiş (çerezsiz) reklam isteyin. Programımız reklam isteğinde çerez göndermez.
- Reklam ağının kendi gizlilik şartları geçerlidir; GIZLILIK.md'deki "Reklam" bölümünü ağın adıyla güncelleyin.

Denemek için adresi yayınlamadan önce panelde **Gelişmiş ayarlar → Reklam → Reklam adresi** kutusuna da yazabilirsin
(bu kutu `reklam_ayari.py`'deki adresi ezer).

### Dürüst not
Program açık kaynaktır (AGPL). Süre sınırı ve kod denetimi kullanıcının bilgisayarında çalışır; bilen biri bunu
kaldıran bir kopya yapabilir ve bu yasaldır. Bu sistem dürüst kullanıcılar ve projeyi desteklemek içindir, bir kilit değildir.
