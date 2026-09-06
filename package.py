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
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG_NAME = "cross-device-sync"
VERSION = "6.3.9"

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
    secret = PKG_SRC / "secret.txt"
    assert not secret.exists(), (
        "REFUSING to package: secret.txt (real passcode) found in dist tree. "
        "Only secret-example.txt may ship."
    )
    # manifest version consistency
    mtext = manifest.read_text(encoding="utf-8")
    assert f"version: {VERSION}" in mtext, (
        f"manifest.yaml version mismatch: expected version: {VERSION}")


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
