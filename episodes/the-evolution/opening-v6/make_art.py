"""Original vector artifacts for The Evolution opening, generated from code.
Every moving part has an id so the composition can animate it:
  telephone.svg  #tel-handset  #tel-wheel (rotates about 500 450)  #tel-ring
  letter.svg     #let-flapC #let-flapO #let-sheet #let-title-clip #let-ink path #let-post
  radio.svg      #rad-needle (rotates about 500 760)  #rad-knob (about 620 612) #rad-lamp
  turntable.svg  #tt-spin (about 440 365)  #tt-arm (about 720 170)  #tt-armshadow
  phone.svg      #ph-dock-* #ph-app-*  (generic smartphone, no brand)
  pitch.svg      chalk football pitch, #pi-ball #pi-net
"""
import math, random
from pathlib import Path

out = Path(__file__).parent / "art"; out.mkdir(exist_ok=True)
R = random.Random(7)
f = lambda v: f"{v:.1f}"


def svg(name, w, h, body, defs=""):
    (out / f"{name}.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" class="artsvg" id="svg-{name}">'
        f'<defs>{defs}</defs>{body}</svg>\n')


SOFT = lambda p: f'<filter id="{p}-soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="14"/></filter>'
FLOOR = lambda p, cx, cy, rx: f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="26" fill="#000" opacity=".5" filter="url(#{p}-soft)"/>'

# ---------------------------------------------------------------- telephone
coil = []
for i in range(0, 361):
    t = i / 360
    bx, by = 232 - 150 * t, 520 + 120 * t - 60 * t * t
    a = t * 2 * math.pi * 11
    coil.append((bx + 15 * math.cos(a), by + 15 * math.sin(a) * .8))
coil_d = "M" + " L".join(f"{f(x)} {f(y)}" for x, y in coil)
cx, cy = 500, 450
num_ang = {str(d % 10): 60 - (d - 1) * 30 for d in range(1, 11)}
plate, holes = [], []
for d, a in num_ang.items():
    r = math.radians(a)
    x, y = cx + 112 * math.sin(r), cy - 112 * math.cos(r)
    plate.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="23" fill="#fffaf0"/><text x="{f(x)}" y="{f(y+10)}" text-anchor="middle" font-family="Inter" font-weight="700" font-size="28" fill="#2a1c16">{d}</text>')
    holes.append(f'M{f(x+24)} {f(y)} A24 24 0 1 0 {f(x-24)} {f(y)} A24 24 0 1 0 {f(x+24)} {f(y)} Z')
