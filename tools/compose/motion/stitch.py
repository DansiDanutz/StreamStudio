import cv2, numpy as np
def build(files, ys, out):
    ims=[cv2.imread(f) for f in files]; w=min(i.shape[1] for i in ims)
    H=ys[-1]+ims[-1].shape[0]; can=np.zeros((H,w,3),np.uint8)
    for y,i in zip(ys,ims): can[y:y+i.shape[0]]=i[:, :w]
    cv2.imwrite(out, can); print(out, can.shape, ys)
def match(a,b):
    best=(0,0)
    g=cv2.cvtColor(b,cv2.COLOR_BGR2GRAY)
    rows=[t for t in range(20, b.shape[0]-140, 20)]
    rows=sorted(rows,key=lambda t:-g[t:t+120].std())[:6]
    for top in rows:
        r=cv2.matchTemplate(a,b[top:top+120],cv2.TM_CCOEFF_NORMED); _,mv,_,ml=cv2.minMaxLoc(r)
        if mv>best[0]: best=(mv, ml[1]-top)
    return best
c='caps/'
build([c+'market-home-0000.png',c+'market-home-0600.png',c+'market-home-0713.png'],[0,600,713],'pages/market-home.png')
build([c+'market-list-0000.png',c+'market-list-0505.png'],[0,505],'pages/market-list.png')
build([c+f'pay-compare-{y:04d}.png' for y in (0,600,1200,1800)],[0,600,1200,1800],'pages/pay-compare.png')
build([c+'jev-control-0000.png',c+'jev-control-0300.png'],[0,300],'pages/jev-control.png')
fs=[c+f'wc-{i}.png' for i in range(7)]; ims=[cv2.imread(f) for f in fs]; ys=[0]
for a,b in zip(ims,ims[1:]):
    mv,dy=match(a,b); print('wc',round(mv,3),dy); ys.append(ys[-1]+dy)
build(fs,ys,'pages/wc.png')
