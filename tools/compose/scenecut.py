"""Cut scene clips out of a HeyGen take, by caption text, each from the middle of the pause before to the middle of the pause after."""
import json, re, subprocess, sys
def ts(x):h,m,s=x.replace(',','.').split(':');return int(h)*3600+int(m)*60+float(s)
norm=lambda s:re.sub(r'[^a-z0-9]','',s.lower())
def caps(srt):
    out=[]
    for b in open(srt).read().strip().split('\n\n'):
        l=b.split('\n');a,c=l[1].split(' --> ');out.append((ts(a),ts(c),' '.join(l[2:])))
    return out
def silences(mp4):
    log=subprocess.run(['ffmpeg','-v','info','-i',mp4,'-af','silencedetect=n=-38dB:d=0.15','-f','null','-'],capture_output=True,text=True).stderr
    s=[];st=None
    for k,v in re.findall(r'silence_(start|end): ([0-9.]+)',log):
        if k=='start': st=float(v)
        elif st is not None: s.append((st,float(v)));st=None
    return s
def locate(C, text):
    t=norm(text)
    for i in range(len(C)):
        acc=''
        for j in range(i,len(C)):
            acc+=norm(C[j][2])
            if acc==t: return C[i][0],C[j][1]
            if not t.startswith(acc): break
    return None
def snap(sil, t, side):
    # middle of the pause nearest t (start: pause just before; end: pause just after)
    cands=[(a+b)/2 for a,b in sil if abs((a+b)/2-t)<0.9]
    return min(cands,key=lambda m:abs(m-t)) if cands else t+(-0.15 if side=='start' else 0.15)
def cut(mp4, a, b, out):
    subprocess.run(['ffmpeg','-v','error','-y','-ss',f'{a:.3f}','-i',mp4,'-t',f'{b-a:.3f}','-c:v','libx264','-preset','veryfast','-crf','14','-r','25','-c:a','aac','-b:a','192k','-ar','48000',out],check=True)
if __name__=='__main__':
    mp4, srt, script, which, outdir = sys.argv[1:6]
    d=json.load(open(script)); C=caps(srt); sil=silences(mp4)
    want=[int(x) for x in which.split(',')]
    for s in d['scenes']:
        if s['scene'] not in want: continue
        r=locate(C, s['voice'])
        if not r: print('NOT FOUND', s['scene'], s['voice'][:50]); continue
        a=max(0,snap(sil,r[0],'start')); b=snap(sil,r[1],'end')
        cut(mp4,a,b,f"{outdir}/scene-{s['scene']:02d}.mp4"); print(s['scene'], round(a,2), round(b,2), round(b-a,2))
