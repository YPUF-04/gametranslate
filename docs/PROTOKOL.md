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
- Program ücretsizdir. `erisim.ucretsiz_dakika_gun` (varsayılan 30) kadar günlük çeviri süresi kodsuz kullanılır; süre dolunca çeviri durmaz, panelde sakin bir "Bugünkü ücretsiz süre doldu. Erişim kodunu gir ya da yarın devam et." uyarısı çıkar ve yeni çeviri yapılmaz (hafıza/önbellekten gelenler gösterilmeye devam eder).
- Kod biçimi: `AK1-` + base32(yük + Ed25519 imzası). Yük: `{"s":"sinirsiz"|"gun","g":30,"t":"2026-11-19","n":"rastgele"}`. Program sadece **açık anahtarı** içerir, imzayı internetsiz doğrular. Özel anahtar sadece geliştiricinin bilgisayarında, depoda ASLA yoktur.
- Kod üretme: `araclar/kod_uret.py` (geliştirici için basit panel/komut). Hiçbir sunucu yok, maliyet yok.
- API (yalnız yerel): `GET /api/erisim` → `{"kalan_dakika":12,"kod":"sinirsiz"|"gun"|null,"bitis":"YYYY-MM-DD"|null,"ucretsiz_dakika":30}`; `POST /api/erisim` `{"kod":"AK1-..."}` → `{"tamam":true,"tur":"sinirsiz"|"gun"}` ya da hata `gecersiz_kod` / `suresi_dolmus_kod` (400). `GET /api/durum` ve `durum` olayına süre dolunca `"sinir": true` eklenir. Sayaç yalnız çeviri çalışırken işler, yerel gece yarısı sıfırlanır; `gun` kodu, yük tarihi + `g` gün sonuna kadar geçerlidir. Kod yazarken büyük/küçük harf, boşluk ve tire önemsizdir.
- Not: Kod açık kaynak olduğu için kontrolü kaldıran kopyalar yapılabilir; bu yasaldır (AGPL). Kod sistemi dürüst kullanıcılar içindir.

## 8. Güncelleme ve TV kurulumu (sürüm 0.2, yalnız yerel)

Ayar: `guncelleme_denetle` (bool, varsayılan `true`). Kapalıyken program kendiliğinden hiç istek yapmaz.

| Yöntem | Yol | Ne yapar |
|---|---|---|
| GET | `/api/guncelleme` | `{"var":true,"surum":"0.3.0","notlar":"...","boyut_mb":48,"ilerleme":0,"asama":"bosta"\|"indiriliyor"\|"dogrulaniyor"\|"baslatiliyor"\|"hata","mesaj":"...","mevcut":"0.2.0","denetim_acik":true,"baglanti":"https://github.com/.../releases/latest"}`. Yeni sürüm yoksa `{"var":false,"neden":"guncel"\|"kapali"\|"bekleniyor"}`. Windows dışında `{"var":false,"neden":"desteklenmiyor","mesaj":"...","baglanti":"..."}`. Gerekirse arka planda (günde en çok 1 kez) GitHub'a bakar |
| POST | `/api/guncelleme/denetle` | Kullanıcı elle bastı: ayar kapalı olsa da bir kez bakar; `GET` ile aynı gövdeyi döner |
| POST | `/api/guncelleme/kur` | İndirmeyi başlatır; `ilerleme` 0-100. `SHA256SUMS.txt` ile doğrulanamazsa kurulmaz (`asama:"hata"`). Doğrulanırsa kurucu `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /GUNCELLEME=1` ile başlar ve sunucu kapanır |
| POST | `/api/tv/lg/kur` | `{"ip":"192.168.1.30","parola":"ABC123","paket":"asil"\|"deneme"\|"acgsiz"}` → arka planda kurar. Yalnız yerel ağ IPv4. Parola/anahtar hiçbir yere yazılmaz |
| GET | `/api/tv/lg/durum` | `{"asama":"bosta"\|"anahtar"\|"baglaniyor"\|"yukleniyor"\|"kuruluyor"\|"bitti"\|"hata","mesaj":"...","ayrinti":"ham hata metni"}` |

