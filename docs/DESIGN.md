# StreamStudio — Design Reference (reverse-engineered)

Working notes from 16 reference frames Dan supplied (aiTrends, AIS, Dopamine Digital, RoboNuggets,
a pixel-art avatar scene, plus raw app captures). Everything below is what StreamStudio must be
able to produce live, inside the Base card, without post-production.

## 1. What the references are, and what made them

| # | Frame | Pattern | Likely tooling |
|---|---|---|---|
| 1 | WhatsApp voice note in phone frame, teal glow | **Device mockup** scene: phone frame centered on dark radial glow, screen content is a recording, overlay card on top | Screen Studio / Rotato-style device frame |
| 2 | Codex app, blue robot peeking in from the right | **Raw capture + mascot**: plain screen share, animated mascot sticker at the frame edge | Screen capture + sticker overlay |
| 3 | Telegram wallet, portrait crop | **Portrait content in landscape**: 9:16 phone screenshot on dark blurred background | Screen Studio / CapCut |
| 4 | Skool page, presenter bottom-left, purple bezel | **Browser + facecam**: window in a rounded card, purple gradient bezel, camera card bottom-left | Screen Studio / Tella |
| 5 | Claude app, no camera | **Raw capture**: no bezel, cursor and tooltip visible | Plain screen recording |
| 6 | "Your AI operating system, *live*." 1/29 | **Keynote slide**: numbered section label, serif-italic accent word, embedded screenshot, presenter bottom-left | Custom HTML/Keynote deck + Screen Studio |
| 7 | Pixel-art dev thinking under lightbulbs | **Full-frame AI avatar scene**: no capture at all, the avatar *is* the video, animated props | AI image + animation (Higgsfield/Kling/Runway) |
| 8 | aiTrends avatar + "+ Story script / + Voiceover…" | **Avatar + glass list, typewriter** | HeyGen-style avatar video + motion-graphics overlay |
| 9 | Rubric Second Brain graph + MENU panel + facecam | **App + visible Menu card**: this is our Menu card toggled ON, a top-right panel with sliders and toggles | Live app capture, camera card bottom-left |
| 10 | "4 things we'll build." 2×2 screenshot grid | **Slide: card grid** with numbered pills | Same deck as 6 |
| 11 | AIS presenter + tilted phone mockup left | **Camera full-frame + floating device** | Real camera + 3D phone mockup overlay |
| 12 | aiTrends avatar + floating app icons + stat pill | **Avatar + icon cloud + pill** | Motion-graphics overlay |
| 13 | AIS presenter small left, landing page large, blue bezel | **Facecam side + browser**: camera card ~18% wide on the left edge, content card right | Screen Studio / Tella |
| 14 | AIS presenter + "Charles Hayes" → "Women's Marketing Coach" | **Connector callout**: profile chip wired by a glowing line to a label | Motion graphics (After Effects/CapCut template) |
| 15 | aiTrends avatar + stacked "242K views" thumbnails | **Avatar + glass list of thumbnails** | Motion graphics |
| 16 | "Part 01 Audit and clean up *your bots*." + feature cards | **Slide: hero number + live preview + 3 feature cards** | Same deck as 6 |

Two of the three creators are *real* on camera, one (aiTrends) is a photoreal AI avatar that never
touches a camera. The pixel-art frame is a third style: the avatar scene is the whole video.
StreamStudio has to cover all three with the Avatar card: live camera, AI avatar, full-frame avatar scene.

## 2. The grammar every frame follows

Every reference frame is the same three layers. This is the Base → Main → overlays structure
Dan described, confirmed by the examples:

```
Layer 0  BEZEL      a gradient or dark field filling the Base card (purple, blue, teal-glow, near-black)
Layer 1  CONTENT    one big rounded card: browser window, slide, app, device mockup, or the avatar full-frame
Layer 2  PRESENCE   the presenter: camera card or avatar card, almost always bottom-left
Layer 3  OVERLAYS   glass panels, lists, pills, callouts, device mockups, icons, mascot, the Menu
```

### Measured from the frames (as fractions of a 16:9 frame)

