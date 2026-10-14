#!/usr/bin/env python3
"""Head tracking for landscape -> 9:16 reframing (RobustVideoMatting ONNX, CPU).
Usage: python track.py SOURCE.mp4 -o track.json [--model ~/.claude-video/models/rvm.onnx]
Writes one entry per frame: {"top","hx","hw","cx"} as fractions of the frame (None where no person)."""
import argparse, json, os, subprocess, numpy as np, onnxruntime as ort
ap=argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("-o","--out",default="track.json")
ap.add_argument("--model",default=os.path.expanduser("~/.claude-video/models/rvm.onnx")); a=ap.parse_args()
W,H=640,360
sess=ort.InferenceSession(a.model,providers=["CPUExecutionProvider"])
p=subprocess.Popen(["ffmpeg","-v","error","-i",a.src,"-vf",f"scale={W}:{H}","-f","rawvideo","-pix_fmt","rgb24","-"],stdout=subprocess.PIPE)
rec=[np.zeros((1,1,1,1),np.float32)]*4; dr=np.array([0.5],np.float32); out=[]
while True:
    b=p.stdout.read(W*H*3)
    if len(b)<W*H*3: break
    f=(np.frombuffer(b,np.uint8).reshape(H,W,3).astype(np.float32)/255).transpose(2,0,1)[None]
    _,pha,*rec=sess.run(None,{"src":f,"r1i":rec[0],"r2i":rec[1],"r3i":rec[2],"r4i":rec[3],"downsample_ratio":dr})
    m=pha[0,0]>0.5; ys,xs=np.where(m)
    if len(ys)<50: out.append(None); continue
    top=int(ys.min()); band=m[top:top+60]; bx=np.where(band.any(0))[0]
    out.append({"top":top/H,"hx":float((bx.min()+bx.max())/2/W),"hw":float((bx.max()-bx.min())/W),"cx":float(xs.mean()/W)})
    if len(out)%300==0: print("tracked",len(out),flush=True)
json.dump(out,open(a.out,"w")); print("frames",len(out),"->",a.out)
