"""Episode 1 storyboards: one function per site card. Times are seconds from the card's first frame,
taken from HeyGen's captions so every highlight lands on Dan's words. Coordinates are page pixels
in the stitched captures (pages/)."""
from pathlib import Path

P = Path(__file__).parent / 'pages'


def seg04(C):  # Nervix Market home — 9.71 s
    c = C('seg04', 9.71, P)
    k = c.page('market-home.png')
    c.show(k, 0, slide=False)
    c.url(0.05, 'nervix-market.vercel.app', typed=True)
    c.cam(k, 0, 0, y=0)
    c.cam(k, 1.9, 1.0, focus=(100, 150, 460, 270), z=1.35)
    c.ring(k, 2.3, 5.3, (100, 165, 450, 255))
    c.call(2.0, 5.4, 'Nervix Market', 'The home of our AI Business Network')
    c.cam(k, 5.3, 1.1, y=820)
    c.ring(k, 6.5, 9.71, (103, 985, 1080, 175))
    c.cursor(k, [(5.9, 640, 905, False), (6.8, 270, 1060, False), (7.6, 640, 1060, False), (8.4, 1000, 1060, False)])
    c.chips([(5.6, 'Show it'), (6.8, 'Find it'), (7.6, 'Use it'), (8.4, 'Buy it')], 9.71)
    return c


def seg07(C):  # NervixPay /compare — 16.15 s
    c = C('seg07', 16.15, P)
    k = c.page('pay-compare.png')
    c.show(k, 0, slide=False)
    c.url(0.05, 'nervixpay.live/compare', typed=True)
    c.cam(k, 0, 0, y=0)
    c.ring(k, 0.4, 2.3, (70, 18, 130, 34), pad=6)
    c.call(0.3, 2.35, 'NervixPay', 'Our own payment rail')
    c.cam(k, 2.4, 1.0, focus=(70, 185, 530, 255), z=1.4)
    c.ring(k, 2.8, 6.3, (70, 185, 530, 255))
    c.call(2.6, 6.35, 'Their wallet → your wallet', 'Customers pay you directly')
    c.cam(k, 6.4, 1.0, focus=(808, 230, 406, 348), z=1.5)
    c.ring(k, 6.8, 8.7, (834, 286, 354, 52), pad=4)
    m = c.cursor(k, [(6.7, 900, 420, False), (7.4, 1130, 318, False)])
    c.cursor_hide(m, 8.6)
    c.call(6.6, 8.75, 'Nothing sits in the middle', 'Who holds your money? You do.')
    c.cam(k, 8.8, 1.2, focus=(71, 1060, 1144, 650), z=1.0)
    c.ring(k, 9.4, 12.7, (71, 1072, 564, 318))
    c.ring(k, 10.6, 12.7, (361, 1406, 274, 294), spot=False)
    c.call(9.0, 12.7, 'Verified on-chain', 'NervixPay never touches the funds')
    c.cam(k, 12.7, 0.9, focus=(95, 1150, 470, 140), z=1.55)
    c.ring(k, 13.0, 16.15, (80, 1210, 480, 70), pad=6)
    c.chips([(12.9, 'No balance to withdraw'), (13.9, '$0 payout fee'), (14.9, 'Nothing to freeze')], 16.15)
    return c


