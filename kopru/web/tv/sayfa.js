// SPDX-License-Identifier: AGPL-3.0-only
// tv.html ve obs.html için: aynı kökenden /kopru/akis akışına bağlanır.
(function () {
  'use strict';
  if (window.MARKA && window.MARKA.ad) { document.title = window.MARKA.ad; }
  var q = window.location.search || '';
  var url = '/kopru/akis';
  var m = /[?&]akis=([^&]+)/.exec(q);
  if (m) { url = decodeURIComponent(m[1]); }
  var obs = /[?&]obs=1/.test(q) || document.documentElement.getAttribute('data-obs') === '1';
  // §17.3: /tv sayfası "+30 dk" reklamını oynatabilir; /obs ASLA (yayına reklam girmesin)
  var reklam = null, reklamVar = !obs && !!window.AKReklam && !m;
  if (reklamVar) { url += (url.indexOf('?') < 0 ? '?' : '&') + 'reklam=1'; }
  function bittiGonder(v, s, deneme) {
    var x = new XMLHttpRequest();
    x.open('POST', v.bitti || '/kopru/reklam/bitti', true); x.setRequestHeader('Content-Type', 'text/plain;charset=UTF-8');   // ön istek (CORS preflight) olmasın
    x.onload = function () {   // erken sayıldıysa (saat farkı) biraz bekleyip yeniden dene
      if (x.status === 409 && deneme < 5) { setTimeout(function () { bittiGonder(v, s, deneme + 1); }, 2000); }
    };
    x.send(JSON.stringify({ id: s.id, sure_sn: s.sure_sn }));
  }
  window.AKOverlay.baslat(url, document.getElementById('kok'), {
    durumRozeti: !obs,
    onReklam: !reklamVar ? null : function (v) {
      if (!v || !v.id || reklam) { return; }
      var tr = (navigator.language || 'tr').toLowerCase().indexOf('tr') === 0;
      reklam = window.AKReklam.oynat(document.body, { id: v.id, vast: v.vast, en_az_sn: v.en_az_sn,
        metin: tr ? null : { reklam: 'Ad', sn: 's', destek: 'Thank you for supporting {marka}', destek_alt: '30 minutes of dubbing time will be added shortly.' },
        bitti: function (s) { reklam = null; bittiGonder(v, s, 0); } });
    },
    onReklamBitti: function () { if (reklam) { reklam.durdur(); reklam = null; } }
  });
}());
