#!/usr/bin/env python3
"""Reframe a landscape cut to 9:16 by following the speaker's head.
Usage: python reframe.py CUT_LANDSCAPE.mp4 track.json edl.json -o vertical.mp4 [--fps 30]
track.json: per-source-frame head x (normalized) from track.py. edl.json maps cut time -> source time.
Smart follow: camera holds still while the head stays near center, eases over when it drifts."""
import argparse, json, subprocess, numpy as np
ap=argparse.ArgumentParser(); ap.add_argument("cut"); ap.add_argument("track"); ap.add_argument("edl")
ap.add_argument("-o","--out",required=True); ap.add_argument("--fps",type=float,default=30)
a=ap.parse_args()
tr=json.load(open(a.track)); keep=None if a.edl=="none" else json.load(open(a.edl))["keep"]
probe=subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height,nb_frames","-of","json",a.cut],capture_output=True,text=True)
st=json.loads(probe.stdout)["streams"][0]; SW,SH=st["width"],st["height"]
CW=int(round(SH*9/16/2))*2
# source time for each cut frame
if a.edl=="none":
    src_t=[i/a.fps for i in range(len(tr))]
else:
    src_t=[]
    for s,e in keep:
        n=int(round((e-s)*a.fps)); src_t+=[s+i/a.fps for i in range(n)]
hx=[]; last=0.5
for t in src_t:
    i=min(len(tr)-1,int(round(t*a.fps))); v=tr[i]
    if v: last=v["hx"]
    hx.append(last)
hx=np.array(hx)*SW
# lazy follow: deadzone then smooth (forward-backward EMA = no lag)
lo,hi=CW/2,SW-CW/2; target=np.clip(hx,lo,hi); cam=np.empty_like(target); c=target[0]; dz=CW*0.10
for i,x in enumerate(target):
    if abs(x-c)>dz: c=x-np.sign(x-c)*dz
    cam[i]=c
def ema(v,k):
    o=np.empty_like(v); s=v[0]
    for i,x in enumerate(v): s=s+k*(x-s); o[i]=s
    return o
cam=ema(ema(cam,0.08)[::-1],0.08)[::-1]; cam=np.clip(cam,lo,hi)
json.dump([float(x) for x in cam],open(a.out+".camx.json","w"))
dec=subprocess.Popen(["ffmpeg","-v","error","-i",a.cut,"-f","rawvideo","-pix_fmt","rgb24","-"],stdout=subprocess.PIPE,bufsize=10**8)
enc=subprocess.Popen(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{CW}x{SH}","-r",str(a.fps),"-i","-",
  "-i",a.cut,"-map","0:v","-map","1:a","-vf","scale=1080:1920:flags=lanczos","-c:v","libx264","-preset","fast","-crf","15",
  "-pix_fmt","yuv420p","-c:a","copy",a.out],stdin=subprocess.PIPE)
n=0; fb=SW*SH*3
while True:
    b=dec.stdout.read(fb)
    if len(b)<fb: break
    f=np.frombuffer(b,np.uint8).reshape(SH,SW,3)
    x0=int(round(cam[min(n,len(cam)-1)]-CW/2)); x0=max(0,min(SW-CW,x0))
    enc.stdin.write(np.ascontiguousarray(f[:,x0:x0+CW]).tobytes()); n+=1
enc.stdin.close(); enc.wait(); print("reframed",n,"frames ->",a.out)
