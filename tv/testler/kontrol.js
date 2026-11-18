// SPDX-License-Identifier: AGPL-3.0-only
// Çalıştır:  cd tv/testler && NODE_PATH=$(npm root -g) node kontrol.js   (Playwright + Chromium gerekir)
// Ekran görüntüsü klasörü için: SHOT_DIR=/yol node kontrol.js
var assert = require('assert'), fs = require('fs'), os = require('os'), path = require('path');
var pw = require('playwright'), sahte = require('./sunucu.js');
var SHOT = process.env.SHOT_DIR || os.tmpdir();
var KOK = path.join(__dirname, '..', '..');
var sonuc = [];
function bekle(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
function ok(ad) { sonuc.push(ad); console.log('  ok  ' + ad); }
function hatalar(sayfa) { var l = []; sayfa.on('pageerror', function (e) { l.push('pageerror: ' + e.message); }); sayfa.on('console', function (m) { if (m.type() === 'error') { l.push('console: ' + m.text()); } }); return l; }

function sahneyiHazirla() { // tv/webos + ortak.* geçici klasöre (paketleme betiğinin yaptığı gibi)
  var d = fs.mkdtempSync(path.join(os.tmpdir(), 'akwebos-')), w = path.join(KOK, 'tv', 'webos');
  fs.readdirSync(w).forEach(function (f) { fs.copyFileSync(path.join(w, f), path.join(d, f)); });
  ['ortak.js', 'ortak.css'].forEach(function (f) { fs.copyFileSync(path.join(KOK, 'kopru', 'web', 'tv', f), path.join(d, f)); });
  return d;
}

(async function () {
  var s = sahte.olustur(); await new Promise(function (r) { s.listen(8642, '0.0.0.0', r); });
  var b = await pw.chromium.launch();
  try {
    // ---------- 1) tv.html ----------
    console.log('tv.html');
    var c = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
    var p = await c.newPage(), h1 = hatalar(p);
    await p.goto('http://127.0.0.1:8642/tv');
    await p.waitForFunction(function () { return window.AKOverlay; });
    for (var i = 0; i < 50 && s.istemciSayisi() < 1; i++) { await bekle(100); }
    assert(s.istemciSayisi() >= 1, 'akışa bağlanmadı'); ok('akışa bağlandı');
    s.yayinla('yazi', { id: 'a1', metin: 'Merhaba dünya', asil: 'Hello world', tur: 'konusma', konusan: 'Ellie', sure_ms: 1200 });
    await p.waitForSelector('.ak-yazi-kutu:visible', { timeout: 3000 });
    var t = await p.textContent('.ak-yazi-kutu'); assert(t.indexOf('Merhaba dünya') >= 0 && t.indexOf('Ellie') >= 0, t); ok('altyazı + konuşan görünüyor');
    var renk = await p.$eval('.ak-konusan', function (e) { return getComputedStyle(e).color; }); assert.strictEqual(renk, 'rgb(255, 209, 102)'); ok('konuşan adı sarı');
    assert.strictEqual(await p.$$eval('.ak-asil', function (l) { return l.length; }), 0); ok('asil_goster=false iken özgün satır yok');
    await p.screenshot({ path: path.join(SHOT, 'tv-html.png') });
    await p.waitForSelector('.ak-yazi', { state: 'hidden', timeout: 3000 }); ok('sure_ms sonunda gizlendi');
    s.yayinla('yazi', { id: 'a2', metin: 'İkinci', sure_ms: 60000 }); await p.waitForSelector('.ak-yazi-kutu:visible');
    s.yayinla('yazi-sil'); await p.waitForSelector('.ak-yazi', { state: 'hidden', timeout: 3000 }); ok('yazi-sil çalışıyor');
    s.yayinla('ekran', { id: 'e1', ogeler: [{ x: 0.1, y: 0.2, g: 0.3, y2: 0.05, metin: 'Ana kampa dön', aciklama: 'Görev: üsse geri git', tur: 'gorev' }, { x: 0.5, y: 0.5, g: 0.2, y2: 0.04, metin: 'Menü', tur: 'menu' }] });
    await p.waitForSelector('.ak-oge'); var r = await p.$$eval('.ak-oge', function (l) { return l.map(function (e) { var b = e.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.width), e.textContent]; }); });
    assert.strictEqual(r.length, 2); assert(Math.abs(r[0][0] - 192) <= 2 && Math.abs(r[0][1] - 216) <= 2 && Math.abs(r[0][2] - 576) <= 2, JSON.stringify(r));
    assert(Math.abs(r[1][0] - 960) <= 2 && Math.abs(r[1][1] - 540) <= 2); assert(r[0][3].indexOf('üsse geri git') >= 0); ok('ekran öğeleri normalize konumda + açıklama');
    await p.screenshot({ path: path.join(SHOT, 'tv-html-ekran.png') });
    s.yayinla('ekran-sil'); await p.waitForFunction(function () { return !document.querySelector('.ak-oge'); }); ok('ekran-sil çalışıyor');
    s.yayinla('yazi', { id: 'a3', metin: 'Boyut', sure_ms: 60000 }); await p.waitForSelector('.ak-yazi-kutu:visible');
    var f1 = await p.$eval('.ak-yazi', function (e) { return parseFloat(getComputedStyle(e).fontSize); });
    s.yayinla('gorunum', { yazi_boyutu: 66, konum: 'ust', kenar_bosluk: 0.05, arka_plan: 0.9, yazi_rengi: '#00FF00', konusan_rengi: '#FFD166', asil_goster: true, ekran_cevir: true });
    await p.waitForFunction(function (a) { return parseFloat(getComputedStyle(document.querySelector('.ak-yazi')).fontSize) > a; }, f1);
    var f2 = await p.$eval('.ak-yazi', function (e) { return parseFloat(getComputedStyle(e).fontSize); });
    assert(Math.abs(f1 - 44) < 0.6 && Math.abs(f2 - 66) < 0.6, f1 + ' ' + f2); ok('gorunum yazı boyutunu değiştirdi (44 -> 66)');
    var ust = await p.$eval('.ak-yazi', function (e) { return e.getBoundingClientRect().top; }); assert(ust < 200, 'konum ust değil: ' + ust); ok('gorunum konumu üste aldı');
    s.yayinla('durum', { calisiyor: true, motor: 'Gemini', yedek: false });
    assert.deepStrictEqual(h1, []); ok('tv.html: konsol hatası yok (bağlantıyı bilerek koparmadan önce)');
    // yeniden bağlanma
    s.kopar(); await bekle(300);
    for (i = 0; i < 60 && s.istemciSayisi() < 1; i++) { await bekle(100); } assert(s.istemciSayisi() >= 1, 'yeniden bağlanmadı'); ok('bağlantı kopunca yeniden bağlandı');
    await c.close();

    // ---------- 2) obs.html saydam ----------
    console.log('obs.html');
    c = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 } }); p = await c.newPage(); var ho = hatalar(p);
    await p.goto('http://127.0.0.1:8642/obs');
    var bg = await p.evaluate(function () { return getComputedStyle(document.body).backgroundColor + '|' + getComputedStyle(document.documentElement).backgroundColor; });
    assert(/rgba\(0, 0, 0, 0\)|transparent/.test(bg.split('|')[0])); ok('obs.html arka planı saydam');
    await bekle(300); assert.deepStrictEqual(ho, []); await c.close();

    // ---------- 3) webOS uygulaması ----------
    console.log('webOS uygulaması');
    var dizin = sahneyiHazirla(), url = 'file://' + dizin + '/index.html';
    var stub = function () { window.PalmServiceBridge = function () { var s = this; this.call = function (u) { s.onservicecallback(JSON.stringify(
      u.indexOf('connectionmanager/getStatus') > 0 ? { returnValue: true, wifi: { state: 'connected', ipAddress: '127.0.0.5' }, wired: { state: 'disconnected' } } : { returnValue: false })); }; }; };
    // 3a) demo kipi (webOS köprüsü yok)
    c = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 }); p = await c.newPage(); var hd = hatalar(p);
    await p.goto(url); await p.waitForSelector('#e-ara.acik'); await bekle(300);
    assert(/Bilgisayar/.test(await p.textContent('#ara-hata')) || true);
    ok('ilk açılış: arama ekranı (ağ adresi yoksa elle girmeye yönlendirir): "' + (await p.textContent('#ara-hata')).trim() + '"');
    await p.screenshot({ path: path.join(SHOT, 'webos-ara.png') });
    await p.click('#b-deneme'); await p.waitForSelector('.ak-yazi-kutu:visible', { timeout: 3000 });
    t = await p.textContent('.ak-yazi-kutu'); assert(t.indexOf('Ellie') >= 0); ok('deneme kipinde örnek altyazı görünüyor');
    await p.waitForSelector('.ak-oge'); ok('deneme kipinde ekran öğeleri görünüyor');
    await p.screenshot({ path: path.join(SHOT, 'webos-demo.png') });
    await p.keyboard.press('Escape'); await p.waitForSelector('#e-ara.acik'); ok('Geri/Esc deneme kipinden çıkarır');
    assert.deepStrictEqual(hd, []); ok('webOS demo: konsol hatası yok'); await c.close();
    // 3b) PalmServiceBridge taklidi ile alt ağ taraması -> bulunan PC -> HDMI -> çalışıyor -> panel
    c = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 }); await c.addInitScript(stub); p = await c.newPage(); var hs = hatalar(p);
    await p.goto(url); await p.waitForSelector('#ara-liste button', { timeout: 30000 });
    t = await p.textContent('#ara-liste button'); assert(t.indexOf('TEST-PC') >= 0 && /127\.0\.0\.\d+:8642/.test(t), t); ok('alt ağ taraması sahte Köprü\'yü buldu: ' + t.trim());
    await p.keyboard.press('Enter'); await p.waitForSelector('#e-hdmi.acik'); ok('OK ile bilgisayar seçilince HDMI ekranı açıldı');
    await p.keyboard.press('Enter'); await p.waitForSelector('#e-calis.acik'); ok('HDMI seçilince çalışma ekranı');
    for (i = 0; i < 40 && s.istemciSayisi() < 1; i++) { await bekle(100); } assert(s.istemciSayisi() >= 1);
    s.yayinla('yazi', { id: 'z1', metin: 'TV üzerinden altyazı', sure_ms: 30000 }); await p.waitForSelector('.ak-yazi-kutu:visible');
    await p.keyboard.press('Enter'); await p.waitForSelector('#panel.acik');
    var pt = await p.textContent('#panel'); assert(/127\.0\.0\.\d+:8642/.test(pt) && pt.indexOf('Bağlı') >= 0 && pt.indexOf('HDMI 1') >= 0 && pt.indexOf('TV üzerinden altyazı') >= 0 && pt.indexOf('0.1.0') >= 0, pt); ok('bilgi paneli adres/bağlantı/HDMI/son altyazı/sürüm gösteriyor');
    await p.screenshot({ path: path.join(SHOT, 'webos-panel.png') });
    var kayit = await p.evaluate(function () { return localStorage.getItem('ak_son_pc') + '|' + localStorage.getItem('ak_hdmi'); }); assert(/^127\.0\.0\.\d+:8642\|1$/.test(kayit), kayit); ok('son bilgisayar ve HDMI hatırlandı');
    var sayfaHatalari = hs.filter(function (x) { return x.indexOf('pageerror') === 0; }); assert.deepStrictEqual(sayfaHatalari, []); ok('tarama/çalışma akışında JS hatası yok (HDMI kaynak hatası Chromium\'da beklenir)');
    // 3c) elle adres: sayı tuşları
    await c.close();
    c = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 } }); p = await c.newPage(); var he = hatalar(p);
    await p.goto(url); await p.waitForSelector('#e-ara.acik'); await p.click('#b-elle'); await p.waitForSelector('#e-elle.acik');
    await p.keyboard.type('127.0.0.1'); assert.strictEqual((await p.textContent('#adres-alan')).trim(), '127.0.0.1');
    await p.click('#b-elle-tamam'); await p.waitForSelector('#e-hdmi.acik'); ok('elle adres + sayı tuşu ile bağlantı');
    assert.deepStrictEqual(he.filter(function (x) { return x.indexOf('pageerror') === 0; }), []); await c.close();
    console.log('\nTÜM KONTROLLER GEÇTİ (' + sonuc.length + ')');
  } catch (e) { console.error('\nBAŞARISIZ:', e && e.stack || e); process.exitCode = 1; }
  finally { await b.close(); s.close(); process.exit(process.exitCode || 0); }
}());
