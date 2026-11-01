"""DansLab — AI Business Network: compose the final video from the HeyGen render.

Avatar segments: Dan cut out (masks/) and seated in the DansLab studio plate, desk in front.
Card segments: the real sites (stills/) in a large card over the blurred studio, Dan in a small
circle (his own lip-synced voice throughout, so the lip-sync rule holds either way).
Audio: the HeyGen track, untouched in time; loudness-normalised at the end.
"""

import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import features

W = Path(sys.argv[1])
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else W / 'danslab-network.mp4'
PREVIEW = '--preview' in sys.argv  # every 5th second only, for checking
PREVIEW_EVERY = 5
WW, HH, FPS = 1920, 1080, 25
STUDIO = Path('/home/claude/streamstudio/assets/studio')
FONT = '/usr/share/fonts/opentype/inter/Inter-{}.otf'
cuts = json.load(open(W / 'cuts.json'))
SRC = W / 'heygen.mp4'
N = round(cuts[-1] * FPS)


def font(size, weight='SemiBold'):
    return ImageFont.truetype(FONT.format(weight), size)


def cover(img, w, h):
    s = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


plate = np.asarray(cover(Image.open(STUDIO / 'plate-landscape-final.png').convert('RGB'), WW, HH)).astype(np.float32)
desk_im = cover(Image.open(STUDIO / 'plate-landscape-final.desk.png').convert('RGBA'), WW, HH)
desk = np.asarray(desk_im).astype(np.float32)
desk_a = desk[..., 3:4] / 255.0
seat = json.load(open(STUDIO / 'plate-landscape-final.json'))['seat']
SCALE, HANDS_Y, SX = seat['scale'], seat['hands_y'], seat['x']
HANDS_IN_CLIP = 0.85
blurred = cv2.GaussianBlur(plate, (0, 0), 18) * 0.38 + np.array([6, 6, 12], np.float32) * 0.62

# ------------------------------------------------------------------ segment plan
# kind: 'avatar' (full studio) or 'card' (site card + circle).  zoom: (cx, cy, z_end) on the plate.
PLAN = [
    dict(kind='avatar', title=('DansLab', 'The AI Business Network'), lower=None),
    dict(kind='avatar', lower=('Dan', 'DansLab')),
    dict(kind='card', still='streamstudio.png', tag='StreamStudio · made in our own studio'),
    dict(kind='card', still='fakereal-home.png', tag='fake-real.live', intro_zoom=(0.73, 0.36)),
    dict(kind='card', still='fakereal-real.png', tag='fake-real.live · the Real side'),
    dict(kind='card', still='nervixpay-hero.png', tag='nervixpay.live'),
    dict(kind='card', still='nervixpay-reasons.png', tag='nervixpay.live · 0.2% per payment, at most $2'),
    dict(kind='avatar', lower=('Zmarty', 'AI trading companion')),
    dict(kind='avatar', lower=('KryptoStack Exchange', None), zoom=(0.26, 0.61, 1.30)),
    dict(kind='avatar', lower=('iRise Coin', None), zoom=(0.20, 0.62, 1.42), zoom_from=(0.26, 0.61, 1.30)),
    dict(kind='avatar', chips=['Fake-Real', 'NervixPay', 'Zmarty', 'KryptoStack', 'iRise']),
    dict(kind='card', still='market-home.png', tag='nervix-market.vercel.app'),
    dict(kind='card', still='market-directory.png', tag='Nervix Market · the directory'),
    dict(kind='card', still='nervixpay-checkout.png', tag='10 USD membership · USDT or USDC · NervixPay'),
    dict(kind='card', still='market-listing.png', tag='Your own page in the network'),
    dict(kind='avatar', lower=('Join the AI Business Network', 'nervix-market.vercel.app')),
    dict(kind='avatar', endcard=True),
]
if (W / 'plan.json').exists():  # an episode's own plan (same keys as above, lists for tuples)
    PLAN = json.load(open(W / 'plan.json'))
assert len(PLAN) == len(cuts) - 1, (len(PLAN), len(cuts) - 1)


