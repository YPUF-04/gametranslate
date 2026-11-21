# SPDX-License-Identifier: AGPL-3.0-only
# ayk-uzaktan: libchiaki (chiaki-ng v1.10.1) + FFmpeg (yalnız H.264/HEVC çözücü + swscale) — PROTOKOL §15.
#
#   cmake -S uzaktan -B build/uzaktan -G Ninja -DCHIAKI_KAYNAK=<chiaki-ng kaynağı> [-DAYK_STATIK=ON]
#   cmake --build build/uzaktan
#
# Windows'ta MSYS2 MINGW64 ile, statik olarak derlenir (uzaktan/derle.sh); tek .exe, ek DLL yok.
cmake_minimum_required(VERSION 3.20)
project(ayk_uzaktan C)

set(CHIAKI_KAYNAK "${CMAKE_CURRENT_SOURCE_DIR}/../build/chiaki-ng" CACHE PATH "chiaki-ng kaynak klasörü (v1.10.1)")
option(AYK_STATIK "Tüm kütüphaneleri statik bağla (Windows paketi için)" OFF)

if(AYK_STATIK)
	set(CMAKE_FIND_LIBRARY_SUFFIXES .a)
	set(OPENSSL_USE_STATIC_LIBS ON CACHE BOOL "" FORCE)
	add_compile_definitions(MINIUPNP_STATICLIB)
	set(PKG_CONFIG_ARGN --static)
endif()

# Yalnız çekirdek kütüphane: arayüz, komut satırı, testler, kol/dokunmatik destekleri, Steam vb. kapalı.
foreach(kapali CHIAKI_ENABLE_GUI CHIAKI_ENABLE_CLI CHIAKI_ENABLE_TESTS CHIAKI_ENABLE_FFMPEG_DECODER
		CHIAKI_ENABLE_PI_DECODER CHIAKI_ENABLE_SPEEX CHIAKI_ENABLE_SETSU CHIAKI_ENABLE_STEAMDECK_NATIVE
		CHIAKI_ENABLE_STEAM_SHORTCUT CHIAKI_ENABLE_BOREALIS CHIAKI_ENABLE_ANDROID
		BUILD_SHARED_LIBS USE_NGHTTP2 USE_LIBIDN2 CURL_ZSTD CURL_BROTLI CURL_USE_LIBPSL CURL_USE_LIBSSH2
		USE_LIBRTMP CURL_ZLIB)
	set(${kapali} OFF CACHE STRING "" FORCE)
endforeach()
set(CHIAKI_LIB_ENABLE_OPUS ON CACHE BOOL "" FORCE)   # PS5 sesi (dublaj için)
set(CURL_DISABLE_LDAP ON CACHE BOOL "" FORCE)
add_subdirectory("${CHIAKI_KAYNAK}" chiaki EXCLUDE_FROM_ALL)

find_package(PkgConfig REQUIRED)
pkg_check_modules(AYK_FFMPEG REQUIRED libavcodec libswscale libavutil)
pkg_check_modules(AYK_JSONC REQUIRED json-c)

add_executable(ayk-uzaktan ayk_uzaktan.c)
target_include_directories(ayk-uzaktan PRIVATE ${AYK_FFMPEG_INCLUDE_DIRS} ${AYK_JSONC_INCLUDE_DIRS})
if(AYK_STATIK)
	target_link_directories(ayk-uzaktan PRIVATE ${AYK_FFMPEG_STATIC_LIBRARY_DIRS} ${AYK_JSONC_STATIC_LIBRARY_DIRS})
	target_link_libraries(ayk-uzaktan PRIVATE chiaki-lib ${AYK_FFMPEG_STATIC_LIBRARIES} ${AYK_JSONC_STATIC_LIBRARIES})
else()
	target_link_directories(ayk-uzaktan PRIVATE ${AYK_FFMPEG_LIBRARY_DIRS} ${AYK_JSONC_LIBRARY_DIRS})
	target_link_libraries(ayk-uzaktan PRIVATE chiaki-lib ${AYK_FFMPEG_LIBRARIES} ${AYK_JSONC_LIBRARIES})
endif()
if(WIN32)
	target_link_libraries(ayk-uzaktan PRIVATE ws2_32 wsock32 iphlpapi bcrypt crypt32 secur32 advapi32 user32
		ole32 shell32 normaliz)
	# Konsol uygulamasıdır; program onu CREATE_NO_WINDOW ile, penceresiz ve borularla çalıştırır.
	if(AYK_STATIK)
		target_link_options(ayk-uzaktan PRIVATE -static -static-libgcc -s)
	endif()
endif()
