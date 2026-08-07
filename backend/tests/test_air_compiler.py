"""Tests for native AIR compilation pipeline (Milestones 1-6)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from app.agreements.compiler import lower_to_agreement_ir
from app.agreements.compiler_models import (
    AgreementCompilationProposal,
    ClauseAnalysisProposal,
    ConditionProposal,
    DefinitionProposal,
    NormProposal,
    ReferenceProposal,
    SettlementProposal,
    SourceDocumentRef,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_proposal(**overrides: object) -> AgreementCompilationProposal:
    """Build a minimal valid proposal for testing."""
    defaults: dict = {
        "compiler_version": "test-1.0",
        "contract_id": "TEST-CONTRACT",
        "model": "test-model",
        "provider": "test",
        "source_documents": [SourceDocumentRef(document_id="DOC-1", title="Test Agreement")],
        "definitions": [],
        "clauses": [
            ClauseAnalysisProposal(
                clause_id="CL-1",
                source_document_id="DOC-1",
                source_text="Price is $1.50 per outcome.",
                material=True,
                clause_type="pricing",
                settlement_effects=[
                    SettlementProposal(
                        id="S1",
                        settlement_type="fixed_per_unit",
                        parameters={"unit_price": "1.50"},
                        source_clause_id="CL-1",
                        description="$1.50 per outcome",
                    )
                ],
            )
        ],
        "global_diagnostics": [],
    }
    defaults.update(overrides)
    return AgreementCompilationProposal.model_validate(defaults)


def _grounded_minimal_proposal() -> AgreementCompilationProposal:
    """Return the minimal proposal with the exact source binding required for approval."""
    from app.agreements.native_compiler import bind_proposal_to_sources

    proposal = _minimal_proposal()
    return bind_proposal_to_sources(
        proposal,
        expected_contract_id="TEST-CONTRACT",
        source_documents={"DOC-1": ("Test Agreement", "Price is $1.50 per outcome.")},
    )


def _clause_with_norm(
    clause_id: str = "CL-NORM",
    norm_id: str = "N1",
    condition_type: str = "field_present",
    condition_params: dict | None = None,
    norm_type: str = "obligation",
    consequence: str = "disputed",
    **clause_overrides: object,
) -> ClauseAnalysisProposal:
    if condition_params is None:
        condition_params = {"field": "outcome_id"}
    return ClauseAnalysisProposal(
        clause_id=clause_id,
        source_document_id="DOC-1",
        source_text="Test clause text",
        material=True,
        clause_type="performance",
        norms=[
            NormProposal(
                id=norm_id,
                norm_type=norm_type,
                subject="vendor",
                condition=ConditionProposal(
                    condition_type=condition_type,
                    parameters=condition_params,
                    description="test condition",
                ),
                consequence=consequence,
            )
        ],
        **clause_overrides,
    )


# ---------------------------------------------------------------------------
# M1: Schema validation tests
# ---------------------------------------------------------------------------


class TestCompilerModels:
    def test_unknown_condition_type_rejected(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            ConditionProposal(
                condition_type="invent_new_logic",  # type: ignore[arg-type]
                parameters={},
                description="bad",
            )

    def test_unknown_settlement_type_rejected(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            SettlementProposal(
                id="S1",
                settlement_type="magic_pricing",  # type: ignore[arg-type]
                parameters={},
                source_clause_id="CL-1",
                description="bad",
            )

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            ConditionProposal(
                condition_type="field_present",
                parameters={"field": "x"},
                description="ok",
                secret_field="hack",  # type: ignore[call-arg]
            )

    def test_field_present_requires_field(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            ConditionProposal(
                condition_type="field_present",
                parameters={},
                description="missing field param",
            )

    def test_event_within_window_requires_all_params(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            ConditionProposal(
                condition_type="event_within_window",
                parameters={"event_types": ["x"]},
                description="missing anchor/window",
            )

    def test_event_within_window_rejects_bad_unit(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            ConditionProposal(
                condition_type="event_within_window",
                parameters={
                    "event_types": ["x"],
                    "anchor_field": "closed_at",
                    "window_value": 7,
                    "window_unit": "fortnights",
                },
                description="bad unit",
            )

    def test_duplicate_norm_ids_rejected(self) -> None:
        clause1 = _clause_with_norm("CL-A", "SAME-ID")
        clause2 = _clause_with_norm("CL-B", "SAME-ID")
        with pytest.raises(Exception, match="globally unique"):
            _minimal_proposal(clauses=[clause1, clause2])

    def test_duplicate_clause_ids_rejected(self) -> None:
        clause1 = _clause_with_norm("SAME-CL", "N1")
        clause2 = _clause_with_norm("SAME-CL", "N2")
        with pytest.raises(Exception, match="unique"):
            _minimal_proposal(clauses=[clause1, clause2])

    def test_resolved_reference_requires_clause_id(self) -> None:
        with pytest.raises(Exception, match="resolved_clause_id"):
            ReferenceProposal(
                from_clause_id="CL-1",
                reference_type="clause",
                target="Section 2",
                resolved=True,
                resolved_clause_id=None,
            )

    def test_valid_proposal_passes(self) -> None:
        p = _minimal_proposal()
        assert p.contract_id == "TEST-CONTRACT"
        assert len(p.clauses) == 1


# ---------------------------------------------------------------------------
# M2: Condition lowering tests
# ---------------------------------------------------------------------------


class TestConditionLowering:
    def test_lower_field_present(self) -> None:
        proposal = _minimal_proposal(
            clauses=[
                _clause_with_norm(
                    condition_type="field_present",
                    condition_params={"field": "outcome_id"},
                )
            ]
        )
        air, _ = lower_to_agreement_ir(proposal, compilation_id="C1", version=1, source_hash="abc")
        norm = air.norms[0]
        assert norm.condition.operator == "present"
        assert norm.condition.operands[0].path == "claim.outcome_id"

    def test_lower_datetime_in_range(self) -> None:
        proposal = _minimal_proposal(
            clauses=[
                _clause_with_norm(
                    condition_type="datetime_in_range",
                    condition_params={
                        "field": "closed_at",
                        "start": "2026-06-01",
                        "end_exclusive": "2026-07-01",
                    },
                )
            ]
        )
        air, _ = lower_to_agreement_ir(proposal, compilation_id="C2", version=1, source_hash="abc")
        assert air.norms[0].condition.operator == "and"
        assert len(air.norms[0].condition.operands) == 2

    def test_lower_event_within_window(self) -> None:
        proposal = _minimal_proposal(
            clauses=[
                _clause_with_norm(
                    condition_type="event_within_window",
                    condition_params={
                        "event_types": ["customer_recontact"],
                        "anchor_field": "closed_at",
                        "window_value": 7,
                        "window_unit": "days",
                        "start_exclusive": True,
                        "compare_fields": [
                            {"event_field": "intent", "claim_field": "intent", "normalizer": "text"}
                        ],
                    },
                    norm_type="prohibition",
                )
            ]
        )
        air, _ = lower_to_agreement_ir(proposal, compilation_id="C3", version=1, source_hash="abc")
        norm = air.norms[0]
        assert norm.condition.operator == "exists_event"
        assert "dynamic_field_equals" in norm.condition.parameters
        assert norm.condition.parameters["window"]["anchor_path"] == "claim.closed_at"

    def test_lower_terminal_outcome(self) -> None:
        proposal = _minimal_proposal(
            clauses=[
                _clause_with_norm(
                    condition_type="terminal_outcome",
                    condition_params={
                        "success_types": ["downstream_succeeded"],
                        "failure_types": ["downstream_failed"],
                        "anchor_field": "closed_at",
                        "window_value": 2,
                        "window_unit": "hours",
                    },
                )
            ]
        )
        air, _ = lower_to_agreement_ir(proposal, compilation_id="C4", version=1, source_hash="abc")
        assert air.norms[0].condition.operator == "terminal_event_outcome"

    def test_lower_field_mismatch(self) -> None:
        proposal = _minimal_proposal(
            clauses=[
                _clause_with_norm(
                    condition_type="field_mismatch",
                    condition_params={
                        "event_type": "downstream_succeeded",
                        "comparisons": [
                            {"event_field": "account_id", "claim_field": "account_id"},
                            {"event_field": "action", "claim_field": "expected_action"},
                        ],
                    },
                    norm_type="prohibition",
                )
            ]
        )
        air, _ = lower_to_agreement_ir(proposal, compilation_id="C5", version=1, source_hash="abc")
        norm = air.norms[0]
        assert norm.condition.parameters["dynamic_field_match_mode"] == "any"
        assert len(norm.condition.parameters["dynamic_field_equals"]) == 2

    def test_lower_duplicate_in_window(self) -> None:
        proposal = _minimal_proposal(
            clauses=[
                _clause_with_norm(
                    condition_type="duplicate_in_window",
                    condition_params={
                        "group_by": ["customer_id", "intent"],
                        "order_by": ["closed_at"],
                        "window_value": 24,
                        "window_unit": "hours",
                        "normalizers": {"intent": "intent"},
                    },
                )
            ]
        )
        air, _ = lower_to_agreement_ir(proposal, compilation_id="C6", version=1, source_hash="abc")
        assert air.norms[0].condition.operator == "unique_by"

    def test_lower_amount_equals(self) -> None:
        proposal = _minimal_proposal(
            clauses=[
                _clause_with_norm(
                    condition_type="amount_equals",
                    condition_params={"field": "billed_amount", "expected_amount": "1.50"},
                )
            ]
        )
        air, _ = lower_to_agreement_ir(proposal, compilation_id="C7", version=1, source_hash="abc")
        assert air.norms[0].condition.operator == "equals"

    def test_lower_all_of(self) -> None:
        proposal = _minimal_proposal(
            clauses=[
                _clause_with_norm(
                    condition_type="all_of",
                    condition_params={
                        "conditions": [
                            {
                                "condition_type": "field_present",
                                "parameters": {"field": "outcome_id"},
                                "description": "a",
                            },
                            {
                                "condition_type": "event_exists",
                                "parameters": {"event_types": ["ai_closed"]},
                                "description": "b",
                            },
                        ]
                    },
                )
            ]
        )
        air, _ = lower_to_agreement_ir(proposal, compilation_id="C8", version=1, source_hash="abc")
        assert air.norms[0].condition.operator == "and"
        assert len(air.norms[0].condition.operands) == 2

    def test_lower_none_of(self) -> None:
        proposal = _minimal_proposal(
            clauses=[
                _clause_with_norm(
                    condition_type="none_of",
                    condition_params={
                        "conditions": [
                            {
                                "condition_type": "event_exists",
                                "parameters": {"event_types": ["spam"]},
                                "description": "no spam",
                            },
                        ]
                    },
                )
            ]
        )
        air, _ = lower_to_agreement_ir(proposal, compilation_id="C9", version=1, source_hash="abc")
        assert air.norms[0].condition.operator == "not"

    def test_lowered_air_passes_validation(self) -> None:
        proposal = _grounded_minimal_proposal()
        air, report = lower_to_agreement_ir(
            proposal, compilation_id="C10", version=1, source_hash="abc"
        )
        assert air.agreement_id == "C10"
        assert air.source_hash == "abc"
        assert len(air.clauses) == 1
        assert report is not None


# ---------------------------------------------------------------------------
# M3: Definitions and references
# ---------------------------------------------------------------------------


class TestDefinitionsAndReferences:
    def test_unresolved_definition_blocks_approval(self) -> None:
        clause = _clause_with_norm()
        clause = clause.model_copy(update={"defined_terms_used": ["Qualified Outcome"]})
        proposal = _minimal_proposal(clauses=[clause], definitions=[])
        air, _ = lower_to_agreement_ir(proposal, compilation_id="D1", version=1, source_hash="abc")
        blocking = [
            d
            for d in air.diagnostics
            if d.severity == "blocking" and d.code == "UNRESOLVED_DEFINITION"
        ]
        assert len(blocking) == 1
        assert "Qualified Outcome" in blocking[0].message

    def test_resolved_definition_does_not_block(self) -> None:
        clause = _clause_with_norm()
        clause = clause.model_copy(update={"defined_terms_used": ["Qualified Outcome"]})
        proposal = _minimal_proposal(
            clauses=[clause],
            definitions=[
                DefinitionProposal(
                    term="Qualified Outcome",
                    meaning="An outcome resolved by the AI agent",
                    source_clause_id="CL-DEF",
                    source_text='"Qualified Outcome" means...',
                )
            ],
        )
        air, _ = lower_to_agreement_ir(proposal, compilation_id="D2", version=1, source_hash="abc")
        blocking = [
            d
            for d in air.diagnostics
            if d.severity == "blocking" and d.code == "UNRESOLVED_DEFINITION"
        ]
        assert len(blocking) == 0

    def test_conflicting_definition_blocks(self) -> None:
        proposal = _minimal_proposal(
            definitions=[
                DefinitionProposal(
                    term="Outcome", meaning="A", source_clause_id="CL-1", source_text="A"
                ),
                DefinitionProposal(
                    term="Outcome", meaning="B", source_clause_id="CL-2", source_text="B"
                ),
            ]
        )
        air, _ = lower_to_agreement_ir(proposal, compilation_id="D3", version=1, source_hash="abc")
        blocking = [d for d in air.diagnostics if d.code == "CONFLICTING_DEFINITION"]
        assert len(blocking) == 1

    def test_unresolved_reference_blocks(self) -> None:
        clause = _clause_with_norm()
        clause = clause.model_copy(
            update={
                "references": [
                    ReferenceProposal(
                        from_clause_id="CL-NORM",
                        reference_type="exhibit",
                        target="Exhibit A",
                        resolved=False,
                    )
                ]
            }
        )
        proposal = _minimal_proposal(clauses=[clause])
        air, _ = lower_to_agreement_ir(proposal, compilation_id="D4", version=1, source_hash="abc")
        blocking = [d for d in air.diagnostics if d.code == "UNRESOLVED_REFERENCE"]
        assert len(blocking) == 1

    def test_non_material_unresolved_does_not_block(self) -> None:
        clause = _clause_with_norm()
        clause = clause.model_copy(
            update={
                "material": False,
                "defined_terms_used": ["Unknown Term"],
            }
        )
        proposal = _minimal_proposal(clauses=[clause])
        air, _ = lower_to_agreement_ir(proposal, compilation_id="D5", version=1, source_hash="abc")
        blocking = [d for d in air.diagnostics if d.severity == "blocking"]
        assert len(blocking) == 0

    def test_circular_reference_blocks(self) -> None:
        cl1 = _clause_with_norm("CL-A", "N1")
        cl1 = cl1.model_copy(
            update={
                "references": [
                    ReferenceProposal(
                        from_clause_id="CL-A",
                        reference_type="clause",
                        target="CL-B",
                        resolved=True,
                        resolved_clause_id="CL-B",
                    ),
                ]
            }
        )
        cl2 = _clause_with_norm("CL-B", "N2")
        cl2 = cl2.model_copy(
            update={
                "references": [
                    ReferenceProposal(
                        from_clause_id="CL-B",
                        reference_type="clause",
                        target="CL-A",
                        resolved=True,
                        resolved_clause_id="CL-A",
                    ),
                ]
            }
        )
        proposal = _minimal_proposal(clauses=[cl1, cl2])
        air, _ = lower_to_agreement_ir(proposal, compilation_id="D6", version=1, source_hash="abc")
        blocking = [d for d in air.diagnostics if d.code == "CIRCULAR_REFERENCE"]
        assert len(blocking) == 1


# ---------------------------------------------------------------------------
# M4: Settlement compilation
# ---------------------------------------------------------------------------


class TestSettlementCompilation:
    def test_fixed_per_unit(self) -> None:
        proposal = _grounded_minimal_proposal()
        air, _ = lower_to_agreement_ir(proposal, compilation_id="S1", version=1, source_hash="abc")
        assert len(air.settlement_policies) == 1
        sp = air.settlement_policies[0]
        assert sp.amount_expression.operator == "multiply"
        assert sp.source_clause_ids == ["NATIVE-CL-1"]

    def test_rate_table(self) -> None:
        clause = ClauseAnalysisProposal(
            clause_id="CL-RT",
            source_document_id="DOC-1",
            source_text="Rate table",
            clause_type="pricing",
            settlement_effects=[
                SettlementProposal(
                    id="S-RT",
                    settlement_type="rate_table",
                    parameters={
                        "lookup_field": "intent",
                        "rates": {"billing": "2.00", "refund": "1.50"},
                        "default": "1.00",
                    },
                    source_clause_id="CL-RT",
                    description="rate table",
                )
            ],
        )
        proposal = _minimal_proposal(clauses=[clause])
        air, _ = lower_to_agreement_ir(proposal, compilation_id="S2", version=1, source_hash="abc")
        sp = air.settlement_policies[0]
        assert sp.amount_expression.operator == "rate_table"
        assert sp.amount_expression.parameters["rates"]["billing"] == "2.00"

    def test_cap(self) -> None:
        clause = ClauseAnalysisProposal(
            clause_id="CL-CAP",
            source_document_id="DOC-1",
            source_text="Capped",
            clause_type="pricing",
            settlement_effects=[
                SettlementProposal(
                    id="S-CAP",
                    settlement_type="cap",
                    parameters={"maximum": "5.00"},
                    source_clause_id="CL-CAP",
                    description="cap at $5",
                )
            ],
        )
        proposal = _minimal_proposal(clauses=[clause])
        air, _ = lower_to_agreement_ir(proposal, compilation_id="S3", version=1, source_hash="abc")
        assert air.settlement_policies[0].amount_expression.operator == "cap"

    def test_floor(self) -> None:
        clause = ClauseAnalysisProposal(
            clause_id="CL-FL",
            source_document_id="DOC-1",
            source_text="Floor",
            clause_type="pricing",
            settlement_effects=[
                SettlementProposal(
                    id="S-FL",
                    settlement_type="floor",
                    parameters={"minimum": "0.50"},
                    source_clause_id="CL-FL",
                    description="floor at $0.50",
                )
            ],
        )
        proposal = _minimal_proposal(clauses=[clause])
        air, _ = lower_to_agreement_ir(proposal, compilation_id="S4", version=1, source_hash="abc")
        assert air.settlement_policies[0].amount_expression.operator == "floor"

    def test_percentage(self) -> None:
        clause = ClauseAnalysisProposal(
            clause_id="CL-PCT",
            source_document_id="DOC-1",
            source_text="10%",
            clause_type="pricing",
            settlement_effects=[
                SettlementProposal(
                    id="S-PCT",
                    settlement_type="percentage",
                    parameters={"percent": 10},
                    source_clause_id="CL-PCT",
                    description="10% of billed",
                )
            ],
        )
        proposal = _minimal_proposal(clauses=[clause])
        air, _ = lower_to_agreement_ir(proposal, compilation_id="S5", version=1, source_hash="abc")
        assert air.settlement_policies[0].amount_expression.operator == "multiply"

    def test_settlement_precise_clause_provenance(self) -> None:
        """Settlement policy must reference ONLY the pricing clause, not all clauses."""
        clauses = [
            ClauseAnalysisProposal(
                clause_id="CL-PERF",
                source_document_id="DOC-1",
                source_text="Performance clause",
                clause_type="performance",
                norms=[
                    NormProposal(
                        id="N-PERF",
                        norm_type="obligation",
                        subject="vendor",
                        condition=ConditionProposal(
                            condition_type="event_exists",
                            parameters={"event_types": ["ai_closed"]},
                            description="closure",
                        ),
                        consequence="disputed",
                    )
                ],
            ),
            ClauseAnalysisProposal(
                clause_id="CL-PRICE",
                source_document_id="DOC-1",
                source_text="$1.50 per outcome",
                clause_type="pricing",
                settlement_effects=[
                    SettlementProposal(
                        id="S-PRICE",
                        settlement_type="fixed_per_unit",
                        parameters={"unit_price": "1.50"},
                        source_clause_id="CL-PRICE",
                        description="pricing",
                    ),
                ],
            ),
        ]
        proposal = _minimal_proposal(clauses=clauses)
        air, _ = lower_to_agreement_ir(proposal, compilation_id="S6", version=1, source_hash="abc")
        sp = air.settlement_policies[0]
        assert sp.source_clause_ids == ["NATIVE-CL-PRICE"]
        assert "NATIVE-CL-PERF" not in sp.source_clause_ids

    def test_unsupported_material_clause_blocks(self) -> None:
        clause = ClauseAnalysisProposal(
            clause_id="CL-UNS",
            source_document_id="DOC-1",
            source_text="Ambiguous clause",
            material=True,
            clause_type="performance",
            automation_classification="unsupported",
            unsupported_concepts=["partial credit for human-assisted outcomes"],
        )
        proposal = _minimal_proposal(clauses=[clause])
        air, _ = lower_to_agreement_ir(proposal, compilation_id="S7", version=1, source_hash="abc")
        blocking = [d for d in air.diagnostics if d.code == "UNSUPPORTED_MATERIAL_CLAUSE"]
        assert len(blocking) == 1


# ---------------------------------------------------------------------------
# M5: AIR persistence
# ---------------------------------------------------------------------------


class TestAIRPersistence:
    """Test AIR version persistence using store functions."""

    def _make_contract(self, session):
        """Create a contract using the actual store functions."""
        from app.upload.store import create_contract, create_upload, ensure_pilot_state

        ensure_pilot_state(session)
        upload = create_upload(session, "contract", "test.txt", uploaded_by="operator")
        contract = create_contract(
            session,
            upload,
            customer="Test Co",
            vendor="Test Vendor",
            period_start=datetime(2026, 1, 1),
            period_end=datetime(2026, 12, 31),
            price_per_outcome=Decimal("1.50"),
            source_document="test.txt",
            source_text="Test contract text",
        )
        return contract

    def _make_compilation(self, session, contract_id: str, comp_id: str, version: int = 1):
        """Create a compilation row using the store's structure."""
        from app.upload.models import PilotRuleCompilationRow

        comp = PilotRuleCompilationRow(
            id=comp_id,
            contract_id=contract_id,
            source_document="test.txt",
            source_hash="h",
            prompt_hash="p",
            provider="test",
            model="test",
            compiler_version="1.0",
            status="approved",
            version=version,
            live_model_call=False,
            created_at=datetime(2026, 7, 1),
            rules=[],
            raw_response={},
        )
        session.add(comp)
        session.flush()
        return comp

    def test_persist_and_retrieve_air_version(self) -> None:
        from app.upload.pilot_db import PilotSessionLocal, initialize_pilot_database
        from app.upload.store import approve_air_version, get_approved_air, persist_air_version

        initialize_pilot_database()
        proposal = _grounded_minimal_proposal()
        comp_id = f"COMP-P1-{uuid4().hex}"
        air, _ = lower_to_agreement_ir(
            proposal, compilation_id=comp_id, version=1, source_hash="th"
        )

        with PilotSessionLocal.begin() as session:
            contract = self._make_contract(session)
            self._make_compilation(session, contract.id, comp_id)

            row = persist_air_version(
                session,
                contract_id=contract.id,
                compilation_id=comp_id,
                air=air,
                compiler_mode="native",
                source_hash="th",
            )
            assert row.version_number == 1
            assert row.approved_at is None

            approve_air_version(session, row.id)
            assert row.approved_at is not None

            loaded = get_approved_air(session, contract.id)
            assert loaded is not None
            assert loaded.agreement_id == comp_id

    def test_approved_air_is_immutable(self) -> None:
        from app.upload.pilot_db import PilotSessionLocal, initialize_pilot_database
        from app.upload.store import approve_air_version, persist_air_version

        initialize_pilot_database()
        proposal = _grounded_minimal_proposal()
        comp_id = f"COMP-IM-{uuid4().hex}"
        air, _ = lower_to_agreement_ir(
            proposal, compilation_id=comp_id, version=1, source_hash="th2"
        )

        with PilotSessionLocal.begin() as session:
            contract = self._make_contract(session)
            self._make_compilation(session, contract.id, comp_id)

            row = persist_air_version(
                session,
                contract_id=contract.id,
                compilation_id=comp_id,
                air=air,
                compiler_mode="native",
                source_hash="th2",
            )
            approve_air_version(session, row.id)
            with pytest.raises(ValueError, match="already approved"):
                approve_air_version(session, row.id)

    def test_recompilation_creates_new_version(self) -> None:
        from app.upload.pilot_db import PilotSessionLocal, initialize_pilot_database
        from app.upload.store import persist_air_version

        initialize_pilot_database()
        proposal = _minimal_proposal()
        comp1 = f"COMP-V1X-{uuid4().hex}"
        comp2 = f"COMP-V2X-{uuid4().hex}"
        air1, _ = lower_to_agreement_ir(
            proposal, compilation_id=comp1, version=1, source_hash="h3"
        )
        air2, _ = lower_to_agreement_ir(
            proposal, compilation_id=comp2, version=2, source_hash="h4"
        )

        with PilotSessionLocal.begin() as session:
            contract = self._make_contract(session)
            self._make_compilation(session, contract.id, comp1, version=1)
            self._make_compilation(session, contract.id, comp2, version=2)

            r1 = persist_air_version(
                session,
                contract_id=contract.id,
                compilation_id=comp1,
                air=air1,
                compiler_mode="native",
                source_hash="h3",
            )
            r2 = persist_air_version(
                session,
                contract_id=contract.id,
                compilation_id=comp2,
                air=air2,
                compiler_mode="native",
                source_hash="h4",
            )
            assert r2.version_number > r1.version_number


# ---------------------------------------------------------------------------
# Regression: demo results unchanged
# ---------------------------------------------------------------------------


def test_demo_financial_result_unchanged() -> None:
    """The existing demo must still produce exact expected results."""
    from app.contracts.compiler import recorded_rule_program
    from app.domain.engine import reconcile
    from app.fixtures.demo import demo_fixture

    records = demo_fixture()
    claim_evidence = [(r.claim, list(r.events)) for r in records]
    program = recorded_rule_program()
    results = reconcile(claim_evidence, program=program)

    payable = sum(d.confirmed_payable_amount for d in results)
    disputed = sum(d.confirmed_disputed_amount for d in results)
    review = sum(d.needs_review_amount for d in results)

    assert len(results) == 10000
    assert payable == Decimal("12480.00")
    assert disputed == Decimal("2520.00")
    assert review == Decimal("0.00")
