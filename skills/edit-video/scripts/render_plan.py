#!/usr/bin/env python3
"""Render overlays onto a vertical cut from an edit plan (plan.json).
Usage: python render_plan.py plan.json -o video_only.mp4 [--from T --to T] [--stills t1,t2,...]
Times in the plan can be numbers (seconds) or word refs: "@life", "@let's#1", "@first-0.1".
Element types: behind_text, word_stack, poster, prompt, cards, list, pop_word, stamp, cta, hook_box, image, video, chapter.
"""
import argparse, json, math, os, random, re, subprocess, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
ap=argparse.ArgumentParser(); ap.add_argument("plan"); ap.add_argument("-o","--out",default="video_only.mp4")
ap.add_argument("--stills",default=""); ap.add_argument("--stills-dir",default="stills"); ap.add_argument("--overlay",default="")
A=ap.parse_args(); P=json.load(open(A.plan)); BASE=os.path.dirname(os.path.abspath(A.plan))
def pth(p): return p if os.path.isabs(p) else os.path.join(BASE,p)
W,H,FPS=1080,1920,P.get("fps",30)
FONT_DIR=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"assets","fonts")
ST=P.get("style",{})
FONTS={"serif":ST.get("serif",os.path.join(FONT_DIR,"InstrumentSerif-Regular.ttf")),
 "serif_i":ST.get("serif_i",os.path.join(FONT_DIR,"InstrumentSerif-Italic.ttf")),
 "sans":ST.get("sans",os.path.join(FONT_DIR,"Inter-Medium.ttf")),
 "sans_b":ST.get("sans_b",os.path.join(FONT_DIR,"Inter-Bold.ttf")),
 "sans_xb":ST.get("sans_xb",os.path.join(FONT_DIR,"Inter-ExtraBold.ttf")),
 "sans_black":ST.get("sans_black",os.path.join(FONT_DIR,"Inter-Black.ttf")),
 "mono":ST.get("mono",os.path.join(FONT_DIR,"DejaVuSansMono.ttf"))}
def hexc(h,a=255): h=h.lstrip("#"); return (int(h[0:2],16),int(h[2:4],16),int(h[4:6],16),a)
ACC=hexc(ST.get("accent","#FF6B2E"))
_F={}
def font(k,s):
    key=(k,int(s))
    if key not in _F: _F[key]=ImageFont.truetype(FONTS.get(k,k),max(4,int(s)))
    return _F[key]
WORDS=json.load(open(pth(P["words"])))
def norm(w): return re.sub(r"[^a-z0-9']","",w.lower())
def T(v):
    if isinstance(v,(int,float)): return float(v)
    m=re.match(r"@([^#+\-]+)(?:#(\d+))?([+\-][\d.]+)?$",v.strip())
    if not m: raise ValueError(v)
    word,occ,off=m.group(1).lower(),int(m.group(2) or 0),float(m.group(3) or 0)
    hits=[w for w in WORDS if norm(w["w"])==norm(word)]
    if len(hits)<=occ: raise KeyError(f"word not found: {v}")
    return hits[occ]["s"]+off
def TE(v):  # end of word ref ("@word<" = start of word)
    if isinstance(v,str) and v.strip().endswith("<"): return T(v.strip()[:-1])
    if isinstance(v,str) and v.startswith("@"):
        m=re.match(r"@([^#+\-]+)(?:#(\d+))?([+\-][\d.]+)?$",v.strip()); word,occ,off=m.group(1).lower(),int(m.group(2) or 0),float(m.group(3) or 0)
        hits=[w for w in WORDS if norm(w["w"])==norm(word)]; return hits[occ]["e"]+off
    return T(v)
END=P.get("duration") or (WORDS[-1]["e"]+0.4)
clamp=lambda x,a=0,b=1:max(a,min(b,x))
def ease(x): x=clamp(x); return 1-(1-x)**3
def eio(x): x=clamp(x); return x*x*(3-2*x)
def back(x,s=1.7): x=clamp(x)-1; return 1+x*x*((s+1)*x+s)
def ramp(t,a,b): return clamp((t-a)/max(1e-6,b-a))
def life(t,t0,t1,fi=0.15,fo=0.15): return clamp(ramp(t,t0,t0+fi))*(1-ramp(t,t1-fo,t1))
# ---------- resolve times ----------
EL=[e for e in P.get("elements",[]) if e.get("engine","html" if A.overlay else "py")=="py"]
ALL_EL=P.get("elements",[])
for e in ALL_EL:
    if "t0" not in e and e.get("items"): e["t0"]=e["items"][0]["t"]
    for k in ("t0","t1","t","type_end","mark_at"):
        if k in e: e[k]=(TE(e[k]) if k=="t1" else T(e[k]))
    for it in e.get("items",[]):
        if "t" in it: it["t"]=T(it["t"])
