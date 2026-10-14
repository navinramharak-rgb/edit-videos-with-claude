#!/usr/bin/env python3
"""Propose a cut list from words.json: drop fillers, tighten dead air, flag likely retakes.
Usage: python propose_cuts.py words.json -o OUTDIR [--max-gap 0.30] [--min-keep-gap 0.10]
Writes OUTDIR/edl.json  {"keep": [[s,e],...], "cut": [...], "flags": [...]}
       OUTDIR/cutlist.md  (human readable: what stays, what goes, what's unsure)
This is a first pass. Claude (or you) reviews cutlist.md, edits edl.json, then runs cut.py.
"""
import argparse, json, re, os

FILLERS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "ah", "ahh", "hmm", "mm", "mhm"}
SOFT = {"like", "so", "basically", "literally", "actually", "right", "okay", "ok"}  # flagged, not cut

def norm(w): return re.sub(r"[^a-z0-9']", "", w.lower())

def phrases(words, pause=0.45):
    """Split into phrases at pauses or sentence punctuation."""
    out, cur = [], []
    for i, w in enumerate(words):
        if cur and (w["s"] - words[i-1]["e"] >= pause):
            out.append(cur); cur = []
        cur.append(i)
        if re.search(r"[.?!]$", w["w"]): out.append(cur); cur = []
    if cur: out.append(cur)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("words"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--max-gap", type=float, default=0.30, help="gaps longer than this get cut")
    ap.add_argument("--pad-in", type=float, default=0.05); ap.add_argument("--pad-out", type=float, default=0.08)
    a = ap.parse_args()
    words = json.load(open(a.words)); os.makedirs(a.out, exist_ok=True)
    drop, flags = set(), []
    for i, w in enumerate(words):
        n = norm(w["w"])
        if n in FILLERS: drop.add(i)
        elif n in SOFT: flags.append({"t": w["s"], "type": "soft-filler", "text": w["w"]})
        if w.get("p", 1) < 0.4: flags.append({"t": w["s"], "type": "low-confidence", "text": w["w"]})
    # retakes: a phrase whose opening 3 words reappear in one of the next 3 phrases -> keep the later one
    ph = phrases(words)
    for k, p in enumerate(ph):
        head = [norm(words[i]["w"]) for i in p if norm(words[i]["w"]) not in FILLERS][:3]
        if len(head) < 2: continue
        for q in ph[k+1:k+4]:
            qh = [norm(words[i]["w"]) for i in q if norm(words[i]["w"]) not in FILLERS][:3]
            if qh[:len(head)] == head:
                drop.update(p)
                flags.append({"t": words[p[0]]["s"], "type": "retake-cut",
                              "text": " ".join(words[i]["w"] for i in p)})
                break
    # also: a phrase with no sentence ending followed by a pause is a false start candidate
    for p in ph:
        txt = " ".join(words[i]["w"] for i in p)
        if len(p) <= 4 and not re.search(r"[.?!]$", words[p[-1]]["w"]) and not set(p) <= drop:
            flags.append({"t": words[p[0]]["s"], "type": "possible-false-start", "text": txt})
    # build keep ranges
    keep, cur = [], None
    for i, w in enumerate(words):
        if i in drop:
            if cur: keep.append(cur); cur = None
            continue
        s, e = max(0, w["s"] - a.pad_in), w["e"] + a.pad_out
        if cur and s - cur[1] <= a.max_gap - a.pad_in - a.pad_out:
            cur[1] = e
        else:
            if cur: keep.append(cur)
            cur = [s, e]
    if cur: keep.append(cur)
    # resolve overlaps from padding
    merged = []
    for s, e in keep:
        if merged and s <= merged[-1][1]: merged[-1][1] = max(merged[-1][1], e)
        else: merged.append([round(s, 3), round(e, 3)])
    total = sum(e - s for s, e in merged); src = words[-1]["e"] if words else 0
    json.dump({"source_words": os.path.abspath(a.words), "keep": merged, "flags": flags},
              open(os.path.join(a.out, "edl.json"), "w"), indent=1)
    # human-readable cut list
    L = [f"# Cut list\n\nSource speech: {src:.1f}s  ->  kept: {total:.1f}s  ({len(merged)} segments)\n",
         "## Kept (in order)\n"]
    for n, (s, e) in enumerate(merged, 1):
        txt = " ".join(w["w"] for i, w in enumerate(words) if i not in drop and w["s"] >= s - 0.01 and w["e"] <= e + 0.01)
        L.append(f"{n}. `{s:6.2f}-{e:6.2f}`  {txt}")
    L.append("\n## Cut\n")
    for i in sorted(drop):
        L.append(f"- `{words[i]['s']:6.2f}`  {words[i]['w']}")
    L.append("\n## Unsure (please check)\n")
    for f in flags:
        if f["type"] != "retake-cut": L.append(f"- `{f['t']:6.2f}` {f['type']}: {f['text']}")
    open(os.path.join(a.out, "cutlist.md"), "w").write("\n".join(L) + "\n")
    print(f"kept {total:.1f}s of {src:.1f}s in {len(merged)} segments, {len(drop)} words cut, {len(flags)} flags")

if __name__ == "__main__":
    main()
