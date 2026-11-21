# AltYazıKöprüsü (SubtitleBridge) — game translator with real-time subtitle translation

[![License: AGPL-3.0](https://img.shields.io/github/license/YPUF-04/gametranslate?color=blue)](../LICENSE)
[![Latest release](https://img.shields.io/github/v/release/YPUF-04/gametranslate?display_name=tag)](https://github.com/YPUF-04/gametranslate/releases/latest)
[![Stars](https://img.shields.io/github/stars/YPUF-04/gametranslate?style=flat)](https://github.com/YPUF-04/gametranslate/stargazers)

**Free, open-source game translator: it reads the foreign text on your game screen with OCR (subtitles, menus, quest lists), translates it in real time – mainly into Turkish, other languages are selectable – and shows it on your LG webOS TV over the game. Built for PS5 Remote Play, the Xbox app, capture cards/OBS and PC games. A Turkish-patch alternative for games that never got a patch.**

*Türkçe: [Ana README](../README.md).*

[![Download: Windows installer](https://img.shields.io/badge/Download-Windows%20installer-2EC4B6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/YPUF-04/gametranslate/releases/latest)

## Why AltYazıKöprüsü?

- **One-click install:** download the Windows installer and double-click it; no administrator rights needed.
- **One-click updates:** when a new version is out, update from inside the program with a single button.
- **One-click LG TV install:** the program installs the TV app onto your TV by itself; no extra tools needed.
- **Live translation:** subtitles, menus and quest text; a per-game memory keeps names and repeated lines consistent.
- **Free and private:** no tracking, no ads, no servers. The local engine works fully offline.
- **On top of the game:** the LG webOS TV app draws the text over your game (TV browser and OBS are fallbacks).

> **Honest status note:** the project is under development. It has not yet been tried on real devices (TV, PS5, Xbox); the table below lists the test status of every flow. The Windows installer, one-click update and one-click LG TV install have not been tried on a real PC/TV yet either.

## What does it translate?

- **Subtitles** (in-game dialogue)
- **Menus** and settings screens
- **All on-screen text** (quest lists, info boxes, signs); optionally with a short explanation for quests
- **Game audio** (experimental, off by default): turns speech into text and translates it

## Get started in 3 minutes (Windows)

1. [**Download the latest release**](https://github.com/YPUF-04/gametranslate/releases/latest): take the `AltYaziKoprusu-Windows-Kur.exe` file. Updates inside the app download only the changed parts.
2. Double-click it and press **Next**. (Turkish or English wizard; no administrator rights needed.)
3. If a blue warning appears: the program is unsigned, so Windows says **"Windows protected your PC"** (SmartScreen). This is normal. Press **More info**, then **Run anyway**.
4. On the last page leave **Start the program now** ticked and press **Finish**.
5. The control panel opens in your browser. Follow the 4 steps: pick your game, pick a translation engine, connect your TV, test.
6. Press the big **Start** button in the panel.

If you prefer no installer, use `AltYaziKoprusu-Tasinabilir-….zip` from the same page (extract it, double-click `AltYaziKoprusu.exe`). You can verify your download against `SHA256SUMS.txt`.

**Installing on an LG TV:** open the Developer Mode app on the TV, type the TV's IP address and the code shown on screen (Passphrase) into the **"Install on the TV in one click"** card in the panel, press **Install**. Details: [LG TV setup](kurulum/lg-webos.md) (guides are in Turkish for now).

**Updates:** when a new version is out, a "A new version is ready" bar with an **Update** button appears at the top of the panel. The program asks GitHub at most once a day whether a new version exists (nothing about you is sent); you can turn this off in Advanced settings.

More: [Windows setup](kurulum/windows.md) · [LG TV setup](kurulum/lg-webos.md) · [TV browser / OBS](kurulum/tv-tarayici.md)

### Run from source (advanced)

Python 3.11 or newer is required.

```bash
pip install -e ".[ocr-windows,tv]"
python -m kopru
```

## Supported devices

| Device / flow | Status | Notes |
|---|---|---|
| LG webOS TV (over the game) | testing | [Setup](kurulum/lg-webos.md) |
| Browser / OBS overlay | awaiting tests | [Setup](kurulum/tv-tarayici.md) |
| PS5 (PS Remote Play) | awaiting tests | [Setup](kurulum/ps5-remote-play.md) |
| Xbox (Xbox app) | awaiting tests | [Setup](kurulum/xbox.md) |
| Capture card / OBS | awaiting tests | [Setup](kurulum/yakalama-karti.md) |
| PC games | awaiting tests | [Windows](kurulum/windows.md) |
| Samsung (Tizen) TV | coming soon | [Note](kurulum/samsung.md) |
| Android TV | coming soon | [Note](kurulum/android-tv.md) |
| macOS | later (beta) | [Note](kurulum/mac.md) |

## Translation engines

| Engine | In short | Key needed | Guide |
|---|---|---|---|
| Gemini | Has a free tier (limits may change) | Yes | [Guide](anahtarlar/gemini.md) |
| DeepSeek | Very cheap | Yes | [Guide](anahtarlar/deepseek.md) |
| Claude | Most natural translation, paid. Subscription login is not available, an API key is required | Yes | [Guide](anahtarlar/claude.md) |
| Local | Offline, free, somewhat weaker | No | — |
| DeepL | Optional | Yes | [Guide](anahtarlar/deepl.md) |

Prices may change; check each provider's own site.

## Privacy in short

No tracking, no statistics. Your API keys live only in your computer's encrypted vault. Text goes only to the translation engine you chose; the "Local" engine is fully offline. The microphone is never opened and no audio is recorded. The update check asks GitHub's public releases page at most once a day, sends no identifier and can be switched off. The TV install code and key stay in memory only. Full text (Turkish): [GIZLILIK.md](../GIZLILIK.md)

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md). Roadmap: [YOL-HARITASI.md](YOL-HARITASI.md). Found a bug? Use the "Hata bildirimi" (bug report) issue form; writing in English is fine.

## License and thanks

AltYazıKöprüsü is distributed under **AGPL-3.0-only** ([LICENSE](../LICENSE)). Thanks to the projects that inspired us: **GameTranslator** (Sefflex) and **CouchSubs** (Sinan Yorulmaz). Details in [NOTICE](../NOTICE); libraries used are in [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md).
