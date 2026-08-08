"""Canonical Agreement IR semantic snapshots and diffs.

These helpers intentionally remove generated IDs and model prose so product
impact analysis and compiler qualification compare contractual meaning rather
than incidental output wording.
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from .models import AgreementIR


def semantic_snapshot(agreement: AgreementIR) -> dict[str, Any]:
    """Canonical material semantics, excluding model prose and generated IDs."""

    proof_by_norm: dict[str, list[dict[str, Any]]] = {}
    for proof in agreement.proof_requirements:
        proof_by_norm.setdefault(proof.norm_id, []).append(
            {
                "fact_types": sorted(proof.acceptable_fact_types),
                "preferred_authority": proof.preferred_authority.value,
                "acceptable_authorities": sorted(
                    item.value for item in proof.acceptable_authorities
                ),
                "identity_keys": sorted(proof.identity_keys),
                "required_fields": sorted(proof.required_fields),
                "observation_window": proof.observation_window,
                "requires_absence_proof": proof.requires_absence_proof,
            }
        )

    rules = []
    for norm in agreement.norms:
        rules.append(
            {
                "norm_type": norm.norm_type.value,
                "subject": norm.subject,
                "beneficiary": norm.beneficiary,
                "condition": norm.condition.model_dump(mode="json"),
                "exceptions": [item.model_dump(mode="json") for item in norm.exceptions],
                "consequence": norm.consequence,
                "automation_class": norm.automation_class.value,
                "indeterminate_consequence": norm.indeterminate_consequence,
                "proofs": sorted(
                    proof_by_norm.get(norm.id, []),
                    key=lambda item: json.dumps(item, sort_keys=True),
                ),
            }
        )

    pricing = [
        {
            "claim_type": policy.claim_type,
            "amount_expression": policy.amount_expression.model_dump(mode="json"),
            "currency": policy.currency,
        }
        for policy in agreement.settlement_policies
    ]
    coverage = [
        {
            "classification": item.classification.value,
            "material": item.material,
        }
        for item in agreement.coverage
    ]
    rules.sort(key=lambda item: json.dumps(item, sort_keys=True))
    pricing.sort(key=lambda item: json.dumps(item, sort_keys=True))
    coverage.sort(key=lambda item: json.dumps(item, sort_keys=True))
    evidence = sorted(
        [proof for values in proof_by_norm.values() for proof in values],
        key=lambda item: json.dumps(item, sort_keys=True),
    )
    return {"rules": rules, "pricing": pricing, "evidence": evidence, "coverage": coverage}


def semantic_fingerprint(agreement: AgreementIR) -> str:
    normalized = semantic_snapshot(agreement)
    return (
        "sha256:"
        + sha256(
            json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )


def semantic_delta(before: AgreementIR, after: AgreementIR) -> dict[str, Any]:
    left = semantic_snapshot(before)
    right = semantic_snapshot(after)
    sections = ("rules", "pricing", "evidence", "coverage")
    changed = [section for section in sections if left[section] != right[section]]
    return {
        "changed_sections": changed,
        "unchanged_sections": [section for section in sections if section not in changed],
        "before_fingerprint": semantic_fingerprint(before),
        "after_fingerprint": semantic_fingerprint(after),
    }