| Element | Value | Source frames |
|---|---|---|
| Bezel padding around the content card | 2–4 % of width (≈ 40–75 px at 1080p) | 4, 6, 13 |
| Content card corner radius | ≈ 1 % of width (12–16 px at 1080p), 20 px on slides | 4, 6, 13 |
| Presenter card, bottom-left | **16 % of width**, ≈ 34 % of height (≈ 4:5 portrait-ish), left margin 5 %, bottom margin 10 % | 6, 10, 16 |
| Presenter card, side layout | 18 % wide, vertically centred, left margin 2 % | 13 |
| Presenter card, large | 20 % wide, bottom-left, shadow, radius 16 px | 4, 9 |
| Presenter card border | 2 px white at 90 % (RoboNuggets) or none with soft shadow (Dopamine) | 9, 4 |
| Presenter card radius | 16–24 px at 1080p | all |
| Glass overlay panels | rgba(20,20,24,.55) + backdrop-blur 16–24 px, 1 px rgba(255,255,255,.12) border, radius 14–18 px | 8, 12, 15 |
| Stat pill | solid accent (coral #E8674A) or glass, radius 999, 15 px text, icon left | 12 |
| Menu panel (ON) | top-right, 12 % wide, dark glass, section labels in 10 px caps, segmented toggles, sliders | 9 |
| Slide section label | mono/caps, 11 px, tracking .2em, "01 / EVERY BOT, ONE DASHBOARD", counter "1 / 29" top-right | 6, 10, 16 |
| Slide headline | 64–72 px sans, with one accent word in serif *italic* | 6, 10, 16 |
| Slide hero number | 160 px, coral, with "PART" micro-label above | 16 |

### Palettes seen

| Name | Bezel | Accent | Where |
|---|---|---|---|
| **Violet** (Dopamine) | radial #3b2466 → #141216, with a faint grid | coral #E8674A, lavender italic | 6, 10, 16, 4 |
| **Ink** (AIS) | #0b3a9c → #050a1a blue | white, electric blue #1e6cf5 | 13, 11, 14 |
| **Ember** (aiTrends) | set lighting, red/black | red hoodie, warm glass | 8, 12, 15 |
| **Teal glow** | #0d1716 with radial teal rgba(0,255,220,.15) | WhatsApp green | 1 |
| **Mono dark** | #171717 flat | none | 2, 5 |

### Typography seen
- Headlines: Inter / SF-style grotesque, tight tracking, 600–700.
- Accent word: a serif italic (Instrument Serif / Newsreader style) inside a sans headline.
- Labels: mono or sans caps, wide tracking, small.
- Lists in glass panels: 28–32 px white sans, "+" prefix, one line each, typed in.

### Motion seen (inferred from stills)
- Lists type in line by line (8), thumbnails stack in with a slight stagger (15).
- Icons float in with drift and a soft shadow (12).
- Connector callouts draw the line then pop the label (14).
- Device mockups enter tilted (−8° Y) and settle (11), or sit centred with a glow (1).
- Presenter card is static; the content card does Screen-Studio-style zoom to the cursor on clicks (4, 13).
- Mascot peeks in from the frame edge and idles (2).

## 3. What StreamStudio builds from this

### Scene templates (Base card presets, landscape + portrait variants)
1. **Browser + Cam** — bezel, content card, presenter bottom-left 16 %. (4, 13)
2. **Slide** — built-in slide renderer with the section label / accent-italic headline / counter system; presenter bottom-left. (6, 10, 16)
3. **App + Menu** — live app capture with the Menu card toggled ON, presenter bottom-left. (9)
4. **Avatar stage** — avatar full-frame, overlays float on it. (8, 12, 15)
5. **Avatar scene** — generated background plate + avatar, no capture. (7)
6. **Device** — phone/laptop mockup centred on a glow, screen fed by a capture or a file. (1, 3, 11)
7. **Raw** — no bezel, capture fills the Base card, optional mascot. (2, 5)

### Overlay library (live, animated, all in the compositor)
- Glass panel (list / bullets, typewriter), thumbnail list, stat pill, connector callout, icon cloud,
  device mockup (iPhone, MacBook, browser chrome), mascot sticker, lower third, chapter title, progress bar.
- Each overlay is a React component drawn into the output canvas; props editable from the Menu;
  enter/exit animations are driven by hotkeys or the Menu.

### Menu card, ON state
Styled after frame 9: top-right dark glass, caps section labels, segmented controls and sliders.
This is the "visible" skin; the default state is fully transparent in the output.

### Slide engine
Slides are a Main-card source rendered from Markdown/JSON in the house style, so Dan never opens Keynote:
section label, headline with `*accent*` italic, body, media slot, feature cards, counter. Themes = the palettes above.

### Avatar card, three modes
- **Camera** — webcam with background removal, rounded card, border/shadow presets.
- **AI avatar (live)** — a 2D/VRM avatar driven by the mic (free, local). Photoreal live avatars
  (HeyGen Streaming Avatar, WebRTC) are an optional paid provider behind the same card.
- **Avatar scene** — a generated plate (Higgsfield/Kling, paid, opt-in) plays as the Main source with the avatar card hidden.

## 3b. Dan's own avatar asset (from the lip-sync test video)

`Dans_Lab___Brian_Landscape_Precision_Lip_Sync_Test.mp4`: 1920×1080, 25 fps, H.264 + AAC 48 kHz, 11.8 s,
with an embedded `mov_text` subtitle track ("Welcome to Dan's Lab. I'm Dan, and this is where we explore
artificial intelligence, test new tools, and turn ideas into things that work.").

What it is: a **photoreal, pre-rendered talking avatar** on a still studio plate (teal LED strips, plants,
desk, monitor). The body and background don't move; only the face animates to the voice. This is the
aiTrends model (frames 8, 12, 15), not a live camera.

Consequences for the Avatar card:
1. **Scripted mode is the primary mode.** A segment of script → cloned voice → lip-sync clip (paid, generated
   once, cached). The stage plays the clip while the Main card shows the matching content. Dan triggers
   scenes and overlays live, or they fire from the script's timing. The subtitle track doubles as the
   caption source, so captions come for free.
2. **Full-frame or cut-out.** The studio plate is a finished background, so "Avatar stage" uses it full-frame
   with overlays on top. For "Browser + Cam" the avatar is cut out (background removal on the still plate,
   once) and placed in the 16 % presenter card.
3. **Live mode comes second**: a streaming avatar provider (HeyGen Streaming Avatar, WebRTC) or the local
   mic-driven 2D/VRM fallback, behind the same card and the same hotkeys.
4. **Per-orientation avatar clips.** `Dans_Lab___Brian_Studio_Avatar_1.mp4` is the portrait twin: 1080×1920,
   25 fps, 11 s, same studio set, framed close (head and shoulders, hands gesturing at the bottom edge, so
   the body moves, not just the face), no subtitle track. So every avatar segment exists as a 16:9 wide shot
   and a 9:16 close-up, and the orientation toggle swaps the clip, not just the layout. Portrait clips are
   framed for the Shorts safe area: the face sits in the top 45 %, leaving the lower half for overlays.
5. **25 fps source** on a 30 fps stage: the compositor must resample or run the stage at 25 fps when an
   avatar clip is the main source. Output presets will offer 25 and 30.

## 4. Tech notes from the research
- **Browser → RTMP** is a known, working pattern: canvas.captureStream → MediaRecorder (WebM) → WebSocket →
  ffmpeg → RTMP. Known hazard: background tabs throttle timers and stall the stream, so the stage must
  run in a foreground window (or a dedicated Chromium on the Mac Studio) and never in a hidden tab.
  (Mux, "The state of going live from a browser")
- **Photoreal live avatars**: HeyGen's Streaming Avatar API uses WebRTC and runs through a Node demo server;
  voice-driven mode goes via an OpenAI Realtime setup, so it is a paid, cloud-dependent provider. We keep it
  as an optional plug-in, and ship the local 2D/VRM avatar first.
- **Screen Studio / Tella** are the look for Browser + Cam: custom backgrounds, rounded windows with
  padding and shadow, auto-zoom on clicks, animated cursor, camera reframing. StreamStudio does this live.

Sources:
- [Mux — The state of going live from a browser](https://www.mux.com/blog/the-state-of-going-live-from-a-browser)
- [HeyGen — Streaming Avatars API](https://docs.heygen.com/docs/streaming-avatars-api)
- [Tella vs Screen Studio](https://www.tella.com/alternatives/screen-studio.md)
- [fbsamples/Canvas-Streaming-Example](https://www.github.com/fbsamples/Canvas-Streaming-Example)


## Lip-sync guard

Viewers forgive a small talking-head bubble; they never forgive a large face whose lips don't match the words.

| Voice heard | Face allowed | Cue on air |
|---|---|---|
| The clip's own audio (HeyGen render of these words) | Full frame or large | as scripted |
| Separate narration (cloned/dubbed voice, VO track) | Small card only | `avatar` → `pip`, `duo` → `content` |
| No voice (timed segment) | Small card only (listening face) | same as narration |

- **Small card:** bottom-left. Landscape is 15% of the width, square in pixels (circle). Portrait is 30% of the width. The 3:4 portrait shape is optional. The card never exceeds 6% of the frame area. The face is centred: cover, a scale of about 1.4, origin at 32% from the top. The card has a white ring and a soft shadow.
- **What sits behind `pip`:** the studio plate with the table objects. The focus rule keeps the studio whenever there is no Main card. The seated cut-out is used only when the face is full frame.
- **Code:**
  - `director/types.ts` (`lipsMatch`, `guardCue`, `MAX_UNSYNCED_AREA`);
  - `director/cueLayouts.ts` (`pipRect`, `guardLayout`);
  - `render/lipsync.py` for offline renders.
- **Script panel:** every segment shows `lips ✓/✕` and the cue it will really play as. The header toggles the circle or portrait shape.

## Scenes

The model has four levels:
- **Show:** the channel, with its studio, avatar, opener and closer.
- **Episode:** one video or stream, with its script.
- **Scene:** a reusable set. It holds the backdrop, the card layout in both orientations, and the media cards.
- **Cue:** the camera move the Director makes inside a scene.

**Collections:** Openers, Talk, Demo, Data and Social, shown in that order in the strip under the stage.

**Scene strip:**
- Each scene has a live thumbnail. Keys 1–9 follow strip order.
- Drag a thumbnail to reorder it, or drop it on another collection to move it there.
- Double-click a name to rename it. Hover a thumbnail to duplicate or delete it.
- Each collection has a **+** button to make a new scene from a template.
- Export and Import move the library as a JSON file.

**Storage:** the source of truth is `/api/scenes` (SQLite on the Mac Studio).
- The server copy wins on load.
- Each change is written back, debounced by 500 ms per scene.
- The browser keeps a localStorage copy as the fallback. The hosted demo has no server, so it uses only that copy.

**Templates:**
- World of AI (Openers);
- Studio Desk, Studio + Circle, Avatar Stage (Talk);
- Browser + Cam, Side Cam, App + Menu (Demo);
- Raw (Data).
