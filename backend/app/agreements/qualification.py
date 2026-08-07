from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import OperationalEvent, OutcomeClaim

from .adjudication import evaluate_claim
from .assurance import assure_agreement
from .compiler import lower_to_agreement_ir
from .compiler_models import AgreementCompilationProposal
from .models import AgreementIR, AutomationClass
from .native_compiler import bind_proposal_to_sources, compile_native_with_gemini
from .presentation import agreement_finance_view

Materiality = Literal["critical", "high", "medium", "informational"]
ExpectedKind = Literal["norm", "settlement", "manual_or_unsupported"]


class QualificationGoldTerm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    materiality: Materiality = "critical"
    source_document_id: str
    source_phrase: str = Field(min_length=3)
    expected_kind: ExpectedKind
    expected_norm_type: str | None = None
    expected_consequence: str | None = None
    expected_automation: str | None = None
    expected_numeric_values: list[str] = Field(default_factory=list)
    expected_fact_types: list[str] = Field(default_factory=list)
    notes: str = ""


class QualificationGold(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pack_id: str
    review_status: Literal["provisional_engineering_gold", "human_reviewed"] = (
        "provisional_engineering_gold"
    )
    exhaustive_financial_terms: bool = False
    terms: list[QualificationGoldTerm] = Field(min_length=1)


class QualificationDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    path: str
    document_type: str = "agreement"
    precedence: int = 100
    effective_from: str | None = None
    effective_until: str | None = None
    source_url: str | None = None
    retrieved_at: str | None = None


class QualificationRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    target_document_id: str
    relation: str


class QualificationMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    document_id: str
    find: str
    replace: str
    financially_material: bool = True


class QualificationScenarioEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source_system: str
    source_record_id: str
    event_type: str
    timestamp: str
    customer_id: str
    outcome_id: str | None = None
    values: dict[str, str] = Field(default_factory=dict)
    ingested_at: str | None = None


class QualificationFinancialScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    outcome_id: str
    invoice_id: str = "QUAL-INVOICE"
    customer_id: str
    intent: str
    vendor_claim: str = "claimed"
    closed_at: str
    expected_action: str
    account_id: str
    billed_amount: str
    events: list[QualificationScenarioEvent] = Field(default_factory=list)
    expected_status: Literal["payable", "disputed", "needs_review"]
    expected_payable_amount: str
    expected_disputed_amount: str
    expected_needs_review_amount: str


class QualificationScenarioSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pack_id: str
    review_status: Literal["provisional_engineering_gold", "human_reviewed"] = (
        "provisional_engineering_gold"
    )
    scenarios: list[QualificationFinancialScenario] = Field(min_length=1)


class QualificationManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    contract_id: str
    customer: str
    vendor: str
    documents: list[QualificationDocument]
    relations: list[QualificationRelation] = Field(default_factory=list)
    gold_file: str | None = None
    scenario_file: str | None = None
    mutations: list[QualificationMutation] = Field(default_factory=list)
    source_class: str = "user_supplied"
    source_notes: str = ""


@dataclass(frozen=True)
class QualificationPack:
    root: Path
    manifest: QualificationManifest
    documents: dict[str, tuple[str, str]]
    gold: QualificationGold | None
    scenarios: QualificationScenarioSet | None


def _strip_html(value: str) -> str:
    from html.parser import HTMLParser

    class Extractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.parts: list[str] = []
            self.skip = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag in {"script", "style", "noscript"}:
                self.skip += 1
            elif tag in {"p", "div", "section", "br", "li", "tr", "h1", "h2", "h3", "h4"}:
                self.parts.append("\n")

        def handle_endtag(self, tag: str) -> None:
            if tag in {"script", "style", "noscript"} and self.skip:
                self.skip -= 1
            elif tag in {"p", "div", "section", "li", "tr"}:
                self.parts.append("\n")

        def handle_data(self, data: str) -> None:
            if not self.skip:
                self.parts.append(data)

    parser = Extractor()
    parser.feed(value)
    text = "".join(parser.parts)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def load_document_text(path: Path) -> str:
    suffix = path.suffix.lower()
    raw = path.read_bytes()
    if suffix in {".txt", ".md", ".text"}:
        text = raw.decode("utf-8-sig")
    elif suffix in {".html", ".htm"}:
        text = _strip_html(raw.decode("utf-8-sig", errors="replace"))
    elif suffix == ".pdf":
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(raw))
        text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages)
    elif suffix == ".docx":
        import io
        import zipfile
        from xml.etree import ElementTree

        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            document_xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(document_xml)
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs: list[str] = []
        for paragraph in root.iter(namespace + "p"):
            pieces = [node.text or "" for node in paragraph.iter(namespace + "t")]
            value = "".join(pieces).strip()
            if value:
                paragraphs.append(value)
        text = "\n\n".join(paragraphs)
    else:
        raise ValueError(f"Unsupported qualification document type: {path.name}")
    cleaned = text.strip()
    if len(cleaned) < 50:
        raise ValueError(f"Qualification document {path.name} has too little readable text")
    return cleaned