CAMK=[dict(k,t=T(k["t"])) for k in P.get("camera",[])]
GRADE=[(T(g["t0"]),TE(g["t1"]),g.get("mode","bw")) for g in P.get("grade",[])]
FLASH=[T(f) for f in P.get("flash",[])]
BLUR=[(T(a),TE(b)) for a,b in P.get("blur_bg",[])]
CAPHIDE=[(T(a),TE(b)) for a,b in P.get("captions",{}).get("hide",[])]
def _t0t1(e): return (T(e["t0"]), TE(e["t1"]) if "t1" in e else END)
CAPHIDE+=[_t0t1(e) for e in ALL_EL if e["type"] in("poster","board","exploded","silhouette","outro") or (e["type"]=="image" and e.get("mode","full")=="full")]
SHAKE=[T(s) for s in P.get("shake",[])]
json.dump({"elements":ALL_EL,"switch_on":(T(P["sound"]["switch_on"]) if P.get("sound",{}).get("switch_on") else None),"flash":FLASH,"shake":SHAKE,"end":END},open(os.path.join(BASE,"resolved.json"),"w"),indent=1)
# ---------- camera ----------
AX,AY=P.get("anchor",[540,700])
def zoom(t):
    z=1.0
    for k in CAMK:
        if t<k["t"]: break
        d=k.get("dur",0.15); et=k.get("ease","snap")
        r=ramp(t,k["t"],k["t"]+d)
        f=ease(r) if et=="snap" else (eio(r) if et=="smooth" else (r if et=="creep" else (back(r,1.2) if et=="settle" else ease(r))))
        z=z+(k["z"]-z)*f if t<k["t"]+d else k["z"]
    return max(1.0,z)
DRIFT=[(T(a),TE(b)) for a,b in P.get("drift",[])]
def shake(t):
    for a,b in DRIFT:
        if a<=t<b: return (6*math.sin(t*1.7)+3*math.sin(t*4.1), 5*math.cos(t*1.3)+2*math.sin(t*3.7))
    for s in SHAKE:
        if s<=t<s+0.18: k=1-ramp(t,s,s+0.18); return (random.uniform(-1,1)*14*k,random.uniform(-1,1)*14*k)
    return (0,0)
def cam(img,z,dx=0,dy=0,rs=Image.BILINEAR):
    if z<=1.0001 and not dx and not dy: return img
    w,h=img.size; cw,ch=w/z,h/z
    cx=min(max(AX*w/W+dx*w/W,cw/2),w-cw/2); cy=min(max(AY*h/H+dy*h/H,ch/2),h-ch/2)
    return img.resize((w,h),rs,box=(max(0.,cx-cw/2),max(0.,cy-ch/2),min(float(w),cx+cw/2),min(float(h),cy+ch/2)))
# ---------- drawing helpers ----------
def layer(): return Image.new("RGBA",(W,H),(0,0,0,0))
def txt(L,xy,s,fk,size,fill,anchor="mm",shadow=0,glow=0,alpha=1.0,dark_halo=0):
    f=font(fk,size); fill=fill[:3]+(int(fill[3]*alpha) if len(fill)>3 else int(255*alpha),)
    if dark_halo:
        G=layer(); ImageDraw.Draw(G).text(xy,s,font=f,fill=(0,0,0,int(200*alpha)),anchor=anchor)
        L.alpha_composite(G.filter(ImageFilter.GaussianBlur(dark_halo)))
    if shadow:
        S=layer(); ImageDraw.Draw(S).text((xy[0],xy[1]+shadow*0.5),s,font=f,fill=(0,0,0,int(150*alpha)),anchor=anchor)
        L.alpha_composite(S.filter(ImageFilter.GaussianBlur(shadow)))
    if glow:
        G=layer(); ImageDraw.Draw(G).text(xy,s,font=f,fill=(255,255,255,int(110*alpha)),anchor=anchor)
        L.alpha_composite(G.filter(ImageFilter.GaussianBlur(glow)))
    ImageDraw.Draw(L).text(xy,s,font=f,fill=fill,anchor=anchor)
