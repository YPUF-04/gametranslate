/* SPDX-License-Identifier: AGPL-3.0-only
 *
 * ayk-uzaktan: AltYazıKöprüsü'nün pencere açmayan PS5 Remote Play yardımcısı (PROTOKOL §15).
 *
 * chiaki-ng'nin libchiaki kütüphanesini (AGPL-3.0, https://github.com/streetpea/chiaki-ng) ve
 * FFmpeg'in H.264/HEVC çözücüsünü (LGPL) kullanır. Bu dosya AltYazıKöprüsü katkıcılarınca yazılmıştır.
 *
 * Değişmez kural (§15.2): bu program PS5'e HİÇBİR girdi (kol, klavye, dokunmatik, mikrofon) göndermez.
 * chiaki_session_set_controller_state hiç çağrılmaz; libchiaki'nin kendi geri bildirim paketleri boştaki
 * kol durumunu taşır. Pencere ve ses çıkışı yoktur; görüntü/ses yalnız standart çıkıştan programa gider.
 */
#include <chiaki/base64.h>
#include <chiaki/common.h>
#include <chiaki/discovery.h>
#include <chiaki/log.h>
#include <chiaki/opusdecoder.h>
#include <chiaki/regist.h>
#include <chiaki/session.h>
#include <chiaki/thread.h>

#include <libavcodec/avcodec.h>
#include <libavutil/imgutils.h>
#include <libavutil/frame.h>
#include <libswscale/swscale.h>

#include <json-c/json.h>

#include <ctype.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
static void uyu_ms(unsigned ms) { Sleep(ms); }
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
static void uyu_ms(unsigned ms) { usleep(ms * 1000u); }
#endif

#define AYK_SURUM "1"
#define AYK_CHIAKI "1.10.1"
#define SES_HZ 16000

/* ------------------------------------------------------------------ çıkış */

static ChiakiMutex cikis_kilidi;
static int ikili_kip = 0; /* akis: stdout ikili çerçevelerdir */

static void cerceve_yaz(char tur, const void *veri1, size_t n1, const void *veri2, size_t n2)
{
	uint8_t bas[8] = { 'A', 'Y', (uint8_t)tur, 0, 0, 0, 0, 0 };
	uint32_t n = (uint32_t)(n1 + n2);
	bas[4] = (uint8_t)(n & 0xff);
	bas[5] = (uint8_t)((n >> 8) & 0xff);
	bas[6] = (uint8_t)((n >> 16) & 0xff);
	bas[7] = (uint8_t)((n >> 24) & 0xff);
	chiaki_mutex_lock(&cikis_kilidi);
	fwrite(bas, 1, sizeof(bas), stdout);
	if(n1)
		fwrite(veri1, 1, n1, stdout);
	if(n2)
		fwrite(veri2, 1, n2, stdout);
	fflush(stdout);
	chiaki_mutex_unlock(&cikis_kilidi);
}

/* JSON olayını yazar ve nesneyi bırakır. Satır kipinde bir satır, ikili kipte 'J' çerçevesi. */
static void olay_yaz(json_object *o)
{
	const char *metin = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
	if(ikili_kip)
		cerceve_yaz('J', metin, strlen(metin), NULL, 0);
	else
	{
		chiaki_mutex_lock(&cikis_kilidi);
		fputs(metin, stdout);
		fputc('\n', stdout);
		fflush(stdout);
		chiaki_mutex_unlock(&cikis_kilidi);
	}
	json_object_put(o);
}

static json_object *olay(const char *ad)
{
	json_object *o = json_object_new_object();
	json_object_object_add(o, "olay", json_object_new_string(ad));
	return o;
}

static void olay_str(json_object *o, const char *k, const char *v)
{
	json_object_object_add(o, k, v ? json_object_new_string(v) : NULL);
}

/* ------------------------------------------------------------------ günlük */

#define HATA_SATIRI 8
static char hata_satirlari[HATA_SATIRI][256];
static int hata_sayisi = 0;
static uint32_t bildirilen_neden = 0;

static void gunluk_cb(ChiakiLogLevel seviye, const char *msg, void *user)
{
	(void)user;
	fprintf(stderr, "[%c] %s\n", chiaki_log_level_char(seviye), msg);
	fflush(stderr);
	if(seviye == CHIAKI_LOG_ERROR)
	{
		const char *p = strstr(msg, "Application Reason: ");
		if(p)
			bildirilen_neden = (uint32_t)strtoul(p + strlen("Application Reason: "), NULL, 0);
		if(hata_sayisi < HATA_SATIRI)
		{
			snprintf(hata_satirlari[hata_sayisi], sizeof(hata_satirlari[0]), "%s", msg);
			hata_sayisi++;
		}
	}
}

