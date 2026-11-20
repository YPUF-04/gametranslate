// SPDX-License-Identifier: AGPL-3.0-only
// AltYazıKöprüsü - ortak bindirme çizicisi (TV tarayıcıları için, yalnızca ES5).
// Kullanım: var k = AKOverlay.baslat('/kopru/akis', element, {onDurum: fn, onYazi: fn, onBilgi: fn});
// url == null ise bağlanmaz (deneme kipi); k.yaziGoster / k.ekranGoster elle çağrılabilir.
// Akıcı gösterim kuralları: docs/PROTOKOL.md 7.2 (sunucudaki kuralların istemci tarafı aynası).
(function (pencere) {
  'use strict';
  var belge = pencere.document;

  var VARSAYILAN = { yazi_boyutu: 44, konum: 'alt', kenar_bosluk: 0.08, arka_plan: 0.55,
    yazi_rengi: '#FFFFFF', konusan_rengi: '#FFD166', asil_goster: false, ekran_cevir: true, onceki_goster: true, ekran_olcek: 1.0 };

  var GIR_MS = 150;        // yeni cümle belirirken eskisi bu sürede solar (çapraz geçiş)
  var SIL_MS = 250;        // yazi-sil: bu sürede solarak kaybolur
  var ONCEKI_MS = 2500;    // önceki satır bu kadar görünür
  var ONCEKI_SOLMA_MS = 400;
  var EKRAN_MS = 250;      // ekran öğeleri belirme / solma
  var GUVENLIK_MS = 15000; // §13.4: silmeyi sunucu (yazi-sil) yapar; bağlantı koparsa son güncellemeden bu kadar sonra kalkar

  function kopyala(a, b) { var s = {}, k; for (k in a) { if (a.hasOwnProperty(k)) { s[k] = a[k]; } }
    if (b) { for (k in b) { if (b.hasOwnProperty(k)) { s[k] = b[k]; } } } return s; }
  function oge(sinif, ust) { var e = belge.createElement('div'); e.className = sinif; if (ust) { ust.appendChild(e); } return e; }
  function sayi(v, varsayilan) { return (typeof v === 'number' && v === v) ? v : varsayilan; }
  function sinirla(v, a, b) { return v < a ? a : (v > b ? b : v); }
  function simdi() { return new Date().getTime(); }
  function bosalt(e) { while (e.firstChild) { e.removeChild(e.firstChild); } }
  function sil(e) { if (e && e.parentNode) { e.parentNode.removeChild(e); } }
  function reflow(e) { return e.offsetWidth; }

  function cssDengeli() {
    try { return !!(pencere.CSS && pencere.CSS.supports && pencere.CSS.supports('text-wrap', 'balance')); } catch (x) { return false; }
  }

  // Bir öğenin satır kutularını (Range ile) döndürür: kelime ortasından bölünüp bölünmediğini de buradan görürüz.
  function satirKutulari(e) {
    var r = belge.createRange(), l = [], i, k;
    r.selectNodeContents(e);
    k = r.getClientRects();
    for (i = 0; i < k.length; i++) { if (k[i].width > 0) { l.push(k[i]); } }
    return l;
  }
  function satirSayisi(e) {
    var k = satirKutulari(e), ust = [], i, j, yeni;
    for (i = 0; i < k.length; i++) {
      yeni = true;
      for (j = 0; j < ust.length; j++) { if (Math.abs(ust[j] - k[i].top) < 4) { yeni = false; break; } }
      if (yeni) { ust.push(k[i].top); }
    }
    return Math.max(1, ust.length);
  }

  // ---------- PROTOKOL 12.4: ekran öğesi satır düzeni (kopru/katman/mantik.py ile aynı kurallar) ----------
  var OGE_EN_AZ_PX = 11, OGE_EN_GENIS = 0.35, OGE_KAYNAK_CARPAN = 1.6, OGE_EN_DAR = 0.12, OGE_EN_COK_SATIR = 2;

  function kelimeler(metin) { return String(metin || '').replace(/\s+/g, ' ').replace(/^ | $/g, '').split(' ').filter(function (k) { return k !== ''; }); }
  // Boşluktan iki satıra böl: ikisi de azami'ye sığan, en dengeli bölme; yoksa null.
  function ikiSatir(k, olc, azami) {
    var i, a, b, wa, wb, en = null, puan = null, p;
    for (i = 1; i < k.length; i++) {
      a = k.slice(0, i).join(' '); b = k.slice(i).join(' '); wa = olc(a); wb = olc(b);
      if (wa > azami || wb > azami) { continue; }
      p = Math.max(wa, wb) * 2 + (wa >= wb ? 0 : 1);
      if (puan === null || p < puan) { en = [a, b]; puan = p; }
    }
    return en;
  }
  function satirlaraBol(k, olc, azami, enCok) {
    var metin = k.join(' ');
    if (!k.length) { return []; }
    if (olc(metin) <= azami) { return [metin]; }
    if (enCok >= 2 && k.length > 1) { return ikiSatir(k, olc, azami); }
    return null;
  }
  function uca(k, olc, azami) {
    var metin = k.join(' '), d, w = k.slice(0), t;
    if (olc(metin) <= azami) { return metin; }
    while (w.length > 1) {
      w.pop(); d = w.join(' ').replace(/[,;:.\-]+$/, '') + '\u2026';
      if (olc(d) <= azami) { return d; }
    }
    t = w[0] || '';
    while (t.length > 1 && olc(t + '\u2026') > azami) { t = t.slice(0, -1); }
    return t + '\u2026';
  }
  function kirp(k, olc, azami, enCok) {
    var satirlar = [], i = 0, cur, j;
    while (satirlar.length < enCok - 1 && i < k.length) {
      cur = k[i];
      if (olc(cur) > azami) { break; }
      j = i + 1;
      while (j < k.length && olc(cur + ' ' + k[j]) <= azami) { cur += ' ' + k[j]; j++; }
      satirlar.push(cur); i = j;
    }
    if (i < k.length) { satirlar.push(uca(k.slice(i), olc, azami)); }
    return satirlar;
  }
  // olc(metin, px) -> piksel genişliği. azami: kutunun dış genişliği. px: başlangıç yazı boyu; enAz: alt sınır.
  // sadeceSatir=true (açıklama): küçültmeden yalnız böl/kırp. Dönen: {satirlar, px, dolgu, kirpildi, metin}
  function yerlesimBul(metin, olc, azami, px, enAz, sadeceSatir) {
    var k = kelimeler(metin), p = Math.max(enAz, px), dolgu, ic, o, satirlar, kirpildi = false, onceki;
    for (;;) {
      dolgu = sadeceSatir ? 0 : Math.max(2, Math.round(p * 0.4));
      ic = Math.max(1, azami - 2 * dolgu);
      o = (function (pp) { return function (t) { return olc(t, pp); }; }(p));
      satirlar = satirlaraBol(k, o, ic, OGE_EN_COK_SATIR);
      if (satirlar !== null) { break; }
      if (sadeceSatir || p <= enAz) { satirlar = kirp(k, o, ic, OGE_EN_COK_SATIR); kirpildi = true; break; }
      onceki = p; p = Math.max(enAz, Math.floor(p * 0.92)); if (p >= onceki) { p = onceki - 1; }
    }
    return { satirlar: satirlar, px: p, dolgu: dolgu, kirpildi: kirpildi, metin: k.join(' ') };
  }

  function baslat(url, kok, secenekler) {
    var sec = secenekler || {};
    var gorunum = kopyala(VARSAYILAN, sec.gorunum);
    var es = null, bekle = null, gozcu = null, gizle = null, oncekiZ = null, durduruldu = false, deneme = 0;
    var sonYaziId = null, sonYazi = null, durum = 'baglaniyor';
    var kutu = null;            // şu an görünen altyazı kutusu
    var gecerli = null;         // {id, metin, konusan, asil} şu an gösterilen
    var ayrilanlar = [];        // solmakta olan kutular
    var ogeHarita = {};         // ekran öğeleri: anahtar -> {el, imza}
    var denge = !cssDengeli() || !!sec.dengeJs;   // true: dengeyi JS kurar
    var sesNesne = null;        // Türkçe dublaj sesi (PROTOKOL 9.4): çalan <audio>

    kok.className = (kok.className ? kok.className + ' ' : '') + 'ak-kok';
    kok.innerHTML = '';
    if (denge && cssDengeli()) { kok.className += ' ak-js-denge'; }   // JS dengesi zorlandıysa CSS dengesi kapanır
    var ekranKatman = oge('ak-ekran', kok);
    var yazi = oge('ak-yazi ak-alt', kok);
    var onceki = oge('ak-onceki', yazi);
    var sahne = oge('ak-sahne', yazi);
    var durumRozet = oge('ak-durum', kok);

    function olcek() { var g = kok.clientWidth || pencere.innerWidth || 1920; return g / 1920; }
    function yukseklik() { return kok.clientHeight || pencere.innerHeight || 1080; }
    function bildir(ad, v) { if (typeof sec[ad] === 'function') { try { sec[ad](v); } catch (e) { /* uygulama hatası bindirmeyi bozmasın */ } } }

    // Hareketi azalt: animasyon yok, her şey anında olur.
    function azaltilmis() {
      var a = false;
      try { a = !!(pencere.matchMedia && pencere.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (x) { a = false; }
      if (a) { if (kok.className.indexOf('ak-azalt') < 0) { kok.className += ' ak-azalt'; } }
      else { kok.className = kok.className.replace(/\s*ak-azalt/g, ''); }
      return a;
    }
    function sure(ms) { return azaltilmis() ? 0 : ms; }

    function durumDegistir(d) {
      durum = d;
      var gorunur = d !== 'bagli' && sec.durumRozeti !== false;
      durumRozet.style.display = gorunur ? 'block' : 'none';
      durumRozet.textContent = d === 'koptu' ? (sec.metinKoptu || 'Bağlantı koptu, yeniden deneniyor…') :
        (d === 'baglaniyor' ? (sec.metinBaglaniyor || 'Bağlanıyor…') : '');
      if (!gorunur) { durumRozet.style.display = 'none'; }
      bildir('onDurum', d);
    }

    function arkaPlan() { return 'rgba(8,12,20,' + sinirla(sayi(gorunum.arka_plan, 0.55), 0, 1) + ')'; }

    function gorunumUygula(g) {
      if (g) { gorunum = kopyala(gorunum, g); }
      var o = olcek(), i, k;
      yazi.style.fontSize = Math.round(sayi(gorunum.yazi_boyutu, 44) * o * 10) / 10 + 'px';
      yazi.style.color = gorunum.yazi_rengi;
      durumRozet.style.fontSize = Math.round(26 * o * 10) / 10 + 'px';
      var kb = sinirla(sayi(gorunum.kenar_bosluk, 0.08), 0, 0.45) * 100 + '%';
      if (gorunum.konum === 'ust') { yazi.style.top = kb; yazi.style.bottom = 'auto'; yazi.className = yazi.className.replace(/\bak-alt\b/, 'ak-ust'); }
      else { yazi.style.bottom = kb; yazi.style.top = 'auto'; yazi.className = yazi.className.replace(/\bak-ust\b/, 'ak-alt'); }
      ekranKatman.style.display = gorunum.ekran_cevir === false ? 'none' : 'block';
      k = yazi.getElementsByClassName('ak-yazi-kutu');
      for (i = 0; i < k.length; i++) { k[i].style.background = arkaPlan(); }
      k = yazi.getElementsByClassName('ak-konusan');
      for (i = 0; i < k.length; i++) { k[i].style.color = gorunum.konusan_rengi; }
      if (gorunum.onceki_goster === false) { oncekiTemizle(); }
      if (kutu) { sigdir(kutu); }
      bildir('onGorunum', gorunum);
    }

    // ---------- satır düzeni: dengeli, en çok iki satır, kelime ortasından bölünmez ----------
    function metinYaz(m, metin) {
      bosalt(m);
      m.appendChild(belge.createTextNode(metin));
    }
    // Metni, boşluklardan, n satıra yaklaşık eşit bölmek için <br> koyar (yalnız CSS dengesi yoksa).
    function dengeleJs(m, metin) {
      var n = satirSayisi(m), kelimeler, sinir, i, k, hedef, en, fark, parca, toplam, sonra;
      if (n < 2) { return; }
      kelimeler = metin.split(' ');
      if (kelimeler.length < 2) { return; }
      sinir = []; toplam = 0;
      for (i = 0; i < kelimeler.length - 1; i++) { toplam += kelimeler[i].length + 1; sinir.push(toplam); }   // her kelimeden sonraki konum
      var kesim = [];
      for (k = 1; k < n; k++) {
        hedef = metin.length * k / n * (k === 1 ? 0.96 : 1);   // ilk satır biraz kısa
        en = -1; fark = 1e9;
        for (i = 0; i < sinir.length; i++) { if (Math.abs(sinir[i] - hedef) < fark) { fark = Math.abs(sinir[i] - hedef); en = i; } }
        if (en >= 0 && kesim.indexOf(en) < 0) { kesim.push(en); }
      }
      kesim.sort(function (a, b) { return a - b; });
      bosalt(m); sonra = 0;
      for (i = 0; i < kesim.length; i++) {
        parca = kelimeler.slice(sonra, kesim[i] + 1).join(' ');
        m.appendChild(belge.createTextNode(parca)); m.appendChild(belge.createElement('br'));
        sonra = kesim[i] + 1;
      }
      m.appendChild(belge.createTextNode(kelimeler.slice(sonra).join(' ')));
      if (satirSayisi(m) > kesim.length + 1) { metinYaz(m, metin); }   // sığmadı: doğal sarmaya dön
    }
    // Kutuyu en uzun satırın genişliğine daraltır: dengeli satırların yanında boş kenar kalmasın.
    function sigdir(k) {
      var m = k.getElementsByClassName('ak-metin')[0], kutular, i, en = 0;
      if (!m) { return; }
      m.style.width = '';
      kutular = satirKutulari(m);
      for (i = 0; i < kutular.length; i++) { if (kutular[i].width > en) { en = kutular[i].width; } }
      if (en > 0) { m.style.width = Math.ceil(en + 3) + 'px'; }
    }
    function kutuIcerik(k, v) {
      var m, a;
      bosalt(k);
      if (v.konusan) { a = oge('ak-konusan', k); a.textContent = v.konusan; a.style.color = gorunum.konusan_rengi; }
      m = oge('ak-metin', k);
      metinYaz(m, v.metin);
      if (denge) { m.style.width = ''; dengeleJs(m, v.metin); }
      if (gorunum.asil_goster && v.asil) { a = oge('ak-asil', k); a.textContent = v.asil; }
      sigdir(k);
    }

    // ---------- altyazı ----------
    function kutuKaldir(k, ms) {
      if (!k) { return; }
      ms = sure(ms);
      if (ms <= 0) { sil(k); }
      else {
        k.className += ' ak-cikiyor';
        k.style.transition = 'opacity ' + ms + 'ms linear';
        k.style.opacity = '0';
        ayrilanlar.push(k);
        pencere.setTimeout(function () { sil(k); ayrilanlar = ayrilanlar.filter(function (x) { return x !== k; }); kapsayiciKontrol(); }, ms + 30);
      }
      kapsayiciKontrol();
    }
    function kapsayiciKontrol() { if (!kutu && sahne.childNodes.length === 0) { yazi.style.display = 'none'; } }

    function oncekiTemizle() {
      if (oncekiZ) { pencere.clearTimeout(oncekiZ); oncekiZ = null; }
      bosalt(onceki); onceki.style.opacity = '0'; onceki.style.display = 'none';
    }
    function oncekiGoster(metin) {
      oncekiTemizle();
      if (gorunum.onceki_goster === false || !metin) { return; }
      var t = belge.createElement('span'); t.className = 'ak-onceki-metin'; t.textContent = metin; onceki.appendChild(t);
      onceki.style.display = 'block'; onceki.style.transition = 'none'; onceki.style.opacity = '0'; reflow(onceki);
      onceki.style.transition = azaltilmis() ? 'none' : 'opacity ' + GIR_MS + 'ms linear'; onceki.style.opacity = '0.5';
      oncekiZ = pencere.setTimeout(function () {
        onceki.style.transition = azaltilmis() ? 'none' : 'opacity ' + ONCEKI_SOLMA_MS + 'ms linear'; onceki.style.opacity = '0';
        oncekiZ = pencere.setTimeout(function () { oncekiZ = null; oncekiTemizle(); }, sure(ONCEKI_SOLMA_MS) + 30);
      }, ONCEKI_MS);
    }

    function gizleKur(ms) {
      if (gizle) { pencere.clearTimeout(gizle); }
      gizle = pencere.setTimeout(function () { gizle = null; yaziSil(); }, sinirla(ms, 300, 60000));
    }

    // §13.4: silme kararı (t_git + L) sunucudadır; burada en az süre / sure_ms beklemesi yok.
    function yaziSil() {
      if (!kutu) { return; }
      if (gizle) { pencere.clearTimeout(gizle); gizle = null; }
      var k = kutu;
      kutu = null; gecerli = null;
      oncekiTemizle();
      kutuKaldir(k, SIL_MS);
    }

    function yaziGoster(v) {
      var sureMs, yerinde, degisti, yeni, eski, oncekiMetin;
      if (!v || typeof v.metin !== 'string' || v.metin === '') { return; }
      if (v.id !== undefined && v.id !== null && v.id === sonYaziId && !kutu) { return; } // yeniden bağlanınca / geç gelen yenileme eski yazıyı geri getirmesin
      // sure_ms yalnız bilgi; `otomatik_sil: true` (deneme yazısı) ise o kadar sonra kalkar, yoksa yalnız güvenlik zaman aşımı
      sureMs = (v.otomatik_sil === true) ? sinirla(sayi(v.sure_ms, 5000), 300, 60000) : GUVENLIK_MS;
      sonYaziId = (v.id === undefined ? null : v.id);
      sonYazi = v.metin;
      yerinde = !!kutu && !!gecerli && (v.devam === true || (v.id !== undefined && v.id !== null && v.id === gecerli.id));
      yazi.style.display = 'flex';
      if (yerinde) {
        // devam: aynı kutu, aynı yerde güncellenir (sönme ve zıplama yok)
        degisti = v.metin !== gecerli.metin || (v.konusan || null) !== (gecerli.konusan || null) || (gorunum.asil_goster && v.asil !== gecerli.asil);
        if (degisti) { kutuIcerik(kutu, v); }
        gecerli = { id: v.id, metin: v.metin, konusan: v.konusan || null, asil: v.asil };
      } else {
        oncekiMetin = (kutu && gecerli) ? gecerli.metin : '';
        eski = kutu;
        // eskiden kalan solmakta kutular varsa hemen toparla (üst üste binmesin)
        while (ayrilanlar.length > 1) { sil(ayrilanlar.shift()); }
        yeni = oge('ak-yazi-kutu', sahne);
        yeni.style.background = arkaPlan();
        yeni.style.opacity = '0'; yeni.style.transition = 'none';
        kutuIcerik(yeni, v);
        reflow(yeni);
        yeni.style.transition = azaltilmis() ? 'none' : 'opacity ' + GIR_MS + 'ms linear';
        yeni.style.opacity = '1';
        yeni.className += ' ak-gorunur';
        kutu = yeni;
        gecerli = { id: v.id, metin: v.metin, konusan: v.konusan || null, asil: v.asil };
        if (eski) { kutuKaldir(eski, GIR_MS); oncekiGoster(oncekiMetin); }
      }
      gizleKur(sureMs);
      bildir('onYazi', v);
    }

    // ---------- ekran öğeleri ----------
    function ogeImza(e) {
      var h = (e.hedef && typeof e.hedef === 'object') ? e.hedef : {};
      return [e.x, e.y, e.g, e.y2, e.metin, e.aciklama || '', e.tur || '', h.x, h.y, h.g, h.y2, e.boyut_px].join('|');
    }
    // PROTOKOL 12.4: yazı boyu `boyut_px` (1080p'ye göre, kaynak satır yüksekliğinin 0.75'i, 12-22);
    // tek satıra sığmaya çalışır; genişlik metne göre, en çok min(kaynak genişliğinin 1.6 katı, ekranın %35'i);
    // yalnız boşlukta, en çok 2 satır; sığmazsa yazı küçülür (en az 11 px), o da yetmezse "…" konur.
    function ogeStil(d, e, o, y) {
      var h = (e.hedef && typeof e.hedef === 'object') ? e.hedef : e;
      var s = y / 1080, bp = sayi(e.boyut_px, 0);
      var px = bp > 0 ? bp : sinirla(Math.round(sayi(e.y2, 0.04) * 1080 * 0.75), 12, 22);
      d._px = Math.max(OGE_EN_AZ_PX, px) * s; d._h = h;
      d._kg = Math.max(sayi(e.g, 0), sayi(h.g, 0));
      d.style.left = sinirla(sayi(h.x, 0), 0, 1) * 100 + '%';
      d.style.top = sinirla(sayi(h.y, 0), 0, 1) * 100 + '%';
      d.style.fontSize = Math.round(d._px * 10) / 10 + 'px';
    }
    function satirlariYaz(el, satirlar) {
      var i; bosalt(el);
      for (i = 0; i < satirlar.length; i++) {
        if (i > 0) { el.appendChild(belge.createElement('br')); }
        el.appendChild(belge.createTextNode(satirlar[i]));
      }
    }
    function ogeSigdir(d) {
      var s = yukseklik() / 1080, en = Math.max(OGE_EN_AZ_PX * s, 1), W = kok.clientWidth || pencere.innerWidth || 1920;
      var H = yukseklik(), h = d._h || {}, kg = d._kg || 0, azami = W * OGE_EN_GENIS, m = d.getElementsByClassName('ak-oge-metin')[0];
      var a = d.getElementsByClassName('ak-oge-aciklama')[0], px = d._px || en, r, sol, ust;
      if (!m) { return; }
      if (kg > 0) { azami = Math.min(azami, Math.max(OGE_KAYNAK_CARPAN * kg * W, OGE_EN_DAR * W)); }
      r = yerlesimBul(d._metin !== undefined ? d._metin : m.textContent, function (t, p) {
        d.style.fontSize = Math.round(p * 10) / 10 + 'px'; m.style.whiteSpace = 'nowrap'; m.textContent = t; return m.getBoundingClientRect().width;
      }, azami, px, en);
      d._metin = r.metin;
      d.style.fontSize = Math.round(r.px * 10) / 10 + 'px';
      satirlariYaz(m, r.satirlar);
      if (a) {
        a.style.whiteSpace = 'nowrap';
        var at = d._aciklama !== undefined ? d._aciklama : a.textContent; d._aciklama = at;
        var ar = yerlesimBul(at, function (t) { a.textContent = t; return a.getBoundingClientRect().width; },
          Math.max(1, azami - 2 * r.dolgu), 0, 0, true);
        satirlariYaz(a, ar.satirlar);
      }
      d._satirlar = r.satirlar; d._px2 = r.px; d._kirpildi = r.kirpildi;
      sol = sinirla(sayi(h.x, 0), 0, 1) * W; ust = sinirla(sayi(h.y, 0), 0, 1) * H;
      d.style.left = Math.max(0, Math.min(sol, W - d.offsetWidth)) + 'px';
      d.style.top = Math.max(0, Math.min(ust, H - d.offsetHeight)) + 'px';
    }
    function ogeIcerik(d, e) {
      var t, a;
      bosalt(d);
      d._metin = e.metin; d._aciklama = e.aciklama || undefined;
      t = oge('ak-oge-metin', d); t.textContent = e.metin;
      if (e.aciklama) { a = oge('ak-oge-aciklama', d); a.textContent = e.aciklama; }
    }
    function ogeKaldir(anahtar) {
      var h = ogeHarita[anahtar], d;
      if (!h) { return; }
      delete ogeHarita[anahtar];
      d = h.el;
      if (sure(EKRAN_MS) <= 0) { sil(d); return; }
      d.className = d.className.replace(/\s*ak-acik/g, '');
      pencere.setTimeout(function () { sil(d); }, EKRAN_MS + 30);
    }
    function ekranSil() {
      var k; for (k in ogeHarita) { if (ogeHarita.hasOwnProperty(k)) { ogeKaldir(k); } }
    }
    function ekranGoster(v) {
      if (!v || !v.ogeler) { ekranSil(); return; }
      var o = olcek(), y = yukseklik(), i, e, d, anahtar, imza, kullanilan = {}, h, k;
      for (i = 0; i < v.ogeler.length; i++) {
        e = v.ogeler[i];
        if (!e || typeof e.metin !== 'string') { continue; }
        imza = ogeImza(e);
        anahtar = (e.id !== undefined && e.id !== null) ? 'i' + e.id : 's' + imza;
        kullanilan[anahtar] = true;
        h = ogeHarita[anahtar];
        if (h) {
          if (h.imza === imza) { continue; }          // aynı yerde aynı yazı: yeniden çizilmez
          ogeStil(h.el, e, o, y); ogeIcerik(h.el, e); ogeSigdir(h.el);  // değişti: yerinde yumuşak güncelle
          h.el.className = 'ak-oge ak-acik ak-' + (e.tur || 'diger'); h.imza = imza;
          continue;
        }
        d = oge('ak-oge ak-' + (e.tur || 'diger'), ekranKatman);
        ogeStil(d, e, o, y); ogeIcerik(d, e); ogeSigdir(d);
        ogeHarita[anahtar] = { el: d, imza: imza };
        reflow(d);
        d.className += ' ak-acik';
      }
      for (k in ogeHarita) { if (ogeHarita.hasOwnProperty(k) && !kullanilan[k]) { ogeKaldir(k); } }
    }

    // ---------- Türkçe dublaj sesi (olay `ses` / `ses-dur`) ----------
    function taban() { var m = /^(https?:\/\/[^\/]+)/.exec(url || ''); return m ? m[1] : ''; }   // PC adresi (TV uygulaması file:// kökenlidir)
    // Sıra: yeni ses öncekini KESMEZ, arkasına eklenir (konuşmalar art arda). Çok gecikmiş (bekleyen
    // > SES_BAYAT_MS) ses atılır. Web Audio varsa onunla çalınır: webOS'te HDMI görüntüsü bir <video>
    // medya hattıdır; Web Audio ikinci bir medya kaynağı açmadığı için HDMI'yi durdurma riski daha düşüktür.
    // (Gerçek LG TV'de DOĞRULANMADI.) Yoksa <audio> sırasıyla çalınır.
    var SES_BAYAT_MS = 6000, sesSira = [], sesCtx = null, sesSon = 0, sesKaynaklar = [];
    function sesBaglam() {
      if (sesCtx) { return sesCtx; }
      var C = pencere.AudioContext || pencere.webkitAudioContext;
      if (!C || sec.webAudio === false) { return null; }
      try { sesCtx = new C(); } catch (x) { sesCtx = null; }
      return sesCtx;
    }
    function sesDurdur() {
      var a = sesNesne, i;
      sesNesne = null; sesSira = [];
      if (a) { try { a.pause(); } catch (x) { /* yok say */ } try { a.removeAttribute('src'); } catch (y) { /* yok say */ } }
      for (i = 0; i < sesKaynaklar.length; i++) { try { sesKaynaklar[i].stop(0); } catch (z) { /* yok say */ } }
      sesKaynaklar = []; sesSon = 0;
    }
    function sesSonraki() {
      var v, a, p;
      if (sesNesne) { return; }
      while (sesSira.length && Date.now() - sesSira[0].gelis > SES_BAYAT_MS) { sesSira.shift(); }
      v = sesSira.shift();
      if (!v) { return; }
      a = new pencere.Audio();
      a.preload = 'auto';
      a.src = taban() + v.url;
      a.onended = function () { if (sesNesne === a) { sesNesne = null; sesSonraki(); } };
      a.onerror = function () { if (sesNesne === a) { sesNesne = null; bildir('onSesHata', v); sesSonraki(); } };
      sesNesne = a;
      try { p = a.play(); if (p && p.catch) { p.catch(function () { if (sesNesne === a) { sesNesne = null; } bildir('onSesHata', v); sesSonraki(); }); } }
      catch (x) { sesNesne = null; bildir('onSesHata', v); }
      bildir('onSes', v);
    }
    function sesWebAudio(ctx, v) {
      var x = new pencere.XMLHttpRequest(), gelis = Date.now();
      x.open('GET', taban() + v.url, true);
      x.responseType = 'arraybuffer';
      x.onload = function () {
        if (x.status !== 200) { bildir('onSesHata', v); return; }
        var bitti = function (tampon) {
          var k, bas;
          if (Date.now() - gelis > SES_BAYAT_MS) { return; }
          if (ctx.state === 'suspended' && ctx.resume) { try { ctx.resume(); } catch (r) { /* yok say */ } }
          k = ctx.createBufferSource(); k.buffer = tampon; k.connect(ctx.destination);
          bas = Math.max(ctx.currentTime + 0.02, sesSon);
          sesSon = bas + tampon.duration;
          k.onended = function () { var i = sesKaynaklar.indexOf(k); if (i >= 0) { sesKaynaklar.splice(i, 1); } };
          sesKaynaklar.push(k);
          try { k.start(bas); } catch (s1) { bildir('onSesHata', v); return; }
          bildir('onSes', v);
        };
        try {
          var p = ctx.decodeAudioData(x.response, bitti, function () { bildir('onSesHata', v); });
          if (p && p.catch) { p.catch(function () { /* hata geri çağrısı bildirdi */ }); }
        } catch (d) { bildir('onSesHata', v); }
      };
      x.onerror = function () { bildir('onSesHata', v); };
      x.send();
    }
    // Tarayıcılar sesi kullanıcı bir tuşa basana dek askıda tutabilir: ilk tuşta açılır
    if (pencere.document && pencere.document.addEventListener) {
      pencere.document.addEventListener('keydown', function () { if (sesCtx && sesCtx.resume) { try { sesCtx.resume(); } catch (x) { /* yok say */ } } }, false);
    }
    function sesCal(v) {
      var ctx;
      if (!v || typeof v.url !== 'string' || v.url.charAt(0) !== '/') { return; }   // yalnız PC'nin kendi yolu
      ctx = sesBaglam();
      if (ctx && ctx.state === 'suspended' && ctx.resume) { try { ctx.resume(); } catch (r) { /* yok say */ } }
      if (ctx && ctx.state !== 'suspended') { sesWebAudio(ctx, v); return; }
      sesSira.push({ url: v.url, id: v.id, yazi_id: v.yazi_id, gelis: Date.now() });
      sesSonraki();
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
      dinle('yazi-sil', function (v) {   // §13.4: silmeyi sunucu t_git + L'de yapar; başka id'li (eski) silme yeni yazıyı silmez
        if (v && v.id !== undefined && v.id !== null && gecerli && gecerli.id !== undefined && gecerli.id !== null && v.id !== gecerli.id) { return; }
        yaziSil();
      });
      dinle('katman-gizle', function () { gizliAyarla(true); });
      dinle('katman-goster', function () { gizliAyarla(false); });
      dinle('ekran', function (v) { ekranGoster(v); });
      dinle('ekran-sil', function () { ekranSil(); });
      dinle('ses', function (v) { sesCal(v); });
      dinle('ses-dur', function () { sesDurdur(); });
      dinle('gorunum', function (v) { gorunumUygula(v); });
      dinle('durum', function (v) { bildir('onBilgi', v); });
    }

    // §13.1: yazılar gizlendi/gösteriliyor (çeviri sürer; yalnız çizim saklanır)
    function gizliAyarla(g) {
      var var_ = / ?ak-gizli\b/.test(kok.className);
      if (g && !var_) { kok.className += ' ak-gizli'; }
      else if (!g) { kok.className = kok.className.replace(/\s*ak-gizli\b/g, ''); }
      bildir('onGizli', !!g);
    }

    function yeniden() { gorunumUygula(); }
    pencere.addEventListener('resize', yeniden, false);

    function durdur() {
      durduruldu = true; kapat(); sesDurdur();
      if (bekle) { pencere.clearTimeout(bekle); } if (gozcu) { pencere.clearTimeout(gozcu); }
      if (gizle) { pencere.clearTimeout(gizle); gizle = null; }
      kutu = null; gecerli = null; ayrilanlar = []; bosalt(sahne); oncekiTemizle(); yazi.style.display = 'none';
      bosalt(ekranKatman); ogeHarita = {};
      pencere.removeEventListener('resize', yeniden, false);
    }

    gorunumUygula();
    oncekiTemizle();
    if (url) { durumDegistir('baglaniyor'); baglan(); } else { durumDegistir('bagli'); }

    return {
      durdur: durdur, yaziGoster: yaziGoster, yaziSil: function () { yaziSil(); }, ekranGoster: ekranGoster, ekranSil: ekranSil, gizliAyarla: gizliAyarla,
      gorunumUygula: gorunumUygula,
      sesCal: sesCal, sesDurdur: sesDurdur,
      durumu: function () { return durum; },
      sonYazi: function () { return sonYazi; }
    };
  }

  pencere.AKOverlay = { baslat: baslat, yerlesimBul: yerlesimBul };
}(window));
