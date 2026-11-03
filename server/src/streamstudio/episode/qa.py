"""Sample a source avatar clip at 12.5 Hz and produce review evidence for its exact take."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from ..core.config import Settings
from .preflight import HAAR_CASCADE

SAMPLE_RATE = 12.5


def check_clip(path: Path, s: Settings, sheet: Path) -> dict:
    import cv2
    import numpy as np

    detector = cv2.CascadeClassifier(str(s.assets_dir / HAAR_CASCADE))
    if detector.empty():
        raise ValueError("missing face detector")
    # Letterboxing keeps the same grid and preserves face shape on portrait and landscape inputs.
    args = [s.ffmpeg_bin, "-v", "error", "-i", str(path)]
    video = subprocess.Popen(
        [*args, "-vf", "fps=12.5,scale=480:270:force_original_aspect_ratio=decrease,"
         "pad=480:270:(ow-iw)/2:(oh-ih)/2", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        stdout=subprocess.PIPE,
    )
    faces, changes, mouths = [], [], []
    first = last = worst = None
    largest_change = -1
    count = 0
    try:
        while raw := video.stdout.read(480 * 270):
            frame = np.frombuffer(raw, np.uint8).reshape(270, 480)
            boxes = detector.detectMultiScale(frame, 1.1, 5, minSize=(32, 32))
            box = max(boxes, key=lambda b: b[2] * b[3]) if len(boxes) else None
            mouth = 0.0
            if box is not None:
                faces.append(box)
            if last is not None:
                delta = cv2.absdiff(frame, last)
                change = float(delta.mean())
                changes.append(change)
                if change > largest_change:
                    largest_change, worst = change, frame
                if box is not None:
                    x, y, w, h = (int(v) for v in box)
                    roi = delta[y:y+h, x+w//4:x+3*w//4]
                    mouth = max(0.0, roi[5*h//8:h].mean() - roi[h//5:h//2].mean())
            else:
                first = worst = frame
            mouths.append(mouth)
            last = frame
            count += 1
    finally:
        video.stdout.close()
        code = video.wait()
    if code or not count:
        raise ValueError("unable to decode source avatar frames")
    audio = subprocess.check_output([*args, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"])
    samples = np.frombuffer(audio, np.int16).astype(np.float32) / 32768
    hop = 1280
    rms = [float(np.sqrt(np.mean(chunk**2))) for chunk in
           (samples[i:i+hop] for i in range(0, len(samples), hop))]
    rms = np.array((rms + [0.] * count)[:count])
    voiced = rms > max(.02, np.percentile(rms, 60) * .35)
    issues = []
    if len(faces) < .97 * count:
        issues.append(f"face missing in {count-len(faces)} of {count} frames")
    if changes:
        threshold = max(4, 6 * (np.median(changes) + .3))
        for i, change in enumerate(changes[2:], 3):
            if change > threshold:
                issues.append(f"picture jumps at {i / SAMPLE_RATE:.1f}s")
                break
    run = longest = 0
    for i, change in enumerate(changes, 1):
        run = run + 1 if voiced[i] and change < .15 else 0
        longest = max(longest, run)
    if longest / SAMPLE_RATE > .6:
        issues.append(f"picture frozen for {longest / SAMPLE_RATE:.1f}s during speech")
    hard = bool(issues)
    mouth = np.array(mouths)
    talking = float(mouth[voiced].mean()) if voiced.any() else 0
    quiet = float(mouth[~voiced].mean()) if (~voiced).sum() > 5 else 0
    for i in range(0, count - 14, 7):
        if voiced[i:i+15].mean() > .8 and mouth[i:i+15].mean() < .35 * max(talking, .001):
            issues.append(f"inspect lip motion at {i / SAMPLE_RATE:.1f}s")
            break
    if not cv2.imwrite(str(sheet), np.hstack([first, worst, last])):
        raise OSError("could not write the scene QA contact sheet")
    return {"status": "FAIL" if hard else ("LOOK" if issues else "ok"), "issues": issues,
            "frames": count, "face_found": len(faces)/count,
            "face": np.median(faces, axis=0).tolist() if faces else None,
            "lip_ratio": talking/quiet if quiet else None}


def inspect(folder: Path, key: str, clip: Path, s: Settings) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    result = folder / f"{key}.json"
    if result.exists():
        return json.loads(result.read_text())
    with TemporaryDirectory(dir=folder) as tmp:
        sheet = Path(tmp) / "sheet.jpg"
        report = check_clip(clip, s, sheet)
        data = Path(tmp) / "result.json"
        data.write_text(json.dumps(report))
        sheet.replace(folder / f"{key}.jpg")
        data.replace(result)
    return report
