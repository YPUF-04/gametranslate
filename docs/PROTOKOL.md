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
  "modeller": {"claude":"claude-opus-5-5","gemini":"gemini-2.5-flash","deepseek":"deepseek-chat"},
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
- API (yalnız yerel): `GET /api/erisim` → `{"kalan_dakika":12,"kod":"sinirsiz"|null}`; `POST /api/erisim` `{"kod":"AK1-..."}` → `{"tamam":true,"tur":"sinirsiz"}`.
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