ring_d = f"M{cx+150} {cy} A150 150 0 1 0 {cx-150} {cy} A150 150 0 1 0 {cx+150} {cy} Z M{cx+64} {cy} A64 64 0 1 0 {cx-64} {cy} A64 64 0 1 0 {cx+64} {cy} Z " + " ".join(holes)
stop_a = math.radians(110)
svg("telephone", 1000, 700, f'''
{FLOOR("tel", 500, 640, 330)}
<path d="{coil_d}" fill="none" stroke="#5f160f" stroke-width="9" stroke-linecap="round"/>
<path d="{coil_d}" fill="none" stroke="#c4473a" stroke-width="3" stroke-linecap="round" opacity=".6"/>
<rect x="228" y="596" width="544" height="46" rx="16" fill="#4e120c"/>
<path d="M262 620 Q215 620 223 576 L286 302 Q296 256 342 256 L658 256 Q704 256 714 302 L777 576 Q785 620 738 620 Z" fill="url(#tel-body)"/>
<path d="M300 300 Q306 272 340 272 L420 272 L330 600 L262 600 Z" fill="#fff" opacity=".07"/>
<path d="M286 302 Q296 256 342 256 L658 256 Q704 256 714 302" fill="none" stroke="#ff9a85" stroke-width="3" opacity=".45"/>
<rect x="322" y="226" width="96" height="44" rx="14" fill="#6f1a12"/><rect x="582" y="226" width="96" height="44" rx="14" fill="#6f1a12"/>
<g id="tel-plate"><circle cx="{cx}" cy="{cy}" r="166" fill="#5c140d"/><circle cx="{cx}" cy="{cy}" r="156" fill="#efe3c9"/>{"".join(plate)}</g>
<g id="tel-wheel"><path d="{ring_d}" fill-rule="evenodd" fill="#f8f1e2" fill-opacity=".62" stroke="#d6c7a6" stroke-width="2"/>
 <path d="M{cx} {cy-150} A150 150 0 0 1 {cx+128} {cy-78}" fill="none" stroke="#fff" stroke-width="5" opacity=".7" stroke-linecap="round"/></g>
<circle cx="{cx}" cy="{cy}" r="60" fill="#f3e8d2" stroke="#cdb994" stroke-width="3"/>
<text x="{cx}" y="{cy-8}" text-anchor="middle" font-family="Mono" font-size="15" fill="#7a3a2a" letter-spacing="2">DAN’S LAB</text>
<text x="{cx}" y="{cy+18}" text-anchor="middle" font-family="Mono" font-size="17" fill="#2a1c16">021 1987</text>
<path d="M{f(cx+146*math.sin(stop_a))} {f(cy-146*math.cos(stop_a))} L{f(cx+182*math.sin(stop_a+.08))} {f(cy-182*math.cos(stop_a+.08))}" stroke="#c9c2b4" stroke-width="12" stroke-linecap="round"/>
<g id="tel-finger" opacity="0"><g transform="translate(403 506) rotate(35)">
 <path d="M-23 0 Q-23 -26 0 -26 Q23 -26 23 0 L26 190 L-26 190 Z" fill="url(#tel-skin)"/>
 <path d="M-13 -6 Q-13 -20 0 -20 Q13 -20 13 -6 L13 16 Q0 22 -13 16 Z" fill="#f6d6c2" stroke="#d9a98a" stroke-width="1.5"/>
 <path d="M-20 70 Q0 78 20 70 M-21 110 Q0 118 21 110" fill="none" stroke="#c98d6a" stroke-width="2" opacity=".6"/></g></g>
<g id="tel-handset">
 <path d="M226 205 Q226 148 290 148 L710 148 Q774 148 774 205 L774 218 Q774 250 736 250 L668 250 Q646 250 636 228 L626 206 L374 206 L364 228 Q354 250 332 250 L264 250 Q226 250 226 218 Z" fill="url(#tel-hs)"/>
 <path d="M300 161 L700 161" stroke="#ffb3a3" stroke-width="5" stroke-linecap="round" opacity=".55"/></g>
<g id="tel-ring" fill="none" stroke="#fff3df" stroke-width="5" stroke-linecap="round" opacity="0">
 <path d="M196 150 Q178 182 196 214"/><path d="M168 132 Q140 182 168 232"/><path d="M804 150 Q822 182 804 214"/><path d="M832 132 Q860 182 832 232"/></g>
''', SOFT("tel") + '<linearGradient id="tel-body" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c8442f"/><stop offset="1" stop-color="#7a1c13"/></linearGradient>'
     '<linearGradient id="tel-skin" x1="0" x2="1"><stop offset="0" stop-color="#d99a74"/><stop offset=".5" stop-color="#efc2a0"/><stop offset="1" stop-color="#cf8e68"/></linearGradient>'
     '<linearGradient id="tel-hs" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#d24c37"/><stop offset="1" stop-color="#7e1e14"/></linearGradient>')

# ---------------------------------------------------------------- letter
ink = []
for li in range(6):
    y = 196 + li * 44
    x, pts = 290 + (40 if li == 0 else 0), []
    end = 720 - (180 if li == 5 else R.randint(0, 50))
    while x < end:
        w = R.uniform(30, 70)
        k = R.randint(3, 6)
        for j in range(k):
            xx = x + w * j / k
            pts.append((xx, y - R.uniform(4, 16) * (j % 2 == 0)))
            pts.append((xx + w / k * .5, y + R.uniform(0, 4)))
        x += w + R.uniform(12, 22)
        pts.append(("M", x, y))
    d, move = "", True
    for p in pts:
        if p[0] == "M":
            move = True; continue
        d += (f"M{f(p[0])} {f(p[1])} " if move else f"L{f(p[0])} {f(p[1])} "); move = False
    ink.append(f'<path d="{d}" fill="none" stroke="#2f3f78" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>')
