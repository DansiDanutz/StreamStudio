"""Shared GSAP logo animation, ported from the original DansLab composition."""
# ruff: noqa: E501  -- embedded GSAP and CSS template
import math

FPS = 30
f = lambda n: n / FPS  # noqa: E731
S0 = 0.5  # logo starts
TITLE = 3.6  # title card starts
DUR = 7.2
size = 230
s = size / 512

FONT_FILES = (
    "newsreader-latin-500-normal.woff2",
    "newsreader-latin-600-normal.woff2",
    "newsreader-latin-500-italic.woff2",
    "jetbrains-mono-latin-500-normal.woff2",
)


def rnd(seed):
    x = math.sin(seed * 9999) * 10000
    return x - math.floor(x)


stars = []
for i in range(92):
    st = dict(
        x=rnd(i * 3 + 1) * 1920,
        y=rnd(i * 7 + 2) * 1080,
        s=0.8 + rnd(i * 11 + 3) * 2.2,
        o=0.10 + rnd(i * 13 + 5) * 0.4,
        warm=rnd(i * 17 + 7) > 0.82,
        tw=0.5 + rnd(i * 19 + 9) * 1.8,
        ph=rnd(i * 23 + 11),
    )
    stars.append(st)
sparks = [
    dict(
        ang=(i / 14) * math.pi * 2,
        dist=0.72 + rnd(i * 5 + 11) * 0.55,
        s=3 + rnd(i * 9 + 4) * 5,
        delay=math.floor(rnd(i * 13 + 6) * 8),
        gold=rnd(i * 3 + 2) > 0.45,
    )
    for i in range(14)
]


