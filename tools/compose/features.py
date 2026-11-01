"""The live feature on each question card of an episode: a small animation that answers the question in
miniature while Dan asks it. Drawn with PIL on a transparent canvas; `u` is the feature's progress 0..1.

    pay    a coin goes from the customer's wallet straight into yours; "Verified on-chain" ticks in
    play   Read · Listen · Watch light up, the Legend card flips, and it joins the collection
    trade  a position opens, the price climbs to the target line, it closes, the next one opens
    sell   a listing's fields fill in, then the page goes live

Features show the flow, never amounts the script doesn't state.
"""

import math

from PIL import Image, ImageDraw, ImageFont

FONT = '/usr/share/fonts/opentype/inter/Inter-{}.otf'
WHITE, TEAL, VIOLET, MUTED, DIM = (242, 244, 250), (45, 226, 196), (140, 100, 255), (170, 176, 196), (60, 66, 88)
KINDS = ('pay', 'play', 'trade', 'sell')
_fonts = {}


def font(size, weight='SemiBold'):
    if (size, weight) not in _fonts:
        _fonts[size, weight] = ImageFont.truetype(FONT.format(weight), size)
    return _fonts[size, weight]


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def phase(u, a, b):
    """0..1 progress of u inside the window [a, b]."""
    return ease((u - a) / (b - a))


def mix(c1, c2, k):
    return tuple(round(c1[i] + (c2[i] - c1[i]) * k) for i in range(3))


def rgba(c, a=1.0):
    return c + (round(255 * max(0.0, min(a, 1.0))),)


def tick(d, x, y, s, col):
    d.line([(x, y + s * 0.5), (x + s * 0.38, y + s * 0.88), (x + s, y)], fill=col, width=max(3, round(s / 6)), joint='curve')


def label(d, xy, text, size, col, weight='SemiBold', anchor='la'):
    d.text(xy, text, font=font(size, weight), fill=col, anchor=anchor)


def wallet(d, x, y, w, h, name, glow):
    edge = mix(DIM, TEAL, glow)
    d.rounded_rectangle((x, y, x + w, y + h), 14, fill=rgba(mix((14, 17, 28), (16, 52, 50), glow * 0.8), 0.95), outline=rgba(edge), width=3)
    d.rounded_rectangle((x + w - 26, y + h / 2 - 12, x + w + 4, y + h / 2 + 12), 8, fill=rgba(edge))
    label(d, (x + w / 2, y + h + 8), name, 19, rgba(MUTED), 'Medium', 'ma')


def pay(d, u, w, h):
    ww, wh = 88, 54
    lx, rx, wy = 8, w - ww - 12, 6
    arrive = phase(u, 0.12, 0.55)
    verified = phase(u, 0.6, 0.75)
    wallet(d, lx, wy, ww, wh, 'Customer', 0.0)
    wallet(d, rx, wy, ww, wh, 'You', verified)
    # the route: nothing sits in the middle
    y = wy + wh / 2
    x0, x1 = lx + ww + 14, rx - 14
    for k in range(int((x1 - x0) / 14)):
        xx = x0 + k * 14
        on = (xx - x0) / (x1 - x0) <= arrive
        d.ellipse((xx - 2, y - 2, xx + 2, y + 2), fill=rgba(TEAL if on else DIM))
    if 0.08 < u < 0.62:
        cx = x0 + (x1 - x0) * arrive
        r = 17
        d.ellipse((cx - r - 6, y - r - 6, cx + r + 6, y + r + 6), fill=rgba(TEAL, 0.18))
        d.ellipse((cx - r, y - r, cx + r, y + r), fill=rgba((255, 214, 102)), outline=rgba((255, 238, 170)), width=2)
        label(d, (cx, y + 1), '$', 22, rgba((92, 64, 0)), 'Bold', 'mm')
    if verified > 0:
        bx, by = w / 2, h - 20
        txt = 'Verified on-chain'
        tw = font(22, 'Bold').getlength(txt) + 46
        d.rounded_rectangle((bx - tw / 2, by - 18, bx + tw / 2, by + 18), 18, fill=rgba((10, 40, 38), verified), outline=rgba(TEAL, verified), width=2)
        tick(d, bx - tw / 2 + 14, by - 7, 14, rgba(TEAL, verified))
        label(d, (bx - tw / 2 + 36, by), txt, 22, rgba(WHITE, verified), 'Bold', 'lm')


