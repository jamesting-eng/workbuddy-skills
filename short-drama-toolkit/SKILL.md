---
name: short-drama-toolkit
version: 1.1.2
description: 短剧导演实战百宝箱：专治短剧开拍前各类剧本痛点。一部短剧从创意到开拍前的所有文档，一次出齐。
agent_created: true
---

> **Documentation showcase.** This file documents the workflow and the director's taste guidelines. The runnable, payment-gated skill (including the scripts that do the actual assembly) is distributed through **SkillHub** — search `short-drama-toolkit` (publisher *user_839f3063*). Reproduced here for transparency; not a drop-in skill.

# 短剧导演实战百宝箱（Short-Drama Toolkit）

A director's field toolkit for short-form drama / micro-drama projects. From script revision to shoot scheduling, every document a director needs before cameras roll is produced in one pipeline — output as ready-to-use `docx` / `xlsx` / `PDF`. Validated end-to-end on a real short-drama project (anonymized; all examples fictional and generic).

The pipeline is reusable across real productions:

- From **script revision** to **AI storyboard PDF + shooting schedule**, the toolchain is battle-tested
- The methodology below (especially the taste guidelines) is the substance of the toolkit

## 何时用（When To Use）

- A script received external revision notes (AI suggestions / actor voice memos) that need to land as a new version
- A fresh script needs an overall quality diagnosis (script-doctor assessment) before deciding how to rewrite
- Actors struggle with line-reading and need a Hollywood-standard formatted screenplay
- The script is locked and needs a shot breakdown (shot list xlsx + AI storyboard PDF)
- A single shooting day needs a continuity-checked schedule (makeup / transitions / golden hour)
- Real locations need scouting before the shoot (28-field record sheet + movement-line SOP)
- A new project needs a character bible, or the diagnosis surfaced character problems to fix
- After AI storyboards exist, turn them into a **silent motion preview** to align camera rhythm and shot timing before shooting

## 导演审美红线（Director's Taste Red Lines — read before touching anything）

These are the user's hard-won judgment standards, not process steps:

