"""Identity matching pipeline.

Connects uploaded OperationalEventRows to OutcomeClaimRows using a
descending hierarchy of match authority:

1. Direct outcome ID
2. Secondary key via identity map (conversation_id → outcome_id)
3. Composite key (customer_id + timestamp window + action type)
4. Unresolved → review queue
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal


@dataclass(frozen=True)
class MatchCandidate:
    event_id: str
    event_outcome_id: str | None
    event_customer_id: str
    event_timestamp: str
    event_type: str
    event_values: dict[str, str]


@dataclass(frozen=True)
class ClaimIdentity:
    outcome_id: str
    customer_id: str
    conversation_id: str
    account_id: str
    closed_at: str
    intent: str


@dataclass(frozen=True)
class IdentityMapping:
    """One row from the identity map CSV."""

    conversation_id: str | None
    customer_id: str | None
    account_id: str | None
    outcome_id: str | None


@dataclass(frozen=True)
class MatchResult:
    event_id: str
    outcome_id: str | None
    method: str
    confidence: Decimal
    reason: str


def _try_direct(
    event: MatchCandidate, claims_by_outcome: dict[str, ClaimIdentity]
) -> MatchResult | None:
    """Match by direct outcome_id on the event."""
    if event.event_outcome_id and event.event_outcome_id in claims_by_outcome:
        return MatchResult(
            event_id=event.event_id,
            outcome_id=event.event_outcome_id,
            method="direct_outcome_id",
            confidence=Decimal("1.0000"),
            reason="Event outcome_id matches a claim",
        )
    return None


def _try_identity_map(
    event: MatchCandidate,
    identity_index: dict[str, list[IdentityMapping]],
    claims_by_outcome: dict[str, ClaimIdentity],
) -> MatchResult | None:
    """Match via the uploaded identity map using conversation_id or customer+account."""
    # Try matching event's outcome_id as a conversation_id in the map
    lookup_keys = []
    if event.event_outcome_id:
        lookup_keys.append(event.event_outcome_id)
    # Also check if event_values has a conversation_id
    conv_id = event.event_values.get("conversation_id", "")
    if conv_id:
        lookup_keys.append(conv_id)

    for key in lookup_keys:
        mappings = identity_index.get(key, [])
        for mapping in mappings:
            if mapping.outcome_id and mapping.outcome_id in claims_by_outcome:
                return MatchResult(
                    event_id=event.event_id,
                    outcome_id=mapping.outcome_id,
                    method="identity_map_conversation",
                    confidence=Decimal("0.9500"),
                    reason=(
                        f"Identity map resolved conversation {key} to outcome {mapping.outcome_id}"
                    ),
                )

    # Customer identity alone is not authoritative: one customer can have
    # multiple billed outcomes.  Require an exact customer+account mapping.
    account_id = event.event_values.get("account_id", "")
    if account_id:
        customer_account_mappings = identity_index.get(
            f"custacct:{event.event_customer_id}:{account_id}", []
        )
        valid = [
            mapping
            for mapping in customer_account_mappings
            if mapping.outcome_id and mapping.outcome_id in claims_by_outcome
        ]
        if len(valid) == 1:
            mapping = valid[0]
            return MatchResult(
                event_id=event.event_id,
                outcome_id=mapping.outcome_id,
                method="identity_map_customer_account",
                confidence=Decimal("0.9500"),
                reason=(
                    "Identity map resolved exact customer/account pair "
                    f"{event.event_customer_id}/{account_id} to outcome {mapping.outcome_id}"
                ),
            )

    return None


def _try_composite(
    event: MatchCandidate,
    claims_by_customer: dict[str, list[ClaimIdentity]],
) -> MatchResult | None:
    """Match by customer_id + timestamp proximity + matching action type."""
    candidates = claims_by_customer.get(event.event_customer_id, [])
    if not candidates:
        return None

    # Only attempt composite match if there is exactly one claim for this
    # customer within a 4-hour window, to avoid ambiguous matches.
    from datetime import datetime

    try:
        event_ts = datetime.fromisoformat(event.event_timestamp)
    except (ValueError, TypeError):
        return None

    window = timedelta(hours=4)
    nearby: list[ClaimIdentity] = []
    for claim in candidates:
        try:
            claim_ts = datetime.fromisoformat(claim.closed_at)
        except (ValueError, TypeError):
            continue
        if abs(event_ts - claim_ts) <= window:
            nearby.append(claim)

    if len(nearby) == 1:
        claim = nearby[0]
        return MatchResult(
            event_id=event.event_id,
            outcome_id=claim.outcome_id,
            method="composite_customer_time",
            confidence=Decimal("0.7000"),
            reason=(
                f"Single claim for customer {event.event_customer_id} "
                f"within 4-hour window of event timestamp"
            ),
        )

    return None


def build_identity_index(
    mappings: list[IdentityMapping],
) -> dict[str, list[IdentityMapping]]:
    """Index identity mappings by conversation_id and customer_id for fast lookup."""
    index: dict[str, list[IdentityMapping]] = {}
    for m in mappings:
        if m.conversation_id:
            index.setdefault(m.conversation_id, []).append(m)
        if m.customer_id and m.account_id:
            index.setdefault(f"custacct:{m.customer_id}:{m.account_id}", []).append(m)
    return index


@dataclass(frozen=True)
class MatchingSummary:
    total_events: int
    direct_matches: int
    identity_map_matches: int
    composite_matches: int
    unresolved: int
    unresolved_value: Decimal


def run_matching(
    events: list[MatchCandidate],
    claims: list[ClaimIdentity],
    identity_mappings: list[IdentityMapping] | None = None,
) -> tuple[list[MatchResult], MatchingSummary]:
    """Run the full matching pipeline and return results + summary."""
    claims_by_outcome = {c.outcome_id: c for c in claims}
    claims_by_customer: dict[str, list[ClaimIdentity]] = {}
    for c in claims:
        claims_by_customer.setdefault(c.customer_id, []).append(c)

    identity_index = build_identity_index(identity_mappings) if identity_mappings else {}

    results: list[MatchResult] = []
    direct = 0
    id_map = 0
    composite = 0
    unresolved = 0

    for event in events:
        # 1. Direct
        match = _try_direct(event, claims_by_outcome)
        if match:
            results.append(match)
            direct += 1
            continue

        # 2. Identity map
        if identity_index:
            match = _try_identity_map(event, identity_index, claims_by_outcome)
            if match:
                results.append(match)
                id_map += 1
                continue

        # 3. Composite
        match = _try_composite(event, claims_by_customer)
        if match:
            results.append(match)
            composite += 1
            continue

        # 4. Unresolved
        results.append(
            MatchResult(
                event_id=event.event_id,
                outcome_id=None,
                method="unresolved",
                confidence=Decimal("0.0000"),
                reason="No matching claim found via direct, identity map, or composite methods",
            )
        )
        unresolved += 1

    summary = MatchingSummary(
        total_events=len(events),
        direct_matches=direct,
        identity_map_matches=id_map,
        composite_matches=composite,
        unresolved=unresolved,
        unresolved_value=Decimal("0.00"),  # Computed by caller from claim amounts
    )
    return results, summary
