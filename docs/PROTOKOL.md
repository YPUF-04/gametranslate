# AltYazıKöprüsü — Bağlantı Sözleşmesi (geliştiriciler için)

Bu belge bilgisayar programı ("Köprü"), TV uygulamaları ve tarayıcı ekranlarının
birbiriyle nasıl konuştuğunu tanımlar. Tüm parçalar BU belgeye uyar.
Alan adları Türkçe ve ASCII'dir (ç→c, ğ→g, ı→i, ö→o, ş→s, ü→u).

## 1. Ağ

- Varsayılan kapı (port): **8642** (ayarlardan değişebilir).
- Bilgisayar programı `0.0.0.0:8642` dinler.
- **Yerel ağdan herkes** erişebilir: `/kopru/*`, `/tv`, `/obs`, `/statik/*`.
- **Yalnızca bu bilgisayardan** (127.0.0.1 / ::1) erişilebilir: `/`, `/panel/*`, `/api/*`.
  Başka adresten gelirse `403` ve `{"hata":"yalniz_yerel"}`.
- CORS: `/kopru/*` için `Access-Control-Allow-Origin: *` (TV uygulaması `file://` kökenlidir).

## 2. TV'nin kullandığı uç noktalar

### `GET /kopru/merhaba`
TV, yerel ağı tararken bunu sorar. Yanıt (JSON):
```json
{"uygulama":"altyazikoprusu","surum":"0.1.0","protokol":1,"ad":"SALON-PC"}
```
`uygulama` alanı tam olarak `"altyazikoprusu"` olmalı; değilse TV o adresi yok sayar.

### `GET /kopru/akis`  (Server-Sent Events, `text/event-stream`)
Bağlanınca sunucu hemen son durumu gönderir: `gorunum`, sonra (varsa) ekrandaki son `yazi` ve `ekran`.
Her 15 sn'de bir `: nabiz` yorum satırı gönderilir. TV 30 sn hiç veri almazsa yeniden bağlanır.

Olaylar (`event:` adı → `data:` JSON):

| Olay | Anlamı | Veri |
|---|---|---|
| `yazi` | Altyazı/konuşma çevirisi göster | `{"id":"a17","metin":"Türkçe metin","asil":"Original text","tur":"altyazi"\|"konusma","konusan":"Ellie"\|null,"sure_ms":4200}` |
| `yazi-sil` | Altyazıyı kaldır | `{}` |
| `ekran` | Ekrandaki diğer yazılar (menü, görev, bilgi) | `{"id":"e5","ogeler":[{"x":0.02,"y":0.05,"g":0.30,"y2":0.04,"metin":"Ana kampa dön","aciklama":"Görev: üsse geri git","tur":"gorev"}]}` |
| `ekran-sil` | Ekran öğelerini kaldır | `{}` |
| `gorunum` | Görünüm ayarı | bkz. aşağı |
| `durum` | Bilgi (TV panelinde gösterilir) | `{"calisiyor":true,"motor":"Gemini","yedek":false}` |

`ekran.ogeler[]` alanları: `x`,`y` = sol üst köşe; `g` = genişlik; `y2` = yükseklik.
Hepsi 0–1 arası oran (ekran boyutuna göre). `tur`: `"menu"`, `"gorev"`, `"bilgi"`, `"diger"`.
`aciklama` isteğe bağlı, en fazla ~60 karakter (kısa açıklama modu).

`sure_ms`: yazının ekranda kalacağı süre. TV bu süre dolunca kendisi kaldırır; yeni `yazi` gelirse
eskisini hemen değiştirir. Okuma süresi hesabı (7.2/1): `max(1800, min(9000, 800 + karakter*55))`.

`gorunum` verisi:
```json
{"yazi_boyutu":44,"konum":"alt","kenar_bosluk":0.08,"arka_plan":0.55,
 "yazi_rengi":"#FFFFFF","konusan_rengi":"#FFD166","asil_goster":false,"ekran_cevir":true}
```
`konum`: `"alt"` | `"ust"`. `arka_plan`: 0–1 opaklık. `kenar_bosluk`: alttan/üstten oran.

### `GET /tv`   ve   `GET /obs`
Tarayıcıdan açılan bindirme sayfaları (yedek plan ve OBS için). Aynı akışı (`/kopru/akis`) dinler.
`/obs` arka planı tamamen saydamdır. `/tv` siyah arka planlıdır (TV tarayıcısı için).

## 3. Bilgisayar paneli API'si (yalnızca yerel)

Tüm yanıtlar JSON. Hata biçimi: `{"hata":"kod","mesaj":"Ne oldu. Ne yapmalı."}` (kullanıcı diline göre).

| Yöntem | Yol | Ne yapar |
|---|---|---|
| GET | `/api/durum` | `{"calisiyor":bool,"motor":"gemini","yedekte":bool,"tv_sayisi":2,"son_yazi":"...","adresler":["192.168.1.20"],"kapi":8642}` |
| GET | `/api/ayarlar` | Ayarları verir (API anahtarları ASLA dönmez; yerine `{"claude":true,...}` "kayıtlı mı" bilgisi) |
| POST | `/api/ayarlar` | Ayarların bir kısmını günceller (gönderilen alanlar) |
| GET | `/api/motorlar` | `[{"kod":"claude","ad":"Claude","anahtar_gerekli":true,"anahtar_kayitli":false,"cevrimdisi":false,"ucretsiz":false}]` |
| POST | `/api/anahtar` | `{"motor":"claude","anahtar":"sk-..."}` → şifreli kasaya yazar. Boş anahtar = sil |
| POST | `/api/dene` | `{"metin":"Hello","motor":"gemini"}` → `{"ceviri":"Merhaba","sure_ms":640}` |
| POST | `/api/baslat` | Yakalama + çeviriyi başlatır |
| POST | `/api/durdur` | Durdurur |
| POST | `/api/deneme-yazi` | TV'ye örnek altyazı gönderir (bağlantı testi) |
| GET | `/api/kaynaklar` | Yakalanabilir ekranlar/pencereler: `[{"kod":"ekran:1","ad":"Ekran 1 (1920×1080)"},{"kod":"pencere:123","ad":"PS Remote Play"}]` |
| GET/POST | `/api/sozluk` | Oyun sözlüğü: `{"oyun":"varsayilan","terimler":[{"asil":"Ellie","ceviri":"Ellie"}]}` |

## 4. Ayarlar dosyası

Konum: Windows `%APPDATA%\AltyaziKoprusu\ayarlar.json`, macOS `~/Library/Application Support/AltyaziKoprusu/`,
Linux `~/.config/altyazikoprusu/`. API anahtarları bu dosyada **yoktur**; işletim sisteminin şifreli
kasasındadır (Windows Kimlik Bilgisi Yöneticisi / macOS Anahtar Zinciri / Linux Secret Service).

```json
{
  "arayuz_dili": "tr",
  "hedef_dil": "tr",
  "kaynak_dil": "otomatik",
  "motor": "gemini",
  "yedek_motor": "yerel",
  "modeller": {"claude":"claude-opus-5-5","gemini":"gemini-3.8-flash","deepseek":"deepseek-chat"},
  "kaynak": "ekran:1",
  "bolge_altyazi": {"x":0.1,"y":0.72,"g":0.8,"y2":0.25},
  "ekrani_cevir": true,
  "kisa_aciklama": true,
  "ses_cevir": false,
  "kapi": 8642,
  "aktif_oyun": "varsayilan",
  "kurulum_tamam": false,
  "cihaz": "ps5",
  "tv": "lg",
  "gorunum": { "...": "bkz. 2. bölüm" }
}
```

## 5. Çeviri motoru arayüzü (Python)

```python
class CeviriMotoru(Protocol):
    kod: str            # "claude", "gemini", "deepseek", "deepl", "yerel", "sahte"
    ad: str
    anahtar_gerekli: bool
    cevrimdisi: bool
    async def cevir(self, metinler: list[str], kaynak: str, hedef: str,
                    sozluk: dict[str, str], aciklama: bool = False) -> list[Ceviri]: ...
```
`Ceviri = {metin: str, aciklama: str | None}`. `aciklama=True` sadece görev/bilgi öğelerinde istenir.
Ağ hatası → `AgHatasi` fırlatılır; yönetici yedek motora (`yerel`) geçer ve `durum` olayında `yedek:true` yayar.

## 6. Oyun hafızası, bağlam ve kalite (sürüm 0.2)

### 6.1 Oyun hafızası (çeviri belleği)
Her oyunun kendi hafızası vardır: `<ayar_dizini>/oyunlar/<oyun_kodu>/`
- `oyun.json`: `{"kod":"gta6","ad":"GTA 6","aciklama":"Açık dünya suç oyunu, argo bol","hitap":"sen","karakterler":[{"ad":"Lucia","cinsiyet":"k"}],"olusturma":"2026-11-18"}`
- `sozluk.json`: terimler (eski `sozlukler/` buraya taşınır)
- `hafiza.sqlite`: `asil → ceviri` kayıtları; alanlar: `asil`, `ceviri`, `kaynak` (`"motor"|"kullanici"|"paket"`), `motor`, `sayac`, `tarih`. `kaynak=kullanici` olan (elle düzeltilmiş) kayıt her zaman kazanır.

**İzin:** Ayarlarda `hafiza_izni`: `null` (sorulmadı) | `true` | `false`. `null` iken hiçbir şey diske yazılmaz (sadece RAM önbelleği). Panel ilk "Başlat"ta sorar.
Hafıza SADECE bu bilgisayarda durur; hiçbir yere gönderilmez.

### 6.2 Paylaşılabilir çeviri paketi
Dosya: `<oyun_kodu>.akpaket` (zip): `oyun.json`, `sozluk.json`, `hafiza.json` (yalnız metin çiftleri; kişisel bilgi, anahtar, ekran görüntüsü YOK).
İçe alırken: kullanıcının kendi düzeltmeleri (`kaynak=kullanici`) ezilmez; paketten gelenler `kaynak=paket`.

### 6.3 Bağlamlı çeviri
Motorlara her istekte gönderilir: oyun adı + kısa açıklama + hitap (sen/siz) + karakter listesi + sözlük + **son 6 altyazı satırı (asıl ve çeviri)** + Türkçe altyazı kuralları (satır başına ~42 karakter, en çok 2 satır, doğal konuşma dili, argo gerekiyorsa argo, isimler çevrilmez).
Yeni geçen özel isimler (kişi/yer/çete adı) motor tarafından `yeni_terimler` olarak döndürülebilir; hafıza izni varsa sözlüğe "öneri" olarak eklenir.

### 6.4 Hızlı zamanlama
- Metin ilk görüldüğü karede **önden çeviri** başlar (sonuç bekletilir); metin 2. karede aynıysa hemen yayınlanır. Değiştiyse önden çeviri çöpe atılır.
- Hafızada/önbellekte varsa çeviri anında (0 ms) yayınlanır.

### 6.5 Kalite modu
Ayar `kalite`: `"en_iyi"` (varsayılan; Claude varsa `claude-opus-5-5`, yoksa Gemini) | `"dengeli"` | `"hizli"` (Claude Haiku 5.5 / Gemini Flash). Panel bunu "En iyi çeviri / Dengeli / En hızlı ve ucuz" diye gösterir.

### 6.6 Yeni API (yalnız yerel)
| Yöntem | Yol | Ne yapar |
|---|---|---|
| GET | `/api/oyunlar` | `[{"kod":"gta6","ad":"GTA 6","kayit_sayisi":1240,"terim_sayisi":35,"son_oynama":"..."}]` |
| POST | `/api/oyunlar` | Yeni oyun: `{"ad":"GTA 6","aciklama":"...","hitap":"sen"}` → `{"kod":"gta6"}` |
| POST | `/api/oyun-sec` | `{"kod":"gta6"}` → aktif oyun |
| GET/POST | `/api/oyun/<kod>` | Oyun bilgisi (açıklama, hitap, karakterler) oku/güncelle |
| DELETE | `/api/oyun/<kod>/hafiza` | O oyunun hafızasını siler |
| GET | `/api/son-ceviriler` | Son 30 çeviri: `[{"id":"a17","asil":"...","ceviri":"...","kaynak":"motor"}]` |
| POST | `/api/duzelt` | `{"asil":"...","ceviri":"Düzgün hâli"}` → hafızaya `kaynak=kullanici`; ekrandaysa TV'de hemen güncellenir |
| GET | `/api/paket/<kod>` | `.akpaket` dosyasını indirir |
| POST | `/api/paket` | `.akpaket` yükler (multipart, alan `dosya`) → `{"tamam":true,"eklenen":812,"atlanan":12}` |
| GET | `/api/oneriler` | Önerilen yeni terimler: `[{"asil":"Vice City","ceviri":"Vice City"}]` |
| POST | `/api/oneriler` | `{"asil":"..","kabul":true}` → sözlüğe ekler ya da reddeder |

Ayarlara eklenen alanlar: `hafiza_izni` (null/true/false), `kalite` ("en_iyi"), `aktif_oyun` (oyun kodu).

## 7. Bölge seçimi, akıcı gösterim ve erişim kodu (sürüm 0.3)

### 7.1 Bölge seçimi ("neyi çevireceğini ben seçeyim")
Ayar `bolgeler`: en çok 3 dikdörtgen: `[{"x":0.1,"y":0.75,"g":0.8,"y2":0.2,"tur":"altyazi"|"ust_yazi"|"diger","ad":"Altyazı"}]` (0–1 oran).
- Liste boşsa: otomatik mod (bugünkü davranış: altyazı bölgesi + ekranın geri kalanı).
- Doluysa: SADECE bu bölgeler okunur (daha hızlı, daha az yanlış). `altyazi` bölgesi → `yazi` olayı; diğerleri → `ekran` öğeleri (kendi konumlarında).
- `GET /api/kare` (yalnız yerel): seçili kaynaktan anlık bir JPEG (genişlik ≤ 1280). Diske YAZILMAZ, hiçbir yere gönderilmez; sadece panelde kare çizmek için.

### 7.2 Akıcı gösterim kuralları ("kesik kesik olmasın, hemen silinmesin")
1. **En az gösterim süresi:** bir altyazı en az `max(1800 ms, okuma_suresi)` ekranda kalır; `okuma_suresi = 800 + karakter*55` (en çok 9000).
2. **Kaybolma toleransı:** kaynak yazı 3 kare üst üste görünmezse "gitti" sayılır; tek karelik titreme yok sayılır.
3. **Gittikten sonra:** en az gösterim süresi dolmadıysa dolana kadar, dolduysa 700 ms daha kalır; sonra 250 ms'de solarak kaybolur.
4. **Devam eden cümle:** yeni metin eskisinin devamıysa (eskisi yenisinin başıysa / daktilo efekti) kutu yerinde güncellenir: zıplama, sönme yok.
5. **Yeni cümle:** eskisi 150 ms'de solarken yenisi belirir; kutu alttan sabit kalır (yükseklik değişse bile yazı tabanı oynamaz).
6. **Satır düzeni:** en çok 2 satır, satırlar dengeli bölünür (ilk satır biraz kısa), kelime ortasından bölünmez.
7. **Önceki satır:** yeni altyazı gelince bir önceki 2,5 sn boyunca üstte küçük ve soluk görünür (`gorunum.onceki_goster`, varsayılan açık).
8. **Ekran öğeleri** (görev/menü): aynı yerde aynı metin varsa yeniden çizilmez; değişince yerinde yumuşak güncellenir; ekrandan gidince 1 sn sonra solar.
`yazi` olayına eklenen alan: `"devam": true|false` (4. kural için; aynı `id` her zaman yerinde güncelleme sayılır). `ekran.ogeler[]` öğelerine kalıcı `"id"` eklenir (8. kural: aynı id = yerinde güncelle, listeden düşen id solar).

