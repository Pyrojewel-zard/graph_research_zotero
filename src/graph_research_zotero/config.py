from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    zotero_mcp_url: str
    zotero_library_id: int | None
    mkg_db_path: Path
    llm_provider: str
    llm_api_key: str | None
    llm_model: str
    llm_base_url: str | None
    enable_s2_enrichment: bool

    agent_runner: str
    agent_timeout_seconds: float
    codex_binary: str
    codex_model: str | None
    claude_binary: str
    claude_model: str | None
    deep_read_dir: Path

    research_embedding_base_url: str | None
    research_embedding_api_key: str | None
    research_embedding_model: str | None
    research_embedding_timeout_seconds: float


def _optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(value)


def _optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _float(value: str | None, default: float) -> float:
    if value is None or not value.strip():
        return default
    return float(value)


def load_settings() -> Settings:
    load_dotenv()
    db_path = Path(os.getenv("MKG_DB_PATH", "./data/mkg.db")).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    deep_read_dir = Path(os.getenv("DEEP_READ_DIR", "./data/deep_reads")).expanduser().resolve()
    deep_read_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        zotero_mcp_url=os.getenv("ZOTERO_MCP_URL", "http://127.0.0.1:23120/mcp").strip(),
        zotero_library_id=_optional_int(os.getenv("ZOTERO_LIBRARY_ID")),
        mkg_db_path=db_path,
        llm_provider=os.getenv("MKG_LLM_PROVIDER", "openai").strip(),
        llm_api_key=_optional_str(os.getenv("MKG_LLM_API_KEY")),
        llm_model=os.getenv("MKG_LLM_MODEL", "gpt-5-mini").strip(),
        llm_base_url=_optional_str(os.getenv("MKG_LLM_BASE_URL")),
        enable_s2_enrichment=os.getenv("MKG_ENABLE_S2_ENRICHMENT", "false").lower()
        in {"1", "true", "yes", "on"},
        agent_runner=os.getenv("DEEP_READ_AGENT", "codex").strip().lower(),
        agent_timeout_seconds=_float(os.getenv("DEEP_READ_AGENT_TIMEOUT_SECONDS"), 900.0),
        codex_binary=os.getenv("CODEX_BINARY", "codex").strip(),
        codex_model=_optional_str(os.getenv("CODEX_MODEL")),
        claude_binary=os.getenv("CLAUDE_BINARY", "claude").strip(),
        claude_model=_optional_str(os.getenv("CLAUDE_MODEL")),
        deep_read_dir=deep_read_dir,
        research_embedding_base_url=_optional_str(os.getenv("RESEARCH_EMBEDDING_BASE_URL")),
        research_embedding_api_key=_optional_str(os.getenv("RESEARCH_EMBEDDING_API_KEY")),
        research_embedding_model=_optional_str(os.getenv("RESEARCH_EMBEDDING_MODEL")),
        research_embedding_timeout_seconds=_float(
            os.getenv("RESEARCH_EMBEDDING_TIMEOUT_SECONDS"), 120.0
        ),
    )
