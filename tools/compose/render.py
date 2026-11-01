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

W = Path(sys.argv[1])
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else W / 'danslab-network.mp4'
PREVIEW = '--preview' in sys.argv  # every 5th second only, for checking
WW, HH, FPS = 1920, 1080, 25
STUDIO = Path('/home/claude/streamstudio/assets/studio')
FONT = '/usr/share/fonts/opentype/inter/Inter-{}.otf'
cuts = json.load(open(W / 'cuts.json'))
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
    dict(kind='avatar', lower=('KryptoStack Exchange', None), zoom=(0.19, 0.30, 1.55)),
    dict(kind='avatar', lower=('iRise Coin', None), zoom=(0.12, 0.46, 1.75), zoom_from=(0.19, 0.30, 1.55)),
    dict(kind='avatar', chips=['Fake-Real', 'NervixPay', 'Zmarty', 'KryptoStack', 'iRise']),
    dict(kind='card', still='market-home.png', tag='nervix-market.vercel.app'),
    dict(kind='card', still='market-directory.png', tag='Nervix Market · the directory'),
    dict(kind='card', still='nervixpay-checkout.png', tag='10 USD membership · USDT or USDC · NervixPay'),
    dict(kind='card', still='market-listing.png', tag='Your own page in the network'),
    dict(kind='avatar', lower=('Join the AI Business Network', 'nervix-market.vercel.app')),
    dict(kind='avatar', endcard=True),
]
assert len(PLAN) == len(cuts) - 1


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
circ = cv2.GaussianBlur(circ, (0, 0), 0.8)[..., None]
ring = np.zeros((CIRCLE + 12, CIRCLE + 12), np.float32)
cv2.circle(ring, ((CIRCLE + 12) // 2, (CIRCLE + 12) // 2), (CIRCLE + 12) // 2 - 2, 1.0, 3, lineType=cv2.LINE_AA)
ring = ring[..., None]
RING_RGB = np.array([45, 226, 196], np.float32)


def card_layer(frame, still, tl, dur, tag):
    out = blurred.copy()
    a = ease(tl / 0.45)
    out = out * (1 - shadow * a)
    img = card_img(still)
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
    # Dan in the circle: head and shoulders from his own clip
    side = int(0.60 * HH)
    cxf, cyf = WW // 2, int(0.37 * HH)
    crop = frame[cyf - side // 2:cyf + side // 2, cxf - side // 2:cxf + side // 2]
    face = cv2.resize(crop, (CIRCLE, CIRCLE), interpolation=cv2.INTER_AREA)
    rr = out[CY0 - 6:CY0 + CIRCLE + 6, CX0 - 6:CX0 + CIRCLE + 6]
    out[CY0 - 6:CY0 + CIRCLE + 6, CX0 - 6:CX0 + CIRCLE + 6] = rr * (1 - ring) + RING_RGB * ring
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


def pill(d, x, y, text, size=30, sub=None):
    f1 = font(size, 'Bold')
    f2 = font(int(size * 0.72), 'Medium')
    w1 = d.textlength(text, font=f1)
    w2 = d.textlength(sub, font=f2) if sub else 0
    w = max(w1, w2) + 56
    h = size + 34 + (int(size * 0.72) + 10 if sub else 0)
    d.rounded_rectangle((x, y, x + w, y + h), 16, fill=(10, 12, 20, 210), outline=(45, 226, 196, 160), width=2)
    d.rectangle((x, y + 14, x + 5, y + h - 14), fill=(45, 226, 196, 255))
    d.text((x + 28, y + 15), text, font=f1, fill=(240, 242, 248, 255))
    if sub:
        d.text((x + 28, y + 19 + size), sub, font=f2, fill=(160, 166, 186, 255))


def tag_draw(text):
    def fn(d):
        f = font(26, 'SemiBold')
        w = d.textlength(text, font=f) + 44
        d.rounded_rectangle((CARD_X, CARD_Y - 66, CARD_X + w, CARD_Y - 18), 24, fill=(10, 12, 20, 220), outline=(124, 92, 255, 170), width=2)
        d.ellipse((CARD_X + 18, CARD_Y - 47, CARD_X + 28, CARD_Y - 37), fill=(45, 226, 196, 255))
        d.text((CARD_X + 36, CARD_Y - 58), text, font=f, fill=(236, 238, 246, 255))
    return fn


def title_draw(d):
    f1, f2 = font(132, 'Bold'), font(46, 'Medium')
    t1, t2 = 'DansLab', 'The AI Business Network'
    w1, w2 = d.textlength(t1, font=f1), d.textlength(t2, font=f2)
    d.rounded_rectangle((WW / 2 - 560, 300, WW / 2 + 560, 620), 36, fill=(6, 8, 14, 170))
    d.text((WW / 2 - w1 / 2, 330), t1, font=f1, fill=(244, 246, 252, 255))
    d.text((WW / 2 - w2 / 2, 500), t2, font=f2, fill=(45, 226, 196, 255))


def chips_draw(n):
    names = PLAN[10]['chips']

    def fn(d):
        f = font(40, 'Bold')
        y = 230
        for k, name in enumerate(names[:n]):
            w = d.textlength(name, font=f) + 60
            d.rounded_rectangle((90, y, 90 + w, y + 74), 37, fill=(10, 12, 20, 215), outline=(45, 226, 196, 190), width=2)
            d.text((120, y + 13), name, font=f, fill=(240, 242, 248, 255))
            y += 92
    return fn


def end_draw(d):
    f1, f2, f3 = font(76, 'Bold'), font(40, 'SemiBold'), font(30, 'Medium')
    d.rounded_rectangle((WW / 2 - 640, 120, WW / 2 + 640, 430), 34, fill=(6, 8, 14, 200), outline=(124, 92, 255, 180), width=3)
    for txt, f, y, col in (('List your AI business', f1, 150, (244, 246, 252, 255)),
                           ('nervix-market.vercel.app', f2, 260, (45, 226, 196, 255)),
                           ('10 USD membership · USDT or USDC · paid with NervixPay', f3, 340, (176, 182, 202, 255))):
        w = d.textlength(txt, font=f)
        d.text((WW / 2 - w / 2, y), txt, font=f, fill=col)


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
        out, tag, a = card_layer(frame, p['still'], tl - (1.1 if iz else 0), dur, p['tag'])
        out = overlay(out, 'tag:' + tag, tag_draw(tag), a)
        return out
    out = studio(frame, f)
    if 'zoom' in p:
        cx, cy, z = p['zoom']
        if 'zoom_from' in p:
            fx, fy, fz = p['zoom_from']
            k = ease(tl / min(dur, 2.5))
            out = zoom(out, fx + (cx - fx) * k, fy + (cy - fy) * k, fz + (z - fz) * k)
        else:
            out = zoom(out, cx, cy, 1 + (z - 1) * ease(tl / min(dur, 2.2)))
    if p.get('title'):
        a = 1 - ease((tl - 2.4) / 0.6)
        out = overlay(out, 'title', title_draw, ease(tl / 0.4) * a)
    if p.get('lower'):
        name, sub = p['lower']
        a = ease((tl - 0.3) / 0.4) * (1 - ease((tl - min(dur - 0.6, 6.5)) / 0.5))
        out = overlay(out, 'lower:' + name, lambda d: pill(d, 90, HH - 240, name, 40, sub), a)
    if p.get('chips'):
        # the five names land as Dan says them (about one per 1.3 s from the start)
        n = min(5, int(tl / 1.3) + 1)
        a = 1 - ease((tl - (dur - 0.8)) / 0.6)
        out = overlay(out, f'chips:{n}', chips_draw(n), a)
    if p.get('endcard') and tl > dur - 6.5:
        out = overlay(out, 'end', end_draw, ease((tl - (dur - 6.5)) / 0.6))
    return out


def main():
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(W / 'heygen.mp4'), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                           stdout=subprocess.PIPE)
    enc_args = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{WW}x{HH}', '-r', str(FPS), '-i', '-']
    if PREVIEW:
        enc_args += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p', str(OUT)]
    else:
        enc_args += ['-i', str(W / 'heygen.mp4'), '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'medium',
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
        if PREVIEW and f % (FPS * 5) != 0:
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
