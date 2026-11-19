// SPDX-License-Identifier: AGPL-3.0-only
// AltYazıKöprüsü - LG webOS TV uygulaması (ES5). Ekranlar: arama, HDMI seçimi, elle adres, çalışıyor, bilgi paneli, deneme.
(function () {
  'use strict';
  var SURUM = '0.1.0', PORT = 8642, T = window.AKI18N.t, P = window.AKPlatform;
  var KEY_PC = 'ak_son_pc', KEY_HDMI = 'ak_hdmi';

  // ---- küçük yardımcılar ----
  function $(id) { return document.getElementById(id); }
  function depoOku(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function depoYaz(k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* yok say */ } }
  function esle(url, tamam, hata, ms) {
    var x = new XMLHttpRequest(), bitti = false;
    function son(ok, v) { if (bitti) { return; } bitti = true; if (ok) { tamam(v); } else { hata(); } }
    try {
      x.open('GET', url, true); x.timeout = ms;
      x.onload = function () { var v = null; try { v = JSON.parse(x.responseText); } catch (e) { v = null; }
        son(x.status === 200 && v && v.uygulama === 'altyazikoprusu', v); };
      x.onerror = function () { son(false); }; x.ontimeout = function () { son(false); };
      x.send();
    } catch (e) { son(false); }
    return x;
  }
  function adresUrl(adres) { return 'http://' + (adres.indexOf(':') < 0 ? adres + ':' + PORT : adres); }

  // ---- durum ----
  var ekran = null, onceki = null, pc = null, hdmiNo = parseInt(depoOku(KEY_HDMI), 10) || 0;
  var baglanti = 'yok', bilgi = null, kontrol = null, hdmiKapat = null, demoZamanci = null, aramaNo = 0, elleMetin = '';
  var panelAcik = false, ipucuZamani = null;

  // ---- ekran yönetimi ----
  var EKRANLAR = ['e-ara', 'e-hdmi', 'e-elle', 'e-calis'];
  function goster(ad) {
    var i; ekran = ad; panelAcik = false; $('panel').className = 'ekran';
    for (i = 0; i < EKRANLAR.length; i++) { $(EKRANLAR[i]).className = 'ekran' + (EKRANLAR[i] === 'e-calis' ? ' sade' : '') + (EKRANLAR[i] === ad ? ' acik' : ''); }
    document.body.className = (ad === 'e-calis' ? 'calisiyor' : '') + (demoZamanci ? ' demo' : '');
    odakla(null);
  }
  function gorunenDugmeler() {
    var kap = panelAcik ? $('panel') : $(ekran), l = kap.getElementsByTagName('button'), s = [], i;
    for (i = 0; i < l.length; i++) { if (l[i].offsetWidth > 0) { s.push(l[i]); } }
    return s;
  }
  function odakla(d) {
    var l = gorunenDugmeler(); if (!l.length) { return; }
    var h = d || l[0]; try { h.focus(); } catch (e) { /* yok say */ }
  }
  function yonOdak(yon) {
    var l = gorunenDugmeler(), a = document.activeElement, i, r, c, en = null, enS = 1e12, dx, dy, s;
    if (!a || a.tagName !== 'BUTTON') { odakla(null); return; }
    r = a.getBoundingClientRect(); var ax = r.left + r.width / 2, ay = r.top + r.height / 2;
    for (i = 0; i < l.length; i++) {
      if (l[i] === a) { continue; }
      c = l[i].getBoundingClientRect(); dx = c.left + c.width / 2 - ax; dy = c.top + c.height / 2 - ay;
      if (yon === 'sol' && dx >= -5) { continue; } if (yon === 'sag' && dx <= 5) { continue; }
      if (yon === 'yukari' && dy >= -5) { continue; } if (yon === 'asagi' && dy <= 5) { continue; }
      s = (yon === 'sol' || yon === 'sag') ? Math.abs(dx) + Math.abs(dy) * 4 : Math.abs(dy) + Math.abs(dx) * 4;
      if (s < enS) { enS = s; en = l[i]; }
    }
    if (en) { en.focus(); }
  }

  // ---- bilgisayar arama ----
  function aramaIptal() { aramaNo++; }
  function ara() {
    var no = ++aramaNo, bulunan = [];
    goster('e-ara');
    $('ara-liste').innerHTML = ''; $('ara-hata').textContent = '';
    $('ara-durum').textContent = T('ara_baslik'); $('ara-durum').className = 'yardim araniyor';
    $('e-ara').getElementsByTagName('h1')[0].textContent = T('ara_baslik');
    P.yerelAdres(function (ip) {
      if (no !== aramaNo) { return; }
      var m = ip && /^(\d+\.\d+\.\d+)\.(\d+)$/.exec(ip);
      if (!m) { $('ara-durum').textContent = ''; $('ara-durum').className = 'yardim'; $('ara-hata').textContent = T('adres_alinamadi'); odakla($('b-elle')); return; }
      var taban = m[1], kendi = parseInt(m[2], 10), liste = [], i;
      for (i = 1; i <= 254; i++) { if (i !== kendi) { liste.push(i); } }
      var sira = 0, bitenSay = 0, aktif = 0, TOPLAM = liste.length, ILK = true;
      function bul(adres, ad) {
        var i2; for (i2 = 0; i2 < bulunan.length; i2++) { if (bulunan[i2] === adres) { return; } }
        bulunan.push(adres);
        var d = document.createElement('button'), alt = document.createElement('span');
        d.className = 'dugme'; d.appendChild(document.createTextNode(ad || adres));
        alt.className = 'pc-adres'; alt.textContent = adres; d.appendChild(alt);
        d.onclick = function () { aramaIptal(); pcSec(adres); };
        $('ara-liste').appendChild(d);
        if (ILK) { ILK = false; odakla(d); }
      }
      function sonraki() {
        if (no !== aramaNo) { return; }
        while (aktif < 30 && sira < TOPLAM) {
          (function (n) {
            aktif++;
            var adres = taban + '.' + n + ':' + PORT;
            esle('http://' + adres + '/kopru/merhaba', function (v) { bul(adres, v && v.ad); done(); }, done, 1500);
          }(liste[sira++]));
        }
      }
      function done() {
        if (no !== aramaNo) { return; }
        aktif--; bitenSay++;
        $('ara-durum').textContent = T('ara_ilerleme', [bitenSay, TOPLAM]);
        if (bitenSay >= TOPLAM) {
          $('ara-durum').textContent = T('ara_bitti'); $('ara-durum').className = 'yardim';
          if (bulunan.length) { $('e-ara').getElementsByTagName('h1')[0].textContent = T('bulunan'); }
          if (!bulunan.length) { $('ara-hata').textContent = T('bulunamadi'); }
        } else { sonraki(); }
      }
      sonraki();
    });
  }

  function pcSec(adres) {
    pc = adres; depoYaz(KEY_PC, adres);
    if (hdmiNo) { calistir(); } else { hdmiEkrani(); }
  }

  // ---- elle adres ----
  function elleEkrani() {
    aramaIptal(); elleMetin = ''; goster('e-elle'); $('elle-hata').textContent = ''; elleYenile(); odakla($('tus-izgara').getElementsByTagName('button')[0]);
  }
  function elleYenile() { $('adres-alan').textContent = elleMetin || ' '; }
  function elleTus(t) {
    if (t === 'sil') { elleMetin = elleMetin.slice(0, -1); } else if (elleMetin.length < 21) { elleMetin += t; }
    $('elle-hata').textContent = ''; elleYenile();
  }
  function elleTamam() {
    var a = elleMetin;
    if (!/^\d{1,3}(\.\d{1,3}){3}(:\d{1,5})?$/.test(a)) { $('elle-hata').textContent = T('adres_hatali'); return; }
    esle(adresUrl(a) + '/kopru/merhaba', function () { pcSec(a.indexOf(':') < 0 ? a + ':' + PORT : a); },
      function () { $('elle-hata').textContent = T('baglanamadi'); }, 3000);
  }
  function tuslariKur() {
    var k = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '.', '0', 'sil'], i, d, g = $('tus-izgara');
    for (i = 0; i < k.length; i++) {
      d = document.createElement('button'); d.className = 'dugme'; d.textContent = k[i] === 'sil' ? '⌫' : k[i];
      d.setAttribute('data-tus', k[i]); g.appendChild(d);
    }
  }

  // ---- HDMI seçimi ----
  function hdmiEkrani() { goster('e-hdmi'); $('hdmi-hata').textContent = ''; var d = document.querySelector('[data-hdmi="' + (hdmiNo || 1) + '"]'); odakla(d); }

  // ---- çalışıyor ----
  function bilgiDurumu(d) {
    baglanti = d === 'bagli' ? 'bagli' : (d === 'koptu' ? 'koptu' : 'baglaniyor'); panelYenile();
  }
  function ipucuGoster() {
    var e = $('calis-ipucu'); e.innerHTML = ''; var s = document.createElement('span'); s.textContent = T('ipucu_calisiyor'); e.appendChild(s);
    e.className = 'ipucu goster'; if (ipucuZamani) { clearTimeout(ipucuZamani); }
    ipucuZamani = setTimeout(function () { e.className = 'ipucu'; }, 6000);
  }
  function durdurHepsi() {
    if (kontrol) { kontrol.durdur(); kontrol = null; }
    if (hdmiKapat) { hdmiKapat(); hdmiKapat = null; }
    if (demoZamanci) { clearInterval(demoZamanci); demoZamanci = null; }
    $('demo-not').className = 'ipucu'; $('calis-hata').style.display = 'none'; bilgi = null;
  }
  function calistir() {
    durdurHepsi(); baglanti = 'baglaniyor'; goster('e-calis');
    hdmiKapat = P.hdmiAc(hdmiNo, $('hdmi'), function (d) {
      var h = $('calis-hata');
      if (d === 'hata') { h.textContent = T('hdmi_hata'); h.style.display = 'block'; } else { h.style.display = 'none'; }
    });
    kontrol = window.AKOverlay.baslat(adresUrl(pc) + '/kopru/akis', $('kok'), {
      onDurum: bilgiDurumu, onBilgi: function (v) { bilgi = v; panelYenile(); }, onYazi: function () { panelYenile(); },
      metinKoptu: T('rozet_koptu'), metinBaglaniyor: T('rozet_baglaniyor')
    });
    ipucuGoster();
  }

  // ---- deneme kipi ----
  var ORNEK = [
    { konusan: 'Ellie', metin: 'Buradan çıkmamız lazım, hemen!', asil: 'We need to get out of here, now!' },
    { konusan: null, metin: 'Kapı kilitli. Başka bir yol bulmalıyız.', asil: 'The door is locked. We have to find another way.' },
    { konusan: 'Joel', metin: 'Yanımdan ayrılma, sessiz ol.', asil: 'Stay close and keep quiet.' }
  ];
  function denemeKipi() {
    aramaIptal(); durdurHepsi(); pc = null; baglanti = 'yok';
    demoZamanci = 1; goster('e-calis'); // bayrak: body.demo
    kontrol = window.AKOverlay.baslat(null, $('kok'), { gorunum: { asil_goster: true } });
    $('demo-not').innerHTML = ''; var s = document.createElement('span'); s.textContent = T('demo_not'); $('demo-not').appendChild(s); $('demo-not').className = 'ipucu goster';
    var n = 0;
    function adim() {
      var o = ORNEK[n % ORNEK.length]; n++;
      kontrol.yaziGoster({ id: 'd' + n, metin: o.metin, asil: o.asil, konusan: o.konusan, sure_ms: 3500 });
      kontrol.ekranGoster({ id: 'de' + n, ogeler: [
        { x: 0.03, y: 0.05, g: 0.28, y2: 0.05, metin: 'Ana kampa dön', aciklama: 'Görev: üsse geri git', tur: 'gorev' },
        { x: 0.70, y: 0.06, g: 0.2, y2: 0.045, metin: 'Sağlık: 80', tur: 'bilgi' } ] });
    }
    adim(); demoZamanci = setInterval(adim, 4000);
  }

  // ---- bilgi paneli ----
  function durumMetni() { return baglanti === 'bagli' ? T('d_bagli') : (baglanti === 'koptu' ? T('d_koptu') : (baglanti === 'baglaniyor' ? T('d_baglaniyor') : T('d_yok'))); }
  function panelYenile() {
    $('p-pc').textContent = pc || T('yok'); $('p-baglanti').textContent = durumMetni();
    $('p-ceviri').textContent = bilgi && bilgi.motor ? bilgi.motor + (bilgi.yedek ? ' (yedek)' : '') : T('yok');
    $('p-son').textContent = (kontrol && kontrol.sonYazi()) || T('yok');
    $('p-hdmi').textContent = hdmiNo ? 'HDMI ' + hdmiNo : T('yok'); $('p-surum').textContent = SURUM;
  }
  function panelAc() { panelYenile(); panelAcik = true; $('panel').className = 'ekran acik'; odakla(null); }
  function panelKapat() { panelAcik = false; $('panel').className = 'ekran'; }

  // ---- tuşlar ----
  function geri() {
    if (panelAcik) { panelKapat(); return; }
    if (ekran === 'e-calis') { if (demoZamanci) { durdurHepsi(); ara(); } else { durdurHepsi(); hdmiEkrani(); } return; }
    if (ekran === 'e-elle') { ara(); return; }
    if (ekran === 'e-hdmi') { ara(); return; }
    P.cik();
  }
  document.addEventListener('keydown', function (e) {
    var k = e.keyCode, a = document.activeElement;
    if (k === P.geriTusu || k === 8 || k === 27) { e.preventDefault(); geri(); return; }
    if (ekran === 'e-calis' && !panelAcik && (k === 13 || k === 405 || k === 406 || k === 403 || k === 404) && !demoZamanci) { e.preventDefault(); panelAc(); return; }
    if (ekran === 'e-elle' && !panelAcik && ((k >= 48 && k <= 57) || k === 190)) { elleTus(k === 190 ? '.' : String(k - 48)); return; }
    var y = k === 37 ? 'sol' : k === 39 ? 'sag' : k === 38 ? 'yukari' : k === 40 ? 'asagi' : null;
    if (y) { e.preventDefault(); yonOdak(y); return; }
    if (k === 13 && a && a.tagName === 'BUTTON') { e.preventDefault(); a.click(); }
  }, false);

  document.addEventListener('click', function (e) {
    var h = e.target; if (h.tagName !== 'BUTTON') { return; }
    if (h.hasAttribute('data-tus')) { elleTus(h.getAttribute('data-tus')); }
    else if (h.hasAttribute('data-hdmi')) { hdmiNo = parseInt(h.getAttribute('data-hdmi'), 10); depoYaz(KEY_HDMI, String(hdmiNo)); calistir(); }
  }, false);

  function baglaDugme(id, fn) { $(id).addEventListener('click', fn, false); }
  baglaDugme('b-yeniden', ara); baglaDugme('b-elle', elleEkrani); baglaDugme('b-deneme', denemeKipi);
  baglaDugme('b-hdmi-geri', function () { ara(); });
  baglaDugme('b-elle-tamam', elleTamam); baglaDugme('b-elle-iptal', function () { ara(); });
  baglaDugme('b-p-kapat', panelKapat);
  baglaDugme('b-p-hdmi', function () { durdurHepsi(); hdmiEkrani(); });
  baglaDugme('b-p-pc', function () { durdurHepsi(); ara(); });

  // ---- başlangıç ----
  var MARKA = window.MARKA || { ad: 'AltYazıKöprüsü', slogan_tr: '', slogan_en: '' };
  document.title = MARKA.ad;
  $('tv-ad').textContent = MARKA.ad;
  $('tv-slogan').textContent = window.AKI18N.dil === 'tr' ? MARKA.slogan_tr : MARKA.slogan_en;
  window.AKI18N.uygula(document);
  tuslariKur();
  var kayitli = depoOku(KEY_PC);
  if (kayitli) {
    goster('e-ara'); $('ara-durum').textContent = T('kayitli_bakiliyor'); $('ara-durum').className = 'yardim araniyor';
    esle(adresUrl(kayitli) + '/kopru/merhaba', function () { pcSec(kayitli); }, function () { ara(); }, 3000);
  } else { ara(); }
}());
