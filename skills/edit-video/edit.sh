#!/usr/bin/env bash
# Edit Videos with Claude: pipeline runner. Claude calls these; you can too.
#   bash edit.sh prep     raw/VIDEO.mov            -> work/NAME/{words.json,transcript.txt,edl.json,cutlist.md,preview_cut.mp4}
#   bash edit.sh reframe  raw/VIDEO.mov            -> work/NAME/vertical_src.mp4 (landscape -> head-tracked 9:16; skip for vertical sources)
#   bash edit.sh cut      raw/VIDEO.mov            -> work/NAME/vertical_cut.mp4 + vertical_cut_words.json (from edl.json; uses vertical_src.mp4 if present)
#   bash edit.sh matte    work/NAME                -> work/NAME/matte_540.u8 (person matte for behind-text, cutouts, background blur)
#   bash edit.sh board    work/NAME/plan.json t1,t2,...   -> work/NAME/storyboard.html (one real frame per beat)
#   bash edit.sh render   work/NAME/plan.json      -> work/NAME/video_only.mp4 + sfx.wav
#   bash edit.sh mix      work/NAME renders/NAME.mp4   -> final file (-14 LUFS, H.265)
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)/scripts"; PY="$HOME/.claude-video/venv/bin/python"
[ -x "$PY" ] || { echo "python env missing: run  bash $(dirname "$0")/setup/doctor.sh"; exit 1; }
command -v brew >/dev/null && export PATH="$(brew --prefix ffmpeg-full 2>/dev/null)/bin:$PATH"
CMD="${1:-}"; ARG="${2:-}"; t0=$(date +%s)
name(){ basename "${1%.*}"; }
case "$CMD" in
  prep)   W="work/$(name "$ARG")"; mkdir -p "$W"
          echo "1/3 transcribing (local whisper)"; nice -n 10 "$PY" "$S/transcribe.py" "$ARG" -o "$W"
          echo "2/3 proposing cuts"; "$PY" "$S/propose_cuts.py" "$W/words.json" -o "$W"
          echo "3/3 low-res preview"; nice -n 10 "$PY" "$S/cut.py" "$ARG" "$W/edl.json" "$W/words.json" -o "$W/preview_cut.mp4" --preview;;
  reframe) W="work/$(name "$ARG")"; mkdir -p "$W"
          nice -n 10 "$PY" "$S/track.py" "$ARG" -o "$W/track.json"
          nice -n 10 "$PY" "$S/reframe.py" "$ARG" "$W/track.json" none -o "$W/vertical_src.mp4";;
  cut)    W="work/$(name "$ARG")"; SRC="$ARG"; [ -f "$W/vertical_src.mp4" ] && SRC="$W/vertical_src.mp4"
          nice -n 10 "$PY" "$S/cut.py" "$SRC" "$W/edl.json" "$W/words.json" -o "$W/vertical_cut.mp4";;
  matte)  nice -n 10 "$PY" "$S/matte.py" "$ARG/vertical_cut.mp4" -o "$ARG/matte_540.u8";;
  board)  D="$(dirname "$ARG")"; "$PY" "$S/render_plan.py" "$ARG" -o /dev/null --stills "${3:?times}" --stills-dir "$D/stills"
          "$PY" "$S/overlay.py" "$ARG" -o "$D/ov" --stills "$3" >/dev/null; "$PY" "$S/render_plan.py" "$ARG" -o /dev/null --overlay "$D/ov" --stills "$3" --stills-dir "$D/stills"
          "$PY" "$S/storyboard.py" "$ARG" --stills "$D/stills" -o "$D/storyboard.html"; open "$D/storyboard.html" 2>/dev/null || true;;
  render) D="$(dirname "$ARG")"; rm -rf "$D/ov"
          echo "1/3 graphics (Chromium)"; nice -n 10 "$PY" "$S/overlay.py" "$ARG" -o "$D/ov"
          echo "2/3 picture"; nice -n 10 "$PY" "$S/render_plan.py" "$ARG" -o "$D/video_only.mp4" --overlay "$D/ov"
          echo "3/3 sound"; DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$D/video_only.mp4")
          PACK=""; [ -d assets/sfx ] && PACK="--pack assets/sfx"; "$PY" "$S/sfx_plan.py" "$D/resolved.json" -o "$D/sfx.wav" --dur "$DUR" $PACK;;
  mix)    OUT="${3:?out}"; mkdir -p "$(dirname "$OUT")"; VOICE="$ARG/voice.wav"
          [ -f "$VOICE" ] || ffmpeg -v error -y -i "$ARG/vertical_cut.mp4" -vn -af "highpass=f=80,afftdn=nf=-25,acompressor=threshold=-18dB:ratio=2.5:attack=8:release=120" -ar 48000 "$VOICE"
          bash "$S/mix.sh" "$VOICE" "$ARG/sfx.wav" "$ARG/video_only.mp4" "$OUT";;
  *) sed -n 2,10p "$0"; exit 1;;
esac
echo "done in $(( $(date +%s)-t0 ))s"