static ChiakiLog gunluk;

/* ------------------------------------------------------------------ yardımcılar */

static int hex_coz(const char *hex, uint8_t *cikti, size_t boy)
{
	if(!hex || strlen(hex) != boy * 2)
		return -1;
	for(size_t i = 0; i < boy; i++)
	{
		unsigned v;
		char iki[3] = { hex[2 * i], hex[2 * i + 1], 0 };
		if(!isxdigit((unsigned char)iki[0]) || !isxdigit((unsigned char)iki[1]))
			return -1;
		sscanf(iki, "%x", &v);
		cikti[i] = (uint8_t)v;
	}
	return 0;
}

static void hex_yaz(const uint8_t *v, size_t boy, char *cikti)
{
	static const char h[] = "0123456789abcdef";
	for(size_t i = 0; i < boy; i++)
	{
		cikti[2 * i] = h[v[i] >> 4];
		cikti[2 * i + 1] = h[v[i] & 0xf];
	}
	cikti[2 * boy] = 0;
}

/* Uyandırma kimliği (§15.3): kayıt anahtarının ASCII metni, 16 tabanında sayı. */
static uint64_t uyandirma_kimligi(const uint8_t anahtar[CHIAKI_SESSION_AUTH_SIZE])
{
	char metin[CHIAKI_SESSION_AUTH_SIZE + 1];
	memcpy(metin, anahtar, CHIAKI_SESSION_AUTH_SIZE);
	metin[CHIAKI_SESSION_AUTH_SIZE] = 0;
	return (uint64_t)strtoull(metin, NULL, 16);
}

static int hesap_coz(const char *b64, uint8_t cikti[CHIAKI_PSN_ACCOUNT_ID_SIZE])
{
	uint8_t tampon[32];
	size_t boy = sizeof(tampon);
	if(!b64 || chiaki_base64_decode(b64, strlen(b64), tampon, &boy) != CHIAKI_ERR_SUCCESS || boy != CHIAKI_PSN_ACCOUNT_ID_SIZE)
		return -1;
	memcpy(cikti, tampon, CHIAKI_PSN_ACCOUNT_ID_SIZE);
	return 0;
}

static json_object *girdi_oku(void)
{
	static char satir[8192];
	if(!fgets(satir, sizeof(satir), stdin))
		return NULL;
	json_object *o = json_tokener_parse(satir);
	if(o && !json_object_is_type(o, json_type_object))
	{
		json_object_put(o);
		return NULL;
	}
	return o;
}

static const char *alan_str(json_object *o, const char *k)
{
	json_object *v;
	if(!o || !json_object_object_get_ex(o, k, &v) || !json_object_is_type(v, json_type_string))
		return NULL;
	return json_object_get_string(v);
}

static int64_t alan_int(json_object *o, const char *k, int64_t varsayilan)
{
	json_object *v;
	if(!o || !json_object_object_get_ex(o, k, &v))
		return varsayilan;
	return json_object_get_int64(v);
}

static int alan_bool(json_object *o, const char *k, int varsayilan)
{
	json_object *v;
	if(!o || !json_object_object_get_ex(o, k, &v))
		return varsayilan;
	return json_object_get_boolean(v) ? 1 : 0;
}

static int hata_ver(const char *olay_adi, const char *neden)
{
	json_object *o = olay(olay_adi);
	json_object_object_add(o, "tamam", json_object_new_boolean(0));
	olay_str(o, "ayrinti", neden);
	olay_yaz(o);
	return 2;
}

/* ------------------------------------------------------------------ bul */

typedef struct { int bulunan; } BulDurum;

static void bul_cb(ChiakiDiscoveryHost *host, void *user)
{
	BulDurum *d = user;
	if(!host || !host->host_addr || !chiaki_discovery_host_is_ps5(host))
		return;
	d->bulunan++;
	json_object *o = olay("konsol");
	olay_str(o, "host", host->host_addr);
	olay_str(o, "ad", host->host_name ? host->host_name : "PS5");
	olay_str(o, "durum", host->state == CHIAKI_DISCOVERY_HOST_STATE_READY ? "acik"
		: host->state == CHIAKI_DISCOVERY_HOST_STATE_STANDBY ? "uyku" : "bilinmiyor");
	olay_str(o, "kimlik", host->host_id);
	olay_str(o, "oyun", host->running_app_name);
	olay_yaz(o);
}

