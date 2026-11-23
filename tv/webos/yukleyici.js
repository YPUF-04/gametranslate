// SPDX-License-Identifier: AGPL-3.0-only
// AltYazıKöprüsü başlatıcısı (PROTOKOL 18). Kasıtlı olarak küçük ve kararlı (ES5): uygulamanın kendisini
// (gövde + CSS + JS) bilgisayardan alır, son iyi paketi önbellekte tutar; bilgisayar yoksa önbellekteki ya da pakete
// gömülü (gomulu.js) uygulama açılır. Bu dosya değişmedikçe TV uygulaması bir daha yeniden kurulmaz.
(function () {
  'use strict';
  var SURUM = 2, PORT = 8642, UYG = 'altyazikoprusu-tv';
  var K_PC = 'ak_son_pc', K_PAKET = 'ak_paket', K_KOTU = 'ak_paket_kotu', K_YEDEK = 'ak_yukleyici_yedek';
  var EN_COK = 1500000, HATA_PENCERESI_MS = 8000;
  var calisan = null, kotu = depoOku(K_KOTU) || '';

  function depoOku(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function depoYaz(k, v) { try { window.localStorage.setItem(k, v); return true; } catch (e) { return false; } }
  function depoSil(k) { try { window.localStorage.removeItem(k); } catch (e) { /* yok say */ } }
  function oturumOku(k) { try { return window.sessionStorage.getItem(k); } catch (e) { return null; } }
  function oturumYaz(k, v) { try { window.sessionStorage.setItem(k, v); } catch (e) { /* yok say */ } }
  function adresUrl(a) { return 'http://' + (a.indexOf(':') < 0 ? a + ':' + PORT : a); }
  function alt(m) { var e = document.getElementById('ak-bekle-alt'); if (e) { e.textContent = m; } }
  function tr() { return String(navigator.language || 'tr').toLowerCase().indexOf('tr') === 0; }

  function jsonAl(url, ms, tamam, hata) {
    var x = new XMLHttpRequest(), bitti = false;
    function son(v) { if (bitti) { return; } bitti = true; if (v) { tamam(v); } else { hata(); } }
    try {
      x.open('GET', url, true); x.timeout = ms;
      x.onload = function () { var v = null; try { v = x.status === 200 ? JSON.parse(x.responseText) : null; } catch (e) { v = null; } son(v && v.uygulama === UYG ? v : null); };
      x.onerror = function () { son(null); }; x.ontimeout = function () { son(null); };
      x.send();
    } catch (e) { son(null); }
  }

  function gecerli(p) {
    var i;
    if (!p || p.uygulama !== UYG || typeof p.surum !== 'string' || typeof p.html !== 'string' ||
        Object.prototype.toString.call(p.css) !== '[object Array]' || Object.prototype.toString.call(p.js) !== '[object Array]' || !p.js.length) { return false; }
    for (i = 0; i < p.css.length; i++) { if (typeof p.css[i] !== 'string') { return false; } }
    for (i = 0; i < p.js.length; i++) { if (!p.js[i] || typeof p.js[i][0] !== 'string' || typeof p.js[i][1] !== 'string') { return false; } }
    return true;
  }
  function onbellek() { var p = null; try { p = JSON.parse(depoOku(K_PAKET) || 'null'); } catch (e) { p = null; } return gecerli(p) && p.surum !== kotu ? p : null; }
  function onbellegeYaz(p) {
    var s = JSON.stringify(p);
    if (s.length > EN_COK || !depoYaz(K_PAKET, s)) { depoSil(K_PAKET); return false; }
    return true;
  }
  function gomulu() { var p = window.AK_GOMULU_PAKET; return gecerli(p) ? p : null; }

  // Paket açılamadı / ilk saniyelerde hata verdi: o sürüm "kötü", gömülüyle bir kez yeniden aç.
  function kotuIsaretle(p, kaynak) {
    if (kaynak === 'gomulu' || oturumOku(K_YEDEK) === '1') { return; }
    kotu = p.surum; depoYaz(K_KOTU, p.surum); depoSil(K_PAKET); oturumYaz(K_YEDEK, '1');
    try { window.location.reload(); } catch (e) { /* yok say */ }
  }

  function calistir(p, kaynak) {
    var bas = document.getElementsByTagName('head')[0], i, s, basla = new Date().getTime(), hata = false;
    calisan = { surum: p.surum, kaynak: kaynak };
    A.paket = p.surum; A.kaynak = kaynak;
    function dinle() { if (new Date().getTime() - basla < HATA_PENCERESI_MS && !hata) { hata = true; setTimeout(function () { kotuIsaretle(p, kaynak); }, 0); } }
    window.addEventListener('error', dinle, false);
    setTimeout(function () { window.removeEventListener('error', dinle, false); }, HATA_PENCERESI_MS);
    try {
      var eski = document.getElementById('ak-yukleyici-stil'); if (eski) { eski.parentNode.removeChild(eski); }
      for (i = 0; i < p.css.length; i++) { s = document.createElement('style'); s.appendChild(document.createTextNode(p.css[i])); bas.appendChild(s); }
      document.body.innerHTML = p.html;
      for (i = 0; i < p.js.length; i++) {
        s = document.createElement('script');
        s.text = p.js[i][1] + '\n//# sourceURL=ak-' + p.js[i][0];
        document.body.appendChild(s);   // satır içi betik eklendiği anda çalışır
      }
    } catch (e) { dinle(); }
  }

  function yedekle(neden) {
    var o = onbellek(), g = gomulu();
    if (o) { calistir(o, 'onbellek'); return; }
    if (g) { calistir(g, 'gomulu'); return; }
    alt(neden || (tr() ? 'Uygulama yüklenemedi. Bilgisayarı açıp TV uygulamasını yeniden başlatın.' : 'The app could not be loaded. Start your computer and reopen the TV app.'));
  }

  function istekUrl(adres, surum) { return adresUrl(adres) + '/kopru/tv/uygulama?yukleyici=' + SURUM + '&surum=' + encodeURIComponent(surum || ''); }

  function basla() {
    var pc = depoOku(K_PC), o = onbellek();
    if (oturumOku(K_YEDEK) === '1') { oturumYaz(K_YEDEK, ''); var g = gomulu(); if (g) { calistir(g, 'gomulu'); return; } }
    if (!pc) { yedekle(); return; }
    alt(tr() ? 'Bilgisayara bağlanılıyor…' : 'Connecting to your computer…');
    jsonAl(istekUrl(pc, o && o.surum), 4000, function (v) {
      if (v.ayni && o && v.surum === o.surum) { calistir(o, 'pc'); return; }
      if (gecerli(v) && v.surum !== kotu) { onbellegeYaz(v); calistir(v, 'pc'); return; }
      yedekle();   // eski_yukleyici ya da kötü sürüm: elimizdekiyle aç
    }, function () { yedekle(); });
  }

  var A = window.AKYukleyici = {
    surum: SURUM, paket: null, kaynak: null,
    // Bilgisayardaki paket farklıysa önbelleğe yazar; cb(true) = yeniden yüklemek gerekir.
    denetle: function (adres, cb) {
      jsonAl(istekUrl(adres, calisan && calisan.surum), 5000, function (v) {
        var yeni = !v.ayni && gecerli(v) && v.surum !== kotu && (!calisan || v.surum !== calisan.surum);
        if (yeni) { onbellegeYaz(v); }
        if (cb) { cb(!!yeni); }
      }, function () { if (cb) { cb(false); } });
    },
    yenile: function () { try { window.location.reload(); } catch (e) { /* yok say */ } }
  };
  basla();
}());
