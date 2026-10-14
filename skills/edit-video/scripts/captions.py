#!/usr/bin/env python3
"""Build word-highlight captions (.ass) from words.json.
Usage: python captions.py words.json -o captions.ass [--words-per-card 3] [--font Inter]
       [--size 78] [--accent FF6B2E] [--y 1300] [--lower]
"""
import argparse, json

def bgr(hexrgb):  # ASS colours are &HBBGGRR&
    h = hexrgb.lstrip("#"); return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&".upper()

def ts(t): return f"{int(t//3600)}:{int(t%3600//60):02d}:{t%60:05.2f}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("words"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--words-per-card", type=int, default=3)
    ap.add_argument("--font", default="Inter"); ap.add_argument("--size", type=int, default=78)
    ap.add_argument("--accent", default="FF6B2E"); ap.add_argument("--y", type=int, default=1300)
    ap.add_argument("--lower", action="store_true", default=True)
    ap.add_argument("--w", type=int, default=1080); ap.add_argument("--h", type=int, default=1920)
    a = ap.parse_args()
    words = json.load(open(a.words))
    marginv = a.h - a.y
    hdr = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {a.w}\nPlayResY: {a.h}\nWrapStyle: 2\n"
           "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
           "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, "
           "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
           f"Style: Cap,{a.font},{a.size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,0,3,2,80,80,{marginv},1\n"
           "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    acc, white = bgr(a.accent), "&HFFFFFF&"
    fix = (lambda s: s.lower()) if a.lower else (lambda s: s)
    out = []
    for i in range(0, len(words), a.words_per_card):
        card = words[i:i + a.words_per_card]
        for j, w in enumerate(card):
            parts = [("{\\c" + acc + "}" + fix(x["w"]) + "{\\c" + white + "}") if k == j else fix(x["w"])
                     for k, x in enumerate(card)]
            end = card[j + 1]["s"] if j + 1 < len(card) else w["e"]
            out.append(f"Dialogue: 0,{ts(w['s'])},{ts(max(end, w['s'] + 0.05))},Cap,,0,0,0,,{' '.join(parts)}")
    open(a.out, "w").write(hdr + "\n".join(out) + "\n")
    print(f"{len(out)} caption events -> {a.out}")

if __name__ == "__main__":
    main()