static int komut_bul(json_object *g)
{
	ChiakiDiscovery kesif;
	if(chiaki_discovery_init(&kesif, &gunluk, AF_INET) != CHIAKI_ERR_SUCCESS)
		return hata_ver("bitti", "kesif_baslamadi");
	BulDurum d = { 0 };
	ChiakiDiscoveryThread is;
	if(chiaki_discovery_thread_start(&is, &kesif, bul_cb, &d) != CHIAKI_ERR_SUCCESS)
	{
		chiaki_discovery_fini(&kesif);
		return hata_ver("bitti", "kesif_baslamadi");
	}
	const char *hedefler[16];
	int hedef_sayisi = 0;
	json_object *dizi;
	if(g && json_object_object_get_ex(g, "hedefler", &dizi) && json_object_is_type(dizi, json_type_array))
	{
		size_t n = json_object_array_length(dizi);
		for(size_t i = 0; i < n && hedef_sayisi < 16; i++)
		{
			json_object *e = json_object_array_get_idx(dizi, i);
			if(json_object_is_type(e, json_type_string))
				hedefler[hedef_sayisi++] = json_object_get_string(e);
		}
	}
	if(!hedef_sayisi)
		hedefler[hedef_sayisi++] = "255.255.255.255";
	int64_t sure = alan_int(g, "sure_ms", 3000);
	if(sure < 200)
		sure = 200;
	if(sure > 20000)
		sure = 20000;

	ChiakiDiscoveryPacket paket;
	memset(&paket, 0, sizeof(paket));
	paket.cmd = CHIAKI_DISCOVERY_CMD_SRCH;
	paket.protocol_version = CHIAKI_DISCOVERY_PROTOCOL_VERSION_PS5;
	for(int64_t gecen = 0; gecen < sure; gecen += 500)
	{
		for(int i = 0; i < hedef_sayisi; i++)
		{
			struct sockaddr_in adres;
			memset(&adres, 0, sizeof(adres));
			adres.sin_family = AF_INET;
			adres.sin_port = htons(CHIAKI_DISCOVERY_PORT_PS5);
			if(inet_pton(AF_INET, hedefler[i], &adres.sin_addr) != 1)
				continue;
			chiaki_discovery_send(&kesif, &paket, (struct sockaddr *)&adres, sizeof(adres));
		}
		uyu_ms(500);
	}
	chiaki_discovery_thread_stop(&is);
	chiaki_discovery_fini(&kesif);
	json_object *o = olay("bitti");
	json_object_object_add(o, "bulunan", json_object_new_int(d.bulunan));
	olay_yaz(o);
	return 0;
}

/* ------------------------------------------------------------------ uyandır */

static int komut_uyandir(json_object *g)
{
	const char *host = alan_str(g, "host");
	uint8_t anahtar[CHIAKI_SESSION_AUTH_SIZE];
	if(!host || hex_coz(alan_str(g, "kayit_anahtari"), anahtar, sizeof(anahtar)))
		return hata_ver("uyandir", "girdi_gecersiz");
	ChiakiErrorCode err = chiaki_discovery_wakeup(&gunluk, NULL, host, uyandirma_kimligi(anahtar), true);
	json_object *o = olay("uyandir");
	json_object_object_add(o, "tamam", json_object_new_boolean(err == CHIAKI_ERR_SUCCESS));
	if(err != CHIAKI_ERR_SUCCESS)
		olay_str(o, "ayrinti", chiaki_error_string(err));
	olay_yaz(o);
	return err == CHIAKI_ERR_SUCCESS ? 0 : 2;
}

/* ------------------------------------------------------------------ kaydet */

typedef struct
{
	ChiakiBoolPredCond bitti;
	ChiakiRegistEventType tur;
	ChiakiRegisteredHost konsol;
} KayitDurum;

static void kayit_cb(ChiakiRegistEvent *e, void *user)
{
	KayitDurum *d = user;
	chiaki_mutex_lock(&d->bitti.mutex);
	d->tur = e->type;
	if(e->type == CHIAKI_REGIST_EVENT_TYPE_FINISHED_SUCCESS && e->registered_host)
		d->konsol = *e->registered_host;
	d->bitti.pred = true;
	chiaki_cond_signal(&d->bitti.cond);
	chiaki_mutex_unlock(&d->bitti.mutex);
}

