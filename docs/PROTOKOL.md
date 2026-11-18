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
eskisini hemen değiştirir. Okuma süresi hesabı: `max(1500, min(9000, 800 + karakter*55))`.

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