def seg08(C):  # checkout → fee → agents → links → PayScan — 27.81 s
    c = C('seg08', 27.81, P)
    ck = c.page('pay-checkout.png')
    cp = c.page('pay-compare.png')
    ps = c.page('payscan.png')
    c.show(ck, 0, slide=False)
    c.url(0.05, 'nervixpay.live/pay', typed=True)
    c.cam(ck, 0, 0, focus=(73, 127, 1160, 240), z=1.0)
    c.cam(ck, 0.8, 1.2, focus=(740, 150, 480, 200), z=1.45)
    c.ring(ck, 1.0, 2.6, (760, 190, 442, 69), pad=5, spot=False)
    c.ring(ck, 2.6, 4.4, (760, 269, 442, 68), pad=5, spot=False)
    c.cursor(ck, [(0.6, 560, 470, False), (1.5, 1000, 230, False), (2.9, 1000, 306, False)])
    c.chips([(0.4, 'USDT'), (0.9, 'USDC'), (1.8, 'Polygon'), (2.6, 'Ethereum'), (3.4, 'BNB Chain')], 4.5)

    c.show(cp, 4.5)
    c.url(4.5, 'nervixpay.live/compare')
    c.cam(cp, 4.5, 0, focus=(808, 230, 406, 348), z=1.5)
    c.ring(cp, 4.9, 8.5, (834, 457, 354, 47), pad=4)
    c.call(4.8, 8.5, '0.2% per payment', 'capped at $2')
    c.cam(cp, 8.55, 1.2, focus=(71, 2060, 1144, 330), z=1.05)
    c.ring(cp, 9.3, 12.4, (651, 2090, 274, 262))
    c.call(8.8, 12.45, 'Your AI agents can use it too', 'with keys you approve')
    c.cam(cp, 12.5, 1.0, focus=(941, 1406, 274, 294), z=1.6)
    c.ring(cp, 12.9, 18.5, (941, 1406, 274, 294))
    c.chips([(13.2, 'Payment link'), (14.6, 'QR code'), (16.0, 'Pay button')], 18.55)
    c.cam(cp, 18.6, 1.0, focus=(361, 1406, 274, 294), z=1.6)
    c.ring(cp, 18.9, 21.5, (361, 1406, 274, 294))
    c.cursor(cp, [(18.9, 700, 1500, False), (20.6, 452, 1662, False), (21.1, 452, 1662, True)])
    c.call(18.7, 21.6, 'A signed message tells your system', 'and anyone can check the payment')

    c.show(ps, 21.6)
    c.url(21.6, 'nervixpay.live/payscan')
    c.cam(ps, 21.6, 0, y=0)
    c.cam(ps, 22.0, 1.2, focus=(35, 150, 620, 220), z=1.25)
    c.ring(ps, 22.4, 25.0, (35, 160, 470, 140))
    c.cam(ps, 25.0, 1.0, y=0)
    c.ring(ps, 25.4, 27.81, (838, 148, 410, 210))
    c.call(22.0, 27.81, 'PayScan', 'our public page of settled payments')
    return c


def seg10(C):  # WorldCup26.world — 30.27 s
    c = C('seg10', 30.27, P)
    a = c.page('wc-a.png', dx=32)
    b = c.page('wc-b.png', dx=32)
    cc = c.page('wc-c.png', dx=32)
    d = c.page('wc-d.png', dx=32)
    c.show(a, 0, slide=False)
    c.url(0.05, 'worldcup26.world', typed=True)
    c.cam(a, 0, 0, y=0)
    c.ring(a, 0.5, 3.4, (28, 45, 280, 40), pad=6)
    c.call(0.4, 3.6, 'WorldCup26.world', 'A free collecting game we built for the World Cup')
    c.cam(a, 3.6, 1.0, focus=(200, 380, 520, 380), z=1.35)
    c.ring(a, 3.9, 7.5, (209, 695, 505, 58), pad=6)
    c.chips([(3.9, '121 Legend cards'), (5.2, 'Free to collect')], 7.6)
    c.cam(a, 7.7, 1.0, focus=(766, 290, 236, 398), z=1.6)
    c.ring(a, 8.0, 10.1, (766, 290, 236, 398))
    c.call(7.9, 10.15, 'Every card has its own story', 'The Vanished Hero · USA 1-0 England · 1950')
    c.cam(a, 10.2, 0.9, focus=(1016, 291, 230, 403), z=1.55)
    for i, t in enumerate((10.4, 11.4, 12.4, 13.4)):
        c.ring(a, t, t + 1.05, (1016, 291 + 101 * i, 230, 92), pad=5, spot=False)
    c.chips([(10.4, 'Read'), (11.1, 'Listen'), (11.9, 'Watch'), (12.9, 'Collect')], 14.45)

    c.show(b, 14.5)
    c.cam(b, 14.5, 0, y=0)
    c.ring(b, 14.8, 17.0, (55, 195, 620, 80))
    c.ring(b, 15.4, 17.0, (1276, 200, 114, 58), pad=6, spot=False)
    c.call(14.7, 17.1, 'A daily quest', 'brings you back')
    c.cursor(b, [(15.2, 700, 600, False), (17.6, 1330, 470, False), (18.0, 1330, 470, True)])
    c.ring(b, 17.6, 19.4, (1287, 458, 92, 28), pad=6)
    c.call(17.2, 19.45, 'Free to play', 'just for fun')

    c.show(cc, 19.5)
    c.cam(cc, 19.5, 0, y=0)
    c.cam(cc, 19.9, 1.0, focus=(970, 425, 435, 337), z=1.4)
    c.ring(cc, 20.2, 23.7, (1191, 553, 199, 59), pad=6)
    c.call(19.7, 23.75, 'The game and the channel', 'feed each other')

    c.show(d, 23.8)
    c.cam(d, 23.8, 0, focus=(325, 228, 258, 500), z=1.15)
    c.ring(d, 24.0, 26.0, (336, 598, 240, 105))
    c.cam(d, 25.9, 1.0, focus=(325, 780, 258, 300), z=1.4)
    c.ring(d, 26.1, 27.9, (340, 906, 228, 41), pad=6)
    c.cursor(d, [(24.2, 700, 500, False), (26.4, 450, 925, False), (26.8, 450, 925, True)])
    c.chips([(24.0, 'Every card → an episode'), (26.0, 'Every episode → a card')], 28.0)
    c.cam(d, 28.0, 1.2, focus=(0, 300, 1456, 900), z=1.0)
    c.call(28.0, 30.27, 'That\'s how a game', 'becomes a community')
    return c


