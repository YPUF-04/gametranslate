/* AltYazıKöprüsü kontrol paneli — düz JS, derleme yok, internet gerekmez. */
(function () {
  'use strict';

  // ---------- küçük yardımcılar ----------
  var $ = function (s, k) { return (k || document).querySelector(s); };
  function h(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      var v = attrs[k];
      if (v === false || v == null) return;
      if (k === 'class') e.className = v;
      else if (k.slice(0, 2) === 'on') e.addEventListener(k.slice(2), v);
      else if (k === 'text') e.textContent = v;
      else e.setAttribute(k, v === true ? '' : v);
    });
    [].concat(kids || []).forEach(function (c) {
      if (c == null || c === false) return;
      e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return e;
  }
  function ls(k, v) {
    try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; }
    return null;
  }
  // marka adı tek yerden (marka.js); metinlerdeki {marka} bununla doldurulur
  var MARKA = window.MARKA || { ad: 'AltYazıKöprüsü', kisa: 'AYK', slogan_tr: '', slogan_en: '' };
  var DILLER = {};
  var dil = 'tr';
  function t(key, vars) {
    var s = (DILLER[dil] && DILLER[dil][key]);
    if (s == null) s = (DILLER.tr && DILLER.tr[key]);
    if (s == null) return key;
    if (vars) Object.keys(vars).forEach(function (k) { s = s.split('{' + k + '}').join(vars[k]); });
    return s.split('{marka}').join(MARKA.ad);
  }

  // ---------- görünüm tercihleri: büyük yazı, hareketi azalt (yalnız bu tarayıcıda) ----------
  var kok = document.documentElement;
  function hareketAz() {
    if (kok.classList.contains('hareket-az')) return true;
    if (kok.classList.contains('hareket-acik')) return false;
    try { return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; }
  }

  // ---------- simgeler (çizgi, 24'lük ızgara; emoji yerine her yerde aynı görünür) ----------
  var IKON = {
    ps5: '<path d="M7.5 8.5h9a4 4 0 0 1 3.9 3.1l.9 4.1a2.3 2.3 0 0 1-3.9 2L15.5 16h-7l-1.9 1.7a2.3 2.3 0 0 1-3.9-2l.9-4.1a4 4 0 0 1 3.9-3.1z"/><path d="M8 11v3M6.5 12.5h3"/><circle cx="16" cy="11.6" r=".6"/><circle cx="17.4" cy="13.2" r=".6"/>',
    xbox: '<circle cx="12" cy="12" r="8.5"/><path d="M7.2 6.6c2.6 1.5 4.8 4.2 6.6 7.6M16.8 6.6c-2.6 1.5-4.8 4.2-6.6 7.6"/>',
    pc: '<rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M9 20h6M12 16.5V20"/>',
    kart: '<rect x="3" y="7" width="13" height="10" rx="2"/><path d="M16 10.5l5-2.5v8l-5-2.5"/>',
    tv: '<rect x="2.5" y="5" width="19" height="12.5" rx="2"/><path d="M8 20.5h8"/><path d="M6.5 14h7" stroke-width="2.2"/>',
    web: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.4 2.4 3.5 5.3 3.5 8.5s-1.1 6.1-3.5 8.5c-2.4-2.4-3.5-5.3-3.5-8.5s1.1-6.1 3.5-8.5z"/>',
    arti: '<path d="M12 5v14M5 12h14"/>',
    paket: '<path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19.5h14"/>',
    oyna: '<path d="M8 5.5v13l10-6.5z" fill="currentColor"/>',
    dur: '<rect x="6.5" y="6.5" width="11" height="11" rx="2" fill="currentColor"/>',
    goz: '<path d="M4 7V5.5A1.5 1.5 0 0 1 5.5 4H7M17 4h1.5A1.5 1.5 0 0 1 20 5.5V7M20 17v1.5a1.5 1.5 0 0 1-1.5 1.5H17M7 20H5.5A1.5 1.5 0 0 1 4 18.5V17"/><path d="M8 10h8M8 14h5"/>',
    yenile: '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.5 4.5v4h-4"/>',
    kare: '<rect x="4" y="5" width="16" height="14" rx="2" stroke-dasharray="3 2.4"/><path d="M8 15h8" stroke-width="2.4"/>',
    indir: '<path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19.5h14"/>',
    kullanici: '<circle cx="12" cy="8.5" r="3.5"/><path d="M5 20c.8-3.6 3.6-5.5 7-5.5s6.2 1.9 7 5.5"/>',
    baglan: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    pencere: '<rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="M3.5 9.5h17"/>',
    ayar: '<path d="M5 7h9M18 7h1M5 17h1M10 17h9"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
    wifi: '<path d="M3.5 9.5a12 12 0 0 1 17 0M6.5 12.8a7.6 7.6 0 0 1 11 0M9.5 16a3.2 3.2 0 0 1 5 0"/><circle cx="12" cy="19" r=".8"/>',
    kablo: '<path d="M8 3v6M16 3v6M6.5 9h11v3.5a5.5 5.5 0 0 1-11 0zM12 18v3"/>',
    yansit: '<path d="M4 8V6.5A1.5 1.5 0 0 1 5.5 5h13A1.5 1.5 0 0 1 20 6.5v11a1.5 1.5 0 0 1-1.5 1.5H14"/><path d="M4 12.5a6.5 6.5 0 0 1 6.5 6.5M4 16.5A2.5 2.5 0 0 1 6.5 19"/><circle cx="4.5" cy="19" r=".6"/>',
    tik: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    klavye: '<rect x="3" y="6.5" width="18" height="11" rx="2"/><path d="M7 10.5h.01M10 10.5h.01M13 10.5h.01M16 10.5h.01M8 14h8"/>',
    telefon: '<rect x="7" y="3" width="10" height="18" rx="2.5"/><path d="M11 18h2"/>',
    ok: '<path d="M6 12h12M13 7l5 5-5 5"/>',
    geri: '<path d="M14.5 6l-6 6 6 6"/>',
    oyun: '<path d="M7 9.5h10a3.5 3.5 0 0 1 3.4 2.7l.8 3.6a2 2 0 0 1-3.4 1.8L16 16H8l-1.8 1.6a2 2 0 0 1-3.4-1.8l.8-3.6A3.5 3.5 0 0 1 7 9.5z"/><path d="M8 12v2.6M6.7 13.3h2.6M15.5 12.6h.01M17 14h.01"/>',
    ceviri: '<path d="M4 6h8M8 4v2M10.5 6c-.6 3.2-2.6 5.7-6 7.2"/><path d="M6.5 9.5c1 1.7 2.6 3 4.5 3.7"/><path d="M12.5 20l3.5-8.5 3.5 8.5M13.7 17.2h4.6"/>',
    hedef: '<rect x="3.5" y="5" width="17" height="14" rx="2"/><rect x="6.5" y="8" width="6" height="3.5" rx="1" stroke-dasharray="2 1.6"/><rect x="8" y="14" width="8" height="2.6" rx="1"/>',
    liste: '<path d="M8 7h11M8 12h11M8 17h7"/><circle cx="4.5" cy="7" r=".9"/><circle cx="4.5" cy="12" r=".9"/><circle cx="4.5" cy="17" r=".9"/>',
    anahtar: '<circle cx="8" cy="15" r="3.5"/><path d="M10.5 12.5 19 4M16 7l2.5 2.5M14 9l1.8 1.8"/>',
    ses: '<path d="M4 10v4h3.5L12 18V6L7.5 10z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/>',
    soru: '<circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.6a2.5 2.5 0 1 1 3.4 2.3c-.7.3-1 .9-1 1.6M12 16.8v.2"/>'
  };
  function ikon(ad) {
    var s = h('span', { class: 'ikon', 'aria-hidden': 'true' });
    s.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" focusable="false">' + (IKON[ad] || '') + '</svg>';
    return s.firstChild;
  }

  // ---------- API (her istek zaman aşımlı: hiçbir aşama sonsuza dek beklemez) ----------
  function hataNesnesi(mesaj, kod, ayrinti, http) {
    var e = new Error(mesaj); e.mesaj = mesaj; e.hata = kod || null; e.ayrinti = ayrinti || null; e.http = http || null; return e;
  }
  function kapaliHata() { var e = new Error(t('hata.kapali')); e.mesaj = t('hata.kapali'); e.kapali = true; return e; }
  function api(yontem, yol, govde, sure) {
    var secenek = { method: yontem, headers: {} };
    if (govde instanceof FormData) { secenek.body = govde; }
    else if (govde !== undefined) { secenek.headers['Content-Type'] = 'application/json'; secenek.body = JSON.stringify(govde); }
    var iptal = window.AbortController ? new AbortController() : null, doldu = false, zaman = null;
    if (iptal) { secenek.signal = iptal.signal; zaman = setTimeout(function () { doldu = true; iptal.abort(); }, sure || 15000); }
    return fetch(yol, secenek).then(function (r) {
      return r.text().then(function (txt) { return { r: r, txt: txt }; });
    }).then(function (y) {
      clearTimeout(zaman);
      var r = y.r, j = null;
      try { j = y.txt ? JSON.parse(y.txt) : {}; } catch (e) { j = null; }
      // hata: HTTP hatası ya da {"hata","mesaj"} biçimli gövde. /api/durum'daki bilgi amaçlı "hata" alanı hata sayılmaz.
      if (!r.ok || (j && j.hata && j.mesaj && !('calisiyor' in j))) {
        // sunucu özel bir mesaj verdiyse HER ZAMAN o gösterilir; genel mesaj yalnız mesaj yoksa
        var m = (j && j.mesaj) || (r.status === 404 ? t('hata.uc_yok') : t('hata.genel'));
        var he = hataNesnesi(m, j && j.hata, j && j.ayrinti, r.status); he.govde = j; throw he;
      }
      return j;
    }, function () {
      clearTimeout(zaman);
      if (doldu) throw hataNesnesi(t('hata.zaman'), 'zaman_asimi', yontem + ' ' + yol.split('?')[0]);
      throw kapaliHata();
    });
  }

  // ---------- durum ----------
  var S = {
    ayarlar: null, durum: null, motorlar: [], kaynaklar: [],
    adim: 1, cihaz: ls('cihaz'), kaynak: null, motor: null, gosterim: null,
    asama: {}, tekAsama: null, donus: null, okunan: null, kareUrl: null, yerel: null,
    kurulumBitti: ls('kurulum') === '1', kapali: false,
    oyunlar: [], sonCeviriler: [], oneriler: [], duzeltAcik: false, oyunDegis: false,
    guncelleme: null, erisim: null, erisimAcik: false, reklamOynuyor: null, reklamId: null, reklamBekle: false,
    dublaj: null, dublajSecim: null
  };
  var ana = $('#ana');
  var afis = $('#afis');

  function banner(tur, metin, alt) {
    if (!metin) { afis.hidden = true; return; }
    afis.className = 'afis ' + tur;
    afis.textContent = '';
    afis.appendChild(document.createTextNode(metin));
    if (alt) afis.appendChild(h('small', { text: alt }));
    afis.hidden = false;
  }
  // "Ne oldu. Ne yapmalı." → ilk cümle kalın, gerisi altında ince
  function ikiParca(m) {
    var i = m.indexOf('. ');
    return (i > 0 && i < m.length - 3) ? [m.slice(0, i + 1), m.slice(i + 2)] : [m, ''];
  }
  function hataGoster(e) {
    if (e && e.kapali) { kapaliBanner(true); return; }
    var p = ikiParca((e && (e.mesaj || e.message)) || t('hata.genel'));
    banner('hata', p[0], p[1]);
  }
  function kapaliBanner(k) {
    S.kapali = k;
    if (k && S.guncelleme && S.guncelleme.asama === 'baslatiliyor') return;   // program bilerek yeniden başlıyor
    if (k) banner('hata', t('hata.kapali'), t('hata.kapali_alt'));
    else if (afis.dataset.kapali !== '0' && afis.classList.contains('hata') && afis.textContent.indexOf(t('hata.kapali')) === 0) banner('', '');
  }

  // ---------- i18n ----------
  function dilYukle(kod) {
    if (DILLER[kod]) return Promise.resolve();
    return fetch('/panel/dil/' + kod + '.json').then(function (r) { return r.json(); }).then(function (j) { DILLER[kod] = j; });
  }
  function dilUygula(kod) {
    dil = kod; document.documentElement.lang = kod;
    document.querySelectorAll('.dil-dugme').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.dil === kod)); });
    document.querySelectorAll('[data-i]').forEach(function (e) { e.textContent = t(e.dataset.i); });
    ls('dil', kod);
  }
  function dilDegistir(kod) {
    return dilYukle(kod).then(function () {
      dilUygula(kod); ciz();
      return api('POST', '/api/ayarlar', { arayuz_dili: kod }).catch(function () {});
    });
  }

  // ---------- veri ----------
  function ayarYukle() { return api('GET', '/api/ayarlar').then(function (a) { S.ayarlar = a; return a; }); }
  function ayarKaydet(parca) {
    Object.keys(parca).forEach(function (k) {
      if (k === 'gorunum') S.ayarlar.gorunum = Object.assign({}, S.ayarlar.gorunum, parca.gorunum);
      else S.ayarlar[k] = parca[k];
    });
    return api('POST', '/api/ayarlar', parca).catch(hataGoster);
  }

  // ---------- ortak parçalar ----------
  var CIHAZLAR = [
    { k: 'pc', ik: 'pc' }, { k: 'ps5', ik: 'ps5' }, { k: 'xbox', ik: 'xbox' }, { k: 'kart', ik: 'kart' }
  ];
  var MOTOR_SIRA = ['gemini', 'deepseek', 'claude', 'yerel', 'deepl'];
  var HEDEF_DILLER = ['tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ar', 'ja', 'ko', 'zh', 'pl', 'nl'];

  function karo(ik, baslik, kucuk, secili, onclick) {
    return h('button', { type: 'button', class: 'karo', 'aria-pressed': String(!!secili), onclick: onclick },
      [h('span', { class: 'ik', 'aria-hidden': 'true' }, IKON[ik] ? ikon(ik) : ik), h('span', { class: 'b', text: baslik }), kucuk ? h('span', { class: 'k', text: kucuk }) : null]);
  }
  function adimlar(anahtar) {
    return h('ol', {}, t(anahtar).split('\n').map(function (s) { return h('li', { text: s }); }));
  }
  function kaynakYukle(cihaz) {
    return api('GET', '/api/kaynaklar' + (cihaz ? '?cihaz=' + encodeURIComponent(cihaz) : '')).then(function (k) {
      S.kaynaklar = k || [];
      if (!S.kaynak && S.ayarlar && S.ayarlar.kaynak) S.kaynak = S.ayarlar.kaynak;
    });
  }
  function motorBilgi(kod) { return S.motorlar.filter(function (m) { return m.kod === kod; })[0]; }

  // ---------- kare (oyun görüntüsü): zaman aşımlı, dostça hata ----------
  function kareAl() {
    var iptal = window.AbortController ? new AbortController() : null, doldu = false;
    var zaman = iptal ? setTimeout(function () { doldu = true; iptal.abort(); }, 12000) : null;
    return fetch('/api/kare?_=' + Date.now(), { cache: 'no-store', signal: iptal ? iptal.signal : undefined }).then(function (r) {
      if (!r.ok) {
        return r.text().then(function (txt) {
          var j = {}; try { j = JSON.parse(txt) || {}; } catch (e) { j = {}; }
          throw hataNesnesi(j.mesaj || (r.status === 404 ? t('hata.uc_yok') : t('kare.yok')), j.hata, j.ayrinti, r.status);
        });
      }
      return r.blob();
    }, function () { throw doldu ? hataNesnesi(t('hata.zaman'), 'zaman_asimi') : kapaliHata(); })
      .then(function (blob) {
        clearTimeout(zaman);
        if (S.kareUrl) { try { URL.revokeObjectURL(S.kareUrl); } catch (e) { /* yok say */ } }
        S.kareUrl = URL.createObjectURL(blob);
        return S.kareUrl;
      }, function (e) { clearTimeout(zaman); throw e; });
  }
  function resimYukle(img, url) {
    return new Promise(function (coz, red) {
      img.onload = function () { coz(img); };
      img.onerror = function () { red(hataNesnesi(t('kare.yok'), 'resim_acilmadi')); };
      img.src = url;
    });
  }
  function yukleniyor(metin, id) {
    return h('p', { class: 'yukleniyor-satir', id: id || null, role: 'status' }, [h('span', { class: 'donen', 'aria-hidden': 'true' }), metin]);
  }

  // Hata kutusu: sunucunun kendi mesajı (ne oldu / ne yapmalı) + çözüm düğmeleri + "Ayrıntı" (ham metin, ekran görüntüsü için)
  function hataKutusu(e, id, cozumler) {
    if (e && e.kapali) kapaliBanner(true);
    var p = ikiParca((e && (e.mesaj || e.message)) || t('hata.genel'));
    var k = h('div', { class: 'sonuc kotu hata-kutu', id: id, role: 'alert' }, [
      h('div', { class: 'hata-ne', id: id + '-mesaj', text: p[0] }),
      p[1] ? h('div', { class: 'hata-yap', text: p[1] }) : null
    ]);
    var cz = (cozumler || []).filter(Boolean);
    if (cz.length) {
      k.appendChild(h('div', { class: 'satir hata-cozum' }, cz.map(function (c) {
        return h('button', { type: 'button', class: 'dugme ikincil kucuk', id: c.id, text: c.ad, onclick: c.f });
      })));
    }
    var ham = [e && e.ayrinti, [e && e.hata ? t('ayrinti.kod') + ': ' + e.hata : '', e && e.http ? 'HTTP ' + e.http : ''].filter(Boolean).join(' · ')].filter(Boolean).join('\n');
    if (ham) {
      k.appendChild(h('details', { class: 'ayrinti-kap', id: id + '-ayrinti-kap' }, [
        h('summary', { text: t('ayrinti.baslik') }),
        h('p', { class: 'sessiz', text: t('tv.kart.ayrinti_not') }),
        h('pre', { class: 'ayrinti', id: id + '-ayrinti', text: ham })
      ]));
    }
    return k;
  }

  // ---------- REHBERLER: cihaz kurulumu ve ekran bağlantısı (adım adım, simgeli) ----------
  var REHBER = {
    pc: { ik: 'pc', adim: ['ayar', 'oyna', 'pencere'] },
    ps5: { ik: 'ps5', adim: ['indir', 'kullanici', 'baglan', 'pencere', 'tik'] },
    xbox: { ik: 'xbox', adim: ['oyna', 'kullanici', 'baglan', 'pencere'] },
    kart: { ik: 'kart', adim: ['oyna', 'arti', 'yansit', 'pencere', 'goz'] },
    bilgisayar: { ik: 'pc', adim: ['ayar', 'tv', 'pencere'] },
    lg: { ik: 'tv', adim: ['wifi', 'tv', 'klavye', 'oyna'] },
    samsung: { ik: 'tv', adim: ['wifi', 'klavye', 'tv', 'pencere', 'oyna'], adres: true },
    android: { ik: 'tv', adim: ['wifi', 'klavye', 'tv', 'pencere', 'oyna'], adres: true },
    apple: { ik: 'tv', adim: ['kablo', 'pc', 'yansit', 'telefon'], adres: true },
    hdmi: { ik: 'kablo', adim: ['kablo', 'tv', 'klavye', 'tik'] }
  };
  var REHBER_EKRAN = ['bilgisayar', 'lg', 'samsung', 'android', 'apple', 'hdmi'];

  function adresBlok() {
    var d = S.durum || {}, kapi = d.kapi || (S.ayarlar && S.ayarlar.kapi) || 8642, ipler = d.adresler || [];
    var k = h('div', { class: 'rehber-adres', 'data-rehber-adres': '1' }, [h('div', { class: 'etiket-kucuk', text: t('rehber.adres_baslik') })]);
    if (!ipler.length) k.appendChild(h('p', { class: 'sessiz', text: t('rehber.adres_yok') }));
    ipler.forEach(function (ip) { k.appendChild(h('span', { class: 'adres', text: 'http://' + ip + ':' + kapi + '/tv' })); });
    k.appendChild(h('p', { class: 'sessiz', text: t('rehber.adres_not') }));
    return k;
  }
  // tek rehberin içi: "Bu ne işe yarar?" + numaralı adımlar + (varsa) ek + "Sorun mu var?"
  function rehberGovde(id, o) {
    o = o || {};
    var d = REHBER[id], ol = h('ol', { class: 'rehber-adimlar' });
    d.adim.forEach(function (ik, i) {
      var n = i + 1;
      ol.appendChild(h('li', { class: 'rehber-adim' }, [
        h('span', { class: 'rehber-ik', 'aria-hidden': 'true' }, [ikon(ik), h('span', { class: 'rehber-no', text: String(n) })]),
        h('div', { class: 'rehber-metin' }, [h('span', { class: 'gizli', text: t('rehber.adim_no', { n: n }) + ': ' }), h('b', { text: t('rg.' + id + '.s' + n) }), h('span', { text: t('rg.' + id + '.s' + n + '.k') })])
      ]));
    });
    var kok = h('div', { class: 'rehber-govde', 'data-rehber-govde': id }, [
      h('p', { class: 'rehber-ne' }, [h('b', { text: t('rehber.ne') + ' ' }), t('rg.' + id + '.ne')]), ol]);
    if (d.adres) kok.appendChild(adresBlok());
    if (o.ekstra) kok.appendChild(o.ekstra);
    kok.appendChild(h('details', { class: 'rehber-sorun' }, [
      h('summary', { text: t('rehber.sorun') }),
      h('ul', {}, t('rg.' + id + '.sorun').split('\n').map(function (x) { return h('li', { text: x }); }))
    ]));
    return kok;
  }
  // açılıp kapanan kart (ekran rehberleri)
  function rehberKart(id, o) {
    o = o || {};
    var ekstra = null;
    if (id === 'lg') {
      ekstra = o.lgKart ? tvKarti() : h('div', { class: 'satir' }, h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'rehber-lg-ac', text: t('rehber.lg_ac'), onclick: function () { if (o.lgAc) o.lgAc(); } }));
    }
    return h('details', { class: 'kart rehber-kart', id: 'rehber-' + id, 'data-rehber': id }, [
      h('summary', {}, [
        h('span', { class: 'rehber-ik buyuk', 'aria-hidden': 'true' }, ikon(REHBER[id].ik)),
        h('span', { class: 'rehber-baslik' }, [h('b', { text: t('rg.' + id + '.baslik') }), h('small', { text: t('rehber.ac') })])
      ]),
      rehberGovde(id, { ekstra: ekstra })
    ]);
  }
  function rehberListesi(o) {
    return h('div', { class: 'rehber-liste', id: 'rehber-liste' }, REHBER_EKRAN.map(function (id) { return rehberKart(id, o); }));
  }
  function rehberEkrani() {
    ana.textContent = '';
    ana.appendChild(h('section', { class: 'dar', id: 'rehber-ekran' }, [
      h('h1', { text: t('rehber.baslik') }),
      h('p', { class: 'alt-baslik', text: t('rehber.alt') }),
      rehberListesi({ lgKart: true }),
      h('div', { class: 'alt-gezinme' }, h('button', { type: 'button', class: 'dugme ikincil', id: 'rehber-geri', text: t('rehber.geri'), onclick: function () { S.rehberEkrani = false; ciz(); } }))
    ]));
  }

  // ---------- PS5 GİZLİ BAĞLANTI (PROTOKOL §15): pencere açmaz, kol göndermez; 3 adım ----------
  function ps5GizliKart(kaynakSecF) {
    var kok = h('div', { class: 'kart ps5-gizli', id: 'ps5-gizli' });
    var zamanlayici = null, onizZaman = null;
    function temizle() { if (zamanlayici) { clearTimeout(zamanlayici); zamanlayici = null; } if (onizZaman) { clearTimeout(onizZaman); onizZaman = null; } }
    function adimBaslik(n, anahtar, bitti) {
      return h('h3', { class: 'ps5-adim-bas' }, [h('span', { class: 'rozet' + (bitti ? ' yesil' : ''), text: bitti ? '✓' : String(n) }), h('span', { text: t(anahtar) })]);
    }
    function yukle() {
      temizle();
      return api('GET', '/api/ps5').then(ciz5, function (e) { kok.textContent = ''; kok.appendChild(hataKutusu(e, 'ps5-hata')); });
    }
    function ciz5(d) {
      kok.textContent = '';
      kok.appendChild(h('div', { class: 'kart-bas' }, h('h2', {}, [ikon('ps5'), h('span', { text: t('ps5g.baslik') })])));
      kok.appendChild(h('p', { class: 'ne' }, [h('b', { text: t('ne.etiket') + ' ' }), t('ps5g.ne')]));
      if (!d.destek) {
        kok.appendChild(h('div', { class: 'ipucu', id: 'ps5-destek-yok', text: t(d.neden === 'yalniz_windows' ? 'ps5g.yalniz_windows' : 'ps5g.yardimci_yok') }));
        return;
      }
      // 1) ikinci PSN hesabı
      var a1 = h('div', { class: 'ps5-adim', id: 'ps5-adim-1' }, [adimBaslik(1, 'ps5g.a1', d.hesap.var)]);
      if (d.hesap.var) {
        a1.appendChild(h('p', { class: 'sessiz', id: 'ps5-hesap-ozet', text: t('ps5g.a1.tamam', { ozet: d.hesap.ozet || '' }) }));
      } else {
        a1.appendChild(adimlar('ps5g.a1.adimlar'));
        var adresGir = h('input', { type: 'text', id: 'ps5-adres', autocomplete: 'off', spellcheck: 'false', placeholder: t('ps5g.a1.yer') });
        var a1Durum = h('div', { id: 'ps5-a1-durum', 'aria-live': 'polite' });
        a1.appendChild(h('div', { class: 'satir' }, [
          h('button', { type: 'button', class: 'dugme', id: 'ps5-sony-ac', text: t('ps5g.a1.ac'), onclick: function () {
            api('POST', '/api/ps5/psn/adres').then(function (r) { window.open(r.adres, '_blank', 'noopener'); }, function (e) { a1Durum.textContent = ''; a1Durum.appendChild(hataKutusu(e, 'ps5-a1-hata')); });
          } })]));
        a1.appendChild(h('label', { class: 'etiket-kucuk', for: 'ps5-adres', text: t('ps5g.a1.yapistir') }));
        a1.appendChild(h('div', { class: 'satir' }, [adresGir, h('button', { type: 'button', class: 'dugme sari', id: 'ps5-adres-kaydet', text: t('ps5g.a1.kaydet'), onclick: function () {
          a1Durum.textContent = ''; a1Durum.appendChild(yukleniyor(t('ps5g.a1.bekle')));
          api('POST', '/api/ps5/psn/kod', { adres: adresGir.value }, 40000).then(yukle, function (e) { a1Durum.textContent = ''; a1Durum.appendChild(hataKutusu(e, 'ps5-a1-hata')); });
        } })]));
        var elleGir = h('input', { type: 'text', id: 'ps5-kimlik', autocomplete: 'off', spellcheck: 'false', placeholder: 'AbCdEfGhIjk=' });
        a1.appendChild(h('details', { class: 'sorun-ac', id: 'ps5-elle' }, [h('summary', { text: t('ps5g.a1.elle') }),
          h('div', { class: 'satir' }, [elleGir, h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'ps5-kimlik-kaydet', text: t('ps5g.a1.kaydet'), onclick: function () {
            api('POST', '/api/ps5/psn/elle', { kimlik: elleGir.value }).then(yukle, function (e) { a1Durum.textContent = ''; a1Durum.appendChild(hataKutusu(e, 'ps5-a1-hata')); });
          } })])]));
        a1.appendChild(a1Durum);
      }
      kok.appendChild(a1);
      // 2) PS5'te "Cihazı Bağla" kodu
      var kayitli = !!(d.konsol && d.konsol.kayitli);
      var a2 = h('div', { class: 'ps5-adim', id: 'ps5-adim-2' }, [adimBaslik(2, 'ps5g.a2', kayitli)]);
      if (kayitli) {
        a2.appendChild(h('p', { class: 'sessiz', id: 'ps5-konsol-ozet', text: t('ps5g.a2.tamam', { ad: d.konsol.ad || 'PS5', ip: d.konsol.host || '' }) }));
      }
      if (d.hesap.var && !kayitli) {
        a2.appendChild(adimlar('ps5g.a2.adimlar'));
        var ipGir = h('input', { type: 'text', id: 'ps5-ip', autocomplete: 'off', inputmode: 'decimal', placeholder: '192.168.1.30', value: (d.konsol && d.konsol.host) || '' });
        var pinGir = h('input', { type: 'text', id: 'ps5-pin', autocomplete: 'off', inputmode: 'numeric', maxlength: '11', placeholder: '1234 5678' });
        var liste = h('div', { class: 'liste', id: 'ps5-konsollar' });
        var a2Durum = h('div', { id: 'ps5-a2-durum', 'aria-live': 'polite' });
        function ara() {
          liste.textContent = ''; liste.appendChild(yukleniyor(t('ps5g.a2.araniyor')));
          api('POST', '/api/ps5/bul', {}, 20000).then(function (r) {
            liste.textContent = '';
            if (!r.konsollar.length) liste.appendChild(h('p', { class: 'sessiz', id: 'ps5-bulunamadi', text: t('ps5g.a2.yok') }));
            r.konsollar.forEach(function (k) {
              liste.appendChild(h('button', { type: 'button', class: 'sec', 'data-ps5-host': k.host, 'aria-pressed': String(ipGir.value === k.host), onclick: function () {
                ipGir.value = k.host; liste.querySelectorAll('[data-ps5-host]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.ps5Host === k.host)); });
              } }, [h('span', { class: 'sec-ad', text: k.ad + ' · ' + k.host }), h('span', { class: 'sec-alt', text: t('ps5g.durum.' + (k.durum === 'uyku' ? 'uyku' : 'acik')) })]));
            });
            if (r.konsollar.length === 1 && !ipGir.value) ipGir.value = r.konsollar[0].host;
          }, function (e) { liste.textContent = ''; liste.appendChild(hataKutusu(e, 'ps5-bul-hata')); });
        }
        a2.appendChild(h('div', { class: 'satir' }, h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'ps5-ara', text: t('ps5g.a2.ara'), onclick: ara })));
        a2.appendChild(liste);
        a2.appendChild(h('label', { class: 'etiket-kucuk', for: 'ps5-ip', text: t('ps5g.a2.ip') }));
        a2.appendChild(ipGir);
        a2.appendChild(h('label', { class: 'etiket-kucuk', for: 'ps5-pin', text: t('ps5g.a2.pin') }));
        a2.appendChild(h('div', { class: 'satir' }, [pinGir, h('button', { type: 'button', class: 'dugme sari', id: 'ps5-kaydet', text: t('ps5g.a2.bagla'), onclick: function () {
          a2Durum.textContent = ''; a2Durum.appendChild(yukleniyor(t('ps5g.a2.bekle')));
          api('POST', '/api/ps5/kaydet', { host: ipGir.value.trim(), pin: pinGir.value }, 70000).then(yukle, function (e) {
            a2Durum.textContent = ''; a2Durum.appendChild(hataKutusu(e, 'ps5-a2-hata', [{ id: 'ps5-a2-tekrar', ad: t('genel.tekrar'), f: function () { pinGir.value = ''; pinGir.focus(); } }]));
          });
        } })]));
        a2.appendChild(a2Durum);
        ara();
      }
      kok.appendChild(a2);
      // 3) bağlantı testi: canlı önizleme + kol sorusu
      var a3 = h('div', { class: 'ps5-adim', id: 'ps5-adim-3' }, [adimBaslik(3, 'ps5g.a3', d.kol_tv === true && d.baglanti.durum === 'bagli')]);
      if (kayitli) {
        var b = d.baglanti || {};
        var a3Durum = h('div', { id: 'ps5-a3-durum', 'aria-live': 'polite' });
        var resim = h('img', { class: 'kare-resim', id: 'ps5-onizleme', alt: t('ps5g.a3.resim'), hidden: true });
        a3.appendChild(h('p', { class: 'sessiz', id: 'ps5-baglanti-durum', text: t('ps5g.baglanti.' + (b.durum || 'kapali')) + (b.mesaj ? ' — ' + b.mesaj : '') }));
        if (b.durum === 'kapali' || b.durum === 'hata') {
          a3.appendChild(h('div', { class: 'satir' }, h('button', { type: 'button', class: 'dugme', id: 'ps5-baglan', text: t('ps5g.a3.baglan'), onclick: function () {
            a3Durum.textContent = ''; a3Durum.appendChild(yukleniyor(t('ps5g.a3.bekle')));
            api('POST', '/api/ps5/baglan', {}, 20000).then(yukle, function (e) { a3Durum.textContent = ''; a3Durum.appendChild(hataKutusu(e, 'ps5-a3-hata')); });
          } })));
        } else {
          if (b.giris_pin) {
            var gp = h('input', { type: 'password', id: 'ps5-giris-pin', inputmode: 'numeric', maxlength: '4', autocomplete: 'off' });
            a3.appendChild(h('div', { class: 'ipucu', id: 'ps5-giris-pin-kutu' }, [t('ps5g.a3.giris_pin'), h('div', { class: 'satir' }, [gp,
              h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'ps5-giris-pin-gonder', text: t('ps5g.a1.kaydet'), onclick: function () { api('POST', '/api/ps5/giris-pin', { pin: gp.value }).catch(hataGoster); } })])]));
          }
          a3.appendChild(h('div', { class: 'kare-sahne' }, resim));
          a3.appendChild(h('div', { class: 'satir' }, h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'ps5-kes', text: t('ps5g.a3.kes'), onclick: function () { api('POST', '/api/ps5/kes').then(yukle, hataGoster); } })));
          if (b.durum === 'bagli') {
            var soru = h('div', { class: 'ps5-kol', id: 'ps5-kol-soru' }, [h('p', {}, h('b', { text: t('ps5g.a3.soru') })),
              h('div', { class: 'satir' }, [
                h('button', { type: 'button', class: 'dugme', id: 'ps5-kol-evet', text: t('ps5g.a3.evet'), onclick: function () {
                  api('POST', '/api/ps5/kol', { calisiyor: true }).then(function () { if (kaynakSecF) kaynakSecF('ps5:gizli'); yukle(); }, hataGoster);
                } }),
                h('button', { type: 'button', class: 'dugme ikincil', id: 'ps5-kol-hayir', text: t('ps5g.a3.hayir'), onclick: function () {
                  api('POST', '/api/ps5/kol', { calisiyor: false }).then(yukle, hataGoster);
                } })])]);
            a3.appendChild(soru);
            if (d.kol_tv === true) a3.appendChild(h('div', { class: 'sonuc iyi', id: 'ps5-hazir', text: t('ps5g.a3.hazir') }));
            if (d.kol_tv === false) a3.appendChild(h('div', { class: 'ipucu', id: 'ps5-kol-yardim' }, adimlar('ps5g.a3.kol_yardim')));
            var onizle5 = function () {
              if (!document.body.contains(resim)) { temizle(); return; }
              fetch('/api/ps5/onizleme?_=' + Date.now(), { cache: 'no-store' }).then(function (r) { return r.ok ? r.blob() : null; }).then(function (bl) {
                if (bl) { var u = URL.createObjectURL(bl); resim.onload = function () { URL.revokeObjectURL(u); }; resim.src = u; resim.hidden = false; }
              }, function () {}).then(function () { onizZaman = setTimeout(onizle5, 1500); });
            };
            onizZaman = setTimeout(onizle5, 0);   // kart sayfaya eklendikten sonra
          }
          if (b.durum !== 'bagli') zamanlayici = setTimeout(yukle, 1500);   // bağlanırken durum yenilenir
        }
        a3.appendChild(a3Durum);
      }
      kok.appendChild(a3);
      kok.appendChild(h('details', { class: 'sorun-ac', id: 'ps5-yedek' }, [h('summary', { text: t('ps5g.yedek.baslik') }), adimlar('ps5g.yedek')]));
      if (d.hesap.var || kayitli) {
        kok.appendChild(h('div', { class: 'satir' }, h('button', { type: 'button', class: 'baglanti', id: 'ps5-unut', text: t('ps5g.unut'), onclick: function () {
          if (window.confirm(t('ps5g.unut.onay'))) api('DELETE', '/api/ps5').then(yukle, hataGoster);
        } })));
      }
    }
    yukle();
    return kok;
  }

  // ---------- SİHİRBAZ: 6 aşama, her biri ayrı ekran ----------
  var ASAMALAR = ['goruntu', 'okuma', 'ceviri', 'gosterim', 'bolge', 'hazir'];
  function asamaOku() { try { var v = JSON.parse(ls('asamalar') || '{}'); return v && typeof v === 'object' ? v : {}; } catch (e) { return {}; } }
  function asamaYaz(n, d) { S.asama[n] = d; ls('asamalar', JSON.stringify(S.asama)); }

  function stepper(aktif) {
    var w = h('ol', { class: 'noktalar', 'aria-label': t('sihirbaz.adim', { n: aktif, m: ASAMALAR.length }) });
    ASAMALAR.forEach(function (k, i) {
      var n = i + 1, d = S.asama[n], simdi = n === aktif;
      var cls = 'nokta' + (simdi ? ' aktif' : (d === 'tamam' ? ' bitti' : (d === 'atlandi' ? ' atlandi' : '')));
      var durumYazi = d === 'tamam' ? t('asama.durum.tamam') : (d === 'atlandi' ? t('asama.durum.atlandi') : '');
      var ic = [h('b', { class: 'nokta-no', 'aria-hidden': 'true', text: d === 'tamam' && !simdi ? '✓' : (d === 'atlandi' && !simdi ? '!' : String(n)) }),
        h('span', { class: 'nokta-ad', text: t('asama.' + k) }), durumYazi ? h('span', { class: 'gizli', text: ' (' + durumYazi + ')' }) : null];
      // geçilmiş aşamalara geri dönülebilir (sorun aramayı kolaylaştırır)
      var gidilir = !simdi && !S.tekAsama && (d || n < aktif) && n < 6;
      w.appendChild(h('li', { class: cls, 'aria-current': simdi ? 'step' : null },
        gidilir ? h('button', { type: 'button', class: 'nokta-dugme', 'data-asama-git': String(n), onclick: function () { S.adim = n; ciz(); } }, ic) : h('span', { class: 'nokta-ic' }, ic)));
    });
    return w;
  }

  // Ortak aşama çerçevesi: başlık, gövde, "✓ Çalıştı" kutusu, "Sorun mu var?", Geri / Bu adımı atla / Devam
  function asamaCerceve(n, o) {
    var tek = S.tekAsama === n;
    var panodan = tek && S.donus === 'ana';   // ana ekrandaki "Değiştir": odaklı tek ekran, adım çubuğu yok, "Bitti" her zaman açık
    var donusMetni = S.donus === 6 ? t('asama.hazira_don') : t('asama.ana_don');
    var kontrol = h('div', { class: 'dogrulama', id: 'dogrula-' + n, role: 'status', 'aria-live': 'polite', hidden: true });
    var devam = h('button', { type: 'button', class: 'dugme', id: 'ileri-' + n, disabled: !(o.hazir || panodan), text: tek ? donusMetni : (o.devamMetni || t('sihirbaz.ileri')), onclick: function () {
      if (o.devamOnce) { var r = o.devamOnce(); if (r === false) return; }
      if (S.asama[n] !== 'tamam' && !o.devamSerbest && !panodan) asamaYaz(n, 'tamam');
      ilerle(n);
    } });
    var atla = panodan ? null : h('button', { type: 'button', class: 'baglanti', id: 'atla-' + n, text: t('asama.atla'), onclick: function () {
      if (S.asama[n] !== 'tamam') asamaYaz(n, 'atlandi');
      ilerle(n);
    } });
    var geri = (n > 1 && !tek) ? h('button', { type: 'button', class: 'dugme ikincil', id: 'geri-' + n, text: t('sihirbaz.geri'), onclick: function () { S.adim = n - 1; ciz(); } }) : null;
    var vazgec = tek ? h('button', { type: 'button', class: 'dugme ikincil', id: 'vazgec-' + n, text: t('asama.vazgec'), onclick: function () { donus(); } }) : null;
    var sorun = o.sorun ? h('details', { class: 'sorun-ac', id: 'sorun-' + n }, [h('summary', { text: t('asama.sorun') }), adimlar(o.sorun)]) : null;
    var bolumEl = h('section', { class: 'asama asama-' + n + (o.genis ? ' genis-asama' : '') + (panodan ? ' odakli' : '') }, [
      panodan ? anaDonusLink(function () { donus(); }) : stepper(n),
      panodan ? null : h('p', { class: 'asama-ust', text: t('asama.no', { n: n, m: ASAMALAR.length }) + ' · ' + t('asama.' + ASAMALAR[n - 1]) }),
      h('h1', { text: o.baslik }),
      o.alt ? h('p', { class: 'alt-baslik', text: o.alt }) : null,
      o.ne ? ne(o.ne) : null
    ].concat(o.govde || [], [kontrol, sorun,
      h('div', { class: 'alt-gezinme' }, [h('span', { class: 'satir' }, [geri, vazgec]), h('span', { class: 'satir' }, [atla, devam])])]));
    ana.appendChild(bolumEl);
    return {
      el: bolumEl, devam: devam,
      tamam: function (baslik, ek) {
        kontrol.textContent = '';
        kontrol.appendChild(h('div', { class: 'dogrulama-bas' }, [h('span', { class: 'onay-isaret', 'aria-hidden': 'true' }), h('span', { text: t('asama.calisti') })]));
        kontrol.appendChild(h('div', { class: 'dogrulama-metin', id: 'dogrula-' + n + '-metin', text: baslik }));
        if (ek) kontrol.appendChild(ek);
        kontrol.hidden = false; devam.disabled = false;
        asamaYaz(n, 'tamam');
      },
      sifirla: function () { kontrol.hidden = true; kontrol.textContent = ''; devam.disabled = !(o.hazir || panodan); }
    };
  }
  // odaklı ekranların üstündeki "Ana ekran" dönüş bağlantısı
  function anaDonusLink(f) {
    return h('button', { type: 'button', class: 'geri-link', id: 'ana-don', onclick: f }, [
      h('span', { class: 'ikon', 'aria-hidden': 'true' }, ikon('geri')), h('span', { text: t('pano.ana_don') })]);
  }
  function ilerle(n) { if (S.tekAsama === n) { donus(); return; } S.adim = n + 1; ciz(); }
  function donus() { var d = S.donus; S.tekAsama = null; S.donus = null; if (d === 6) S.adim = 6; ciz(); }
  function asamaAc(n, nereye) { S.tekAsama = n; S.donus = nereye; ciz(); }

  function sihirbaz(n) {
    ana.textContent = '';
    [asama1, asama2, asama3, asama4, asama5, asama6][(n || 1) - 1]();
  }

  // ---------- 1. GÖRÜNTÜ ----------
  function asama1() {
    var kaynakKutu = h('div', { class: 'liste', id: 'kaynak-liste' });
    var ipucu = h('div', { class: 'ipucu', id: 'kaynak-ipucu', hidden: true });
    var resim = h('img', { class: 'kare-resim', id: 'onizleme-resim', alt: t('goruntu.resim_alt'), draggable: 'false' });
    var sahne = h('div', { class: 'kare-sahne', id: 'goruntu-sahne', hidden: true }, [resim, h('span', { class: 'canli-rozet', text: t('goruntu.canli') })]);
    var durum = h('div', { id: 'goruntu-durum', 'aria-live': 'polite' });
    var kaynakDurum = h('div', { id: 'kaynak-durum' });
    var uyariKutu = h('div', { id: 'kaynak-uyari-alani' });
    var rehberKutu = h('div', { id: 'kaynak-rehber-alani' });
    var elle = false;   // kullanıcı kaynağı kendisi seçtiyse otomatik seçimle ezme
    function yenileyin(sonra) {
      kaynakDurum.textContent = ''; kaynakDurum.appendChild(yukleniyor(t('kaynak.araniyor')));
      return kaynakYukle(S.cihaz).then(function () { kaynakDurum.textContent = ''; kaynakCiz(); if (sonra) sonra(); }).catch(function (e) {
        kaynakDurum.textContent = ''; kaynakDurum.appendChild(hataKutusu(e, 'kaynak-hata')); if (sonra) sonra(true);
      });
    }
    var yenile = h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'kaynak-yenile', text: t('kaynak.yenile'), onclick: function () {
      yenileyin(function () { if (!elle) otoSec(true); });
    } });
    var onizKart = h('div', { class: 'kart', id: 'onizleme-kart', hidden: true }, [
      h('div', { class: 'kart-bas' }, [h('h2', { text: t('goruntu.onizleme') }),
        h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'goruntu-yenile', text: t('goruntu.yenile'), onclick: function () { onizle(); } })]),
      sahne, durum
    ]);
    var kaynakKart = h('div', { class: 'kart', id: 'kaynak-kart', hidden: true }, [
      h('div', { class: 'kart-bas' }, [h('h2', { text: t('adim1.kaynak_baslik') }), yenile]), kaynakDurum, uyariKutu, kaynakKutu, rehberKutu]);
    var c;
    function onizle() {
      if (!c) return;
      c.sifirla(); durum.textContent = ''; durum.appendChild(yukleniyor(t('goruntu.aliniyor'), 'goruntu-bekle'));
      return kareAl().then(function (url) { return resimYukle(resim, url); }).then(function () {
        if (!document.body.contains(durum)) return;
        sahne.hidden = false; durum.textContent = '';
        c.tamam(t('goruntu.tamam'));
      }).catch(function (e) {
        sahne.hidden = true; durum.textContent = '';
        durum.appendChild(hataKutusu(e, 'goruntu-hata', [
          { id: 'goruntu-tekrar', ad: t('genel.tekrar'), f: onizle },
          { id: 'goruntu-baska', ad: t('goruntu.baska'), f: function () { kaynakKutu.scrollIntoView({ block: 'center' }); var b = kaynakKutu.querySelector('button'); if (b) b.focus(); } }
        ]));
      });
    }
    function pencereMi(k) { return k.tur ? k.tur === 'pencere' : k.kod.indexOf('pencere') === 0; }
    function onerilenBul() { return S.kaynaklar.filter(function (k) { return k.onerilen && !k.haric; })[0] || null; }
    function otoSec(zorla) {   // önerilen pencereyi seç; yenilemede kullanıcının geçerli seçimine dokunma
      var o = onerilenBul();
      if (!o || S.kaynak === o.kod) return false;
      if (!zorla && S.kaynak && S.kaynaklar.some(function (k) { return k.kod === S.kaynak; })) return false;
      kaynakSec(o.kod, true); return true;
    }
    function kaynakCiz() {
      kaynakKutu.textContent = ''; uyariKutu.textContent = ''; rehberKutu.textContent = '';
      if (!S.kaynaklar.length) { kaynakKutu.appendChild(h('p', { class: 'bos-durum', text: t('kaynak.bos') })); }
      var oner = onerilenBul(), secili = S.kaynaklar.filter(function (k) { return k.kod === S.kaynak; })[0];
      if (oner && pencereMi(oner) && secili && !pencereMi(secili)) {   // tüm ekran seçili ama önerilen pencere var: nazik uyarı
        uyariKutu.appendChild(h('div', { class: 'ipucu', id: 'ekran-uyari', role: 'status' }, [
          t('kaynak.ekran_uyari', { ad: oner.ad }),
          h('div', { class: 'satir' }, h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'oneri-sec', text: t('kaynak.oneri_sec'), onclick: function () { elle = true; kaynakSec(oner.kod); } }))]));
      }
      // önerilenler başa; sonra diğerleri
      S.kaynaklar.slice().sort(function (a, b) { return (a.haric ? 1 : 0) - (b.haric ? 1 : 0) || (b.onerilen ? 1 : 0) - (a.onerilen ? 1 : 0); }).forEach(function (k) {
        kaynakKutu.appendChild(h('button', { type: 'button', class: 'sec' + (k.haric ? ' haric' : ''), 'data-kaynak': k.kod, 'aria-pressed': String(S.kaynak === k.kod),
          onclick: function () { elle = true; kaynakSec(k.kod); } }, [
          h('span', { class: 'sec-ad' }, [h('span', { text: k.ad }), k.onerilen ? h('span', { class: 'rozet sari', text: t('kaynak.onerilen') }) : null]),
          h('span', { class: 'sec-alt', text: t(k.tur === 'ps5' ? 'kaynak.tur.ps5' : (pencereMi(k) ? 'kaynak.tur.pencere' : 'kaynak.tur.ekran')) })]));
      });
      // ps5/xbox/kart için uygun pencere yoksa: cihazın kısa rehberi burada
      if (S.cihaz && S.cihaz !== 'pc' && !oner && REHBER[S.cihaz]) {
        rehberKutu.appendChild(h('div', { class: 'kaynak-rehber', id: 'kaynak-rehber' }, [
          h('div', { class: 'ipucu', text: t('rehber.cihaz.yok', { ad: t('cihaz.' + S.cihaz) }) + ' ' + t('rehber.cihaz.yok.k') }),
          rehberGovde(S.cihaz),
          h('div', { class: 'satir' }, h('button', { type: 'button', class: 'dugme', id: 'rehber-yenile', text: t('kaynak.listeyi_yenile'), onclick: function () { yenile.click(); } }))
        ]));
      }
    }
    function kaynakSec(kod, otomatik) {
      S.kaynak = kod; kaynakCiz(); onizKart.hidden = false; onizKart.classList.add('acil');
      api('POST', '/api/ayarlar', { kaynak: kod, cihaz: S.cihaz }).then(function () { S.ayarlar.kaynak = kod; S.ayarlar.cihaz = S.cihaz; }, function () {}).then(onizle);
    }
    function guncelle() {
      document.querySelectorAll('[data-cihaz]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.cihaz === S.cihaz)); });
      ipucu.hidden = !S.cihaz; kaynakKart.hidden = !S.cihaz;
      if (S.cihaz) ipucu.textContent = t('kaynak.ipucu.' + S.cihaz);
      if (typeof ps5Guncelle === 'function') ps5Guncelle();
      kaynakCiz();
    }
    var acikRehber = null;
    function rehberGoster(k) {   // karonun altındaki "Nasıl yapılır?" düğmesi: o cihazın rehberi bir kart olarak açılır
      acikRehber = acikRehber === k ? null : k;
      document.querySelectorAll('[data-rehber-ac]').forEach(function (b) { b.setAttribute('aria-expanded', String(b.dataset.rehberAc === acikRehber)); });
      cihazRehber.textContent = '';
      if (!acikRehber) return;
      cihazRehber.appendChild(h('div', { class: 'kart rehber-panel acil', id: 'cihaz-rehber-kart', 'data-rehber': acikRehber, role: 'region', 'aria-label': t('rg.' + acikRehber + '.baslik') }, [
        h('div', { class: 'kart-bas' }, [h('h2', {}, [ikon(REHBER[acikRehber].ik), h('span', { text: t('rg.' + acikRehber + '.baslik') })]),
          h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'rehber-kapat', text: t('rehber.kapat'), onclick: function () { var a = acikRehber; rehberGoster(a); var b = document.querySelector('[data-rehber-ac="' + a + '"]'); if (b) b.focus(); } })]),
        rehberGovde(acikRehber)
      ]));
    }
    var cihazRehber = h('div', { id: 'cihaz-rehber' });
    var ps5Alan = h('div', { id: 'ps5-alan' });
    function ps5Guncelle() {   // PS5 seçiliyse gizli bağlantı sihirbazı kaynak listesinin üstünde
      if (S.cihaz !== 'ps5') { ps5Alan.textContent = ''; return; }
      if (!ps5Alan.firstChild) ps5Alan.appendChild(ps5GizliKart(function (kod) { elle = true; kaynakYukle(S.cihaz).then(function () { kaynakSec(kod); }, function () { kaynakSec(kod); }); }));
    }
    var cihazIzgara = h('div', { class: 'izgara izgara-4', role: 'group', 'aria-label': t('asama1.baslik') }, CIHAZLAR.map(function (x) {
      var b = karo(x.ik, t('cihaz.' + x.k), t('cihaz.' + x.k + '.kucuk'), S.cihaz === x.k, function () {
        var ilk = !S.cihaz; S.cihaz = x.k; ls('cihaz', x.k); elle = false; guncelle();
        kaynakKart.classList.add('acil');
        // cihaz kaydedilir, sonra o cihaza göre sıralanmış liste alınır; önerilen varsa kendiliğinden seçilir
        function sonra() { if (document.body.contains(kaynakKutu) && S.cihaz === x.k && !elle) otoSec(true); }
        if (S.kaynak && (ilk || onizKart.hidden)) kaynakSec(S.kaynak);
        api('POST', '/api/ayarlar', { cihaz: x.k }).then(function () { S.ayarlar.cihaz = x.k; }, function () {}).then(function () { return yenileyin(sonra); });
      });
      b.dataset.cihaz = x.k;
      var ac = h('button', { type: 'button', class: 'rehber-ac', id: 'rehber-ac-' + x.k, 'data-rehber-ac': x.k, 'aria-expanded': 'false', 'aria-controls': 'cihaz-rehber', onclick: function () { rehberGoster(x.k); } },
        [ikon('soru'), h('span', { text: t('rehber.ac') })]);
      return h('div', { class: 'karo-sarma' }, [b, ac]);
    }));
    c = asamaCerceve(1, {
      baslik: t('asama1.baslik'), alt: t('asama1.alt'), ne: 'asama1.ne', sorun: 'sorun.asama1',
      govde: [cihazIzgara, cihazRehber, ipucu, ps5Alan, kaynakKart, onizKart]
    });
    guncelle();
    if (!S.kaynaklar.length) yenile.click();
    else if (S.cihaz && !S.kaynak) otoSec();
    if (S.cihaz && S.kaynak) { onizKart.hidden = false; onizle(); }
  }

  // ---------- 2. YAZI OKUMA ----------
  function asama2() {
    var resim = h('img', { class: 'kare-resim', id: 'okuma-resim', alt: t('okuma.resim_alt'), draggable: 'false' });
    var katman = h('div', { class: 'okuma-katman', id: 'okuma-katman', 'aria-hidden': 'true' });
    var sahne = h('div', { class: 'kare-sahne', id: 'okuma-sahne', hidden: true }, [resim, katman]);
    var liste = h('ol', { class: 'okunan-liste', id: 'okunan-liste', hidden: true });
    var durum = h('div', { id: 'okuma-durum', 'aria-live': 'polite' });
    var oku = h('button', { type: 'button', class: 'dugme sari', id: 'oku', onclick: function () { okuBaslat(); } }, [ikon('goz'), h('span', { text: t('okuma.dugme') })]);
    var c;
    function kutulariCiz(satirlar) {
      katman.textContent = ''; liste.textContent = '';
      satirlar.forEach(function (s, i) {
        var k = h('div', { class: 'okuma-kutu' }, h('span', { class: 'okuma-no', text: String(i + 1) }));
        k.style.left = s.x * 100 + '%'; k.style.top = s.y * 100 + '%'; k.style.width = s.g * 100 + '%'; k.style.height = s.y2 * 100 + '%';
        k.style.animationDelay = Math.min(i * 40, 320) + 'ms';
        katman.appendChild(k);
        liste.appendChild(h('li', {}, [h('span', { class: 'okuma-no', 'aria-hidden': 'true', text: String(i + 1) }), h('span', { class: 'okunan-metin', text: s.metin })]));
      });
      liste.hidden = !satirlar.length;
    }
    var paket = h('div', { id: 'okuma-paket' });
    function paketKontrol() {   // Türkçe Windows'ta İngilizce okuma paketi yoksa sakin bir öneri göster
      api('GET', '/api/okuma/diller', undefined, 8000).then(function (r) {
        paket.textContent = '';
        if (!r || !r.destek || r.ingilizce) return;
        var dugme = h('button', { type: 'button', class: 'dugme', id: 'okuma-paket-kur' }, t('okuma.paket.dugme'));
        dugme.onclick = function () {
          dugme.disabled = true;
          api('POST', '/api/okuma/ingilizce-kur', {}, 15000).then(function () {
            paket.textContent = '';
            paket.appendChild(h('div', { class: 'ipucu', text: t('okuma.paket.basladi') }));
          }, function (e) { dugme.disabled = false; paket.appendChild(hataKutusu(e, 'okuma-paket-hata', [])); });
        };
        paket.appendChild(h('div', { class: 'ipucu' }, [h('b', { text: t('okuma.paket.baslik') }), h('br'),
          t('okuma.paket.aciklama', { dil: r.kullanilan || '' }), h('div', { class: 'satir' }, dugme)]));
      }, function () {});
    }
    function okuBaslat() {
      c.sifirla(); durum.textContent = ''; oku.disabled = true;
      durum.appendChild(yukleniyor(t('okuma.okuyor'), 'okuma-bekle'));
      var kare = kareAl().then(function (url) { return resimYukle(resim, url); }).then(function () { return true; }, function () { return false; });
      var okuma = api('GET', '/api/okuma-dene', undefined, 25000);
      Promise.all([kare, okuma]).then(function (r) {
        oku.disabled = false;
        if (!document.body.contains(durum)) return;
        var satirlar = ((r[1] && r[1].satirlar) || []).filter(function (s) { return s && typeof s.metin === 'string'; });
        S.okunan = satirlar;
        paketKontrol();
        sahne.hidden = !r[0]; durum.textContent = '';
        kutulariCiz(satirlar);
        if (!satirlar.length) {
          durum.appendChild(h('div', { class: 'ipucu', id: 'okuma-sifir' }, [h('b', { text: t('okuma.sifir') }), h('br'), t('okuma.sifir.k')]));
          return;
        }
        var bilgi = [r[1].okuyucu ? t('okuma.okuyucu', { ad: r[1].okuyucu }) : '', r[1].sure_ms != null ? t('okuma.sure', { n: r[1].sure_ms }) : ''].filter(Boolean).join(' · ');
        c.tamam(t('okuma.tamam', { n: satirlar.length }), bilgi ? h('div', { class: 'sessiz', text: bilgi }) : null);
      }).catch(function (e) {
        oku.disabled = false; durum.textContent = ''; paketKontrol();
        durum.appendChild(hataKutusu(e, 'okuma-hata', [{ id: 'okuma-tekrar', ad: t('genel.tekrar'), f: okuBaslat },
          e && (e.hata === 'kaynak_yok' || e.hata === 'yakalama_yok') ? { id: 'okuma-goruntu', ad: t('okuma.goruntuye_don'), f: function () { S.adim = 1; ciz(); } } : null]));
      });
    }
    c = asamaCerceve(2, {
      baslik: t('asama2.baslik'), alt: t('asama2.alt'), ne: 'asama2.ne', sorun: 'sorun.asama2',
      govde: [h('div', { class: 'kart' }, [h('div', { class: 'satir' }, oku), durum, paket, sahne, liste])]
    });
    if (S.okunan && S.okunan.length && S.kareUrl) {   // daha önce okunduysa göster (yeniden okumak için düğme)
      resimYukle(resim, S.kareUrl).then(function () { sahne.hidden = false; }, function () {});
      kutulariCiz(S.okunan);
    }
  }

  // ---------- 3. ÇEVİRİ ----------
  function asama3() {
    var liste = S.motorlar.filter(function (m) { return m.kod !== 'sahte'; })
      .sort(function (a, b) { var x = MOTOR_SIRA.indexOf(a.kod), y = MOTOR_SIRA.indexOf(b.kod); return (x < 0 ? 99 : x) - (y < 0 ? 99 : y); });
    if (!S.motor) S.motor = (S.ayarlar && S.ayarlar.motor) || null;
    var detay = h('div', { id: 'motor-detay' });
    var yerelZaman = null;
    var c;
    var DENE = 'Hello, how are you?';

    function cozumler(e, m) {
      var k = e && e.hata;
      return [
        { id: 'dene-tekrar', ad: t('genel.tekrar'), f: function () { dene(); } },
        m.kod === 'yerel' && (k === 'motor_hatasi' || k === 'model_yok' || k === 'yerel_hazir_degil' || k === 'yerel_dil_dosyasi_yok') ? { id: 'yerel-yeniden', ad: t('yerel.yeniden'), f: function () { yerelIndir(); } } : null,
        (k === 'anahtar_yok' || k === 'anahtar_gecersiz') ? { id: 'anahtar-odak', ad: t('anahtar.yeniden'), f: function () { var g = $('#anahtar-gir'); if (g) { g.value = ''; g.focus(); } } } : null,
        (k === 'ag_hatasi' && m.kod !== 'yerel' && motorBilgi('yerel')) ? { id: 'yerele-gec', ad: t('motor.yerele_gec'), f: function () { motorSec('yerel'); } } : null
      ];
    }
    function sonucKutu() { return $('#dene-sonuc'); }
    function dene() {
      var m = motorBilgi(S.motor); var sonuc = sonucKutu(); if (!m || !sonuc) return Promise.resolve();
      c.sifirla(); sonuc.textContent = ''; sonuc.appendChild(yukleniyor(t('dene.calisiyor'), 'dene-bekle'));
      return api('POST', '/api/ayarlar', { motor: m.kod }).then(function () { S.ayarlar.motor = m.kod; return api('POST', '/api/dene', { metin: DENE, motor: m.kod }, 45000); }).then(function (r) {
        sonuc.textContent = '';
        c.tamam(t('ceviri.tamam', { ad: m.ad }), h('div', { class: 'ceviri-ornek', id: 'dene-ornek' }, [
          h('div', { class: 'asil', text: DENE }), h('div', { class: 'ceviri', text: '→ ' + r.ceviri }),
          r.sure_ms != null ? h('div', { class: 'sessiz', text: t('ceviri.sure', { n: r.sure_ms }) }) : null]));
        banner('', '');
      }).catch(function (e) {
        sonuc.textContent = ''; sonuc.appendChild(hataKutusu(e, 'dene-hata', cozumler(e, m)));
      });
    }

    // çevrimdışı motor: dil dosyası durumu → İndir → ilerleme → Dene
    function yerelBolum() {
      var kap = h('div', { class: 'yerel-durum', id: 'yerel-durum' });
      kap.appendChild(yukleniyor(t('yerel.bakiliyor')));
      yerelYukle(kap);
      return kap;
    }
    function yerelYukle(kap) {
      kap = kap || $('#yerel-durum'); if (!kap) return;
      api('GET', '/api/motor/yerel').then(function (y) {
        S.yerel = y || {}; yerelCiz(kap);
        var ind = S.yerel.indirme || {};
        if (ind.durum === 'iniyor') yerelTakip();
      }).catch(function (e) {
        if (e && e.http === 404) { S.yerel = { hazir: true, eski: true }; yerelCiz(kap); return; }   // eski sürüm: doğrudan dene
        kap.textContent = ''; kap.appendChild(hataKutusu(e, 'yerel-hata', [{ id: 'yerel-durum-tekrar', ad: t('genel.tekrar'), f: function () { yerelYukle(); } }]));
      });
    }
    function yerelTakip() {
      clearTimeout(yerelZaman);
      yerelZaman = setTimeout(function () { var k = $('#yerel-durum'); if (k && S.motor === 'yerel') yerelYukle(k); }, 700);
    }
    function yerelIndir() {
      var kap = $('#yerel-durum'); if (!kap) return;
      S.yerel = Object.assign({}, S.yerel, { hazir: false, indirme: { durum: 'iniyor', yuzde: 0 } }); yerelCiz(kap);
      api('POST', '/api/motor/yerel/hazirla', {}, 20000).then(function () { yerelTakip(); }).catch(function (e) {
        S.yerel = Object.assign({}, S.yerel, { indirme: { durum: 'hata', mesaj: e.mesaj || e.message, ayrinti: e.ayrinti, hata: e.hata, http: e.http } }); yerelCiz(kap);
      });
    }
    function yerelCiz(kap) {
      var y = S.yerel || {}, ind = y.indirme || {}, mb = y.boyut_mb;
      var bar = $('#yerel-ilerleme', kap);
      if (ind.durum === 'iniyor' && !y.hazir && bar) {   // yerinde güncelle: çubuk kaymadan ilerlesin
        var yz = Math.max(0, Math.min(100, ind.yuzde || 0));
        bar.setAttribute('aria-valuenow', String(yz)); bar.firstChild.style.width = yz + '%';
        $('#yerel-metin', kap).textContent = t('yerel.iniyor', { n: yz });
        return;
      }
      kap.textContent = '';
      var sonuc = h('div', { id: 'dene-sonuc', 'aria-live': 'polite' });
      if (y.hazir) {
        kap.appendChild(h('p', { class: 'hazir-satir', id: 'yerel-hazir' }, [h('span', { class: 'onay-isaret kucuk', 'aria-hidden': 'true' }), y.eski ? t('motor.yerel.yerel_not') : t('yerel.hazir')]));
        kap.appendChild(h('div', { class: 'satir' }, h('button', { type: 'button', class: 'dugme', id: 'sadece-dene', text: t('dene.dugme'), onclick: function () { dene(); } })));
        kap.appendChild(sonuc);
        return;
      }
      if (ind.durum === 'iniyor') {
        var yz2 = Math.max(0, Math.min(100, ind.yuzde || 0));
        kap.appendChild(h('p', { class: 'yerel-metin', id: 'yerel-metin', role: 'status', text: t('yerel.iniyor', { n: yz2 }) }));
        var b2 = h('div', { class: 'ilerleme genis-cubuk', id: 'yerel-ilerleme', role: 'progressbar', 'aria-label': t('yerel.ilerleme'), 'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-valuenow': String(yz2) }, h('i'));
        b2.firstChild.style.width = yz2 + '%';
        kap.appendChild(b2);
        kap.appendChild(h('p', { class: 'sessiz', text: t('yerel.iniyor.k') }));
        return;
      }
      kap.appendChild(h('p', { text: mb ? t('yerel.gerekli', { mb: mb }) : (y.mesaj || t('yerel.gerekli_bos')) }));
      var indirMetni = ind.durum === 'hata' ? (mb ? t('yerel.tekrar_indir', { mb: mb }) : t('genel.tekrar')) : (mb ? t('yerel.indir', { mb: mb }) : t('yerel.indir_bir'));
      kap.appendChild(h('div', { class: 'satir' }, h('button', { type: 'button', class: 'dugme', id: 'yerel-indir', text: indirMetni, onclick: yerelIndir })));
      if (ind.durum === 'hata') {
        kap.appendChild(hataKutusu({ mesaj: ind.mesaj || t('yerel.indirme_hata'), ayrinti: ind.ayrinti, hata: ind.hata || 'indirme', http: ind.http }, 'yerel-hata'));
      }
      kap.appendChild(h('p', { class: 'sessiz', text: t('yerel.gizlilik') }));
    }

    function detayCiz() {
      detay.textContent = ''; clearTimeout(yerelZaman);
      var m = motorBilgi(S.motor); if (!m) return;
      var kart = h('div', { class: 'kart acil' });
      kart.appendChild(h('h2', { text: m.ad }));
      if (S.motor === 'claude') kart.appendChild(h('div', { class: 'not', text: t('motor.claude.abonelik') }));
      if (m.kod === 'yerel') {
        kart.appendChild(yerelBolum());
      } else if (m.anahtar_gerekli) {
        var sonuc = h('div', { id: 'dene-sonuc', 'aria-live': 'polite' });
        if (m.anahtar_kayitli) kart.appendChild(h('p', { class: 'sessiz', text: t('anahtar.kayitli') }));
        kart.appendChild(h('details', {}, [h('summary', { text: t('anahtar.nereden') }), adimlar('rehber.' + m.kod)]));
        kart.appendChild(h('label', { class: 'etiket', for: 'anahtar-gir', text: t('anahtar.etiket') }));
        kart.appendChild(h('input', { type: 'password', id: 'anahtar-gir', autocomplete: 'off', spellcheck: 'false', placeholder: m.anahtar_kayitli ? '••••••••' : t('anahtar.yer') }));
        kart.appendChild(h('p', { class: 'sessiz', text: t('anahtar.guvenli') }));
        kart.appendChild(h('div', { class: 'satir', style: 'margin-top:10px' }, [
          h('button', { type: 'button', class: 'dugme', id: 'kaydet-dene', text: t('anahtar.kaydet_dene'), onclick: function () {
            var v = $('#anahtar-gir').value.trim();
            var once = v ? api('POST', '/api/anahtar', { motor: m.kod, anahtar: v }).then(function () { m.anahtar_kayitli = true; }) : Promise.resolve();
            once.then(dene).catch(function (e) { sonuc.textContent = ''; sonuc.appendChild(hataKutusu(e, 'dene-hata', cozumler(e, m))); });
          } })
        ]));
        kart.appendChild(sonuc);
      } else {
        var sonuc2 = h('div', { id: 'dene-sonuc', 'aria-live': 'polite' });
        kart.appendChild(h('div', { class: 'satir' }, h('button', { type: 'button', class: 'dugme', id: 'sadece-dene', text: t('dene.dugme'), onclick: function () { dene(); } })));
        kart.appendChild(sonuc2);
      }
      detay.appendChild(kart);
      if (m.kod !== 'yerel') detay.appendChild(kaliteSec('wiz'));
    }
    function motorSec(kod) {
      S.motor = kod; if (c) c.sifirla();
      document.querySelectorAll('[data-motor]').forEach(function (x) { x.setAttribute('aria-pressed', String(x.dataset.motor === kod)); });
      detayCiz();
    }
    var izgara = h('div', { class: 'izgara', role: 'group', 'aria-label': t('asama3.baslik') }, liste.map(function (m) {
      var rozet = h('span', { class: 'rozet' + (m.kod === 'claude' ? ' sari' : ''), text: t('motor.' + m.kod + '.rozet') });
      return h('button', { type: 'button', class: 'karo', 'data-motor': m.kod, 'aria-pressed': String(S.motor === m.kod), onclick: function () { motorSec(m.kod); } },
        [h('span', { class: 'b', text: m.ad }), rozet, h('span', { class: 'k', text: t('motor.' + m.kod + '.kisa') })]);
    }));
    c = asamaCerceve(3, {
      baslik: t('asama3.baslik'), alt: t('asama3.alt'), ne: 'asama3.ne', sorun: 'sorun.asama3',
      govde: [izgara, detay],
      devamOnce: function () { if (S.motor) ayarKaydet({ motor: S.motor }); }
    });
    detayCiz();
  }

  // ---------- 4. NEREDE GÖREYİM? ----------
  var GOSTERIMLER = ['bilgisayar', 'tv', 'tarayici'];
  function asama4() {
    var secim = S.gosterim || (S.ayarlar && S.ayarlar.gosterim) || 'bilgisayar';
    if (GOSTERIMLER.indexOf(secim) < 0) secim = 'bilgisayar';
    var detay = h('div', { id: 'gosterim-detay' });
    var c;
    var listeEl = h('div', { class: 'liste gosterim-liste', role: 'group', 'aria-label': t('asama4.baslik') }, GOSTERIMLER.map(function (k) {
      var ik = k === 'bilgisayar' ? 'pc' : (k === 'tv' ? 'tv' : 'web');
      return h('button', { type: 'button', class: 'sec sec-ikonlu', id: 'gosterim-' + k, 'data-gosterim': k, 'aria-pressed': String(secim === k), onclick: function () { sec(k); } }, [
        h('span', { class: 'sec-ik', 'aria-hidden': 'true' }, ikon(ik)),
        h('span', { class: 'sec-ad' }, [t('gosterim.' + k), k === 'bilgisayar' && (S.cihaz === 'pc' || !S.cihaz) ? h('span', { class: 'rozet sari', text: t('kalite.onerilen') }) : null]),
        h('span', { class: 'sec-alt', text: t('gosterim.' + k + '.k') })
      ]);
    }));
    function sec(k) {
      secim = k; S.gosterim = k;
      listeEl.querySelectorAll('[data-gosterim]').forEach(function (x) { x.setAttribute('aria-pressed', String(x.dataset.gosterim === k)); });
      ayarKaydet({ gosterim: k });
      if (c) c.sifirla();
      detayCiz();
    }
    function adresler() {
      var d = S.durum || {}; var kapi = d.kapi || (S.ayarlar && S.ayarlar.kapi) || 8642;
      return { kapi: kapi, ip: d.adresler || [] };
    }
    // ortak deneme: gönder → "gördün mü?" → Evet (✓) / Hayır (ipuçları)
    function denemeAkisi(dugmeMetin, gonder, soruMetin, ipucuAnahtar, tamamMetin, evetOnce) {
      var sonuc = h('div', { id: 'deneme-sonuc', 'aria-live': 'polite' });
      var sorun = h('div', { class: 'ipucu-kutu', id: 'sorun-kutu', hidden: true }, [h('h3', { text: t('sorun.baslik') }), adimlar(ipucuAnahtar),
        h('div', { class: 'satir' }, h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'deneme-tekrar', text: t('adim3.tekrar'), onclick: function () { git(); } }))]);
      var soru = h('div', { class: 'soru-kutu', id: 'soru-kutu', hidden: true }, [h('h3', { text: soruMetin }), h('div', { class: 'satir' }, [
        h('button', { type: 'button', class: 'dugme', id: 'evet', text: t('evet'), onclick: function () { sorun.hidden = true; if (evetOnce) evetOnce(); c.tamam(tamamMetin); } }),
        h('button', { type: 'button', class: 'dugme ikincil', id: 'hayir', text: t('hayir'), onclick: function () { sorun.hidden = false; c.sifirla(); } })
      ])]);
      var dugme = h('button', { type: 'button', class: 'dugme sari', id: 'deneme-yazi', text: dugmeMetin, onclick: function () { git(); } });
      function git() {
        sonuc.textContent = ''; sonuc.appendChild(yukleniyor(t('deneme.gonderiliyor')));
        gonder().then(function () {
          sonuc.textContent = ''; sonuc.appendChild(h('p', { class: 'bilgi-satir', id: 'deneme-gitti', text: t('deneme.gonderildi') })); soru.hidden = false;
        }).catch(function (e) { sonuc.textContent = ''; sonuc.appendChild(hataKutusu(e, 'deneme-hata', [{ id: 'deneme-hata-tekrar', ad: t('genel.tekrar'), f: git }])); });
      }
      return [h('div', { class: 'satir', style: 'margin-top:18px' }, dugme), sonuc, soru, sorun];
    }
    function bilgisayarDetay() {
      var kart = h('div', { class: 'kart acil', id: 'katman-kart' }, [h('h2', { text: t('katman.baslik') }), h('p', { class: 'sessiz', text: t('katman.aciklama') })]);
      var ic = h('div', {}, yukleniyor(t('katman.bakiliyor')));
      kart.appendChild(ic);
      api('GET', '/api/ekran-katmani').catch(function (e) {
        // sunucu "destek yok" bilgisini 200 + {hata, mesaj} ile de verebilir: gövdeyi kullan
        if (e && e.http === 200 && e.govde && e.govde.ekranlar) return e.govde;
        throw e;
      }).then(function (k) {
        if (!document.body.contains(ic)) return;
        ic.textContent = '';
        if (k && (k.destek === false || k.hata)) {
          ic.appendChild(hataKutusu({ mesaj: k.mesaj || t('katman.destek_yok'), ayrinti: k.ayrinti, hata: k.hata || 'katman_destek_yok' }, 'katman-hata', [{ id: 'katman-tarayici', ad: t('katman.tarayiciya_gec'), f: function () { sec('tarayici'); } }]));
          return;
        }
        var ekranlar = (k && k.ekranlar) || [];
        var secili = Number((S.ayarlar && S.ayarlar.katman_ekran) || (k && k.ekran) || 1);
        if (ekranlar.length > 1) {
          var el = h('div', { class: 'liste ekran-liste', role: 'group', 'aria-label': t('katman.hangi_ekran') });
          ekranlar.forEach(function (e) {
            el.appendChild(h('button', { type: 'button', class: 'sec', 'data-ekran': String(e.no), 'aria-pressed': String(secili === e.no), onclick: function () {
              secili = e.no; c.sifirla();
              el.querySelectorAll('[data-ekran]').forEach(function (x) { x.setAttribute('aria-pressed', String(Number(x.dataset.ekran) === e.no)); });
              ayarKaydet({ katman_ekran: e.no });
            } }, [h('span', { class: 'sec-ad', text: e.ad || t('katman.ekran_no', { n: e.no }) })]));
          });
          ic.appendChild(h('h3', { class: 'ara-baslik', text: t('katman.hangi_ekran') }));
          ic.appendChild(el);
        }
        denemeAkisi(t('katman.dene'), function () { return api('POST', '/api/ekran-katmani/dene', { ekran: secili }); },
          t('katman.gordun_mu'), 'sorun.katman', t('gosterim.tamam.bilgisayar'), function () { ayarKaydet({ gosterim: 'bilgisayar', katman_ekran: secili }); })
          .forEach(function (x) { ic.appendChild(x); });
        $('#deneme-yazi', ic).id = 'katman-dene';
      }).catch(function (e) {
        ic.textContent = '';
        ic.appendChild(hataKutusu(e, 'katman-hata', [{ id: 'katman-tekrar', ad: t('genel.tekrar'), f: function () { detayCiz(); } }, { id: 'katman-tarayici', ad: t('katman.tarayiciya_gec'), f: function () { sec('tarayici'); } }]));
      });
      return kart;
    }
    function adresKutusu(lg) {
      var a = adresler(), k = h('div', { id: 'adres-kutu' });
      k.appendChild(h('p', { text: lg ? t('adim3.yedek_adres') : t('adim3.tarayici') }));
      a.ip.forEach(function (ip) { k.appendChild(h('span', { class: 'adres', text: 'http://' + ip + ':' + a.kapi + '/tv' })); });
      if (!lg) k.appendChild(h('p', { class: 'sessiz', style: 'margin-top:10px', text: t('adim3.obs') + ' http://127.0.0.1:' + a.kapi + '/obs' }));
      return k;
    }
    function detayCiz() {
      detay.textContent = '';
      if (secim === 'bilgisayar') { detay.appendChild(bilgisayarDetay()); return; }
      var gonder = function () { return api('POST', '/api/deneme-yazi', {}); };
      if (secim === 'tv') {
        detay.appendChild(tvKarti());
        detay.appendChild(h('div', { class: 'kart acil' }, [h('h2', { text: t('gosterim.tv.dene') }), h('p', { text: t('adim3.lg') }), adresKutusu(true)].concat(
          denemeAkisi(t('adim3.gonder'), gonder, t('adim3.gordun_mu'), 'sorun.liste', t('gosterim.tamam.tv')))));
        return;
      }
      detay.appendChild(h('div', { class: 'kart acil' }, [h('h2', { text: t('gosterim.tarayici') }), adresKutusu(false)].concat(
        denemeAkisi(t('adim3.gonder'), gonder, t('tarayici.gordun_mu'), 'sorun.liste', t('gosterim.tamam.tarayici')))));
    }
    c = asamaCerceve(4, {
      baslik: t('asama4.baslik'), alt: t('asama4.alt'), ne: 'asama4.ne', sorun: 'sorun.asama4',
      govde: [listeEl, h('p', { class: 'sessiz yakinda', id: 'yakinda', text: t('gosterim.yakinda') }), detay,
        h('details', { class: 'kart rehber-bolum', id: 'rehber-bolum' }, [
          h('summary', {}, [h('span', { class: 'rehber-ik buyuk', 'aria-hidden': 'true' }, ikon('yansit')),
            h('span', { class: 'rehber-baslik' }, [h('b', { text: t('rehber.liste_baslik') }), h('small', { text: t('rehber.menu') + ' · ' + t('rehber.liste_k') })])]),
          rehberListesi({ lgAc: function () { sec('tv'); var k = $('#gosterim-tv'); if (k) k.scrollIntoView({ block: 'center' }); } })]),
        h('div', { class: 'kart', id: 'ekran-olcek-kart' }, [ekranOlcekAlani('ekran-olcek'), enAzAlani('en-az')])],
      devamOnce: function () { ayarKaydet({ gosterim: secim }); }
    });
    S.gosterim = secim;
    detayCiz();
  }

  // ---------- 5. NEYİ ÇEVİREYİM? (en son; tam genişlikte editör) ----------
  function asama5() {
    var c;
    var ed = bolgeEditoru({
      degisti: function () { if (c) c.sifirla(); },
      kaydedildi: function (n) { c.tamam(n ? t('bolge.tamam', { n: n }) : t('bolge.tamam_otomatik')); }
    });
    c = asamaCerceve(5, {
      baslik: t('asama5.baslik'), alt: t('asama5.alt'), sorun: 'sorun.asama5', genis: true,
      govde: [ed.el]
    });
    ed.yukle();
  }

  // ---------- 6. HAZIR ----------
  function asama6() {
    var a = S.ayarlar || {};
    function ozet(n) {
      if (n === 1) { var k = S.kaynaklar.filter(function (x) { return x.kod === (S.kaynak || a.kaynak); })[0]; return k ? k.ad : ''; }
      if (n === 2) return S.okunan && S.okunan.length ? t('okuma.tamam', { n: S.okunan.length }) : '';
      if (n === 3) { var m = motorBilgi(a.motor || S.motor); return m ? m.ad : ''; }
      if (n === 4) return t('gosterim.' + (S.gosterim || a.gosterim || 'bilgisayar'));
      if (n === 5) return bolgeOzet();
      return '';
    }
    var liste = h('ul', { class: 'ozet-liste', id: 'ozet-liste' });
    ASAMALAR.slice(0, 5).forEach(function (k, i) {
      var n = i + 1, d = S.asama[n] === 'tamam' ? 'tamam' : 'atlandi';
      liste.appendChild(h('li', { class: 'ozet-satir ' + d, 'data-ozet': String(n) }, [
        h('span', { class: 'ozet-ik', 'aria-hidden': 'true', text: d === 'tamam' ? '✓' : '!' }),
        h('span', { class: 'ozet-metin' }, [h('span', { class: 'ozet-ad', text: n + '. ' + t('asama.' + k) }),
          h('span', { class: 'ozet-alt', text: d === 'tamam' ? (ozet(n) || t('asama.durum.tamam')) : t('asama.durum.atlandi') })]),
        h('button', { type: 'button', class: d === 'tamam' ? 'baglanti' : 'dugme ikincil kucuk', id: 'simdi-yap-' + n, text: d === 'tamam' ? t('hazir.degistir') : t('hazir.simdi_yap'), onclick: function () { S.adim = n; asamaAc(n, 6); } })
      ]));
    });
    var atlanan = ASAMALAR.slice(0, 5).filter(function (k, i) { return S.asama[i + 1] !== 'tamam'; }).length;
    var baslat = h('button', { type: 'button', class: 'buyuk', id: 'hazir-baslat', onclick: function () { kurulumuBitir(); baslatDurdur(); } }, [ikon('oyna'), h('span', { text: t('baslat') })]);
    ana.appendChild(h('section', { class: 'asama asama-6' }, [
      stepper(6),
      h('p', { class: 'asama-ust', text: t('asama.no', { n: 6, m: 6 }) + ' · ' + t('asama.hazir') }),
      h('h1', { text: atlanan ? t('asama6.baslik_eksik') : t('asama6.baslik') }),
      h('p', { class: 'alt-baslik', text: atlanan ? t('asama6.alt_eksik', { n: atlanan }) : t('asama6.alt') }),
      h('div', { class: 'kart' }, liste),
      h('div', { class: 'kart hero hazir-kart' }, [baslat, h('p', { class: 'sessiz', style: 'margin:14px 0 0;text-align:center', text: t('asama6.baslat_not') })]),
      h('div', { class: 'alt-gezinme' }, [h('button', { type: 'button', class: 'dugme ikincil', id: 'geri-6', text: t('sihirbaz.geri'), onclick: function () { S.adim = 5; ciz(); } }),
        h('button', { type: 'button', class: 'baglanti', id: 'hazir-ana', text: t('asama6.ana'), onclick: function () { kurulumuBitir(); } })])
    ]));
  }
  function kurulumuBitir() {
    S.kurulumBitti = true; ls('kurulum', '1'); S.tekAsama = null; S.donus = null;
    if (S.ayarlar) S.ayarlar.kurulum_tamam = true;
    api('POST', '/api/ayarlar', { kurulum_tamam: true }).catch(function () {});
    ciz();
  }

  // ---------- ortak: sakin açıklama satırı, bildirim, pencere ----------
  function ne(anahtar, tur) {
    return h('p', { class: 'ne' }, [h('b', { text: t(tur === 'isi' ? 'isi.etiket' : 'ne.etiket') + ' ' }), t(anahtar)]);
  }
  function sayi(n) { try { return Number(n || 0).toLocaleString(dil === 'tr' ? 'tr-TR' : 'en-US'); } catch (e) { return String(n || 0); } }
  function toast(metin, tur) {
    var kutu = $('#bildirim');
    if (!kutu) { kutu = h('div', { id: 'bildirim', class: 'bildirim', 'aria-live': 'polite' }); document.body.appendChild(kutu); }
    var b = h('div', { class: 'tost' + (tur ? ' ' + tur : ''), role: 'status', text: metin });
    kutu.appendChild(b);
    setTimeout(function () { b.classList.add('cikis'); setTimeout(function () { b.remove(); }, hareketAz() ? 0 : 300); }, 4500);
  }
  // dugmeler: [{ad, deger, sinif, id}] → seçilen değerle çözülen söz (Esc = null)
  function pencere(baslik, govde, dugmeler) {
    return new Promise(function (coz) {
      var onceki = document.activeElement;
      var arka = h('div', { class: 'perde' });
      function kapat(v) { document.removeEventListener('keydown', tus); arka.remove(); if (onceki && onceki.focus) onceki.focus(); coz(v); }
      function tus(e) { if (e.key === 'Escape') kapat(null); }
      var kutu = h('div', { class: 'pencere', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'pencere-baslik' }, [
        h('h2', { id: 'pencere-baslik', text: baslik }),
        h('p', { text: govde }),
        h('div', { class: 'pencere-dugme' }, dugmeler.map(function (d) {
          return h('button', { type: 'button', class: 'dugme ' + (d.sinif || ''), id: d.id, text: d.ad, onclick: function () { kapat(d.deger); } });
        }))
      ]);
      arka.appendChild(kutu);
      document.body.appendChild(arka);
      document.addEventListener('keydown', tus);
      var ilk = kutu.querySelector('button'); if (ilk) ilk.focus();
    });
  }

  // ---------- kalite seçimi (sihirbaz + ayarlar) ----------
  var KALITELER = ['en_iyi', 'dengeli', 'hizli'];
  function kaliteSec(onek) {
    var simdi = (S.ayarlar && S.ayarlar.kalite) || 'en_iyi';
    var kutu = h('div', { class: 'kart', id: 'kalite-' + onek }, [
      h('h2', { text: t('kalite.baslik') }), ne('kalite.ne', 'isi')
    ]);
    var liste = h('div', { class: 'liste' });
    KALITELER.forEach(function (k) {
      var b = h('button', { type: 'button', class: 'sec', id: 'kalite-' + onek + '-' + k, 'data-kalite': k, 'aria-pressed': String(simdi === k), onclick: function () {
        simdi = k;
        kutu.querySelectorAll('[data-kalite]').forEach(function (x) { x.setAttribute('aria-pressed', String(x.dataset.kalite === k)); });
        ayarKaydet({ kalite: k });
      } }, [
        h('span', { class: 'sec-ad' }, [t('kalite.' + k), k === 'en_iyi' ? h('span', { class: 'rozet sari', text: t('kalite.onerilen') }) : null]),
        h('span', { class: 'sec-alt', text: t('kalite.' + k + '.k') })
      ]);
      liste.appendChild(b);
    });
    kutu.appendChild(liste);
    return kutu;
  }

  // ---------- OYUN SEÇİMİ (sihirbaz adım 2 ve "Oyunu değiştir") ----------
  function oyunYukle() {
    return api('GET', '/api/oyunlar').then(function (l) { S.oyunlar = l || []; }).catch(function () { S.oyunlar = S.oyunlar || []; });
  }
  function oyunAdi(kod) {
    var o = S.oyunlar.filter(function (x) { return x.kod === kod; })[0];
    return o ? o.ad : '';
  }
  function hatirlaMetni(o) {
    return o && o.kayit_sayisi ? t('oyun.hatirla', { n: sayi(o.kayit_sayisi) }) : t('oyun.hic');
  }
  function oyunEkrani(mod) {
    var sihirbazda = false;   // oyun seçimi artık ana ekrandan ("Oyunu değiştir")
    var secili = (S.ayarlar && S.ayarlar.aktif_oyun) || null;
    var liste = h('div', { class: 'izgara', id: 'oyun-liste' });
    var devam = h('button', { type: 'button', class: 'dugme', id: 'ileri-oyun', text: sihirbazda ? t('sihirbaz.ileri') : t('oyun.tamam'), onclick: function () {
      api('POST', '/api/oyun-sec', { kod: secili }).then(function () {
        S.ayarlar.aktif_oyun = secili;
        if (sihirbazda) { S.adim = 3; } else { S.oyunDegis = false; }
        ciz();
      }).catch(hataGoster);
    } });
    function guncelle() { devam.disabled = !secili; bilgiCiz(); }
    function listeCiz() {
      liste.textContent = '';
      S.oyunlar.forEach(function (o) {
        var b = h('button', { type: 'button', class: 'karo', 'data-oyun': o.kod, 'aria-pressed': String(secili === o.kod), onclick: function () {
          secili = o.kod; listeCiz(); guncelle();
        } }, [h('span', { class: 'b', text: o.ad }), h('span', { class: 'k', text: hatirlaMetni(o) })]);
        liste.appendChild(b);
      });
      liste.appendChild(h('button', { type: 'button', class: 'karo ekle', id: 'yeni-oyun-ac', onclick: function () {
        yeni.hidden = !yeni.hidden; if (!yeni.hidden) { $('#oyun-ad').focus(); paket.hidden = true; }
      } }, [h('span', { class: 'ik', 'aria-hidden': 'true' }, ikon('arti')), h('span', { class: 'b', text: t('oyun.yeni') })]));
      liste.appendChild(h('button', { type: 'button', class: 'karo ekle', id: 'paket-ac', onclick: function () {
        paket.hidden = !paket.hidden; if (!paket.hidden) yeni.hidden = true;
      } }, [h('span', { class: 'ik', 'aria-hidden': 'true' }, ikon('paket')), h('span', { class: 'b', text: t('oyun.paket') })]));
    }

    // yeni oyun formu
    var hitap = 'sen';
    var hitapDugme = h('div', { class: 'ikili', role: 'group', 'aria-label': t('oyun.hitap') }, ['sen', 'siz'].map(function (k) {
      return h('button', { type: 'button', class: 'sec', 'data-hitap': k, 'aria-pressed': String(k === hitap), text: t('oyun.hitap.' + k), onclick: function () {
        hitap = k; hitapDugme.querySelectorAll('[data-hitap]').forEach(function (x) { x.setAttribute('aria-pressed', String(x.dataset.hitap === k)); });
      } });
    }));
    var ekleHata = h('div', { class: 'sessiz', 'aria-live': 'polite' });
    var yeni = h('div', { class: 'kart', id: 'yeni-oyun-form', hidden: true }, [
      h('label', { class: 'etiket', for: 'oyun-ad', text: t('oyun.ad') }),
      h('input', { type: 'text', id: 'oyun-ad', placeholder: t('oyun.ad_yer'), autocomplete: 'off' }),
      h('label', { class: 'etiket', for: 'oyun-acik', text: t('oyun.acik') }),
      h('input', { type: 'text', id: 'oyun-acik', placeholder: t('oyun.acik_yer'), autocomplete: 'off' }),
      h('label', { class: 'etiket', text: t('oyun.hitap') }), hitapDugme,
      h('p', { class: 'sessiz', text: t('oyun.hitap.k') }),
      h('div', { class: 'satir', style: 'margin-top:14px' }, [
        h('button', { type: 'button', class: 'dugme', id: 'oyun-ekle', text: t('oyun.ekle'), onclick: function () {
          var ad = $('#oyun-ad').value.trim();
          if (!ad) { ekleHata.textContent = t('oyun.ad_gerekli'); return; }
          ekleHata.textContent = '';
          api('POST', '/api/oyunlar', { ad: ad, aciklama: $('#oyun-acik').value.trim(), hitap: hitap }).then(function (r) {
            secili = r.kod; return oyunYukle();
          }).then(function () { yeni.hidden = true; listeCiz(); guncelle(); }).catch(function (e) { ekleHata.textContent = (e && e.mesaj) || t('hata.genel'); });
        } }), ekleHata
      ])
    ]);

    // paket içe aktar
    var paketSonuc = h('div', { id: 'paket-sonuc', 'aria-live': 'polite' });
    var dosya = h('input', { type: 'file', id: 'paket-dosya', accept: '.akpaket', hidden: true, onchange: function () {
      var f = dosya.files && dosya.files[0]; if (!f) return;
      var fd = new FormData(); fd.append('dosya', f, f.name);
      paketSonuc.textContent = ''; paketSonuc.appendChild(h('span', { class: 'sessiz', text: t('oyun.paket.yukleniyor') }));
      api('POST', '/api/paket', fd).then(function (r) {
        paketSonuc.textContent = '';
        paketSonuc.appendChild(h('div', { class: 'sonuc', text: t('oyun.paket.eklendi', { n: sayi(r.eklenen) }) }));
        var once = S.oyunlar.map(function (o) { return o.kod; });
        return oyunYukle().then(function () {
          var yenisi = S.oyunlar.filter(function (o) { return once.indexOf(o.kod) < 0; })[0];
          if (yenisi) secili = yenisi.kod;
          listeCiz(); guncelle();
        });
      }).catch(function (e) {
        paketSonuc.textContent = ''; paketSonuc.appendChild(h('div', { class: 'sonuc kotu', text: (e && e.mesaj) || t('hata.genel') }));
      });
      dosya.value = '';
    } });
    var paket = h('div', { class: 'kart', id: 'paket-kutu', hidden: true }, [
      h('p', { text: t('oyun.paket.aciklama') }),
      h('button', { type: 'button', class: 'dugme ikincil', id: 'paket-sec', text: t('oyun.paket.sec'), onclick: function () { dosya.click(); } }),
      dosya, paketSonuc
    ]);

    // ---- oyun bilgisi: isimleri öğren → incele/düzelt → kaydet (PROTOKOL 12.3) ----
    var bilgiKart = h('div', { class: 'kart', id: 'bilgi-kart', hidden: true });
    var bilgi = { kod: null, faz: 'bos', veri: null, hata: null, sonuc: 0 };
    function bilgiAdim() { return h('div', {}, [h('h2', { text: t('bilgi.baslik') }), h('p', { class: 'sessiz', text: t('bilgi.aciklama') })]); }
    function bilgiCiz() {
      bilgiKart.hidden = !secili;
      if (!secili) return;
      if (bilgi.kod !== secili) bilgi = { kod: secili, faz: 'bos', veri: null, hata: null, sonuc: 0 };
      bilgiKart.textContent = '';
      var ad = oyunAdi(secili) || secili;
      if (bilgi.faz === 'bos' || bilgi.faz === 'hata') {
        bilgiKart.appendChild(bilgiAdim());
        bilgiKart.appendChild(h('p', { class: 'sessiz', text: t('bilgi.not') }));
        bilgiKart.appendChild(h('div', { class: 'satir' }, h('button', { type: 'button', class: 'dugme', id: 'bilgi-hazirla', text: t('bilgi.dugme'), onclick: bilgiHazirla })));
        if (bilgi.faz === 'hata') {
          var e = bilgi.hata;
          var cevrimdisi = (function () { var m = motorBilgi(S.ayarlar && S.ayarlar.motor); return !!(m && m.cevrimdisi) || (e && /cevrimdisi|cevrim_disi|offline/i.test(String(e.hata || ''))); }());
          bilgiKart.appendChild(hataKutusu(e, 'bilgi-hata', [{ id: 'bilgi-tekrar-dene', ad: t('genel.tekrar'), f: bilgiHazirla }]));
          if (cevrimdisi) bilgiKart.appendChild(h('div', { class: 'ipucu', id: 'bilgi-gemini' }, [t('bilgi.cevrimdisi'),
            h('div', { class: 'satir' }, h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'bilgi-motor', text: t('bilgi.motor_degistir'), onclick: function () { asamaAc(3, 'ana'); } }))]));
        }
      } else if (bilgi.faz === 'calisiyor') {
        bilgiKart.appendChild(bilgiAdim());
        bilgiKart.appendChild(h('div', { class: 'belirsiz-bar', id: 'bilgi-ilerleme', role: 'progressbar', 'aria-label': t('bilgi.baslik') }, h('span')));
        bilgiKart.appendChild(yukleniyor(t('bilgi.calisiyor', { ad: ad }), 'bilgi-bekle'));
      } else if (bilgi.faz === 'sonuc') {
        bilgiInceleme(ad);
      } else if (bilgi.faz === 'kaydedildi') {
        bilgiKart.appendChild(h('h2', { text: t('bilgi.baslik') }));
        bilgiKart.appendChild(h('div', { class: 'sonuc', id: 'bilgi-kaydedildi', text: t('bilgi.kaydedildi', { n: bilgi.sonuc }) }));
        bilgiKart.appendChild(h('div', { class: 'satir' }, h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'bilgi-yeniden', text: t('bilgi.tekrar'), onclick: function () { bilgi.faz = 'bos'; bilgiCiz(); } })));
      }
    }
    function bilgiHazirla() {
      var kod = secili;
      bilgi = { kod: kod, faz: 'calisiyor', veri: null, hata: null, sonuc: 0 }; bilgiCiz();
      api('POST', '/api/oyun/' + encodeURIComponent(kod) + '/bilgi-hazirla', {}, 120000).then(function (r) {
        if (bilgi.kod !== kod || !document.body.contains(bilgiKart)) return;
        r = r || {};
        bilgi.veri = {
          aciklama: String(r.aciklama || ''), hitap: r.hitap === 'siz' ? 'siz' : 'sen',
          terimler: (r.terimler || []).filter(function (x) { return x && x.asil; }).map(function (x) { return { asil: String(x.asil), ceviri: String(x.ceviri == null ? x.asil : x.ceviri), sec: true }; }),
          karakterler: (r.karakterler || []).filter(function (x) { return x && x.ad; }).map(function (x) { return { ad: String(x.ad), cinsiyet: x.cinsiyet === 'k' || x.cinsiyet === 'e' ? x.cinsiyet : '' }; })
        };
        bilgi.faz = 'sonuc'; bilgiCiz();
      }).catch(function (e) {
        if (bilgi.kod !== kod || !document.body.contains(bilgiKart)) return;
        bilgi.faz = 'hata'; bilgi.hata = e; bilgiCiz();
      });
    }
    function bilgiInceleme(ad) {
      var v = bilgi.veri, sayac = h('p', { class: 'sessiz', id: 'bilgi-sayac', 'aria-live': 'polite' });
      function say() { var n = v.terimler.filter(function (x) { return x.sec; }).length; sayac.textContent = t('bilgi.secili', { n: n, m: v.terimler.length }); }
      var acik = h('textarea', { id: 'bilgi-aciklama', rows: '2', maxlength: '200', 'aria-label': t('bilgi.aciklama_etiket') });
      acik.value = v.aciklama; acik.addEventListener('input', function () { v.aciklama = acik.value; });
      var hitapEl = h('div', { class: 'ikili', role: 'group', 'aria-label': t('bilgi.hitap') }, ['sen', 'siz'].map(function (k) {
        return h('button', { type: 'button', class: 'sec', 'data-bilgi-hitap': k, 'aria-pressed': String(v.hitap === k), text: t('oyun.hitap.' + k), onclick: function () {
          v.hitap = k; hitapEl.querySelectorAll('[data-bilgi-hitap]').forEach(function (x) { x.setAttribute('aria-pressed', String(x.dataset.bilgiHitap === k)); });
        } });
      }));
      var liste = h('ul', { class: 'bilgi-terimler', id: 'bilgi-terimler' });
      v.terimler.forEach(function (x, i) {
        var cb = h('input', { type: 'checkbox', class: 'bilgi-sec', 'aria-label': t('bilgi.birak', { ad: x.asil }) }); cb.checked = x.sec;
        var gir = h('input', { type: 'text', class: 'bilgi-ceviri', 'aria-label': t('bilgi.ceviri_aria', { ad: x.asil }), autocomplete: 'off', spellcheck: 'false' }); gir.value = x.ceviri;
        var li = h('li', { class: 'bilgi-terim' + (x.sec ? '' : ' birakildi'), 'data-terim': String(i) }, [cb, h('span', { class: 'bilgi-asil', text: x.asil }), h('span', { class: 'bilgi-ok', 'aria-hidden': 'true' }, ikon('ok')), gir]);
        cb.addEventListener('change', function () { x.sec = cb.checked; li.classList.toggle('birakildi', !x.sec); gir.disabled = !x.sec; say(); });
        gir.addEventListener('input', function () { x.ceviri = gir.value; });
        liste.appendChild(li);
      });
      var kaydet = h('button', { type: 'button', class: 'dugme', id: 'bilgi-kaydet', text: t('bilgi.kaydet'), onclick: function () {
        kaydet.disabled = true; kaydet.textContent = t('bilgi.kaydediliyor');
        var secilen = v.terimler.filter(function (x) { return x.sec; }).map(function (x) { return { asil: x.asil, ceviri: (x.ceviri || '').trim() || x.asil }; });
        var kod = bilgi.kod;
        api('POST', '/api/oyun/' + encodeURIComponent(kod) + '/bilgi-kaydet', { aciklama: v.aciklama.trim(), hitap: v.hitap, terimler: secilen, karakterler: v.karakterler || [] }, 30000).then(function () {
          bilgi = { kod: kod, faz: 'kaydedildi', veri: null, hata: null, sonuc: secilen.length };
          return oyunYukle();
        }).then(function () { if (document.body.contains(bilgiKart)) { bilgiCiz(); listeCiz(); } }).catch(function (e) {
          kaydet.disabled = false; kaydet.textContent = t('bilgi.kaydet');
          var eski = $('#bilgi-kaydet-hata'); if (eski) eski.remove();
          bilgiKart.appendChild(hataKutusu(e, 'bilgi-kaydet-hata'));
        });
      } });
      bilgiKart.appendChild(h('h2', { text: t('bilgi.baslik') + ' · ' + ad }));
      bilgiKart.appendChild(h('p', { class: 'ne' }, [h('b', { text: t('bilgi.inceleme') + ': ' }), t('bilgi.inceleme.k')]));
      bilgiKart.appendChild(h('label', { class: 'etiket', for: 'bilgi-aciklama', text: t('bilgi.aciklama_etiket') }));
      bilgiKart.appendChild(acik);
      bilgiKart.appendChild(h('label', { class: 'etiket', text: t('bilgi.hitap') })); bilgiKart.appendChild(hitapEl);
      bilgiKart.appendChild(h('label', { class: 'etiket', text: t('bilgi.terimler') }));
      if (v.terimler.length) {
        bilgiKart.appendChild(h('div', { class: 'bilgi-baslik', 'aria-hidden': 'true' }, [h('span', {}), h('span', { text: t('bilgi.asil') }), h('span', {}), h('span', { text: t('bilgi.ceviri') })]));
        bilgiKart.appendChild(liste);
      } else bilgiKart.appendChild(h('p', { class: 'sessiz', text: t('bilgi.bos_terim') }));
      bilgiKart.appendChild(sayac); say();
      bilgiKart.appendChild(h('div', { class: 'satir', style: 'margin-top:14px' }, [kaydet,
        h('button', { type: 'button', class: 'dugme ikincil', id: 'bilgi-vazgec', text: t('bilgi.vazgec'), onclick: function () { bilgi.faz = 'bos'; bilgiCiz(); } })]));
    }

    var gezinme = h('div', { class: 'alt-gezinme' }, [
      h('button', { type: 'button', class: 'dugme ikincil', id: 'oyun-geri', text: t('sihirbaz.geri'), onclick: function () {
        if (sihirbazda) S.adim = 1; else S.oyunDegis = false; ciz();
      } }),
      h('span', { class: 'satir' }, [
        sihirbazda ? h('button', { type: 'button', class: 'baglanti', id: 'oyun-atla', text: t('oyun.atla'), onclick: function () { S.adim = 3; ciz(); } }) : null,
        devam
      ])
    ]);
    ana.textContent = '';
    ana.appendChild(h('section', { class: 'odakli' }, [
      anaDonusLink(function () { S.oyunDegis = false; ciz(); }),
      h('h1', { text: t('oyun.baslik') }),
      h('p', { class: 'alt-baslik', text: t('oyun.alt') }),
      ne('oyun.ne'),
      liste, yeni, paket, bilgiKart, gezinme
    ]));
    listeCiz(); guncelle();
    if (S.bilgiBaslat && secili) { S.bilgiBaslat = false; bilgiHazirla(); var bk = $('#bilgi-kart'); if (bk) bk.scrollIntoView({ block: 'center' }); }
    S.bilgiBaslat = false;
    oyunYukle().then(function () { if (document.body.contains(liste)) listeCiz(); });
  }

  // ---------- ANA EKRAN (PROTOKOL 13.3): üstte Başlat/Durdur + durum; altında özet kartları, her birinde tek "Değiştir" ----------
  var ekran = {};
  var KISAYOL_ADLAR = ['baslat_durdur', 'gizle_goster', 'yeniden_oku'];
  var KISAYOL_VARSAYILAN = { baslat_durdur: 'ctrl+shift+t', gizle_goster: 'ctrl+shift+h', yeniden_oku: 'ctrl+shift+r' };
  function kisayollar() {
    var k = (S.ayarlar && S.ayarlar.kisayollar) || {};
    var o = {};
    KISAYOL_ADLAR.forEach(function (ad) { o[ad] = typeof k[ad] === 'string' ? k[ad] : (S.ayarlar && S.ayarlar.kisayollar ? '' : KISAYOL_VARSAYILAN[ad]); });
    return o;
  }
  function kisayolYukle() {
    return api('GET', '/api/kisayollar', undefined, 6000).then(function (k) { S.kisayol = k || {}; }, function () { S.kisayol = { bilinmiyor: true }; })
      .then(function () { kisayolOzetCiz(); kisayolIpucuCiz(); });
  }
  // "ctrl+shift+t" → [Ctrl][Shift][T] tuş kapakları
  var TUS_AD = { ctrl: 'Ctrl', alt: 'Alt', shift: 'Shift', win: 'Win', space: 'Space', pageup: 'PgUp', pagedown: 'PgDn', insert: 'Ins', home: 'Home', end: 'End', pause: 'Pause', delete: 'Del' };
  function tusAdi(p) { return TUS_AD[p] || (p.length === 1 ? p.toUpperCase() : p.charAt(0).toUpperCase() + p.slice(1)); }
  function tusYazi(k) { return (k || '').split('+').filter(Boolean).map(tusAdi).join('+'); }
  function tusKapaklari(k) {
    var w = h('span', { class: 'tuslar', 'aria-label': tusYazi(k), role: 'img' });
    (k || '').split('+').filter(Boolean).forEach(function (p, i) {
      if (i) w.appendChild(h('span', { class: 'tus-arti', 'aria-hidden': 'true', text: '+' }));
      w.appendChild(h('kbd', { 'aria-hidden': 'true', text: tusAdi(p) }));
    });
    return w;
  }

  function panoKart(o) {
    var bas = h('h2', { id: 'pk-' + o.ad + '-b', text: o.baslik });
    var kart = h('section', { class: 'pk' + (o.sinif ? ' ' + o.sinif : ''), id: 'pk-' + o.ad, 'aria-labelledby': 'pk-' + o.ad + '-b' }, [
      h('div', { class: 'pk-bas' }, [
        h('span', { class: 'pk-ik', 'aria-hidden': 'true' }, ikon(o.ik)), bas,
        o.degistir ? h('button', { type: 'button', class: 'dugme ikincil kucuk pk-degistir', id: 'degistir-' + o.ad, 'aria-label': t('pano.degistir') + ': ' + o.baslik, text: o.degistirMetni || t('pano.degistir'), onclick: o.degistir }) : null
      ]),
      h('div', { class: 'pk-govde' }, o.govde)
    ]);
    return kart;
  }
  function anaEkran() {
    if (S.oyunDegis) { oyunEkrani('ana'); return; }
    if (S.kisayolEkrani) { kisayolEkrani(); return; }
    if (S.gelismisEkrani) { gelismisEkrani(); return; }
    ana.textContent = '';
    var a = S.ayarlar || {};

    // --- üst: büyük düğme + canlı durum + oyun + kısayol ipucu
    ekran.buyuk = h('button', { type: 'button', class: 'buyuk', id: 'baslat-durdur', onclick: baslatDurdur });
    ekran.led = h('span', { class: 'led', 'aria-hidden': 'true' });
    ekran.durum = h('span', { id: 'durum-metin' });
    ekran.ne = h('p', { class: 'pano-ne', id: 'ne-satir' });
    ekran.oyunAd = h('p', { class: 'pano-oyun', id: 'aktif-oyun-ad' });
    ekran.ipucu = h('p', { class: 'pano-kisayol', id: 'kisayol-ipucu', hidden: true });
    ekran.uyari = h('div', { class: 'ipucu uyari-banner', id: 'uyari-banner', role: 'status', hidden: true });
    var hero = h('div', { class: 'pano-hero', id: 'hero' }, [
      kopruKemer(),
      h('div', { class: 'pano-hero-sol' }, [
        h('p', { class: 'durum-satir', role: 'status' }, [ekran.led, ekran.durum]),
        ekran.oyunAd, ekran.ne, ekran.ipucu
      ]),
      h('div', { class: 'pano-hero-sag' }, ekran.buyuk)
    ]);
    ekran.hero = hero;

    // --- kartlar
    ekran.oyunAlt = h('p', { class: 'pk-alt', id: 'aktif-oyun-alt' });
    ekran.oyunDeger = h('p', { class: 'pk-deger', id: 'pk-oyun-ad' });
    ekran.bilgiDugme = h('button', { type: 'button', class: 'baglanti pk-ek', id: 'pano-bilgi', text: t('pano.bilgi'), onclick: function () { S.oyunDegis = true; S.bilgiBaslat = true; ciz(); } });
    var oyunK = panoKart({ ad: 'oyun', ik: 'oyun', baslik: t('pano.oyun'), degistir: function () { S.oyunDegis = true; ciz(); },
      govde: [ekran.oyunDeger, ekran.oyunAlt, ekran.bilgiDugme] });

    var kaynak = S.kaynaklar.filter(function (x) { return x.kod === (S.kaynak || a.kaynak); })[0];
    var cihaz = S.cihaz || a.cihaz;
    ekran.kareler = [];
    var goruntuK = panoKart({ ad: 'goruntu', ik: 'pc', baslik: t('pano.goruntu'), degistir: function () { asamaAc(1, 'ana'); }, sinif: 'pk-resimli',
      govde: [panoKucukResim('goruntu', false), h('div', { class: 'pk-metin' }, [
        h('p', { class: 'pk-deger', id: 'pk-goruntu-deger', text: kaynak ? kaynak.ad : (a.kaynak || t('pano.secilmedi')) }),
        h('p', { class: 'pk-alt', text: cihaz ? t('cihaz.' + cihaz) : t('pano.cihaz_yok') })])] });

    var m = motorBilgi(a.motor || S.motor);
    var motorAlt = !m ? '' : (m.kod === 'yerel' ? t('pano.motor_yerel') : t('pano.kalite', { ad: t('kalite.' + (a.kalite || 'en_iyi')) }));
    var motorK = panoKart({ ad: 'motor', ik: 'ceviri', baslik: t('pano.motor'), degistir: function () { asamaAc(3, 'ana'); },
      govde: [h('p', { class: 'pk-deger', id: 'pk-motor-deger', text: m ? m.ad : t('pano.secilmedi') }), h('p', { class: 'pk-alt', text: motorAlt })] });

    var gos = S.gosterim || a.gosterim || 'bilgisayar';
    ekran.gosAlt = h('p', { class: 'pk-alt', id: 'pk-gosterim-alt' });
    var gosK = panoKart({ ad: 'gosterim', ik: gos === 'bilgisayar' ? 'pc' : (gos === 'tv' ? 'tv' : 'web'), baslik: t('pano.gosterim'), degistir: function () { asamaAc(4, 'ana'); },
      govde: [h('p', { class: 'pk-deger', id: 'pk-gosterim-deger', text: t('pano.gosterim.' + gos) }), ekran.gosAlt] });

    var bolgeK = panoKart({ ad: 'bolge', ik: 'hedef', baslik: t('bolge.baslik'), degistir: function () { asamaAc(5, 'ana'); }, sinif: 'pk-resimli',
      govde: [panoKucukResim('bolge', true), h('div', { class: 'pk-metin' }, [
        h('p', { class: 'pk-deger', id: 'bolge-ozet', text: (a.bolgeler || []).length ? t('pano.bolge.n', { n: a.bolgeler.length }) : t('pano.bolge.oto') }),
        h('p', { class: 'pk-alt', text: ((a.bolgeler || []).length ? t('pano.bolge.k') : t('pano.bolge.oto.k')) })])] });

    ekran.kisayolOzet = h('div', { class: 'kisayol-ozet', id: 'kisayol-ozet' });
    var kisayolK = panoKart({ ad: 'kisayol', ik: 'klavye', baslik: t('kisayol.baslik'), degistir: function () { S.kisayolEkrani = true; ciz(); },
      govde: [ekran.kisayolOzet] });

    ekran.sonKutu = h('div', { id: 'son-liste', class: 'son-liste', tabindex: '0', role: 'region', 'aria-label': t('son.liste_aria') });
    ekran.onerKutu = h('div', { id: 'oneri-kart', class: 'oneri', hidden: true });
    var sonK = h('section', { class: 'pk pk-genis', id: 'son-kart', 'aria-labelledby': 'son-baslik' }, [
      h('div', { class: 'pk-bas' }, [h('span', { class: 'pk-ik', 'aria-hidden': 'true' }, ikon('liste')), h('h2', { id: 'son-baslik', text: t('son.baslik') }),
        h('span', { class: 'pk-not', text: t('pano.son.k') })]),
      ekran.sonKutu, ekran.onerKutu
    ]);

    ekran.erisim = h('div', { class: 'pk pk-genis erisim-kart', id: 'erisim-kart' });
    var dublaj = h('details', { class: 'pk pk-genis dublaj-ac', id: 'dublaj-kart' }, [
      h('summary', {}, [h('span', { class: 'pk-ik', 'aria-hidden': 'true' }, ikon('ses')),
        h('h2', { text: t('dublaj.baslik') }), h('span', { class: 'pk-not' }, [h('span', { id: 'dublaj-ozet', text: t('dublaj.' + ((a.dublaj && a.dublaj.motor) || 'kapali')) }), h('span', { id: 'dublaj-sure-ozet' })])]),
      dublajKarti()
    ]);

    ana.appendChild(h('section', { class: 'pano', id: 'pano' }, [
      h('h1', { class: 'gizli', text: t('ana.baslik') }),
      h('div', { id: 'guncelleme-alani' }), ekran.uyari, hero,
      h('div', { class: 'pano-izgara' }, [oyunK, goruntuK, motorK, gosK, bolgeK, kisayolK, sonK, ekran.erisim, dublaj]),
      h('div', { class: 'pano-alt' }, [
        h('button', { type: 'button', class: 'baglanti', id: 'gelismis-ac', text: t('gelismis.link'), onclick: function () { S.gelismisEkrani = true; ciz(); } })
      ])
    ]));
    oyunYukle().then(function () { oyunCiz(); });
    guncellemeCiz();
    oyunCiz(); gosterimCiz(); kisayolOzetCiz(); kisayolIpucuCiz(); sonCiz(); oneriCiz(); durumCiz(); erisimCiz(); listeYenile();
    kisayolYukle();
    if (!S.panoKare && !S.panoKareIstendi) panoKareAl();
  }

  // logodaki köprü kemeri: hero'nun üstünde ince bir çizgi; çalışırken yavaşça parlar
  function kopruKemer() {
    var s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    s.setAttribute('class', 'kemer'); s.setAttribute('viewBox', '0 0 1000 120'); s.setAttribute('preserveAspectRatio', 'none');
    s.setAttribute('aria-hidden', 'true'); s.setAttribute('focusable', 'false');
    s.innerHTML = '<defs><linearGradient id="kemer-g" x1="0" x2="1"><stop offset="0" stop-color="#2EC4B6" stop-opacity="0"/><stop offset=".5" stop-color="#6BE3D7"/><stop offset="1" stop-color="#2EC4B6" stop-opacity="0"/></linearGradient></defs>' +
      '<path d="M-10 118 Q500 -40 1010 118" fill="none" stroke="url(#kemer-g)" stroke-width="1.5" vector-effect="non-scaling-stroke"/>';
    return s;
  }

  // küçük canlı resim (görüntü kaynağı) ya da kutulu harita (çevrilecek yerler); /api/kare istekle yenilenir
  function panoKucukResim(tur, kutulu) {
    var img = h('img', { class: 'pk-kare-resim', alt: '', draggable: 'false', hidden: !S.panoKare });
    if (S.panoKare) img.src = S.panoKare;
    var bos = h('span', { class: 'pk-kare-bos', 'aria-hidden': 'true', hidden: !!S.panoKare }, ikon(kutulu ? 'hedef' : 'pc'));
    var kap = h('div', { class: 'pk-kare' + (kutulu ? ' kutulu' : ''), id: 'pk-kare-' + tur }, [img, bos]);
    if (kutulu) {
      var katman = h('div', { class: 'pk-kutular', 'aria-hidden': 'true' });
      ((S.ayarlar && S.ayarlar.bolgeler) || []).forEach(function (b) {
        var k = h('span', { class: 'pk-kutu t-' + (b.tur || 'diger') });
        k.style.left = b.x * 100 + '%'; k.style.top = b.y * 100 + '%'; k.style.width = b.g * 100 + '%'; k.style.height = b.y2 * 100 + '%';
        katman.appendChild(k);
      });
      kap.appendChild(katman);
    } else {
      img.alt = t('pano.kare_alt');
      kap.appendChild(h('button', { type: 'button', class: 'pk-kare-yenile', id: 'pano-kare-yenile', 'aria-label': t('goruntu.yenile'), title: t('goruntu.yenile'), onclick: function () { panoKareAl(); } }, ikon('yenile')));
    }
    ekran.kareler.push({ img: img, bos: bos });
    return kap;
  }
  function panoKareAl() {
    S.panoKareIstendi = true;
    var dugme = $('#pano-kare-yenile'); if (dugme) dugme.classList.add('donuyor');
    fetch('/api/kare?_=' + Date.now(), { cache: 'no-store' }).then(function (r) { if (!r.ok) throw new Error('kare'); return r.blob(); }).then(function (blob) {
      if (S.panoKare) { try { URL.revokeObjectURL(S.panoKare); } catch (e) { /* yok say */ } }
      S.panoKare = URL.createObjectURL(blob);
      (ekran.kareler || []).forEach(function (k) { k.img.src = S.panoKare; k.img.hidden = false; k.bos.hidden = true; });
    }).catch(function () { /* resim yoksa sakin yer tutucu kalır */ }).then(function () { var d = $('#pano-kare-yenile'); if (d) d.classList.remove('donuyor'); });
  }

  function oyunCiz() {
    if (!ekran.oyunAd || !document.body.contains(ekran.oyunAd)) return;
    var kod = S.ayarlar && S.ayarlar.aktif_oyun;
    var o = S.oyunlar.filter(function (x) { return x.kod === kod; })[0];
    var ad = o ? o.ad : (kod || '');
    ekran.oyunAd.textContent = ad || t('oyun.yok');
    ekran.oyunAd.classList.toggle('bos', !ad);
    ekran.oyunDeger.textContent = ad || t('oyun.yok');
    if (o && o.kayit_sayisi) sayacYaz(ekran.oyunAlt, o.kayit_sayisi, function (n) { return t('oyun.hatirla', { n: sayi(n) }); });
    else { ekran.oyunAlt.dataset.n = ''; ekran.oyunAlt.textContent = o ? hatirlaMetni(o) : t('oyun.yok.k'); }
    ekran.bilgiDugme.hidden = !kod;
    var dg = $('#degistir-oyun'); if (dg) { dg.textContent = kod ? t('pano.degistir') : t('oyun.sec'); dg.setAttribute('aria-label', (kod ? t('pano.degistir') : t('oyun.sec')) + ': ' + t('pano.oyun')); }
  }
  function gosterimCiz() {
    if (!ekran.gosAlt || !document.body.contains(ekran.gosAlt)) return;
    var gos = S.gosterim || (S.ayarlar && S.ayarlar.gosterim) || 'bilgisayar', d = S.durum || {};
    var p = [t('pano.yazi_boyu', { n: Math.round(ekranOlcek() * 100) }), t('pano.en_az', { n: saniye(enAzMs()) })];
    if (gos !== 'bilgisayar') p.push(t('durum.tv', { n: d.tv_sayisi || 0 }));
    var yazi = p.join(' · ');
    if (ekran.gosAlt.textContent !== yazi) ekran.gosAlt.textContent = yazi;
  }
  function kisayolIpucuCiz() {
    var el = ekran.ipucu; if (!el || !document.body.contains(el)) return;
    var k = kisayollar().baslat_durdur, ks = S.kisayol || {};
    var calisir = !!k && ks.destek !== false && !ks.bilinmiyor && !(ks.hata && ks.hata.baslat_durdur);
    el.hidden = !calisir;
    if (!calisir) return;
    el.textContent = '';
    el.appendChild(h('span', { text: t('pano.oyun_icinde') + ' ' }));
    el.appendChild(tusKapaklari(k));
    el.appendChild(h('span', { text: ' ' + t('pano.baslat_durdur_k') }));
  }
  function kisayolOzetCiz() {
    var el = ekran.kisayolOzet; if (!el || !document.body.contains(el)) return;
    var k = kisayollar(), ks = S.kisayol || {};
    el.textContent = '';
    var ul = h('ul', { class: 'kisayol-liste' });
    KISAYOL_ADLAR.forEach(function (ad) {
      var hata = ks.hata && ks.hata[ad], kayitli = ks.kayitli && ks.kayitli[ad];
      var durum = !k[ad] ? h('span', { class: 'ks-durum kapali', text: t('kisayol.kapali') })
        : (hata ? h('span', { class: 'ks-durum sorun', title: hata, text: t('kisayol.sorun') })
        : (kayitli ? h('span', { class: 'ks-durum iyi', text: t('kisayol.hazir') }) : null));
      ul.appendChild(h('li', { 'data-kisayol': ad }, [h('span', { class: 'ks-ad', text: t('kisayol.' + ad) }), k[ad] ? tusKapaklari(k[ad]) : null, durum]));
    });
    el.appendChild(ul);
    var sorunlu = KISAYOL_ADLAR.filter(function (ad) { return k[ad] && ks.hata && ks.hata[ad]; })[0];
    if (sorunlu) el.appendChild(h('p', { class: 'pk-uyari', id: 'kisayol-ozet-hata', text: ks.hata[sorunlu] }));
    else if (ks.destek === false) el.appendChild(h('p', { class: 'pk-alt', id: 'kisayol-destek-yok', text: t('kisayol.destek_yok') }));
  }

  // ---------- KISAYOL DÜZENLEYİCİ: kutuya tıkla, tuşlara bas ----------
  var KOD_TUS = { Space: 'space', PageUp: 'pageup', PageDown: 'pagedown', Insert: 'insert', Home: 'home', End: 'end', Pause: 'pause', Delete: 'delete' };
  function tusOku(e) {   // klavye düzeninden bağımsız: e.code (KeyT → t)
    var c = e.code || '', ana = null;
    if (/^Key[A-Z]$/.test(c)) ana = c.slice(3).toLowerCase();
    else if (/^Digit[0-9]$/.test(c)) ana = c.slice(5);
    else if (/^F([1-9]|1[0-2])$/.test(c)) ana = c.toLowerCase();
    else if (KOD_TUS[c]) ana = KOD_TUS[c];
    var p = [];
    if (e.ctrlKey) p.push('ctrl'); if (e.altKey) p.push('alt'); if (e.shiftKey) p.push('shift'); if (e.metaKey) p.push('win');
    return { ana: ana, ekler: p };
  }
  function kisayolEkrani() {
    ana.textContent = '';
    var deger = kisayollar(), ks = S.kisayol || {}, dinleyen = null;
    var satirlar = {};
    var kaydet = h('button', { type: 'button', class: 'dugme', id: 'kisayol-kaydet', text: t('kisayol.kaydet'), onclick: function () {
      if (cakisma()) return;
      kaydet.disabled = true;
      ayarKaydet({ kisayollar: Object.assign({}, deger) }).then(function () { return kisayolYukle(); }).then(function () {
        kaydet.disabled = false;
        var ks2 = S.kisayol || {};
        var sorun = KISAYOL_ADLAR.filter(function (ad) { return deger[ad] && ks2.hata && ks2.hata[ad]; });
        if (sorun.length) { ks = ks2; hepsiniCiz(); var b = $('#kisayol-' + sorun[0]); if (b) b.focus(); return; }   // başka program kullanıyorsa burada kal, göster
        toast(t('kisayol.kaydedildi')); S.kisayolEkrani = false; ciz();
      });
    } });
    var duyuru = h('p', { class: 'gizli', id: 'kisayol-duyuru', 'aria-live': 'polite' });
    function cakisma() {
      var gor = {}, var_ = false;
      KISAYOL_ADLAR.forEach(function (ad) { var k = deger[ad]; if (!k) return; (gor[k] = gor[k] || []).push(ad); });
      Object.keys(gor).forEach(function (k) { if (gor[k].length > 1) var_ = true; });
      return var_ ? gor : null;
    }
    function satirCiz(ad) {
      var s = satirlar[ad]; s.dugme.textContent = '';
      var dinle = dinleyen === ad;
      s.dugme.setAttribute('aria-pressed', String(dinle));
      s.dugme.classList.toggle('dinliyor', dinle);
      if (dinle) s.dugme.appendChild(h('span', { class: 'ks-bekle', text: s.onizleme ? tusYazi(s.onizleme) + '+…' : t('kisayol.bas') }));
      else if (deger[ad]) s.dugme.appendChild(tusKapaklari(deger[ad]));
      else s.dugme.appendChild(h('span', { class: 'ks-bos', text: t('kisayol.kapali') }));
      s.temizle.hidden = !deger[ad] || dinle;
      s.mesaj.textContent = ''; s.mesaj.className = 'ks-mesaj';
      var c = cakisma(), es = c && deger[ad] && c[deger[ad]] && c[deger[ad]].filter(function (x) { return x !== ad; });
      if (s.uyari) { s.mesaj.textContent = s.uyari; s.mesaj.classList.add('sorun'); }
      else if (es && es.length) { s.mesaj.textContent = t('kisayol.cakisma', { ad: t('kisayol.' + es[0]) }); s.mesaj.classList.add('sorun'); }
      else if (deger[ad] && ks.hata && ks.hata[ad] && deger[ad] === kisayollar()[ad]) { s.mesaj.textContent = ks.hata[ad]; s.mesaj.classList.add('sorun'); }
      else if (dinle) s.mesaj.textContent = t('kisayol.bas.k');
      s.satir.classList.toggle('sorunlu', s.mesaj.classList.contains('sorun'));
    }
    function hepsiniCiz() { KISAYOL_ADLAR.forEach(satirCiz); kaydet.disabled = !!cakisma(); }
    function dinlemeBitir() { var d = dinleyen; dinleyen = null; if (d) { satirlar[d].onizleme = null; satirCiz(d); } }
    var liste = h('ul', { class: 'kisayol-duzen', id: 'kisayol-duzen' });
    KISAYOL_ADLAR.forEach(function (ad) {
      var s = {};
      s.dugme = h('button', { type: 'button', class: 'ks-kayit', id: 'kisayol-' + ad, 'aria-labelledby': 'kisayol-' + ad + '-ad kisayol-' + ad, 'aria-describedby': 'kisayol-' + ad + '-mesaj kisayol-' + ad + '-yardim', onclick: function () {
        var once = dinleyen; dinlemeBitir();
        if (once !== ad) { dinleyen = ad; s.uyari = null; satirCiz(ad); }
      } });
      s.dugme.addEventListener('keydown', function (e) {
        if (dinleyen !== ad) return;
        if (e.key === 'Tab') { dinlemeBitir(); return; }
        e.preventDefault(); e.stopPropagation();
        if (e.key === 'Escape' && !e.ctrlKey && !e.altKey && !e.shiftKey) { s.uyari = null; dinlemeBitir(); return; }
        if ((e.key === 'Backspace' || e.key === 'Delete') && !e.ctrlKey && !e.altKey && !e.shiftKey && !e.metaKey) {
          deger[ad] = ''; s.uyari = null; dinlemeBitir(); hepsiniCiz(); duyuru.textContent = t('kisayol.temizlendi', { ad: t('kisayol.' + ad) }); return;
        }
        var r = tusOku(e);
        if (!r.ana) { s.onizleme = r.ekler.join('+') || null; satirCiz(ad); return; }   // yalnız Ctrl/Shift basılı: bekle
        if (!r.ekler.length && !/^f\d+$/.test(r.ana)) { s.uyari = t('kisayol.ek_gerekli'); s.onizleme = null; satirCiz(ad); return; }
        deger[ad] = r.ekler.concat([r.ana]).join('+'); s.uyari = null;
        dinlemeBitir(); hepsiniCiz();
        duyuru.textContent = t('kisayol.kaydedildi_tus', { ad: t('kisayol.' + ad), tus: tusYazi(deger[ad]) });
      });
      s.dugme.addEventListener('keyup', function (e) {
        if (dinleyen !== ad || !s.onizleme) return;
        var r = tusOku(e); s.onizleme = r.ekler.join('+') || null; satirCiz(ad);
      });
      s.dugme.addEventListener('blur', function () { if (dinleyen === ad) dinlemeBitir(); });
      s.temizle = h('button', { type: 'button', class: 'baglanti ks-temizle', id: 'kisayol-' + ad + '-temizle', 'aria-label': t('kisayol.temizle') + ': ' + t('kisayol.' + ad), text: t('kisayol.temizle'), onclick: function () {
        deger[ad] = ''; s.uyari = null; hepsiniCiz(); s.dugme.focus();
      } });
      s.mesaj = h('p', { class: 'ks-mesaj', id: 'kisayol-' + ad + '-mesaj', 'aria-live': 'polite' });
      s.satir = h('li', { class: 'ks-satir', 'data-kisayol': ad }, [
        h('div', { class: 'ks-ac' }, [h('b', { id: 'kisayol-' + ad + '-ad', text: t('kisayol.' + ad) }), h('span', { class: 'sessiz', text: t('kisayol.' + ad + '.k') }), h('span', { class: 'gizli', id: 'kisayol-' + ad + '-yardim', text: t('kisayol.kayit_aria', { ad: t('kisayol.' + ad) }) })]),
        h('div', { class: 'ks-sag' }, [s.dugme, s.temizle]), s.mesaj
      ]);
      satirlar[ad] = s;
      liste.appendChild(s.satir);
    });
    var destekNot = (ks.destek === false) ? h('div', { class: 'not', id: 'kisayol-destek-yok', text: t('kisayol.destek_yok') }) : null;
    ana.appendChild(h('section', { class: 'odakli kisayol-ekrani', id: 'kisayol-ekrani' }, [
      anaDonusLink(function () { S.kisayolEkrani = false; ciz(); }),
      h('h1', { text: t('kisayol.baslik') }),
      h('p', { class: 'alt-baslik', text: t('kisayol.alt') }),
      destekNot,
      h('div', { class: 'kart' }, [liste, h('div', { class: 'satir ks-varsayilan' }, h('button', { type: 'button', class: 'baglanti', id: 'kisayol-varsayilan', text: t('kisayol.varsayilan'), onclick: function () {
        deger = Object.assign({}, KISAYOL_VARSAYILAN); KISAYOL_ADLAR.forEach(function (ad) { satirlar[ad].uyari = null; }); hepsiniCiz();
      } }))]),
      duyuru,
      h('div', { class: 'alt-gezinme' }, [
        h('button', { type: 'button', class: 'dugme ikincil', id: 'kisayol-vazgec', text: t('asama.vazgec'), onclick: function () { S.kisayolEkrani = false; ciz(); } }),
        kaydet])
    ]));
    hepsiniCiz();
  }

  // sayı yukarı sayarak gelir (yalnız görsel; ekran okuyucu son değeri bir kez duyar)
  function sayacYaz(el, hedef, bicim) {
    var onceki = Number(el.dataset.n || 0);
    el.dataset.n = String(hedef);
    if (onceki === hedef && el.textContent) { el.textContent = bicim(hedef); return; }
    el.setAttribute('aria-label', bicim(hedef));
    if (hareketAz() || !window.requestAnimationFrame) { el.textContent = bicim(hedef); el.removeAttribute('aria-label'); return; }
    var bas = null, sure = 900;
    (function adim(z) {
      if (el.dataset.n !== String(hedef)) return;
      if (bas === null) bas = z;
      var k = Math.min(1, (z - bas) / sure), e = 1 - Math.pow(1 - k, 3);
      el.textContent = bicim(Math.round(onceki + (hedef - onceki) * e));
      if (k < 1) requestAnimationFrame(adim); else el.removeAttribute('aria-label');
    })(performance.now());
  }

  function izinSor() {
    var iz = S.ayarlar && S.ayarlar.hafiza_izni;
    if (iz === true || iz === false) return Promise.resolve(true);
    return pencere(t('izin.baslik'), t('izin.govde'), [
      { ad: t('izin.evet'), deger: true, id: 'izin-evet' },
      { ad: t('izin.hayir'), deger: false, sinif: 'ikincil', id: 'izin-hayir' }
    ]).then(function (v) {
      if (v === null) return false;
      return ayarKaydet({ hafiza_izni: v }).then(function () { gelismisYenile(); return true; });
    });
  }
  function baslatDurdur() {
    var calisiyor = S.durum && S.durum.calisiyor;
    if (calisiyor) { return api('POST', '/api/durdur', {}).then(durumYukle).catch(hataGoster); }
    return izinSor().then(function (ok) {
      if (!ok) return;
      return api('POST', '/api/baslat', {}).then(durumYukle).then(listeYenile);
    }).catch(hataGoster);
  }

  // ---------- son çeviriler + öneriler ----------
  function listeYenile() {
    if (!S.kurulumBitti || !ekran.sonKutu || !document.body.contains(ekran.sonKutu)) return;
    api('GET', '/api/son-ceviriler').then(function (l) { if (!S.duzeltAcik) { S.sonCeviriler = l || []; sonCiz(); } }).catch(function () {});
    api('GET', '/api/oneriler').then(function (l) { S.oneriler = l || []; oneriCiz(); }).catch(function () {});
  }
  function sonCiz() {
    if (!ekran.sonKutu || !document.body.contains(ekran.sonKutu)) return;
    ekran.sonKutu.textContent = '';
    var toplam = S.sonCeviriler.length, sinirN = 5;   // kompakt: en çok 5 satır, kart kendi içinde kayar
    if (!toplam) { ekran.sonKutu.appendChild(h('p', { class: 'bos-durum', id: 'son-bos', text: t('son.bos') })); return; }
    S.sonCeviriler.slice(0, sinirN).forEach(function (c) {   // sunucu en yeniyi başta verir
      var satir = h('div', { class: 'ceviri-satir', 'data-id': c.id });
      function normal() {
        satir.textContent = '';
        satir.appendChild(h('div', { class: 'metin' }, [h('div', { class: 'asil', text: c.asil }), h('div', { class: 'ceviri' }, [c.ceviri, c.kaynak === 'kullanici' ? h('span', { class: 'rozet sari senin', text: t('son.senin') }) : null])]));
        satir.appendChild(h('button', { type: 'button', class: 'dugme ikincil kucuk duzelt', text: t('duzelt.dugme'), onclick: duzenle }));
      }
      function duzenle() {
        S.duzeltAcik = true; satir.textContent = '';
        var inp = h('input', { type: 'text', class: 'duzelt-girdi', value: c.ceviri, 'aria-label': t('duzelt.etiket') });
        var kapat = function () { S.duzeltAcik = false; normal(); };
        satir.appendChild(h('div', { class: 'metin' }, [h('div', { class: 'asil', text: c.asil }), inp,
          h('div', { class: 'satir', style: 'margin-top:10px' }, [
            h('button', { type: 'button', class: 'dugme kucuk duzelt-kaydet', text: t('duzelt.kaydet'), onclick: function () {
              var yeniMetin = inp.value.trim(); if (!yeniMetin) return;
              api('POST', '/api/duzelt', { asil: c.asil, ceviri: yeniMetin }).then(function () {
                c.ceviri = yeniMetin; c.kaynak = 'kullanici'; S.duzeltAcik = false; normal(); toast(t('duzelt.tamam'));
              }).catch(hataGoster);
            } }),
            h('button', { type: 'button', class: 'dugme ikincil kucuk', text: t('duzelt.vazgec'), onclick: kapat })
          ])]));
        inp.focus();
      }
      normal(); ekran.sonKutu.appendChild(satir);
    });
  }
  function oneriCiz() {
    if (!ekran.onerKutu || !document.body.contains(ekran.onerKutu)) return;
    ekran.onerKutu.hidden = !S.oneriler.length;
    ekran.onerKutu.textContent = '';
    if (!S.oneriler.length) return;
    ekran.onerKutu.appendChild(h('h3', { text: t('oneri.baslik') }));
    ekran.onerKutu.appendChild(ne('oneri.ne', 'isi'));
    S.oneriler.forEach(function (o) {
      function karar(kabul) {
        api('POST', '/api/oneriler', { asil: o.asil, kabul: kabul }).then(function () {
          S.oneriler = S.oneriler.filter(function (x) { return x.asil !== o.asil; }); oneriCiz();
          toast(kabul ? t('oneri.eklendi') : t('oneri.atildi'));
        }).catch(hataGoster);
      }
      ekran.onerKutu.appendChild(h('div', { class: 'ceviri-satir', 'data-oneri': o.asil }, [
        h('div', { class: 'metin' }, [h('div', { class: 'ceviri', text: o.asil + (o.ceviri && o.ceviri !== o.asil ? ' → ' + o.ceviri : '') })]),
        h('div', { class: 'satir' }, [
          h('button', { type: 'button', class: 'dugme kucuk kabul', text: '✓', 'aria-label': t('oneri.kabul'), title: t('oneri.kabul'), onclick: function () { karar(true); } }),
          h('button', { type: 'button', class: 'dugme ikincil kucuk red', text: '✕', 'aria-label': t('oneri.red'), title: t('oneri.red'), onclick: function () { karar(false); } })
        ])
      ]));
    });
  }


  // ---------- GÜNCELLEME (tek tuş) ----------
  var guncelZaman = null;
  function guncellemeYukle() {
    return api('GET', '/api/guncelleme').then(function (d) {
      var onceki = S.guncelleme;
      S.guncelleme = d;
      // program yeniden başlayıp geri geldiyse sayfayı yenile
      if (onceki && onceki.asama === 'baslatiliyor' && !d.var) { location.reload(); return; }
      guncellemeCiz();
    }).catch(function () {});
  }
  function guncellemeKur() {
    api('POST', '/api/guncelleme/kur').then(function (d) { S.guncelleme = d; guncellemeCiz(); guncellemeTakip(); }).catch(hataGoster);
  }
  function guncellemeTakip() {
    clearTimeout(guncelZaman);
    guncelZaman = setTimeout(function () {
      guncellemeYukle().then(function () {
        var g = S.guncelleme;
        if (g && (g.asama === 'indiriliyor' || g.asama === 'dogrulaniyor' || g.asama === 'baslatiliyor')) guncellemeTakip();
      });
    }, 800);
  }
  // "## 0.1.3 — Başlık\n- **Kalın** madde" -> ["Kalın madde", ...] (düz yazı; HTML olarak basılmaz)
  function guncellemeNotlari(metin) {
    return String(metin || '').split('\n').map(function (x) { return x.trim(); })
      .filter(function (x) { return x && x.indexOf('#') !== 0; })
      .map(function (x) { return x.replace(/^[-*]\s+/, '').replace(/\*\*|`|__/g, '').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1'); })
      .slice(0, 12);
  }
  function guncellemeBar(g) {
    var kutu = h('div', { class: 'guncelleme-bar', id: 'guncelleme-bar', role: 'status' });
    var a = g.asama;
    if (a === 'indiriliyor' || a === 'dogrulaniyor' || a === 'baslatiliyor') {
      var yuzde = a === 'baslatiliyor' ? 100 : (g.ilerleme || 0);
      var metin = a === 'baslatiliyor' ? t('guncelleme.yeniden') : (a === 'dogrulaniyor' ? t('guncelleme.dogrulaniyor') : t('guncelleme.indiriliyor', { n: yuzde }));
      kutu.appendChild(h('span', { class: 'metin', id: 'guncelleme-metin', text: metin }));
      kutu.appendChild(h('div', { class: 'ilerleme', role: 'progressbar', 'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-valuenow': String(yuzde) },
        h('i', { style: 'width:' + yuzde + '%' })));
      return kutu;
    }
    kutu.appendChild(h('span', { class: 'metin', id: 'guncelleme-metin',
      text: (a === 'hata' && g.mesaj) ? g.mesaj : (g.yalniz_degisenler && g.boyut_bayt
        ? t('guncelleme.hazir_kucuk', { surum: g.surum, boyut: g.boyut_bayt < 1048576 ? Math.max(1, Math.round(g.boyut_bayt / 1024)) + ' KB' : (g.boyut_bayt / 1048576).toFixed(1) + ' MB' })
        : t('guncelleme.hazir', { surum: g.surum })) + (a === 'hata' ? '' : ' ' + t('guncelleme.soru')) }));
    kutu.appendChild(h('button', { type: 'button', class: 'dugme kucuk', id: 'guncelle-dugme', onclick: guncellemeKur,
      text: a === 'hata' ? t('guncelleme.tekrar') : t('guncelleme.dugme') }));
    if (a !== 'hata') {
      kutu.appendChild(h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'guncelle-sonra', text: t('guncelleme.sonra'),
        onclick: function () { S.guncellemeErtelenen = g.surum; guncellemeCiz(); } }));
    }
    var notlar = guncellemeNotlari(g.notlar);
    if (notlar.length) {
      var liste = h('ul', { class: 'guncelleme-notlar' });
      notlar.forEach(function (n) { liste.appendChild(h('li', { text: n })); });
      kutu.appendChild(h('details', { class: 'guncelleme-yenilikler', id: 'guncelleme-yenilikler', open: 'open' },
        [h('summary', { text: t('guncelleme.yenilikler') }), liste]));
    }
    return kutu;
  }
  function guncellemeCiz() {
    var kap = $('#guncelleme-alani');
    var g = S.guncelleme;
    if (kap) {
      kap.textContent = '';
      if (g && g.var && !(S.guncellemeErtelenen === g.surum && !g.asama)) kap.appendChild(guncellemeBar(g));
    }
    var d = $('#guncelleme-durum');
    if (d && g) {
      d.textContent = '';
      var yazi = g.neden === 'desteklenmiyor' ? g.mesaj
        : (g.denetim_hatasi ? g.denetim_hatasi
        : (g.var ? t('guncelleme.var', { surum: g.surum }) : (g.son_denetim ? t('guncelleme.guncel', { surum: g.mevcut }) : '')));
      d.appendChild(document.createTextNode(yazi || ''));
      if (g.neden === 'desteklenmiyor' && g.baglanti) {
        d.appendChild(document.createTextNode(' '));
        d.appendChild(h('a', { href: g.baglanti, target: '_blank', rel: 'noopener', text: t('guncelleme.sayfa') }));
      }
    }
    var dn = $('#guncelleme-denetle');
    if (dn && g) dn.hidden = g.neden === 'desteklenmiyor';
  }
  function guncellemeBolumu() {
    var a = S.ayarlar || {};
    var durum = h('p', { class: 'sessiz', id: 'guncelleme-durum', 'aria-live': 'polite' });
    var dugme = h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'guncelleme-denetle', text: t('guncelleme.denetle'), onclick: function () {
      durum.textContent = t('guncelleme.denetleniyor');
      api('POST', '/api/guncelleme/denetle').then(function (d) { S.guncelleme = d; guncellemeCiz(); }).catch(hataGoster);
    } });
    var b = bolum(t('guncelleme.baslik'), 'guncelleme.ne', [
      anahtar(t('ayar.guncelleme'), t('ayar.guncelleme.k'), a.guncelleme_denetle !== false, function (v) { ayarKaydet({ guncelleme_denetle: v }); }, 'guncelleme-denetle-ayar'),
      h('div', { class: 'satir', style: 'margin-top:10px' }, dugme), durum
    ]);
    setTimeout(guncellemeCiz, 0);
    return b;
  }

  // ---------- TV'YE TEK TUŞLA KUR (LG) ----------
  var TV_ASAMALAR = ['anahtar', 'baglaniyor', 'yukleniyor', 'kuruluyor', 'bitti'];
  function tvKarti() {
    var ip = h('input', { type: 'text', id: 'tv-ip', inputmode: 'decimal', autocomplete: 'off', spellcheck: 'false',
      placeholder: t('tv.kart.ip_yer'), value: ls('tv_ip') || '' });
    var kod = h('input', { type: 'text', id: 'tv-parola', autocomplete: 'off', autocapitalize: 'characters', spellcheck: 'false',
      maxlength: '32', placeholder: t('tv.kart.parola_yer') });
    var asamalar = h('ol', { class: 'tv-asamalar', id: 'tv-asamalar', hidden: true }, TV_ASAMALAR.map(function (a) {
      return h('li', { 'data-asama': a, text: t('tv.kart.asama.' + a) });
    }));
    var sonuc = h('div', { id: 'tv-sonuc', 'aria-live': 'polite' });
    var kurDugme = h('button', { type: 'button', class: 'dugme', id: 'tv-kur', text: t('tv.kart.kur'), onclick: function () { kur('asil'); } });
    var denemeDugme = h('button', { type: 'button', class: 'dugme ikincil', id: 'tv-deneme', text: t('tv.kart.deneme'), onclick: function () { kur('deneme'); } });
    var kart = h('div', { class: 'kart', id: 'tv-kart' }, [
      h('h2', { text: t('tv.kart.baslik') }), ne('tv.kart.ne', 'isi'),
      adimlar('tv.kart.adimlar'),
      h('label', { class: 'etiket', for: 'tv-ip', text: t('tv.kart.ip') }), ip,
      h('label', { class: 'etiket', for: 'tv-parola', text: t('tv.kart.parola') }), kod,
      h('div', { class: 'satir', style: 'margin-top:16px' }, [kurDugme, denemeDugme]),
      asamalar, sonuc
    ]);
    var zaman = null, sonAsama = 0, sonPaket = 'asil';

    function mesgul(m) { kurDugme.disabled = m; denemeDugme.disabled = m; }
    function hataKutu(mesaj, ayrinti) {
      var k = h('div', { class: 'sonuc kotu', id: 'tv-hata' }, [h('div', { id: 'tv-hata-mesaj', text: mesaj })]);
      if (ayrinti) {
        k.appendChild(h('details', { id: 'tv-ayrinti-kap' }, [
          h('summary', { text: t('tv.kart.ayrinti') }),
          h('p', { class: 'sessiz', text: t('tv.kart.ayrinti_not') }),
          h('pre', { class: 'ayrinti', id: 'tv-ayrinti', text: ayrinti })
        ]));
      }
      if (sonPaket === 'asil') {
        k.appendChild(h('div', { class: 'satir', style: 'margin-top:12px' },
          h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'tv-acgsiz', text: t('tv.kart.acgsiz'), onclick: function () { kur('acgsiz'); } })));
      }
      return k;
    }
    function goster(d) {
      var i = TV_ASAMALAR.indexOf(d.asama);
      if (i >= 0) sonAsama = i;
      asamalar.hidden = d.asama === 'bosta';
      [].forEach.call(asamalar.children, function (li, n) {
        var bitti = d.asama === 'bitti' ? true : n < sonAsama;
        li.className = bitti ? 'bitti' : (n === sonAsama && d.asama !== 'hata' ? 'simdi' : '');
      });
      sonuc.textContent = '';
      if (d.asama === 'hata') { sonuc.appendChild(hataKutu(d.mesaj, d.ayrinti)); mesgul(false); }
      else if (d.asama === 'bitti') { sonuc.appendChild(h('div', { class: 'sonuc', id: 'tv-bitti', text: d.mesaj })); kod.value = ''; mesgul(false); }
      else if (d.asama !== 'bosta') { sonuc.appendChild(h('p', { class: 'sessiz', id: 'tv-mesaj', text: d.mesaj })); }
    }
    function takip() {
      clearTimeout(zaman);
      zaman = setTimeout(function () {
        if (!document.body.contains(kart)) return;
        api('GET', '/api/tv/lg/durum').then(function (d) {
          goster(d);
          if (d.asama !== 'bitti' && d.asama !== 'hata') takip();
        }).catch(function (e) { mesgul(false); hataGoster(e); });
      }, 600);
    }
    function kur(paket) {
      var a = ip.value.trim(), p = kod.value.trim();
      if (!a || !p) { sonuc.textContent = ''; sonuc.appendChild(h('div', { class: 'sonuc kotu', id: 'tv-hata', text: t('tv.kart.eksik') })); return; }
      ls('tv_ip', a);          // yalnız IP hatırlanır; kod hiçbir yere kaydedilmez
      sonPaket = paket; sonAsama = 0; mesgul(true);
      api('POST', '/api/tv/lg/kur', { ip: a, parola: p, paket: paket }).then(function (d) { goster(d); takip(); })
        .catch(function (e) { mesgul(false); sonuc.textContent = ''; sonuc.appendChild(hataKutu(e.mesaj || e.message, '')); });
    }
    return kart;
  }

  // ---------- GELİŞMİŞ AYARLAR (tek bağlantı arkasında) ----------
  function gelismisYenile() { if (S.gelismisEkrani && S.kurulumBitti) ciz(); }
  function anahtar(baslik, kucuk, deger, degisti, id) {
    var inp = h('input', { type: 'checkbox', id: id, onchange: function () { degisti(inp.checked); } });
    inp.checked = !!deger;
    return h('label', { class: 'anahtar' }, [h('span', { class: 'ac' }, [baslik, kucuk ? h('small', { text: kucuk }) : null]), h('span', { class: 'sw' }, [inp, h('i')])]);
  }
  function bolum(baslik, isi, kids) {
    return h('div', { class: 'bolum' }, [h('h2', { class: 'bolum-baslik', text: baslik }), isi ? ne(isi, 'isi') : null].concat(kids));
  }
  function hafizaBolumu() {
    var a = S.ayarlar || {}; var kod = a.aktif_oyun;
    var sil = h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'hafiza-sil', disabled: !kod, text: t('hafiza.sil'), onclick: function () {
      pencere(t('hafiza.sil_baslik', { ad: oyunAdi(kod) || kod }), t('hafiza.sil_govde'), [
        { ad: t('hafiza.sil_evet'), deger: true, sinif: 'kirmizi', id: 'sil-evet' },
        { ad: t('hafiza.sil_hayir'), deger: false, sinif: 'ikincil', id: 'sil-hayir' }
      ]).then(function (v) {
        if (!v) return;
        return api('DELETE', '/api/oyun/' + encodeURIComponent(kod) + '/hafiza').then(function () {
          return oyunYukle();
        }).then(function () { oyunCiz(); toast(t('hafiza.silindi')); });
      }).catch(hataGoster);
    } });
    return bolum(t('hafiza.baslik'), 'hafiza.ne', [
      anahtar(t('hafiza.ac'), t('hafiza.ac.k'), a.hafiza_izni === true, function (v) { ayarKaydet({ hafiza_izni: v }); }, 'hafiza-izni'),
      h('div', { class: 'satir', style: 'margin:10px 0 18px' }, [sil]),
      h('h3', { class: 'ara-baslik', text: t('paylas.baslik') }),
      h('p', { class: 'sessiz', text: t('paylas.aciklama') }),
      kod ? h('a', { class: 'dugme ikincil kucuk', id: 'paket-paylas', href: '/api/paket/' + encodeURIComponent(kod), download: kod + '.akpaket', text: t('paylas.dugme') })
          : h('p', { class: 'sessiz', text: t('oyun.yok.k') })
    ]);
  }
  // Gelişmiş ayarlar: ayrı, odaklı bir ekran. Ana ekrandaki kartlarda olanlar (motor, kalite, ekran ölçeği, TV kurulumu) burada TEKRAR edilmez.
  function gelismisEkrani() {
    var a = S.ayarlar || {}; var g = a.gorunum || {};
    ana.textContent = '';
    var sesAcik = h('div', { class: 'not', id: 'ses-not', hidden: !a.ses_cevir, text: t('ayar.ses.onay') });
    var ne1 = bolum(t('ayar.bolum'), 'ayar.ne', [
      anahtar(t('ayar.ekran'), t('ayar.ekran.k'), a.ekrani_cevir, function (v) { ayarKaydet({ ekrani_cevir: v }); }, 'ekrani-cevir'),
      anahtar(t('ayar.aciklama'), t('ayar.aciklama.k'), a.kisa_aciklama, function (v) { ayarKaydet({ kisa_aciklama: v }); }, 'kisa-aciklama'),
      anahtar(t('ayar.ses'), t('ayar.ses.k'), a.ses_cevir, function (v) { sesAcik.hidden = !v; ayarKaydet({ ses_cevir: v }); }, 'ses-cevir'),
      sesAcik
    ]);
    var dilSec = h('select', { id: 'hedef-dil', onchange: function () { ayarKaydet({ hedef_dil: dilSec.value }); } },
      HEDEF_DILLER.map(function (k) { var o = h('option', { value: k, text: t('hd.' + k) }); if (a.hedef_dil === k) o.selected = true; return o; }));
    var dilB = bolum(t('ayar.hedef'), null, [h('label', { class: 'gizli', for: 'hedef-dil', text: t('ayar.hedef') }), dilSec]);

    function gorunumAyar(alan, deger) { var p = {}; p[alan] = deger; ayarKaydet({ gorunum: p }); }
    var boyut = h('input', { type: 'range', min: 24, max: 80, step: 2, id: 'yazi-boyutu', value: g.yazi_boyutu || 44 });
    var koyu = h('input', { type: 'range', min: 0, max: 100, step: 5, id: 'arka-plan', value: Math.round((g.arka_plan == null ? 0.55 : g.arka_plan) * 100) });
    // §16.1: "Orijinal yazının üstünde" (örtü, varsayılan) ya da eski çubuk: altta / üstte
    var konum = h('select', { id: 'konum', onchange: function () {
      ayarKaydet({ gorunum: konum.value === 'ustune' ? { yerlesim: 'ustune' } : { yerlesim: 'cubuk', konum: konum.value } });
    } }, [
      h('option', { value: 'ustune', text: t('gorunum.ustune') }),
      h('option', { value: 'alt', text: t('gorunum.alt') }), h('option', { value: 'ust', text: t('gorunum.ust') })]);
    konum.value = g.yerlesim === 'cubuk' ? (g.konum || 'alt') : 'ustune';
    ekran.yazi = h('div', { class: 'alt-yazi', id: 'son-yazi' });
    ekran.onizleme = h('div', { class: 'onizleme' }, ekran.yazi);
    function onizlemeGuncelle() {
      ekran.yazi.style.fontSize = Math.max(12, boyut.value * 0.35) + 'px';
      ekran.yazi.style.background = 'rgba(0,0,0,' + (koyu.value / 100) + ')';
      ekran.onizleme.style.alignItems = konum.value === 'ust' ? 'flex-start' : 'flex-end';
    }
    var zaman;
    function gecik(f) { clearTimeout(zaman); zaman = setTimeout(f, 300); }
    boyut.addEventListener('input', function () { onizlemeGuncelle(); gecik(function () { gorunumAyar('yazi_boyutu', Number(boyut.value)); }); });
    koyu.addEventListener('input', function () { onizlemeGuncelle(); gecik(function () { gorunumAyar('arka_plan', koyu.value / 100); }); });
    konum.addEventListener('change', onizlemeGuncelle);
    var gorB = bolum(t('gorunum.baslik'), null, [
      h('div', { class: 'onizleme-kutu' }, [h('div', { class: 'etiket-kucuk', text: t('on.baslik') }), ekran.onizleme]),
      h('label', { class: 'etiket', for: 'yazi-boyutu', text: t('gorunum.boyut') }), boyut,
      h('div', { class: 'iki' }, [
        h('div', {}, [h('label', { class: 'etiket', for: 'konum', text: t('gorunum.konum') }), konum]),
        h('div', {}, [h('label', { class: 'etiket', for: 'arka-plan', text: t('gorunum.koyuluk') }), koyu])
      ])
    ]);
    onizlemeGuncelle();
    var kur = bolum(t('kurulum.yeniden'), null, [h('p', { class: 'sessiz', text: t('kurulum.yeniden.k') }),
      h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'yeniden-kur', text: t('kurulum.yeniden'), onclick: function () {
        S.gelismisEkrani = false; S.kurulumBitti = false; S.adim = 1; S.asama = {}; S.okunan = null; ls('asamalar', '{}'); ls('kurulum', '0'); ciz();
      } })]);
    function don() { S.gelismisEkrani = false; ciz(); }
    ana.appendChild(h('section', { class: 'odakli gelismis-ekrani', id: 'gelismis' }, [
      anaDonusLink(don),
      h('h1', { text: t('gelismis.link') }),
      h('p', { class: 'alt-baslik', text: t('gelismis.uyari') }),
      hafizaBolumu(), ne1, dilB, gorB, sozlukBolumu(), guncellemeBolumu(), motorBolumu(), reklamBolumu(), kur,
      h('div', { class: 'alt-gezinme' }, [h('span'), h('button', { type: 'button', class: 'dugme', id: 'gelismis-don', text: t('asama.ana_don'), onclick: don })])
    ]));
    durumCiz();
  }

  // §17.7: reklam izni (geri alınabilir) + VAST adresi (program sahibi için)
  function reklamBolumu() {
    var a = S.ayarlar || {}, e = a.erisim || {};
    var adres = h('input', { type: 'url', id: 'vast-adresi', autocomplete: 'off', spellcheck: 'false', value: e.vast_adresi || '', placeholder: 'https://…', 'aria-label': t('reklam.vast') });
    var not = h('p', { class: 'sessiz', id: 'vast-not', role: 'status' });
    return bolum(t('reklam.bolum'), null, [
      anahtar(t('reklam.izin_ayar'), t('reklam.izin_ayar.k'), e.reklam_izni === true, function (v) {
        ayarKaydet({ erisim: Object.assign({}, (S.ayarlar || {}).erisim, { reklam_izni: v }) }).then(erisimYukle);
      }, 'reklam-izni'),
      h('label', { class: 'etiket', for: 'vast-adresi', text: t('reklam.vast') }),
      h('div', { class: 'satir' }, [adres, h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'vast-kaydet', text: t('erisim.kaydet'), onclick: function () {
        var v = adres.value.trim();
        if (v && v.indexOf('https://') !== 0) { not.textContent = t('reklam.vast_hata'); return; }
        ayarKaydet({ erisim: Object.assign({}, (S.ayarlar || {}).erisim, { vast_adresi: v }) }).then(function () { not.textContent = t('reklam.vast_tamam'); });
      } })]),
      h('p', { class: 'sessiz', text: t('reklam.vast.k') }), not
    ]);
  }

  function sozlukBolumu() {
    var govde = h('tbody'); var oyun = h('input', { type: 'text', id: 'sozluk-oyun', placeholder: t('sozluk.oyun_yer') });
    var durumYazi = h('span', { class: 'sessiz', id: 'sozluk-durum' });
    function satir(asil, ceviri) {
      var tr = h('tr', {}, [
        h('td', {}, h('input', { type: 'text', class: 'sz-asil', value: asil || '', placeholder: t('sozluk.asil'), 'aria-label': t('sozluk.asil') })),
        h('td', {}, h('input', { type: 'text', class: 'sz-ceviri', value: ceviri || '', placeholder: t('sozluk.ceviri'), 'aria-label': t('sozluk.ceviri') })),
        h('td', {}, h('button', { type: 'button', class: 'x', 'aria-label': t('sozluk.sil'), text: '✕', onclick: function () { tr.remove(); } }))
      ]);
      govde.appendChild(tr);
    }
    api('GET', '/api/sozluk').then(function (s) {
      oyun.value = (s && s.oyun && s.oyun !== 'varsayilan') ? s.oyun : '';
      ((s && s.terimler) || []).forEach(function (x) { satir(x.asil, x.ceviri); });
      if (!govde.children.length) satir();
    }).catch(function () { satir(); });
    return bolum(t('sozluk.baslik'), 'sozluk.ne', [
      h('p', { class: 'sessiz', text: t('sozluk.alt') }),
      h('label', { class: 'etiket', for: 'sozluk-oyun', text: t('sozluk.oyun') }), oyun,
      h('table', { class: 'sozluk' }, govde),
      h('div', { class: 'satir', style: 'margin-top:10px' }, [
        h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'sozluk-ekle', text: t('sozluk.ekle'), onclick: function () { satir(); } }),
        h('button', { type: 'button', class: 'dugme kucuk', id: 'sozluk-kaydet', text: t('sozluk.kaydet'), onclick: function () {
          var terimler = [].map.call(govde.querySelectorAll('tr'), function (tr) {
            return { asil: $('.sz-asil', tr).value.trim(), ceviri: $('.sz-ceviri', tr).value.trim() };
          }).filter(function (x) { return x.asil; });
          api('POST', '/api/sozluk', { oyun: oyun.value.trim() || 'varsayilan', terimler: terimler }).then(function () {
            durumYazi.textContent = t('sozluk.kaydedildi');
          }).catch(hataGoster);
        } }), durumYazi
      ])
    ]);
  }

  function motorBolumu() {
    var a = S.ayarlar || {}; var m = a.modeller || {};
    var kapi = h('input', { type: 'number', id: 'kapi', min: 1024, max: 65535, value: a.kapi || 8642 });
    var uygun = S.motorlar.filter(function (x) { return x.kod !== 'sahte'; });
    var yedek = h('select', { id: 'yedek-motor' }, [h('option', { value: '', text: t('gelismis.yedek_yok') })].concat(
      uygun.map(function (x) { var o = h('option', { value: x.kod, text: x.ad }); if (a.yedek_motor === x.kod) o.selected = true; return o; })));
    var modelGirdi = {};
    var modelAlanlari = ['claude', 'gemini', 'deepseek'].map(function (k) {
      modelGirdi[k] = h('input', { type: 'text', id: 'model-' + k, value: m[k] || '' });
      return h('div', {}, [h('label', { class: 'etiket', for: 'model-' + k, text: t('gelismis.model', { ad: k }) }), modelGirdi[k]]);
    });
    var tamam = h('span', { class: 'sessiz', id: 'gelismis-durum' });
    return bolum(t('gelismis.baslik'), null, [
      h('div', { class: 'iki' }, [
        h('div', {}, [h('label', { class: 'etiket', for: 'yedek-motor', text: t('gelismis.yedek') }), yedek]),
        h('div', {}, [h('label', { class: 'etiket', for: 'kapi', text: t('gelismis.kapi') }), kapi, h('small', { class: 'sessiz', text: t('gelismis.kapi_not') })])
      ]),
      h('div', { class: 'iki' }, modelAlanlari),
      h('div', { class: 'satir', style: 'margin-top:14px' }, [
        h('button', { type: 'button', class: 'dugme kucuk', id: 'gelismis-kaydet', text: t('gelismis.kaydet'), onclick: function () {
          var mm = {}; Object.keys(modelGirdi).forEach(function (k) { if (modelGirdi[k].value.trim()) mm[k] = modelGirdi[k].value.trim(); });
          ayarKaydet({ yedek_motor: yedek.value || null, kapi: Number(kapi.value) || 8642, modeller: Object.assign({}, a.modeller, mm) })
            .then(function () { tamam.textContent = t('gelismis.kaydedildi'); });
        } }), tamam
      ])
    ]);
  }

  function durumCiz() {
    var d = S.durum;
    if (ekran.yazi && document.body.contains(ekran.yazi)) {   // gelişmiş ayarlardaki altyazı önizlemesi
      var yeniYazi = (d && d.son_yazi) || t('on.bos');
      if (ekran.yazi.textContent !== yeniYazi) {
        ekran.yazi.textContent = yeniYazi;
        ekran.yazi.classList.remove('yeni'); void ekran.yazi.offsetWidth; ekran.yazi.classList.add('yeni');
      }
      ekran.yazi.style.opacity = d && d.son_yazi ? 1 : .55;
    }
    if (!ekran.buyuk || !document.body.contains(ekran.buyuk)) return;
    if (!d) { ekran.durum.textContent = t('durum.bekle'); return; }
    var dImza = (d.calisiyor ? '1' : '0') + dil;
    if (ekran.buyuk.dataset.imza !== dImza) {
      ekran.buyuk.dataset.imza = dImza;
      ekran.buyuk.textContent = '';
      ekran.buyuk.appendChild(ikon(d.calisiyor ? 'dur' : 'oyna'));
      ekran.buyuk.appendChild(h('span', { text: d.calisiyor ? t('durdur') : t('baslat') }));
    }
    ekran.buyuk.classList.toggle('dur', !!d.calisiyor);
    if (ekran.hero) ekran.hero.classList.toggle('calisiyor', !!d.calisiyor);
    if (ekran.uyari) {   // sunucunun nazik uyarısı (ör. tüm ekran seçili); yoksa gizli
      var um = d.uyari && d.uyari.mesaj ? String(d.uyari.mesaj) : '';
      if (ekran.uyari.textContent !== um) ekran.uyari.textContent = um;
      ekran.uyari.hidden = !um;
    }
    var sorun = d.hata === 'yakalama' || d.hata === 'genel' ? d.hata : null;   // boru hattı durduysa nedeni
    ekran.led.className = 'led' + (d.calisiyor ? (d.yedekte ? ' yedek' : ' acik') : (sorun ? ' sorun' : ''));
    var dm = !d.calisiyor ? (sorun ? t('durum.hata.' + sorun) : t('durum.durdu')) : (d.yedekte ? t('durum.yedekte') : t('durum.calisiyor'));
    if (d.calisiyor && d.yedekte && d.yedek_neden && d.yedek_neden.mesaj) dm = d.yedek_neden.mesaj;   // neden yedeğe geçtiğini açıkça söyle
    if (ekran.durum.textContent !== dm) ekran.durum.textContent = dm;
    var nm = d.calisiyor ? t('ana.ne.calisiyor') : (sorun ? t('durum.hata.' + sorun + '.k') : t('ana.ne.durdu'));
    var gk = d.calisiyor && d.gecikme && d.gecikme.olcum ? d.gecikme : null;   // §16.4: aşama aşama gecikme
    if (gk && gk.toplam_ms != null) {
      var sn = function (ms) { return ((ms || 0) / 1000).toFixed(1).replace('.', ','); };
      nm += ' · ' + t('gecikme.ozet', { okuma: gk.okuma_ms || 0, ceviri: sn(gk.ceviri_ms), toplam: sn(gk.toplam_ms) });
      if (gk.kuyruk > 1) nm += ' · ' + t('gecikme.kuyruk', { n: gk.kuyruk });
    }
    if (ekran.ne.textContent !== nm) ekran.ne.textContent = nm;
    gosterimCiz();
  }

  // durum.bildirim (PROTOKOL 13.1): kısayolla başlat/durdur, gizle/göster → küçük bildirim. İlk okumada eski bildirim gösterilmez.
  function bildirimDenetle(d) {
    var b = d && d.bildirim;
    var metin = !b ? '' : (typeof b === 'string' ? b : (b.metin || b.mesaj || ''));
    var imza = !b ? '' : (typeof b === 'string' ? b : JSON.stringify([b.id, b.zaman, metin]));
    var ilk = S.bildirimImza === undefined;
    var onceki = S.bildirimImza; S.bildirimImza = imza;
    if (ilk || !metin || imza === onceki) return;
    toast(metin, 'bilgi');
  }

  // ---------- erişim (PROTOKOL §17): altyazı sınırsız, dublaj süresi, "+30 dk ekle", cihaza bağlı kod ----------
  function erisimYukle() {
    return api('GET', '/api/erisim').then(function (e) { S.erisim = e; erisimCiz(); reklamIzle(); }).catch(function () {});
  }
  function sureMetni(dk) {   // 80 → "1 sa 20 dk"
    var sa = Math.floor(dk / 60), d = dk % 60;
    if (sa && d) return t('erisim.sa_dk', { sa: sa, dk: d });
    return sa ? t('erisim.sa', { sa: sa }) : t('erisim.dk', { dk: d });
  }
  function dublajSureMetni(e) {
    var d = (e && e.dublaj) || {};
    if (d.sinirsiz) return t('erisim.dublaj_sinirsiz');
    return d.kalan_dakika > 0 ? t('erisim.dublaj_kalan', { sure: sureMetni(d.kalan_dakika) }) : t('erisim.dublaj_yok');
  }
  function erisimCiz() {
    var e = S.erisim;
    var oz = $('#dublaj-sure-ozet'); if (oz && e && e.dublaj) oz.textContent = e.dublaj.sinirsiz ? '' : ' · ' + (e.dublaj.kalan_dakika > 0 ? sureMetni(e.dublaj.kalan_dakika) : t('erisim.ozet_yok'));
    if (!ekran.erisim || !document.body.contains(ekran.erisim)) return;
    if (!e || !e.dublaj) return;
    var kutu = ekran.erisim, d = e.dublaj, r = e.reklam, yerel = !!S.reklamOynuyor;
    var tvde = !!(r && r.hedef === 'tv' && !yerel);
    var imza = [e.kod, d.sinirsiz, d.durdu, d.ekleyebilir, !!r, tvde, yerel, S.erisimAcik, S.reklamBekle, e.cihaz, dil].join('|');
    var metin = $('#erisim-dublaj');
    if (kutu.dataset.imza === imza) { if (metin) metin.textContent = dublajSureMetni(e); return; }   // yalnız süreyi güncelle (yazı/odak kaybolmasın)
    kutu.dataset.imza = imza;
    kutu.textContent = '';
    kutu.appendChild(h('div', { class: 'satir erisim-satir' }, [
      h('span', { class: 'etiket-kucuk', text: t('erisim.altyazi') }),
      h('span', { id: 'erisim-altyazi', class: 'erisim-deger', text: t('erisim.altyazi_sinirsiz') })]));
    kutu.appendChild(h('div', { class: 'satir erisim-satir' }, [
      h('span', { class: 'etiket-kucuk', text: t('erisim.dublaj') }),
      h('span', { id: 'erisim-dublaj', class: 'erisim-deger', 'aria-live': 'polite', text: dublajSureMetni(e) })]));
    if (!d.sinirsiz) {
      var ekle = h('button', { type: 'button', class: 'dugme erisim-ekle', id: 'erisim-ekle', disabled: !d.ekleyebilir || !!r || !!S.reklamBekle,
        text: t('erisim.ekle'), onclick: function () { otuzEkle(); } });
      kutu.appendChild(h('div', { class: 'satir erisim-ekle-satir' }, [ekle,
        h('span', { class: 'sessiz', id: 'erisim-ekle-not', text: d.ekleyebilir ? t('erisim.ekle_not') : t('erisim.en_cok') })]));
      if (d.durdu) kutu.appendChild(h('p', { class: 'not', id: 'erisim-durdu', role: 'status', text: t('erisim.durdu') }));
      if (tvde) {
        kutu.appendChild(h('div', { class: 'satir erisim-tv', id: 'erisim-tv' }, [
          h('span', { role: 'status', text: t('erisim.tvde') }),
          h('button', { type: 'button', class: 'baglanti', id: 'erisim-burada', text: t('erisim.burada'), onclick: function () { reklamOynat(r.id, null, r.en_az_sn); } })]));
      }
    }
    if (!e.kod) {
      kutu.appendChild(h('button', { type: 'button', class: 'baglanti', id: 'kodum-var', text: t('erisim.kodum_var'), onclick: function () {
        S.erisimAcik = !S.erisimAcik; erisimCiz(); var g = $('#erisim-kod'); if (g) g.focus();
      } }));
    }
    if (S.erisimAcik && !e.kod) {
      var hata = h('p', { class: 'sessiz erisim-hata', id: 'erisim-hata', role: 'alert' });
      var girdi = h('input', { type: 'text', id: 'erisim-kod', autocomplete: 'off', spellcheck: 'false', 'aria-label': t('erisim.kod_etiket'), placeholder: 'AK1-XXXXX-XXXXX-…', onkeydown: function (ev) { if (ev.key === 'Enter') kaydet(); } });
      var kaydet = function () {
        var v = girdi.value.trim();
        if (!v) { hata.textContent = t('erisim.bos'); return; }
        api('POST', '/api/erisim', { kod: v }).then(function () {
          S.erisimAcik = false; toast(t('erisim.tamam'));
          return Promise.all([erisimYukle(), durumYukle()]);
        }).catch(function (er) { hata.textContent = (er && er.mesaj) || t('hata.genel'); });
      };
      kutu.appendChild(h('div', { class: 'satir erisim-form' }, [girdi,
        h('button', { type: 'button', class: 'dugme kucuk', id: 'erisim-kaydet', text: t('erisim.kaydet'), onclick: kaydet }),
        h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'erisim-vazgec', text: t('erisim.vazgec'), onclick: function () { S.erisimAcik = false; erisimCiz(); } })]));
      kutu.appendChild(hata);
      kutu.appendChild(h('div', { class: 'satir erisim-cihaz' }, [
        h('span', { class: 'etiket-kucuk', text: t('erisim.cihaz') }),
        h('code', { id: 'erisim-cihaz', text: e.cihaz || '-' }),
        h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'erisim-cihaz-kopyala', text: t('erisim.kopyala'), onclick: function () {
          var bitti = function () { toast(t('erisim.kopyalandi')); };
          try { navigator.clipboard.writeText(e.cihaz).then(bitti, function () {}); } catch (x) { /* yok say */ }
        } })]));
      kutu.appendChild(h('p', { class: 'sessiz', id: 'erisim-cihaz-not', text: t('erisim.cihaz_not') }));
    }
  }

  // "+30 dk ekle": ilk reklam şirketi reklamından önce izin (§17.7), sonra reklam ya da destek ekranı
  function otuzEkle() {
    var e = S.erisim || {};
    if (e.vast_var && e.reklam_izni == null) {
      return pencere(t('reklam.izin_baslik'), t('reklam.izin_govde'), [
        { ad: t('reklam.izin_kabul'), deger: 'kabul', id: 'reklam-izin-kabul' },
        { ad: t('reklam.izin_reklamsiz'), deger: 'red', sinif: 'ikincil', id: 'reklam-izin-reklamsiz' },
        { ad: t('reklam.izin_vazgec'), deger: null, sinif: 'ikincil', id: 'reklam-izin-vazgec' }
      ]).then(function (v) {
        if (!v) return;
        return ayarKaydet({ erisim: Object.assign({}, (S.ayarlar || {}).erisim, { reklam_izni: v === 'kabul' }) }).then(function () { e.reklam_izni = v === 'kabul'; return reklamBaslat(); });
      });
    }
    return reklamBaslat();
  }
  function reklamBaslat() {
    S.reklamBekle = true; erisimCiz();
    return api('POST', '/api/erisim/reklam', { yer: 'otomatik' }).then(function (r) {
      S.reklamBekle = false; S.reklamId = r.id; S.reklamBas = Date.now(); S.reklamZaman = (r.zaman_asimi_sn || 120) * 1000;
      if (r.hedef === 'panel') reklamOynat(r.id, r.vast, r.en_az_sn);
      return erisimYukle();
    }).catch(function (er) { S.reklamBekle = false; erisimCiz(); hataGoster(er); });
  }
  function reklamOynat(id, vast, enAz) {
    if (!window.AKReklam || S.reklamOynuyor) return;
    S.reklamOynuyor = window.AKReklam.oynat(document.body, { id: id, vast: vast, en_az_sn: enAz,
      metin: { reklam: t('reklam.etiket'), sn: t('reklam.sn'), destek: t('reklam.destek'), destek_alt: t('reklam.destek_alt') },
      bitti: function (s) { S.reklamOynuyor = null; reklamBitir(s.id, s.sure_sn, 0); } });
    erisimCiz();
  }
  function reklamBitir(id, sure, deneme) {
    return api('POST', '/api/erisim/reklam/bitti', { id: id, sure_sn: sure || 0 }).then(function () {
      S.reklamId = null; toast(t('erisim.eklendi')); return Promise.all([erisimYukle(), durumYukle()]);
    }).catch(function (er) {
      if (er && er.hata === 'reklam_erken' && deneme < 10) {   // sunucu saatiyle birkaç saniye eksikse bekle
        var bekle = Math.min(20, ((er.govde && er.govde.kalan_sn) || 1) + 0.5) * 1000;
        return new Promise(function (ok) { setTimeout(ok, bekle); }).then(function () { return reklamBitir(id, sure, deneme + 1); });
      }
      if (er && er.hata === 'reklam_yok') { S.reklamId = null; return erisimYukle(); }   // TV bitirdi: süre zaten eklendi
      hataGoster(er);
    });
  }
  // TV'deki reklam bitince (reklam alanı boşalınca) haber ver; TV hiç bitirmezse yedek zamanlayıcı panelden bitirir
  function reklamIzle() {
    var e = S.erisim; if (!e || !S.reklamId) return;
    if (!e.reklam) { S.reklamId = null; if (!S.reklamOynuyor) toast(t('erisim.eklendi')); return; }
    if (!S.reklamOynuyor && !S.reklamYedek && Date.now() - S.reklamBas > S.reklamZaman) {
      S.reklamYedek = true;
      reklamBitir(e.reklam.id, 0, 0).then(function () { S.reklamYedek = false; });
    }
  }

  function durumYukle() {
    return api('GET', '/api/durum').then(function (d) {
      var oncekiKapali = S.kapali;
      S.durum = d; S.kapali = false;
      bildirimDenetle(d);
      erisimYukle();
      if (oncekiKapali) banner('', '');
      if (!S.ayarlar || !S.motorlar.length) {
        return Promise.all([ayarYukle(), api('GET', '/api/motorlar').then(function (m) { S.motorlar = m; }), kaynakYukle()]).then(ciz).catch(function () {});
      }
      durumCiz();
    }).catch(function (e) { if (e.kapali) kapaliBanner(true); });
  }


  // ---------- BÖLGE EDİTÖRÜ ("neyi çevireyim?", PROTOKOL 7.1 + 10.1: en çok 6 kare) ----------
  var BOLGE_TURLER = ['altyazi', 'ust_yazi', 'diger'];
  var BOLGE_EN_COK = 6, BOLGE_MIN_G = 0.03, BOLGE_MIN_Y = 0.02, BOLGE_ADIM = 0.01;
  function yuvarla(v) { return Math.round(v * 10000) / 10000; }
  function sinir(v, a, b) { return v < a ? a : (v > b ? b : v); }
  var BOLGE_ALTYAZI_ALAN = { x: 0.2, y: 0.84, g: 0.6, y2: 0.1 };   // "alttaki altyazı çubuğu" (önizleme için)
  function varsayilanHedef(tur) { return tur === 'altyazi' ? 'altyazi' : 'ustune'; }
  function olcekSinir(v) { v = Number(v); if (!isFinite(v) || v <= 0) v = 1; return Math.round(sinir(v, 0.6, 2) * 100) / 100; }
  function ekranOlcek() { var g = (S.ayarlar && S.ayarlar.gorunum) || {}; return olcekSinir(g.ekran_olcek == null ? 1 : g.ekran_olcek); }
  function hedefGecerli(k) { return !!k && typeof k === 'object' && isFinite(k.x) && isFinite(k.y) && isFinite(k.g) && isFinite(k.y2); }
  function bolgeIlkle(b) {   // eski kayıtlarda hedef/olcek yoktur: varsayılanları koy
    if (!hedefGecerli(b.hedef) && b.hedef !== 'ustune' && b.hedef !== 'altyazi') b.hedef = varsayilanHedef(b.tur);
    b.olcek = olcekSinir(b.olcek == null ? 1 : b.olcek);
    return b;
  }
  // ekran ölçeği ("Ekrandaki yazıların büyüklüğü"): 4. aşama ve ayarlarda
  function ekranOlcekAlani(id) {
    var v = Math.round(ekranOlcek() * 100), zaman;
    var deger = h('output', { class: 'olcek-deger', id: id + '-deger', 'for': id, text: '%' + v });
    var inp = h('input', { type: 'range', min: 60, max: 200, step: 10, id: id, value: v, 'aria-describedby': id + '-not' });
    inp.addEventListener('input', function () {
      deger.textContent = '%' + inp.value;
      clearTimeout(zaman); zaman = setTimeout(function () { ayarKaydet({ gorunum: { ekran_olcek: olcekSinir(Number(inp.value) / 100) } }); }, 250);
    });
    return h('div', { class: 'ekran-olcek' }, [
      h('label', { class: 'etiket', 'for': id, text: t('gorunum.ekran_olcek') }),
      h('div', { class: 'olcek-satir' }, [inp, deger]),
      h('p', { class: 'sessiz', id: id + '-not', text: t('gorunum.ekran_olcek.k') })
    ]);
  }
  // gorunum.en_az_ms (PROTOKOL 13.4): çok kısa yanıp sönen yazılar en az bu kadar kalır (0–3 sn)
  function enAzMs() { var g = (S.ayarlar && S.ayarlar.gorunum) || {}, v = Number(g.en_az_ms); return isFinite(v) && g.en_az_ms != null ? Math.max(0, Math.min(3000, Math.round(v / 100) * 100)) : 800; }
  function saniye(ms) { var v = ms / 1000; try { return v.toLocaleString(dil === 'tr' ? 'tr-TR' : 'en-US', { maximumFractionDigits: 1 }); } catch (e) { return String(v); } }
  function enAzAlani(id) {
    var v = enAzMs(), zaman;
    var deger = h('output', { class: 'olcek-deger', id: id + '-deger', 'for': id, text: t('enaz.deger', { n: saniye(v) }) });
    var inp = h('input', { type: 'range', min: 0, max: 3000, step: 100, id: id, value: v, 'aria-describedby': id + '-not', 'aria-valuetext': t('enaz.deger', { n: saniye(v) }) });
    inp.addEventListener('input', function () {
      var m = Number(inp.value), y = t('enaz.deger', { n: saniye(m) });
      deger.textContent = y; inp.setAttribute('aria-valuetext', y);
      clearTimeout(zaman); zaman = setTimeout(function () { ayarKaydet({ gorunum: { en_az_ms: m } }); }, 250);
    });
    return h('div', { class: 'ekran-olcek en-az' }, [
      h('label', { class: 'etiket', 'for': id, text: t('enaz.baslik') }),
      h('div', { class: 'olcek-satir' }, [inp, deger]),
      h('p', { class: 'sessiz', id: id + '-not', text: t('enaz.k') })
    ]);
  }
  function bolgeOzet() {
    var n = ((S.ayarlar && S.ayarlar.bolgeler) || []).length;
    return n ? t('bolge.secili_durum', { n: n }) : t('bolge.otomatik_durum');
  }
  // çizilen yerin konumundan türünü tahmin et: alt orta = altyazı, üst = görev/bilgi
  function turTahmin(b) {
    var cy = b.y + b.y2 / 2;
    if (cy > 0.6) return 'altyazi';
    if (cy < 0.4) return 'ust_yazi';
    return 'diger';
  }
  // okunan satırları yakınlığa göre kümele → her küme bir kare (alt orta: altyazı, sol üst: görev/bilgi)
  function okunandanOner(satirlar) {
    var gruplar = satirlar.map(function (s) {
      var cx = s.x + s.g / 2, cy = s.y + s.y2 / 2;
      var tur = (cy > 0.6 && cx > 0.2 && cx < 0.8) ? 'altyazi' : ((cy < 0.4 && cx < 0.5) ? 'ust_yazi' : 'diger');
      return { x: s.x, y: s.y, g: s.g, y2: s.y2, tur: tur };
    });
    var degisti = true;
    function yakin(a, b) {
      return a.tur === b.tur && a.x - 0.03 < b.x + b.g && b.x - 0.03 < a.x + a.g && a.y - 0.025 < b.y + b.y2 && b.y - 0.025 < a.y + a.y2;
    }
    while (degisti) {
      degisti = false;
      for (var i = 0; i < gruplar.length && !degisti; i++) {
        for (var j = i + 1; j < gruplar.length; j++) {
          if (yakin(gruplar[i], gruplar[j])) {
            var a = gruplar[i], b = gruplar[j], x1 = Math.min(a.x, b.x), y1 = Math.min(a.y, b.y);
            gruplar[i] = { x: x1, y: y1, g: Math.max(a.x + a.g, b.x + b.g) - x1, y2: Math.max(a.y + a.y2, b.y + b.y2) - y1, tur: a.tur };
            gruplar.splice(j, 1); degisti = true; break;
          }
        }
      }
    }
    var p = 0.015;
    return gruplar.sort(function (a, b) { return (b.g * b.y2) - (a.g * a.y2); }).slice(0, BOLGE_EN_COK).map(function (k) {
      var x = sinir(k.x - p, 0, 1), y = sinir(k.y - p, 0, 1);
      var g = sinir(k.g + 2 * p, BOLGE_MIN_G, 1 - x), y2 = sinir(k.y2 + 2 * p, BOLGE_MIN_Y, 1 - y);
      return { x: yuvarla(x), y: yuvarla(y), g: yuvarla(g), y2: yuvarla(y2), tur: k.tur, ad: t('bolge.ad.' + k.tur) };
    }).sort(function (a, b) { return a.y - b.y || a.x - b.x; });
  }

  // Dönen: { el, yukle(), kapat() }. o.degisti: kare değişince; o.kaydedildi(n): kayıt bitince.
  function bolgeEditoru(o) {
    o = o || {};
    var liste = JSON.parse(JSON.stringify((S.ayarlar && S.ayarlar.bolgeler) || [])).slice(0, BOLGE_EN_COK).map(bolgeIlkle);
    var secili = -1, surukle = null, popIdx = -1, hedefCiz = -1;
    var katman = h('div', { class: 'bolge-katman', id: 'bolge-katman' });
    var resim = h('img', { class: 'bolge-resim', id: 'bolge-resim', alt: t('bolge.resim_alt'), draggable: 'false' });
    var pop = h('div', { class: 'bolge-pop', id: 'bolge-pop', role: 'dialog', 'aria-modal': 'false', 'aria-labelledby': 'bolge-pop-baslik', hidden: true });
    var ipucuPerde = h('div', { class: 'bolge-ipucu', id: 'bolge-ipucu', hidden: true }, h('div', { class: 'bolge-ipucu-kart' }, [
      h('span', { class: 'bolge-ipucu-ik', 'aria-hidden': 'true' }, ikon('kare')),
      h('p', { text: t('bolge.ilk_ipucu') }),
      h('button', { type: 'button', class: 'dugme kucuk', id: 'bolge-ipucu-tamam', text: t('bolge.ipucu_tamam'), onclick: function () { ipucuKapat(); var k = katman; try { k.focus(); } catch (e) { /* yok */ } } })
    ]));
    var sahne = h('div', { class: 'bolge-sahne', id: 'bolge-sahne', hidden: true }, [resim, katman, pop, ipucuPerde]);
    var mesaj = h('div', { id: 'bolge-mesaj', 'aria-live': 'polite' });
    var modBar = h('div', { class: 'bolge-mod', id: 'bolge-mod', role: 'status', hidden: true });
    var satirlar = h('div', { class: 'bolge-satirlar', id: 'bolge-satirlar' });
    var sayac = h('span', { class: 'bolge-sayac', id: 'bolge-sayac', 'aria-live': 'polite' });
    var dolu = h('p', { class: 'not', id: 'bolge-dolu', hidden: true, text: t('bolge.dolu', { n: BOLGE_EN_COK }) });
    var kaydetBtn = h('button', { type: 'button', class: 'dugme', id: 'bolge-kaydet', text: t('bolge.kaydet'), onclick: function () { kaydet(); } });
    var kok = h('div', { class: 'bolge-edit', id: 'bolge-edit' });

    function turAd(tur) { return t('bolge.tur.' + tur); }
    function turKisa(tur) { return t('bolge.tur_kisa.' + tur); }
    function kutuEtiket(i) { return t('bolge.kutu_aria', { n: i + 1, tur: turAd(liste[i].tur) }); }
    function bildir() { if (o.degisti) o.degisti(); }
    function odakla(el) { if (!el) return; try { el.focus({ preventScroll: true }); } catch (x) { el.focus(); } }
    function ipucuKapat() { ipucuPerde.hidden = true; ls('bolge_ipucu', '1'); }

    function kutulariCiz() {
      var onceki = document.activeElement;
      var odakIdx = onceki && onceki.classList && onceki.classList.contains('bolge') ? Number(onceki.dataset.bolge) : -1;
      var odakHedef = onceki && onceki.classList && onceki.classList.contains('bolge-hedef') ? Number(onceki.dataset.hedef) : -1;
      katman.textContent = '';
      liste.forEach(function (b, i) {
        var el = h('div', { class: 'bolge t-' + b.tur + (i === secili ? ' secili' : ''), 'data-bolge': String(i), tabindex: '0', role: 'group',
          'aria-label': kutuEtiket(i), onkeydown: function (e) { tus(e, i, false); }, onfocus: function (e) { if (e.target === el && secili !== i) { secili = i; isaretle(); } } });
        el.style.left = b.x * 100 + '%'; el.style.top = b.y * 100 + '%'; el.style.width = b.g * 100 + '%'; el.style.height = b.y2 * 100 + '%';
        el.appendChild(h('button', { type: 'button', class: 'bolge-cip', id: 'bolge-cip-' + i, 'aria-haspopup': 'dialog', 'aria-expanded': String(popIdx === i),
          onclick: function (e) { e.stopPropagation(); popAc(i); } },
          [h('span', { class: 'gizli', text: t('bolge.cip_kare') + ' ' }), h('b', { text: String(i + 1) }), h('span', { class: 'cip-tur', text: ' ' + turKisa(b.tur) }),
            h('span', { class: 'gizli', text: ', ' + t('bolge.cip_degistir') }), h('i', { class: 'ok-asagi', 'aria-hidden': 'true' })]));
        el.appendChild(h('button', { type: 'button', class: 'bolge-x', 'data-kutu-sil': String(i), 'aria-label': t('bolge.sil', { n: i + 1 }), text: '×', onclick: function (e) { e.stopPropagation(); sil(i); } }));
        ['nw', 'ne', 'sw', 'se'].forEach(function (k) { el.appendChild(h('span', { class: 'tutamac ' + k, 'data-tutamac': k, 'aria-hidden': 'true' })); });
        katman.appendChild(el);
        if (i === odakIdx) odakla(el);
      });
      liste.forEach(function (b, i) {   // hedef kutuları: kaynakla aynı renkte, kesik çizgili
        if (!hedefGecerli(b.hedef)) return;
        var he = h('div', { class: 'bolge-hedef t-' + b.tur + (i === secili ? ' secili' : ''), 'data-hedef': String(i), tabindex: '0', role: 'group',
          'aria-label': t('bolge.hedef_aria', { n: i + 1 }), onkeydown: function (e) { tus(e, i, true); },
          onfocus: function (e) { if (e.target === he && secili !== i) { secili = i; isaretle(); } } });
        he.style.left = b.hedef.x * 100 + '%'; he.style.top = b.hedef.y * 100 + '%'; he.style.width = b.hedef.g * 100 + '%'; he.style.height = b.hedef.y2 * 100 + '%';
        he.appendChild(h('span', { class: 'hedef-etiket', text: t('bolge.hedef_etiket', { n: i + 1 }) }));
        ['nw', 'ne', 'sw', 'se'].forEach(function (k) { he.appendChild(h('span', { class: 'tutamac ' + k, 'data-tutamac': k, 'aria-hidden': 'true' })); });
        katman.appendChild(he);
        if (i === odakHedef) odakla(he);
      });
      baglantiCiz(); onizlemeCiz();
      dolu.hidden = liste.length < BOLGE_EN_COK;
      sayac.textContent = t('bolge.sayac', { n: liste.length, m: BOLGE_EN_COK });
    }
    // kaynak → hedef ince bağlantı çizgileri (katmanın en altında, tıklamayı engellemez)
    function kenar(k, hx, hy) {   // kutunun merkezinden (hx,hy)'e doğru giderken kenarla kesiştiği nokta
      var cx = k.x + k.g / 2, cy = k.y + k.y2 / 2, dx = hx - cx, dy = hy - cy;
      if (!dx && !dy) return { x: cx, y: cy };
      var s = Math.min(dx ? (k.g / 2) / Math.abs(dx) : Infinity, dy ? (k.y2 / 2) / Math.abs(dy) : Infinity);
      return { x: cx + dx * s, y: cy + dy * s };
    }
    function baglantiCiz() {
      var eski = katman.querySelector('.bolge-baglanti'); if (eski) eski.remove();
      var NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg');
      svg.setAttribute('class', 'bolge-baglanti'); svg.setAttribute('viewBox', '0 0 100 100'); svg.setAttribute('preserveAspectRatio', 'none'); svg.setAttribute('aria-hidden', 'true');
      liste.forEach(function (b, i) {
        if (!hedefGecerli(b.hedef)) return;
        var k = b.hedef, a = kenar(b, k.x + k.g / 2, k.y + k.y2 / 2), z = kenar(k, b.x + b.g / 2, b.y + b.y2 / 2);
        var ln = document.createElementNS(NS, 'line');
        ln.setAttribute('x1', a.x * 100); ln.setAttribute('y1', a.y * 100); ln.setAttribute('x2', z.x * 100); ln.setAttribute('y2', z.y * 100);
        ln.setAttribute('class', 'baglanti-cizgi t-' + b.tur);
        svg.appendChild(ln);
      });
      katman.insertBefore(svg, katman.firstChild);
    }
    // örnek yazı: seçili karenin çeviri yerinde, hesaplanan büyüklükte (boşlukta bölünür, harf harf asla)
    function ornekMetin(b) {
      var l = (S.okunan || []).filter(function (s) { var cx = s.x + s.g / 2, cy = s.y + s.y2 / 2; return cx >= b.x && cx <= b.x + b.g && cy >= b.y && cy <= b.y + b.y2; })
        .sort(function (p, q) { return p.y - q.y || p.x - q.x; }).map(function (s) { return s.metin; }).join(' ').trim();
      return l ? (l.length > 90 ? l.slice(0, 90).replace(/\s+\S*$/, '') + '…' : l) : t('bolge.ornek');
    }
    function boyut1080(b) { return sinir(b.y2 * 1080, 14, 30) * olcekSinir(b.olcek) * ekranOlcek(); }
    function onizlemeCiz() {
      var eski = katman.querySelector('.bolge-onizle'); if (eski) eski.remove();
      if (secili < 0 || !liste[secili]) return;
      var b = liste[secili], H = katman.getBoundingClientRect().height;
      if (!H) return;
      var ozel = hedefGecerli(b.hedef), alan = ozel ? b.hedef : (b.hedef === 'altyazi' ? BOLGE_ALTYAZI_ALAN : b);
      var yazi = h('span', { class: 'bolge-onizle-yazi', text: ornekMetin(b) });
      var kutu = h('div', { class: 'bolge-onizle' + (ozel || b.hedef === 'altyazi' ? ' sabit' : ' buyur') + (b.hedef === 'altyazi' ? ' altyazi' : ''), 'aria-hidden': 'true' }, yazi);
      kutu.style.left = alan.x * 100 + '%'; kutu.style.top = alan.y * 100 + '%';
      if (ozel || b.hedef === 'altyazi') { kutu.style.width = alan.g * 100 + '%'; kutu.style.height = alan.y2 * 100 + '%'; }
      else { kutu.style.minWidth = alan.g * 100 + '%'; kutu.style.minHeight = alan.y2 * 100 + '%'; }
      katman.insertBefore(kutu, katman.firstChild);
      var px = H / 1080, boy = boyut1080(b) * px, en = 12 * px;
      yazi.style.fontSize = boy + 'px';
      if (kutu.classList.contains('sabit')) {   // sığmazsa küçül (en az 12 px)
        for (var n = 0; n < 40 && boy > en && (kutu.scrollHeight > kutu.clientHeight + 1 || kutu.scrollWidth > kutu.clientWidth + 1); n++) { boy = Math.max(en, boy * 0.93); yazi.style.fontSize = boy + 'px'; }
      }
    }
    if (window.ResizeObserver) new ResizeObserver(function () { onizlemeCiz(); }).observe(katman);
    function isaretle() {
      [].forEach.call(katman.children, function (el) { var k = el.dataset.bolge != null ? el.dataset.bolge : el.dataset.hedef; if (k != null) el.classList.toggle('secili', Number(k) === secili); });
      onizlemeCiz();
      [].forEach.call(satirlar.children, function (el) { el.classList.toggle('secili', Number(el.dataset.satir) === secili); });
    }
    function satirlariCiz() {
      satirlar.textContent = '';
      if (!liste.length) { satirlar.appendChild(h('p', { class: 'bos-durum', id: 'bolge-bos', text: t('bolge.bos') })); return; }
      liste.forEach(function (b, i) {
        var sec = h('select', { id: 'bolge-tur-' + i, 'aria-label': t('bolge.kare', { n: i + 1 }) + ': ' + t('bolge.tur'), onchange: function () { turDegis(i, sec.value); } },
          BOLGE_TURLER.map(function (k) { return h('option', { value: k, selected: k === b.tur, text: turAd(k) }); }));
        sec.value = b.tur;
        var mod = hedefGecerli(b.hedef) ? 'kendim' : b.hedef;
        var seg = h('fieldset', { class: 'bolge-hedef-sec' }, [h('legend', { text: t('bolge.nereye') }),
          h('div', { class: 'segment' }, ['ustune', 'altyazi', 'kendim'].map(function (k) {
            var id = 'bolge-hedef-' + i + '-' + k, r = h('input', { type: 'radio', name: 'bolge-hedef-' + i, id: id, value: k, onchange: function () { hedefSec(i, k); } });
            r.checked = mod === k;
            return h('span', { class: 'seg' }, [r, h('label', { 'for': id, text: t('bolge.hedef.' + k) })]);
          }))]);
        var deger = h('output', { class: 'olcek-deger', id: 'bolge-olcek-deger-' + i, 'for': 'bolge-olcek-' + i, text: '%' + Math.round(b.olcek * 100) });
        var kay = h('input', { type: 'range', min: 60, max: 200, step: 10, id: 'bolge-olcek-' + i, value: Math.round(b.olcek * 100), 'aria-label': t('bolge.olcek_aria', { n: i + 1 }) });
        kay.addEventListener('input', function () {
          b.olcek = olcekSinir(Number(kay.value) / 100); deger.textContent = '%' + Math.round(b.olcek * 100);
          secili = i; isaretle(); bildir();
        });
        var satir = h('div', { class: 'bolge-satir t-' + b.tur + (i === secili ? ' secili' : ''), 'data-satir': String(i) }, [
          h('div', { class: 'bolge-ust' }, [h('span', { class: 'bolge-no', text: t('bolge.kare', { n: i + 1 }) }), sec,
            h('button', { type: 'button', class: 'x bolge-sil', 'data-sil': String(i), 'aria-label': t('bolge.sil', { n: i + 1 }), text: '×', onclick: function () { sil(i); } })]),
          seg,
          h('div', { class: 'bolge-olcek' }, [h('label', { class: 'etiket', 'for': 'bolge-olcek-' + i, text: t('bolge.olcek') }), h('div', { class: 'olcek-satir' }, [kay, deger])])
        ]);
        satir.addEventListener('focusin', function () { if (secili !== i) { secili = i; isaretle(); } });
        satirlar.appendChild(satir);
      });
    }
    function modGoster(i) {
      modBar.textContent = '';
      modBar.appendChild(h('span', { text: t('bolge.mod_ciz', { n: i + 1 }) }));
      modBar.appendChild(h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'bolge-mod-bitti', text: t('bolge.mod_bitti'), onclick: modKapat }));
      modBar.hidden = false; katman.classList.add('hedef-ciz');
    }
    function modKapat() { hedefCiz = -1; modBar.hidden = true; katman.classList.remove('hedef-ciz'); }
    function hedefSec(i, mod) {
      var b = liste[i];
      if (mod === 'kendim') {
        if (!hedefGecerli(b.hedef)) {   // hazır bir yer koy (kaynağın altına ya da üstüne); istersen yeniden çizilir
          var k = { x: b.x, y: b.y + b.y2 + 0.03, g: b.g, y2: b.y2 };
          if (k.y + k.y2 > 1) k.y = b.y - b.y2 - 0.03;
          duzelt(k); b.hedef = k;
        }
        hedefCiz = i; secili = i; modGoster(i);
        try { sahne.scrollIntoView({ block: 'nearest', behavior: 'auto' }); } catch (x) { /* yok */ }
      } else { b.hedef = mod; if (hedefCiz === i) modKapat(); }
      hepsiniCiz(); bildir();
      odakla($('#bolge-hedef-' + i + '-' + mod));
    }
    function hepsiniCiz() { kutulariCiz(); satirlariCiz(); }
    function turDegis(i, tur) { var b = liste[i]; b.tur = tur; b.ad = t('bolge.ad.' + tur); if (!hedefGecerli(b.hedef)) b.hedef = varsayilanHedef(tur); hepsiniCiz(); bildir(); }
    function sil(i) {
      popKapat(false); modKapat();
      liste.splice(i, 1); secili = -1; hepsiniCiz(); bildir();
      odakla(katman.querySelector('.bolge') || katman);
    }

    // tür seçme açılır kutusu (kutunun hemen altında/üstünde)
    function popAc(i) {
      if (popIdx === i && !pop.hidden) { popKapat(true); return; }
      popIdx = i; secili = i; var b = liste[i];
      pop.textContent = '';
      pop.appendChild(h('p', { class: 'bolge-pop-baslik', id: 'bolge-pop-baslik', text: t('bolge.pop_baslik', { n: i + 1 }) }));
      var grup = h('div', { class: 'bolge-pop-liste', role: 'group', 'aria-labelledby': 'bolge-pop-baslik' });
      BOLGE_TURLER.forEach(function (k) {
        grup.appendChild(h('button', { type: 'button', class: 'bolge-pop-sec t-' + k, 'data-pop-tur': k, 'aria-pressed': String(b.tur === k), onclick: function () {
          turDegis(i, k); popKapat(true);
        } }, [h('i', { class: 'renk', 'aria-hidden': 'true' }), h('span', {}, [h('b', { text: turKisa(k) }), h('small', { text: t('bolge.tur_ne.' + k) })])]));
      });
      pop.appendChild(grup);
      pop.appendChild(h('button', { type: 'button', class: 'bolge-pop-sil', id: 'bolge-pop-sil', text: t('bolge.sil', { n: i + 1 }), onclick: function () { sil(i); } }));
      pop.style.left = sinir(b.x * 100, 0, 72) + '%';
      if (b.y + b.y2 > 0.62) { pop.style.top = ''; pop.style.bottom = (100 - b.y * 100) + '%'; } else { pop.style.bottom = ''; pop.style.top = (b.y + b.y2) * 100 + '%'; }
      pop.hidden = false;
      kutulariCiz();
      odakla(pop.querySelector('[aria-pressed=true]') || pop.querySelector('button'));
    }
    function popKapat(odakGeri) {
      if (pop.hidden) return;
      var i = popIdx; pop.hidden = true; popIdx = -1; kutulariCiz();
      if (odakGeri) odakla($('#bolge-cip-' + i) || katman);
    }
    pop.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); popKapat(true); }
    });
    function disariTik(e) {
      if (!document.body.contains(kok)) { document.removeEventListener('pointerdown', disariTik, true); return; }
      if (!pop.hidden && !pop.contains(e.target) && !(e.target.closest && e.target.closest('.bolge-cip'))) popKapat(false);
    }
    document.addEventListener('pointerdown', disariTik, true);

    function duzelt(b) { // sınırların içinde ve en küçük boyutun üstünde tut
      b.g = sinir(b.g, BOLGE_MIN_G, 1); b.y2 = sinir(b.y2, BOLGE_MIN_Y, 1);
      b.x = sinir(b.x, 0, 1 - b.g); b.y = sinir(b.y, 0, 1 - b.y2);
      b.x = yuvarla(b.x); b.y = yuvarla(b.y); b.g = yuvarla(b.g); b.y2 = yuvarla(b.y2);
    }
    function tus(e, i, hed) {
      var kutuEl = e.currentTarget;
      if (e.target !== kutuEl) return;   // içteki düğmeler kendi işini yapsın
      var b = hed ? liste[i].hedef : liste[i], d = e.altKey ? BOLGE_ADIM / 4 : BOLGE_ADIM, dx = 0, dy = 0;
      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        if (hed) { liste[i].hedef = varsayilanHedef(liste[i].tur); if (hedefCiz === i) modKapat(); hepsiniCiz(); bildir(); odakla(katman.querySelector('[data-bolge="' + i + '"]')); } else sil(i);
        return;
      }
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (hed) odakla(katman.querySelector('[data-bolge="' + i + '"]')); else popAc(i); return; }
      if (e.key === 'Escape' && hedefCiz >= 0) { e.preventDefault(); modKapat(); return; }
      if (e.key === 'ArrowLeft') dx = -d; else if (e.key === 'ArrowRight') dx = d; else if (e.key === 'ArrowUp') dy = -d; else if (e.key === 'ArrowDown') dy = d; else return;
      e.preventDefault();
      if (e.shiftKey) { b.g += dx; b.y2 += dy; } else { b.x += dx; b.y += dy; }
      duzelt(b); kutulariCiz(); bildir();
    }
    // klavyeyle yeni kare: katman odaktayken Enter → ortada bir kare
    katman.setAttribute('tabindex', '0');
    katman.setAttribute('role', 'application');
    katman.setAttribute('aria-label', t('bolge.katman_aria'));
    katman.addEventListener('keydown', function (e) {
      if (e.target !== katman || (e.key !== 'Enter' && e.key !== ' ')) return;
      e.preventDefault(); ipucuKapat();
      if (liste.length >= BOLGE_EN_COK) { dolu.hidden = false; return; }
      var b = { x: 0.35, y: 0.4, g: 0.3, y2: 0.12 }; b.tur = turTahmin(b); b.ad = t('bolge.ad.' + b.tur); bolgeIlkle(b);
      liste.push(b); secili = liste.length - 1; hepsiniCiz(); bildir();
      odakla(katman.querySelector('[data-bolge="' + secili + '"]'));
    });

    // fare/dokunma: boş yerde sürükle = çiz; kutu gövdesi = taşı; köşe = boyutlandır
    function nokta(e) {
      var r = katman.getBoundingClientRect();
      return { x: sinir((e.clientX - r.left) / r.width, 0, 1), y: sinir((e.clientY - r.top) / r.height, 0, 1) };
    }
    katman.addEventListener('pointerdown', function (e) {
      if (e.button !== undefined && e.button > 0) return;
      if (e.target.closest && e.target.closest('.bolge-cip,.bolge-x')) return;
      if (!ipucuPerde.hidden) ipucuKapat();
      var n = nokta(e), kutu = e.target.closest ? e.target.closest('.bolge,.bolge-hedef') : null;
      if (kutu) {
        var hed = kutu.classList.contains('bolge-hedef');
        var i = Number(hed ? kutu.dataset.hedef : kutu.dataset.bolge), b = hed ? liste[i].hedef : liste[i], tm = e.target.dataset && e.target.dataset.tutamac;
        secili = i;
        surukle = { tur: tm ? 'boyut' : 'tasi', i: i, hed: hed, tm: tm, n0: n, b0: { x: b.x, y: b.y, g: b.g, y2: b.y2 } };
        e.preventDefault();
        try { katman.setPointerCapture(e.pointerId); } catch (x) { /* eski tarayıcı */ }
        isaretle();
        return;
      }
      if (hedefCiz >= 0 && liste[hedefCiz]) {   // "Kendim seçeyim": ikinci kutu = hedef
        e.preventDefault(); secili = hedefCiz;
        surukle = { tur: 'hedefciz', i: hedefCiz, hed: true, n0: n, b0: null };
        try { katman.setPointerCapture(e.pointerId); } catch (x) { /* eski tarayıcı */ }
        return;
      }
      if (liste.length >= BOLGE_EN_COK) { dolu.hidden = false; return; }
      e.preventDefault();
      surukle = { tur: 'ciz', n0: n, b0: null };
      try { katman.setPointerCapture(e.pointerId); } catch (x) { /* eski tarayıcı */ }
    });
    katman.addEventListener('pointermove', function (e) {
      if (!surukle) return;
      var n = nokta(e), s0 = surukle, b;
      if (s0.tur === 'ciz') {
        var x1 = Math.min(s0.n0.x, n.x), y1 = Math.min(s0.n0.y, n.y), g = Math.abs(n.x - s0.n0.x), y2 = Math.abs(n.y - s0.n0.y);
        if (!s0.cizim) {
          if (g < 0.01 && y2 < 0.01) return;       // titreme: henüz çizim sayma
          liste.push({ x: x1, y: y1, g: g, y2: y2, tur: 'diger', ad: '' });
          s0.i = liste.length - 1; s0.cizim = true; secili = s0.i;
          kutulariCiz();
        }
        b = liste[s0.i]; b.x = x1; b.y = y1; b.g = g; b.y2 = y2;
      } else if (s0.tur === 'hedefciz') {
        var hx1 = Math.min(s0.n0.x, n.x), hy1 = Math.min(s0.n0.y, n.y), hg = Math.abs(n.x - s0.n0.x), hy2 = Math.abs(n.y - s0.n0.y);
        if (!s0.cizim && hg < 0.01 && hy2 < 0.01) return;
        s0.cizim = true; b = liste[s0.i].hedef = { x: hx1, y: hy1, g: hg, y2: hy2 };
      } else if (s0.tur === 'tasi') {
        b = s0.hed ? liste[s0.i].hedef : liste[s0.i];
        b.x = sinir(s0.b0.x + n.x - s0.n0.x, 0, 1 - b.g); b.y = sinir(s0.b0.y + n.y - s0.n0.y, 0, 1 - b.y2);
      } else {
        b = s0.hed ? liste[s0.i].hedef : liste[s0.i];
        var o0 = s0.b0, solSag = s0.tm.indexOf('w') >= 0, ustAlt = s0.tm.indexOf('n') >= 0;
        var sabitX = solSag ? o0.x + o0.g : o0.x, sabitY = ustAlt ? o0.y + o0.y2 : o0.y;   // karşı köşe sabit
        b.x = Math.min(sabitX, n.x); b.g = Math.abs(n.x - sabitX); b.y = Math.min(sabitY, n.y); b.y2 = Math.abs(n.y - sabitY);
      }
      s0.oynadi = true;
      var sel = (s0.hed ? '[data-hedef="' : '[data-bolge="') + s0.i + '"]';
      var el = katman.querySelector(sel);
      if (!el) { kutulariCiz(); el = katman.querySelector(sel); }
      el.style.left = b.x * 100 + '%'; el.style.top = b.y * 100 + '%'; el.style.width = b.g * 100 + '%'; el.style.height = b.y2 * 100 + '%';
      baglantiCiz(); onizlemeCiz();
    });
    function birak(e) {
      if (!surukle) return;
      var s0 = surukle; surukle = null;
      try { katman.releasePointerCapture(e.pointerId); } catch (x) { /* yok say */ }
      if (s0.tur === 'hedefciz' && s0.cizim) modKapat();
      if (s0.i != null && liste[s0.i]) {
        var b = s0.hed ? liste[s0.i].hedef : liste[s0.i];
        if (s0.tur === 'ciz' && (b.g < BOLGE_MIN_G || b.y2 < BOLGE_MIN_Y)) { liste.splice(s0.i, 1); secili = -1; }   // çok küçük: kaza ile çizilmiş
        else {
          duzelt(b);
          if (s0.tur === 'ciz') { b.tur = turTahmin(b); b.ad = t('bolge.ad.' + b.tur); b.hedef = varsayilanHedef(b.tur); b.olcek = 1; }
        }
      }
      hepsiniCiz();
      if (s0.oynadi) bildir();
      odakla(secili >= 0 ? katman.querySelector((s0.hed ? '[data-hedef="' : '[data-bolge="') + secili + '"]') : null);
    }
    katman.addEventListener('pointerup', birak);
    katman.addEventListener('pointercancel', birak);

    function kareYukle() {
      mesaj.textContent = ''; mesaj.appendChild(yukleniyor(t('bolge.yukleniyor'), 'bolge-bekle'));
      return kareAl().then(function (url) { return resimYukle(resim, url); }).then(function () {
        sahne.hidden = false; mesaj.textContent = ''; hepsiniCiz();
        if (ls('bolge_ipucu') !== '1' && !liste.length) ipucuPerde.hidden = false;
      }).catch(function (e) {
        sahne.hidden = true; mesaj.textContent = '';
        mesaj.appendChild(hataKutusu(e, 'bolge-hata', [{ id: 'bolge-hata-tekrar', ad: t('bolge.yenile'), f: kareYukle }]));
      });
    }
    function oner() {
      var once = (S.okunan && S.okunan.length) ? Promise.resolve(S.okunan)
        : api('GET', '/api/okuma-dene', undefined, 25000).then(function (r) { S.okunan = (r && r.satirlar) || []; return S.okunan; });
      mesaj.textContent = ''; mesaj.appendChild(yukleniyor(t('bolge.oneriyor'), 'bolge-bekle'));
      return once.then(function (satirlar) {
        mesaj.textContent = '';
        var yeni = okunandanOner(satirlar || []);
        if (!yeni.length) { mesaj.appendChild(h('div', { class: 'ipucu', id: 'bolge-oner-yok', text: t('bolge.oner_yok') })); return; }
        liste = yeni.map(bolgeIlkle); secili = -1; modKapat(); ipucuKapat(); popKapat(false); hepsiniCiz(); bildir();
        mesaj.appendChild(h('p', { class: 'bilgi-satir', id: 'bolge-onerildi', text: t('bolge.onerildi', { n: yeni.length }) }));
      }).catch(function (e) { mesaj.textContent = ''; mesaj.appendChild(hataKutusu(e, 'bolge-oner-hata', [{ id: 'bolge-oner-tekrar', ad: t('genel.tekrar'), f: oner }])); });
    }
    function kaydet(otomatikMi) {
      var temiz = otomatikMi ? [] : liste.slice(0, BOLGE_EN_COK).map(function (b) {
        var hd = hedefGecerli(b.hedef) ? { x: yuvarla(b.hedef.x), y: yuvarla(b.hedef.y), g: yuvarla(b.hedef.g), y2: yuvarla(b.hedef.y2) } : (b.hedef === 'altyazi' ? 'altyazi' : 'ustune');
        return { x: yuvarla(b.x), y: yuvarla(b.y), g: yuvarla(b.g), y2: yuvarla(b.y2), tur: b.tur, ad: b.ad || t('bolge.ad.' + b.tur), hedef: hd, olcek: olcekSinir(b.olcek) };
      });
      kaydetBtn.disabled = true;
      return api('POST', '/api/ayarlar', { bolgeler: temiz }).then(function () {
        kaydetBtn.disabled = false;
        if (S.ayarlar) S.ayarlar.bolgeler = temiz;
        mesaj.textContent = '';
        if (o.kaydedildi) o.kaydedildi(temiz.length);
      }).catch(function (e) {
        kaydetBtn.disabled = false; mesaj.textContent = '';
        mesaj.appendChild(hataKutusu(e, 'bolge-kayit-hata', [{ id: 'bolge-kayit-tekrar', ad: t('genel.tekrar'), f: function () { kaydet(otomatikMi); } }]));
      });
    }
    function otomatik() { liste = []; secili = -1; modKapat(); popKapat(false); hepsiniCiz(); return kaydet(true); }

    kok.appendChild(h('div', { class: 'bolge-rehber', id: 'bolge-rehber' }, [
      h('p', { text: t('bolge.rehber1') }), h('p', { class: 'sessiz', text: t('bolge.rehber2') })]));
    kok.appendChild(h('div', { class: 'bolge-arac' }, [
      h('div', { class: 'satir' }, [
        h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'bolge-oner', onclick: oner }, [ikon('goz'), h('span', { text: t('bolge.oner') })]),
        h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'bolge-yenile', onclick: kareYukle }, [ikon('yenile'), h('span', { text: t('bolge.yenile') })])
      ]),
      sayac
    ]));
    kok.appendChild(mesaj);
    kok.appendChild(modBar);
    kok.appendChild(sahne);
    kok.appendChild(h('p', { class: 'sessiz bolge-ipucu-satir', text: t('bolge.ipucu') + ' ' + t('bolge.ipucu_hedef') }));
    kok.appendChild(dolu);
    kok.appendChild(satirlar);
    kok.appendChild(h('div', { class: 'satir bolge-kayit', style: 'margin-top:16px' }, [
      kaydetBtn,
      h('button', { type: 'button', class: 'dugme ikincil', id: 'bolge-otomatik', text: t('bolge.otomatik'), onclick: otomatik })
    ]));
    hepsiniCiz();
    return { el: kok, yukle: kareYukle, kapat: function () {} };
  }

  // ---------- TÜRKÇE DUBLAJ (deneysel, PROTOKOL 9) ----------
  var DUBLAJ_MOTORLAR = ['kapali', 'chatterbox', 'pocket', 'elevenlabs'];
  var dublajKok = null, dublajImza = '', dublajMesaj = '';
  function dublajAyar() { return (S.ayarlar && S.ayarlar.dublaj) || {}; }
  function dublajSecim() { return S.dublajSecim || dublajAyar().motor || 'kapali'; }
  function dublajYukle() {
    return Promise.all([
      api('GET', '/api/dublaj').then(function (b) { S.dublaj = b; }),
      api('GET', '/api/dublaj/video').then(function (v) { S.dublajVideo = v; }).catch(function () {})
    ]).then(function () { dublajCiz(); return S.dublaj; }).catch(function () {});
  }
  function profilYukle() {
    return api('GET', '/api/dublaj/ses-profilleri').then(function (p) { S.dublajProfil = p; dublajImza = ''; dublajCiz(); }).catch(function () {});
  }
  function girisYukle() {
    return api('GET', '/api/dublaj/girisler').then(function (g) { S.dublajGiris = g.girisler || []; dublajImza = ''; dublajCiz(); }).catch(function () {});
  }
  function sureYaz(sn) {
    if (sn == null) return '';
    if (sn < 90) return t('dublaj.sure.sn', { n: Math.max(1, Math.round(sn)) });
    if (sn < 5400) return t('dublaj.sure.dk', { n: Math.round(sn / 60) });
    return t('dublaj.sure.sa', { n: (sn / 3600).toFixed(1).replace('.', ',') });
  }
  function gbYaz(mb) { return (Math.round(mb / 102.4) / 10).toFixed(1).replace('.', ','); }
  function ilerlemeCubugu(id, yuzde, gizli, etiket) {
    var bar = h('div', { class: 'ilerleme', role: 'progressbar', 'aria-label': etiket, 'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-valuenow': String(Math.round(yuzde || 0)), id: id, hidden: !!gizli }, h('i'));
    bar.firstChild.style.width = Math.round(yuzde || 0) + '%';
    return bar;
  }
  // 1) Dublaj paketi (PROTOKOL 14.1): onay, boyut, aşamalar, iptal, kaldır
  function dublajPaketCiz(k, b) {
    var pk = b.paket; if (!pk) return;
    var bol = h('div', { class: 'bolum dublaj-adim', id: 'dublaj-paket' });
    bol.appendChild(h('h3', { class: 'ara-baslik', text: t('dublaj.paket.baslik') }));
    if (!pk.destek) { bol.appendChild(h('p', { class: 'not', id: 'dublaj-paket-yok', text: pk.mesaj_hata || t('dublaj.paket.destek_yok') })); k.appendChild(bol); return; }
    if (pk.kurulu && pk.tamam) {
      bol.appendChild(h('p', { class: 'sessiz', id: 'dublaj-paket-durum', role: 'status', text: t(pk.gelistirici ? 'dublaj.paket.hazir_gel' : 'dublaj.paket.hazir') }));
      bol.appendChild(h('details', { class: 'kucuk-ac', id: 'dublaj-paket-kaldir-ac' }, [
        h('summary', { text: t('dublaj.paket.kaldir') }),
        h('p', { class: 'sessiz', text: t('dublaj.paket.kaldir.k', { konum: pk.konum }) }),
        h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'dublaj-paket-kaldir', text: t('dublaj.paket.kaldir.evet'), onclick: function () {
          api('POST', '/api/dublaj/paket/kaldir', { onay: true }, 60000).then(function () { toast(t('dublaj.paket.kaldirildi')); dublajImza = ''; return dublajYukle(); }).catch(hataGoster);
        } })
      ]));
      k.appendChild(bol); return;
    }
    var suruyor = pk.durum === 'kuruluyor';
    bol.appendChild(h('p', { class: 'ne', text: t('dublaj.paket.ne') }));
    bol.appendChild(h('p', { class: 'sessiz', id: 'dublaj-paket-boyut', text: t('dublaj.paket.boyut', { gb: gbYaz(pk.indirme_mb), disk: gbYaz(pk.disk_mb) }) }));
    var liste = h('ol', { class: 'asama-liste', id: 'dublaj-paket-asamalar' });
    (pk.asamalar || []).forEach(function (a) {
      liste.appendChild(h('li', { class: 'asama-' + a.durum, 'data-asama': a.kod }, [
        h('span', { text: t('dublaj.paket.a.' + a.kod) }),
        h('span', { class: 'sessiz', text: a.durum === 'bitti' ? ' ✓' : (a.durum === 'suruyor' ? ' %' + a.yuzde : (a.durum === 'hata' ? ' ✗' : '')) })]));
    });
    bol.appendChild(liste);
    if (suruyor) {
      bol.appendChild(ilerlemeCubugu('dublaj-paket-ilerleme', pk.yuzde, false, t('dublaj.paket.baslik')));
      bol.appendChild(h('p', { class: 'sessiz', id: 'dublaj-paket-durum', role: 'status', 'aria-live': 'polite', text: t('dublaj.paket.suruyor', { n: pk.yuzde }) + (pk.mesaj ? ' · ' + pk.mesaj : '') }));
      bol.appendChild(h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'dublaj-paket-iptal', text: t('dublaj.paket.iptal'), onclick: function () {
        api('POST', '/api/dublaj/paket/iptal', {}, 30000).then(function () { dublajImza = ''; return dublajYukle(); }).catch(hataGoster);
      } }));
    } else {
      if (pk.durum === 'hata' && pk.mesaj_hata) bol.appendChild(h('p', { class: 'not', id: 'dublaj-paket-hata', role: 'alert', text: pk.mesaj_hata }));
      if (pk.durum === 'iptal') bol.appendChild(h('p', { class: 'sessiz', text: t('dublaj.paket.durdu') }));
      var onay = h('input', { type: 'checkbox', id: 'dublaj-paket-onay' });
      var kur = h('button', { type: 'button', class: 'dugme kucuk', id: 'dublaj-paket-kur', disabled: true, text: t(pk.yuzde > 0 ? 'dublaj.paket.surdur' : 'dublaj.paket.kur'), onclick: function () {
        api('POST', '/api/dublaj/paket/kur', { onay: true }).then(function (r) { S.dublaj.paket = r; dublajImza = ''; dublajCiz(); }).catch(hataGoster);
      } });
      onay.addEventListener('change', function () { kur.disabled = !onay.checked; });
      bol.appendChild(h('label', { class: 'onay-satir', for: 'dublaj-paket-onay' }, [onay, h('span', { text: t('dublaj.paket.onay', { gb: gbYaz(pk.indirme_mb) }) })]));
      bol.appendChild(h('div', { class: 'satir' }, [kur]));
    }
    k.appendChild(bol);
  }
  // 2) Canlı dublaj ayarları (PROTOKOL 14.3/14.5)
  function dublajCanliCiz(k, b, a) {
    var cikis = a.cikis || 'bilgisayar';
    if (cikis === 'tv') {
      k.appendChild(h('div', { class: 'bilgi-kutu', id: 'dublaj-diyalog-ipucu' }, [
        h('strong', { text: t('dublaj.diyalog.baslik') }), h('p', { text: t('dublaj.diyalog.k') })]));
    } else {
      k.appendChild(h('h3', { class: 'ara-baslik', text: t('dublaj.orijinal') }));
      var ol = h('div', { class: 'liste', role: 'group', 'aria-label': t('dublaj.orijinal') });
      ['otomatik', 'kis', 'tamamen_turkce'].forEach(function (o) {
        ol.appendChild(h('button', { type: 'button', class: 'sec', id: 'dublaj-orijinal-' + o, 'aria-pressed': String((a.orijinal_ses || 'otomatik') === o), onclick: function () { dublajKaydet({ orijinal_ses: o }); } }, [
          h('span', { class: 'sec-ad', text: t('dublaj.orijinal.' + o) }), h('span', { class: 'sec-alt', text: t('dublaj.orijinal.' + o + '.k') })]));
      });
      k.appendChild(ol);
      if (b.tamamen_turkce && !b.tamamen_turkce_destek) k.appendChild(h('p', { class: 'not', text: t('dublaj.orijinal.destek_yok') }));
      var gl = S.dublajGiris;
      if (b.isci) {
        var sec = h('select', { id: 'dublaj-giris', 'aria-label': t('dublaj.giris'), onchange: function () { dublajKaydet({ ses_girisi: sec.value }); } },
          [h('option', { value: '', text: t('dublaj.giris.yok') })].concat((gl || []).map(function (g) { return h('option', { value: g.kimlik, text: g.ad + (g.kart ? ' ★' : '') }); })));
        sec.value = a.ses_girisi || '';
        k.appendChild(h('div', { style: 'margin-top:8px' }, [h('label', { class: 'etiket', for: 'dublaj-giris', text: t('dublaj.giris') }), sec,
          h('p', { class: 'sessiz', text: t('dublaj.giris.k') }),
          gl ? null : h('button', { type: 'button', class: 'baglanti', id: 'dublaj-giris-yukle', text: t('dublaj.giris.listele'), onclick: girisYukle })]));
      }
    }
    k.appendChild(anahtar(t('dublaj.profil'), t('dublaj.profil.k'), a.ses_profili_izni, function (v) { dublajKaydet({ ses_profili_izni: v }).then(profilYukle); }, 'dublaj-profil-izin'));
    var pr = S.dublajProfil;
    if (pr && pr.profiller && pr.profiller.length) {
      var pl = h('ul', { class: 'profil-liste', id: 'dublaj-profiller' });
      pr.profiller.forEach(function (p) {
        pl.appendChild(h('li', {}, [h('span', { text: p.ad + ' · ' + t('dublaj.sure.sn', { n: Math.round(p.sure_sn) }) }),
          h('button', { type: 'button', class: 'baglanti', 'aria-label': t('dublaj.profil.sil_ad', { ad: p.ad }), text: t('dublaj.profil.sil'), onclick: function () {
            api('DELETE', '/api/dublaj/ses-profilleri?ad=' + encodeURIComponent(p.ad)).then(profilYukle).catch(hataGoster);
          } })]));
      });
      k.appendChild(pl);
      k.appendChild(h('button', { type: 'button', class: 'baglanti', id: 'dublaj-profil-hepsi', text: t('dublaj.profil.hepsi'), onclick: function () {
        api('DELETE', '/api/dublaj/ses-profilleri').then(function () { toast(t('dublaj.profil.silindi')); return profilYukle(); }).catch(hataGoster);
      } }));
    }
    k.appendChild(anahtar(t('dublaj.hafif'), t('dublaj.hafif.k'), a.hafif_mod === 'acik', function (v) { dublajKaydet({ hafif_mod: v ? 'acik' : 'kapali' }); }, 'dublaj-hafif'));
    var g = b.gecikme;
    if (g && g.son) {
      var s2 = g.son, parcalar = [];
      if (s2.erken) parcalar.push(t('dublaj.gecikme.erken'));
      if (g.ortalama_bekleme_ms != null) parcalar.push(t('dublaj.gecikme.ort', { n: (g.ortalama_bekleme_ms / 1000).toFixed(1).replace('.', ',') }));
      ['stt_ms', 'ceviri_ms', 'ses_ms', 'ilk_ses_ms'].forEach(function (x) { if (s2[x] != null) parcalar.push(t('dublaj.gecikme.' + x, { n: s2[x] })); });
      k.appendChild(h('p', { class: 'sessiz', id: 'dublaj-gecikme', text: parcalar.join(' · ') }));
    }
  }
  // PROTOKOL 14.6 "Dublaj tanı": hangi cihazda çalışıyor (ekran kartı / işlemci + Onar) ve son 5 satır
  function dublajTaniCiz(k, b) {
    var tn = b.tani, c, d, sat, liste, on;
    if (!tn || (!tn.cihaz && !(tn.satirlar && tn.satirlar.length))) return;
    on = tn.onarim || {};
    d = h('div', { class: 'dublaj-tani', id: 'dublaj-tani' });
    d.appendChild(h('h4', { class: 'ara-baslik', text: t('dublaj.tani.baslik') }));
    c = tn.cihaz || {};
    if (c.cihaz === 'cuda') {
      d.appendChild(h('p', { class: 'tamam', id: 'dublaj-tani-cihaz', text: t('dublaj.tani.gpu', { kart: c.ekran_karti || 'GPU' }) }));
    } else if (tn.uyari) {
      d.appendChild(h('p', { class: 'uyari', id: 'dublaj-tani-cihaz', role: 'status', text: t('dublaj.tani.' + tn.uyari, { kart: c.ekran_karti || '' }) }));
      if (on.durum === 'suruyor') {
        d.appendChild(h('p', { class: 'sessiz', id: 'dublaj-tani-onarim', text: t('dublaj.tani.onariliyor') }));
      } else if (tn.onarilabilir) {
        d.appendChild(h('button', { type: 'button', class: 'dugme', id: 'dublaj-onar', text: t('dublaj.tani.onar'), onclick: function () {
          api('POST', '/api/dublaj/onar', {}, 20000).then(function (r) { S.dublaj = r; dublajImza = ''; dublajCiz(); }).catch(hataGoster);
        } }));
        if (on.durum === 'hata') d.appendChild(h('p', { class: 'hata', text: t('dublaj.tani.onarim_hata') }));
      }
    } else if (c.cihaz) {
      d.appendChild(h('p', { class: 'sessiz', id: 'dublaj-tani-cihaz', text: t('dublaj.tani.cihaz', { cihaz: c.cihaz }) }));
    }
    if (tn.satirlar && tn.satirlar.length) {
      liste = h('ul', { class: 'dublaj-tani-satirlar', id: 'dublaj-tani-satirlar' });
      tn.satirlar.forEach(function (x) {
        var p = [];
        if (x.atildi) p.push(t('dublaj.tani.atildi', { neden: t('dublaj.tani.neden.' + x.atildi) }));
        else if (x.ilk_ses_ms != null) p.push(t('dublaj.tani.gecikme', { n: (x.ilk_ses_ms / 1000).toFixed(1).replace('.', ',') }));
        else if (x.bekleme_ms != null) p.push(t('dublaj.tani.gecikme', { n: (x.bekleme_ms / 1000).toFixed(1).replace('.', ',') }));
        if (x.ref_tur) p.push(t('dublaj.tani.ref.' + (String(x.ref_tur).indexOf('yerlesik') === 0 ? 'yerlesik' : x.ref_tur), { n: x.ref_sn != null ? String(x.ref_sn).replace('.', ',') : '0' }));
        if (x.cinsiyet) p.push(t('dublaj.tani.cins.' + x.cinsiyet));
        if (x.uretim_ms != null) p.push(t('dublaj.gecikme.ses_ms', { n: x.uretim_ms }));
        sat = h('li', { text: p.join(' · ') || '—' });
        liste.appendChild(sat);
      });
      d.appendChild(liste);
    }
    k.appendChild(d);
  }
  // 3) Videoyu Türkçe dublajla (PROTOKOL 14.4)
  function dublajVideoCiz(k, b) {
    var v = S.dublajVideo || { durum: 'bosta' }, pk = b.paket || {};
    var bol = h('section', { class: 'bolum dublaj-video', id: 'dublaj-video', 'aria-labelledby': 'dublaj-video-baslik' });
    bol.appendChild(h('h3', { class: 'ara-baslik', id: 'dublaj-video-baslik', text: t('dublaj.video.baslik') }));
    bol.appendChild(h('p', { class: 'sessiz', text: t('dublaj.video.ne') }));
    if (!pk.kurulu) { bol.appendChild(h('p', { class: 'sessiz', id: 'dublaj-video-paket', text: t('dublaj.video.paket_once') })); k.appendChild(bol); return; }
    var calisiyor = v.durum === 'calisiyor';
    var secilen = S.dublajVideoSecim;
    if (!calisiyor) {
      bol.appendChild(h('div', { class: 'satir' }, [
        h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'dublaj-video-sec', text: t('dublaj.video.sec'), onclick: function () {
          api('POST', '/api/dublaj/dosya-sec', {}, 610000).then(function (r) { if (r && r.yol) { S.dublajVideoSecim = r; dublajImza = ''; dublajCiz(); } }).catch(hataGoster);
        } }),
        secilen ? h('span', { class: 'sessiz', id: 'dublaj-video-dosya', text: secilen.ad + ' · ' + secilen.boyut_mb + ' MB' }) : null,
        h('button', { type: 'button', class: 'dugme kucuk', id: 'dublaj-video-basla', disabled: !secilen, text: t(v.devam_edilebilir ? 'dublaj.video.surdur' : 'dublaj.video.basla'), onclick: function () {
          api('POST', '/api/dublaj/video', { yol: secilen.yol }).then(function (r) { S.dublajVideo = r; dublajImza = ''; dublajCiz(); }).catch(hataGoster);
        } })
      ]));
    }
    if (v.durum !== 'bosta') {
      bol.appendChild(h('p', { class: 'sessiz', id: 'dublaj-video-durum', role: 'status', 'aria-live': 'polite', text:
        (v.ad ? v.ad + ' · ' : '') + t('dublaj.video.d.' + v.durum) + (calisiyor ? ' · %' + v.yuzde + (v.kalan_sn != null ? ' · ' + t('dublaj.video.kalan', { s: sureYaz(v.kalan_sn) }) : '') : '') }));
      if (calisiyor) bol.appendChild(ilerlemeCubugu('dublaj-video-ilerleme', v.yuzde, false, t('dublaj.video.baslik')));
      var al = h('ol', { class: 'asama-liste', id: 'dublaj-video-asamalar' });
      (v.asamalar || []).forEach(function (a) {
        var ek = a.durum === 'suruyor' ? ' %' + a.yuzde : (a.durum === 'bitti' ? ' ✓' : '');
        if (a.kod === 'seslendir' && a.durum === 'suruyor' && v.satir && v.satir.toplam) ek = ' ' + v.satir.bitti + '/' + v.satir.toplam;
        if (a.kod === 'konusmaci' && a.durum === 'bitti' && v.konusmaci_sayisi) ek += ' (' + t('dublaj.video.karakter', { n: v.konusmaci_sayisi }) + ')';
        al.appendChild(h('li', { class: 'asama-' + a.durum, 'data-asama': a.kod }, [h('span', { text: t('dublaj.video.a.' + a.kod) }), h('span', { class: 'sessiz', text: ek })]));
      });
      bol.appendChild(al);
      if (calisiyor) bol.appendChild(h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'dublaj-video-iptal', text: t('dublaj.video.iptal'), onclick: function () {
        api('POST', '/api/dublaj/video/iptal', {}, 30000).then(function (r) { S.dublajVideo = r; dublajImza = ''; dublajCiz(); }).catch(hataGoster);
      } }));
      if (v.durum === 'hata' && v.mesaj) bol.appendChild(h('p', { class: 'not', id: 'dublaj-video-hata', role: 'alert', text: v.mesaj }));
      if (v.durum === 'bitti') bol.appendChild(h('div', { class: 'satir' }, [
        h('span', { class: 'sessiz', id: 'dublaj-video-cikti', text: t('dublaj.video.hazir', { ad: (v.cikti || '').split(/[\\/]/).pop() }) }),
        h('button', { type: 'button', class: 'dugme kucuk', id: 'dublaj-video-goster', text: t('dublaj.video.goster'), onclick: function () { api('POST', '/api/dublaj/video/goster', {}).catch(hataGoster); } })]));
    }
    bol.appendChild(h('p', { class: 'sessiz', text: t('dublaj.video.yasal') }));
    k.appendChild(bol);
  }
  function dublajKaydet(parca) {
    if (S.ayarlar) S.ayarlar.dublaj = Object.assign({}, dublajAyar(), parca);
    return api('POST', '/api/dublaj', parca).then(function (r) {
      if (r && r.dublaj && S.ayarlar) S.ayarlar.dublaj = r.dublaj;
      S.dublajSecim = null; return dublajYukle();
    }).catch(function (e) { hataGoster(e); return ayarYukle().then(dublajYukle); });
  }
  function dublajKarti() {
    dublajKok = h('div', { class: 'dublaj-ic', id: 'dublaj-ic' });
    dublajImza = '';
    dublajCiz();
    dublajYukle();
    profilYukle();
    return dublajKok;
  }
  function dublajCiz() {
    if (!dublajKok || !document.body.contains(dublajKok) && dublajKok.dataset.kuruldu) return;
    var b = S.dublaj || {}, a = dublajAyar(), sec = dublajSecim(), ind = b.indirme || {};
    var pk = b.paket || {}, vd = S.dublajVideo || {};
    var imza = [sec, b.hazir, b.onerilen, b.ekran_karti, ind.durum, ind.yuzde, ind.hata, b.son_hata, b.elevenlabs_anahtar,
      a.elevenlabs_onay, a.elevenlabs_klon_onay, a.cikis, dublajMesaj, dil, a.orijinal_ses, a.hafif_mod, a.ses_profili_izni, a.ses_girisi,
      pk.durum, pk.yuzde, pk.kurulu, pk.tamam, pk.mesaj, JSON.stringify(pk.asamalar || []), b.tamamen_turkce, JSON.stringify(b.gecikme || null), JSON.stringify(b.tani || null),
      vd.durum, vd.yuzde, vd.kalan_sn, vd.asama, vd.satir && vd.satir.bitti, vd.cikti, vd.mesaj, S.dublajVideoSecim && S.dublajVideoSecim.yol].join('|');
    if (imza === dublajImza) return;   // değişmediyse yeniden çizme (yazı/odak kaybolmasın)
    dublajImza = imza;
    var k = dublajKok; k.dataset.kuruldu = '1'; k.textContent = '';
    var oz = $('#dublaj-ozet'); if (oz) oz.textContent = t('dublaj.' + (a.motor || 'kapali')) + (a.motor && a.motor !== 'kapali' && b.hazir ? ' · ' + t('dublaj.hazir') : '');
    k.appendChild(h('p', { class: 'ne', id: 'dublaj-ne', text: t('dublaj.ne') }));
    k.appendChild(h('p', { class: 'sessiz', text: t('dublaj.gecikme') }));
    dublajPaketCiz(k, b);
    if (b.motor !== undefined) {
      k.appendChild(h('p', { class: 'sessiz', id: 'dublaj-donanim', text: b.ekran_karti ? t('dublaj.donanim', { kart: b.ekran_karti + (b.vram_gb ? ' (' + b.vram_gb + ' GB)' : '') }) : t('dublaj.donanim_yok') }));
    }
    dublajTaniCiz(k, b);
    var liste = h('div', { class: 'liste', role: 'group', 'aria-label': t('dublaj.motor') });
    DUBLAJ_MOTORLAR.forEach(function (m) {
      liste.appendChild(h('button', { type: 'button', class: 'sec', id: 'dublaj-motor-' + m, 'data-motor': m, 'aria-pressed': String(sec === m), onclick: function () {
        if (m === 'elevenlabs' && !a.elevenlabs_onay) { S.dublajSecim = 'elevenlabs'; dublajMesaj = ''; dublajImza = ''; dublajCiz(); return; }   // önce onay
        S.dublajSecim = null; dublajMesaj = ''; dublajKaydet({ motor: m });
      } }, [
        h('span', { class: 'sec-ad' }, [t('dublaj.' + m), b.onerilen === m ? h('span', { class: 'rozet sari', text: t('dublaj.onerilen') }) : null]),
        h('span', { class: 'sec-alt', text: t('dublaj.' + m + '.k') })
      ]));
    });
    k.appendChild(liste);

    if (sec === 'elevenlabs') {
      var anah = h('input', { type: 'password', id: 'dublaj-eleven-anahtar', autocomplete: 'off', spellcheck: 'false', 'aria-label': t('dublaj.eleven.anahtar'),
        placeholder: b.elevenlabs_anahtar ? t('dublaj.eleven.anahtar_kayitli') : 'xi-…' });
      var ses = h('input', { type: 'text', id: 'dublaj-eleven-ses', autocomplete: 'off', value: a.elevenlabs_ses_kimligi || '', 'aria-label': t('dublaj.eleven.ses'), onchange: function () { dublajKaydet({ elevenlabs_ses_kimligi: ses.value.trim() }); } });
      k.appendChild(h('div', { class: 'bolum', id: 'dublaj-eleven' }, [
        h('label', { class: 'etiket', for: 'dublaj-eleven-anahtar', text: t('dublaj.eleven.anahtar') }),
        h('div', { class: 'satir' }, [anah, h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'dublaj-eleven-kaydet', text: t('dublaj.eleven.kaydet'), onclick: function () {
          if (!anah.value.trim()) return;
          api('POST', '/api/anahtar', { motor: 'elevenlabs', anahtar: anah.value.trim() }).then(function () { anah.value = ''; return dublajYukle(); }).catch(hataGoster);
        } })]),
        anahtar(t('dublaj.eleven.onay'), null, a.elevenlabs_onay, function (v) {
          if (v) dublajKaydet({ elevenlabs_onay: true, motor: 'elevenlabs' }); else dublajKaydet({ elevenlabs_onay: false, elevenlabs_klon_onay: false });
        }, 'dublaj-eleven-onay'),
        a.elevenlabs_onay ? anahtar(t('dublaj.eleven.klon'), null, a.elevenlabs_klon_onay, function (v) { dublajKaydet({ elevenlabs_klon_onay: v }); }, 'dublaj-eleven-klon') : null,
        a.elevenlabs_onay ? h('label', { class: 'etiket', for: 'dublaj-eleven-ses', text: t('dublaj.eleven.ses') }) : null,
        a.elevenlabs_onay ? ses : null,
        a.elevenlabs_onay ? h('p', { class: 'sessiz', text: t('dublaj.eleven.ses.k') }) : null
      ]));
    }

    if (sec !== 'kapali' && (sec !== 'elevenlabs' || a.elevenlabs_onay)) {
      var surer = ind.durum === 'indiriliyor' || ind.durum === 'yukleniyor';
      var durumMetin = surer ? (ind.durum === 'yukleniyor' ? t('dublaj.yukleniyor') : t('dublaj.indiriliyor', { n: ind.yuzde || 0 }))
        : (b.hazir ? t('dublaj.hazir') : (ind.hata && ind.mesaj ? ind.mesaj : t('dublaj.hazir_degil')));
      var bar = h('div', { class: 'ilerleme', role: 'progressbar', 'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-valuenow': String(ind.yuzde || 0), id: 'dublaj-ilerleme', hidden: !surer }, h('i'));
      bar.firstChild.style.width = (ind.yuzde || 0) + '%';
      k.appendChild(h('div', { class: 'satir', style: 'margin-top:16px' }, [
        h('button', { type: 'button', class: 'dugme kucuk', id: 'dublaj-hazirla', disabled: surer, text: t('dublaj.hazirla'), onclick: function () {
          dublajMesaj = ''; api('POST', '/api/dublaj/hazirla', {}).then(function (r) { S.dublaj = r; dublajYukle(); }).catch(hataGoster);
        } }),
        h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'dublaj-dene', disabled: !b.hazir || surer, text: t('dublaj.dene'), onclick: function () {
          api('POST', '/api/dublaj/dene', { metin: t('dublaj.dene_metin') }).then(function () { toast(t('dublaj.dene_tamam')); }).catch(hataGoster);
        } }),
        h('span', { class: 'sessiz', id: 'dublaj-durum', role: 'status', 'aria-live': 'polite', text: durumMetin })
      ]));
      k.appendChild(bar);
      if (!b.hazir && !surer && !ind.hata) k.appendChild(h('p', { class: 'sessiz', text: t('dublaj.hazirla.k') }));
      if (b.son_hata_mesaj) k.appendChild(h('p', { class: 'not', id: 'dublaj-hata', role: 'alert', text: b.son_hata_mesaj }));

      var kisIlk = Math.round((1 - (a.oyun_sesi_kis == null ? 0.25 : a.oyun_sesi_kis)) * 100);
      var kis = h('input', { type: 'range', min: 0, max: 100, step: 5, id: 'dublaj-kis', value: kisIlk, 'aria-label': t('dublaj.kis') });
      var kisDeger = h('span', { class: 'sessiz', id: 'dublaj-kis-deger', text: t('dublaj.kis.deger', { n: kisIlk }) });
      var sev = h('input', { type: 'range', min: 20, max: 200, step: 10, id: 'dublaj-seviye', value: Math.round((a.ses_seviyesi == null ? 1 : a.ses_seviyesi) * 100), 'aria-label': t('dublaj.seviye') });
      var sevDeger = h('span', { class: 'sessiz', id: 'dublaj-seviye-deger', text: t('dublaj.kis.deger', { n: sev.value }) });
      var gecKis, gecSev;   // her kaydırıcının kendi gecikmesi (biri ötekini iptal etmesin)
      kis.addEventListener('input', function () { kisDeger.textContent = t('dublaj.kis.deger', { n: kis.value }); clearTimeout(gecKis); gecKis = setTimeout(function () { dublajKaydet({ oyun_sesi_kis: Math.round((100 - Number(kis.value))) / 100 }); }, 300); });
      sev.addEventListener('input', function () { sevDeger.textContent = t('dublaj.kis.deger', { n: sev.value }); clearTimeout(gecSev); gecSev = setTimeout(function () { dublajKaydet({ ses_seviyesi: Number(sev.value) / 100 }); }, 300); });
      k.appendChild(h('div', { class: 'iki', style: 'margin-top:8px' }, [
        h('div', {}, [h('label', { class: 'etiket', for: 'dublaj-kis', text: t('dublaj.kis') }), kis, kisDeger]),
        h('div', {}, [h('label', { class: 'etiket', for: 'dublaj-seviye', text: t('dublaj.seviye') }), sev, sevDeger])
      ]));
      k.appendChild(h('h3', { class: 'ara-baslik', text: t('dublaj.cikis') }));
      var cl = h('div', { class: 'liste', role: 'group', 'aria-label': t('dublaj.cikis') });
      ['bilgisayar', 'tv'].forEach(function (c) {
        cl.appendChild(h('button', { type: 'button', class: 'sec', id: 'dublaj-cikis-' + c, 'data-cikis': c, 'aria-pressed': String((a.cikis || 'bilgisayar') === c), onclick: function () { dublajKaydet({ cikis: c }); } }, [
          h('span', { class: 'sec-ad', text: t('dublaj.cikis.' + c) }), h('span', { class: 'sec-alt', text: t('dublaj.cikis.' + c + '.k') })
        ]));
      });
      k.appendChild(cl);
      if (b.paket && b.paket.kurulu && sec !== 'elevenlabs') dublajCanliCiz(k, b, a);
    }
    dublajVideoCiz(k, b);
    k.appendChild(h('p', { class: 'sessiz', style: 'margin-top:16px', text: t('dublaj.haklar') }));
  }

  // ---------- çizim ----------
  // ekran değişince yumuşak geçiş (ileri: sağdan, geri: soldan) ve odak yeni başlığa
  var SIRA = { asama1: 1, asama2: 2, asama3: 3, asama4: 4, asama5: 5, asama6: 6, ana: 7, oyun: 8, kisayol: 8, gelismis: 8, rehber: 9 };
  var sonEkran = null;
  function ekranAdi() {
    if (S.rehberEkrani) return 'rehber';
    if (S.tekAsama) return 'asama' + S.tekAsama;
    if (!S.kurulumBitti) return 'asama' + S.adim;
    return S.oyunDegis ? 'oyun' : (S.kisayolEkrani ? 'kisayol' : (S.gelismisEkrani ? 'gelismis' : 'ana'));
  }
  function ciz() {
    document.querySelectorAll('[data-i]').forEach(function (e) { e.textContent = t(e.dataset.i); });
    if (S.rehberEkrani) rehberEkrani();
    else if (S.tekAsama) sihirbaz(S.tekAsama);
    else if (S.kurulumBitti) anaEkran();
    else sihirbaz(S.adim);
    var ad = ekranAdi(), bolumEl = ana.firstElementChild;
    ana.classList.toggle('genis', ad === 'asama5');
    ana.classList.toggle('pano-ana', ad === 'ana');
    if (ad !== sonEkran && bolumEl) {
      var ilk = sonEkran === null;
      bolumEl.classList.add(ilk ? 'gecis-ilk' : ((SIRA[ad] || 0) >= (SIRA[sonEkran] || 0) ? 'gecis-ileri' : 'gecis-geri'));
      if (!ilk) {
        try { window.scrollTo({ top: 0, behavior: 'instant' }); } catch (e) { window.scrollTo(0, 0); }
        var b = bolumEl.querySelector('h1');
        if (b) { b.setAttribute('tabindex', '-1'); try { b.focus({ preventScroll: true }); } catch (e) { b.focus(); } }
      }
    }
    sonEkran = ad;
  }

  function tercihleriKur() {
    var tercih = $('#tercih'), by = $('#buyuk-yazi'), hz = $('#hareket-azalt');
    if (!tercih || !by || !hz) return;
    by.checked = kok.classList.contains('buyuk-yazi');
    hz.checked = hareketAz();
    by.addEventListener('change', function () { kok.classList.toggle('buyuk-yazi', by.checked); ls('buyuk_yazi', by.checked ? '1' : '0'); });
    hz.addEventListener('change', function () {
      kok.classList.toggle('hareket-az', hz.checked); kok.classList.toggle('hareket-acik', !hz.checked);
      ls('hareket_azalt', hz.checked ? '1' : '0');
    });
    var rm = $('#rehber-menu');
    if (rm) rm.addEventListener('click', function () { tercih.open = false; S.rehberEkrani = true; ciz(); });
    var kp = $('#program-kapat');
    if (kp) kp.addEventListener('click', function () {
      if (!window.confirm(t('tercih.kapat.onay'))) return;
      api('POST', '/api/kapat', {}, 5000).catch(function () {}).then(function () {
        document.body.textContent = '';
        document.body.appendChild(h('main', { class: 'kapandi' }, [h('h1', { text: t('tercih.kapat.bitti') }), h('p', { text: t('tercih.kapat.bitti.k') })]));
      });
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && tercih.open) { tercih.open = false; $('#tercih-ac').focus(); } });
    document.addEventListener('click', function (e) { if (tercih.open && !tercih.contains(e.target)) tercih.open = false; });
  }

  // ---------- başlangıç ----------
  function basla() {
    document.title = MARKA.ad;
    var ma = $('#marka-ad'); if (ma) ma.textContent = MARKA.ad;
    tercihleriKur();
    S.asama = asamaOku();
    document.querySelectorAll('.dil-dugme').forEach(function (b) { b.addEventListener('click', function () { dilDegistir(b.dataset.dil); }); });
    var ilk = ls('dil') || 'tr';
    if (ilk !== 'tr' && ilk !== 'en') ilk = 'tr';
    dilYukle('tr').then(function () { return dilYukle(ilk); }).then(function () { dilUygula(ilk); })
      .then(function () {
        return Promise.all([ayarYukle(), api('GET', '/api/motorlar').then(function (m) { S.motorlar = m; }), kaynakYukle().catch(function () {}), durumYukle()]);
      })
      .then(function () {
        if (S.ayarlar && S.ayarlar.kurulum_tamam && ls('kurulum') === null) S.kurulumBitti = true;
        if (S.ayarlar) {
          if (!S.cihaz && S.ayarlar.cihaz) S.cihaz = S.ayarlar.cihaz;
          if (!S.gosterim && S.ayarlar.gosterim) S.gosterim = S.ayarlar.gosterim;
        }
        var sd = S.ayarlar && S.ayarlar.arayuz_dili;
        if (sd && sd !== dil && (sd === 'tr' || sd === 'en')) return dilYukle(sd).then(function () { dilUygula(sd); });
      })
      .then(ciz)
      .catch(function (e) { hataGoster(e); ciz(); });
    setInterval(durumYukle, 2000);
    setTimeout(guncellemeYukle, 300); setTimeout(guncellemeYukle, 4000);   // ilk denetim arka planda biter
    setInterval(guncellemeYukle, 60000);
    setInterval(function () { if (S.durum && S.durum.calisiyor) listeYenile(); }, 3000);
    setInterval(function () { if (dublajKok && document.body.contains(dublajKok)) dublajYukle(); }, 2000);
  }
  basla();
})();
