#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agreements.qualification import (
    QualificationDocument,
    QualificationManifest,
    QualificationPack,
    apply_mutation,
    compile_pack_live_result,
    compile_pack_proposal,
    load_document_text,
    load_pack,
    run_financial_scenarios,
    score_agreement,
)
from app.agreements.semantics import semantic_delta, semantic_fingerprint


def _adhoc_pack(args: argparse.Namespace) -> QualificationPack:
    documents: dict[str, tuple[str, str]] = {}
    manifest_docs: list[QualificationDocument] = []
    for index, raw in enumerate(args.document or [], start=1):
        if "=" in raw:
            doc_id, path_text = raw.split("=", 1)
        else:
            doc_id, path_text = f"DOC-{index}", raw
        path = Path(path_text).expanduser().resolve()
        documents[doc_id] = (path.name, load_document_text(path))
        manifest_docs.append(
            QualificationDocument(
                id=doc_id,
                title=path.name,
                path=str(path),
                precedence=index * 100,
            )
        )
    if not documents:
        raise SystemExit("Provide --pack or at least one --document DOC_ID=/path/to/contract")
    manifest = QualificationManifest(
        id=args.id or "adhoc-real-contract",
        title=args.title or "Ad hoc real contract qualification",
        contract_id=args.contract_id or "QUAL-ADHOC-CONTRACT",
        customer=args.customer or "Qualification customer",
        vendor=args.vendor or "Qualification vendor",
        documents=manifest_docs,
        source_class="user_supplied",
        source_notes=(
            "Ad hoc qualification run; no gold standard supplied unless converted to a pack."
        ),
    )
    return QualificationPack(
        root=Path.cwd(),
        manifest=manifest,
        documents=documents,
        gold=None,
        scenarios=None,
    )


def _compile(
    pack: QualificationPack,
    args: argparse.Namespace,
    run_number: int,
) -> tuple[Any, dict[str, Any]]:
    if args.mode == "live":
        try:
            result = compile_pack_live_result(
                pack,
                run_number=run_number,
                provider=args.provider,
                model=args.model,
            )
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
        return result.agreement, result.provenance

    if not args.proposal:
        raise SystemExit("--proposal path/to/proposal.json is required for --mode proposal")
    payload = json.loads(Path(args.proposal).read_text())
    agreement = compile_pack_proposal(pack, payload, run_number=run_number)
    return agreement, {
        "provider": "proposal-file",
        "model": payload.get("model"),
        "compiler_version": payload.get("compiler_version"),
        "proposal_path": str(Path(args.proposal).resolve()),
    }


