"""Zotero MCP to vendored Meta Knowledge Graph bridge."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _activate_mkg_source() -> None:
    """Put the vendored MKG source tree on sys.path.

    ``MKG_SOURCE_PATH`` remains as an explicit developer override, but normal
    installs from this repository use ``vendor/meta-knowledge-graph`` directly.
    No runtime clone/download is required.
    """
    candidates: list[Path] = []

    configured = os.getenv("MKG_SOURCE_PATH")
    if configured:
        candidates.append(Path(configured).expanduser())

    root = _project_root()
    candidates.extend(
        [
            root / "vendor" / "meta-knowledge-graph",
            Path.cwd() / "vendor" / "meta-knowledge-graph",
        ]
    )

    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / "mkg").is_dir():
            text = str(resolved)
            if text not in sys.path:
                sys.path.insert(0, text)
            return

    raise RuntimeError(
        "Vendored Meta Knowledge Graph source was not found. Expected "
        "vendor/meta-knowledge-graph (or set MKG_SOURCE_PATH explicitly)."
    )


_activate_mkg_source()

__all__ = ["__version__"]
__version__ = "0.1.0"
