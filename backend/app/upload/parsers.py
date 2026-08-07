"""Parse uploaded CSV, JSON, and JSONL files into normalized row dicts.

Each parser returns (accepted_rows, rejected_rows) where rejected_rows
carry the row number, reason, and raw data for operator review.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True)
class ParsedRow:
    row_number: int
    data: dict[str, Any]


@dataclass(frozen=True)
class RejectedRow:
    row_number: int
    reason: str
    raw_data: dict[str, Any]


@dataclass(frozen=True)
class ParseResult:
    accepted: list[ParsedRow]
    rejected: list[RejectedRow]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TIMESTAMP_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
]


def _parse_timestamp(value: str) -> datetime:
    value = value.strip()

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        parsed = None

    if parsed is None:
        for fmt in _TIMESTAMP_FORMATS:
            try:
                parsed = datetime.strptime(value, fmt).replace(tzinfo=UTC)
                break
            except ValueError:
                continue

    if parsed is None:
        raise ValueError(f"Invalid timestamp: {value}")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC).replace(tzinfo=None)


def _parse_decimal(value: str) -> Decimal | None:
    cleaned = value.strip().replace(",", "")
    if cleaned.startswith("$"):
        cleaned = cleaned[1:].strip()
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _payload_hash(raw: dict[str, Any]) -> str:
    serialized = json.dumps(raw, sort_keys=True, default=str)
    return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()}"


def _normalize_key(key: str) -> str:
    """Lowercase and replace common separators so column name matching
    is flexible: 'Outcome ID', 'outcome-id', 'OUTCOME_ID' all become
    'outcome_id'."""
    return key.strip().lower().replace(" ", "_").replace("-", "_")


def _build_column_map(headers: list[str], aliases: dict[str, list[str]]) -> dict[str, str | None]:
    """Map canonical field names to the actual CSV column headers.

    *aliases* maps canonical name → list of acceptable column names.
    Returns canonical → actual header (or None if not found).
    """
    normalized = {_normalize_key(h): h for h in headers}
    result: dict[str, str | None] = {}
    for canonical, options in aliases.items():
        matched = None
        for option in options:
            key = _normalize_key(option)
            if key in normalized:
                matched = normalized[key]
                break
        result[canonical] = matched
    return result


# ---------------------------------------------------------------------------
# Invoice CSV parser
# ---------------------------------------------------------------------------

INVOICE_COLUMN_ALIASES: dict[str, list[str]] = {
    "outcome_id": ["outcome_id", "outcome id", "OutcomeID", "id"],
    "vendor_claim_id": [
        "vendor_claim_id",
        "claim_id",
        "claimid",
        "vendor claim id",
    ],
    "customer_id": [
        "customer_reference",
        "customer_id",
        "customerid",
        "customer id",
        "customer_ref",
    ],
    "account_id": [
        "account_reference",
        "account_id",
        "accountid",
        "account id",
        "account_ref",
    ],
    "intent": [
        "claimed_outcome_type",
        "outcome_type",
        "intent",
        "issue_type",
        "category",
    ],
    "closed_at": [
        "claimed_completion_time",
        "closed_at",
        "completed_at",
        "resolution_time",
        "timestamp",
    ],
    "billed_amount": [
        "billed_amount",
        "amount",
        "charge",
        "price",
    ],
    "expected_action": [
        "expected_action",
        "action",
        "action_type",
        "claimed_outcome_type",
    ],
    "vendor_claim": [
        "vendor_disposition",
        "vendor_claim",
        "disposition",
        "status",
    ],
    "conversation_id": [
        "conversation_id",
        "conversationid",
        "ticket_id",
        "case_id",
    ],
    "agent_version": [
        "agent_version",
        "model_version",
        "version",
    ],
}


def parse_invoice_csv(
    content: str | bytes,
    column_mapping: dict[str, str] | None = None,
) -> ParseResult:
    """Parse a vendor invoice CSV into claim rows.

    ``column_mapping`` maps Evidue canonical fields to the user's actual CSV
    headers.  It is applied after alias auto-detection and is strictly checked
    against the uploaded headers.
    """
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return ParseResult([], [RejectedRow(0, "Invoice CSV must be UTF-8 encoded", {})])

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return ParseResult([], [RejectedRow(0, "Empty CSV or no headers", {})])

    headers = list(reader.fieldnames)
    col_map = _build_column_map(headers, INVOICE_COLUMN_ALIASES)
    if column_mapping:
        for canonical, actual in column_mapping.items():
            if canonical not in INVOICE_COLUMN_ALIASES:
                return ParseResult([], [RejectedRow(0, f"Unknown Evidue field '{canonical}'", {})])
            if actual not in headers:
                return ParseResult(
                    [], [RejectedRow(0, f"Mapped column '{actual}' is not in the CSV", {})]
                )
            col_map[canonical] = actual

    required = ["outcome_id", "customer_id", "intent", "closed_at", "billed_amount"]
    missing = [field for field in required if col_map[field] is None]
    if missing:
        return ParseResult(
            [],
            [
                RejectedRow(
                    0,
                    "Missing "
                    + ", ".join(missing)
                    + " invoice field(s). "
                    + f"Found columns: {headers}",
                    {},
                )
            ],
        )

    accepted: list[ParsedRow] = []
    rejected: list[RejectedRow] = []

    for row_num, raw in enumerate(reader, start=2):
        outcome_id = raw.get(col_map["outcome_id"] or "", "").strip()
        if not outcome_id:
            rejected.append(RejectedRow(row_num, "Missing outcome_id", dict(raw)))
            continue

        closed_at_str = raw.get(col_map["closed_at"] or "", "").strip()
        try:
            closed_at = _parse_timestamp(closed_at_str)
        except ValueError:
            rejected.append(
                RejectedRow(row_num, f"Unparseable timestamp: '{closed_at_str}'", dict(raw))
            )
            continue

        amount_str = raw.get(col_map["billed_amount"] or "", "").strip()
        if not amount_str:
            rejected.append(RejectedRow(row_num, "Missing billed_amount", dict(raw)))
            continue
        billed_amount = _parse_decimal(amount_str)
        if billed_amount is None or not billed_amount.is_finite() or billed_amount < 0:
            rejected.append(
                RejectedRow(row_num, f"Unparseable or negative amount: '{amount_str}'", dict(raw))
            )
            continue

        customer_id = raw.get(col_map["customer_id"] or "", "").strip()
        if not customer_id:
            rejected.append(RejectedRow(row_num, "Missing customer_id", dict(raw)))
            continue

        claim_id = raw.get(col_map["vendor_claim_id"] or "", "").strip() or f"CLM-{outcome_id}"
        account_id = raw.get(col_map["account_id"] or "", "").strip() or ""
        intent = raw.get(col_map["intent"] or "", "").strip()
        if not intent:
            rejected.append(RejectedRow(row_num, "Missing claimed outcome type/intent", dict(raw)))
            continue
        expected_action = raw.get(col_map["expected_action"] or "", "").strip() or intent
        vendor_claim = raw.get(col_map["vendor_claim"] or "", "").strip() or "claimed"
        conversation_id = raw.get(col_map["conversation_id"] or "", "").strip() or ""
        agent_version = raw.get(col_map["agent_version"] or "", "").strip() or "unknown"

        accepted.append(
            ParsedRow(
                row_num,
                {
                    "outcome_id": outcome_id,
                    "vendor_claim_id": claim_id,
                    "customer_id": customer_id,
                    "account_id": account_id,
                    "intent": intent,
                    "closed_at": closed_at,
                    "billed_amount": billed_amount,
                    "expected_action": expected_action,
                    "vendor_claim": vendor_claim,
                    "conversation_id": conversation_id,
                    "agent_version": agent_version,
                    "payload_hash": _payload_hash(dict(raw)),
                    "raw": dict(raw),
                },
            )
        )

    return ParseResult(accepted, rejected)


def inspect_invoice_csv(
    content: str | bytes,
    column_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return mapping hints, safe samples, and finance control totals when mappable."""
    if isinstance(content, bytes):
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValueError("Invoice CSV must be UTF-8 encoded") from None
    else:
        decoded = content
    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise ValueError("Invoice CSV is empty or has no header row")
    headers = list(reader.fieldnames)
    mapping = _build_column_map(headers, INVOICE_COLUMN_ALIASES)
    if column_mapping:
        for canonical, actual in column_mapping.items():
            if canonical not in INVOICE_COLUMN_ALIASES:
                raise ValueError(f"Unknown Evidue field '{canonical}'")
            if actual not in headers:
                raise ValueError(f"Mapped column '{actual}' is not in the CSV")
            mapping[canonical] = actual
    required = ["outcome_id", "customer_id", "intent", "closed_at", "billed_amount"]
    samples: list[dict[str, str]] = []
    for raw in reader:
        samples.append({str(key): str(value or "")[:200] for key, value in raw.items()})
        if len(samples) >= 5:
            break

    missing = [field for field in required if mapping[field] is None]
    control_totals: dict[str, Any] | None = None
    if not missing:
        parsed = parse_invoice_csv(decoded, {key: value for key, value in mapping.items() if value})
        if parsed.accepted:
            amounts = [Decimal(str(row.data["billed_amount"])) for row in parsed.accepted]
            closed = [row.data["closed_at"] for row in parsed.accepted]
            customers = {str(row.data["customer_id"]) for row in parsed.accepted}
            outcome_counts: dict[str, int] = {}
            for row in parsed.accepted:
                intent = str(row.data["intent"])
                outcome_counts[intent] = outcome_counts.get(intent, 0) + 1
            total = len(parsed.accepted)
            control_totals = {
                "total_rows": total + len(parsed.rejected),
                "accepted_rows": total,
                "rejected_rows": len(parsed.rejected),
                "total_billed": f"{sum(amounts, Decimal()):.2f}",
                "unique_customers": len(customers),
                "period_start": min(closed).isoformat(),
                "period_end": max(closed).isoformat(),
                "outcome_mix": [
                    {
                        "name": name,
                        "count": count,
                        "percent": round(count / total * 100, 1),
                    }
                    for name, count in sorted(
                        outcome_counts.items(), key=lambda item: (-item[1], item[0])
                    )
                ],
                "rejection_reasons": [
                    {"row": item.row_number, "reason": item.reason} for item in parsed.rejected[:20]
                ],
            }

    return {
        "headers": headers,
        "auto_mapping": mapping,
        "required_fields": required,
        "missing_required_fields": missing,
        "sample_rows": samples,
        "control_totals": control_totals,
    }


