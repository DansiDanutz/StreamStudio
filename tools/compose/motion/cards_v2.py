"""Episode 1 v2 storyboards: one motion card per group of consecutive card scenes.
Times are seconds from the group's first frame; T(scene, phrase) places a beat on the words
(scene start in the group + the phrase's position in the scene's text × the scene's length)."""
import json
import os
from pathlib import Path

P = Path(__file__).parent / 'pages'
# the episode script (scenes) and the measured scene durations; override with EP_SCRIPT / EP_DURATIONS
SC = json.load(open(os.environ.get('EP_SCRIPT', Path(__file__).parent.parent / 'ep1-v2.json')))['scenes']
DUR = {int(k): v for k, v in json.load(open(os.environ.get('EP_DURATIONS', Path(__file__).parent.parent / 'ep1v2' / 'durations.json'))).items()}
TEXT = {s['scene']: s['voice'] for s in SC}


def group(scenes, lead=0.0):
    """Offsets of each scene inside a card group; lead = seconds of the first scene not in the card."""
    off, t = {}, -lead
    for s in scenes:
        off[s] = t
        t += DUR[s]
    return off, t


def T(off, s, phrase):
    txt = TEXT[s]
    i = txt.find(phrase)
    assert i >= 0, (s, phrase)
    return round(off[s] + DUR[s] * (i / len(txt)) * 0.97 + 0.1, 2)


# ---------------------------------------------------------------- scene 6: Fake-Real tab closes, nervix.space opens
def g06(C):
    off, dur = group([6], lead=0.0)
    c = C('g06', dur, P)
    fr = c.page('fakereal-home.png')
    sp = c.page('space-home.png')
    c.show(fr, 0, slide=False)
    c.url(0, 'fake-real.live')
    c.cam(fr, 0, 0, y=0)
    t_in = c.navigate(sp, 1.05, 'nervix.space')  # Fake-Real stays a beat, then the tab changes
    c.cam(sp, 0, 0, y=0)
    c.cam(sp, t_in + 0.1, 1.0, focus=(100, 150, 520, 280), z=1.3)
    c.ring(sp, t_in + 0.4, T(off, 6, 'Builders') - 0.1, (100, 160, 510, 265))
    c.call(t_in + 0.2, T(off, 6, 'Builders'), 'Nervix Space', 'The home of our AI Business Network')
    tb = T(off, 6, 'Builders')
    c.cam(sp, tb, 1.1, y=772)
    c.ring(sp, tb + 0.9, dur, (103, 1080, 1080, 175))
    c.cursor(sp, [(tb + 0.5, 640, 1000, False), (T(off, 6, 'find it'), 270, 1160, False), (T(off, 6, 'use it'), 640, 1160, False),
                  (T(off, 6, 'buy it'), 1000, 1160, False)])
    c.chips([(tb + 0.1, 'Show it'), (T(off, 6, 'find it'), 'Find it'), (T(off, 6, 'use it'), 'Use it'), (T(off, 6, 'buy it'), 'Buy it')], dur)
    return c