def card(w,h,r=30,fill=(255,255,255,255),shadow=True,border=None,bw=0,pad=60):
    L=Image.new("RGBA",(w+2*pad,h+2*pad),(0,0,0,0))
    if shadow:
        S=Image.new("RGBA",L.size,(0,0,0,0)); ImageDraw.Draw(S).rounded_rectangle((pad,pad+16,pad+w,pad+h+16),r,fill=(0,0,0,130))
        L=Image.alpha_composite(L,S.filter(ImageFilter.GaussianBlur(24)))
    ImageDraw.Draw(L).rounded_rectangle((pad,pad,pad+w,pad+h),r,fill=fill,outline=border,width=bw); return L,pad
def put(base,L,xy,alpha=1.0,scale=1.0,rot=0):
    if alpha<=0.003: return
    if rot: L=L.rotate(rot,resample=Image.BICUBIC,expand=True)
    if abs(scale-1)>1e-3: L=L.resize((max(1,int(L.width*scale)),max(1,int(L.height*scale))),Image.BICUBIC)
    if alpha<1: a=L.getchannel("A").point(lambda v:int(v*alpha)); L=L.copy(); L.putalpha(a)
    base.alpha_composite(L,(int(xy[0]-L.width/2),int(xy[1]-L.height/2))) if 0<=xy[0]-L.width/2 and xy[0]+L.width/2<=W and 0<=xy[1]-L.height/2 and xy[1]+L.height/2<=H else _paste(base,L,xy)
def _paste(base,L,xy):
    tmp=layer(); tmp.paste(L,(int(xy[0]-L.width/2),int(xy[1]-L.height/2)),L); base.alpha_composite(tmp)
def wrap(s,fk,size,maxw):
    f=font(fk,size); out=[]; cur=""
    for w in s.split():
        if f.getlength((cur+" "+w).strip())<=maxw: cur=(cur+" "+w).strip()
        else: out.append(cur); cur=w
    if cur: out.append(cur)
    return out
_IMG={}
def load_img(p):
    if p not in _IMG: _IMG[p]=Image.open(pth(p)).convert("RGBA")
    return _IMG[p]
def cover(im,w,h,zoom=1.0,fx=0.5,fy=0.5):
    s=max(w/im.width,h/im.height)*zoom; nw,nh=int(im.width*s)+1,int(im.height*s)+1
    im=im.resize((nw,nh),Image.BICUBIC); x=int((nw-w)*fx); y=int((nh-h)*fy); return im.crop((x,y,x+w,y+h))
