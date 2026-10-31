# Table objects — Sora (ChatGPT) prompts

Settings for every clip: upload the object's still (`assets/objects/<id>/still.png`) as the **starting image**,
16:9, 1080p, 5 s, 1 variation. Download each as `<id>-<phase>.mp4` into Downloads; StreamStudio trims, loops,
reverses and mattes them (`object_matte` per frame), so 5 s clips are fine.

Trick for **arrive**: Sora always starts from the still, so it can't make the object appear from nothing. We ask
for the opposite (the object dissolves into light) and **play it backwards**. Reversed, it materialises.

## dissolve  (→ reversed = arrive)
The glass emblem slowly breaks apart into thousands of tiny glowing particles in its own colour, which drift upward and fade into the darkness. The light disc under it dims and goes out. By the end the frame is completely black. Camera perfectly still, no zoom, no pan. Pure black background throughout. No text.

## idle  (looped)
The glass emblem floats gently in place, rising and falling by a centimetre, turning a few degrees left and back. The glow inside it slowly breathes brighter and dimmer, and the light disc beneath shimmers softly. Calm, subtle, continuous motion. Camera perfectly still, no zoom, no pan. Pure black background throughout. No text.

## react
The glass emblem lights up sharply from inside, lifts slightly and settles back, while a ring of light pulses outward across the surface beneath it and fades. One clean pulse, then calm floating. Camera perfectly still, no zoom, no pan. Pure black background throughout. No text.

## Per-object additions (append to each prompt)
- OpenClaw: "The lobster's claws open and close slowly." (idle) / "The lobster raises both claws." (react)
- Grok cluster: "The little robot on the right blinks its red eyes." (idle)
- Hermes: "The small wings flutter gently." (idle)

## Order
Do Claude Code's three first and send them; if they composite well, run the rest.