### 7.3 Erişim kodu (sunucusuz, isteğe bağlı)
> **Yerine geçti:** sonraki sürümden itibaren §17 geçerlidir (altyazı sınırsız; yalnız dublaj süreli). Aşağısı tarihçe içindir.

- Program ücretsizdir. `erisim.ucretsiz_dakika_gun` (varsayılan 30) kadar günlük çeviri süresi kodsuz kullanılır; süre dolunca çeviri durmaz, panelde sakin bir "Bugünkü ücretsiz süre doldu. Erişim kodunu gir ya da yarın devam et." uyarısı çıkar ve yeni çeviri yapılmaz (hafıza/önbellekten gelenler gösterilmeye devam eder).
- Kod biçimi: `AK1-` + base32(yük + Ed25519 imzası). Yük: `{"s":"sinirsiz"|"gun","g":30,"t":"2026-11-19","n":"rastgele"}`. Program sadece **açık anahtarı** içerir, imzayı internetsiz doğrular. Özel anahtar sadece geliştiricinin bilgisayarında, depoda ASLA yoktur.
- Kod üretme: `araclar/kod_uret.py` (geliştirici için basit panel/komut). Hiçbir sunucu yok, maliyet yok.
- API (yalnız yerel): `GET /api/erisim` → `{"kalan_dakika":12,"kod":"sinirsiz"|"gun"|null,"bitis":"YYYY-MM-DD"|null,"ucretsiz_dakika":30}`; `POST /api/erisim` `{"kod":"AK1-..."}` → `{"tamam":true,"tur":"sinirsiz"|"gun"}` ya da hata `gecersiz_kod` / `suresi_dolmus_kod` (400). `GET /api/durum` ve `durum` olayına süre dolunca `"sinir": true` eklenir. Sayaç yalnız çeviri çalışırken işler, yerel gece yarısı sıfırlanır; `gun` kodu, yük tarihi + `g` gün sonuna kadar geçerlidir. Kod yazarken büyük/küçük harf, boşluk ve tire önemsizdir.
- Not: Kod açık kaynak olduğu için kontrolü kaldıran kopyalar yapılabilir; bu yasaldır (AGPL). Kod sistemi dürüst kullanıcılar içindir.

## 8. Güncelleme ve TV kurulumu (sürüm 0.2, yalnız yerel; Velopack: sürüm 0.3)

Ayar: `guncelleme_denetle` (bool, varsayılan `true`). Kapalıyken program kendiliğinden hiç istek yapmaz.

**İki güncelleme yolu (API aynıdır, `yalniz_degisenler` alanı hangisinin kullanıldığını söyler):**

