# Short-Drama Toolkit

> **Showcase & documentation repository.** This page describes the skill and its methodology. The full, runnable, payment-gated skill installs from **SkillHub** — see [Install](#install).

A director's field toolkit for short-form drama / micro-drama projects, covering the full pipeline from script revision to shoot scheduling. Every step was validated end-to-end on a real short-drama production and hardened through multiple rounds of director feedback (project details anonymized; all examples are fictional and generic).

---

## What It Does

One toolkit, every document a director needs before the cameras roll — produced as ready-to-use `docx` / `xlsx` / `PDF`.

| Module | Artifact | Highlights |
| --- | --- | --- |
| Script Doctor | Diagnostic report | 5 categories, 23 items on a 4-grade scale + 100-point overall score + 7-dimension revision notes — diagnose before you rewrite |
| Character Sheet | 59-item questionnaire | 3-layer character bible (physical / psychological / social) — doubles as the visual-anchoring source for AI storyboard art |
| Hollywood Format | Screenplay docx | Industry-standard indent-column layout adapted for Chinese screenplays; auto-verified against a PASS/FAIL checker |
| Shot Breakdown | shots.json + xlsx | Structured intermediate data shared by 4 downstream consumers |
| AI Storyboard | Cadrage-style PDF | Hand-drawn comic look, per-shot AI generation, camera-move marks, auto-assembled |
| Location Scouting | 28-field checklist | Field SOP + 4-category decision framework; feeds real transition times into the schedule |
| Shooting Schedule | xlsx | Single-day schedule with makeup/wardrobe continuity verification |
| **Storyboard Motion Preview** | mp4 | Turn static storyboards into a "moving preview" to align camera rhythm, shot duration, and transitions *before* shooting (see below) |

---

## Spotlight: Storyboard Motion Preview

The newest capability. Once static storyboards exist, the toolkit can turn them into a **silent motion preview** — each storyboard frame becomes an image-to-video clip, normalized to the shot duration from `shots.json`, then concatenated.

Use it to align camera movement, shot length, and transition feel **before a single frame is shot** — not as a finished piece.

- Default **silent delivery** (no synthesized BGM — code-composed music reads as cheap/uncanny; only mux royalty-cleared audio when the director supplies it)
- Heavy compute: image-to-video is called **per storyboard frame**; the toolkit warns about time + credit cost and requires explicit confirmation before batch generation
- 3 style samples first, full batch only after approval

> Full SOP lives in [`references/video-preview.md`](./references/video-preview.md).

---

## Pricing

This is a **Pay Skill**, billed **per run**:

- **¥2.68 per run** (≈ $0.37 USD at publication exchange rate)
- Charged through **Alipay** via SkillHub's Pay-Skill settlement — no card, no subscription
- The payment gate is enforced by the platform; the runnable skill (including the gate) lives on SkillHub, not here

You only pay when you actually invoke the toolkit. Diagnosis, rewriting, formatting, breakdown, storyboard, scouting, scheduling, and the motion preview are all metered the same way.

---

## Workflow at a Glance

1. **Diagnose** — run the script doctor; confirm the issue list with the director before touching the script
2. **Rewrite** — check external feedback line by line; never move locked camera blocking
3. **Format** — Hollywood-standard docx; re-run the format checker until PASS on every revision
4. **Break down** — produce `shots.json` (the quality hub of the whole pipeline; image prompts come from here, never from raw script text)
5. **Generate** — 3 style samples first, batch only after approval; report the full budget upfront
6. **Assemble** — Cadrage-layout storyboard PDF with camera-move marks
7. **Schedule** — scouting data → single-day schedule with continuity checks
8. **Preview** — optional: turn storyboards into a silent motion preview to lock the rhythm before shooting

The director's hard-won taste guidelines (what gets rejected, and why) are documented in [`references/taste-and-judgment.md`](./references/taste-and-judgment.md) — the substance of the toolkit, and the part worth reading even if you never install it.

---

## Install

The runnable, payment-gated skill is distributed through **SkillHub** (the scripts that do the actual assembly are not published here):

1. Open **SkillHub** inside WorkBuddy
2. Search for **`short-drama-toolkit`** (publisher: *user_839f3063*)
3. Install — the toolkit then triggers on keywords like "short drama", "script revision", "shooting schedule", "location scouting"

Direct link: **https://skillhub.cn/skills/user_839f3063/short-drama-toolkit**

> This GitHub repository is the **showcase / documentation** mirror. It contains the methodology (`SKILL.md`, `references/`) and license — not the executable scripts.

---

## Repository Layout

```
short-drama-toolkit/
├── README.md                     # This page (showcase / landing)
├── SKILL.md                      # Documentation: workflow SOP + director's taste guidelines
├── LICENSE.txt                   # Tiered license notice (proprietary code, CC BY-NC-ND docs)
└── references/
    ├── taste-and-judgment.md     # Judgment handbook: what gets rejected, and why
    ├── script-doctor.md          # Evaluation framework (pre-rewrite diagnosis)
    ├── character-sheet.md        # 59-item character bible questionnaire
    ├── hollywood-format.md       # Format spec with measured parameters
    ├── shots-schema.md           # shots.json schema + image-gen prompt template
    ├── scouting.md               # Location scouting checklist + field SOP
    └── video-preview.md          # Storyboard motion-preview SOP
```

The runnable scripts (`verify_format.py`, `assemble_ai_board.py`, `build_schedule.py`, `make_video_preview.py`, and the payment gate) are distributed via SkillHub and are **not** included here.

---

## Requirements (for the SkillHub build)

- Python 3.10+ (3.13 recommended)
- pillow / pymupdf / openpyxl
- Windows CJK fonts (msyh.ttc / msyhbd.ttc — preinstalled on Windows)
- ffmpeg 7.x for the motion-preview post-processing

---

## License

Tiered license — see [LICENSE.txt](./LICENSE.txt) for full terms:

- **Documentation** (`SKILL.md`, `references/*`): [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/en) — attribution required, non-commercial, no derivatives
- **Code** (`scripts/*`): Proprietary. Direct code-level reuse, modification, redistribution, or embedding in other projects is **not permitted** without prior written consent from the copyright holder.

© 2026 南京新菁年影视科技有限责任公司（Nanjing New-Youth Film & Technology Co., Ltd.）. All rights reserved.
