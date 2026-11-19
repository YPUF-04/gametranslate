/* Panel uçtan uca testi. Çalıştır: node kopru/web/panel/test/panel.test.js
   Sahte bir /api/* sunucusu (PROTOKOL.md sözleşmesi) ile sihirbazı baştan sona gezer. */
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const zlib = require('zlib');
const { chromium } = require('playwright');

const PANEL = path.join(__dirname, '..');
const SHOTS = process.env.SHOTS_DIR || '';
const TV = path.join(PANEL, '..', 'tv');
const TURLER = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.woff2': 'font/woff2' };


// örnek bir oyun karesi (PNG): gökyüzü, ufuk, sol üstte görev yazıları, altta altyazı, sağda bilgi — sahte /api/kare yanıtı.
// Yazı şeritleri OKUNAN satırlarla aynı yerde durur (2. aşamadaki kutular resimle örtüşsün).
const OKUNAN = [
  { metin: 'Return to the camp', x: 0.04, y: 0.06, g: 0.22, y2: 0.04 },
  { metin: 'Talk to Marcus', x: 0.04, y: 0.105, g: 0.16, y2: 0.03 },
  { metin: 'New area discovered: Old Mill', x: 0.04, y: 0.2, g: 0.24, y2: 0.03 },
  { metin: 'Where were you last night?', x: 0.27, y: 0.8, g: 0.46, y2: 0.045 },
  { metin: 'I told you to wait for me.', x: 0.31, y: 0.855, g: 0.38, y2: 0.045 },
  { metin: 'Ammo 24/120', x: 0.83, y: 0.35, g: 0.13, y2: 0.035 },
  { metin: 'Medkit x2', x: 0.83, y: 0.4, g: 0.1, y2: 0.035 }
];
function ornekPng(w, h) {
  const renk = (x, y) => {
    const u = x / w, v = y / h;
    for (const [i, s] of OKUNAN.entries()) {
      if (u >= s.x && u <= s.x + s.g && v >= s.y + s.y2 * 0.22 && v <= s.y + s.y2 * 0.78) {
        const kelime = Math.floor((u - s.x) / s.g * 9) % 3 !== 2 || (u - s.x) / s.g > 0.85;   // kelime boşlukları
        if (!kelime) break;
        return i === 0 ? [255, 214, 120] : (i >= 5 ? [200, 230, 225] : [238, 238, 230]);
      }
    }
    if (u > 0.79 && u < 0.985 && v > 0.32 && v < 0.46) return [18, 28, 40];       // sağdaki bilgi kutusu zemini
    if (u > 0.23 && u < 0.77 && v > 0.78 && v < 0.92) return [12, 14, 18];        // altyazı şeridi
    const ufuk = 0.55 + 0.06 * Math.sin(u * 7) + 0.03 * Math.sin(u * 19);
    if (v < ufuk) return [40 + 60 * v, 70 + 70 * v, 120 + 50 * v];                // gökyüzü
    const d = (v - ufuk) / (1 - ufuk);
    return [52 - 30 * d + 10 * Math.sin(u * 40), 64 - 34 * d, 46 - 26 * d];        // yer
  };
  const satir = (y) => { const b = Buffer.alloc(1 + w * 3); for (let x = 0; x < w; x++) { const c = renk(x, y); b[1 + x * 3] = c[0]; b[2 + x * 3] = c[1]; b[3 + x * 3] = c[2]; } return b; };
  const ham = Buffer.concat(Array.from({ length: h }, (_, y) => satir(y)));
  const crcT = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  const crc = (buf) => { let c = 0xffffffff; for (const x of buf) c = crcT[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const parca = (ad, veri) => { const u = Buffer.alloc(4); u.writeUInt32BE(veri.length); const t = Buffer.concat([Buffer.from(ad), veri]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(t)); return Buffer.concat([u, t, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), parca('IHDR', ihdr), parca('IDAT', zlib.deflateSync(ham)), parca('IEND', Buffer.alloc(0))]);
}
const KARE = ornekPng(960, 540);

function sahteSunucu() {
  const st = {
    ayarlar: { arayuz_dili: 'tr', hedef_dil: 'tr', motor: 'gemini', yedek_motor: 'yerel', kaynak: 'ekran:1', ekrani_cevir: true,
      kisa_aciklama: true, ses_cevir: false, kapi: 8642, modeller: { gemini: 'gemini-2.5-flash' },
      gorunum: { yazi_boyutu: 44, konum: 'alt', arka_plan: 0.55 }, dublaj: { motor: 'kapali', oyun_sesi_kis: 0.25, hiz_siniri: 1.25, ses_seviyesi: 1, cikis: 'bilgisayar', elevenlabs_onay: false, elevenlabs_klon_onay: false, elevenlabs_ses_kimligi: '', elevenlabs_model: 'eleven_multilingual_v2' }, hafiza_izni: null, kalite: 'en_iyi', aktif_oyun: null },
    oyunlar: [{ kod: 'gta6', ad: 'GTA 6', kayit_sayisi: 1240, terim_sayisi: 35 }, { kod: 'tlou', ad: 'The Last of Us', kayit_sayisi: 0, terim_sayisi: 2 }],
    ceviriler: [{ id: 'a1', asil: 'Where were you last night?', ceviri: 'Dün gece neredeydin?', kaynak: 'motor' }, { id: 'a2', asil: 'Head back to the safehouse.', ceviri: 'Güvenli eve dön.', kaynak: 'motor' }],
    oneriler: [{ asil: 'Vice City', ceviri: 'Vice City' }],
    guncelleme: { ilerleme: 0, asama: 'bosta' }, tvIstekleri: [], tvKuyruk: [], tvSon: { asama: 'bosta', mesaj: '', ayrinti: '' },
    erisim: { kalan_dakika: 12, kod: null, bitis: null, ucretsiz_dakika: 30 }, sinir: false, kodlar: [],
    dublajHazir: false, dublajIndirme: { durum: 'bosta', yuzde: 0, hata: null }, dublajDene: [],
    okumaMod: 'iyi', okumaIstekleri: 0,
    yerel: { hazir: false, boyut_mb: 95, indirme: { durum: 'yok', yuzde: 0, mesaj: null } }, yerelHazirla: 0, yerelDene: 0, yerelAdim: 0,
    katman: { destek: true, acik: false, ekran: 1, ekranlar: [{ no: 1, ad: 'Ekran 1 (1920×1080)' }, { no: 2, ad: 'Ekran 2 (2560×1440)' }] }, katmanDene: [],
    bolgePostlari: [], kareIstekleri: 0, kareHata: false, calisiyor: false, anahtarlar: {}, istekler: [], govdeler: {}, sozluk: { oyun: 'varsayilan', terimler: [{ asil: 'Ellie', ceviri: 'Ellie' }] }
  };
  const motorlar = () => [
    { kod: 'gemini', ad: 'Gemini', anahtar_gerekli: true, anahtar_kayitli: !!st.anahtarlar.gemini, cevrimdisi: false, ucretsiz: true },
    { kod: 'deepseek', ad: 'DeepSeek', anahtar_gerekli: true, anahtar_kayitli: false, cevrimdisi: false, ucretsiz: false },
    { kod: 'claude', ad: 'Claude', anahtar_gerekli: true, anahtar_kayitli: false, cevrimdisi: false, ucretsiz: false },
    { kod: 'yerel', ad: 'Yerel', anahtar_gerekli: false, anahtar_kayitli: false, cevrimdisi: true, ucretsiz: true },
    { kod: 'deepl', ad: 'DeepL', anahtar_gerekli: true, anahtar_kayitli: false, cevrimdisi: false, ucretsiz: true },
    { kod: 'sahte', ad: 'Sahte', anahtar_gerekli: false, anahtar_kayitli: false, cevrimdisi: true, ucretsiz: true }
  ];
  const sunucu = http.createServer((q, s) => {
    const url = new URL(q.url, 'http://x');
    let govde = '';
    q.on('data', (c) => (govde += c));
    q.on('end', () => {
      const j = (o, kod = 200) => { s.writeHead(kod, { 'Content-Type': 'application/json' }); s.end(JSON.stringify(o)); };
      let b = {}; try { b = govde ? JSON.parse(govde) : {}; } catch (e) {}
      if (url.pathname.startsWith('/api/')) { st.istekler.push(q.method + ' ' + url.pathname); st.govdeler[q.method + ' ' + url.pathname] = govde; }
      if (url.pathname === '/' || url.pathname.startsWith('/panel/')) {
        const f = url.pathname === '/' ? 'index.html' : url.pathname.slice('/panel/'.length);
        const tam = path.join(PANEL, f);
        if (!tam.startsWith(PANEL) || !fs.existsSync(tam)) { s.writeHead(404); return s.end(); }
        s.writeHead(200, { 'Content-Type': TURLER[path.extname(tam)] || 'application/octet-stream' });
        return s.end(fs.readFileSync(tam));
      }
      if (url.pathname.startsWith('/statik/')) {   // yazı tipi gibi ortak dosyalar (gerçek sunucuda kopru/web/tv)
        const tam = path.join(TV, url.pathname.slice('/statik/'.length));
        if (!tam.startsWith(TV) || !fs.existsSync(tam)) { s.writeHead(404); return s.end(); }
        s.writeHead(200, { 'Content-Type': TURLER[path.extname(tam)] || 'application/octet-stream' });
        return s.end(fs.readFileSync(tam));
      }
      switch (q.method + ' ' + url.pathname) {
        case 'GET /api/durum':
          return j({ calisiyor: st.calisiyor, motor: st.ayarlar.motor, yedekte: false, tv_sayisi: st.calisiyor ? 1 : 0,
            son_yazi: st.calisiyor || st.sonYazi ? (st.sonYazi || 'Ana kampa dön') : '', adresler: ['192.168.1.20'], kapi: 8642, sinir: st.sinir });
        case 'GET /api/ayarlar': return j(Object.assign({ claude: false, gemini: !!st.anahtarlar.gemini }, st.ayarlar));
        case 'POST /api/ayarlar': if (b.bolgeler) st.bolgePostlari.push(b.bolgeler); Object.assign(st.ayarlar, b, b.gorunum ? { gorunum: Object.assign({}, st.ayarlar.gorunum, b.gorunum) } : {}); return j({ tamam: true });
        case 'GET /api/kare': st.kareIstekleri++; if (st.kareHata) return j({ hata: 'yakalama_yok', mesaj: 'Ekran görüntüsü alınamadı. Oyunun penceresini küçültmeyin ve "Görüntüyü yenile"ye basın.', ayrinti: 'YakalamaHatasi: DXGI_ERROR_ACCESS_LOST (pencere:123)' }, 400); s.writeHead(200, { 'Content-Type': 'image/png', 'Cache-Control': 'no-store' }); return s.end(KARE);
        case 'GET /api/okuma-dene':
          st.okumaIstekleri++;
          if (st.okumaMod === 'hata') return j({ hata: 'okuma_yok', mesaj: 'Yazı okuyucu bulunamadı. Windows ayarlarından İngilizce dil paketini yükleyin.', ayrinti: 'OkumaHatasi: Windows.Media.Ocr dil yok (en-US)' }, 500);
          return j({ satirlar: st.okumaMod === 'bos' ? [] : OKUNAN, sure_ms: 120, okuyucu: 'windows' });
        case 'GET /api/motor/yerel': {
          const y = st.yerel, i = y.indirme;
          if (i.durum === 'iniyor') {
            st.yerelAdim++;
            if (st.yerelHazirla === 1) { y.indirme = { durum: 'hata', yuzde: 12, mesaj: 'Dil dosyası indirilemedi: bağlantı yarıda kesildi. İnternetinizi kontrol edip "Tekrar indir"e basın.', ayrinti: 'IndirmeHatasi: https://argos-net.com/v1/translate-en_tr-1_5.argosmodel — ConnectionResetError(104)' }; }
            else { i.yuzde = Math.min(100, i.yuzde + 35); if (i.yuzde >= 100) { y.indirme = { durum: 'bitti', yuzde: 100, mesaj: null }; y.hazir = true; } }
          }
          return j(y);
        }
        case 'POST /api/motor/yerel/hazirla': st.yerelHazirla++; st.yerel.indirme = { durum: 'iniyor', yuzde: 0, mesaj: null }; return j(st.yerel);
        case 'GET /api/ekran-katmani': return j(Object.assign({}, st.katman, { ekran: st.ayarlar.katman_ekran || 1 }));
        case 'POST /api/ekran-katmani/dene': st.katmanDene.push(b); return j({ tamam: true, sure_ms: 4000 });
        case 'GET /api/erisim': return j(st.erisim);
        case 'POST /api/erisim':
          st.kodlar.push(b.kod);
          if (b.kod === 'AK1-IYI') { st.erisim = { kalan_dakika: 0, kod: 'sinirsiz', bitis: null, ucretsiz_dakika: 30 }; st.sinir = false; return j({ tamam: true, tur: 'sinirsiz' }); }
          return j({ hata: 'gecersiz_kod', mesaj: 'Bu kod geçerli değil. Harfleri kontrol edip tekrar deneyin.' }, 400);
        case 'GET /api/motorlar': return j(motorlar());
        case 'POST /api/anahtar': st.anahtarlar[b.motor] = b.anahtar; return j({ tamam: true });
        case 'POST /api/dene':
          if (b.motor === 'gemini' && !st.anahtarlar.gemini) return j({ hata: 'anahtar_yok', mesaj: 'Anahtar bulunamadı. Anahtarı yapıştırıp tekrar dene.' }, 400);
          if (b.motor === 'yerel') {
            st.yerelDene++;
            if (!st.yerel.hazir) return j({ hata: 'yerel_hazir_degil', mesaj: 'Çevrimdışı dil dosyası henüz indirilmedi. "İndir"e basın.' }, 409);
            if (st.yerelDene === 1) return j({ hata: 'motor_hatasi', mesaj: 'Çevrimdışı dil dosyası açılamadı: dosya eksik görünüyor. "Dil dosyasını yeniden indir"e basın.', ayrinti: "RuntimeError: Unable to open file 'model.bin' in model 'modeller/argos/en_tr/model'" }, 502);
          }
          return j({ ceviri: 'Merhaba, nasılsın?', sure_ms: 640 });
        case 'POST /api/baslat': st.calisiyor = true; return j({ tamam: true });
        case 'POST /api/durdur': st.calisiyor = false; return j({ tamam: true });
        case 'POST /api/deneme-yazi': st.sonYazi = 'Merhaba, bu bir deneme altyazısı'; return j({ tamam: true });
        case 'GET /api/kaynaklar': return j([{ kod: 'ekran:1', ad: 'Ekran 1 (1920×1080)' }, { kod: 'pencere:123', ad: 'PS Remote Play' }]);
        case 'GET /api/oyunlar': return j(st.oyunlar);
        case 'POST /api/oyunlar': { const kod = b.ad.toLowerCase().replace(/[^a-z0-9]/g, ''); st.oyunlar.push({ kod, ad: b.ad, kayit_sayisi: 0, terim_sayisi: 0 }); return j({ kod }); }
        case 'POST /api/oyun-sec': st.ayarlar.aktif_oyun = b.kod; return j({ tamam: true });
        case 'POST /api/paket': st.oyunlar.push({ kod: 'rdr3', ad: 'RDR 3', kayit_sayisi: 812, terim_sayisi: 4 }); return j({ tamam: true, eklenen: 812, atlanan: 12 });
        case 'GET /api/paket/gta6': s.writeHead(200, { 'Content-Type': 'application/octet-stream' }); return s.end('PK');
        case 'GET /api/son-ceviriler': return j(st.calisiyor ? st.ceviriler : []);
        case 'POST /api/duzelt': st.ceviriler.forEach((c) => { if (c.asil === b.asil) c.ceviri = b.ceviri; }); return j({ tamam: true });
        case 'GET /api/oneriler': return j(st.oneriler);
        case 'POST /api/oneriler': st.oneriler = st.oneriler.filter((o) => o.asil !== b.asil); return j({ tamam: true });
        case 'DELETE /api/oyun/rdr3/hafiza': st.silindi = true; return j({ tamam: true });
        case 'GET /api/guncelleme': {
          const g = st.guncelleme;
          if (g.asama === 'indiriliyor' && g.sayac++ >= 1) { g.ilerleme = g.ilerleme >= 80 ? 100 : 80; if (g.ilerleme === 100) g.asama = 'baslatiliyor'; }
          return j({ var: true, surum: '0.3.0', notlar: 'Tek tuşla güncelleme', boyut_mb: 48, mevcut: '0.1.0', ilerleme: g.ilerleme, asama: g.asama, mesaj: g.mesaj, denetim_acik: st.ayarlar.guncelleme_denetle !== false, son_denetim: 1 });
        }
        case 'POST /api/guncelleme/kur': st.guncelleme = { asama: 'indiriliyor', ilerleme: 40, sayac: 0 }; return j({ var: true, surum: '0.3.0', notlar: '', boyut_mb: 48, mevcut: '0.1.0', ilerleme: 40, asama: 'indiriliyor' });
        case 'POST /api/guncelleme/denetle': return j({ var: true, surum: '0.3.0', notlar: '', boyut_mb: 48, mevcut: '0.1.0', ilerleme: st.guncelleme.ilerleme, asama: st.guncelleme.asama, son_denetim: 2 });
        case 'POST /api/tv/lg/kur': {
          st.tvIstekleri.push(b);
          if (b.parola === 'BAD000') {
            st.tvKuyruk = [{ asama: 'anahtar', mesaj: 'TV\'den anahtar alınıyor...', ayrinti: '' }, { asama: 'hata', mesaj: 'Kod yanlış görünüyor. TV\'deki Developer Mode uygulamasındaki 6 haneli kodu tekrar yazın.', ayrinti: 'TvHatasi: Anahtar bu kodla açılamadı' }];
          } else {
            st.tvKuyruk = ['baglaniyor', 'yukleniyor', 'kuruluyor', 'bitti'].map((a) => ({ asama: a, mesaj: a === 'bitti' ? 'Kuruldu. Uygulama TV\'de açılıyor.' : a + '...', ayrinti: '' }));
          }
          st.tvSon = { asama: 'anahtar', mesaj: 'TV\'den anahtar alınıyor...', ayrinti: '' };
          return j(st.tvSon);
        }
        case 'GET /api/tv/lg/durum': if (st.tvKuyruk.length) st.tvSon = st.tvKuyruk.shift(); return j(st.tvSon);
        case 'GET /api/dublaj': {
          const i = st.dublajIndirme;
          if (i.durum === 'indiriliyor') { i.yuzde = i.yuzde >= 60 ? 100 : 60; if (i.yuzde === 100) { i.durum = 'bitti'; st.dublajHazir = true; } }
          return j({ motor: st.ayarlar.dublaj.motor, hazir: st.dublajHazir && st.ayarlar.dublaj.motor !== 'kapali', onerilen: 'chatterbox', ekran_karti: 'NVIDIA GeForce RTX 3060', vram_gb: 12, ram_gb: 16,
            indirme: i, calisiyor: false, son_hata: null, elevenlabs_anahtar: !!st.anahtarlar.elevenlabs, motorlar: [] });
        }
        case 'POST /api/dublaj': {
          const m = Object.assign({}, st.ayarlar.dublaj, b);
          if (!m.elevenlabs_onay) { m.elevenlabs_klon_onay = false; if (m.motor === 'elevenlabs') { if (b.motor === 'elevenlabs') return j({ hata: 'dublaj_onay_gerekli', mesaj: 'ElevenLabs için önce onayı işaretleyin.' }, 400); m.motor = 'kapali'; } }
          if (b.motor && b.motor !== st.ayarlar.dublaj.motor) { st.dublajHazir = false; st.dublajIndirme = { durum: 'bosta', yuzde: 0, hata: null }; }
          st.ayarlar.dublaj = m; return j({ tamam: true, dublaj: m });
        }
        case 'POST /api/dublaj/hazirla': st.dublajIndirme = { durum: 'indiriliyor', yuzde: 10, hata: null }; return j({ motor: st.ayarlar.dublaj.motor, hazir: false, onerilen: 'chatterbox', indirme: st.dublajIndirme });
        case 'POST /api/dublaj/dene': st.dublajDene.push(b.metin); return j({ tamam: true, sure_ms: 1800, cikis: st.ayarlar.dublaj.cikis });
        case 'GET /api/sozluk': return j(st.sozluk);
        case 'POST /api/sozluk': st.sozluk = b; return j({ tamam: true });
      }
      j({ hata: 'yok', mesaj: 'Bulunamadı.' }, 404);
    });
  });
  return { sunucu, st };
}

function dilKontrol() {
  const oku = (k) => JSON.parse(fs.readFileSync(path.join(PANEL, 'dil', k + '.json'), 'utf8'));
  const tr = oku('tr'), en = oku('en');
  assert.deepStrictEqual(Object.keys(tr).sort(), Object.keys(en).sort(), 'tr ve en anahtarları aynı olmalı');
  const js = fs.readFileSync(path.join(PANEL, 'panel.js'), 'utf8');
  const eksik = [];
  for (const m of js.matchAll(/\b(?:t|ne|adimlar|bolum)\('([a-z0-9_]+(?:\.[a-z0-9_]+)+)'/g)) if (!(m[1] in tr)) eksik.push(m[1]);
  assert.deepStrictEqual(eksik, [], 'panel.js içinde tr.json\'da olmayan anahtar: ' + eksik.join(', '));
}

(async () => {
  dilKontrol();
  console.log('  ok - tr/en anahtarları eşit, panel.js anahtarları tanımlı');
  const { sunucu, st } = sahteSunucu();
  await new Promise((r) => sunucu.listen(0, '127.0.0.1', r));
  const taban = 'http://127.0.0.1:' + sunucu.address().port;
  const tarayici = await chromium.launch();
  const sayfa = await (await tarayici.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: Number(process.env.SCALE || 1) })).newPage();
  const hatalar = [];
  sayfa.on('console', (m) => { if (m.type() === 'error') hatalar.push(m.text()); });
  sayfa.on('pageerror', (e) => hatalar.push(String(e)));
  const gor = async (ad, tam) => { if (SHOTS && tam) await sayfa.waitForFunction(() => !document.querySelector('.tost'), null, { timeout: 8000 }).catch(() => {}); if (SHOTS) await sayfa.screenshot({ path: path.join(SHOTS, ad), fullPage: !!tam || !!process.env.FULL }); };
  const adim = (s) => console.log('  ok -', s);

  try {
    await sayfa.goto(taban + '/');
    await sayfa.waitForSelector('h1');
    const yakin = (a, b, ne) => assert.ok(Math.abs(a - b) < 0.006, ne + ': ' + a + ' ≠ ' + b);
    const metin = async (s) => (await sayfa.textContent(s)) || '';

    // ================= 1. GÖRÜNTÜ =================
    assert.match(await metin('h1'), /Oyunu nerede oynuyorsun\?/);
    assert.strictEqual(await sayfa.locator('.noktalar > li').count(), 6, 'üstte 6 adım');
    assert.match(await metin('.noktalar'), /Görüntü[\s\S]*Yazı okuma[\s\S]*Çeviri[\s\S]*Nerede göreyim\?[\s\S]*Neyi çevireyim\?[\s\S]*Hazır/);
    assert.ok(await sayfa.isDisabled('#ileri-1'), 'görüntü görülmeden Devam kapalı');
    assert.ok(await sayfa.isVisible('#atla-1'));
    assert.match(await metin('[data-cihaz=pc]'), /Bu bilgisayarda/);
    assert.match(await metin('[data-cihaz=ps5]'), /PS5 Remote Play/);
    assert.strictEqual(await sayfa.locator('text=TV\'n hangisi?').count(), 0, '"TV\'n hangisi?" sorusu yok');
    // görüntü alınamazsa: sunucunun özel mesajı + çözüm + Ayrıntı
    st.kareHata = true;
    await sayfa.click('[data-cihaz=pc]');
    assert.match(await metin('#kaynak-ipucu'), /pencere moduna/);
    await sayfa.waitForSelector('#goruntu-hata');
    assert.match(await metin('#goruntu-hata-mesaj'), /Ekran görüntüsü alınamadı\./);
    assert.doesNotMatch(await metin('#goruntu-hata'), /Bir şeyler ters gitti/);
    assert.ok(!(await sayfa.isVisible('#goruntu-hata-ayrinti')), 'ayrıntı kapalı gelir');
    await sayfa.click('#goruntu-hata-ayrinti-kap > summary');
    assert.match(await metin('#goruntu-hata-ayrinti'), /DXGI_ERROR_ACCESS_LOST[\s\S]*kod: yakalama_yok · HTTP 400/);
    assert.ok(await sayfa.isDisabled('#ileri-1'));
    st.kareHata = false;
    await sayfa.click('#goruntu-tekrar');
    await sayfa.waitForSelector('#dogrula-1:not([hidden])');
    assert.match(await metin('#dogrula-1'), /Çalıştı[\s\S]*Oyun görüntüsünü görüyorum\./);
    await sayfa.click('[data-kaynak="pencere:123"]');
    await sayfa.waitForFunction(() => document.querySelector('#dogrula-1') && !document.querySelector('#dogrula-1').hidden && document.querySelector('[data-kaynak="pencere:123"]').getAttribute('aria-pressed') === 'true');
    assert.strictEqual(st.ayarlar.kaynak, 'pencere:123'); assert.strictEqual(st.ayarlar.cihaz, 'pc');
    assert.ok(!(await sayfa.isDisabled('#ileri-1')));
    await gor('adim-1.png', true);
    adim('1. Görüntü: cihaz → pencere → önizleme ✓; hata özel mesaj + Ayrıntı ile');
    await sayfa.click('#ileri-1');

    // ================= 2. YAZI OKUMA (önce 0 yazı, sonra atla) =================
    await sayfa.waitForSelector('#oku');
    assert.match(await metin('h1'), /Ekrandaki yazıları okuyabiliyor muyum\?/);
    st.okumaMod = 'bos';
    await sayfa.click('#oku');
    await sayfa.waitForSelector('#okuma-sifir');
    assert.match(await metin('#okuma-sifir'), /Oyunda yazı olan bir ekran açın, sonra tekrar deneyin\./);
    assert.ok(await sayfa.isDisabled('#ileri-2'), '0 yazıda Devam kapalı');
    st.okumaMod = 'hata';
    await sayfa.click('#oku');
    await sayfa.waitForSelector('#okuma-hata');
    assert.match(await metin('#okuma-hata-mesaj'), /Yazı okuyucu bulunamadı\./);
    await sayfa.click('#okuma-hata-ayrinti-kap > summary');
    assert.match(await metin('#okuma-hata-ayrinti'), /Windows\.Media\.Ocr/);
    await sayfa.click('#sorun-2 > summary');
    assert.strictEqual(await sayfa.locator('#sorun-2 li').count(), 4);
    await sayfa.click('#atla-2');
    adim('2. Yazı okuma: 0 yazıda ipucu, hata özel mesajla, "Bu adımı atla" ile geçildi');

    // ================= 3. ÇEVİRİ =================
    await sayfa.waitForSelector('[data-motor=gemini]');
    assert.ok(await sayfa.isDisabled('#ileri-3'));
    await sayfa.click('[data-motor=claude]');
    assert.match(await metin('#motor-detay'), /Pro\/Max/);
    await sayfa.click('[data-motor=gemini]');
    await sayfa.click('#kalite-wiz-dengeli');
    await sayfa.waitForTimeout(150);
    assert.strictEqual(st.ayarlar.kalite, 'dengeli');
    await sayfa.click('#kaydet-dene'); // anahtarsız → sunucunun özel hatası + çözüm
    await sayfa.waitForSelector('#dene-hata');
    assert.match(await metin('#dene-hata-mesaj'), /Anahtar bulunamadı\./);
    assert.ok(await sayfa.isVisible('#anahtar-odak'));
    await sayfa.click('#dene-hata-ayrinti-kap > summary');
    assert.match(await metin('#dene-hata-ayrinti'), /kod: anahtar_yok · HTTP 400/);
    await sayfa.fill('#anahtar-gir', 'AIzaSAHTE-ANAHTAR');
    await sayfa.click('#kaydet-dene');
    await sayfa.waitForSelector('#dogrula-3:not([hidden])');
    assert.match(await metin('#dogrula-3'), /Gemini çeviri yapıyor\.[\s\S]*Hello, how are you\?[\s\S]*Merhaba, nasılsın\?/);
    assert.strictEqual(st.anahtarlar.gemini, 'AIzaSAHTE-ANAHTAR');
    adim('3. Çeviri: Gemini anahtarsız özel hata, anahtarla ✓');
    // çevrimdışı motor: İndir → hata (özel mesaj + Ayrıntı) → Tekrar indir → ilerleme → hazır → Dene
    await sayfa.click('[data-motor=yerel]');
    assert.ok(await sayfa.isDisabled('#ileri-3'), 'motor değişince ✓ sıfırlanır');
    await sayfa.waitForSelector('#yerel-indir');
    assert.match(await metin('#yerel-indir'), /İndir \(~95 MB, bir kez\)/);
    await sayfa.click('#yerel-indir');
    await sayfa.waitForSelector('#yerel-hata', { timeout: 6000 });
    assert.match(await metin('#yerel-hata-mesaj'), /Dil dosyası indirilemedi: bağlantı yarıda kesildi\./);
    assert.doesNotMatch(await metin('#yerel-hata'), /Çeviri motoru çalışmadı/);
    await sayfa.click('#yerel-hata-ayrinti-kap > summary');
    assert.match(await metin('#yerel-hata-ayrinti'), /ConnectionResetError/);
    await gor('adim-3-hata.png', true);
    assert.match(await metin('#yerel-indir'), /Tekrar indir/);
    await sayfa.click('#yerel-indir');
    await sayfa.waitForSelector('#yerel-ilerleme');
    await sayfa.waitForFunction(() => { const b = document.querySelector('#yerel-ilerleme'); return b && Number(b.getAttribute('aria-valuenow')) > 0 && Number(b.getAttribute('aria-valuenow')) < 100; }, null, { timeout: 6000 });
    assert.match(await metin('#yerel-metin'), /Dil dosyası indiriliyor… %\d+/);
    await sayfa.waitForSelector('#yerel-hazir', { timeout: 8000 });
    assert.strictEqual(st.yerelHazirla, 2);
    await sayfa.click('#sadece-dene');
    await sayfa.waitForSelector('#dene-hata');
    assert.match(await metin('#dene-hata-mesaj'), /Çevrimdışı dil dosyası açılamadı: dosya eksik görünüyor\./);
    assert.doesNotMatch(await metin('#dene-hata'), /Çeviri motoru çalışmadı|Bir şeyler ters gitti/, 'genel mesaj yerine sunucunun özel mesajı');
    assert.ok(await sayfa.isVisible('#yerel-yeniden'), 'çözüm: dil dosyasını yeniden indir');
    await sayfa.click('#dene-hata-ayrinti-kap > summary');
    assert.match(await metin('#dene-hata-ayrinti'), /Unable to open file 'model\.bin'[\s\S]*kod: motor_hatasi · HTTP 502/);
    await sayfa.click('#dene-tekrar');
    await sayfa.waitForSelector('#dogrula-3:not([hidden])');
    assert.match(await metin('#dogrula-3'), /Yerel çeviri yapıyor\.[\s\S]*Merhaba, nasılsın\?/);
    assert.strictEqual(st.ayarlar.motor, 'yerel');
    await gor('adim-3.png', true);
    adim('3. Çeviri (çevrimdışı): İndir → özel indirme hatası + Ayrıntı → ilerleme çubuğu → hazır → Dene hatası özel → ✓');
    await sayfa.click('#ileri-3');

    // ================= 4. NEREDE GÖREYİM? =================
    await sayfa.waitForSelector('[data-gosterim=bilgisayar]');
    assert.match(await metin('h1'), /Çeviriyi nerede göreyim\?/);
    assert.strictEqual(await sayfa.getAttribute('#gosterim-bilgisayar', 'aria-pressed'), 'true', 'varsayılan: bu bilgisayar');
    assert.match(await metin('#gosterim-bilgisayar'), /Bu bilgisayarın ekranında \(oyunun üstünde\)[\s\S]*Önerilen/);
    assert.strictEqual(await sayfa.locator('[data-gosterim]').count(), 3, 'Samsung/Android eşit kare değil');
    assert.match(await metin('#yakinda'), /Samsung ve Android TV uygulamaları yakında/);
    await sayfa.waitForSelector('[data-ekran="2"]');
    await sayfa.click('[data-ekran="2"]');
    await sayfa.waitForTimeout(120);
    assert.strictEqual(st.ayarlar.katman_ekran, 2);
    await sayfa.click('#katman-dene');
    await sayfa.waitForSelector('#soru-kutu:not([hidden])');
    assert.match(await metin('#soru-kutu'), /Ekranında yazıyı gördün mü\?/);
    assert.deepStrictEqual(st.katmanDene[0], { ekran: 2 });
    await sayfa.click('#hayir');
    await sayfa.waitForSelector('#sorun-kutu:not([hidden])');
    assert.match(await metin('#sorun-kutu'), /Pencereli tam ekran[\s\S]*Kenarlıksız/);
    assert.ok(await sayfa.isDisabled('#ileri-4'));
    adim('4. Bilgisayar ekranı: 2 monitörden seçildi, "Ekranda dene", Hayır → tam ekran ipuçları');
    // LG TV: kurulum kartı (eski test korunur)
    await sayfa.click('#gosterim-tv');
    await sayfa.waitForSelector('#tv-kart');
    await sayfa.waitForTimeout(100);
    assert.strictEqual(st.ayarlar.gosterim, 'tv');
    assert.match(await metin('#adres-kutu'), /192\.168\.1\.20:8642\/tv/);
    assert.strictEqual(await sayfa.locator('#tv-kart > ol:not(.tv-asamalar) > li').count(), 3);
    assert.match(await metin('#tv-kart > ol:not(.tv-asamalar)'), /Developer Mode uygulamasını aç[\s\S]*IP adresini ve ekrandaki kodu \(Passphrase\)[\s\S]*Kur'a bas/);
    await sayfa.click('#tv-kur');
    assert.match(await metin('#tv-hata'), /IP adresini ve ekrandaki kodu yaz/);
    await sayfa.fill('#tv-ip', '192.168.1.30');
    await sayfa.fill('#tv-parola', 'BAD000');
    await sayfa.click('#tv-kur');
    await sayfa.waitForSelector('#tv-hata-mesaj', { timeout: 6000 });
    assert.match(await metin('#tv-hata-mesaj'), /Kod yanlış görünüyor/);
    assert.ok(!(await sayfa.isVisible('#tv-ayrinti')), 'ham metin kapalı gelmeli');
    await sayfa.click('#tv-ayrinti-kap > summary');
    assert.match(await metin('#tv-ayrinti'), /Anahtar bu kodla açılamadı/);
    assert.deepStrictEqual(st.tvIstekleri[0], { ip: '192.168.1.30', parola: 'BAD000', paket: 'asil' });
    await sayfa.click('#tv-acgsiz');
    await sayfa.waitForFunction(() => !document.querySelector('#tv-acgsiz') && document.querySelector('#tv-hata-mesaj'), null, { timeout: 6000 });
    assert.strictEqual(st.tvIstekleri[1].paket, 'acgsiz');
    await sayfa.fill('#tv-parola', 'GOOD12');
    await sayfa.click('#tv-deneme');
    await sayfa.waitForSelector('#tv-bitti', { timeout: 8000 });
    assert.strictEqual(st.tvIstekleri[2].paket, 'deneme');
    assert.strictEqual(await sayfa.locator('#tv-asamalar li.bitti').count(), 5);
    assert.strictEqual(await sayfa.inputValue('#tv-parola'), '', 'kod başarıdan sonra silinir');
    assert.ok(!JSON.stringify(await sayfa.evaluate(() => Object.assign({}, localStorage))).match(/BAD000|GOOD12/), 'kod tarayıcıda saklanmaz');
    await sayfa.click('#deneme-yazi');
    await sayfa.waitForSelector('#hayir');
    await sayfa.click('#hayir');
    await sayfa.waitForSelector('#sorun-kutu:not([hidden])');
    assert.ok(st.istekler.includes('POST /api/deneme-yazi'));
    adim('4. LG TV: kurulum kartı (boş alan, yanlış kod + Ayrıntı, başka sürüm, deneme uygulaması), deneme altyazısı, sorun listesi');
    await sayfa.click('#gosterim-tarayici');
    await sayfa.waitForSelector('#adres-kutu');
    assert.match(await metin('#adres-kutu'), /192\.168\.1\.20:8642\/tv[\s\S]*127\.0\.0\.1:8642\/obs/);
    // geri: bu bilgisayar → dene → Evet → ✓
    await sayfa.click('#gosterim-bilgisayar');
    await sayfa.waitForSelector('#katman-dene');
    assert.strictEqual(await sayfa.getAttribute('[data-ekran="2"]', 'aria-pressed'), 'true', 'seçilen monitör hatırlanır');
    await sayfa.click('#katman-dene');
    await sayfa.waitForSelector('#evet');
    await sayfa.click('#evet');
    await sayfa.waitForSelector('#dogrula-4:not([hidden])');
    assert.match(await metin('#dogrula-4'), /Yazıyı bu bilgisayarın ekranında gördün\./);
    await gor('adim-4.png', true);
    // genel "Ekrandaki yazıların büyüklüğü" (4. aşama): gorunum.ekran_olcek
    assert.match(await metin('#ekran-olcek-kart'), /Ekrandaki yazıların büyüklüğü[\s\S]*Yazılar fazla büyük\/küçük görünüyorsa buradan ayarla\./);
    await sayfa.fill('#ekran-olcek', '70');
    await sayfa.waitForFunction(() => document.querySelector('#ekran-olcek-deger').textContent === '%70');
    await sayfa.waitForTimeout(500);
    assert.strictEqual(st.ayarlar.gorunum.ekran_olcek, 0.7, 'gorunum.ekran_olcek kaydedildi');
    assert.strictEqual(st.ayarlar.gorunum.yazi_boyutu, 44, 'diğer görünüm ayarları korunur');
    await sayfa.click('#ileri-4');
    await sayfa.waitForTimeout(100);
    assert.strictEqual(st.ayarlar.gosterim, 'bilgisayar'); assert.strictEqual(st.ayarlar.katman_ekran, 2);
    adim('4. Nerede göreyim: bilgisayar ekranında Evet → ✓, gosterim + katman_ekran kaydedildi');

    // ================= 5. NEYİ ÇEVİREYİM? (en son, tam genişlik) =================
    await sayfa.waitForSelector('#bolge-sahne:not([hidden])');
    assert.match(await metin('h1'), /Neyi çevireyim\?/);
    assert.ok(await sayfa.evaluate(() => document.querySelector('#ana').classList.contains('genis')), 'editör geniş');
    const genislik = await sayfa.evaluate(() => document.querySelector('#bolge-sahne').getBoundingClientRect().width);
    assert.ok(genislik > 1100, 'resim neredeyse tam genişlik: ' + genislik);
    await sayfa.waitForSelector('#bolge-ipucu:not([hidden])');
    assert.match(await metin('#bolge-ipucu'), /Çevrilmesini istediğin yerleri fareyle kare içine al: örn\. alttaki konuşmalar, sol üstteki görev yazısı\./);
    await gor('adim-5-ipucu.png');
    await sayfa.click('#bolge-ipucu-tamam');
    assert.ok(!(await sayfa.isVisible('#bolge-ipucu')));
    // okunan yazılardan öner (2. adım atlandığı için kendisi okur)
    st.okumaMod = 'iyi';
    await sayfa.click('#bolge-oner');
    await sayfa.waitForFunction(() => document.querySelectorAll('.bolge').length === 4);
    const oneri = await sayfa.evaluate(() => [...document.querySelectorAll('.bolge')].map((e) => e.className.match(/t-(\w+)/)[1]));
    assert.deepStrictEqual(oneri, ['ust_yazi', 'ust_yazi', 'diger', 'altyazi']);
    assert.match(await metin('#bolge-sayac'), /4 \/ 6 kare/);
    await sayfa.click('#bolge-kaydet');
    await sayfa.waitForSelector('#dogrula-5:not([hidden])');
    const onerKayit = st.bolgePostlari[st.bolgePostlari.length - 1];
    assert.strictEqual(onerKayit.length, 4);
    const alt = onerKayit.find((b) => b.tur === 'altyazi');
    assert.ok(alt.x < 0.27 && alt.x + alt.g > 0.73 && alt.y < 0.8 && alt.y + alt.y2 > 0.9, 'altyazı kümesi iki satırı kapsar');
    adim('5. "Okunan yazılardan öner": 4 kare (sol üstte 2 görev-bilgi, sağda diğer, altta altyazı) kaydedildi');
    // hepsini sil, kullanıcının çizimi gibi elle 4 kare çiz
    while (await sayfa.locator('.bolge').count()) { await sayfa.focus('.bolge[data-bolge="0"]'); await sayfa.keyboard.press('Delete'); }
    assert.ok(await sayfa.isDisabled('#ileri-5'), 'değişince ✓ sıfırlanır');
    await sayfa.evaluate(() => document.querySelector('#bolge-sahne').scrollIntoView({ block: 'center', behavior: 'instant' }));
    await sayfa.waitForTimeout(100);
    let kb;
    const fare = async (ax, ay, bx, by) => {
      kb = await sayfa.locator('#bolge-katman').boundingBox();
      await sayfa.mouse.move(kb.x + kb.width * ax, kb.y + kb.height * ay);
      await sayfa.mouse.down();
      await sayfa.mouse.move(kb.x + kb.width * ((ax + bx) / 2), kb.y + kb.height * ((ay + by) / 2), { steps: 3 });
      await sayfa.mouse.move(kb.x + kb.width * bx, kb.y + kb.height * by, { steps: 3 });
      await sayfa.mouse.up();
    };
    await fare(0.03, 0.04, 0.29, 0.155);     // sol üst: görev
    await fare(0.03, 0.18, 0.3, 0.25);       // altında: bilgi
    await fare(0.24, 0.77, 0.76, 0.93);      // alt orta: altyazı
    await fare(0.81, 0.3, 0.98, 0.64);       // sağ kenar
    assert.strictEqual(await sayfa.locator('.bolge').count(), 4);
    const turler = await sayfa.evaluate(() => [...document.querySelectorAll('.bolge')].map((e) => e.className.match(/t-(\w+)/)[1]));
    assert.deepStrictEqual(turler, ['ust_yazi', 'ust_yazi', 'altyazi', 'diger'], 'tür konumdan tahmin edilir');
    // tür: küçük açılır kutu (fare), Esc ile kapanır; liste seçimi (klavye)
    await sayfa.click('#bolge-cip-3');
    await sayfa.waitForSelector('#bolge-pop:not([hidden])');
    assert.match(await metin('#bolge-pop'), /4\. karede ne var\?[\s\S]*Altyazı[\s\S]*Görev-bilgi[\s\S]*Diğer/);
    await sayfa.click('#bolge-pop [data-pop-tur=ust_yazi]');
    assert.ok(await sayfa.isHidden('#bolge-pop'));
    assert.match(await sayfa.getAttribute('.bolge[data-bolge="3"]', 'class'), /t-ust_yazi/);
    assert.strictEqual(await sayfa.evaluate(() => document.activeElement.id), 'bolge-cip-3', 'odak etikete döner');
    await sayfa.keyboard.press('Enter');
    await sayfa.waitForSelector('#bolge-pop:not([hidden])');
    await sayfa.keyboard.press('Escape');
    assert.ok(await sayfa.isHidden('#bolge-pop'));
    await sayfa.selectOption('#bolge-tur-3', 'diger');
    assert.match(await sayfa.getAttribute('.bolge[data-bolge="3"]', 'aria-label'), /Kare 4: Diğer/);
    // en çok 6
    await fare(0.4, 0.3, 0.5, 0.38); await fare(0.4, 0.45, 0.5, 0.52);
    assert.strictEqual(await sayfa.locator('.bolge').count(), 6);
    await fare(0.55, 0.3, 0.65, 0.38);
    assert.strictEqual(await sayfa.locator('.bolge').count(), 6, '7. kare çizilemez');
    assert.ok(await sayfa.isVisible('#bolge-dolu'));
    await sayfa.click('[data-sil="5"]');      // listeden × ile sil
    await sayfa.focus('.bolge[data-bolge="4"]'); await sayfa.keyboard.press('Delete');   // Delete tuşu
    assert.strictEqual(await sayfa.locator('.bolge').count(), 4);
    // köşeden boyutlandır: altyazı kutusunun sağ-alt köşesi
    await sayfa.evaluate(() => document.querySelector('#bolge-sahne').scrollIntoView({ block: 'center', behavior: 'instant' }));
    kb = await sayfa.locator('#bolge-katman').boundingBox();
    const k3 = await sayfa.locator('.bolge[data-bolge="2"] .tutamac.se').boundingBox();
    await sayfa.mouse.move(k3.x + k3.width / 2, k3.y + k3.height / 2); await sayfa.mouse.down();
    await sayfa.mouse.move(kb.x + kb.width * 0.78, kb.y + kb.height * 0.94, { steps: 4 }); await sayfa.mouse.up();
    // klavye: 1. kutuyu 1 adım sağa, Shift+Aşağı ile 1 adım uzat
    await sayfa.focus('.bolge[data-bolge="0"]');
    await sayfa.keyboard.press('ArrowRight');
    await sayfa.keyboard.press('Shift+ArrowDown');
    await sayfa.click('#bolge-kaydet');
    await sayfa.waitForSelector('#dogrula-5:not([hidden])');
    assert.match(await metin('#dogrula-5'), /4 yeri kaydettim\./);
    const kayit = st.bolgePostlari[st.bolgePostlari.length - 1];
    assert.strictEqual(kayit.length, 4);
    yakin(kayit[0].x, 0.04, 'x'); yakin(kayit[0].y, 0.04, 'y'); yakin(kayit[0].g, 0.26, 'g'); yakin(kayit[0].y2, 0.125, 'y2');
    yakin(kayit[2].x, 0.24, 'x3'); yakin(kayit[2].y, 0.77, 'y3'); yakin(kayit[2].g, 0.54, 'g3'); yakin(kayit[2].y2, 0.17, 'y23');
    assert.deepStrictEqual(kayit.map((b) => b.tur), ['ust_yazi', 'ust_yazi', 'altyazi', 'diger']);
    assert.deepStrictEqual(kayit.map((b) => b.ad), ['Görev-bilgi', 'Görev-bilgi', 'Altyazı', 'Diğer']);
    for (const b of kayit) { assert.ok(b.x >= 0 && b.y >= 0 && b.x + b.g <= 1.0001 && b.y + b.y2 <= 1.0001); assert.deepStrictEqual(Object.keys(b).sort(), ['ad', 'g', 'hedef', 'olcek', 'tur', 'x', 'y', 'y2']); assert.ok(b.hedef === 'ustune' || b.hedef === 'altyazi'); assert.strictEqual(b.olcek, 1); }
    assert.deepStrictEqual(kayit.map((b) => b.hedef), ['ustune', 'ustune', 'altyazi', 'ustune'], 'varsayılan hedef türe göre');
    await sayfa.click('.bolge[data-bolge="2"]', { position: { x: 200, y: 40 } });
    await sayfa.evaluate(() => window.scrollTo(0, 0));
    await gor('adim-5.png', true);
    // kare alınamazsa dostça mesaj, kareler korunur
    st.kareHata = true; await sayfa.click('#bolge-yenile');
    await sayfa.waitForSelector('#bolge-hata');
    assert.match(await metin('#bolge-hata-mesaj'), /Ekran görüntüsü alınamadı/);
    st.kareHata = false; await sayfa.click('#bolge-hata-tekrar'); await sayfa.waitForSelector('#bolge-sahne:not([hidden])');
    assert.strictEqual(await sayfa.locator('.bolge').count(), 4, 'yenileyince kareler kaybolmaz');
    // ---- hedef kutusu + yazı büyüklüğü ----
    assert.match(await metin('#bolge-rehber'), /Kareyi okunacak yazının etrafına çiz\. Sonra çevirinin nereye yazılacağını seç: aynı yere, alttaki çubuğa ya da kendin bir yer çiz\.[\s\S]*Oyundaki sayıları \(puan, para\) kare içine alma; onları çevirmem\./);
    assert.match(await metin('[data-satir="0"]'), /Çeviriyi nereye yazayım\?[\s\S]*Aynı yerin üstüne[\s\S]*Alttaki altyazı çubuğuna[\s\S]*Kendim seçeyim[\s\S]*Yazı büyüklüğü[\s\S]*%100/);
    assert.ok(await sayfa.isChecked('#bolge-hedef-0-ustune') && await sayfa.isChecked('#bolge-hedef-2-altyazi'), 'varsayılanlar');
    await sayfa.evaluate(() => document.querySelector('#bolge-sahne').scrollIntoView({ block: 'center', behavior: 'instant' }));
    await sayfa.click('#bolge-hedef-0-kendim');
    await sayfa.waitForSelector('.bolge-hedef[data-hedef="0"]');
    assert.ok(await sayfa.isVisible('#bolge-mod'), 'hedef çizme kipi bildirilir');
    assert.match(await metin('.bolge-hedef[data-hedef="0"] .hedef-etiket'), /1 → hedef/);
    assert.ok(await sayfa.evaluate(() => getComputedStyle(document.querySelector('.bolge-hedef')).borderStyle === 'dashed'), 'hedef kesik çizgili');
    assert.strictEqual(await sayfa.locator('.bolge-baglanti line').count(), 1, 'bağlantı çizgisi');
    await sayfa.evaluate(() => document.querySelector('#bolge-sahne').scrollIntoView({ block: 'center', behavior: 'instant' }));
    await fare(0.42, 0.45, 0.66, 0.55);    // ikinci kutu = hedef
    assert.ok(await sayfa.isHidden('#bolge-mod'), 'çizim bitince kip kapanır');
    assert.strictEqual(await sayfa.locator('.bolge').count(), 4, 'hedef çizmek yeni kaynak kare açmaz');
    // slider %80 (klavye erişilebilir aralık girdisi)
    await sayfa.fill('#bolge-olcek-0', '80');
    assert.strictEqual(await metin('#bolge-olcek-deger-0'), '%80');
    // önizleme: hedefte örnek yazı (OCR metni), kelime ortasından bölünmez
    const onizle = await sayfa.evaluate(() => { const e = document.querySelector('.bolge-onizle'), y = e.firstChild, r = e.getBoundingClientRect(), h = document.querySelector('.bolge-hedef[data-hedef="0"]').getBoundingClientRect();
      return { metin: y.textContent, px: parseFloat(y.style.fontSize), wrap: getComputedStyle(y).wordBreak + '/' + getComputedStyle(y).overflowWrap, dx: Math.abs(r.left - h.left), dy: Math.abs(r.top - h.top) }; });
    assert.match(onizle.metin, /Return to the camp/); assert.ok(onizle.px > 4 && onizle.wrap === 'normal/normal', JSON.stringify(onizle)); assert.ok(onizle.dx < 2 && onizle.dy < 2, 'önizleme hedefin içinde');
    // ikinci kare: alttaki altyazı çubuğu
    await sayfa.click('#bolge-hedef-2-altyazi');
    assert.ok(await sayfa.isChecked('#bolge-hedef-2-altyazi'));
    // klavye: hedef kutusu odaklanır, ok tuşu taşır, Enter kaynağa döner
    await sayfa.focus('.bolge-hedef[data-hedef="0"]');
    const solOnce = await sayfa.evaluate(() => parseFloat(document.querySelector('.bolge-hedef').style.left));
    await sayfa.keyboard.press('ArrowRight');
    assert.ok(await sayfa.evaluate(() => parseFloat(document.querySelector('.bolge-hedef').style.left)) > solOnce, 'hedef klavyeyle taşınır');
    await sayfa.click('#bolge-kaydet');
    await sayfa.waitForSelector('#dogrula-5:not([hidden])');
    const k2 = st.bolgePostlari[st.bolgePostlari.length - 1];
    assert.strictEqual(k2[0].olcek, 0.8);
    assert.ok(k2[0].hedef && typeof k2[0].hedef === 'object' && Object.keys(k2[0].hedef).sort().join() === 'g,x,y,y2', JSON.stringify(k2[0].hedef));
    yakin(k2[0].hedef.x, 0.43, 'hx'); yakin(k2[0].hedef.y, 0.45, 'hy'); yakin(k2[0].hedef.g, 0.24, 'hg'); yakin(k2[0].hedef.y2, 0.1, 'hy2');
    for (const v of Object.values(k2[0].hedef)) assert.strictEqual(v, Math.round(v * 10000) / 10000, '4 hane');
    assert.strictEqual(k2[2].hedef, 'altyazi'); assert.strictEqual(k2[1].hedef, 'ustune'); assert.strictEqual(k2[1].olcek, 1);
    // yeniden yükleyince hedef ve ölçek geri gelir; alanı olmayan eski kayıt varsayılan gösterir
    if (SHOTS) { await sayfa.focus('.bolge[data-bolge="0"]'); await sayfa.evaluate(() => document.querySelector('#bolge-rehber').scrollIntoView({ block: 'start', behavior: 'instant' })); await sayfa.waitForTimeout(150); await sayfa.screenshot({ path: path.join(SHOTS, 'hedef-editor.png') }); }
    adim('hedef kutusu (Kendim seçeyim), %80 yazı büyüklüğü, altyazı çubuğu seçimi kaydedildi');

    adim('5. Elle 4 kare (kullanıcının çizimi gibi), tür açılır kutusu + Esc, en çok 6, sil, boyutlandır, klavye, normalize JSON');
    await sayfa.click('#ileri-5');

    // ================= 6. HAZIR (atlanan adım amber, "Şimdi yap") =================
    await sayfa.waitForSelector('#hazir-baslat');
    assert.match(await metin('h1'), /Neredeyse hazır/);
    assert.strictEqual(await sayfa.locator('.ozet-satir.tamam').count(), 4);
    assert.strictEqual(await sayfa.locator('.ozet-satir.atlandi').count(), 1);
    assert.match(await metin('[data-ozet="2"]'), /atlandı[\s\S]*Şimdi yap/);
    assert.match(await metin('[data-ozet="3"]'), /Yerel/);
    assert.match(await metin('[data-ozet="5"]'), /4 kare seçili/);
    await gor('adim-6-eksik.png', true);
    await sayfa.click('#simdi-yap-2');
    await sayfa.waitForSelector('#oku');
    assert.match(await metin('#ileri-2'), /Bitti, özete dön/);
    await sayfa.click('#oku');
    await sayfa.waitForSelector('#dogrula-2:not([hidden])');
    assert.match(await metin('#dogrula-2'), /7 yazı okudum\./);
    assert.strictEqual(await sayfa.locator('#okuma-katman .okuma-kutu').count(), 7);
    assert.match(await metin('#okunan-liste'), /Where were you last night\?/);
    await sayfa.waitForTimeout(1200);
    await gor('adim-2.png', true);
    adim('2. Yazı okuma ("Şimdi yap" ile): 7 yazı kutularla resimde ve listede ✓');
    await sayfa.click('#ileri-2');
    await sayfa.waitForSelector('#hazir-baslat');
    assert.match(await metin('h1'), /Her şey hazır/);
    assert.strictEqual(await sayfa.locator('.ozet-satir.tamam').count(), 5);
    await gor('adim-6.png', true);
    adim('6. Hazır: 5 adımın özeti yeşil, büyük Başlat');
    await sayfa.click('#hazir-baslat');

    // ================= ANA EKRAN =================
    await sayfa.waitForSelector('#izin-evet');
    assert.match(await metin('.pencere'), /Bu oyunun çevirilerini hatırlayayım mı\?/);
    await gor('v2-izin.png');
    await sayfa.click('#izin-evet');
    await sayfa.waitForFunction(() => /Durdur/.test(document.querySelector('#baslat-durdur').textContent));
    assert.strictEqual(st.ayarlar.hafiza_izni, true);
    assert.strictEqual(st.ayarlar.kurulum_tamam, true);
    adim('Başlat → izin penceresi: Evet → hafiza_izni=true, kurulum_tamam=true');
    // kurulum durumu: 5 adım, tıklayınca o adım yeniden
    assert.strictEqual(await sayfa.locator('#kurulum-durumu .kurulum-cip.tamam').count(), 5);
    await sayfa.click('#kurulum-adim-4');
    await sayfa.waitForSelector('[data-gosterim=bilgisayar]');
    assert.match(await metin('#ileri-4'), /Bitti, ana ekrana dön/);
    await sayfa.click('#vazgec-4');
    await sayfa.waitForSelector('#kurulum-durumu');
    adim('ana ekran: "Kurulum durumu" 5 ✓, bir adıma basınca o adım tek başına açılır, Vazgeç ile döner');
    // oyun seçimi (ana ekrandan): yeni oyun, paket, seç
    await sayfa.click('#oyun-degistir');
    await sayfa.waitForSelector('[data-oyun=gta6]');
    assert.match(await metin('h1'), /Hangi oyunu oynuyorsun/);
    assert.match(await metin('[data-oyun=gta6]'), /1\.240 cümle hatırlıyorum/);
    assert.ok(await sayfa.isDisabled('#ileri-oyun'));
    await sayfa.click('#yeni-oyun-ac');
    await sayfa.fill('#oyun-ad', 'Cyberpunk');
    await sayfa.fill('#oyun-acik', 'Fütüristik şehirde aksiyon');
    await sayfa.click('[data-hitap=siz]');
    await sayfa.click('#oyun-ekle');
    await sayfa.waitForSelector('[data-oyun=cyberpunk][aria-pressed=true]');
    assert.deepStrictEqual(JSON.parse(st.govdeler['POST /api/oyunlar']), { ad: 'Cyberpunk', aciklama: 'Fütüristik şehirde aksiyon', hitap: 'siz' });
    await sayfa.click('#paket-ac');
    await sayfa.setInputFiles('#paket-dosya', { name: 'rdr3.akpaket', mimeType: 'application/zip', buffer: Buffer.from('PKfake') });
    await sayfa.waitForFunction(() => /812 cümle eklendi/.test(document.querySelector('#paket-sonuc').textContent));
    assert.match(st.govdeler['POST /api/paket'], /name="dosya"/);
    await sayfa.waitForSelector('[data-oyun=rdr3][aria-pressed=true]');
    await sayfa.click('#ileri-oyun');
    await sayfa.waitForSelector('#aktif-oyun-ad');
    await sayfa.waitForFunction(() => /RDR 3/.test(document.querySelector('#aktif-oyun-ad').textContent));
    assert.strictEqual(st.ayarlar.aktif_oyun, 'rdr3');
    await sayfa.waitForFunction(() => /deneme altyazısı/.test(document.querySelector('#son-yazi').textContent), null, { timeout: 6000 });
    adim('oyun seçimi (ana ekrandan): yeni oyun (hitap: siz), çeviri paketi içe alındı, seçildi');
    // erişim satırı: kalan süre, kötü kod, iyi kod, sınır uyarısı
    await sayfa.waitForSelector('#erisim-metin');
    assert.match(await sayfa.textContent('#erisim-metin'), /Bugün kalan ücretsiz süre: 12 dk/);
    assert.ok(!(await sayfa.locator('#erisim-sinir').count()), 'sınır yokken uyarı görünmez');
    await sayfa.click('#kodum-var');
    await sayfa.fill('#erisim-kod', 'AK1-KOTU');
    await sayfa.click('#erisim-kaydet');
    await sayfa.waitForFunction(() => /Bu kod geçerli değil/.test((document.querySelector('#erisim-hata') || {}).textContent || ''));
    assert.strictEqual(await sayfa.inputValue('#erisim-kod'), 'AK1-KOTU', 'hatada yazı silinmez');
    await sayfa.waitForTimeout(2300);   // yoklama yazıyı bozmaz
    assert.strictEqual(await sayfa.inputValue('#erisim-kod'), 'AK1-KOTU');
    await gor('v4-erisim-hata.png');
    st.erisim = { kalan_dakika: 0, kod: null, bitis: null, ucretsiz_dakika: 30 }; st.sinir = true;
    await sayfa.waitForSelector('#erisim-sinir', { timeout: 6000 });
    assert.match(await sayfa.textContent('#erisim-sinir'), /Bugünkü ücretsiz süre doldu\. Erişim kodunu gir ya da yarın devam et\. Daha önce çevrilmiş cümleler gösterilmeye devam eder\./);
    assert.match(await sayfa.textContent('#erisim-metin'), /0 dk/);
    await gor('v4-erisim-sinir.png');
    await sayfa.fill('#erisim-kod', 'ak1-iyi');
    assert.strictEqual(await sayfa.inputValue('#erisim-kod'), 'ak1-iyi');
    await sayfa.fill('#erisim-kod', 'AK1-IYI');
    await sayfa.click('#erisim-kaydet');
    await sayfa.waitForFunction(() => /Sınırsız erişim açık ✓/.test(document.querySelector('#erisim-metin').textContent));
    assert.ok(!(await sayfa.locator('#erisim-sinir').count()), 'kod girilince uyarı kalkar');
    assert.ok(!(await sayfa.locator('#kodum-var').count()), 'kod açıkken "Kodum var" gizlenir');
    assert.deepStrictEqual(st.kodlar, ['AK1-KOTU', 'AK1-IYI']);
    await gor('v4-erisim-acik.png');
    adim('erişim: kalan dakika, yanlış kod dostça hata, süre dolunca sakin uyarı, doğru kod → "Sınırsız erişim açık ✓"');
    // son çeviriler + düzelt
    await sayfa.waitForSelector('.ceviri-satir[data-id=a1]', { timeout: 6000 });
    await sayfa.waitForSelector('#oneri-kart:not([hidden])');
    // kompakt "Son çeviriler": en çok 5 satır, kendi içinde kayan odaklanabilir bölge, "Tümünü göster" en çok 20
    const eskiCev = st.ceviriler.slice();
    for (let i = 0; i < 24; i++) st.ceviriler.push({ id: 'x' + i, asil: 'Line ' + i, ceviri: 'Satır ' + i, kaynak: 'motor' });
    await sayfa.waitForFunction(() => document.querySelectorAll('#son-liste .ceviri-satir').length === 5, null, { timeout: 8000 });
    assert.strictEqual(await sayfa.getAttribute('#son-liste', 'tabindex'), '0');
    assert.match(await sayfa.getAttribute('#son-liste', 'aria-label'), /Son çeviriler listesi/);
    assert.ok(await sayfa.evaluate(() => document.querySelector('#son-liste').getBoundingClientRect().height <= 321));
    assert.match(await metin('#son-tumu'), /Tümünü göster/);
    await sayfa.click('#son-tumu');
    assert.strictEqual(await sayfa.locator('#son-liste .ceviri-satir').count(), 20, 'en çok 20');
    assert.ok(await sayfa.evaluate(() => { const e = document.querySelector('#son-liste'); return e.scrollHeight > e.clientHeight && e.getBoundingClientRect().height <= 321; }), 'kart kendi içinde kayar');
    assert.strictEqual(await sayfa.getAttribute('#son-tumu', 'aria-expanded'), 'true');
    await sayfa.click('#son-tumu');
    assert.strictEqual(await sayfa.locator('#son-liste .ceviri-satir').count(), 5);
    st.ceviriler.length = 0; st.ceviriler.push(...eskiCev);
    await sayfa.waitForFunction(() => document.querySelectorAll('#son-liste .ceviri-satir').length === 2, null, { timeout: 8000 });
    await sayfa.waitForSelector('#son-tumu', { state: 'hidden' });
    await sayfa.waitForSelector('#guncelleme-bar #guncelle-dugme', { timeout: 8000 });
    assert.match(await sayfa.textContent('#guncelleme-bar'), /Yeni sürüm hazır \(0\.3\.0\)\./);
    await gor('v3-guncelleme.png');
    await sayfa.click('#guncelle-dugme');
    await sayfa.waitForFunction(() => /indiriliyor/.test(document.querySelector('#guncelleme-metin').textContent));
    assert.ok(await sayfa.locator('#guncelleme-bar [role=progressbar]').count());
    await sayfa.waitForFunction(() => /Program kendini yeniden başlatacak\./.test(document.querySelector('#guncelleme-metin').textContent), null, { timeout: 8000 });
    assert.strictEqual(await sayfa.getAttribute('#guncelleme-bar [role=progressbar]', 'aria-valuenow'), '100');
    assert.ok(st.istekler.includes('POST /api/guncelleme/kur'));
    adim('güncelleme çubuğu: Yeni sürüm hazır → Güncelle → ilerleme → "Program kendini yeniden başlatacak."');

    // bölge kartı (ana ekran): özet, "Çevrilecek yerleri düzenle" → 5. adım tek başına → otomatiğe dön
    assert.match(await sayfa.textContent('#bolge-ozet'), /4 kare seçili/);
    await sayfa.click('#bolge-ac');
    await sayfa.waitForSelector('#bolge-sahne:not([hidden])');
    assert.strictEqual(await sayfa.locator('.bolge').count(), 4);
    assert.ok(await sayfa.isHidden('#bolge-ipucu'), 'ipucu yalnız ilk sefer');
    assert.ok(await sayfa.isChecked('#bolge-hedef-0-kendim') && await sayfa.isChecked('#bolge-hedef-2-altyazi') && await sayfa.isChecked('#bolge-hedef-1-ustune'), 'kayıtlı hedefler geri gelir');
    assert.strictEqual(await sayfa.inputValue('#bolge-olcek-0'), '80');
    assert.strictEqual(await sayfa.locator('.bolge-hedef').count(), 1);
    await sayfa.click('#bolge-otomatik');
    await sayfa.waitForSelector('#dogrula-5:not([hidden])');
    assert.match(await sayfa.textContent('#dogrula-5'), /Otomatik: ekrandaki yazıları kendim bulacağım\./);
    assert.deepStrictEqual(st.bolgePostlari[st.bolgePostlari.length - 1], []);
    assert.strictEqual(await sayfa.locator('.bolge').count(), 0);
    await sayfa.click('#ileri-5');
    await sayfa.waitForSelector('#bolge-ozet');
    assert.match(await sayfa.textContent('#bolge-ozet'), /Şimdi otomatik/);
    adim('ana ekran: "Çevrilecek yerleri düzenle" 5. adımı açtı, "Otomatik bulsun" bölgeleri temizledi, ana ekrana dönüldü');
    await gor('v2-ana.png');
    await sayfa.click('[data-id=a1] .duzelt');
    await sayfa.fill('[data-id=a1] .duzelt-girdi', 'Dün gece neredeydin sen?');
    await sayfa.click('[data-id=a1] .duzelt-kaydet');
    await sayfa.waitForSelector('.tost:has-text("bundan sonra hep böyle")');
    assert.deepStrictEqual(JSON.parse(st.govdeler['POST /api/duzelt']), { asil: 'Where were you last night?', ceviri: 'Dün gece neredeydin sen?' });
    assert.match(await sayfa.textContent('[data-id=a1]'), /neredeydin sen/);
    adim('son çeviriler görünür, Düzelt doğru gövdeyi gönderdi');
    // öneri kabul
    await sayfa.click('[data-oneri="Vice City"] .kabul');
    await sayfa.waitForSelector('#oneri-kart[hidden]', { state: 'attached' });
    assert.deepStrictEqual(JSON.parse(st.govdeler['POST /api/oneriler']), { asil: 'Vice City', kabul: true });
    adim('öneri kabul edildi');
    // Türkçe dublaj kartı (PROTOKOL 9)
    await sayfa.waitForSelector('#dublaj-kart #dublaj-motor-pocket');
    assert.match(await sayfa.textContent('#dublaj-kart h2'), /Türkçe dublaj \(deneysel\)/);
    assert.match(await sayfa.textContent('#dublaj-ne'), /Karakterler kendi sesleriyle Türkçe konuşur\. Sadece oyunun sesi dinlenir, mikrofon açılmaz, hiçbir ses kaydedilmez\./);
    assert.match(await sayfa.textContent('#dublaj-motor-chatterbox'), /Bilgisayarın için önerilen/);
    assert.match(await sayfa.textContent('#dublaj-motor-chatterbox'), /En iyi kalite, güçlü ekran kartı ister/);
    assert.doesNotMatch(await sayfa.textContent('#dublaj-motor-pocket'), /önerilen/);
    assert.match(await sayfa.textContent('#dublaj-motor-pocket'), /Her bilgisayarda çalışır, kalite biraz daha düşük/);
    assert.match(await sayfa.textContent('#dublaj-motor-elevenlabs'), /En doğal, ücretli; ses örneği ElevenLabs'e gider/);
    assert.match(await sayfa.textContent('#dublaj-donanim'), /NVIDIA GeForce RTX 3060/);
    assert.strictEqual(await sayfa.locator('#dublaj-hazirla').count(), 0, 'kapalıyken hazırlık düğmesi yok');
    adim('dublaj kartı: açıklama, öneri rozeti (donanımdan) ve dürüst notlar görünür');
    await sayfa.click('#dublaj-motor-pocket');
    await sayfa.waitForSelector('#dublaj-hazirla');
    assert.strictEqual(st.ayarlar.dublaj.motor, 'pocket');
    assert.ok(await sayfa.isDisabled('#dublaj-dene'), 'hazır olmadan Dene kapalı');
    await sayfa.click('#dublaj-hazirla');
    await sayfa.waitForFunction(() => /İndiriliyor… %/.test((document.querySelector('#dublaj-durum') || {}).textContent || ''));
    await sayfa.waitForFunction(() => /Hazır ✓/.test((document.querySelector('#dublaj-durum') || {}).textContent || ''), null, { timeout: 9000 });
    assert.ok(st.istekler.includes('POST /api/dublaj/hazirla'));
    adim('dublaj: Hazırla indirme ilerlemesini gösterdi ve "Hazır ✓" oldu');
    await sayfa.click('#dublaj-dene');
    await sayfa.waitForSelector('.tost:has-text("Örnek ses çalındı")');
    assert.deepStrictEqual(st.dublajDene, ['Merhaba, nasılsın?']);
    await sayfa.evaluate(() => { const k = document.querySelector('#dublaj-kis'); k.value = 50; k.dispatchEvent(new Event('input')); const v = document.querySelector('#dublaj-seviye'); v.value = 150; v.dispatchEvent(new Event('input')); });
    await sayfa.waitForFunction(() => /%50/.test(document.querySelector('#dublaj-kis-deger').textContent));
    await sayfa.waitForTimeout(500);
    assert.strictEqual(st.ayarlar.dublaj.oyun_sesi_kis, 0.5);
    assert.strictEqual(st.ayarlar.dublaj.ses_seviyesi, 1.5);
    await sayfa.click('#dublaj-cikis-tv');
    await sayfa.waitForFunction(() => document.querySelector('#dublaj-cikis-tv').getAttribute('aria-pressed') === 'true');
    assert.strictEqual(st.ayarlar.dublaj.cikis, 'tv');
    adim('dublaj: Dene, oyun sesini kıs / dublaj seviyesi kaydırıcıları ve çıkış (TV) kaydedildi');
    await sayfa.click('#dublaj-motor-elevenlabs');
    await sayfa.waitForSelector('#dublaj-eleven');
    assert.strictEqual(st.ayarlar.dublaj.motor, 'pocket', 'onaysız ElevenLabs seçilmemeli');
    assert.strictEqual(await sayfa.locator('#dublaj-eleven-klon').count(), 0, 'ikinci onay, birincisi olmadan görünmez');
    await sayfa.fill('#dublaj-eleven-anahtar', 'xi-GIZLI');
    await sayfa.click('#dublaj-eleven-kaydet');
    await sayfa.waitForFunction(() => document.querySelector('#dublaj-eleven-anahtar').placeholder.indexOf('Anahtar kayıtlı') === 0);
    assert.strictEqual(st.anahtarlar.elevenlabs, 'xi-GIZLI');
    await sayfa.click('#dublaj-eleven-onay', { force: true });
    await sayfa.waitForSelector('#dublaj-eleven-klon', { state: 'attached' });
    assert.strictEqual(st.ayarlar.dublaj.motor, 'elevenlabs'); assert.strictEqual(st.ayarlar.dublaj.elevenlabs_onay, true); assert.strictEqual(st.ayarlar.dublaj.elevenlabs_klon_onay, false);
    await sayfa.click('#dublaj-eleven-klon', { force: true });
    await sayfa.waitForFunction(() => document.querySelector('#dublaj-eleven-klon').checked);
    await sayfa.waitForTimeout(100);
    assert.strictEqual(st.ayarlar.dublaj.elevenlabs_klon_onay, true);
    await sayfa.waitForTimeout(400);   // kaydın ardından kart yeniden çizilir
    await sayfa.click('#dublaj-eleven-onay', { force: true });
    await sayfa.waitForFunction(() => !document.querySelector('#dublaj-eleven-klon'));
    assert.strictEqual(st.ayarlar.dublaj.motor, 'kapali'); assert.strictEqual(st.ayarlar.dublaj.elevenlabs_klon_onay, false);
    await gor('3-dublaj.png');
    adim('dublaj: ElevenLabs ancak onayla seçilir; ikinci onay ayrıdır; onay geri alınınca motor kapanır');
    // gelişmiş ayarlar
    await sayfa.click('#gelismis > summary');
    assert.match(await sayfa.getAttribute('#paket-paylas', 'href'), /\/api\/paket\/rdr3$/);
    assert.strictEqual(await sayfa.inputValue('#tv-ip'), '192.168.1.30', 'IP hatırlanır');
    assert.strictEqual(await sayfa.locator('#gelismis #tv-kart').count(), 1);
    await sayfa.click('#guncelleme-denetle-ayar', { force: true });
    await sayfa.waitForTimeout(150);
    assert.strictEqual(st.ayarlar.guncelleme_denetle, false);
    await sayfa.click('#guncelleme-denetle');
    await sayfa.waitForFunction(() => /Yeni sürüm var: 0\.3\.0/.test(document.querySelector('#guncelleme-durum').textContent));
    assert.ok(st.istekler.includes('POST /api/guncelleme/denetle'));
    adim('ayarlar: güncelleme anahtarı kapandı, "Güncellemeleri denetle" çalıştı, TV kartı ayarlarda');
    await sayfa.click('#kalite-ayar-hizli');
    await sayfa.waitForTimeout(150);
    assert.strictEqual(st.ayarlar.kalite, 'hizli');
    await sayfa.click('#hafiza-sil');
    await sayfa.click('#sil-evet');
    await sayfa.waitForFunction(() => /Hafıza silindi/.test(document.body.textContent));
    assert.ok(st.silindi);
    await sayfa.fill('#ekran-olcek-ayar', '120');
    await sayfa.waitForTimeout(500);
    assert.strictEqual(st.ayarlar.gorunum.ekran_olcek, 1.2, 'ayarlarda ekran ölçeği kaydedildi');
    adim('ayarlarda kalite, paylaş bağlantısı ve hafıza silme çalıştı');
    await sayfa.click('#ses-cevir', { force: true });
    await sayfa.waitForSelector('#ses-not:not([hidden])');
    assert.strictEqual(st.ayarlar.ses_cevir, true);
    await sayfa.selectOption('#hedef-dil', 'de');
    await sayfa.waitForTimeout(200);
    assert.strictEqual(st.ayarlar.hedef_dil, 'de');
    adim('ana ekran: başlat, durum, son yazı, ses onayı, hedef dil');
    await sayfa.click('#sozluk-kaydet');
    await sayfa.waitForFunction(() => /Kaydedildi/.test(document.querySelector('#sozluk-durum').textContent));
    await gor('4-ana.png');

    await sayfa.click('[data-dil=en]');
    await sayfa.waitForFunction(() => /Stop/.test(document.querySelector('#baslat-durdur').textContent));
    await sayfa.waitForTimeout(200);
    assert.strictEqual(st.ayarlar.arayuz_dili, 'en');
    assert.match(await sayfa.textContent('body'), /Also translate other on-screen text/);
    assert.match(await sayfa.textContent('#erisim-metin'), /Unlimited access is on ✓/);
    assert.match(await sayfa.textContent('#guncelleme-metin'), /The program will restart by itself\./);
    assert.match(await sayfa.textContent('#tv-kart h2'), /Install on the TV in one click/);
    assert.match(await sayfa.textContent('#dublaj-kart h2'), /Turkish dubbing \(experimental\)/);
    assert.match(await sayfa.textContent('#dublaj-ne'), /Characters speak Turkish in their own voices\. Only the game's sound is listened to, the microphone is never turned on, and no audio is recorded\./);
    await gor('5-ana-en.png');
    adim('EN diline geçildi ve ayar kaydedildi');

    // güncelleme hata verirse (ör. doğrulanamadı) mesaj ve "Try again" görünür
    st.guncelleme = { asama: 'hata', ilerleme: 0, sayac: 0, mesaj: 'The downloaded file could not be verified and was not installed, please try again later.' };
    await sayfa.waitForFunction(() => /could not be verified/.test((document.querySelector('#guncelleme-metin') || {}).textContent || ''), null, { timeout: 6000 });
    assert.match(await sayfa.textContent('#guncelle-dugme'), /Try again/);
    adim('güncelleme hatası mesajla ve "Tekrar dene" ile gösterildi');

    // API kapanınca dostça uyarı
    sunucu.closeAllConnections && sunucu.closeAllConnections();
    await new Promise((r) => sunucu.close(r));
    await sayfa.waitForSelector('#afis:not([hidden])', { timeout: 6000 });
    assert.match(await sayfa.textContent('#afis'), /seems to be closed/);
    adim('API kapalıyken "program kapalı" uyarısı görüldü');

    const beklenen = hatalar.filter((h) => !/Failed to load resource|ERR_CONNECTION|ERR_EMPTY|ERR_FAILED/.test(h));
    assert.deepStrictEqual(beklenen, [], 'konsol hataları: ' + beklenen.join(' | '));
    adim('konsolda hata yok');
    console.log('TÜM TESTLER GEÇTİ');
  } catch (e) {
    console.error('TEST BAŞARISIZ:', e.message);
    if (SHOTS) await sayfa.screenshot({ path: path.join(SHOTS, 'hata.png') }).catch(() => {});
    process.exitCode = 1;
  } finally {
    await tarayici.close();
    sunucu.close();
  }
})();
