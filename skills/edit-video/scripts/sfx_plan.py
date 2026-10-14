#!/usr/bin/env python3
"""Sound design from resolved.json (written by render_plan.py).
Usage: python sfx_plan.py resolved.json -o sfx.wav --dur SECONDS [--pack assets/sfx]
Uses real files from --pack when present (whoosh/hit/pop/stamp/type/tick .mp3|.wav), else a quiet synthesized fallback.
Design rule: whoosh only on full-screen posters. Everything else is a pop, tick or thud. Fewer, better."""
import json, wave, argparse, os, subprocess, numpy as np
ap=argparse.ArgumentParser(); ap.add_argument("resolved"); ap.add_argument("-o",default="sfx.wav"); ap.add_argument("--dur",type=float,required=True)
ap.add_argument("--pack",default=""); ap.add_argument("--gain",type=float,default=1.0); ap.add_argument("--bed",type=float,default=0.012)
a=ap.parse_args(); R=json.load(open(a.resolved)); SR=48000; N=int(SR*a.dur)+SR; out=np.zeros(N); rng=np.random.default_rng(3)
def load(name):
    for ext in (".wav",".mp3",".m4a"):
        p=os.path.join(a.pack,name+ext)
        if a.pack and os.path.exists(p):
            raw=subprocess.run(["ffmpeg","-v","error","-i",p,"-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True,check=True).stdout
            x=np.frombuffer(raw,np.float32).astype(np.float64)
            # trim leading silence, normalise peak
            idx=np.where(np.abs(x)>0.02)[0]; x=x[max(0,idx[0]-200):] if len(idx) else x
            return x/max(1e-6,np.max(np.abs(x)))
    return None
def env(n,at,d): t=np.arange(n)/SR; return np.minimum(1,t/at)*np.exp(-t/d)
def lp(x,k):
    y=np.zeros_like(x)
    for i in range(1,len(x)): y[i]=y[i-1]+k*(x[i]-y[i-1])
    return y
def syn_whoosh(d=0.4):
    n=int(d*SR); x=rng.standard_normal(n); t=np.arange(n)/SR; k=0.02+0.5*(t/d)**2; y=np.zeros(n)
    for i in range(1,n): y[i]=y[i-1]+k[i]*(x[i]-y[i-1])
    return y*np.sin(np.pi*t/d)**2
def syn_hit(): n=int(0.7*SR); t=np.arange(n)/SR; f=55+60*np.exp(-t/0.05); return np.sin(2*np.pi*np.cumsum(f)/SR)*env(n,0.001,0.22)*1.4
def syn_pop(): n=int(0.09*SR); t=np.arange(n)/SR; f=620*(1+0.6*np.exp(-t/0.01)); return np.sin(2*np.pi*np.cumsum(f)/SR)*env(n,0.001,0.03)
def syn_tick(): n=int(0.03*SR); t=np.arange(n)/SR; return np.sin(2*np.pi*2400*t)*env(n,0.0005,0.006)
def syn_type():
    n=int(1.2*SR); y=np.zeros(n)
    for k in range(11): i=int(k*n/11); y[i:i+int(0.04*SR)]+=lp(rng.standard_normal(int(0.04*SR)),0.35)*env(int(0.04*SR),0.0005,0.008)
    return y
def syn_riser(d=0.7):
    n=int(d*SR); x=rng.standard_normal(n); t=np.arange(n)/SR; k=0.01+0.25*(t/d)**3; y=np.zeros(n)
    for i in range(1,n): y[i]=y[i-1]+k[i]*(x[i]-y[i-1])
    return y*(t/d)**2.2
def syn_stamp(): n=int(0.5*SR); t=np.arange(n)/SR; return np.sin(2*np.pi*48*t)*env(n,0.001,0.16)*1.5
S={k:(load(k) if a.pack else None) for k in ("whoosh","hit","pop","stamp","type","tick")}
F={"whoosh":syn_whoosh,"hit":syn_hit,"pop":syn_pop,"stamp":syn_stamp,"type":syn_type,"tick":syn_tick}
used=set()
def snd(k):
    s=S.get(k)
    if s is None: return F[k]()
    used.add(k); return s.copy()
def add(t,k,g,maxlen=None):
    sig=snd(k)
    if maxlen: sig=sig[:int(maxlen*SR)]; sig[-int(0.02*SR):]*=np.linspace(1,0,int(0.02*SR))
    i=int(max(0,t)*SR); j=min(N,i+len(sig))
    if i<N: out[i:j]+=sig[:j-i]*g
cnt={}
def tally(k): cnt[k]=cnt.get(k,0)+1
for e in R["elements"]:
    ty=e["type"]
    if ty=="poster":
        r=syn_riser(0.7); i=int(max(0,e["t0"]-0.72)*SR); out[i:i+len(r)]+=r*0.28; tally("riser")
        add(e["t0"]-0.30,"whoosh",0.5,0.6); add(e["t0"]+0.02,"hit",0.6,0.9); tally("whoosh"); tally("hit")
    elif ty=="outro": add(e["t0"],"hit",0.5,0.9); add(e["t0"]+0.7,"type",0.3,0.6); tally("hit")
    elif ty=="hook_split": add(e["t0"],"whoosh",0.35,0.5); add(e["t1"]-0.3,"whoosh",0.35,0.5); tally("whoosh")
    elif ty in("hook_box","cta"): add(e["t0"],"pop",0.4,0.3); tally("pop")
    elif ty in("behind_text","word_stack"):
        for it in e.get("items") or [{"t":e["t0"]}]: add(it["t"]-0.02,"pop",0.22,0.3); tally("pop")
    elif ty=="cards":
        for it in e["items"]: add(it["t"]-0.02,"pop",0.38,0.3); tally("pop")
    elif ty in("list","list_panel"):
        add(e["t0"],"pop",0.3,0.3); tally("pop")
        for it in e["items"]: add(it["t"],"tick",0.35,0.2); tally("tick")
    elif ty=="prompt": add(e["t0"]+0.15,"type",0.35,max(0.5,e.get("type_end",e["t1"]-0.3)-e["t0"]-0.15)); tally("type")
    elif ty in("image","card_image","board"): add(e["t0"]-0.02,"pop",0.3,0.35); tally("pop")
    elif ty=="stamp": add(e["t0"],"stamp",0.7,0.6); tally("stamp")
    elif ty=="profile_card":
        add(e["t0"],"pop",0.4,0.3); tally("pop")
        tm=e.get("mark_at",e["t0"]+0.45); add(tm,"stamp",0.5,0.4); tally("stamp")
    elif ty=="kinetic": add(e["t0"]-0.15,"whoosh",0.45,0.5); add(e["t0"]+0.3,"hit",0.4,0.6); tally("whoosh"); tally("hit")
    elif ty=="exploded": add(e["t0"]-0.2,"whoosh",0.4,0.6); add(e["t0"]+0.9,"pop",0.3,0.3); tally("whoosh"); tally("pop")
    elif ty=="filmstrip":
        tt=e["t0"]
        while tt<e["t1"]-0.3: add(tt,"tick",0.18,0.1); tt+=0.125
        tally("tick-train")
    elif ty=="silhouette":
        r=syn_riser(0.6); i=int(max(0,e["t0"]-0.6)*SR); out[i:i+len(r)]+=r*0.3; add(e["t0"],"hit",0.55,0.9); tally("riser"); tally("hit")
    elif ty=="phone_fan":
        for k in range(len(e["phones"])): add(e["t0"]+k*0.07,"pop",0.3,0.25); tally("pop")
    elif ty=="timeline":
        for it in e["items"]:
            if it.get("kind")=="removed": add(it["t"],"tick",0.4,0.2); tally("tick")
if R.get("switch_on") is not None:
    so=R["switch_on"]; r=syn_riser(1.0); i=int(max(0,so-1.0)*SR); out[i:i+len(r)]+=r*0.4; add(so,"hit",0.7,1.0); tally("switch_on")
for f in R.get("flash",[]): add(f,"hit",0.5,0.9); tally("hit")
out=out/max(1e-6,np.max(np.abs(out)))*0.5*a.gain
if a.bed>0:
    bed=lp(rng.standard_normal(N),0.02); bed=bed/np.max(np.abs(bed))*a.bed
    if R.get("switch_on") is not None: bed[:int(R["switch_on"]*SR)]*=0.35
    out+=bed
out=out[:int(a.dur*SR)]
pcm=(np.stack([out,out],1)*32767).astype(np.int16)
w=wave.open(a.o,"wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes()); w.close()
print("sfx ->",a.o,"| counts",cnt,"| real files used:",sorted(used) or "none (synth fallback)")
