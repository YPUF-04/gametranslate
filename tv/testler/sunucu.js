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
    if (q.method === 'OPTIONS') { r.setHeader('Access-Control-Allow-Headers', '*'); r.statusCode = 204; r.end(); return; }
    if (u === '/kopru/akis') { sunucu.akisSorgulari.push(q.url.split('?')[1] || ''); }
    if (u === '/kopru/reklam/bitti' && q.method === 'POST') {   // §17.3: TV reklamı bitirdi
      var g = ''; q.on('data', function (p) { g += p; }); q.on('end', function () { sunucu.reklamBitti.push(JSON.parse(g)); r.setHeader('Content-Type', 'application/json'); r.end('{"tamam":true}'); }); return;
    }
    if (u.indexOf('/reklam/piksel/') === 0) { sunucu.pikseller.push(u.slice(15)); r.setHeader('Content-Type', 'image/gif'); r.end(Buffer.from('R0lGODlhAQABAAAAACw=', 'base64')); return; }
    if (u === '/reklam/vast.xml' || u === '/reklam/bos.xml' || u === '/reklam/sarma.xml') {
      r.setHeader('Content-Type', 'text/xml'); r.end(sunucu.vast[u]); return;
    }
    if (u === '/reklam/video.webm' && sunucu.video) { r.setHeader('Content-Type', 'video/webm'); r.end(sunucu.video); return; }
    if (u === '/kopru/merhaba') { r.setHeader('Content-Type', 'application/json'); r.end('{"uygulama":"altyazikoprusu","surum":"0.1.0","protokol":1,"ad":"TEST-PC"}'); return; }
    if (u === '/kopru/akis') {
      r.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'Access-Control-Allow-Origin': '*' });
      r.write('event: gorunum\ndata: ' + JSON.stringify(sunucu.gorunum) + '\n\n');
      istemciler.push(r); q.on('close', function () { istemciler.splice(istemciler.indexOf(r), 1); }); return;
    }
    if (u.indexOf('/kopru/ses/') === 0 && /\.wav$/.test(u)) { // dublaj sesi (0,4 sn sessiz WAV)
      var n = 3200, w = Buffer.alloc(44 + n * 2); w.write('RIFF', 0); w.writeUInt32LE(36 + n * 2, 4); w.write('WAVEfmt ', 8); w.writeUInt32LE(16, 16); w.writeUInt16LE(1, 20); w.writeUInt16LE(1, 22);
      w.writeUInt32LE(8000, 24); w.writeUInt32LE(16000, 28); w.writeUInt16LE(2, 32); w.writeUInt16LE(16, 34); w.write('data', 36); w.writeUInt32LE(n * 2, 40);
      r.setHeader('Content-Type', 'audio/wav'); r.end(w); return;
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
  sunucu.akisSorgulari = []; sunucu.reklamBitti = []; sunucu.pikseller = []; sunucu.video = null;
  var P = 'http://127.0.0.1:8642/reklam/piksel/';
  sunucu.vast = {
    '/reklam/vast.xml': '<?xml version="1.0"?><VAST version="4.0"><Ad id="1"><InLine><AdSystem>Test</AdSystem><AdTitle>T</AdTitle>' +
      '<Impression><![CDATA[' + P + 'imp?c=[CACHEBUSTING]]]></Impression><Error><![CDATA[' + P + 'hata?k=[ERRORCODE]]]></Error><Creatives><Creative><Linear><Duration>00:00:02</Duration>' +
      '<TrackingEvents><Tracking event="start"><![CDATA[' + P + 'start]]></Tracking><Tracking event="firstQuartile"><![CDATA[' + P + 'q1]]></Tracking>' +
      '<Tracking event="midpoint"><![CDATA[' + P + 'mid]]></Tracking><Tracking event="complete"><![CDATA[' + P + 'complete]]></Tracking></TrackingEvents>' +
      '<MediaFiles><MediaFile delivery="progressive" type="application/javascript" apiFramework="VPAID" width="640" height="360"><![CDATA[http://127.0.0.1:8642/vpaid.js]]></MediaFile>' +
      '<MediaFile delivery="progressive" type="video/webm" width="320" height="180"><![CDATA[http://127.0.0.1:8642/reklam/video.webm]]></MediaFile></MediaFiles>' +
      '</Linear></Creative></Creatives></InLine></Ad></VAST>',
    '/reklam/sarma.xml': '<VAST version="3.0"><Ad><Wrapper><Impression>' + P + 'sarma-imp</Impression><VASTAdTagURI><![CDATA[http://127.0.0.1:8642/reklam/vast.xml]]></VASTAdTagURI>' +
      '<Creatives><Creative><Linear><TrackingEvents><Tracking event="complete">' + P + 'sarma-complete</Tracking></TrackingEvents></Linear></Creative></Creatives></Wrapper></Ad></VAST>',
    '/reklam/bos.xml': '<VAST version="4.0"><Error><![CDATA[' + P + 'bos?k=[ERRORCODE]]]></Error></VAST>'
  };
  sunucu.kopar = function () { istemciler.slice().forEach(function (c) { c.destroy(); }); };
  return sunucu;
}
module.exports = { olustur: olustur };
