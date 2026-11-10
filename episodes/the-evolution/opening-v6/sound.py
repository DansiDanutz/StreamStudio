"""Original sound design for The Evolution opening — every sound is synthesised here
(no samples, no third-party audio). Levels sit well under speech: SFX peak about -16 dBFS,
beds about -30 dBFS, so Dan's voice (normalised to -14 LUFS at mux) stays on top."""
import numpy as np, wave

SR = 48000
rng = np.random.RandomState(1903)


def _t(d):
    return np.arange(int(d * SR)) / SR


def _bp(x, lo, hi):
    """Band-pass by FFT masking with soft edges."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = 1 / (1 + (lo / np.maximum(f, 1)) ** 4) / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * m, len(x))


def _norm(x):
    p = np.max(np.abs(x)) or 1
    return x / p


def _env(n, a, r):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na: e[:na] = np.linspace(0, 1, na)
    if nr: e[-nr:] *= np.linspace(1, 0, nr)
    return e


def click(f=2400, d=.018, bright=1.0):
    t = _t(d)
    return (np.sin(2 * np.pi * f * t) * .6 + rng.uniform(-1, 1, len(t)) * .4 * bright) * np.exp(-t * 260)


def dial(wind=.55, pulses=9, gap=.11):
    """Rotary dial: ratchet while winding, then the return with one pulse per digit step."""
    out = np.zeros(int((wind + .07 + pulses * gap + .25) * SR))
    for k in range(int(wind * 34)):
        i = int(k / 34 * SR)
        c = click(3200, .01, .6) * .35
        out[i:i + len(c)] += c
    whir = _bp(rng.uniform(-1, 1, len(out)), 250, 900) * .25
    s0 = int((wind + .07) * SR)
    e = np.zeros(len(out)); e[s0:s0 + int(pulses * gap * SR)] = 1
    out += whir * np.convolve(e, np.ones(400) / 400, "same")
    for k in range(pulses):
        i = s0 + int(k * gap * SR)
        c = click(1800, .022) * .9
        out[i:i + len(c)] += c
    return out


def paper(d=1.35):
    n = rng.uniform(-1, 1, int(d * SR))
    x = _bp(n, 1800, 7000)
    t = _t(d)
    e = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 1.5 * (0.7 + 0.3 * np.sin(2 * np.pi * 7 * t))
    return _norm(x * e)


def tick():
    return click(1100, .03, .3)


def tuning(d):
    """Static with heterodyne whistles sweeping as the needle crosses stations."""
    t = _t(d)
    st = _bp(rng.uniform(-1, 1, len(t)), 900, 5200)
    gl = 500 + 2100 * np.abs(np.sin(np.pi * t / d * 1.6))
    ph = 2 * np.pi * np.cumsum(gl) / SR
    wh = np.sin(ph) * (0.5 + 0.5 * np.sin(2 * np.pi * 2.3 * t)) ** 2
    return _norm(st * .8 + wh * .35) * _env(len(t), .08, .25)


def crowd(d, swell_at=None):
    t = _t(d)
    base = _bp(rng.uniform(-1, 1, len(t)), 180, 2600)
    mur = 0.55 + 0.25 * np.sin(2 * np.pi * .37 * t) + 0.2 * np.sin(2 * np.pi * 1.13 * t + 1)
    x = base * mur
    if swell_at is not None:
        u = t - swell_at
        sw = np.where(u > 0, np.minimum(1, u / .35) * np.exp(-np.maximum(0, u - .35) / 1.6), 0)
        bright = _bp(rng.uniform(-1, 1, len(t)), 600, 4200)
        x = x + (base * 1.6 + bright * 1.2) * sw * 2.2
    return x / (np.max(np.abs(base)) * 2.6)


def thump(f=58, d=.35):
    t = _t(d)
    return np.sin(2 * np.pi * f * t * (1 - .3 * t)) * np.exp(-t * 14)


def crackle(d, dens=38):
    x = np.zeros(int(d * SR))
    for _ in range(int(d * dens)):
        i = rng.randint(0, len(x) - 200)
        c = click(rng.uniform(1500, 5000), .004, 1) * rng.uniform(.2, 1)
        x[i:i + len(c)] += c
    return x + _bp(rng.uniform(-1, 1, len(x)), 2000, 8000) * .06


def keys(d, bpm=92):
    """A warm original chord progression (Dmaj7 – Bm7 – Em7 – A7), Rhodes-like."""
    chords = [[146.83, 220, 277.18, 369.99], [123.47, 185, 220, 293.66], [164.81, 196, 246.94, 293.66], [110, 164.81, 196, 277.18]]
    beat = 60 / bpm
    out = np.zeros(int(d * SR))
    k = 0; t0 = 0.0
    while t0 < d:
        ch = chords[k % 4]
        for hit, vel in ((0, 1), (1.5, .55), (2.5, .7)):
            s = t0 + hit * beat
            if s >= d: break
            tt = _t(min(2.2, d - s))
            v = sum(np.sin(2 * np.pi * f * tt) + .25 * np.sin(4 * np.pi * f * tt) for f in ch) * np.exp(-tt * 1.6) * vel
            i = int(s * SR); out[i:i + len(v)] += v[:len(out) - i]
        t0 += 4 * beat; k += 1
    return out / 8


def whoosh(d=.7, up=True):
    t = _t(d)
    n = rng.uniform(-1, 1, len(t))
    lo = _bp(n, 300, 1500); hi = _bp(n, 1500, 7000)
    p = t / d if up else 1 - t / d
    return _norm(lo * (1 - p) + hi * p) * np.sin(np.pi * t / d) ** 2


def blip(f, d=.25):
    t = _t(d)
    return (np.sin(2 * np.pi * f * t) + .3 * np.sin(4 * np.pi * f * t)) * np.exp(-t * 16) * _env(len(t), .004, .02)


def chime(f):
    t = _t(1.6)
    return sum(a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * (2.5 + m)) for m, a in ((1, 1), (2.01, .4), (3.02, .18)))


def pad(d, root=98):
    t = _t(d)
    x = sum(np.sin(2 * np.pi * f * t + i) for i, f in enumerate((root, root * 1.5, root * 2, root * 2.52)))
    return x / 4 * (0.85 + 0.15 * np.sin(2 * np.pi * .2 * t))


def bell(d=.75):
    t = _t(d)
    trem = (np.sin(2 * np.pi * 20 * t) > 0).astype(float)
    tone = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((1180, 1), (1760, .5), (2950, .25)))
    return tone * trem * _env(len(t), .01, .15) * np.exp(-t * .8)


def quindar(f):
    t = _t(.25)
    return np.sin(2 * np.pi * f * t) * _env(len(t), .005, .02)


def rewind(d=1.0):
    t = _t(d)
    gl = 300 + 2600 * (t / d) ** 1.5
    return np.sin(2 * np.pi * np.cumsum(gl) / SR) * .4 * np.sin(np.pi * t / d) + _bp(rng.uniform(-1, 1, len(t)), 2000, 7000) * .3 * np.sin(np.pi * t / d)


def projector(d):
    """16 mm projector: motor hum, a 24 fps shutter flutter and gate rattle."""
    t = _t(d)
    hum = np.sin(2 * np.pi * 60 * t) * .35 + np.sin(2 * np.pi * 120 * t) * .15
    rattle = _bp(rng.uniform(-1, 1, len(t)), 1500, 6000) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 24 * t)))
    return hum * .6 + rattle * .5


def render(C, D, path):
    L = int(D * SR) + SR
    mix = np.zeros((L, 2))

    def put(x, at, db, pan=0.0):
        i = int(max(0, at) * SR)
        x = x[:L - i] * 10 ** (db / 20)
        mix[i:i + len(x), 0] += x * np.sqrt((1 - pan) / 2) * 1.414
        mix[i:i + len(x), 1] += x * np.sqrt((1 + pan) / 2) * 1.414

    # THE PAST: projector + warm drone, cut dead on "Now"
    past = C["present"] - C["shrink"]
    n = int(past * SR)
    put(projector(past) * _env(n, 1.0, 0.0), C["shrink"], -33)
    put(pad(past, 73.4) * _env(n, 1.5, 0.0), C["shrink"], -33)
    put(rewind(1.2), C["shrink"] - .3, -27)                           # 2026 rolls back
    put(whoosh(.9, False), C["shrink"] - .1, -30)
    for k in range(10):
        put(tick(), C["shrink"] + .2 + 1.4 * ((k + 1) / 10) ** .5, -30)
    wind = max(.6, C["ret"] - C["wind"] - .1)
    put(click(700, .04, .3), C["finger"] + .4, -26)                   # fingertip into the hole
    put(dial(wind, 7, .1), C["wind"], -17, .15)                       # wind to the stop, seven pulses back
    put(whoosh(.8, True), C["letterIn"] - .1, -31)
    put(thump(90, .25), C["post"], -18); put(click(900, .03, .4), C["post"], -24)
    put(paper(.5), C["flap"], -26)
    put(paper(1.1), C["slide"], -24, -.1)
    span = max(.8, C["waitEnd"] - C["waitStart"] - .2)
    for k in range(20):
        put(tick(), C["waitStart"] + .2 + span * ((k + 1) / 20) ** .6, -28, .3)
    put(whoosh(.8, True), C["radioIn"] - .1, -31)
    put(tuning(C["tuneLock"] - C["tune"] + .2), C["tune"], -22)
    td = C["recordIn"] + .4 - C["tuneLock"]
    tx = (_bp(rng.uniform(-1, 1, int(td * SR)), 300, 3000) * .5 + crowd(td) * .6) * _env(int(td * SR), .2, .5)
    put(tx, C["tuneLock"], -22)
    put(quindar(2525), C["moonIn"] + .4, -25); put(quindar(2475), C["step"] + .3, -25)
    put(thump(45, .5), C["step"], -20)
    vd = max(1, C["viewersEnd"] - C["viewers"])
    for k in range(16):
        put(tick(), C["viewers"] + vd * (k / 16) ** 2, -31, -.3)
    put(whoosh(.8, True), C["recordIn"] - .1, -31)
    put(thump(75, .3), C["drop"], -19)                                # record lands on the platter
    put(thump(), C["needle"], -16)
    cd = C["present"] - C["needle"]
    put(crackle(cd), C["needle"], -27)
    kd = C["present"] - C["dance"] + .9
    put(keys(kd), C["dance"] - .9, -21)
    # NOW: silence for a beat, then a crisp digital hit
    i0 = int(C["present"] * SR); mix[i0:, :] *= 0
    put(thump(55, .5), C["present"], -14); put(blip(1567.98, .35), C["present"], -18); put(blip(2093, .3), C["present"] + .06, -20)
    put(chime(659.3), C["hasAll"], -28)
    for i, k in enumerate(("wireCall", "wireLetter", "wireRadio", "wireMusic")):
        put(blip((587.3, 659.3, 784, 880)[i]), C[k] + .45, -23, (-.4, -.4, .4, .4)[i])
    notes = {"internet": 523.25, "money": 587.33, "ai": 659.26, "news": 783.99, "friends": 880, "travel": 987.77, "business": 1046.5}
    pans = {"internet": 0, "money": .45, "ai": .7, "news": .45, "friends": 0, "travel": -.45, "business": -.45}
    for k, f in notes.items():
        put(blip(f, .3), C[k], -23 if k != "ai" else -20, pans[k])
    pr = C["danBig"] - C["present"]
    put(pad(pr, 110) * _env(int(pr * SR), 1.5, .8), C["present"] + .3, -38)
    for k, off in (("present", 1.2), ("internet", .3), ("danBack", .5), ("title", .4)):
        put(whoosh(.9, True) * .5, C[k] + off, -34, .3)          # shooting stars
    put(whoosh(1.0, False), C["danBig"] - .1, -28)
    pd = C["danBack"] - C["danBig"] + 1
    put(pad(pd, 110) * _env(int(pd * SR), 1.2, 1.0), C["danBig"], -36)
    for k, f in (("easier", 880), ("ownbiz", 987.77), ("independent", 1174.66)):
        put(chime(f), C[k], -29)
    put(thump(60, .5), C["rich"], -20)
    for k, f in (("school", 659.3), ("info", 783.99), ("resources", 987.77)):
        put(blip(f, .35), C[k], -23)
    put(chime(1318.5), C["dreams"], -27)
    put(rewind(1.0), C["goBack"] - .2, -27)
    tdd = D - C["danBack"] + .5
    put(pad(tdd, 98) * _env(int(tdd * SR), 1.5, 1.8), C["danBack"], -27)
    for k, f in (("pTech", 523.25), ("pHealth", 659.26), ("pEdu", 783.99), ("pFin", 1046.5)):
        put(blip(f, .35), C[k], -23)
    put(thump(49, .9), C["title"], -18); put(chime(392), C["title"], -26)

    mix = mix[:int(D * SR)] * 10 ** (6 / 20)
    peak = np.max(np.abs(mix))
    if peak > 10 ** (-7 / 20):
        mix *= 10 ** (-7 / 20) / peak
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())
