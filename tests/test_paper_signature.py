import json

from graph_research_zotero import paper_signature as signatures

PAYLOAD = {
    "note_markdown": "# Note\n\nA useful explanation.",
    "signature": {
        "paper_id": "paper-a",
        "title": "Paper A",
        "research_problem": "Optimize a circuit under a fixed budget.",
        "prior_assumption": "One topology is sufficient.",
        "prior_failure": "The assumption fails across topology changes.",
        "main_contribution": "A transferable graph representation.",
        "change_type": "relation",
        "change_description": "Topology is represented as a graph rather than a fixed vector.",
        "mechanism_steps": ["encode topology", "predict performance"],
        "evidence": [
            {
                "claim": "Transfer improves.",
                "evidence": "Three held-out topologies are evaluated.",
                "strength": "direct",
                "locator": "Table 2",
            }
        ],
        "limitations": ["No post-layout validation."],
        "boundary_conditions": ["Only tested on one process node."],
        "load_bearing_concepts": [
            {
                "concept": "topology graph",
                "distinguishes": "connectivity from flat sizing vectors",
                "depends_on": ["circuit netlist"],
                "affects": ["transferability"],
                "example": "A CS and CG stage have different graph structure.",
                "boundary": "Graph encoding quality limits the representation.",
            }
        ],
        "open_questions": ["Does it survive post-layout parasitics?"],
        "transfer_candidates": ["layout-aware optimization"],
        "confidence": 0.88,
    },
}


def test_parse_direct_and_claude_wrapped_result():
    direct = signatures.parse_deep_read_result(json.dumps(PAYLOAD))
    assert isinstance(direct, signatures.DeepReadResult)
    assert direct.signature.paper_id == "paper-a"

    wrapped = signatures.parse_deep_read_result(
        json.dumps({"type": "result", "is_error": False, "result": json.dumps(PAYLOAD)})
    )
    assert wrapped.signature.main_contribution.startswith("A transferable")


def test_embedding_text_excludes_human_note_and_is_stable():
    result = signatures.DeepReadResult.model_validate(PAYLOAD)
    first = result.signature.embedding_text()
    second = result.signature.embedding_text()
    assert first == second
    assert "A useful explanation" not in first
    assert "No post-layout validation" in first