def _mutation_result(
    baseline: Any,
    mutated: Any,
    mutation: Any,
) -> dict[str, Any]:
    delta = semantic_delta(baseline, mutated)
    changed = set(delta["changed_sections"])
    expected_changed = set(mutation.expected_changed_sections)
    expected_unchanged = set(mutation.expected_unchanged_sections)

    issues: list[str] = []
    missing_changes = sorted(expected_changed - changed)
    collateral_changes = sorted(expected_unchanged & changed)
    if missing_changes:
        issues.append("expected semantic section(s) did not change: " + ", ".join(missing_changes))
    if collateral_changes:
        issues.append("unexpected collateral semantic change: " + ", ".join(collateral_changes))
    if mutation.financially_material and not changed:
        issues.append("financially material mutation produced no semantic delta")

    return {
        "id": mutation.id,
        "financially_material": mutation.financially_material,
        "expected_changed_sections": sorted(expected_changed),
        "expected_unchanged_sections": sorted(expected_unchanged),
        "semantic_delta": delta,
        "passed": not issues,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Qualify Evidue contract compilation against real contract documents."
    )
    parser.add_argument("--pack", help="Qualification pack directory containing manifest.json")
    parser.add_argument(
        "--document",
        action="append",
        help="Ad hoc document as DOC_ID=/path/to/file (repeat for multi-document agreements)",
    )
    parser.add_argument("--id")
    parser.add_argument("--title")
    parser.add_argument("--contract-id")
    parser.add_argument("--customer")
    parser.add_argument("--vendor")
    parser.add_argument("--mode", choices=["live", "proposal"], default="live")
    parser.add_argument(
        "--proposal", help="Recorded/manual proposal used only for offline harness tests"
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="Pin live qualification to this provider (for example gemini or openai)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Pin live qualification to an explicit provider model",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Repeat live compilation to test semantic stability",
    )
    parser.add_argument(
        "--mutations",
        action="store_true",
        help="Run material mutations declared in the pack",
    )
    parser.add_argument("--output", default="contract-qualification-report.json")
    parser.add_argument(
        "--exit-zero-on-review",
        action="store_true",
        help="Return exit 0 when execution succeeds but qualification remains review-required",
    )
    args = parser.parse_args()

    if args.runs < 1 or args.runs > 10:
        raise SystemExit("--runs must be between 1 and 10")
    pack = load_pack(args.pack) if args.pack else _adhoc_pack(args)

    run_reports: list[dict[str, Any]] = []
    agreements: list[Any] = []
    fingerprints: list[str] = []
    for run_number in range(1, args.runs + 1):
        agreement, provenance = _compile(pack, args, run_number)
        agreements.append(agreement)
        report = score_agreement(agreement, pack.gold)
        report["provenance"] = provenance
        report["financial_scenarios"] = run_financial_scenarios(agreement, pack.scenarios)
        run_reports.append(report)
        fingerprints.append(semantic_fingerprint(agreement))

    if args.runs < 2:
        stability: dict[str, Any] = {
            "status": "insufficient_runs",
            "runs": args.runs,
            "stable": None,
            "fingerprints": fingerprints,
            "materially_unstable": None,
        }
        stable_gate = True
    else:
        stable = len(set(fingerprints)) == 1
        stability = {
            "status": "stable" if stable else "unstable",
            "runs": args.runs,
            "stable": stable,
            "fingerprints": fingerprints,
            "materially_unstable": not stable,
        }
        stable_gate = stable

    mutation_reports: list[dict[str, Any]] = []
    if args.mutations:
        baseline = agreements[0]
        for index, mutation in enumerate(pack.manifest.mutations, start=args.runs + 1):
            mutated_pack = apply_mutation(pack, mutation)
            mutated_agreement, mutation_provenance = _compile(mutated_pack, args, index)
            mutation_report = _mutation_result(baseline, mutated_agreement, mutation)
            mutation_report["provenance"] = mutation_provenance
            mutation_reports.append(mutation_report)

    report = {
        "report_version": "qualification-v2",
        "pack": {
            "id": pack.manifest.id,
            "title": pack.manifest.title,
            "source_class": pack.manifest.source_class,
            "documents": [item.model_dump(mode="json") for item in pack.manifest.documents],
            "gold_review_status": pack.gold.review_status if pack.gold else None,
            "financial_scenario_review_status": (
                pack.scenarios.review_status if pack.scenarios else None
            ),
        },
        "mode": args.mode,
        "provider_pin": args.provider,
        "model_pin": args.model,
        "runs": run_reports,
        "semantic_stability": stability,
        "mutations": mutation_reports,
    }
    qualification_passed = all(item.get("qualification_passed", False) for item in run_reports)
    if pack.scenarios is not None:
        qualification_passed = qualification_passed and all(
            item.get("financial_scenarios", {}).get("passed", False) for item in run_reports
        )
    qualification_passed = qualification_passed and stable_gate
    qualification_passed = qualification_passed and all(
        item.get("passed", False) for item in mutation_reports
    )
    report["qualification_passed"] = qualification_passed

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(
        json.dumps(
            {
                "pack": pack.manifest.id,
                "qualification_passed": qualification_passed,
                "semantic_stability": stability["status"],
                "gold_available": pack.gold is not None,
                "gold_review_status": pack.gold.review_status if pack.gold else None,
                "financial_scenarios_available": pack.scenarios is not None,
                "mutation_count": len(mutation_reports),
                "report": str(output),
            },
            indent=2,
        )
    )

    if qualification_passed:
        return 0
    if args.exit_zero_on_review and all(
        item.get("qualification_status") == "review_required" for item in run_reports
    ):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
