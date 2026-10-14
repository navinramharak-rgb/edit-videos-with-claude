#!/usr/bin/env bash
# Measure reference videos so Claude can learn a style from them.
# Usage: bash analyze_refs.sh research/references  -> research/references/_analysis/
# Per video: specs, cut count + cuts/min (scene changes), loudness, and a 6x4 contact sheet.
set -uo pipefail
DIR="$1"; OUT="$DIR/_analysis"; mkdir -p "$OUT"
SUM="$OUT/summary.tsv"; echo -e "file\tdur_s\tres\tfps\tcuts\tcuts_per_min\tlufs" > "$SUM"
i=0
for f in "$DIR"/*.mp4 "$DIR"/*.mov "$DIR"/*.MOV "$DIR"/*.MP4; do
  [ -f "$f" ] || continue; i=$((i+1)); tag=$(printf "ref%02d" $i)
  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
  res=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0:s=x "$f")
  rate=$(awk -v d="$dur" 'BEGIN{printf "%.4f", 24/d}')
  ffmpeg -v error -y -i "$f" -filter_complex \
    "[0:v]scale=240:-2,split[a][b];[a]select='gt(scene,0.32)',metadata=print:file=$OUT/${tag}_scenes.txt,nullsink;[b]fps=$rate,tile=6x4:padding=4:color=black[t]" \
    -map "[t]" -frames:v 1 "$OUT/${tag}_sheet.jpg"
  cuts=$(grep -c pts_time "$OUT/${tag}_scenes.txt" 2>/dev/null || echo 0)
  lufs=$(ffmpeg -v info -i "$f" -vn -af ebur128 -f null - 2>&1 | awk '/Integrated loudness/{getline; print $2}' | tail -1)
  cpm=$(awk -v c="$cuts" -v d="$dur" 'BEGIN{printf "%.1f", c/(d/60)}')
  echo -e "$tag $(basename "$f")\t${dur%.*}\t${res%x*}\t${res##*x}\t$cuts\t$cpm\t$lufs" >> "$SUM"
  echo "done $tag"
done
column -t -s $'\t' "$SUM"