def play(d, u, w, h):
    steps = ('Read', 'Listen', 'Watch')
    for k, s in enumerate(steps):
        on = phase(u, 0.08 + k * 0.12, 0.16 + k * 0.12)
        y = 14 + k * 40
        d.rounded_rectangle((4, y, 132, y + 32), 16, fill=rgba(mix((14, 17, 28), (16, 52, 50), on)), outline=rgba(mix(DIM, TEAL, on)), width=2)
        if on > 0.5:
            tick(d, 16, y + 10, 12, rgba(TEAL))
        label(d, (38, y + 16), s, 19, rgba(mix(MUTED, WHITE, on)), 'SemiBold', 'lm')
    # the Legend card flips at 0.5
    cw, ch = 96, 134
    cx, cy = w - 72 - cw / 2 - 70, h / 2 - 4
    flip = phase(u, 0.46, 0.62)
    sx = abs(1 - 2 * flip)
    half = max(cw * sx / 2, 1)
    back = flip < 0.5
    fill = (22, 26, 44) if back else (40, 30, 86)
    edge = DIM if back else VIOLET
    d.rounded_rectangle((cx - half, cy - ch / 2, cx + half, cy + ch / 2), 10, fill=rgba(fill), outline=rgba(edge), width=3)
    if back and sx > 0.3:
        label(d, (cx, cy), '?', 44, rgba(MUTED), 'Bold', 'mm')
    elif not back and sx > 0.3:
        star = [(cx + (22 if i % 2 == 0 else 9) * sx * c, cy - 16 + (22 if i % 2 == 0 else 9) * s)
                for i, (c, s) in enumerate(_STAR)]
        d.polygon(star, fill=rgba((255, 214, 102)))
        label(d, (cx, cy + 34), 'LEGEND', 15, rgba(WHITE), 'Bold', 'mm')
    got = phase(u, 0.66, 0.8)
    if got > 0:
        x = w - 66
        label(d, (x, cy - 22), 'Collected', 18, rgba(MUTED, got), 'Medium', 'mm')
        label(d, (x, cy + 8), '1/121', 30, rgba(TEAL, got), 'Bold', 'mm')


# unit directions of a five-pointed star's 10 points (outer, inner, …), starting at the top
_STAR = [(math.cos(math.pi / 2 + k * math.pi / 5), -math.sin(math.pi / 2 + k * math.pi / 5)) for k in range(10)]