svg("letter", 1000, 700, f'''
{FLOOR("let", 500, 650, 340)}
<rect x="180" y="330" width="640" height="310" rx="12" fill="#cdb488"/>
<path id="let-flapO" d="M180 332 L500 150 L820 332 Z" fill="#c3a777" stroke="#a88a5a" stroke-width="2" transform="matrix(1 0 0 0 0 332)"/>
<clipPath id="let-clip"><rect x="0" y="0" width="1000" height="600"/></clipPath><g clip-path="url(#let-clip)"><g id="let-sheet" transform="translate(0 380)">
 <rect x="240" y="70" width="520" height="430" rx="6" fill="#fbf4e3"/>
 <path d="M240 70 L760 70 L760 500 L240 500 Z" fill="none" stroke="#e2d5b8" stroke-width="2"/>
 <clipPath id="let-title-clip"><rect id="let-title-rect" x="280" y="96" width="0" height="70"/></clipPath>
 <text x="290" y="148" font-family="Hand" font-size="50" fill="#2f3f78" clip-path="url(#let-title-clip)">Dragă Elena,</text>
 <g id="let-ink">{"".join(ink)}</g></g></g>
<path d="M180 400 L500 566 L820 400 L820 628 Q820 640 808 640 L192 640 Q180 640 180 628 Z" fill="url(#let-front)"/>
<path d="M180 640 L455 470 M820 640 L545 470" stroke="#b99c6b" stroke-width="2" opacity=".6"/>
<path id="let-flapC" d="M180 332 L500 582 L820 332 Z" fill="#e3cfa6" stroke="#b99c6b" stroke-width="2"/>
<g transform="translate(700 470) rotate(4)"><rect x="-44" y="-54" width="88" height="108" fill="#fff8ea" stroke="#d9c7a4" stroke-dasharray="4 4"/>
 <rect x="-34" y="-44" width="68" height="88" fill="#7b2f3a"/><circle cx="0" cy="-4" r="18" fill="#e9c9a2"/><path d="M-22 30 Q0 6 22 30 Z" fill="#e9c9a2"/>
 <text x="0" y="-26" text-anchor="middle" font-family="Mono" font-size="11" fill="#f6e3c8">ROMÂNIA</text></g>
<g id="let-post" transform="translate(600 500)" opacity="0"><circle r="54" fill="none" stroke="#3b3b55" stroke-width="3" opacity=".75"/><circle r="42" fill="none" stroke="#3b3b55" stroke-width="2" opacity=".6"/>
 <text y="-14" text-anchor="middle" font-family="Mono" font-size="13" fill="#3b3b55" opacity=".8">BUCUREȘTI</text><text y="12" text-anchor="middle" font-family="Mono" font-size="15" fill="#3b3b55" opacity=".85">14·V·1987</text>
 <path d="M60 -14 Q90 -24 120 -14 T180 -14 M60 2 Q90 -8 120 2 T180 2 M60 18 Q90 8 120 18 T180 18" fill="none" stroke="#3b3b55" stroke-width="3" opacity=".6"/></g>
<text x="300" y="610" font-family="Hand" font-size="34" fill="#4a3a28" opacity=".85">D-nei Elena Popescu · Iași</text>
''', SOFT("let") + '<linearGradient id="let-front" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f0e1c2"/><stop offset="1" stop-color="#ddc69c"/></linearGradient>')

# ---------------------------------------------------------------- radio
grain = "".join(f'<path d="M{280+i*34} 640 Q{290+i*34+R.uniform(-20,20)} 360 {300+i*30} {120+abs(i-6)*22}" fill="none" stroke="#3a1a08" stroke-width="{R.uniform(1,2.4):.1f}" opacity=".25"/>' for i in range(14))
labels = [55, 60, 70, 80, 100, 120, 140, 160]
tick_s, lab_s = [], []
for i in range(71):
    a = math.radians(-22 + 44 * i / 70)
    r1 = 218 if i % 10 == 0 else 225
    tick_s.append(f'<line x1="{f(500+r1*math.sin(a))}" y1="{f(760-r1*math.cos(a))}" x2="{f(500+232*math.sin(a))}" y2="{f(760-232*math.cos(a))}" stroke="#4a2e15" stroke-width="{1.8 if i%10==0 else 1}"/>')
for i, l in enumerate(labels):
    a = -22 + 44 * i / 7
    lab_s.append(f'<text x="500" y="{760-246}" text-anchor="middle" font-family="Inter" font-weight="700" font-size="15" fill="#4a2e15" transform="rotate({a:.2f} 500 760)">{l}</text>')