def seg_at(t):
    for i in range(len(cuts) - 1):
        if t < cuts[i + 1]:
            return i
    return len(cuts) - 2


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# ------------------------------------------------------------------ masks
_mask_cache = {}


def mask_for(f):
    """Person alpha at 1920x1080 (float 0..1). Masks exist for even frames; odd ones are blended."""
    def load(k):
        if k not in _mask_cache:
            p = W / 'masks' / f'{k:05d}.png'
            if not p.exists():
                return None
            m = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            _mask_cache[k] = m
            if len(_mask_cache) > 8:
                _mask_cache.pop(next(iter(_mask_cache)))
        return _mask_cache[k]
    # nearest computed masks before and after (masks were made every 2nd or 4th frame)
    a = next((k for k in range(f, f - 5, -1) if (W / 'masks' / f'{k:05d}.png').exists()), None)
    b = next((k for k in range(f, f + 5) if (W / 'masks' / f'{k:05d}.png').exists()), None)
    if a is None and b is None:
        return None
    ma = load(a) if a is not None else None
    mb = load(b) if b is not None else None
    if ma is None or mb is None or a == b:
        m = (ma if ma is not None else mb).astype(np.float32)
    else:
        w = (f - a) / (b - a)
        m = ma.astype(np.float32) * (1 - w) + mb.astype(np.float32) * w
    m = cv2.resize(m, (WW, HH), interpolation=cv2.INTER_LINEAR)
    m = cv2.GaussianBlur(m, (0, 0), 1.2)
    # tighten the edge a little so no studio fringe shows
    m = np.clip((m / 255.0 - 0.08) / 0.84, 0, 1)
    return m[..., None]


# ------------------------------------------------------------------ layers
def studio(frame, f):
    """Dan seated in the DansLab plate, desk in front."""
    m = mask_for(f)
    out = plate.copy()
    if m is not None:
        ph = round(HH * SCALE)
        pw = round(WW * ph / HH)
        fg = cv2.resize(frame, (pw, ph), interpolation=cv2.INTER_AREA)
        ma = cv2.resize(m, (pw, ph), interpolation=cv2.INTER_AREA)[..., None]
        bottom = (HANDS_Y + (1 - HANDS_IN_CLIP) * SCALE) * HH
        x0, y0 = round(WW * SX - pw / 2), round(bottom - ph)
        xs, ys = max(0, x0), max(0, y0)
        xe, ye = min(WW, x0 + pw), min(HH, y0 + ph)
        sub_fg = fg[ys - y0:ye - y0, xs - x0:xe - x0]
        sub_m = ma[ys - y0:ye - y0, xs - x0:xe - x0]
        out[ys:ye, xs:xe] = out[ys:ye, xs:xe] * (1 - sub_m) + sub_fg * sub_m
    out = out * (1 - desk_a) + desk[..., :3] * desk_a
    return out


def zoom(img, cx, cy, z):
    if z <= 1.001:
        return img
    w, h = WW / z, HH / z
    x0 = min(max(cx * WW - w / 2, 0), WW - w)
    y0 = min(max(cy * HH - h / 2, 0), HH - h)
    M = np.array([[z, 0, -x0 * z], [0, z, -y0 * z]], np.float32)
    return cv2.warpAffine(img, M, (WW, HH), flags=cv2.INTER_LINEAR)


_stills = {}


def card_img(name):
    if name not in _stills:
        im = Image.open(W / 'stills' / name).convert('RGB')
        im = cover(im, 1306, 735) if abs(im.width / im.height - 16 / 9) > 0.01 else im
        _stills[name] = np.asarray(im.resize((1400, 788), Image.LANCZOS)).astype(np.float32)
    return _stills[name]


def zoom_card(img, cx, cy, z):
    if z <= 1.001:
        return img
    h, w = img.shape[:2]
    x0 = min(max(cx * w - w / z / 2, 0), w - w / z)
    y0 = min(max(cy * h - h / z / 2, 0), h - h / z)
    M = np.array([[z, 0, -x0 * z], [0, z, -y0 * z]], np.float32)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR)