def load_pack(root: str | Path) -> QualificationPack:
    root_path = Path(root).resolve()
    manifest_path = root_path / "manifest.json"
    manifest = QualificationManifest.model_validate_json(manifest_path.read_text())
    documents: dict[str, tuple[str, str]] = {}
    for item in manifest.documents:
        path = root_path / item.path
        documents[item.id] = (item.title, load_document_text(path))
    gold = None
    if manifest.gold_file:
        gold = QualificationGold.model_validate_json((root_path / manifest.gold_file).read_text())
        if gold.pack_id != manifest.id:
            raise ValueError("Gold pack_id does not match manifest id")
    scenarios = None
    if manifest.scenario_file:
        scenarios = QualificationScenarioSet.model_validate_json(
            (root_path / manifest.scenario_file).read_text()
        )
        if scenarios.pack_id != manifest.id:
            raise ValueError("Scenario pack_id does not match manifest id")
    return QualificationPack(
        root=root_path,
        manifest=manifest,
        documents=documents,
        gold=gold,
        scenarios=scenarios,
    )


def pack_metadata(pack: QualificationPack) -> dict[str, str]:
    return {
        "customer": pack.manifest.customer,
        "vendor": pack.manifest.vendor,
        "qualification_pack": pack.manifest.id,
        "source_class": pack.manifest.source_class,
        "agreement_documents": json.dumps(
            [item.model_dump(mode="json") for item in pack.manifest.documents], sort_keys=True
        ),
        "agreement_relations": json.dumps(
            [item.model_dump(mode="json") for item in pack.manifest.relations], sort_keys=True
        ),
    }


def source_bundle_hash(pack: QualificationPack) -> str:
    payload = {
        "documents": {
            doc_id: sha256(text.encode("utf-8")).hexdigest()
            for doc_id, (_, text) in sorted(pack.documents.items())
        },
        "relations": [item.model_dump(mode="json") for item in pack.manifest.relations],
    }
    return "sha256:" + sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def compile_pack_live(pack: QualificationPack, *, run_number: int = 1) -> AgreementIR:
    result = compile_native_with_gemini(
        contract_id=pack.manifest.contract_id,
        source_documents=pack.documents,
        metadata=pack_metadata(pack),
    )
    agreement, _ = lower_to_agreement_ir(
        result.proposal,
        compilation_id=f"QUAL-{pack.manifest.id}-{run_number}",
        version=run_number,
        source_hash=source_bundle_hash(pack),
    )
    return agreement


def compile_pack_proposal(
    pack: QualificationPack,
    proposal_payload: dict[str, Any],
    *,
    run_number: int = 1,
) -> AgreementIR:
    proposal = AgreementCompilationProposal.model_validate(proposal_payload)
    proposal = bind_proposal_to_sources(
        proposal,
        expected_contract_id=pack.manifest.contract_id,
        source_documents=pack.documents,
    )
    agreement, _ = lower_to_agreement_ir(
        proposal,
        compilation_id=f"QUAL-{pack.manifest.id}-{run_number}",
        version=run_number,
        source_hash=source_bundle_hash(pack),
    )
    return agreement


