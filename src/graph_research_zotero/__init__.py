"""Zotero MCP to Meta Knowledge Graph bridge."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _activate_mkg_source() -> None:
    candidates: list[Path] = []
    configured = os.getenv("MKG_SOURCE_PATH")
    if configured:
        candidates.append(Path(configured).expanduser())

    candidates.append(Path.cwd() / ".vendor" / "meta-knowledge-graph")
    try:
        candidates.append(Path(__file__).resolve().parents[2] / ".vendor" / "meta-knowledge-graph")
    except IndexError:
        pass

    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / "mkg").is_dir():
            text = str(resolved)
            if text not in sys.path:
                sys.path.insert(0, text)
            break


_activate_mkg_source()

__all__ = ["__version__"]
__version__ = "0.1.0"
