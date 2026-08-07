"""Deterministic fact derivation from normalized evidence and approved AIR."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from .models import AgreementIR, CommercialClaim, Fact, TruthValue
from .runtime import EvaluationContext, evaluate_expression, truth_value

FACT_DERIVER_VERSION = "facts-v2"


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + sha256(encoded).hexdigest()


def derive_facts(
    agreement: AgreementIR,
    claim: CommercialClaim,
    events: list[dict[str, Any]],
) -> list[Fact]:
    """Derive one deterministic fact per proof requirement.

    Each proof requirement resolves through its persisted atomic predicate.
    Legacy AIR payloads without first-class predicates fall back to the norm
    condition only for backwards compatibility. Semantic or human-attested
    requirements remain UNKNOWN until a dedicated evaluator/reviewer supplies
    them.
    """

    norm_by_id = {norm.id: norm for norm in agreement.norms}
    predicate_by_id = {predicate.id: predicate for predicate in agreement.predicates}
    fields = {"claim": {"id": claim.id, **claim.fields, "submitted_amount": claim.submitted_amount}}
    context = EvaluationContext(fields=fields, events=tuple(events))
    facts: list[Fact] = []
    for requirement in agreement.proof_requirements:
        norm = norm_by_id.get(requirement.norm_id)
        if norm is None:
            continue
        predicate = predicate_by_id.get(requirement.predicate_id)
        automation_class = predicate.automation_class if predicate is not None else norm.automation_class
        if automation_class.value in {"model_assisted", "human_attestation_required"}:
            result_truth = TruthValue.UNKNOWN
            evidence_ids: list[str] = []
        else:
            expression = predicate.expression if predicate is not None else norm.condition
            result = evaluate_expression(expression, context)
            result_truth = truth_value(result)
            evidence_ids = list(dict.fromkeys(result.evidence_ids))
        fact_type = requirement.acceptable_fact_types[0]
        payload = {
            "agreement_id": agreement.agreement_id,
            "claim_id": claim.id,
            "requirement_id": requirement.id,
            "predicate_id": requirement.predicate_id,
            "predicate_hash": predicate.canonical_hash if predicate is not None else None,
            "truth": result_truth.value,
            "evidence_ids": evidence_ids,
        }
        facts.append(
            Fact(
                id=f"FACT-{claim.id}-{requirement.id}",
                fact_type=fact_type,
                predicate_id=requirement.predicate_id,
                truth=result_truth,
                evidence_ids=evidence_ids,
                authority=requirement.preferred_authority,
                input_hash=_canonical_hash(payload),
                evaluator_version=FACT_DERIVER_VERSION,
            )
        )
    return facts
