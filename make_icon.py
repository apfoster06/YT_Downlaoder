#!/usr/bin/env python3
"""
make_icon.py — generate the app icon (assets/icon.ico + assets/icon.png).

Drawn in code with Pillow so the icon can be re-tuned by editing the palette or
proportions below, rather than by hunting for a source file. The design follows
the same neo-brutalist language as templates/index.html: flat colour, a heavy
black keyline and a hard offset plate.

Mark: a download arrow whose head is a play triangle — "video" + "save it".

The offset plate is mustard rather than black on purpose. A black drop shadow
disappears against a dark taskbar, which leaves the tile looking misaligned;
mustard reads on any background and doubles as a risograph misregistration.

Each ICO frame is drawn at 8x and downsampled, so small sizes stay crisp
instead of being one big render squashed down. The plate is dropped below 32px,
where it would only turn to mush.

Usage:   python make_icon.py
Output:  assets/icon.ico (16-256px frames), assets/icon.png (512px)
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent.resolve()
OUT_DIR = HERE / "assets"

# Palette lifted from templates/index.html.
INK = (17, 17, 17, 255)  # --ink
TOMATO = (229, 72, 47, 255)  # --tomato
MUSTARD = (242, 193, 78, 255)  # --mustard
CREAM = (245, 240, 230, 255)  # --bg

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
SS = 8  # supersampling factor


def _draw(size: int) -> Image.Image:
    """Render one icon frame at the given pixel size."""
    plate = size >= 32  # too muddy to be worth it below this
    s = size * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def px(v: float) -> float:
        return v * s

    if plate:
        tile = (px(0.045), px(0.045), px(0.845), px(0.845))
        offset = px(0.085)
        border = max(2, int(px(0.052)))
        radius = px(0.155)
        d.rounded_rectangle(
            (tile[0] + offset, tile[1] + offset, tile[2] + offset, tile[3] + offset),
            radius=radius,
            fill=MUSTARD,
            outline=INK,
            width=border,
        )
    else:
        tile = (px(0.035), px(0.035), px(0.965), px(0.965))
        border = max(2, int(px(0.075)))
        radius = px(0.175)

    d.rounded_rectangle(tile, radius=radius, fill=TOMATO, outline=INK, width=border)

    # Arrow, positioned inside the keyline.
    ix0, iy0 = tile[0] + border, tile[1] + border
    ix1, iy1 = tile[2] - border, tile[3] - border
    w, h = ix1 - ix0, iy1 - iy0
    cx = (ix0 + ix1) / 2

    def x(f: float) -> float:
        return cx + f * w

    def y(f: float) -> float:
        return iy0 + f * h

    # Shaft.
    d.rectangle((x(-0.105), y(0.155), x(0.105), y(0.565)), fill=CREAM)
    # Head — a play triangle turned to point down.
    d.polygon([(x(-0.295), y(0.495)), (x(0.295), y(0.495)), (x(0.0), y(0.855))], fill=CREAM)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    frames = [_draw(n) for n in ICO_SIZES]

    ico = OUT_DIR / "icon.ico"
    frames[-1].save(ico, format="ICO", sizes=[(n, n) for n in ICO_SIZES])

    png = OUT_DIR / "icon.png"
    _draw(512).save(png, format="PNG")

    print(f"wrote {ico}  ({', '.join(f'{n}px' for n in ICO_SIZES)})")
    print(f"wrote {png}  (512px)")


if __name__ == "__main__":
    main()
