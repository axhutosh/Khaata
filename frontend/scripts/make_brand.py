"""Generate Khaata's logo, favicon and app icons from one geometry.

    backend/.venv/Scripts/python frontend/scripts/make_brand.py

Writes the web assets to frontend/public/ and upload-ready files to branding/
(e.g. branding/google-console-logo-120.png for the Google OAuth consent screen).
The mark: a jade rounded square with a rounded "K" — white stem and upper arm, a
mint lower arm (money in, money out). Edit the numbers below, re-run, done.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend" / "public"
BRAND = ROOT / "branding"

JADE = "#0E7C66"
WHITE = "#FFFFFF"
MINT = "#8FE3C8"
INK = "#16181D"

# geometry on a 512 x 512 canvas
SIZE = 512
RADIUS = 116                     # corner radius of the tile
STROKE = 66                      # width of every K stroke (round caps)
STEM = ((178, 132), (178, 380))
UPPER = ((206, 270), (346, 132))
LOWER = ((240, 236), (352, 380))


def svg(tile=True) -> str:
    def line(p, color):
        (x1, y1), (x2, y2) = p
        return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
                f'stroke-width="{STROKE}" stroke-linecap="round"/>')
    bg = f'<rect width="{SIZE}" height="{SIZE}" rx="{RADIUS}" fill="{JADE}"/>' if tile else ""
    lower = MINT if tile else JADE
    upper = WHITE if tile else INK
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" role="img" aria-label="Khaata">'
            f'<title>Khaata</title>{bg}{line(LOWER, lower)}{line(STEM, upper)}{line(UPPER, upper)}</svg>\n')


def wordmark_svg(dark_text=True) -> str:
    """Mark + 'Khaata' set in Space Grotesk (falls back to system sans)."""
    text = INK if dark_text else "#F7F6F2"
    mark = svg().replace('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="Khaata">', "") \
                .replace("<title>Khaata</title>", "").replace("</svg>\n", "")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1700 512" role="img" aria-label="Khaata">'
            f'<title>Khaata</title><g>{mark}</g>'
            f'<text x="600" y="352" font-family="Space Grotesk, Inter, Segoe UI, Arial, sans-serif" font-weight="600" '
            f'font-size="300" letter-spacing="-6" fill="{text}">Khaata</text></svg>\n')


def render(px: int, tile=True) -> Image.Image:
    """Draw the mark at 4x and downsample, for clean anti-aliased edges at any size."""
    ss = 4
    s = px * ss / SIZE
    img = Image.new("RGBA", (px * ss, px * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if tile:
        d.rounded_rectangle((0, 0, px * ss - 1, px * ss - 1), radius=RADIUS * s, fill=JADE)
    w = STROKE * s
    for seg, color in ((LOWER, MINT if tile else JADE), (STEM, WHITE if tile else INK), (UPPER, WHITE if tile else INK)):
        (x1, y1), (x2, y2) = [(x * s, y * s) for x, y in seg]
        d.line((x1, y1, x2, y2), fill=color, width=round(w))
        for cx, cy in ((x1, y1), (x2, y2)):  # round caps
            d.ellipse((cx - w / 2, cy - w / 2, cx + w / 2, cy + w / 2), fill=color)
    return img.resize((px, px), Image.LANCZOS)


def on_white(img: Image.Image, pad: float = 0.0) -> Image.Image:
    """Flatten onto white (Google's logo upload wants a plain square image)."""
    size = img.size[0]
    canvas = Image.new("RGB", (size, size), "#FFFFFF")
    inner = img if not pad else img.resize((round(size * (1 - 2 * pad)),) * 2, Image.LANCZOS)
    off = (size - inner.size[0]) // 2
    canvas.paste(inner, (off, off), inner)
    return canvas


def main():
    PUBLIC.mkdir(parents=True, exist_ok=True)
    BRAND.mkdir(parents=True, exist_ok=True)

    (PUBLIC / "favicon.svg").write_text(svg(), encoding="utf-8")
    (BRAND / "khaata-logo.svg").write_text(svg(), encoding="utf-8")
    (BRAND / "khaata-logo-mono.svg").write_text(svg(tile=False), encoding="utf-8")
    (BRAND / "khaata-wordmark.svg").write_text(wordmark_svg(), encoding="utf-8")
    (BRAND / "khaata-wordmark-on-dark.svg").write_text(wordmark_svg(dark_text=False), encoding="utf-8")

    render(48).save(PUBLIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    for px in (32, 180, 192, 512):
        name = {180: "apple-touch-icon.png"}.get(px, f"icon-{px}.png")
        render(px).save(PUBLIC / name)
    # maskable icon: Android crops to a circle, so keep the K inside the middle 80%
    maskable = Image.new("RGBA", (512, 512), JADE)
    maskable.alpha_composite(render(410), (51, 51))
    maskable.save(PUBLIC / "icon-maskable-512.png")

    # Google OAuth consent screen: square, 120x120, PNG/JPG, under 1 MB
    on_white(render(120)).save(BRAND / "google-console-logo-120.png")
    on_white(render(512)).save(BRAND / "khaata-logo-512.png")
    render(1024).save(BRAND / "khaata-logo-1024-transparent.png")

    # a preview sheet to eyeball every size at once
    sheet = Image.new("RGB", (1000, 300), "#F7F6F2")
    x = 30
    for px in (16, 32, 48, 64, 120, 180):
        sheet.paste(render(px), (x, 150 - px // 2), render(px))
        x += px + 40
    try:
        font = ImageFont.truetype("segoeuib.ttf", 64)
    except OSError:
        font = ImageFont.load_default()
    ImageDraw.Draw(sheet).text((x + 10, 112), "Khaata", fill=INK, font=font)
    sheet.save(BRAND / "preview.png")

    for p in sorted(list(PUBLIC.iterdir()) + list(BRAND.iterdir())):
        print(f"{p.relative_to(ROOT)}  {p.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
