"""Frame-exact render of index.html (seeks the GSAP timeline per frame) → MP4.
usage: python3 render.py out.mp4 [--fps 30] [--stills t1,t2,...] [--from s --to e]
The Mac Studio HyperFrames renderer remains the reference for the final cut with Dan's take."""
import argparse, json, re, subprocess, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

here = Path(__file__).parent.resolve()
ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--stills"); ap.add_argument("--from", dest="t0", type=float, default=0); ap.add_argument("--to", dest="t1", type=float)
a = ap.parse_args()
D = json.loads(re.search(r"const TIMING=(.*);", (here / "timeline.js").read_text()).group(1))["duration"]

with sync_playwright() as p:
    b = p.chromium.launch(args=["--allow-file-access-from-files", "--disable-gpu-vsync"])
    pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    pg.goto((here / "index.html").as_uri())
    pg.wait_for_function("window.__timelines && document.fonts.status==='loaded'")
    pg.evaluate("document.fonts.ready")
    pg.wait_for_timeout(400)
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    # Seek GSAP, then (when the presenter take is loaded) wait until the video has
    # finished seeking and decoded the requested frame, so the screenshot never
    # pairs the animation at t with a stale presenter frame.
    seek = """async t=>{
      const tl=Object.values(window.__timelines)[0]; tl.seek(t,false);
      const v=document.querySelector('#dan-take');
      const ev=(name)=>new Promise((r,j)=>{v.addEventListener(name,r,{once:true});
        setTimeout(()=>j(new Error('dan-take: no '+name+' at t='+t)),8000);});
      if(v){
        if(v.error) throw new Error('dan-take failed to load');
        if(v.readyState<1) await ev('loadedmetadata');
        const tt=Math.min(t,Math.max(0,v.duration-1e-3));
        if(Math.abs(v.currentTime-tt)>1e-4||v.seeking){
          const done=ev('seeked');
          v.currentTime=tt; await done;
        }
        if(v.readyState<2) await ev('loadeddata');
        await new Promise(r=>'requestVideoFrameCallback' in v
          ? (v.requestVideoFrameCallback(()=>r()), setTimeout(r,250))
          : requestAnimationFrame(()=>requestAnimationFrame(r)));
      }
      await new Promise(r=>requestAnimationFrame(()=>r()));
    }"""
    if a.stills:
        out = Path(a.out); out.mkdir(exist_ok=True)
        for t in [float(x) for x in a.stills.split(",")]:
            pg.evaluate(seek, t); pg.wait_for_timeout(60)
            pg.screenshot(path=str(out / f"t{t:06.2f}.jpg"), type="jpeg", quality=85)
    else:
        t1 = a.t1 or D
        n0, n1 = int(a.t0 * a.fps), int(t1 * a.fps)
        ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(a.fps), "-c:v", "mjpeg", "-i", "-",
                               "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", a.out], stdin=subprocess.PIPE)
        for n in range(n0, n1):
            pg.evaluate(seek, n / a.fps)
            ff.stdin.write(pg.screenshot(type="jpeg", quality=92))
            if n % 150 == 0: print(f"frame {n}/{n1}", flush=True)
        ff.stdin.close(); ff.wait()
    if errs: print("PAGE ERRORS:", errs, file=sys.stderr); sys.exit(1)
    b.close()