Güncelleme adresleri yalnız `https` ve `github.com`, `api.github.com`, `objects.githubusercontent.com`, `release-assets.githubusercontent.com` olabilir (yönlendirmeler dahil her adımda denetlenir).
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
`POST /api/oyun/<kod>/bilgi-hazirla` → seçili çeviri motoruyla (LLM) oyunun adından: kısa açıklama (≤200 karakter), hitap önerisi, 20–80 terimlik sözlük (karakter/yer/eşya/çete adları; çoğu çevrilmez, gerekiyorsa Türkçe karşılığı). Sonuç öneri olarak döner: `{"aciklama","hitap","terimler":[{"asil","ceviri"}]}`; panel kullanıcıya gösterir, "Kaydet" ile sözlüğe ve oyun bilgisine yazılır. Çevrimdışı motorda kullanılamaz (açık mesaj).

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
`{"olay":"merhaba","anahtar":"<aynısı>","surum":"1","cihaz":"cuda","ekran_karti":"...","vram_gb":8.0}`
olmalıdır, değilse süreç kapatılır. İşçi kendi stdout'unu stderr'e yönlendirir (kütüphanelerin
`print`'i kanalı bozamaz); stderr `kurulum.log`'a değil, ayrı `isci.log`'a yazılır (anahtar asla yazılmaz).

İstek: `{"no":7,"komut":"seslendir",...}` → yanıt `{"no":7,"tamam":true,"sonuc":{...}}` ya da
`{"no":7,"tamam":false,"hata":"dublaj_uretim_hata","ayrinti":"..."}`. Ara olaylar:
`{"olay":"ilerleme","no":7,"yuzde":40,"mesaj":"..."}`, `{"olay":"parca",...}` (canlı ses parçası),
`{"olay":"gunluk","seviye":"bilgi","mesaj":"..."}`. Ses verisi: `{"pcm":"<base64 float32 LE mono>","sr":24000}`.

| Komut | Girdi | Sonuç |
|---|---|---|
| `merhaba` | — | işçi/cihaz bilgisi |
| `modeller` | `{"liste":["tts","stt","ayirma"],"stt":"large-v3-turbo"}` | indirir (ilerleme olaylı) |
| `yukle` | `{"tts":"chatterbox","stt":"large-v3-turbo"\|"small","ayirma":true,"hafif":false}` | modelleri belleğe alır |
| `birak` | — | modelleri boşaltır (VRAM serbest) |
| `ayir` | `{"pcm","sr"}` ya da `{"giris":yol,"ses_cikis":yol,"arka_cikis":yol}` | konuşma sesi / arka plan |
| `yaziya` | `{"pcm","sr"}` ya da `{"giris":yol,"cikis":yol}` | metin, dil, kelimeler `[{"k":"Hey","b":1.2,"s":1.5}]` |
| `izler` | `{"giris":yol,"araliklar":[[b,s],...]}` | konuşmacı izleri (256 boyutlu, birim vektör) |
| `seslendir` | `{"metin","ref_pcm","ref_sr","duygu":{"canlilik":0.5,"cfg":0.5},"motor":"chatterbox"}` ya da `ref_yol`/`cikis` | Türkçe ses |
| `karistir` | `{"arka":yol,"satirlar":[{"yol","bas"}],"cikis":yol}` | dublaj ses izi |
| `video_cikar` / `video_birlestir` | ffmpeg ile ses çıkarma / video+ses birleştirme | dosya yolları |
| `canli_baslat` | `{"pid":1234\|null,"ayirma":true,"tamamen_turkce":false,"giris":""}` | `parca` olayları (`{"pcm","temiz","sr","sure_sn","kaynak":"surec"\|"giris"\|"sistem"}`), `olcum` (`ayirma_ms`) başlar |
| `seslendir_cal` | `seslendir` + `{"hedef_sn","hiz_siniri","seviye","kis","pid"}` | akışlı seslendirip çalar → `{"ilk_ses_ms","toplam_ms","hiz","sure_sn"}` |
| `girisler` | — | ses girişlerinin adları (açılmaz) |
| `izler` / `referans_kaydet` / `hizlandir` | video aşamaları (14.4) | dosya yolları |
| `canli_durdur` | — | yakalama durur, oyun sesi eski hâline döner |
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
- **Metin önce altyazıdan:** ekranda altyazı belirdiği anda (cümle bitmeden) çeviri + seslendirme başlar;
  hazır olunca TV'ye hemen gönderilir (`cikis:"tv"` ya da İngilizce çıkarılıyorsa). Konuşma parçası
  sonra gelince aynı satır tekrar çalınmaz, yalnız karakterin sesi örneklenir. Altyazısı olmayan
  konuşmada Whisper yedektir.
- TV uygulaması gelen sesleri **sıraya** koyar (öncekini kesmez), 6 sn'den eski kalanı atar; Web Audio
  ile çalar (HDMI `<video>` medya hattına ikinci bir medya kaynağı açmaz), yoksa `<audio>` sırası.
  Gerçek LG TV'de HDMI üstünde ses çalma DOĞRULANMADI; çalmazsa yedek: `cikis:"bilgisayar"` +
  Bluetooth hoparlör / LG Sound Share.

- **Yalnız oyunun sesi**: Windows 10 2004+ üzerinde, seçili oyun penceresinin süreci için WASAPI
  *process loopback* (`AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK`, `PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE`)
  kullanılır; olmazsa bugünkü tüm-sistem loopback'e düşülür (`parca.kaynak:"surec"|"sistem"`). Mikrofon ASLA.
- Her parça işçide ayırıcıdan geçer (`ayirma:true`): **temiz konuşma sesi** hem yazıya çevirmede hem
  ses örneği (klon) olarak kullanılır. Konuşmacı örnekleri YALNIZ işçinin ve ana programın belleğinde
  durur, diske yazılmaz.
- Duygu: orijinal parçanın ses yüksekliği/enerjisi ve perde değişkenliğinden `canlilik` (Chatterbox
  `exaggeration`, 0.25–1.2) ve `cfg` (0.3–0.7) hesaplanır: bağırma bağırma, fısıltı fısıltı kalır (motorun izin verdiği ölçüde).
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
  `small`, Chatterbox dil modeli yarım hassas. Oyun PS5'te çalıştığından dizüstünün ekran kartı boştur:
  varsayılan tam kalite (Whisper `large-v3-turbo` int8_float16, fp16 hesap). 180 sn boşta kalınca ses motoru
  ekran kartından indirilir, ilk istekte geri yüklenir.
- Akışlı seslendirme (`seslendir_cal`): metin cümleciklere bölünür, ilk cümlecik hazır olur olmaz çalar
  (bilgisayar çıkışı). Ölçümler `GET /api/dublaj` → `gecikme`: `{"son":{"stt_ms","ceviri_ms","ses_ms",
  "ilk_ses_ms","bekleme_ms","erken"},"ortalama_bekleme_ms"}` (bekleme = İngilizce parça bitişinden Türkçe sesin başlamasına).

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
- Gerçek kişilerin seslerini taklit eden hazır ses paketi yoktur; yalnız videodaki/oyundaki karakterin kendi sesi örneklenir.
- **Yasal not (panelde de yazar):** Dublaj kişisel kullanım içindir. Dublajlı videoyu yayınlamak
  (YouTube vb.) oyunun ve seslendirme sanatçılarının haklarına tabidir; izin almak kullanıcının sorumluluğundadır.
