"""Build the DansLab explainer from the original Dan opener and three local Dan voice takes.

Run with the server episode environment. The two example MP4s supply video only.
"""
import argparse
import json
import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright


def encode(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *map(str, args)], check=True)


def duration(path):
    raw = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                   "format=duration", "-of", "csv=p=0", str(path)])
    return float(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("narration", "original", "revised", "output"):
        parser.add_argument(key, type=Path)
    parser.add_argument("--browser", type=Path)
    parser.add_argument("--captions", type=Path, help="Timed SRT matching the supplied voice takes")
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    root = here.parents[2]
    audio = ["-af", "loudnorm=I=-16:TP=-1.5:LRA=9", "-ar", "48000", "-ac", "2",
             "-c:a", "aac", "-b:a", "160k"]
    video = ["-c:v", "libx264", "-crf", "17", "-preset", "fast", "-pix_fmt", "yuv420p", "-r", "25"]
    chapters = json.loads((here / "narration.json").read_text(encoding="utf-8-sig"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output.parent) as tmp, sync_playwright() as pw:
        d = Path(tmp)
        browser = pw.chromium.launch(executable_path=args.browser)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto((root/"server/src/streamstudio/episode/templates/connected-cards.html").as_uri())
        encode("-i", root/"assets/avatar/dan-landscape-test.mp4", "-t", "9.6",
               "-map", "0:v:0", "-map", "0:a:0", "-vf", "scale=1280:720,setsar=1",
               *video, *audio, d/"0.mp4")
        for i, scene in enumerate(chapters):
            voice = args.narration/(scene["id"]+".wav")
            seconds = duration(voice)
            motion = d/"motion.mp4"
            proc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "image2pipe",
                                     "-framerate", "25", "-i", "-", *video, str(motion)],
                                    stdin=subprocess.PIPE)
            try:
                for f in range(math.ceil(seconds*25)):
                    page.evaluate("t => window.seekScene(t)", i*6 + 6*f/(25*seconds))
                    proc.stdin.write(page.screenshot(type="jpeg", quality=94))
            finally:
                proc.stdin.close()
                if proc.wait():
                    raise RuntimeError("could not encode motion cards")
            sources = ["-i", motion, "-i", voice]
            mapping = ["-map", "0:v"]
            if i == 0:
                sources += ["-i", args.original]
                mapping = ["-filter_complex", "[2:v]scale=1280:720,setpts=PTS+5/TB[demo];"
                           "[0:v][demo]overlay=enable='gte(t,5)':shortest=0[v]", "-map", "[v]"]
            if i == 2:
                plate = Image.new("RGB", (1280, 720), "#102029")
                draw = ImageDraw.Draw(plate)
                font = root/"assets/brand/fonts/inter-latin-600-normal.woff2"
                draw.text((35, 58), "One capture. Two directions.", fill="white",
                          font=ImageFont.truetype(str(font), 48))
                label = ImageFont.truetype(str(font), 22)
                draw.text((35, 555), "ORIGINAL   /   RIGHT", fill="white", font=label)
                draw.text((665, 555), "REVISION   /   LEFT", fill="white", font=label)
                plate.save(d/"comparison.png")
                sources += ["-i", args.original, "-i", args.revised,
                            "-loop", "1", "-framerate", "25", "-i", d/"comparison.png"]
                mapping = ["-filter_complex",
                           "[2:v]scale=614:346,pad=iw+4:ih+4:2:2:color=0x85bbad[a];"
                           "[3:v]scale=614:346,pad=iw+4:ih+4:2:2:color=0x85bbad[b];"
                           "[a][b]hstack=inputs=2[pair];"
                           "[4:v][pair]overlay=22:180,setpts=PTS+3/TB[demo];"
                           "[0:v][demo]overlay=enable='gte(t,3)'[v]", "-map", "[v]"]
            encode(*sources, *mapping, "-map", "1:a:0", "-t", str(seconds),
                   *video, *audio, d/f"{i+1}.mp4")
        browser.close()
        listing = d/"list.txt"
        listing.write_text("".join(f"file '{i}.mp4'\n" for i in range(len(chapters)+1)))
        inputs = ["-f", "concat", "-safe", "0", "-i", listing]
        streams = ["-c", "copy"]
        if args.captions:
            inputs += ["-i", args.captions]
            streams += ["-map", "0:v", "-map", "0:a", "-map", "1:s", "-c:s", "mov_text",
                        "-metadata:s:s:0", "language=eng"]
        encode(*inputs, *streams, "-movflags", "+faststart", args.output)


if __name__ == "__main__":
    main()
