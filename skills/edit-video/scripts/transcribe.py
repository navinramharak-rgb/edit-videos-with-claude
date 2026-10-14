#!/usr/bin/env python3
"""Word-level transcription for editing.
Usage: python transcribe.py INPUT_VIDEO -o OUTDIR [--model large-v3-turbo] [--lang en]
Writes OUTDIR/words.json  [{"w","s","e","p"}]  (word, start, end, probability)
       OUTDIR/transcript.txt  (plain text with [pause Xs] markers, for Claude to read)
Audio is decoded with ffmpeg directly (no PyAV), so it works with any ffmpeg build.
"""
import argparse, json, subprocess, sys, os
import numpy as np

def load_audio(path, sr=16000):
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-vn", "-ac", "1",
           "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--model", default="large-v3-turbo"); ap.add_argument("--lang", default="en")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    from faster_whisper import WhisperModel
    audio = load_audio(a.input)
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
    # The prompt nudges Whisper to keep disfluencies (um, uh) instead of cleaning them up,
    # which we need so the cutter can find and remove them.
    segs, info = model.transcribe(
        audio, language=a.lang, word_timestamps=True, vad_filter=False,
        condition_on_previous_text=False,
        initial_prompt="Umm, so, uh, I was like, you know, I mean, uh, okay so basically.")
    words = []
    for s in segs:
        for w in (s.words or []):
            words.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3),
                          "p": round(w.probability, 3)})
    json.dump(words, open(os.path.join(a.out, "words.json"), "w"), indent=1)
    lines, prev = [], 0.0
    for w in words:
        gap = w["s"] - prev
        if gap >= 0.5: lines.append(f"\n[pause {gap:.1f}s @ {prev:.2f}]\n")
        lines.append(w["w"]); prev = w["e"]
    open(os.path.join(a.out, "transcript.txt"), "w").write(" ".join(lines).replace(" \n", "\n"))
    dur = len(audio) / 16000
    print(f"transcribed {len(words)} words, {dur:.1f}s audio -> {a.out}")

if __name__ == "__main__":
    main()