def seg12(C):  # JEV — 25.48 s (control + AI stats only; no balances or P&L)
    c = C('seg12', 25.48, P)
    k = c.page('jev-control.png')
    ai = c.page('jev-ai.png')
    c.show(k, 0, slide=False)
    c.url(0.05, 'danslab-jev.vercel.app', typed=True)
    c.cam(k, 0, 0, y=0)
    c.ring(k, 0.4, 3.6, (53, 22, 180, 32), pad=6)
    c.call(0.3, 3.65, 'JEV', 'our live trading bot on KuCoin futures')

    c.show(ai, 3.7)
    c.cam(ai, 3.7, 0, y=0)
    c.ring(ai, 4.0, 8.3, (848, 5, 385, 85), pad=4)
    c.ring(ai, 5.6, 8.3, (320, 150, 120, 575), pad=4, spot=False)
    c.call(3.9, 8.35, 'An AI model is its brain', 'runs on its own from our Mac Studio')

    c.show(k, 8.4)
    c.cam(k, 8.4, 0, focus=(737, 270, 475, 560), z=1.2)
    for i, t in enumerate((8.7, 10.0, 11.2)):
        c.ring(k, t, t + 1.3, (737, 361 + 79 * i, 475, 70), pad=4, spot=False)
    c.cursor(k, [(8.6, 900, 760, False), (9.6, 1160, 396, False), (10.8, 1160, 474, False), (12.0, 1160, 552, False),
                 (14.4, 560, 490, False), (22.8, 380, 705, False)])
    c.chips([(8.6, 'Open'), (9.8, 'Close on a clear target'), (11.6, 'Move on')], 13.7)
    c.cam(k, 13.8, 1.0, focus=(53, 420, 645, 380), z=1.3)
    c.ring(k, 14.1, 16.5, (53, 444, 645, 90))
    c.ring(k, 16.5, 21.6, (80, 742, 590, 36), pad=6)
    c.chips([(14.0, 'Fixed trade size'), (16.2, 'Cap on open positions'), (18.6, 'Session stop')], 21.6)
    c.cam(k, 21.7, 1.0, focus=(74, 676, 603, 55), z=1.6)
    c.ring(k, 22.1, 25.48, (74, 676, 603, 55), pad=6)
    c.call(22.0, 25.48, 'Start or stop it from anywhere', 'right here, on the dashboard')
    return c


