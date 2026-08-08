from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import OperationalEvent, OutcomeClaim

from .adjudication import evaluate_claim
from .assurance import assure_agreement
from .compiler import lower_to_agreement_ir
from .compiler_models import AgreementCompilationProposal
from .document_ingestion import read_decoded_file, validate_text_artifact
from .models import AgreementIR, AutomationClass
from .native_compiler import bind_proposal_to_sources, compile_native
from .presentation import agreement_finance_view
from .semantics import semantic_fingerprint

Materiality = Literal[
    "critical",
    "high",
    "medium",
    "informational",
    "critical_financial",
    "material_operational",
    "supporting",
    "non_material",
]
ExpectedKind = Literal["norm", "settlement", "manual_or_unsupported", "source_only"]
SemanticSection = Literal["rules", "pricing", "evidence", "coverage"]


class QualificationGoldTerm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    materiality: Materiality = "critical"
    source_document_id: str
    source_phrase: str = Field(min_length=3)
    expected_kind: ExpectedKind
    expected_requirement_kind: str | None = None
    expected_requirement_data_dependencies: list[str] = Field(default_factory=list)
    expected_norm_type: str | None = None
    expected_consequence: str | None = None
    expected_automation: str | None = None
    expected_numeric_values: list[str] = Field(default_factory=list)
    expected_fact_types: list[str] = Field(default_factory=list)
    forbidden_numeric_values: list[str] = Field(default_factory=list)
    numeric_parameter_must_be_unknown: bool = False
    must_not_be_executable: bool = False
    expected_diagnostic_codes: list[str] = Field(default_factory=list)
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
    raw_sha256: str | None = None
    content_sha256: str | None = None
    transport_encoding: str | None = None
    content_type: str | None = None


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
    expected_changed_sections: list[SemanticSection] = Field(default_factory=list)
    expected_unchanged_sections: list[SemanticSection] = Field(default_factory=list)


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
    decoded = read_decoded_file(path)
    raw = decoded.content
    if suffix in {".txt", ".md", ".text"}:
        text = raw.decode("utf-8-sig", errors="strict")
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
    validate_text_artifact(cleaned, name=path.name, require_contract_like=True)
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


@dataclass(frozen=True)
class QualificationCompilation:
    agreement: AgreementIR
    provenance: dict[str, Any]


def compile_pack_live_result(
    pack: QualificationPack,
    *,
    run_number: int = 1,
    provider: str | None = None,
    model: str | None = None,
) -> QualificationCompilation:
    result = compile_native(
        contract_id=pack.manifest.contract_id,
        source_documents=pack.documents,
        metadata=pack_metadata(pack),
        provider=provider,
        model=model,
        pin_provider=True,
    )
    agreement, _ = lower_to_agreement_ir(
        result.proposal,
        compilation_id=f"QUAL-{pack.manifest.id}-{run_number}",
        version=run_number,
        source_hash=source_bundle_hash(pack),
    )
    return QualificationCompilation(agreement=agreement, provenance=result.provenance)


def compile_pack_live(
    pack: QualificationPack,
    *,
    run_number: int = 1,
    provider: str | None = None,
    model: str | None = None,
) -> AgreementIR:
    return compile_pack_live_result(
        pack,
        run_number=run_number,
        provider=provider,
        model=model,
    ).agreement


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
    if isinstance(payload, bool) or payload is None:
        return False

    try:
        return Decimal(str(payload).strip()) == Decimal(expected.strip())
    except InvalidOperation:
        return str(payload).strip() == expected.strip()


def _numeric_literals(payload: Any) -> set[str]:
    values: set[str] = set()
    if isinstance(payload, dict):
        for value in payload.values():
            values.update(_numeric_literals(value))
    elif isinstance(payload, list):
        for value in payload:
            values.update(_numeric_literals(value))
    elif isinstance(payload, bool) or payload is None:
        pass
    elif isinstance(payload, (int, float, Decimal)):
        values.add(str(payload))
    elif isinstance(payload, str):
        with suppress(InvalidOperation):
            values.add(format(Decimal(payload), "f"))
    return values