static int komut_kaydet(json_object *g)
{
	const char *host = alan_str(g, "host");
	int64_t pin = alan_int(g, "pin", -1);
	ChiakiRegistInfo bilgi;
	memset(&bilgi, 0, sizeof(bilgi));
	if(!host || pin < 0 || pin > 99999999 || hesap_coz(alan_str(g, "hesap"), bilgi.psn_account_id))
		return hata_ver("kayit", "girdi_gecersiz");
	bilgi.target = CHIAKI_TARGET_PS5_1;
	bilgi.host = host;
	bilgi.broadcast = alan_bool(g, "yayin", 0);
	bilgi.psn_online_id = NULL;
	bilgi.pin = (uint32_t)pin;
	bilgi.console_pin = 0;
	bilgi.holepunch_info = NULL;
	bilgi.rudp = NULL;

	KayitDurum d;
	memset(&d, 0, sizeof(d));
	chiaki_bool_pred_cond_init(&d.bitti);
	ChiakiRegist kayit;
	if(chiaki_regist_start(&kayit, &gunluk, &bilgi, kayit_cb, &d) != CHIAKI_ERR_SUCCESS)
		return hata_ver("kayit", "kayit_baslamadi");
	chiaki_mutex_lock(&d.bitti.mutex);
	ChiakiErrorCode bekle = CHIAKI_ERR_SUCCESS;
	while(!d.bitti.pred && bekle != CHIAKI_ERR_TIMEOUT)
		bekle = chiaki_cond_timedwait(&d.bitti.cond, &d.bitti.mutex, 40000);
	int tamam = d.bitti.pred && d.tur == CHIAKI_REGIST_EVENT_TYPE_FINISHED_SUCCESS;
	int zaman_asimi = !d.bitti.pred;
	chiaki_mutex_unlock(&d.bitti.mutex);
	if(zaman_asimi)
		chiaki_regist_stop(&kayit);
	chiaki_regist_fini(&kayit);

	json_object *o = olay("kayit");
	json_object_object_add(o, "tamam", json_object_new_boolean(tamam));
	if(tamam)
	{
		char hex[65];
		char ad[sizeof(d.konsol.server_nickname) + 1];
		memcpy(ad, d.konsol.server_nickname, sizeof(d.konsol.server_nickname));
		ad[sizeof(d.konsol.server_nickname)] = 0;
		olay_str(o, "ad", ad);
		hex_yaz((const uint8_t *)d.konsol.rp_regist_key, sizeof(d.konsol.rp_regist_key), hex);
		olay_str(o, "kayit_anahtari", hex);
		hex_yaz(d.konsol.rp_key, sizeof(d.konsol.rp_key), hex);
		olay_str(o, "sabah", hex);
		hex_yaz(d.konsol.server_mac, sizeof(d.konsol.server_mac), hex);
		olay_str(o, "mac", hex);
		json_object_object_add(o, "hedef", json_object_new_int((int)d.konsol.target));
	}
	else
	{
		json_object_object_add(o, "neden", json_object_new_int64(bildirilen_neden));
		json_object_object_add(o, "zaman_asimi", json_object_new_boolean(zaman_asimi));
		json_object *satirlar = json_object_new_array();
		for(int i = 0; i < hata_sayisi; i++)
			json_object_array_add(satirlar, json_object_new_string(hata_satirlari[i]));
		json_object_object_add(o, "satirlar", satirlar);
	}
	olay_yaz(o);
	chiaki_bool_pred_cond_fini(&d.bitti);
	return tamam ? 0 : 2;
}

/* ------------------------------------------------------------------ akış */

typedef struct
{
	ChiakiSession oturum;
	ChiakiOpusDecoder opus;
	AVCodecContext *cozucu;
	AVPacket *paket;
	AVFrame *gecici;
	AVFrame *son;            /* son çözülmüş kare (son_kilit altında) */
	int son_var;
	ChiakiMutex son_kilit;
	struct SwsContext *sws;
	uint8_t *bgra;
	size_t bgra_boy;
	unsigned ses_kanal, ses_hz;
	int16_t *ses_tampon;
	size_t ses_tampon_boy;
	double ses_kalan;        /* yeniden örneklemede kesir */
	int ses_acik;
	int bagli;
	int bitti;
	int hatali_kare;
	ChiakiBoolPredCond kapandi;
} Akis;

/* PS5'in oturum isteğini reddettiği nedenler (kayıt/hesap geçersiz). 0x80108b26: anahtar yanlış biçimde saklanmış. */
static int kayit_reddi_mi(uint32_t neden)
{
	return neden == CHIAKI_RP_APPLICATION_REASON_REGIST_FAILED || neden == CHIAKI_RP_APPLICATION_REASON_INVALID_PSN_ID
		|| neden == 0x80108b26u;
}

