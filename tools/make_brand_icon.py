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

from PIL import Image, ImageDraw, ImageFilter

SCALE = 8
SIZE = 512 * SCALE

# Diagonal green, light top-left to deep bottom-right.
GREEN_LIGHT = (86, 196, 96)
GREEN_DEEP = (20, 92, 40)
WHITE = (255, 255, 255, 255)
BOLT = (255, 205, 0, 255)


def u(value: float) -> int:
    """Design units (0..512) to pixels."""
    return round(value * SCALE)


def diagonal_gradient(a: tuple, b: tuple) -> Image.Image:
    """Colour a at the top-left corner, b at the bottom-right."""
    small = Image.new("RGBA", (64, 64))
    px = small.load()
    for y in range(64):
        for x in range(64):
            t = (x + y) / 126
            px[x, y] = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)
    return small.resize((SIZE, SIZE), Image.BICUBIC)


def build() -> Image.Image:
    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

    # --- badge ----------------------------------------------------------------
    badge = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(badge).rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=u(110), fill=255)
    icon.paste(diagonal_gradient(GREEN_LIGHT, GREEN_DEEP), (0, 0), badge)

    # A soft highlight in the upper left, like light on a glossy tile.
    glow = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(glow).ellipse((u(-140), u(-200), u(360), u(240)), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(u(60)))
    highlight = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    highlight.putalpha(Image.composite(glow, Image.new("L", (SIZE, SIZE), 0), badge))
    icon.alpha_composite(highlight)

    # --- battery ----------------------------------------------------------------
    body = (u(96), u(168), u(392), u(344))
    terminal = (u(392), u(220), u(430), u(292))

    # Shadow under the battery, so it lifts off the tile.
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        tuple(v + u(10) for v in body), radius=u(34), fill=(0, 40, 10, 110)
    )
    sd.rounded_rectangle(
        tuple(v + u(10) for v in terminal), radius=u(12), fill=(0, 40, 10, 110)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(u(14)))
    icon.alpha_composite(shadow)

    # White body and terminal; the bolt is cut out of the body so the green
    # shows through, which reads at every size.
    battery = Image.new("L", (SIZE, SIZE), 0)
    bd = ImageDraw.Draw(battery)
    bd.rounded_rectangle(body, radius=u(34), fill=255)
    bd.rounded_rectangle(terminal, radius=u(12), fill=255)
    # Bolt, centred in the body and large enough to survive 24 px.
    base = [(268, 196), (206, 270), (250, 270), (222, 318), (288, 238), (244, 238)]
    bx = sum(x for x, _ in base) / len(base)
    by = sum(y for _, y in base) / len(base)
    bolt = [(244 + (x - bx) * 1.4, 256 + (y - by) * 1.4) for x, y in base]
    bd.polygon([(u(x), u(y)) for x, y in bolt], fill=0)
    white = Image.new("RGBA", (SIZE, SIZE), WHITE)
    icon.paste(white, (0, 0), battery)

    # A yellow bolt just inside the cut-out, slightly smaller, for a lit look.
    inner = [(x, y) for x, y in bolt]
    cx = sum(x for x, _ in inner) / len(inner)
    cy = sum(y for _, y in inner) / len(inner)
    lit = [(cx + (x - cx) * 0.72, cy + (y - cy) * 0.72) for x, y in inner]
    ImageDraw.Draw(icon).polygon([(u(x), u(y)) for x, y in lit], fill=BOLT)

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