def rounded_mask(w, h, r):
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=255)
    return np.asarray(m).astype(np.float32)[..., None] / 255.0


CARD_W, CARD_H, CARD_X, CARD_Y = 1400, 788, 440, 150
card_round = rounded_mask(CARD_W, CARD_H, 22)
shadow = np.zeros((HH, WW), np.float32)
shadow[CARD_Y + 18:CARD_Y + CARD_H + 18, CARD_X:CARD_X + CARD_W] = 1
shadow = cv2.GaussianBlur(shadow, (0, 0), 28)[..., None] * 0.55

CIRCLE = 300
CX0, CY0 = 92, HH - 92 - CIRCLE
circ = np.zeros((CIRCLE, CIRCLE), np.float32)
cv2.circle(circ, (CIRCLE // 2, CIRCLE // 2), CIRCLE // 2 - 2, 1.0, -1, lineType=cv2.LINE_AA)
circ = cv2.GaussianBlur(circ, (0, 0), 2.2)[..., None]  # soft edge, no frame: nothing draws the eye to the lips
ring = np.zeros((CIRCLE + 12, CIRCLE + 12), np.float32)
cv2.circle(ring, ((CIRCLE + 12) // 2, (CIRCLE + 12) // 2), (CIRCLE + 12) // 2 - 2, 1.0, 3, lineType=cv2.LINE_AA)
ring = ring[..., None]
RING_RGB = np.array([45, 226, 196], np.float32)


def neon_frame(x, y, w, h, r=22, width=3, blur=16):
    """A neon rim (teal → violet) with its glow, as additive RGB."""
    m = Image.new('L', (WW, HH), 0)
    ImageDraw.Draw(m).rounded_rectangle((x - 2, y - 2, x + w + 1, y + h + 1), r + 2, outline=255, width=width)
    m = np.asarray(m).astype(np.float32) / 255.0
    grad = np.linspace(0, 1, WW, dtype=np.float32)[None, :, None]
    col = np.array([45, 226, 196], np.float32) * (1 - grad) + np.array([140, 100, 255], np.float32) * grad
    glow = cv2.GaussianBlur(m, (0, 0), blur) * 2.2 + cv2.GaussianBlur(m, (0, 0), 4) * 0.9
    return col * np.clip(glow, 0, 1.4)[..., None], col * m[..., None], m[..., None]


NEON_GLOW, NEON_RGB, NEON_A = neon_frame(CARD_X, CARD_Y, CARD_W, CARD_H)


def path_at(ks, fr):
    """Keyframes [[frac, a, b, c], …] eased at fraction fr → (a, b, c)."""
    k0 = max((k for k in ks if k[0] <= fr), key=lambda k: k[0], default=ks[0])
    k1 = min((k for k in ks if k[0] > fr), key=lambda k: k[0], default=k0)
    u = 0 if k1 is k0 else ease((fr - k0[0]) / (k1[0] - k0[0]))
    return tuple(k0[j] + (k1[j] - k0[j]) * u for j in (1, 2, 3))


def card_layer(frame, still, tl, dur, tag, focus=None):
    out = blurred.copy()
    a = ease(tl / 0.45)
    out = out * (1 - shadow * a)
    img = card_img(still)
    if focus:  # push toward the part Dan names: [[frac, cx, cy, z], …] in fractions of the still
        fx, fy, fz = path_at(focus, tl / max(dur, 1))
        img = zoom_card(img, fx, fy, fz)
        z = 1.0
    else:
        z = 1.0 + 0.045 * min(tl / max(dur, 1), 1.0)
    if z > 1.0:
        h, w = img.shape[:2]
        cw, ch = w / z, h / z
        M = np.array([[z, 0, -(w - cw) / 2 * z], [0, z, -(h - ch) * 0.15 * z]], np.float32)
        img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR)
    s = 0.955 + 0.045 * a
    if s < 0.999:
        sw, sh = round(CARD_W * s), round(CARD_H * s)
        img_s = cv2.resize(img, (sw, sh), interpolation=cv2.INTER_AREA)
        rm = cv2.resize(card_round, (sw, sh))[..., None]
        x0, y0 = CARD_X + (CARD_W - sw) // 2, CARD_Y + (CARD_H - sh) // 2
    else:
        img_s, rm, x0, y0, sw, sh = img, card_round, CARD_X, CARD_Y, CARD_W, CARD_H
    region = out[y0:y0 + sh, x0:x0 + sw]
    out[y0:y0 + sh, x0:x0 + sw] = region * (1 - rm * a) + img_s * rm * a
    # the neon rim: this is where the eye should go
    if s >= 0.999:
        pulse = 0.82 + 0.18 * np.sin(tl * 2.4)
        out = out + NEON_GLOW * (a * pulse)
        out = out * (1 - NEON_A * a) + NEON_RGB * 1.15 * a
    # Dan in the circle: head and shoulders from his own clip
    side = int(0.60 * HH)
    cxf, cyf = WW // 2, int(0.37 * HH)
    crop = frame[cyf - side // 2:cyf + side // 2, cxf - side // 2:cxf + side // 2]
    face = cv2.resize(crop, (CIRCLE, CIRCLE), interpolation=cv2.INTER_AREA)
    reg = out[CY0:CY0 + CIRCLE, CX0:CX0 + CIRCLE]
    out[CY0:CY0 + CIRCLE, CX0:CX0 + CIRCLE] = reg * (1 - circ) + face * circ
    return out, tag, a


# ------------------------------------------------------------------ text overlays (PIL, cached per text)
_txt = {}


def text_rgba(key, draw_fn):
    if key not in _txt:
        im = Image.new('RGBA', (WW, HH), (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(im))
        arr = np.asarray(im).astype(np.float32)
        _txt[key] = (arr[..., :3], arr[..., 3:4] / 255.0)
    return _txt[key]


def overlay(out, key, draw_fn, alpha):
    if alpha <= 0.01:
        return out
    rgb, a = text_rgba(key, draw_fn)
    a = a * alpha
    return out * (1 - a) + rgb * a


def tag_draw(text):
    def fn(d):
        f = font(26, 'SemiBold')
        w = d.textlength(text, font=f) + 44
        d.rounded_rectangle((CARD_X, CARD_Y - 66, CARD_X + w, CARD_Y - 18), 24, fill=(10, 12, 20, 220), outline=(124, 92, 255, 170), width=2)
        d.ellipse((CARD_X + 18, CARD_Y - 47, CARD_X + 28, CARD_Y - 37), fill=(45, 226, 196, 255))
        d.text((CARD_X + 36, CARD_Y - 58), text, font=f, fill=(236, 238, 246, 255))
    return fn


TABLE_BOTTOM = 1004  # where cards stand on the desk (just in front of Dan's hands)
_tc = {}


def table_card(key, lines, w, h, text_w=None):
    """A glass mini card with a neon rim, standing on the table, plus its reflection in the wood.
    lines: [(text, size, weight, rgb)]; text_w centres them in the left text_w px (a feature fills the rest).
    Returns (rgb, alpha) arrays of (h*2) x w incl. reflection."""
    if key in _tc:
        return _tc[key]
    pad = 40
    W2, H2 = w + pad * 2, h + pad * 2
    im = Image.new('RGBA', (W2, H2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((pad, pad, pad + w, pad + h), 18, fill=(8, 10, 18, 205))
    rim = Image.new('L', (W2, H2), 0)
    ImageDraw.Draw(rim).rounded_rectangle((pad, pad, pad + w, pad + h), 18, outline=255, width=3)
    rim_a = np.asarray(rim).astype(np.float32) / 255.0
    total = sum(sz for _, sz, _, _ in lines) + 14 * (len(lines) - 1)
    y = pad + (h - total) / 2 - 4
    for text, sz, wt, rgb in lines:
        f = font(sz, wt)
        tw = d.textlength(text, font=f)
        d.text((pad + ((text_w or w) - tw) / 2, y), text, font=f, fill=rgb + (255,))
        y += sz + 14
    base = np.asarray(im).astype(np.float32)
    grad = np.linspace(0, 1, W2, dtype=np.float32)[None, :, None]
    col = np.array([45, 226, 196], np.float32) * (1 - grad) + np.array([140, 100, 255], np.float32) * grad
    glow = np.clip(cv2.GaussianBlur(rim_a, (0, 0), 10) * 2.4, 0, 1)[..., None]
    rgb = base[..., :3] * (base[..., 3:4] / 255.0)
    a = base[..., 3:4] / 255.0
    # glow under the card, then the rim on top
    rgb = rgb * (1 - glow * (1 - a)) + col * glow * (1 - a)
    a = np.clip(a + glow * 0.85, 0, 1)
    rgb = rgb * (1 - rim_a[..., None]) + col * 1.1 * rim_a[..., None]
    a = np.maximum(a, rim_a[..., None])
    # reflection in the polished wood
    ref_rgb, ref_a = rgb[::-1], a[::-1]
    fade = np.linspace(0.32, 0, H2, dtype=np.float32)[:, None, None]
    out_rgb = np.concatenate([rgb, ref_rgb], 0)
    out_a = np.concatenate([a, ref_a * fade], 0)
    _tc[key] = (out_rgb, out_a, pad)
    return _tc[key]


def place_table_card(out, key, lines, w, h, cx, alpha, rise=0.0, text_w=None):
    """Stand a mini card on the table centred at cx; rise=0..1 animates it up out of the table."""
    if alpha <= 0.01:
        return out
    rgb, a, pad = table_card(key, lines, w, h, text_w)
    H2 = h + pad * 2
    lift = int((1 - rise) * 46)
    x0 = int(cx - (w + pad * 2) / 2)
    y0 = TABLE_BOTTOM - h - pad + lift
    hh, ww = rgb.shape[:2]
    # cards rise out of the table: hide what is still below the surface
    vis = np.ones((hh, 1, 1), np.float32)
    cut = H2 - pad - lift  # rows of the card above the table line
    vis[max(cut, 0):H2] = 0 if lift > 0 else vis[max(cut, 0):H2]
    ys, xs = max(0, y0), max(0, x0)
    ye, xe = min(HH, y0 + hh), min(WW, x0 + ww)
    if ye <= ys or xe <= xs:
        return out
    sa = a[ys - y0:ye - y0, xs - x0:xe - x0] * vis[ys - y0:ye - y0] * alpha
    sr = rgb[ys - y0:ye - y0, xs - x0:xe - x0]
    out[ys:ye, xs:xe] = out[ys:ye, xs:xe] * (1 - sa) + sr * sa
    return out


def table_glow(out, cx, w, alpha):
    """A soft pool of neon light on the wood where cards appear."""
    if alpha <= 0.01:
        return out
    g = np.zeros((HH, WW), np.float32)
    cv2.ellipse(g, (int(cx), TABLE_BOTTOM), (int(w * 0.62), 26), 0, 0, 360, 1.0, -1)
    g = cv2.GaussianBlur(g, (0, 0), 22)[..., None] * 0.5 * alpha
    return out + np.array([60, 200, 190], np.float32) * g


WHITE, TEAL, MUTED = (242, 244, 250), (45, 226, 196), (170, 176, 196)

FEAT_W, FEAT_H, FEAT_TEXT_W = 900, 190, 420  # a question card: text left, its live feature right
_feat = {}


def feature_rgba(kind, u):
    q = round(min(max(u, 0), 1) * 60)  # 60 steps over the feature is smooth at 25 fps
    if (kind, q) not in _feat:
        arr = np.asarray(features.draw(kind, q / 60, FEAT_W - FEAT_TEXT_W - 30, FEAT_H - 40)).astype(np.float32)
        _feat[kind, q] = (arr[..., :3], arr[..., 3:4] / 255.0)
    return _feat[kind, q]


def place_feature(out, kind, u, cx, alpha):
    rgb, a = feature_rgba(kind, u)
    h, w = a.shape[:2]
    x0 = int(cx - FEAT_W / 2) + FEAT_TEXT_W
    y0 = TABLE_BOTTOM - FEAT_H + 20
    a = a * alpha
    out[y0:y0 + h, x0:x0 + w] = out[y0:y0 + h, x0:x0 + w] * (1 - a) + rgb * a
    return out


def fact_draw(items):
    """Fact chips in a row under the site card; one RGBA per chip so each can rise on its own word."""
    f = font(26, 'SemiBold')
    xs, x = [], CARD_X
    for text in items:
        xs.append(x)
        x += f.getlength(text) + 64 + 14
    def chip(k):
        def fn(d):
            x0, text = xs[k], items[k]
            w = f.getlength(text) + 64
            y0 = CARD_Y + CARD_H + 30
            d.rounded_rectangle((x0, y0, x0 + w, y0 + 52), 26, fill=(10, 14, 22, 230), outline=(45, 226, 196, 200), width=2)
            d.line([(x0 + 20, y0 + 27), (x0 + 26, y0 + 34), (x0 + 38, y0 + 19)], fill=(45, 226, 196, 255), width=4, joint='curve')
            d.text((x0 + 48, y0 + 26), text, font=f, fill=(236, 238, 246, 255), anchor='lm')
        return fn
    return chip


# ------------------------------------------------------------------ main loop
def compose(frame, f):
    t = f / FPS
    i = seg_at(t)
    p = PLAN[i]
    t0, t1 = cuts[i], cuts[i + 1]
    tl, dur = t - t0, t1 - t0
    if p['kind'] == 'card':
        iz = p.get('intro_zoom')
        if iz and tl < 1.1:  # into the studio monitor, then the site
            out = zoom(studio(frame, f) if mask_for(f) is not None else plate.copy(), iz[0], iz[1], 1 + 1.6 * ease(tl / 1.1))
            return out
        tc = tl - (1.1 if iz else 0)
        out, tag, a = card_layer(frame, p['still'], tc, dur, p['tag'], p.get('focus'))
        out = overlay(out, 'tag:' + tag, tag_draw(tag), a)
        facts = p.get('facts') or []  # [[frac, text], …]: proof chips rising on the words that name them
        chip = fact_draw([t for _, t in facts])
        for k, (fa, text) in enumerate(facts):
            al = ease((tl - fa * dur) / 0.35) * (1 - ease((tl - (dur - 0.5)) / 0.4))
            out = overlay(out, f'fact:{p["still"]}:{k}', chip(k), al)
        return out
    out = studio(frame, f)
    if p.get('title'):
        al = ease(tl / 0.5) * (1 - ease((tl - 2.6) / 0.6))
        out = table_glow(out, WW / 2, 820, al)
        t1_, t2_ = p['title']
        out = place_table_card(out, 'title:' + t1_, [(t1_, 64, 'Bold', WHITE), (t2_, 30, 'Medium', TEAL)],
                               max(820, int(font(64, 'Bold').getlength(t1_)) + 140), 170, WW / 2, al, ease(tl / 0.6))
    lowers = p.get('lowers') or ([[0, None] + list(p['lower'])] if p.get('lower') else [])
    for fa, fb, name, sub in lowers:  # fa/fb: start/end as fractions of the segment (fb None = default)
        t_in = 0.3 + fa * dur
        t_out = fb * dur - 0.5 if fb is not None else min(dur - 0.6, 7.0 + t_in)
        al = ease((tl - t_in) / 0.4) * (1 - ease((tl - t_out) / 0.5))
        lines = [(name, 44, 'Bold', WHITE)] + ([(sub, 26, 'Medium', TEAL)] if sub else [])
        w = max(460, int(font(44, 'Bold').getlength(name)) + 120)
        cx = WW * 0.47 if not ('zoom' in p or 'zoom_path' in p) else WW * p.get('card_x', 0.30)  # world space: zoom is applied after the table cards
        rise = ease((tl - t_in) / 0.5)
        if p.get('feature'):  # the question card answers itself in miniature while Dan asks
            out = table_glow(out, cx, FEAT_W, al)
            out = place_table_card(out, 'q:' + name, [(name, 44, 'Bold', WHITE), (sub or '', 24, 'Medium', TEAL)],
                                   FEAT_W, FEAT_H, cx, al, rise, FEAT_TEXT_W)
            if rise > 0.98:
                u = (tl - t_in - 0.6) / max(min(t_out - t_in - 1.0, 4.5), 1.5)
                out = place_feature(out, p['feature'], u, cx, al)
            continue
        out = table_glow(out, cx, w, al)
        out = place_table_card(out, 'lower:' + name, lines, w, 150 if sub else 112, cx, al, rise)
    if p.get('chips'):
        names = p['chips']
        al_out = 1 - ease((tl - (dur - 0.8)) / 0.6)
        xs = np.linspace(WW * 0.14, WW * 0.86, len(names))
        times = p.get('chip_at') or [k * 1.3 / max(dur, 1) for k in range(len(names))]
        for k, name in enumerate(names):
            t_in = times[k] * dur
            al = ease((tl - t_in) / 0.35) * al_out
            out = table_glow(out, xs[k], 300, al)
            out = place_table_card(out, 'chip:' + name, [(name, 36, 'Bold', WHITE)], 300, 96, xs[k], al, ease((tl - t_in) / 0.45))
    if p.get('endcard') and tl > dur - 6.5:
        al = ease((tl - (dur - 6.5)) / 0.6)
        out = table_glow(out, WW / 2, 1100, al)
        e = p['endcard'] if isinstance(p['endcard'], list) else ['List your AI business', 'nervix-market.vercel.app',
                                                                 '10 USD membership · USDT or USDC · paid with NervixPay']
        out = place_table_card(out, 'end:' + e[0], [(e[0], 56, 'Bold', WHITE), (e[1], 36, 'SemiBold', TEAL), (e[2], 24, 'Medium', MUTED)],
                               1100, 230, WW / 2, al, ease((tl - (dur - 6.5)) / 0.7))
    if 'zoom_path' in p:  # keyframes [frac, cx, cy, z]; eased between them
        out = zoom(out, *path_at(p['zoom_path'], tl / dur))
    elif 'zoom' in p:
        cx, cy, z = p['zoom']
        if 'zoom_from' in p:
            fx, fy, fz = p['zoom_from']
            k = ease(tl / min(dur, 2.5))
            out = zoom(out, fx + (cx - fx) * k, fy + (cy - fy) * k, fz + (z - fz) * k)
        else:
            out = zoom(out, cx, cy, 1 + (z - 1) * ease(tl / min(dur, 2.2)))
    return out


def main():
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(SRC), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                           stdout=subprocess.PIPE)
    enc_args = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{WW}x{HH}', '-r', str(FPS), '-i', '-']
    if PREVIEW:
        enc_args += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p', str(OUT)]
    else:
        enc_args += ['-i', str(SRC), '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'medium',
                     '-crf', '18', '-pix_fmt', 'yuv420p', '-r', str(FPS),
                     '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
                     '-movflags', '+faststart', '-shortest', str(OUT)]
    enc = subprocess.Popen(enc_args, stdin=subprocess.PIPE)
    size = WW * HH * 3
    f = 0
    while True:
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        if PREVIEW and f % (FPS * PREVIEW_EVERY) != 0:
            f += 1
            continue
        frame = np.frombuffer(buf, np.uint8).reshape(HH, WW, 3).astype(np.float32)
        out = compose(frame, f)
        enc.stdin.write(np.clip(out, 0, 255).astype(np.uint8).tobytes())
        if f % 250 == 0:
            print('frame', f, '/', N, flush=True)
        f += 1
    enc.stdin.close()
    enc.wait()
    dec.wait()
    print('done', OUT, flush=True)


if __name__ == '__main__':
    main()
