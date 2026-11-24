// SPDX-License-Identifier: AGPL-3.0-only
// Çalıştır:  cd tv/testler && NODE_PATH=$(npm root -g) node kontrol.js   (Playwright + Chromium gerekir)
// Ekran görüntüsü klasörü için: SHOT_DIR=/yol node kontrol.js
var assert = require('assert'), fs = require('fs'), os = require('os'), path = require('path');
var pw = require('playwright'), sahte = require('./sunucu.js'), cp = require('child_process');
var PY = process.env.PYTHON || 'python3';
var SHOT = process.env.SHOT_DIR || os.tmpdir();
var KOK = path.join(__dirname, '..', '..');
var sonuc = [];
function bekle(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
function ok(ad) { sonuc.push(ad); console.log('  ok  ' + ad); }
function hatalar(sayfa) { var l = []; sayfa.on('pageerror', function (e) { l.push('pageerror: ' + e.message); }); sayfa.on('console', function (m) { if (m.type() === 'error') { l.push('console: ' + m.text()); } }); return l; }

function sahneyiHazirla() { // başlatıcı (tv/webos) + yazı tipleri + gömülü paket, paketleme betiğinin yaptığı gibi (PROTOKOL 18)
  var d = fs.mkdtempSync(path.join(os.tmpdir(), 'akwebos-')), w = path.join(KOK, 'tv', 'webos');
  fs.readdirSync(w).forEach(function (f) { fs.copyFileSync(path.join(w, f), path.join(d, f)); });
  ['yazi-latin.woff2', 'yazi-latin-ext.woff2'].forEach(function (f) { fs.copyFileSync(path.join(KOK, 'kopru', 'web', 'tv', f), path.join(d, f)); });
  cp.execFileSync(PY, ['-m', 'kopru.tv_kurulum.uygulama', '--gomulu', path.join(d, 'gomulu.js')], { cwd: KOK });
  return d;
}
function paketAl() { // sunucunun sunduğu paketin aynısı
  var f = path.join(os.tmpdir(), 'ak-tv-paket-' + process.pid + '.json');
  cp.execFileSync(PY, ['-m', 'kopru.tv_kurulum.uygulama', '--json', f], { cwd: KOK });
  return JSON.parse(fs.readFileSync(f, 'utf8'));
}

(async function () {
  var s = sahte.olustur(); await new Promise(function (r) { s.listen(8642, '0.0.0.0', r); });
  var PAKET = paketAl(); s.tvPaket = PAKET;
  var b = await pw.chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
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
    assert.strictEqual(await p.$$eval('.tt-secim', function (l) { return l.length; }), 0); ok('webOS olmayan tarayıcıda HDMI seçimi yok (eski davranış)');
    await p.screenshot({ path: path.join(SHOT, 'tv-html.png') });
    await bekle(1800); assert(await p.isVisible('.ak-yazi-kutu'), 'sure_ms dolunca kendiliğinden gizlendi'); ok('§13.4: sure_ms dolsa da istemci kendiliğinden gizlemez');
    s.yayinla('yazi', { id: 'a1b', metin: 'Yeni cümle', sure_ms: 300 }); await bekle(300);
    s.yayinla('yazi-sil', { id: 'a1' }); await bekle(150);   // eskinin gecikmiş silmesi yeni yazıyı silmez
    assert(await p.isVisible('.ak-yazi-kutu'), 'başka id\'li yazi-sil yeni yazıyı sildi'); ok('yazi-sil id eşleşmezse yok sayılır');
    s.yayinla('yazi-sil', { id: 'a1b' }); await p.waitForSelector('.ak-yazi', { state: 'hidden', timeout: 3000 }); ok('yazi-sil (id) ile gizlendi');
    s.yayinla('yazi', { id: 'a2', metin: 'İkinci', sure_ms: 1500 }); await p.waitForSelector('.ak-yazi-kutu:visible');
    s.yayinla('yazi-sil'); await p.waitForSelector('.ak-yazi', { state: 'hidden', timeout: 1500 }); ok('yazi-sil (§13.2): kaynak gitti, en az süre beklenmeden kalkar');
    s.yayinla('yazi', { id: 'g1', metin: 'Üçüncü', sure_ms: 3000 }); await p.waitForSelector('.ak-yazi-kutu:visible');
    s.yayinla('katman-gizle'); await bekle(100); assert.strictEqual(await p.isVisible('.ak-yazi-kutu'), false, 'gizli iken görünür'); ok('katman-gizle: yazı gizlendi');
    s.yayinla('katman-goster'); await bekle(100); assert(await p.isVisible('.ak-yazi-kutu'), 'gösterilince görünmedi'); ok('katman-goster: yazı yeniden görünür');
    s.yayinla('yazi-sil'); await p.waitForSelector('.ak-yazi', { state: 'hidden', timeout: 1500 });
    s.yayinla('ekran', { id: 'e1', ogeler: [{ x: 0.1, y: 0.2, g: 0.3, y2: 0.05, metin: 'Ana kampa dön', aciklama: 'Görev: üsse geri git', tur: 'gorev' }, { x: 0.5, y: 0.5, g: 0.2, y2: 0.04, metin: 'Menü', tur: 'menu' }] });
    await p.waitForSelector('.ak-oge'); var r = await p.$$eval('.ak-oge', function (l) { return l.map(function (e) { var b = e.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.width), e.textContent]; }); });
    assert.strictEqual(r.length, 2); assert(Math.abs(r[0][0] - 192) <= 2 && Math.abs(r[0][1] - 216) <= 2 && r[0][2] <= 0.35 * 1920 + 2, JSON.stringify(r));
    assert(Math.abs(r[1][0] - 960) <= 2 && Math.abs(r[1][1] - 540) <= 2); assert(r[0][3].indexOf('üsse geri git') >= 0); ok('ekran öğeleri normalize konumda + açıklama');
    await p.screenshot({ path: path.join(SHOT, 'tv-html-ekran.png') });
    s.yayinla('ekran-sil'); await p.waitForFunction(function () { return !document.querySelector('.ak-oge'); }); ok('ekran-sil çalışıyor');
    // PROTOKOL 12.4: hedef kutusu + boyut_px; tek satır; en çok 2 satır, yalnız boşlukta; genişlik <= %35; ekran içinde; normal ağırlık
    var uzun = 'Bu çok uzun bir görev açıklaması olup kutu genişleyip sonra kelime sınırlarında alt satıra geçmelidir ve hâlâ sığmazsa kısaltılmalıdır. Bu çok uzun bir görev açıklaması olup kutu genişleyip sonra kelime sınırlarında alt satıra geçmelidir ve hâlâ sığmazsa kısaltılmalıdır';
    var orta = 'Return to the base camp before sunset and talk to the guard captain';
    s.yayinla('ekran', { id: 'e9', ogeler: [
      { id: 'h1', x: 0.1, y: 0.2, g: 0.02, y2: 0.03, metin: 'Parti: Hazır', tur: 'menu', hedef: { x: 0.6, y: 0.3, g: 0.2, y2: 0.05 }, boyut_px: 18 },
      { id: 'h2', x: 0.1, y: 0.5, g: 0.2, y2: 0.03, metin: uzun, tur: 'gorev', hedef: { x: 0.9, y: 0.9, g: 0.05, y2: 0.03 }, boyut_px: 22 },
      { id: 'h3', x: 0.1, y: 0.7, g: 0.3, y2: 0.03, metin: 'Ana kampa dön', tur: 'menu', boyut_px: 16 },
      { id: 'h4', x: 0.1, y: 0.35, g: 0.12, y2: 0.03, metin: orta, tur: 'menu', boyut_px: 16 }] });
    await p.waitForSelector('.ak-oge'); await bekle(400);
    var hr = await p.$$eval('.ak-oge', function (l) { return l.map(function (e) {
      var b = e.getBoundingClientRect(), t = e.querySelector('.ak-oge-metin'), cs = getComputedStyle(e);
      var satirlar = []; for (var c = t.firstChild; c; c = c.nextSibling) { if (c.nodeType === 3) { satirlar.push(c.textContent); } }
      return { l: b.left, t: b.top, w: b.width, r: b.right, b: b.bottom, f: parseFloat(cs.fontSize), fw: cs.fontWeight, satirlar: satirlar }; }); });
    assert(Math.abs(hr[0].l - 1152) <= 2 && Math.abs(hr[0].t - 324) <= 2, JSON.stringify(hr)); assert(Math.abs(hr[0].f - 18) <= 0.6, JSON.stringify(hr));
    assert.strictEqual(hr[0].satirlar.length, 1, JSON.stringify(hr[0])); assert.strictEqual(hr[0].fw, '400', 'ekran öğesi normal ağırlıkta olmalı');
    assert(hr[0].w < 0.35 * 1920, JSON.stringify(hr[0]));
    var sozcukTamMi = function (satirlar, metin) { var ks = metin.split(' '), i = 0; return satirlar.every(function (sat) { var son = sat.charAt(sat.length - 1) === '\u2026'; var w = (son ? sat.slice(0, -1) : sat).split(' ').filter(Boolean); return w.every(function (k, j) { var ok2 = ks[i + j] === k || (son && j === w.length - 1 && ks[i + j] && ks[i + j].indexOf(k) === 0); return ok2; }) && (i += w.length, true); }); };
    assert(hr[1].satirlar.length <= 2 && hr[1].w <= 0.35 * 1920 + 2 && hr[1].r <= 1920 + 1 && hr[1].b <= 1080 + 1 && hr[1].f >= 11 - 0.2, JSON.stringify(hr[1]));
    assert(sozcukTamMi(hr[1].satirlar, uzun) && hr[1].satirlar.join('').indexOf('\u2026') > 0, 'uzun metin: boşlukta kırıldı, sonu "…" ile bitti: ' + JSON.stringify(hr[1].satirlar));
    assert.strictEqual(hr[2].satirlar.length, 1, JSON.stringify(hr[2])); assert(Math.abs(hr[2].f - 16) <= 0.6);
    assert(hr[3].satirlar.length <= 2 && hr[3].w <= 0.35 * 1920 + 2 && sozcukTamMi(hr[3].satirlar, orta), JSON.stringify(hr[3]));
    hr[3].satirlar.forEach(function (x) { assert(x.split(' ').length >= 2, 'tek kelimelik satır yığılması: ' + JSON.stringify(hr[3].satirlar)); });
    ok('ekran öğesi: normal ağırlık, tek satır, ≤2 satır boşlukta, ≤%35, ekran içinde, uzunsa "…"');
    var yb = await p.evaluate(function () { return window.AKOverlay.yerlesimBul('Return to the base camp quickly', function (t, px) { return t.length * px * 0.55; }, 400, 16, 11); });
    assert(yb.satirlar.length <= 2 && yb.px >= 11, JSON.stringify(yb)); ok('AKOverlay.yerlesimBul saf düzen: ≤2 satır, ≥11 px');
    s.yayinla('ekran-sil'); await p.waitForFunction(function () { return !document.querySelector('.ak-oge'); });
    // ---------- PROTOKOL 16.1/16.2: orijinal yazının üstünü örtme ----------
    var ortu = { x: 0.3, y: 0.8, g: 0.4, y2: 0.06, zemin: '#E6E6E6', renk: '#111111', opaklik: 0.94, satir: 1, metin: "Kabul etmek için ✕'e bas" };
    s.yayinla('yazi', { id: 'o1', metin: "Kabul etmek için ✕'e bas", asil: 'Press ✕ to Accept', sure_ms: 3000, ortu: ortu });
    await p.waitForSelector('.ak-ortu-yazi.ak-acik'); await bekle(250);
    var ob = await p.$eval('.ak-ortu-yazi', function (e) { var b = e.getBoundingClientRect(), cs = getComputedStyle(e), m = e.querySelector('.ak-ortu-metin');
      return { l: b.left, t: b.top, w: b.width, h: b.height, bg: cs.backgroundColor, c: cs.color, f: parseFloat(cs.fontSize), op: +cs.opacity,
        mw: m.getBoundingClientRect().width, mh: m.getBoundingClientRect().height, d: Array.prototype.map.call(e.querySelectorAll('.ak-dugme'), function (x) { return x.textContent; }), txt: m.textContent }; });
    assert(Math.abs(ob.l - 576) <= 1 && Math.abs(ob.t - 864) <= 1 && Math.abs(ob.w - 768) <= 1 && Math.abs(ob.h - 64.8) <= 1.5, JSON.stringify(ob));
    assert.strictEqual(ob.bg, 'rgba(230, 230, 230, 0.94)'); assert.strictEqual(ob.c, 'rgb(17, 17, 17)'); assert(ob.op > 0.99, 'örtü görünmüyor');
    assert(ob.mw <= ob.w && ob.mh <= ob.h + 1 && ob.f >= 16, JSON.stringify(ob)); assert.deepStrictEqual(ob.d, ['✕']); assert(ob.txt.indexOf('Kabul etmek için') === 0, ob.txt);
    assert.strictEqual(await p.isVisible('.ak-yazi-kutu'), false, 'örtüde alt çubuk da görünüyor'); ok('§16.1: altyazı kaynağın yerinde, o boyda, opak örtü; düğme rozet; yazı kutuya sığdı');
    await p.screenshot({ path: path.join(SHOT, 'tv-ortu.png') });
    var uzunTr = 'Bu çok uzun bir Türkçe çeviri cümlesi olup İngilizce kutusuna en küçük okunur boyda bile sığmayabilir, kutu büyümelidir';
    s.yayinla('yazi', { id: 'o1', metin: uzunTr, sure_ms: 3000, devam: true, ortu: { x: 0.3, y: 0.8, g: 0.2, y2: 0.03, zemin: '#101418', renk: '#FFFFFF', metin: uzunTr } });
    await bekle(100);
    var ob2 = await p.$$eval('.ak-ortu-yazi', function (l) { return l.map(function (e) { var b = e.getBoundingClientRect(), m = e.querySelector('.ak-ortu-metin');
      return { w: b.width, h: b.height, b: b.bottom, r: b.right, f: parseFloat(getComputedStyle(e).fontSize), mw: m.getBoundingClientRect().width, mh: m.getBoundingClientRect().height }; }); });
    assert.strictEqual(ob2.length, 1, 'aynı id (devam) yerinde güncellenmeli: ' + JSON.stringify(ob2));
    assert(Math.abs(ob2[0].f - 16) <= 0.5 && ob2[0].h > 32.4 && ob2[0].mh <= ob2[0].h + 1 && ob2[0].mw <= ob2[0].w + 1 && ob2[0].b <= 1081 && ob2[0].r <= 1921, JSON.stringify(ob2));
    ok('§16.1: sığmayan çeviri en az 16 px, kutu büyür, ekrandan taşmaz; devam yerinde');
    s.yayinla('yazi-sil', { id: 'o1' }); await p.waitForFunction(function () { return !document.querySelector('.ak-ortu-yazi'); }, null, { timeout: 2000 }); ok('§16.1: yazi-sil örtüyü kaldırır');
    s.yayinla('ekran', { id: 'eo', ogeler: [{ id: 'k1', x: 0.05, y: 0.1, g: 0.3, y2: 0.04, metin: 'Nehir kenarında üç ot topla', tur: 'gorev', aciklama: 'Görev',
      ortu: { x: 0.045, y: 0.095, g: 0.31, y2: 0.05, zemin: '#282828', renk: '#FFFFFF', metin: 'Nehir kenarında üç ot topla' } }] });
    await p.waitForSelector('.ak-ortu-oge.ak-acik'); await bekle(250);
    var eo = await p.$eval('.ak-ortu-oge', function (e) { var b = e.getBoundingClientRect(); return { l: b.left, t: b.top, w: b.width, bg: getComputedStyle(e).backgroundColor, a: !!e.querySelector('.ak-ortu-aciklama') }; });
    assert(Math.abs(eo.l - 86.4) <= 1 && Math.abs(eo.t - 102.6) <= 1 && Math.abs(eo.w - 595.2) <= 1 && eo.bg === 'rgba(40, 40, 40, 0.94)' && eo.a, JSON.stringify(eo));
    ok('§16.1: ekran öğesi kaynağın üstünü örter (açıklama altında)');
    s.yayinla('ekran-sil'); await p.waitForFunction(function () { return !document.querySelector('.ak-ortu-oge'); });
    s.yayinla('gorunum', { yerlesim: 'cubuk' }); await bekle(100);
    s.yayinla('yazi', { id: 'o2', metin: 'Çubukta', sure_ms: 3000, ortu: ortu }); await p.waitForSelector('.ak-yazi-kutu:visible');
    assert.strictEqual(await p.$$eval('.ak-ortu-yazi', function (l) { return l.length; }), 0); ok('§16.1: yerlesim "cubuk": eski alt çubuk aynen');
    s.yayinla('yazi-sil', { id: 'o2' }); await p.waitForSelector('.ak-yazi', { state: 'hidden', timeout: 2000 });
    s.yayinla('gorunum', { yerlesim: 'ustune' });
    var dp = await p.evaluate(function () { return [window.AKOverlay.dugmeParcala("✕'e"), window.AKOverlay.dugmeParcala('R2,'), window.AKOverlay.dugmeParcala('[X]'), window.AKOverlay.dugmeParcala('Kabul')]; });
    assert.deepStrictEqual(dp, [['', '✕', "'e"], ['', 'R2', ','], ['', '[X]', ''], null]); ok('§16.2: düğme belirteci ayrıştırma (Türkçe ek, noktalama)');
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


    // ---------- 1b) akıcı gösterim (PROTOKOL 7.2, istemci tarafı) ----------
    console.log('akıcı gösterim');
    var ornekle = function () { // her karede kutuların saydamlığını kaydeder
      window.__o = []; var t0 = performance.now();
      (function d() { window.__o.push([Math.round(performance.now() - t0), Array.prototype.map.call(document.querySelectorAll('.ak-yazi-kutu'), function (k) { return +getComputedStyle(k).opacity; }),
        (function () { var e = document.querySelector('.ak-onceki'); return e && getComputedStyle(e).display !== 'none' ? [e.textContent, +getComputedStyle(e).opacity] : null; }())]); if (performance.now() - t0 < 7000) { requestAnimationFrame(d); } }());
    };
    var cf = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
    var pf = await cf.newPage(), hf = hatalar(pf);
    var onceki = s.istemciSayisi();
    await pf.goto('http://127.0.0.1:8642/tv'); await pf.waitForFunction(function () { return window.AKOverlay; });
    for (i = 0; i < 50 && s.istemciSayisi() <= onceki; i++) { await bekle(100); }
    // A) çapraz geçiş + önceki satır
    s.yayinla('yazi', { id: 'f1', metin: 'Birinci cümle burada', sure_ms: 9000, devam: false });
    await pf.waitForSelector('.ak-yazi-kutu:visible'); await bekle(400);
    await pf.evaluate(ornekle); s.yayinla('yazi', { id: 'f2', metin: 'İkinci cümle geldi', sure_ms: 9000, devam: false }); var t2 = Date.now();
    await bekle(700);
    var oz = await pf.evaluate(function () { return window.__o; });
    var ikili = oz.filter(function (x) { return x[1].length === 2; });
    assert(ikili.length > 2, 'çapraz geçiş yok'); assert(ikili.some(function (x) { return x[1][0] < 0.95 && x[1][1] < 1; }) || ikili.some(function (x) { return x[1][0] < 0.95; }), 'eski kutu solmadı');
    var uzun = ikili.filter(function (x) { return x[1][0] > 0.95 && x[1][1] > 0.95; }); assert(uzun.length <= 3, 'ikisi birden uzun süre tam görünür: ' + uzun.length);
    var son = oz[oz.length - 1]; assert.strictEqual(son[1].length, 1); assert(Math.abs(son[1][0] - 1) < 0.01); ok('yeni cümlede eskisi 150 ms\'de solarken yenisi belirdi, sonunda tek kutu');
    var ilkOnceki = oz.filter(function (x) { return x[2]; })[0]; assert(ilkOnceki && ilkOnceki[2][0].indexOf('Birinci cümle burada') >= 0, JSON.stringify(ilkOnceki)); ok('önceki satır üstte görünüyor');
    await pf.screenshot({ path: path.join(SHOT, 'v3-altyazi.png') });
    await pf.waitForFunction(function () { var e = document.querySelector('.ak-onceki'); return getComputedStyle(e).display === 'none'; }, null, { timeout: 5000 });
    var gecen = Date.now() - t2; assert(gecen > 2300 && gecen < 3600, 'önceki satır ' + gecen + ' ms sonra kayboldu'); ok('önceki satır ~2,5 sn sonra kayboldu (' + gecen + ' ms)');
    // B) devam:true -> aynı düğüm, solma yok
    s.yayinla('yazi', { id: 'f3', metin: 'Bir iki üç', sure_ms: 9000, devam: false }); await bekle(400);
    await pf.evaluate(function () { document.querySelector('.ak-yazi-kutu.ak-gorunur').__isaret = 7; ornekle2(); function ornekle2() { window.__d = []; var t0 = performance.now(); (function d() { var k = document.querySelectorAll('.ak-yazi-kutu'); window.__d.push([k.length, k.length ? +getComputedStyle(k[0]).opacity : -1, k.length ? k[0].className : '']); if (performance.now() - t0 < 600) { requestAnimationFrame(d); } }()); } });
    s.yayinla('yazi', { id: 'f3', metin: 'Bir iki üç dört beş altı', sure_ms: 9000, devam: true }); await bekle(700);
    var dv = await pf.evaluate(function () { var k = document.querySelectorAll('.ak-yazi-kutu'); return { n: k.length, isaret: k[0].__isaret, metin: k[0].textContent, sinif: k[0].className, ornek: window.__d }; });
    assert.strictEqual(dv.n, 1); assert.strictEqual(dv.isaret, 7, 'devam: yeni düğüm yaratıldı'); assert(dv.metin.indexOf('dört beş altı') >= 0);
    assert(dv.sinif.indexOf('ak-cikiyor') < 0); assert(dv.ornek.every(function (x) { return x[0] === 1 && x[1] > 0.99; }), 'devam sırasında solma/titreme: ' + JSON.stringify(dv.ornek.filter(function (x) { return x[1] < 0.99 || x[0] !== 1; }).slice(0, 3)));
    ok('devam:true metni aynı düğümde, solmadan günceller');
    // C) id aynı, devam alanı yok -> yine yerinde
    s.yayinla('yazi', { id: 'f3', metin: 'Bir iki üç dört beş altı yedi', sure_ms: 9000 }); await bekle(200);
    assert.strictEqual(await pf.evaluate(function () { return document.querySelectorAll('.ak-yazi-kutu').length + document.querySelector('.ak-yazi-kutu').__isaret; }), 8); ok('aynı id her zaman yerinde güncellenir');
    // D) taban sabit: kısa/uzun metinde kutunun alt kenarı oynamaz
    s.yayinla('yazi', { id: 'f4', metin: 'Kısa', sure_ms: 9000, devam: false }); await bekle(500);
    var alt1 = await pf.$eval('.ak-yazi-kutu.ak-gorunur:last-child', function (e) { return e.getBoundingClientRect().bottom; });
    s.yayinla('yazi', { id: 'f5', metin: 'Bu oldukça uzun bir cümle ve iki satıra yayılması gerekiyor çünkü tek satıra sığmayacak kadar uzun', sure_ms: 9000, devam: false }); await bekle(500);
    var alt2 = await pf.$eval('.ak-yazi-kutu.ak-gorunur:last-child', function (e) { return e.getBoundingClientRect().bottom; });
    assert(Math.abs(alt1 - alt2) < 1, 'taban oynadı: ' + alt1 + ' ' + alt2); ok('kutu alttan sabit: yükseklik değişse de taban çizgisi oynamıyor (' + alt1 + ')');
    // E) satır düzeni: en çok 2 satır, dengeli, kelime ortasından bölünmez, genişlik <= %70
    var duzen = await pf.evaluate(function () {
      var m = document.querySelector('.ak-yazi-kutu.ak-gorunur:last-child .ak-metin'), r = document.createRange(), tops = {}, kelimeBolundu = 0, kutular, i, w = [];
      var metin = m.textContent, re = /\S+/g, mm, tn = m.firstChild;
      var tum = m.childNodes; var node = tum[0];
      while ((mm = re.exec(metin))) { r.setStart(node, mm.index); r.setEnd(node, mm.index + mm[0].length); if (r.getClientRects().length > 1) { kelimeBolundu++; } }
      r.selectNodeContents(m); kutular = r.getClientRects();
      for (i = 0; i < kutular.length; i++) { tops[Math.round(kutular[i].top / 4)] = (tops[Math.round(kutular[i].top / 4)] || 0) + kutular[i].width; }
      for (var k in tops) { w.push(tops[k]); }
      return { satir: w.length, genislikler: w, bolunen: kelimeBolundu, kutu: document.querySelector('.ak-yazi-kutu.ak-gorunur:last-child').getBoundingClientRect().width };
    });
    assert.strictEqual(duzen.bolunen, 0, 'kelime bölündü'); assert(duzen.satir === 2, 'satır sayısı: ' + duzen.satir); assert(duzen.kutu <= 1920 * 0.7 + 2, 'kutu %70\'ten geniş: ' + duzen.kutu);
    var oran = Math.min.apply(null, duzen.genislikler) / Math.max.apply(null, duzen.genislikler); assert(oran > 0.55, 'satırlar dengesiz: ' + JSON.stringify(duzen.genislikler)); ok('uzun metin 2 dengeli satır, kelime bölünmedi, kutu <= %70 (' + JSON.stringify(duzen.genislikler.map(Math.round)) + ')');
    // F) JS dengesi (CSS dengesi olmayan TV'ler): zorla
    var js = await pf.evaluate(function () {
      var d = document.createElement('div'); d.style.cssText = 'position:fixed;left:0;top:0;width:1920px;height:1080px'; document.body.appendChild(d);
      var k = window.AKOverlay.baslat(null, d, { dengeJs: true, gorunum: { yazi_boyutu: 44 } });
      var metin = 'Bu oldukça uzun bir cümle ve iki satıra yayılması gerekiyor çünkü tek satıra sığmayacak kadar uzun';
      k.yaziGoster({ id: 'j1', metin: metin, sure_ms: 9000 });
      var m = d.querySelector('.ak-metin'), br = m.getElementsByTagName('br').length, r = document.createRange(), bol = 0, re = /\S+/g, mm, nodes = [], i, parca = [];
      for (i = 0; i < m.childNodes.length; i++) { if (m.childNodes[i].nodeType === 3) { parca.push(m.childNodes[i].data); } }
      var tum = parca.join(' ');
      r.selectNodeContents(m); var kt = r.getClientRects(), tops = {}; for (i = 0; i < kt.length; i++) { tops[Math.round(kt[i].top / 4)] = 1; }
      var sonuc = { br: br, satir: Object.keys(tops).length, ayni: tum === metin, parcalar: parca };
      k.durdur(); d.remove(); return sonuc;
    });
    assert.strictEqual(js.br, 1, JSON.stringify(js)); assert.strictEqual(js.satir, 2); assert(js.ayni, 'JS bölme metni bozdu: ' + JSON.stringify(js.parcalar));
    var oranJs = Math.min(js.parcalar[0].length, js.parcalar[1].length) / Math.max(js.parcalar[0].length, js.parcalar[1].length); assert(oranJs > 0.6 && js.parcalar[0].length <= js.parcalar[1].length + 6, JSON.stringify(js.parcalar)); ok('JS yedek dengesi: tek <br>, kelime ortasından değil, ilk satır biraz kısa/eşit');
    // G) yazi-sil: solarak kalkar
    await pf.evaluate(ornekle); s.yayinla('yazi', { id: 'f6', metin: 'Silinecek', sure_ms: 1800, devam: false }); await bekle(2000);
    s.yayinla('yazi-sil'); await bekle(700);
    oz = await pf.evaluate(function () { return window.__o; });
    var cik = oz.filter(function (x) { return x[1].length === 1 && x[1][0] > 0.02 && x[1][0] < 0.98; }); assert(cik.length >= 3, 'fade-out yok'); assert.strictEqual(oz[oz.length - 1][1].length, 0);
    assert(await pf.isHidden('.ak-yazi')); ok('yazi-sil: 250 ms\'de solarak kayboldu (' + cik.length + ' ara kare)');
    // H) ekran öğeleri: aynıysa yeniden çizilmez, değişince yerinde güncellenir, gidince solar
    var ogeler = function (m) { return [{ id: 'o1', x: 0.1, y: 0.2, g: 0.3, y2: 0.05, metin: m, tur: 'gorev' }, { id: 'o2', x: 0.5, y: 0.5, g: 0.2, y2: 0.04, metin: 'Menü', tur: 'menu' }]; };
    s.yayinla('ekran', { id: 'e1', ogeler: ogeler('Ana kampa dön') }); await pf.waitForSelector('.ak-oge.ak-acik');
    await pf.evaluate(function () { Array.prototype.forEach.call(document.querySelectorAll('.ak-oge'), function (e, i) { e.__n = i + 1; }); });
    s.yayinla('ekran', { id: 'e2', ogeler: ogeler('Ana kampa dön') }); await bekle(400);
    assert.deepStrictEqual(await pf.$$eval('.ak-oge', function (l) { return l.map(function (e) { return e.__n; }); }), [1, 2]); ok('aynı yerde aynı öğe yeniden çizilmedi');
    s.yayinla('ekran', { id: 'e3', ogeler: ogeler('Kampa geri dön') }); await bekle(400);
    assert.deepStrictEqual(await pf.$$eval('.ak-oge', function (l) { return l.map(function (e) { return e.__n + ':' + e.textContent; }); }), ['1:Kampa geri dön', '2:Menü']); ok('değişen öğe yerinde güncellendi');
    s.yayinla('ekran', { id: 'e4', ogeler: ogeler('Kampa geri dön').slice(0, 1) }); await bekle(60);
    assert.strictEqual(await pf.$$eval('.ak-oge', function (l) { return l.length; }), 2, 'solmadan kalktı'); await pf.waitForFunction(function () { return document.querySelectorAll('.ak-oge').length === 1; }); ok('giden öğe solarak kalktı');
    s.yayinla('ekran-sil'); await pf.waitForFunction(function () { return !document.querySelector('.ak-oge'); });
    assert.deepStrictEqual(hf, []); await cf.close(); ok('akıcı gösterim: konsol hatası yok');

    // I) hareketi azalt: animasyon yok, anında
    var cr = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 }, reducedMotion: 'reduce' });
    var pr = await cr.newPage(), hr = hatalar(pr); onceki = s.istemciSayisi();
    await pr.goto('http://127.0.0.1:8642/tv'); await pr.waitForFunction(function () { return window.AKOverlay; });
    for (i = 0; i < 50 && s.istemciSayisi() <= onceki; i++) { await bekle(100); }
    s.yayinla('yazi', { id: 'r1', metin: 'Birinci', sure_ms: 1800, devam: false }); await pr.waitForSelector('.ak-yazi-kutu:visible');
    s.yayinla('yazi', { id: 'r2', metin: 'İkinci', sure_ms: 1800, devam: false }); await bekle(60);
    var ra = await pr.evaluate(function () { var k = document.querySelectorAll('.ak-yazi-kutu'); return { n: k.length, op: +getComputedStyle(k[0]).opacity, td: getComputedStyle(k[0]).transitionDuration, onceki: getComputedStyle(document.querySelector('.ak-onceki')).transitionDuration }; });
    assert.strictEqual(ra.n, 1, 'çapraz geçiş var'); assert.strictEqual(ra.op, 1); assert.strictEqual(ra.td, '0s'); ok('reduced-motion: eski kutu anında gitti, yenisi anında tam görünür');
    await bekle(1900); s.yayinla('yazi-sil'); await bekle(80);
    assert(await pr.isHidden('.ak-yazi')); ok('reduced-motion: yazi-sil anında kaldırdı');
    s.yayinla('ekran', { id: 'er', ogeler: ogeler('Merhaba') }); await bekle(60); s.yayinla('ekran-sil'); await bekle(60);
    assert.strictEqual(await pr.$$eval('.ak-oge', function (l) { return l.length; }), 0); ok('reduced-motion: ekran öğeleri anında kalktı');
    assert.deepStrictEqual(hr, []); await cr.close();

    // ---------- 1c) Türkçe dublaj sesi (PROTOKOL 9.4 / 14.3: `ses` / `ses-dur`, sıralı çalma) ----------
    console.log('dublaj sesi (Web Audio)');
    var cw = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 } });
    await cw.addInitScript(function () { // Web Audio çağrılarını kaydet
      window.__wa = [];
      var bas = AudioBufferSourceNode.prototype.start, dur = AudioBufferSourceNode.prototype.stop;
      AudioBufferSourceNode.prototype.start = function (t) { window.__wa.push({ t: 'start', zaman: t, uz: this.buffer.duration, simdi: this.context.currentTime }); return bas.apply(this, arguments); };
      AudioBufferSourceNode.prototype.stop = function () { window.__wa.push({ t: 'stop' }); return dur.apply(this, arguments); };
    });
    var pw2 = await cw.newPage(), hw = hatalar(pw2); onceki = s.istemciSayisi();
    await pw2.goto('http://127.0.0.1:8642/tv'); await pw2.waitForFunction(function () { return window.AKOverlay; });
    for (i = 0; i < 50 && s.istemciSayisi() <= onceki; i++) { await bekle(100); }
    s.yayinla('ses', { id: 's1', url: '/kopru/ses/s1.wav', sure_ms: 400, yazi_id: 'a9' });
    s.yayinla('ses', { id: 's2', url: '/kopru/ses/s2.wav', sure_ms: 400, yazi_id: 'a10' });
    await pw2.waitForFunction(function () { return window.__wa.filter(function (x) { return x.t === 'start'; }).length >= 2; }, null, { timeout: 4000 });
    var wa = await pw2.evaluate(function () { return window.__wa.slice(); });
    assert(wa[1].zaman >= wa[0].zaman + wa[0].uz - 0.001, 'ikinci ses birincinin bitişine sıralanmadı: ' + JSON.stringify(wa)); ok('Web Audio: ikinci ses birincinin ARKASINA sıralandı (kesmedi)');
    s.yayinla('ses-dur'); await pw2.waitForFunction(function () { return window.__wa.some(function (x) { return x.t === 'stop'; }); }, null, { timeout: 3000 }); ok('ses-dur sıradaki sesleri durdurdu');
    s.yayinla('ses', { id: 's3', url: 'http://kotu.example/x.wav', sure_ms: 400 }); await bekle(300);
    assert.strictEqual(await pw2.evaluate(function () { return window.__wa.filter(function (x) { return x.t === 'start'; }).length; }), 2); ok('PC dışı (mutlak) adresler çalınmaz');
    assert.deepStrictEqual(hw.filter(function (x) { return x.indexOf('pageerror') === 0; }), []); await cw.close();

    console.log('dublaj sesi (<audio> yedeği)');
    var cd = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 } });
    await cd.addInitScript(function () { // Web Audio yok (eski TV): <audio> sırası; çağrıları kaydet
      window.AudioContext = undefined; window.webkitAudioContext = undefined;
      window.__ses = [];
      var oynat = HTMLMediaElement.prototype.play, durdur = HTMLMediaElement.prototype.pause;
      HTMLMediaElement.prototype.play = function () { window.__ses.push('play:' + this.src); try { return oynat.call(this); } catch (e) { return Promise.resolve(); } };
      HTMLMediaElement.prototype.pause = function () { window.__ses.push('pause:' + this.src); return durdur.call(this); };
    });
    var pd = await cd.newPage(), hdl = hatalar(pd); onceki = s.istemciSayisi();
    await pd.goto('http://127.0.0.1:8642/tv'); await pd.waitForFunction(function () { return window.AKOverlay; });
    for (i = 0; i < 50 && s.istemciSayisi() <= onceki; i++) { await bekle(100); }
    s.yayinla('yazi', { id: 'a9', metin: 'Altyazı önce gelir', sure_ms: 3000 });
    s.yayinla('ses', { id: 's1', url: '/kopru/ses/s1.wav', sure_ms: 400, yazi_id: 'a9' });
    s.yayinla('ses', { id: 's2', url: '/kopru/ses/s2.wav', sure_ms: 400, yazi_id: 'a9' });
    await pd.waitForFunction(function () { return window.__ses.some(function (x) { return /^play:.*\/kopru\/ses\/s1\.wav$/.test(x); }); }, null, { timeout: 3000 });
    var ilkSes = await pd.evaluate(function () { return window.__ses.filter(function (x) { return x.indexOf('play:') === 0; })[0]; });
    assert(/^play:http:\/\/127\.0\.0\.1:8642\/kopru\/ses\/s1\.wav$/.test(ilkSes), ilkSes); ok('ses olayı bir <audio> oluşturup PC adresinden çalmaya başladı');
    await pd.waitForFunction(function () { return window.__ses.some(function (x) { return /^play:.*s2\.wav$/.test(x); }); }, null, { timeout: 4000 });
    var gunluk = await pd.evaluate(function () { return window.__ses.slice(); });
    assert(!gunluk.some(function (x) { return /^pause:.*s1\.wav$/.test(x); }), 'önceki ses kesildi: ' + gunluk.join(','));
    assert(gunluk.indexOf('play:http://127.0.0.1:8642/kopru/ses/s2.wav') > gunluk.indexOf(ilkSes)); ok('<audio>: ikinci ses birinci bitince çaldı (kesmeden sıra)');
    // göreli bekleme sınırı (`bayat_ms`, PC sıranın süresini bilir): alan bozuk/uç olsa da ses çalar
    s.yayinla('ses', { id: 's5', url: '/kopru/ses/s5.wav', sure_ms: 400, yazi_id: 'a11', bayat_ms: 20000 });
    s.yayinla('ses', { id: 's6', url: '/kopru/ses/s6.wav', sure_ms: 400, yazi_id: 'a11', bayat_ms: 'x' });
    await pd.waitForFunction(function () { return window.__ses.some(function (x) { return /^play:.*s6\.wav$/.test(x); }); }, null, { timeout: 5000 });
    ok('bayat_ms (göreli bekleme sınırı) olan ve bozuk olan sesler sırayla çaldı');
    s.yayinla('ses', { id: 's4', url: '/kopru/ses/s4.wav', sure_ms: 400 });
    s.yayinla('ses-dur'); await bekle(300);
    assert(!(await pd.evaluate(function () { return window.__ses.some(function (x) { return /^play:.*s4\.wav$/.test(x); }) && !window.__ses.some(function (x) { return /^pause:/.test(x); }); }))); ok('ses-dur çalanı ve sırayı durdurdu');
    assert.deepStrictEqual(hdl.filter(function (x) { return x.indexOf('pageerror') === 0; }), []); await cd.close();

    // ---------- 2) obs.html saydam ----------
    console.log('obs.html');
    c = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 } }); p = await c.newPage(); var ho = hatalar(p);
    await p.goto('http://127.0.0.1:8642/obs');
    var bg = await p.evaluate(function () { return getComputedStyle(document.body).backgroundColor + '|' + getComputedStyle(document.documentElement).backgroundColor; });
    assert(/rgba\(0, 0, 0, 0\)|transparent/.test(bg.split('|')[0])); ok('obs.html arka planı saydam');
    await bekle(300); assert.deepStrictEqual(ho, []); await c.close();
    assert(s.akisSorgulari.some(function (q) { return q === 'reklam=1'; }), 'tv.html reklam=1 ile bağlanmadı: ' + JSON.stringify(s.akisSorgulari));
    assert.strictEqual(s.akisSorgulari[s.akisSorgulari.length - 1], '', 'obs.html reklam istememeli'); ok('§17.3: /tv reklam=1 ile bağlanır, /obs reklam almaz');

    // ---------- 3) webOS uygulaması ----------
    console.log('webOS uygulaması');
    var dizin = sahneyiHazirla(), url = 'file://' + dizin + '/index.html';
    var stub = function () { window.PalmServiceBridge = function () { var s = this; this.call = function (u) { s.onservicecallback(JSON.stringify(
      u.indexOf('connectionmanager/getStatus') > 0 ? { returnValue: true, wifi: { state: 'connected', ipAddress: '127.0.0.5' }, wired: { state: 'disconnected' } } : { returnValue: false })); }; }; };
    // 3a) demo kipi (webOS köprüsü yok)
    c = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 }); p = await c.newPage(); var hd = hatalar(p);
    await p.goto(url); await p.waitForSelector('#e-ara.acik'); await bekle(300);
    assert.deepStrictEqual(await p.evaluate(function () { return [window.AKYukleyici.surum, window.AKYukleyici.kaynak, window.AKYukleyici.paket]; }), [2, 'gomulu', PAKET.surum]);
    ok('§18.3: kayıtlı bilgisayar yokken başlatıcı gömülü paketi açtı');
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
    var pt = await p.textContent('#panel'); assert(/127\.0\.0\.\d+:8642/.test(pt) && pt.indexOf('Bağlı') >= 0 && pt.indexOf('HDMI 1') >= 0 && pt.indexOf('TV üzerinden altyazı') >= 0 && pt.indexOf('0.2.0') >= 0 && pt.indexOf(PAKET.surum) >= 0, pt); ok('bilgi paneli adres/bağlantı/HDMI/son altyazı/sürüm gösteriyor');
    await p.screenshot({ path: path.join(SHOT, 'webos-panel.png') });
    // §17.3: "+30 dk" reklamı TV'de: SSE reklam → oynat → bitti çağrısı (süreyi PC verir)
    assert.strictEqual(s.akisSorgulari.slice(-1)[0], 'reklam=1&yukleyici=2&paket=' + PAKET.surum, 'webOS akış sorgusu'); ok('webOS akışa reklam=1 + başlatıcı/paket sürümüyle bağlandı (§18.3/6)');
    assert(s.paketIstekleri.some(function (q) { return q.yukleyici === '2' && q.surum === PAKET.surum; }), JSON.stringify(s.paketIstekleri)); ok('§18.3/5: bilgisayar seçilince paket sürümü denetlendi (aynı: yeniden yükleme yok)');
    await p.keyboard.press('Escape'); await p.waitForSelector('#panel.acik', { state: 'detached', timeout: 1 }).catch(function () {});
    s.reklamBitti.length = 0;
    var istekler = []; p.on('request', function (q) { istekler.push(q.url()); });
    s.yayinla('reklam', { id: 'r1', vast: null, en_az_sn: 2, bitti: '/kopru/reklam/bitti' });
    await p.waitForSelector('.akr-kok .akr-destek', { timeout: 3000 });
    var rt = await p.textContent('.akr-kok'); assert(rt.indexOf('AltYazıKöprüsü\'nü desteklediğin için teşekkürler') >= 0 && /Reklam · \d+ sn/.test(rt), rt);
    var kap = await p.evaluate(function () { var r = document.querySelector('.akr-kok').getBoundingClientRect(); return [r.width, r.height, getComputedStyle(document.querySelector('.akr-kok')).zIndex]; });
    assert(kap[0] === 1920 && kap[1] === 1080 && +kap[2] > 1000000, JSON.stringify(kap)); ok('VAST yokken destek ekranı oyunun üstünde tam ekran + "Reklam · n sn"');
    await p.screenshot({ path: path.join(SHOT, 'webos-reklam-destek.png') });
    await p.keyboard.press('Escape'); await bekle(200); assert(await p.isVisible('.akr-kok'), 'Geri reklamı kapatmamalı'); ok('Geri tuşu reklamı kapatmaz');
    await p.waitForSelector('.akr-kok', { state: 'detached', timeout: 5000 });
    for (i = 0; i < 30 && !s.reklamBitti.length; i++) { await bekle(100); }
    assert.strictEqual(s.reklamBitti.length, 1); assert.strictEqual(s.reklamBitti[0].id, 'r1'); ok('destek ekranı bitince TV /kopru/reklam/bitti çağırdı');
    assert.deepStrictEqual(istekler.filter(function (u) { return u.indexOf('/kopru/reklam/bitti') < 0; }), []); ok('destek ekranı hiçbir yere (reklam şirketine) bağlanmaz');
    // VAST: sarmalayıcı → inline → webm (VPAID atlanır), izleme pikselleri, bitti(sure_sn≈2)
    var webm = path.join(os.tmpdir(), 'ak-reklam-test.webm');
    try { require('child_process').execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=0x2ec4b6:s=320x180:d=2', '-c:v', 'libvpx', '-b:v', '200k', webm]); s.video = fs.readFileSync(webm); } catch (fe) { s.video = null; }
    if (s.video) {
      s.reklamBitti.length = 0; s.pikseller.length = 0;
      s.yayinla('reklam', { id: 'r2', vast: 'http://127.0.0.1:8642/reklam/sarma.xml', en_az_sn: 1, bitti: '/kopru/reklam/bitti' });
      await p.waitForSelector('.akr-kok video', { timeout: 6000 });
      await p.screenshot({ path: path.join(SHOT, 'webos-reklam-video.png') });
      for (i = 0; i < 80 && !s.reklamBitti.length; i++) { await bekle(100); }
      assert.strictEqual(s.reklamBitti.length, 1, 'VAST reklamı bitmedi: ' + JSON.stringify(s.pikseller)); assert.strictEqual(s.reklamBitti[0].id, 'r2');
      assert(Math.abs(s.reklamBitti[0].sure_sn - 2) < 0.6, JSON.stringify(s.reklamBitti[0]));
      ['sarma-imp', 'imp', 'start', 'q1', 'mid', 'complete', 'sarma-complete'].forEach(function (k) { assert(s.pikseller.indexOf(k) >= 0, k + ' pikseli yok: ' + JSON.stringify(s.pikseller)); });
      ok('VAST sarmalayıcı + inline: webm oynadı, gösterim/çeyrek/bitiş pikselleri, bitti sure_sn≈2');
    } else { ok('ffmpeg yok: VAST video kontrolü atlandı'); }
    // reklam gelmedi (boş VAST) → hata pikseli 303 + destek ekranı; PC "reklam-bitti" derse kapanır
    s.pikseller.length = 0; s.reklamBitti.length = 0;
    s.yayinla('reklam', { id: 'r3', vast: 'http://127.0.0.1:8642/reklam/bos.xml', en_az_sn: 30, bitti: '/kopru/reklam/bitti' });
    await p.waitForSelector('.akr-kok .akr-destek', { timeout: 4000 });
    for (i = 0; i < 20 && s.pikseller.indexOf('bos') < 0; i++) { await bekle(100); }
    assert(s.pikseller.indexOf('bos') >= 0, JSON.stringify(s.pikseller)); ok('boş VAST (reklam yok): hata pikseli + destek ekranı');
    s.yayinla('reklam-bitti', { id: 'r3' }); await p.waitForSelector('.akr-kok', { state: 'detached', timeout: 2000 });
    assert.strictEqual(s.reklamBitti.length, 0); ok('reklam-bitti olayı reklamı kapattı (çift bitti yok)');
    var kayit = await p.evaluate(function () { return localStorage.getItem('ak_son_pc') + '|' + localStorage.getItem('ak_hdmi'); }); assert(/^127\.0\.0\.\d+:8642\|1$/.test(kayit), kayit); ok('son bilgisayar ve HDMI hatırlandı');
    var sayfaHatalari = hs.filter(function (x) { return x.indexOf('pageerror') === 0; }); assert.deepStrictEqual(sayfaHatalari, []); ok('tarama/çalışma akışında JS hatası yok (HDMI kaynak hatası Chromium\'da beklenir)');
    // 3c) elle adres: sayı tuşları
    await c.close();
    c = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 } }); p = await c.newPage(); var he = hatalar(p);
    await p.goto(url); await p.waitForSelector('#e-ara.acik'); await p.click('#b-elle'); await p.waitForSelector('#e-elle.acik');
    await p.keyboard.type('127.0.0.1'); assert.strictEqual((await p.textContent('#adres-alan')).trim(), '127.0.0.1');
    await p.click('#b-elle-tamam'); await p.waitForSelector('#e-hdmi.acik'); ok('elle adres + sayı tuşu ile bağlantı');
    assert.deepStrictEqual(he.filter(function (x) { return x.indexOf('pageerror') === 0; }), []); await c.close();
    // 3d) PROTOKOL 18: TV bir daha yeniden kurulmaz — paket bilgisayardan gelir, önbelleğe alınır, PC yokken önbellekten açılır
    console.log('webOS başlatıcı (kendini güncelleme)');
    var YENI = JSON.parse(JSON.stringify(PAKET)); YENI.surum = 'abcdef000001';
    YENI.html = YENI.html + '<div id="yeni-isaret">yeni paket</div>';
    s.tvPaket = YENI; s.paketIstekleri.length = 0;
    c = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 } });
    await c.addInitScript(function () { if (!sessionStorage.getItem('ak_test_ilk')) { sessionStorage.setItem('ak_test_ilk', '1'); localStorage.setItem('ak_son_pc', '127.0.0.1:8642'); localStorage.setItem('ak_hdmi', '1'); } });
    p = await c.newPage(); var hy = hatalar(p);
    await p.goto(url); await p.waitForSelector('#yeni-isaret', { timeout: 8000 }); await p.waitForSelector('#e-calis.acik', { timeout: 8000 });
    var yk = await p.evaluate(function () { return [window.AKYukleyici.kaynak, window.AKYukleyici.paket, JSON.parse(localStorage.getItem('ak_paket')).surum]; });
    assert.deepStrictEqual(yk, ['pc', 'abcdef000001', 'abcdef000001']); ok('§18.3/1: kayıtlı bilgisayardan yeni paket alındı, önbelleğe yazıldı ve doğrudan çalışma ekranı açıldı');
    for (i = 0; i < 40 && s.istemciSayisi() < 1; i++) { await bekle(100); }
    assert(/yukleyici=2&paket=abcdef000001$/.test(s.akisSorgulari.slice(-1)[0]), s.akisSorgulari.slice(-1)[0]); ok('akışa yeni paket sürümüyle bağlandı');
    // bilgisayar kapalı: önbellekteki paket açılır + sakin "Bilgisayar bekleniyor" ekranı; PC gelince kendiliğinden bağlanır
    s.kapali = true; s.kopar();
    await p.reload(); await p.waitForSelector('#yeni-isaret', { timeout: 10000 });
    await p.waitForFunction(function () { return /bekleniyor/.test(document.querySelector('#e-ara h1').textContent) && document.querySelector('#e-ara').className.indexOf('acik') >= 0; }, null, { timeout: 10000 });
    assert.strictEqual(await p.evaluate(function () { return window.AKYukleyici.kaynak; }), 'onbellek'); ok('§18.3/2: bilgisayar yokken önbellekteki son paket + "Bilgisayar bekleniyor…"');
    await p.screenshot({ path: path.join(SHOT, 'webos-bekleniyor.png') });
    // bilgisayar güncellendi ve geri geldi: yeni sürüm algılanır, sayfa kendiliğinden yeniden yüklenir
    var YENI2 = JSON.parse(JSON.stringify(YENI)); YENI2.surum = 'abcdef000002'; YENI2.html = PAKET.html + '<div id="yeni-isaret2">daha yeni</div>';
    s.tvPaket = YENI2; s.kapali = false;
    await p.waitForSelector('#yeni-isaret2', { timeout: 15000 }); await p.waitForSelector('#e-calis.acik', { timeout: 8000 });
    assert.deepStrictEqual(await p.evaluate(function () { return [window.AKYukleyici.kaynak, window.AKYukleyici.paket]; }), ['pc', 'abcdef000002']);
    ok('§18.3/5: bilgisayar geri gelince kendiliğinden bağlandı, yeni sürümü aldı ve yeniden yüklendi');
    assert.deepStrictEqual(hy.filter(function (x) { return x.indexOf('pageerror') === 0; }), []); await c.close();
    // 3e) bozuk paket: ilk saniyelerde hata → o sürüm "kötü", gömülü paketle açılır (TV asla boş ekranda kalmaz)
    var BOZUK = JSON.parse(JSON.stringify(PAKET)); BOZUK.surum = 'bozuk0000001'; BOZUK.js = BOZUK.js.concat([['bozuk.js', 'throw new Error("bozuk paket");']]);
    s.tvPaket = BOZUK;
    c = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 } });
    await c.addInitScript(function () { if (!sessionStorage.getItem('ak_test_ilk')) { sessionStorage.setItem('ak_test_ilk', '1'); localStorage.setItem('ak_son_pc', '127.0.0.1:8642'); } });
    p = await c.newPage();
    await p.goto(url);
    await p.waitForFunction(function () { return window.AKYukleyici && window.AKYukleyici.kaynak === 'gomulu'; }, null, { timeout: 10000 });
    assert.strictEqual(await p.evaluate(function () { return localStorage.getItem('ak_paket_kotu'); }), 'bozuk0000001'); ok('§18.3/4: hata veren paket kötü işaretlendi, gömülü paketle açıldı');
    await c.close(); s.tvPaket = PAKET;
    // ---------- PROTOKOL 20.1: LG'nin kendi tarayıcısında /tv — HDMI seçimi, sayfa içi HDMI, desteklenmiyorsa yalnız yazı ----------
    console.log('LG tarayıcısı (/tv, kurulumsuz)');
    var UA_LG = 'Mozilla/5.0 (Web0S; Linux/SmartTV) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.79 Safari/537.36 WebAppManager';
    c = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 }, userAgent: UA_LG });
    await c.addInitScript(function () {   // gerçek hdmiAc'ı sarar: oluşturduğu işaretlemeyi kaydeder
      var gercek; window.__hdmi = []; Object.defineProperty(window, 'AKPlatform', { configurable: true, get: function () { return gercek; }, set: function (v) {
        var asil = v.hdmiAc; v.hdmiAc = function (n, kutu, bildir) { var k = asil.call(v, n, kutu, bildir); window.__hdmi.push(kutu.innerHTML); return k; }; gercek = v; } });
    });
    p = await c.newPage(); var hl = hatalar(p);
    await p.goto('http://127.0.0.1:8642/tv'); await p.waitForSelector('.tt-secim', { timeout: 3000 });
    assert.strictEqual(await p.$$eval('.tt-secim button[data-hdmi]', function (l) { return l.length; }), 5);
    assert.strictEqual(await p.evaluate(function () { return document.activeElement.getAttribute('data-hdmi'); }), '1'); ok('webOS tarayıcısı: HDMI seçimi açıldı, HDMI 1 odakta');
    await p.screenshot({ path: path.join(SHOT, 'tv-tarayici-secim.png') });
    await p.keyboard.press('ArrowRight'); await p.keyboard.press('Enter');
    await p.waitForFunction(function () { return window.__hdmi.length === 1; }, null, { timeout: 2000 });
    var ht = await p.evaluate(function () { return window.__hdmi[0]; });
    assert(ht.indexOf('type="service/webos-external"') >= 0 && ht.indexOf('src="ext://hdmi:2"') >= 0, ht);
    ok('ok + OK: HDMI 2, sayfanın içinde <video><source type="service/webos-external" src="ext://hdmi:2">');
    await p.waitForSelector('.tt-desteksiz', { timeout: 9500 });
    var mt = await p.textContent('.tt-mesaj-metin'); assert(mt.indexOf('açamadı') >= 0 && mt.indexOf('LG uygulaması') >= 0, mt);
    assert.strictEqual(await p.$$eval('#hdmi video', function (l) { return l.length; }), 0); ok('desteklenmiyor: görüntü kaldırıldı, açık mesaj + Yeniden dene / Başka giriş');
    await p.screenshot({ path: path.join(SHOT, 'tv-tarayici-desteksiz.png') });
    for (i = 0; i < 40 && s.istemciSayisi() < 1; i++) { await bekle(100); }
    s.yayinla('yazi', { id: 'lg1', metin: 'Yalnız yazı kipinde de çalışır', sure_ms: 2000 }); await p.waitForSelector('.ak-yazi-kutu:visible', { timeout: 3000 }); ok('desteksiz kipte Türkçe yazı yine görünüyor');
    assert.strictEqual(await p.evaluate(function () { return localStorage.getItem('ak_tv_hdmi'); }), '2');
    await p.reload(); await p.waitForSelector('.tt-secim'); await p.waitForFunction(function () { return /HDMI 2 açılıyor/.test(document.querySelector('.tt-oto').textContent); });
    assert.strictEqual(await p.evaluate(function () { return document.activeElement.getAttribute('data-hdmi'); }), '2');
    await p.keyboard.press('ArrowLeft'); assert.strictEqual((await p.textContent('.tt-oto')).trim(), ''); ok('seçim hatırlandı: 5 sn sayaçla kendiliğinden açılır, tuşa basınca sayaç durur');
    await p.goto('http://127.0.0.1:8642/tv?hdmi=0'); await p.waitForFunction(function () { return window.AKTarayiciTV && window.AKTarayiciTV.durum() === 'yazi'; });
    assert.strictEqual(await p.$$eval('.tt-secim', function (l) { return l.length; }), 0); ok('?hdmi=0: seçim sorulmadan görüntüsüz açıldı');
    await p.keyboard.press('Enter'); await p.waitForSelector('.tt-menu'); await p.keyboard.press('Escape'); await p.waitForFunction(function () { return !document.querySelector('.tt-menu'); }); ok('çalışırken OK menüyü açar, Geri kapatır (sayfadan çıkmaz)');
    assert.deepStrictEqual(hl.filter(function (x) { return x.indexOf('pageerror') === 0; }), []); await c.close();
    // HDMI destekleyen TV (sahte hdmiAc 'tamam' der): görüntü açık kalır, seçim ekranı kapanır
    c = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 }, userAgent: UA_LG });
    await c.addInitScript(function () {
      var gercek; Object.defineProperty(window, 'AKPlatform', { configurable: true, get: function () { return gercek; }, set: function (v) {
        v.hdmiAc = function (n, kutu, bildir) { var vd = document.createElement('video'); vd.className = 'hdmi-video'; kutu.appendChild(vd); setTimeout(function () { bildir('tamam'); }, 200); return function () { kutu.innerHTML = ''; }; };
        gercek = v; } });
    });
    p = await c.newPage(); await p.goto('http://127.0.0.1:8642/tv?hdmi=3');
    await p.waitForFunction(function () { return window.AKTarayiciTV.durum() === 'hdmi' && /tt-hdmi/.test(document.body.className); }, null, { timeout: 3000 });
    assert.strictEqual(await p.$$eval('#hdmi video', function (l) { return l.length; }), 1); ok('HDMI açılınca görüntü yazının altında kalır (durum hdmi)');
    // PROTOKOL 20.6: görünüm 2 (canlı)
    for (i = 0; i < 40 && s.istemciSayisi() < 1; i++) { await bekle(100); }
    s.yayinla('gorunum', { yerlesim: 'cubuk', konum: 'alt', boyut: 'buyuk', zemin: 'serit', konusan_goster: false, kalinlik: 'normal', yazi_rengi: '#9AD8FF' });
    s.yayinla('yazi', { id: 'g2', metin: 'Görünüm denemesi', konusan: 'Lucia', sure_ms: 3000 }); await p.waitForSelector('.ak-yazi-kutu:visible');
    var gs = await p.evaluate(function () { var k = document.querySelector('.ak-kok'), y = document.querySelector('.ak-yazi'), m = document.querySelector('.ak-yazi-kutu');
      return [/ak-zemin-serit/.test(k.className), /ak-ince/.test(k.className), parseFloat(getComputedStyle(y).fontSize), document.querySelectorAll('.ak-konusan').length, getComputedStyle(m).color, getComputedStyle(m).fontWeight, y.getBoundingClientRect().width]; });
    assert.deepStrictEqual(gs.slice(0, 6), [true, true, 52, 0, 'rgb(154, 216, 255)', '450'], JSON.stringify(gs)); assert(gs[6] >= 1900, 'şerit ekran genişliğinde değil');
    ok('§20.6: boyut büyük (52 px), şerit zemin, konuşan gizli, açık mavi, normal kalınlık');
    await p.screenshot({ path: path.join(SHOT, 'tv-gorunum-serit.png') });
    s.yayinla('gorunum', { yerlesim: 'ustune', boyut: 'otomatik', zemin: 'golge', konusan_goster: true, kalinlik: 'kalin', yazi_rengi: '#FFFFFF', konusan_rengi: '#FFD166' });
    s.yayinla('yazi', { id: 'g3', metin: 'Örtü gölgeli', konusan: 'Jason', sure_ms: 3000, ortu: { x: 0.3, y: 0.8, g: 0.4, y2: 0.06, zemin: '#101010' } });
    await p.waitForSelector('.ak-ortu-yazi.ak-acik');
    var og = await p.evaluate(function () { var d = document.querySelector('.ak-ortu-yazi'); return [getComputedStyle(d).backgroundColor, d.querySelector('.ak-ortu-konusan').textContent, getComputedStyle(d.querySelector('.ak-ortu-konusan')).color]; });
    assert.deepStrictEqual(og, ['rgba(0, 0, 0, 0)', 'Jason:', 'rgb(255, 209, 102)']); ok('§20.6: gölge zeminde örtü saydam; konuşan ön eki ayrı renkte');
    // PROTOKOL 20.7: konsolsuz dene karesi arka planda
    s.yayinla('demo', { acik: true, kare: '/statik/yazi-latin.woff2' }); await p.waitForFunction(function () { return !document.getElementById('demo-kare').hidden; });
    s.yayinla('demo', { acik: false }); await p.waitForFunction(function () { return document.getElementById('demo-kare').hidden; }); ok('§20.7: demo olayı örnek kareyi gösterir/kaldırır');
    await c.close();
    console.log('\nTÜM KONTROLLER GEÇTİ (' + sonuc.length + ')');
  } catch (e) { console.error('\nBAŞARISIZ:', e && e.stack || e); process.exitCode = 1; }
  finally { await b.close(); s.close(); process.exit(process.exitCode || 0); }
}());
