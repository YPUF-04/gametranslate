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
  window.AKOverlay.baslat(url, document.getElementById('kok'), { durumRozeti: !obs });
}());
