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
  var DILLER = {};
  var dil = 'tr';
  function t(key, vars) {
    var s = (DILLER[dil] && DILLER[dil][key]);
    if (s == null) s = (DILLER.tr && DILLER.tr[key]);
    if (s == null) return key;
    if (vars) Object.keys(vars).forEach(function (k) { s = s.split('{' + k + '}').join(vars[k]); });
    return s;
  }

  // ---------- API ----------
  function api(yontem, yol, govde) {
    var secenek = { method: yontem, headers: {} };
    if (govde instanceof FormData) { secenek.body = govde; }
    else if (govde !== undefined) { secenek.headers['Content-Type'] = 'application/json'; secenek.body = JSON.stringify(govde); }
    return fetch(yol, secenek).then(function (r) {
      return r.text().then(function (txt) {
        var j = null;
        try { j = txt ? JSON.parse(txt) : {}; } catch (e) { j = null; }
        if (!r.ok || (j && j.hata)) {
          var err = new Error((j && j.mesaj) || t('hata.genel'));
          err.hata = j && j.hata; err.mesaj = j && j.mesaj; throw err;
        }
        return j;
      });
    }, function () {
      var e = new Error(t('hata.kapali')); e.kapali = true; throw e;
    });
  }

  // ---------- durum ----------
  var S = {
    ayarlar: null, durum: null, motorlar: [], kaynaklar: [],
    adim: 1, cihaz: ls('cihaz'), tv: ls('tv'), kaynak: null, motor: null, testTamam: false,
    kurulumBitti: ls('kurulum') === '1', kapali: false,
    oyunlar: [], sonCeviriler: [], oneriler: [], duzeltAcik: false, oyunDegis: false
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
  function hataGoster(e) {
    if (e && e.kapali) { kapaliBanner(true); return; }
    banner('hata', (e && (e.mesaj || e.message)) || t('hata.genel'));
  }
  function kapaliBanner(k) {
    S.kapali = k;
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
    { k: 'ps5', ik: '🎮' }, { k: 'xbox', ik: '🟩' }, { k: 'pc', ik: '🖥️' }, { k: 'kart', ik: '📹' }
  ];
  var TVLER = [
    { k: 'lg', ik: '📺' }, { k: 'samsung', ik: '📺' }, { k: 'android', ik: '📺' }, { k: 'yok', ik: '🌐' }
  ];
  var MOTOR_SIRA = ['gemini', 'deepseek', 'claude', 'yerel', 'deepl'];
  var HEDEF_DILLER = ['tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ar', 'ja', 'ko', 'zh', 'pl', 'nl'];

  function karo(ik, baslik, kucuk, secili, onclick) {
    return h('button', { type: 'button', class: 'karo', 'aria-pressed': String(!!secili), onclick: onclick },
      [h('span', { class: 'ik', text: ik, 'aria-hidden': 'true' }), h('span', { class: 'b', text: baslik }), kucuk ? h('span', { class: 'k', text: kucuk }) : null]);
  }
  function noktalar(adim) {
    var w = h('div', { class: 'noktalar', role: 'img', 'aria-label': t('sihirbaz.adim', { n: adim, m: 4 }) });
    for (var i = 1; i <= 4; i++) w.appendChild(h('div', { class: 'nokta' + (i === adim ? ' aktif' : (i < adim ? ' bitti' : '')) }));
    w.appendChild(h('span', { text: t('sihirbaz.adim', { n: adim, m: 4 }) }));
    return w;
  }
  function adimlar(anahtar) {
    return h('ol', {}, t(anahtar).split('\n').map(function (s) { return h('li', { text: s }); }));
  }

  // ---------- SİHİRBAZ ----------
  function sihirbaz() {
    ana.textContent = '';
    if (S.adim === 1) adim1(); else if (S.adim === 2) oyunEkrani('sihirbaz'); else if (S.adim === 3) adim2(); else adim3();
  }

  function adim1() {
    var kaynakKutu = h('div', { class: 'liste', id: 'kaynak-liste' });
    var ipucu = h('div', { class: 'ipucu', id: 'kaynak-ipucu', hidden: true });
    var devam = h('button', { type: 'button', class: 'dugme', id: 'ileri1', onclick: function () {
      ayarKaydet({ kaynak: S.kaynak }).then(function () { S.adim = 2; ciz(); });
    }, text: t('sihirbaz.ileri') });

    function guncelle() {
      document.querySelectorAll('[data-cihaz]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.cihaz === S.cihaz)); });
      document.querySelectorAll('[data-tv]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.tv === S.tv)); });
      ipucu.hidden = !S.cihaz;
      if (S.cihaz) ipucu.textContent = t('kaynak.ipucu.' + S.cihaz);
      devam.disabled = !(S.cihaz && S.tv && S.kaynak);
    }
    function kaynakCiz() {
      kaynakKutu.textContent = '';
      if (!S.kaynaklar.length) { kaynakKutu.appendChild(h('p', { class: 'sessiz', text: t('kaynak.bos') })); return; }
      S.kaynaklar.forEach(function (k) {
        kaynakKutu.appendChild(h('button', { type: 'button', class: 'sec', 'data-kaynak': k.kod, 'aria-pressed': String(S.kaynak === k.kod),
          onclick: function () { S.kaynak = k.kod; kaynakCiz(); guncelle(); } , text: k.ad }));
      });
    }
    var cihazIzgara = h('div', { class: 'izgara' }, CIHAZLAR.map(function (c) {
      var b = karo(c.ik, t('cihaz.' + c.k), t('cihaz.' + c.k + '.kucuk'), false, function () {
        S.cihaz = c.k; ls('cihaz', c.k); guncelle();
      });
      b.dataset.cihaz = c.k; return b;
    }));
    var tvIzgara = h('div', { class: 'izgara' }, TVLER.map(function (c) {
      var b = karo(c.ik, t('tv.' + c.k), t('tv.' + c.k + '.kucuk'), false, function () {
        S.tv = c.k; ls('tv', c.k); guncelle();
      });
      b.dataset.tv = c.k; return b;
    }));
    var yenile = h('button', { type: 'button', class: 'dugme ikincil kucuk', onclick: function () { kaynakYukle().then(kaynakCiz); }, text: t('kaynak.yenile') });

    ana.appendChild(h('section', {}, [
      noktalar(1),
      h('h1', { text: t('adim1.baslik') }),
      h('p', { class: 'alt-baslik', text: t('adim1.alt') }), ne('adim1.ne'),
      cihazIzgara, ipucu,
      h('div', { class: 'kart', style: 'margin-top:20px' }, [h('h2', { text: t('adim1.kaynak_baslik') }), kaynakKutu, h('div', { style: 'margin-top:12px' }, yenile)]),
      h('h2', { text: t('adim1.tv_baslik') }), tvIzgara,
      h('div', { class: 'alt-gezinme' }, [h('button', { type: 'button', class: 'dugme ikincil', onclick: atla, text: t('sihirbaz.atla') }), devam])
    ]));
    kaynakCiz(); guncelle();
  }

  function kaynakYukle() {
    return api('GET', '/api/kaynaklar').then(function (k) {
      S.kaynaklar = k || [];
      if (!S.kaynak && S.ayarlar && S.ayarlar.kaynak) S.kaynak = S.ayarlar.kaynak;
    }).catch(hataGoster);
  }
  function atla() { S.kurulumBitti = true; ls('kurulum', '1'); ciz(); }

  function motorBilgi(kod) { return S.motorlar.filter(function (m) { return m.kod === kod; })[0]; }

  function adim2() {
    var liste = S.motorlar.filter(function (m) { return m.kod !== 'sahte'; })
      .sort(function (a, b) { var x = MOTOR_SIRA.indexOf(a.kod), y = MOTOR_SIRA.indexOf(b.kod); return (x < 0 ? 99 : x) - (y < 0 ? 99 : y); });
    var detay = h('div', { id: 'motor-detay' });
    var devam = h('button', { type: 'button', class: 'dugme', id: 'ileri2', disabled: !S.testTamam, onclick: function () {
      ayarKaydet({ motor: S.motor }).then(function () { S.adim = 4; ciz(); });
    }, text: t('sihirbaz.ileri') });

    function detayCiz() {
      detay.textContent = '';
      var m = motorBilgi(S.motor); if (!m) return;
      var kart = h('div', { class: 'kart' });
      kart.appendChild(h('h2', { text: m.ad }));
      var sonuc = h('div', { id: 'dene-sonuc', 'aria-live': 'polite' });
      if (S.motor === 'claude') kart.appendChild(h('div', { class: 'not', text: t('motor.claude.abonelik') }));
      var dene = function () {
        sonuc.textContent = ''; sonuc.className = '';
        sonuc.appendChild(h('span', { text: t('dene.calisiyor') }));
        return api('POST', '/api/dene', { metin: 'Hello, how are you?', motor: S.motor }).then(function (r) {
          sonuc.className = 'sonuc';
          sonuc.textContent = '';
          sonuc.appendChild(h('div', { class: 'sessiz', text: 'Hello, how are you?' }));
          sonuc.appendChild(h('div', { text: '→ ' + r.ceviri }));
          S.testTamam = true; devam.disabled = false;
          banner('', '');
        }).catch(function (e) {
          S.testTamam = false; devam.disabled = true;
          sonuc.className = 'sonuc kotu'; sonuc.textContent = (e && (e.mesaj || e.message)) || t('hata.genel');
          if (e && e.kapali) kapaliBanner(true);
        });
      };
      if (m.anahtar_gerekli) {
        if (m.anahtar_kayitli) kart.appendChild(h('p', { class: 'sessiz', text: t('anahtar.kayitli') }));
        kart.appendChild(h('details', {}, [h('summary', { text: t('anahtar.nereden') }), adimlar('rehber.' + m.kod)]));
        kart.appendChild(h('label', { class: 'etiket', for: 'anahtar-gir', text: t('anahtar.etiket') }));
        kart.appendChild(h('input', { type: 'password', id: 'anahtar-gir', autocomplete: 'off', spellcheck: 'false', placeholder: m.anahtar_kayitli ? '••••••••' : t('anahtar.yer') }));
        kart.appendChild(h('p', { class: 'sessiz', text: t('anahtar.guvenli') }));
        kart.appendChild(h('div', { class: 'satir', style: 'margin-top:10px' }, [
          h('button', { type: 'button', class: 'dugme', id: 'kaydet-dene', text: t('anahtar.kaydet_dene'), onclick: function () {
            var v = $('#anahtar-gir').value.trim();
            var once = v ? api('POST', '/api/anahtar', { motor: m.kod, anahtar: v }).then(function () { m.anahtar_kayitli = true; }) : Promise.resolve();
            once.then(function () { return api('POST', '/api/ayarlar', { motor: m.kod }); }).then(dene).catch(function (e) {
              sonuc.className = 'sonuc kotu'; sonuc.textContent = (e && (e.mesaj || e.message)) || t('hata.genel');
            });
          } })
        ]));
      } else {
        kart.appendChild(h('p', { text: t('motor.' + m.kod + '.yerel_not') }));
        kart.appendChild(h('button', { type: 'button', class: 'dugme', id: 'sadece-dene', text: t('dene.dugme'), onclick: function () {
          api('POST', '/api/ayarlar', { motor: m.kod }).then(dene).catch(hataGoster);
        } }));
      }
      kart.appendChild(sonuc);
      detay.appendChild(kart);
    }
    var izgara = h('div', { class: 'izgara' }, liste.map(function (m) {
      var rozet = h('span', { class: 'rozet' + (m.kod === 'claude' ? ' sari' : ''), text: t('motor.' + m.kod + '.rozet') });
      var b = h('button', { type: 'button', class: 'karo', 'data-motor': m.kod, 'aria-pressed': String(S.motor === m.kod), onclick: function () {
        S.motor = m.kod; S.testTamam = false; devam.disabled = true;
        document.querySelectorAll('[data-motor]').forEach(function (x) { x.setAttribute('aria-pressed', String(x.dataset.motor === m.kod)); });
        detayCiz();
      } }, [h('span', { class: 'b', text: m.ad }), rozet, h('span', { class: 'k', text: t('motor.' + m.kod + '.kisa') })]);
      return b;
    }));
    ana.appendChild(h('section', {}, [
      noktalar(3), h('h1', { text: t('adim2.baslik') }), h('p', { class: 'alt-baslik', text: t('adim2.alt') }), ne('adim2.ne'),
      izgara, h('div', { style: 'margin-top:20px' }, detay), kaliteSec('wiz'),
      h('div', { class: 'alt-gezinme' }, [h('button', { type: 'button', class: 'dugme ikincil', onclick: function () { S.adim = 2; ciz(); }, text: t('sihirbaz.geri') }), devam])
    ]));
    detayCiz();
  }

  function adim3() {
    var sonuc = h('div', { 'aria-live': 'polite' });
    var sorular = h('div', { class: 'kart', hidden: true, id: 'soru-kutu' });
    var sorun = h('div', { class: 'kart', hidden: true, id: 'sorun-kutu' });
    var adresKutu = h('div', { id: 'adres-kutu' });
    function adresCiz() {
      adresKutu.textContent = '';
      var d = S.durum || {}; var kapi = d.kapi || (S.ayarlar && S.ayarlar.kapi) || 8642;
      var ad = d.adresler || [];
      if (S.tv === 'yok' || S.tv === 'samsung' || S.tv === 'android' || !S.tv) {
        adresKutu.appendChild(h('p', { text: t('adim3.tarayici') }));
        ad.forEach(function (ip) { adresKutu.appendChild(h('span', { class: 'adres', text: 'http://' + ip + ':' + kapi + '/tv' })); });
        adresKutu.appendChild(h('p', { class: 'sessiz', text: t('adim3.obs') + ' http://127.0.0.1:' + kapi + '/obs' }));
      } else {
        adresKutu.appendChild(h('p', { text: t('adim3.lg') }));
        adresKutu.appendChild(h('p', { class: 'sessiz', text: t('adim3.yedek_adres') }));
        ad.forEach(function (ip) { adresKutu.appendChild(h('span', { class: 'adres', text: 'http://' + ip + ':' + kapi + '/tv' })); });
      }
    }
    adresCiz();
    sorun.appendChild(h('h2', { text: t('sorun.baslik') }));
    sorun.appendChild(adimlar('sorun.liste'));
    sorun.appendChild(h('div', { class: 'satir' }, [h('button', { type: 'button', class: 'dugme ikincil', text: t('adim3.tekrar'), onclick: gonder })]));
    function gonder() {
      sonuc.textContent = '';
      api('POST', '/api/deneme-yazi', {}).then(function () {
        sonuc.appendChild(h('div', { class: 'sonuc', text: t('adim3.gonderildi') }));
        sorular.hidden = false;
      }).catch(function (e) { hataGoster(e); });
    }
    sorular.appendChild(h('h2', { text: t('adim3.gordun_mu') }));
    sorular.appendChild(h('div', { class: 'satir' }, [
      h('button', { type: 'button', class: 'dugme', id: 'evet', text: t('evet'), onclick: function () {
        S.kurulumBitti = true; ls('kurulum', '1'); api('POST', '/api/ayarlar', { kurulum_tamam: true }).catch(function () {}); ciz();
      } }),
      h('button', { type: 'button', class: 'dugme ikincil', id: 'hayir', text: t('hayir'), onclick: function () { sorun.hidden = false; } })
    ]));
    ana.appendChild(h('section', {}, [
      noktalar(4), h('h1', { text: t('adim3.baslik') }), h('p', { class: 'alt-baslik', text: t('adim3.alt') }), ne('adim3.ne'),
      h('div', { class: 'kart' }, [adresKutu, h('button', { type: 'button', class: 'dugme sari', id: 'deneme-yazi', text: t('adim3.gonder'), onclick: gonder }), sonuc]),
      sorular, sorun,
      h('div', { class: 'alt-gezinme' }, [h('button', { type: 'button', class: 'dugme ikincil', onclick: function () { S.adim = 3; ciz(); }, text: t('sihirbaz.geri') }), h('span')])
    ]));
  }

  // ---------- ortak: sakin açıklama satırı, bildirim, pencere ----------
  function ne(anahtar, tur) {
    return h('p', { class: 'ne' }, [h('b', { text: t(tur === 'isi' ? 'isi.etiket' : 'ne.etiket') + ' ' }), t(anahtar)]);
  }
  function sayi(n) { try { return Number(n || 0).toLocaleString(dil === 'tr' ? 'tr-TR' : 'en-US'); } catch (e) { return String(n || 0); } }
  function toast(metin) {
    var kutu = $('#bildirim');
    if (!kutu) { kutu = h('div', { id: 'bildirim', class: 'bildirim', 'aria-live': 'polite' }); document.body.appendChild(kutu); }
    var b = h('div', { class: 'tost', text: metin });
    kutu.appendChild(b);
    setTimeout(function () { b.remove(); }, 4500);
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
    var sihirbazda = mod === 'sihirbaz';
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
      } }, [h('span', { class: 'ik', text: '+', 'aria-hidden': 'true' }), h('span', { class: 'b', text: t('oyun.yeni') })]));
      liste.appendChild(h('button', { type: 'button', class: 'karo ekle', id: 'paket-ac', onclick: function () {
        paket.hidden = !paket.hidden; if (!paket.hidden) yeni.hidden = true;
      } }, [h('span', { class: 'ik', text: '↓', 'aria-hidden': 'true' }), h('span', { class: 'b', text: t('oyun.paket') })]));
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
      sihirbazda ? noktalar(2) : null,
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

    var oyunKart = h('div', { class: 'kart oyun-kart' }, [
      h('div', {}, [h('div', { class: 'etiket-kucuk', text: t('ana.oyun') }), ekran.oyunAd, ekran.oyunAlt]),
      h('button', { type: 'button', class: 'dugme ikincil', id: 'oyun-degistir', text: t('oyun.degistir'), onclick: function () { S.oyunDegis = true; ciz(); } })
    ]);
    var hero = h('div', { class: 'kart hero' }, [
      buyukDugme,
      h('div', { class: 'durum-satir' }, [ekran.led, ekran.durum]), ekran.alt, ekran.ne,
      h('div', { class: 'onizleme-kutu' }, [h('div', { class: 'etiket-kucuk', text: t('on.baslik') }), ekran.onizleme])
    ]);
    var sonKart = h('div', { class: 'kart', id: 'son-kart' }, [
      h('h2', { text: t('son.baslik') }), ne('son.ne', 'isi'), ekran.sonKutu
    ]);

    ana.appendChild(h('section', { class: 'dar' }, [oyunKart, hero, sonKart, ekran.onerKutu, gelismisAlani(), 
      h('div', { class: 'satir', style: 'margin-top:8px' }, [h('button', { type: 'button', class: 'baglanti', id: 'yeniden-kur', text: t('kurulum.yeniden'), onclick: function () {
        S.kurulumBitti = false; S.adim = 1; S.testTamam = false; ls('kurulum', '0'); ciz();
      } })])
    ]));
    oyunYukle().then(function () { oyunCiz(); });
    oyunCiz(); sonCiz(); oneriCiz(); durumCiz(); listeYenile();
  }

  function oyunCiz() {
    if (!ekran.oyunAd || !document.body.contains(ekran.oyunAd)) return;
    var kod = S.ayarlar && S.ayarlar.aktif_oyun;
    var o = S.oyunlar.filter(function (x) { return x.kod === kod; })[0];
    ekran.oyunAd.textContent = o ? o.ad : (kod || t('oyun.yok'));
    ekran.oyunAlt.textContent = o ? hatirlaMetni(o) : t('oyun.yok.k');
    var dg = $('#oyun-degistir'); if (dg) dg.textContent = kod ? t('oyun.degistir') : t('oyun.sec');
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
    if (!S.sonCeviriler.length) { ekran.sonKutu.appendChild(h('p', { class: 'sessiz', id: 'son-bos', text: t('son.bos') })); return; }
    S.sonCeviriler.forEach(function (c) {
      var satir = h('div', { class: 'ceviri-satir', 'data-id': c.id });
      function normal() {
        satir.textContent = '';
        satir.appendChild(h('div', { class: 'metin' }, [h('div', { class: 'asil', text: c.asil }), h('div', { class: 'ceviri', text: c.ceviri })]));
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
    var dilSec = h('select', { id: 'hedef-dil', onchange: function () { ayarKaydet({ hedef_dil: dilSec.value }); } },
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
        hafizaBolumu(), kaliteSec('ayar'), ne1, dilB, gorB, sozlukBolumu(), motorBolumu()
      ])
    ]);
    gelismisKap = kap;
    return kap;
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
    ekran.buyuk.textContent = d.calisiyor ? t('durdur') : t('baslat');
    ekran.buyuk.classList.toggle('dur', !!d.calisiyor);
    ekran.led.className = 'led' + (d.calisiyor ? (d.yedekte ? ' yedek' : ' acik') : '');
    ekran.durum.textContent = !d.calisiyor ? t('durum.durdu') : (d.yedekte ? t('durum.yedekte') : t('durum.calisiyor'));
    var mot = motorBilgi(d.motor); var tv = t('durum.tv', { n: d.tv_sayisi || 0 });
    ekran.alt.textContent = (mot ? t('durum.motor', { ad: mot.ad }) + ' · ' : '') + tv;
    ekran.ne.textContent = '';
    ekran.ne.appendChild(h('b', { text: t('ne.etiket') + ' ' }));
    ekran.ne.appendChild(document.createTextNode(t(d.calisiyor ? 'ana.ne.calisiyor' : 'ana.ne.durdu')));
    ekran.yazi.textContent = d.son_yazi || t('on.bos');
    ekran.yazi.style.opacity = d.son_yazi ? 1 : .5;
  }

  function durumYukle() {
    return api('GET', '/api/durum').then(function (d) {
      var oncekiKapali = S.kapali;
      S.durum = d; S.kapali = false;
      if (oncekiKapali) banner('', '');
      if (!S.ayarlar || !S.motorlar.length) {
        return Promise.all([ayarYukle(), api('GET', '/api/motorlar').then(function (m) { S.motorlar = m; }), kaynakYukle()]).then(ciz).catch(function () {});
      }
      durumCiz();
    }).catch(function (e) { if (e.kapali) kapaliBanner(true); });
  }

  // ---------- çizim ----------
  function ciz() {
    document.querySelectorAll('[data-i]').forEach(function (e) { e.textContent = t(e.dataset.i); });
    if (S.kurulumBitti) anaEkran(); else sihirbaz();
  }

  // ---------- başlangıç ----------
  function basla() {
    document.querySelectorAll('.dil-dugme').forEach(function (b) { b.addEventListener('click', function () { dilDegistir(b.dataset.dil); }); });
    var ilk = ls('dil') || 'tr';
    if (ilk !== 'tr' && ilk !== 'en') ilk = 'tr';
    dilYukle('tr').then(function () { return dilYukle(ilk); }).then(function () { dilUygula(ilk); })
      .then(function () {
        return Promise.all([ayarYukle(), api('GET', '/api/motorlar').then(function (m) { S.motorlar = m; }), kaynakYukle(), durumYukle()]);
      })
      .then(function () {
        if (S.ayarlar && S.ayarlar.kurulum_tamam && ls('kurulum') === null) S.kurulumBitti = true;
        var sd = S.ayarlar && S.ayarlar.arayuz_dili;
        if (sd && sd !== dil && (sd === 'tr' || sd === 'en')) return dilYukle(sd).then(function () { dilUygula(sd); });
      })
      .then(ciz)
      .catch(function (e) { hataGoster(e); ciz(); });
    setInterval(durumYukle, 2000);
    setInterval(function () { if (S.durum && S.durum.calisiyor) listeYenile(); }, 3000);
  }
  basla();
})();
