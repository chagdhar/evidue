"""Deterministic financial impact analysis between Agreement IR versions.

This module is deliberately LLM-free. It replays the same normalized claims and
evidence through two immutable Agreement IR versions and reports only the
financial/semantic differences caused by the policy change. The result is a
simulation; it never replaces the currently approved AIR as financial authority.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain.models import OperationalEvent, OutcomeClaim, OutcomeDetermination

from .adjudication import reconcile_agreement
from .models import AgreementIR
from .semantics import semantic_delta

ZERO = Decimal(0)


def _money(value: Decimal) -> str:
    return format(value, "f")


def _totals(results: list[OutcomeDetermination]) -> dict[str, Any]:
    billed = sum((item.claim.billed_amount for item in results), ZERO)
    payable = sum((item.confirmed_payable_amount for item in results), ZERO)
    disputed = sum((item.confirmed_disputed_amount for item in results), ZERO)
    needs_review = sum((item.needs_review_amount for item in results), ZERO)
    conservation_delta = billed - payable - disputed - needs_review
    return {
        "lines": len(results),
        "billed": _money(billed),
        "payable": _money(payable),
        "disputed": _money(disputed),
        "needs_review": _money(needs_review),
        "conservation_delta": _money(conservation_delta),
        "conservation_passed": conservation_delta == ZERO,
        "status_counts": {
            "payable": sum(item.status == "payable" for item in results),
            "disputed": sum(item.status == "disputed" for item in results),
            "needs_review": sum(item.status == "needs_review" for item in results),
        },
    }


def _amount_delta(after: str, before: str) -> str:
    return _money(Decimal(after) - Decimal(before))


def compare_reconciliation_results(
    baseline: list[OutcomeDetermination],
    candidate: list[OutcomeDetermination],
) -> dict[str, Any]:
    """Compare two deterministic reconciliations over the same claim set."""

    baseline_by_id = {item.claim.outcome_id: item for item in baseline}
    candidate_by_id = {item.claim.outcome_id: item for item in candidate}
    if baseline_by_id.keys() != candidate_by_id.keys():
        missing_candidate = sorted(baseline_by_id.keys() - candidate_by_id.keys())
        missing_baseline = sorted(candidate_by_id.keys() - baseline_by_id.keys())
        raise ValueError(
            "Financial impact requires identical claim sets; "
            f"missing_from_candidate={missing_candidate}, missing_from_baseline={missing_baseline}"
        )

    baseline_totals = _totals(baseline)
    candidate_totals = _totals(candidate)
    if not baseline_totals["conservation_passed"] or not candidate_totals["conservation_passed"]:
        raise ValueError(
            "Financial impact cannot compare a reconciliation that violates conservation"
        )

    changed_lines: list[dict[str, Any]] = []
    for outcome_id in sorted(baseline_by_id):
        before = baseline_by_id[outcome_id]
        after = candidate_by_id[outcome_id]
        changed = (
            before.status != after.status
            or before.confirmed_payable_amount != after.confirmed_payable_amount
            or before.confirmed_disputed_amount != after.confirmed_disputed_amount
            or before.needs_review_amount != after.needs_review_amount
            or before.rule_id != after.rule_id
        )
        if not changed:
            continue
        changed_lines.append(
            {
                "outcome_id": outcome_id,
                "billed_amount": _money(before.claim.billed_amount),
                "before": {
                    "status": before.status,
                    "rule_id": before.rule_id,
                    "payable": _money(before.confirmed_payable_amount),
                    "disputed": _money(before.confirmed_disputed_amount),
                    "needs_review": _money(before.needs_review_amount),
                },
                "after": {
                    "status": after.status,
                    "rule_id": after.rule_id,
                    "payable": _money(after.confirmed_payable_amount),
                    "disputed": _money(after.confirmed_disputed_amount),
                    "needs_review": _money(after.needs_review_amount),
                },
                "delta": {
                    "payable": _money(
                        after.confirmed_payable_amount - before.confirmed_payable_amount
                    ),
                    "disputed": _money(
                        after.confirmed_disputed_amount - before.confirmed_disputed_amount
                    ),
                    "needs_review": _money(after.needs_review_amount - before.needs_review_amount),
                },
            }
        )

    return {
        "baseline": baseline_totals,
        "candidate": candidate_totals,
        "delta": {
            "payable": _amount_delta(candidate_totals["payable"], baseline_totals["payable"]),
            "disputed": _amount_delta(candidate_totals["disputed"], baseline_totals["disputed"]),
            "needs_review": _amount_delta(
                candidate_totals["needs_review"], baseline_totals["needs_review"]
            ),
        },
        "affected_line_count": len(changed_lines),
        "affected_lines": changed_lines,
    }


def simulate_agreement_financial_impact(
    claim_evidence: list[tuple[OutcomeClaim, list[OperationalEvent]]],
    baseline_air: AgreementIR,
    candidate_air: AgreementIR,
) -> dict[str, Any]:
    """Replay one invoice/evidence set across two AIR versions.

    The function has no persistence and no provider access. It is safe to use
    before candidate AIR approval because the return value is explicitly a
    simulation, never a financial determination.
    """

    baseline_results = reconcile_agreement(claim_evidence, baseline_air)
    candidate_results = reconcile_agreement(claim_evidence, candidate_air)
    financial = compare_reconciliation_results(baseline_results, candidate_results)
    return {
        "version": "air-financial-impact-1",
        "simulation_only": True,
        "financial_authority_changed": False,
        "semantic_delta": semantic_delta(baseline_air, candidate_air),
        "financial": financial,
    }