def trade(d, u, w, h):
    x0, x1, top, bot = 10, w - 10, 26, h - 36
    target_y = top + 12
    entry_y = bot - 26
    # the price path: wiggles up to the target, then a new position starts
    pts = [(0.0, 0.0), (0.12, 0.18), (0.22, 0.08), (0.36, 0.42), (0.46, 0.33), (0.58, 0.71), (0.66, 0.6), (0.76, 1.0)]
    run = phase(u, 0.05, 0.62)
    xy = [(x0 + (x1 - x0) * px, entry_y + (target_y - entry_y) * py) for px, py in pts]
    shown, last = [], xy[0]
    span = pts[-1][0]
    for (px, _), p in zip(pts, xy):
        if px / span <= run:
            shown.append(p)
            last = p
        else:
            prev = shown[-1]
            prev_px = (prev[0] - x0) / (x1 - x0)
            k = (run * span - prev_px) / (px - prev_px)
            last = (prev[0] + (p[0] - prev[0]) * k, prev[1] + (p[1] - prev[1]) * k)
            shown.append(last)
            break
    # target line
    for k in range(int((x1 - x0) / 16)):
        xx = x0 + k * 16
        d.line([(xx, target_y), (xx + 8, target_y)], fill=rgba(TEAL, 0.7), width=2)
    label(d, (x1, target_y - 6), 'Target', 17, rgba(TEAL), 'SemiBold', 'rb')
    if len(shown) > 1:
        d.line(shown, fill=rgba((255, 214, 102)), width=4, joint='curve')
    d.ellipse((xy[0][0] - 7, xy[0][1] - 7, xy[0][0] + 7, xy[0][1] + 7), fill=rgba(VIOLET))
    label(d, (xy[0][0] + 12, xy[0][1] + 10), 'Open', 17, rgba(MUTED), 'SemiBold', 'lm')
    if 0.03 < u:
        d.ellipse((last[0] - 6, last[1] - 6, last[0] + 6, last[1] + 6), fill=rgba(WHITE))
    closed = phase(u, 0.64, 0.74)
    if closed > 0:
        hx, hy = xy[-1]
        d.ellipse((hx - 11, hy - 11, hx + 11, hy + 11), outline=rgba(TEAL, closed), width=3)
        txt = 'Target hit · closed'
        tw = font(20, 'Bold').getlength(txt) + 44
        bx, by = w / 2, h - 16
        d.rounded_rectangle((bx - tw / 2, by - 17, bx + tw / 2, by + 17), 17, fill=rgba((10, 40, 38), closed), outline=rgba(TEAL, closed), width=2)
        tick(d, bx - tw / 2 + 13, by - 7, 13, rgba(TEAL, closed))
        label(d, (bx - tw / 2 + 34, by), txt, 20, rgba(WHITE, closed), 'Bold', 'lm')
    nxt = phase(u, 0.82, 0.92)
    if nxt > 0:
        d.ellipse((x1 - 30 - 7, entry_y - 7, x1 - 30 + 7, entry_y + 7), fill=rgba(VIOLET, nxt))
        label(d, (x1 - 44, entry_y), 'Next', 17, rgba(MUTED, nxt), 'SemiBold', 'rm')


def sell(d, u, w, h):
    fields = ('What it does', 'Price', 'Contact')
    fill_w = (0.92, 0.42, 0.66)
    fw = w - 150
    for k, name in enumerate(fields):
        y = 2 + k * 36
        p = phase(u, 0.08 + k * 0.14, 0.2 + k * 0.14)
        label(d, (4, y + 15), name, 17, rgba(MUTED), 'Medium', 'lm')
        bx = 124
        d.rounded_rectangle((bx, y + 3, bx + fw - 4, y + 27), 8, fill=rgba((14, 17, 28)), outline=rgba(DIM), width=2)
        if p > 0:
            d.rounded_rectangle((bx + 6, y + 10, bx + 6 + (fw - 18) * fill_w[k] * p, y + 20), 5, fill=rgba(mix(VIOLET, TEAL, p)))
    live = phase(u, 0.58, 0.7)
    if live > 0:
        bx, by = w / 2 + 50, h - 19
        txt = 'Your page is live'
        tw = font(21, 'Bold').getlength(txt) + 46
        d.rounded_rectangle((bx - tw / 2, by - 18, bx + tw / 2, by + 18), 18, fill=rgba((10, 40, 38), live), outline=rgba(TEAL, live), width=2)
        tick(d, bx - tw / 2 + 14, by - 7, 14, rgba(TEAL, live))
        label(d, (bx - tw / 2 + 36, by), txt, 21, rgba(WHITE, live), 'Bold', 'lm')
        # a buyer arrives: a small dot travels into the page
        if u > 0.75:
            k = phase(u, 0.75, 0.92)
            d.ellipse((bx + tw / 2 + 6 + 40 * (1 - k), by - 6, bx + tw / 2 + 18 + 40 * (1 - k), by + 6), fill=rgba(VIOLET, k))


DRAW = {'pay': pay, 'play': play, 'trade': trade, 'sell': sell}


def draw(kind, u, w, h):
    """Feature frame at progress u as a transparent RGBA image of w x h."""
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    DRAW[kind](ImageDraw.Draw(im), min(max(u, 0.0), 1.0), w, h)
    return im
