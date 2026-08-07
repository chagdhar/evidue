#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agreements.qualification import (  # noqa: E402
    QualificationDocument,
    QualificationManifest,
    QualificationPack,
    apply_mutation,
    compile_pack_live,
    compile_pack_proposal,
    load_document_text,
    load_pack,
    score_agreement,
    semantic_fingerprint,
    run_financial_scenarios,
)


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
                id=doc_id, title=path.name, path=str(path), precedence=index * 100
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


def _compile(pack: QualificationPack, args: argparse.Namespace, run_number: int):
    if args.mode == "live":
        if not os.getenv("GEMINI_API_KEY"):
            raise SystemExit(
                "GEMINI_API_KEY is required for --mode live. Configure it in the server/shell; "
                "do not place it in the qualification pack."
            )
        return compile_pack_live(pack, run_number=run_number)
    if not args.proposal:
        raise SystemExit("--proposal path/to/proposal.json is required for --mode proposal")
    payload = json.loads(Path(args.proposal).read_text())
    return compile_pack_proposal(pack, payload, run_number=run_number)


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
        "--runs", type=int, default=1, help="Repeat live compilation to test semantic stability"
    )
    parser.add_argument(
        "--mutations", action="store_true", help="Run material mutations declared in the pack"
    )
    parser.add_argument("--output", default="contract-qualification-report.json")
    args = parser.parse_args()

    if args.runs < 1 or args.runs > 10:
        raise SystemExit("--runs must be between 1 and 10")
    pack = load_pack(args.pack) if args.pack else _adhoc_pack(args)

    run_reports = []
    fingerprints: list[str] = []
    for run_number in range(1, args.runs + 1):
        agreement = _compile(pack, args, run_number)
        report = score_agreement(agreement, pack.gold)
        report["financial_scenarios"] = run_financial_scenarios(agreement, pack.scenarios)
        run_reports.append(report)
        fingerprints.append(semantic_fingerprint(agreement))

    stable = len(set(fingerprints)) == 1
    mutation_reports = []
    if args.mutations:
        for index, mutation in enumerate(pack.manifest.mutations, start=args.runs + 1):
            mutated = apply_mutation(pack, mutation)
            agreement = _compile(mutated, args, index)
            fingerprint = semantic_fingerprint(agreement)
            changed = fingerprint != fingerprints[0]
            mutation_reports.append(
                {
                    "id": mutation.id,
                    "financially_material": mutation.financially_material,
                    "semantic_policy_changed": changed,
                    "passed": changed if mutation.financially_material else True,
                    "fingerprint": fingerprint,
                }
            )

    report = {
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
        "runs": run_reports,
        "semantic_stability": {
            "runs": args.runs,
            "stable": stable,
            "fingerprints": fingerprints,
        },
        "mutations": mutation_reports,
    }
    qualification_passed = all(item.get("qualification_passed", False) for item in run_reports)
    if pack.scenarios is not None:
        qualification_passed = qualification_passed and all(
            item.get("financial_scenarios", {}).get("passed", False) for item in run_reports
        )
    if args.runs > 1:
        qualification_passed = qualification_passed and stable
    qualification_passed = qualification_passed and all(
        item.get("passed", False) for item in mutation_reports
    )
    report["qualification_passed"] = qualification_passed

    output = Path(args.output)
    output.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps({
        "pack": pack.manifest.id,
        "qualification_passed": qualification_passed,
        "semantic_stability": stable,
        "gold_available": pack.gold is not None,
        "financial_scenarios_available": pack.scenarios is not None,
        "report": str(output),
    }, indent=2))
    return 0 if qualification_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
