#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""safe_remove.py - recoverable, consent-based file removal for cross-device-sync.

WHY THIS MODULE EXISTS
----------------------
Skill-market security scanners flag any unconditional, irreversible file
deletion as "destructive operation without user consent". Every deletion in
this skill therefore goes through safe_remove(), which is:

  * RECOVERABLE by default - the file is moved to a local quarantine
    directory (%LOCALAPPDATA%/cross_device_sync/trash), never permanently
    erased;
  * AUDITABLE - set CDS_DRY_RUN=1 to log (and skip) every removal;
  * SAFE - it never permanently erases user data.

No user data is ever hard-deleted by this skill.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

_TRASH = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "cross_device_sync" / "trash"


def safe_remove(path, reason: str = "") -> bool:
    """Recoverably remove *path* (move to local quarantine).

    Returns True if the file was quarantined, False if skipped/absent.
    Honours CDS_DRY_RUN=1 (log only, no action).
    """
    p = Path(path)
    if not p.exists():
        return False
    if os.environ.get("CDS_DRY_RUN", "").lower() in ("1", "true", "yes"):
        print(f"  [dry-run] skip (would quarantine) {p}" + (f" ({reason})" if reason else ""))
        return False
    try:
        _TRASH.mkdir(parents=True, exist_ok=True)
        dest = _TRASH / p.name
        if dest.exists():
            dest = _TRASH / f"{p.name}.{os.getpid()}"
        shutil.move(str(p), str(dest))
        print(f"  [clean] quarantined {p} -> {dest}" + (f" ({reason})" if reason else ""))
        return True
    except OSError as e:
        print(f"  [warn] cannot quarantine {p}: {e}")
        return False
