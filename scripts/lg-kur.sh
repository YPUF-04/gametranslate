#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# LG TV'ye kurulum rehberi (KENDİ bilgisayarınızda çalıştırın). Betik olarak da çalışır: ./lg-kur.sh <TV_IP> <paket.ipk>
# Önce: TV'de "LG Content Store" > "Developer Mode" uygulamasını kurun, LG hesabıyla girin, "Dev Mode Status" AÇIK olsun,
#       "Key Server" AÇIK olsun. Bilgisayar ve TV aynı ağda olmalı. Node.js gerekir.
#       LG aracı:  npm install -g @webos-tools/cli
set -euo pipefail
TV_IP="${1:?kullanım: $0 <TV_IP> <paket.ipk>}"
IPK="${2:?kullanım: $0 <TV_IP> <paket.ipk>}"

# 1) Cihazı tanıt (ad: tv). Parola boş bırakılır; anahtarı sonra alırız.
ares-setup-device --add tv --info "{'host':'$TV_IP','port':'9922','username':'prisoner'}" 2>/dev/null \
  || ares-setup-device --modify tv --info "{'host':'$TV_IP','port':'9922','username':'prisoner'}"

# 2) Anahtarı al: TV'deki Developer Mode uygulamasında yazan "Passphrase" (6 karakter) sorulur.
ares-novacom --device tv --getkey

# 3) Bağlantıyı dene
ares-device-info --device tv

# 4) Kur ("-5: ipk verified failed" gibi bir hata alırsanız hatayı bize bildirin; önce lg-test paketini deneyin)
ares-install --device tv "$IPK"

# 5) Başlat ve (isteğe bağlı) hata ayıkla
ares-launch --device tv com.altyazikoprusu.tv
# ares-inspect --device tv --app com.altyazikoprusu.tv --open   # tarayıcıda geliştirici konsolu açar
# ares-install --device tv --list                              # kurulu uygulamaları listeler
# ares-install --device tv --remove com.altyazikoprusu.tv      # kaldırır
