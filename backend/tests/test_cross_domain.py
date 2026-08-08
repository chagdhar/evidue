"""Cross-domain contract qualification tests.

Proves the qualification infrastructure works across contract categories
without contract-specific code paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.agreements.qualification import (
    load_pack,
)

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "qualification" / "fixtures"
DOWNLOADED = ROOT / "qualification" / "downloaded"


def _all_packs() -> list[Path]:
    packs = []
    for base in (FIXTURES, DOWNLOADED):
        if base.exists():
            for child in sorted(base.iterdir()):
                if (child / "manifest.json").exists():
                    packs.append(child)
    return packs


@pytest.mark.parametrize("pack_path", _all_packs(), ids=lambda p: p.name)
def test_pack_loads_and_validates(pack_path: Path) -> None:
    """Every qualification pack must load without errors."""
    pack = load_pack(pack_path)
    assert pack.manifest.id
    assert len(pack.documents) >= 1
    # Every document must have readable text
    for doc_id, (filename, text) in pack.documents.items():
        assert len(text) > 10, f"Document {doc_id} ({filename}) has no readable content"


@pytest.mark.parametrize("pack_path", _all_packs(), ids=lambda p: p.name)
def test_gold_validates_against_schema(pack_path: Path) -> None:
    """Every gold file must validate against the QualificationGold schema."""
    pack = load_pack(pack_path)
    if pack.gold is None:
        pytest.skip(f"No gold file for {pack_path.name}")
    assert len(pack.gold.terms) >= 1
    for term in pack.gold.terms:
        assert term.source_phrase, f"Term {term.id} has no source_phrase"
        # Verify source_phrase exists in at least one document (whitespace-normalized)
        normalized_phrase = " ".join(term.source_phrase.split())
        found = any(
            normalized_phrase in " ".join(text.split()) for _, (_, text) in pack.documents.items()
        )
        assert found, (
            f"Term {term.id} source_phrase not found in any document: {term.source_phrase[:60]!r}"
        )


@pytest.mark.parametrize("pack_path", _all_packs(), ids=lambda p: p.name)
def test_scenarios_validate_against_schema(pack_path: Path) -> None:
    """Every scenario file must validate against QualificationScenarioSet."""
    pack = load_pack(pack_path)
    if pack.scenarios is None:
        pytest.skip(f"No scenario file for {pack_path.name}")
    assert len(pack.scenarios.scenarios) >= 1
    for scenario in pack.scenarios.scenarios:
        assert scenario.expected_status in ("payable", "disputed", "needs_review")
        # Conservation: expected amounts must equal billed
        from decimal import Decimal

        billed = Decimal(scenario.billed_amount)
        total = (
            Decimal(scenario.expected_payable_amount)
            + Decimal(scenario.expected_disputed_amount)
            + Decimal(scenario.expected_needs_review_amount)
        )
        assert billed == total, (
            f"Scenario {scenario.id}: conservation violated in expected amounts {billed} != {total}"
        )


@pytest.mark.parametrize("pack_path", _all_packs(), ids=lambda p: p.name)
def test_mutations_are_findable(pack_path: Path) -> None:
    """Every mutation's find text must exist in the target document."""
    pack = load_pack(pack_path)
    if not pack.manifest.mutations:
        pytest.skip(f"No mutations for {pack_path.name}")
    for mutation in pack.manifest.mutations:
        doc = pack.documents.get(mutation.document_id)
        assert doc is not None, (
            f"Mutation {mutation.id} references missing document {mutation.document_id}"
        )
        _, text = doc
        assert mutation.find in text, (
            f"Mutation {mutation.id}: find text not found in document: {mutation.find[:60]!r}"
        )