def _normalized_text(value: str) -> str:
    return " ".join(value.lower().split())


def _source_matches(agreement: AgreementIR, term: QualificationGoldTerm) -> list[str]:
    phrase = _normalized_text(term.source_phrase)
    matches: list[str] = []
    for clause in agreement.clauses:
        if clause.document_id != term.source_document_id:
            continue
        if phrase in _normalized_text(clause.text):
            matches.append(clause.id)
    return matches


def _requirement_source_matches(agreement: AgreementIR, term: QualificationGoldTerm) -> list[Any]:
    """Return atomic requirements grounded in the gold source phrase.

    A clause can contain several independent financial requirements. Matching at the
    requirement layer prevents one generic norm on that clause from receiving credit
    for every requirement in the clause.
    """

    phrase = _normalized_text(term.source_phrase)
    candidates = [
        requirement
        for requirement in agreement.requirements
        if requirement.source_document_id == term.source_document_id
        and (
            phrase in _normalized_text(requirement.source_text)
            or _normalized_text(requirement.source_text) in phrase
        )
    ]

    expected_disposition = {
        "norm": "norm",
        "settlement": "settlement",
        "manual_or_unsupported": None,
        "source_only": None,
    }[term.expected_kind]
    if expected_disposition is not None:
        disposition_matches = [
            item for item in candidates if item.disposition == expected_disposition
        ]
        if disposition_matches:
            candidates = disposition_matches

    if term.expected_numeric_values:
        numeric_matches = [
            item
            for item in candidates
            if all(
                _contains_numeric(item.model_dump(mode="json"), expected)
                for expected in term.expected_numeric_values
            )
        ]
        if numeric_matches:
            candidates = numeric_matches

    return candidates


def _candidate_term_semantics(
    agreement: AgreementIR,
    term: QualificationGoldTerm,
    *,
    clause_ids: list[str],
    requirement_id: str | None,
) -> dict[str, Any]:
    """Score one requirement/artifact candidate without cross-crediting sibling rules."""

    if requirement_id is None:
        norms = [
            norm for norm in agreement.norms if set(norm.source_clause_ids).intersection(clause_ids)
        ]
        policies = [
            policy
            for policy in agreement.settlement_policies
            if set(policy.source_clause_ids).intersection(clause_ids)
        ]
    else:
        norms = [norm for norm in agreement.norms if requirement_id in norm.requirement_ids]
        policies = [
            policy
            for policy in agreement.settlement_policies
            if requirement_id in policy.requirement_ids
        ]

    norm_ids = {norm.id for norm in norms}
    proof_fact_types = {
        fact_type
        for proof in agreement.proof_requirements
        if proof.norm_id in norm_ids
        and (requirement_id is None or requirement_id in proof.requirement_ids)
        for fact_type in proof.acceptable_fact_types
    }
    issues: list[str] = []
    requirement = (
        next((item for item in agreement.requirements if item.id == requirement_id), None)
        if requirement_id is not None
        else None
    )
    if (
        term.expected_requirement_kind
        and requirement is not None
        and requirement.kind != term.expected_requirement_kind
    ):
        issues.append(
            f"atomic requirement kind mismatch (expected {term.expected_requirement_kind})"
        )
    if term.expected_requirement_data_dependencies and requirement is not None:
        expected_dependencies = set(term.expected_requirement_data_dependencies)
        actual_dependencies = set(requirement.data_dependencies)
        if actual_dependencies != expected_dependencies:
            issues.append(
                "atomic requirement data dependency mismatch: expected "
                f"{sorted(expected_dependencies)}, got {sorted(actual_dependencies)}"
            )

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

    forbidden_numeric = [
        value for value in term.forbidden_numeric_values if _contains_numeric(structured, value)
    ]
    if forbidden_numeric:
        issues.append("forbidden numeric interpretation: " + ", ".join(forbidden_numeric))

    numeric_literals = _numeric_literals(structured)
    if term.numeric_parameter_must_be_unknown and numeric_literals:
        issues.append(
            "redacted/unknown parameter was assigned numeric value(s): "
            + ", ".join(sorted(numeric_literals))
        )

    automatically_executable = bool(policies) or any(
        norm.automation_class
        in {AutomationClass.FULLY_EXECUTABLE, AutomationClass.EXECUTABLE_IF_DATA_AVAILABLE}
        for norm in norms
    )
    if term.must_not_be_executable and automatically_executable:
        issues.append("gold requires this term to remain non-executable")

    diagnostic_codes = {
        diagnostic.code
        for diagnostic in agreement.diagnostics
        if not diagnostic.clause_ids or set(diagnostic.clause_ids).intersection(clause_ids)
    }
    missing_diagnostics = sorted(set(term.expected_diagnostic_codes) - diagnostic_codes)
    if missing_diagnostics:
        issues.append("missing expected diagnostic(s): " + ", ".join(missing_diagnostics))

    expected_artifact_present = not (
        (term.expected_kind == "norm" and not norms)
        or (term.expected_kind == "settlement" and not policies)
    )
    return {
        "requirement_id": requirement_id,
        "norms": norms,
        "policies": policies,
        "issues": issues,
        "numeric_mismatches": numeric_mismatches,
        "forbidden_numeric": forbidden_numeric,
        "numeric_literals": numeric_literals,
        "missing_diagnostics": missing_diagnostics,
        "expected_artifact_present": expected_artifact_present,
    }


