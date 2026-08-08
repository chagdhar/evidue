from app.agreements.capabilities import (
    ProofPlanStatus,
    VerificationPlan,
    VerificationPlanItem,
    verification_readiness_summary,
)


def _item(identifier: str, status: ProofPlanStatus) -> VerificationPlanItem:
    missing = [] if status == ProofPlanStatus.READY else [f"fact.{identifier}"]
    return VerificationPlanItem(
        proof_requirement_id=identifier,
        status=status,
        selected_source_ids=["SRC-1"] if status != ProofPlanStatus.UNAVAILABLE else [],
        missing_fact_types=missing,
        missing_capabilities=["absence_proof"] if status != ProofPlanStatus.READY else [],
        rationale="test",
    )


def test_readiness_summary_exposes_verification_gaps() -> None:
    plan = VerificationPlan(
        agreement_id="AGR-1",
        items=[
            _item("P1", ProofPlanStatus.READY),
            _item("P2", ProofPlanStatus.PARTIAL),
            _item("P3", ProofPlanStatus.UNAVAILABLE),
        ],
    )
    summary = verification_readiness_summary(plan)
    assert summary["status"] == "partial"
    assert summary["ready_for_full_verification"] is False
    assert summary["readiness_percent"] == 33.3
    assert summary["requirements"] == {
        "total": 3,
        "ready": 1,
        "partial": 1,
        "unavailable": 1,
    }
    assert summary["missing_fact_types"] == ["fact.P2", "fact.P3"]
    assert summary["missing_capabilities"] == ["absence_proof"]
    assert len(summary["blocking_requirements"]) == 2


def test_empty_plan_is_not_falsely_blocked() -> None:
    summary = verification_readiness_summary(VerificationPlan(agreement_id="AGR-1", items=[]))
    assert summary["status"] == "no_external_evidence_required"
    assert summary["ready_for_full_verification"] is True
    assert summary["readiness_percent"] == 100.0