static const char *cikis_nedeni(ChiakiQuitReason r)
{
	switch(r)
	{
		case CHIAKI_QUIT_REASON_STOPPED: return "durdu";
		case CHIAKI_QUIT_REASON_SESSION_REQUEST_RP_IN_USE: return "kullanimda";
		case CHIAKI_QUIT_REASON_SESSION_REQUEST_UNKNOWN:
			return kayit_reddi_mi(bildirilen_neden) ? "reddedildi" : "diger";
		case CHIAKI_QUIT_REASON_SESSION_REQUEST_CONNECTION_REFUSED: return "erisilemedi";
		case CHIAKI_QUIT_REASON_CTRL_CONNECTION_REFUSED:
		case CHIAKI_QUIT_REASON_PSN_REGIST_FAILED: return "reddedildi";
		case CHIAKI_QUIT_REASON_CTRL_CONNECT_FAILED:
		case CHIAKI_QUIT_REASON_STREAM_CONNECTION_REMOTE_DISCONNECTED:
		case CHIAKI_QUIT_REASON_STREAM_CONNECTION_UNKNOWN: return "ag";
		case CHIAKI_QUIT_REASON_STREAM_CONNECTION_REMOTE_SHUTDOWN: return "kapandi";
		case CHIAKI_QUIT_REASON_SESSION_REQUEST_RP_VERSION_MISMATCH: return "surum";
		default: return "diger";
	}
}

static void akis_olay_cb(ChiakiEvent *e, void *user)
{
	Akis *a = user;
	switch(e->type)
	{
		case CHIAKI_EVENT_CONNECTED:
			a->bagli = 1;
			olay_yaz(olay("bagli"));
			break;
		case CHIAKI_EVENT_NICKNAME_RECEIVED:
		{
			json_object *o = olay("ad");
			char ad[sizeof(e->server_nickname) + 1];
			memcpy(ad, e->server_nickname, sizeof(e->server_nickname));
			ad[sizeof(e->server_nickname)] = 0;
			olay_str(o, "ad", ad);
			olay_yaz(o);
			break;
		}
		case CHIAKI_EVENT_LOGIN_PIN_REQUEST:
		{
			json_object *o = olay("giris_pin_gerekli");
			json_object_object_add(o, "yanlis", json_object_new_boolean(e->login_pin_request.pin_incorrect));
			olay_yaz(o);
			break;
		}
		case CHIAKI_EVENT_QUIT:
		{
			json_object *o = olay("bitti");
			olay_str(o, "neden", cikis_nedeni(e->quit.reason));
			olay_str(o, "ayrinti", e->quit.reason_str ? e->quit.reason_str : chiaki_quit_reason_string(e->quit.reason));
			json_object_object_add(o, "neden_kodu", json_object_new_int64(bildirilen_neden));
			olay_yaz(o);
			chiaki_mutex_lock(&a->kapandi.mutex);
			a->bitti = 1;
			a->kapandi.pred = true;
			chiaki_cond_signal(&a->kapandi.cond);
			chiaki_mutex_unlock(&a->kapandi.mutex);
			break;
		}
		default:
			/* titreşim, tetik efekti, LED, klavye vb. yok sayılır: kol yok, girdi yok */
			break;
	}
}

static bool akis_goruntu_cb(uint8_t *buf, size_t buf_size, int32_t frames_lost, bool frame_recovered, void *user)
{
	Akis *a = user;
	(void)frames_lost;
	(void)frame_recovered;
	a->paket->data = buf;
	a->paket->size = (int)buf_size;
	int r = avcodec_send_packet(a->cozucu, a->paket);
	if(r < 0 && r != AVERROR(EAGAIN))
	{
		if(++a->hatali_kare >= 3)
		{
			chiaki_session_request_idr(&a->oturum);
			a->hatali_kare = 0;
		}
		return false;
	}
	while(avcodec_receive_frame(a->cozucu, a->gecici) == 0)
	{
		chiaki_mutex_lock(&a->son_kilit);
		av_frame_unref(a->son);
		av_frame_move_ref(a->son, a->gecici);
		a->son_var = 1;
		chiaki_mutex_unlock(&a->son_kilit);
		a->hatali_kare = 0;
	}
	return true;
}

static void akis_ses_ayar_cb(uint32_t kanal, uint32_t hz, void *user)
{
	Akis *a = user;
	a->ses_kanal = kanal ? kanal : 2;
	a->ses_hz = hz ? hz : 48000;
	a->ses_kalan = 0;
}

/* 48 kHz stereo -> 16 kHz mono (kanal ortalaması + kutu süzgeçli seyreltme). */
static void akis_ses_kare_cb(int16_t *buf, size_t ornek, void *user)
{
	Akis *a = user;
	if(!a->ses_acik || !ornek)
		return;
	unsigned kanal = a->ses_kanal ? a->ses_kanal : 2;
	double oran = (double)(a->ses_hz ? a->ses_hz : 48000) / SES_HZ;
	size_t en_cok = (size_t)(ornek / oran) + 2;
	if(a->ses_tampon_boy < en_cok)
	{
		int16_t *yeni = realloc(a->ses_tampon, en_cok * sizeof(int16_t));
		if(!yeni)
			return;
		a->ses_tampon = yeni;
		a->ses_tampon_boy = en_cok;
	}
	size_t n = 0;
	double konum = a->ses_kalan;
	while(konum + oran <= (double)ornek && n < en_cok)
	{
		size_t bas = (size_t)konum, son = (size_t)(konum + oran);
		if(son <= bas)
			son = bas + 1;
		int64_t toplam = 0;
		size_t sayi = 0;
		for(size_t i = bas; i < son && i < ornek; i++)
			for(unsigned k = 0; k < kanal; k++, sayi++)
				toplam += buf[i * kanal + k];
		a->ses_tampon[n++] = (int16_t)(sayi ? toplam / (int64_t)sayi : 0);
		konum += oran;
	}
	a->ses_kalan = konum - (double)ornek;
	if(a->ses_kalan < 0)
		a->ses_kalan = 0;
	if(n)
		cerceve_yaz('S', a->ses_tampon, n * sizeof(int16_t), NULL, 0);
}

