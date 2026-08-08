#!/usr/bin/env python3
"""End-to-end product smoke with no external model/network dependency."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

TOKEN = "product-smoke-workspace-key-32-characters"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="evidue-product-smoke-") as directory:
        os.environ["EVIDUE_PILOT_TOKEN"] = TOKEN
        os.environ["EVIDUE_PILOT_DB_PATH"] = str(Path(directory) / "product.db")
        os.environ.pop("EVIDUE_WORKSPACE_TOKENS", None)
        os.environ.pop("GEMINI_API_KEY", None)

        from app.main import app
        from fastapi.testclient import TestClient

        headers = {"Authorization": f"Bearer {TOKEN}"}
        with TestClient(app) as client:
            seeded = client.post("/api/pilot/sample/seed", headers=headers)
            seeded.raise_for_status()
            reconciliation = seeded.json()["reconciliation"]
            assert reconciliation["payable_outcomes"] == 1
            assert reconciliation["disputed_outcomes"] == 1
            assert reconciliation["needs_review_outcomes"] == 1

            details = client.get("/api/pilot/reconciliation", headers=headers)
            details.raise_for_status()
            disputed = next(
                row for row in details.json()["determinations"] if row["status"] == "disputed"
            )
            assert disputed["contract_clauses"]
            assert disputed["evidence"]

            run_id = reconciliation["reconciliation_id"]
            for kind in (
                "corrected-invoice.csv",
                "disputes.csv",
                "summary.json",
                "evidence.json",
                "review-report.html",
            ):
                response = client.get(
                    f"/api/pilot/reconciliations/{run_id}/exports/{kind}",
                    headers=headers,
                )
                response.raise_for_status()
                assert response.content

            overview = client.get("/api/pilot/product/overview", headers=headers)
            overview.raise_for_status()
            assert overview.json()["counts"]["vendors"] == 1

            reviews = client.get(
                "/api/pilot/product/review-cases",
                params={"run_id": run_id},
                headers=headers,
            )
            reviews.raise_for_status()
            review_items = reviews.json()["items"]
            assert len(review_items) == 1

            blocked = client.post(
                f"/api/pilot/product/reconciliations/{run_id}/approve",
                json={"approved_by": "smoke-finance"},
                headers=headers,
            )
            assert blocked.status_code == 409

            decision = client.post(
                f"/api/pilot/product/review-cases/{review_items[0]['id']}/decision",
                json={
                    "decision": "disputed",
                    "rationale": "Smoke test: unsupported evidence remains after review.",
                    "decided_by": "smoke-finance",
                },
                headers=headers,
            )
            decision.raise_for_status()

            approved = client.post(
                f"/api/pilot/product/reconciliations/{run_id}/approve",
                json={"approved_by": "smoke-finance", "note": "smoke approval"},
                headers=headers,
            )
            approved.raise_for_status()
            statement = approved.json()["statement"]
            assert statement["status"] == "approved"
            assert statement["kernel_input_manifest_hash"]
            assert statement["kernel_calculation_hash"]
            assert statement["calculation_hash"]

            dispute = client.post(
                f"/api/pilot/product/reconciliations/{run_id}/disputes",
                json={"created_by": "smoke-finance"},
                headers=headers,
            )
            dispute.raise_for_status()
            dispute_id = dispute.json()["id"]
            assert dispute.json()["item_count"] == 2

            ready = client.post(
                f"/api/pilot/product/disputes/{dispute_id}/transition",
                json={"status": "ready"},
                headers=headers,
            )
            ready.raise_for_status()
            pdf = client.get(
                f"/api/pilot/product/disputes/{dispute_id}/package.pdf",
                headers=headers,
            )
            pdf.raise_for_status()
            assert pdf.content.startswith(b"%PDF-1.4")

            audit = client.get("/api/pilot/audit-log", headers=headers)
            audit.raise_for_status()
            actions = {event["action"] for event in audit.json()["events"]}
            assert "reconciliation.completed" in actions
            assert "review_case.decided" in actions
            assert "reconciliation.approved" in actions
            assert "dispute_case.created" in actions

        print(
            json.dumps(
                {
                    "status": "ok",
                    "billed": reconciliation["submitted_amount"],
                    "machine_payable": reconciliation["confirmed_payable_amount"],
                    "machine_disputed": reconciliation["recommended_deduction"],
                    "machine_needs_review": reconciliation["needs_review_amount"],
                    "approved_payable": statement["recommended_final_payable_amount"],
                    "approved_disputed": statement["recommended_final_disputed_amount"],
                    "financial_authority": "approved_air",
                    "llm_required_for_reconciliation": False,
                    "finance_workflow": "review -> approval -> dispute",
                    "input_manifest_hash": reconciliation["input_manifest_hash"],
                    "kernel_calculation_hash": reconciliation["calculation_hash"],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
