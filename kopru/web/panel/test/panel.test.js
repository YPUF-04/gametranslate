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
const TURLER = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json' };


// küçük, örnek bir oyun karesi (PNG): gradyan + altyazı şeridi — sahte /api/kare yanıtı
function ornekPng(w, h) {
  const satir = (y) => { const b = Buffer.alloc(1 + w * 3); for (let x = 0; x < w; x++) { const alt = y > h * 0.72 && y < h * 0.9 && x > w * 0.12 && x < w * 0.88; b[1 + x * 3] = alt ? 240 : 30 + (x * 60) / w; b[2 + x * 3] = alt ? 240 : 60 + (y * 80) / h; b[3 + x * 3] = alt ? 240 : 110; } return b; };
  const ham = Buffer.concat(Array.from({ length: h }, (_, y) => satir(y)));
  const crcT = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  const crc = (buf) => { let c = 0xffffffff; for (const x of buf) c = crcT[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const parca = (ad, veri) => { const u = Buffer.alloc(4); u.writeUInt32BE(veri.length); const t = Buffer.concat([Buffer.from(ad), veri]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(t)); return Buffer.concat([u, t, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), parca('IHDR', ihdr), parca('IDAT', zlib.deflateSync(ham)), parca('IEND', Buffer.alloc(0))]);
}

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
      switch (q.method + ' ' + url.pathname) {
        case 'GET /api/durum':
          return j({ calisiyor: st.calisiyor, motor: st.ayarlar.motor, yedekte: false, tv_sayisi: st.calisiyor ? 1 : 0,
            son_yazi: st.calisiyor || st.sonYazi ? (st.sonYazi || 'Ana kampa dön') : '', adresler: ['192.168.1.20'], kapi: 8642, sinir: st.sinir });
        case 'GET /api/ayarlar': return j(Object.assign({ claude: false, gemini: !!st.anahtarlar.gemini }, st.ayarlar));
        case 'POST /api/ayarlar': if (b.bolgeler) st.bolgePostlari.push(b.bolgeler); Object.assign(st.ayarlar, b); return j({ tamam: true });
        case 'GET /api/kare': st.kareIstekleri++; if (st.kareHata) return j({ hata: 'yakalama_yok', mesaj: 'Ekran görüntüsü alınamadı, ekran kaynağını ve izinleri kontrol edin.' }, 400); s.writeHead(200, { 'Content-Type': 'image/png', 'Cache-Control': 'no-store' }); return s.end(ornekPng(320, 180));
        case 'GET /api/erisim': return j(st.erisim);
        case 'POST /api/erisim':
          st.kodlar.push(b.kod);
          if (b.kod === 'AK1-IYI') { st.erisim = { kalan_dakika: 0, kod: 'sinirsiz', bitis: null, ucretsiz_dakika: 30 }; st.sinir = false; return j({ tamam: true, tur: 'sinirsiz' }); }
          return j({ hata: 'gecersiz_kod', mesaj: 'Bu kod geçerli değil. Harfleri kontrol edip tekrar deneyin.' }, 400);
        case 'GET /api/motorlar': return j(motorlar());
        case 'POST /api/anahtar': st.anahtarlar[b.motor] = b.anahtar; return j({ tamam: true });
        case 'POST /api/dene':
          if (b.motor === 'gemini' && !st.anahtarlar.gemini) return j({ hata: 'anahtar_yok', mesaj: 'Anahtar bulunamadı. Anahtarı yapıştırıp tekrar dene.' }, 400);
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
  const gor = async (ad) => { if (SHOTS) await sayfa.screenshot({ path: path.join(SHOTS, ad), fullPage: !!process.env.FULL }); };
  const adim = (s) => console.log('  ok -', s);

  try {
    await sayfa.goto(taban + '/');
    await sayfa.waitForSelector('h1');
    assert.match(await sayfa.textContent('h1'), /Oyunu nereden oynuyorsun/);
    adim('sihirbaz adım 1 açıldı (TR)');

    await sayfa.click('[data-cihaz=ps5]');
    assert.match(await sayfa.textContent('#kaynak-ipucu'), /PS Remote Play/);
    await sayfa.click('[data-kaynak="pencere:123"]');
    await sayfa.click('[data-tv=lg]');
    await gor('1-adim1.png');

    // bölge editörü (sihirbaz): kare çiz, tür seç, klavye ile taşı, kaydet
    await sayfa.waitForSelector('#bolge-kart:not([hidden])');
    await sayfa.click('#bolge-ac');
    await sayfa.waitForSelector('#bolge-sahne:not([hidden])');
    assert.match(await sayfa.textContent('#bolge-ne'), /Çevirmemi istediğin yerleri kare içine al\. En fazla 3 kare\. Sadece bu kareleri okurum, ekranın geri kalanına dokunmam\./);
    assert.ok(st.kareIstekleri >= 1);
    await sayfa.evaluate(() => document.querySelector('#bolge-sahne').scrollIntoView({ block: 'start', behavior: 'instant' }));
    await sayfa.waitForTimeout(100);
    let kb = await sayfa.locator('#bolge-katman').boundingBox();
    const fare = async (ax, ay, bx, by) => {
      kb = await sayfa.locator('#bolge-katman').boundingBox();
      await sayfa.mouse.move(kb.x + kb.width * ax, kb.y + kb.height * ay);
      await sayfa.mouse.down();
      await sayfa.mouse.move(kb.x + kb.width * ((ax + bx) / 2), kb.y + kb.height * ((ay + by) / 2), { steps: 3 });
      await sayfa.mouse.move(kb.x + kb.width * bx, kb.y + kb.height * by, { steps: 3 });
      await sayfa.mouse.up();
    };
    await fare(0.1, 0.7, 0.9, 0.9);          // altyazı kutusu
    await fare(0.02, 0.03, 0.4, 0.15);       // üstteki yazılar
    assert.strictEqual(await sayfa.locator('.bolge').count(), 2);
    await sayfa.selectOption('#bolge-tur-1', 'ust_yazi');
    assert.strictEqual(await sayfa.inputValue('#bolge-tur-0'), 'altyazi');
    assert.match(await sayfa.getAttribute('.bolge[data-bolge="0"]', 'aria-label'), /Kare 1: Altyazı/);
    assert.match(await sayfa.textContent('#bolge-satirlar'), /Üstteki yazılar \(görev, bilgi\)/);
    // üçüncü ve dördüncü kare: en çok 3
    await fare(0.5, 0.2, 0.7, 0.3);
    assert.strictEqual(await sayfa.locator('.bolge').count(), 3);
    await fare(0.5, 0.4, 0.7, 0.5);
    assert.strictEqual(await sayfa.locator('.bolge').count(), 3, '4. kare çizilemez');
    assert.ok(await sayfa.isVisible('#bolge-dolu'));
    await sayfa.click('[data-sil="2"]');      // × ile sil
    assert.strictEqual(await sayfa.locator('.bolge').count(), 2);
    // köşeden boyutlandır: 2. kutunun sağ-alt köşesini sürükle
    kb = await sayfa.locator('#bolge-katman').boundingBox();
    const k2 = await sayfa.locator('.bolge[data-bolge="1"] .tutamac.se').boundingBox();
    await sayfa.mouse.move(k2.x + k2.width / 2, k2.y + k2.height / 2); await sayfa.mouse.down();
    await sayfa.mouse.move(kb.x + kb.width * 0.5, kb.y + kb.height * 0.2, { steps: 4 }); await sayfa.mouse.up();
    // klavye: 1. kutuyu 3 adım sağa taşı, 1 adım yukarı, Shift+Aşağı ile 1 adım yüksel
    await sayfa.focus('.bolge[data-bolge="0"]');
    for (let i = 0; i < 3; i++) await sayfa.keyboard.press('ArrowRight');
    await sayfa.keyboard.press('ArrowUp');
    await sayfa.keyboard.press('Shift+ArrowDown');
    await gor('v3-bolge-kaydirma.png');
    await sayfa.click('#bolge-kaydet');
    await sayfa.waitForFunction(() => document.querySelector('.tost'));
    const kayit = st.bolgePostlari[st.bolgePostlari.length - 1];
    assert.strictEqual(kayit.length, 2);
    const yakin = (a, b, ne) => assert.ok(Math.abs(a - b) < 0.006, ne + ': ' + a + ' ≠ ' + b);
    // 1. kutu: çizilen (0.1, 0.7, 0.8, 0.2) → x +0.03, y -0.01, y2 +0.01
    yakin(kayit[0].x, 0.13, 'x'); yakin(kayit[0].y, 0.69, 'y'); yakin(kayit[0].g, 0.8, 'g'); yakin(kayit[0].y2, 0.21, 'y2');
    assert.strictEqual(kayit[0].tur, 'altyazi'); assert.strictEqual(kayit[0].ad, 'Altyazı');
    // 2. kutu: sol-üst (0.02,0.03) sabit, sağ-alt (0.5,0.2)
    yakin(kayit[1].x, 0.02, 'x2'); yakin(kayit[1].y, 0.03, 'y2'); yakin(kayit[1].g, 0.48, 'g2'); yakin(kayit[1].y2, 0.17, 'y22');
    assert.strictEqual(kayit[1].tur, 'ust_yazi'); assert.strictEqual(kayit[1].ad, 'Üst yazılar');
    for (const b of kayit) { assert.ok(b.x >= 0 && b.y >= 0 && b.x + b.g <= 1.0001 && b.y + b.y2 <= 1.0001); assert.deepStrictEqual(Object.keys(b).sort(), ['ad', 'g', 'tur', 'x', 'y', 'y2']); }
    adim('bölge editörü (sihirbaz): 2 kare çizildi, tür seçildi, en çok 3 sınırı, köşeden boyutlandı, klavye ile taşındı, normalize JSON gönderildi');
    // Delete tuşu ile silme + geri alınamaz değil: yeniden çiz
    await sayfa.focus('.bolge[data-bolge="1"]'); await sayfa.keyboard.press('Delete');
    assert.strictEqual(await sayfa.locator('.bolge').count(), 1);
    await fare(0.02, 0.03, 0.4, 0.15); await sayfa.selectOption('#bolge-tur-1', 'ust_yazi');
    await sayfa.click('#bolge-kaydet');
    await sayfa.waitForFunction(() => document.querySelectorAll('.tost').length >= 2);
    assert.strictEqual(st.bolgePostlari[st.bolgePostlari.length - 1].length, 2);
    adim('Delete tuşu kareyi sildi, yeniden çizilip kaydedildi');
    // kare alınamazsa dostça mesaj
    st.kareHata = true; await sayfa.click('#bolge-yenile');
    await sayfa.waitForSelector('#bolge-mesaj.kotu');
    assert.match(await sayfa.textContent('#bolge-mesaj'), /Ekran görüntüsü alınamadı/);
    st.kareHata = false; await sayfa.click('#bolge-yenile'); await sayfa.waitForSelector('#bolge-sahne:not([hidden])');
    assert.strictEqual(await sayfa.locator('.bolge').count(), 2, 'yenileyince kareler kaybolmaz');
    await sayfa.evaluate(() => document.querySelector('#bolge-sahne').scrollIntoView({ block: 'center', behavior: 'instant' }));
    await gor('v3-bolge.png');
    adim('görüntü yenilenince kareler korunur, hata dostça gösterilir');
    await sayfa.click('#ileri1');
    adim('PS5 + kaynak + LG seçildi');

    // oyun adımı
    await sayfa.waitForSelector('[data-oyun=gta6]');
    assert.match(await sayfa.textContent('h1'), /Hangi oyunu oynuyorsun/);
    assert.match(await sayfa.textContent('[data-oyun=gta6]'), /1\.240 cümle hatırlıyorum/);
    assert.ok(await sayfa.isDisabled('#ileri-oyun'));
    await gor('v2-oyun-adimi.png');
    await sayfa.click('#yeni-oyun-ac');
    await sayfa.fill('#oyun-ad', 'Cyberpunk');
    await sayfa.fill('#oyun-acik', 'Fütüristik şehirde aksiyon');
    await sayfa.click('[data-hitap=siz]');
    await sayfa.click('#oyun-ekle');
    await sayfa.waitForSelector('[data-oyun=cyberpunk][aria-pressed=true]');
    assert.deepStrictEqual(JSON.parse(st.govdeler['POST /api/oyunlar']), { ad: 'Cyberpunk', aciklama: 'Fütüristik şehirde aksiyon', hitap: 'siz' });
    adim('yeni oyun eklendi (hitap: siz)');
    await sayfa.click('#paket-ac');
    await sayfa.setInputFiles('#paket-dosya', { name: 'rdr3.akpaket', mimeType: 'application/zip', buffer: Buffer.from('PKfake') });
    await sayfa.waitForFunction(() => /812 cümle eklendi/.test(document.querySelector('#paket-sonuc').textContent));
    assert.match(st.govdeler['POST /api/paket'], /name="dosya"/);
    await sayfa.waitForSelector('[data-oyun=rdr3][aria-pressed=true]');
    await gor('v2-oyun-adimi-paket.png');
    await sayfa.click('#ileri-oyun');
    adim('çeviri paketi içe alındı, oyun seçildi');

    await sayfa.waitForSelector('[data-motor=gemini]');
    await sayfa.click('[data-motor=claude]');
    assert.match(await sayfa.textContent('#motor-detay'), /Pro\/Max/);
    await sayfa.click('[data-motor=gemini]');
    await sayfa.click('#kalite-wiz-dengeli');
    await sayfa.waitForTimeout(150);
    assert.strictEqual(st.ayarlar.kalite, 'dengeli');
    adim('kalite seçimi kaydedildi');
    await gor('2-adim2.png');
    assert.ok(await sayfa.isDisabled('#ileri2'));
    await sayfa.click('#kaydet-dene'); // anahtarsız → dostça hata
    await sayfa.waitForSelector('.sonuc.kotu');
    await sayfa.fill('#anahtar-gir', 'AIzaSAHTE-ANAHTAR');
    await sayfa.click('#kaydet-dene');
    await sayfa.waitForSelector('.sonuc:not(.kotu)');
    assert.match(await sayfa.textContent('#dene-sonuc'), /Merhaba, nasılsın\?/);
    assert.strictEqual(st.anahtarlar.gemini, 'AIzaSAHTE-ANAHTAR');
    adim('Gemini anahtarı kaydedildi, çeviri denemesi çalıştı');
    await sayfa.click('#ileri2');

    await sayfa.waitForSelector('#deneme-yazi');
    assert.match(await sayfa.textContent('#adres-kutu'), /192\.168\.1\.20:8642\/tv/);
    // TV'ye tek tuşla kur kartı (LG seçili)
    await sayfa.waitForSelector('#tv-kart');
    assert.strictEqual(await sayfa.locator('#tv-kart > ol:not(.tv-asamalar) > li').count(), 3);
    assert.match(await sayfa.textContent('#tv-kart > ol:not(.tv-asamalar)'), /Developer Mode uygulamasını aç[\s\S]*IP adresini ve ekrandaki kodu \(Passphrase\)[\s\S]*Kur'a bas/);
    await sayfa.click('#tv-kur');
    assert.match(await sayfa.textContent('#tv-hata'), /IP adresini ve ekrandaki kodu yaz/);
    await sayfa.fill('#tv-ip', '192.168.1.30');
    await sayfa.fill('#tv-parola', 'BAD000');
    await sayfa.click('#tv-kur');
    await sayfa.waitForSelector('#tv-hata-mesaj', { timeout: 6000 });
    assert.match(await sayfa.textContent('#tv-hata-mesaj'), /Kod yanlış görünüyor/);
    assert.ok(!(await sayfa.isVisible('#tv-ayrinti')), 'ham metin kapalı gelmeli');
    await sayfa.click('#tv-ayrinti-kap > summary');
    assert.match(await sayfa.textContent('#tv-ayrinti'), /Anahtar bu kodla açılamadı/);
    await gor('v3-tv-hata.png');
    assert.deepStrictEqual(st.tvIstekleri[0], { ip: '192.168.1.30', parola: 'BAD000', paket: 'asil' });
    await sayfa.click('#tv-acgsiz');
    await sayfa.waitForFunction(() => !document.querySelector('#tv-acgsiz') && document.querySelector('#tv-hata-mesaj'), null, { timeout: 6000 });
    assert.strictEqual(st.tvIstekleri[1].paket, 'acgsiz');
    adim('TV kartı: boş alan uyarısı, yanlış kod dostça hata, ayrıntı aç/kapa, başka sürüm denemesi');
    assert.ok(!(await sayfa.locator('#tv-acgsiz').count()), 'acgsiz denemesinden sonra tekrar önerilmez');
    await sayfa.fill('#tv-parola', 'GOOD12');
    await sayfa.click('#tv-deneme');
    await sayfa.waitForSelector('#tv-bitti', { timeout: 8000 });
    assert.strictEqual(st.tvIstekleri[2].paket, 'deneme');
    assert.strictEqual(await sayfa.locator('#tv-asamalar li.bitti').count(), 5);
    assert.strictEqual(await sayfa.inputValue('#tv-parola'), '', 'kod başarıdan sonra silinir');
    assert.match(await sayfa.textContent('#tv-bitti'), /Kuruldu/);
    await gor('v3-tv-bitti.png');
    assert.ok(!JSON.stringify(await sayfa.evaluate(() => Object.assign({}, localStorage))).match(/BAD000|GOOD12/), 'kod tarayıcıda saklanmaz');
    adim('TV kartı: deneme uygulaması aşamaları (anahtar→…→bitti), kod saklanmadı');
    await sayfa.click('#deneme-yazi');
    await sayfa.waitForSelector('#hayir');
    await sayfa.click('#hayir');
    await sayfa.waitForSelector('#sorun-kutu:not([hidden])');
    await gor('3-adim3.png');
    assert.ok(st.istekler.includes('POST /api/deneme-yazi'));
    adim('deneme altyazısı gönderildi, sorun giderme listesi göründü');
    await sayfa.click('#evet');

    await sayfa.waitForSelector('#baslat-durdur');
    await sayfa.waitForFunction(() => /Başlat/.test(document.querySelector('#baslat-durdur').textContent));
    await sayfa.click('#baslat-durdur');
    await sayfa.waitForSelector('#izin-evet');
    assert.match(await sayfa.textContent('.pencere'), /Bu oyunun çevirilerini hatırlayayım mı\?/);
    await gor('v2-izin.png');
    await sayfa.click('#izin-evet');
    await sayfa.waitForFunction(() => /Durdur/.test(document.querySelector('#baslat-durdur').textContent));
    await sayfa.waitForFunction(() => /deneme altyazısı/.test(document.querySelector('#son-yazi').textContent), null, { timeout: 6000 });
    assert.strictEqual(st.ayarlar.hafiza_izni, true);
    assert.strictEqual(st.ayarlar.aktif_oyun, 'rdr3');
    assert.match(await sayfa.textContent('#aktif-oyun-ad'), /RDR 3/);
    adim('izin penceresi: Evet → hafiza_izni=true kaydedildi');
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

    // bölge kartı (ana ekran): özet, düzenle, otomatiğe dön
    assert.match(await sayfa.textContent('#bolge-ozet'), /2 kare seçili/);
    await sayfa.click('#bolge-ac');
    await sayfa.waitForSelector('#bolge-sahne:not([hidden])');
    assert.strictEqual(await sayfa.locator('.bolge').count(), 2);
    await sayfa.click('#bolge-otomatik');
    await sayfa.waitForFunction(() => /Şimdi otomatik/.test(document.querySelector('#bolge-ozet').textContent));
    assert.deepStrictEqual(st.bolgePostlari[st.bolgePostlari.length - 1], []);
    assert.strictEqual(await sayfa.locator('.bolge').count(), 0);
    adim('ana ekran: "Neyi çevireceğimi seç" kartı kareleri gösterdi, "Otomatik bulsun" bölgeleri temizledi');
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
