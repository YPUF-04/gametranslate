// SPDX-License-Identifier: AGPL-3.0-only
// AltYazıKöprüsü - ortak bindirme çizicisi (TV tarayıcıları için, yalnızca ES5).
// Kullanım: var k = AKOverlay.baslat('/kopru/akis', element, {onDurum: fn, onYazi: fn, onBilgi: fn});
// url == null ise bağlanmaz (deneme kipi); k.yaziGoster / k.ekranGoster elle çağrılabilir.
(function (pencere) {
  'use strict';
  var belge = pencere.document;

  var VARSAYILAN = { yazi_boyutu: 44, konum: 'alt', kenar_bosluk: 0.08, arka_plan: 0.55,
    yazi_rengi: '#FFFFFF', konusan_rengi: '#FFD166', asil_goster: false, ekran_cevir: true };

  function kopyala(a, b) { var s = {}, k; for (k in a) { if (a.hasOwnProperty(k)) { s[k] = a[k]; } }
    if (b) { for (k in b) { if (b.hasOwnProperty(k)) { s[k] = b[k]; } } } return s; }
  function oge(sinif, ust) { var e = belge.createElement('div'); e.className = sinif; if (ust) { ust.appendChild(e); } return e; }
  function sayi(v, varsayilan) { return (typeof v === 'number' && v === v) ? v : varsayilan; }
  function sinirla(v, a, b) { return v < a ? a : (v > b ? b : v); }

  function baslat(url, kok, secenekler) {
    var sec = secenekler || {};
    var gorunum = kopyala(VARSAYILAN, sec.gorunum);
    var es = null, bekle = null, gozcu = null, gizle = null, durduruldu = false, deneme = 0;
    var sonYaziId = null, sonYazi = null, durum = 'baglaniyor';

    kok.className = (kok.className ? kok.className + ' ' : '') + 'ak-kok';
    kok.innerHTML = '';
    var ekranKatman = oge('ak-ekran', kok);
    var yazi = oge('ak-yazi', kok);
    var kutu = oge('ak-yazi-kutu', yazi);
    var durumRozet = oge('ak-durum', kok);

    function olcek() { var g = kok.clientWidth || pencere.innerWidth || 1920; return g / 1920; }
    function yukseklik() { return kok.clientHeight || pencere.innerHeight || 1080; }

    function bildir(ad, v) { if (typeof sec[ad] === 'function') { try { sec[ad](v); } catch (e) { /* uygulama hatası bindirmeyi bozmasın */ } } }

    function durumDegistir(d) {
      durum = d;
      var gorunur = d !== 'bagli' && sec.durumRozeti !== false;
      durumRozet.style.display = gorunur ? 'block' : 'none';
      durumRozet.textContent = d === 'koptu' ? (sec.metinKoptu || 'Bağlantı koptu, yeniden deneniyor…') :
        (d === 'baglaniyor' ? (sec.metinBaglaniyor || 'Bağlanıyor…') : '');
      if (!gorunur) { durumRozet.style.display = 'none'; }
      bildir('onDurum', d);
    }

    function gorunumUygula(g) {
      if (g) { gorunum = kopyala(gorunum, g); }
      var o = olcek();
      yazi.style.fontSize = Math.round(sayi(gorunum.yazi_boyutu, 44) * o * 10) / 10 + 'px';
      yazi.style.color = gorunum.yazi_rengi;
      durumRozet.style.fontSize = Math.round(26 * o * 10) / 10 + 'px';
      var kb = sinirla(sayi(gorunum.kenar_bosluk, 0.08), 0, 0.45) * 100 + '%';
      if (gorunum.konum === 'ust') { yazi.style.top = kb; yazi.style.bottom = 'auto'; }
      else { yazi.style.bottom = kb; yazi.style.top = 'auto'; }
      kutu.style.background = 'rgba(14,26,43,' + sinirla(sayi(gorunum.arka_plan, 0.55), 0, 1) + ')';
      ekranKatman.style.display = gorunum.ekran_cevir === false ? 'none' : 'block';
      var k = yazi.getElementsByClassName('ak-konusan'), i;
      for (i = 0; i < k.length; i++) { k[i].style.color = gorunum.konusan_rengi; }
      bildir('onGorunum', gorunum);
    }

    function yaziSil() {
      if (gizle) { pencere.clearTimeout(gizle); gizle = null; }
      yazi.style.display = 'none'; kutu.innerHTML = '';
    }

    function yaziGoster(v) {
      if (!v || typeof v.metin !== 'string' || v.metin === '') { return; }
      if (v.id !== undefined && v.id !== null && v.id === sonYaziId && yazi.style.display === 'none') { return; } // yeniden bağlanınca eski yazı geri gelmesin
      sonYaziId = (v.id === undefined ? null : v.id);
      sonYazi = v.metin;
      if (gizle) { pencere.clearTimeout(gizle); }
      kutu.innerHTML = '';
      if (v.konusan) { var k = oge('ak-konusan', kutu); k.textContent = v.konusan + ':'; k.style.color = gorunum.konusan_rengi; }
      var m = belge.createElement('span'); m.textContent = v.metin; kutu.appendChild(m);
      if (gorunum.asil_goster && v.asil) { var a = oge('ak-asil', kutu); a.textContent = v.asil; }
      yazi.style.display = 'block';
      var sure = sayi(v.sure_ms, 5000);
      gizle = pencere.setTimeout(function () { gizle = null; yaziSil(); }, sinirla(sure, 300, 60000));
      bildir('onYazi', v);
    }

    function ekranSil() { ekranKatman.innerHTML = ''; }

    function ekranGoster(v) {
      ekranSil();
      if (!v || !v.ogeler) { return; }
      var o = olcek(), y = yukseklik(), i, e, d, t, a;
      for (i = 0; i < v.ogeler.length; i++) {
        e = v.ogeler[i];
        if (!e || typeof e.metin !== 'string') { continue; }
        d = oge('ak-oge ak-' + (e.tur || 'diger'), ekranKatman);
        d.style.left = sinirla(sayi(e.x, 0), 0, 1) * 100 + '%';
        d.style.top = sinirla(sayi(e.y, 0), 0, 1) * 100 + '%';
        d.style.width = sinirla(sayi(e.g, 0.2), 0.03, 1) * 100 + '%';
        d.style.minHeight = sinirla(sayi(e.y2, 0.04), 0.01, 1) * 100 + '%';
        d.style.fontSize = Math.round(sinirla(sayi(e.y2, 0.04) * y * 0.5, 18 * o, 40 * o) * 10) / 10 + 'px';
        t = oge('ak-oge-metin', d); t.textContent = e.metin;
        if (e.aciklama) { a = oge('ak-oge-aciklama', d); a.textContent = e.aciklama; }
      }
    }

    function olayVeri(ev) { var v = null; try { v = JSON.parse(ev.data); } catch (x) { v = null; } return v; }

    function gozcuKur() {
      if (gozcu) { pencere.clearTimeout(gozcu); }
      gozcu = pencere.setTimeout(function () { yenidenBaglan(); }, sec.gozcuMs || 30000);
    }

    function kapat() { if (es) { try { es.close(); } catch (x) { /* yok say */ } es = null; } }

    function yenidenBaglan() {
      kapat();
      if (durduruldu) { return; }
      if (durum === 'bagli') { durumDegistir('koptu'); }
      if (bekle) { pencere.clearTimeout(bekle); }
      var ms = Math.min(10000, 1000 * Math.pow(2, Math.min(deneme, 4)));
      deneme++;
      bekle = pencere.setTimeout(baglan, ms);
    }

    function dinle(ad, islev) {
      es.addEventListener(ad, function (ev) { gozcuKur(); islev(olayVeri(ev)); }, false);
    }

    function baglan() {
      if (durduruldu || !url) { return; }
      if (!pencere.EventSource) { durumDegistir('desteklenmiyor'); return; }
      kapat();
      try { es = new pencere.EventSource(url); } catch (x) { yenidenBaglan(); return; }
      es.onopen = function () { deneme = 0; durumDegistir('bagli'); gozcuKur(); };
      es.onerror = function () { yenidenBaglan(); };
      dinle('yazi', function (v) { yaziGoster(v); });
      dinle('yazi-sil', function () { yaziSil(); });
      dinle('ekran', function (v) { ekranGoster(v); });
      dinle('ekran-sil', function () { ekranSil(); });
      dinle('gorunum', function (v) { gorunumUygula(v); });
      dinle('durum', function (v) { bildir('onBilgi', v); });
    }

    function yeniden() { gorunumUygula(); }
    pencere.addEventListener('resize', yeniden, false);

    function durdur() {
      durduruldu = true; kapat();
      if (bekle) { pencere.clearTimeout(bekle); } if (gozcu) { pencere.clearTimeout(gozcu); }
      yaziSil(); ekranSil();
      pencere.removeEventListener('resize', yeniden, false);
    }

    gorunumUygula();
    if (url) { durumDegistir('baglaniyor'); baglan(); } else { durumDegistir('bagli'); }

    return {
      durdur: durdur, yaziGoster: yaziGoster, yaziSil: yaziSil, ekranGoster: ekranGoster, ekranSil: ekranSil,
      gorunumUygula: gorunumUygula,
      durumu: function () { return durum; },
      sonYazi: function () { return sonYazi; }
    };
  }

  pencere.AKOverlay = { baslat: baslat };
}(window));
