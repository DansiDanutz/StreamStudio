"""Generate the channel intro locally from its pinned GSAP composition and sound effects."""
from __future__ import annotations

import hashlib
import html
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from ..core.config import Settings
from . import channel_files, intro_template, profiles

CUES = {"riser": 0, "pop": 567, "shimmer": 1300, "whoosh": 3350, "impact": 4000}


def selected_fonts(profile: profiles.Profile) -> dict:
    look = profile.look.fonts if profile.look else {}
    fallback = next((look[slot] for slot in ("body", "display", "small") if slot in look), None)
    return {slot: profile.intro.fonts.get(slot) or look.get(source) or fallback
            for slot, source in (("serif", "display"), ("serif_bold", "display"),
                                 ("serif_italic", "body"), ("mono", "small"))}


def generate(s: Settings, profile: profiles.Profile) -> str:
    from playwright.sync_api import sync_playwright

    intro = profile.intro
    title = html.escape(intro.title or profile.name)
    if intro.title_em:
        title += " <em>" + html.escape(intro.title_em) + "</em>"
    markup = intro_template.composition(
        html.escape(intro.kicker), title, html.escape(intro.tagline),
        html.escape(intro.logo_letter or profile.name[0]), intro.colours.model_dump(),
    )
    sound = profile.sound or profiles.Sound()
    gsap = s.cards_dir / "node_modules/gsap/dist/gsap.min.js"
    if not gsap.is_file():
        raise ValueError("run npm ci in the cards workspace before generating an intro")
    with TemporaryDirectory(dir=s.cards_dir) as tmp, sync_playwright() as pw:
        d = Path(tmp)
        fonts = selected_fonts(profile)
        for slot, default_name in zip(fonts, intro_template.FONT_FILES, strict=True):
            source = (channel_files.verify(s, fonts[slot], kind="intro_font") if fonts[slot]
                      else s.assets_dir / "brand" / "fonts" / default_name)
            name = slot + source.suffix
            shutil.copy2(source, d / name)
            markup = markup.replace(f"url({default_name})", f"url({name})", 1)
        shutil.copy2(gsap, d / gsap.name)
        page_file = d / "index.html"
        page_file.write_text(markup, encoding="utf8")
        browser = pw.chromium.launch(executable_path=s.hyperframes_browser)
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, offline=True)
        page.goto(page_file.as_uri())
        loaded = page.evaluate("""async () => {
            const faces = Array.from(document.fonts);
            await Promise.all(faces.map(face => face.load()));
            return faces.length === 4 && faces.every(face => face.status === 'loaded');
        }""")
        if not loaded:
            raise ValueError("the intro could not load its four selected font faces")
        page.evaluate("""() => { for (const selector of ['.name','.tag','.kick']) {
            const el = document.querySelector(selector);
            el.style.maxWidth = '1760px';
            while (el.scrollWidth > 1760 && parseFloat(getComputedStyle(el).fontSize)>12)
              el.style.fontSize = (parseFloat(getComputedStyle(el).fontSize)-1)+'px';
        }}""")
        inputs = ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:d=7.2"]
        filters = []
        sources = "[1:a]"
        for role, delay in CUES.items():
            if digest := sound.sfx.get(role):
                inputs += ["-i", str(channel_files.verify(s, digest))]
                n = len(filters) + 2
                filters.append(f"[{n}:a]adelay={delay}:all=1[a{n}]")
                sources += f"[a{n}]"
        filters.append(f"{sources}amix=inputs={len(filters)+1}:duration=first:normalize=0,"
                       f"loudnorm=I={sound.levels.intro}:TP=-2:LRA=11,afade=t=out:st=6.4:d=0.8[a]")
        movie = d / "intro.mp4"
        args = [s.ffmpeg_bin, "-v", "error", "-f", "image2pipe", "-framerate", "25", "-i", "-",
                *inputs, "-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[a]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-t", "7.2", "-movflags", "+faststart", str(movie)]
        with subprocess.Popen(args, stdin=subprocess.PIPE) as encoder:
            try:
                for frame in range(180):
                    page.evaluate("t => { window.__timelines.root.seek(t); }", frame / 25)
                    if frame == 135 and not page.evaluate("""() =>
                        ['#root', '.card'].every(q =>
                            Number(getComputedStyle(document.querySelector(q)).opacity) > .9)"""):
                        raise RuntimeError("intro title did not become visible")
                    encoder.stdin.write(page.screenshot(type="jpeg", quality=94))
            finally:
                encoder.stdin.close()
            if encoder.wait():
                raise RuntimeError("channel intro encoding failed")
        with movie.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        channel_files._store(s, movie, ".mp4", digest)
        return digest