class VidSrc:
    def __init__(s,p,w,h):
        s.p=subprocess.Popen(["ffmpeg","-v","error","-i",pth(p),"-vf",f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS}","-f","rawvideo","-pix_fmt","rgba","-"],stdout=subprocess.PIPE); s.w,s.h=w,h; s.last=None
    def next(s):
        b=s.p.stdout.read(s.w*s.h*4)
        if len(b)==s.w*s.h*4: s.last=Image.frombytes("RGBA",(s.w,s.h),b)
        return s.last
VIDS={}
# ---------- element renderers ----------
def R_behind_text(e,t,F,B):
    a=life(t,e["t0"],e["t1"],e.get("fade_in",0.12),0.25)*e.get("opacity",0.92)
    if a<=0: return
    sc=1+e.get("grow",0.03)*(t-e["t0"])
    txt(B,(W/2,e.get("y",250)),e["text"],e.get("font","serif"),e.get("size",520)*sc,hexc(e.get("color","#FFFFFF")),alpha=a,glow=e.get("glow",0))
def R_word_stack(e,t,F,B):
    its=e["items"]
    for i,it in enumerate(its):
        te=its[i+1]["t"] if i+1<len(its) else e["t1"]
        if it["t"]-0.05<=t<te+0.25:
            a=ease(ramp(t,it["t"]-0.05,it["t"]+0.15))*(1-ramp(t,te,te+0.25)); sc=0.9+0.1*ease(ramp(t,it["t"]-0.05,it["t"]+0.2))
            txt(B,(W/2,e.get("y",175)),it["text"],e.get("font","serif"),e.get("size",230)*sc,hexc(it.get("color",e.get("color","#FFFFFF"))),alpha=a,glow=8)
def R_poster(e,t,F,B):
    if not (e["t0"]<=t<e["t1"]): return
    k=ramp(t,e["t0"],e["t0"]+0.18)
    bg=e.get("bg","#FF6B2E")
    L=layer(); d=ImageDraw.Draw(L)
    if isinstance(bg,list):  # vertical gradient
        c1,c2=np.array(hexc(bg[0])[:3]),np.array(hexc(bg[1])[:3]); g=np.linspace(0,1,H)[:,None]
        arr=(c1*(1-g)+c2*g).astype(np.uint8); arr=np.repeat(arr[:,None,:],W,1); L=Image.fromarray(arr).convert("RGBA")
    elif bg!="none": d.rectangle((0,0,W,H),fill=hexc(bg))
    if e.get("image"):
        im=cover(load_img(e["image"]),W,H,1.0+0.06*ramp(t,e["t0"],e["t1"])); L.alpha_composite(im)
        if e.get("dim",0): L.alpha_composite(Image.new("RGBA",(W,H),(0,0,0,int(255*e["dim"]))))
    y=e.get("y",700); 
    for li,ln in enumerate(e["lines"]):
        lt=T(ln["t"]) if "t" in ln else e["t0"]
        if t<lt-0.02: continue
        lk=back(ramp(t,lt,lt+0.22),1.4)
        fs=ln.get("size",160)
        for row in wrap(ln["text"],ln.get("font","sans_black"),fs,W-120):
            txt(L,(W/2,y+(1-lk)*40),row,ln.get("font","sans_black"),fs,hexc(ln.get("color","#FFFFFF")),shadow=ln.get("shadow",12),alpha=clamp(lk))
            y+=fs*ln.get("lh",0.95)
        y+=ln.get("gap",20)
    # slide/scale in
    sc=1.06-0.06*ease(k); F.alpha_composite(L if sc==1 else L.resize((int(W*sc),int(H*sc))).crop((int((W*sc-W)/2),int((H*sc-H)/2),int((W*sc-W)/2)+W,int((H*sc-H)/2)+H)))
def R_prompt(e,t,F,B):
    t0,t1=e["t0"],e["t1"]
    if not (t0-0.05<=t<t1+0.2): return
    k=ease(ramp(t,t0-0.05,t0+0.25)); a=k*(1-ramp(t,t1-0.1,t1+0.2))
    L,p=card(900,170,34,(247,244,238,255)); d=ImageDraw.Draw(L)
    d.text((p+40,p+48),e.get("label","TO CLAUDE"),font=font("mono",24),fill=(140,136,128),anchor="lm")
    s=e["text"]; n=int(len(s)*ramp(t,t0+0.15,e.get("type_end",t1-0.3))); shown=s[:n]; ft=font("sans",44)
    while ft.getlength(shown)>720 and len(shown)>4: shown="…"+shown[-(len(shown)-6):]
    d.text((p+40,p+112),shown,font=ft,fill=(25,25,25),anchor="lm")
    if int(t*2.5)%2==0 or n<len(s): cx=p+40+ft.getlength(shown)+4; d.rectangle((cx,p+88,cx+3,p+136),fill=(25,25,25))
    d.ellipse((p+804,p+52,p+864,p+112),fill=ACC); d.text((p+834,p+82),"↑",font=font("sans_b",34),fill=(255,255,255),anchor="mm")
    put(F,L,(W/2,e.get("y",1560)+70*(1-k)),a)
def R_cards(e,t,F,B):
    its=e["items"]; t1=e["t1"]; out=ramp(t,t1-0.05,t1+0.25)
    if t<its[0]["t"]-0.05 or out>=1: return
    n=len(its); cw=e.get("w",330); gap=(W-60-n*cw)/max(1,n-1) if n>1 else 0
    for i,it in enumerate(its):
        if t<it["t"]-0.05: continue
        k=back(ramp(t,it["t"]-0.05,it["t"]+0.25),2.2)
        L,p=card(cw,120,30); d=ImageDraw.Draw(L)
        if it.get("dot"): d.ellipse((p+26,p+36,p+74,p+84),fill=hexc(it["dot"])); tx=p+90
        else: tx=p+32
        fs=44
        while font("sans_b",fs).getlength(it["text"])>cw-(tx-p)-24 and fs>24: fs-=2
        d.text((tx,p+60),it["text"],font=font("sans_b",fs),fill=(20,20,20),anchor="lm")
        x=30+cw/2+i*(cw+gap) if n>1 else W/2
        rot=it.get("rot",[-6,2,7,-3,4][i%5])
        put(F,L,(x,e.get("y",1520)+40*out),clamp(ramp(t,it["t"]-0.05,it["t"]+0.05))*(1-out),scale=max(0.05,k),rot=rot)
def R_list(e,t,F,B):
    t0,t1=e["t0"],e["t1"]
    if not (t0<=t<t1+0.25): return
    a=life(t,t0,t1+0.25,0.2,0.25); x=e.get("x",70); y=e.get("y",230); L=layer()
    if e.get("panel",True):
        nrows=len(e["items"])+1; ph=90+nrows*e.get("row",78)
        P_,pp=card(W-2*x+40,ph,28,(15,15,15,170),shadow=False); L.alpha_composite(P_,(int(x-20-pp),int(y-50-pp)))
    txt(L,(x,y),e.get("title",""),e.get("title_font","serif"),e.get("title_size",66),(255,255,255,255),anchor="ls")
    for i,it in enumerate(e["items"]):
        yy=y+(i+1)*e.get("row",78)+10; on=t>=it["t"]-0.03; k=ease(ramp(t,it["t"]-0.03,it["t"]+0.2))
        col=ACC if (on and (i+1==len(e["items"]) or t<e["items"][i+1]["t"])) else (255,255,255,255 if on else 90)
        num=f"{i+1}."; txt(L,(x,yy),num,"sans_b",44,col if on else (255,255,255,90),anchor="ls")
        if on: txt(L,(x+70+30*(1-k),yy),it["text"],"sans_b",48,col,anchor="ls",alpha=k)
    put(F,L,(W/2,H/2),a)
def R_pop_word(e,t,F,B):
    if not (e["t0"]-0.02<=t<e["t1"]): return
    sc=back(ramp(t,e["t0"],e["t0"]+0.25)); a=clamp(ramp(t,e["t0"]-0.02,e["t0"]+0.08))*(1-ramp(t,e["t1"]-0.2,e["t1"]))
    L=layer(); txt(L,(e.get("x",W/2),e.get("y",1050)),e["text"],e.get("font","serif_i"),e.get("size",240)*max(0.05,sc),hexc(e.get("color",ST.get("accent","#FF6B2E"))),anchor=e.get("anchor","mm"),shadow=18)
    target=B if e.get("behind") else F; target.alpha_composite(L) if a>=0.999 else put(target,L,(W/2,H/2),a)
def R_stamp(e,t,F,B):
    if t<e["t0"]-0.02 or t>=e.get("t1",1e9): return
    k=ramp(t,e["t0"],e["t0"]+0.12); sc=1.5-0.5*ease(k)
    L,p=card(e.get("w",560),190,24,(0,0,0,70),shadow=False,border=ACC,bw=12)
    ImageDraw.Draw(L).text((p+e.get("w",560)/2,p+98),e["text"],font=font("sans_xb",120),fill=ACC,anchor="mm")
    put(F,L,(W/2,e.get("y",1560)),clamp(ramp(t,e["t0"]-0.02,e["t0"]+0.05)),scale=sc,rot=-6)
    if e.get("sub"): 
        S=layer(); txt(S,(W/2,e.get("y",1560)+190),e["sub"],"mono",28,(255,255,255,255),shadow=14,alpha=ramp(t,e["t0"]+0.2,e["t0"]+0.5)); F.alpha_composite(S)
def R_box(e,t,F,B,top):
    if not (e["t0"]-0.05<=t<e["t1"]): return
    k=back(ramp(t,e["t0"]-0.05,e["t0"]+0.25),1.6); a=clamp(ramp(t,e["t0"]-0.05,e["t0"]+0.1))*(1-ramp(t,e["t1"]-0.15,e["t1"]))
    rows=wrap(e["text"],"sans_xb",e.get("size",54),W-260); fs=e.get("size",54); bw=int(max(font("sans_xb",fs).getlength(r) for r in rows))+70; bh=int(len(rows)*fs*1.18)+50
    L,p=card(bw,bh,26,(255,255,255,255)); d=ImageDraw.Draw(L)
    for i,r in enumerate(rows):
        d.text((p+bw/2,p+25+fs*0.6+i*fs*1.18),r,font=font("sans_xb",fs),fill=(15,15,15),anchor="mm")
    put(F,L,(W/2,e.get("y",230 if top else 1500)),a,scale=max(0.05,k))
def R_image(e,t,F,B):
    if not (e["t0"]<=t<e["t1"]): return
    k=ramp(t,e["t0"],e["t1"])
    if e["path"].lower().endswith((".mp4",".mov")):
        key=id(e)
        if key not in VIDS: VIDS[key]=VidSrc(e["path"],W if e.get("mode","full")=="full" else e.get("w",820),H if e.get("mode","full")=="full" else e.get("h",1000))
        im=VIDS[key].next()
        if im is None: return
    else:
        im=load_img(e["path"])
    if e.get("mode")=="board":
        a=clamp(ramp(t,e["t0"],e["t0"]+0.12))*(1-ramp(t,e["t1"]-0.12,e["t1"]))
        F.alpha_composite(Image.new("RGBA",(W,H),(10,10,10,int(205*a))))
        w=e.get("w",860); h=int(im.height*w/im.width); fr=im.resize((w,h),Image.LANCZOS)
        L,p=card(w,h,28,(0,0,0,0)); m=Image.new("L",(w,h),0); ImageDraw.Draw(m).rounded_rectangle((0,0,w,h),28,fill=255); L.paste(fr,(p,p),m)
        kk=back(ramp(t,e["t0"],e["t0"]+0.3),1.3); put(F,L,(W/2,e.get("y",780)+60*(1-kk)),a,scale=0.92+0.08*kk+0.03*k)
        return
    if e.get("mode","full")=="full":
        fr=cover(im,W,H,1.04+0.08*k if e.get("kenburns",True) else 1.0)
        a=clamp(ramp(t,e["t0"],e["t0"]+0.08))*(1-ramp(t,e["t1"]-0.08,e["t1"]))
        put(F,fr,(W/2,H/2),a)
    else:
        w,h=e.get("w",820),e.get("h",1000); fr=cover(im,w,h,1.02+0.05*k)
        L,p=card(w,h,36,(255,255,255,255)); m=Image.new("L",(w,h),0); ImageDraw.Draw(m).rounded_rectangle((0,0,w,h),36,fill=255)
        L.paste(fr,(p,p),m); kk=back(ramp(t,e["t0"],e["t0"]+0.3),1.3); a=clamp(ramp(t,e["t0"],e["t0"]+0.1))*(1-ramp(t,e["t1"]-0.15,e["t1"]))
        put(F,L,(e.get("x",W/2),e.get("y",620)+80*(1-kk)),a,scale=0.9+0.1*kk,rot=e.get("rot",-3))
        if e.get("label"):
            S=layer(); txt(S,(e.get("x",W/2),e.get("y",620)+h/2+60),e["label"],"mono",26,(255,255,255,255),shadow=10,alpha=a); F.alpha_composite(S)
def R_chapter(e,t,F,B):
    if not (e["t0"]<=t<e["t1"]): return
    a=life(t,e["t0"],e["t1"],0.2,0.2); L=layer(); d=ImageDraw.Draw(L)
    n=e.get("total",5); i=e.get("index",1); x0,x1,y=70,W-70,80; seg=(x1-x0-(n-1)*10)/n
    for j in range(n):
        xs=x0+j*(seg+10); col=ACC if j<i else (255,255,255,90)
        if j==i-1:
            d.rounded_rectangle((xs,y,xs+seg,y+8),4,fill=(255,255,255,90)); d.rounded_rectangle((xs,y,xs+seg*ramp(t,e["t0"],e["t1"]),y+8),4,fill=ACC)
        else: d.rounded_rectangle((xs,y,xs+seg,y+8),4,fill=col)
    txt(L,(x0,y+52),e["label"].upper(),"mono",26,(255,255,255,255),anchor="ls",shadow=8)
    put(F,L,(W/2,H/2),a)
RENDER={"behind_text":R_behind_text,"word_stack":R_word_stack,"poster":R_poster,"prompt":R_prompt,"cards":R_cards,"list":R_list,
 "pop_word":R_pop_word,"stamp":R_stamp,"cta":lambda e,t,F,B:R_box(e,t,F,B,False),"hook_box":lambda e,t,F,B:R_box(e,t,F,B,True),"image":R_image,"chapter":R_chapter}
# ---------- captions ----------
CAP=P.get("captions",{}); CAPY=CAP.get("y",1290); CAPS=CAP.get("size",86); CAPMAX=CAP.get("max_words",4)
def chunks():
    out=[];cur=[]
    for i,w in enumerate(WORDS):
        cur.append(w); gap=(WORDS[i+1]["s"]-w["e"]) if i+1<len(WORDS) else 9
        if len(cur)>=CAPMAX or w["w"][-1] in ".?!" or (w["w"][-1]=="," and len(cur)>=2) or gap>0.35: out.append(cur);cur=[]
    if cur: out.append(cur)
    return out
def phrase_chunks():
    out=[]; nw=[norm(w["w"]) for w in WORDS]; i=0
    for ph in CAP["phrases"]:
        toks=[norm(x) for x in ph.split()]
        for j in range(i,len(WORDS)-len(toks)+1):
            if nw[j:j+len(toks)]==toks:
                out.append(WORDS[j:j+len(toks)]); i=j+len(toks); break
        else: print("caption phrase not found:",ph)
    return out
CH=phrase_chunks() if CAP.get("phrases") else chunks(); EMPH={norm(x) for x in CAP.get("emphasis",[])}
def caption(t):
    if any(a<=t<b for a,b in CAPHIDE): return None
    for k,c in enumerate(CH):
        s=c[0]["s"]; e=min(CH[k+1][0]["s"] if k+1<len(CH) else END, c[-1]["e"]+(0.45 if CAP.get("phrases") else 0.6))
        if not (s-0.05<=t<e): continue
        mixed=CAP.get("style")=="mixed"; ws=[w["w"].strip(",.") for w in c]
        ems=[norm(x) in EMPH for x in ws]
        fs=[font("serif_i",CAPS*1.18) if (mixed and em) else font("sans_xb" if mixed else "serif",CAPS*(0.78 if mixed else 1)) for em in ems]
        f=fs[0]; sp=f.getlength(" "); wd=[fs[i].getlength(x) for i,x in enumerate(ws)]
        lines=[list(range(len(ws)))]
        if sum(wd)+sp*(len(ws)-1)>W-160: m=(len(ws)+1)//2; lines=[list(range(m)),list(range(m,len(ws)))]
        G=layer(); L=layer(); dg=ImageDraw.Draw(G); d=ImageDraw.Draw(L); y0=CAPY-(len(lines)-1)*(CAPS*0.56)
        for li,ln in enumerate(lines):
            lw=sum(wd[i] for i in ln)+sp*(len(ln)-1); x=(W-lw)/2; y=y0+li*CAPS*1.12
            for i in ln:
                on=c[i]["s"]-0.03<=t; em=ems[i] and on; fi=fs[i]
                col=(ACC[:3]+(255,)) if em else ((255,255,255,255) if on else (255,255,255,165))
                if mixed and not on: col=(255,255,255,120)
                dg.text((x,y),ws[i],font=fi,fill=(0,0,0,215),anchor="ls")
                d.text((x,y+3),ws[i],font=fi,fill=(0,0,0,90),anchor="ls"); d.text((x,y),ws[i],font=fi,fill=col,anchor="ls"); x+=wd[i]+sp
        Gb=G.filter(ImageFilter.GaussianBlur(16)); Gb.alpha_composite(G.filter(ImageFilter.GaussianBlur(5))); Gb.alpha_composite(L); return Gb
    return None
# ---------- main ----------
VID=pth(P["video"]); MATTE=pth(P["matte"]) if P.get("matte") else None
M=np.memmap(MATTE,np.uint8,"r").reshape(-1,960,540) if MATTE else None
stills={round(float(s)*FPS) for s in A.stills.split(",") if s} 
os.makedirs(pth(A.stills_dir),exist_ok=True)
dec=subprocess.Popen(["ffmpeg","-v","error","-i",VID,"-f","rawvideo","-pix_fmt","rgb24","-"],stdout=subprocess.PIPE,bufsize=10**8)
enc=None if stills else subprocess.Popen(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-",
 "-c:v","libx264","-preset","medium","-crf","17","-pix_fmt","yuv420p",pth(A.out)],stdin=subprocess.PIPE)
