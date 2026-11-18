/* Panel uçtan uca testi. Çalıştır: node kopru/web/panel/test/panel.test.js
   Sahte bir /api/* sunucusu (PROTOKOL.md sözleşmesi) ile sihirbazı baştan sona gezer. */
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { chromium } = require('playwright');

const PANEL = path.join(__dirname, '..');
const SHOTS = process.env.SHOTS_DIR || '';
const TURLER = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json' };

function sahteSunucu() {
  const st = {
    ayarlar: { arayuz_dili: 'tr', hedef_dil: 'tr', motor: 'gemini', yedek_motor: 'yerel', kaynak: 'ekran:1', ekrani_cevir: true,
      kisa_aciklama: true, ses_cevir: false, kapi: 8642, modeller: { gemini: 'gemini-2.5-flash' },
      gorunum: { yazi_boyutu: 44, konum: 'alt', arka_plan: 0.55 } },
    calisiyor: false, anahtarlar: {}, istekler: [], sozluk: { oyun: 'varsayilan', terimler: [{ asil: 'Ellie', ceviri: 'Ellie' }] }
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
      if (url.pathname.startsWith('/api/')) st.istekler.push(q.method + ' ' + url.pathname);
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
            son_yazi: st.calisiyor || st.sonYazi ? (st.sonYazi || 'Ana kampa dön') : '', adresler: ['192.168.1.20'], kapi: 8642 });
        case 'GET /api/ayarlar': return j(Object.assign({ claude: false, gemini: !!st.anahtarlar.gemini }, st.ayarlar));
        case 'POST /api/ayarlar': Object.assign(st.ayarlar, b); return j({ tamam: true });
        case 'GET /api/motorlar': return j(motorlar());
        case 'POST /api/anahtar': st.anahtarlar[b.motor] = b.anahtar; return j({ tamam: true });
        case 'POST /api/dene':
          if (b.motor === 'gemini' && !st.anahtarlar.gemini) return j({ hata: 'anahtar_yok', mesaj: 'Anahtar bulunamadı. Anahtarı yapıştırıp tekrar dene.' }, 400);
          return j({ ceviri: 'Merhaba, nasılsın?', sure_ms: 640 });
        case 'POST /api/baslat': st.calisiyor = true; return j({ tamam: true });
        case 'POST /api/durdur': st.calisiyor = false; return j({ tamam: true });
        case 'POST /api/deneme-yazi': st.sonYazi = 'Merhaba, bu bir deneme altyazısı'; return j({ tamam: true });
        case 'GET /api/kaynaklar': return j([{ kod: 'ekran:1', ad: 'Ekran 1 (1920×1080)' }, { kod: 'pencere:123', ad: 'PS Remote Play' }]);
        case 'GET /api/sozluk': return j(st.sozluk);
        case 'POST /api/sozluk': st.sozluk = b; return j({ tamam: true });
      }
      j({ hata: 'yok', mesaj: 'Bulunamadı.' }, 404);
    });
  });
  return { sunucu, st };
}

(async () => {
  const { sunucu, st } = sahteSunucu();
  await new Promise((r) => sunucu.listen(0, '127.0.0.1', r));
  const taban = 'http://127.0.0.1:' + sunucu.address().port;
  const tarayici = await chromium.launch();
  const sayfa = await (await tarayici.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 })).newPage();
  const hatalar = [];
  sayfa.on('console', (m) => { if (m.type() === 'error') hatalar.push(m.text()); });
  sayfa.on('pageerror', (e) => hatalar.push(String(e)));
  const gor = async (ad) => { if (SHOTS) await sayfa.screenshot({ path: path.join(SHOTS, ad), fullPage: true }); };
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
    await sayfa.click('#ileri1');
    adim('PS5 + kaynak + LG seçildi');

    await sayfa.waitForSelector('[data-motor=gemini]');
    await sayfa.click('[data-motor=claude]');
    assert.match(await sayfa.textContent('#motor-detay'), /Pro\/Max/);
    await sayfa.click('[data-motor=gemini]');
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
    await sayfa.waitForFunction(() => /Durdur/.test(document.querySelector('#baslat-durdur').textContent));
    await sayfa.waitForFunction(() => /deneme altyazısı/.test(document.querySelector('#son-yazi').textContent), null, { timeout: 6000 });
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
    await gor('5-ana-en.png');
    adim('EN diline geçildi ve ayar kaydedildi');

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
