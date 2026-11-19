#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Sürükle-bırak .dmg üretir (UDZO). Kullanım: dmg_yap.sh <.app yolu> <çıktı.dmg>
set -euo pipefail
APP="$1"; CIKTI="$2"
HAZIR="$(mktemp -d)"
cp -R "$APP" "$HAZIR/"
ln -s /Applications "$HAZIR/Applications"
for d in LICENSE NOTICE README.md GIZLILIK.md; do [ -f "$d" ] && cp "$d" "$HAZIR/" || true; done
mkdir -p "$(dirname "$CIKTI")"
rm -f "$CIKTI"
# GitHub'ın Mac makinelerinde hdiutil ara sıra "Resource busy" der; birkaç kez dene.
for deneme in 1 2 3 4 5; do
  if hdiutil create -volname "AltYazıKöprüsü" -srcfolder "$HAZIR" -ov -format UDZO "$CIKTI"; then
    break
  fi
  if [ "$deneme" = 5 ]; then echo "hdiutil 5 denemede de başarısız" >&2; exit 1; fi
  echo "hdiutil meşgul, $((deneme * 5)) sn sonra yeniden deneniyor..." >&2
  sleep $((deneme * 5))
done
rm -rf "$HAZIR"
echo "Üretildi: $CIKTI"
