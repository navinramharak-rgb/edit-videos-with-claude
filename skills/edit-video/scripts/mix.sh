#!/usr/bin/env bash
# Final audio + mux + delivery encode.
#   bash scripts/mix.sh VOICE.wav SFX.wav VIDEO_ONLY.mp4 OUT.mp4
# voice + sfx -> two-pass loudnorm (-14 LUFS, TP -1.5) -> mux -> H.265 delivery (~25MB/min)
set -euo pipefail
V="$1"; S="$2"; VID="$3"; OUT="$4"; T="$(mktemp -d)"
ffmpeg -v error -y -i "$V" -i "$S" -filter_complex "[0:a][1:a]amix=inputs=2:duration=first:normalize=0" "$T/raw.wav"
ffmpeg -y -i "$T/raw.wav" -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | grep -A12 '^{' > "$T/ln.json"
ARGS=$(python3 -c "import json;j=json.load(open('$T/ln.json'));print(f\"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true\")")
ffmpeg -v error -y -i "$T/raw.wav" -af "$ARGS" -ar 48000 "$T/mix.wav"
ffmpeg -v error -y -i "$VID" -i "$T/mix.wav" -map 0:v -map 1:a -c:v libx265 -preset medium -crf 23 -tag:v hvc1 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT"
cp "$T/mix.wav" "${OUT%.*}_mix.wav"; rm -rf "$T"; echo "done -> $OUT"