0. **Script is the soul (highest principle)**: content quality comes first. Polish the process all you want — if the script is weak, the output is garbage. Fix content before process; breakdown/schedule/layout are all downstream of the script.
1. **Storyboard = readable at a glance by the director**: abstract stick-figure/silhouette boards get rejected — generate per-shot AI art directly.
2. **Batch only after samples**: 3 frames to validate style, then full batch after approval; report the total budget upfront.
3. **Dialogue balance = structural health**: if a main character has no lines for two consecutive episodes, suspect a structure problem — don't excuse it.
4. **Layout serves the first reader**: the screenplay is for actors to read lines (cue/dialogue indent columns separated), not for you. "Looks tiring to read" is a reject reason.
5. **Check external notes line by line** (AI suggestions / actor voice memos marked ✓/✗ each), not "referenced as a whole."
6. **Found a BUG? Fix upstream before downstream**: only continue producing downstream docs after logic is self-consistent.
7. **Archive only head + tail** (original + final); process files are fine to delete. When the user says delete, delete — don't second-guess.
8. **Motion preview is silent by default**: when generating a "storyboard motion-preview video", add no BGM by default — code-composed BGM reads as cheap/uncanny (even "ancient-pentatonic" doesn't save it). Deliver silent unless the user supplies royalty-cleared BGM; footstep/page-turn SFX must be separate stems.

## 全流程 SOP（Full Pipeline SOP — in order）

### 第 0 步：读判断手册（强制，不可跳过 / Read the judgment handbook — mandatory）

Before doing anything, read `references/taste-and-judgment.md` in full (the content & taste handbook, 24+ real director corrections). The 8 red lines above are only a summary; the handbook is the complete set. Skipping it = losing half the toolkit's value.

### 第 1 步：剧本改稿落地（Script Revision）

**Diagnose before rewriting**: before a new script / major rewrite, run the script-doctor assessment (framework in `references/script-doctor.md`: 5 categories, 23 four-grade items + 100-point score + 7-dimension revision notes). Confirm the issue list with the user before writing — scoring only locates problems; rewrite order follows the diagnosis (fix low-structure scores first, dialogue issues later).
**Character low-scores** (motivation conflict / token character / dumbed-down) → rebuild the character bible with `references/character-sheet.md` (59-item 3-layer questionnaire: physical / psychological / social); "the decisive moment in the past" is where the sole main-motive answer lives.

Principle: **only add dialogue,微调 wording — never move camera blocking/movement lines** (they cascade). Check external notes line by line against the existing script: satisfied → ✓; not → embed new lines into existing shots. After rewriting, two-way verify: forward (every script line → found in shot list) + reverse (shot-list dialogue column → found in script original).

### 第 2 步：好莱坞格式剧本 docx（Hollywood-Format Screenplay）

Layout rules (full spec in `references/hollywood-format.md`: six-element decision rules + US-standard geometry + degradation modes): six element types separated by **indent columns**, never center the whole page of dialogue — scene heading 12pt bold flush-left; action flush-left; character cue indent 150pt (before8/after2, glued to dialogue); dialogue left=70pt / **right=60pt** narrow column; parenthetical emotion note merged into cue line; transition right-aligned; line spacing 1.3 (line=312); body bold 10.5pt (五号), US Letter (612×792pt).

**Format acceptance (run after every layout revision, deliver only on PASS)**: `scripts/verify_format.py` — checks each line of the exported PDF against indent buckets (flush-left/70/150 ±3pt) and transition right-alignment, reporting unmatched lines. Format degrades (lesson learned); re-accept fully every revision, not just changed spots.

### 第 3 步：拆分镜 → shots.json 中间数据（Shot Breakdown → shots.json）

**shots.json is the quality hub of the whole pipeline**: shot list / AI art / AI board / schedule — four downstream consumers all read it (schema in `references/shots-schema.md`). **The sole source of AI-art prompts = shots.json; never skip breakdown and generate art straight from script text** — AI guessing shots from literary text paints everything as medium shots, with no cut logic, losing director intent (a red line).

Two breakdown granularities by script density:
- **Script already has shot/action cues** (high granularity): breakdown = structured extraction + framing/camera design; shots drawn directly from the script's action description
- **Pure literary script** (only narration + dialogue): before breakdown, do **shot-translation** — split each scene's narration into beats, set framing/camera/composition/dialogue per beat; show the translation (breakdown design) to the director for confirmation before固化 into shots.json — moves sample-approval up to the data layer, avoiding批量 art that misses the intent

Character visual anchoring: script's own costume cues → hard-code into the fixed style prefix; the canonical collection source for appearance material = `references/character-sheet.md` physical layer (costume/hair/build/jewelry/scar 5-combo); pure literary script lacking visual settings → **first produce 2-3 character design images for director confirmation**, hard-code the confirmed appearance into the prefix. Consistency comes from the prefix anchor, not AI initiative.

### 第 4 步：AI 手绘分镜生图（AI Storyboard Art — the user-approved best approach）

Program-drawn (stick-figure / silhouette) boards get rejected — **generate per-shot AI art directly**, with a "hand-drawn comic cinematic storyboard" look.

Flow:
1. **3 style samples first** (close-up / medium / wide — framing control is the biggest risk), full batch only after approval
2. Prompt template in `references/shots-schema.md`: fixed style prefix + `第0NN镜：` prefix + per-shot framing/character/lighting/mood — **per-shot elements from shots.json, never improvised from script text**
3. Size 1536x1024, quality=medium (~6 credits/shot; report total budget by shot count before running)
4. After generation, rename uniformly `shot_NN.png`, verify zero missing
5. Post shots (title/name/end cards) get no art; assemble as black-background caption cells

### 第 5 步：组装 AI 分镜 PDF（Assemble AI Storyboard PDF）

`scripts/assemble_ai_board.py` (edit the top CONFIG block: image dir / shots.json / output path / project name / total shots / start shot # / post-shot notes). Auto: center-crop 1.85:1 (face biased up, y-offset 35%), camera-move marks overlay (blue = push/follow/orbit/OTS/reverse/slow-mo/FX/subjective; red = fast-cut), episode-cut markers, Cadrage layout (Letter 300dpi, 8 cells/page, 2-line caption under each, header shows scene range).

### 第 6 步：顺场表（单日拍摄 / Shooting Schedule）

`scripts/build_schedule.py` (**BLOCKS/CHECK/SCENE_MAP data block + trailing assert values (total shots / duration / cut blocks) must be refilled per project; logic is generic**).

Core principles (from real pitfalls):
- **Makeup flows one direction**: each makeup state must be a continuous interval on the timeline; switches only at transitions / meal breaks. Injury makeup applied once + removed once — otherwise continuity breaks or a redo that can't be undone (a real v1 schedule died here)
- "Pre-injury plot" must never land in the injured time block; next-day (healed) plot uniformly makeup-free, so it shares makeup with the prior day
- Transition time's reliable source = scouting data (`references/scouting.md`: road/equipment transport/orientation/lighting window); **unscouted** degrades to a conservative 30-min standalone reserve + a机动 buffer block
- Golden hour: check local sunset, reverse-plan the costume window (use a stunt double wide shot when tight)
- FX shots: shoot more framings (wide/hand/close/empty) — the title cold-open relies on reversed FX material; too little = nothing to cut in post
- Self-check: full shot # coverage no duplicates, cut shots land in the right block, makeup verified per block ✓

### 第 7 步：生成视频（分镜动态预览 / Storyboard Motion Preview）

Turn static storyboards into a "moving preview" to align camera rhythm, shot duration, and transition feel before shooting. Full SOP + script in `references/video-preview.md` + `scripts/make_video_preview.py`.

> ⚠️ **Compute / credit reminder (mandatory; when the user chooses "generate video", inform and get confirmation first)**: this calls image-to-video on **every** storyboard frame — 3–17s per shot, dozens of shots across the whole drama consumes **significant compute + credits** (tens of minutes, billed by shot × duration). If static storyboards (AI storyboard PDF) already express the intent, you can skip video generation. Only start the batch after the user explicitly says "I know the time + credits, still generate"; 3 samples per shot first for style + character consistency, then full.

Flow (details in the reference):
1. Per-shot video: `shot_NN.png` as the first frame, image-to-video, motion prompt = camera move + description; keep the style prefix
2. Duration normalization: crop / slow (≤2x) + tail-frame hold per `dur` in shots.json; unify fps/resolution
3. Post shots: title cold-open = reversed tail segment; name/end cards = black-background white-text
4. Concat + audio: **silent by default (`-an`)**; only mux BGM if the user explicitly wants it and supplies a licensed track (pass `--bgm`); SFX on separate stems
5. Reuse `scripts/make_video_preview.py` for normalization + concat + mux (silent without `--bgm`)

## 目录结构（Repository Layout）

```
short-drama-toolkit/            # this documentation mirror
├── SKILL.md                     # This file: workflow SOP + director's taste guidelines
├── README.md                    # Showcase / landing page (English)
├── LICENSE.txt                  # Tiered license notice
└── references/
    ├── taste-and-judgment.md    # Judgment handbook: what gets rejected, and why
    ├── script-doctor.md         # Script-doctor evaluation framework (pre-rewrite diagnosis)
    ├── character-sheet.md       # 59-item 3-layer character bible questionnaire
    ├── hollywood-format.md      # Hollywood-format spec (measured parameters + degradation modes)
    ├── shots-schema.md          # shots.json schema + AI-art prompt template
    ├── scouting.md              # Location scouting (28-field checklist + field SOP)
    └── video-preview.md         # Storyboard motion-preview SOP
```

The runnable scripts (`verify_format.py`, `assemble_ai_board.py`, `build_schedule.py`, `make_video_preview.py`, and the payment gate) are distributed via SkillHub and are **not** included in this documentation mirror.

## 版权与许可（License）

This toolkit is proprietary to **南京新菁年影视科技有限责任公司（Nanjing New-Youth Film & Technology Co., Ltd.）**, tiered-licensed, not open source:

- **Documentation / knowledge** (`SKILL.md`, `references/*`): CC BY-NC-ND 4.0 — attribution required for learning reference; no commercial use, no derivative redistribution
- **Code** (`scripts/*`): Proprietary — direct code-level reuse is **not permitted**; copy / modify / redistribute / embed in other projects requires prior written consent from the copyright holder

Full terms in `LICENSE.txt`.
