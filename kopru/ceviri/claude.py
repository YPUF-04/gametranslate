# SPDX-License-Identifier: AGPL-3.0-only
"""Claude motoru (resmi anthropic SDK)."""
from __future__ import annotations

from typing import Any

from . import istem
from .temel import AgHatasi, AnahtarHatasi, Baglam, Ceviri, MotorHatasi

MODELLER = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]


class ClaudeMotoru:
    kod = "claude"
    ad = "Claude"
    anahtar_gerekli = True
    cevrimdisi = False
    ucretsiz = False
    baglam_destekler = True

    def __init__(self, anahtar: str | None, model: str = MODELLER[0], istemci: Any = None) -> None:
        self._anahtar = anahtar
        self.model = model
        self._istemci = istemci

    def _al(self) -> Any:
        if self._istemci is None:
            if not self._anahtar:
                raise AnahtarHatasi("claude")
            import anthropic
            self._istemci = anthropic.AsyncAnthropic(
                api_key=self._anahtar, timeout=8.0, max_retries=1)
        return self._istemci

    async def cevir(self, metinler: list[str], kaynak: str, hedef: str,
                    sozluk: dict[str, str], aciklama: bool = False,
                    baglam: Baglam | None = None) -> list[Ceviri]:
        import anthropic
        if not metinler:
            return []
        istemci = self._al()
        try:
            yanit = await istemci.messages.create(
                model=self.model,
                max_tokens=2000,
                output_config={"effort": "low"},
                system=istem.sistem_bloklari(kaynak, hedef, sozluk, aciklama, baglam),
                messages=[{"role": "user", "content": istem.kullanici_metni(metinler, baglam)}],
            )
        except anthropic.AuthenticationError as e:
            raise AnahtarHatasi("claude") from e
        except (anthropic.APIConnectionError, anthropic.APITimeoutError,
                anthropic.InternalServerError, anthropic.RateLimitError) as e:
            raise AgHatasi(str(type(e).__name__)) from e
        if getattr(yanit, "stop_reason", None) == "refusal":
            # Model reddetti: asıl metni olduğu gibi göster
            return [Ceviri(m) for m in metinler]
        ham = "".join(b.text for b in yanit.content if getattr(b, "type", "") == "text")
        try:
            sonuc, terimler = istem.yaniti_coz_tam(ham, len(metinler), aciklama)
        except ValueError as e:
            raise MotorHatasi("Claude yanıtı okunamadı") from e
        if baglam is not None:
            baglam.yeni_terimler.extend(terimler)
        return sonuc
