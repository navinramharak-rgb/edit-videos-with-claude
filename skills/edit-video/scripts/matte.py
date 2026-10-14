#!/usr/bin/env python3
"""Person matte for a 1080x1920 video (RobustVideoMatting ONNX, CPU).
Usage: python matte.py vertical_cut.mp4 -o matte_540.u8 [--model ~/.claude-video/models/rvm.onnx]
Writes a raw uint8 alpha stream at 540x960 per frame (used for behind-the-head text, cutouts, background blur)."""
import argparse, os, subprocess, time, numpy as np, onnxruntime as ort
ap=argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("-o","--out",default="matte_540.u8")
ap.add_argument("--model",default=os.path.expanduser("~/.claude-video/models/rvm.onnx")); a=ap.parse_args()
W,H=1080,1920
sess=ort.InferenceSession(a.model,providers=["CPUExecutionProvider"])
p=subprocess.Popen(["ffmpeg","-v","error","-i",a.src,"-vf",f"scale={W}:{H}","-f","rawvideo","-pix_fmt","rgb24","-"],stdout=subprocess.PIPE)
rec=[np.zeros((1,1,1,1),np.float32)]*4; dr=np.array([0.25],np.float32)
out=open(a.out,"wb"); n=0; t0=time.time()
while True:
    b=p.stdout.read(W*H*3)
    if len(b)<W*H*3: break
    f=(np.frombuffer(b,np.uint8).reshape(H,W,3).astype(np.float32)/255).transpose(2,0,1)[None]
    _,pha,*rec=sess.run(None,{"src":f,"r1i":rec[0],"r2i":rec[1],"r3i":rec[2],"r4i":rec[3],"downsample_ratio":dr})
    out.write((pha[0,0]*255).clip(0,255).astype(np.uint8)[::2,::2].tobytes()); n+=1
    if n%120==0: print(n,f"{(time.time()-t0)/n:.2f}s/frame",flush=True)
out.close(); print("frames",n,"->",a.out)