static void kare_gonder(Akis *a, int azami_genislik)
{
	uint8_t boyut[4] = { 0, 0, 0, 0 };
	chiaki_mutex_lock(&a->son_kilit);
	if(!a->son_var || a->son->width <= 0 || a->son->height <= 0)
	{
		chiaki_mutex_unlock(&a->son_kilit);
		cerceve_yaz('V', boyut, 4, NULL, 0);
		return;
	}
	int g = a->son->width, y = a->son->height;
	if(azami_genislik > 0 && g > azami_genislik)
	{
		y = (int)((int64_t)y * azami_genislik / g);
		g = azami_genislik;
	}
	if(g > 65535 || y > 65535 || y < 1)
	{
		chiaki_mutex_unlock(&a->son_kilit);
		cerceve_yaz('V', boyut, 4, NULL, 0);
		return;
	}
	size_t gerekli = (size_t)g * (size_t)y * 4u;
	if(a->bgra_boy < gerekli)
	{
		uint8_t *yeni = realloc(a->bgra, gerekli);
		if(!yeni)
		{
			chiaki_mutex_unlock(&a->son_kilit);
			cerceve_yaz('V', boyut, 4, NULL, 0);
			return;
		}
		a->bgra = yeni;
		a->bgra_boy = gerekli;
	}
	a->sws = sws_getCachedContext(a->sws, a->son->width, a->son->height, (enum AVPixelFormat)a->son->format,
		g, y, AV_PIX_FMT_BGRA, SWS_BILINEAR, NULL, NULL, NULL);
	int ok = 0;
	if(a->sws)
	{
		uint8_t *hedef[4] = { a->bgra, NULL, NULL, NULL };
		int adim[4] = { g * 4, 0, 0, 0 };
		ok = sws_scale(a->sws, (const uint8_t *const *)a->son->data, a->son->linesize, 0, a->son->height, hedef, adim) > 0;
	}
	chiaki_mutex_unlock(&a->son_kilit);
	if(!ok)
	{
		cerceve_yaz('V', boyut, 4, NULL, 0);
		return;
	}
	boyut[0] = (uint8_t)(g & 0xff);
	boyut[1] = (uint8_t)(g >> 8);
	boyut[2] = (uint8_t)(y & 0xff);
	boyut[3] = (uint8_t)(y >> 8);
	cerceve_yaz('V', boyut, 4, a->bgra, gerekli);
}

