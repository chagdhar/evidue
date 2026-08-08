from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .models import EvidenceAuthority, ProofRequirement


class ProofPlanStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class EvidenceCapability(BaseModel):
    """Canonical evidence capability independent of connector/vendor name."""

    model_config = ConfigDict(extra="forbid")

    fact_type: str
    entity_type: str
    fields: list[str] = Field(default_factory=list)
    event_types: list[str] = Field(default_factory=list)
    state_transitions: list[str] = Field(default_factory=list)
    authority: EvidenceAuthority
    identity_keys: list[str] = Field(default_factory=list)
    timestamp_semantics: str = "event_time"
    source_timezone: str = "UTC"
    freshness_seconds: int | None = Field(default=None, ge=0)
    retention_days: int | None = Field(default=None, ge=0)
    historical_snapshots: bool = False
    absence_provable: bool = False
    completeness_guarantee: str = "unknown"
    parser_version: str | None = None


class EvidenceSourceDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_type: str
    system: str
    capabilities: list[EvidenceCapability]


class VerificationPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proof_requirement_id: str
    status: ProofPlanStatus
    selected_source_ids: list[str]
    missing_fact_types: list[str]
    missing_capabilities: list[str] = Field(default_factory=list)
    rationale: str


class VerificationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agreement_id: str
    items: list[VerificationPlanItem]

    @property
    def ready(self) -> bool:
        return all(item.status == ProofPlanStatus.READY for item in self.items)


def verification_readiness_summary(plan: VerificationPlan) -> dict[str, object]:
    """Return a finance-friendly summary of whether the approved contract is verifiable.

    This is derived entirely from the deterministic verification plan.  It is
    intended to answer a practical question before reconciliation: which
    contractual checks can Evidue actually prove with the evidence sources the
    workspace has supplied?
    """

    total = len(plan.items)
    ready = [item for item in plan.items if item.status == ProofPlanStatus.READY]
    partial = [item for item in plan.items if item.status == ProofPlanStatus.PARTIAL]
    unavailable = [item for item in plan.items if item.status == ProofPlanStatus.UNAVAILABLE]
    readiness_percent = 100.0 if total == 0 else round(len(ready) / total * 100, 1)
    missing_fact_types = sorted(
        {fact_type for item in plan.items for fact_type in item.missing_fact_types}
    )
    missing_capabilities = sorted(
        {capability for item in plan.items for capability in item.missing_capabilities}
    )
    blocking = [
        {
            "proof_requirement_id": item.proof_requirement_id,
            "status": item.status.value,
            "missing_fact_types": list(item.missing_fact_types),
            "missing_capabilities": list(item.missing_capabilities),
            "rationale": item.rationale,
        }
        for item in plan.items
        if item.status != ProofPlanStatus.READY
    ]
    if total == 0:
        status = "no_external_evidence_required"
    elif not unavailable and not partial:
        status = "ready"
    elif ready or partial:
        status = "partial"
    else:
        status = "blocked"
    return {
        "status": status,
        "ready_for_full_verification": plan.ready,
        "readiness_percent": readiness_percent,
        "requirements": {
            "total": total,
            "ready": len(ready),
            "partial": len(partial),
            "unavailable": len(unavailable),
        },
        "missing_fact_types": missing_fact_types,
        "missing_capabilities": missing_capabilities,
        "blocking_requirements": blocking,
    }


def _capability_matches(requirement: ProofRequirement, capability: EvidenceCapability) -> list[str]:
    missing: list[str] = []
    if (
        requirement.required_entity_type
        and capability.entity_type != requirement.required_entity_type
    ):
        missing.append(f"entity_type:{requirement.required_entity_type}")
    if requirement.required_fields and not set(requirement.required_fields).issubset(
        capability.fields
    ):
        missing.append("required_fields")
    if requirement.identity_keys and not (
        set(requirement.identity_keys) & set(capability.identity_keys)
    ):
        missing.append("identity_keys")
    if requirement.requires_absence_proof and not capability.absence_provable:
        missing.append("absence_proof")
    if capability.authority not in requirement.acceptable_authorities:
        missing.append("authority")
    return missing


def build_verification_plan(
    agreement_id: str,
    requirements: list[ProofRequirement],
    sources: list[EvidenceSourceDescriptor],
) -> VerificationPlan:
    items: list[VerificationPlanItem] = []
    for requirement in requirements:
        selected: set[str] = set()
        missing_fact_types: list[str] = []
        missing_capabilities: set[str] = set()
        for fact_type in requirement.acceptable_fact_types:
            matches: list[tuple[EvidenceSourceDescriptor, EvidenceCapability]] = []
            for source in sources:
                for capability in source.capabilities:
                    if capability.fact_type != fact_type:
                        continue
                    gaps = _capability_matches(requirement, capability)
                    if gaps:
                        missing_capabilities.update(gaps)
                        continue
                    matches.append((source, capability))
            if not matches:
                missing_fact_types.append(fact_type)
            else:
                matches.sort(
                    key=lambda match: (
                        match[1].authority != requirement.preferred_authority,
                        match[0].source_id,
                    )
                )
                selected.add(matches[0][0].source_id)
        if not missing_fact_types:
            status = ProofPlanStatus.READY
            rationale = "Every required fact type has a capability-complete evidence source."
        elif selected:
            status = ProofPlanStatus.PARTIAL
            rationale = "Some required fact types or evidence capabilities are unavailable."
        else:
            status = ProofPlanStatus.UNAVAILABLE
            rationale = "No acceptable evidence source can satisfy this proof requirement."
        items.append(
            VerificationPlanItem(
                proof_requirement_id=requirement.id,
                status=status,
                selected_source_ids=sorted(selected),
                missing_fact_types=missing_fact_types,
                missing_capabilities=sorted(missing_capabilities),
                rationale=rationale,
            )
        )
    return VerificationPlan(agreement_id=agreement_id, items=items)
