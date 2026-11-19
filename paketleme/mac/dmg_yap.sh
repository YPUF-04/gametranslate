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
hdiutil create -volname "AltYazıKöprüsü" -srcfolder "$HAZIR" -ov -format UDZO "$CIKTI"
rm -rf "$HAZIR"
echo "Üretildi: $CIKTI"
