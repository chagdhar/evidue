from __future__ import annotations

import json
from pathlib import Path

from app.agreements.consensus import (
    assurance_provider_unavailable_diagnostic,
    compiler_consensus_report,
    consensus_blocking_diagnostic,
)
from app.agreements.qualification import apply_mutation, compile_pack_proposal, load_pack

PACK_ROOT = Path("qualification/fixtures/outcome-pricing-e2e")


def _replace_value(value, old: str, new: str):
    if isinstance(value, dict):
        return {key: _replace_value(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_value(item, old, new) for item in value]
    if value == old:
        return new
    if isinstance(value, str):
        return value.replace(f"${old}", f"${new}")
    return value


def test_identical_semantics_do_not_block_approval() -> None:
    pack = load_pack(PACK_ROOT)
    proposal = json.loads((PACK_ROOT / "proposal.json").read_text())
    first = compile_pack_proposal(pack, proposal, run_number=1)
    second = compile_pack_proposal(pack, proposal, run_number=2)

    report = compiler_consensus_report(first, second)

    assert report["agreed"] is True
    assert report["changed_sections"] == []
    assert consensus_blocking_diagnostic(report) is None


def test_material_disagreement_blocks_instead_of_model_voting() -> None:
    pack = load_pack(PACK_ROOT)
    proposal = json.loads((PACK_ROOT / "proposal.json").read_text())
    first = compile_pack_proposal(pack, proposal, run_number=1)

    mutated_pack = apply_mutation(pack, pack.manifest.mutations[0])
    mutated_proposal = _replace_value(proposal, "1.50", "1.75")
    second = compile_pack_proposal(mutated_pack, mutated_proposal, run_number=2)

    report = compiler_consensus_report(first, second)
    diagnostic = consensus_blocking_diagnostic(report)

    assert report["agreed"] is False
    assert set(report["changed_sections"]) == {"pricing", "rules"}
    assert report["approval_blocked"] is True
    assert diagnostic is not None
    assert diagnostic.code == "INDEPENDENT_COMPILER_DISAGREEMENT"
    assert diagnostic.severity == "blocking"


def test_required_secondary_provider_failure_is_blocking() -> None:
    diagnostic = assurance_provider_unavailable_diagnostic("secondary-provider")

    assert diagnostic.code == "INDEPENDENT_COMPILER_UNAVAILABLE"
    assert diagnostic.severity == "blocking"
    assert "cannot be approved" in diagnostic.message
