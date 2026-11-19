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
    kare: '<rect x="4" y="5" width="16" height="14" rx="2" stroke-dasharray="3 2.4"/><path d="M8 15h8" stroke-width="2.4"/>'
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
    guncelleme: null, erisim: null, erisimAcik: false,
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
  function kaynakYukle() {
    return api('GET', '/api/kaynaklar').then(function (k) {
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
    var donusMetni = S.donus === 6 ? t('asama.hazira_don') : t('asama.ana_don');
    var kontrol = h('div', { class: 'dogrulama', id: 'dogrula-' + n, role: 'status', 'aria-live': 'polite', hidden: true });
    var devam = h('button', { type: 'button', class: 'dugme', id: 'ileri-' + n, disabled: !o.hazir, text: tek ? donusMetni : (o.devamMetni || t('sihirbaz.ileri')), onclick: function () {
      if (o.devamOnce) { var r = o.devamOnce(); if (r === false) return; }
      if (S.asama[n] !== 'tamam' && !o.devamSerbest) asamaYaz(n, 'tamam');
      ilerle(n);
    } });
    var atla = h('button', { type: 'button', class: 'baglanti', id: 'atla-' + n, text: t('asama.atla'), onclick: function () {
      if (S.asama[n] !== 'tamam') asamaYaz(n, 'atlandi');
      ilerle(n);
    } });
    var geri = (n > 1 && !tek) ? h('button', { type: 'button', class: 'dugme ikincil', id: 'geri-' + n, text: t('sihirbaz.geri'), onclick: function () { S.adim = n - 1; ciz(); } }) : null;
    var vazgec = tek ? h('button', { type: 'button', class: 'dugme ikincil', id: 'vazgec-' + n, text: t('asama.vazgec'), onclick: function () { donus(); } }) : null;
    var sorun = o.sorun ? h('details', { class: 'sorun-ac', id: 'sorun-' + n }, [h('summary', { text: t('asama.sorun') }), adimlar(o.sorun)]) : null;
    var bolumEl = h('section', { class: 'asama asama-' + n + (o.genis ? ' genis-asama' : '') }, [
      stepper(n),
      h('p', { class: 'asama-ust', text: t('asama.no', { n: n, m: ASAMALAR.length }) + ' · ' + t('asama.' + ASAMALAR[n - 1]) }),
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
      sifirla: function () { kontrol.hidden = true; kontrol.textContent = ''; devam.disabled = !o.hazir; }
    };
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
    var yenile = h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'kaynak-yenile', text: t('kaynak.yenile'), onclick: function () {
      kaynakDurum.textContent = ''; kaynakDurum.appendChild(yukleniyor(t('kaynak.araniyor')));
      kaynakYukle().then(function () { kaynakDurum.textContent = ''; kaynakCiz(); }).catch(function (e) {
        kaynakDurum.textContent = ''; kaynakDurum.appendChild(hataKutusu(e, 'kaynak-hata'));
      });
    } });
    var onizKart = h('div', { class: 'kart', id: 'onizleme-kart', hidden: true }, [
      h('div', { class: 'kart-bas' }, [h('h2', { text: t('goruntu.onizleme') }),
        h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'goruntu-yenile', text: t('goruntu.yenile'), onclick: function () { onizle(); } })]),
      sahne, durum
    ]);
    var kaynakKart = h('div', { class: 'kart', id: 'kaynak-kart', hidden: true }, [
      h('div', { class: 'kart-bas' }, [h('h2', { text: t('adim1.kaynak_baslik') }), yenile]), kaynakDurum, kaynakKutu]);
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
    function kaynakCiz() {
      kaynakKutu.textContent = '';
      if (!S.kaynaklar.length) { kaynakKutu.appendChild(h('p', { class: 'bos-durum', text: t('kaynak.bos') })); return; }
      S.kaynaklar.forEach(function (k) {
        kaynakKutu.appendChild(h('button', { type: 'button', class: 'sec', 'data-kaynak': k.kod, 'aria-pressed': String(S.kaynak === k.kod),
          onclick: function () { kaynakSec(k.kod); } }, [h('span', { class: 'sec-ad', text: k.ad }),
          h('span', { class: 'sec-alt', text: t(k.kod.indexOf('pencere') === 0 ? 'kaynak.tur.pencere' : 'kaynak.tur.ekran') })]));
      });
    }
    function kaynakSec(kod) {
      S.kaynak = kod; kaynakCiz(); onizKart.hidden = false; onizKart.classList.add('acil');
      api('POST', '/api/ayarlar', { kaynak: kod, cihaz: S.cihaz }).then(function () { S.ayarlar.kaynak = kod; S.ayarlar.cihaz = S.cihaz; }, function () {}).then(onizle);
    }
    function guncelle() {
      document.querySelectorAll('[data-cihaz]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.cihaz === S.cihaz)); });
      ipucu.hidden = !S.cihaz; kaynakKart.hidden = !S.cihaz;
      if (S.cihaz) ipucu.textContent = t('kaynak.ipucu.' + S.cihaz);
    }
    var cihazIzgara = h('div', { class: 'izgara izgara-4', role: 'group', 'aria-label': t('asama1.baslik') }, CIHAZLAR.map(function (x) {
      var b = karo(x.ik, t('cihaz.' + x.k), t('cihaz.' + x.k + '.kucuk'), S.cihaz === x.k, function () {
        var ilk = !S.cihaz; S.cihaz = x.k; ls('cihaz', x.k); guncelle();
        kaynakKart.classList.add('acil');
        if (S.kaynak && (ilk || onizKart.hidden)) kaynakSec(S.kaynak);
      });
      b.dataset.cihaz = x.k; return b;
    }));
    c = asamaCerceve(1, {
      baslik: t('asama1.baslik'), alt: t('asama1.alt'), ne: 'asama1.ne', sorun: 'sorun.asama1',
      govde: [cihazIzgara, ipucu, kaynakKart, onizKart]
    });
    kaynakCiz(); guncelle();
    if (!S.kaynaklar.length) yenile.click();
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
      govde: [listeEl, h('p', { class: 'sessiz yakinda', id: 'yakinda', text: t('gosterim.yakinda') }), detay],
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
      if (n === 3) { var m = motorBilgi(S.motor || a.motor); return m ? m.ad : ''; }
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
  function toast(metin) {
    var kutu = $('#bildirim');
    if (!kutu) { kutu = h('div', { id: 'bildirim', class: 'bildirim', 'aria-live': 'polite' }); document.body.appendChild(kutu); }
    var b = h('div', { class: 'tost', role: 'status', text: metin });
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
    function guncelle() { devam.disabled = !secili; }
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
    ana.appendChild(h('section', {}, [
      h('h1', { text: t('oyun.baslik') }),
      h('p', { class: 'alt-baslik', text: t('oyun.alt') }),
      ne('oyun.ne'),
      liste, yeni, paket, gezinme
    ]));
    listeCiz(); guncelle();
    oyunYukle().then(function () { if (document.body.contains(liste)) listeCiz(); });
  }

  // ---------- ANA EKRAN ----------
  var ekran = {};
  function anaEkran() {
    if (S.oyunDegis) { oyunEkrani('ana'); return; }
    ana.textContent = '';
    var a = S.ayarlar || {};
    var buyukDugme = h('button', { type: 'button', class: 'buyuk', id: 'baslat-durdur', onclick: baslatDurdur });
    ekran.buyuk = buyukDugme;
    ekran.led = h('span', { class: 'led' });
    ekran.durum = h('span', { id: 'durum-metin' });
    ekran.alt = h('div', { class: 'durum-alt', id: 'durum-alt' });
    ekran.ne = h('p', { class: 'ne', id: 'ne-satir' });
    ekran.yazi = h('div', { class: 'alt-yazi', id: 'son-yazi' });
    ekran.onizleme = h('div', { class: 'onizleme' }, ekran.yazi);
    ekran.oyunAd = h('div', { class: 'oyun-ad', id: 'aktif-oyun-ad' });
    ekran.oyunAlt = h('div', { class: 'sessiz', id: 'aktif-oyun-alt' });
    ekran.sonKutu = h('div', { id: 'son-liste', class: 'liste' });
    ekran.onerKutu = h('div', { id: 'oneri-kart', class: 'kart oneri', hidden: true });

    var oyunKart = h('div', { class: 'oyun-kart' }, [
      h('div', {}, [h('div', { class: 'etiket-kucuk', text: t('ana.oyun') }), ekran.oyunAd, ekran.oyunAlt]),
      h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'oyun-degistir', text: t('oyun.degistir'), onclick: function () { S.oyunDegis = true; ciz(); } })
    ]);
    // tek ana eylem: Başlat/Durdur. Oyun, durum ve TV önizlemesi aynı kartta
    var hero = h('div', { class: 'kart hero', id: 'hero' }, [
      oyunKart,
      buyukDugme,
      h('div', { class: 'durum-satir' }, [ekran.led, ekran.durum]), ekran.alt, ekran.ne,
      h('div', { class: 'onizleme-kutu' }, [h('div', { class: 'etiket-kucuk', text: t('on.baslik') }), ekran.onizleme])
    ]);
    var sonKart = h('div', { class: 'kart', id: 'son-kart' }, [
      h('h2', { text: t('son.baslik') }), ne('son.ne', 'isi'), ekran.sonKutu
    ]);

    ekran.erisim = h('div', { class: 'kart erisim-kart', id: 'erisim-kart' });
    ekran.hero = hero;
    ana.appendChild(h('section', { class: 'dar' }, [h('h1', { class: 'gizli', text: t('ana.baslik') }), h('div', { id: 'guncelleme-alani' }), hero, kurulumDurumu(), sonKart, ekran.onerKutu, ekran.erisim, bolgeKarti(), dublajKarti(), gelismisAlani(),
      h('div', { class: 'satir', style: 'margin-top:8px' }, [h('button', { type: 'button', class: 'baglanti', id: 'yeniden-kur', text: t('kurulum.yeniden'), onclick: function () {
        S.kurulumBitti = false; S.adim = 1; S.asama = {}; S.okunan = null; ls('asamalar', '{}'); ls('kurulum', '0'); ciz();
      } })])
    ]));
    oyunYukle().then(function () { oyunCiz(); });
    guncellemeCiz();
    oyunCiz(); sonCiz(); oneriCiz(); durumCiz(); erisimCiz(); listeYenile();
  }

  function oyunCiz() {
    if (!ekran.oyunAd || !document.body.contains(ekran.oyunAd)) return;
    var kod = S.ayarlar && S.ayarlar.aktif_oyun;
    var o = S.oyunlar.filter(function (x) { return x.kod === kod; })[0];
    ekran.oyunAd.textContent = o ? o.ad : (kod || t('oyun.yok'));
    if (o && o.kayit_sayisi) sayacYaz(ekran.oyunAlt, o.kayit_sayisi, function (n) { return t('oyun.hatirla', { n: sayi(n) }); });
    else { ekran.oyunAlt.dataset.n = ''; ekran.oyunAlt.textContent = o ? hatirlaMetni(o) : t('oyun.yok.k'); }
    var dg = $('#oyun-degistir'); if (dg) dg.textContent = kod ? t('oyun.degistir') : t('oyun.sec');
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
    if (!S.kurulumBitti || S.oyunDegis || !ekran.sonKutu || !document.body.contains(ekran.sonKutu)) return;
    api('GET', '/api/son-ceviriler').then(function (l) { if (!S.duzeltAcik) { S.sonCeviriler = l || []; sonCiz(); } }).catch(function () {});
    api('GET', '/api/oneriler').then(function (l) { S.oneriler = l || []; oneriCiz(); }).catch(function () {});
  }
  function sonCiz() {
    if (!ekran.sonKutu || !document.body.contains(ekran.sonKutu)) return;
    ekran.sonKutu.textContent = '';
    if (!S.sonCeviriler.length) { ekran.sonKutu.appendChild(h('p', { class: 'bos-durum', id: 'son-bos', text: t('son.bos') })); return; }
    S.sonCeviriler.forEach(function (c) {
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
    ekran.onerKutu.appendChild(h('h2', { text: t('oneri.baslik') }));
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
    kutu.appendChild(h('span', { class: 'metin', id: 'guncelleme-metin', title: g.notlar || '',
      text: (a === 'hata' && g.mesaj) ? g.mesaj : t('guncelleme.hazir', { surum: g.surum }) }));
    kutu.appendChild(h('button', { type: 'button', class: 'dugme kucuk', id: 'guncelle-dugme', onclick: guncellemeKur,
      text: a === 'hata' ? t('guncelleme.tekrar') : t('guncelleme.dugme') }));
    return kutu;
  }
  function guncellemeCiz() {
    var kap = $('#guncelleme-alani');
    var g = S.guncelleme;
    if (kap) {
      kap.textContent = '';
      if (g && g.var) kap.appendChild(guncellemeBar(g));
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
  var gelismisKap = null;
  function gelismisYenile() {
    if (!gelismisKap || !document.body.contains(gelismisKap)) return;
    var acik = gelismisKap.open;
    var yeni = gelismisAlani(); yeni.open = acik;
    gelismisKap.replaceWith(yeni);
  }
  function anahtar(baslik, kucuk, deger, degisti, id) {
    var inp = h('input', { type: 'checkbox', id: id, onchange: function () { degisti(inp.checked); } });
    inp.checked = !!deger;
    return h('label', { class: 'anahtar' }, [h('span', { class: 'ac' }, [baslik, kucuk ? h('small', { text: kucuk }) : null]), h('span', { class: 'sw' }, [inp, h('i')])]);
  }
  function bolum(baslik, isi, kids) {
    return h('div', { class: 'bolum' }, [h('h3', { text: baslik }), isi ? ne(isi, 'isi') : null].concat(kids));
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
      h('h4', { text: t('paylas.baslik') }),
      h('p', { class: 'sessiz', text: t('paylas.aciklama') }),
      kod ? h('a', { class: 'dugme ikincil kucuk', id: 'paket-paylas', href: '/api/paket/' + encodeURIComponent(kod), download: kod + '.akpaket', text: t('paylas.dugme') })
          : h('p', { class: 'sessiz', text: t('oyun.yok.k') })
    ]);
  }
  function gelismisAlani() {
    var a = S.ayarlar || {}; var g = a.gorunum || {};
    var sesAcik = h('div', { class: 'not', id: 'ses-not', hidden: !a.ses_cevir, text: t('ayar.ses.onay') });
    var ne1 = bolum(t('ayar.bolum'), 'ayar.ne', [
      anahtar(t('ayar.ekran'), t('ayar.ekran.k'), a.ekrani_cevir, function (v) { ayarKaydet({ ekrani_cevir: v }); }, 'ekrani-cevir'),
      anahtar(t('ayar.aciklama'), t('ayar.aciklama.k'), a.kisa_aciklama, function (v) { ayarKaydet({ kisa_aciklama: v }); }, 'kisa-aciklama'),
      anahtar(t('ayar.ses'), t('ayar.ses.k'), a.ses_cevir, function (v) { sesAcik.hidden = !v; ayarKaydet({ ses_cevir: v }); }, 'ses-cevir'),
      sesAcik
    ]);
    var dilSec = h('select', { id: 'hedef-dil', 'aria-label': t('ayar.hedef'), onchange: function () { ayarKaydet({ hedef_dil: dilSec.value }); } },
      HEDEF_DILLER.map(function (k) { var o = h('option', { value: k, text: t('hd.' + k) }); if (a.hedef_dil === k) o.selected = true; return o; }));
    var dilB = bolum(t('ayar.hedef'), null, [dilSec]);

    function gorunumAyar(alan, deger) { var p = {}; p[alan] = deger; ayarKaydet({ gorunum: p }); }
    var boyut = h('input', { type: 'range', min: 24, max: 80, step: 2, id: 'yazi-boyutu', value: g.yazi_boyutu || 44 });
    var koyu = h('input', { type: 'range', min: 0, max: 100, step: 5, id: 'arka-plan', value: Math.round((g.arka_plan == null ? 0.55 : g.arka_plan) * 100) });
    var konum = h('select', { id: 'konum', onchange: function () { gorunumAyar('konum', konum.value); } }, [
      h('option', { value: 'alt', text: t('gorunum.alt') }), h('option', { value: 'ust', text: t('gorunum.ust') })]);
    konum.value = g.konum || 'alt';
    function onizlemeGuncelle() {
      if (!ekran.yazi) return;
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
      h('label', { class: 'etiket', for: 'yazi-boyutu', text: t('gorunum.boyut') }), boyut,
      h('div', { class: 'iki' }, [
        h('div', {}, [h('label', { class: 'etiket', for: 'konum', text: t('gorunum.konum') }), konum]),
        h('div', {}, [h('label', { class: 'etiket', for: 'arka-plan', text: t('gorunum.koyuluk') }), koyu])
      ])
    ]);
    onizlemeGuncelle();

    var kap = h('details', { class: 'gelismis', id: 'gelismis' }, [
      h('summary', { text: t('gelismis.link') }),
      h('div', { class: 'gelismis-ic' }, [
        h('p', { class: 'sessiz', text: t('gelismis.uyari') }),
        hafizaBolumu(), kaliteSec('ayar'), ne1, dilB, gorB, sozlukBolumu(), tvKartiBolumu(), guncellemeBolumu(), motorBolumu()
      ])
    ]);
    gelismisKap = kap;
    return kap;
  }

  function tvKartiBolumu() { return h('div', { class: 'bolum' }, tvKarti()); }

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
    var aktif = h('select', { id: 'aktif-motor' }, uygun.map(function (x) { var o = h('option', { value: x.kod, text: x.ad }); if (a.motor === x.kod) o.selected = true; return o; }));
    var modelGirdi = {};
    var modelAlanlari = ['claude', 'gemini', 'deepseek'].map(function (k) {
      modelGirdi[k] = h('input', { type: 'text', id: 'model-' + k, value: m[k] || '' });
      return h('div', {}, [h('label', { class: 'etiket', for: 'model-' + k, text: t('gelismis.model', { ad: k }) }), modelGirdi[k]]);
    });
    var tamam = h('span', { class: 'sessiz', id: 'gelismis-durum' });
    return bolum(t('gelismis.baslik'), null, [
      h('div', { class: 'iki' }, [
        h('div', {}, [h('label', { class: 'etiket', for: 'aktif-motor', text: t('gelismis.motor') }), aktif]),
        h('div', {}, [h('label', { class: 'etiket', for: 'yedek-motor', text: t('gelismis.yedek') }), yedek]),
        h('div', {}, [h('label', { class: 'etiket', for: 'kapi', text: t('gelismis.kapi') }), kapi, h('small', { class: 'sessiz', text: t('gelismis.kapi_not') })])
      ]),
      h('div', { class: 'iki' }, modelAlanlari),
      h('div', { class: 'satir', style: 'margin-top:14px' }, [
        h('button', { type: 'button', class: 'dugme kucuk', id: 'gelismis-kaydet', text: t('gelismis.kaydet'), onclick: function () {
          var mm = {}; Object.keys(modelGirdi).forEach(function (k) { if (modelGirdi[k].value.trim()) mm[k] = modelGirdi[k].value.trim(); });
          ayarKaydet({ motor: aktif.value, yedek_motor: yedek.value || null, kapi: Number(kapi.value) || 8642, modeller: Object.assign({}, a.modeller, mm) })
            .then(function () { tamam.textContent = t('gelismis.kaydedildi'); });
        } }), tamam
      ])
    ]);
  }

  function durumCiz() {
    if (!ekran.buyuk || !document.body.contains(ekran.buyuk)) return;
    var d = S.durum;
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
    var sorun = d.hata === 'yakalama' || d.hata === 'genel' ? d.hata : null;   // boru hattı durduysa nedeni
    ekran.led.className = 'led' + (d.calisiyor ? (d.yedekte ? ' yedek' : ' acik') : (sorun ? ' sorun' : ''));
    ekran.durum.textContent = !d.calisiyor ? (sorun ? t('durum.hata.' + sorun) : t('durum.durdu')) : (d.yedekte ? t('durum.yedekte') : t('durum.calisiyor'));
    var mot = motorBilgi(d.motor), gos = S.gosterim || (S.ayarlar && S.ayarlar.gosterim) || 'bilgisayar';
    var nerede = gos === 'bilgisayar' ? t('durum.bu_ekran') : t('durum.tv', { n: d.tv_sayisi || 0 });
    ekran.alt.textContent = (mot ? t('durum.motor', { ad: mot.ad }) + ' · ' : '') + nerede;
    ekran.ne.textContent = '';
    ekran.ne.appendChild(h('b', { text: t('ne.etiket') + ' ' }));
    ekran.ne.appendChild(document.createTextNode(d.calisiyor ? t('ana.ne.calisiyor') : (sorun ? t('durum.hata.' + sorun + '.k') : t('ana.ne.durdu'))));
    var yeniYazi = d.son_yazi || t('on.bos');
    if (ekran.yazi.textContent !== yeniYazi) {
      ekran.yazi.textContent = yeniYazi;
      ekran.yazi.classList.remove('yeni'); void ekran.yazi.offsetWidth; ekran.yazi.classList.add('yeni');
    }
    ekran.yazi.style.opacity = d.son_yazi ? 1 : .55;
  }

  // ---------- erişim (günlük ücretsiz süre / erişim kodu, PROTOKOL 7.3) ----------
  function erisimYukle() {
    return api('GET', '/api/erisim').then(function (e) { S.erisim = e; erisimCiz(); }).catch(function () {});
  }
  function erisimCiz() {
    if (!ekran.erisim || !document.body.contains(ekran.erisim)) return;
    var e = S.erisim; if (!e) return;
    var kutu = ekran.erisim;
    var sinir = !!(S.durum && S.durum.sinir) && !e.kod;
    var imza = [sinir, e.kod, e.kalan_dakika, e.bitis, S.erisimAcik, dil].join('|');
    if (kutu.dataset.imza === imza) return;   // değişmediyse yeniden çizme (yazı/hata silinmesin)
    kutu.dataset.imza = imza;
    kutu.textContent = '';
    var metin = e.kod === 'sinirsiz' ? t('erisim.sinirsiz')
      : (e.kod === 'gun' ? t('erisim.gun', { tarih: e.bitis || '' }) : t('erisim.kalan', { n: e.kalan_dakika }));
    var satir = h('div', { class: 'satir erisim-satir' }, [
      h('span', { class: 'etiket-kucuk', text: t('erisim.baslik') }),
      h('span', { id: 'erisim-metin', text: metin, 'aria-live': 'polite' }),
      e.kod ? null : h('button', { type: 'button', class: 'baglanti', id: 'kodum-var', text: t('erisim.kodum_var'), onclick: function () {
        S.erisimAcik = !S.erisimAcik; erisimCiz(); var g = $('#erisim-kod'); if (g) g.focus();
      } })
    ]);
    kutu.appendChild(satir);
    if (sinir) kutu.appendChild(h('p', { class: 'not', id: 'erisim-sinir', role: 'status', text: t('erisim.sinir') }));
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
    }
  }

  function durumYukle() {
    return api('GET', '/api/durum').then(function (d) {
      var oncekiKapali = S.kapali;
      S.durum = d; S.kapali = false;
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
    var liste = JSON.parse(JSON.stringify((S.ayarlar && S.ayarlar.bolgeler) || [])).slice(0, BOLGE_EN_COK);
    var secili = -1, surukle = null, popIdx = -1;
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
      katman.textContent = '';
      liste.forEach(function (b, i) {
        var el = h('div', { class: 'bolge t-' + b.tur + (i === secili ? ' secili' : ''), 'data-bolge': String(i), tabindex: '0', role: 'group',
          'aria-label': kutuEtiket(i), onkeydown: function (e) { tus(e, i); }, onfocus: function (e) { if (e.target === el && secili !== i) { secili = i; isaretle(); } } });
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
      dolu.hidden = liste.length < BOLGE_EN_COK;
      sayac.textContent = t('bolge.sayac', { n: liste.length, m: BOLGE_EN_COK });
    }
    function isaretle() {
      [].forEach.call(katman.children, function (el) { el.classList.toggle('secili', Number(el.dataset.bolge) === secili); });
      [].forEach.call(satirlar.children, function (el) { el.classList.toggle('secili', Number(el.dataset.satir) === secili); });
    }
    function satirlariCiz() {
      satirlar.textContent = '';
      if (!liste.length) { satirlar.appendChild(h('p', { class: 'bos-durum', id: 'bolge-bos', text: t('bolge.bos') })); return; }
      liste.forEach(function (b, i) {
        var sec = h('select', { id: 'bolge-tur-' + i, 'aria-label': t('bolge.kare', { n: i + 1 }) + ': ' + t('bolge.tur'), onchange: function () { turDegis(i, sec.value); } },
          BOLGE_TURLER.map(function (k) { return h('option', { value: k, selected: k === b.tur, text: turAd(k) }); }));
        sec.value = b.tur;
        satirlar.appendChild(h('div', { class: 'bolge-satir t-' + b.tur + (i === secili ? ' secili' : ''), 'data-satir': String(i) }, [
          h('span', { class: 'bolge-no', text: t('bolge.kare', { n: i + 1 }) }), sec,
          h('button', { type: 'button', class: 'x bolge-sil', 'data-sil': String(i), 'aria-label': t('bolge.sil', { n: i + 1 }), text: '×', onclick: function () { sil(i); } })
        ]));
      });
    }
    function hepsiniCiz() { kutulariCiz(); satirlariCiz(); }
    function turDegis(i, tur) { liste[i].tur = tur; liste[i].ad = t('bolge.ad.' + tur); hepsiniCiz(); bildir(); }
    function sil(i) {
      popKapat(false);
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
    function tus(e, i) {
      var kutuEl = e.currentTarget;
      if (e.target !== kutuEl) return;   // içteki düğmeler kendi işini yapsın
      var b = liste[i], d = e.altKey ? BOLGE_ADIM / 4 : BOLGE_ADIM, dx = 0, dy = 0;
      if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); sil(i); return; }
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); popAc(i); return; }
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
      var b = { x: 0.35, y: 0.4, g: 0.3, y2: 0.12 }; b.tur = turTahmin(b); b.ad = t('bolge.ad.' + b.tur);
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
      var n = nokta(e), kutu = e.target.closest ? e.target.closest('.bolge') : null;
      if (kutu) {
        var i = Number(kutu.dataset.bolge), b = liste[i], tm = e.target.dataset && e.target.dataset.tutamac;
        secili = i;
        surukle = { tur: tm ? 'boyut' : 'tasi', i: i, tm: tm, n0: n, b0: { x: b.x, y: b.y, g: b.g, y2: b.y2 } };
        e.preventDefault();
        try { katman.setPointerCapture(e.pointerId); } catch (x) { /* eski tarayıcı */ }
        isaretle();
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
      } else if (s0.tur === 'tasi') {
        b = liste[s0.i];
        b.x = sinir(s0.b0.x + n.x - s0.n0.x, 0, 1 - b.g); b.y = sinir(s0.b0.y + n.y - s0.n0.y, 0, 1 - b.y2);
      } else {
        b = liste[s0.i];
        var o0 = s0.b0, solSag = s0.tm.indexOf('w') >= 0, ustAlt = s0.tm.indexOf('n') >= 0;
        var sabitX = solSag ? o0.x + o0.g : o0.x, sabitY = ustAlt ? o0.y + o0.y2 : o0.y;   // karşı köşe sabit
        b.x = Math.min(sabitX, n.x); b.g = Math.abs(n.x - sabitX); b.y = Math.min(sabitY, n.y); b.y2 = Math.abs(n.y - sabitY);
      }
      s0.oynadi = true;
      var el = katman.querySelector('[data-bolge="' + s0.i + '"]');
      if (!el) { kutulariCiz(); el = katman.querySelector('[data-bolge="' + s0.i + '"]'); }
      el.style.left = b.x * 100 + '%'; el.style.top = b.y * 100 + '%'; el.style.width = b.g * 100 + '%'; el.style.height = b.y2 * 100 + '%';
    });
    function birak(e) {
      if (!surukle) return;
      var s0 = surukle; surukle = null;
      try { katman.releasePointerCapture(e.pointerId); } catch (x) { /* yok say */ }
      if (s0.i != null && liste[s0.i]) {
        var b = liste[s0.i];
        if (s0.tur === 'ciz' && (b.g < BOLGE_MIN_G || b.y2 < BOLGE_MIN_Y)) { liste.splice(s0.i, 1); secili = -1; }   // çok küçük: kaza ile çizilmiş
        else {
          duzelt(b);
          if (s0.tur === 'ciz') { b.tur = turTahmin(b); b.ad = t('bolge.ad.' + b.tur); }
        }
      }
      hepsiniCiz();
      if (s0.oynadi) bildir();
      odakla(secili >= 0 ? katman.querySelector('[data-bolge="' + secili + '"]') : null);
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
        liste = yeni; secili = -1; ipucuKapat(); popKapat(false); hepsiniCiz(); bildir();
        mesaj.appendChild(h('p', { class: 'bilgi-satir', id: 'bolge-onerildi', text: t('bolge.onerildi', { n: yeni.length }) }));
      }).catch(function (e) { mesaj.textContent = ''; mesaj.appendChild(hataKutusu(e, 'bolge-oner-hata', [{ id: 'bolge-oner-tekrar', ad: t('genel.tekrar'), f: oner }])); });
    }
    function kaydet(otomatikMi) {
      var temiz = otomatikMi ? [] : liste.slice(0, BOLGE_EN_COK).map(function (b) {
        return { x: yuvarla(b.x), y: yuvarla(b.y), g: yuvarla(b.g), y2: yuvarla(b.y2), tur: b.tur, ad: b.ad || t('bolge.ad.' + b.tur) };
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
    function otomatik() { liste = []; secili = -1; popKapat(false); hepsiniCiz(); return kaydet(true); }

    kok.appendChild(h('div', { class: 'bolge-arac' }, [
      h('div', { class: 'satir' }, [
        h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'bolge-oner', onclick: oner }, [ikon('goz'), h('span', { text: t('bolge.oner') })]),
        h('button', { type: 'button', class: 'dugme ikincil kucuk', id: 'bolge-yenile', onclick: kareYukle }, [ikon('yenile'), h('span', { text: t('bolge.yenile') })])
      ]),
      sayac
    ]));
    kok.appendChild(mesaj);
    kok.appendChild(sahne);
    kok.appendChild(h('p', { class: 'sessiz bolge-ipucu-satir', text: t('bolge.ipucu') }));
    kok.appendChild(dolu);
    kok.appendChild(satirlar);
    kok.appendChild(h('div', { class: 'satir bolge-kayit', style: 'margin-top:16px' }, [
      kaydetBtn,
      h('button', { type: 'button', class: 'dugme ikincil', id: 'bolge-otomatik', text: t('bolge.otomatik'), onclick: otomatik })
    ]));
    hepsiniCiz();
    return { el: kok, yukle: kareYukle, kapat: function () {} };
  }

  // Ana ekran kartı: özet + "Çevrilecek yerleri düzenle" (5. aşamayı tek başına açar)
  function bolgeKarti() {
    return h('div', { class: 'kart', id: 'bolge-kart' }, [h('h2', { text: t('bolge.baslik') }),
      h('p', { class: 'sessiz', id: 'bolge-ozet', text: bolgeOzet() }),
      h('button', { type: 'button', class: 'dugme ikincil', id: 'bolge-ac', text: t('bolge.duzenle'), onclick: function () { asamaAc(5, 'ana'); } })]);
  }

  // ana ekran: kurulum durumu (5 aşama; her biri tıklanınca o aşama yeniden yapılır)
  function kurulumDurumu() {
    var satir = h('div', { class: 'kurulum-satir', role: 'list' });
    ASAMALAR.slice(0, 5).forEach(function (k, i) {
      var n = i + 1, d = S.asama[n] === 'tamam' ? 'tamam' : (S.asama[n] === 'atlandi' ? 'atlandi' : 'yok');
      satir.appendChild(h('div', { role: 'listitem' }, h('button', { type: 'button', class: 'kurulum-cip ' + d, id: 'kurulum-adim-' + n,
        'aria-label': t('kurulum.cip_aria', { ad: t('asama.' + k), durum: d === 'tamam' ? t('asama.durum.tamam') : (d === 'atlandi' ? t('asama.durum.atlandi') : t('asama.durum.yok')) }),
        onclick: function () { asamaAc(n, 'ana'); } }, [h('span', { class: 'cip-ik', 'aria-hidden': 'true', text: d === 'tamam' ? '✓' : (d === 'atlandi' ? '!' : String(n)) }), h('span', { text: t('asama.' + k) })])));
    });
    return h('div', { class: 'kart kurulum-kart', id: 'kurulum-durumu' }, [
      h('div', { class: 'kart-bas' }, [h('h2', { class: 'kucuk-baslik', text: t('kurulum.durum') }), h('span', { class: 'sessiz', text: t('kurulum.durum.k') })]), satir]);
  }


  // ---------- TÜRKÇE DUBLAJ (deneysel, PROTOKOL 9) ----------
  var DUBLAJ_MOTORLAR = ['kapali', 'chatterbox', 'pocket', 'elevenlabs'];
  var dublajKok = null, dublajImza = '', dublajMesaj = '';
  function dublajAyar() { return (S.ayarlar && S.ayarlar.dublaj) || {}; }
  function dublajSecim() { return S.dublajSecim || dublajAyar().motor || 'kapali'; }
  function dublajYukle() {
    return api('GET', '/api/dublaj').then(function (b) { S.dublaj = b; dublajCiz(); return b; }).catch(function () {});
  }
  function dublajKaydet(parca) {
    if (S.ayarlar) S.ayarlar.dublaj = Object.assign({}, dublajAyar(), parca);
    return api('POST', '/api/dublaj', parca).then(function (r) {
      if (r && r.dublaj && S.ayarlar) S.ayarlar.dublaj = r.dublaj;
      S.dublajSecim = null; return dublajYukle();
    }).catch(function (e) { hataGoster(e); return ayarYukle().then(dublajYukle); });
  }
  function dublajKarti() {
    dublajKok = h('div', { class: 'kart', id: 'dublaj-kart' });
    dublajImza = '';
    dublajCiz();
    dublajYukle();
    return dublajKok;
  }
  function dublajCiz() {
    if (!dublajKok || !document.body.contains(dublajKok) && dublajKok.dataset.kuruldu) return;
    var b = S.dublaj || {}, a = dublajAyar(), sec = dublajSecim(), ind = b.indirme || {};
    var imza = [sec, b.hazir, b.onerilen, b.ekran_karti, ind.durum, ind.yuzde, ind.hata, b.son_hata, b.elevenlabs_anahtar,
      a.elevenlabs_onay, a.elevenlabs_klon_onay, a.cikis, dublajMesaj, dil].join('|');
    if (imza === dublajImza) return;   // değişmediyse yeniden çizme (yazı/odak kaybolmasın)
    dublajImza = imza;
    var k = dublajKok; k.dataset.kuruldu = '1'; k.textContent = '';
    k.appendChild(h('h2', { text: t('dublaj.baslik') }));
    k.appendChild(h('p', { class: 'ne', id: 'dublaj-ne', text: t('dublaj.ne') }));
    k.appendChild(h('p', { class: 'sessiz', text: t('dublaj.gecikme') }));
    if (b.motor !== undefined) {
      k.appendChild(h('p', { class: 'sessiz', id: 'dublaj-donanim', text: b.ekran_karti ? t('dublaj.donanim', { kart: b.ekran_karti + (b.vram_gb ? ' (' + b.vram_gb + ' GB)' : '') }) : t('dublaj.donanim_yok') }));
    }
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
    }
    k.appendChild(h('p', { class: 'sessiz', style: 'margin-top:16px', text: t('dublaj.haklar') }));
  }

  // ---------- çizim ----------
  // ekran değişince yumuşak geçiş (ileri: sağdan, geri: soldan) ve odak yeni başlığa
  var SIRA = { asama1: 1, asama2: 2, asama3: 3, asama4: 4, asama5: 5, asama6: 6, ana: 7, oyun: 8 };
  var sonEkran = null;
  function ekranAdi() {
    if (S.tekAsama) return 'asama' + S.tekAsama;
    return S.kurulumBitti ? (S.oyunDegis ? 'oyun' : 'ana') : 'asama' + S.adim;
  }
  function ciz() {
    document.querySelectorAll('[data-i]').forEach(function (e) { e.textContent = t(e.dataset.i); });
    if (S.tekAsama) sihirbaz(S.tekAsama);
    else if (S.kurulumBitti) anaEkran();
    else sihirbaz(S.adim);
    var ad = ekranAdi(), bolumEl = ana.firstElementChild;
    ana.classList.toggle('genis', ad === 'asama5');
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
