// SPDX-License-Identifier: AGPL-3.0-only
// Test için küçük sahte Köprü: kopru/web/tv/ dosyalarını sunar ve /kopru/merhaba + /kopru/akis (SSE) uç noktalarını taklit eder.
var http = require('http'), fs = require('fs'), path = require('path');
var TV = path.join(__dirname, '..', '..', 'kopru', 'web', 'tv');
var TUR = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html; charset=utf-8' };

function olustur() {
  var istemciler = [], sunucu;
  sunucu = http.createServer(function (q, r) {
    var u = q.url.split('?')[0];
    r.setHeader('Access-Control-Allow-Origin', '*');
    if (u === '/kopru/merhaba') { r.setHeader('Content-Type', 'application/json'); r.end('{"uygulama":"altyazikoprusu","surum":"0.1.0","protokol":1,"ad":"TEST-PC"}'); return; }
    if (u === '/kopru/akis') {
      r.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'Access-Control-Allow-Origin': '*' });
      r.write('event: gorunum\ndata: ' + JSON.stringify(sunucu.gorunum) + '\n\n');
      istemciler.push(r); q.on('close', function () { istemciler.splice(istemciler.indexOf(r), 1); }); return;
    }
    var dosya = u === '/tv' ? 'tv.html' : u === '/obs' ? 'obs.html' : u.indexOf('/statik/') === 0 ? u.slice(8) : null;
    if (dosya && dosya.indexOf('..') < 0 && fs.existsSync(path.join(TV, dosya))) {
      r.setHeader('Content-Type', TUR[path.extname(dosya)] || 'text/plain'); r.end(fs.readFileSync(path.join(TV, dosya))); return;
    }
    r.statusCode = 404; r.end('yok');
  });
  sunucu.gorunum = { yazi_boyutu: 44, konum: 'alt', kenar_bosluk: 0.08, arka_plan: 0.55, yazi_rengi: '#FFFFFF', konusan_rengi: '#FFD166', asil_goster: false, ekran_cevir: true };
  sunucu.yayinla = function (ad, veri) { var s = 'event: ' + ad + '\ndata: ' + JSON.stringify(veri || {}) + '\n\n'; istemciler.forEach(function (c) { c.write(s); }); };
  sunucu.istemciSayisi = function () { return istemciler.length; };
  sunucu.kopar = function () { istemciler.slice().forEach(function (c) { c.destroy(); }); };
  return sunucu;
}
module.exports = { olustur: olustur };
