#!/usr/bin/env bash
# Edit Videos with Claude: one-time Mac setup. Safe to re-run; it skips what is already installed.
#   bash setup/setup-mac.sh
# Installs: Homebrew, ffmpeg, uv + Python 3.12 env (faster-whisper, onnxruntime, playwright Chromium),
# Claude Code, the whisper + person-matte models, and registers the skill so  /edit-video  works in Claude Code.
set -uo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
HOMEDIR="$HOME/.claude-video"; VENV="$HOMEDIR/venv"; MODELS="$HOMEDIR/models"; mkdir -p "$HOMEDIR" "$MODELS"
LOG="$HOMEDIR/setup-log.txt"; : > "$LOG"
ok(){ echo "  [ok] $*" | tee -a "$LOG"; }
bad(){ echo "  [!!] $*" | tee -a "$LOG"; }
step(){ echo; echo "== $*" | tee -a "$LOG"; }
addpath(){ grep -qF "$1" "$HOME/.zprofile" 2>/dev/null || echo "export PATH=\"$1:\$PATH\"" >> "$HOME/.zprofile"; export PATH="$1:$PATH"; }
export HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1 HOMEBREW_NO_ENV_HINTS=1

step "0. Mac check"
[ "$(uname)" = "Darwin" ] || { bad "This installer is for macOS. On Linux, install ffmpeg + uv and run the venv steps by hand."; exit 1; }
MACOS=$(sw_vers -productVersion); MAJOR=${MACOS%%.*}
echo "  macOS $MACOS, $(sysctl -n machdep.cpu.brand_string), $(( $(sysctl -n hw.memsize)/1073741824 ))GB RAM" | tee -a "$LOG"
[ "$MAJOR" -ge 15 ] || { bad "macOS $MACOS is too old: Homebrew compiles everything from source for hours. Update macOS, then re-run."; exit 1; }
ok "macOS $MACOS"

step "1. Xcode command line tools + Homebrew"
xcode-select -p >/dev/null 2>&1 || { echo "  Installing Command Line Tools: click Install in the popup, wait for it to finish, then re-run this script."; xcode-select --install; exit 0; }
ok "command line tools"
if ! command -v brew >/dev/null; then
  [ -x /opt/homebrew/bin/brew ] || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv)"
  grep -q "brew shellenv" "$HOME/.zprofile" 2>/dev/null || echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
fi
command -v brew >/dev/null && ok "$(brew --version | head -1)" || { bad "Homebrew failed"; exit 1; }

step "2. ffmpeg (full build)"
brew list ffmpeg-full >/dev/null 2>&1 || { echo "  installing ffmpeg-full (a few minutes)..."; brew install ffmpeg-full >>"$LOG" 2>&1; }
addpath "$(brew --prefix ffmpeg-full)/bin"
ffmpeg -version >/dev/null 2>&1 && ok "$(ffmpeg -version | head -1 | cut -c1-30)" || bad "ffmpeg missing"
ffmpeg -v error -f lavfi -i "anullsrc=r=48000:cl=mono:d=0.2" -af loudnorm -f null - >/dev/null 2>&1 && ok "loudnorm" || bad "ffmpeg build without loudnorm"

step "3. uv + Python 3.12"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh >>"$LOG" 2>&1
addpath "$HOME/.local/bin"
uv python install 3.12 >>"$LOG" 2>&1
command -v uv >/dev/null && ok "$(uv --version)" || bad "uv missing"

step "4. Claude Code"
if ! command -v claude >/dev/null; then curl -fsSL https://claude.ai/install.sh | bash >>"$LOG" 2>&1; addpath "$HOME/.local/bin"; fi
command -v claude >/dev/null && ok "claude $(claude --version 2>/dev/null | head -1)" || bad "Claude Code missing: run  curl -fsSL https://claude.ai/install.sh | bash"

step "5. Python env (whisper, person matte, Chromium renderer)"
[ -d "$VENV" ] || uv venv --python 3.12 "$VENV" >>"$LOG" 2>&1
uv pip install --python "$VENV/bin/python" faster-whisper onnxruntime numpy pillow playwright >>"$LOG" 2>&1
"$VENV/bin/python" -c "import faster_whisper, onnxruntime, PIL, playwright" 2>>"$LOG" && ok "faster-whisper, onnxruntime, pillow, playwright" || bad "python deps (see $LOG)"
"$VENV/bin/python" -m playwright install chromium >>"$LOG" 2>&1 && ok "headless Chromium (graphics renderer)" || bad "playwright chromium (see $LOG)"

