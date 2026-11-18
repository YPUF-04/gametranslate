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
    "okuma_yok": {
        "tr": "Ekrandaki yazıyı okuyacak bileşen kurulu değil, kurulum kılavuzuna bakın.",
        "en": "No text recognition component is installed, please see the setup guide."},
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
