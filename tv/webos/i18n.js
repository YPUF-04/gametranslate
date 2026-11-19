// SPDX-License-Identifier: AGPL-3.0-only
// Arayüz metinleri: tarayıcı dili Türkçe ise Türkçe, değilse İngilizce.
(function () {
  'use strict';
  var M = {
    tr: {
      ara_baslik: 'Bilgisayarı arıyorum…',
      ara_ilerleme: 'Ağda aranıyor: %1 / %2',
      ara_bitti: 'Arama bitti.',
      bulunan: 'Bulunan bilgisayarlar',
      bulunamadi: 'Bilgisayar bulunamadı. Bilgisayarda {marka} açık ve TV ile aynı ağda mı, bakıp yeniden arayın.',
      yeniden: 'Yeniden ara',
      elle: 'Adresi elle gir',
      deneme: 'Deneme (bilgisayarsız)',
      kayitli_bakiliyor: 'Son bilgisayara bağlanılıyor…',
      adres_alinamadi: 'TV’nin ağ adresi alınamadı. Bilgisayarın adresini elle girin.',
      hdmi_baslik: 'Oyun cihazı hangi girişte?',
      hdmi_ipucu: 'Bağlı olduğu HDMI numarasını seçin. Seçiminiz hatırlanır.',
      geri: 'Geri',
      elle_baslik: 'Bilgisayarın adresi',
      elle_ipucu: 'Bilgisayardaki {marka} ekranında yazan adresi girin. Örnek: 192.168.1.20',
      tamam: 'Tamam',
      iptal: 'Vazgeç',
      sil: 'Sil',
      adres_hatali: 'Adres geçersiz. 192.168.1.20 gibi dört sayı yazın.',
      baglanamadi: 'Bu adrese bağlanılamadı. Bilgisayarın açık ve aynı ağda olduğunu kontrol edin.',
      hdmi_hata: 'HDMI görüntüsü açılamadı. Kablonun takılı olduğundan emin olup başka bir HDMI seçin.',
      ipucu_calisiyor: 'Bilgi için OK tuşuna basın',
      panel_baslik: 'Bilgi',
      p_bilgisayar: 'Bilgisayar',
      p_baglanti: 'Bağlantı',
      p_son: 'Son altyazı',
      p_hdmi: 'Giriş',
      p_surum: 'Sürüm',
      p_ceviri: 'Çeviri',
      d_baglaniyor: 'Bağlanıyor…',
      d_bagli: 'Bağlı',
      d_koptu: 'Koptu, yeniden deneniyor',
      d_yok: 'Bağlı değil',
      yok: '-',
      kapat: 'Kapat',
      hdmi_degistir: 'Girişi değiştir',
      pc_degistir: 'Bilgisayarı değiştir',
      demo_not: 'Deneme kipi: bilgisayar gerekmez. Çıkmak için Geri tuşuna basın.',
      cikis: 'Uygulamadan çık',
      rozet_koptu: 'Bağlantı koptu, yeniden deneniyor…',
      rozet_baglaniyor: 'Bağlanıyor…'
    },
    en: {
      ara_baslik: 'Looking for your computer…',
      ara_ilerleme: 'Searching the network: %1 / %2',
      ara_bitti: 'Search finished.',
      bulunan: 'Computers found',
      bulunamadi: 'No computer found. Check that {marka} is open on your computer and on the same network as the TV, then search again.',
      yeniden: 'Search again',
      elle: 'Enter address',
      deneme: 'Try without a computer',
      kayitli_bakiliyor: 'Connecting to your last computer…',
      adres_alinamadi: 'Could not read the TV’s network address. Please enter the computer’s address by hand.',
      hdmi_baslik: 'Which input is your game device on?',
      hdmi_ipucu: 'Pick the HDMI number it is plugged into. Your choice is remembered.',
      geri: 'Back',
      elle_baslik: 'Computer address',
      elle_ipucu: 'Type the address shown in the {marka} window on your computer. Example: 192.168.1.20',
      tamam: 'OK',
      iptal: 'Cancel',
      sil: 'Delete',
      adres_hatali: 'That address is not valid. Type four numbers like 192.168.1.20.',
      baglanamadi: 'Could not reach that address. Check that the computer is on and on the same network.',
      hdmi_hata: 'The HDMI picture could not be opened. Check the cable and pick another HDMI input.',
      ipucu_calisiyor: 'Press OK for info',
      panel_baslik: 'Info',
      p_bilgisayar: 'Computer',
      p_baglanti: 'Connection',
      p_son: 'Last subtitle',
      p_hdmi: 'Input',
      p_surum: 'Version',
      p_ceviri: 'Translation',
      d_baglaniyor: 'Connecting…',
      d_bagli: 'Connected',
      d_koptu: 'Lost, retrying',
      d_yok: 'Not connected',
      yok: '-',
      kapat: 'Close',
      hdmi_degistir: 'Change input',
      pc_degistir: 'Change computer',
      demo_not: 'Trial mode: no computer needed. Press Back to leave.',
      cikis: 'Exit app',
      rozet_koptu: 'Connection lost, retrying…',
      rozet_baglaniyor: 'Connecting…'
    }
  };
  var dil = String((navigator.language || navigator.userLanguage || 'tr')).toLowerCase().indexOf('tr') === 0 ? 'tr' : 'en';
  window.AKI18N = {
    dil: dil,
    t: function (k, a) {
      var s = (M[dil][k] !== undefined) ? M[dil][k] : (M.tr[k] !== undefined ? M.tr[k] : k), i;
      if (a) { for (i = 0; i < a.length; i++) { s = s.replace('%' + (i + 1), String(a[i])); } }
      return s.split('{marka}').join((window.MARKA && window.MARKA.ad) || 'AltYazıKöprüsü');
    },
    uygula: function (kok) {
      var l = (kok || document).querySelectorAll('[data-i]'), i;
      for (i = 0; i < l.length; i++) { l[i].textContent = window.AKI18N.t(l[i].getAttribute('data-i')); }
    }
  };
}());
