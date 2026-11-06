#!/usr/bin/env python3
"""Generate all signage, poster and surface textures for the 7-Eleven scene.

Everything is drawn procedurally with Pillow; no external design assets are
required apart from the supplied 7-Eleven logo mark (trademark of its owner).
"""
from __future__ import annotations

import math
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

ROOT = Path(__file__).resolve().parent.parent
TEX = ROOT / "textures"
TEX.mkdir(exist_ok=True)

# Fonts ---------------------------------------------------------------------
FONT_DIR = Path("/System/Library/Fonts")
SUP = FONT_DIR / "Supplemental"
F_HEI = str(FONT_DIR / "Hiragino Sans GB.ttc")
F_HEI_BOLD = F_HEI
F_ARIAL_BLACK = str(SUP / "Arial Black.ttf")
F_ARIAL_BOLD = str(SUP / "Arial Bold.ttf")
F_ARIAL = str(SUP / "Arial.ttf")
F_DIN = str(SUP / "DIN Condensed Bold.ttf")
F_DIN_ALT = str(SUP / "DIN Alternate Bold.ttf")
F_NEWYORK = str(FONT_DIR / "NewYork.ttf")
F_AVENIR = str(FONT_DIR / "Avenir Next.ttc")

ORANGE = (245, 130, 31)
GREEN = (0, 128, 97)
RED = (237, 27, 45)
INK = (23, 29, 27)
PAPER = (234, 229, 218)


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.truetype(F_ARIAL, size)


def f_hei(size):
    try:
        return ImageFont.truetype(F_HEI, size)
    except Exception:
        return ImageFont.truetype(F_ARIAL, size)


def text(draw, xy, string, f, fill, anchor="la", stroke=0, stroke_fill=None, spacing=0):
    if spacing:
        # Letter-spaced text, drawn manually (for small all-caps captions).
        x, y = xy
        for ch in string:
            draw.text((x, y), ch, font=f, fill=fill, anchor=anchor,
                      stroke_width=stroke, stroke_fill=stroke_fill)
            x += draw.textlength(ch, font=f) + spacing
        return
    draw.text(xy, string, font=f, fill=fill, anchor=anchor,
              stroke_width=stroke, stroke_fill=stroke_fill)


def center(draw, cx, y, string, f, fill, **kw):
    draw.text((cx, y), string, font=f, fill=fill, anchor="ma", **kw)


def linear_gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGB", size, top)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        col = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        d.line([(0, y), (w, y)], fill=col)
    return img


def grain(img, amount=8, seed=1):
    rng = random.Random(seed)
    px = img.load()
    w, h = img.size
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            n = rng.randint(-amount, amount)
            r, g, b = px[x, y][:3]
            v = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
            px[x, y] = v
            if x + 1 < w:
                px[x + 1, y] = v
            if y + 1 < h:
                px[x, y + 1] = v
    return img