# ---------------------------------------------------------------------------
# Evidence parser (CSV, JSON, JSONL)
# ---------------------------------------------------------------------------

EVIDENCE_COLUMN_ALIASES: dict[str, list[str]] = {
    "event_id": ["event_id", "id", "record_id"],
    "event_type": [
        "event_type",
        "type",
        "action",
        "status",
        "result",
    ],
    "timestamp": [
        "occurred_at",
        "timestamp",
        "created_at",
        "updated_at",
        "event_time",
        "closed_at",
    ],
    "customer_id": [
        "customer_id",
        "customer_reference",
        "user_id",
        "requester_id",
    ],
    "outcome_id": [
        "outcome_id",
        "conversation_id",
        "ticket_id",
        "case_id",
    ],
    "account_id": [
        "account_id",
        "account_reference",
    ],
    "action": [
        "action",
        "action_type",
        "intent",
    ],
}


def _parse_evidence_record(
    raw: dict[str, Any],
    row_num: int,
    source_type: str,
    col_map: dict[str, str | None] | None = None,
) -> ParsedRow | RejectedRow:
    """Parse a single evidence record (from CSV row or JSON object)."""

    def _get(canonical: str) -> str:
        if col_map and col_map.get(canonical):
            return str(raw.get(col_map[canonical] or "", "")).strip()
        # Direct field lookup for JSON sources
        for alias in EVIDENCE_COLUMN_ALIASES.get(canonical, [canonical]):
            key = _normalize_key(alias)
            for raw_key, raw_value in raw.items():
                if _normalize_key(raw_key) == key:
                    return str(raw_value).strip()
        return ""

    ts_str = _get("timestamp")
    try:
        timestamp = _parse_timestamp(ts_str)
    except ValueError:
        return RejectedRow(row_num, f"Unparseable timestamp: '{ts_str}'", dict(raw))

    customer_id = _get("customer_id")
    if not customer_id:
        return RejectedRow(row_num, "Missing customer_id", dict(raw))

    event_type = _get("event_type")
    if not event_type:
        return RejectedRow(row_num, "Missing event_type", dict(raw))
    outcome_id = _get("outcome_id") or None
    event_id = _get("event_id") or _payload_hash(dict(raw)).split(":", 1)[1]
    account_id = _get("account_id")
    action = _get("action")

    # Collect remaining fields as values
    values: dict[str, str] = {}
    if account_id:
        values["account_id"] = account_id
    if action:
        values["action"] = action
    # Include any extra fields from the raw record
    known_keys = set()
    for aliases in EVIDENCE_COLUMN_ALIASES.values():
        for a in aliases:
            known_keys.add(_normalize_key(a))
    for k, v in raw.items():
        if _normalize_key(k) not in known_keys and v is not None:
            str_val = str(v).strip()
            if str_val and str_val != "None":
                values[k] = str_val

    return ParsedRow(
        row_num,
        {
            "event_id": event_id,
            "source_system": source_type,
            "source_record_id": event_id,
            "event_type": event_type,
            "timestamp": timestamp,
            "customer_id": customer_id,
            "outcome_id": outcome_id,
            "values": values,
            "payload_hash": _payload_hash(dict(raw)),
            "raw": dict(raw),
        },
    )


