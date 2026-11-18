# SPDX-License-Identifier: AGPL-3.0-only
"""Kullanıcıya görünen metinler (tr + en). Ne oldu + ne yapmalı, tek cümle."""
from __future__ import annotations

HATALAR: dict[str, dict[str, str]] = {
    "yalniz_yerel": {
        "tr": "Bu sayfaya yalnızca bu bilgisayardan erişilebilir.",
        "en": "This page is only available from this computer."},
    "gecersiz_istek": {
        "tr": "İstek okunamadı, lütfen sayfayı yenileyip tekrar deneyin.",
        "en": "The request could not be read, please refresh the page and try again."},
    "gecersiz_ayar": {
        "tr": "Bu ayar değeri geçersiz, lütfen listeden bir seçenek seçin.",
        "en": "This setting value is invalid, please pick one from the list."},
    "bulunamadi": {
        "tr": "Aranan sayfa bulunamadı.", "en": "The requested page was not found."},
    "anahtar_yok": {
        "tr": "Bu çeviri motoru için anahtar girilmemiş, lütfen ayarlardan anahtarı ekleyin.",
        "en": "No key is saved for this translation engine, please add it in settings."},
    "anahtar_gecersiz": {
        "tr": "Anahtar kabul edilmedi, lütfen anahtarı kontrol edip yeniden girin.",
        "en": "The key was not accepted, please check it and enter it again."},
    "ag_hatasi": {
        "tr": "Çeviri servisine ulaşılamadı, internet bağlantınızı kontrol edin.",
        "en": "The translation service could not be reached, please check your internet connection."},
    "motor_hatasi": {
        "tr": "Çeviri motoru çalışmadı, başka bir motor seçmeyi deneyin.",
        "en": "The translation engine failed, please try another engine."},
    "kasa_yok": {
        "tr": "Bu bilgisayarda güvenli anahtar kasası bulunamadı, anahtar kaydedilemedi; "
              "işletim sisteminin parola/anahtarlık hizmetini açın ve tekrar deneyin.",
        "en": "No secure key vault was found on this computer so the key was not saved; "
              "enable the system keyring service and try again."},
    "kasa_hata": {
        "tr": "Anahtar kasasına erişilemedi, kasanın kilidini açıp tekrar deneyin.",
        "en": "The key vault could not be accessed, please unlock it and try again."},
    "yakalama_yok": {
        "tr": "Ekran görüntüsü alınamadı, ekran kaynağını ve izinleri kontrol edin.",
        "en": "The screen could not be captured, please check the source and permissions."},
    "kaynak_yok": {
        "tr": "Yakalanacak ekran seçilmemiş, lütfen listeden oyunun göründüğü ekranı seçin.",
        "en": "No screen is selected, please pick the screen that shows the game."},
    "okuma_yok": {
        "tr": "Ekrandaki yazıyı okuyacak bileşen kurulu değil, kurulum kılavuzuna bakın.",
        "en": "No text recognition component is installed, please see the setup guide."},
    "oyun_yok": {
        "tr": "Bu oyun bulunamadı, lütfen listeden mevcut bir oyun seçin ya da yeni oyun ekleyin.",
        "en": "This game was not found, please pick one from the list or add a new game."},
    "oyun_gecersiz": {
        "tr": "Oyun adı geçersiz, lütfen en fazla 100 karakterlik bir ad yazın.",
        "en": "The game name is invalid, please enter a name of up to 100 characters."},
    "paket_gecersiz": {
        "tr": "Bu dosya geçerli bir çeviri paketi değil, lütfen AltYazıKöprüsü'nden alınmış "
              ".akpaket dosyası seçin.",
        "en": "This file is not a valid translation pack, please choose an .akpaket file "
              "exported from AltYazıKöprüsü."},
    "paket_buyuk": {
        "tr": "Çeviri paketi çok büyük (en fazla 50 MB), lütfen daha küçük bir paket seçin.",
        "en": "The translation pack is too large (50 MB at most), please choose a smaller one."},
    "oneri_yok": {
        "tr": "Bu öneri artık listede yok, lütfen öneri listesini yenileyin.",
        "en": "This suggestion is no longer in the list, please refresh the suggestions."},
    "sunucu_hatasi": {
        "tr": "Beklenmeyen bir sorun oluştu, programı yeniden başlatmayı deneyin.",
        "en": "Something unexpected went wrong, please try restarting the program."},
}

DIGER: dict[str, dict[str, str]] = {
    "deneme_tr": {"tr": "Merhaba! Bu bir deneme altyazısıdır.", "en": "Hello! This is a test subtitle."},
    "tv_adres": {"tr": "TV'de bu adresi açın: {adres}", "en": "Open this address on the TV: {adres}"},
    "panel_adres": {"tr": "Kontrol paneli: {adres}", "en": "Control panel: {adres}"},
    "demo_acik": {"tr": "Deneme modu: örnek altyazılar gönderiliyor.",
                  "en": "Demo mode: sending sample subtitles."},
    "durdu": {"tr": "Kapatıldı.", "en": "Stopped."},
}


def mesaj(kod: str, dil: str = "tr") -> str:
    tablo = HATALAR.get(kod) or DIGER.get(kod) or HATALAR["sunucu_hatasi"]
    return tablo.get(dil) or tablo["tr"]
