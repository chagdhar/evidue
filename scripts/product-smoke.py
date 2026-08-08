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

            audit = client.get("/api/pilot/audit-log", headers=headers)
            audit.raise_for_status()
            assert any(
                event["action"] == "reconciliation.completed" for event in audit.json()["events"]
            )

        print(
            json.dumps(
                {
                    "status": "ok",
                    "billed": reconciliation["submitted_amount"],
                    "payable": reconciliation["confirmed_payable_amount"],
                    "disputed": reconciliation["recommended_deduction"],
                    "needs_review": reconciliation["needs_review_amount"],
                    "financial_authority": "approved_air",
                    "llm_required_for_reconciliation": False,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