def parse_evidence_csv(content: str | bytes, source_type: str) -> ParseResult:
    """Parse a customer evidence CSV."""
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return ParseResult([], [RejectedRow(0, "Empty CSV or no headers", {})])

    col_map = _build_column_map(list(reader.fieldnames), EVIDENCE_COLUMN_ALIASES)
    accepted: list[ParsedRow] = []
    rejected: list[RejectedRow] = []

    for row_num, raw in enumerate(reader, start=2):
        result = _parse_evidence_record(dict(raw), row_num, source_type, col_map)
        if isinstance(result, RejectedRow):
            rejected.append(result)
        else:
            accepted.append(result)

    return ParseResult(accepted, rejected)


def parse_evidence_jsonl(content: str | bytes, source_type: str) -> ParseResult:
    """Parse a customer evidence JSONL file (one JSON object per line)."""
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")

    accepted: list[ParsedRow] = []
    rejected: list[RejectedRow] = []

    for row_num, line in enumerate(content.strip().splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            rejected.append(RejectedRow(row_num, f"Invalid JSON: {exc}", {"raw_line": line[:500]}))
            continue
        if not isinstance(obj, dict):
            rejected.append(RejectedRow(row_num, "Expected JSON object", {"raw_line": line[:500]}))
            continue
        result = _parse_evidence_record(obj, row_num, source_type)
        if isinstance(result, RejectedRow):
            rejected.append(result)
        else:
            accepted.append(result)

    return ParseResult(accepted, rejected)


def parse_evidence_json(content: str | bytes, source_type: str) -> ParseResult:
    """Parse a JSON file containing an array of evidence records."""
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        return ParseResult([], [RejectedRow(0, f"Invalid JSON: {exc}", {})])

    if isinstance(data, dict):
        # Try to find an array inside common wrapper keys
        for key in ("records", "events", "data", "items", "results"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            data = [data]

    if not isinstance(data, list):
        return ParseResult([], [RejectedRow(0, "Expected JSON array or object", {})])

    accepted: list[ParsedRow] = []
    rejected: list[RejectedRow] = []

    for row_num, obj in enumerate(data, start=1):
        if not isinstance(obj, dict):
            rejected.append(RejectedRow(row_num, "Expected JSON object", {"raw": str(obj)[:500]}))
            continue
        result = _parse_evidence_record(obj, row_num, source_type)
        if isinstance(result, RejectedRow):
            rejected.append(result)
        else:
            accepted.append(result)

    return ParseResult(accepted, rejected)


# ---------------------------------------------------------------------------
# Identity map CSV parser
# ---------------------------------------------------------------------------

IDENTITY_MAP_ALIASES: dict[str, list[str]] = {
    "conversation_id": ["conversation_id", "ticket_id", "case_id"],
    "customer_id": ["customer_id", "support_customer_id", "user_id"],
    "account_id": ["customer_account_id", "account_id", "payment_account_id"],
    "outcome_id": ["outcome_id"],
}


def parse_identity_map_csv(content: str | bytes) -> ParseResult:
    """Parse an identity mapping CSV that connects IDs across systems."""
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return ParseResult([], [RejectedRow(0, "Empty CSV or no headers", {})])

    col_map = _build_column_map(list(reader.fieldnames), IDENTITY_MAP_ALIASES)

    # Need at least two mapped columns for the mapping to be useful
    mapped_count = sum(1 for v in col_map.values() if v is not None)
    if mapped_count < 2:
        return ParseResult(
            [],
            [
                RejectedRow(
                    0,
                    f"Need at least 2 recognized identity columns. Found: {reader.fieldnames}",
                    {},
                )
            ],
        )

    accepted: list[ParsedRow] = []
    rejected: list[RejectedRow] = []

    for row_num, raw in enumerate(reader, start=2):
        mapping: dict[str, str] = {}
        for canonical, actual in col_map.items():
            if actual:
                val = raw.get(actual, "").strip()
                if val:
                    mapping[canonical] = val

        if len(mapping) < 2:
            rejected.append(
                RejectedRow(row_num, "Fewer than 2 non-empty identity fields", dict(raw))
            )
            continue

        accepted.append(ParsedRow(row_num, mapping))

    return ParseResult(accepted, rejected)
