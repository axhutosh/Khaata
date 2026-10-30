# Khaata branding

A jade rounded square with a rounded "K": white stem and upper arm, mint lower arm
(money in, money out). Generated from one geometry by `frontend/scripts/make_brand.py`;
edit the numbers there and re-run to change every size at once:

    backend/.venv/Scripts/python frontend/scripts/make_brand.py

| File | Use |
| --- | --- |
| `google-console-logo-120.png` | **Google OAuth consent screen → Branding → App logo** (120×120 PNG, as Google asks) |
| `khaata-logo.svg` | The mark, any size |
| `khaata-logo-512.png` | The mark on white, 512×512 (app stores, social, docs) |
| `khaata-logo-1024-transparent.png` | The mark on transparent, 1024×1024 |
| `khaata-logo-mono.svg` | One-colour mark without the tile (print, watermarks) |
| `khaata-wordmark.svg` / `khaata-wordmark-on-dark.svg` | Mark + "Khaata" for light / dark backgrounds |
| `preview.png` | Every size side by side, for checking legibility |

Colours: jade `#0E7C66`, mint `#8FE3C8`, white `#FFFFFF`, ink `#16181D`.
The app's favicon and icons (`frontend/public/`) come from the same script.