# ---------------------------------------------------------------- scenes 10-13: NervixPay
def g10(C):
    off, dur = group([10, 11, 12, 13])
    c = C('g10', dur, P)
    c.files = ['qr.png']
    k = c.page('pay-compare.png')
    ps = c.page('payscan.png')
    c.show(k, 0, slide=False)
    c.url(0.05, 'nervixpay.live', typed=True)
    c.cam(k, 0, 0, y=0)
    c.ring(k, 0.4, 1.9, (70, 18, 130, 34), pad=6)
    c.call(0.3, 1.95, 'NervixPay', 'Our own payment rail')
    ts = T(off, 10, 'If you have a shop')
    c.cam(k, ts, 1.0, focus=(941, 1406, 274, 294), z=1.45)
    c.ring(k, ts + 0.4, off[11] - 0.1, (941, 1406, 274, 294))
    tq = T(off, 10, 'product QR code') - 0.3
    qr = c.overlay(tq, off[11], '<img src="qr.png" style="width:230px;height:230px;border-radius:14px;display:block">'
                   '<div style="font:700 22px Inter;color:#fff;margin-top:12px;text-align:center">Your product QR</div>',
                   'left:70px;top:130px;padding:18px;background:rgba(9,11,20,.94);border:2px solid #2de2c4;border-radius:20px;'
                   'box-shadow:0 0 40px rgba(45,226,196,.35)')
    c.chips([(T(off, 10, 'the money lands'), 'Paid straight to your wallet'), (T(off, 10, 'Fast and simple'), 'Fast and simple')], off[11])
    # 11: nothing in the middle, nobody freezes it
    c.cam(k, off[11], 0.9, focus=(808, 230, 406, 348), z=1.5)
    c.ring(k, off[11] + 0.3, off[12] - 0.1, (834, 286, 354, 52), pad=4)
    c.chips([(off[11] + 0.2, 'No middleman'), (T(off, 11, 'nobody can freeze'), 'Nobody freezes your money'),
             (T(off, 11, 'or your account'), 'or your account')], off[12])
    # 12: the comparison scorecard
    c.cam(k, off[12], 1.0, focus=(71, 1060, 1144, 650), z=1.0)
    rows = ['Payments by AI agents', 'Easy for non-technical people', 'Fast: straight to your wallet', 'Set up in minutes']
    sc = c.overlay(off[12] + 0.3, off[13], '<h4>How NervixPay compares</h4>' + ''.join(
        f'<div class="row"><span class="tick">✓</span>{r}</div>' for r in rows), 'right:60px;top:120px;width:560px', cls='ov score')
    c.reveal_rows(sc, [T(off, 12, 'payments made by AI agents'), T(off, 12, 'just as easy'), T(off, 12, "It's fast"),
                       T(off, 12, 'set it up in minutes')])
    # 13: agents with keys you approve, then PayScan
    c.cam(k, off[13], 1.0, focus=(651, 2090, 274, 262), z=1.4)
    tp = T(off, 13, 'And anyone')
    c.ring(k, off[13] + 0.4, tp, (651, 2090, 274, 262))
    c.call(off[13] + 0.2, tp, 'Your agents use it too', 'with keys you approve')
    t_in = c.navigate(ps, tp - 0.2, 'nervixpay.live/payscan')
    c.cam(ps, 0, 0, y=0)
    c.cam(ps, t_in, 1.0, focus=(35, 150, 620, 220), z=1.25)
    c.ring(ps, t_in + 0.3, dur, (35, 160, 470, 140))
    c.call(t_in + 0.1, dur, 'PayScan', 'our public page of settled payments')
    return c


# ---------------------------------------------------------------- scenes 15-18: WorldCup26 + the channel
def g15(C):
    off, dur = group([15, 16, 17, 18])
    c = C('g15', dur, P)
    a = c.page('wc-a.png', dx=32)
    b = c.page('wc-b.png', dx=32)
    cc = c.page('wc-c.png', dx=32)
    d = c.page('wc-d.png', dx=32)
    ch = c.page('worldcup-channel.png')
    c.show(a, 0, slide=False)
    c.url(0.05, 'worldcup26.world', typed=True)
    c.cam(a, 0, 0, y=0)
    c.ring(a, 0.4, 3.2, (28, 45, 280, 40), pad=6)
    c.call(0.4, 3.4, 'WorldCup26.world', 'A free collecting game we built for the World Cup')
    c.cam(a, 3.4, 1.0, focus=(200, 380, 520, 380), z=1.35)
    t121 = T(off, 15, 'a hundred and twenty-one')
    c.ring(a, 3.8, T(off, 15, 'Every card') - 0.1, (209, 695, 505, 58), pad=6)
    c.chips([(T(off, 15, 'a free collecting game'), 'Free to play'), (t121, '121 Legend cards')], T(off, 15, 'Every card'))
    te = T(off, 15, 'Every card')
    c.cam(a, te - 0.3, 0.9, focus=(766, 290, 236, 398), z=1.6)
    c.ring(a, te, off[16], (766, 290, 236, 398))
    c.call(te, off[16], 'Every card has its own story', 'The Vanished Hero · USA 1-0 England · 1950')
    # 16: read / listen / watch / collect, the daily quest
    c.cam(a, off[16], 0.9, focus=(1016, 291, 230, 403), z=1.55)
    beats = [T(off, 16, 'You read'), T(off, 16, 'you listen'), T(off, 16, 'you watch'), T(off, 16, 'the card is yours')]
    for i, t in enumerate(beats):
        c.ring(a, t, t + 1.0, (1016, 291 + 101 * i, 230, 92), pad=5, spot=False)
    c.chips(list(zip(beats, ['Read', 'Listen', 'Watch', 'Collect'])), T(off, 16, 'A daily quest') - 0.2)
    tqd = T(off, 16, 'A daily quest')
    c.show(b, tqd - 0.4)
    c.cam(b, tqd - 0.4, 0, y=0)
    c.ring(b, tqd, T(off, 16, 'Free to play'), (55, 195, 620, 80))
    c.call(tqd - 0.2, T(off, 16, 'Free to play'), 'A daily quest', 'brings you back')
    tf = T(off, 16, 'Free to play')
    c.cursor(b, [(tqd, 700, 600, False), (tf + 0.3, 1330, 470, False), (tf + 0.6, 1330, 470, True)])
    c.call(tf, off[17], 'Free to play', 'just for fun')
    # 17: game ⇄ channel, card → episode → card
    c.show(cc, off[17])
    c.cam(cc, off[17], 0, y=0)
    c.cam(cc, off[17] + 0.3, 1.0, focus=(970, 425, 435, 337), z=1.4)
    tcard = T(off, 17, 'Every card leads')
    c.ring(cc, off[17] + 0.6, tcard - 0.3, (1191, 553, 199, 59), pad=6)
    c.call(off[17] + 0.2, tcard - 0.3, 'The game and the channel', 'feed each other')
    c.show(d, tcard - 0.3)
    c.cam(d, tcard - 0.3, 0, focus=(325, 228, 258, 500), z=1.15)
    c.ring(d, tcard, tcard + 2.0, (336, 598, 240, 105))
    tw = T(off, 17, 'every episode leads back')
    c.cam(d, tw - 0.2, 1.0, focus=(325, 780, 258, 300), z=1.4)
    c.ring(d, tw, T(off, 17, "That's how"), (340, 906, 228, 41), pad=6)
    c.cursor(d, [(tcard, 700, 500, False), (tw + 0.4, 450, 925, False), (tw + 0.8, 450, 925, True)])
    c.chips([(tcard, 'Every card → an episode'), (tw, 'Every episode → a card')], T(off, 17, "That's how"))
    th = T(off, 17, "That's how")
    c.cam(d, th, 1.2, focus=(0, 300, 1392, 900), z=1.0)
    c.call(th, off[18], "That's how a game", 'becomes a community')
    # 18: the channel went viral — 13.5K
    t_in = c.navigate(ch, off[18] + 0.05, 'youtube.com/@DansLab-WorldCup')
    c.cam(ch, 0, 0, y=0)
    c.cam(ch, t_in, 1.0, focus=(170, 150, 560, 200), z=1.3)
    c.ring(ch, t_in + 0.3, dur, (330, 212, 132, 26), pad=6)
    c.chips([(T(off, 18, 'went viral'), 'Went viral')], dur)
    tn = T(off, 18, 'In one month') - 0.2
    n = c.overlay(tn, dur, '<div class="num">0</div><div class="numsub">subscribers in one month</div>',
                  'right:70px;top:150px;padding:26px 34px;background:rgba(9,11,20,.94);border:2px solid #2de2c4;border-radius:22px;'
                  'text-align:right;box-shadow:0 0 50px rgba(45,226,196,.3)')
    c.counter(n, tn + 0.2, max(1.2, T(off, 18, 'fourteen thousand') + 0.6 - tn), 13500,
              lambda v: f'{v / 1000:.1f}K' if v >= 1000 else f'{int(v)}')
    return c


