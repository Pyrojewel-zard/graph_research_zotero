from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class AgentRunError(RuntimeError):
    pass


class AgentRunner(Protocol):
    name: str

    def available(self) -> bool: ...

    def run(
        self,
        prompt: str,
        *,
        output_schema: dict[str, Any] | None = None,
        cwd: Path | None = None,
    ) -> str: ...


@dataclass(frozen=True)
class RunnerConfig:
    binary: str
    model: str | None = None
    timeout_seconds: float = 900.0


class _SubprocessRunner:
    name = "base"

    def __init__(self, config: RunnerConfig) -> None:
        self.config = config

    def available(self) -> bool:
        return shutil.which(self.config.binary) is not None

    def version(self) -> str | None:
        if not self.available():
            return None
        try:
            completed = subprocess.run(
                [self.config.binary, "--version"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        text = (completed.stdout or completed.stderr).strip()
        return text or None

    def _execute(
        self,
        command: list[str],
        *,
        prompt: str,
        cwd: Path | None,
    ) -> subprocess.CompletedProcess[str]:
        if not self.available():
            raise AgentRunError(f"{self.name} executable not found: {self.config.binary}")
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                cwd=str(cwd) if cwd else None,
                timeout=self.config.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AgentRunError(
                f"{self.name} timed out after {self.config.timeout_seconds:.0f}s"
            ) from exc
        except OSError as exc:
            raise AgentRunError(f"failed to start {self.name}: {exc}") from exc

        if completed.returncode != 0:
            stderr = completed.stderr.strip()[-4000:]
            raise AgentRunError(
                f"{self.name} exited with code {completed.returncode}: {stderr}"
            )
        return completed


class CodexRunner(_SubprocessRunner):
    """Non-interactive Codex CLI adapter.

    The full paper prompt is provided on stdin to avoid command-line length
    limits. Codex's `--output-schema` is used when available, and the returned
    payload is still validated by the application afterwards.
    """

    name = "codex"

    def build_command(
        self,
        *,
        schema_path: Path,
        output_path: Path,
    ) -> list[str]:
        command = [
            self.config.binary,
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
        ]
        if self.config.model:
            command.extend(["--model", self.config.model])
        command.append("-")
        return command

    def run(
        self,
        prompt: str,
        *,
        output_schema: dict[str, Any] | None = None,
        cwd: Path | None = None,
    ) -> str:
        schema = output_schema or {
            "type": "object",
            "additionalProperties": True,
        }
        with tempfile.TemporaryDirectory(prefix="grz-codex-") as tmp:
            tmp_path = Path(tmp)
            schema_path = tmp_path / "schema.json"
            output_path = tmp_path / "result.json"
            schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
            completed = self._execute(
                self.build_command(schema_path=schema_path, output_path=output_path),
                prompt=prompt,
                cwd=cwd,
            )
            if output_path.exists():
                output = output_path.read_text(encoding="utf-8").strip()
                if output:
                    return output
            return completed.stdout.strip()


class ClaudeRunner(_SubprocessRunner):
    """Claude Code print-mode adapter.

    Claude Code's JSON mode wraps the assistant response in a top-level
    `result` string. `parse_deep_read_result` handles that wrapper later.
    """

    name = "claude"

    def build_command(self) -> list[str]:
        command = [
            self.config.binary,
            "--print",
            "--output-format",
            "json",
            "--max-turns",
            "1",
        ]
        if self.config.model:
            command.extend(["--model", self.config.model])
        command.append(
            "Use only the task and paper content supplied on stdin. "
            "Do not modify files. Return the requested JSON object only."
        )
        return command

    def run(
        self,
        prompt: str,
        *,
        output_schema: dict[str, Any] | None = None,
        cwd: Path | None = None,
    ) -> str:
        # Claude's CLI schema surface differs from Codex. The generated prompt
        # contains the JSON contract and the application validates it afterwards.
        del output_schema
        completed = self._execute(self.build_command(), prompt=prompt, cwd=cwd)
        return completed.stdout.strip()


def build_runner(
    name: str,
    *,
    codex_binary: str = "codex",
    codex_model: str | None = None,
    claude_binary: str = "claude",
    claude_model: str | None = None,
    timeout_seconds: float = 900.0,
) -> AgentRunner:
    normalized = name.strip().lower()
    if normalized == "codex":
        return CodexRunner(
            RunnerConfig(codex_binary, model=codex_model, timeout_seconds=timeout_seconds)
        )
    if normalized == "claude":
        return ClaudeRunner(
            RunnerConfig(claude_binary, model=claude_model, timeout_seconds=timeout_seconds)
        )
    raise ValueError(f"Unsupported agent runner: {name}")