def _contains_numeric(payload: Any, expected: str) -> bool:
    if isinstance(payload, dict):
        return any(_contains_numeric(value, expected) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_numeric(value, expected) for value in payload)
    if payload is None:
        return False
    return str(payload).strip() == expected.strip()


def _source_matches(agreement: AgreementIR, term: QualificationGoldTerm) -> list[str]:
    phrase = " ".join(term.source_phrase.lower().split())
    matches: list[str] = []
    for clause in agreement.clauses:
        if clause.document_id != term.source_document_id:
            continue
        text = " ".join(clause.text.lower().split())
        if phrase in text:
            matches.append(clause.id)
    return matches


def _term_result(agreement: AgreementIR, term: QualificationGoldTerm) -> dict[str, Any]:
    clause_ids = _source_matches(agreement, term)
    norms = [
        norm for norm in agreement.norms if set(norm.source_clause_ids).intersection(clause_ids)
    ]
    policies = [
        policy
        for policy in agreement.settlement_policies
        if set(policy.source_clause_ids).intersection(clause_ids)
    ]
    proof_fact_types = {
        fact_type
        for proof in agreement.proof_requirements
        if proof.norm_id in {norm.id for norm in norms}
        for fact_type in proof.acceptable_fact_types
    }

    issues: list[str] = []
    found = bool(clause_ids)
    if not found:
        issues.append("source clause not represented")
    if term.expected_kind == "norm" and not norms:
        issues.append("expected contract rule missing")
    if term.expected_kind == "settlement" and not policies:
        issues.append("expected pricing term missing")
    if (
        term.expected_kind == "manual_or_unsupported"
        and norms
        and all(
            norm.automation_class
            in {AutomationClass.FULLY_EXECUTABLE, AutomationClass.EXECUTABLE_IF_DATA_AVAILABLE}
            for norm in norms
        )
    ):
        issues.append("subjective/unsupported term was silently made automatic")

    if (
        term.expected_norm_type
        and norms
        and not any(norm.norm_type.value == term.expected_norm_type for norm in norms)
    ):
        issues.append(f"norm type mismatch (expected {term.expected_norm_type})")
    if (
        term.expected_consequence
        and norms
        and not any(norm.consequence == term.expected_consequence for norm in norms)
    ):
        issues.append(f"consequence mismatch (expected {term.expected_consequence})")
    if (
        term.expected_automation
        and norms
        and not any(norm.automation_class.value == term.expected_automation for norm in norms)
    ):
        issues.append(f"automation mismatch (expected {term.expected_automation})")
    if term.expected_fact_types and not set(term.expected_fact_types).issubset(proof_fact_types):
        issues.append(
            "evidence-plan mismatch: missing "
            + ", ".join(sorted(set(term.expected_fact_types) - proof_fact_types))
        )

    structured = [norm.model_dump(mode="json") for norm in norms] + [
        policy.model_dump(mode="json") for policy in policies
    ]
    numeric_mismatches = [
        value for value in term.expected_numeric_values if not _contains_numeric(structured, value)
    ]
    if numeric_mismatches:
        issues.append("numeric parameter mismatch: " + ", ".join(numeric_mismatches))

    return {
        "id": term.id,
        "description": term.description,
        "materiality": term.materiality,
        "source_document_id": term.source_document_id,
        "source_clause_ids": clause_ids,
        "norm_ids": [item.id for item in norms],
        "settlement_policy_ids": [item.id for item in policies],
        "found": found
        and not (
            (term.expected_kind == "norm" and not norms)
            or (term.expected_kind == "settlement" and not policies)
        ),
        "numeric_mismatches": numeric_mismatches,
        "issues": issues,
    }