def composition(kicker, title_html, tagline, letter, colors):
    css = f"""
    @font-face{{font-family:Newsreader;src:url(newsreader-latin-500-normal.woff2);font-weight:500}}
    @font-face{{font-family:Newsreader;src:url(newsreader-latin-600-normal.woff2);font-weight:600}}
    @font-face{{font-family:Newsreader;src:url(newsreader-latin-500-italic.woff2);font-weight:500;font-style:italic}}
    @font-face{{font-family:JBM;src:url(jetbrains-mono-latin-500-normal.woff2);font-weight:500}}
    *{{margin:0;padding:0;box-sizing:border-box}}
    html,body{{width:1920px;height:1080px;background:{colors['bg']};overflow:hidden}}
    #root{{position:relative;width:1920px;height:1080px;overflow:hidden;background:{colors['bg']}}}
    .glow{{position:absolute;inset:0;background:radial-gradient(1200px 640px at 50% -10%,{colors['glow']},transparent 60%)}}
    .grid{{position:absolute;inset:0;background-image:radial-gradient(#ffffff08 1px,transparent 1px);background-size:44px 44px}}
    .stars{{position:absolute;inset:-40px}}
    .star{{position:absolute;border-radius:50%}}
    .center{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}}
    .logo{{position:relative;width:{size}px;height:{size}px}}
    .ring{{position:absolute;left:50%;top:50%;width:{size}px;height:{size}px;margin:-{size / 2}px 0 0 -{size / 2}px;border-radius:32%;border:{max(1.5, 3 * s * 2):.1f}px solid {colors['accent']};opacity:0}}
    .spark{{position:absolute;left:50%;top:50%;border-radius:50%;opacity:0}}
    .tile{{position:absolute;inset:0;transform:scale(0) rotate(-10deg)}}
    .plate{{position:absolute;inset:0;border-radius:{104 * s:.1f}px;background:linear-gradient(135deg,{colors['accent']},{colors['accent_dark']});border:{max(1, 5 * s):.1f}px solid #ffffff24;overflow:hidden}}
    .shine{{position:absolute;top:-20%;bottom:-20%;left:-60%;width:34%;background:linear-gradient(105deg,transparent,#ffffff88,transparent);opacity:0;transform:rotate(8deg)}}
    .D{{position:absolute;left:46%;top:47%;transform:translate(-50%,-50%);font:600 {300 * s:.1f}px/1 Newsreader;color:{colors['letter']};opacity:0}}
    .cur{{position:absolute;left:{352 * s:.1f}px;top:{308 * s:.1f}px;width:{52 * s:.1f}px;height:{76 * s:.1f}px;border-radius:{10 * s:.1f}px;background:{colors['highlight']};opacity:0}}
    .card{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;opacity:0}}
    .kick{{font:500 27px JBM;letter-spacing:10px;color:{colors['accent']};opacity:0}}
    .name{{font:500 128px Newsreader;color:{colors['title']};margin-top:20px;white-space:nowrap}}
    .name em{{font-style:italic;color:{colors['highlight']}}}
    .rule{{margin-top:26px;height:5px;width:560px;border-radius:999px;background:#ffffff10;overflow:hidden}}
    .rule i{{display:block;height:100%;width:100%;background:linear-gradient(90deg,{colors['accent']},{colors['highlight']});transform:scaleX(0)}}
    .tag{{font:italic 500 40px Newsreader;color:{colors['muted']};margin-top:30px;opacity:0}}
    """
    star_html = "".join(
        f'<div class="star" id="st{i}" style="left:{st["x"]:.0f}px;top:{st["y"]:.0f}px;width:{st["s"]:.1f}px;height:{st["s"]:.1f}px;'
        f'background:{colors["highlight"] if st["warm"] else "#fff"};opacity:{st["o"] * 0.5:.2f};'
        f'{"box-shadow:0 0 {:.1f}px {}66;".format(st["s"] * 2, colors["highlight"] if st["warm"] else "#ffffff") if st["s"] > 2.2 else ""}"></div>'
        for i, st in enumerate(stars)
    )
    spark_html = "".join(
        f'<div class="spark" id="sp{i}" style="width:{p["s"] * s * 3.4:.1f}px;height:{p["s"] * s * 3.4:.1f}px;margin:-{p["s"] * s * 1.7:.1f}px 0 0 -{p["s"] * s * 1.7:.1f}px;background:{colors["highlight"] if p["gold"] else colors["accent"]}"></div>'
        for i, p in enumerate(sparks)
    )

    js: list[str] = []
    A = js.append
    # stars: twinkle (finite yoyo) + slow drift of the whole field
    for i, st in enumerate(stars):
        per = 2 * math.pi / (0.062 * st["tw"] * FPS)  # seconds per full twinkle cycle
        A(
            f"tl.fromTo('#st{i}',{{opacity:{st['o'] * 0.05:.3f}}},{{opacity:{st['o'] * 1.05:.3f},duration:{per / 2:.2f},ease:'sine.inOut',yoyo:true,repeat:{int(DUR / (per / 2)) + 1}}},{st['ph'] * .4:.2f});"
        )
    A(f"tl.fromTo('.stars',{{x:-18,y:12}},{{x:18,y:-12,duration:{DUR},ease:'sine.inOut'}},0);")
    # logo (frames from DlLogoAnimated, start = S0)
    A(f"tl.to('.tile',{{scale:1,rotation:0,duration:{f(16)},ease:'back.out(1.6)'}},{S0});")
    A(
        f"tl.fromTo('.D',{{opacity:0,y:{18 * s * 3:.1f}}},{{opacity:1,y:0,duration:{f(14)},ease:'power2.out'}},{S0 + f(10)});"
    )
    A(f"tl.to('.cur',{{opacity:1,duration:{f(14)}}},{S0 + f(10)});")
    t = S0 + f(22)
    on = True
    while t < TITLE:
        A(f"tl.set('.cur',{{opacity:{1 if on else 0.25}}},{t:.3f});")
        t += f(14)
        on = not on
    A(
        f"tl.fromTo('.shine',{{left:'-60%',opacity:0}},{{left:'140%',duration:{f(20)},ease:'sine.inOut'}},{S0 + f(26)});"
    )
    A(
        f"tl.to('.shine',{{opacity:0.5,duration:{f(4)}}},{S0 + f(26)});tl.to('.shine',{{opacity:0,duration:{f(4)}}},{S0 + f(42)});"
    )
    A(
        f"tl.fromTo('.ring',{{scale:1,opacity:0}},{{scale:1.9,duration:{f(26)},ease:'power2.out'}},{S0 + f(14)});"
    )
    A(
        f"tl.to('.ring',{{opacity:0.55,duration:{f(6)}}},{S0 + f(14)});tl.to('.ring',{{opacity:0,duration:{f(20)}}},{S0 + f(20)});"
    )
    for i, p in enumerate(sparks):
        d0, d1 = size * 0.5 * 0.6, size * 0.5 * (0.6 + p["dist"])
        t0 = S0 + f(16) + p["delay"] / 60 * f(28)
        c, si = math.cos(p["ang"]), math.sin(p["ang"])
        A(
            f"tl.fromTo('#sp{i}',{{x:{c * d0:.1f},y:{si * d0:.1f},opacity:0}},{{x:{c * d1:.1f},y:{si * d1:.1f},duration:{f(28)},ease:'power2.out'}},{t0:.3f});"
        )
        A(
            f"tl.to('#sp{i}',{{opacity:0.9,duration:{f(7)}}},{t0:.3f});tl.to('#sp{i}',{{opacity:0,duration:{f(21)}}},{t0 + f(7):.3f});"
        )
    # logo out, title card in (TIntro timings)
    A(f"tl.to('.center',{{opacity:0,duration:{f(18)},ease:'power2.in'}},{TITLE - f(22):.3f});")
    A(f"tl.to('.card',{{opacity:1,duration:{f(18)},ease:'power2.out'}},{TITLE + f(12):.3f});")
    A(
        f"tl.fromTo('.card',{{scale:1.06}},{{scale:1,duration:{f(22)},ease:'power2.out'}},{TITLE + f(12):.3f});"
    )
    A(f"tl.to('.kick',{{opacity:1,duration:{f(14)}}},{TITLE:.3f});")
    A(f"tl.to('.rule i',{{scaleX:1,duration:{f(24)},ease:'sine.inOut'}},{TITLE + f(34):.3f});")
    A(f"tl.to('.tag',{{opacity:1,duration:{f(16)}}},{TITLE + f(60):.3f});")
    A(f"tl.fromTo('#root',{{opacity:1}},{{opacity:0,duration:0.6,ease:'power2.in',immediateRender:false}},{DUR - 0.6:.2f});")

    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>
    <div id="root" data-composition-id="root" data-width="1920" data-height="1080" data-fps="25" data-start="0" data-duration="{DUR}">
    <div class="glow"></div><div class="grid"></div><div class="stars">{star_html}</div>
    <div class="center"><div class="logo"><div class="ring"></div>{spark_html}
    <div class="tile"><div class="plate"><div class="shine"></div></div><span class="D">{letter}</span><div class="cur"></div></div></div></div>
    <div class="card"><div class="kick">{kicker}</div><div class="name">{title_html}</div><div class="rule"><i></i></div><div class="tag">{tagline}</div></div>
    </div>
    <script src="gsap.min.js"></script>
    <script>
    const tl=gsap.timeline({{paused:true}});
    gsap.set("#root", {{opacity:1}});
    {chr(10).join(js)}
    tl.set({{}},{{}},{DUR});
    window.__timelines={{root:tl}};
    </script></body></html>"""
    return html
