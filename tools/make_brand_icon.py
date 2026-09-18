"""Render the integration's brand icon.

Since Home Assistant 2026.3 a custom integration carries its own brand
images in a ``brand/`` folder next to its manifest; older versions ignore
the folder and show the generic icon. Writes ``icon.png`` (256 x 256) and
``icon@2x.png`` (512 x 512), drawn at 8x and downscaled so the edges stay
smooth.

    python tools/make_brand_icon.py [output_dir]
"""

from __future__ import annotations

from pathlib import Path
import sys

from PIL import Image, ImageDraw

SCALE = 8
SIZE = 512 * SCALE

GREEN_TOP = (76, 175, 80)
GREEN_BOTTOM = (27, 94, 32)
WHITE = (255, 255, 255, 255)
BOLT = (255, 214, 0, 255)


def u(value: float) -> int:
    """Design units (0..512) to pixels."""
    return round(value * SCALE)


def vertical_gradient(top: tuple, bottom: tuple) -> Image.Image:
    gradient = Image.new("RGBA", (1, SIZE))
    for y in range(SIZE):
        t = y / (SIZE - 1)
        gradient.putpixel(
            (0, y),
            tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,),
        )
    return gradient.resize((SIZE, SIZE))


def build() -> Image.Image:
    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

    # Badge: a rounded square filling the canvas, so it sits flush wherever
    # Home Assistant boxes it.
    badge = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(badge).rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=u(96), fill=255)
    icon.paste(vertical_gradient(GREEN_TOP, GREEN_BOTTOM), (0, 0), badge)

    draw = ImageDraw.Draw(icon)

    # A horizontal battery: shell, terminal and three cells, the last one
    # holding a bolt. Reads as "UPS" at every size down to 24 px.
    shell = (u(72), u(176), u(408), u(336))
    draw.rounded_rectangle(shell, radius=u(28), outline=WHITE, width=u(18))
    draw.rounded_rectangle((u(408), u(224), u(444), u(288)), radius=u(10), fill=WHITE)

    cells = [(u(108), u(212), u(186), u(300)), (u(202), u(212), u(280), u(300))]
    for cell in cells:
        draw.rounded_rectangle(cell, radius=u(10), fill=WHITE)

    bolt = [
        (334, 196),
        (296, 262),
        (326, 262),
        (306, 318),
        (356, 244),
        (326, 244),
    ]
    draw.polygon([(u(x), u(y)) for x, y in bolt], fill=BOLT)

    return icon


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "custom_components/suptronics_ups_x120x/brand")
    out.mkdir(parents=True, exist_ok=True)
    icon = build()
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        icon.resize((size, size), Image.LANCZOS).save(out / name, "PNG", optimize=True)
        print("wrote", out / name)


if __name__ == "__main__":
    main()
