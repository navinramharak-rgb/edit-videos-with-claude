#!/usr/bin/env python3
"""HTML + GSAP overlay renderer (nav-signature style).
Builds one HTML page per layer (front / behind) from plan.json, drives a GSAP timeline frame by frame
in headless Chromium, and writes transparent RGBA PNGs: OUT/front/f_000123.png, OUT/behind/f_000123.png.
Only frames where something is visible are written; the compositor treats missing frames as empty.

Usage: python overlay.py plan.json -o overlay_dir [--only front|behind] [--stills t1,t2]
Element types (engine html): hook_box, poster, list_panel, cards, prompt, behind_text, word_stack, stamp, cta, card_image, board
"""
import argparse, json, os, re, subprocess, sys, html as H, numpy as np
SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); FONT_DIR = os.path.join(SKILL, "assets", "fonts"); GSAP = os.path.join(SKILL, "assets", "vendor", "gsap.min.js")
from PIL import Image

ap = argparse.ArgumentParser(); ap.add_argument("plan"); ap.add_argument("-o", "--out", required=True)
ap.add_argument("--only", default=""); ap.add_argument("--stills", default=""); ap.add_argument("--fps", type=int, default=30)
A = ap.parse_args(); P = json.load(open(A.plan)); BASE = os.path.dirname(os.path.abspath(A.plan)); FPS = A.fps
def pth(p): return p if os.path.isabs(p) else os.path.join(BASE, p)
WORDS = json.load(open(pth(P["words"])))
def norm(w): return re.sub(r"[^a-z0-9']", "", w.lower())
def _ref(v, end=False):
    if isinstance(v, (int, float)): return float(v)
    if v.strip().endswith("<"): v = v.strip()[:-1]; end = False
    m = re.match(r"@([^#+\-]+)(?:#(\d+))?([+\-][\d.]+)?$", v.strip())
    if not m: raise ValueError(v)
    word, occ, off = m.group(1), int(m.group(2) or 0), float(m.group(3) or 0)
    hits = [w for w in WORDS if norm(w["w"]) == norm(word)]
    if len(hits) <= occ: raise KeyError(f"word not found: {v}")
    return (hits[occ]["e"] if end else hits[occ]["s"]) + off
T = lambda v: _ref(v); TE = lambda v: _ref(v, True)
END = P.get("duration") or (WORDS[-1]["e"] + 0.4)
EL = [e for e in P["elements"] if e.get("engine", "html") == "html"]
for e in EL:
    for it in e.get("items", []):
        if "t" in it: it["t"] = T(it["t"])
        if "t_end" in it: it["t_end"] = TE(it["t_end"])
    if "clips" in e: e["clips"] = [[T(a), TE(b)] for a, b in e["clips"]]
    if "t0" not in e: e["t0"] = e["items"][0]["t"]
    e["t0"] = T(e["t0"]); e["t1"] = TE(e["t1"]) if "t1" in e else END
    if "type_end" in e: e["type_end"] = T(e["type_end"])
    for ln in e.get("lines", []):
        if "t" in ln: ln["t"] = T(ln["t"])
ST = P.get("style", {}); ACC = ST.get("accent", "#FF6B2E")
os.makedirs(A.out, exist_ok=True)

# ---------- cutouts (person PNG from matte) ----------
MATTE = pth(P["matte"]) if P.get("matte") else None
M = np.memmap(MATTE, np.uint8, "r").reshape(-1, 960, 540) if MATTE else None
def cutout(t, name):
    f = os.path.join(A.out, f"cut_{name}.png")
    if os.path.exists(f): return f
    n = int(round(t * FPS))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", pth(P["video"]), "-frames:v", "1", f + ".jpg"], check=True)
    im = Image.open(f + ".jpg").convert("RGBA")
    a = Image.fromarray(np.asarray(M[min(n, len(M) - 1)])).resize(im.size, Image.BILINEAR); im.putalpha(a); im.save(f); os.remove(f + ".jpg"); return f
for i, e in enumerate(EL):
    if e.get("cutout"):
        e["cutout_png"] = cutout(T(e["cutout"]) if isinstance(e["cutout"], str) else e["cutout"], f"{i}")

