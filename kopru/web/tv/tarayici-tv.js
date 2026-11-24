// SPDX-License-Identifier: AGPL-3.0-only
// PROTOKOL 20.1: LG'de kurulumsuz yol. TV'nin kendi tarayıcısı /tv sayfasını açar; sayfa konsolun HDMI görüntüsünü
// kendi içinde (webOS <video> + ext://hdmi:N) oynatır ve Türkçe yazıyı üstüne çizer. Destek yoksa yalnız yazıyla sürer.
// Yalnız ES5. Paketli LG uygulamasının platform-webos.js'indeki hdmiAc yeniden kullanılır (window.AKPlatform).
(function (pencere) {
  'use strict';
  var belge = pencere.document, q = pencere.location.search || '';
  var KEY = 'ak_tv_hdmi', BEKLE_MS = 8000, OTO_SN = 5;
  var tr = (pencere.navigator.language || 'tr').toLowerCase().indexOf('tr') === 0;
  var M = tr ? {
    baslik: 'Konsol hangi HDMI girişine takılı?',
    ipucu: 'Kumandanın oklarıyla seçip OK’a basın. Görüntü bu sayfanın içinde açılır, Türkçe yazı üstüne gelir.',
    goruntusuz: 'Görüntüsüz (yalnız yazı)', oto: '{g} açılıyor… ({n})  ·  değiştirmek için bir tuşa basın',
    acilmadi: 'Bu TV’nin tarayıcısı HDMI görüntüsünü sayfada açamadı. Türkçe yazılar siyah ekranda gösteriliyor. ' +
      'Oyunun üstünde görmek için panelde “LG uygulaması” yolunu kullanın.',
    kisa: 'HDMI görüntüsü açılamadı · OK: menü', yeniden: 'Yeniden dene', baska: 'Başka giriş', kapat: 'Kapat',
    menu: 'Ayarlar', yalniz: 'Yalnız yazı', aciliyor: '{g} açılıyor…'
  } : {
    baslik: 'Which HDMI input is the console on?',
    ipucu: 'Choose with the arrow keys and press OK. The picture opens inside this page with the translation on top.',
    goruntusuz: 'No picture (text only)', oto: 'Opening {g}… ({n})  ·  press any key to change',
    acilmadi: 'This TV’s browser could not show the HDMI picture inside the page. Translations are shown on a black ' +
      'screen. To see them over the game, use the “LG app” option in the panel.',
    kisa: 'HDMI picture unavailable · OK: menu', yeniden: 'Retry', baska: 'Other input', kapat: 'Close',
    menu: 'Settings', yalniz: 'Text only', aciliyor: 'Opening {g}…'
  };
  function bicim(s, v) { return s.replace(/\{(\w+)\}/g, function (_, k) { return v[k]; }); }
  function depoOku() { try { return pencere.localStorage.getItem(KEY); } catch (e) { return null; } }
  function depoYaz(v) { try { pencere.localStorage.setItem(KEY, v); } catch (e) { /* yok say */ } }
  function el(etiket, sinif, metin) { var e = belge.createElement(etiket); if (sinif) { e.className = sinif; } if (metin) { e.textContent = metin; } return e; }
  function webosMu() { return /Web0S|webOS/i.test(pencere.navigator.userAgent || '') || /[?&]webos=1/.test(q); }

  var kontrol = null, kutu = null, ui = null, durum = 'secim', giris = null, kapatHdmi = null, zaman = null, otoZaman = null;
  var mesajZaman = null, kilit = null, canli = null;

  function gorunGiris(n) { return n > 0 ? 'HDMI ' + n : M.goruntusuz; }

  // ---- ekran açık kalsın (sayfa içi; asıl güvence PC'nin SSAP dokunuşu, PROTOKOL 20.3) ----
  function uyanikTut() {
    try {
      if (pencere.navigator.wakeLock && pencere.navigator.wakeLock.request) {
        pencere.navigator.wakeLock.request('screen').then(function (k) { kilit = k; }, function () { kilit = null; });
        return;
      }
    } catch (e) { /* desteklenmiyor */ }
    if (canli || giris > 0) { return; }
    try {   // görüntüsüz kip: 2×2 tuvalden sessiz, döngülü video (varsa)
      var c = el('canvas'), x = c.getContext('2d'), v = el('video', 'tt-canli'), t = 0;
      c.width = 2; c.height = 2;
      if (!c.captureStream) { return; }
      v.muted = true; v.setAttribute('muted', 'muted'); v.setAttribute('playsinline', 'playsinline');
      v.srcObject = c.captureStream(1);
      canli = { v: v, z: pencere.setInterval(function () { t = 1 - t; x.fillStyle = t ? '#000001' : '#000000'; x.fillRect(0, 0, 2, 2); }, 1000) };
      belge.body.appendChild(v);
      var p = v.play(); if (p && p.catch) { p.catch(function () { /* yok say */ }); }
    } catch (e2) { canli = null; }
  }
  belge.addEventListener('visibilitychange', function () { if (!belge.hidden && durum !== 'secim' && !kilit) { uyanikTut(); } }, false);

  function tamEkran() {
    var d = belge.documentElement, f = d.requestFullscreen || d.webkitRequestFullscreen;
    if (f && !(belge.fullscreenElement || belge.webkitFullscreenElement)) { try { var p = f.call(d); if (p && p.catch) { p.catch(function () { /* yok say */ }); } } catch (e) { /* yok say */ } }
  }

  // ---- arayüz ----
  function odakla(kap) { var b = kap.getElementsByTagName('button'); if (b.length) { try { b[0].focus(); } catch (e) { /* yok say */ } } }
  function dugme(metin, fn, ekSinif) {
    var b = el('button', 'tt-dugme' + (ekSinif ? ' ' + ekSinif : ''), metin);
    b.type = 'button'; b.addEventListener('click', function () { fn(); }, false); return b;
  }
  function temizle() { while (ui.firstChild) { ui.removeChild(ui.firstChild); } ui.className = 'tt-ui'; }
  function secimEkrani(oto) {
    durum = 'secim'; temizle(); ui.className = 'tt-ui tt-secim';
    var kap = el('div', 'tt-kutu'), satir = el('div', 'tt-satir'), i, b, onceki = parseInt(oto, 10);
    kap.appendChild(el('h1', 'tt-baslik', M.baslik));
    kap.appendChild(el('p', 'tt-ipucu', M.ipucu));
    for (i = 1; i <= 4; i++) { (function (n) { satir.appendChild(b = dugme('HDMI ' + n, function () { sec(n); }, 'tt-buyuk')); b.setAttribute('data-hdmi', String(n)); }(i)); }
    kap.appendChild(satir);
    var alt = el('div', 'tt-satir'); b = dugme(M.goruntusuz, function () { sec(0); }); b.setAttribute('data-hdmi', '0'); alt.appendChild(b); kap.appendChild(alt);
    var sayac = el('p', 'tt-oto'); kap.appendChild(sayac);
    ui.appendChild(kap);
    var hedef = kap.querySelector('[data-hdmi="' + (onceki >= 0 ? onceki : 1) + '"]') || kap.getElementsByTagName('button')[0];
    try { hedef.focus(); } catch (e) { /* yok say */ }
    if (onceki >= 0 && onceki <= 4 && oto !== null) {
      var n = OTO_SN;
      sayac.textContent = bicim(M.oto, { g: gorunGiris(onceki), n: n });
      otoZaman = pencere.setInterval(function () {
        n--; if (n <= 0) { otoIptal(); sec(onceki, true); return; }
        sayac.textContent = bicim(M.oto, { g: gorunGiris(onceki), n: n });
      }, 1000);
    }
  }
  function otoIptal() { if (otoZaman) { pencere.clearInterval(otoZaman); otoZaman = null; var s = ui.querySelector('.tt-oto'); if (s) { s.textContent = ''; } } }

  function hdmiKapat() { if (zaman) { pencere.clearTimeout(zaman); zaman = null; } if (kapatHdmi) { kapatHdmi(); kapatHdmi = null; } belge.body.className = belge.body.className.replace(/\s*tt-hdmi\b/g, ''); }

  function sec(n, kendiliginden) {
    otoIptal(); giris = n; depoYaz(String(n)); temizle(); hdmiKapat();
    if (!kendiliginden) { tamEkran(); }
    if (kontrol && kontrol.sesAc) { kontrol.sesAc(); }
    uyanikTut();
    if (n <= 0) { durum = 'yazi'; return; }
    durum = 'aciliyor';
    var not = el('div', 'tt-not', bicim(M.aciliyor, { g: gorunGiris(n) })); ui.appendChild(not);
    var P = pencere.AKPlatform;
    if (!P || !P.hdmiAc) { desteklenmiyor(); return; }
    var bitti = false;
    kapatHdmi = P.hdmiAc(n, kutu, function (d) {
      if (bitti) { return; }
      if (d === 'tamam') { bitti = true; if (zaman) { pencere.clearTimeout(zaman); zaman = null; } durum = 'hdmi'; temizle(); belge.body.className += ' tt-hdmi'; }
      else { bitti = true; desteklenmiyor(); }
    });
    zaman = pencere.setTimeout(function () { zaman = null; if (!bitti) { bitti = true; desteklenmiyor(); } }, BEKLE_MS);
  }

  function desteklenmiyor() {
    hdmiKapat(); durum = 'desteksiz'; temizle(); ui.className = 'tt-ui tt-desteksiz';
    var kap = el('div', 'tt-kutu tt-mesaj'), satir = el('div', 'tt-satir');
    kap.appendChild(el('p', 'tt-mesaj-metin', M.acilmadi));
    satir.appendChild(dugme(M.yeniden, function () { sec(giris); }));
    satir.appendChild(dugme(M.baska, function () { secimEkrani(null); }));
    kap.appendChild(satir); ui.appendChild(kap); odakla(kap);
    if (mesajZaman) { pencere.clearTimeout(mesajZaman); }
    mesajZaman = pencere.setTimeout(function () {   // 10 sn sonra köşede küçük hatırlatma
      mesajZaman = null; if (durum !== 'desteksiz') { return; }
      temizle(); ui.appendChild(el('div', 'tt-kose', M.kisa));
    }, 10000);
  }

  function menu() {
    if (durum === 'menu') { menuKapat(); return; }
    var onceki = durum; durum = 'menu'; temizle(); ui.className = 'tt-ui tt-menu';
    var kap = el('div', 'tt-kutu'), satir = el('div', 'tt-satir');
    kap.appendChild(el('h1', 'tt-baslik', M.menu));
    satir.appendChild(dugme(M.baska, function () { hdmiKapat(); secimEkrani(null); }));
    satir.appendChild(dugme(M.yalniz, function () { sec(0); }));
    satir.appendChild(dugme(M.yeniden, function () { sec(giris); }));
    satir.appendChild(dugme(M.kapat, function () { menuKapat(onceki); }));
    kap.appendChild(satir); ui.appendChild(kap); odakla(kap);
    ui._onceki = onceki;
  }
  function menuKapat(onceki) {
    temizle(); durum = onceki || ui._onceki || (kapatHdmi ? 'hdmi' : 'yazi');
    if (durum === 'desteksiz') { ui.appendChild(el('div', 'tt-kose', M.kisa)); }
  }

  function yonOdak(yon) {
    var l = ui.getElementsByTagName('button'), a = belge.activeElement, i, r, c, en = null, enS = 1e12, dx, dy, s;
    if (!l.length) { return; }
    if (!a || a.tagName !== 'BUTTON') { l[0].focus(); return; }
    r = a.getBoundingClientRect();
    for (i = 0; i < l.length; i++) {
      if (l[i] === a) { continue; }
      c = l[i].getBoundingClientRect(); dx = (c.left + c.width / 2) - (r.left + r.width / 2); dy = (c.top + c.height / 2) - (r.top + r.height / 2);
      if ((yon === 'sol' && dx >= -5) || (yon === 'sag' && dx <= 5) || (yon === 'yukari' && dy >= -5) || (yon === 'asagi' && dy <= 5)) { continue; }
      s = (yon === 'sol' || yon === 'sag') ? Math.abs(dx) + Math.abs(dy) * 4 : Math.abs(dy) + Math.abs(dx) * 4;
      if (s < enS) { enS = s; en = l[i]; }
    }
    if (en) { en.focus(); }
  }

  function tus(e) {
    var k = e.keyCode;
    otoIptal();
    if (kontrol && kontrol.sesAc) { kontrol.sesAc(); }
    if (k === 461 || k === 27 || k === 8) {   // Geri: menü aç/kapat, sayfadan çıkma
      e.preventDefault();
      if (durum === 'menu') { menuKapat(); } else if (durum !== 'secim') { menu(); }
      return;
    }
    var y = k === 37 ? 'sol' : k === 39 ? 'sag' : k === 38 ? 'yukari' : k === 40 ? 'asagi' : null;
    if (y && ui.getElementsByTagName('button').length) { e.preventDefault(); yonOdak(y); return; }
    if (k === 13) {
      var a = belge.activeElement;
      if (a && a.tagName === 'BUTTON' && ui.contains(a)) { return; }   // tarayıcı kendisi tıklar
      if (durum === 'hdmi' || durum === 'yazi' || durum === 'desteksiz') { e.preventDefault(); menu(); }
    }
  }

  pencere.AKTarayiciTV = {
    gerekli: function () { return webosMu() || /[?&]hdmi=\d/.test(q); },
    // kok: bindirme kökü; kutuEl: HDMI <video>'nun konacağı (bindirmenin altında) kutu
    baslat: function (k, kutuEl, uiEl) {
      kontrol = k; kutu = kutuEl; ui = uiEl;
      belge.addEventListener('keydown', tus, false);
      var m = /[?&]hdmi=(\d)/.exec(q);
      if (m) { sec(parseInt(m[1], 10), true); return; }
      secimEkrani(depoOku());
    },
    durum: function () { return durum; }
  };
}(window));
