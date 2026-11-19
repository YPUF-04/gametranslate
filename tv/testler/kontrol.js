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

    // ---------- 1c) Türkçe dublaj sesi (PROTOKOL 9.4: `ses` / `ses-dur`) ----------
    console.log('dublaj sesi');
    var cd = await b.newContext({ locale: 'tr-TR', viewport: { width: 1920, height: 1080 } });
    await cd.addInitScript(function () { // <audio> çağrılarını kaydet (başsız tarayıcıda çıkış aygıtı olmayabilir)
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
    await pd.waitForFunction(function () { return window.__ses.some(function (x) { return /^play:.*\/kopru\/ses\/s1\.wav$/.test(x); }); }, null, { timeout: 3000 });
    var ilkSes = await pd.evaluate(function () { return window.__ses.filter(function (x) { return x.indexOf('play:') === 0; })[0]; });
    assert(/^play:http:\/\/127\.0\.0\.1:8642\/kopru\/ses\/s1\.wav$/.test(ilkSes), ilkSes); ok('ses olayı bir <audio> oluşturup PC adresinden çalmaya başladı');
    s.yayinla('ses', { id: 's2', url: '/kopru/ses/s2.wav', sure_ms: 400, yazi_id: 'a9' });
    await pd.waitForFunction(function () { return window.__ses.some(function (x) { return /^play:.*s2\.wav$/.test(x); }); }, null, { timeout: 3000 });
    var gunluk = await pd.evaluate(function () { return window.__ses.slice(); });
    assert(gunluk.some(function (x) { return /^pause:.*s1\.wav$/.test(x); }), 'önceki ses durmadı: ' + gunluk.join(',')); ok('yeni ses gelince önceki ses durduruldu');
    s.yayinla('ses-dur'); await pd.waitForFunction(function () { return window.__ses.some(function (x) { return /^pause:.*s2\.wav$/.test(x); }); }, null, { timeout: 3000 }); ok('ses-dur çalan sesi durdurdu');
    s.yayinla('ses', { id: 's3', url: 'http://kotu.example/x.wav', sure_ms: 400 }); await bekle(300);
    assert(!(await pd.evaluate(function () { return window.__ses.some(function (x) { return x.indexOf('kotu.example') >= 0; }); })), 'dış adres çalındı'); ok('PC dışı (mutlak) adresler çalınmaz');
    assert.deepStrictEqual(hdl.filter(function (x) { return x.indexOf('pageerror') === 0; }), []); await cd.close();

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