knob = lambda x, idn="": f'<g {idn}><circle cx="{x}" cy="612" r="26" fill="#3a1b0b"/><circle cx="{x}" cy="612" r="20" fill="url(#rad-knob)"/>' + "".join(
    f'<line x1="{x}" y1="{612-20}" x2="{x}" y2="{612-13}" stroke="#1d0d05" stroke-width="2.5" transform="rotate({k*30} {x} 612)"/>' for k in range(12)) + f'<circle cx="{x}" cy="{612-15}" r="3" fill="#e8c18a"/></g>'
svg("radio", 1000, 700, f'''
{FLOOR("rad", 500, 662, 300)}
<rect x="244" y="622" width="512" height="40" rx="10" fill="#3b1a0a"/>
<path d="M270 636 L270 330 Q270 92 500 92 Q730 92 730 330 L730 636 Z" fill="url(#rad-wood)"/>{grain}
<path d="M270 330 Q270 92 500 92 Q730 92 730 330" fill="none" stroke="#e8a466" stroke-width="3" opacity=".35"/>
<path d="M318 474 L318 338 Q318 142 500 142 Q682 142 682 338 L682 474 Z" fill="url(#rad-cloth)" stroke="#3b1a0a" stroke-width="6"/>
<g fill="none" stroke="#6b3412" stroke-width="15" stroke-linejoin="round"><path d="M452 474 L452 300 Q452 210 500 186 Q548 210 548 300 L548 474"/>
 <path d="M362 474 L362 340 Q362 268 398 252 Q434 268 434 340 L434 474"/><path d="M566 474 L566 340 Q566 268 602 252 Q638 268 638 340 L638 474"/></g>
<rect x="300" y="474" width="400" height="16" fill="#5a2a10"/>
<clipPath id="rad-win"><path d="M392 576 L392 528 Q392 500 422 500 L578 500 Q608 500 608 528 L608 576 Z"/></clipPath>
<path d="M392 576 L392 528 Q392 500 422 500 L578 500 Q608 500 608 528 L608 576 Z" fill="url(#rad-dial)" stroke="#d9b072" stroke-width="5"/>
<g clip-path="url(#rad-win)"><ellipse id="rad-lamp" cx="500" cy="556" rx="120" ry="56" fill="url(#rad-lampg)" opacity=".35"/>{"".join(tick_s)}{"".join(lab_s)}
 <line id="rad-needle" x1="500" y1="760" x2="500" y2="512" stroke="#a31d10" stroke-width="3.4" stroke-linecap="round" transform="rotate(-18 500 760)"/></g>
{knob(380)}{knob(500)}{knob(620, 'id="rad-knob"')}
''', SOFT("rad") + '<linearGradient id="rad-wood" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#9a5427"/><stop offset=".6" stop-color="#6e3415"/><stop offset="1" stop-color="#4a210c"/></linearGradient>'
     '<pattern id="rad-cloth" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="#b88f58"/><rect width="4" height="4" fill="#cfa86f"/><rect x="4" y="4" width="4" height="4" fill="#a37a45"/></pattern>'
     '<linearGradient id="rad-dial" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fbe7bd"/><stop offset="1" stop-color="#e3b26a"/></linearGradient>'
     '<radialGradient id="rad-lampg"><stop offset="0" stop-color="#fff6d0"/><stop offset="1" stop-color="#fff6d0" stop-opacity="0"/></radialGradient>'
     '<radialGradient id="rad-knob" cx=".35" cy=".35"><stop offset="0" stop-color="#7a4422"/><stop offset="1" stop-color="#2b1306"/></radialGradient>')

# ---------------------------------------------------------------- turntable (top-down)
grooves = "".join(f'<circle cx="440" cy="365" r="{r}" fill="none" stroke="{"#2c2928" if r%2 else "#1d1b1b"}" stroke-width="2"/>' for r in range(80, 204, 3))
specks = "".join(f'<circle cx="{f(440+r*math.cos(a))}" cy="{f(365+r*math.sin(a))}" r="1.6" fill="#fff" opacity=".35"/>' for a, r in [(R.uniform(0, 6.28), R.uniform(90, 200)) for _ in range(14)])
arm = '<circle cx="720" cy="170" r="34" fill="url(#tt-metal)" stroke="#8d8577" stroke-width="2"/><circle cx="720" cy="170" r="12" fill="#5d574f"/>' \
      '<path d="M716 176 L716 470 Q716 500 700 512 L708 522 Q732 506 730 470 L730 176 Z" fill="url(#tt-metal)" stroke="#7d766a" stroke-width="1.5"/>' \
      '<g transform="translate(712 520) rotate(18)"><rect x="-22" y="-6" width="44" height="58" rx="5" fill="#e9e1cf" stroke="#9b927f" stroke-width="2"/><rect x="-10" y="40" width="20" height="16" fill="#5b3b2b"/></g>' \
      '<rect x="706" y="120" width="28" height="40" rx="6" fill="#4e4943"/>'
