"""Draw the StreamStudio app icon (1024 px) and write AppIcon.icns + AppIcon.png.

A dark macOS-style rounded square; a studio "lens" ring in the brand gradient (cyan → violet),
and a red record dot at its centre. Run: python3 mac/make_icon.py"""

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

S = 1024
OUT = Path(__file__).parent / "StreamStudio.app" / "Contents" / "Resources"


def gradient(size, c1, c2, diagonal=True):
    g = Image.new("RGB", (size, size))
    px = g.load()
    for y in range(size):
        for x in range(size):
            t = ((x + y) / (2 * size)) if diagonal else y / size
            px[x, y] = tuple(int(a + (b - a) * t) for a, b in zip(c1, c2, strict=True))
    return g


def main() -> None:
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # macOS icon grid: 824 px rounded square centred on 1024, radius ~185
    m = 100
    card = gradient(S, (34, 28, 58), (10, 9, 18)).convert("RGBA")
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((m, m, S - m, S - m), radius=185, fill=255)
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((m, m + 14, S - m, S - m + 14), radius=185, fill=(0, 0, 0, 150))
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
    base.paste(card, (0, 0), mask)
    # subtle top sheen
    sheen = Image.new("L", (S, S), 0)
    ImageDraw.Draw(sheen).ellipse((m - 200, m - 520, S - m + 200, S // 2), fill=36)
    base.paste(Image.new("RGBA", (S, S), (255, 255, 255, 255)), (0, 0), ImageChops.multiply(sheen, mask))
    # gradient ring
    c, r, w = S // 2, 250, 64
    ring = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(ring)
    d.ellipse((c - r, c - r, c + r, c + r), fill=255)
    d.ellipse((c - r + w, c - r + w, c + r - w, c + r - w), fill=0)
    glow = ring.filter(ImageFilter.GaussianBlur(26))
    grad = gradient(S, (60, 225, 235), (150, 110, 255)).convert("RGBA")
    base.paste(grad, (0, 0), ImageChops.multiply(glow, Image.new("L", (S, S), 110)))
    base.paste(grad, (0, 0), ring)
    # record dot
    dot = Image.new("L", (S, S), 0)
    ImageDraw.Draw(dot).ellipse((c - 92, c - 92, c + 92, c + 92), fill=255)
    base.paste(Image.new("RGBA", (S, S), (255, 60, 70, 255)), (0, 0), dot.filter(ImageFilter.GaussianBlur(30)))
    base.paste(Image.new("RGBA", (S, S), (240, 40, 56, 255)), (0, 0), dot)
    hi = Image.new("L", (S, S), 0)
    ImageDraw.Draw(hi).ellipse((c - 52, c - 70, c + 8, c - 24), fill=90)
    base.paste(Image.new("RGBA", (S, S), (255, 255, 255, 255)), (0, 0), hi.filter(ImageFilter.GaussianBlur(10)))
    OUT.mkdir(parents=True, exist_ok=True)
    base.save(OUT / "AppIcon.png")
    base.save(OUT / "AppIcon.icns", sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)])
    print(OUT / "AppIcon.icns")


if __name__ == "__main__":
    main()
