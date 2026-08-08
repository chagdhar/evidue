"""Deterministic financial decision trace graph.

This module never calls an LLM.  It turns an already-approved AgreementIR plus
one persisted reconciliation decision into a machine-traversable explanation
from financial amount back to rule, source clause, proof requirement, and
evidence event.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .models import AgreementIR, Norm, SettlementPolicy


def _money(value: Decimal | str) -> str:
    return format(Decimal(str(value)), "f")


def _rule_for_id(
    agreement: AgreementIR,
    rule_id: str | None,
) -> tuple[str, Norm | SettlementPolicy] | None:
    if not rule_id:
        return None
    for norm in agreement.norms:
        aliases = {norm.id, norm.violation_reason_code, norm.indeterminate_rule_id}
        if rule_id in {item for item in aliases if item}:
            return "norm", norm
    for policy in agreement.settlement_policies:
        if policy.id == rule_id:
            return "settlement_policy", policy
    return None


def build_decision_trace(
    agreement: AgreementIR | None,
    *,
    outcome_id: str,
    status: str,
    rule_id: str | None,
    billed_amount: Decimal | str,
    payable_amount: Decimal | str,
    disputed_amount: Decimal | str,
    needs_review_amount: Decimal | str,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a deterministic provenance graph for one financial decision.

    The graph is intentionally composed only from persisted product state.  It
    does not invent causal links or generate explanatory prose with an LLM.
    """

    evidence = evidence or []
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []

    claim_node = f"claim:{outcome_id}"
    decision_node = f"decision:{outcome_id}"
    nodes.append(
        {
            "id": claim_node,
            "type": "invoice_claim",
            "outcome_id": outcome_id,
            "billed_amount": _money(billed_amount),
        }
    )
    nodes.append(
        {
            "id": decision_node,
            "type": "financial_decision",
            "status": status,
            "payable_amount": _money(payable_amount),
            "disputed_amount": _money(disputed_amount),
            "needs_review_amount": _money(needs_review_amount),
        }
    )
    edges.append({"source": decision_node, "target": claim_node, "relation": "decides_claim"})

    contractual_rule_found = False
    source_clause_count = 0
    proof_requirement_count = 0

    resolved = _rule_for_id(agreement, rule_id) if agreement is not None else None
    if resolved is not None:
        rule_type, rule = resolved
        contractual_rule_found = True
        rule_node = f"rule:{rule.id}"
        nodes.append(
            {
                "id": rule_node,
                "type": rule_type,
                "rule_id": rule.id,
                "source_clause_ids": list(rule.source_clause_ids),
            }
        )
        edges.append({"source": decision_node, "target": rule_node, "relation": "determined_by"})

        clause_by_id = {item.id: item for item in agreement.clauses}
        for clause_id in rule.source_clause_ids:
            clause = clause_by_id.get(clause_id)
            if clause is None:
                continue
            source_clause_count += 1
            clause_node = f"clause:{clause.id}"
            nodes.append(
                {
                    "id": clause_node,
                    "type": "contract_source",
                    "clause_id": clause.id,
                    "document_id": clause.document_id,
                    "text": clause.text,
                    "source_start": clause.source_start,
                    "source_end": clause.source_end,
                    "text_hash": clause.text_hash,
                }
            )
            edges.append({"source": rule_node, "target": clause_node, "relation": "grounded_in"})

        if rule_type == "norm":
            requirements = [
                item for item in agreement.proof_requirements if item.norm_id == rule.id
            ]
            for requirement in requirements:
                proof_requirement_count += 1
                proof_node = f"proof:{requirement.id}"
                nodes.append(
                    {
                        "id": proof_node,
                        "type": "proof_requirement",
                        "proof_requirement_id": requirement.id,
                        "acceptable_fact_types": list(requirement.acceptable_fact_types),
                        "preferred_authority": requirement.preferred_authority.value,
                        "requires_absence_proof": requirement.requires_absence_proof,
                    }
                )
                edges.append(
                    {"source": rule_node, "target": proof_node, "relation": "requires_proof"}
                )

    for item in evidence:
        event_id = str(item.get("event_id") or item.get("id") or "")
        if not event_id:
            continue
        evidence_node = f"evidence:{event_id}"
        nodes.append(
            {
                "id": evidence_node,
                "type": "evidence_event",
                "event_id": event_id,
                "source_system": item.get("source_system"),
                "source_record_id": item.get("source_record_id"),
                "event_type": item.get("event_type"),
                "timestamp": item.get("timestamp"),
                "purpose": item.get("purpose"),
                "match_method": item.get("match_method"),
                "match_confidence": item.get("match_confidence"),
            }
        )
        edges.append({"source": decision_node, "target": evidence_node, "relation": "supported_by"})

    financial_amount = {
        "payable": _money(payable_amount),
        "disputed": _money(disputed_amount),
        "needs_review": _money(needs_review_amount),
    }.get(status, "0")

    # A disputed dollar must always be traceable to an approved contractual rule
    # and at least one immutable source clause.  Evidence may legitimately be
    # absent for contract-only failures such as a wrong billed rate.
    complete = True
    gaps: list[str] = []
    if status == "disputed":
        if not contractual_rule_found:
            complete = False
            gaps.append("approved_rule")
        if source_clause_count == 0:
            complete = False
            gaps.append("contract_source")
    elif status == "needs_review" and rule_id and not contractual_rule_found:
        complete = False
        gaps.append("approved_rule")

    return {
        "version": "decision-trace-1",
        "outcome_id": outcome_id,
        "status": status,
        "financial_amount": financial_amount,
        "complete": complete,
        "gaps": gaps,
        "summary": {
            "contractual_rule_found": contractual_rule_found,
            "source_clause_count": source_clause_count,
            "proof_requirement_count": proof_requirement_count,
            "evidence_event_count": len(evidence),
        },
        "nodes": nodes,
        "edges": edges,
    }