svg("turntable", 1000, 700, f'''
{FLOOR("tt", 500, 640, 350)}
<rect x="164" y="104" width="672" height="522" rx="30" fill="url(#tt-wood)"/>
<rect x="196" y="136" width="608" height="458" rx="14" fill="#ece3cf" stroke="#c9bda3" stroke-width="2"/>
<circle cx="440" cy="365" r="222" fill="url(#tt-metal)" stroke="#9a9284" stroke-width="2"/>
<g id="tt-vinyl" opacity="0"><g id="tt-spin"><circle cx="440" cy="365" r="208" fill="#141212"/>{grooves}{specks}
 <circle cx="440" cy="365" r="74" fill="#b4322a"/><circle cx="440" cy="365" r="62" fill="none" stroke="#f1dcb6" stroke-width="3"/>
 <path id="tt-lbl" d="M380 365 A60 60 0 1 1 500 365 A60 60 0 1 1 380 365" fill="none"/>
 <text font-family="Mono" font-size="13" fill="#f4dfbd" letter-spacing="3"><textPath href="#tt-lbl">DAN’S LAB · SIDE A · 33⅓ · DANCE ·</textPath></text>
 <text x="440" y="358" text-anchor="middle" font-family="Hand" font-size="26" fill="#f4dfbd">their song</text></g></g>
<path d="M300 210 A208 208 0 0 1 560 190" fill="none" stroke="#fff" stroke-width="10" opacity=".08" stroke-linecap="round"/>
<path d="M330 540 A208 208 0 0 0 600 500" fill="none" stroke="#fff" stroke-width="8" opacity=".06" stroke-linecap="round"/>
<circle cx="440" cy="365" r="7" fill="#d8d2c6"/>
<g id="tt-armshadow" opacity=".45" filter="url(#tt-blur)" transform="translate(16 18)"><g class="armrot">{arm.replace('url(#tt-metal)','#000').replace('#e9e1cf','#000').replace('#5b3b2b','#000')}</g></g>
<g id="tt-arm"><g class="armrot">{arm}</g></g>
<g transform="translate(730 548)"><rect x="-46" y="-22" width="92" height="44" rx="8" fill="#d8ceb8" stroke="#b5a98f"/><text x="0" y="6" text-anchor="middle" font-family="Mono" font-size="14" fill="#5a4a36">33 45 78</text></g>
<circle cx="250" cy="560" r="20" fill="#3b2a20"/><circle cx="250" cy="560" r="12" fill="#e9dfc9"/>
''', SOFT("tt") + '<filter id="tt-blur"><feGaussianBlur stdDeviation="5"/></filter>'
     '<linearGradient id="tt-wood" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8a4c26"/><stop offset="1" stop-color="#4f2711"/></linearGradient>'
     '<linearGradient id="tt-metal" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f1efe9"/><stop offset=".5" stop-color="#b9b3a7"/><stop offset="1" stop-color="#e6e2da"/></linearGradient>')

