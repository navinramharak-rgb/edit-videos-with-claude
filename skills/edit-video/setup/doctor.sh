#!/usr/bin/env bash
# edit-video doctor: read-only check of every dependency. Prints the exact command to fix anything missing.
#   bash setup/doctor.sh
set -uo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
ok(){ printf "  \033[32m[ok]\033[0m %s\n" "$*"; }
bad(){ printf "  \033[31m[!!]\033[0m %s\n" "$*"; MISSING=1; }
fix(){ printf "       fix: %s\n" "$*"; }
MISSING=0; VENV="$HOME/.claude-video/venv"; MODELS="$HOME/.claude-video/models"
command -v brew >/dev/null 2>&1 && export PATH="$(brew --prefix ffmpeg-full 2>/dev/null)/bin:$PATH"
echo "== edit-video doctor"
if [ "$(uname)" = "Darwin" ]; then echo "  macOS $(sw_vers -productVersion) · $(sysctl -n machdep.cpu.brand_string)"; else echo "  $(uname -s) (built for macOS; Linux works with manual installs)"; fi
command -v brew >/dev/null && ok "Homebrew" || { bad "Homebrew missing"; fix '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'; }
if command -v ffmpeg >/dev/null; then ffmpeg -v error -f lavfi -i "anullsrc=r=48000:cl=mono:d=0.2" -af loudnorm -f null - >/dev/null 2>&1 && ok "ffmpeg $(ffmpeg -version | head -1 | awk '{print $3}')" || { bad "ffmpeg without loudnorm"; fix "brew install ffmpeg-full && echo 'export PATH=\"\$(brew --prefix ffmpeg-full)/bin:\$PATH\"' >> ~/.zprofile"; }
else bad "ffmpeg missing"; fix "brew install ffmpeg-full && echo 'export PATH=\"\$(brew --prefix ffmpeg-full)/bin:\$PATH\"' >> ~/.zprofile"; fi
command -v uv >/dev/null && ok "uv" || { bad "uv missing"; fix "curl -LsSf https://astral.sh/uv/install.sh | sh"; }
command -v claude >/dev/null && ok "Claude Code $(claude --version 2>/dev/null | head -1)" || { bad "Claude Code missing"; fix "curl -fsSL https://claude.ai/install.sh | bash"; }
if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "import faster_whisper, onnxruntime, PIL, playwright" 2>/dev/null; then ok "python env (whisper, onnxruntime, pillow, playwright)"
else bad "python env incomplete"; fix "uv venv --python 3.12 $VENV && uv pip install --python $VENV/bin/python faster-whisper onnxruntime numpy pillow playwright && $VENV/bin/python -m playwright install chromium"; fi
[ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "from playwright.sync_api import sync_playwright
with sync_playwright() as p: p.chromium.launch().close()" 2>/dev/null && ok "headless Chromium" || { bad "headless Chromium missing (graphics renderer)"; fix "$VENV/bin/python -m playwright install chromium"; }
ls "$HOME/.cache/huggingface/hub" 2>/dev/null | grep -qi "large-v3-turbo" && ok "whisper large-v3-turbo cached" || { bad "whisper model not downloaded (1.6GB, one time)"; fix "$VENV/bin/python -c \"from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo',device='cpu',compute_type='int8')\""; }
[ -s "$MODELS/rvm.onnx" ] && ok "person matte model" || { bad "person matte model missing (15MB)"; fix "mkdir -p $MODELS && curl -L -o $MODELS/rvm.onnx https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx"; }
[ -f "$SKILL/assets/fonts/Anton-Regular.ttf" ] && [ -f "$SKILL/assets/vendor/gsap.min.js" ] && ok "bundled fonts + GSAP" || bad "skill assets missing: re-download the skill folder"
[ -f "$HOME/.claude/skills/edit-video/SKILL.md" ] && ok "skill registered (~/.claude/skills/edit-video)" || { bad "skill not registered with Claude Code"; fix "mkdir -p ~/.claude/skills && ln -s \"$SKILL\" ~/.claude/skills/edit-video"; }
[ -d "$SKILL/assets/sfx" ] && ls "$SKILL/assets/sfx" | grep -q . && ok "sound pack (assets/sfx)" || echo "  [--] no sound pack in assets/sfx (optional: synth fallback is used; drop whoosh/hit/pop/stamp/type/tick .mp3 or .wav there)"
echo
[ "$MISSING" = 0 ] && echo "All good. In your video project folder run:  claude   then   /edit-video" || echo "Paste the fix lines above into Terminal one at a time, then run doctor again."
