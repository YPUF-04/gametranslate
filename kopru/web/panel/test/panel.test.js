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
      gorunum: { yazi_boyutu: 44, konum: 'alt', arka_plan: 0.55 }, hafiza_izni: null, kalite: 'en_iyi', aktif_oyun: null },
    oyunlar: [{ kod: 'gta6', ad: 'GTA 6', kayit_sayisi: 1240, terim_sayisi: 35 }, { kod: 'tlou', ad: 'The Last of Us', kayit_sayisi: 0, terim_sayisi: 2 }],
    ceviriler: [{ id: 'a1', asil: 'Where were you last night?', ceviri: 'Dün gece neredeydin?', kaynak: 'motor' }, { id: 'a2', asil: 'Head back to the safehouse.', ceviri: 'Güvenli eve dön.', kaynak: 'motor' }],
    oneriler: [{ asil: 'Vice City', ceviri: 'Vice City' }],
    calisiyor: false, anahtarlar: {}, istekler: [], govdeler: {}, sozluk: { oyun: 'varsayilan', terimler: [{ asil: 'Ellie', ceviri: 'Ellie' }] }
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
    // son çeviriler + düzelt
    await sayfa.waitForSelector('.ceviri-satir[data-id=a1]', { timeout: 6000 });
    await sayfa.waitForSelector('#oneri-kart:not([hidden])');
    await gor('v2-ana.png');
    await sayfa.click('[data-id=a1] .duzelt');
    await sayfa.fill('[data-id=a1] .duzelt-girdi', 'Dün gece neredeydin sen?');
    await sayfa.click('[data-id=a1] .duzelt-kaydet');
    await sayfa.waitForSelector('.tost');
    assert.match(await sayfa.textContent('.tost'), /bundan sonra hep böyle çevireceğim/);
    assert.deepStrictEqual(JSON.parse(st.govdeler['POST /api/duzelt']), { asil: 'Where were you last night?', ceviri: 'Dün gece neredeydin sen?' });
    assert.match(await sayfa.textContent('[data-id=a1]'), /neredeydin sen/);
    adim('son çeviriler görünür, Düzelt doğru gövdeyi gönderdi');
    // öneri kabul
    await sayfa.click('[data-oneri="Vice City"] .kabul');
    await sayfa.waitForSelector('#oneri-kart[hidden]', { state: 'attached' });
    assert.deepStrictEqual(JSON.parse(st.govdeler['POST /api/oneriler']), { asil: 'Vice City', kabul: true });
    adim('öneri kabul edildi');
    // gelişmiş ayarlar
    await sayfa.click('#gelismis > summary');
    assert.match(await sayfa.getAttribute('#paket-paylas', 'href'), /\/api\/paket\/rdr3$/);
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
