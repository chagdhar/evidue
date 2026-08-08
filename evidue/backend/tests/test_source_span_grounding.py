from __future__ import annotations

import pytest
from app.agreements.compiler_models import (
    AgreementCompilationProposal,
    ClauseAnalysisProposal,
    SourceDocumentRef,
)
from app.agreements.native_compiler import _build_source_spans, bind_proposal_to_sources


def _proposal(*, quote: str, spans: list[str]) -> AgreementCompilationProposal:
    return AgreementCompilationProposal(
        compiler_version="test",
        contract_id="C1",
        model="test",
        provider="test",
        source_documents=[SourceDocumentRef(document_id="DOC-1", title="Contract")],
        clauses=[
            ClauseAnalysisProposal(
                clause_id="CL-1",
                source_document_id="DOC-1",
                source_span_ids=spans,
                source_text=quote,
                clause_type="pricing",
            )
        ],
    )


def test_span_ids_preserve_original_bytes_and_offsets() -> None:
    text = "Heading\nProvider earns $1.00 per outcome.\nEnd"
    spans = _build_source_spans({"DOC-1": ("Contract", text)})
    span = spans["SPAN-000002"]
    assert span.text == "Provider earns $1.00 per outcome."
    assert text[span.start : span.end] == span.text


def test_live_binding_ignores_model_paraphrase_and_uses_original_span() -> None:
    text = "Heading\nProvider earns $1.00 per outcome.\nEnd"
    proposal = _proposal(
        quote="The provider receives one dollar for every outcome.",
        spans=["SPAN-000002"],
    )
    bound = bind_proposal_to_sources(
        proposal,
        expected_contract_id="C1",
        source_documents={"DOC-1": ("Contract", text)},
        require_source_spans=True,
    )
    clause = bound.clauses[0]
    assert clause.source_text == "Provider earns $1.00 per outcome."
    assert clause.source_start == text.index(clause.source_text)
    assert clause.source_end == clause.source_start + len(clause.source_text)
    assert clause.source_text_hash is not None


def test_live_binding_rejects_unknown_span() -> None:
    with pytest.raises(ValueError, match="unknown source span"):
        bind_proposal_to_sources(
            _proposal(quote="anything", spans=["SPAN-999999"]),
            expected_contract_id="C1",
            source_documents={"DOC-1": ("Contract", "Provider earns $1.00 per outcome.")},
            require_source_spans=True,
        )


def test_live_binding_requires_span_ids() -> None:
    with pytest.raises(ValueError, match="omitted source_span_ids"):
        bind_proposal_to_sources(
            _proposal(quote="Provider earns $1.00 per outcome.", spans=[]),
            expected_contract_id="C1",
            source_documents={"DOC-1": ("Contract", "Provider earns $1.00 per outcome.")},
            require_source_spans=True,
        )
