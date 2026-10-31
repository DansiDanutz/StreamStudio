# Table objects — ChatGPT prompts

Workflow: one chat. Generate Claude first. When it is approved, generate the others in the same chat, so the style
carries over. Attach each tool's official logo PNG with its prompt (Hermes has no logo: its prompt describes the shape).
Landscape 3:2. Download at full size. Save as `objects/<tool>/still.png`.

## 1. Claude (send first)
Studio product render on a pure black background. One 3D emblem shaped exactly like the attached logo, made of dark smoked glass with a warm coral-terracotta glow inside it, like light trapped in crystal. Thin warm amber highlights on the edges and a subtle teal rim light from the left. It floats 2 cm above a thin glowing disc of light, which lies on a small patch of dark polished walnut. The disc casts a soft reflection on the wood. The walnut fades to black within a hand's width, and everything else is pure black. The emblem is centred, takes up about one third of the image height, and sits in the lower half of the image. Camera at desk height, 35 mm lens, slight three-quarter angle. Cinematic, photoreal, sharp. No text, no wordmark, no other objects.

## 2. Codex
Same style, lighting, camera, framing and black background as the previous image. This time the emblem is shaped exactly like the attached logo, with a cool white-mint glow inside the smoked glass. No text.

## 3. Grok + GrokBot
Same style, lighting, camera, framing and black background as the previous images. The emblem is shaped exactly like the attached logo, in dark smoked glass with a deep red core glow and silver edges. A small, friendly robot head (GrokBot) sits on the right side of the light disc, at about one quarter of the emblem's height, made of the same smoked glass with two glowing red eyes. No text.

## 4. Hermes
Same style, lighting, camera, framing and black background as the previous images. The emblem is an original design, not an existing logo: a sealed envelope with a pair of small swept-back wings, in smoked glass with a deep violet glow inside. It is the messenger of an AI agent fleet. No text.

## 5. Kimi
Same style, lighting, camera, framing and black background as the previous images. The emblem is shaped exactly like the attached logo, with a clear electric-blue glow inside the smoked glass. No text.

## 6. GLM
Same style, lighting, camera, framing and black background as the previous images. The emblem is shaped exactly like the attached logo, with a green-teal glow inside the smoked glass. No text.

## Fix-up lines (add if needed)
- The logo is distorted: "Keep the logo's proportions exactly as in the attached file; only the material changes."
- The background isn't black: "Everything outside the small patch of wood must be pure #000000."
- The emblem is too big or small: "The emblem should be about one third of the image height."
- It doesn't match the others: "Match the exact glass, edge light and disc of the Claude image."

## Then (video)
Animate each approved still with image-to-video (Sora in ChatGPT, or Kling/Veo/Higgsfield). Use the three motion prompts in `docs/scripts/intro-world-of-ai.md` (arrive 2 s, idle 4 s loop, react 1 s), with the camera locked and a black background.