# ---------- HTML ----------
CSS = """
@font-face{font-family:Anton;src:url(FONTDIR/Anton-Regular.ttf)}
@font-face{font-family:Bebas;src:url(FONTDIR/BebasNeue-Regular.ttf)}
@font-face{font-family:ISerif;src:url(FONTDIR/InstrumentSerif-Regular.ttf)}
@font-face{font-family:ISerif;font-style:italic;src:url(FONTDIR/InstrumentSerif-Italic.ttf)}
@font-face{font-family:Inter;font-weight:500;src:url(FONTDIR/Inter-Medium.ttf)}
@font-face{font-family:Inter;font-weight:700;src:url(FONTDIR/Inter-Bold.ttf)}
@font-face{font-family:Inter;font-weight:800;src:url(FONTDIR/Inter-ExtraBold.ttf)}
@font-face{font-family:Inter;font-weight:900;src:url(FONTDIR/Inter-Black.ttf)}
@font-face{font-family:Mono;src:url(FONTDIR/DejaVuSansMono.ttf)}
*{box-sizing:border-box;margin:0}html,body{background:transparent;width:1080px;height:1920px;overflow:hidden}
body{font-family:Inter;position:relative}
.el{position:absolute;opacity:0;will-change:transform,opacity}
.acc{color:ACC}
.grain{position:absolute;inset:-200px;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.5'/%3E%3C/svg%3E");opacity:.13;mix-blend-mode:overlay;pointer-events:none}
/* hook box */
.hook{left:50%;top:150px;transform:translateX(-50%) rotate(-2deg);background:#fff;color:#111;font:800 56px/1 Inter;padding:26px 40px;border-radius:14px;box-shadow:0 30px 60px rgba(0,0,0,.45);white-space:nowrap;transform-origin:center}
/* poster */
.poster{inset:0;background:linear-gradient(160deg,#ff8a4c 0%,ACC 45%,#e4521a 100%);overflow:hidden}
.poster.dark{background:linear-gradient(160deg,#1a1a1c 0%,#0d0d0f 100%)}
.poster .small{position:absolute;left:0;right:0;text-align:center;font:italic 400 110px/1 ISerif;color:#fff}
.poster .big{position:absolute;left:0;right:0;text-align:center;font:400 500px/.82 Anton;color:#111;text-transform:uppercase;letter-spacing:-.01em}
.poster.dark .big{color:#fff}.poster .big.orange{color:ACC}
.poster .big .ch{display:inline-block}
.poster .rule{position:absolute;left:50%;height:10px;background:#111;border-radius:5px;transform-origin:left center}
.poster .sub{position:absolute;left:60px;right:60px;text-align:center;font:400 78px/1.1 Bebas;color:#fff;letter-spacing:.12em}
.poster .cut{position:absolute;left:0;width:1080px;height:1920px;object-fit:cover;transform-origin:top center;filter:drop-shadow(0 40px 60px rgba(0,0,0,.45))}
/* glass panel list */
.panel{left:60px;right:60px;background:rgba(10,10,12,.78);backdrop-filter:blur(16px);border-radius:30px;padding:36px 40px;border:2px solid rgba(255,140,80,.85);box-shadow:0 0 50px rgba(255,107,46,.45),0 30px 60px rgba(0,0,0,.5);transform-origin:center bottom}
.panel .t{font:400 64px/1 ISerif;color:#fff;margin-bottom:22px}
.panel .it{display:flex;align-items:center;gap:20px;font:700 46px/1 Inter;color:#fff;padding:15px 0;border-top:1px solid rgba(255,255,255,.12);opacity:.3}
.panel .it .n{width:54px;height:54px;border-radius:50%;background:rgba(255,255,255,.14);color:#fff;font-size:28px;display:flex;align-items:center;justify-content:center;flex:none}
.panel .it.on{opacity:1}.panel .it.cur .n{background:ACC;color:#111}
/* cards / chips */
.chip{background:#fff;color:#111;font:700 44px/1 Inter;padding:34px 36px;border-radius:30px;box-shadow:0 24px 50px rgba(0,0,0,.45);white-space:nowrap;display:flex;align-items:center;gap:18px;transform-origin:center}
.chip .dot{width:46px;height:46px;border-radius:50%;flex:none}
.chip.dark{background:#111;color:#fff}
/* prompt bar */
.prompt{left:90px;width:900px;background:#f7f4ee;border-radius:34px;padding:34px 40px;box-shadow:0 24px 60px rgba(0,0,0,.45)}
.prompt .lbl{font:400 24px/1 Mono;color:#8c8880;margin-bottom:16px}
.prompt .tx{font:500 44px/1 Inter;color:#191919;white-space:nowrap;overflow:hidden}
.prompt .cur{display:inline-block;width:3px;height:46px;background:#191919;vertical-align:middle;margin-left:3px}
.prompt .go{position:absolute;right:36px;top:50%;transform:translateY(-50%);width:60px;height:60px;border-radius:50%;background:ACC;color:#fff;font:700 34px/60px Inter;text-align:center}
/* behind text */
.behind{left:0;right:0;text-align:center;font:400 520px/1 ISerif;color:#fff;white-space:nowrap}
.behind.anton{font-family:Anton;text-transform:uppercase;letter-spacing:-.01em}
/* stamp */
.stamp{left:50%;transform:translateX(-50%) rotate(-6deg);border:12px solid ACC;color:ACC;font:900 120px/1 Inter;padding:14px 40px;border-radius:24px;background:rgba(0,0,0,.25);white-space:nowrap;transform-origin:center}
/* cta */
.cta{left:50%;background:#111;white-space:nowrap;border-radius:28px;padding:36px 44px;box-shadow:0 30px 70px rgba(0,0,0,.5);transform-origin:center bottom}
.cta .t{font:400 96px/1 Bebas;color:#fff;letter-spacing:.04em}
.cta .btn{margin-top:22px;display:inline-block;background:ACC;color:#111;font:800 36px/1 Inter;padding:20px 30px;border-radius:14px}
/* hook split */
.split{inset:0;overflow:hidden}
.split .half{position:absolute;top:0;width:540px;height:1920px;overflow:hidden}
.split .half img{position:absolute;top:0;width:1080px;height:1920px;object-fit:cover}
.split .l{left:0}.split .r{left:540px}.split .r img{left:-540px}
.split .bar{position:absolute;left:538px;top:0;width:4px;height:1920px;background:#fff;box-shadow:0 0 30px rgba(0,0,0,.6)}
.split .tag{position:absolute;top:1700px;font:400 30px/1 Mono;color:#fff;background:rgba(0,0,0,.65);padding:12px 18px;border-radius:8px}
.split .tag.l{left:40px}.split .tag.r{right:40px;background:ACC;color:#111}
/* outro */
.outro{inset:0;background:#0f0f10}
.outro .h{position:absolute;left:0;right:0;top:420px;text-align:center;font:400 200px/1 Bebas;color:#fff;letter-spacing:.04em}
.outro .h b{color:ACC;font-weight:400}
.outro .box{position:absolute;left:90px;right:90px;top:720px;background:#1c1c1e;border:2px solid #2c2c2e;border-radius:40px;padding:34px 40px;display:flex;align-items:center;gap:22px}
.outro .box .av{width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,#ff8a4c,#e4521a);flex:none}
.outro .box .tx{font:500 52px/1 Inter;color:#fff}
.outro .box .tx .c{display:inline-block;width:4px;height:52px;background:#fff;vertical-align:middle;margin-left:4px}
.outro .box .post{margin-left:auto;font:700 36px/1 Inter;color:ACC}
.outro .sub{position:absolute;left:0;right:0;top:900px;text-align:center;font:italic 400 70px/1 ISerif;color:rgba(255,255,255,.8)}
.outro .brand{position:absolute;left:0;right:0;top:1560px;text-align:center;font:400 64px/1 Bebas;color:#fff;letter-spacing:.3em}
.outro .skill{position:absolute;left:0;right:0;top:1640px;text-align:center;font:400 30px/1 Mono;color:ACC}
/* raw tag */
.rawtag{left:50px;top:1760px;font:400 30px/1 Mono;color:#fff;background:rgba(0,0,0,.6);padding:14px 20px;border-radius:8px;letter-spacing:.05em}
.rawtag i{display:inline-block;width:16px;height:16px;border-radius:50%;background:#ff4a3d;margin-right:14px;vertical-align:middle}
/* cut marker */
.cutmark{left:0;top:0;width:1080px;height:1920px}
.cutmark .l{position:absolute;top:0;bottom:0;width:6px;background:#fff;left:50%;margin-left:-3px}
/* caption pill */
.pill{left:50%;background:#fff;color:#111;font:400 88px/1 ISerif;padding:22px 44px;border-radius:22px;white-space:nowrap;box-shadow:0 24px 60px rgba(0,0,0,.45)}
.pill .acc{color:ACC}
/* zoom brackets */
.brk{left:0;top:0;width:1080px;height:1920px}
.brk i{position:absolute;width:90px;height:90px;border:6px solid #fff;border-radius:6px}
.brk .tl{left:120px;top:380px;border-right:0;border-bottom:0}.brk .tr{right:120px;top:380px;border-left:0;border-bottom:0}
.brk .bl{left:120px;bottom:620px;border-right:0;border-top:0}.brk .br{right:120px;bottom:620px;border-left:0;border-top:0}
/* timeline */
.tlw{left:60px;right:60px;background:rgba(10,10,12,.78);backdrop-filter:blur(16px);border-radius:28px;padding:28px 34px;border:2px solid rgba(255,140,80,.5);box-shadow:0 30px 60px rgba(0,0,0,.5)}
.tlw .row{position:relative;height:54px;margin:10px 0;border-radius:10px;background:rgba(255,255,255,.06)}
.tlw .lab{position:absolute;left:14px;top:50%;transform:translateY(-50%);font:400 22px/1 Mono;color:rgba(255,255,255,.55);letter-spacing:.08em}
.tlw .clip{position:absolute;top:8px;height:38px;border-radius:8px;background:rgba(255,255,255,.22)}
.tlw .cap{position:absolute;top:14px;height:26px;border-radius:6px;background:rgba(255,255,255,.35)}
.tlw .key{position:absolute;top:17px;width:20px;height:20px;transform:rotate(45deg);background:rgba(255,255,255,.5);border-radius:3px}
.tlw .on{background:ACC !important}
.tlw .cutl{position:absolute;top:4px;height:46px;width:4px;background:#fff;opacity:.5}
.tlw .ph{position:absolute;top:18px;bottom:18px;width:3px;background:ACC;box-shadow:0 0 14px ACC}
.tlw .ph:before{content:"";position:absolute;top:-14px;left:-8px;width:19px;height:14px;background:ACC;clip-path:polygon(0 0,100% 0,50% 100%)}
/* image card */
.icard{left:50%;transform:translateX(-50%);border-radius:36px;overflow:hidden;box-shadow:0 40px 80px rgba(0,0,0,.55);transform-origin:center;background:#111}
.icard img{display:block;width:100%;height:100%;object-fit:cover}
.icard .lab{position:absolute;left:0;right:0;bottom:0;padding:18px;text-align:center;font:400 26px/1 Mono;color:#fff;background:linear-gradient(transparent,rgba(0,0,0,.7))}
.board{inset:0;background:rgba(8,8,10,.82)}
.board img{position:absolute;left:50%;transform:translateX(-50%);border-radius:28px;box-shadow:0 40px 90px rgba(0,0,0,.6)}
/* profile card (Sahas-style popup) */
.pcard{left:50%;background:#fff;border-radius:34px;padding:28px 44px 28px 28px;display:flex;align-items:center;gap:26px;box-shadow:0 30px 70px rgba(0,0,0,.5);transform-origin:center;white-space:nowrap}
.pcard img,.pcard .av{width:120px;height:120px;border-radius:50%;flex:none;object-fit:cover}
.pcard .av{background:linear-gradient(135deg,#ff8a4c,#e4521a);color:#111;font:900 64px/120px Inter;text-align:center}
.pcard .nm{font:800 46px/1.1 Inter;color:#111}.pcard .hd{font:500 30px/1.2 Inter;color:#8a8a8a;margin-top:6px}
.pcard .x{position:absolute;right:-50px;top:-50px;width:150px;height:150px;opacity:0;transform-origin:center}
.pcard .x:before,.pcard .x:after{content:"";position:absolute;left:50%;top:50%;width:150px;height:30px;margin:-15px 0 0 -75px;background:#ff2d2d;border-radius:8px;transform:rotate(45deg);box-shadow:0 10px 30px rgba(0,0,0,.35)}
.pcard .x:after{transform:rotate(-45deg)}
.pcard .ok{position:absolute;right:-46px;top:-46px;width:130px;height:130px;border-radius:50%;background:ACC;opacity:0;transform-origin:center;box-shadow:0 10px 30px rgba(0,0,0,.35)}
.pcard .ok:after{content:"";position:absolute;left:40px;top:28px;width:34px;height:62px;border:solid #111;border-width:0 14px 14px 0;transform:rotate(45deg)}
/* kinetic extruded word */
.kin{left:50%;font:400 400px/1 Anton;text-transform:uppercase;color:ACC;white-space:nowrap;letter-spacing:-.01em;
 text-shadow:2px 2px 0 #b8451a,4px 4px 0 #b8451a,6px 6px 0 #b8451a,8px 8px 0 #b8451a,10px 10px 0 #b8451a,12px 12px 0 #b8451a,14px 14px 0 #b8451a,16px 16px 0 #b8451a,18px 18px 0 #b8451a,20px 20px 0 #b8451a,22px 22px 0 #b8451a,24px 24px 0 #b8451a,26px 26px 0 #b8451a,28px 28px 0 #b8451a,30px 30px 0 #b8451a,34px 34px 40px rgba(0,0,0,.5)}
.kin.white{color:#fff;text-shadow:2px 2px 0 #333,4px 4px 0 #333,6px 6px 0 #333,8px 8px 0 #333,10px 10px 0 #333,12px 12px 0 #333,14px 14px 0 #333,16px 16px 0 #333,18px 18px 0 #333,20px 20px 0 #333,22px 22px 0 #333,24px 24px 0 #333,26px 26px 0 #333,28px 28px 0 #333,30px 30px 0 #333,34px 34px 40px rgba(0,0,0,.5)}
/* film strip + frame counter */
.strip{left:0;top:0;width:1080px;overflow:hidden}
.strip .trk{position:absolute;left:0;top:34px;display:flex;gap:0;background:#0b0b0c;padding:26px 0;box-shadow:0 20px 50px rgba(0,0,0,.5)}
.strip .trk img{width:300px;height:169px;object-fit:cover;margin:0 10px;border-radius:4px;flex:none}
.strip .holes{position:absolute;left:0;right:0;height:16px;background:repeating-linear-gradient(90deg,transparent 0 18px,#2a2a2c 18px 36px)}
.strip .holes.a{top:6px}.strip .holes.b{bottom:6px}
.strip .cnt{position:absolute;right:50px;top:270px;font:400 44px/1 Mono;color:#fff;background:rgba(0,0,0,.65);padding:14px 22px;border-radius:10px;letter-spacing:.06em}
.strip .cnt b{color:ACC;font-weight:400}
/* exploded layers */
.expl{inset:0;background:#0d0d0f;overflow:hidden}
.expl .st{position:absolute;left:0;top:0;width:1080px;height:1920px}
.expl .ly{position:absolute;left:50%;top:50%;width:1080px;height:1920px;margin:-960px 0 0 -540px;border-radius:40px;overflow:hidden;box-shadow:0 60px 120px rgba(0,0,0,.6);background:rgba(255,255,255,.07);border:3px solid rgba(255,140,80,.45)}
.expl .ly img{position:absolute;left:0;top:0;width:100%;height:100%;object-fit:cover}
.expl .ly.vid img{filter:none}
.expl .lab{position:absolute;left:60px;top:1620px;font:400 56px/1 Bebas;color:#fff;letter-spacing:.1em;opacity:0}
.expl .lab i{display:inline-block;width:22px;height:22px;border-radius:50%;background:ACC;margin-right:18px;vertical-align:middle}
.expl .ttl{position:absolute;left:0;right:0;top:50px;text-align:center;font:italic 400 90px/1 ISerif;color:#fff;opacity:0}
/* silhouette */
.sil{inset:0;background:radial-gradient(ellipse at 50% 40%,#2a1408 0%,#0b0b0c 60%)}
.sil .glow{position:absolute;left:50%;top:40%;width:1300px;height:1300px;margin:-650px 0 0 -650px;border-radius:50%;background:radial-gradient(circle,rgba(255,150,90,1) 0%,rgba(255,107,46,.55) 30%,transparent 68%);filter:blur(20px)}
.sil img{position:absolute;left:0;top:0;width:1080px;height:1920px;filter:brightness(0) drop-shadow(0 0 28px rgba(255,107,46,.9))}
.sil .w{position:absolute;left:0;right:0;text-align:center;font:400 190px/1 Anton;color:#fff;text-transform:uppercase;letter-spacing:.02em}
/* phone fan */
.fan{inset:0}
.fan .ph{position:absolute;left:50%;top:60%;width:440px;height:780px;margin:-390px 0 0 -220px;border-radius:44px;background:#141416;border:8px solid #2a2a2e;box-shadow:0 40px 90px rgba(0,0,0,.6);overflow:hidden;transform-origin:50% 120%}
.fan .ph img{width:100%;height:100%;object-fit:cover;display:block}
.fan .ph .n{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font:400 260px/1 Anton;color:ACC;opacity:.55}
.fan .ph .yours{position:absolute;left:0;right:0;bottom:0;padding:16px;text-align:center;font:400 26px/1 Mono;color:#fff;background:linear-gradient(transparent,rgba(0,0,0,.75))}
/* reactions (comment box add-on) */
.react{position:absolute;width:110px;height:110px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;font:900 54px/1 Inter;color:#ff2d55;box-shadow:0 20px 40px rgba(0,0,0,.4);opacity:0;transform-origin:center}
.react.e{background:ACC;color:#111;font-size:34px;border-radius:30px;width:auto;padding:0 28px;height:90px}
/* cut timeline with removed takes */
.tlw .rm{position:absolute;top:8px;height:38px;border-radius:8px;background:rgba(255,45,45,.75);opacity:0}
.tlw .rm span{position:absolute;left:50%;top:-40px;transform:translateX(-50%);font:400 20px/1 Mono;color:#ff5c5c;white-space:nowrap}
.tlw .tx{position:relative;height:44px;margin:10px 0 0;font:400 24px/44px Mono;color:rgba(255,255,255,.55);white-space:nowrap;overflow:hidden}
.tlw .tx s{color:#ff5c5c}
""".replace("ACC", ACC).replace("FONTDIR", "file://" + FONT_DIR)

