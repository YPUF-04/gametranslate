#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# LG webOS paketleri (.ipk) - LG'nin RESMİ aracı @webos-tools/cli (ares-package) ile üretir.
# Eski elle yapılmış ipk'larda usr/palm/packages/<id>/packageinfo.json yoktu ("-5: ipk verified failed" şüphelisi);
# ares-package bu dosyayı her zaman oluşturur.
# Çıktı: dist/tv/*.ipk  ve kopya: tv/paketler/
set -euo pipefail
KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KOK"
ARAC="$KOK/.araclar"
ARES="$ARAC/node_modules/.bin/ares-package"
if [ ! -x "$ARES" ]; then
  echo ">> @webos-tools/cli kuruluyor ($ARAC) ..."
  mkdir -p "$ARAC"
  npm install --prefix "$ARAC" @webos-tools/cli
fi

CIKTI="$KOK/dist/tv"
ARA="$KOK/dist/ara"
rm -rf "$CIKTI" "$ARA"; mkdir -p "$CIKTI" "$ARA" "$KOK/tv/paketler"

# 1) Ana uygulama = BAŞLATICI (PROTOKOL 18): tv/webos/ (index.html + yukleyici.js + simgeler) ve yazı tipleri.
#    Uygulamanın kendisi (kopru/web/tv/webos/*, ortak.js, ...) TV'ye bilgisayardan gelir; pakete yalnız yedek olarak
#    gömülür (gomulu.js, sunucunun sunduğu paketle aynı üreticiden: python -m kopru.tv_kurulum.uygulama).
PY="${PYTHON:-python3}"
ORTAK="yazi-latin.woff2 yazi-latin-ext.woff2 yazi-LISANS-OFL.txt"
hazirla_tv() { # $1=hedef klasör
  mkdir -p "$1"
  cp -L "$KOK"/tv/webos/* "$1"/
  for f in $ORTAK; do cp -L "$KOK/kopru/web/tv/$f" "$1"/; done
  ( cd "$KOK" && "$PY" -m kopru.tv_kurulum.uygulama --gomulu "$1/gomulu.js" )
}
hazirla_tv "$ARA/tv"
mkdir -p "$ARA/deneme"; cp -L "$KOK"/tv/lg-test/* "$ARA/deneme"/; cp -L "$KOK/kopru/web/tv/marka.js" "$ARA/deneme"/

# 2) requiredACG'siz varyant: sürüm 0.2.1 (ares-package dosya adını sürümden verir)
hazirla_tv "$ARA/tv-acgsiz"
node -e '
  var f=process.argv[1], fs=require("fs"), a=JSON.parse(fs.readFileSync(f,"utf8"));
  delete a.requiredACG; a.version="0.2.1"; fs.writeFileSync(f, JSON.stringify(a,null,2)+"\n");' "$ARA/tv-acgsiz/appinfo.json"

echo ">> Uygulama denetimi (ares-package --check)"
for k in tv deneme tv-acgsiz; do
  "$ARES" --check "$ARA/$k" || echo "!! $k denetimde uyarı verdi"
done

echo ">> Paketleniyor"
for k in tv deneme tv-acgsiz; do "$ARES" --outdir "$CIKTI" "$ARA/$k"; done

echo ">> Doğrulama"
HATA=0
for ipk in "$CIKTI"/*.ipk; do
  ad="$(basename "$ipk")"; id="${ad%%_*}"
  T="$(mktemp -d)"; ( cd "$T" && ar x "$ipk" )
  echo "--- $ad ($(stat -c %s "$ipk") bayt)"; ar t "$ipk" | sed 's/^/    ar: /'
  if tar tzf "$T/data.tar.gz" | grep -q "usr/palm/packages/$id/packageinfo.json"; then
    echo "    packageinfo.json: VAR"
  else
    echo "    packageinfo.json: YOK  <-- sorun"; HATA=1
  fi
  tar tzf "$T/data.tar.gz" | sed 's/^/    data: /'
  rm -rf "$T"
done
[ "$HATA" = 0 ] || { echo "Doğrulama başarısız"; exit 1; }

rm -f "$KOK"/tv/paketler/com.altyazikoprusu.tv_*.ipk
cp "$CIKTI"/*.ipk "$KOK/tv/paketler/"
echo
echo "Hazır: $CIKTI  (kopyası: tv/paketler/)"
echo "NOT: *_0.2.1_all.ipk = requiredACG'SİZ varyant (ana paket kurulmazsa bunu deneyin)."
