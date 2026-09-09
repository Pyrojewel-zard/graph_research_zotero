from pathlib import Path

from graph_research_zotero.agent_runner import ClaudeRunner, CodexRunner, RunnerConfig


def test_codex_command_uses_stdin_and_structured_output():
    runner = CodexRunner(RunnerConfig("codex", model="gpt-test", timeout_seconds=30))
    command = runner.build_command(
        schema_path=Path("/tmp/schema.json"),
        output_path=Path("/tmp/result.json"),
    )
    assert command[:2] == ["codex", "exec"]
    assert "--ephemeral" in command
    assert "--sandbox" in command
    assert "read-only" in command
    assert "--output-schema" in command
    assert "--output-last-message" in command
    assert ["--model", "gpt-test"] == command[command.index("--model") : command.index("--model") + 2]
    assert command[-1] == "-"


def test_claude_command_is_noninteractive_json():
    runner = ClaudeRunner(RunnerConfig("claude", model="sonnet", timeout_seconds=30))
    command = runner.build_command()
    assert command[0] == "claude"
    assert "--print" in command
    assert command[command.index("--output-format") + 1] == "json"
    assert command[command.index("--max-turns") + 1] == "1"
    assert command[command.index("--model") + 1] == "sonnet"