def esc(s): return H.escape(str(s))
def accent(txt):  # *word* -> accent span
    return re.sub(r"\*(.+?)\*", r'<span class="acc">\1</span>', esc(txt)).replace("&lt;br&gt;", "<br>")

def build(layer):
    body, js = [], []
    for i, e in enumerate(EL):
        beh = bool(e.get("behind")) or e["type"] in ("behind_text", "word_stack")
        if (layer == "behind") != beh: continue
        ty, id_ = e["type"], f"e{i}"; t0, t1 = e["t0"], e["t1"]
        if ty == "hook_box":
            body.append(f'<div class="el hook" id="{id_}" style="top:{e.get("y",150)}px">{accent(e["text"])}</div>')
            js.append(f'''tl.fromTo("#{id_}",{{opacity:0,scale:.6,rotation:-8}},{{opacity:1,scale:1,rotation:-2,duration:.45,ease:"back.out(1.8)"}},{t0});
tl.to("#{id_}",{{opacity:0,y:-40,duration:.25,ease:"power2.in"}},{t1-0.25});''')
        elif ty == "poster":
            cls = "poster" + (" dark" if e.get("theme") == "dark" else "")
            inner = ""
            small = e.get("small"); big = e.get("big"); sub = e.get("sub")
            if small: inner += f'<div class="small" id="{id_}s" style="top:{e.get("small_y",200)}px">{accent(small)}</div>'
            if big:
                chars = "".join(f'<span class="ch">{esc(c) if c!=" " else "&nbsp;"}</span>' for c in big)
                inner += f'<div class="big{" orange" if e.get("big_orange") else ""}" id="{id_}b" style="top:{e.get("big_y",330)}px;font-size:{e.get("big_size",500)}px">{chars}</div>'
            if big: inner += f'<div class="rule" id="{id_}r" style="top:{e.get("rule_y",e.get("big_y",330)+e.get("big_size",500)*0.9)}px;width:{e.get("rule_w",760)}px"></div>'
            if sub: inner += f'<div class="sub" id="{id_}u" style="top:{e.get("sub_y",800)}px">{accent(sub)}</div>'
            if e.get("cutout_png"): inner += f'<img class="cut" id="{id_}c" src="file://{os.path.abspath(e["cutout_png"])}" style="top:{e.get("cut_y",760)}px;left:0">'
            inner += '<div class="grain"></div>'
            body.append(f'<div class="el {cls}" id="{id_}">{inner}</div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0,scale:1.06}},{{opacity:1,scale:1,duration:.22,ease:"power3.out"}},{t0});')
            if small: js.append(f'tl.fromTo("#{id_}s",{{opacity:0,y:30}},{{opacity:1,y:0,duration:.35,ease:"power3.out"}},{t0+0.05});')
            if big: js.append(f'tl.fromTo("#{id_}b .ch",{{opacity:0,scale:1.6,y:40}},{{opacity:1,scale:1,y:0,duration:.5,ease:"power4.out",stagger:.035}},{t0+0.08});')
            if big: js.append(f'tl.fromTo("#{id_}r",{{scaleX:0,xPercent:-50}},{{scaleX:1,xPercent:-50,duration:.45,ease:"power4.out"}},{t0+0.3});')
            if sub: js.append(f'tl.fromTo("#{id_}u",{{opacity:0,y:40}},{{opacity:1,y:0,duration:.4,ease:"power3.out"}},{t0+0.45});')
            js.append(f'tl.fromTo("#{id_}b",{{scale:1}},{{scale:1.03,duration:{max(0.5,t1-t0)},ease:"none",transformOrigin:"center"}},{t0+0.5});')
            if e.get("cutout_png"): js.append(f'tl.fromTo("#{id_}c",{{opacity:0,y:160,scale:{e.get("cut_scale",.92)},transformOrigin:"top center"}},{{opacity:1,y:0,scale:{e.get("cut_scale",.92)},duration:.55,ease:"power4.out"}},{t0+0.2});')
            js.append(f'tl.to("#{id_}",{{opacity:0,duration:.18,ease:"power2.in"}},{t1-0.18});')
        elif ty == "list_panel":
            its = "".join(f'<div class="it" id="{id_}i{k}"><span class="n">{k+1}</span>{esc(it["text"])}</div>' for k, it in enumerate(e["items"]))
            body.append(f'<div class="el panel" id="{id_}" style="top:{e.get("y",1330)}px"><div class="t">{accent(e.get("title",""))}</div>{its}</div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0,y:60,scale:.96}},{{opacity:1,y:0,scale:1,duration:.45,ease:"power3.out"}},{t0});')
            for k, it in enumerate(e["items"]):
                js.append(f'tl.call(()=>{{document.querySelectorAll("#{id_} .it").forEach(x=>x.classList.remove("cur"));let q=document.getElementById("{id_}i{k}");q.classList.add("on","cur")}},null,{it["t"]});')
                js.append(f'tl.fromTo("#{id_}i{k}",{{x:30}},{{x:0,duration:.3,ease:"power3.out"}},{it["t"]});')
            js.append(f'tl.to("#{id_}",{{opacity:0,y:40,duration:.25,ease:"power2.in"}},{t1-0.25});')
        elif ty == "cards":
            n = len(e["items"]); y = e.get("y", 1520)
            for k, it in enumerate(e["items"]):
                dot = f'<span class="dot" style="background:{it["dot"]}"></span>' if it.get("dot") else ""
                xs = e.get("xs") or ([540] if n == 1 else [int(120 + k * (840 / (n - 1))) for k in range(n)])
                rot = it.get("rot", [-6, 2, 7, -3, 4][k % 5])
                body.append(f'<div class="el chip{" dark" if it.get("dark") else ""}" id="{id_}c{k}" style="left:{xs[k]}px;top:{y}px;transform:translate(-50%,-50%) rotate({rot}deg)">{dot}{accent(it["text"])}</div>')
                js.append(f'tl.fromTo("#{id_}c{k}",{{opacity:0,scale:.3,rotation:{rot-14}}},{{opacity:1,scale:1,rotation:{rot},duration:.5,ease:"back.out(2.2)",transformOrigin:"center"}},{it["t"]-0.03});')
                js.append(f'tl.to("#{id_}c{k}",{{opacity:0,y:40,duration:.22,ease:"power2.in"}},{t1-0.22});')
        elif ty == "prompt":
            body.append(f'<div class="el prompt" id="{id_}" style="top:{e.get("y",1480)}px"><div class="lbl">{esc(e.get("label","TO CLAUDE"))}</div><div class="tx"><span id="{id_}t"></span><span class="cur"></span></div><div class="go">↑</div></div>')
            te = e.get("type_end", t1 - 0.3); txt = e["text"]
            js.append(f'tl.fromTo("#{id_}",{{opacity:0,y:70}},{{opacity:1,y:0,duration:.4,ease:"power3.out"}},{t0});')
            js.append(f'tl.to({{}},{{duration:{te-(t0+0.15)},onUpdate:function(){{let p=this.progress();document.getElementById("{id_}t").textContent={json.dumps(txt)}.slice(0,Math.round(p*{len(txt)}))}}}},{t0+0.15});')
            js.append(f'tl.to("#{id_}",{{opacity:0,y:40,duration:.25,ease:"power2.in"}},{t1-0.25});')
        elif ty in ("behind_text", "word_stack"):
            items = e.get("items") or [{"text": e["text"], "t": t0}]
            for k, it in enumerate(items):
                te_ = items[k + 1]["t"] if k + 1 < len(items) else t1
                cls = "behind" + (" anton" if e.get("font") == "anton" else "")
                body.append(f'<div class="el {cls}" id="{id_}w{k}" style="top:{e.get("y",60)}px;font-size:{e.get("size",520)}px;color:{it.get("color","#fff")};opacity:0">{esc(it["text"])}</div>')
                js.append(f'tl.fromTo("#{id_}w{k}",{{opacity:0,scale:.92,y:30}},{{opacity:{e.get("opacity",.92)},scale:1,y:0,duration:.35,ease:"power3.out"}},{it["t"]-0.02});')
                js.append(f'tl.to("#{id_}w{k}",{{scale:1.04,duration:{max(0.3,te_-it["t"])},ease:"none"}},{it["t"]+0.3});')
                js.append(f'tl.to("#{id_}w{k}",{{opacity:0,duration:.22,ease:"power2.in"}},{te_-0.22});')
        elif ty == "stamp":
            body.append(f'<div class="el stamp" id="{id_}" style="top:{e.get("y",1500)}px">{esc(e["text"])}</div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0,scale:1.8,rotation:-14}},{{opacity:1,scale:1,rotation:-6,duration:.22,ease:"power4.in"}},{t0-0.1});')
            js.append(f'tl.to("#{id_}",{{opacity:0,duration:.2}},{t1-0.2});')
        elif ty == "cta":
            body.append(f'<div class="el cta" id="{id_}" style="top:{e.get("y",1480)}px"><div class="t">{accent(e["text"])}</div>{"<div class=btn>"+esc(e["btn"])+"</div>" if e.get("btn") else ""}</div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0,y:80,scale:.94,xPercent:-50}},{{opacity:1,y:0,scale:1,xPercent:-50,duration:.5,ease:"back.out(1.4)"}},{t0});')
            if t1 < END - 0.1: js.append(f'tl.to("#{id_}",{{opacity:0,y:40,duration:.25}},{t1-0.25});')
        elif ty == "hook_split":
            body.append(f'<div class="el split" id="{id_}"><div class="half l" id="{id_}l"><img src="file://{os.path.abspath(pth(e["left"]))}"></div><div class="half r" id="{id_}r"><img src="file://{os.path.abspath(pth(e["right"]))}"></div><div class="bar" id="{id_}b"></div><div class="tag l" id="{id_}tl">{esc(e.get("left_label","RAW"))}</div><div class="tag r" id="{id_}tr">{esc(e.get("right_label","CLAUDE"))}</div></div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:1}},{{opacity:1,duration:.01}},{t0});')
            js.append(f'tl.fromTo("#{id_}l",{{x:-540}},{{x:0,duration:.45,ease:"power4.out"}},{t0});')
            js.append(f'tl.fromTo("#{id_}r",{{x:540}},{{x:0,duration:.45,ease:"power4.out"}},{t0+0.08});')
            js.append(f'tl.fromTo("#{id_}b",{{scaleY:0}},{{scaleY:1,duration:.3,ease:"power3.out",transformOrigin:"top"}},{t0+0.4});')
            js.append(f'tl.fromTo("#{id_}tl, #{id_}tr",{{opacity:0,y:20}},{{opacity:1,y:0,duration:.3,stagger:.1}},{t0+0.5});')
            js.append(f'tl.to("#{id_}l",{{x:-540,duration:.35,ease:"power4.in"}},{t1-0.35});')
            js.append(f'tl.to("#{id_}r",{{x:540,duration:.35,ease:"power4.in"}},{t1-0.35});')
            js.append(f'tl.to("#{id_}b, #{id_}tl, #{id_}tr",{{opacity:0,duration:.2}},{t1-0.3});')
            js.append(f'tl.to("#{id_}",{{opacity:0,duration:.01}},{t1});')
        elif ty == "outro":
            body.append(f'<div class="el outro" id="{id_}"><div class="h" id="{id_}h">{accent(e.get("headline","COMMENT *EDIT*"))}</div><div class="box" id="{id_}x"><div class="av"></div><div class="tx"><span id="{id_}t"></span><span class="c"></span></div><div class="post">Post</div></div><div class="sub" id="{id_}s">{esc(e.get("sub","and I\'ll send you the skill"))}</div><div class="brand" id="{id_}br">{esc(e.get("brand",""))}</div><div class="skill" id="{id_}sk">{esc(e.get("skill",""))}</div></div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0}},{{opacity:1,duration:.25}},{t0});')
            js.append(f'tl.fromTo("#{id_}h",{{opacity:0,y:40,scale:.9}},{{opacity:1,y:0,scale:1,duration:.45,ease:"back.out(1.5)"}},{t0+0.1});')
            js.append(f'tl.fromTo("#{id_}x",{{opacity:0,y:40}},{{opacity:1,y:0,duration:.4,ease:"power3.out"}},{t0+0.35});')
            word=e.get("word","EDIT")
            js.append(f'tl.to({{}},{{duration:.5,onUpdate:function(){{let p=this.progress();document.getElementById("{id_}t").textContent={json.dumps(word)}.slice(0,Math.round(p*{len(word)}))}}}},{t0+0.7});')
            js.append(f'tl.fromTo("#{id_}s",{{opacity:0,y:20}},{{opacity:1,y:0,duration:.35}},{t0+1.0});')
            js.append(f'tl.fromTo("#{id_}br, #{id_}sk",{{opacity:0,y:20}},{{opacity:1,y:0,duration:.35,stagger:.1}},{t0+1.1});')
            if e.get("reactions"):
                rx=[("♥",150,640,-8),("EDIT",800,1000,6),("♥",900,620,10),("EDIT",190,1010,-6),("♥",560,1090,4)]
                for k,(tx,x,y,r) in enumerate(rx):
                    body[-1]=body[-1].replace('<div class="grain">','')  # no-op safety
                    body.append(f'<div class="el react{" e" if tx=="EDIT" else ""}" id="{id_}r{k}" style="left:{x}px;top:{y}px;opacity:0">{tx}</div>')
                    js.append(f'tl.fromTo("#{id_}r{k}",{{opacity:0,scale:.2,rotation:{r-20}}},{{opacity:1,scale:1,rotation:{r},duration:.4,ease:"back.out(2.5)"}},{t0+1.3+k*0.18});')
                    js.append(f'tl.to("#{id_}r{k}",{{y:-30,duration:1.2,repeat:-1,yoyo:true,ease:"sine.inOut"}},{t0+1.7+k*0.18});')
        elif ty == "raw_tag":
            body.append(f'<div class="el rawtag" id="{id_}"><i></i>{esc(e.get("text","RAW · 00:00:07"))}</div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0}},{{opacity:1,duration:.15}},{t0});')
            js.append(f'tl.to("#{id_} i",{{opacity:.2,duration:.5,repeat:-1,yoyo:true,ease:"none"}},{t0});')
            js.append(f'tl.to("#{id_}",{{opacity:0,duration:.08}},{t1-0.08});')
        elif ty == "cut_marker":
            body.append(f'<div class="el cutmark" id="{id_}"><div class="l"></div></div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0}},{{opacity:1,duration:.03}},{t0}); tl.to("#{id_}",{{opacity:0,duration:.06}},{t0+0.07});')
        elif ty == "pill":
            body.append(f'<div class="el pill" id="{id_}" style="top:{e.get("y",1225)}px">{accent(e["text"])}</div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0,y:50,scale:.8,xPercent:-50}},{{opacity:1,y:0,scale:1,xPercent:-50,duration:.4,ease:"back.out(2)"}},{t0-0.03});')
            js.append(f'tl.to("#{id_}",{{opacity:0,y:-30,duration:.2,ease:"power2.in"}},{t1-0.2});')
        elif ty == "brackets":
            body.append(f'<div class="el brk" id="{id_}"><i class="tl"></i><i class="tr"></i><i class="bl"></i><i class="br"></i></div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0,scale:1.25}},{{opacity:1,scale:1,duration:.3,ease:"power4.out",transformOrigin:"540px 760px"}},{t0-0.02});')
            js.append(f'tl.to("#{id_}",{{opacity:0,scale:.95,duration:.25,ease:"power2.in"}},{t1-0.25});')
        elif ty == "timeline":
            its=e["items"]; span=t1-t0; W_=1080-120-68-130
            def px(tt): return 130+W_*max(0,min(1,(tt-t0)/span))
            vclips="".join(f'<div class="clip v" style="left:{px(a)}px;width:{px(b)-px(a)-6}px"></div>' for a,b in e.get("clips",[[t0,t1]]))
            cuts="".join(f'<div class="cutl" id="{id_}k{k}" style="left:{px(it["t"])}px"></div>' for k,it in enumerate(its) if it["kind"]=="cut")
            caps="".join(f'<div class="cap" id="{id_}k{k}" style="left:{px(it["t"])}px;width:{px(it.get("t_end",it["t"]+0.8))-px(it["t"])}px"></div>' for k,it in enumerate(its) if it["kind"]=="caption")
            keys="".join(f'<div class="key" id="{id_}k{k}" style="left:{px(it["t"])-10}px"></div>' for k,it in enumerate(its) if it["kind"]=="zoom")
            rms="".join(f'<div class="rm" id="{id_}m{k}" style="left:{px(it["t"])}px;width:{max(30,px(it.get("t_end",it["t"]+0.6))-px(it["t"]))}px"><span>{esc(it.get("label","cut"))}</span></div>' for k,it in enumerate(its) if it["kind"]=="removed")
            rows=f'<div class="row"><span class="lab">VIDEO</span>{vclips}{cuts}{rms}</div>'
            if not e.get("video_only"): rows+=f'<div class="row"><span class="lab">CAPTIONS</span>{caps}</div><div class="row"><span class="lab">ZOOM</span>{keys}</div>'
            if e.get("transcript"): rows+=f'<div class="tx" id="{id_}x">{re.sub(r"~(.+?)~",r"<s>\1</s>",esc(e["transcript"]))}</div>'
            body.append(f'<div class="el tlw" id="{id_}" style="top:{e.get("y",1480)}px">{rows}<div class="ph" id="{id_}p" style="left:130px;top:{18 if not e.get("video_only") else 46}px;height:{(3*74) if not e.get("video_only") else 54}px;bottom:auto"></div></div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0,y:60}},{{opacity:1,y:0,duration:.4,ease:"power3.out"}},{t0-0.1});')
            js.append(f'tl.fromTo("#{id_}p",{{left:130}},{{left:{130+W_},duration:{span},ease:"none"}},{t0});')
            for k,it in enumerate(its):
                if it["kind"]=="removed": js.append(f'tl.fromTo("#{id_}m{k}",{{opacity:0,scaleX:0}},{{opacity:1,scaleX:1,duration:.25,ease:"power3.out",transformOrigin:"left"}},{it["t"]});')
                else: js.append(f'tl.call(()=>{{document.getElementById("{id_}k{k}").classList.add("on")}},null,{it["t"]});')
            js.append(f'tl.to("#{id_}",{{opacity:0,y:40,duration:.25,ease:"power2.in"}},{t1});')
        elif ty == "card_image":
            w, h = e.get("w", 820), e.get("h", 1000); rot = e.get("rot", -3)
            body.append(f'<div class="el icard" id="{id_}" style="top:{e.get("y",620)-h//2}px;width:{w}px;height:{h}px;transform:translateX(-50%) rotate({rot}deg)"><img src="file://{os.path.abspath(pth(e["path"]))}">{"<div class=lab>"+esc(e["label"])+"</div>" if e.get("label") else ""}</div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0,y:120,scale:.85,rotation:{rot-8}}},{{opacity:1,y:0,scale:1,rotation:{rot},duration:.55,ease:"back.out(1.3)"}},{t0});')
            js.append(f'tl.to("#{id_} img",{{scale:1.06,duration:{t1-t0},ease:"none"}},{t0});')
            js.append(f'tl.to("#{id_}",{{opacity:0,y:60,duration:.25,ease:"power2.in"}},{t1-0.25});')
        elif ty == "board":
            w = e.get("w", 820)
            body.append(f'<div class="el board" id="{id_}"><img id="{id_}i" src="file://{os.path.abspath(pth(e["path"]))}" style="width:{w}px;top:{e.get("y",300)}px"></div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0}},{{opacity:1,duration:.2}},{t0});')
            js.append(f'tl.fromTo("#{id_}i",{{y:80,scale:.9,opacity:0}},{{y:0,scale:1,opacity:1,duration:.5,ease:"power4.out"}},{t0+0.05});')
            js.append(f'tl.to("#{id_}i",{{scale:1.03,duration:{t1-t0},ease:"none"}},{t0});')
            js.append(f'tl.to("#{id_}",{{opacity:0,duration:.22}},{t1-0.22});')
        elif ty == "profile_card":
            av = f'<img src="file://{os.path.abspath(pth(e["avatar"]))}">' if e.get("avatar") else f'<div class="av">{esc(e.get("letter","C"))}</div>'
            mark = e.get("mark", "x"); rot = e.get("rot", -3)
            body.append(f'<div class="el pcard" id="{id_}" style="top:{e.get("y",300)}px;transform:translateX(-50%) rotate({rot}deg)">{av}<div><div class="nm">{esc(e["name"])}</div><div class="hd">{esc(e.get("handle",""))}</div></div><div class="{"x" if mark=="x" else "ok"}" id="{id_}m"></div></div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0,scale:.5,rotation:{rot-12},xPercent:-50,y:60}},{{opacity:1,scale:1,rotation:{rot},xPercent:-50,y:0,duration:.45,ease:"back.out(1.9)"}},{t0});')
            tm = T(e["mark_at"]) if "mark_at" in e else t0 + 0.45
            js.append(f'tl.fromTo("#{id_}m",{{opacity:0,scale:3,rotation:30}},{{opacity:1,scale:1,rotation:0,duration:.22,ease:"power4.in"}},{tm});')
            js.append(f'tl.to("#{id_}",{{x:6,duration:.04,repeat:5,yoyo:true,ease:"none"}},{tm+0.2});')
            js.append(f'tl.to("#{id_}",{{opacity:0,y:-50,scale:.9,duration:.25,ease:"power2.in"}},{t1-0.25});')
        elif ty == "kinetic":
            cls = "kin" + (" white" if e.get("color") == "white" else "")
            frm = e.get("from", "right"); sx = 1400 if frm == "right" else -1400
            body.append(f'<div class="el {cls}" id="{id_}" style="top:{e.get("y",120)}px;font-size:{e.get("size",400)}px;transform:translateX(-50%) rotate({e.get("rot",-4)}deg)">{esc(e["text"])}</div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:1,x:{sx},xPercent:-50,rotation:{e.get("rot",-4)},scale:1.15}},{{x:{e.get("x_end",0)},xPercent:-50,scale:1,duration:.5,ease:"power4.out"}},{t0});')
            js.append(f'tl.to("#{id_}",{{x:{e.get("x_end",0)-(60 if frm=="right" else -60)},duration:{max(0.3,t1-t0-0.5)},ease:"none"}},{t0+0.5});')
            js.append(f'tl.to("#{id_}",{{x:{-sx},duration:.35,ease:"power4.in"}},{t1-0.35});')
        elif ty == "filmstrip":
            frames = e.get("frames") or sorted(os.path.join(pth(e["dir"]), f) for f in os.listdir(pth(e["dir"])) if f.endswith(".jpg"))
            imgs = "".join(f'<img src="file://{os.path.abspath(f)}">' for f in frames * 2)
            total = e.get("count_to", 1126); n_fr = len(frames)
            body.append(f'<div class="el strip" id="{id_}" style="height:{e.get("h",340)}px"><div class="trk" id="{id_}t"><div class="holes a"></div>{imgs}<div class="holes b"></div></div><div class="cnt">FRAME <b id="{id_}c">0000</b>/{total:04d}</div></div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0,y:-120}},{{opacity:1,y:0,duration:.4,ease:"power3.out"}},{t0});')
            js.append(f'tl.fromTo("#{id_}t",{{x:0}},{{x:{-320*n_fr},duration:{t1-t0},ease:"none"}},{t0});')
            js.append(f'tl.to({{}},{{duration:{t1-t0},onUpdate:function(){{document.getElementById("{id_}c").textContent=String(Math.round(this.progress()*{total})).padStart(4,"0")}}}},{t0});')
            js.append(f'tl.to("#{id_}",{{opacity:0,y:-120,duration:.3,ease:"power2.in"}},{t1-0.3});')
        elif ty == "exploded":
            lys = e["layers"]; n = len(lys)
            inner = "".join(f'<div class="ly{" vid" if k==0 else ""}" id="{id_}l{k}" style="z-index:{k+1}"><img src="file://{os.path.abspath(pth(l["path"]))}"></div>' for k, l in enumerate(lys))
            labs = "".join(f'<div class="lab" id="{id_}b{k}" style="top:{1660-k*100}px"><i></i>{esc(l["label"])}</div>' for k, l in enumerate(lys))
            body.append(f'<div class="el expl" id="{id_}"><div class="st" id="{id_}s">{inner}</div>{labs}<div class="ttl" id="{id_}t">{accent(e.get("title",""))}</div></div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0}},{{opacity:1,duration:.15}},{t0});')
            js.append(f'tl.fromTo("#{id_}s",{{rotation:0,skewY:0,scale:1,y:0,x:0}},{{rotation:-9,skewY:4,scale:.34,y:400,x:-60,duration:.9,ease:"power3.inOut",transformOrigin:"50% 50%"}},{t0+0.1});')
            for k in range(n):
                js.append(f'tl.fromTo("#{id_}l{k}",{{y:0,x:0}},{{y:{-k*1300},x:{k*330},duration:.9,ease:"power3.inOut"}},{t0+0.25});')
                js.append(f'tl.fromTo("#{id_}b{k}",{{opacity:0,x:-30}},{{opacity:1,x:0,duration:.3}},{t0+0.9+k*0.12});')
            js.append(f'tl.to("#{id_}s",{{rotation:-10,duration:{max(0.5,t1-t0-1.2)},ease:"none"}},{t0+1.0});')
            js.append(f'tl.fromTo("#{id_}t",{{opacity:0,y:-20}},{{opacity:1,y:0,duration:.35}},{t0+0.6});')
            js.append(f'tl.to("#{id_}",{{opacity:0,duration:.22}},{t1-0.22});')
        elif ty == "silhouette":
            body.append(f'<div class="el sil" id="{id_}"><div class="glow" id="{id_}g"></div><img src="file://{os.path.abspath(e["cutout_png"])}" id="{id_}i"><div class="w" id="{id_}w" style="top:{e.get("y",1250)}px">{esc(e.get("text",""))}</div><div class="grain"></div></div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0}},{{opacity:1,duration:.2}},{t0});')
            js.append(f'tl.fromTo("#{id_}g",{{scale:.4,opacity:0}},{{scale:1,opacity:1,duration:.7,ease:"power3.out"}},{t0});')
            js.append(f'tl.to("#{id_}g",{{scale:1.12,duration:.9,repeat:-1,yoyo:true,ease:"sine.inOut"}},{t0+0.7});')
            js.append(f'tl.fromTo("#{id_}i",{{scale:1.08,y:30}},{{scale:1,y:0,duration:.6,ease:"power3.out",transformOrigin:"center"}},{t0});')
            js.append(f'tl.fromTo("#{id_}w",{{opacity:0,y:40,scale:.9}},{{opacity:1,y:0,scale:1,duration:.4,ease:"back.out(1.6)"}},{t0+0.35});')
            js.append(f'tl.to("#{id_}",{{opacity:0,duration:.2}},{t1-0.2});')
        elif ty == "phone_fan":
            phs = e["phones"]; n = len(phs); mid = (n - 1) / 2
            inner = ""
            for k, p in enumerate(phs):
                if p.get("path"): inner += f'<div class="ph" id="{id_}p{k}"><img src="file://{os.path.abspath(pth(p["path"]))}"><div class="yours">{esc(p.get("label","yours"))}</div></div>'
                else: inner += f'<div class="ph" id="{id_}p{k}"><div class="n">{esc(p.get("n",k+1))}</div></div>'
            body.append(f'<div class="el fan" id="{id_}" style="top:{e.get("y",0)}px">{inner}</div>')
            js.append(f'tl.fromTo("#{id_}",{{opacity:0}},{{opacity:1,duration:.1}},{t0});')
            order = sorted(range(n), key=lambda k: abs(k - mid))
            for j, k in enumerate(order):
                r = (k - mid) * e.get("spread", 16)
                js.append(f'tl.fromTo("#{id_}p{k}",{{rotation:0,y:200,opacity:0,scale:.8}},{{rotation:{r},y:0,opacity:1,scale:1,duration:.55,ease:"back.out(1.5)"}},{t0+j*0.07});')
            js.append(f'tl.to("#{id_} .ph",{{y:-16,duration:1.4,repeat:-1,yoyo:true,ease:"sine.inOut",stagger:.15}},{t0+0.6});')
            js.append(f'tl.to("#{id_}",{{opacity:0,y:60,duration:.25,ease:"power2.in"}},{t1-0.25});')
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style><script src="file://{GSAP}"></script></head>
<body>{''.join(body)}<script>
gsap.ticker.lagSmoothing(0);
const OFF=2;const raw=gsap.timeline({{paused:true}});
const tl={{fromTo:(a,b,c,p)=>raw.fromTo(a,b,c,(p||0)+OFF),to:(a,b,p)=>raw.to(a,b,(p||0)+OFF),call:(f,pa,p)=>raw.call(f,pa,(p||0)+OFF)}};
{chr(10).join(js)}
tl.to({{}},{{duration:.01}},{END+1});
window.seek=t=>{{raw.pause().time(t+OFF,false)}};
</script></body></html>"""
    f = os.path.join(A.out, f"{layer}.html"); open(f, "w").write(page); return f

# active frame set per layer
def active(layer):
    s = set()
    for i, e in enumerate(EL):
        beh = bool(e.get("behind")) or e["type"] in ("behind_text", "word_stack")
        if (layer == "behind") != beh: continue
        a, b = max(0, e["t0"] - 0.2), min(END + 0.5, e["t1"] + 0.3)
        s.update(range(int(a * FPS), int(b * FPS) + 1))
    return sorted(s)

from playwright.sync_api import sync_playwright
stills = [float(x) for x in A.stills.split(",") if x]
with sync_playwright() as p:
    br = p.chromium.launch(args=["--allow-file-access-from-files"])
    for layer in (["front", "behind"] if not A.only else [A.only]):
        f = build(layer); frames = active(layer)
        if stills: frames = [int(round(t * FPS)) for t in stills]
        d = os.path.join(A.out, layer); os.makedirs(d, exist_ok=True)
        pg = br.new_page(viewport={"width": 1080, "height": 1920}); pg.goto("file://" + os.path.abspath(f)); pg.wait_for_timeout(800)
        pg.evaluate("document.fonts.ready")
        for k, n in enumerate(frames):
            pg.evaluate(f"seek({n/FPS:.4f})")
            pg.screenshot(path=os.path.join(d, f"f_{n:06d}.png"), omit_background=True)
            if k % 200 == 0: print(layer, k, "/", len(frames), flush=True)
        pg.close(); print(layer, "done", len(frames), "frames")
    br.close()
