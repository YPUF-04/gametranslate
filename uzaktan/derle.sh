#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# ayk-uzaktan'ı derler (PROTOKOL §15.1). Windows'ta MSYS2 MINGW64 kabuğunda (statik, tek .exe),
# Linux'ta geliştirme/sınama için (sistem kütüphaneleriyle).
#
#   bash uzaktan/derle.sh [çıktı_klasörü]       (varsayılan: build/uzaktan-cikti)
#
# Kaynaklar sabitlenmiştir ve commit özetiyle doğrulanır:
#   chiaki-ng v1.10.1   (AGPL-3.0)  https://github.com/streetpea/chiaki-ng
#   FFmpeg    n7.1.1    (LGPL-2.1+, yalnız H.264/HEVC çözücü + swscale; --enable-gpl YOK)
set -euo pipefail

KOK="$(cd "$(dirname "$0")/.." && pwd)"
IS="${KOK}/build/uzaktan-is"
CIKTI="${1:-${KOK}/build/uzaktan-cikti}"
CHIAKI_ETIKET="v1.10.1"
CHIAKI_COMMIT="f30da0aaeb96fc0026cc03683153f682352e7d7c"
FFMPEG_ETIKET="n7.1.1"
FFMPEG_COMMIT="db69d06eeeab4f46da15030a80d539efb4503ca8"
mkdir -p "$IS" "$CIKTI"

windows=0
case "$(uname -s)" in MINGW*|MSYS*) windows=1 ;; esac

kaynak_al() {   # <adres> <etiket> <commit> <klasör>
	if [ ! -d "$4/.git" ]; then
		git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$2" "$1" "$4"
	fi
	local var
	var="$(git -C "$4" rev-parse HEAD)"
	if [ "$var" != "$3" ]; then
		echo "HATA: $4 beklenen commit değil ($var != $3)" >&2
		exit 1
	fi
}

kaynak_al https://github.com/streetpea/chiaki-ng.git "$CHIAKI_ETIKET" "$CHIAKI_COMMIT" "$IS/chiaki-ng"
git -C "$IS/chiaki-ng" submodule update --init --depth 1 \
	third-party/nanopb third-party/jerasure third-party/gf-complete third-party/curl

# --- FFmpeg: yalnız gereken çözücüler, statik ---
FF_KUR="$IS/ffmpeg-kur"
if [ ! -f "$FF_KUR/lib/pkgconfig/libavcodec.pc" ]; then
	kaynak_al https://github.com/FFmpeg/FFmpeg.git "$FFMPEG_ETIKET" "$FFMPEG_COMMIT" "$IS/ffmpeg"
	(
		cd "$IS/ffmpeg"
		ek=()
		if [ "$windows" = 1 ]; then ek+=(--target-os=mingw32 --arch=x86_64); fi
		./configure --prefix="$FF_KUR" --enable-static --disable-shared --disable-programs --disable-doc \
			--disable-everything --disable-autodetect --disable-network --disable-debug \
			--disable-avdevice --disable-avformat --disable-avfilter --disable-swresample \
			--enable-avcodec --enable-swscale --enable-decoder=h264,hevc --enable-parser=h264,hevc \
			--disable-iconv --disable-zlib --disable-bzlib --disable-lzma --pkg-config-flags=--static \
			"${ek[@]}"
		make -j"$(nproc 2>/dev/null || echo 4)"
		make install
	)
fi
export PKG_CONFIG_PATH="$FF_KUR/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"

statik=OFF
if [ "$windows" = 1 ]; then statik=ON; fi
cmake -S "$KOK/uzaktan" -B "$IS/derleme" -G Ninja -DCMAKE_BUILD_TYPE=Release \
	-DCHIAKI_KAYNAK="$IS/chiaki-ng" -DAYK_STATIK="$statik"
cmake --build "$IS/derleme"

if [ "$windows" = 1 ]; then
	cp "$IS/derleme/ayk-uzaktan.exe" "$CIKTI/"
	echo "--- bağımlı DLL'ler (yalnız Windows sistem DLL'leri olmalı) ---"
	objdump -p "$CIKTI/ayk-uzaktan.exe" | grep "DLL Name" || true
else
	cp "$IS/derleme/ayk-uzaktan" "$CIKTI/"
fi
# Lisans dosyaları yardımcının yanına
cp "$IS/chiaki-ng/COPYING" "$CIKTI/LICENSE-chiaki-ng.txt"
cp "$IS/ffmpeg/COPYING.LGPLv2.1" "$CIKTI/LICENSE-FFmpeg-LGPL.txt" 2>/dev/null || true
ls -la "$CIKTI"