def rounded(draw, box, r, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def stripes(img, y, height=34, alpha=255):
    w = img.width
    d = ImageDraw.Draw(img)
    n = 3
    for i, col in enumerate((ORANGE, GREEN, RED)):
        yy = y + i * height
        d.rectangle([0, yy, w, yy + height], fill=col + (alpha,) if img.mode == "RGBA" else col)


def paste_logo(base, box, preserve_ratio=True):
    logo = Image.open(TEX / "logo_7eleven.png").convert("RGBA")
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    if preserve_ratio:
        s = min(bw / logo.width, bh / logo.height)
        nw, nh = int(logo.width * s), int(logo.height * s)
    else:
        nw, nh = bw, bh
    logo = logo.resize((max(1, nw), max(1, nh)), Image.LANCZOS)
    base.paste(logo, (x0 + (bw - nw) // 2, y0 + (bh - nh) // 2), logo)


# ---------------------------------------------------------------------------
# Signage
# ---------------------------------------------------------------------------
def make_fascia():
    # The facade sign is 13.12 m by 0.82 m, exactly 16:1. Drawing at the same
    # aspect keeps the 7-Eleven wordmark from looking stretched in 3D.
    W, H = 4096, 256
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    # Very subtle panel joints and a light institutional gradient.
    for x in range(0, W, 512):
        d.line([(x, 0), (x, H)], fill=(226, 227, 220), width=3)
    top_glow = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(top_glow)
    for y in range(58):
        gd.rectangle([0, y, W, y + 1], fill=int(18 * (1 - y / 58)))
    img = Image.composite(Image.new("RGB", (W, H), (255, 255, 255)), img, top_glow)

    # Left descriptor.
    text(d, (132, 102), "便利商店", f_hei(64), (52, 60, 55), anchor="lm")
    text(d, (134, 170), "CONVENIENCE  STORE", font(F_DIN_ALT, 25), (125, 133, 126), spacing=5)
    d.line([(500, 56), (500, 198)], fill=(218, 219, 212), width=2)

    # Central official logo mark.
    paste_logo(img, (1840, 16, 2128, 240))
    d = ImageDraw.Draw(img)
    d.line([(2204, 62), (2204, 197)], fill=(219, 220, 213), width=2)
    text(d, (2258, 80), "24", font(F_DIN, 116), ORANGE, anchor="lt")
    text(d, (2362, 92), "HOURS", font(F_DIN_ALT, 57), GREEN)
    text(d, (2258, 154), "全年无休 · 天天为你", f_hei(31), (80, 87, 81))
    # Right-hand support copy, centred as one block.
    text(d, (3600, 102), "OPEN ALWAYS", font(F_DIN_ALT, 31), GREEN, anchor="ma")
    text(d, (3600, 151), "24 / 7", font(F_DIN, 42), (79, 86, 80), anchor="ma")
    # Thin colored rule along the bottom.
    stripes(img, H - 20, height=6)
    d = ImageDraw.Draw(img)
    d.line([(0, 0), (W, 0)], fill=(205, 207, 199), width=3)
    grain(img, 3, 4)
    img.save(TEX / "fascia_sign.png", optimize=True)


def make_pylon():
    W, H = 1024, 2048
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    # White lightbox upper half with inset border.
    d.rectangle([22, 22, W - 22, H - 22], outline=(205, 208, 200), width=5)
    paste_logo(img, (92, 84, W - 92, 1060))
    # Color band.
    stripes(img, 1112, 56)
    d = ImageDraw.Draw(img)
    # Lower green lightbox.
    d.rectangle([0, 1280, W, H], fill=GREEN)
    text(d, (512, 1328), "24", font(F_DIN, 390), (248, 248, 238), anchor="ma")
    text(d, (512, 1728), "HOURS", font(F_DIN_ALT, 108), (255, 255, 255), anchor="ma", spacing=16)
    d.line([(150, 1872), (874, 1872)], fill=(255, 255, 255), width=3)
    text(d, (512, 1902), "便利商店  ·  CONVENIENCE", f_hei(47), (246, 248, 239), anchor="ma")
    text(d, (512, 1972), "OPEN EVERY DAY", font(F_DIN_ALT, 33), (197, 226, 214), anchor="ma", spacing=6)
    grain(img, 2, 9)
    img.save(TEX / "pylon_sign.png", optimize=True)


def neon_text(draw, xy, string, f, color, glow=(255, 58, 39), radius=18):
    """Draw a faux neon tube with broad glow and a hot white core."""
    x, y = xy
    # broad bloom
    layer = Image.new("RGBA", draw._image.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.text((x, y), string, font=f, fill=glow + (255,), anchor="la")
    layer = layer.filter(ImageFilter.GaussianBlur(radius))
    draw._image.alpha_composite(layer)
    # inner glow
    layer2 = Image.new("RGBA", draw._image.size, (0, 0, 0, 0))
    l2 = ImageDraw.Draw(layer2)
    l2.text((x, y), string, font=f, fill=color + (255,), anchor="la", stroke_width=max(2, radius // 6),
            stroke_fill=color + (255,))
    layer2 = layer2.filter(ImageFilter.GaussianBlur(max(2, radius // 3)))
    draw._image.alpha_composite(layer2)
    # tube core
    draw.text((x, y), string, font=f, fill=(255, 248, 226, 255), anchor="la",
              stroke_width=max(1, radius // 12), stroke_fill=color + (255,))


def make_open_neon():
    W, H = 1024, 512
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(F_DIN, 278)
    neon_text(d, (512, 196), "OPEN", f, (255, 81, 54), radius=28)
    # center anchor by redrawing onto a temp layer
    img2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d2 = ImageDraw.Draw(img2)
    neon_text(d2, (74, 104), "OPEN", font(F_DIN, 290), (255, 83, 55), radius=30)
    # neon underline
    for off, alpha in ((14, 50), (8, 100), (2, 220)):
        d2.rounded_rectangle([160 - off, 414 - off // 2, 864 + off, 426 + off // 2], radius=off,
                             outline=(255, 92, 63, alpha), width=3)
    img2.save(TEX / "open_neon.png", optimize=True)


def make_window_decal():
    W, H = 1024, 768
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # A neat hours tag, plus a chain of small colored bars.
    d.rounded_rectangle([38, 40, 986, 724], radius=36, outline=(248, 249, 244, 200), width=4)
    text(d, (92, 116), "24", font(F_DIN, 296), (255, 255, 255, 238), anchor="la")
    text(d, (390, 160), "HOURS", font(F_DIN_ALT, 95), (255, 255, 255, 238), spacing=5)
    text(d, (96, 428), "全年无休", f_hei(95), (255, 255, 255, 238))
    text(d, (96, 556), "ALWAYS OPEN FOR YOU", font(F_DIN_ALT, 42), (255, 255, 255, 210), spacing=5)
    for i, c in enumerate((ORANGE, GREEN, RED)):
        d.rectangle([96 + i * 150, 646, 216 + i * 150, 664], fill=c + (230,))
    img.save(TEX / "window_decal.png", optimize=True)


def make_menu():
    W, H = 640, 900
    img = Image.new("RGB", (W, H), (22, 31, 28))
    d = ImageDraw.Draw(img)
    # chalkboard texture
    rng = random.Random(12)
    for _ in range(2400):
        x, y = rng.randrange(W), rng.randrange(H)
        v = rng.randint(20, 52)
        d.point((x, y), fill=(v, v + 5, v + 2))
    d.rounded_rectangle([24, 24, W - 24, H - 24], radius=16, outline=(243, 227, 198), width=4)
    text(d, (W // 2, 74), "CITY CAFÉ", font(F_NEWYORK, 72), (247, 238, 220), anchor="ma")
    text(d, (W // 2, 170), "城市咖啡", f_hei(38), (192, 216, 203), anchor="ma")
    d.line([(92, 232), (548, 232)], fill=(243, 227, 198, 255), width=3)
    items = [
        ("美式咖啡", "AMERICANO", "12"),
        ("拿铁咖啡", "LATTE", "16"),
        ("焦糖玛奇朵", "MACCHIATO", "18"),
        ("热巧克力", "HOT COCOA", "15"),
    ]
    y = 278
    for cn, en, price in items:
        text(d, (92, y), cn, f_hei(39), (245, 239, 224))
        text(d, (92, y + 48), en, font(F_DIN_ALT, 23), (151, 177, 165), spacing=2)
        text(d, (548, y + 18), f"¥{price}", font(F_DIN, 56), (245, 164, 92), anchor="ra")
        d.line([(92, y + 92), (548, y + 92)], fill=(72, 91, 83), width=2)
        y += 122
    text(d, (W // 2, 806), "OPEN DAILY", font(F_DIN_ALT, 30), (126, 203, 173), anchor="ma", spacing=6)
    img.save(TEX / "menu_coffee.png", optimize=True)


def make_slurpee_label():
    W, H = 1024, 320
    img = Image.new("RGB", (W, H), (247, 249, 245))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 16], fill=ORANGE)
    d.rectangle([0, 16, W, 30], fill=GREEN)
    d.rectangle([0, 30, W, 42], fill=RED)
    text(d, (54, 118), "SLURPEE", font(F_DIN, 150), RED, anchor="lm")
    text(d, (56, 246), "思乐冰 · FROZEN DRINKS", f_hei(46), (38, 65, 77), anchor="lm")
    # A small cup mark on the right.
    d.polygon([(760, 72), (916, 72), (954, 264), (722, 264)], fill=(218, 238, 245))
    d.ellipse([742, 52, 934, 104], fill=(245, 251, 251))
    d.line([(836, 58), (884, 12)], fill=(239, 93, 109), width=18)
    d.ellipse([(836, 50), (858, 76)], fill=(238, 72, 87))
    for k, c in enumerate((ORANGE, GREEN, RED)):
        d.rectangle([(754 + k * 54), 286, (790 + k * 54), 298], fill=c)
    img.save(TEX / "slurpee_machine_label.png", optimize=True)


def make_condiment_sign():
    W, H = 800, 280
    img = Image.new("RGB", (W, H), (247, 243, 232))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 14], fill=GREEN)
    d.rectangle([0, H - 14, W, H], fill=ORANGE)
    text(d, (42, 45), "COFFEE & CONDIMENTS", font(F_DIN_ALT, 46), GREEN, spacing=2)
    text(d, (44, 118), "咖啡调味台", f_hei(74), (33, 43, 37))
    text(d, (46, 210), "SELF SERVICE · 自行取用", f_hei(30), (97, 108, 98))
    # cup icon
    d.polygon([(670, 96), (730, 96), (718, 205), (682, 205)], fill=(101, 74, 55))
    d.ellipse([(668, 90), (732, 112)], fill=(244, 237, 220))
    d.line([(690, 82), (686, 58), (700, 50)], fill=(255, 255, 255), width=8)
    d.arc([(654, 118), (748, 190)], start=300, end=60, fill=(255, 255, 255), width=7)
    img.save(TEX / "condiment_sign.png", optimize=True)


def make_exit_sign():
    W, H = 512, 192
    img = Image.new("RGB", (W, H), (0, 121, 83))
    d = ImageDraw.Draw(img)
    d.rectangle([3, 3, W - 4, H - 4], outline=(233, 244, 232), width=4)
    text(d, (32, 55), "出口", f_hei(90), (247, 253, 240))
    text(d, (302, 68), "EXIT", font(F_DIN, 102), (247, 251, 240))
    d.polygon([(214, 58), (262, 96), (214, 134)], fill=(246, 250, 238))
    img.save(TEX / "exit_sign.png", optimize=True)


def make_atm_sign():
    W, H = 512, 512
    img = Image.new("RGB", (W, H), (12, 93, 155))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([12, 12, W - 13, H - 13], radius=18, outline=(168, 224, 242), width=7)
    text(d, (W // 2, 150), "ATM", font(F_DIN, 220), (246, 252, 253), anchor="mm")
    text(d, (W // 2, 326), "提款 / ATM", f_hei(48), (204, 237, 246), anchor="mm")
    d.rectangle([146, 398, 366, 410], fill=(ORANGE))
    d.rectangle([146, 410, 256, 422], fill=(GREEN))
    d.rectangle([256, 410, 366, 422], fill=(RED))
    img.save(TEX / "atm_sign.png", optimize=True)


def make_hotfood_menu():
    W, H = 560, 800
    img = Image.new("RGB", (W, H), (22, 30, 27))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([18, 18, W - 18, H - 18], radius=12, outline=(224, 182, 112), width=4)
    d.rectangle([18, 18, W - 18, 118], fill=(186, 56, 45))
    text(d, (W // 2, 66), "热食 HOT FOOD", f_hei(48), (255, 245, 220), anchor="mm")
    items = [("茶叶蛋", "TEA EGG", "2"), ("关东煮", "ODEN", "6起"),
             ("热狗", "HOT DOG", "6"), ("微波食品", "MICROWAVE", "12起"),
             ("包子", "STEAMED BUN", "4"), ("咖啡", "CITY CAFÉ", "12起")]
    y = 156
    for cn, en, price in items:
        d.text((50, y), cn, font=font(F_HEI, 34), fill=(247, 233, 204))
        d.text((52, y + 42), en, font=font(F_DIN_ALT, 21), fill=(152, 184, 166), spacing=2)
        d.text((W - 48, y + 20), f"¥{price}", font=font(F_DIN, 42), fill=(244, 170, 88), anchor="ra")
        d.line([(48, y + 74), (W - 48, y + 74)], fill=(99, 117, 105), width=1)
        y += 94
    text(d, (W // 2, 737), "现点现做 / MADE TO ORDER", f_hei(21), (136, 190, 161), anchor="mm")
    img.save(TEX / "hotfood_menu.png", optimize=True)


def make_newspaper_box():
    W, H = 560, 360
    img = Image.new("RGB", (W, H), (22, 50, 48))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 12], fill=ORANGE)
    d.rectangle([0, 12, W, 24], fill=GREEN)
    d.rectangle([0, 24, W, 36], fill=RED)
    text(d, (36, 70), "报纸", f_hei(82), (248, 245, 231))
    text(d, (38, 166), "NEWSPAPER", font(F_DIN_ALT, 32), (177, 212, 196), spacing=2)
    d.rounded_rectangle([316, 56, 512, 246], radius=8, outline=(200, 222, 207), width=4)
    # stylised folded newspaper
    d.rectangle([348, 98, 486, 214], fill=(238, 236, 223))
    for i in range(6):
        d.line([(360, 116 + i * 15), (470, 116 + i * 15)], fill=(100, 108, 99), width=2)
    d.rectangle([360, 98, 470, 108], fill=(188, 65, 51))
    text(d, (38, 262), "投币 · 取报", f_hei(28), (215, 228, 211))
    text(d, (38, 306), "COIN · TAKE ONE", font(F_DIN_ALT, 20), (150, 189, 169), spacing=2)
    img.save(TEX / "newspaper_box.png", optimize=True)


def make_magazine_sign():
    W, H = 560, 150
    img = Image.new("RGB", (W, H), (16, 96, 73))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=ORANGE)
    text(d, (28, 48), "杂志", f_hei(54), (251, 248, 233))
    text(d, (154, 57), "MAGAZINES · NEWSPAPERS", font(F_DIN_ALT, 24), (203, 232, 216), spacing=2)
    d.rectangle([W - 112, 38, W - 98, 114], fill=ORANGE)
    d.rectangle([W - 94, 38, W - 80, 114], fill=GREEN)
    d.rectangle([W - 76, 38, W - 62, 114], fill=RED)
    img.save(TEX / "magazine_sign.png", optimize=True)


def make_sidewalk_stains():
    W = H = 512
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rng = random.Random(902)
    for i in range(7):
        cx, cy = rng.randint(80, W - 80), rng.randint(80, H - 80)
        rw, rh = rng.randint(32, 110), rng.randint(18, 48)
        for j in range(4):
            ox, oy = rng.randint(-22, 22), rng.randint(-12, 12)
            alpha = rng.randint(20, 65)
            d.ellipse([cx - rw + ox, cy - rh + oy, cx + rw + ox, cy + rh + oy],
                      fill=(64, 54, 41, alpha))
    # Fine cracks / grime streaks.
    for i in range(3):
        y = rng.randint(80, H - 80)
        pts = [(0, y)]
        for x in range(0, W + 40, 40):
            pts.append((x, y + rng.randint(-3, 3)))
        d.line(pts, fill=(48, 41, 32, 55), width=2)
    img = img.filter(ImageFilter.GaussianBlur(1.4))
    img.save(TEX / "sidewalk_stains.png", optimize=True)


def make_door_stickers():
    W = H = 512
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Auto-door sticker.
    d.rounded_rectangle([42, 54, 470, 200], radius=18, fill=(247, 247, 240, 238),
                        outline=(54, 108, 124, 245), width=6)
    text(d, (70, 74), "自动门", f_hei(50), (39, 66, 70))
    text(d, (72, 143), "AUTO DOOR · 请小心", f_hei(20), (85, 108, 108))
    d.polygon([(406, 94), (446, 126), (406, 158)], fill=(48, 126, 145, 245))
    # Push plate.
    d.rounded_rectangle([68, 258, 444, 486], radius=24, fill=(246, 245, 235, 238),
                        outline=(213, 57, 48, 245), width=7)
    text(d, (W // 2, 306), "推", f_hei(64), (42, 51, 43), anchor="mm")
    text(d, (W // 2, 382), "PUSH", font(F_DIN_ALT, 36), (52, 64, 55), anchor="mm")
    d.polygon([(218, 428), (294, 428), (256, 468)], fill=(213, 57, 48, 245))
    # Small 7-Eleven stripe at the bottom.
    for i, c in enumerate((ORANGE, GREEN, RED)):
        d.rectangle([(72 + i * 58), 456, (112 + i * 58), 472], fill=c)
    img.save(TEX / "door_stickers.png", optimize=True)


def make_payment_methods():
    """Vertical payment-method plaque for the blank pier left of the door."""
    W, H = 512, 1280
    img = Image.new("RGB", (W, H), (249, 246, 235))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 148], fill=(18, 87, 67))
    for i, c in enumerate((ORANGE, GREEN, RED)):
        d.rectangle([0, i * 8, W, (i + 1) * 8], fill=c)
    text(d, (30, 44), "本店支援", f_hei(36), (247, 247, 233))
    text(d, (30, 96), "PAYMENT METHODS", font(F_DIN_ALT, 24), (190, 222, 207), spacing=2)
    d.rectangle([32, 148, W - 32, 153], fill=(202, 196, 177))

    def row_card(y, h=250):
        d.rounded_rectangle([24, y, W - 24, y + h], radius=16,
                            fill=(252, 250, 242), outline=(220, 215, 199), width=2)

    # Alipay.
    y = 184
    row_card(y)
    d.rounded_rectangle([44, y + 44, 174, y + 174], radius=22, fill=(24, 119, 255))
    text(d, (109, y + 106), "支", f_hei(92), (255, 255, 255), anchor="mm")
    text(d, (206, y + 52), "支付宝", f_hei(50), (32, 48, 39))
    text(d, (208, y + 124), "Alipay", font(F_DIN_ALT, 42), (24, 119, 255), spacing=2)
    text(d, (208, y + 186), "扫码付款 · SCAN TO PAY", f_hei(19), (104, 114, 102))
    d.line([(24, y + 250), (W - 24, y + 250)], fill=(217, 211, 193), width=2)

    # WeChat Pay.
    y = 466
    row_card(y)
    d.rounded_rectangle([44, y + 44, 174, y + 174], radius=22, fill=(7, 193, 96))
    d.ellipse([66, y + 78, 146, y + 142], fill=(247, 252, 244))
    d.polygon([(92, y + 134), (88, y + 164), (120, y + 142)], fill=(247, 252, 244))
    d.ellipse([108, y + 96, 186, y + 158], fill=(247, 252, 244))
    d.polygon([(158, y + 150), (172, y + 174), (142, y + 156)], fill=(247, 252, 244))
    for cx, cy in ((94, y + 106), (124, y + 106), (130, y + 124), (156, y + 124)):
        d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(7, 193, 96))
    text(d, (206, y + 52), "微信支付", f_hei(45), (32, 48, 39))
    text(d, (208, y + 124), "WeChat Pay", font(F_DIN_ALT, 34), (7, 162, 81), spacing=1)
    text(d, (208, y + 186), "扫码付款 · SCAN TO PAY", f_hei(19), (104, 114, 102))
    d.line([(24, y + 250), (W - 24, y + 250)], fill=(217, 211, 193), width=2)

    # UnionPay.
    y = 748
    row_card(y)
    for i, c in enumerate(((210, 30, 45), (0, 91, 172), (0, 153, 68))):
        x = 48 + i * 48
        d.rounded_rectangle([x, y + 50, x + 42, y + 186], radius=12, fill=c)
        d.rounded_rectangle([x + 9, y + 64, x + 33, y + 172], radius=8,
                            outline=(255, 255, 255, 65), width=2)
    text(d, (214, y + 52), "银联", f_hei(48), (32, 48, 39))
    text(d, (216, y + 124), "UnionPay", font(F_DIN_ALT, 34), (0, 91, 172), spacing=1)
    text(d, (216, y + 186), "刷卡付款 · CARD ACCEPTED", f_hei(19), (104, 114, 102))

    # Footer.
    d.rectangle([0, H - 116, W, H], fill=(18, 87, 67))
    text(d, (W // 2, H - 72), "7-ELEVEN · 中山门店", f_hei(24), (233, 244, 229), anchor="mm")
    text(d, (W // 2, H - 36), "支付方式以门店公告为准", f_hei(16), (165, 200, 182), anchor="mm")
    img.save(TEX / "payment_methods.png", optimize=True)


def make_bike_parking():
    W, H = 420, 540
    img = Image.new("RGB", (W, H), (21, 88, 142))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([12, 12, W - 12, H - 12], radius=12,
                        outline=(232, 245, 246), width=6)
    text(d, (W // 2, 62), "自行车", f_hei(46), (249, 252, 248), anchor="mm")
    text(d, (W // 2, 106), "停放区", f_hei(34), (207, 234, 240), anchor="mm")
    # Simple bicycle icon.
    cy = 300
    for cx in (112, 308):
        d.ellipse([cx - 70, cy - 70, cx + 70, cy + 70], outline=(250, 252, 248), width=8)
    d.line([(112, cy), (185, cy - 78), (238, cy), (112, cy)], fill=(250, 252, 248), width=8)
    d.line([(185, cy - 78), (220, cy - 78)], fill=(250, 252, 248), width=8)
    d.line([(238, cy), (270, cy - 78)], fill=(250, 252, 248), width=8)
    d.line([(258, cy - 92), (294, cy - 92)], fill=(250, 252, 248), width=7)
    d.ellipse([198, cy - 98, 230, cy - 75], fill=(250, 252, 248))
    text(d, (W // 2, 462), "BIKE PARKING", font(F_DIN_ALT, 28), (225, 241, 242), anchor="mm")
    text(d, (W // 2, 500), "请依序停放", f_hei(17), (191, 222, 231), anchor="mm")
    img.save(TEX / "bike_parking.png", optimize=True)


def make_store_plaque():
    W, H = 640, 360
    img = Image.new("RGB", (W, H), (241, 237, 226))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([10, 10, W - 10, H - 10], radius=12, outline=(52, 63, 55), width=7)
    text(d, (36, 38), "7-ELEVEN", font(F_ARIAL_BLACK, 70), (231, 80, 35))
    text(d, (40, 134), "中山门店", f_hei(78), (37, 48, 40))
    text(d, (42, 242), "NO. 7  ·  ZHONGSHAN", font(F_DIN_ALT, 36), (71, 94, 81), spacing=2)
    for i, c in enumerate((ORANGE, GREEN, RED)):
        d.rectangle([(444 + i * 48), 58, (478 + i * 48), 144], fill=c)
    img.save(TEX / "store_plaque.png", optimize=True)


def make_promo_tag():
    W, H = 512, 640
    img = Image.new("RGB", (W, H), (251, 239, 191))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 86], fill=(221, 52, 52))
    text(d, (W // 2, 43), "本日特价", f_hei(56), (255, 249, 228), anchor="mm")
    d.ellipse([72, 110, 440, 478], fill=(250, 250, 242))
    text(d, (W // 2, 194), "49", font(F_DIN, 210), (216, 47, 49), anchor="mm")
    text(d, (W // 2, 306), "元", f_hei(58), (55, 66, 56), anchor="mm")
    text(d, (W // 2, 420), "咖啡 / COFFEE", f_hei(30), (67, 85, 70), anchor="mm")
    for i, c in enumerate((ORANGE, GREEN, RED)):
        d.rectangle([(152 + i * 72), 546, (206 + i * 72), 580], fill=c)
    img.save(TEX / "promo_tag.png", optimize=True)


def make_icecream_label():
    W, H = 768, 256
    img = Image.new("RGB", (W, H), (244, 241, 230))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 20], fill=(72, 163, 198))
    d.rectangle([0, H - 20, W, H], fill=(72, 163, 198))
    text(d, (42, 64), "冰品", f_hei(84), (42, 72, 79))
    text(d, (44, 160), "ICE CREAM · 霜淇淋", f_hei(32), (78, 106, 112))
    # cone mark
    d.polygon([(620, 76), (716, 76), (690, 200), (646, 200)], fill=(214, 166, 105))
    d.ellipse([(606, 46), (730, 112)], fill=(249, 244, 224))
    d.arc([(616, 74), (720, 152)], start=190, end=350, fill=(242, 230, 201), width=10)
    img.save(TEX / "icecream_label.png", optimize=True)


def make_road_sign():
    W, H = 900, 280
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, W - 5, H - 5], radius=18, fill=(14, 92, 70, 255), outline=(245, 248, 242, 255), width=9)
    text(d, (46, 42), "中山北路", f_hei(100), (251, 252, 248), anchor="la")
    text(d, (48, 176), "Zhongshan N. Rd.", font(F_ARIAL_BOLD, 54), (245, 248, 241), anchor="la")
    text(d, (W - 34, 190), "§2", font(F_DIN, 58), (225, 237, 231), anchor="ra")
    img.save(TEX / "road_sign.png", optimize=True)


def make_a_frame():
    W, H = 640, 900
    img = Image.new("RGB", (W, H), (15, 23, 20))
    d = ImageDraw.Draw(img)
    # aluminum inset frame
    d.rounded_rectangle([20, 20, W - 20, H - 20], radius=22, outline=(198, 205, 195), width=5)
    paste_logo(img, (92, 62, W - 92, 320))
    d = ImageDraw.Draw(img)
    stripes(img, 356, 24, alpha=255)
    d = ImageDraw.Draw(img)
    text(d, (W // 2, 470), "霜淇淋", f_hei(84), (248, 245, 223), anchor="ma")
    text(d, (W // 2, 574), "SOFT SERVE", font(F_DIN_ALT, 44), (164, 206, 186), anchor="ma", spacing=8)
    # little cone graphic
    d.polygon([(260, 640), (380, 640), (342, 785), (298, 785)], fill=(222, 179, 112))
    d.polygon([(258, 630), (382, 630), (374, 684), (266, 684)], fill=(250, 242, 216))
    d.arc([270, 570, 370, 660], start=180, end=360, fill=(250, 242, 216), width=26)
    d.arc([265, 620, 375, 700], start=200, end=340, fill=(245, 230, 197), width=10)
    text(d, (W // 2, 830), "便利店 / CONVENIENCE", f_hei(28), (213, 221, 207), anchor="ma")
    img.save(TEX / "a_frame.png", optimize=True)


def make_ice_label():
    W, H = 640, 240
    img = Image.new("RGB", (W, H), (239, 246, 247))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 36], fill=(39, 147, 193))
    d.rectangle([0, H - 36, W, H], fill=(39, 147, 193))
    text(d, (W // 2, H // 2 + 4), "ICE", font(F_DIN, 154), (41, 128, 168), anchor="mm")
    text(d, (58, 140), "纯净冰块", f_hei(36), (77, 112, 126), anchor="lm")
    text(d, (W - 58, 140), "CRYSTAL", font(F_DIN_ALT, 26), (77, 112, 126), anchor="rm", spacing=5)
    img.save(TEX / "ice_label.png", optimize=True)


def make_fridge_header():
    W, H = 1200, 170
    img = Image.new("RGB", (W, H), (245, 248, 241))
    d = ImageDraw.Draw(img)
    text(d, (44, H // 2), "饮料", f_hei(86), GREEN, anchor="lm")
    text(d, (222, H // 2 + 4), "DRINKS · COLD BEVERAGES", font(F_DIN_ALT, 46), (46, 73, 61), anchor="lm", spacing=5)
    for i, c in enumerate((ORANGE, GREEN, RED)):
        d.rectangle([38 + i * 52, H - 18, 78 + i * 52, H - 10], fill=c)
    img.save(TEX / "fridge_header.png", optimize=True)


def make_aisle_signs():
    items = [
        ("零食", "SNACKS", "01"),
        ("饮料", "DRINKS", "02"),
        ("生活用品", "DAILY GOODS", "03"),
    ]
    for i, (cn, en, no) in enumerate(items):
        W, H = 640, 200
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([4, 4, W - 5, H - 5], radius=16, fill=(246, 247, 239, 252), outline=(206, 208, 198), width=3)
        d.rectangle([4, 4, 22, H - 4], fill=GREEN)
        text(d, (52, 32), cn, f_hei(66), (28, 39, 33), anchor="la")
        text(d, (54, 124), en, font(F_DIN_ALT, 31), (107, 122, 113), spacing=3)
        text(d, (W - 44, 100), no, font(F_DIN, 102), ORANGE, anchor="mm")
        img.save(TEX / f"aisle_{i + 1}.png", optimize=True)


# ---------------------------------------------------------------------------
# Posters
# ---------------------------------------------------------------------------
def make_coffee_poster():
    W, H = 720, 1080
    base = linear_gradient((W, H), (44, 33, 29), (96, 57, 35))
    img = base.convert("RGBA")
    d = ImageDraw.Draw(img)
    # halo
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hd.ellipse([80, 150, W - 20, 900], fill=(243, 160, 86, 36))
    halo = halo.filter(ImageFilter.GaussianBlur(120))
    img.alpha_composite(halo)
    d = ImageDraw.Draw(img)
    # cup + saucer, stylized
    d.ellipse([188, 760, 532, 900], fill=(34, 26, 22, 205))
    d.ellipse([214, 745, 506, 870], fill=(233, 214, 184, 255))
    d.rounded_rectangle([250, 390, 470, 770], radius=36, fill=(245, 237, 218))
    d.ellipse([250, 356, 470, 448], fill=(66, 39, 27))
    d.ellipse([274, 372, 446, 430], fill=(119, 70, 40))
    d.arc([436, 486, 560, 674], start=280, end=100, fill=(245, 237, 218), width=24)
    # steam
    for k in range(3):
        pts = []
        for j in range(31):
            t = j / 30
            pts.append((350 + (k - 1) * 58 + math.sin(t * 8 + k) * 18, 350 - t * 190))
        d.line(pts, fill=(243, 227, 202, 100), width=7, joint="curve")
    # typography
    text(d, (48, 54), "CITY", font(F_NEWYORK, 112), (249, 239, 217))
    text(d, (48, 158), "CAFÉ", font(F_NEWYORK, 112), (245, 170, 105))
    text(d, (52, 304), "城市咖啡", f_hei(48), (243, 230, 213))
    text(d, (W - 44, 86), "07 / 11", font(F_DIN, 58), (233, 184, 128), anchor="ra")
    text(d, (52, 930), "今天，也为你留一杯。", f_hei(43), (244, 231, 212))
    text(d, (52, 994), "A WARM CUP, AROUND THE CLOCK", font(F_DIN_ALT, 29), (211, 180, 151), spacing=3)
    stripes(img, H - 28, 10)
    grain(img.convert("RGB"), 4, 5).save(TEX / "poster_coffee.png", optimize=True)


def make_slurpee_poster():
    W, H = 720, 1080
    base = linear_gradient((W, H), (13, 115, 157), (37, 191, 178))
    img = base.convert("RGBA")
    d = ImageDraw.Draw(img)
    # ice crystal shapes
    rng = random.Random(101)
    for _ in range(60):
        x, y = rng.randrange(W), rng.randrange(H)
        r = rng.randint(3, 18)
        col = (255, 255, 255, rng.randint(16, 64))
        d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    # frozen wave field
    d.ellipse([-170, 690, W + 170, 1220], fill=(232, 247, 244, 48))
    d.ellipse([-250, 790, W + 260, 1320], fill=(9, 80, 124, 120))
    # Slurpee cup
    d.polygon([(252, 444), (500, 444), (552, 893), (196, 893)], fill=(247, 248, 242))
    d.polygon([(252, 444), (500, 444), (506, 492), (246, 492)], fill=(32, 64, 73))
    d.ellipse([236, 398, 514, 500], fill=(250, 250, 246))
    # icy swirl dome
    for i, (cx, cy, rr, col) in enumerate([
        (350, 370, 122, (251, 87, 109)), (410, 330, 94, (255, 149, 78)),
        (300, 316, 82, (71, 200, 199)), (370, 280, 74, (249, 245, 210)),
    ]):
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col + (255,))
    # straw
    d.line([(430, 280), (512, 110)], fill=(244, 96, 106), width=30)
    d.line([(430, 280), (512, 110)], fill=(255, 155, 155), width=8)
    # cup graphics
    d.polygon([(268, 575), (486, 575), (500, 698), (252, 698)], fill=(232, 55, 96))
    text(d, (376, 638), "SLURPEE", font(F_DIN_ALT, 54), (255, 249, 231), anchor="mm", spacing=2)
    for k, col in enumerate(((246, 196, 69), (78, 198, 182), (238, 98, 123))):
        d.arc([300 + k * 46, 736, 364 + k * 46, 800], start=200, end=340, fill=col, width=15)
    text(d, (48, 54), "思乐冰", f_hei(104), (251, 250, 238))
    text(d, (52, 184), "FROZEN  ·  HAPPY", font(F_DIN_ALT, 37), (217, 250, 244), spacing=6)
    text(d, (48, 942), "整个夏天，都在这一杯。", f_hei(40), (246, 252, 247))
    text(d, (48, 1000), "ICE COLD · EVERY DAY", font(F_DIN_ALT, 29), (202, 238, 232), spacing=4)
    stripes(img, H - 28, 10)
    grain(img.convert("RGB"), 3, 6).save(TEX / "poster_slurpee.png", optimize=True)


def make_food_poster():
    W, H = 720, 1080
    base = linear_gradient((W, H), (119, 34, 28), (236, 120, 45))
    img = base.convert("RGBA")
    d = ImageDraw.Draw(img)
    # sun disc
    d.ellipse([340, 140, 860, 660], fill=(255, 205, 110, 70))
    # onigiri
    d.polygon([(212, 720), (370, 440), (528, 720)], fill=(248, 243, 223))
    d.rounded_rectangle([300, 610, 440, 792], radius=26, fill=(27, 46, 37))
    d.polygon([(312, 706), (430, 706), (430, 748), (312, 748)], fill=(248, 243, 223))
    # fried chicken pieces
    for cx, cy, rr in ((164, 852, 78), (286, 903, 64), (420, 848, 70)):
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(197, 108, 45))
        for k in range(9):
            ang = k / 9 * math.tau
            d.ellipse([cx + math.cos(ang) * rr * .45 - 10, cy + math.sin(ang) * rr * .32 - 10,
                       cx + math.cos(ang) * rr * .45 + 10, cy + math.sin(ang) * rr * .32 + 10],
                      fill=(228, 149, 74, 180))
    text(d, (46, 60), "HOT", font(F_DIN, 150), (255, 246, 218))
    text(d, (46, 188), "& FRESH", font(F_DIN, 96), (255, 219, 158))
    text(d, (50, 328), "加热即食 · 温暖上桌", f_hei(44), (255, 237, 209))
    text(d, (50, 960), "每一口，都是刚好的温度。", f_hei(37), (255, 239, 214))
    stripes(img, H - 28, 10)
    grain(img.convert("RGB"), 4, 7).save(TEX / "poster_food.png", optimize=True)


# ---------------------------------------------------------------------------
# Surface materials / atlas
# ---------------------------------------------------------------------------
def make_tiles(name, base, grout, n=4, size=1024, rough=False, dirt=0.05, seed=1):
    img = Image.new("RGB", (size, size), grout)
    d = ImageDraw.Draw(img)
    rng = random.Random(seed)
    gap = 6
    cell = size // n
    for iy in range(n):
        for ix in range(n):
            v = rng.randint(-6, 6)
            col = tuple(max(0, min(255, c + v)) for c in base)
            x0, y0 = ix * cell + gap, iy * cell + gap
            x1, y1 = x0 + cell - gap, y0 + cell - gap
            d.rectangle([x0, y0, x1, y1], fill=col)
            if dirt:
                for _ in range(int(35 * dirt * 20)):
                    px = rng.randint(x0 + 4, max(x0 + 5, x1 - 4))
                    py = rng.randint(y0 + 4, max(y0 + 5, y1 - 4))
                    rr = rng.randint(1, 7)
                    shade = tuple(max(0, min(255, c + rng.randint(-18, 10))) for c in col)
                    d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=shade)
    grain(img, 5, seed)
    img.save(TEX / name, optimize=True)


def make_asphalt():
    W = H = 1024
    img = Image.new("RGB", (W, H), (46, 48, 47))
    d = ImageDraw.Draw(img)
    rng = random.Random(31)
    for _ in range(28000):
        x, y = rng.randrange(W), rng.randrange(H)
        v = rng.randint(23, 83)
        a = rng.randint(40, 160)
        d.point((x, y), fill=(v, v + 2, v + 1))
    for _ in range(40):
        x, y = rng.randrange(W), rng.randrange(H)
        r = rng.randint(4, 26)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(38, 40, 39))
    # a few faint tar seams
    for _ in range(8):
        x = rng.randrange(W)
        d.line([(x, 0), (x + rng.randint(-80, 80), H)], fill=(38, 40, 39), width=rng.randint(1, 3))
    img = img.filter(ImageFilter.GaussianBlur(0.35))
    img.save(TEX / "asphalt.png", optimize=True)


def make_facade_panels():
    """A quiet, warm off-white aluminium panel surface for the building shell."""
    W = H = 1024
    img = Image.new("RGB", (W, H), (227, 224, 214))
    d = ImageDraw.Draw(img)
    rng = random.Random(181)
    # Fine vertical brushed-metal streaks.
    for _ in range(16000):
        x = rng.randrange(W)
        y = rng.randrange(H)
        v = rng.randint(214, 235)
        d.point((x, y), fill=(v, v - 1, v - 5))
    # Large panel joints: the texture tiles every 2.4 m in the model.
    for x in (0, 512):
        d.line([(x, 0), (x, H)], fill=(190, 187, 178), width=3)
    for y in (0, 512):
        d.line([(0, y), (W, y)], fill=(195, 192, 183), width=2)
    # A few faint streaks and water marks near the panel joints.
    for _ in range(24):
        x = rng.randrange(W)
        y = rng.randrange(H)
        rw = rng.randint(4, 26)
        rh = rng.randint(8, 60)
        d.rectangle([x, y, x + rw, y + rh], fill=(218 + rng.randint(-6, 5), 216, 206))
    img = img.filter(ImageFilter.GaussianBlur(0.45))
    grain(img, 2, 17)
    img.save(TEX / "facade_panels.png", optimize=True)


def make_concrete():
    W = H = 768
    img = Image.new("RGB", (W, H), (201, 199, 188))
    d = ImageDraw.Draw(img)
    rng = random.Random(33)
    for _ in range(18000):
        x, y = rng.randrange(W), rng.randrange(H)
        v = rng.randint(170, 225)
        d.point((x, y), fill=(v, v - 1, v - 5))
    # formwork scars / subtle stains
    for _ in range(14):
        x = rng.randrange(W)
        y = rng.randrange(H)
        r = rng.randint(12, 70)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(186, 184, 172))
    img = img.filter(ImageFilter.GaussianBlur(0.7))
    img.save(TEX / "concrete_wall.png", optimize=True)


def make_magazines():
    W = H = 1024
    img = Image.new("RGB", (W, H), (214, 210, 198))
    d = ImageDraw.Draw(img)
    rng = random.Random(66)
    cols, rows = 8, 8
    cw, ch = W // cols, H // rows
    palette = [(225, 64, 83), (48, 144, 189), (240, 170, 50), (60, 165, 103),
               (120, 94, 176), (241, 113, 55), (23, 62, 95), (232, 219, 187),
               (205, 48, 62), (52, 169, 167)]
    words = ["CITY", "WEEKLY", "MILK", "STYLE", "TODAY", "GAME", "HOME", "TRAVEL"]
    for iy in range(rows):
        for ix in range(cols):
            x0, y0 = ix * cw + 3, iy * ch + 3
            x1, y1 = x0 + cw - 6, y0 + ch - 6
            col = rng.choice(palette)
            d.rectangle([x0, y0, x1, y1], fill=col)
            # white title band and dramatic diagonal photo shape
            d.rectangle([x0 + 5, y0 + 6, x1 - 5, y0 + 26], fill=(249, 247, 238))
            d.text((x0 + 9, y0 + 8), rng.choice(words), font=font(F_ARIAL_BOLD, 15), fill=(26, 30, 28))
            d.polygon([(x0 + 7, y1 - 32), (x1 - 7, y0 + 38), (x1 - 7, y1 - 8), (x0 + 7, y1 - 8)],
                      fill=tuple(min(255, c + 26) for c in col))
            d.ellipse([x1 - 37, y1 - 40, x1 - 11, y1 - 14], fill=(250, 245, 230))
            d.text((x0 + 9, y1 - 24), "7", font=font(F_ARIAL_BLACK, 18), fill=(250, 247, 236))
    img.save(TEX / "magazines.png", optimize=True)


def make_product_atlas():
    """Small atlas of generic package labels used on boxes and bottles."""
    W, H = 1024, 512
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    rng = random.Random(8)
    colors = [(238, 77, 61), (253, 183, 64), (69, 164, 210), (58, 158, 112),
              (112, 91, 169), (239, 142, 64), (44, 73, 95), (228, 221, 208)]
    for i in range(16):
        x0 = (i % 4) * 256
        y0 = (i // 4) * 128
        c = colors[i % len(colors)]
        d.rectangle([x0, y0, x0 + 256, y0 + 128], fill=c)
        d.rectangle([x0 + 18, y0 + 16, x0 + 238, y0 + 58], fill=(249, 246, 235))
        d.text((x0 + 28, y0 + 24), ["MILK", "TEA", "CHIPS", "COCOA", "SODA", "BREAD", "CANDY", "RICE"][i % 8],
               font=font(F_ARIAL_BOLD, 25), fill=(31, 38, 34))
        for k in range(7):
            px = x0 + 25 + k * 30
            d.ellipse([px, y0 + 78, px + 18, y0 + 96], fill=tuple(max(0, min(255, v - 25)) for v in c))
        d.rectangle([x0 + 200, y0 + 76, x0 + 232, y0 + 100], fill=(251, 248, 236))
    img.save(TEX / "product_atlas.png", optimize=True)


def make_product_packaging():
    """A 64-cell atlas of generic snack, drink and grocery packaging.

    Each cell is a readable faceted front label. In Blender, boxes are mapped
    to individual cells so the shelves read as stocked merchandise rather than
    coloured blocks.
    """
    W = H = 2048
    cols = rows = 8
    cell = W // cols
    img = Image.new("RGB", (W, H), (230, 226, 215))
    d = ImageDraw.Draw(img)
    rng = random.Random(714)
    palettes = [
        ((226, 61, 55), (255, 220, 154), (246, 247, 239)),
        ((47, 123, 171), (194, 232, 241), (248, 247, 236)),
        ((241, 148, 41), (255, 236, 183), (64, 55, 42)),
        ((75, 152, 92), (219, 241, 194), (250, 249, 239)),
        ((116, 80, 151), (230, 213, 245), (252, 248, 238)),
        ((196, 73, 57), (255, 227, 198), (255, 252, 243)),
        ((47, 67, 87), (196, 213, 222), (251, 248, 238)),
        ((209, 174, 61), (255, 248, 210), (44, 50, 42)),
        ((38, 118, 118), (213, 244, 237), (250, 249, 237)),
        ((173, 66, 95), (250, 218, 224), (250, 246, 234)),
        ((79, 101, 61), (224, 235, 190), (250, 249, 238)),
        ((213, 118, 60), (255, 234, 199), (57, 48, 36)),
    ]
    names = [
        ("洋芋片", "POTATO CHIPS", "chips"), ("巧克力", "CHOCOLATE", "bar"),
        ("苏打饼", "SODA CRACKERS", "cracker"), ("泡面", "INSTANT NOODLES", "noodle"),
        ("奶茶", "MILK TEA", "cup"), ("咖啡", "COFFEE", "cup"),
        ("果汁", "FRUIT JUICE", "bottle"), ("矿泉水", "MINERAL WATER", "bottle"),
        ("牛奶", "MILK", "carton"), ("面包", "BREAD", "bread"),
        ("饭团", "RICE BALL", "rice"), ("糖果", "CANDY", "candy"),
        ("口香糖", "GUM", "candy"), ("冰品", "ICE CREAM", "ice"),
        ("能量饮", "ENERGY DRINK", "can"), ("茶饮", "TEA", "bottle"),
        ("饼干", "COOKIE", "cookie"), ("泡芙", "CREAM PUFF", "puff"),
        ("优格", "YOGURT", "cup"), ("豆浆", "SOY MILK", "carton"),
        ("巧克力棒", "CHOC BAR", "bar"), ("薯条", "FRIES", "chips"),
        ("坚果", "NUTS", "snack"), ("果冻", "JELLY", "cup"),
        ("科学面", "SNACK NOODLES", "noodle"), ("米果", "RICE CRACKER", "cracker"),
        ("红茶", "BLACK TEA", "bottle"), ("运动饮料", "SPORTS DRINK", "bottle"),
        ("三明治", "SANDWICH", "sandwich"), ("热狗", "HOT DOG", "snack"),
        ("茶叶蛋", "TEA EGG", "snack"), ("关东煮", "ODEN", "noodle"),
    ]

    def food_icon(kind, cx, cy, s, accent):
        if kind == "chips":
            d.polygon([(cx - 38*s, cy + 10*s), (cx - 12*s, cy - 34*s), (cx + 26*s, cy - 14*s), (cx + 8*s, cy + 26*s)], fill=accent)
            d.polygon([(cx + 4*s, cy - 24*s), (cx + 38*s, cy - 8*s), (cx + 24*s, cy + 26*s)], fill=(255, 205, 102))
        elif kind == "bar":
            d.rounded_rectangle([cx - 48*s, cy - 24*s, cx + 48*s, cy + 24*s], radius=6*s, fill=(72, 43, 30))
            d.rectangle([cx - 40*s, cy - 16*s, cx + 40*s, cy + 16*s], fill=accent)
            for i in range(4):
                d.line([(cx - 33*s + i*18*s, cy - 16*s), (cx - 33*s + i*18*s, cy + 16*s)], fill=(98, 60, 35), width=max(1,int(2*s)))
        elif kind in ("bottle", "can"):
            d.rounded_rectangle([cx - 24*s, cy - 42*s, cx + 24*s, cy + 36*s], radius=10*s, fill=accent)
            d.rectangle([cx - 18*s, cy - 6*s, cx + 18*s, cy + 18*s], fill=(249, 245, 229))
            d.ellipse([cx - 13*s, cy - 38*s, cx + 13*s, cy - 27*s], fill=(231, 235, 226))
        elif kind == "cup":
            d.polygon([(cx - 34*s, cy - 26*s), (cx + 34*s, cy - 26*s), (cx + 22*s, cy + 34*s), (cx - 22*s, cy + 34*s)], fill=(247, 241, 226))
            d.ellipse([cx - 35*s, cy - 34*s, cx + 35*s, cy - 20*s], fill=accent)
            d.arc([cx - 58*s, cy - 100*s, cx - 12*s, cy - 20*s], start=200, end=340, fill=(255, 255, 255), width=max(2,int(2*s)))
        elif kind == "carton":
            d.polygon([(cx - 35*s, cy - 34*s), (cx + 35*s, cy - 34*s), (cx + 35*s, cy + 40*s), (cx - 35*s, cy + 40*s)], fill=(244, 241, 227))
            d.polygon([(cx - 35*s, cy - 34*s), (cx, cy - 54*s), (cx + 35*s, cy - 34*s)], fill=accent)
            d.rectangle([cx - 28*s, cy - 12*s, cx + 28*s, cy + 20*s], fill=accent)
        elif kind == "bread":
            d.ellipse([cx - 48*s, cy - 30*s, cx + 48*s, cy + 38*s], fill=(208, 153, 81))
            d.arc([cx - 32*s, cy - 18*s, cx + 8*s, cy + 20*s], start=200, end=340, fill=(240, 201, 145), width=max(2,int(3*s)))
            d.arc([cx + 2*s, cy - 18*s, cx + 42*s, cy + 20*s], start=200, end=340, fill=(240, 201, 145), width=max(2,int(3*s)))
        elif kind == "rice":
            d.polygon([(cx, cy - 46*s), (cx + 48*s, cy + 32*s), (cx - 48*s, cy + 32*s)], fill=(250, 247, 233))
            d.rounded_rectangle([cx - 32*s, cy + 4*s, cx + 32*s, cy + 38*s], radius=4*s, fill=(37, 52, 42))
        elif kind == "candy":
            for row in range(2):
                for col in range(3):
                    d.ellipse([cx - 42*s + col*30*s, cy - 30*s + row*30*s, cx - 20*s + col*30*s, cy - 8*s + row*30*s], fill=accent if (row+col)%2 else (255, 223, 113))
        elif kind == "cookie":
            for row in range(2):
                for col in range(2):
                    d.ellipse([cx - 40*s + col*42*s, cy - 28*s + row*38*s, cx - 4*s + col*42*s, cy + 4*s + row*38*s], fill=(190, 134, 76))
                    d.ellipse([cx - 33*s + col*42*s, cy - 21*s + row*38*s, cx - 25*s + col*42*s, cy - 13*s + row*38*s], fill=(84, 55, 38))
        elif kind == "noodle":
            d.arc([cx - 48*s, cy - 24*s, cx + 48*s, cy + 50*s], start=0, end=180, fill=accent, width=max(2,int(5*s)))
            for i in range(3):
                d.arc([cx - 30*s + i*10*s, cy - 38*s, cx + 12*s + i*10*s, cy + 12*s], start=190, end=350, fill=(245, 220, 142), width=max(1,int(3*s)))
        elif kind == "ice":
            for i in range(3):
                d.ellipse([cx - 42*s + i*12*s, cy - 30*s + (i%2)*12*s, cx + 6*s + i*12*s, cy + 18*s + (i%2)*12*s], fill=(255, 220, 168) if i%2 else accent)
        elif kind == "puff":
            d.ellipse([cx - 44*s, cy - 32*s, cx + 44*s, cy + 34*s], fill=(211, 161, 93))
            d.ellipse([cx - 26*s, cy - 19*s, cx + 26*s, cy + 15*s], fill=(250, 233, 196))
        elif kind == "sandwich":
            d.polygon([(cx - 44*s, cy + 12*s), (cx, cy - 42*s), (cx + 44*s, cy + 12*s)], fill=(238, 203, 139))
            d.rectangle([cx - 42*s, cy + 4*s, cx + 42*s, cy + 22*s], fill=(102, 167, 96))
        elif kind == "snack":
            d.rounded_rectangle([cx - 36*s, cy - 36*s, cx + 36*s, cy + 32*s], radius=10*s, fill=accent)
            d.ellipse([cx - 22*s, cy - 20*s, cx + 8*s, cy + 10*s], fill=(253, 228, 164))
            d.ellipse([cx + 2*s, cy - 2*s, cx + 24*s, cy + 20*s], fill=(222, 92, 72))
        else:
            d.ellipse([cx - 38*s, cy - 38*s, cx + 38*s, cy + 38*s], fill=accent)

    for i in range(cols * rows):
        cx0 = (i % cols) * cell
        cy0 = (i // cols) * cell
        bg, secondary, accent = palettes[i % len(palettes)]
        name, en, kind = names[i % len(names)]
        # Background with a subtle vertical gradient.
        d.rectangle([cx0, cy0, cx0 + cell, cy0 + cell], fill=bg)
        for yy in range(0, cell, 3):
            fade = int(18 * (yy / cell))
            d.line([(cx0, cy0 + yy), (cx0 + cell, cy0 + yy)],
                   fill=tuple(max(0, min(255, c - fade)) for c in bg), width=2)
        # Top brand ribbon.
        d.rectangle([cx0 + 8, cy0 + 8, cx0 + cell - 8, cy0 + 34], fill=secondary)
        d.text((cx0 + 18, cy0 + 14), "SUNNY  MART", font=font(F_ARIAL_BOLD, 13), fill=(36, 45, 38))
        
        # White label area and product name.
        d.rounded_rectangle([cx0 + 18, cy0 + 48, cx0 + cell - 18, cy0 + 148],
                            radius=7, fill=(249, 247, 237), outline=(224, 223, 211), width=2)
        fname = font(F_HEI_BOLD if False else F_HEI, 34)
        try:
            fname = ImageFont.truetype(F_HEI, 34)
        except Exception:
            pass
        d.text((cx0 + cell // 2, cy0 + 66), name, font=fname, fill=(34, 41, 36), anchor="ma")
        d.text((cx0 + cell // 2, cy0 + 110), en, font=font(F_DIN_ALT, 15), fill=tuple(max(0, min(255, c - 30)) for c in accent), anchor="ma")
        # Product illustration.
        food_icon(kind, cx0 + cell // 2, cy0 + 176, 0.78, secondary if sum(bg) < 300 else accent)
        # Bottom stripe / weight / barcode.
        for j, c in enumerate((ORANGE, GREEN, RED)):
            d.rectangle([cx0 + 16 + j * 42, cy0 + cell - 32, cx0 + 48 + j * 42, cy0 + cell - 24], fill=c)
        d.text((cx0 + cell - 18, cy0 + cell - 38), "NET 50g", font=font(F_DIN_ALT, 12), fill=(254, 250, 238), anchor="ra")
        bx = cx0 + cell - 76
        for k in range(17):
            if k % 3 == 0:
                d.line([(bx + k * 2, cy0 + cell - 34), (bx + k * 2, cy0 + cell - 14)],
                       fill=(245, 244, 234), width=1)
        # A few tiny dots for texture.
        for _ in range(14):
            px = rng.randint(cx0 + 8, cx0 + cell - 8)
            py = rng.randint(cy0 + 38, cy0 + cell - 12)
            d.point((px, py), fill=(255, 255, 255, 30))
    img = img.filter(ImageFilter.GaussianBlur(0.15))
    img.save(TEX / "product_packaging.png", optimize=True)


def make_shelf_tag_atlas():
    """A compact atlas of Taiwanese-style shelf price tags and promo wobblers."""
    W, H = 1024, 512
    cols, rows = 8, 4
    cw, ch = W // cols, H // rows
    img = Image.new("RGB", (W, H), (245, 243, 234))
    d = ImageDraw.Draw(img)
    tags = [
        ("特价", "9", "元"), ("特价", "6", "元"), ("新品", "12", "元"),
        ("任选", "2件19", ""), ("会员", "8", "元"), ("限时", "10", "元"),
        ("特价", "5", "元"), ("加购", "3", "元"), ("买一送一", "12", "元"),
        ("特价", "15", "元"), ("早餐", "9", "元"), ("冰品", "8", "元"),
        ("咖啡", "12", "元"), ("茶饮", "6", "元"), ("零食", "7", "元"),
        ("特价", "16", "元"), ("任选", "3件20", ""), ("特价", "4", "元"),
        ("大包装", "18", "元"), ("人气", "12", "元"), ("季节限定", "13", "元"),
        ("特价", "3", "元"), ("点心", "8", "元"), ("饮料", "5", "元"),
        ("特价", "10", "元"), ("早餐", "12", "元"), ("点数", "2倍", ""),
        ("新品", "9", "元"), ("特价", "7", "元"), ("任选", "4件25", ""),
        ("特价", "19", "元"), ("限量", "15", "元"),
    ]
    for i, (label, price, unit) in enumerate(tags):
        x0 = (i % cols) * cw
        y0 = (i // cols) * ch
        bg = (222, 49, 49) if i % 3 == 0 else ((250, 232, 145) if i % 3 == 1 else (249, 248, 239))
        fg = (255, 252, 241) if i % 3 == 0 else (41, 48, 40)
        accent = (27, 125, 91) if i % 3 != 0 else (255, 184, 76)
        d.rectangle([x0 + 2, y0 + 2, x0 + cw - 4, y0 + ch - 4], fill=bg, outline=(60, 68, 58), width=2)
        d.rectangle([x0 + 2, y0 + 2, x0 + cw - 4, y0 + 36], fill=accent)
        d.text((x0 + 12, y0 + 10), label, font=font(F_HEI, 21), fill=(255, 255, 247))
        d.text((x0 + cw // 2, y0 + 63), price, font=font(F_DIN, 66), fill=fg, anchor="ma")
        if unit:
            d.text((x0 + cw - 22, y0 + 112), unit, font=font(F_HEI, 20), fill=fg, anchor="ra")
        for j, c in enumerate((ORANGE, GREEN, RED)):
            d.rectangle([x0 + 12 + j * 25, y0 + ch - 20, x0 + 29 + j * 25, y0 + ch - 14], fill=c)
        d.line([(x0 + 8, y0 + ch - 8), (x0 + cw - 8, y0 + ch - 8)], fill=(80, 87, 77), width=1)
    img.save(TEX / "shelf_tags.png", optimize=True)


def make_roof_gravel():
    W = H = 512
    img = Image.new("RGB", (W, H), (103, 105, 98))
    d = ImageDraw.Draw(img)
    rng = random.Random(52)
    for _ in range(20000):
        x, y = rng.randrange(W), rng.randrange(H)
        v = rng.randint(65, 145)
        r = rng.randint(1, 2)
        d.ellipse([x, y, x + r, y + r], fill=(v, v, v - 2))
    img.save(TEX / "roof_gravel.png", optimize=True)


def make_store_ceiling():
    W = H = 512
    img = Image.new("RGB", (W, H), (233, 231, 219))
    d = ImageDraw.Draw(img)
    for x in range(0, W, 64):
        d.line([(x, 0), (x, H)], fill=(215, 214, 203), width=2)
    for y in range(0, H, 64):
        d.line([(0, y), (W, y)], fill=(217, 216, 204), width=2)
    grain(img, 2, 14)
    img.save(TEX / "ceiling_tile.png", optimize=True)


def make_store_floor():
    # 60 x 60 cm cream tiles, with darker grout.
    W = H = 1024
    img = Image.new("RGB", (W, H), (190, 187, 176))
    d = ImageDraw.Draw(img)
    rng = random.Random(23)
    cell = W // 4
    for iy in range(4):
        for ix in range(4):
            v = rng.randint(-4, 4)
            col = (226 + v, 222 + v, 210 + v)
            x0, y0 = ix * cell + 4, iy * cell + 4
            d.rectangle([x0, y0, x0 + cell - 8, y0 + cell - 8], fill=col)
            # soft speckle / subtle veining
            for _ in range(50):
                x, y = rng.randint(x0 + 4, x0 + cell - 12), rng.randint(y0 + 4, y0 + cell - 12)
                d.point((x, y), fill=tuple(max(0, min(255, c + rng.randint(-10, 7))) for c in col))
    img.save(TEX / "store_floor.png", optimize=True)


def main():
    print("Generating textures in", TEX)
    make_fascia()
    make_pylon()
    make_open_neon()
    make_window_decal()
    make_menu()
    make_road_sign()
    make_a_frame()
    make_ice_label()
    make_fridge_header()
    make_aisle_signs()
    make_coffee_poster()
    make_slurpee_poster()
    make_food_poster()
    make_slurpee_label()
    make_condiment_sign()
    make_exit_sign()
    make_atm_sign()
    make_store_plaque()
    make_hotfood_menu()
    make_magazine_sign()
    make_newspaper_box()
    make_sidewalk_stains()
    make_door_stickers()
    make_payment_methods()
    make_bike_parking()
    make_promo_tag()
    make_icecream_label()
    make_facade_panels()
    make_tiles("sidewalk_tiles.png", (158, 158, 150), (117, 120, 114), n=4, dirt=1.0, seed=12)
    make_tiles("store_tiles.png", (226, 222, 210), (186, 184, 174), n=4, dirt=0.25, seed=13)
    make_asphalt()
    make_concrete()
    make_magazines()
    make_product_atlas()
    make_product_packaging()
    make_shelf_tag_atlas()
    make_roof_gravel()
    make_store_ceiling()
    make_store_floor()
    print("Done; files:")
    for p in sorted(TEX.glob("*.png")):
        print(f"  {p.name:28s} {p.stat().st_size/1024:7.1f} KiB")


if __name__ == "__main__":
    main()
