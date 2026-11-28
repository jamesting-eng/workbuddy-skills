#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a SkillHub-ready zip package for cross-device-sync.

Usage:  python package.py

What it does:
  1. Validates the dist/ Chinese tree: manifest.yaml + SKILL.md exist, SKILL.md
     has frontmatter with name/description, and secret.txt (real values) is NOT
     present. (NOTE: the package is built from dist/cross-device-sync/, the
     Chinese SkillHub tree -- NOT the repo root, which is the English GitHub
     source. See PKG_SRC below.)
  2. Zips all skill files from dist/cross-device-sync/ under a
     `cross-device-sync/` prefix (SkillHub expects a folder-wrapped package),
     excluding repo/runtime artifacts.
  3. Writes dist/cross-device-sync-<version>.zip and prints a manifest.

Zero dependencies (stdlib only). Run from the repo root.
"""
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG_NAME = "cross-device-sync"
VERSION = "7.1.3"

# SkillHub package is built from the Chinese-ready dist tree, NOT the repo root.
# ROOT is the GitHub/English source; dist/cross-device-sync/ is the SkillHub/Chinese
# tree (localized SKILL.md/README/manifest, LICENSE.txt, no .bat, no .gitignore).
# Building from ROOT previously shipped the English SKILL.md to SkillHub -- a relapse
# of the "SkillHub must be 100% Chinese" red line. Fixed in 6.3.9.
PKG_SRC = ROOT / "dist" / PKG_NAME

EXCLUDE_NAMES = {
    ".git", ".github", "dist", "__pycache__", "node_modules",
    ".gitignore",  # SkillHub rejects this file type (400); GitHub keeps it
    "secret.txt",  # real passcode must NEVER ship
    "package.py",  # build tool itself, not part of the skill
}
EXCLUDE_SUFFIXES = {".log", ".pid", ".pyc", ".zip", ".bat"}  # SkillHub rejects .bat
EXCLUDE_LIVENESS_PREFIXES = ("liveness_", "heartbeat_")


# ── Language-gate tuning (measured 2026-10-29, not guessed) ──────────────────
# Chinese tree today: SKILL.md 846/1420 CJK lines (60%), README 160/253 (63%),
# AI_HANDOFF_GUIDE 142/228 (62%), sync-task-SKILL 195/346 (56%),
# sync-identity-guide 37/71 (52%). The English root versions sit at 0% for all of
# them (root SKILL.md keeps 42 CJK lines because it quotes Chinese literals).
# So a 30% ratio floor + a 20-line absolute floor separates them with wide margin.
CJK_RATIO_MIN = 0.30
CJK_LINES_MIN = 20

# Docs that are legitimately English in BOTH trees — exempt from the language gate.
# PUBLISH.md is a release-history table written in English on purpose (1 CJK line).
ENGLISH_ONLY_DOCS = {"PUBLISH.md"}

# Sections added 2026-10-29. If a stale or partially-overwritten doc slips past the
# language gate, these disappear — so their absence is itself a failure signal.
FIELD_TEST_MARKERS = (
    ("单台机器在同步目录里反复写", "Q4: conflict copies from ONE machine"),
    ("第零板：先暂停 WPS 同步", "Axe 0: pause sync before bulk deletes"),
    ("要看文件数", "file-count guard for test runs"),
)


def _frontmatter_version(text: str) -> str:
    """Version from a SKILL.md YAML frontmatter (first 20 lines)."""
    for ln in text.splitlines()[:20]:
        if ln.strip().startswith("version:"):
            return ln.split(":", 1)[1].strip().strip('"').strip("'")
    return ""


def _manifest_version(text: str) -> str:
    """Version from a manifest.yaml."""
    for ln in text.splitlines()[:20]:
        if ln.strip().startswith("version:"):
            return ln.split(":", 1)[1].strip().strip('"').strip("'")
    return ""


def validate() -> None:
    manifest = PKG_SRC / "manifest.yaml"
    skill = PKG_SRC / "SKILL.md"
    assert manifest.exists(), "dist manifest.yaml missing (SkillHub required)"
    assert skill.exists(), "dist SKILL.md missing"
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---"), "SKILL.md must start with YAML frontmatter"
    fm = text.split("---", 2)[1]
    assert "name:" in fm, "SKILL.md frontmatter missing name"
    assert "description:" in fm, "SKILL.md frontmatter missing description"

    # ── Gate 1: EVERY Chinese doc in the dist tree must actually be Chinese ──
    # 6.4.3 shipped the English docs by accident: a root-to-dist sync overwrote the
    # Chinese docs and nothing caught it, because only SKILL.md was ever checked.
    for md in sorted(PKG_SRC.rglob("*.md")):
        rel_parts = md.relative_to(PKG_SRC).parts
        if any(part in EXCLUDE_NAMES for part in rel_parts):
            continue
        rel = md.relative_to(PKG_SRC).as_posix()
        if md.name in ENGLISH_ONLY_DOCS:
            continue
        body = md.read_text(encoding="utf-8", errors="replace")
        lines = body.splitlines()
        cjk = sum(1 for ln in lines if re.search(r"[\u4e00-\u9fff]", ln))
        total = len(lines) or 1
        assert cjk >= CJK_LINES_MIN and (cjk / total) >= CJK_RATIO_MIN, (
            f"REFUSING to package: {rel} is only {cjk}/{total} CJK lines "
            f"({cjk / total:.0%}) — the Chinese doc was likely overwritten by its "
            "English root version. Restore it from the latest dist zip before packaging."
        )

    # ── Gate 2: root and dist SKILL.md must NOT be identical ──
    # One tree is English, the other Chinese. Identical content means the English
    # root was copied over the Chinese tree — exactly the 6.4.3 regression.
    root_skill = ROOT / "SKILL.md"
    if root_skill.exists():
        root_text = root_skill.read_text(encoding="utf-8")
        assert root_text.strip() != text.strip(), (
            "REFUSING to package: root SKILL.md and dist SKILL.md are identical. "
            "The English root has been copied over the Chinese dist tree (the 6.4.3 "
            "regression). Restore the Chinese SKILL.md from the latest dist zip."
        )

    # ── Gate 3: version must agree in all four places ──
    mtext = manifest.read_text(encoding="utf-8")
    assert f"version: {VERSION}" in mtext, (
        f"dist manifest.yaml version mismatch: expected version: {VERSION}")
    dist_v = _frontmatter_version(text)
    assert dist_v == VERSION, (
        f"dist SKILL.md version is {dist_v!r}, expected {VERSION!r} — bump both trees together")
    if root_skill.exists():
        root_v = _frontmatter_version(root_skill.read_text(encoding="utf-8"))
        assert root_v == VERSION, (
            f"root SKILL.md version is {root_v!r}, expected {VERSION!r}")
        root_manifest = ROOT / "manifest.yaml"
        if root_manifest.exists():
            root_mv = _manifest_version(root_manifest.read_text(encoding="utf-8"))
            assert root_mv == VERSION, (
                f"root manifest.yaml version is {root_mv!r}, expected {VERSION!r}")

    # ── Gate 4: the 2026-10-29 field-test sections must survive in the dist tree ──
    for marker, what in FIELD_TEST_MARKERS:
        assert marker in text, (
            f"REFUSING to package: dist SKILL.md is missing the section {what!r} "
            f"(marker: {marker!r}). A stale or partially-overwritten doc got through."
        )

    secret = PKG_SRC / "secret.txt"
    assert not secret.exists(), (
        "REFUSING to package: secret.txt (real passcode) found in dist tree. "
        "Only secret-example.txt may ship."
    )


def collect_files() -> list[Path]:
    files = []
    for p in sorted(PKG_SRC.rglob("*")):
        if not p.is_file():
            continue
        if any(part in EXCLUDE_NAMES for part in p.relative_to(PKG_SRC).parts):
            continue
        if p.suffix.lower() in EXCLUDE_SUFFIXES:
            continue
        if p.name.startswith(EXCLUDE_LIVENESS_PREFIXES):
            continue
        files.append(p)
    return files


def main() -> int:
    try:
        validate()
    except AssertionError as e:
        print(f"[FAIL] {e}")
        return 1

    out_dir = ROOT / "dist"
    out_dir.mkdir(exist_ok=True)
    out_zip = out_dir / f"{PKG_NAME}-{VERSION}.zip"

    files = collect_files()
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in files:
            arcname = Path(PKG_NAME) / p.relative_to(PKG_SRC)
            # SkillHub rejects an extensionless LICENSE; ship it as LICENSE.txt
            # (the repo keeps the GitHub-standard extensionless LICENSE).
            if arcname.name == "LICENSE":
                arcname = arcname.with_name("LICENSE.txt")
            zf.write(p, arcname.as_posix())

    print(f"[OK] {out_zip}")
    print(f"     {len(files)} files, prefix '{PKG_NAME}/'")
    for p in files:
        print(f"       - {(Path(PKG_NAME) / p.relative_to(PKG_SRC)).as_posix()}")
    # paranoia: verify no secret inside
    with zipfile.ZipFile(out_zip) as zf:
        names = zf.namelist()
        assert not any(n.endswith("/secret.txt") for n in names), "secret.txt leaked!"
    print("[OK] secret.txt check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