static int komut_akis(json_object *g)
{
	static Akis a; /* büyük yapı: yığında değil */
	memset(&a, 0, sizeof(a));
	ChiakiConnectInfo bilgi;
	memset(&bilgi, 0, sizeof(bilgi));
	const char *host = alan_str(g, "host");
	if(!host || hex_coz(alan_str(g, "kayit_anahtari"), (uint8_t *)bilgi.regist_key, sizeof(bilgi.regist_key))
		|| hex_coz(alan_str(g, "sabah"), bilgi.morning, sizeof(bilgi.morning))
		|| hesap_coz(alan_str(g, "hesap"), bilgi.psn_account_id))
		return hata_ver("bitti", "girdi_gecersiz");
	int cozunurluk = (int)alan_int(g, "cozunurluk", 720);
	int fps = (int)alan_int(g, "fps", 30);
	const char *kodek = alan_str(g, "kodek");
	int hevc = kodek && !strcmp(kodek, "hevc");
	a.ses_acik = alan_bool(g, "ses", 1);

	bilgi.ps5 = true;
	bilgi.host = host;
	chiaki_connect_video_profile_preset(&bilgi.video_profile,
		cozunurluk >= 1080 ? CHIAKI_VIDEO_RESOLUTION_PRESET_1080p
		: cozunurluk <= 540 ? CHIAKI_VIDEO_RESOLUTION_PRESET_540p : CHIAKI_VIDEO_RESOLUTION_PRESET_720p,
		fps >= 60 ? CHIAKI_VIDEO_FPS_PRESET_60 : CHIAKI_VIDEO_FPS_PRESET_30);
	bilgi.video_profile.codec = hevc ? CHIAKI_CODEC_H265 : CHIAKI_CODEC_H264;
	bilgi.video_profile_auto_downgrade = true;
	/* §15.2: kol ve klavye özellikleri kapalı. Hiçbir girdi gönderilmez. */
	bilgi.enable_keyboard = false;
	bilgi.enable_dualsense = false;
	bilgi.audio_video_disabled = a.ses_acik ? CHIAKI_NONE_DISABLED : CHIAKI_AUDIO_DISABLED;
	bilgi.auto_regist = false;
	bilgi.holepunch_session = NULL;
	bilgi.rudp_sock = NULL;
	bilgi.packet_loss_max = 0.05;
	bilgi.enable_idr_on_fec_failure = true;

	const AVCodec *c = avcodec_find_decoder(hevc ? AV_CODEC_ID_HEVC : AV_CODEC_ID_H264);
	if(!c)
		return hata_ver("bitti", "cozucu_yok");
	a.cozucu = avcodec_alloc_context3(c);
	a.cozucu->thread_count = 2;
	a.cozucu->flags |= AV_CODEC_FLAG_LOW_DELAY;
	if(avcodec_open2(a.cozucu, c, NULL) < 0)
		return hata_ver("bitti", "cozucu_acilmadi");
	a.paket = av_packet_alloc();
	a.gecici = av_frame_alloc();
	a.son = av_frame_alloc();
	chiaki_mutex_init(&a.son_kilit, false);
	chiaki_bool_pred_cond_init(&a.kapandi);

	bildirilen_neden = 0;
	if(chiaki_session_init(&a.oturum, &bilgi, &gunluk) != CHIAKI_ERR_SUCCESS)
		return hata_ver("bitti", "oturum_hazirlanamadi");
	chiaki_opus_decoder_init(&a.opus, &gunluk);
	chiaki_opus_decoder_set_cb(&a.opus, akis_ses_ayar_cb, akis_ses_kare_cb, &a);
	ChiakiAudioSink ses;
	chiaki_opus_decoder_get_sink(&a.opus, &ses);
	chiaki_session_set_audio_sink(&a.oturum, &ses);
	chiaki_session_set_event_cb(&a.oturum, akis_olay_cb, &a);
	chiaki_session_set_video_sample_cb(&a.oturum, akis_goruntu_cb, &a);
	/* chiaki_session_set_controller_state ASLA çağrılmaz (§15.2). */
	if(chiaki_session_start(&a.oturum) != CHIAKI_ERR_SUCCESS)
	{
		chiaki_session_fini(&a.oturum);
		return hata_ver("bitti", "oturum_baslamadi");
	}
	olay_yaz(olay("baslatildi"));

	char satir[256];
	while(fgets(satir, sizeof(satir), stdin))
	{
		if(a.bitti)
			break;
		if(!strncmp(satir, "kare", 4))
			kare_gonder(&a, atoi(satir + 4));
		else if(!strncmp(satir, "giris_pin ", 10))
		{
			char *p = satir + 10;
			size_t n = 0;
			while(isdigit((unsigned char)p[n]))
				n++;
			if(n == 4)
				chiaki_session_set_login_pin(&a.oturum, (const uint8_t *)p, n);
		}
		else if(!strncmp(satir, "dur", 3))
			break;
	}
	/* stdin kapandı ya da "dur": oturum kapanır */
	chiaki_session_stop(&a.oturum);
	chiaki_session_join(&a.oturum);
	chiaki_session_fini(&a.oturum);
	chiaki_opus_decoder_fini(&a.opus);
	if(a.sws)
		sws_freeContext(a.sws);
	av_frame_free(&a.son);
	av_frame_free(&a.gecici);
	av_packet_free(&a.paket);
	avcodec_free_context(&a.cozucu);
	free(a.bgra);
	free(a.ses_tampon);
	return 0;
}

/* ------------------------------------------------------------------ öz denetim */