step "6. Models (one time)"
"$VENV/bin/python" -c "
from faster_whisper import WhisperModel
WhisperModel('large-v3-turbo', device='cpu', compute_type='int8')" >>"$LOG" 2>&1 && ok "whisper large-v3-turbo (1.6GB, cached)" || bad "whisper model download failed"
[ -f "$MODELS/rvm.onnx" ] || curl -L -o "$MODELS/rvm.onnx" https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx >>"$LOG" 2>&1
[ -s "$MODELS/rvm.onnx" ] && ok "person matte model (RobustVideoMatting)" || bad "rvm.onnx download failed"

step "7. Register the skill with Claude Code"
mkdir -p "$HOME/.claude/skills"
if [ ! -e "$HOME/.claude/skills/edit-video" ]; then ln -s "$SKILL" "$HOME/.claude/skills/edit-video"; fi
[ -f "$HOME/.claude/skills/edit-video/SKILL.md" ] && ok "~/.claude/skills/edit-video -> $SKILL" || bad "skill link failed"

step "8. Smoke test (voice -> transcript -> captions + graphics -> mp4)"
T="$HOMEDIR/smoke"; rm -rf "$T"; mkdir -p "$T"
say -o "$T/voice.aiff" "Most people edit videos the hard way. Here is how Claude does it in sixty seconds." 2>>"$LOG"
ffmpeg -y -v error -f lavfi -i "color=c=0x2a1a12:s=1080x1920:r=30" -i "$T/voice.aiff" -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac "$T/base.mp4"
"$VENV/bin/python" "$SKILL/scripts/transcribe.py" "$T/base.mp4" -o "$T" >>"$LOG" 2>&1 && echo "  heard: $(cat "$T/transcript.txt")"
cat > "$T/plan.json" <<EOF
{"video":"base.mp4","words":"words.json","captions":{"y":1290,"size":92,"style":"mixed","emphasis":["claude","hard"],"phrases":["edit videos the hard way","how Claude does it"]},
 "elements":[{"type":"hook_box","text":"the *hard* way","t0":0,"t1":"@claude<","y":150},{"type":"stamp","text":"CLAUDE","t0":"@claude","t1":999}],
 "camera":[{"t":"@claude","z":1.12,"dur":0.1,"ease":"settle"}]}
EOF
grep -qi "claude" "$T/transcript.txt" || cat > "$T/plan.json" <<EOF
{"video":"base.mp4","words":"words.json","captions":{"y":1290,"size":92,"style":"mixed","max_words":4},"elements":[{"type":"hook_box","text":"the *hard* way","t0":0,"t1":2.0,"y":150},{"type":"stamp","text":"CLAUDE","t0":2.2,"t1":999}],"camera":[{"t":2.2,"z":1.12,"dur":0.1,"ease":"settle"}]}
EOF
( cd "$T" && "$VENV/bin/python" "$SKILL/scripts/overlay.py" plan.json -o ov >>"$LOG" 2>&1 && "$VENV/bin/python" "$SKILL/scripts/render_plan.py" plan.json -o smoke_video.mp4 --overlay ov >>"$LOG" 2>&1 \
  && ffmpeg -y -v error -i smoke_video.mp4 -i base.mp4 -map 0:v -map 1:a -c:v copy -c:a aac -shortest smoke_test.mp4 ) && ok "$T/smoke_test.mp4 (open it)" || bad "smoke render failed (see $LOG)"

step "9. Your editing folder"
bash "$SKILL/setup/make-launcher.sh" | tee -a "$LOG"

step "SUMMARY (also in $LOG)"
grep -E "^\s+\[(ok|!!)\]" "$LOG"
echo; echo "Done. A folder called \"Claude Video Edits\" just opened. Drop a video into its raw folder and double-click \"Edit Video\"."
open "$HOME/Claude Video Edits" 2>/dev/null || true
