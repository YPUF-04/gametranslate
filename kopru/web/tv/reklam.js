// SPDX-License-Identifier: AGPL-3.0-only
// "+30 dk ekle" reklam oynatıcısı (PROTOKOL 17.3/17.4). ES5: LG webOS, /tv sayfası ve panel aynı dosyayı kullanır.
// Kendi küçük VAST 3/4 ayrıştırıcımız + <video>: dış betik (IMA) yüklenmez, sağlayıcıdan bağımsızdır.
// Reklam yoksa / gelmezse / oynamazsa 15 sn'lik "destek" ekranı gösterilir; asla takılı kalmaz.
// Süreyi bu dosya VERMEZ: bitince `bitti({id, tur, sure_sn})` çağrılır, karar PC'dedir.
// Kullanım: var o = AKReklam.oynat(document.body, {id:'r1', vast:'https://…'|null, en_az_sn:15, metin:{…}, bitti: fn});  o.durdur();
(function (pencere) {
  'use strict';
  var YUKLEME_MS = 6000, TAKILMA_MS = 8000, EN_COK_SARMALAYICI = 5, EN_UZUN_SN = 120;
  var METIN = { reklam: 'Reklam', sn: 'sn', destek: '{marka}\'nü desteklediğin için teşekkürler', destek_alt: 'Biraz sonra 30 dakika dublaj süresi eklenecek.' };

  // ---------- küçük yardımcılar ----------
  function makro(url, hata) {
    var r = String(Math.floor(Math.random() * 1e8) + 1e8);
    return String(url).replace(/\[CACHEBUSTING\]/g, r).replace(/\[TIMESTAMP\]/g, String(Date.now()))
      .replace(/\[ERRORCODE\]/g, String(hata || 900));
  }
  function piksel(liste, hata) {
    var i, im;
    for (i = 0; i < liste.length; i++) {
      if (!/^https?:\/\//.test(liste[i])) { continue; }
      try { im = new pencere.Image(); im.src = makro(liste[i], hata); } catch (e) { /* yok say */ }
    }
  }
  function metinAl(el) { return el ? String(el.textContent || '').replace(/^\s+|\s+$/g, '') : ''; }
  function adla(kok, ad) {   // ad alanı (namespace) olsa da yerel ada göre bul
    var l = kok.getElementsByTagName('*'), s = [], i;
    for (i = 0; i < l.length; i++) { if ((l[i].localName || l[i].nodeName) === ad) { s.push(l[i]); } }
    return s;
  }
  function sureCoz(t) {   // "00:00:30" ya da "00:00:30.500"
    var m = /^(\d+):(\d+):(\d+(?:\.\d+)?)$/.exec(t || '');
    return m ? (+m[1]) * 3600 + (+m[2]) * 60 + parseFloat(m[3]) : 0;
  }

  // ---------- VAST ayrıştırma (saf: sınanabilir) ----------
  // Döner: {tur:'inline'|'wrapper'|'bos', sarmalayici:url, impression:[], error:[], izleme:{start:[],…}, medya:[{url,tip,gen,yuk,bitrate}], sure:sn}
  function vastCoz(xmlMetni) {
    var b = { tur: 'bos', sarmalayici: null, impression: [], error: [], izleme: {}, medya: [], sure: 0 };
    var doc, ad, kap, i, j, lin, olaylar, mf;
    try { doc = new pencere.DOMParser().parseFromString(xmlMetni, 'text/xml'); } catch (e) { return b; }
    if (!doc || adla(doc, 'parsererror').length) { return b; }
    adla(doc, 'Error').forEach(function (e) { if (e.parentNode && (e.parentNode.localName || e.parentNode.nodeName) === 'VAST') { b.error.push(metinAl(e)); } });
    ad = adla(doc, 'Ad')[0];
    if (!ad) { return b; }
    kap = adla(ad, 'InLine')[0] || adla(ad, 'Wrapper')[0];
    if (!kap) { return b; }
    adla(kap, 'Impression').forEach(function (e) { if (metinAl(e)) { b.impression.push(metinAl(e)); } });
    adla(kap, 'Error').forEach(function (e) { if (metinAl(e)) { b.error.push(metinAl(e)); } });
    lin = adla(kap, 'Linear')[0];
    if (lin) {
      olaylar = adla(lin, 'Tracking');
      for (i = 0; i < olaylar.length; i++) {
        j = olaylar[i].getAttribute('event');
        if (j && metinAl(olaylar[i])) { (b.izleme[j] = b.izleme[j] || []).push(metinAl(olaylar[i])); }
      }
      b.sure = sureCoz(metinAl(adla(lin, 'Duration')[0]));
      mf = adla(lin, 'MediaFile');
      for (i = 0; i < mf.length; i++) {
        var api = (mf[i].getAttribute('apiFramework') || '').toUpperCase(), tes = (mf[i].getAttribute('delivery') || 'progressive').toLowerCase();
        if (api === 'VPAID' || tes !== 'progressive' || !/^https?:\/\//.test(metinAl(mf[i]))) { continue; }
        b.medya.push({ url: metinAl(mf[i]), tip: (mf[i].getAttribute('type') || '').toLowerCase(),
          gen: parseInt(mf[i].getAttribute('width'), 10) || 0, yuk: parseInt(mf[i].getAttribute('height'), 10) || 0,
          bitrate: parseInt(mf[i].getAttribute('bitrate'), 10) || 0 });
      }
    }
    if ((kap.localName || kap.nodeName) === 'Wrapper') {
      b.tur = 'wrapper'; b.sarmalayici = metinAl(adla(kap, 'VASTAdTagURI')[0]) || null;
    } else { b.tur = 'inline'; }
    return b;
  }

  // Oynatılabilen en uygun dosya: ekran genişliğine en yakın (taşmayan önce)
  function medyaSec(medya, video, ekranGen) {
    var uygun = [], i, m;
    for (i = 0; i < medya.length; i++) {
      m = medya[i];
      if (!/^video\/(mp4|webm)$/.test(m.tip)) { continue; }
      if (video && video.canPlayType && !video.canPlayType(m.tip)) { continue; }
      uygun.push(m);
    }
    uygun.sort(function (a, b) {
      var at = a.gen > ekranGen ? 1 : 0, bt = b.gen > ekranGen ? 1 : 0;
      if (at !== bt) { return at - bt; }
      return Math.abs(ekranGen - a.gen) - Math.abs(ekranGen - b.gen);
    });
    return uygun[0] || null;
  }

  function getir(url, tamam, hata) {
    var x, bitti = false;
    function son(ok, v) { if (bitti) { return; } bitti = true; if (ok) { tamam(v); } else { hata(); } }
    try {
      x = new pencere.XMLHttpRequest();
      x.open('GET', makro(url), true); x.timeout = YUKLEME_MS;   // çerezsiz (withCredentials yok)
      x.onload = function () { son(x.status >= 200 && x.status < 300, x.responseText); };
      x.onerror = function () { son(false); }; x.ontimeout = function () { son(false); };
      x.send();
    } catch (e) { son(false); }
  }

  // Sarmalayıcıları izleyerek tek bir Inline topla (izleme adresleri birleşir)
  function vastYukle(url, tamam, hata) {
    var top = { impression: [], error: [], izleme: {} };
    function birlestir(b) {
      var k;
      top.impression = top.impression.concat(b.impression); top.error = top.error.concat(b.error);
      for (k in b.izleme) { if (b.izleme.hasOwnProperty(k)) { top.izleme[k] = (top.izleme[k] || []).concat(b.izleme[k]); } }
    }
    function adim(u, derinlik) {
      getir(u, function (xml) {
        var b = vastCoz(xml);
        birlestir(b);
        if (b.tur === 'wrapper' && b.sarmalayici && derinlik < EN_COK_SARMALAYICI) { adim(b.sarmalayici, derinlik + 1); return; }
        if (b.tur !== 'inline' || !b.medya.length) { hata(top, 303); return; }   // 303: reklam yok (no fill)
        top.medya = b.medya; top.sure = b.sure; tamam(top);
      }, function () { hata(top, 301); });
    }
    adim(url, 0);
  }

  // ---------- görünüm ----------
  var STIL = '.akr-kok{position:fixed;left:0;top:0;right:0;bottom:0;z-index:2147483000;background:#000;color:#eef3f8;font-family:system-ui,"Segoe UI",sans-serif}' +
    '.akr-kok video{position:absolute;left:0;top:0;width:100%;height:100%;background:#000;object-fit:contain}' +
    '.akr-etiket{position:absolute;left:24px;top:20px;padding:6px 14px;border-radius:999px;background:rgba(0,0,0,.6);font-size:20px;font-weight:600;letter-spacing:.02em}' +
    '.akr-destek{position:absolute;left:0;top:0;right:0;bottom:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:24px;background:radial-gradient(circle at 50% 35%,#1a3256,#0c1729 70%)}' +
    '.akr-destek svg{width:120px;height:120px;margin-bottom:28px}.akr-destek h2{font-size:clamp(22px,3.2vw,46px);margin:0 0 14px;font-weight:700}' +
    '.akr-destek p{font-size:clamp(16px,1.8vw,26px);margin:0;opacity:.85}.akr-sayac{margin-top:26px;font-size:clamp(18px,2vw,30px);color:#ffd166;font-weight:700}';
  var LOGO = '<svg viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="16" fill="#13243f"/>' +
    '<path d="M8 33 A30 30 0 0 1 56 33" fill="none" stroke="#2EC4B6" stroke-width="5" stroke-linecap="round"/>' +
    '<path d="M20 26 V36 M32 23 V36 M44 26 V36" stroke="#2EC4B6" stroke-width="2.2" stroke-linecap="round" opacity=".55"/>' +
    '<rect x="10" y="37" width="44" height="11" rx="5.5" fill="#FFD166"/><rect x="17" y="41" width="17" height="3" rx="1.5" fill="#0C1729" opacity=".72"/>' +
    '<rect x="37" y="41" width="10" height="3" rx="1.5" fill="#0C1729" opacity=".72"/></svg>';

  function stilEkle(belge) {
    if (belge.getElementById('akr-stil')) { return; }
    var s = belge.createElement('style'); s.id = 'akr-stil'; s.textContent = STIL;
    (belge.head || belge.documentElement).appendChild(s);
  }

  // ---------- oynatma ----------
  function oynat(kap, sec) {
    var belge = kap.ownerDocument || pencere.document, M = {}, k;
    for (k in METIN) { if (METIN.hasOwnProperty(k)) { M[k] = (sec.metin && sec.metin[k]) || METIN[k]; } }
    var marka = (pencere.MARKA && pencere.MARKA.ad) || 'AltYazıKöprüsü';
    var enAz = Math.max(1, Number(sec.en_az_sn) || 15), bas = Date.now(), bitti = false, zaman = [], video = null, reklamSure = 0;
    stilEkle(belge);
    var kok = belge.createElement('div'); kok.className = 'akr-kok'; kok.setAttribute('role', 'dialog'); kok.setAttribute('aria-live', 'polite');
    kok.setAttribute('data-reklam', sec.id || '');
    var etiket = belge.createElement('div'); etiket.className = 'akr-etiket';
    kok.appendChild(etiket); kap.appendChild(kok);

    function temizle() {
      var i; for (i = 0; i < zaman.length; i++) { pencere.clearInterval(zaman[i]); pencere.clearTimeout(zaman[i]); }
      zaman = [];
      if (video) { try { video.pause(); video.removeAttribute('src'); video.load(); } catch (e) { /* yok say */ } }
      if (kok.parentNode) { kok.parentNode.removeChild(kok); }
    }
    function bitir(tur) {
      if (bitti) { return; } bitti = true; temizle();
      if (typeof sec.bitti === 'function') { sec.bitti({ id: sec.id, tur: tur, sure_sn: Math.round(reklamSure * 10) / 10 }); }
    }
    function etiketYaz(kalan) { etiket.textContent = M.reklam + ' · ' + Math.max(0, Math.ceil(kalan)) + ' ' + M.sn; }

    function destek(saniye) {   // kendi kartımız: logo + teşekkür + geri sayım
      if (bitti) { return; }
      if (video) { try { video.pause(); } catch (e) { /* yok say */ } video.style.display = 'none'; }
      var d = belge.createElement('div'), son = Date.now() + saniye * 1000, h2 = belge.createElement('h2'), p = belge.createElement('p'), sayac = belge.createElement('div');
      d.className = 'akr-destek'; d.innerHTML = LOGO;
      h2.textContent = M.destek.replace('{marka}', marka); p.textContent = M.destek_alt; sayac.className = 'akr-sayac';
      d.appendChild(h2); d.appendChild(p); d.appendChild(sayac); kok.appendChild(d); kok.appendChild(etiket);
      function tik() {
        var kalan = (son - Date.now()) / 1000;
        sayac.textContent = Math.max(0, Math.ceil(kalan)) + ' ' + M.sn; etiketYaz(kalan);
        if (kalan <= 0) { bitir(reklamSure > 0 ? 'vast' : 'destek'); }
      }
      tik(); zaman.push(pencere.setInterval(tik, 250));
    }
    function kalanEnAz() { return Math.max(0, enAz - (Date.now() - bas) / 1000); }

    function videoOynat(v) {
      var dosya, ceyrek = {}, sonT = -1, sonDegisim = Date.now(), basladi = false;
      video = belge.createElement('video');
      video.setAttribute('playsinline', ''); video.autoplay = true; video.controls = false;
      dosya = medyaSec(v.medya, video, pencere.innerWidth || 1920);
      if (!dosya) { piksel(v.error, 403); destek(Math.max(kalanEnAz(), 1)); return; }
      kok.insertBefore(video, etiket);
      function hata(kod) { if (bitti) { return; } piksel(v.error, kod); reklamSure = 0; destek(Math.max(kalanEnAz(), 1)); }
      video.addEventListener('playing', function () {
        if (basladi) { return; } basladi = true;
        piksel(v.impression); piksel(v.izleme.creativeView || []); piksel(v.izleme.start || []);
      }, false);
      video.addEventListener('timeupdate', function () {
        var d = video.duration || v.sure || 0, t = video.currentTime, o;
        if (t !== sonT) { sonT = t; sonDegisim = Date.now(); }
        if (d > 0) {
          etiketYaz(d - t);
          o = t / d;
          if (o >= 0.25 && !ceyrek.a) { ceyrek.a = 1; piksel(v.izleme.firstQuartile || []); }
          if (o >= 0.5 && !ceyrek.b) { ceyrek.b = 1; piksel(v.izleme.midpoint || []); }
          if (o >= 0.75 && !ceyrek.c) { ceyrek.c = 1; piksel(v.izleme.thirdQuartile || []); }
        }
      }, false);
      video.addEventListener('ended', function () {
        if (bitti) { return; }
        reklamSure = Math.min(EN_UZUN_SN, video.duration || v.sure || 0);
        piksel(v.izleme.complete || []);
        var kalan = kalanEnAz();
        if (kalan > 0.5) { destek(kalan); } else { bitir('vast'); }
      }, false);
      video.addEventListener('error', function () { hata(405); }, false);
      zaman.push(pencere.setInterval(function () {   // takıldıysa (ağ, çözücü) destek ekranına geç
        if (!bitti && Date.now() - sonDegisim > TAKILMA_MS) { hata(402); }
        if (!bitti && (Date.now() - bas) / 1000 > EN_UZUN_SN + 15) { hata(202); }
      }, 1000));
      etiketYaz(v.sure || enAz);
      video.src = dosya.url;
      try { var p = video.play(); if (p && p.catch) { p.catch(function () { /* otomatik oynatma engeli: sessiz dene */ video.muted = true; try { video.play(); } catch (e) { hata(400); } }); } } catch (e2) { hata(400); }
    }

    if (sec.vast && (/^https:\/\//.test(sec.vast) || /^http:\/\/(127\.0\.0\.1|localhost)[:\/]/.test(sec.vast))) {   // http yalnız yerel sınama için
      etiketYaz(enAz);
      vastYukle(sec.vast, function (v) { if (!bitti) { videoOynat(v); } },
        function (v, kod) { if (bitti) { return; } piksel(v.error, kod); destek(Math.max(kalanEnAz(), enAz)); });
    } else {
      destek(enAz);
    }
    return { durdur: function () { bitti = true; temizle(); }, kok: kok };
  }

  pencere.AKReklam = { oynat: oynat, vastCoz: vastCoz, medyaSec: medyaSec, makro: makro, sureCoz: sureCoz };
}(window));
