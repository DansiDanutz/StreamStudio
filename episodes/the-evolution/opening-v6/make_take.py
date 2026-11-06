"""Make Dan's continuous avatar take for this opening with StreamStudio's own HeyGen client.
Runs on the Mac Studio. PAID: prints the cost and does nothing unless --confirm is given.

  python3 make_take.py                     # estimate only
  python3 make_take.py --confirm           # render, wait, download take.mp4
  then: whisper take.mp4 --model medium.en --word_timestamps True --output_format json --output_dir .
        python3 retime.py take.json && python3 build.py --final && python3 render.py out.mp4
"""
import argparse, json, sys, time, urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--confirm", action="store_true")
ap.add_argument("--repo", default=str(Path.home() / "StreamStudio"))
ap.add_argument("--data-dir", default=None, help="folder holding heygen.json (searched if omitted)")
a = ap.parse_args()
sys.path.insert(0, str(Path(a.repo) / "server" / "src"))
from streamstudio.core import heygen  # noqa: E402

here = Path(__file__).parent
cands = [Path(a.data_dir)] if a.data_dir else [Path.home() / "StreamStudioData", Path(a.repo) / "data", Path(a.repo) / "server" / "data", Path.home() / ".streamstudio"]
data = next((d for d in cands if (d / "heygen.json").exists()), None)
if not data:
    sys.exit("heygen.json not found; pass --data-dir")
cfg = heygen.load_config(data)
if not (cfg["api_key"] and cfg["avatar_id"]):
    sys.exit("heygen.json has no API key or avatar look; set them in StreamStudio's HeyGen panel")
script = " ".join(json.loads((here / "script.json").read_text()))
est = heygen.estimate([{"script": script}])
print(f"look: {cfg.get('look_name') or cfg['avatar_id']}   voice: {cfg['voice_id'] or '(look default)'}")
print(f"one continuous take · ~{est['seconds']} s · ~${est['usd']} at StreamStudio's rate")
if not a.confirm:
    sys.exit("estimate only — rerun with --confirm to render (spends HeyGen credits)")
cl = heygen.Client(cfg["api_key"])
vid = cl.create_video(heygen.video_spec(cfg["avatar_id"], cfg["voice_id"], script=script, title="The Evolution — opening take"))
print("HeyGen video", vid)
for _ in range(240):
    v = cl.get_video(vid)
    st = (v.get("status") or "").lower()
    if st in ("completed", "success", "done"):
        url = v.get("video_url") or v.get("url") or (v.get("video") or {}).get("url")
        urllib.request.urlretrieve(url, here / "take.mp4")
        print("saved take.mp4"); break
    if st in ("failed", "error"):
        sys.exit(f"HeyGen failed: {v.get('error') or v}")
    time.sleep(15)
else:
    sys.exit("timed out waiting; video id " + vid)
