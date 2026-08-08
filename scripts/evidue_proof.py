#!/usr/bin/env python3
"""Run Evidue's reproducible technical proof suite and emit a validation dossier.

Core mode is deliberately offline: it validates source integrity, source-span
provenance, qualification logic, controlled contract-to-dollar scenarios,
traceability, and product smoke without requiring any LLM credential.

Live mode adds pinned-provider contract compilation.  It never silently falls
back, because a benchmark is meaningless if different runs use different
providers without saying so.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts" / "validation"
CORE_QUALIFICATION = ARTIFACT_DIR / "synthetic-e2e.json"
SEC_QUALIFICATION = ARTIFACT_DIR / "sec-demandtec-target.json"
LIVE_SYNTHETIC_QUALIFICATION = ARTIFACT_DIR / "synthetic-e2e-live.json"


def _run(
    label: str,
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    required: bool = True,
) -> dict[str, Any]:
    merged = os.environ.copy()
    merged["PYTHONPATH"] = str(ROOT / "backend")
    if env:
        merged.update(env)
    started = datetime.now(UTC)
    proc = subprocess.run(
        command,
        cwd=ROOT,
        env=merged,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = proc.stdout.strip()
    status = "passed" if proc.returncode == 0 else ("failed" if required else "warning")
    print(f"[{status.upper():7}] {label}")
    if proc.returncode != 0 and output:
        print(output[-4000:])
    return {
        "label": label,
        "status": status,
        "required": required,
        "returncode": proc.returncode,
        "command": command,
        "started_at": started.isoformat(),
        "duration_seconds": round((datetime.now(UTC) - started).total_seconds(), 3),
        "output_tail": output[-12000:],
    }


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _controlled_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {"available": False}
    run = report.get("runs", [{}])[0]
    scenarios = run.get("financial_scenarios", {})
    return {
        "available": True,
        "qualification_passed": report.get("qualification_passed"),
        "gold_review_status": report.get("pack", {}).get("gold_review_status"),
        "critical_financial_term_recall_percent": run.get("critical_financial_term_recall_percent"),
        "hard_failures": run.get("hard_failures", []),
        "financial_scenarios_passed": scenarios.get("passed"),
        "financial_conservation_passed": scenarios.get("conservation_passed"),
        "financial_totals": scenarios.get("totals"),
        "financial_scenario_count": len(scenarios.get("scenarios", [])),
        "semantic_stability": report.get("semantic_stability"),
    }


def _sec_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {"available": False, "status": "not_measured"}
    run = report.get("runs", [{}])[0]
    return {
        "available": True,
        "qualification_passed": report.get("qualification_passed"),
        "qualification_status": run.get("qualification_status"),
        "gold_review_status": report.get("pack", {}).get("gold_review_status"),
        "critical_financial_term_recall_percent": run.get("critical_financial_term_recall_percent"),
        "hard_failures": run.get("hard_failures", []),
        "semantic_stability": report.get("semantic_stability"),
        "warning": (
            "DemandTec/Target gold is provisional engineering review, not legal review; "
            "this pack cannot establish release-level qualification yet."
        ),
    }


def _markdown(report: dict[str, Any]) -> str:
    steps = report["steps"]
    controlled = report["controlled_contract_to_dollar"]
    sec = report["real_contract_structural_qualification"]
    lines = [
        "# Evidue Validation Dossier — Generated",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Mode: `{report['mode']}`",
        "",
        "## Executive result",
        "",
        f"- Required checks passed: **{report['required_checks_passed']}**",
        f"- Required checks failed: **{report['required_checks_failed']}**",
        f"- Overall proof status: **{report['status']}**",
        "",
        "## Controlled contract → deterministic dollars",
        "",
    ]
    if controlled.get("available"):
        totals = controlled.get("financial_totals") or {}
        lines.extend(
            [
                f"- Qualification passed: **{controlled.get('qualification_passed')}**",
                f"- Gold status: `{controlled.get('gold_review_status')}`",
                (
                    "- Critical financial-term recall: "
                    f"**{controlled.get('critical_financial_term_recall_percent')}%**"
                ),
                f"- Hard safety failures: **{len(controlled.get('hard_failures', []))}**",
                f"- Financial scenarios: **{controlled.get('financial_scenario_count')}**",
                f"- Financial scenarios passed: **{controlled.get('financial_scenarios_passed')}**",
                f"- Conservation passed: **{controlled.get('financial_conservation_passed')}**",
                f"- Billed: **{totals.get('billed', 'NOT MEASURED')}**",
                f"- Payable: **{totals.get('payable', 'NOT MEASURED')}**",
                f"- Disputed: **{totals.get('disputed', 'NOT MEASURED')}**",
                f"- Needs review: **{totals.get('needs_review', 'NOT MEASURED')}**",
            ]
        )
    else:
        lines.append("- NOT MEASURED")

    lines.extend(["", "## Real executed-contract qualification", ""])
    if sec.get("available"):
        lines.extend(
            [
                "- Pack: DemandTec / Target SEC-filed executed agreement",
                f"- Qualification status: **{sec.get('qualification_status')}**",
                f"- Release qualification passed: **{sec.get('qualification_passed')}**",
                f"- Gold status: `{sec.get('gold_review_status')}`",
                (
                    "- Critical financial-term recall: "
                    f"**{sec.get('critical_financial_term_recall_percent')}%**"
                ),
                f"- Hard failures: **{len(sec.get('hard_failures', []))}**",
                f"- Caveat: {sec.get('warning')}",
            ]
        )
    else:
        lines.extend(
            [
                "- **NOT MEASURED in this run.**",
                (
                    "- The SEC artifact is transport-decoded and integrity-checked, "
                    "but a new live provider run is required because the earlier "
                    "gzip-corrupted run is invalid."
                ),
            ]
        )

    lines.extend(["", "## Checks", ""])
    for step in steps:
        marker = "PASS" if step["status"] == "passed" else step["status"].upper()
        lines.append(f"- **{marker}** — {step['label']} ({step['duration_seconds']}s)")

    lines.extend(
        [
            "",
            "## Claims this dossier does not make",
            "",
            "- It does not claim legal correctness of the provisional SEC gold.",
            "- It does not claim customer validation or recovered savings.",
            "- It does not treat synthetic scenarios as real customer data.",
            "- It does not treat semantic stability as correctness.",
            "- It does not allow an LLM to adjudicate invoice lines after AIR approval.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_report(mode: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    required_failures = [item for item in steps if item["required"] and item["status"] == "failed"]
    required_passes = [item for item in steps if item["required"] and item["status"] == "passed"]
    controlled = _controlled_summary(_load_json(CORE_QUALIFICATION))
    sec = _sec_summary(_load_json(SEC_QUALIFICATION))
    report = {
        "report_version": "evidue-proof-2",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "status": "passed" if not required_failures else "failed",
        "required_checks_passed": len(required_passes),
        "required_checks_failed": len(required_failures),
        "controlled_contract_to_dollar": controlled,
        "real_contract_structural_qualification": sec,
        "steps": steps,
        "limitations": [
            "SEC gold is provisional engineering gold, not legal review.",
            "Synthetic financial scenarios prove deterministic behavior, not customer demand.",
            "Live provider quality is only measured when live mode is explicitly run.",
        ],
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / "latest.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    (ARTIFACT_DIR / "latest.md").write_text(_markdown(report))
    return report


def _core_steps(*, full: bool) -> list[dict[str, Any]]:
    python = sys.executable
    steps: list[dict[str, Any]] = []

    # Syntax integrity is available even in minimal/offline environments.
    steps.append(
        _run(
            "Python syntax compilation",
            [python, "-m", "compileall", "-q", "backend/app", "scripts"],
        )
    )

    proof_tests = [
        "backend/tests/test_document_ingestion.py",
        "backend/tests/test_source_span_grounding.py",
        "backend/tests/test_providers.py",
        "backend/tests/test_compiler_consensus.py",
        "backend/tests/test_financial_impact.py",
        "backend/tests/test_traceability.py",
        "backend/tests/test_verification_readiness.py",
        "backend/tests/test_qualification.py",
        "backend/tests/test_native_generalization.py",
        "backend/tests/test_proofs.py",
        "backend/tests/test_upload.py::test_candidate_air_financial_impact_is_simulation_only",
        "backend/tests/test_upload.py::test_independent_compiler_disagreement_blocks_air_approval",
        "backend/tests/test_upload.py::test_historical_replay_is_non_persistent_analysis",
        "backend/tests/test_upload.py::test_historical_replay_rejects_stale_approved_air",
    ]
    steps.append(
        _run(
            "Verification-kernel tests",
            [python, "-m", "pytest", *proof_tests, "-q", "--tb=short"],
        )
    )

    steps.append(
        _run(
            "Controlled contract-to-dollar qualification",
            [
                python,
                "scripts/qualify_contract.py",
                "--pack",
                "qualification/fixtures/outcome-pricing-e2e",
                "--mode",
                "proposal",
                "--proposal",
                "qualification/fixtures/outcome-pricing-e2e/proposal.json",
                "--runs",
                "1",
                "--output",
                str(CORE_QUALIFICATION),
            ],
        )
    )

    steps.append(_run("Product smoke", [python, "scripts/product-smoke.py"]))

    # Ruff and frontend are required in full mode, advisory in core mode when
    # dependencies are absent.  This keeps core useful in offline inspection
    # environments while fresh development checkouts still get the full gate.
    if shutil.which("ruff"):
        steps.append(
            _run("Python format check", ["ruff", "format", "--check", "backend", "scripts"])
        )
        steps.append(_run("Python lint", ["ruff", "check", "backend", "scripts"]))
    elif full:
        steps.append(
            {
                "label": "Python Ruff checks",
                "status": "failed",
                "required": True,
                "returncode": 127,
                "command": ["ruff"],
                "started_at": datetime.now(UTC).isoformat(),
                "duration_seconds": 0.0,
                "output_tail": "ruff executable is unavailable",
            }
        )
    else:
        print("[WARNING] Ruff unavailable; static Ruff gate not measured in core mode")

    if full:
        steps.append(
            _run(
                "Complete backend tests",
                [python, "-m", "pytest", "backend/tests", "-q", "--tb=short"],
            )
        )
        if (ROOT / "frontend" / "node_modules").is_dir() and shutil.which("npm"):
            steps.extend(
                [
                    _run("Frontend lint", ["npm", "--prefix", "frontend", "run", "lint"]),
                    _run("Frontend tests", ["npm", "--prefix", "frontend", "test", "--", "--run"]),
                    _run("Frontend build", ["npm", "--prefix", "frontend", "run", "build"]),
                ]
            )
        else:
            steps.append(
                {
                    "label": "Frontend dependency gate",
                    "status": "failed",
                    "required": True,
                    "returncode": 127,
                    "command": ["npm"],
                    "started_at": datetime.now(UTC).isoformat(),
                    "duration_seconds": 0.0,
                    "output_tail": "frontend/node_modules or npm is unavailable",
                }
            )
    return steps


def _live_steps(provider: str, model: str | None) -> list[dict[str, Any]]:
    python = sys.executable
    common = ["--provider", provider]
    if model:
        common += ["--model", model]
    steps: list[dict[str, Any]] = []
    steps.append(
        _run(
            "Live controlled outcome-pricing qualification (3 runs + mutations)",
            [
                python,
                "scripts/qualify_contract.py",
                "--pack",
                "qualification/fixtures/outcome-pricing-e2e",
                "--mode",
                "live",
                *common,
                "--runs",
                "3",
                "--mutations",
                "--output",
                str(LIVE_SYNTHETIC_QUALIFICATION),
            ],
        )
    )
    steps.append(
        _run(
            "Live SEC executed-contract qualification",
            [
                python,
                "scripts/qualify_contract.py",
                "--pack",
                "qualification/downloaded/sec-demandtec-target-2010",
                "--mode",
                "live",
                *common,
                "--runs",
                "1",
                "--output",
                str(SEC_QUALIFICATION),
                "--exit-zero-on-review",
            ],
        )
    )
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Evidue's reproducible proof suite")
    parser.add_argument("mode", choices=["core", "live", "full"], nargs="?", default="core")
    parser.add_argument("--provider", default=os.getenv("EVIDUE_LLM_PRIMARY", "gemini"))
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, Any]] = []
    if args.mode in {"core", "full"}:
        steps.extend(_core_steps(full=args.mode == "full"))
    if args.mode in {"live", "full"}:
        steps.extend(_live_steps(args.provider, args.model))

    report = _write_report(args.mode, steps)
    print()
    print(f"Evidue proof status: {report['status'].upper()}")
    print(f"JSON: {ARTIFACT_DIR / 'latest.json'}")
    print(f"Markdown: {ARTIFACT_DIR / 'latest.md'}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
