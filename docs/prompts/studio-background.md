# Studio background — generation prompts

Base-card / Main-card background plate for Dan's stage. Must match the existing avatar clips
(dark studio, teal LED strips, warm amber lamps, desk-height camera) and keep the centre empty.

Brand priority: NervixPay (hero neon) › Fake-Real.live (live on monitor) › KryptoStack Exchange (sign) ›
iRise Coin (gold coin in a glass case) › Players Poker Club (chips, cards, small plaque).

## Master (Nano Banana / Gemini)
Wide cinematic photo of an empty high-end creator studio, 16:9, shot at desk height with a 35mm lens, nobody in frame, the center of the frame left clear for a presenter to sit at a dark walnut desk. Moody dark teal-and-charcoal walls with black acoustic slat panels, teal LED strip lighting along the shelves and under the desk, two warm amber Edison filament lamps for contrast. Left wall: a large glowing neon sign reading "NervixPay" in clean white-and-electric-blue letters, under it a smaller brushed-metal sign reading "KryptoStack Exchange". Right side: a dark desk setup with two monitors, the left monitor showing a dark fact-checking web dashboard titled "Fake-Real.live" with green "REAL" and red "FAKE" verdict badges, the right monitor showing a crypto trading chart with a payments dashboard. On the shelves: a glass display case with a single large gold coin engraved "iRise", a neat stack of black-and-gold poker chips and two decks of cards beside a framed "Players Poker Club" plaque, a small camera, a mechanical keyboard, trailing pothos plants, a few hardcover books about AI and startups. Subtle: a small AI robot figurine and a GPU server rack with soft blue status lights in the back corner. Premium YouTube studio aesthetic, photoreal, 8k detail, soft volumetric light, shallow depth of field with the background slightly out of focus and the desk in focus, no people, no text other than the signs named.

## Midjourney v7
empty high-end YouTube creator studio, 16:9, 35mm, desk-height camera, center of frame clear for a presenter, dark walnut desk, charcoal and deep teal walls, black acoustic slat panels, teal LED strips on shelves and under desk, warm amber Edison lamps, large white-and-electric-blue neon sign "NervixPay" on left wall, smaller brushed metal sign "KryptoStack Exchange" below it, dual monitors on the right showing a dark fact-checking dashboard "Fake-Real.live" with green and red verdict badges and a crypto trading chart, glass case with a large gold coin "iRise", black-and-gold poker chips and two card decks next to a framed "Players Poker Club" plaque, pothos plants, AI and startup books, small robot figurine, GPU server rack with blue status lights in the back corner, cinematic, photoreal, volumetric light, shallow depth of field, desk in focus, no people --ar 16:9 --style raw --v 7 --q 2 --no people, person, face, watermark, extra text

## GPT Image / Imagen
Photoreal, 16:9, empty premium creator studio for a tech and crypto YouTuber. Camera at desk height, 35mm, center of frame clear so a presenter can be composited at a dark walnut desk. Lighting: dark teal and charcoal palette, teal LED strips along shelves and under the desk, two warm amber Edison filament lamps, soft volumetric haze, shallow depth of field with the desk sharp and the back wall soft. Left wall: large neon sign with the exact text "NervixPay" in white and electric blue; below it a brushed-metal sign with the exact text "KryptoStack Exchange". Right side: two monitors; the left displays a dark website header reading exactly "Fake-Real.live" with green REAL and red FAKE badges; the right shows a crypto candlestick chart and a payments dashboard. Shelves: a glass display case holding one large gold coin engraved "iRise"; black-and-gold poker chips stacked beside two decks of cards and a small framed plaque reading exactly "Players Poker Club"; a compact camera, mechanical keyboard, trailing pothos plants, hardcover books on AI and entrepreneurship; a small AI robot figurine; a GPU server rack with blue status lights in the back corner. No people. Render the sign text exactly as written and nothing else.

## Variant B — blank panels (recommended for the live stage)
Replace brand mentions with: a large rectangular unlit neon sign panel, blank, matte black with a thin electric-blue light tube border; a blank brushed-metal plaque below it; two monitors with plain dark empty screens and a faint blue glow; a plain gold coin with no engraving; a small blank black framed plaque. Logos are composited in StreamStudio (sharp, swappable per video).

## Portrait companion
Same prompts at 9:16 (`--ar 9:16`), plus: "vertical composition, the shelf with the glass coin case and poker chips framed at eye level on one side, neon sign visible in the upper third, lower third of the frame kept visually quiet for captions."

## Checklist
- 4 generations each; judge on centre clearance, teal match with the avatar clips, sign legibility.
- Export ≥ 3840×2160 (upscale if needed) for the click-zoom effect.
- Winners (landscape + portrait) → `assets/studio/`. A 10 s "living plate" (LED flicker, moving charts) is made from the still later.

## Round 1 result (2026-10-30)
GPT Image won (assets/studio/plate-landscape-v1-gpt.png, 1680×945). Gemini: good brands, bad composition (corner, no desk centre). Midjourney: rejected.
v2 fixes: desk only in bottom third, camera at seated chest height, Fake-Real monitor fully right of centre, 4K.

## Round 2 result
Chosen: assets/studio/plate-landscape-v2-final.png (frontal, desk bottom third, monitors fully right, clear centre).
Backup: plate-landscape-v2-alt.png. Still 1680×945 → needs a 4K upscale before use. Portrait plate still to generate.
