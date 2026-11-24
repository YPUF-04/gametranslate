# SPDX-License-Identifier: AGPL-3.0-only
"""PROTOKOL 20.3: LG ekranı kararmasın. Bilgisayar, TV'nin yerel ağdaki SSAP kanalına (ws 3000 / wss 3001) bir kez
eşleşir (TV ekranında izin sorusu çıkar), sonra çeviri sürerken 120 sn'de bir iki zararsız imleç hareketi gönderir.

İstemci anahtarı şifreli kasadadır (`keyring`, ad `lg_ssap`); ayar dosyasına, günlüğe, yanıta girmez.
Gerçek bir LG TV'de DOĞRULANMADI (geliştirme ortamında TV yok); sahte SSAP sunucusuyla sınanır.
"""
from __future__ import annotations

import asyncio
import json
import logging
import ssl
import time
from typing import Any, Callable

import aiohttp

from .. import anahtarlar
from .lg_ssap_manifest import MANIFEST

log = logging.getLogger("kopru.lg_uyanik")
KASA_ADI = "lg_ssap"
ARALIK_SN = 120.0
ESLESME_SN = 60.0
BAGLANTI_SN = 6.0
EN_COK_HATA = 3
IMLEC = "ssap://com.webos.service.networkinput/getPointerInputSocket"

MESAJ = {
    "tr": {"kapali": "Kapalı.", "adres_yok": "LG TV bulunamadı: TV'de /tv sayfasını ya da LG uygulamasını açın.",
           "eslesme_yok": "TV ile eşleşmedi: 'TV ile eşleştir'e basın, TV'de çıkan soruya Kabul et deyin.",
           "esleniyor": "TV'nin ekranındaki soruya kumandayla 'Kabul et' deyin (60 sn).",
           "bekliyor": "Hazır: çeviri başlayınca TV ekranı açık tutulur.",
           "calisiyor": "TV ekranı açık tutuluyor.", "ag": "TV'ye ulaşılamadı (TV kapalı ya da başka ağda).",
           "reddedildi": "TV eşleşmeyi reddetti. Yeniden deneyin ve 'Kabul et'i seçin.",
           "zaman_asimi": "TV'de soru yanıtlanmadı. Yeniden deneyin.",
           "kasa_yok": "Bu bilgisayarda şifreli kasa yok: eşleşme saklanamıyor, her açılışta yeniden sorulur."},
    "en": {"kapali": "Off.", "adres_yok": "No LG TV found: open the /tv page or the LG app on the TV.",
           "eslesme_yok": "Not paired: press 'Pair with TV' and accept the prompt on the TV.",
           "esleniyor": "Accept the prompt on the TV screen with the remote (60 s).",
           "bekliyor": "Ready: the TV screen is kept on while translating.",
           "calisiyor": "Keeping the TV screen on.", "ag": "Could not reach the TV (off or on another network).",
           "reddedildi": "The TV refused pairing. Try again and choose 'Accept'.",
           "zaman_asimi": "The prompt on the TV was not answered. Try again.",
           "kasa_yok": "No secure keychain on this PC: pairing cannot be stored."},
}


class SsapHatasi(Exception):
    def __init__(self, kod: str) -> None:
        super().__init__(kod)
        self.kod = kod


def _ssl_baglami() -> ssl.SSLContext:
    """TV'nin sertifikası kendinden imzalıdır (LG): doğrulanamaz; yalnız yerel ağdaki TV adresine kullanılır."""
    b = ssl.create_default_context()
    b.check_hostname = False
    b.verify_mode = ssl.CERT_NONE
    return b


