# SPDX-License-Identifier: AGPL-3.0-only
"""Çevrilmeden geri gelen satırları yakalamak için küçük İngilizce sözcük listesi.

Kullanıcı hatası (0.1.5): "Hang up" gibi kısa arayüz yazıları çevrilmeden aynen geri geliyordu.
Motor bir satırı aynen döndürdüğünde, içinde sıradan İngilizce sözcük varsa bu bir isim değildir:
yönetici satırı "mutlaka çevir" uyarısıyla bir kez daha sorar. Liste bilerek küçük ve yaygındır;
özel isimler (Vice City, Lucia) burada geçmez.
"""
from __future__ import annotations

import re

_SOZCUKLER = """
a about above accept across act add after again against ahead aim all alone along already also always am an and
another answer any anyone anything are area around arrest as ask at attack available away back bad bag bank be
because bed been before begin behind being best better between big bike bitch black block blue boat body boss both
box break bring brother buy by call calm came can cancel car careful carry cash catch change check chief choose city
clear climb close come confirm continue control cop could cover crew cut damn dark day dead deal death deliver did
die do does dog done door down drive drop dude during each easy eat end enemy enter escape even ever every exit
eye face fail fall family far fast father fight find fine finish fire first fix follow food for forget friend from
front fuck full game gang garage gas get girl give go god gone good got grab great green ground gun guy hand hang
happen hard has have he head hear heart hell help her here hey hide high him his hit hold home hope horse hospital
hot house how hurry i if in inside into is it its job jump just keep key kill kind know last later leave left let
level life light like listen little live load lock long look lose lost love make man many map me mean meet menu
mission money more morning most mother move much must my name near need never new next nice night no none not
nothing now of off ok okay old on once one only open or order other our out over own park pay people phone pick
place plan play please police press pull push put quick quit raid ready real red remember rent rest restart
resume return ride right road run safe save say score see sell send set settings shit shoot shop should show shut
side sign sit skip sleep slow so some someone something sorry speak stand start stay steal step still stop store
street such sure take talk target team tell than thank thanks that the their them then there these they thing
think this those through time to today together tonight too track truck try turn under unlock until up us use
wait walk want wanted warning was watch water way we weapon well went were what when where which while white who
why will win with without woman work world would wrong yeah yes yet you your
""".split()
SIK = frozenset(_SOZCUKLER)
_KELIME = re.compile(r"[A-Za-z']+")


def siradan_ingilizce_mi(metin: str) -> bool:
    """Satırda en az bir sıradan İngilizce sözcük var mı (isim/kod değil, çevrilmesi gereken yazı)?"""
    kelimeler = [k.lower().strip("'") for k in _KELIME.findall(metin or "")]
    kelimeler = [k for k in kelimeler if len(k) >= 2]
    if not kelimeler:
        return False
    sik = sum(1 for k in kelimeler if k in SIK)
    ham = [k for k in _KELIME.findall(metin) if len(k.strip("'")) >= 2]
    # Her sözcüğü büyük harfle başlayan (ama TAMAMI BÜYÜK olmayan) çok sözcüklü yazı çoğu zaman bir isimdir
    # ("Vice City", "Grove Street"): ancak sözcüklerin hepsi yaygınsa çevrilecek yazı sayılır ("Hang Up").
    baslik = len(ham) > 1 and all(k[0].isupper() for k in ham) and not all(k.isupper() for k in ham)
    if baslik:
        return sik == len(kelimeler)
    # tek sözcük: o sözcük yaygın olmalı; çok sözcük: en az yarısı yaygın olmalı
    return sik >= 1 and sik * 2 >= len(kelimeler)


ZORUNLU_CEVIR_IPUCU = (
    "IMPORTANT: the following lines are ordinary English game text (UI labels, prompts, actions or dialogue), "
    "NOT names. You MUST translate every one of them into natural Turkish. Never return them unchanged. "
    "Examples: \"Hang up\" => \"Telefonu kapat\", \"Call back\" => \"Geri ara\", \"Skip\" => \"Geç\", "
    "\"Hold to sprint\" => \"Koşmak için basılı tut\".")
