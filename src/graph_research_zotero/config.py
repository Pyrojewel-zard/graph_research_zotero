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


def _optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(value)


def _optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def load_settings() -> Settings:
    load_dotenv()
    db_path = Path(os.getenv("MKG_DB_PATH", "./data/mkg.db")).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        zotero_mcp_url=os.getenv("ZOTERO_MCP_URL", "http://127.0.0.1:23120/mcp").strip(),
        zotero_library_id=_optional_int(os.getenv("ZOTERO_LIBRARY_ID")),
        mkg_db_path=db_path,
        llm_provider=os.getenv("MKG_LLM_PROVIDER", "openai").strip(),
        llm_api_key=_optional_str(os.getenv("MKG_LLM_API_KEY")),
        llm_model=os.getenv("MKG_LLM_MODEL", "gpt-5-mini").strip(),
        llm_base_url=_optional_str(os.getenv("MKG_LLM_BASE_URL")),
        enable_s2_enrichment=os.getenv("MKG_ENABLE_S2_ENRICHMENT", "false").lower() in {"1", "true", "yes", "on"},
    )
