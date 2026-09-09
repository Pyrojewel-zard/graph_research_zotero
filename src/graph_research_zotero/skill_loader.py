from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillBundle:
    name: str
    revision: str
    text: str
    root: Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ljg_paper_skill_dir() -> Path:
    return project_root() / ".agents" / "skills" / "ljg-paper"


def _read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _revision_from_vendor_info(text: str) -> str | None:
    match = re.search(r"^- Commit:\s*([0-9a-f]{7,40})\s*$", text, flags=re.MULTILINE)
    return match.group(1) if match else None


def load_ljg_paper_skill() -> SkillBundle:
    root = ljg_paper_skill_dir()
    required = [root / "SKILL.md", root / "ReadingGuide.md"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Vendored ljg-paper skill is incomplete; missing: " + ", ".join(missing)
        )

    sections = [
        ("SKILL.md", _read_optional(root / "SKILL.md")),
        ("ReadingGuide.md", _read_optional(root / "ReadingGuide.md")),
        ("references/template.md", _read_optional(root / "references" / "template.md")),
    ]
    combined = "\n\n".join(
        f"===== {name} =====\n{content.strip()}" for name, content in sections if content.strip()
    )

    vendor_info = _read_optional(root / "UPSTREAM_VENDOR_INFO.md")
    revision = _revision_from_vendor_info(vendor_info)
    if not revision:
        revision = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]

    return SkillBundle(name="ljg-paper", revision=revision, text=combined, root=root)
