from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

PRICE = Decimal("1.50")
@dataclass(frozen=True)
class OperationalEvent:
    id: str; source_system: str; source_record_id: str; event_type: str; timestamp: datetime; customer_id: str; outcome_id: str | None; values: dict[str, str]; ingested_at: datetime
@dataclass(frozen=True)
class OutcomeClaim:
    outcome_id: str; customer_id: str; intent: str; claimed_resolved: bool; closed_at: datetime; expected_action: str; account_id: str; billed_amount: Decimal = PRICE
@dataclass(frozen=True)
class EvidenceReference:
    event_id: str; purpose: str
@dataclass(frozen=True)
class OutcomeDetermination:
    claim: OutcomeClaim; status: str; reason: str; rule_id: str | None; evidence: tuple[EvidenceReference, ...]; payable_amount: Decimal; evaluated_at: datetime; engine_version: str = "2026.06.1"
@dataclass(frozen=True)
class ContractRule:
    id: str; title: str; description: str
RULES = (ContractRule("R1", "No same-intent recontact", "No same-intent customer contact within seven calendar days."), ContractRule("R2", "No human completion", "No human completion or material correction within 24 hours."), ContractRule("R3", "Downstream action succeeds", "Promised action succeeds within two hours."), ContractRule("R4", "Single attribution", "Only one billable outcome per customer and intent in 24 hours."), ContractRule("R5", "Account and action match", "Evidence matches expected account and action."), ContractRule("R6", "Billing period", "Outcome closes in the billing period."), ContractRule("R7", "Sufficient identifiers", "Claim identifiers associate operational evidence."))
