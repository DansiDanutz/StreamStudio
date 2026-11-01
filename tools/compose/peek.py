import sys, subprocess, numpy as np, cv2
sys.argv=[sys.argv[0], sys.argv[1]] + sys.argv[2:]
W=sys.argv[1]
import importlib.util
import os
spec=importlib.util.spec_from_file_location('r', os.path.join(os.path.dirname(os.path.abspath(__file__)),'render.py')); r=importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
ts=[float(x) for x in sys.argv[2:]]
tiles=[]
for t in ts:
    f=round(t*25)
    raw=subprocess.run(['ffmpeg','-v','error','-ss',f'{f/25:.3f}','-i',W+'/heygen.mp4','-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True).stdout
    fr=np.frombuffer(raw,np.uint8).reshape(1080,1920,3).astype(np.float32)
    out=np.clip(r.compose(fr,f),0,255).astype(np.uint8)
    tiles.append(cv2.resize(out,(960,540)))
rows=[np.hstack(tiles[i:i+2]) if i+1<len(tiles) else np.hstack([tiles[i],np.zeros_like(tiles[i])]) for i in range(0,len(tiles),2)]
cv2.imwrite(W+'/peek.jpg', cv2.cvtColor(np.vstack(rows),cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 80])
print('ok')
