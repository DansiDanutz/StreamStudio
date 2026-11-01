"""Local speech-to-text with whisper.cpp (`whisper-cli`): free, offline, EN/RO auto-detected.

A take's MP4 → 16 kHz mono WAV (ffmpeg) → whisper-cli → <rid>.transcript.json (segments and
word timings) + <rid>.srt next to the recording.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .config import Settings

#: Models tried in order when none is configured: best first.
MODEL_CANDIDATES = (
    Path.home() / ".local/share/whisper-models/ggml-large-v3-turbo-q5_0.bin",
    Path.home() / ".local/share/whisper-models/ggml-base.bin",
)
WHISPER_TIMEOUT_S = 3 * 3600


class TranscribeError(RuntimeError):
    pass


def whisper_model(s: Settings) -> Path | None:
    if s.whisper_model:
        return s.whisper_model if s.whisper_model.exists() else None
    return next((m for m in MODEL_CANDIDATES if m.exists()), None)


def whisper_status(s: Settings) -> dict[str, str | None]:
    model = whisper_model(s)
    return {"bin": shutil.which(s.whisper_bin), "model": str(model) if model else None}


def require_whisper(s: Settings) -> tuple[str, Path]:
    status = whisper_status(s)
    if not status["bin"]:
        raise TranscribeError(f"whisper-cli not found ({s.whisper_bin}): brew install whisper-cpp")
    if not status["model"]:
        raise TranscribeError(
            "no whisper model: set STREAMSTUDIO_WHISPER_MODEL or put ggml-base.bin in "
            "~/.local/share/whisper-models"
        )
    return status["bin"], Path(status["model"])


def _is_special(token: str) -> bool:
    return token.startswith("[_") and token.endswith("]")


def parse_whisper_json(data: dict[str, Any]) -> dict[str, Any]:
    """whisper-cli -ojf output → {language, text, segments, words}. Sub-word tokens join into
    words: a token that starts with a space starts a new word."""
    segments: list[dict[str, Any]] = []
    words: list[dict[str, Any]] = []
    for seg in data.get("transcription", []):
        text = seg.get("text", "").strip()
        if text:
            off = seg["offsets"]
            segments.append({"start_ms": off["from"], "end_ms": off["to"], "text": text})
        for tok in seg.get("tokens", []):
            t = tok.get("text", "")
            if not t or _is_special(t):
                continue
            off = tok["offsets"]
            if t.startswith(" ") or not words:
                words.append({"start_ms": off["from"], "end_ms": off["to"], "word": t.strip()})
            else:
                words[-1] = {**words[-1], "end_ms": off["to"], "word": words[-1]["word"] + t}
    return {
        "language": data.get("result", {}).get("language"),
        "text": " ".join(s["text"] for s in segments),
        "segments": segments,
        "words": [w for w in words if w["word"]],
    }


def transcribe(mp4: Path, out_json: Path, out_srt: Path, s: Settings) -> dict[str, Any]:
    """Transcribe `mp4`; write the transcript JSON and SRT atomically. Returns the transcript."""
    whisper_bin, model = require_whisper(s)
    with tempfile.TemporaryDirectory(prefix="ss-whisper-") as tmp:
        wav = Path(tmp) / "audio.wav"
        stem = Path(tmp) / "out"
        subprocess.run(
            [s.ffmpeg_bin, "-v", "error", "-y", "-i", str(mp4), "-vn", "-ac", "1", "-ar", "16000",
             "-c:a", "pcm_s16le", str(wav)],
            check=True, timeout=WHISPER_TIMEOUT_S,
        )  # fmt: skip
        subprocess.run(
            [whisper_bin, "-m", str(model), "-f", str(wav), "-l", "auto", "-ojf", "-osrt",
             "-of", str(stem), "-np"],
            check=True, capture_output=True, timeout=WHISPER_TIMEOUT_S,
        )  # fmt: skip
        raw = Path(f"{stem}.json")
        if not raw.exists():
            raise TranscribeError("whisper-cli produced no transcript")
        transcript = parse_whisper_json(json.loads(raw.read_text()))
        transcript["model"] = model.name
        tmp_json = out_json.with_suffix(".tmp")
        tmp_json.write_text(json.dumps(transcript, ensure_ascii=False))
        tmp_srt = out_srt.with_suffix(".tmp-srt")
        shutil.copyfile(f"{stem}.srt", tmp_srt)
        tmp_json.replace(out_json)
        tmp_srt.replace(out_srt)
    return transcript
