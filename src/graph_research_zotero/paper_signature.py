from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str
    evidence: str
    strength: Literal["direct", "author_interpretation", "inference"]
    locator: str


class LoadBearingConcept(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept: str
    distinguishes: str
    depends_on: list[str]
    affects: list[str]
    example: str
    boundary: str


class PaperSignature(BaseModel):
    """Machine-facing companion to a human-readable ljg-paper note."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    title: str
    research_problem: str
    prior_assumption: str
    prior_failure: str
    main_contribution: str
    change_type: Literal["relation", "operation", "evaluation", "feasibility", "mixed"]
    change_description: str
    mechanism_steps: list[str]
    evidence: list[EvidenceItem]
    limitations: list[str]
    boundary_conditions: list[str]
    load_bearing_concepts: list[LoadBearingConcept]
    open_questions: list[str]
    transfer_candidates: list[str]
    confidence: float = Field(ge=0.0, le=1.0)

    def embedding_text(self) -> str:
        """Canonical text for the second-order research embedding.

        Deliberately excludes long prose and paper full text. The goal is to
        represent problem structure / mechanism / evidence / limitations rather
        than duplicate Zotero's existing semantic embedding space.
        """
        payload = {
            "research_problem": self.research_problem,
            "prior_assumption": self.prior_assumption,
            "prior_failure": self.prior_failure,
            "main_contribution": self.main_contribution,
            "change_type": self.change_type,
            "change_description": self.change_description,
            "mechanism_steps": self.mechanism_steps,
            "evidence": [item.model_dump() for item in self.evidence],
            "limitations": self.limitations,
            "boundary_conditions": self.boundary_conditions,
            "load_bearing_concepts": [item.model_dump() for item in self.load_bearing_concepts],
            "open_questions": self.open_questions,
            "transfer_candidates": self.transfer_candidates,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class DeepReadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_markdown: str
    signature: PaperSignature


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text


def parse_deep_read_result(raw: str) -> DeepReadResult:
    """Parse direct JSON or common CLI JSON wrappers into the typed result."""
    text = _strip_json_fence(raw)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Agent output does not contain a JSON object") from None
        payload = json.loads(text[start : end + 1])

    if isinstance(payload, dict) and "note_markdown" in payload and "signature" in payload:
        return DeepReadResult.model_validate(payload)

    # Claude Code --output-format json wraps the assistant text in `result`.
    if isinstance(payload, dict) and "result" in payload:
        nested = payload["result"]
        if isinstance(nested, str):
            return parse_deep_read_result(nested)
        if isinstance(nested, dict):
            return DeepReadResult.model_validate(nested)

    raise ValueError("Agent JSON does not match DeepReadResult")