# ---------------------------------------------------------------- scenes 21-24: JEV (control + AI stats only)
def g21(C):
    off, dur = group([21, 22, 23, 24])
    c = C('g21', dur, P)
    k = c.page('jev-control.png')
    ai = c.page('jev-ai.png')
    c.show(k, 0, slide=False)
    c.url(0.05, 'danslab-jev.vercel.app', typed=True)
    c.cam(k, 0, 0, y=0)
    c.ring(k, 0.4, 3.4, (53, 22, 180, 32), pad=6)
    c.call(0.3, 3.5, 'JEV', 'our live trading bot on KuCoin futures')
    tr = T(off, 21, 'It runs on its own')
    c.show(ai, tr - 0.2)
    c.cam(ai, tr - 0.2, 0, y=0)
    c.ring(ai, tr, off[22], (848, 5, 385, 85), pad=4)
    c.ring(ai, T(off, 21, 'an AI model'), off[22], (320, 150, 120, 575), pad=4, spot=False)
    c.call(tr, off[22], 'An AI model is its brain', 'runs on its own from our Mac Studio')
    c.show(k, off[22])
    c.cam(k, off[22], 0, focus=(737, 270, 475, 560), z=1.2)
    beats = [T(off, 22, 'It opens'), T(off, 22, 'closes it'), T(off, 22, 'moves on')]
    for i, t in enumerate(beats):
        c.ring(k, t, t + 1.2, (737, 361 + 79 * i, 475, 70), pad=4, spot=False)
    c.cursor(k, [(off[22], 900, 760, False), (beats[0] + 0.3, 1160, 396, False), (beats[1] + 0.3, 1160, 474, False),
                 (beats[2] + 0.3, 1160, 552, False), (off[23] + 0.6, 560, 490, False), (off[24] + 0.8, 380, 705, False)])
    c.chips([(beats[0], 'Open'), (beats[1], 'Close on a clear target'), (beats[2], 'Move on')], off[23])
    c.cam(k, off[23], 1.0, focus=(53, 420, 645, 380), z=1.3)
    c.ring(k, off[23] + 0.3, T(off, 23, 'a cap on'), (53, 444, 645, 90))
    c.ring(k, T(off, 23, 'a cap on'), off[24], (80, 742, 590, 36), pad=6)
    c.chips([(T(off, 23, 'a fixed trade size'), 'Fixed trade size'), (T(off, 23, 'a cap on'), 'Cap on open positions'),
             (T(off, 23, 'a stop for'), 'Session stop')], off[24])
    c.cam(k, off[24], 0.9, focus=(74, 676, 603, 55), z=1.6)
    c.ring(k, off[24] + 0.3, dur, (74, 676, 603, 55), pad=6)
    c.call(off[24] + 0.1, dur, 'Start or stop it from anywhere', 'right here, on the dashboard')
    return c


