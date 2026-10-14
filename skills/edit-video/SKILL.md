---
name: edit-video
description: Edit a raw talking-head recording into a finished, captioned, motion-graphic short in the creator's own style, on their Mac. Use when someone says "edit this video", drops a raw take in a folder, or asks for captions, cuts, zooms, graphics, a cut list or a storyboard for a video.
---

# Edit video

One raw take in, a finished vertical video out. Scripts do the mechanical work (transcribe, cut, reframe, matte, render, mix). You make the creative calls and check the result like an editor would. The creator approves twice: the **cut list** and the **storyboard**. Nothing renders before the storyboard is approved.

Skill root: the folder this file is in (`$SKILL`). Scripts in `scripts/`, runner `edit.sh`, presets in `presets/`, a worked example in `examples/`, field reference in `reference/plan-schema.md`. Python: `~/.claude-video/venv/bin/python`. Work happens inside the creator's **project folder** (wherever they keep the video), never inside the skill folder.

## 0. Interview + machine check (every run, keep it short)

1. Run `bash $SKILL/setup/doctor.sh`. If anything is `[!!]`, show the creator the exact fix lines it printed and stop until they're done. Don't try to install things yourself.
2. Ask at most three questions, only the ones you can't infer:
   - Where is the raw file? (Look in `raw/` and the current folder first. If there's a separate mic file next to it, use it.)
   - Platform and format? Default 9:16, 1080x1920, 30fps.
   - What's the one thing the video is for: teach, sell, or story, and what's the CTA? (If a script was pasted, infer it.)
3. If `style/STYLE.md` exists in the project, read it. If not, run step 1. If the creator says "just use the default", use `presets/nav-signature.json` and say so.

Set up the project layout if missing: `raw/ work/ renders/ style/ references/ assets/sfx/`.

## 1. Learn the style (once per creator, 10 minutes)

Ask for 5 to 10 of their own videos plus a couple they wish they'd made, in `references/`. Run `bash $SKILL/scripts/analyze_refs.sh references` (length, cuts per minute, loudness, contact sheets). Look at the sheets yourself.

Write `style/STYLE.md`: caption font and treatment, accent colour, pace (seconds between visual changes), which cutaway types they use, how they handle the hook and the CTA, loudness, what they never do. Keep the creator's own videos separate from the admired ones: their videos define the voice, the admired ones define the ceiling. Save it as a preset too (`style/preset.json`, same shape as `presets/nav-signature.json`) so the plan can read it.

One rule that transfers from every great reference: **every spoken claim gets a prop.** Not a caption, a prop: a card, a word, a strip, a layer view, a real screenshot. Pattern interrupt every 1 to 2.5 seconds. Information gets followers; a prop that literalises the claim gets rewatches.

## 2. Transcribe + cut list (first approval)

`bash $SKILL/edit.sh prep raw/VIDEO.mov` writes `work/VIDEO/words.json`, `transcript.txt`, `edl.json`, `cutlist.md`, `preview_cut.mp4`.

Read `transcript.txt` and `cutlist.md` and fix what the script got wrong: a retake it missed (same line twice: keep the LAST complete take), a list it flagged as a false start, a pause that is a deliberate beat. Edit `edl.json` by hand if needed. Show the creator the cut list as a short table (keep / cut / why, seconds saved). Wait for approval.

Landscape source? Reframe BEFORE cutting (cutting 4K first runs out of memory): `bash $SKILL/edit.sh reframe raw/VIDEO.mov`, then `bash $SKILL/edit.sh cut raw/VIDEO.mov`. Vertical source: just `cut`. Then `bash $SKILL/edit.sh matte work/VIDEO` (person matte: needed for behind-the-head text, cutouts, silhouette, background blur).

## 3. Plan the edit (write `work/VIDEO/plan.json`)

Go through `vertical_cut_words.json` line by line and give every line a prop. Full field reference: `reference/plan-schema.md`. Start from `examples/plan-edit1.json` if the style is nav-signature.

Timing is always tied to spoken words, never to seconds: `"@word"`, `"@word#2"` (third occurrence), `"@word+0.2"`, `"@word<"` (start of the word, for end times). The engine throws if the word isn't in the transcript, so copy words exactly from `words.json`.

Rules that make it look edited by a person:
- Hook on frame 1. The first 2 seconds should look "raw" (grade `raw`, `raw_tag`, `drift`) and the edit "switches on" at the first spoken name of the thing (`sound.switch_on`, `look.from`, `flash`, a `kinetic` word behind the head).
- Safe zones: lower third (y 1450 to 1650) and above the head (y 60 to 320). Never cover the face while the person is speaking. Screenshots and cards go below the chin (`board` with `lower: true`, y 1190, w 640) and captions shift up (`captions.y_over_board`, 1110). Full-screen takeovers are for moments that work without the face. Full-screen takeovers (poster, board, exploded, silhouette, image full) are 1.5 to 3s, never two in a row.
- Mixed-typography captions: bold sans, the one meaning-carrying word per phrase in italic serif accent (`captions.style: "mixed"`, list the accent words in `captions.emphasis`). Phrases, not every word: `captions.phrases` lists the 60% of lines that deserve a caption.
- Proof over decoration: the real cut list, the real storyboard, real screenshots (`board`), the real source frames (`filmstrip`). Never invent results, numbers, logos or testimonials.
- Camera: a snap punch-in (1.08 to 1.22) on emphasis words, a slow creep on explanations, back to 1.0 on resets. Max one jump cut per 10s.
- Sound: one whoosh per 10s, only on posters, kinetic words and layer views. Everything else is a pop, tick or thud. Music is added on the platform at posting.
- Background: leave it sharp when the set looks good (a textured wall is part of the look). Blur behind the person (`blur_bg`, `blur_px` 8 to 10) only when the background is plain or messy.
- The creator's "never" list in the preset wins over everything above.

## 4. Storyboard (second approval, hard gate)

`bash $SKILL/edit.sh board work/VIDEO/plan.json 0.4,2.1,...` with one timestamp per beat. It renders real frames with the real graphics and opens `storyboard.html`: frame, spoken line, what's on screen. Walk the creator through it in 5 lines: hook, the three biggest props, the CTA. Ask for notes per timestamp. Change the plan, re-run `board`, repeat until they say **go**. Do not render before "go".

## 5. Render

`bash $SKILL/edit.sh render work/VIDEO/plan.json` (graphics in headless Chromium, then the picture pass, then auto sound design from `resolved.json`; drops in a real sound pack from `assets/sfx/` when present). Then `bash $SKILL/edit.sh mix work/VIDEO renders/VIDEO_v1.mp4` (voice clean-up, two-pass loudnorm to -14 LUFS / -1.5 dBTP, H.265 delivery).

Plan on ~1x realtime per pass on an M-series Mac for the picture pass and about the same for graphics. Run passes one at a time with `nice` (the runner does).

## 6. QA before anyone sees it

Make a contact sheet of a frame at every beat and every cut (`ffmpeg -ss T -frames:v 1`) and look at it. Check: face never covered; captions readable on the actual clothing colour; nothing clipped at the edges; captions hidden under every full-screen takeover; the first frame is a real hook; every graphic leaves on time (no lingering overlays: use `@word<` for end times); loudness -14 ±0.5 (`ffmpeg -af ebur128`); no pops at cuts. Fix and re-render, max 3 passes. Tell the creator what you checked and what is still imperfect. Never claim it's perfect.

## 7. Notes, learning loop, cost log

Take notes like an editor: what the creator changed and why. Append their corrections to `style/STYLE.md` and the preset's `never` list so the next video starts there. Log wall-clock time, machine time and estimated cost per video in `renders/log.md` (they will want this number).

## Element types (engine `html` unless noted)

`profile_card` (name card, red X or check slams on a word), `kinetic` (giant extruded word slides behind the head), `hook_box`, `pill` (caption pill), `brackets` (zoom corners), `cut_marker`, `raw_tag`, `poster` (full-screen slam, orange or dark, letter-by-letter big word, underline, sub line), `list_panel` (glass list, builds item by item), `cards` (chips), `prompt` (typing bar), `behind_text` / `word_stack` (behind the head), `stamp`, `cta`, `card_image`, `board` (real screenshot on dark), `image` (engine `py`: full/card, also .mp4), `filmstrip` (real source frames + frame counter), `exploded` (the edit comes apart into labelled layers), `timeline` (video/captions/zoom tracks, or `video_only` with red `removed` regions + struck transcript), `phone_fan` (own videos as phones), `silhouette` (black cutout, orange glow, one word), `outro` (comment box types the word, reactions pop).

Global: `captions`, `camera` (zoom keyframes, eases `snap` `smooth` `creep` `settle`), `grade` (`raw`, `bw` ranges), `look` (contrast, warmth, vignette, `from`), `flash`, `flash_alpha`, `shake`, `drift`, `blur_bg`, `blur_px`, `sound.switch_on`, `duration`.