def _term_result(agreement: AgreementIR, term: QualificationGoldTerm) -> dict[str, Any]:
    clause_ids = _source_matches(agreement, term)
    source_covered = bool(clause_ids)
    ledger_present = bool(agreement.requirements)
    requirement_matches = _requirement_source_matches(agreement, term) if ledger_present else []
    atomic_requirement_covered = bool(requirement_matches) if ledger_present else source_covered

    candidate_results: list[dict[str, Any]] = []
    if ledger_present:
        candidate_results = [
            _candidate_term_semantics(
                agreement,
                term,
                clause_ids=clause_ids,
                requirement_id=requirement.id,
            )
            for requirement in requirement_matches
        ]
    else:
        candidate_results = [
            _candidate_term_semantics(
                agreement,
                term,
                clause_ids=clause_ids,
                requirement_id=None,
            )
        ]

    passing_candidates = [
        item
        for item in candidate_results
        if item["expected_artifact_present"] and not item["issues"]
    ]
    if passing_candidates:
        selected = min(
            passing_candidates,
            key=lambda item: item["requirement_id"] or "",
        )
    elif candidate_results:
        selected = min(
            candidate_results,
            key=lambda item: (len(item["issues"]), item["requirement_id"] or ""),
        )
    else:
        selected = {
            "requirement_id": None,
            "norms": [],
            "policies": [],
            "issues": [],
            "numeric_mismatches": list(term.expected_numeric_values),
            "forbidden_numeric": [],
            "numeric_literals": set(),
            "missing_diagnostics": list(term.expected_diagnostic_codes),
            "expected_artifact_present": term.expected_kind not in {"norm", "settlement"},
        }

    issues = list(selected["issues"])
    if not source_covered:
        issues.insert(0, "source clause not represented")
    if ledger_present and not atomic_requirement_covered:
        issues.insert(0, "atomic requirement missing")

    semantic_match = (
        source_covered
        and atomic_requirement_covered
        and selected["expected_artifact_present"]
        and not issues
    )
    selected_requirement_id = selected["requirement_id"]
    selected_requirement_ids = [selected_requirement_id] if selected_requirement_id else []

    return {
        "id": term.id,
        "description": term.description,
        "materiality": term.materiality,
        "source_document_id": term.source_document_id,
        "source_clause_ids": clause_ids,
        "requirement_ids": selected_requirement_ids,
        "candidate_requirement_ids": sorted(item.id for item in requirement_matches),
        "norm_ids": [item.id for item in selected["norms"]],
        "settlement_policy_ids": [item.id for item in selected["policies"]],
        "source_covered": source_covered,
        "atomic_requirement_covered": atomic_requirement_covered,
        "semantic_match": semantic_match,
        # Compatibility alias. Unlike qualification v2, found means complete
        # semantic fidelity for one atomic requirement, never aggregate clause overlap.
        "found": semantic_match,
        "numeric_mismatches": selected["numeric_mismatches"],
        "forbidden_numeric_values_found": selected["forbidden_numeric"],
        "numeric_literals": sorted(selected["numeric_literals"]),
        "missing_diagnostics": selected["missing_diagnostics"],
        "issues": issues,
    }


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
    critical = [item for item in terms if item["materiality"] in {"critical", "critical_financial"}]
    critical_found = [item for item in critical if item["semantic_match"]]
    source_covered = [item for item in critical if item["source_covered"]]
    requirement_covered = [item for item in critical if item["atomic_requirement_covered"]]
    numeric_faithful = [item for item in critical if not item["numeric_mismatches"]]
    automation_faithful = [
        item
        for item in critical
        if not any("automation mismatch" in issue for issue in item["issues"])
    ]
    numeric_mismatches = [
        {"id": item["id"], "values": item["numeric_mismatches"]}
        for item in terms
        if item["materiality"] in {"critical", "critical_financial"} and item["numeric_mismatches"]
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
    source_recall = 100.0 if not critical else len(source_covered) / len(critical) * 100
    requirement_recall = 100.0 if not critical else len(requirement_covered) / len(critical) * 100
    numeric_fidelity = 100.0 if not critical else len(numeric_faithful) / len(critical) * 100
    automation_fidelity = 100.0 if not critical else len(automation_faithful) / len(critical) * 100
    dangerous_term_failures = [
        {"id": item["id"], "issues": item["issues"]} for item in critical if item["issues"]
    ]
    hard_failures: list[dict[str, Any]] = []
    if unsupported_executable:
        hard_failures.append(
            {"code": "UNEXPECTED_EXECUTABLE_RULE", "items": unsupported_executable}
        )
    if ungrounded or ungrounded_policies:
        hard_failures.append(
            {
                "code": "UNGROUNDED_EXECUTABLE_SEMANTICS",
                "items": [*ungrounded, *ungrounded_policies],
            }
        )
    if dangerous_term_failures:
        hard_failures.append({"code": "CRITICAL_GOLD_MISMATCH", "items": dangerous_term_failures})

    metric_gate_passed = (
        assurance.hard_gate_passed
        and critical_recall == 100.0
        and not hard_failures
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
            "source_recall_percent": round(source_recall, 1),
            "atomic_requirement_recall_percent": round(requirement_recall, 1),
            "semantic_fidelity_percent": round(critical_recall, 1),
            "numeric_parameter_fidelity_percent": round(numeric_fidelity, 1),
            "automation_fidelity_percent": round(automation_fidelity, 1),
            "unsupported_executable_financial_rules": unsupported_executable,
            "critical_numeric_parameter_mismatches": numeric_mismatches,
            "silent_subjective_automation": silent_automation,
            "hard_failures": hard_failures,
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

    billed_total = sum(Decimal(item.billed_amount) for item in scenario_set.scenarios)
    payable_total = sum(Decimal(row["actual"]["payable"]) for row in rows)
    disputed_total = sum(Decimal(row["actual"]["disputed"]) for row in rows)
    review_total = sum(Decimal(row["actual"]["needs_review"]) for row in rows)
    conservation_passed = billed_total == payable_total + disputed_total + review_total
    metric_passed = all(row["passed"] for row in rows) and conservation_passed
    reviewed = scenario_set.review_status == "human_reviewed"
    passed = metric_passed and reviewed
    return {
        "available": True,
        "review_status": scenario_set.review_status,
        "metric_gate_passed": metric_passed,
        "conservation_passed": conservation_passed,
        "totals": {
            "billed": format(billed_total, "f"),
            "payable": format(payable_total, "f"),
            "disputed": format(disputed_total, "f"),
            "needs_review": format(review_total, "f"),
        },
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
