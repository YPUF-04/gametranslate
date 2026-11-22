# SPDX-License-Identifier: AGPL-3.0-only
"""Altyazı gösterim sırası (PROTOKOL §16.4): hiçbir satır atlanmaz, sırayla gösterilir, geride kalınca kuyruk
satır atarak değil boşluğu kırparak yetişir. Saf mantık: saat dışarıdan verilir (sahte saatle sınanır)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

OKUMA_EN_AZ_S = 1.2       # okuma tabanı alt sınırı (en_az_ms > 0 iken)
OKUMA_EN_COK_S = 3.5      # okuma tabanı üst sınırı
KARAKTER_MS_VARSAYILAN = 60
GERIDE_S = 0.3           # bu kadardan fazla birikme "geride kalındı" sayılır (kare aralığı + pay)
YENI_BEKLE_S = 2.0        # kaynak boşalmadan değişti, yenisi henüz çevriliyor: eskisi en çok bu kadar bekler
ESIK = 1e-9


def okuma_tabani(metin: str, en_az_s: float, karakter_ms: float = KARAKTER_MS_VARSAYILAN) -> float:
    """§16.4: okuma_i = min(3,5, max(1,2, karakter × karakter_ms)); en_az 0 ise taban yok."""
    if en_az_s <= 0:
        return 0.0
    return max(en_az_s, min(OKUMA_EN_COK_S, max(OKUMA_EN_AZ_S, len(metin or "") * karakter_ms / 1000)))


@dataclass(eq=False)
class SiraSatiri:
    """Kuyruktaki bir altyazı satırı."""
    id: str
    gel: float                       # t_gel: kaynağın ilk görüldüğü kare anı
    git: float | None = None         # t_git: kaynağın gittiği ya da yerine yenisinin geldiği an
    git_tur: str = ""                # "kayip" | "yeni"
    hazir: float | None = None       # çevirinin hazır olduğu an (t_hazir)
    metin: str | None = None         # çeviri
    hata: bool = False               # çeviri başarısız: kuyruktan çıkar
    goster: float | None = None      # ekrana geldiği an (g_i)
    zincir: bool = False             # önceki satırın yerine geçerek gösterildi (§16.4 diyalog zinciri)
    guncel: bool = False             # gösterilirken çevirisi yenilendi (yerinde güncelle)
    ek: dict[str, Any] = field(default_factory=dict)   # çağıranın verisi (kaynak metin, kutu, görev...)


class GosterimSirasi:
    def __init__(self, en_az_s: float = 0.8, karakter_ms: float = KARAKTER_MS_VARSAYILAN,
                 yeni_bekle_s: float = YENI_BEKLE_S) -> None:
        self.en_az_s = en_az_s
        self.karakter_ms = karakter_ms
        self.yeni_bekle_s = yeni_bekle_s
        self.satirlar: list[SiraSatiri] = []    # gösterilen (varsa en başta) + bekleyenler, sırayla
        self.gosterilen: SiraSatiri | None = None

    # -- kuyruk --
    def ekle(self, s: SiraSatiri) -> SiraSatiri:
        self.satirlar.append(s)
        return s

    def son(self) -> SiraSatiri | None:
        return self.satirlar[-1] if self.satirlar else None

    def bekleyenler(self) -> list[SiraSatiri]:
        return [s for s in self.satirlar if s is not self.gosterilen]

    def temizle(self) -> None:
        self.satirlar, self.gosterilen = [], None

    def _sonraki(self) -> SiraSatiri | None:
        for s in self.satirlar:
            if s is not self.gosterilen and not s.hata:
                return s
        return None

    def taban(self, s: SiraSatiri, nxt: SiraSatiri | None) -> float:
        """§16.4: satırın en az gösterim süresi. Geride kalınmışsa okuma tabanı (uzunluğa göre), diyalog
        zincirinde en az 1,2 sn, tek başına satırda `en_az`."""
        if self.en_az_s <= 0:
            return 0.0
        nxt_hazir = nxt is not None and nxt.hazir is not None
        g = s.goster if s.goster is not None else 0.0
        geride = s.hazir is not None and g - s.hazir > GERIDE_S
        if nxt_hazir and s.git is not None and nxt.hazir < s.git + max(0.0, g - s.gel) - GERIDE_S:  # type: ignore[union-attr]
            geride = True   # sonraki, bunun doğal bitişinden belirgin önce hazır: kuyruk birikti
        if geride:
            return okuma_tabani(s.metin or "", self.en_az_s, self.karakter_ms)
        if s.zincir or nxt_hazir:
            return max(self.en_az_s, OKUMA_EN_AZ_S)
        return self.en_az_s

    def bitis(self, cur: SiraSatiri, nxt: SiraSatiri | None) -> float | None:
        """Gösterilen satırın bitiş anı (None: kaynak hâlâ ekranda ve sıradaki yok, belirsiz)."""
        nxt_hazir = nxt is not None and nxt.hazir is not None
        taban = self.taban(cur, nxt)
        g = cur.goster if cur.goster is not None else 0.0
        if cur.git is None:
            if nxt_hazir:   # savunma: kaynak gitmeden sıradaki hazırsa (olmamalı) en az taban kadar kalır
                return max(g + taban, nxt.hazir)  # type: ignore[union-attr]
            return None
        dogal = max(cur.git + max(0.0, g - cur.gel), g + taban)
        if nxt_hazir:
            return max(g + taban, min(dogal, nxt.hazir))  # type: ignore[union-attr]
        if nxt is not None and cur.git_tur == "yeni":
            return dogal + self.yeni_bekle_s   # yenisi gelince yukarıdaki kuralla hemen değişir
        return dogal

    def adim(self, simdi: float) -> list[tuple[str, SiraSatiri]]:
        """Vakti gelen kararları uygular. Dönen eylemler sırayla: ("goster", s) yeni satır (öncekinin yerine
        geçer, ayrıca silme yok), ("devam", s) gösterilenin çevirisi yerinde güncellendi, ("sil", s) kaldır."""
        out: list[tuple[str, SiraSatiri]] = []
        self.satirlar = [s for s in self.satirlar if not s.hata or s is self.gosterilen]
        for _ in range(len(self.satirlar) + 2):
            cur, nxt = self.gosterilen, self._sonraki()
            if cur is not None and cur.guncel:
                cur.guncel = False
                out.append(("devam", cur))
            if cur is None:
                if nxt is not None and nxt.hazir is not None and nxt.hazir <= simdi + ESIK:
                    self._goster(nxt, simdi, zincir=False)
                    out.append(("goster", nxt))
                    continue
                break
            b = self.bitis(cur, nxt)
            if b is None or simdi < b - ESIK:
                break
            self.satirlar.remove(cur)
            self.gosterilen = None
            if nxt is not None and nxt.hazir is not None and nxt.hazir <= simdi + ESIK:
                self._goster(nxt, simdi, zincir=True)
                out.append(("goster", nxt))
            else:
                out.append(("sil", cur))
        return out

    def _goster(self, s: SiraSatiri, simdi: float, zincir: bool) -> None:
        s.goster, s.zincir = simdi, zincir
        self.gosterilen = s

    def sonraki_an(self) -> float | None:
        """Bir sonraki kararın anı (uyandırma zamanlayıcısı için)."""
        cur, nxt = self.gosterilen, self._sonraki()
        if cur is None:
            return nxt.hazir if nxt is not None and nxt.hazir is not None else None
        return self.bitis(cur, nxt)