# ---------------------------------------------------------------- scenes 27-29: join free, 10 USD a month, the directory
def g27(C):
    off, dur = group([27, 28, 29])
    c = C('g27', dur, P)
    f = c.page('space-list.png')
    home = c.page('space-home.png')
    li = c.page('space-listing-nervixpay.png')
    c.show(f, 0, slide=False)
    c.url(0.05, 'nervix.space/list', typed=True)
    c.cam(f, 0, 0, focus=(283, 100, 720, 460), z=1.15)
    c.typed(f, 0.6, (283, 294, 720, 43), 'Your AI project')
    c.typed(f, 1.4, (283, 405, 720, 43), 'What it does, in one line')
    c.call(0.4, T(off, 27, "here's the deal") - 0.2, 'Bring your project', 'what it does · the price · how to reach you')
    c.cam(f, 2.6, 1.0, focus=(283, 640, 720, 330), z=1.2)
    c.typed(f, T(off, 27, 'the price'), (651, 798, 352, 43), '$19/month')
    c.typed(f, T(off, 27, 'how to reach you'), (283, 909, 352, 43), '@yourhandle')
    td = T(off, 27, "here's the deal")
    c.cam(f, td - 0.4, 1.0, focus=(283, 1079, 720, 85), z=1.25)
    c.ring(f, td, off[28], (283, 1079, 720, 85))
    c.call(T(off, 27, 'the first two hundred'), off[28], 'The first 200 projects', 'are listed for free', top=True)
    c.cursor(f, [(td, 520, 960, False), (off[28] - 0.9, 918, 1121, False), (off[28] - 0.5, 918, 1121, True)])
    # 28: then 10 USD a month; every project its own page
    t_in = c.navigate(home, off[28] + 0.05, 'nervix.space')
    c.cam(home, 0, 0, y=600)
    c.ring(home, t_in, T(off, 28, 'Every project') + 0.6, (467, 690, 351, 162))
    c.call(t_in - 0.2, T(off, 28, 'Every project') + 0.6, 'Then 10 USD a month', 'USDT or USDC · through NervixPay')
    t_li = c.navigate(li, T(off, 28, 'Every project') + 0.6, 'nervix.space/l/nervixpay')
    c.cam(li, 0, 0, y=0)
    c.ring(li, t_li, T(off, 28, 'No middleman'), (290, 150, 430, 80))
    c.chips([(t_li, 'Its own page'), (T(off, 28, 'search by category'), 'Search by category'),
             (T(off, 28, 'come straight'), 'Buyers come straight to you')], T(off, 28, 'No middleman'))
    c.call(T(off, 28, 'No middleman'), off[29], 'No middleman', 'between you and your buyers')
    # 29: the directory
    t_dir = c.navigate(home, off[29] + 0.05, 'nervix.space/#explore')
    c.cam(home, off[29], 0, y=772)
    c.ring(home, t_dir, T(off, 29, 'Fake-Real'), (103, 1080, 1080, 390))
    c.call(t_dir - 0.1, T(off, 29, 'Fake-Real'), 'Already in the space', 'our founding projects')
    cards = [((103, 1080, 350, 175), T(off, 29, 'Fake-Real'), T(off, 29, 'NervixPay.'), 'Fake-Real', 'the link fact-checker'),
             ((468, 1080, 350, 175), T(off, 29, 'NervixPay.'), T(off, 29, 'Smarty'), 'NervixPay', 'the payment rail'),
             ((832, 1080, 350, 175), T(off, 29, 'Smarty'), T(off, 29, 'And StreamStudio'), 'Zmarty', 'our AI trading companion'),
             ((103, 1270, 350, 196), T(off, 29, 'And StreamStudio'), dur, 'StreamStudio', 'the studio this video was made in')]
    for rect, t, end, name, sub in cards:
        c.cam(home, t - 0.3, 0.7, focus=rect, z=1.5)
        c.ring(home, t, end, rect)
        c.call(t, end, name, sub, top=rect[1] > 1200)
    c.cursor(home, [(t_dir, 700, 1300, False)] + [(t + 0.2, r[0] + 170, r[1] + 95, False) for r, t, *_ in cards])
    return c


CARDS = {f.__name__: f for f in (g06, g10, g15, g21, g27)}