def seg15(C):  # list your project → pay → live page — 19.38 s
    c = C('seg15', 19.38, P)
    f = c.page('market-list.png')
    li = c.page('market-listing-nervixpay.png')
    c.show(f, 0, slide=False)
    c.url(0.05, 'nervix-market.vercel.app/list', typed=True)
    c.cam(f, 0, 0, focus=(283, 100, 720, 460), z=1.15)
    c.typed(f, 0.6, (283, 294, 720, 43), 'Your AI project')
    c.typed(f, 1.5, (283, 405, 720, 43), 'What it does, in one line')
    c.call(0.4, 5.2, 'List your project', 'what it does · the price · how to reach you')
    c.cam(f, 2.8, 1.0, focus=(283, 640, 720, 330), z=1.2)
    c.ring(f, 3.3, 4.7, (651, 798, 352, 43), pad=4, spot=False)
    c.typed(f, 3.4, (651, 798, 352, 43), '$19/month')
    c.ring(f, 4.2, 5.3, (283, 909, 352, 43), pad=4, spot=False)
    c.typed(f, 4.3, (283, 909, 352, 43), '@yourhandle')
    c.cam(f, 5.3, 1.0, focus=(283, 1079, 720, 85), z=1.25)
    c.ring(f, 5.7, 9.2, (283, 1079, 720, 85))
    c.call(5.5, 9.4, '10 USD membership', 'USDT or USDC · paid through NervixPay', top=True)
    c.cursor(f, [(5.6, 520, 960, False), (8.3, 890, 1121, False), (8.7, 890, 1121, True)])

    c.show(li, 9.4)
    c.url(9.4, 'nervix-market.vercel.app/l/nervixpay')
    c.cam(li, 9.4, 0, y=0)
    c.ring(li, 9.8, 11.3, (290, 150, 430, 80))
    c.call(9.6, 11.35, 'Your page is live', None)
    c.ring(li, 11.5, 13.9, (290, 245, 272, 25), pad=6)
    c.ring(li, 14.0, 16.8, (290, 476, 152, 39), pad=6)
    c.cursor(li, [(11.5, 700, 400, False), (13.0, 420, 257, False), (15.0, 365, 495, False), (15.4, 365, 495, True)])
    c.chips([(11.4, 'Its own page'), (12.6, 'Search by category'), (14.2, 'Buyers come straight to you')], 16.85)
    c.cam(li, 16.85, 1.0, focus=(250, 100, 800, 450), z=1.12)
    c.call(16.9, 19.38, 'No middleman', 'between you and your buyers')
    return c


def seg16(C):  # the directory — 11.89 s
    c = C('seg16', 11.89, P)
    k = c.page('market-home.png')
    c.show(k, 0, slide=False)
    c.url(0, 'nervix-market.vercel.app')
    c.cam(k, 0, 0, y=760)
    c.ring(k, 0.2, 2.0, (103, 985, 1080, 390))
    c.call(0.2, 2.1, 'Already in the network', 'our founding projects')
    cards = [((103, 985, 350, 175), 2.1, 4.9, 'Fake-Real', 'the link fact-checker'),
             ((467, 985, 350, 175), 4.9, 6.5, 'NervixPay', 'the payment rail'),
             ((832, 985, 350, 175), 6.5, 9.1, 'Zmarty', 'our AI trading companion'),
             ((103, 1175, 350, 210), 9.1, 11.89, 'StreamStudio', 'the studio this video was made in')]
    for rect, t, end, name, sub in cards:
        c.cam(k, t, 0.8, focus=rect, z=1.5)
        c.ring(k, t + 0.2, end, rect)
        c.call(t + 0.1, end, name, sub)
    c.cursor(k, [(0.5, 700, 1300, False), (2.6, 280, 1075, False), (5.3, 640, 1075, False), (7.0, 1000, 1075, False),
                 (9.5, 280, 1270, False)])
    return c


CARDS = {f.__name__: f for f in (seg04, seg07, seg08, seg10, seg12, seg15, seg16)}
