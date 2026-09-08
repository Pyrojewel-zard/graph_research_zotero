from __future__ import annotations

import os
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()
UPSTREAM = "https://github.com/Seaual/meta-knowledge-graph.git"


def project_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists():
        return cwd
    return Path(__file__).resolve().parents[2]


def vendor_path() -> Path:
    configured = os.getenv("MKG_SOURCE_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return project_root() / ".vendor" / "meta-knowledge-graph"


def main() -> None:
    target = vendor_path()
    if (target / "mkg").is_dir():
        console.print(f"[green]MKG source already present[/green]: {target}")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    console.print(f"Cloning Meta Knowledge Graph into {target}")
    subprocess.run(
        ["git", "clone", "--depth", "1", UPSTREAM, str(target)],
        check=True,
    )
    console.print("[green]MKG source ready[/green]")
    console.print(f"MKG_SOURCE_PATH={target}")


if __name__ == "__main__":
    main()