# ---------------------------------------------------------------- smartphone (generic, no brand)
ICONS = {
 "call": ("#34c759", '<path d="M-12 -14h6l3 8-4 3a16 16 0 0 0 8 8l3-4 8 3v6a3 3 0 0 1-3 3A26 26 0 0 1-15 -11a3 3 0 0 1 3-3z" fill="#fff"/>'),
 "messages": ("#30b0f0", '<path d="M-16 -12h32v20h-18l-10 8v-8h-4z" fill="#fff"/>'),
 "scores": ("#1f8a4c", '<circle r="15" fill="#fff"/><path d="M0 -7l7 5-3 8h-8l-3-8z" fill="#1f8a4c"/>'),
 "music": ("#ff3b5c", '<path d="M-6 10V-12l18-4v20" fill="none" stroke="#fff" stroke-width="4"/><circle cx="-10" cy="10" r="5" fill="#fff"/><circle cx="8" cy="6" r="5" fill="#fff"/>'),
 "internet": ("#2f7cf6", '<circle r="15" fill="none" stroke="#fff" stroke-width="3"/><path d="M-15 0h30M0-15c7 7 7 23 0 30M0-15c-7 7-7 23 0 30" fill="none" stroke="#fff" stroke-width="2.5"/>'),
 "money": ("#f2b233", '<circle r="15" fill="#fff"/><text y="7" text-anchor="middle" font-family="Inter" font-weight="700" font-size="20" fill="#c98a12">$</text>'),
 "ai": ("#ff8a3d", '<path d="M0-17l4 11 11 4-11 4-4 11-4-11-11-4 11-4z" fill="#fff"/>'),
 "news": ("#e8e3d8", '<rect x="-14" y="-14" width="28" height="28" rx="3" fill="#333"/><path d="M-9-7h18M-9 0h18M-9 7h11" stroke="#fff" stroke-width="2.5"/>'),
 "friends": ("#8e5cf6", '<circle cx="-6" cy="-6" r="6" fill="#fff"/><circle cx="8" cy="-4" r="5" fill="#fff"/><path d="M-16 13c2-8 18-8 20 0zM2 13c1-6 14-7 16 0z" fill="#fff"/>'),
 "travel": ("#13b5c8", '<path d="M-16 4l32-14-10 26-6-9z" fill="#fff"/>'),
 "business": ("#6b4b3a", '<rect x="-15" y="-7" width="30" height="20" rx="3" fill="#fff"/><path d="M-6-7v-4h12v4" fill="none" stroke="#fff" stroke-width="3"/>'),
}
app = lambda k, x, y, s=1: f'<g transform="translate({x} {y})"><g id="ph-{k}" class="ph-app"><rect x="-34" y="-34" width="68" height="68" rx="17" fill="{ICONS[k][0]}"/>{ICONS[k][1]}</g></g>'
dock = "".join(app(k, 92 + i * 79, 762) for i, k in enumerate(["call", "messages", "scores", "music"]))
grid = "".join(app(k, 92 + (i % 4) * 79, 250 + (i // 4) * 110) for i, k in enumerate(["internet", "money", "ai", "news", "friends", "travel", "business"]))
glabels = "".join(f'<text x="{92+(i%4)*79}" y="{250+(i//4)*110+52}" text-anchor="middle" font-family="Inter" font-size="13" fill="#fff" class="ph-lbl" id="ph-l-{k}">{t}</text>'
                  for i, (k, t) in enumerate([("internet", "Internet"), ("money", "Money"), ("ai", "AI"), ("news", "News"), ("friends", "Friends"), ("travel", "Travel"), ("business", "Business")]))
svg("phone", 420, 860, f'''
<rect x="4" y="4" width="412" height="852" rx="66" fill="url(#ph-edge)"/>
<rect x="14" y="14" width="392" height="832" rx="57" fill="#0d0d10"/>
<rect x="24" y="24" width="372" height="812" rx="48" fill="url(#ph-wall)"/>
<circle cx="120" cy="220" r="210" fill="#ffb07a" opacity=".18"/><circle cx="330" cy="640" r="240" fill="#7a3cff" opacity=".14"/>
<rect x="150" y="40" width="120" height="34" rx="17" fill="#000"/>
<text x="62" y="64" font-family="Inter" font-weight="700" font-size="18" fill="#fff">12:05</text>
<text x="210" y="160" text-anchor="middle" font-family="Inter" font-weight="700" font-size="64" fill="#fff" opacity=".92" letter-spacing="-2">12:05</text>
<text x="210" y="190" text-anchor="middle" font-family="Inter" font-size="16" fill="#fff" opacity=".7">Friday, 6 November</text>
<g id="ph-grid">{grid}{glabels}</g>
<rect x="40" y="716" width="340" height="92" rx="30" fill="#ffffff2e"/>
<g id="ph-dock">{dock}</g>
<rect x="150" y="818" width="120" height="6" rx="3" fill="#fff" opacity=".8"/>
''', '<linearGradient id="ph-edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#d9d4cc"/><stop offset=".5" stop-color="#6d6863"/><stop offset="1" stop-color="#c2bcb3"/></linearGradient>'
     '<linearGradient id="ph-wall" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4a2a3e"/><stop offset=".55" stop-color="#2a1a2e"/><stop offset="1" stop-color="#1b1430"/></linearGradient>')

# ---------------------------------------------------------------- the Moon, 20 July 1969
craters = "".join(f'<circle cx="{f(x)}" cy="{f(y)}" r="{f(r)}" fill="#9d978c" opacity=".55"/><circle cx="{f(x+r*.18)}" cy="{f(y+r*.18)}" r="{f(r*.8)}" fill="#b9b3a6" opacity=".5"/>'
                  for x, y, r in [(360,180,34),(470,130,18),(520,250,46),(400,300,22),(300,260,16),(560,160,14),(440,220,10),(330,360,26),(500,350,18)])
stars = "".join(f'<circle cx="{R.uniform(0,900):.0f}" cy="{R.uniform(0,560):.0f}" r="{R.uniform(.8,2.2):.1f}" fill="#fff" opacity="{R.uniform(.3,.9):.2f}"/>' for _ in range(70))
svg("moon", 900, 560, f'''
<g id="mo-stars">{stars}</g>
<circle cx="760" cy="110" r="44" fill="url(#mo-earth)"/><path d="M736 96 Q752 84 770 98 Q760 112 742 110 Z M770 128 Q784 120 792 132 Q780 140 770 128 Z" fill="#5fa86b" opacity=".85"/>
<circle cx="760" cy="110" r="44" fill="url(#mo-shade)"/>
<g id="mo-disc"><circle cx="430" cy="250" r="190" fill="url(#mo-moon)"/>{craters}<circle cx="430" cy="250" r="190" fill="url(#mo-limb)"/></g>
<path d="M0 560 L0 470 Q200 440 420 462 Q640 484 900 452 L900 560 Z" fill="#8c877d"/>
<path d="M0 560 L0 492 Q260 470 460 488 Q680 506 900 486 L900 560 Z" fill="#6f6a61"/>
<g transform="translate(600 410)"><g id="mo-lander">
 <path d="M-46 30 L-62 66 M46 30 L62 66 M-20 36 L-28 66 M20 36 L28 66" stroke="#d9d4c8" stroke-width="5"/>
 <path d="M-76 66 L-48 66 M48 66 L76 66" stroke="#d9d4c8" stroke-width="6" stroke-linecap="round"/>
 <path d="M-52 0 L52 0 L44 36 L-44 36 Z" fill="#c9a44c"/><path d="M-52 0 L52 0 L44 36 L-44 36 Z" fill="url(#mo-foil)" opacity=".5"/>
 <path d="M-36 0 L-28 -42 L28 -42 L36 0 Z" fill="#cfcac0"/><rect x="-14" y="-32" width="28" height="18" fill="#2b2b33"/>
 <path d="M0 -42 L0 -64 M-10 -64 L10 -64" stroke="#d9d4c8" stroke-width="3"/></g></g>
<g id="mo-flag" transform="translate(470 470)"><path d="M0 0 L0 -86" stroke="#e9e4da" stroke-width="3"/><rect x="0" y="-86" width="54" height="34" fill="#e9e4da"/>
 <path d="M0 -86 h22 v18 h-22z" fill="#5a6a9a"/><path d="M22 -80 h32 M0 -64 h54 M0 -58 h54" stroke="#b5463a" stroke-width="3"/></g>
<g transform="translate(380 512) rotate(-12)"><g id="mo-step" opacity="0"><path d="M-18 -10 Q-20 -34 0 -36 Q20 -34 18 -10 L16 22 Q0 34 -16 22 Z" fill="#4a463f"/>
 {"".join(f'<path d="M{-14+i*7} {-28+i%2*4} L{-14+i*7} {16-i%2*4}" stroke="#2f2c27" stroke-width="2.5"/>' for i in range(5))}</g></g>
''', '<radialGradient id="mo-moon" cx=".38" cy=".35"><stop offset="0" stop-color="#f3efe5"/><stop offset="1" stop-color="#c8c2b6"/></radialGradient>'
     '<radialGradient id="mo-limb" cx=".5" cy=".5" r=".5"><stop offset=".75" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".35"/></radialGradient>'
     '<radialGradient id="mo-earth" cx=".35" cy=".35"><stop offset="0" stop-color="#7cc2ff"/><stop offset="1" stop-color="#1d4f8f"/></radialGradient>'
     '<linearGradient id="mo-shade" x1="0" x2="1"><stop offset=".45" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".75"/></linearGradient>'
     '<linearGradient id="mo-foil" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
print("art:", sorted(p.name for p in out.iterdir()))
