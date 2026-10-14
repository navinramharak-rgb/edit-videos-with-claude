# plan.json reference

```json
{
  "video": "vertical_cut.mp4",          "words": "vertical_cut_words.json",   "matte": "matte_540.u8",
  "fps": 30, "duration": 64.0,          "anchor": [540, 560],                 "style": {"accent": "#FF6B2E"},
  "captions": { "style": "mixed", "y": 1290, "size": 92, "max_words": 4,
                "emphasis": ["claude", "free"], "phrases": ["Claude did", "for free"],
                "hide": [["@studies", "@captions+0.5"]] },
  "camera":  [ {"t": "@claude", "z": 1.16, "dur": 0.1, "ease": "settle"}, {"t": "@done", "z": 1.0, "dur": 0.6, "ease": "smooth"} ],
  "grade":   [ {"t0": -1, "t1": "@claude<", "mode": "raw"}, {"t0": "@it's", "t1": "@promise-0.02", "mode": "bw"} ],
  "look":    {"contrast": 1.08, "warm_r": 1.03, "warm_b": 0.97, "vignette": 0.18, "from": "@claude"},
  "flash": ["@claude"], "flash_alpha": 120, "shake": ["@go"], "drift": [[-1, "@claude<"]],
  "blur_bg": [["@claude", 999]], "blur_px": 9,
  "sound": {"switch_on": "@claude"},
  "elements": [ ... ]
}
```

## Time references
`"@word"` start of the first occurrence · `"@word#2"` third occurrence (0-based) · `"@word+0.25"` / `"@word-0.1"` offsets · `"@word<"` start of the word even in a `t1` (end times otherwise resolve to the END of the word) · a plain number is seconds · `999` = until the end. Words are matched case-insensitively with punctuation stripped; `"@it's"` works.

## Elements
Every element has `type`, `t0`, `t1` (and `engine: "py"` for `image`). `behind: true` puts an html element behind the person (needs the matte).

| type | fields | notes |
|---|---|---|
| `profile_card` | `name`, `handle`, `avatar` (png) or `letter`, `mark` x/ok, `mark_at`, `y`, `rot` | X slams on `mark_at`, card shakes |
| `kinetic` | `text`, `size` (330), `y`, `rot`, `from` right/left, `color` accent/white, `x_end` | extruded Anton, use `behind: true` |
| `hook_box` | `text` (`*accent*`), `y` | white tilted box |
| `pill` | `text`, `y` | caption-sized white pill |
| `brackets` | | zoom corners around the face |
| `cut_marker` | | one-frame white line (jump cut tell) |
| `raw_tag` | `text` | "● RAW · 00:00:07" corner tag |
| `poster` | `small`, `big`, `sub`, `theme` dark, `big_orange`, `big_size`, `big_y`, `small_y`, `sub_y`, `rule_w` | full-screen; captions auto-hidden |
| `list_panel` | `title`, `items: [{text, t}]`, `y` | glass panel, current item accent |
| `cards` | `items: [{text, t, dot, dark, rot}]`, `xs`, `y` | chips pop with overshoot |
| `prompt` | `text`, `label`, `y`, `type_end` | typing bar |
| `behind_text` / `word_stack` | `text` or `items: [{text, t, color}]`, `size`, `y`, `font` anton/serif | behind the head |
| `stamp` | `text`, `y` | |
| `cta` | `text`, `btn`, `y` | hugs its text |
| `card_image` | `path`, `w`, `h`, `y`, `rot`, `label` | tilted photo card |
| `board` | `path`, `w`, `y` | real screenshot on dark |
| `image` (py) | `path` (jpg/png/mp4), `mode` full/card | |
| `filmstrip` | `dir` (jpgs) or `frames`, `count_to`, `h` | scrolling strip + FRAME counter |
| `exploded` | `title`, `layers: [{path, label}]` | dark; layers fan out, labels stagger |
| `timeline` | `items: [{kind: cut|caption|zoom|removed, t, t_end, label}]`, `clips`, `video_only`, `transcript` (`~struck~`), `y` | |
| `phone_fan` | `phones: [{path, label} or {n}]`, `spread`, `y` | own videos as phones |
| `silhouette` | `cutout` (time), `text`, `y` | black cutout + glow |
| `outro` | `headline`, `word`, `sub`, `brand`, `skill`, `reactions` | dark end card |

## Camera eases
`snap` (instant), `settle` (fast in, soft land), `smooth`, `creep` (slow push over `dur`). `dur: 0` with two keyframes = jump cut.

## Captions
`style: "mixed"` = Inter ExtraBold + Instrument Serif Italic accent words; omit for serif-only. `phrases` lists the lines that get a caption (in order; each must appear verbatim in the transcript). Captions auto-hide under `poster`, `board`, `exploded`, `silhouette`, `outro` and full `image`; add other ranges in `hide`.
