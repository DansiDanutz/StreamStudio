# DansLab logo-reveal intro (HyperFrames)

Ported 1:1 from the channel's existing intro (DansiDanutz/Claude-Youtube, `remotion/src/lib/danslab.tsx`
`DlLogoAnimated` + `SiteBg`, `shots/danslab-ep03/TIntro.tsx`): starfield, the red tile with the serif D and the
blinking gold cursor, ring pulse, sparks, shine sweep, then the title card (kicker, title, red→gold rule, tagline).

    python make_intro.py "DANSLAB" 'Build it. Show it. <em>Sell it.</em>' "Tagline"
    npx hyperframes render comps/intro -o out/intro.mp4 -f 30 -q delivery

Fonts: @fontsource Newsreader 500/600/500-italic, JetBrains Mono 500 (copied next to index.html).
Sound (from Claude-Youtube `media/library/sfx`, ElevenLabs-generated, owned): riser-soft 0.0 s, pop-reveal 0.57 s,
warm-shimmer 1.3 s, whoosh-soft 3.35 s, impact-deep-soft 4.0 s; mixed to −18 LUFS, fade out from 6.4 s.