class LgUyanik:
    def __init__(self, ayar: Callable[[], dict[str, Any]], calisiyor: Callable[[], bool],
                 tv_adresi: Callable[[], str | None], adresler: Callable[[str], list[str]] | None = None,
                 saat: Callable[[], float] = time.time) -> None:
        self._ayar = ayar
        self._calisiyor = calisiyor
        self._tv_adresi = tv_adresi
        # (adres) -> denenecek ws adresleri; testte sahte sunucu verilir
        self._adresler = adresler or (lambda ip: [f"wss://{ip}:3001/", f"ws://{ip}:3000/"])
        self.saat = saat
        self.durum = "kapali"
        self.hata: str | None = None
        self.son_dokunus: float | None = None
        self._ardisik = 0
        self._esleme: asyncio.Task | None = None
        self._anahtar_onbellek: str | None = None

    # ---- ayar / kasa ----
    def _a(self) -> dict[str, Any]:
        return self._ayar().get("lg_uyanik") or {}

    def acik(self) -> bool:
        return self._a().get("acik") is True

    def adres(self) -> str | None:
        return self._a().get("adres") or self._tv_adresi() or None

    def anahtar(self) -> str | None:
        if self._anahtar_onbellek:
            return self._anahtar_onbellek
        try:
            self._anahtar_onbellek = anahtarlar.oku(KASA_ADI)
        except Exception:   # noqa: BLE001 — kasa yok/kilitli
            self._anahtar_onbellek = None
        return self._anahtar_onbellek

    def _anahtar_yaz(self, deger: str | None) -> bool:
        self._anahtar_onbellek = deger
        try:
            anahtarlar.yaz(KASA_ADI, deger or "")   # boş = sil
            return True
        except Exception:   # noqa: BLE001
            return False

    def unut(self) -> None:
        self._anahtar_yaz(None)
        self.hata = None

    # ---- SSAP ----
    async def _baglan(self, oturum: aiohttp.ClientSession, ip: str) -> aiohttp.ClientWebSocketResponse:
        son: Exception | None = None
        for url in self._adresler(ip):
            try:
                return await oturum.ws_connect(url, ssl=_ssl_baglami() if url.startswith("wss:") else True,
                                               timeout=aiohttp.ClientWSTimeout(ws_close=3),
                                               heartbeat=None, autoping=True, max_msg_size=1 << 20,
                                               proxy=None)
            except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as e:
                son = e
        raise SsapHatasi("ag") from son

    async def _kaydol(self, ws: aiohttp.ClientWebSocketResponse, anahtar: str | None, sure: float) -> str:
        yuk: dict[str, Any] = {"forcePairing": False, "pairingType": "PROMPT", "manifest": MANIFEST}
        if anahtar:
            yuk["client-key"] = anahtar
        await ws.send_str(json.dumps({"type": "register", "id": "kayit", "payload": yuk}))
        bitis = time.monotonic() + sure
        while True:
            kalan = bitis - time.monotonic()
            if kalan <= 0:
                raise SsapHatasi("zaman_asimi")
            try:
                m = await ws.receive(timeout=kalan)
            except asyncio.TimeoutError:
                raise SsapHatasi("zaman_asimi") from None
            if m.type != aiohttp.WSMsgType.TEXT:
                raise SsapHatasi("ag")
            try:
                v = json.loads(m.data)
            except ValueError:
                continue
            if v.get("type") == "registered":
                k = (v.get("payload") or {}).get("client-key")
                if not isinstance(k, str) or not k or len(k) > 200:
                    raise SsapHatasi("reddedildi")
                return k
            if v.get("type") == "error":
                raise SsapHatasi("reddedildi")
            # {"type":"response","payload":{"pairingType":"PROMPT"}}: TV soruyu gösterdi; beklemeye devam

    async def _istek(self, ws: aiohttp.ClientWebSocketResponse, uri: str) -> dict[str, Any]:
        await ws.send_str(json.dumps({"type": "request", "id": "imlec", "uri": uri}))
        while True:
            m = await ws.receive(timeout=BAGLANTI_SN)
            if m.type != aiohttp.WSMsgType.TEXT:
                raise SsapHatasi("ag")
            v = json.loads(m.data)
            if v.get("id") == "imlec":
                if v.get("type") == "error":
                    raise SsapHatasi("reddedildi")
                return v.get("payload") or {}

    async def esle(self) -> str:
        """TV'de izin sorusu çıkarır; kabul edilirse anahtarı kasaya yazar. Hata kodu ya da 'tamam'."""
        ip = self.adres()
        if not ip:
            self.hata = "adres_yok"
            return "adres_yok"
        self.durum, self.hata = "esleniyor", None
        try:
            async with aiohttp.ClientSession() as oturum:
                ws = await self._baglan(oturum, ip)
                async with ws:
                    k = await self._kaydol(ws, self.anahtar(), ESLESME_SN)
        except SsapHatasi as e:
            self.durum, self.hata = "hata", e.kod
            return e.kod
        except (aiohttp.ClientError, OSError, asyncio.TimeoutError):
            self.durum, self.hata = "hata", "ag"
            return "ag"
        if not self._anahtar_yaz(k):
            self.hata = "kasa_yok"
        self.durum = "bekliyor"
        return "tamam"

    def esle_baslat(self) -> None:
        if self._esleme is None or self._esleme.done():
            self.durum, self.hata = "esleniyor", None
            self._esleme = asyncio.get_running_loop().create_task(self.esle())

    async def dokun(self) -> None:
        """Kayıtlı anahtarla bağlanır, imleci 1 piksel oynatıp geri alır (ekran koruyucu sayacı sıfırlanır)."""
        ip, anahtar = self.adres(), self.anahtar()
        if not ip:
            raise SsapHatasi("adres_yok")
        if not anahtar:
            raise SsapHatasi("eslesme_yok")
        async with aiohttp.ClientSession() as oturum:
            ws = await self._baglan(oturum, ip)
            async with ws:
                k = await self._kaydol(ws, anahtar, BAGLANTI_SN)
                if k != anahtar:
                    self._anahtar_yaz(k)
                yol = (await self._istek(ws, IMLEC)).get("socketPath")
            if not isinstance(yol, str) or not yol.startswith(("ws://", "wss://")):
                raise SsapHatasi("ag")
            imlec = await oturum.ws_connect(yol, ssl=_ssl_baglami() if yol.startswith("wss:") else True,
                                            heartbeat=None, proxy=None)
            async with imlec:
                for dx in (1, -1):
                    await imlec.send_str(f"type:move\ndx:{dx}\ndy:0\ndown:0\n\n")
                    await asyncio.sleep(0.05)
        self.son_dokunus = self.saat()

    async def adim(self) -> None:
        """Döngünün bir adımı: açık + çeviri çalışıyor + eşleşmiş ise dokunur."""
        if self._esleme is not None and not self._esleme.done():
            return
        if not self.acik():
            self.durum = "kapali"
            return
        if not self._calisiyor() or not self.anahtar() or not self.adres():
            if self.durum not in ("hata",):
                self.durum = "bekliyor"
            return
        try:
            await asyncio.wait_for(self.dokun(), BAGLANTI_SN * 3)
            self._ardisik, self.durum, self.hata = 0, "calisiyor", None
        except (SsapHatasi, aiohttp.ClientError, OSError, asyncio.TimeoutError, ValueError) as e:
            self._ardisik += 1
            kod = e.kod if isinstance(e, SsapHatasi) else "ag"
            log.info("LG ekranı uyanık tutma adımı başarısız: %s", kod)
            if kod == "reddedildi":   # anahtar geçersiz (TV sıfırlandı): yeniden eşleşme gerekir
                self._anahtar_yaz(None)
            if self._ardisik >= EN_COK_HATA or kod == "reddedildi":
                self.durum, self.hata = "hata", kod

    async def dongu(self) -> None:
        while True:
            try:
                await self.adim()
            except Exception:   # noqa: BLE001 — döngü ölmesin
                log.exception("LG uyanık tutma döngüsü")
            await asyncio.sleep(ARALIK_SN)

    def bilgi(self, dil: str = "tr") -> dict[str, Any]:
        eslesti = bool(self.anahtar())
        d = self.durum if self.acik() or self.durum == "esleniyor" else "kapali"
        if d == "kapali" and self.acik():
            d = "bekliyor"
        if self.hata:
            kod = self.hata
        elif d == "kapali":
            kod = "kapali"
        elif not self.adres():
            kod = "adres_yok"
        elif not eslesti and d != "esleniyor":
            kod = "eslesme_yok"
        else:
            kod = d
        return {"acik": self.acik(), "adres": self.adres(), "eslesti": eslesti, "durum": d,
                "son_dokunus": int(self.son_dokunus) if self.son_dokunus else None,
                "hata": self.hata, "mesaj": MESAJ["en" if dil == "en" else "tr"].get(kod, "")}