def semantic_fingerprint(agreement: AgreementIR) -> str:
    finance = agreement_finance_view(agreement)
    normalized = {
        "rules": [
            {
                "description": item["description"],
                "consequence": item["consequence"],
                "verification_method": item["verification_method"],
                "evidence_needed": sorted(item["evidence_needed"]),
                "condition": item["technical"]["condition"],
            }
            for item in finance["contract_rules"]
        ],
        "pricing": [
            {
                "description": item["description"],
                "currency": item["currency"],
                "amount_expression": item["technical"]["amount_expression"],
            }
            for item in finance["pricing_terms"]
        ],
    }
    return (
        "sha256:"
        + sha256(
            json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )


def score_agreement(agreement: AgreementIR, gold: QualificationGold | None) -> dict[str, Any]:
    assurance = assure_agreement(agreement)
    executable = {
        AutomationClass.FULLY_EXECUTABLE,
        AutomationClass.EXECUTABLE_IF_DATA_AVAILABLE,
    }
    clause_ids = {clause.id for clause in agreement.clauses}
    ungrounded = [
        norm.id
        for norm in agreement.norms
        if norm.automation_class in executable
        and (not norm.source_clause_ids or not set(norm.source_clause_ids).issubset(clause_ids))
    ]
    ungrounded_policies = [
        policy.id
        for policy in agreement.settlement_policies
        if not policy.source_clause_ids or not set(policy.source_clause_ids).issubset(clause_ids)
    ]

    base: dict[str, Any] = {
        "agreement_id": agreement.agreement_id,
        "semantic_fingerprint": semantic_fingerprint(agreement),
        "assurance_hard_gate_passed": assurance.hard_gate_passed,
        "assurance_review_required": assurance.review_required,
        "executable_rules": sum(
            1 for norm in agreement.norms if norm.automation_class in executable
        ),
        "ungrounded_executable_rules": ungrounded,
        "ungrounded_pricing_policies": ungrounded_policies,
        "finance_view": agreement_finance_view(agreement),
        "gold_available": gold is not None,
    }
    if gold is None:
        base["structural_validation_passed"] = assurance.hard_gate_passed
        base["qualification_passed"] = False
        base["qualification_status"] = "review_required"
        base["warning"] = (
            "The AIR passed structural checks, but no reviewed gold standard was supplied. "
            "Contract correctness is therefore unqualified and cannot be reported as passed."
        )
        return base

    terms = [_term_result(agreement, term) for term in gold.terms]
    critical = [item for item in terms if item["materiality"] == "critical"]
    critical_found = [item for item in critical if item["found"] and not item["issues"]]
    numeric_mismatches = [
        {"id": item["id"], "values": item["numeric_mismatches"]}
        for item in terms
        if item["materiality"] == "critical" and item["numeric_mismatches"]
    ]
    silent_automation = [
        item["id"]
        for item in terms
        if any("silently made automatic" in issue for issue in item["issues"])
    ]

    unsupported_executable: list[str] = []
    if gold.exhaustive_financial_terms:
        represented_norms = {norm_id for item in terms for norm_id in item["norm_ids"]}
        represented_policies = {
            policy_id for item in terms for policy_id in item["settlement_policy_ids"]
        }
        unsupported_executable.extend(
            norm.id
            for norm in agreement.norms
            if norm.automation_class in executable and norm.id not in represented_norms
        )
        unsupported_executable.extend(
            policy.id
            for policy in agreement.settlement_policies
            if policy.id not in represented_policies
        )

    critical_recall = 100.0 if not critical else len(critical_found) / len(critical) * 100
    metric_gate_passed = (
        assurance.hard_gate_passed
        and critical_recall == 100.0
        and not unsupported_executable
        and not ungrounded
        and not ungrounded_policies
        and not numeric_mismatches
        and not silent_automation
    )
    independently_reviewed = gold.review_status == "human_reviewed"
    exhaustive = gold.exhaustive_financial_terms
    passed = metric_gate_passed and independently_reviewed and exhaustive
    if passed:
        status = "passed"
    elif metric_gate_passed and (not independently_reviewed or not exhaustive):
        status = "review_required"
    else:
        status = "failed"
    base.update(
        {
            "gold_review_status": gold.review_status,
            "gold_exhaustive": gold.exhaustive_financial_terms,
            "metric_gate_passed": metric_gate_passed,
            "independently_reviewed": independently_reviewed,
            "terms": terms,
            "critical_term_count": len(critical),
            "critical_term_pass_count": len(critical_found),
            "critical_financial_term_recall_percent": round(critical_recall, 1),
            "unsupported_executable_financial_rules": unsupported_executable,
            "critical_numeric_parameter_mismatches": numeric_mismatches,
            "silent_subjective_automation": silent_automation,
            "qualification_status": status,
            "qualification_passed": passed,
        }
    )
    return base


def _parse_scenario_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def run_financial_scenarios(
    agreement: AgreementIR,
    scenario_set: QualificationScenarioSet | None,
) -> dict[str, Any]:
    if scenario_set is None:
        return {
            "available": False,
            "review_status": None,
            "passed": False,
            "status": "review_required",
            "warning": (
                "No reviewed financial scenarios were supplied for contract-to-dollar validation."
            ),
            "scenarios": [],
        }

    rows: list[dict[str, Any]] = []
    for scenario in scenario_set.scenarios:
        claim = OutcomeClaim(
            outcome_id=scenario.outcome_id,
            invoice_id=scenario.invoice_id,
            customer_id=scenario.customer_id,
            intent=scenario.intent,
            vendor_claim=scenario.vendor_claim,
            closed_at=_parse_scenario_datetime(scenario.closed_at),
            expected_action=scenario.expected_action,
            account_id=scenario.account_id,
            billed_amount=Decimal(scenario.billed_amount),
        )
        events = [
            OperationalEvent(
                id=item.id,
                source_system=item.source_system,
                source_record_id=item.source_record_id,
                event_type=item.event_type,
                timestamp=_parse_scenario_datetime(item.timestamp),
                customer_id=item.customer_id,
                outcome_id=item.outcome_id,
                values=item.values,
                ingested_at=_parse_scenario_datetime(item.ingested_at or item.timestamp),
            )
            for item in scenario.events
        ]
        result = evaluate_claim(claim, events, agreement)
        actual = {
            "status": result.status,
            "payable": format(result.confirmed_payable_amount, "f"),
            "disputed": format(result.confirmed_disputed_amount, "f"),
            "needs_review": format(result.needs_review_amount, "f"),
        }
        expected = {
            "status": scenario.expected_status,
            "payable": format(Decimal(scenario.expected_payable_amount), "f"),
            "disputed": format(Decimal(scenario.expected_disputed_amount), "f"),
            "needs_review": format(Decimal(scenario.expected_needs_review_amount), "f"),
        }
        issues = [key for key in expected if actual[key] != expected[key]]
        rows.append(
            {
                "id": scenario.id,
                "description": scenario.description,
                "expected": expected,
                "actual": actual,
                "passed": not issues,
                "mismatches": issues,
                "rule_id": result.rule_id,
                "reason": result.reason,
            }
        )

    metric_passed = all(row["passed"] for row in rows)
    reviewed = scenario_set.review_status == "human_reviewed"
    passed = metric_passed and reviewed
    return {
        "available": True,
        "review_status": scenario_set.review_status,
        "metric_gate_passed": metric_passed,
        "passed": passed,
        "status": "passed" if passed else ("review_required" if metric_passed else "failed"),
        "scenarios": rows,
    }


def apply_mutation(pack: QualificationPack, mutation: QualificationMutation) -> QualificationPack:
    documents = dict(pack.documents)
    if mutation.document_id not in documents:
        raise ValueError(f"Mutation references unknown document {mutation.document_id}")
    title, text = documents[mutation.document_id]
    if mutation.find not in text:
        raise ValueError(f"Mutation {mutation.id} source text was not found")
    documents[mutation.document_id] = (title, text.replace(mutation.find, mutation.replace, 1))
    return QualificationPack(
        root=pack.root,
        manifest=pack.manifest,
        documents=documents,
        gold=pack.gold,
        scenarios=pack.scenarios,
    )