1. **Velopack (Windows, program Velopack kurucusuyla kurulmuşsa):** `velopack.UpdateManager` + `GithubSource("https://github.com/YPUF-04/gametranslate")`. Yalnız **değişen parçalar** (delta paketleri) iner; Velopack paketlerin SHA256'sını kendisi doğrular, uygular ve programı yeniden başlatır. Paket kimliği (`packId`) `AltYaziKoprusu.Program`, kanal `win`. Sürüm yayın varlıkları: `AltYaziKoprusu.Program-<sürüm>-full.nupkg`, `…-<sürüm>-delta.nupkg` (önceki sürüm varsa), `releases.win.json`, `RELEASES`, `assets.win.json`. Program açılışta **her şeyden önce** `velopack.App().run()` çağırır (yalnız paketli Windows programında; `--katman` ve `--dosya-sec` alt süreçlerinde çağrılmaz).
2. **Eski yol (geliştirme, macOS, Velopack'sız zip, eski Inno kurulumu):** tam kurucu (`AltYaziKoprusu-Kur-<sürüm>.exe`) `releases/latest` üzerinden indirilir, `SHA256SUMS.txt` ile doğrulanır ve sessizce çalıştırılır. Sürümler sayfasındaki bu dosya, eski Inno kurulumlarını Velopack'a **bir kez** geçiren "geçiş kurucusu"dur (`paketleme/windows/gecis.iss`); eski sürümlerdeki düğme aynen çalışmaya devam eder.

Kullanıcı verisi (ayarlar `%APPDATA%\AltyaziKoprusu`, dublaj paketi `%LOCALAPPDATA%\AltYaziKoprusu\dublaj-ortami`, modeller, anahtarlar Credential Manager'da) Velopack'ın yönettiği klasörün (`%LOCALAPPDATA%\AltYaziKoprusu.Program`) **dışındadır**; güncelleme ve kaldırma ona dokunmaz, güncelleme dublaj paketini asla yeniden indirmez.

| Yöntem | Yol | Ne yapar |
|---|---|---|
| GET | `/api/guncelleme` | `{"var":true,"surum":"0.3.0","notlar":"...","boyut_mb":48,"boyut_bayt":50331648,"yalniz_degisenler":false,"ilerleme":0,"asama":"bosta"\|"indiriliyor"\|"dogrulaniyor"\|"baslatiliyor"\|"hata","mesaj":"...","mevcut":"0.2.0","denetim_acik":true,"baglanti":"https://github.com/.../releases/latest"}`. Yeni sürüm yoksa `{"var":false,"neden":"guncel"\|"kapali"\|"bekleniyor"}`. Windows dışında `{"var":false,"neden":"desteklenmiyor","mesaj":"...","baglanti":"..."}`. Gerekirse arka planda (günde en çok 1 kez) GitHub'a bakar. Velopack yolunda `boyut_bayt`/`boyut_mb` yalnız indirilecek delta paketlerinin toplamıdır (delta yoksa tam paket) ve `yalniz_degisenler:true` olur |
| POST | `/api/guncelleme/denetle` | Kullanıcı elle bastı: ayar kapalı olsa da bir kez bakar; `GET` ile aynı gövdeyi döner |
| POST | `/api/guncelleme/kur` | İndirmeyi başlatır; `ilerleme` 0-100. Eski yol: `SHA256SUMS.txt` ile doğrulanamazsa kurulmaz (`asama:"hata"`); doğrulanırsa kurucu `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /GUNCELLEME=1` ile başlar ve sunucu kapanır. Velopack yolu: delta indirilir (`indiriliyor`), sonra `baslatiliyor` ve `UpdateManager.apply_updates_and_restart`; sunucu kapanır, program yeni sürümle açılır. İndirme/uygulama hatasında program açık kalır (`asama:"hata"`) |
| POST | `/api/tv/lg/kur` | `{"ip":"192.168.1.30","parola":"ABC123","paket":"asil"\|"deneme"\|"acgsiz"\|"oturum"}` → arka planda kurar (`oturum`: kurmadan yalnız geliştirici modu belirtecini okur, §18.6). Yalnız yerel ağ IPv4. Parola/anahtar hiçbir yere yazılmaz |
| GET | `/api/tv/lg/durum` | `{"asama":"bosta"\|"anahtar"\|"baglaniyor"\|"yukleniyor"\|"kuruluyor"\|"bitti"\|"hata","mesaj":"...","ayrinti":"ham hata metni"}` |

Eski yolda güncelleme adresleri yalnız `https` ve `github.com`, `api.github.com`, `objects.githubusercontent.com`, `release-assets.githubusercontent.com` olabilir (yönlendirmeler dahil her adımda denetlenir). Velopack yolunun kaynağı kodda sabittir (yalnız bu deponun GitHub Sürümleri); Velopack Flow/telemetri kullanılmaz.
LG kurulumu, LG'nin `ares-install` aracını izler: `http://<TV>:9991/webos_rsa` (anahtar), SSH `<TV>:9922` kullanıcı `prisoner`, SFTP `/media/developer/temp/`, `luna-send-pub -i luna://com.webos.appInstallService/dev/install`, ardından `luna://com.webos.applicationManager/launch`.

## 9. Türkçe dublaj — karakterin kendi sesiyle (sürüm 0.4)

Amaç: karakter İngilizce konuşurken, AYNI SESLE Türkçe konuşuyormuş gibi duyulsun.

### 9.1 Akış
1. **Oyun sesi** (yalnız sistem/oyun sesi; mikrofon ASLA) → konuşma parçalarına bölünür (VAD).
2. **Konuşmadan yazıya** (yerel Whisper). Ekranda aynı cümlenin altyazısı varsa altyazı metni tercih edilir.
3. **Çeviri** (mevcut bağlamlı çeviri; dublaj için "söylenebilir, süreye sığar" kısa Türkçe istenir).
4. **Ses klonlama**: o parçanın KENDİ sesi (3–10 sn) örnek alınır → aynı tonda Türkçe seslendirilir.
   Örnek ses yalnız bellekte tutulur; diske yazılmaz, hiçbir yere gönderilmez (yerel motorlarda).
   Aynı konuşmacının daha temiz örnekleri birikirse (benzerlik eşleştirmesiyle) onlar kullanılır.
5. **Süreye sığdırma**: Türkçe ses orijinal süreden uzunsa en çok 1.25× hızlandırılır; yine sığmazsa kısaltılmış çeviri istenir.
6. **Çalma**: Türkçe ses çalarken oyunun kendi sesi kısılır (Windows: yalnız oyun/Remote Play uygulamasının sesi; diğerlerinde genel ses) ve bitince yumuşakça geri açılır.
7. Gecikme hedefi: konuşma bittikten sonra ≤ 2,5 sn (güçlü ekran kartıyla). Altyazı her zaman dublajdan önce görünür.

### 9.2 Ses motorları (`dublaj.motor`)
| kod | ne | nerede | not |
|---|---|---|---|
| `chatterbox` | Chatterbox Multilingual (Resemble AI, MIT, Türkçe dahil 23 dil) | yerel, NVIDIA ekran kartı önerilir | en iyi yerel kalite |
| `pocket` | Pocket TTS + Türkçe topluluk modeli (`kaanhgunay/pocket-tts-tr`) | yerel, ekran kartı gerekmez | zayıf bilgisayar için |
| `elevenlabs` | ElevenLabs (kullanıcının kendi anahtarı, ücretli) | bulut | en doğal; ses örneği o servise gider — panel bunu açıkça söyler ve ayrıca onay ister |
| `kapali` | dublaj yok | — | varsayılan |
Program bilgisayarı tanır (ekran kartı var mı, bellek) ve uygun motoru önerir. Modeller ilk açılışta, kullanıcı onayıyla indirilir.

### 9.3 Ayarlar
`dublaj`: `{"motor":"kapali","oyun_sesi_kis":0.25,"hiz_siniri":1.25,"ses_seviyesi":1.0,"cikis":"bilgisayar"|"tv"}`
`cikis:"tv"`: Türkçe ses TV uygulamasına gönderilir ve orada çalınır (olay `ses`, aşağıda).
Ek alanlar (ElevenLabs, çift onay): `elevenlabs_onay` (bool; **metin** ElevenLabs'e gider, onay yoksa motor seçilemez), `elevenlabs_klon_onay` (bool; ayrıca ses **örneği** yüklenir, birinci onay yoksa kendiliğinden `false` olur), `elevenlabs_ses_kimligi` (klon onayı yoksa kullanılan hazır ses), `elevenlabs_model` (`eleven_multilingual_v2`). Anahtar yalnız kasadadır (`POST /api/anahtar` `motor:"elevenlabs"`). Onay geri alınırsa motor `kapali` olur; onaysız `motor:"elevenlabs"` isteği `400 dublaj_onay_gerekli` döner.
Doğrulama: `oyun_sesi_kis` 0–1 (oyun sesinin kalacağı kesir), `ses_seviyesi` 0–2, `hiz_siniri` 1.0–1.5.

### 9.4 Yeni olaylar ve API
- SSE `ses`: `{"id":"s12","url":"/kopru/ses/s12.wav","sure_ms":2300,"yazi_id":"a17"}` (dosya bellekten sunulur, 60 sn sonra silinir)
- SSE `ses-dur`: `{}`
- `GET /kopru/ses/<id>.wav` (yerel ağ; sadece bellekteki geçici ses)
- `GET /api/dublaj` → `{"motor":"chatterbox","hazir":true,"onerilen":"chatterbox","ekran_karti":"NVIDIA RTX 3060","indirme":{"durum":"bitti","yuzde":100}}`
- `POST /api/dublaj` → ayarları değiştirir; `POST /api/dublaj/hazirla` → seçili motorun modelini indirir (ilerleme `GET /api/dublaj`'da)
- `POST /api/dublaj/dene` `{"metin":"Merhaba, nasılsın?"}` → örnek Türkçe ses (hazır bir referans sesle) çalar

### 9.5 Kurallar
- Mikrofon asla açılmaz; ses dosyası diske yazılmaz; konuşmacı örnekleri oturum bitince silinir.
- Gerçek kişilerin (ünlü, yayıncı) seslerini taklit eden hazır ses paketi YOKTUR; yalnız oyunun o anki kendi sesi örnek alınır.
- Dublaj kişisel kullanım içindir; kaydedip yayınlamak oyunun ve seslendirme sanatçılarının haklarına tabidir (belgede yazılır).

## 10. Adım adım kurulum, bilgisayar ekranında gösterim, sağlam çevrimdışı motor (sürüm 0.5)

### 10.1 Sihirbaz sırası (her adımda "✓ çalıştı" denetimi; geçmeden sonraki açılmaz, "Atla" hep var)
1. **Görüntü**: cihaz → kaynak (ekran/pencere) → önizleme (`/api/kare`) ✓
2. **Yazı okuma**: önizlemedeki yazılar okunur (`/api/okuma-dene`) ve resim üstünde kutularla gösterilir ✓
3. **Çeviri**: motor seçimi → (gerekirse anahtar / çevrimdışı dil dosyası indirme) → `/api/dene` ✓
4. **Nerede göreyim?**: `gosterim` = `"bilgisayar"` (bu ekranda oyunun üstünde) | `"tv"` (LG uygulaması) | `"tarayici"` (başka cihazın tarayıcısı/OBS) → deneme altyazısı ✓
5. **Neyi çevireyim?** (EN SON): tam genişlikte oyun görüntüsü üzerinde serbestçe kare çizme, en çok **6** kare
6. **Hazır** → Başlat

### 10.2 Yeni API (yalnız yerel)
- `GET /api/okuma-dene` → `{"satirlar":[{"metin":"Press X","x":0.1,"y":0.8,"g":0.2,"y2":0.04}],"sure_ms":120,"okuyucu":"windows"}`; hata: `yakalama_yok`/`okuma_yok`/`kaynak_yok`
- `GET /api/motor/yerel` → `{"hazir":false,"boyut_mb":95,"indirme":{"durum":"yok"|"iniyor"|"bitti"|"hata","yuzde":0,"mesaj":null}}`
- `POST /api/motor/yerel/hazirla` → dil dosyasını indirir (kaynak→hedef, varsayılan en→tr); ilerleme yukarıdaki GET'te
- `GET /api/ekran-katmani` → `{"destek":true,"acik":false,"ekran":1,"ekranlar":[{"no":1,"ad":"Ekran 1 (1920×1080)"}]}`
- `POST /api/ekran-katmani/dene` → bilgisayar ekranında 4 sn deneme altyazısı gösterir
- Ayarlar: `gosterim` ("bilgisayar"|"tv"|"tarayici", varsayılan "bilgisayar"), `katman_ekran` (1..n), `bolgeler` en çok 6.

### 10.3 Bilgisayar ekranında gösterim (ekran katmanı)
Oyunun üstünde, her zaman en önde, tıklamaları geçiren (oyunu engellemeyen), saydam pencere.
Aynı `yazi`/`ekran`/`gorunum` olaylarını ve §7.2 akıcılık kurallarını kullanır. Tam ekran (exclusive fullscreen) oyunlarda görünmeyebilir → rehber "Pencereli tam ekran / Kenarlıksız" ayarını önerir.

### 10.4 Çevrimdışı motor
argostranslate yerine doğrudan Argos dil dosyası (`.argosmodel` = CTranslate2 modeli + SentencePiece) indirilir ve `ctranslate2` + `sentencepiece` ile çalıştırılır (torch/stanza gerekmez, pakete sığar).
Dizin: `https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json` (en→tr örneği: `https://argos-net.com/v1/translate-en_tr-1_5.argosmodel`). İndirme yalnız kullanıcı "İndir"e basınca; ayar dizinine `modeller/argos/<from>_<to>/` olarak açılır.

## 11. Gerçek kullanım düzeltmeleri (sürüm 0.6)

### 11.1 Kendi yazısını okumama (geri besleme döngüsü)
- Ekran katmanı penceresi ekran yakalamadan HARİÇ tutulur: Windows'ta `SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE=0x11)` (Win10 2004+); olmazsa katman kutularının bulunduğu alanlar okumadan önce karartılır (maske).
- Ek güvenlik: son 60 sn'de yayınlanan çevirilere çok benzeyen (≥%80) okunan satırlar atılır.

### 11.2 Yalnız seçilen pencere
- `kaynak = "pencere:<hwnd>"` iken yalnız o pencerenin içi yakalanır (Windows: PrintWindow PW_RENDERFULLCONTENT, olmazsa pencere dikdörtgeni kırpılır). Katman da o pencerenin üstüne konumlanır (koordinatlar pencereye göre).

### 11.3 Okuma süzgeci
- En az 2 harf içermeyen, çoğu rakam/simge olan (HUD sayıları: "358", "30 30"), tek karakterlik veya aynı kelimenin tekrarından oluşan satırlar çevrilmez.
- Otomatik modda altyazı yalnız ekranın alt-orta bandından alınır; bölge varsa yalnız `altyazi` türündeki bölgeden.

### 11.4 Bölge başına "nereye yazayım"
`bolgeler[i]` yeni alanlar:
- `hedef`: `"ustune"` (aynı yerin üstüne, varsayılan görev/menü için) | `"altyazi"` (alttaki altyazı çubuğuna; altyazı türü için varsayılan) | `{"x","y","g","y2"}` (kullanıcının çizdiği hedef kutu)
- `olcek`: 0.6–2.0 (yazı büyüklüğü çarpanı, varsayılan 1.0)
`ekran` olayındaki öğelere `hedef` kutusu ve `boyut_px` (1080p'ye göre önerilen yazı boyu) eklenir.

### 11.5 Ekran öğesi çizimi
- Yazı boyu kaynak yazının yüksekliğinden hesaplanır (1080p'de 14–30 px, `olcek` ve genel `gorunum.ekran_olcek` ile çarpılır).
- Kelime ortasından/harf harf ASLA bölünmez; kutu metne göre genişler (en çok ekran genişliğinin %45'i), sığmazsa yazı küçülür (en az 12 px).

## 12. Kendi panelini okumama, cihaza göre yakalama, oyun bilgisi, bağlantı rehberleri (sürüm 0.7)

### 12.1 Asla kendini okuma
- Windows'ta başlığında marka adı ("AltYazıKöprüsü") geçen tüm görünür pencereler (panelin açık olduğu tarayıcı sekmesi dahil) ve katman penceresi, yakalanan karede siyaha boyanır ve üzerlerine katman çizilmez.
- `kaynak` tüm ekran (`ekran:N`) ise: bölge yoksa YALNIZ altyazı bandı okunur; `ekrani_cevir` (menü/görev yazıları) yalnız kullanıcı bölge çizdiyse ve yalnız o bölgelerde çalışır.

### 12.2 Cihaza göre kaynak
`cihaz` → otomatik pencere eşleştirme (başlık içerir, büyük/küçük harf duyarsız):
- `ps5`: "PS Remote Play", "chiaki"
- `xbox`: "Xbox"
- `kart`: "Windowed Projector", "Projektör", "OBS", kart yazılımları ("Elgato", "4K Capture Utility", "RECentral")
- `pc`: oyun penceresi (kullanıcı seçer; tarayıcılar ve marka penceresi listede alta itilir)
`GET /api/kaynaklar` her öğeye `onerilen: true|false` ve `tur: "ekran"|"pencere"` ekler; uygun pencere yoksa panel cihaz rehberini gösterir.

### 12.3 Oyun bilgisi hazırlama
`POST /api/oyun/<kod>/bilgi-hazirla` → seçili çeviri motoruyla (LLM) oyunun adından: kısa açıklama (≤200 karakter), hitap önerisi, 20–80 terimlik sözlük (karakter/yer/eşya/çete adları; çoğu çevrilmez, gerekiyorsa Türkçe karşılığı). Sonuç öneri olarak döner: `{"aciklama","hitap","terimler":[{"asil","ceviri"}],"karakterler":[{"ad","cinsiyet":"k"|"e"|""}]}` (en çok 30 ana karakter; cinsiyet hem Türkçedeki cinsiyetli sözcükler hem dublaj sesi için); panel kullanıcıya gösterir, "Kaydet" ile sözlüğe ve oyun bilgisine yazılır (`bilgi-kaydet` gövdesine isteğe bağlı `karakterler`; kullanıcının girdiği karakter ve cinsiyeti korunur, yalnız boş cinsiyet doldurulur). Çevrimdışı motorda kullanılamaz (açık mesaj).

### 12.4 Ekran öğesi boyutu
Varsayılan yazı boyu kaynak satır yüksekliğinin 0.75'i (1080p'de 12–22 px); öğe tek satıra sığmaya çalışır, genişlik metne göre (kaynak genişliğinin en çok 1.6 katı, ekranın en çok %35'i), yalnız boşlukta satır kırılır, en çok 2 satır; sığmazsa yazı küçülür (en az 11 px) ve sonuna "…" konur.

## 13. Kısayol tuşları, eski yazının temizlenmesi, ana ekran (sürüm 0.8)

### 13.1 Kısayol tuşları (yalnız Windows; diğerlerinde panelden)
Ayar `kisayollar`: `{"baslat_durdur":"ctrl+shift+t","gizle_goster":"ctrl+shift+h","yeniden_oku":"ctrl+shift+r"}` (boş = kapalı).
- Sunucu sürecinde ayrı bir iş parçacığı Windows `RegisterHotKey` ile dinler (oyun odaktayken de çalışır).
- `baslat_durdur`: çeviriyi başlatır/durdurur. `gizle_goster`: ekran katmanını gizler/gösterir (çeviri sürer); SSE `katman-gizle` / `katman-goster`. `yeniden_oku`: bekleyen yazıları siler, hemen yeni kare okur.
- `GET /api/kisayollar` → `{"destek":true,"kayitli":{"baslat_durdur":true,...},"hata":{"gizle_goster":"Bu tuş başka bir programda kullanılıyor."}}`
- Durum değişince `durum` olayı yayınlanır (panel ve katman küçük bir bildirim gösterir: "Çeviri durdu", "Yazılar gizlendi").

### 13.2 Kaynak yazı gidince çeviri de gitsin
- Ekran öğeleri: kaynak bölgede metin 2 ardışık karede görünmezse 600 ms sonra `ekran` olayında çıkarılır (öğe `id` bazlı); bölge tamamen boşsa o bölgenin tüm öğeleri silinir.
- Altyazı: §7.2 aynen; ama metin kaybolunca en çok 1500 ms daha kalır (en az gösterim süresi uzunsa bile).
- Kare değişmediği için OCR atlanırsa bu sayaçlar ilerlemez → değişiklik algısı "boş bölge"yi de değişiklik sayar.

### 13.3 Ana ekran (kurulum bittikten sonra)
Üstte büyük Başlat/Durdur + durum; altında kartlar: Oyun · Görüntü kaynağı · Çeviri motoru · Nerede göreyim · Çevrilecek yerler · Kısayol tuşları · Son çeviriler (kompakt). Her kartta tek "Değiştir" → o sihirbaz adımını tek başına açar, "Bitti" ile ana ekrana döner. Gelişmiş ayarlar tek bağlantının arkasında.

### 13.4 Oyunla aynı süre (kayık zamanlama) — §13.2'nin altyazı kuralının yerine geçer
Her altyazı satırı için: kaynak ekrana gelme anı `t_gel`, kaybolma anı `t_git`, çevirinin hazır olduğu an `t_hazir`; gecikme `L = t_hazir - t_gel`.
- Çeviri `t_hazir`'da gösterilir ve `t_git + L` anında silinir → ekranda oyundaki süre kadar kalır (yalnız L kadar kayık).
- Arka arkaya diyaloglarda (2 sn, 2 sn, 1,3 sn, 1 sn) her biri kendi süresi kadar görünür; bir sonrakinin gösterim anı gelince önceki o anda değişir (çakışma yok).
- Çok kısa yanıp sönmeleri önlemek için en az 0,8 sn gösterilir (ayar `gorunum.en_az_ms`, varsayılan 800).
- Kaynak hiç kaybolmadan değişirse (yeni cümle) önceki için `t_git` = yeni cümlenin `t_gel`'i.
- Ekran öğeleri (görev/menü) aynı kayık kuralla silinir.
- Bu kural §7.2 kural 1–3'ün ve §13.2 altyazı kuralının yerine geçer. Silme olayı `yazi-sil` artık `{"id": ...}` taşır; istemci başka id'li silmeyi yok sayar.
- İstemciler kendi süre sayacıyla silmez (sunucu karar verir); bağlantı koparsa diye 15 sn güvenlik süresi vardır.
- Deneme/demo yazıları `"otomatik_sil": true` taşır: istemci bunları `sure_ms` sonunda kendisi siler.
- **Güncelleme (§16.4):** satırlar sıraya girer, çeviriler paralel yürür, hiçbir satır atlanmaz; geride kalınca
  okuma tabanı uygulanır. Altyazının yeri §16.1'e göre (varsayılan: orijinalin üstü).

## 14. Türkçe dublaj 2: dublaj paketi, canlı ve video (sürüm 0.9)

Amaç: Tamer Yeşildağ'ın GTA 6 dublajındaki gibi karakterler KENDİ sesleri ve duygularıyla Türkçe
konuşsun. İki kullanım: **canlı** (oynarken; Türkçe ses ~2 sn geç gelir) ve **video** (kaydedilmiş
oyun videosundan Türkçe dublajlı kopya). Varsayılan motor ücretsiz ve yereldir (Chatterbox, NVIDIA
ekran kartında); bulut motorları (ElevenLabs) seçilebilir kalır. §9 geçerlidir; bu bölüm onu genişletir.

### 14.1 Dublaj paketi (ayrı çalışma ortamı)
Ana program küçük kalır (torch/chatterbox/faster-whisper içermez). Dublaj için gereken her şey,
kullanıcı **açıkça onaylarsa**, ayrı bir klasöre indirilir:

| Sistem | Klasör (`KOPRU_DUBLAJ_ORTAMI` ortam değişkeni önceliklidir) |
|---|---|
| Windows | `%LOCALAPPDATA%\AltYaziKoprusu\dublaj-ortami\` |
| macOS | `~/Library/Application Support/AltyaziKoprusu/dublaj-ortami/` |
| Linux | `$XDG_DATA_HOME/altyazikoprusu/dublaj-ortami/` (yoksa `~/.local/share/...`) |

İçerik: `python/` (bağımsız Python 3.13, python-build-standalone), `ffmpeg/` (yalnız Windows: sabit
sürüm ffmpeg; diğerlerinde pip `imageio-ffmpeg`), `modeller/` (`HF_HOME`; ses modelleri), `kod/`
(işçi kodunun kopyası), `indirilen/` (yarım indirmeler `*.part`, devam ettirilebilir),
`durum.json` (`{"surum":"1","asamalar":{"python":"bitti",...}}`), `kurulum.log`.

Sabitlenmiş sürümler (`kopru/dublaj/ortam.py` → `MANIFEST`): Python `3.13.18+20261110`, torch/torchaudio
`2.6.0` (Windows/Linux: `cu124` dizini), `chatterbox-tts==0.1.7`, `faster-whisper==1.2.1`,
`demucs==4.1.0`, ffmpeg `9.1` (gyan.dev essentials). Arşivler **SHA256 ile doğrulanmadan açılmaz**;
pip paketleri PyPI/PyTorch dizinlerinin verdiği özetlerle pip tarafından doğrulanır. Arşiv açarken
mutlak yol, `..`, sembolik/sabit bağlantı ve aygıt dosyası reddedilir (yol aşımı yok).

Aşamalar (sırayla; biten aşama `durum.json`'a yazılır, yeniden kurulumda atlanır):
`python` → `ffmpeg` → `paketler` → `modeller` → `denetim`.
- `indir` adımları HTTP `Range` ile yarım kalan yerden sürer; 3 kez artan beklemeyle yeniden dener.
- `modeller`: işçi süreci Chatterbox çok dilli, Whisper `large-v3-turbo`, HT-Demucs-ft modellerini indirir.
- `denetim`: işçi açılır, `merhaba` + ekran kartı bilgisi alınır.
- Geliştirici kipi: programı çalıştıran Python'da `torch` + `chatterbox` zaten kuruluysa paket
  "kurulu" sayılır ve işçi o Python ile çalışır (`gelistirici: true`); yalnız `modeller` gerekir.

| Yöntem | Yol | Ne yapar |
|---|---|---|
| GET | `/api/dublaj/paket` | `{"durum":"yok"\|"kuruluyor"\|"hazir"\|"hata"\|"iptal"\|"kaldiriliyor","kurulu":false,"gelistirici":false,"indirme_mb":8900,"disk_mb":12500,"asama":"paketler"\|null,"asamalar":[{"kod":"python","durum":"bekliyor"\|"suruyor"\|"bitti"\|"hata","yuzde":0}],"yuzde":37,"mesaj":null,"hata":null,"konum":"C:\\...\\dublaj-ortami","destek":true}` |
| POST | `/api/dublaj/paket/kur` | `{"onay":true}` zorunlu (yoksa `400 dublaj_paket_onay`). Arka planda kurar/sürdürür; kurulum sürüyorsa aynı gövdeyi döner |
| POST | `/api/dublaj/paket/iptal` | Kurulumu durdurur (yarım indirmeler saklanır, sonra sürdürülür) |
| POST | `/api/dublaj/paket/kaldir` | `{"onay":true}` → işçiyi kapatır, YALNIZ dublaj-ortami klasörünü siler (`durum:"yok"`) |
`destek:false` (ör. 32 bit / ARM Windows): `mesaj` nedenini söyler, kur düğmesi gösterilmez.

### 14.2 İşçi süreci (worker) ve kanal
Ağır işler (ayırma, yazıya çevirme, seslendirme, video karıştırma, canlı ses yakalama ve çalma)
ayrı bir süreçte çalışır: `<paket>/python/python -E -s -m kopru.dublaj.isci` (`cwd = <paket>/kod`;
geliştirici kipinde programın kendi Python'u). Ana program işçi yoksa/çökerse ÇÖKMEZ; `son_hata`
olur ve bir sonraki istekte işçi yeniden başlatılır (dakikada en çok 3).

Kanal: işçinin **stdin/stdout'u üzerinden JSON satırları** (UTF-8, satır başına bir nesne, ≤ 64 MB).
Başka süreçler bu borulara erişemez; ayrıca ana program her başlatmada rastgele 32 baytlık bir
anahtar üretir ve `KOPRU_ISCI_ANAHTAR` ortam değişkeniyle verir; işçinin ilk satırı
`{"olay":"merhaba","anahtar":"<aynısı>","surum":"1","cihaz":"cuda","ekran_karti":"...","vram_gb":8.0,
"durum":"gpu","torch":"2.6.0+cu124","torch_cuda":"12.4","bf16":true}` olmalıdır, değilse süreç kapatılır. `durum`:
`"gpu"` | `"cpu_torch_cpu"` (NVIDIA kart var, pakette CUDA'sız torch: onarılabilir) | `"cpu_surucu"` (torch CUDA'lı,
kart/sürücü açılamadı; `cuda_hata` nedeni) | `"cpu"` (NVIDIA yok) | `"mps"` | `"torch_yok"`. İşçi bunu ve her
seslendirmenin süresini (`Seslendirme: N harf → X sn ses, Y ms (cihaz; koşul …)`) `isci.log`'a yazar. İşçi kendi stdout'unu stderr'e yönlendirir (kütüphanelerin
`print`'i kanalı bozamaz); stderr `kurulum.log`'a değil, ayrı `isci.log`'a yazılır (anahtar asla yazılmaz).

İstek: `{"no":7,"komut":"seslendir",...}` → yanıt `{"no":7,"tamam":true,"sonuc":{...}}` ya da
`{"no":7,"tamam":false,"hata":"dublaj_uretim_hata","ayrinti":"..."}`. Ara olaylar:
`{"olay":"ilerleme","no":7,"yuzde":40,"mesaj":"..."}`, `{"olay":"parca",...}` (canlı ses parçası),
`{"olay":"gunluk","seviye":"bilgi","mesaj":"..."}`. Ses verisi: `{"pcm":"<base64 float32 LE mono>","sr":24000}`.

| Komut | Girdi | Sonuç |
|---|---|---|
| `merhaba` | — | işçi/cihaz bilgisi |
| `modeller` | `{"liste":["tts","stt","ayirma"],"stt":"large-v3-turbo"}` | indirir (ilerleme olaylı) |
| `yukle` | `{"tts":"chatterbox","stt":"large-v3-turbo"\|"small","ayirma":true,"hafif":false,"isit":true}` | modelleri belleğe alır; ardından bir kısa üretimle ısınır ve yerleşik yedek seslerin koşullarını hazırlar (ilk gerçek satır yavaş olmasın) → `{"cihaz","isinma_ms",...}` |
| `birak` | — | modelleri boşaltır (VRAM serbest) |
| `ayir` | `{"pcm","sr"}` ya da `{"giris":yol,"ses_cikis":yol,"arka_cikis":yol}` | konuşma sesi / arka plan |
| `yaziya` | `{"pcm","sr"}` ya da `{"giris":yol,"cikis":yol}` | metin, dil, kelimeler `[{"k":"Hey","b":1.2,"s":1.5}]` |
| `izler` | `{"giris":yol,"araliklar":[[b,s],...]}` | konuşmacı izleri (256 boyutlu, birim vektör) |
| `seslendir` | `{"metin","ref_pcm","ref_sr","duygu":{"canlilik":0.5,"cfg":0.35},"motor":"chatterbox","varsayilan":"k"\|"e"}` ya da `ref_yol`/`cikis` | Türkçe ses + `{"cihaz","uretim_ms","kosul":ms\|"onbellek","ref_sn"}`. `ref_pcm` boşsa `varsayilan` cinsiyetin yerleşik yedek sesi (yoksa motorun kendi sesi) |
| `karistir` | `{"arka":yol,"satirlar":[{"yol","bas"}],"cikis":yol}` | dublaj ses izi |
| `video_cikar` / `video_birlestir` | ffmpeg ile ses çıkarma / video+ses birleştirme | dosya yolları |
| `canli_baslat` | `{"pid":1234\|null,"ayirma":true,"tamamen_turkce":false,"giris":""}` | `parca` olayları (`{"pcm","temiz","sr","sure_sn","kaynak":"surec"\|"giris"\|"sistem"}`), `olcum` (`ayirma_ms`) başlar |
| `seslendir_cal` | `seslendir` + `{"hedef_sn","hiz_siniri","seviye","kis","pid"}` | akışlı seslendirip çalar → `{"ilk_ses_ms","toplam_ms","hiz","sure_sn"}` |
| `girisler` | — | ses girişlerinin adları (açılmaz) |
| `izler` / `referans_kaydet` / `hizlandir` | video aşamaları (14.4) | dosya yolları |
| `canli_durdur` | — | yakalama durur, oyun sesi eski hâline döner |
| `canli_son` | `{"sn":1.5}` | son ≤3 sn konuşma `{"pcm","sr"}` (yoksa `{}`); `iptal` gibi ANINDA işlenir, seslendirme sırasını beklemez |
| `oynat` | `{"pcm","sr","seviye":1.0,"kis":0.25,"pid":1234\|null}` | çalar (çalarken oyun sesini kısar) |
| `iptal` | `{"hedef":7}` | süren işi bırakır (`hata:"iptal"`) |
| `kapat` | — | süreç biter |

### 14.3 Canlı dublaj (§9.1'e ek)
**Ana kurulum (hedef):** PS5 → HDMI → LG TV (görüntü ve İngilizce ses TV'den, gecikmesiz). Bilgisayar PS5'e
ikinci bir PSN hesabıyla Remote Play ile arka planda bağlanır; bu akış yalnız yazı okuma (OCR) ve ses
çözümleme içindir. Türkçe altyazı bugünkü gibi TV uygulamasında çıkar; dublaj bunun YANINA eklenen bir
katmandır (altyazı davranışı değişmez). Türkçe ses **TV'den** çalar (`cikis:"tv"`, SSE `ses`).
- İngilizce sesi TV'den bilgisayar silemez. Önerilen: oyunun ayarlarında **Diyalog sesi %10–20**
  (0 değil): İngilizce Türkçenin altında neredeyse duyulmaz, ama Remote Play akışında kısık da olsa
  durur → ayrılır, düzeyi eşitlenir (en çok +30 dB) ve klon örneği olur. Panel bunu adım olarak söyler.
- Ses profili açıksa (§14.5) yeterli ses toplanınca Diyalog 0 yapılabilir; profili olmayan karakter
  motorun nötr Türkçe sesiyle konuşur.
- **Metin önce altyazıdan:** ekranda altyazı belirdiği anda (cümle bitmeden) seslendirme başlar. Altyazının
  Türkçesi (`yazi` olayının `metin`i) zaten hazır olduğundan **ikinci bir çeviri isteği yapılmaz** (gecikme ve
  çeviri motorunun istek kotası yarıya iner); yalnız `metin` yoksa dublaj çevirisi istenir. Ses
  hazır olunca TV'ye hemen gönderilir (`cikis:"tv"` ya da İngilizce çıkarılıyorsa). Konuşma parçası
  sonra gelince aynı satır tekrar çalınmaz, yalnız karakterin sesi örneklenir. Altyazısı olmayan
  konuşmada Whisper yedektir.
- **Örnek seçimi (önden seslendirmede):** 1) adı altyazıda geçen karakterin biriktirilmiş örneği (temiz
  parçalar 8 sn'ye dek birleşir, sonra yalnız daha temizi yerini alır; ≤10 sn); 2) altyazı anında işçiden alınan
  son 1,5 sn konuşma (`canli_son`) bankadaki bir örneğe benziyorsa o; 3) cinsiyeti tutan son örnek — cinsiyet
  oyun bilgisindeki karakterden (§12.3) ya da o anki sesin perdesinden (ortanca F0 < 160 Hz erkek, > 175 Hz
  kadın, arası belirsiz); 4) o cinsiyetin **yerleşik yedek sesi**; 5) bilgi yoksa son duyulan örnek / motorun
  kendi sesi. Bankaya yalnız ≥3 sn ve konuşmalı çerçevelerinin ≥%35'i net perdeli (müzik/efekt değil) parçalar
  girer; örnek düzeyi eşitlenir.
- **Yerleşik yedek sesler:** kadın `vctk/p228_023_enhanced.wav`, erkek `vctk/p226_023_enhanced.wav`
  (Kyutai `kyutai/tts-voices`, sürüm `323332d3…`; kaynak VCTK, Edinburgh Üniversitesi, **CC BY 4.0**; anonim
  gönüllü konuşmacılar). Model indirme aşamasında ya da ilk kullanımda Hugging Face önbelleğine iner.
- **Chatterbox ayarları:** diller arası klonda (İngilizce örnek → Türkçe) `cfg_weight` düşük (0,2–0,45,
  varsayılan ~0,35; Chatterbox'ın dil aktarımı önerisi: aksan ve "okuma" havası taşınmaz), `exaggeration`
  0,25–0,9 (varsayılan 0,5; üstü abartılı/robotik). Ekran kartında yalnız konuşma dil modeli (T3) yarı
  hassastır (bf16 destekleniyorsa bf16, yoksa fp16); ses üreteci (S3Gen + vokoder) tam hassas kalır.
  Konuşmacı koşulları (`prepare_conditionals`) ses başına bir kez hesaplanır, son 8 ses bellekte tutulur.
  Canlı dublaj sürerken model ekran kartından indirilmez.
- **Sıra, akış ve atlama (önden çalınan kip):** satırlar altyazı sırasıyla seslendirilir. Türkçe metin
  cümleciklere bölünür; her cümlecik hazır olur olmaz TV'ye ayrı `ses` olayıyla gider (ilk ses erken).
  Altyazı göründükten 8 sn sonra hâlâ seslendirilmemiş ya da TV'de ≥8 sn ses birikmişse satır atlanır
  (`atildi:"gecikme"|"tv_sirasi"`, gecikme biriktirmek yerine yetişir). Bu kipte konuşma parçası Whisper'dan
  hiç geçmez (işçide seslendirmenin önünü tıkamaz): yalnız karakterin örneği olur; altyazısı olmayan
  konuşmada Whisper yine yedektir.
- `ses` olayına `bayat_ms` (1000–30000) eklenir: TV bu sesi gelişinden en çok bu kadar sonra başlatabilir
  (önündeki sıranın süresi + 4 sn). TV uygulaması gelen sesleri **sıraya** koyar (öncekini kesmez), `bayat_ms`
  (yoksa 6 sn) aşılmışsa atar; Web Audio
  ile çalar (HDMI `<video>` medya hattına ikinci bir medya kaynağı açmaz), yoksa `<audio>` sırası.
  Gerçek LG TV'de HDMI üstünde ses çalma DOĞRULANMADI; çalmazsa yedek: `cikis:"bilgisayar"` +
  Bluetooth hoparlör / LG Sound Share.

- **Yalnız oyunun sesi**: Windows 10 2004+ üzerinde, seçili oyun penceresinin süreci için WASAPI
  *process loopback* (`AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK`, `PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE`)
  kullanılır; olmazsa bugünkü tüm-sistem loopback'e düşülür (`parca.kaynak:"surec"|"sistem"`). Mikrofon ASLA.
- Her konuşma parçası işçide ayırıcıdan **bir kez** geçer (`ayirma:true`): **temiz konuşma sesi** hem yazıya
  çevirmede hem ses örneği (klon) olarak kullanılır. Akışlı (her 0,25 sn'de) ayırma yalnız "Tamamen Türkçe"de
  yapılır. Kaynak `ps5:gizli` iken (oyun bu bilgisayarın ekran kartında değil) hafif kipte de ayrılır. Konuşmacı örnekleri YALNIZ işçinin ve ana programın belleğinde
  durur, diske yazılmaz.
- Duygu: orijinal parçanın ses yüksekliği/enerjisi ve perde değişkenliğinden `canlilik` (Chatterbox
  `exaggeration`, 0.25–0.9) ve `cfg` (0.2–0.45) hesaplanır: bağırma bağırma, fısıltı fısıltı kalır (motorun izin verdiği ölçüde).
- `dublaj.orijinal_ses` (yalnız ses BİLGİSAYARDAN duyuluyorsa anlamlı): `"otomatik"` (varsayılan:
  Remote Play penceresi (`cihaz` ps5/xbox) ya da yakalama kartı girişi seçiliyse tamamen, oyun bu
  bilgisayardaysa kıs) | `"kis"` | `"tamamen_turkce"` (**deneysel**): oyunun ses oturumu kapatılır, işçi
  sesi 0,25 sn'lik bloklarla ayırıp yalnız arka planı (müzik/efekt) çalar (gecikme ≈ 0,25 sn + ayırma
  süresi; `olcum` olayıyla ölçülür), Türkçe ses üstüne biner. Remote Play'de önce ölçülür: yakalama oturum
  sesinden önceyse oyun tamamen susar; sonraysa oturum −30 dB'e çekilip yakalanan ses telafi edilir;
  ölçülemezse "kıs"a dönülür. Yakalama kartında kartın görüntü programının (OBS vb.) oturumu kapatılır.
- Yakalama kartı sesi (`dublaj.ses_girisi`): kartın ses girişi YALNIZ kullanıcı listeden adıyla açıkça
  seçerse açılır (`GET /api/dublaj/girisler` → `{"girisler":[{"ad","kimlik","kart":true}]}`, hiçbiri açılmaz).
  Varsayılan giriş/mikrofon kendiliğinden ASLA açılmaz.
- Hafif mod (`dublaj.hafif_mod`: `"kapali"` varsayılan | `"acik"` | `"otomatik"` = ≤ 8,5 GB'ta açık): Whisper
  `small`. Oyun PS5'te çalıştığından dizüstünün ekran kartı boştur: varsayılan tam kalite (Whisper
  `large-v3-turbo` int8_float16). Her iki kipte Chatterbox'ın dil modeli (T3) yarı hassas (bf16/fp16), ses
  üreteci tam hassas (`KOPRU_TAM_HASSAS=1`: hepsi fp32). 180 sn boşta kalınca ses motoru ekran kartından
  indirilir (canlı dublaj sürerken asla), ilk istekte geri yüklenir.
- Akışlı seslendirme (`seslendir_cal`): metin cümleciklere bölünür, ilk cümlecik hazır olur olmaz çalar
  (bilgisayar çıkışı). Ölçümler `GET /api/dublaj` → `gecikme`: `{"son":{"stt_ms","ceviri_ms","ses_ms",
  "ilk_ses_ms","bekleme_ms","erken"},"ortalama_bekleme_ms","ortalama_ilk_ses_ms","atilan"}` (bekleme = İngilizce
  parça bitişinden Türkçe sesin başlamasına; önden kipte `ilk_ses_ms` = altyazının görünmesinden ilk Türkçe sesin
  hazır olmasına; hedef ekran kartında ≤ 1,5 sn).
- **Dublaj tanı:** `GET /api/dublaj` → `tani`: `{"cihaz":{"cihaz","durum","ekran_karti","vram_gb","torch",
  "torch_cuda","cuda_hata","bf16"}|null,"uyari":null|"cpu_torch_cpu"|"cpu_surucu"|"cpu","onarilabilir":bool,
  "isinma_ms","satirlar":[{"yazi_id","ilk_ses_ms","bekleme_ms","uretim_ms","ref_sn","ref_tur":"konusan"|"benzer"|
  "banka"|"yerlesik_k"|"yerlesik_e"|"notr","cinsiyet","atildi"}] (son 5),"onarim":{"durum":"yok"|"suruyor"|"bitti"|
  "hata","mesaj"}}`. Panel: "Ekran kartında çalışıyor ✓ (kart)" ya da "İşlemcide çalışıyor — çok yavaş olur" +
  nedeni; `cpu_torch_cpu`'da **Onar**: `POST /api/dublaj/onar` → torch/torchaudio CUDA yapısıyla yeniden kurulur
  (`pip --force-reinstall --no-deps … --index-url …/cu124`, ~2,6 GB), işçi yeniden başlar; dublaj çalışırken
  `409 dublaj_onar_calisirken`, paket yoksa `400 dublaj_paket_yok`. Kurulumun `denetim` aşaması da işçi
  `cpu_torch_cpu` bildirirse bir kez kendiliğinden onarır. CUDA'lı torch kurulsun mu kararı `nvidia-smi` ile
  verilir: dizüstünde uyuyan kart için 15 sn beklenir, PATH dışında `System32` ve `NVSMI` klasörlerine de bakılır.

### 14.4 Video dublaj
Akış (her aşamanın çıktısı iş klasöründe saklanır; iptal edilen iş kaldığı aşamadan sürer):
1. `cikar`: ffmpeg → 44,1 kHz stereo WAV.
2. `ayir`: HT-Demucs-ft (konuşma uzmanı) → `ses.wav` (konuşma) + `arka.wav` (müzik/efekt). 8 GB'a
   sığmak için 7,8 sn'lik pencerelerle, %25 bindirmeli parça parça.
3. `yazi`: Whisper `large-v3-turbo`, kelime zaman damgalı.
4. `bol`: kelimeler cümlelere (≤ 8 sn, sessizlik ≥ 0,6 sn ya da noktalama → yeni satır).
5. `konusmaci`: her satırın konuşmacı izi → kosinüs benzerliğiyle (eşik 0,72) gruplama; her karaktere
   en temiz/uzun 3–10 sn'lik örneklerinden bir klon sesi.
6. `cevir`: TÜM satırlar bağlamıyla (oyun bilgisi + sözlük + önceki satırlar), 40'lık gruplar hâlinde,
   seçili çeviri motoruyla (Gemini…); her satıra "söylenebilir, X sn'ye sığan" kuralı.
7. `seslendir`: her satır, kendi karakterinin sesi ve duygusuyla. Süreye sığdırma: en çok
   `hiz_siniri` (1,25×) perdesiz hızlandırma; yine uzunsa bir kez daha kısa çeviri istenir.
8. `karistir`: Türkçe sesler arka plan izinin üstüne; konuşma boyunca arka plan −6 dB yumuşakça kısılır
   (sidechain), seslere hafif EQ (80 Hz altı kesilir) + tepe sınırlayıcı.
9. `birlestir`: ffmpeg ile görüntü kopyalanır (yeniden kodlanmaz) + yeni ses (AAC 192k) →
   `<ad> - Türkçe dublaj.mp4` asıl videonun yanına (asıl dosya ASLA değişmez; ad doluysa ` (2)` eklenir).
   `dublaj.video_srt:true` ise yanına `<ad> - Türkçe dublaj.srt`.
İş klasörü: `<sistem geçici klasörü>/AltYaziKoprusu-dublaj/<iş kimliği>/` (kimlik = yol+boyut+değişme
zamanı özeti); iş başarıyla bitince silinir.

| Yöntem | Yol | Ne yapar |
|---|---|---|
| POST | `/api/dublaj/dosya-sec` | Bu bilgisayarda yerel "Dosya aç" penceresi açar → `{"yol":"D:\\Kayıt\\gta.mp4","ad":"gta.mp4","boyut_mb":812}` ya da `{"yol":null}` (vazgeçti) |
| POST | `/api/dublaj/video` | `{"yol":"..."}` → işi başlatır/sürdürür. Hatalar: `400 video_gecersiz` (yok, uzantı mp4/mkv/mov/webm/avi değil, klasör), `409 dublaj_paket_yok`, `409 video_suruyor` |
| GET | `/api/dublaj/video` | `{"durum":"bosta"\|"calisiyor"\|"bitti"\|"hata"\|"iptal","ad":"gta.mp4","asama":"seslendir","asamalar":[{"kod":"cikar","durum":"bitti","yuzde":100}],"yuzde":63,"kalan_sn":420,"satir":{"bitti":120,"toplam":190},"konusmaci_sayisi":4,"cikti":"D:\\Kayıt\\gta - Türkçe dublaj.mp4","srt":"...","hata":null,"mesaj":null,"devam_edilebilir":false}` |
| POST | `/api/dublaj/video/iptal` | Durdurur; ara çıktılar saklanır (`devam_edilebilir:true`) |
| POST | `/api/dublaj/video/goster` | Bitmiş videoyu dosya yöneticisinde seçili gösterir |
SSE `dublaj-video`: `GET /api/dublaj/video` ile aynı gövde (değişince). `kalan_sn`: aşama başına
ölçülen hızdan tahmin (ilk aşamalarda kaba tahmin).

### 14.5 Ayarlar (`dublaj` içine eklenenler)
`orijinal_ses`: `"otomatik"` | `"kis"` | `"tamamen_turkce"` (`"otomatik"`); `hafif_mod`: `"kapali"` | `"acik"` |
`"otomatik"` (`"kapali"`); `ayirma`: bool (`true`); `erken_seslendir`: bool (`true`; altyazıyla önden hazırlık);
`ses_girisi`: metin ≤ 200 (`""`); `ses_profili_izni`: bool (`false`); `video_srt`: bool (`true`);
`video_motor`: `"chatterbox"` | `"pocket"`. Bilinmeyen değer `400 gecersiz_ayar`.
`GET /api/dublaj` ek alanları: `paket` (14.1 gövdesi), `isci` (paket kullanılıyor mu), `tamamen_turkce`,
`tamamen_turkce_destek`, `hafif`, `gecikme`.

**Ses profili (tek istisna):** `ses_profili_izni:true` iken her karakterin (OCR'daki konuşan adı) en uzun 3
örneği (her biri ≤ 10 sn) bu bilgisayarda `<ayar_dizini>/oyunlar/<oyun>/sesler/` altında WAV olarak saklanır
(aynı karakter için en sık 30 sn'de bir yazılır) ve oturum başında belleğe alınır. Hiçbir yere gönderilmez.
`GET /api/dublaj/ses-profilleri` → `{"izin":false,"oyun":"gta6","profiller":[{"ad":"Lucia","sure_sn":18.2,"klip":3,"tarih":"..."}]}`;
`DELETE /api/dublaj/ses-profilleri[?ad=Lucia]` → `{"tamam":true,"silinen":1}`. İzin kapalıyken hiçbir ses diske yazılmaz.

### 14.6 Kurallar
- Mikrofon asla (yakalama kartı girişi yalnız kullanıcı adıyla seçerse). Canlı ses örnekleri yalnız
  bellekte; tek istisna izinli "Ses profili" (§14.5). Video modunda ara dosyalar yalnız iş klasöründe,
  iş bitince silinir; çıktı videosu kullanıcının dosyasıdır.
- API anahtarları işçiye verilmez (çeviri ana programda yapılır); günlükte anahtar yoktur.
- Gerçek kişilerin (ünlülerin, seslendirme sanatçılarının) seslerini taklit eden hazır ses paketi yoktur; yalnız
  videodaki/oyundaki karakterin kendi sesi örneklenir. Tek istisna, karakterin sesi henüz yokken kullanılan iki
  anonim, açık lisanslı yedek sestir (VCTK, CC BY 4.0; §14.3).
- **Yasal not (panelde de yazar):** Dublaj kişisel kullanım içindir. Dublajlı videoyu yayınlamak
  (YouTube vb.) oyunun ve seslendirme sanatçılarının haklarına tabidir; izin almak kullanıcının sorumluluğundadır.

## 15. PS5 gizli bağlantı — pencere açmayan, kol göndermeyen Remote Play (sürüm 0.10)

Amaç: PS5 → HDMI → TV kurulumunda bilgisayar oyunu **pencere açmadan** izlesin; TV'deki DualSense
oyunu kontrol etmeye devam etsin. Resmî PS Remote Play uygulaması (ikinci hesapla bile) gerçek bir
denemede kontrolü bilgisayara aldı; bu yüzden program kendi gizli istemcisini taşır. Resmî uygulama
penceresini yakalamak **yedek** seçenek olarak kalır (§12). Bu bölüm §12 ve §14.3'ü genişletir.

### 15.1 Parçalar
- `ayk-uzaktan(.exe)`: kendi küçük C yardımcımız (`uzaktan/ayk_uzaktan.c`), chiaki-ng'nin `libchiaki`
  kütüphanesine (AGPL-3.0, sürüm **v1.10.1**, commit `f30da0aaeb96fc0026cc03683153f682352e7d7c`) ve
  FFmpeg'in yalnız H.264/HEVC çözücüsü + swscale'ine (LGPL, **7.1.1**) statik bağlanır. Penceresi,
  ses çıkışı ve kol/klavye girişi **yoktur**; yalnız ağ konuşur, standart giriş/çıkışla programla konuşur.
- Python: `kopru/uzaktan/` (PSN hesap kimliği, kayıt, oturum yöneticisi, kanal çözücü).
- Windows paketinde `_internal/uzaktan/ayk-uzaktan.exe`. Geliştirmede `KOPRU_UZAKTAN_YARDIMCI`
  ortam değişkeni yolu verir. Yardımcı yoksa `destek:false` ve panel yedek yolu (resmî uygulama penceresi) önerir.

### 15.2 Kol (DualSense) kuralı — değişmez
- Yardımcı **hiçbir zaman** kol, klavye, fare, dokunmatik, mikrofon ya da hareket verisi göndermez;
  `chiaki_session_set_controller_state` hiç çağrılmaz, klavye/DualSense özellikleri kapalı açılır.
- libchiaki'nin oturum sırasında kendiliğinden yolladığı "geri bildirim" paketleri (~200 ms'de bir)
  **boştaki (hiçbir tuşa basılmamış) kol durumunu** taşır; bu, PlayStation'ın oturumu açık tutması için
  kütüphanenin kendi davranışıdır. Bu durum hiçbir zaman değiştirilmez.
- Bağlantı ikinci PSN hesabıyla kurulur (TV'deki ana hesap kendi kolunu tutar).
- Gerçek PS5'te doğrulanmadı (§15.9).

### 15.3 Yardımcının komutları
Çağrı: `ayk-uzaktan <komut>`. Gizli değerler (hesap kimliği, anahtarlar, PIN) **komut satırında
değil**, standart girişin ilk satırında tek JSON nesnesiyle verilir (başka süreçler komut satırını görebilir).
Günlük satırları stderr'e yazılır (anahtarlar ve PIN günlüğe yazılmaz).

| Komut | stdin ilk satırı | stdout |
|---|---|---|
| `--help` / `surum` | — | kullanım / `{"olay":"surum","surum":"1","chiaki":"1.10.1","ffmpeg":"..."}` |
| `ozdenetim` | — | `{"olay":"ozdenetim","tamam":true,"h264":true,"hevc":true,"opus":true,"ag":true}` + `OZDENETIM uzaktan=tamam` |
| `bul` | `{"hedefler":["255.255.255.255"],"sure_ms":3000}` | her PS5 için `{"olay":"konsol","host":"192.168.1.30","ad":"PS5-123","durum":"acik"\|"uyku","kimlik":"..","oyun":".."}`, sonunda `{"olay":"bitti"}` |
| `uyandir` | `{"host","kayit_anahtari"}` | `{"olay":"uyandir","tamam":true}` |
| `kaydet` | `{"host","hesap":"<base64 8 bayt>","pin":12345678}` | `{"olay":"kayit","tamam":true,"ad":"PS5-123","kayit_anahtari":"<32 hex>","sabah":"<32 hex>","mac":"<12 hex>","hedef":1000100}` ya da `{"olay":"kayit","tamam":false,"neden":2148567817,"ayrinti":"..."}` |
| `akis` | `{"host","kayit_anahtari","sabah","hesap","cozunurluk":720\|1080,"fps":30,"kodek":"h264"\|"hevc","ses":true}` | ikili çerçeveler (15.4) |

Anahtar biçimi (önemli): `kayit_anahtari` ve `sabah`, libchiaki'nin `rp_regist_key` / `rp_key`
alanlarının **çözülmüş 16 baytının** onaltılık yazımıdır (32 hex karakter). PS5'in verdiği metin
(`PS5-RegistKey`) libchiaki tarafından zaten çözülür; onu bir kez daha metin olarak saklamak oturumun
`0x80108b26` ile reddedilmesine yol açar (GameTranslator'ın düzelttiği hata). Uyandırma kimliği:
`kayit_anahtari` baytlarının sondaki sıfırlar atılmış ASCII metni 16 tabanında sayı olarak okunur.

### 15.4 `akis` kanalı
- stdout: çerçeveler `"AY"` + tür (1 bayt) + 0 + uzunluk (uint32 LE) + veri.
  - `J`: UTF-8 JSON olay: `bagli`, `ad`, `kare_boyutu {"g","y"}`, `giris_pin_gerekli`, `bitti {"neden":"durdu"|"kullanimda"|"reddedildi"|"erisilemedi"|"ag"|"kapandi"|"surum"|"diger","ayrinti","neden_kodu"}`, `gunluk`.
  - `V`: kare: genişlik (uint16 LE), yükseklik (uint16 LE), sonra BGRA satırları (satır = g×4 bayt).
  - `S`: ses: 16 kHz, tek kanal, 16 bit işaretli LE PCM (PS5'in 48 kHz stereo Opus sesinden indirgenmiş).
- stdin satırları: `kare` (son çözülmüş kareyi bir kez gönder; kareler YALNIZ istenince gönderilir),
  `kare <azami_genislik>`, `giris_pin <4 hane>`, `dur`. stdin kapanırsa yardımcı oturumu kapatıp çıkar.
- Görüntü PS5'ten 720p/30 H.264 istenir (`cozunurluk`/`kodek` ayarı). OCR kareyi kendi hızıyla ister.

### 15.5 PSN hesap kimliği (ikinci hesap)
chiaki-ng'nin belgelediği resmî Remote Play giriş akışı: kullanıcı panelde "Sony girişini aç"a basar,
tarayıcıda `https://auth.api.sonyentertainmentnetwork.com/2.0/oauth/authorize?...` (Remote Play
istemcisinin herkese açık `client_id`'si) açılır, **ikinci hesapla** girer; tarayıcı
`https://remoteplay.dl.playstation.net/remoteplay/redirect?code=...` adresine gider (sayfa boş/hatalı
görünebilir). Kullanıcı bu adresi kopyalayıp panele yapıştırır; program kodu `.../oauth/token` ile
erişim belirtecine, belirteci `.../oauth/token/<belirteç>` ile `user_id`'ye çevirir; `user_id` (ondalık)
8 baytlık little-endian dizi olur ve base64 yazılır. **Şifre programa hiç girmez; belirteç saklanmaz.**
Bilen kullanıcı base64 kimliği elle de girebilir.

### 15.6 Saklama
- Şifreli kasa (`anahtarlar.py`, keyring): `ps5_hesap` = base64 hesap kimliği; `ps5_kayit` =
  `{"host","ad","kayit_anahtari","sabah","mac","hedef"}` JSON. Düz dosyaya ASLA yazılmaz; kasa yoksa
  kayıt yapılamaz (`kasa_yok`).
- Ayar dosyası (`ps5` nesnesi, gizli değil): `{"host":"192.168.1.30","ad":"PS5-123","cozunurluk":720,"kodek":"h264","kol_tv":null|true|false}`.
- Kaynak kodu: `"kaynak":"ps5:gizli"`. `yakalama.kare_al("ps5:gizli")` pencere yakalamayla aynı
  arayüzdür (PIL.Image); oturum yoksa açar ve ilk kareyi en çok 15 sn bekler, olmazsa `YakalamaHatasi`.
  `GET /api/kaynaklar` listesinin başına (yardımcı varsa) `{"kod":"ps5:gizli","ad":"PS5 (gizli bağlantı)","tur":"ps5","onerilen":bool,"kayitli":bool}` eklenir.

### 15.7 Panel API'si
| Yöntem | Yol | Ne yapar |
|---|---|---|
| GET | `/api/ps5` | `{"destek":bool,"neden":null\|"yalniz_windows"\|"yardimci_yok","hesap":{"var":bool,"ozet":"AbC…"},"konsol":{"host","ad","kayitli":bool}\|null,"baglanti":{"durum":"kapali"\|"uyandiriliyor"\|"baglaniyor"\|"bagli"\|"bekliyor"\|"hata","hata":kod\|null,"mesaj":metin\|null,"kare_boyutu":[g,y]\|null,"kare_sayisi":n,"ses":bool,"deneme":n},"kol_tv":null\|bool}` |
| POST | `/api/ps5/psn/adres` | `{"adres":"https://auth.api.sonyentertainmentnetwork.com/..."}` |
| POST | `/api/ps5/psn/kod` | `{"adres":"<yapıştırılan adres ya da kod>"}` → `{"tamam":true,"ozet":"AbC…"}`. Hata: `400 psn_kod_yok`, `400 psn_reddetti`, `429 psn_cok_deneme`, `502 psn_ag`, `502 psn_yanit` |
| POST | `/api/ps5/psn/elle` | `{"kimlik":"<base64>"}` → 8 bayt değilse `400 psn_kimlik_gecersiz` |
| POST | `/api/ps5/bul` | `{"host":"192.168.1.30"?}` (boşsa yayın) → `{"konsollar":[{"host","ad","durum","kayitli"}]}` |
| POST | `/api/ps5/kaydet` | `{"host","pin"}` → `{"tamam":true,"ad"}`. Hata: `400 ps5_pin_gecersiz`, `409 psn_hesap_yok`, `502 ps5_pin_yanlis`, `502 ps5_hesap_taninmadi`, `502 ps5_kullanimda`, `502 ps5_yanit_yok`, `502 ps5_surum`, `502 ps5_kayit_hata` |
| POST | `/api/ps5/baglan` | Oturumu açar (uyku modundaysa önce uyandırır); `ayar.kaynak` değişmez |
| POST | `/api/ps5/kes` | Oturumu kapatır |
| POST | `/api/ps5/uyandir` | Uyandırma paketi yollar |
| GET | `/api/ps5/onizleme` | Son karenin küçük JPEG'i (≤ 480 px); kare yoksa `404 ps5_kare_yok`. Diske yazılmaz |
| POST | `/api/ps5/kol` | `{"calisiyor":bool}` → `ayar.ps5.kol_tv` |
| POST | `/api/ps5/giris-pin` | `{"pin":"1234"}`: ikinci kullanıcının PS5 giriş şifresi varsa (`baglanti.giris_pin:true`) |
| DELETE | `/api/ps5` | Oturumu kapatır, kasadaki `ps5_hesap` ve `ps5_kayit`'ı ve `ayar.ps5`'i siler |
SSE `ps5`: `GET /api/ps5`'in `baglanti` gövdesi (değişince).

### 15.8 Yeniden bağlanma, uyandırma, ses
- Oturum `bitti` ile kapanırsa (`ag`, `erisilemedi`, `kapandi`, `diger`) 2, 4, 8, 15, 30 sn arayla yeniden denenir
  (`durum:"bekliyor"`, `deneme` artar). `reddedildi` (kayıt geçersiz) ve `kullanimda`'da tekrar denenmez:
  `hata` + Türkçe açıklama (`ps5_kayit_gecersiz` / `ps5_kullanimda`).
- `POST /api/durdur` kaynak `ps5:gizli` iken oturumu da kapatır; `Başlat` (ilk kare isteği) yeniden açar.
- Bağlanmadan önce `bul` ile durum sorulur; `uyku` ise `uyandir` yollanır, 40 sn'ye kadar `acik` beklenir.
- Ses (canlı dublaj): kaynak `ps5:gizli` iken işçinin `canli_baslat`'ına `{"ps5_ses":{"kapi":p,"anahtar":a}}`
  eklenir; işçi `127.0.0.1:p`'ye bağlanır, ilk satır olarak anahtarı yollar, sonra 16 kHz mono 16 bit PCM
  okur (`parca.kaynak:"ps5"`). Ana program bu kapıyı yalnız 127.0.0.1'de, oturum başına rastgele 32 baytlık
  anahtarla açar. PS5 sesi bilgisayarda **çalınmaz** (TV zaten çalar); "tamamen Türkçe" kipi bu kaynakta yoktur.
- Mikrofon asla; ses ve kareler yalnız bellekte.

### 15.9 Bilinen sınırlar (dürüstçe)
- Gerçek PS5 ile denenmedi: kayıt, oturum, kare/ses akışı yalnız sahte yardımcıyla ve derleme/öz denetimle sınandı.
- Kolun TV'de kalması ikinci hesap + hiç girdi göndermeme tasarımına dayanır; PS5 yazılımının oturum başında
  odağı uzaktaki kullanıcıya verip vermediği doğrulanmadı. Panel bağlantı testinde kullanıcıya sorar; "Hayır"
  derse önce DualSense'in PS tuşuna basıp ana hesabı seçmesini, olmazsa yedek yolu önerir.

## 16. Orijinal yazının üstünü örtme, düğme simgeleri, okuma gürültüsü, sıralı hızlı gösterim (sonraki sürüm)

Gerçek kullanımdan (PS5 → HDMI → LG TV, laptop gizli Remote Play'den okur): Türkçe yazı İngilizcenin
yanına/altına çıkıyordu, düğme simgeleri kayboluyordu, HUD simgeleri çeviriye gidiyordu ve hızlı diyalogda
(1 sn, 1 sn, 2 sn, 1 sn) çeviriler geç gelip bir an görünüyor, bazıları hiç görünmüyordu. Bu bölüm §7.2,
§11.4, §12.4 ve §13.4'ü günceller.

### 16.1 Üstünü örtme (varsayılan yerleşim)
- Yeni görünüm alanı `gorunum.yerlesim`: `"ustune"` (varsayılan) | `"cubuk"` (eski davranış: altyazı alttaki/üstteki
  çubukta, `konum` ile). Panel tek seçimde sunar: "Orijinal yazının üstünde" / "Altta" / "Üstte".
- `yerlesim:"ustune"` iken `yazi` olayına `ortu` eklenir (kaynak satırın kutusu, tam kareye göre 0–1):
  `{"x","y","g","y2","zemin":"#RRGGBB","renk":"#RRGGBB","opaklik":0.94,"metin":"çizilecek metin","satir":n}`
  (`yazi.metin` yine tam çeviridir; `ortu.metin` uçtaki, örtülmeyen düğme simgesi çıkarılmış hâlidir, §16.2).
  Kutu kaynağın kutusudur, her yöne yazı yüksekliğinin ~%15'i kadar (en az 0,002) genişletilir.
  `zemin`: kutunun hemen dışındaki piksellerin ortancası (oyunun kendi arka planı); hesaplanamazsa `#0B0F18`.
  `renk`: zemin açıksa (bağıl parlaklık > 0,55) `#111111`, değilse `gorunum.yazi_rengi`.
  `satir`: kaynak yazının satır sayısı (yazı boyu hesabı için).
- Ekran öğeleri: hedef `"ustune"` (kullanıcı kutusu değil) ve `yerlesim:"ustune"` iken `ekran.ogeler[]` öğesine
  aynı biçimde `ortu` eklenir (`aciklama` kutunun hemen altında küçük yazılır). Kullanıcının çizdiği hedef kutusu ve `hedef:"altyazi"` (çubuk) değişmez (§11.4).
- İstemci (TV `ortak.js`, `/tv`, `/obs`, bilgisayar katmanı) `ortu` varsa: kutuyu tam o yere, o boyda, opak
  (`opaklik`, varsayılan 0,94) `zemin` rengiyle çizer; yazı boyunu kutuya sığacak en büyük boydan başlatıp
  (en çok kutu yüksekliği / satır × 0,8) küçültür; en çok 2 satır (kaynak daha çok satırlıysa o kadar), yalnız
  boşlukta bölünür. En az okunur boy 1080p'de 16 px (ekran öğesinde 12 px); o boyda da sığmazsa kutu aşağı
  ve sağa doğru büyür (ekran dışına taşmaz; kenarda ise içeri kayar), İngilizce yine örtülü kalır.
- LG TV uygulaması (0.1.x) `ortak.js`'i paketin içinde taşır: örtü için TV uygulaması bir kez yeniden kurulur (panelden tek tuş;
  §18'den sonra bu son kurulumdur, uygulama artık bilgisayardan güncellenir);
  eski uygulama `ortu` alanını tanımaz ve eski çubuğu çizer (geriye uyumlu).
  `ortu` yoksa eski çizim (§7.2/§12.4) aynen kullanılır.
- Örtme modunda "önceki satır" (§7.2/7) gösterilmez (eski yazının yerinde zaten yenisi vardır).
- Katman maskesi (§11.1 yedeği): kaynağın üstündeki örtü maskelenmez (kendi kaynağını silerdi). Bilgisayar ekranı
  kipinde örtü, katman yakalamadan hariç tutulamıyorsa (`WDA_EXCLUDEFROMCAPTURE` yok, Windows 10 2004 öncesi) okuyucu
  İngilizce yerine kendi Türkçemizi görür; o durumda `yerlesim:"cubuk"` önerilir.

### 16.2 Düğme simgeleri korunur
- Düğme belirteçleri: PlayStation `✕ ○ △ □` (ve OCR'ın sık yanlış okudukları: `×`→`✕`, `®`/`©`/`◯`/`⭘`→`○`,
  `Δ`/`▵`→`△`, `◻`/`▢`/`☐`→`□`; yalnız tek başına duran simge olarak), `L1 L2 L3 R1 R2 R3`, `OPTIONS`,
  `CREATE`, `SHARE`, `PS`, Xbox `LB RB LT RT LS RS`, köşeli/açılı/yuvarlak parantezli tek harf ya da sayı
  (`[X]`, `<A>`, `(B)`), yön okları `← → ↑ ↓ ◀ ▶ ▲ ▼`.
- Çeviriden önce normalize edilir (yanlış okumalar doğru simgeye) ve istemde "düğme belirteçlerini aynen,
  cümledeki yerinde bırak" kuralı vardır. Çeviride kaybolan belirteç, kaynaktaki yerine göre başa ya da sona eklenir.
- Örtme: okuyucu kelime kutuları verirse (Windows OCR `words[].bounding_rect`), satırın **başındaki ya da
  sonundaki** düğme simgesi örtünün dışında bırakılır (gerçek simge görünür; örtü onun yanından başlar/biter)
  ve `ortu.metin`'den aynı uçtaki belirteç çıkarılır. Ortadaki simgeler örtülür; belirteç Türkçe metnin içinde
  rozet olarak çizilir (`span.ak-dugme`). Kelime kutusu yoksa (RapidOCR, Apple Vision) hepsi rozettir.
- `Satir.kelimeler`: `[(metin, x, y, g, y2)]` (0–1, okuyucunun verdiği kelime kutuları; yoksa boş).

### 16.3 Okuma gürültüsü süzgeci (§11.3'e ek, çeviriden önce)
- Satırdan emoji/piktogram (`So`/`Cs`/`Co` sınıfı, değişken seçiciler, ZWJ) ve 2+ karakterlik simge yığınları
  silinir; harf, rakam, olağan noktalama (`. , ! ? ; : ' " - – — … ( ) % / & + #`), kesme işaretleri ve §16.2
  belirteçleri kalır. Tek başına duran, düğme olmayan tek karakterli simgeler atılır.
- Sonra satır çevrilmez: harf sayısı < 2, ya da harf payı (belirteçler hariç, boşluksuz) < %50, ya da yalnız
  sayı/süre/koordinat/yüzde (`12:34`, `3/10`, `X: 120 Y: 45`, `100%`, `x3`, `+250`), ya da yalnız belirteçlerden
  oluşuyor, ya da §11.3 tekrar kuralı. Virgülle ayrılıp `!`/`?`/`.` ile biten tekrar gerçek konuşmadır, çevrilir
  ("Move, move, move!", "Go, go, go!").

### 16.4 Sıralı, hızlı gösterim (§13.4'ün güncellemesi)
Gecikme zinciri: kare aralığı (0,25 sn) → OCR → kararlılık → çeviri isteği → yayın → TV. Değişiklikler:
- **Çeviri kare döngüsünü bekletmez.** Her altyazı satırının çevirisi ayrı bir görevde, aynı anda (paralel)
  yürür; kare okuma sürer, böylece çeviri beklerken gelen satırlar kaçmaz. Gösterim sırası satırların ekrana
  geliş sırasıdır (sıra numarası/`id`), çevirilerin bitiş sırası değil.
- Altyazı satırı ilk görüldüğü karede çevrilmeye başlar (önden çeviri, §6.4; yalnız 50 ms beklenir ki hemen
  değişen metne istek gitmesin); ikinci karede aynıysa kesinleşir. Önden istek henüz yola çıkmadıysa kesinleşince
  beklemeden yenisi atılır. Daktilo gibi büyüyen yazı kararlı olunca çevrilir (eskisi gibi). Çevirisi başarısız
  olan aynı satır en erken 1 sn sonra yeniden denenir (her karede istek atılmaz).
- HTTP bağlantısı motorlar arasında açık tutulur (aynı olay döngüsünde tek oturum, keep-alive; başka iş parçacığının
  döngüsü kendi oturumunu açar). Sunucunun sessizce kapattığı açık bağlantı yanıt gelmeden koparsa
  (`ServerDisconnected`/bağlantı sıfırlandı) aynı istek kalan süre içinde **bir kez** yeni bağlantıyla yinelenir.
- **Gemini düşünme düzeyi (altyazı):** Flash modellerinde `thinkingConfig.thinkingLevel:"low"` (az ama sıfır değil:
  daha doğal Türkçe, kısa gecikme), Flash-Lite'ta `"minimal"`; Gemini 2.x'e düzey gönderilmez. (0.1.3 her modele
  `"minimal"` yolluyordu: varsayılan **gemini-3.8-flash "minimal"i desteklemez** → HTTP 400 → düşünme ayarı
  kaldırılıp yeniden deneniyordu → model varsayılan `"medium"` düşünmeyle yanıt verip 8 sn sınırını aşıyor, satırlar
  atlanıyordu: "altyazıyı hiç çevirmiyor".) Model bir düzeyi yine de tanımazsa (HTTP 400) o model için düzeysiz
  denenir ve hatırlanır. Altyazı isteğinin sınırı 8 sn; zaman aşımı, 429 ya da 5xx'te satır kaybolmasın diye kendi
  kotası olan `gemini-3.5-flash-lite` (`"minimal"`, 6 sn) bir kez denenir. Kalite `hizli` (Flash-Lite) en kısa
  gecikmedir; panel bunu "En hızlı" diye sunar.
- Altyazı satırının konuşanı (`"AD: ..."` ön eki) ve oyun bilgisindeki cinsiyeti istemde bağlam olarak verilir
  (yalnız cinsiyetli sözcükler/ton için; çeviriye ad eklenmez); son satırlar bağlamı konuşan adıyla tutulur.
- **Kuyruk tıkanmaz:** bir satırın çevirisi en çok 15 sn beklenir (`SATIR_EN_COK_SN`); aşarsa satır atlanır
  (`atlanan`, `durum` `hata:"ag"`), sıradakiler gösterilir. Satıra devredilmiş önden çeviri dışarıdan iptal edilirse
  satır askıda kalmaz, kendi isteğini yapar.
- **Kuyruk, hiçbir satır atlanmaz.** Her satır sırayla gösterilir. Satır `i` gösterildiği an `g_i`, gecikmesi
  `L_i = g_i - t_gel_i`, doğal bitişi `d_i = max(t_git_i + L_i, g_i + taban_i)`.
  - `okuma_i = max(en_az, min(3,5 sn, max(1,2 sn, karakter × gorunum.karakter_ms)))` (çevirinin karakter sayısı;
    `karakter_ms` 40–120, varsayılan 60); `en_az_ms` 0 ise hiçbir taban yoktur.
  - `taban_i`: **geride kalınmışsa** `okuma_i` (satır çevirisi hazır olduktan sonra kuyrukta 0,3 sn'den fazla beklediyse
    ya da sonraki satır, bu satırın doğal bitişinden `t_git_i + L_i` 0,3 sn'den fazla önce hazırsa); değilse satır bir
    **diyalog zincirindeyse** (önceki satırın yerine geçerek gösterildiyse ya da sonraki satır hazırsa) `max(en_az, 1,2 sn)`;
    tek başına satırda `en_az` (§13.4 aynen). Böylece gecikme sabitken (her çeviri aynı sürede) satırlar oyundaki
    sürelerince görünür; yalnız 1,2 sn'den kısa olanlar 1,2 sn'ye uzar.
  - Sonraki satır hazırsa (geride kalınmış): satır `i` en erken `g_i + taban_i`'de, en geç
    `max(g_i + taban_i, min(d_i, t_hazir_{i+1}))`'de biter ve sonraki **aynı anda** yerine geçer (boşluk, çakışma yok).
    Uzun satır okuma tabanına kırpılır, kısa satır okuma tabanına uzatılır: kuyruk satır atarak değil, aradaki
    boşluğu kırparak yetişir.
  - Sonraki satır henüz çevriliyorsa ve kaynak hiç boşalmadan değiştiyse eskisi en çok `d_i + 2 sn` bekler; yoksa `d_i`'de
    `yazi-sil {"id"}`.
  - Çevirisi başarısız olan satır kuyruktan çıkar (hata `durum` olayıyla bildirilir).
- Örnek (sınanır): oyunda 1, 1, 2, 1 sn'lik satırlar, her çeviri 1,5 sn → dördü de sırayla, her biri en az
  okuma tabanı kadar görünür.
- **Gecikme bilgisi:** `GET /api/durum` yanıtına `gecikme` eklenir (yalnız çalışırken, son 20 satırın ortancası, ms):
  `{"kare_ms","okuma_ms","kararlilik_ms","ceviri_ms","bekleme_ms","toplam_ms","kuyruk":n,"atlanan":n,"olcum":n}`
  (`kare`/`okuma`: son karenin alınması ve yazı okuma süresi; `kararlilik`: ilk görülme → kesinleşme; `ceviri`:
  istek → yanıt; `bekleme`: çeviri hazır → ekrana; `toplam`: ilk görülme → ekrana; `kuyruk`: sırada bekleyen satır;
  `atlanan`: çevirisi başarısız olduğu için gösterilemeyen satır sayısı). Panel ana ekranda kısa bir satırla gösterir.
- Ekran öğesi (görev/menü) çevirisi de kare döngüsünü bekletmez: önceki öğe çevirisi sürerken o karede öğe adımı atlanır.

## 17. Erişim 2: altyazı sınırsız, dublaj süresi, "+30 dk" reklamı, cihaza bağlı kod (sonraki sürüm)

Sahibin kararı. Bu bölüm §7.3'ün **yerine geçer** (eski "günde 30 dk ücretsiz çeviri" kuralı kalktı).

### 17.1 Ne sınırlı, ne değil
- **Altyazı/ekran çevirisi herkese sınırsız ve ücretsizdir.** Hiçbir sayaç, kota ya da `ErisimSiniri` altyazı yolunu
  durdurmaz (`CeviriYoneticisi.cevir`, `/api/dene`, oyun bilgisi hazırlama sınırsızdır). `durum` olayında ve
  `GET /api/durum`'da artık `sinir` alanı YOKTUR.
- **Yalnız Türkçe dublaj sınırlıdır.** Canlı dublaj yalnız "dublaj süresi" varken ya da geçerli bir sınırsız kod
  varken çalışır. "Dublajı dene" (tek örnek cümle) süre istemez.
- Video dublajı (§14.4) başlatmak için de süre (ya da kod) gerekir; başlamış bir video işi süre bitse de sonuna kadar
  biter (yarım iş çöpe gitmesin). Video işi sürerken de süre azalır.

### 17.2 Dublaj süresi (yalnız bellekte)
- Başta **0**. "+30 dk ekle" ile her seferinde **+30 dk** eklenir; üst üste eklenebilir (30, 60, 90 …), en çok
  **4 sa (240 dk)**. Kalan + 30 dk > 240 dk ise ekleme reddedilir (`409 dublaj_sure_dolu`).
- **Diske YAZILMAZ.** Program kapanınca süre gider; sonraki açılış yine 0'dan başlar (yeniden başlatmak süre vermez).
- Süre yalnız dublaj **gerçekten çalışırken** azalır: çeviri Başlat'a basılmış + dublaj açık + boru hattı çalışıyor
  (ya da bir video dublajı işi sürüyor). Çeviri durunca ya da dublaj kapalıyken süre durur. Sayaç adımı 5 sn'dir;
  iki ölçüm arası 30 sn'den uzunsa (uyku, takılma) fazlası sayılmaz. Saat monotoniktir (sistem saati değişse de
  süre artmaz/azalmaz).
- Süre 0 olunca dublaj **sakince duraklar** (o an çalan cümle biter, yenisi başlamaz), altyazılar sürer. `durum`
  olayına `"dublaj_sinir": true` eklenir; panel sakin bir mesaj ve "+30 dk ekle" düğmesini gösterir. Süre eklenince
  dublaj kendiliğinden devam eder (Başlat'a yeniden basmak gerekmez).

### 17.3 "+30 dk ekle" = bir reklam (ya da destek ekranı)
1. Panel `POST /api/erisim/reklam` `{"yer":"otomatik"|"panel"}` → `200 {"id":"r…","vast":"https://…"|null,
   "en_az_sn":15,"hedef":"tv"|"panel","zaman_asimi_sn":120}`. Açık (bitmemiş) bir reklam varsa yenisi açılmaz, o döner.
   Hata: `409 dublaj_sure_dolu`, `409 dublaj_sinirsiz` (kod zaten sınırsız).
2. `hedef`: reklam gösterebilen bir TV uygulaması bağlıysa (`/kopru/akis?reklam=1` ile bağlanan istemci) ve
   `yer` `"panel"` değilse `"tv"`, değilse `"panel"`. `"tv"` ise SSE `reklam` olayı yayınlanır:
   `{"id":"r…","vast":"https://…"|null,"en_az_sn":15,"bitti":"/kopru/reklam/bitti"}`.
   TV oyunun üstünde tam ekran oynatır (sol üstte küçük "Reklam · n sn"), bitince `POST /kopru/reklam/bitti`
   `{"id":"r…","sure_sn":30.0}` gönderir. Panel bu sırada "Reklam TV'de oynuyor" kartını gösterir.
   `"panel"` ise reklamı panel kendi içinde (tam pencere) oynatır ve `POST /api/erisim/reklam/bitti` `{"id","sure_sn"}` gönderir.
3. **Süreyi PC verir, istemci değil.** Bitti isteği yalnız sunucu saatine göre yeterince zaman geçtiyse kabul edilir:
   `gecen ≥ max(15, min(sure_sn, 120)) − 1 sn` (`sure_sn`: istemcinin bildirdiği reklam süresi). Erken gelen istek
   `409 reklam_erken` `{"kalan_sn":n}` döner ve süre vermez; aynı reklam iki kez süre vermez (`404 reklam_yok`).
   Kabul edilince +30 dk eklenir, SSE `reklam-bitti` `{"id"}` yayınlanır (TV hâlâ oynatıyorsa kapatır).
4. **Hiç takılmaz:** VAST adresi yoksa, reklam gelmezse (boş yanıt), yüklenemezse (6 sn), oynatılamazsa ya da 8 sn
   ilerlemezse istemci 15 sn'lik **destek ekranını** (logo + "{marka}'nü desteklediğin için teşekkürler" + geri sayım)
   gösterir, sonra bitti gönderir. Reklam 15 sn'den kısa bittiyse kalan süre destek ekranıyla tamamlanır.
   TV `zaman_asimi_sn` içinde bitti göndermezse panel kendisi gönderir (yedek zamanlayıcı). 10 dk içinde bitmeyen
   reklam unutulur.
5. `GET /api/erisim` içinde açık reklam `reklam` alanında görünür (`{"id","hedef","gecen_sn","en_az_sn"}`), yoksa `null`.

### 17.4 VAST oynatıcı (sağlayıcıdan bağımsız)
- Kendi küçük VAST 3/4 ayrıştırıcımız + `<video>` (`kopru/web/tv/reklam.js`, ES5, `window.AKReklam`); TV uygulaması,
  `/tv` sayfası ve panel aynı dosyayı kullanır. `/obs` reklam göstermez (yayına reklam girmesin).
- Desteklenen: Inline/Wrapper (en çok 5 kat), Linear Creative, `progressive` MP4/WebM `MediaFile` (ekrana en uygun
  genişlik), `Impression`, `Error` (`[ERRORCODE]`), `TrackingEvents` (start, firstQuartile, midpoint, thirdQuartile,
  complete). Desteklenmeyen: VPAID, SIMID, OMID doğrulaması, atlanabilir/etkileşimli reklam, tıklama (TV'de tıklanmaz).
  Bunlar "reklam gelmedi" sayılır → destek ekranı.
- URL makroları: `[CACHEBUSTING]`, `[TIMESTAMP]` rastgele/şimdiki sayıyla değiştirilir.
- **VAST adresi** sahibin yapı ayarıdır: `kopru/reklam_ayari.py` → `VAST_ADRESI` (varsayılan boş). Gelişmiş ayarlarda
  `erisim.vast_adresi` (boş ya da `https://` ile başlayan, en çok 2000 karakter) onu ezer. Boşsa hep destek ekranı.

### 17.5 Cihaza bağlı sınırsız dublaj kodu
- **Cihaz numarası:** `SHA-256("AltYaziKoprusu/cihaz/v1" + makine kimliği)`'nin ilk 50 biti, Crockford base32,
  10 harf, `XXXXX-XXXXX` biçiminde gösterilir. Makine kimliği: Windows `MachineGuid` (kayıt defteri), macOS
  `IOPlatformUUID`, Linux `/etc/machine-id`. Bulunamazsa bir kez rastgele üretilip ayar klasörüne (`cihaz.json`)
  yazılır. Ham kimlik hiçbir yere gönderilmez, gösterilmez; numaradan geri çıkarılamaz.
- **Kod:** yine `AK1-` biçimi (§7.3). Yeni yük: `{"s":"sinirsiz_dublaj","c":"<10 harf cihaz no>","t":"YYYY-MM-DD","n":"<8 harf kod no>"}`.
  İmza Ed25519, açık anahtar `kopru/erisim_anahtar.py`. Program imzayı ve `c == bu cihazın numarası`nı denetler;
  başka cihazın kodu `400 baska_cihaz_kodu` ile reddedilir.
- **Eski kodlar geçerli:** `sinirsiz` → sınırsız dublaj (her cihazda); `gun` → bitiş tarihine kadar sınırsız dublaj.
- Kabul edilen kod şifreli kasada saklanır (`keyring`, ad `erisim_kodu`); kasa yoksa ayar klasöründeki
  `erisim.json`'a yazılır (kod gizli değildir, başka cihazda işe yaramaz). Eski `erisim.json` içindeki kod da okunur.
  Kod geçerliyken dublaj kalıcı olarak sınırsızdır: reklam yok, geri sayım yok.
- Üretim: `python araclar/kod_uret.py` sayfasında "Cihaza bağlı (sınırsız dublaj)" + cihaz numarası, ya da
  `python araclar/kod_uret.py --cihaz ABCDE-FGHJK`.

### 17.6 API (yalnız yerel; `/kopru/reklam/bitti` yerel ağ)
- `GET /api/erisim` →
  `{"altyazi":"sinirsiz","dublaj":{"sinirsiz":false,"kalan_sn":4800,"kalan_dakika":80,"aktif":true,"durdu":false,
  "ekle_dakika":30,"en_cok_dakika":240,"ekleyebilir":true},"kod":"sinirsiz_dublaj"|"sinirsiz"|"gun"|null,
  "bitis":"YYYY-MM-DD"|null,"cihaz":"ABCDE-FGHJK","tv_reklam":true,"reklam":null}`
  (`durdu`: dublaj açık ve çeviri çalışıyor ama süre bitti).
- `POST /api/erisim` `{"kod":"AK1-…"}` → `{"tamam":true,"tur":"sinirsiz_dublaj"|"sinirsiz"|"gun"}`; hata
  `gecersiz_kod`, `suresi_dolmus_kod`, `baska_cihaz_kodu` (400).
- `POST /api/erisim/reklam`, `POST /api/erisim/reklam/bitti`, `POST /kopru/reklam/bitti`: §17.3.
- `POST /api/dublaj/video` süre yoksa `402 dublaj_suresi_yok`.
- Not (dürüstçe): program açık kaynaktır (AGPL). Bütün bu sınırlar kullanıcının kendi bilgisayarında çalışır;
  kaldıran bir kopya yapılabilir. Sistem dürüst kullanıcılar ve projeyi desteklemek içindir, bir kilit değildir.

### 17.7 Reklam izni (KVKK)
- Reklam şirketinin (VAST) reklamı yalnız kullanıcı **açıkça izin verdiyse** açılır. Ayar `erisim.reklam_izni`:
  `null` (sorulmadı) | `true` | `false`. `true` değilse `POST /api/erisim/reklam` her zaman `"vast": null` döner ve
  yalnız kendi destek ekranımız gösterilir; destek ekranı **hiçbir yere bağlanmaz** (ağ isteği yok).
- Panel, VAST adresi tanımlıyken (`GET /api/erisim` → `"vast_var": true`) ve izin `null` iken "+30 dk ekle"ye ilk
  basışta kısa bir izin ekranı gösterir: "Kabul et ve reklamı izle" (`reklam_izni:true`) / "Vazgeç" (`false`; yine
  destek ekranıyla +30 dk). İzin Gelişmiş ayarlardan her an geri alınır. `GET /api/erisim` ayrıca
  `"reklam_izni": null|true|false` verir. Ayrıntı: GIZLILIK.md.

## 18. LG TV uygulaması bir daha yeniden kurulmaz: başlatıcı + bilgisayardan gelen uygulama, geliştirici modu uzatma (sonraki sürüm)

Sahibin isteği: "televizyondaki şeyi her seferinde 0'dan kurmaktansa direkt yapamıyor muyuz". Bu bölüm §8 (LG kurulumu)
ve §16.1'deki "örtü için TV uygulaması bir kez yeniden kurulur" notunun yerine geçer.

### 18.1 Parçalar
- **Başlatıcı** (`tv/webos/`, `.ipk` içinde, uygulama kimliği yine `com.altyazikoprusu.tv`, sürüm `0.2.0`; ACG'siz
  yedek varyant `0.2.1`): `index.html` (sakin "Yükleniyor…/Bilgisayar bekleniyor" ekranı), `yukleyici.js` (ES5, kararlı;
  değişmesi gerekmez), yazı tipleri, simgeler ve paketleme anında üretilen `gomulu.js` (uygulamanın pakete gömülü son
  hâli, `window.AK_GOMULU_PAKET`). Başlatıcı sürümü (`yukleyici`) tam sayıdır: eski (`0.1.x`) uygulama = 1, bu = **2**.
- **Uygulama** (değişen her şey): `kopru/web/tv/webos/govde.html` (gövde işaretlemesi), `webos/style.css`, `ortak.css`,
  `marka.js`, `webos/i18n.js`, `webos/platform-webos.js`, `ortak.js`, `reklam.js`, `webos/app.js` (bu sırayla).
  Bilgisayar bunları tek bir JSON "paket" olarak sunar; her program güncellemesi TV'yi kendiliğinden günceller.
- Yazı tipleri ve simgeler pakette kalır (CSS `url(yazi-latin.woff2)` başlatıcının klasörüne göre çözülür).

### 18.2 `GET /kopru/tv/uygulama`  (yerel ağ, CORS `*`)
Sorgu: `yukleyici=<n>` (başlatıcı sürümü), `surum=<elindeki paket sürümü>` (isteğe bağlı).
- Elindeki sürüm güncelse: `{"uygulama":"altyazikoprusu-tv","surum":"<12 hex>","ayni":true}`.
- Değilse tam paket:
  `{"uygulama":"altyazikoprusu-tv","surum":"<12 hex>","yukleyici_en_az":2,"kopru_surum":"0.1.4",
    "html":"<gövde>","css":["…","…"],"js":[["ortak.js","…"],…]}`.
  `surum` = bütün içeriğin SHA-256'sının ilk 12 hex'i (dosya değişmedikçe aynı).
- Başlatıcı `yukleyici_en_az`'dan eskiyse `{"uygulama":"altyazikoprusu-tv","eski_yukleyici":true,"yukleyici_en_az":n}`
  döner; başlatıcı elindeki (önbellek/gömülü) paketle açılır ve panel "bir kez yeniden kurun" der.
- Her istek TV'yi kayda geçirir (§18.5).

### 18.3 Başlatıcının akışı (`yukleyici.js`)
1. Kayıtlı bilgisayar (`localStorage.ak_son_pc`) varsa paketi ondan ister (4 sn sınır).
   Gelen paket doğrulanır (`uygulama`, `surum`, `html`, `css[]`, `js[][2]`), **önbelleğe** yazılır
   (`localStorage.ak_paket`, en çok ~1,5 MB; sığmazsa yazılmaz) ve çalıştırılır (`kaynak:"pc"`).
2. Bilgisayar yanıt vermezse önbellekteki son iyi paket (`kaynak:"onbellek"`), o da yoksa gömülü paket
   (`kaynak:"gomulu"`) çalışır. Uygulama kayıtlı bilgisayarı beklerken sakin **"Bilgisayar bekleniyor…"** ekranını
   gösterir ve 5 sn'de bir yeniden dener (arama/elle adres/deneme düğmeleri durur).
3. Çalıştırma: CSS'ler `<style>`, gövde `<body>` içine, JS'ler sırayla satır içi `<script>` olarak eklenir (webOS
   paketli uygulamalarında CSP yoktur; köken `file://` kalır, böylece `PalmServiceBridge`/Luna ve HDMI `<video>`
   eskisi gibi çalışır — uygulamayı `http://` adresine yönlendirmek bu yetkileri kaybettirirdi).
4. Güvenlik ağı: paketin ilk 8 sn'sinde yakalanmamış bir hata olursa (ya da paket hiç açılamazsa) o sürüm "kötü"
   işaretlenir (`localStorage.ak_paket_kotu`), önbellek silinir ve uygulama bir kez gömülü paketle yeniden açılır.
5. `window.AKYukleyici = {surum:2, paket:"<surum>", kaynak, denetle(adres, cb)}`. Uygulama bilgisayar bulup
   seçtiğinde ve akış koptuktan sonra yeniden bağlandığında `denetle` çağırır; bilgisayardaki sürüm farklıysa yeni paket
   önbelleğe yazılır ve sayfa yeniden yüklenir (reklam oynarken yüklenmez, bitince yüklenir).
6. Uygulama akışa `…/kopru/akis?reklam=1&yukleyici=2&paket=<surum>` ile bağlanır.

### 18.4 Eski kurulumlar
`0.1.x` uygulaması aynen çalışır (akış değişmedi), yalnız kendini güncelleyemez. Başlatıcıya geçmek için **bir son kez**
yeniden kurulur (panelde tek tuş, §8); sonra bir daha kurulum gerekmez (geliştirici modu süresi dolmadıkça, §18.6).

### 18.5 TV kaydı ve panel API'si (yalnız yerel)
- Sunucu, `/kopru/tv/uygulama` ve `/kopru/akis` isteklerinden TV'leri RAM'de tutar (adres başına; en çok 16):
  `yukleyici` (akış sorgusunda yoksa ve istek `Origin: null` ile — paketli uygulama — geliyorsa **1** = eski uygulama;
  tarayıcıdaki `/tv` sayfası kaydedilmez), `paket`, son görülme.
- `GET /api/tv/uygulama` →
  `{"paket_surum":"<12 hex>","yukleyici_guncel":2,"durum":"guncel"|"eski"|"bilinmiyor","mesaj":"…",
    "tvler":[{"adres":"192.168.1.30","yukleyici":2,"paket":"<12 hex>","guncel":true,"son_gorulme_sn":4}]}`.
  `durum`: en az bir TV görülmüşse ve hepsinin başlatıcısı güncelse `guncel`; biri eskiyse `eski`
  ("TV uygulaması eski: bir kez yeniden kurun, sonra hep kendiliğinden güncellenir"); hiç TV görülmediyse `bilinmiyor`.
  TV'nin paketi henüz eski sürümse (`paket` ≠ `paket_surum`) `guncel:false` ama `yukleyici` 2 ise yeniden kurulum
  gerekmez: TV bir sonraki bağlantıda kendini günceller.

### 18.6 Geliştirici modu oturumunu kendiliğinden uzatma
LG'nin Developer Mode uygulaması bir oturum süresi sayar (LG'nin sunucusunda; bugün 1000 sa, eskiden 50 sa) ve süre
dolunca TV açılışta geliştirici modunu ve kurulu uygulamaları siler. Süre LG'nin kendi adresiyle sıfırlanır.
- **Belirteç:** TV'deki `/var/luna/preferences/devmode_enabled` dosyası (Developer Mode uygulamasının LG hesabıyla
  aldığı oturum belirteci). Kurulumda (SSH `prisoner` zaten açıkken) `cat` ile okunur; yalnız harf/rakam/`-_`,
  8–256 karakter kabul edilir. **Şifreli kasaya** yazılır (`keyring`, ad `lg_devmode`); ayar dosyasına, günlüğe,
  yanıta asla girmez. Kasa yoksa saklanmaz (uzatma kapalı kalır, panel hatırlatır).
- **Uzatma:** program açıkken saatte bir bakılır; son başarılı uzatmadan 24 sa geçtiyse (ya da hiç yapılmadıysa)
  `GET https://developer.lge.com/secure/ResetDevModeSession.dev?sessionToken=<belirteç>` çağrılır, ardından kalan süre
  için `GET https://developer.lge.com/secure/CheckDevModeSession.dev?sessionToken=<belirteç>`. Yanıt
  `{"result":"success","errorCode":"200","errorMsg":"999:58:40"}` (Check: kalan `SSS:DD:SS`; Reset'in `errorMsg`'i
  anlamsızdır). Yalnız bu iki adres, yalnız `https`, yönlendirme izlenmez, vekil (proxy) ayarına uyulur, başka hiçbir
  veri gönderilmez. Hata olursa 1 sa sonra yeniden denenir. `result` `fail` (ör. `ERR_006 Check sessionToken`) ise
  belirteç geçersiz sayılır (TV'de geliştirici modu yeniden açılmış olabilir): panel "TV'yi bir kez daha bağlayın" der.
- Not (LG'nin davranışı): TV ekranındaki sayaç yalnız TV tamamen kapatılıp açılınca güncellenir; süre denetimi açılışta
  yapılır. Uzatma TV kapalıyken de çalışır.
- Durum dosyası `<ayar_dizini>/lg_devmode.json` (belirteç YOK): `{"otomatik":true,"son_uzatma":<epoch>,
  "son_deneme":<epoch>,"kalan_sn":3599920,"bitis_tahmini":<epoch>,"hata":null|"ag"|"gecersiz","tv":"192.168.1.30"}`.
- API (yalnız yerel):
  - `GET /api/tv/lg/gelistirici` → `{"belirtec_var":true,"otomatik":true,"son_uzatma":<epoch|null>,
    "kalan_sn":n|null,"bitis_tahmini":<epoch|null>,"hata":null|"ag"|"gecersiz"|"kasa_yok","mesaj":"…",
    "hatirlatma":bool}` (`hatirlatma`: belirteç yok/geçersizken ve son kurulumdan 40 sa geçtiyse true).
  - `POST /api/tv/lg/gelistirici` `{"otomatik":bool}` → aç/kapat; `{"uzat":true}` → hemen uzat (en çok 5 dk'da bir);
    `{"belirtec":"…"}` → belirteci elle kaydet (boş = sil).
  - `POST /api/tv/lg/kur` yeni `paket:"oturum"`: kurulum yapmadan yalnız SSH ile bağlanıp belirteci okur
    (eski kurulumu olanlar için "Oturum uzatmayı aç").

## 19. Profesyonel altyazı çevirisi 2: sahne bağlamı, hitap hafızası, iki aşamalı kalite, okuma temizliği (sonraki sürüm)

Sahibin isteği: "aşırı iyi, profesyonel çevirsin" — gecikmeyi artırmadan. Bu bölüm §6.3 ve §6.5'i günceller.

### 19.1 İstem (prompt)
- **Sahne bağlamı:** son **8** altyazı satırı (konuşan adıyla, `AD: asıl => çeviri`), eskiden 6.
- **Hitap hafızası:** yayınlanan her konuşanlı satırda Türkçe çevirinin hitabı (sen/siz) basit eklerle sezilir
  (`siz`, `-sınız/-siniz`, `-ınız`, `lütfen … -ın` …) ve "konuşan → önceki farklı konuşan" çifti için tutulur
  (oyun başına, yalnız RAM, en çok 40 çift). İstemde `Address memory (speaker -> listener: form)` olarak verilir; oyun
  bilgisindeki `hitap` varsayılandır.
- **Sözlük öğrenme:** motorun `yeni_terimler` önerisi aynı biçimle **2 kez** gelirse (ya da kullanıcı öneriyi kabul
  ederse — o zaten sözlüğe girer) oturum için "öğrenilmiş ad" olur (en çok 60) ve istemde `KNOWN NAMES` altında verilir;
  böylece aynı ad hep aynı yazılır. Sözlüğe kendiliğinden girmez (öneri listesi §6.3 aynen).
- **Türkçe altyazı kuralları** (kısa): sokak ağzı doğal Türkçe argoyla (zorlama/"cringe" olmadan, ör. "bro" → "kanka"
  yalnız konuşan o ağızdaysa), küfür aynı şiddette (yumuşatma da sertleştirme de yok), deyimler karşılığıyla, kelime
  kelime çeviri yok; sayılar rakamla, para birimi `$500` → `500 dolar` (oyundaki para işareti `$`, HUD'da aynen kalır),
  mil/feet/pound çevrilmez (oyun dünyasının birimi), saat 24 sa değil olduğu gibi; satır başına ≤ 42 karakter, ≤ 2 satır,
  bölme anlam öbeğinde (`\n`), iki satır mümkünse dengeli.
- **Örnekler (few-shot):** istemin kararlı kısmında 8 kısa, elle yazılmış İngilizce → Türkçe oyun altyazısı örneği
  (sokak ağzı, küfür, şaka, görev metni, menü, düğme belirteci, para). Kararlı kısım önbelleğe alınır (Claude),
  böylece maliyet ve gecikme artmaz.

### 19.2 İki aşamalı kalite
- Yeni ayar `ceviri_kalitesi`: `"hizli"` | `"dengeli"` (varsayılan, önerilen) | `"en_iyi"`. Panel: "Çeviri kalitesi:
  Hızlı / Dengeli (önerilen) / En iyi". (`kalite` §6.5 model seçimidir ve aynen kalır.)
- İlk çeviri her zaman hızlı yoldan hemen gösterilir (§16.4 değişmez). Sonra **iyileştirme**:
  - `dengeli`: ekranda **2,5 sn**'den uzun kalan altyazı satırı ve **2,5 sn**'den uzun duran ekran öğesi (menü/görev)
    için bir kez; `en_iyi`: altyazıda **1,2 sn**, öğede 2,5 sn; `hizli`: hiç.
  - Yalnız motor desteklerse (Claude, Gemini, DeepSeek; yerel/DeepL/sahte hayır), yedekteyken değil, kaynak `motor` iken
    (kullanıcı düzeltmesi/paket iyileştirilmez) ve satır bu oturumda henüz iyileştirilmediyse.
  - Gecikme ve kota önce ilk çeviriye: kuyrukta bekleyen ya da süren bir ilk çeviri varken iyileştirme başlamaz (sonraki
    karede yeniden bakılır); dakikada en çok **8** iyileştirme isteği; iyileştirme `429` alırsa 60 sn ara verilir.
  - İyileştirme isteği "derin" kiptedir: Gemini aynı modelde daha çok düşünme (`thinkingLevel:"medium"`, 15 sn),
    Claude `claude-opus-5-5` + `effort:"medium"` (15 sn), DeepSeek aynı model. İstemde ilk taslak verilir; model taslak
    iyiyse **aynen** döndürür.
  - Sonuç yalnız **anlamlı biçimde farklıysa** (normalize metin farklı ve benzerlik < 0,98) uygulanır: satır hâlâ
    gösteriliyorsa aynı `id` ile `yazi {"devam":true}` (yerinde, titreme yok); kuyrukta bekliyorsa metni değişir; çoktan
    kalktıysa yalnız hafızaya/önbelleğe yazılır. Aynı metin asla yeniden yayınlanmaz. Kuyruk sırası ve zamanlama kuralları (§16.4)
    aynen uygulanır (okuma tabanı yeni metnin uzunluğuyla hesaplanır); iyileştirme hiçbir satırı bekletmez.
  - İyileştirilmiş çeviri hafızaya (`motor`) ve önbelleğe yazılır; aynı satır bir daha geldiğinde hemen iyi hâli çıkar.
- `GET /api/durum` `gecikme` içine `iyilestirilen` (değişen satır sayısı) ve `iyilestirme_istek` eklenir.

### 19.3 Çeviri öncesi okuma temizliği (§16.3'e ek)
- **Satır birleştirme:** altyazı kümesinin satırları tek cümle olarak birleştirilir; satır sonu kısa çizgiyle bölünmüş
  kelime (`some-` + `thing`, sonraki küçük harfle başlıyorsa) birleşir; `-` ile başlayan iki konuşmacılı satırlar
  `\n` ile ayrı kalır.
- **Okuma karışıklıkları (temkinli):** tek başına `l`/`|` → `I` (İngilizce kaynakta; `l'm`, `l'll`, `l've`, `l'd` dahil);
  harfler arasındaki `0` → `O`/`o` (komşu harfin büyüklüğüne göre; düğme belirteçleri ve sayılar dokunulmaz);
  `rn` → `m` yalnız sonuç sık kullanılan bir İngilizce kelimeyse ve asıl hâli kelime değilse (`rnore` → `more`,
  `sorne` → `some`, `turn` aynen).
- **Konuşan ön eki:** `AD: metin` (`：` dahil, iki nokta sonrası boşluksuz da), `[AD] metin`; AD en çok 3 kelime ve
  büyük harfle başlar. Konuşan istemde bağlamdır, çeviriye eklenmez (§16.4 aynen).
- **Daktilo kareleri:** metin bir önceki karenin uzantısı olarak büyüyorsa (daktilo) ve cümle sonu noktalamasıyla
  bitmiyorsa kesinleşmek için **3** aynı kare beklenir (eskiden 2); önden çeviri büyürken atılmaz. Cümle sonu
  noktalaması varsa ya da büyüme yoksa 2 kare (§16.4 aynen).

### 19.4 Değerlendirme
- `tests/ceviri_ornekleri.json`: ~40 gerçekçi GTA benzeri satır (argo, şaka, görev, menü, para, düğme) ve her biri için
  beklenen nitelikler (`yasak` sözcükler, `en_cok_karakter`, korunacak belirteçler).
- `araclar/ceviri_degerlendir.py`: istemi kurar, sahte modelle yapıyı denetler; `GEMINI_API_KEY` varsa (ve
  `--canli`) gerçek modelle çalıştırıp kuralları puanlar. CI'da canlı kısım atlanır.
