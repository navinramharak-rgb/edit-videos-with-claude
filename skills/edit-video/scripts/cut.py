#!/usr/bin/env python3
"""Render a cut from edl.json and remap word timings to the new timeline.
Usage: python cut.py SOURCE edl.json words.json -o OUT.mp4 [--preview] [--w 1080 --h 1920]
--preview: 540x960 fast encode for review. Without it: full quality from the original.
Writes OUT.mp4 and OUT_words.json (word timings on the cut timeline, for captions/graphics).
Each segment gets a 15ms audio fade in/out so cuts never pop.
"""
import argparse, json, subprocess, os

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source"); ap.add_argument("edl"); ap.add_argument("words")
    ap.add_argument("-o", "--out", required=True); ap.add_argument("--preview", action="store_true")
    ap.add_argument("--w", type=int, default=1080); ap.add_argument("--h", type=int, default=1920)
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    keep = json.load(open(a.edl))["keep"]; words = json.load(open(a.words))
    w, h = (540, 960) if a.preview else (a.w, a.h)
    f, parts = [], []
    for i, (s, e) in enumerate(keep):
        d = e - s; fd = min(0.015, d / 4)
        f.append(f"[0:v:0]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]")
        f.append(f"[0:a:0]atrim=start={s}:end={e},asetpts=PTS-STARTPTS,"
                 f"afade=t=in:st=0:d={fd},afade=t=out:st={d-fd:.4f}:d={fd}[a{i}]")
        parts.append(f"[v{i}][a{i}]")
    f.append("".join(parts) + f"concat=n={len(keep)}:v=1:a=1[vc][ac]")
    f.append(f"[vc]scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},fps={a.fps},format=yuv420p[vo]")
    enc = (["-c:v", "libx264", "-preset", "veryfast", "-crf", "28"] if a.preview
           else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "14"])
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", a.source, "-filter_complex", ";".join(f),
           "-map", "[vo]", "-map", "[ac]", *enc, "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    # remap words onto the new timeline
    out, offset = [], 0.0
    for s, e in keep:
        for wd in words:
            if wd["s"] >= s - 0.02 and wd["e"] <= e + 0.02:
                out.append({**wd, "s": round(offset + max(0, wd["s"] - s), 3),
                            "e": round(offset + min(e, wd["e"]) - s, 3)})
        offset += e - s
    json.dump(out, open(os.path.splitext(a.out)[0] + "_words.json", "w"), indent=1)
    print(f"rendered {a.out} ({offset:.2f}s, {len(keep)} segments, {len(out)} words remapped)")

if __name__ == "__main__":
    main()