static int komut_ozdenetim(void)
{
	int h264 = avcodec_find_decoder(AV_CODEC_ID_H264) != NULL;
	int hevc = avcodec_find_decoder(AV_CODEC_ID_HEVC) != NULL;
	ChiakiOpusDecoder opus;
	chiaki_opus_decoder_init(&opus, &gunluk);
	ChiakiAudioSink sink;
	chiaki_opus_decoder_get_sink(&opus, &sink);
	ChiakiAudioHeader baslik;
	chiaki_audio_header_set(&baslik, 2, 16, 48000, 480);
	sink.header_cb(&baslik, sink.user);
	int ses = opus.opus_decoder != NULL;
	chiaki_opus_decoder_fini(&opus);
	ChiakiDiscovery kesif;
	int ag = chiaki_discovery_init(&kesif, &gunluk, AF_INET) == CHIAKI_ERR_SUCCESS;
	if(ag)
		chiaki_discovery_fini(&kesif);
	uint8_t hesap[CHIAKI_PSN_ACCOUNT_ID_SIZE];
	int b64 = hesap_coz("AQIDBAUGBwg=", hesap) == 0 && hesap[0] == 1 && hesap[7] == 8;
	uint8_t anahtar[CHIAKI_SESSION_AUTH_SIZE] = { '1', 'a', '2', 'b', 0 };
	int uyan = uyandirma_kimligi(anahtar) == 0x1a2b;
	int tamam = h264 && hevc && ses && ag && b64 && uyan;
	json_object *o = olay("ozdenetim");
	json_object_object_add(o, "tamam", json_object_new_boolean(tamam));
	json_object_object_add(o, "h264", json_object_new_boolean(h264));
	json_object_object_add(o, "hevc", json_object_new_boolean(hevc));
	json_object_object_add(o, "opus", json_object_new_boolean(ses));
	json_object_object_add(o, "ag", json_object_new_boolean(ag));
	json_object_object_add(o, "anahtar", json_object_new_boolean(b64 && uyan));
	olay_yaz(o);
	printf("OZDENETIM uzaktan=%s\n", tamam ? "tamam" : "HATA");
	return tamam ? 0 : 1;
}

static void yardim(void)
{
	puts("ayk-uzaktan " AYK_SURUM " - AltYaziKoprusu PS5 gizli baglanti yardimcisi (libchiaki " AYK_CHIAKI ")\n"
	     "Pencere acmaz, PS5'e hicbir kol/klavye girdisi gondermez.\n\n"
	     "Kullanim: ayk-uzaktan <komut>   (gizli degerler stdin'in ilk satirinda JSON olarak verilir)\n"
	     "  --help      bu yardim\n"
	     "  surum       surum bilgisi (JSON)\n"
	     "  ozdenetim   cozucu/ag/anahtar oz denetimi\n"
	     "  bul         {\"hedefler\":[\"255.255.255.255\"],\"sure_ms\":3000}\n"
	     "  uyandir     {\"host\":\"...\",\"kayit_anahtari\":\"<32 hex>\"}\n"
	     "  kaydet      {\"host\":\"...\",\"hesap\":\"<base64>\",\"pin\":12345678}\n"
	     "  akis        {\"host\",\"kayit_anahtari\",\"sabah\",\"hesap\",\"cozunurluk\":720,\"ses\":true}\n"
	     "Lisans: AGPL-3.0-only. Kaynak: https://github.com/ (AltYaziKoprusu deposu, uzaktan/)");
}

int main(int argc, char **argv)
{
	chiaki_mutex_init(&cikis_kilidi, false);
	if(argc < 2 || !strcmp(argv[1], "--help") || !strcmp(argv[1], "-h") || !strcmp(argv[1], "yardim"))
	{
		yardim();
		return argc < 2 ? 1 : 0;
	}
	const char *komut = argv[1];
	if(!strcmp(komut, "surum"))
	{
		json_object *o = olay("surum");
		olay_str(o, "surum", AYK_SURUM);
		olay_str(o, "chiaki", AYK_CHIAKI);
		olay_str(o, "ffmpeg", av_version_info());
		olay_yaz(o);
		return 0;
	}
	if(chiaki_lib_init() != CHIAKI_ERR_SUCCESS)
	{
		fputs("libchiaki baslatilamadi\n", stderr);
		return 3;
	}
	chiaki_log_init(&gunluk, CHIAKI_LOG_ERROR | CHIAKI_LOG_WARNING | CHIAKI_LOG_INFO, gunluk_cb, NULL);
	if(!strcmp(komut, "ozdenetim"))
		return komut_ozdenetim();

	json_object *girdi = girdi_oku();
	int sonuc;
	if(!strcmp(komut, "bul"))
		sonuc = komut_bul(girdi);
	else if(!strcmp(komut, "uyandir"))
		sonuc = komut_uyandir(girdi);
	else if(!strcmp(komut, "kaydet"))
		sonuc = komut_kaydet(girdi);
	else if(!strcmp(komut, "akis"))
	{
#ifdef _WIN32
		_setmode(_fileno(stdout), _O_BINARY);
#endif
		ikili_kip = 1;
		sonuc = komut_akis(girdi);
	}
	else
	{
		fprintf(stderr, "bilinmeyen komut: %s (bkz. --help)\n", komut);
		sonuc = 1;
	}
	if(girdi)
		json_object_put(girdi);
	return sonuc;
}
