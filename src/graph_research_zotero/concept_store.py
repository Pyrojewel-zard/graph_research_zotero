from __future__ import annotations

from typing import Any


class ConceptTreeStore:
    """Persist an MKG ConceptTree using public repository methods.

    This intentionally does not call backend ProcessService._save_concepts().
    The bridge writes concepts, paper associations and hierarchy relations
    explicitly so the graph is complete.
    """

    def __init__(self, db: Any) -> None:
        self.db = db

    def replace_paper_associations(self, paper_identifier: str) -> list[str]:
        """Remove old per-paper links before a changed paper is reprocessed.

        Global concept hierarchy edges are retained because MKG does not track
        per-paper relation provenance.  Orphan concepts are cleaned when safe.
        """
        rows = self.db.execute_read(
            "SELECT concept_id FROM paper_concepts WHERE paper_doi = ?",
            (paper_identifier,),
        ).fetchall()
        old_ids = [row["concept_id"] for row in rows]
        self.db.execute_write(
            "DELETE FROM paper_concepts WHERE paper_doi = ?",
            (paper_identifier,),
        )
        self.db.execute_write(
            "DELETE FROM concept_extractions WHERE paper_doi = ?",
            (paper_identifier,),
        )
        for concept_id in old_ids:
            try:
                self.db.concepts._update_paper_count(concept_id)
            except Exception:
                pass
        return old_ids

    def save(
        self,
        paper_identifier: str,
        hierarchy: dict[str, Any] | None,
        *,
        raw_response: str = "",
    ) -> int:
        if not hierarchy:
            return 0

        count = 0

        def walk(node: dict[str, Any], parent_id: str | None = None, depth: int = 0) -> None:
            nonlocal count
            if depth > 30:
                raise ValueError("Concept hierarchy exceeds maximum supported depth (30)")

            text = str(node.get("concept") or "").strip()
            text_en = node.get("concept_en")
            if not text and text_en:
                text = str(text_en).strip()
            if not text:
                return

            concept_id = self.db.concepts.add(
                {
                    "id": node.get("id"),
                    "text": text,
                    "text_en": text_en,
                    "text_zh": text,
                    "category": node.get("category"),
                }
            )
            confidence = float(node.get("confidence", 1.0) or 1.0)
            self.db.concepts.add_paper_concept(
                paper_identifier,
                concept_id,
                relevance=confidence,
            )
            self.db.execute_write(
                """
                UPDATE paper_concepts
                SET source = 'llm', is_anchor = ?, contribution_role = ?
                WHERE paper_doi = ? AND concept_id = ?
                """,
                (
                    1 if node.get("is_anchor") else 0,
                    node.get("contribution_role"),
                    paper_identifier,
                    concept_id,
                ),
            )

            if parent_id and parent_id != concept_id:
                self.db.concepts.add_relation(parent_id, concept_id, "parent-child")

            count += 1
            for child in node.get("children", []) or []:
                if isinstance(child, dict):
                    walk(child, concept_id, depth + 1)

        walk(hierarchy)
        self.db.concepts.save_extraction(paper_identifier, hierarchy, raw_response)
        try:
            self.db.concepts.recalculate_depth_cache()
        except Exception:
            pass
        return count