LOOK=P.get("look"); LOOK_T0=T(LOOK["from"]) if LOOK and "from" in LOOK else -1
if LOOK:
    yy,xx=np.mgrid[0:H,0:W]; rr=np.sqrt(((xx-W/2)/(W/2))**2+((yy-H*0.45)/(H/2))**2)
    VIG=(1-LOOK.get("vignette",0.18)*np.clip((rr-0.6)/0.8,0,1)**1.5).astype(np.float32)
rng=np.random.default_rng(7); n=0; maxn=max(stills) if stills else 10**9
while n<=maxn:
    b=dec.stdout.read(W*H*3)
    if len(b)<W*H*3: break
    t=n/FPS
    if stills and n not in stills: n+=1; continue
    fr=Image.frombytes("RGB",(W,H),b)
    mt=Image.fromarray(np.asarray(M[min(n,len(M)-1)])).resize((W,H),Image.BILINEAR) if M is not None else None
    z=zoom(t); dx,dy=shake(t)
    if dx or dy: z=max(z,1.03)
    fr=cam(fr,z,dx,dy); mt=cam(mt,z,dx,dy) if mt is not None else None
    for g0,g1,mode in GRADE:
        if g0<=t<g1 and mode=="raw":
            arr=np.asarray(fr,np.float32); g=arr.mean(2,keepdims=True); arr=arr*0.82+g*0.18; arr=(arr-128)*0.94+128
            fr=Image.fromarray(np.clip(arr,0,255).astype(np.uint8))
        if g0<=t<g1 and mode=="bw":
            arr=np.asarray(fr.convert("L"),np.int16)+rng.integers(-14,15,(H,W),dtype=np.int16)
            fr=Image.fromarray(np.clip((arr-128)*1.12+128,0,255).astype(np.uint8)).convert("RGB")
    if LOOK and t>=LOOK_T0:
        arr=np.asarray(fr,np.float32)
        arr=(arr-128)*LOOK.get("contrast",1.08)+128
        arr[...,0]*=LOOK.get("warm_r",1.03); arr[...,2]*=LOOK.get("warm_b",0.97)
        arr=np.clip(arr*VIG[...,None],0,255).astype(np.uint8); fr=Image.fromarray(arr)
    base=fr.convert("RGBA")
    bl=max([ramp(t,a,a+0.35)*(1-ramp(t,b2-0.35,b2)) for a,b2 in BLUR]+[0])
    if bl>0 and mt is not None: base=Image.composite(base,fr.filter(ImageFilter.GaussianBlur(P.get("blur_px",14)*bl)).convert("RGBA"),mt)
    F=layer(); B=layer()
    for e in EL: RENDER[e["type"]](e,t,F,B)
    if A.overlay:
        pb=os.path.join(pth(A.overlay),"behind",f"f_{n:06d}.png"); pf=os.path.join(pth(A.overlay),"front",f"f_{n:06d}.png")
        if os.path.exists(pb): B.alpha_composite(Image.open(pb).convert("RGBA"))
        if os.path.exists(pf): F.alpha_composite(Image.open(pf).convert("RGBA"))
    if B.getbbox():
        wt=Image.alpha_composite(base,B); base=Image.composite(base,wt,mt) if mt is not None else wt
    for f0 in FLASH:
        if f0<=t<f0+0.35: base.alpha_composite(Image.new("RGBA",(W,H),(255,255,255,int(P.get("flash_alpha",190)*(1-ramp(t,f0,f0+0.35))))))
    base.alpha_composite(F)
    cp=caption(t)
    if cp is not None: base.alpha_composite(cp)
    out=base.convert("RGB")
    if stills: out.save(os.path.join(pth(A.stills_dir),f"s_{t:06.2f}.jpg"),quality=88)
    else: enc.stdin.write(out.tobytes())
    n+=1
    if n%150==0: print("frame",n,flush=True)
if enc: enc.stdin.close(); enc.wait()
dec.kill(); print("done",n)
