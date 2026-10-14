#!/usr/bin/env bash
# Creates the beginner workspace: ~/Claude Video Edits with raw/ and a double-clickable "Edit Video.command".
set -u
W="$HOME/Claude Video Edits"; mkdir -p "$W/raw" "$W/references" "$W/renders"
cat > "$W/Edit Video.command" <<'EOC'
#!/usr/bin/env bash
# Double-click me. Opens Claude in this folder and starts the editor.
cd "$HOME/Claude Video Edits"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"
command -v brew >/dev/null 2>&1 && export PATH="$(brew --prefix ffmpeg-full 2>/dev/null)/bin:$PATH"
if ! command -v claude >/dev/null 2>&1; then echo "Claude Code is not installed yet. Run the installer first (buildwithnav.com/edit)."; read -r -p "Press Enter to close."; exit 1; fi
if ! ls raw/* >/dev/null 2>&1; then echo "Drop a video into the 'raw' folder first (it's in this same folder), then double-click me again."; open "$HOME/Claude Video Edits/raw"; read -r -p "Press Enter to close."; exit 1; fi
clear; echo "Starting Claude. Answer its questions, approve the cut list, approve the storyboard, say go."; echo
claude "/edit-video"
EOC
chmod +x "$W/Edit Video.command"
cat > "$W/README.txt" <<'EOT'
How to edit a video with Claude

1. Drop your raw recording into the "raw" folder.
2. (First time only, optional) drop 5 to 10 of your own videos into "references" so it learns your style.
3. Double-click "Edit Video". Claude asks a couple of questions, shows you the cut list, shows you a storyboard, then renders.
4. Your finished video appears in "renders".

Something broken? Open Terminal and run:  bash ~/edit-videos-with-claude/doctor.sh
EOT
echo "  [ok] workspace: $W (raw/, references/, renders/, Edit Video.command)"
