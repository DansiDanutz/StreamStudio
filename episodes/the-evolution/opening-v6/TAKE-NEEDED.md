# The Evolution — opening v5: the take we need

No existing take matches these words. Checked: `dan-landscape-test.mp4` (only "Welcome to Dan's Lab. I'm Dan. And this is where we explore artificial intelligence…") and all 36 Episode 1 avatar clips (NervixPay / WorldCup / JEV / Nervix Space lines). None contain the opening narration, so nothing has been dubbed, frozen or substituted.

## Record ONE continuous take (≈ 75–84 s)

Same look as `dan-landscape-test.mp4`: 1920×1080, 25 or 30 fps, Dan centred at the desk, head in the upper third (the composition crops it into a 280×400 portrait card, then a 1100×1080 side panel, so keep hands and head inside the middle 55% of the frame width). Natural delivery, small pause (≈0.5 s) between the numbered lines. No cuts — the presenter card moves and resizes over the whole take.

1. Do you remember how we called our parents to ask them something? Finger in the hole, all the way to the stop, and back.
2. Do you remember writing a letter? By hand, to the girl you loved. Then waiting weeks for an answer.
3. Do you remember listening to the radio? The night Armstrong landed on the Moon, over six hundred million people followed it live.
4. And do you remember putting on a record? The needle drops, a little crackle, and our parents start to dance.
5. Now. We have one gadget, and it has it all. The call, the letter, the radio, the music.
6. And what else did it swallow? The internet. Money. AI. News. Friends. Travel. Business.
7. I'm Dan, and this is Dan's Lab. An entrepreneur in love with technology and AI. I'm building a community that learns to make life easier, to build its own business, and to be independent.
8. Because we have never been this rich. Never had this much school, this much information, this many resources to make our dreams real.
9. So today: how these objects evolved, and how AI, with the internet, the phone and digital money, can grow our technology, our health, our education and our financial freedom. Let's dive in. The Evolution.

Either route keeps lip sync authentic: record it on camera, or (only with your approval, since it costs) render it as a HeyGen avatar clip from your own recorded audio of these lines.

## Drop-in (Mac Studio, ~/StreamStudioData/the-evolution-opening)

```
cp <take>.mp4 take.mp4
whisper take.mp4 --model medium.en --word_timestamps True --output_format json --output_dir .
python3 retime.py take.json        # refuses the take if any line doesn't match the script
python3 build.py --final           # cues move to Dan's real words; guide captions + slot removed
# render index.html with the HyperFrames renderer (or: python3 render.py out.mp4), then mux take audio at -14 LUFS over sound.wav
```

Every artifact cue lives in `cues.json` as `[line, word, offset]`, so changing a reveal is a one-line edit; each artifact is its own `<article class="card" data-artifact=…>` with its own overlay and tweens in `composition.html.in`.
