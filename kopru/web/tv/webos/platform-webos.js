// SPDX-License-Identifier: AGPL-3.0-only
// webOS'a özgü işler. Samsung (Tizen) için ileride platform-tizen.js aynı arayüzü sağlayacak:
//   geriTusu, hdmiAc(girisNo, kutu, bildir), yerelAdres(cb), exit()
// Yalnızca GENEL Luna API'leri kullanılır (com.palm.connectionmanager/getStatus -> requiredACG: network.query).
(function () {
  'use strict';

  function luna(uri, params, cb) {
    try {
      var kopru = new window.PalmServiceBridge();
      kopru.onservicecallback = function (mesaj) {
        var v = null; try { v = JSON.parse(mesaj); } catch (e) { v = null; }
        cb(v);
      };
      kopru.call(uri, JSON.stringify(params || {}));
      return true;
    } catch (e) { return false; }
  }

  window.AKPlatform = {
    ad: 'webos',
    geriTusu: 461,

    // TV'nin kendi yerel adresi (alt ağı taramak için). Alınamazsa cb(null).
    yerelAdres: function (cb) {
      var bitti = false;
      function don(ip) { if (!bitti) { bitti = true; cb(ip); } }
      var var_ = typeof window.PalmServiceBridge !== 'undefined';
      if (!var_) { don(null); return; }
      var tamam = luna('luna://com.palm.connectionmanager/getStatus', {}, function (v) {
        var ip = null;
        if (v) {
          if (v.wired && v.wired.state === 'connected' && v.wired.ipAddress) { ip = v.wired.ipAddress; }
          else if (v.wifi && v.wifi.state === 'connected' && v.wifi.ipAddress) { ip = v.wifi.ipAddress; }
        }
        don(ip);
      });
      if (!tamam) { don(null); } else { window.setTimeout(function () { don(null); }, 4000); }
    },

    // HDMI girişini tam ekran gösterir. kutu: video'nun konacağı kutu. bildir('tamam' | 'hata').
    // Ekran koruyucu: dışarıdan görüntü oynarken TV genellikle devreye sokmaz; ayrıca bir şey yapılmaz.
    hdmiAc: function (girisNo, kutu, bildir) {
      kutu.innerHTML = '';
      var v = document.createElement('video');
      v.setAttribute('autoplay', 'autoplay');
      v.className = 'hdmi-video';
      var s = document.createElement('source');
      s.setAttribute('type', 'service/webos-external');
      s.setAttribute('src', 'ext://hdmi:' + girisNo);
      v.appendChild(s);
      v.addEventListener('error', function () { bildir('hata'); }, false);
      s.addEventListener('error', function () { bildir('hata'); }, false);
      v.addEventListener('playing', function () { bildir('tamam'); }, false);
      kutu.appendChild(v);
      try { var oy = v.play(); if (oy && oy.catch) { oy.catch(function () { /* autoplay yeter; kapatılınca kesilir */ }); } } catch (e) { /* autoplay yeter */ }
      return function kapat() { try { v.pause(); } catch (e) { /* yok say */ } kutu.innerHTML = ''; };
    },

    cik: function () {
      try { if (window.webOS && window.webOS.platformBack) { window.webOS.platformBack(); return; } } catch (e) { /* devam */ }
      try { window.close(); } catch (e2) { /* devam */ }
    }
  };
}());
