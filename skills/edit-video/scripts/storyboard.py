#!/usr/bin/env python3
"""Storyboard page from plan stills: one real frame per beat with the spoken line + what the graphic is.
Usage: python storyboard.py plan.json --stills STILLS_DIR -o storyboard.html
Run render_plan.py first with --stills t1,t2,... --stills-dir STILLS_DIR (one time per beat)."""
import argparse, json, os, glob, html, re
ap=argparse.ArgumentParser(); ap.add_argument("plan"); ap.add_argument("--stills",required=True); ap.add_argument("-o","--out",default="storyboard.html"); a=ap.parse_args()
P=json.load(open(a.plan)); base=os.path.dirname(os.path.abspath(a.plan))
W=json.load(open(os.path.join(base,P["words"])))
R=os.path.join(base,"resolved.json"); EL=json.load(open(R))["elements"] if os.path.exists(R) else []
def line_at(t): return " ".join(w["w"] for w in W if t-1.2<=w["s"]<=t+1.2)
def els_at(t): return ", ".join(e["type"]+(" "+str(e.get("text") or e.get("big") or e.get("title") or "")[:30] if (e.get("text") or e.get("big") or e.get("title")) else "") for e in EL if isinstance(e.get("t0"),(int,float)) and e["t0"]-0.05<=t<e.get("t1",9e9))
cards=[]
for f in sorted(glob.glob(os.path.join(a.stills,"s_*.jpg"))):
    t=float(re.search(r"s_([\d.]+)\.jpg",f).group(1))
    cards.append(f'<div class="c"><img src="{os.path.relpath(f,os.path.dirname(os.path.abspath(a.out)))}"><div class="t">{t:05.2f}s</div><div class="l">{html.escape(line_at(t))}</div><div class="g">{html.escape(els_at(t)) or "clean"}</div></div>')
open(a.out,"w").write(f'''<!doctype html><meta charset="utf-8"><title>Storyboard</title><style>body{{background:#111;color:#eee;font:15px/1.4 -apple-system,Inter,sans-serif;margin:24px}}h1{{font-weight:600}}.g{{color:#FF6B2E;font-family:ui-monospace,monospace;font-size:12px}}.w{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:18px}}.c img{{width:100%;border-radius:12px}}.t{{color:#888;font-size:12px;margin-top:6px}}.l{{margin:4px 0}}</style>
<h1>Storyboard: {html.escape(os.path.basename(a.plan))}</h1><p>Each card is a real frame. Reply "go" to render, or give notes per timestamp.</p><div class="w">{"".join(cards)}</div>''')
print("storyboard ->",a.out,len(cards),"beats")
