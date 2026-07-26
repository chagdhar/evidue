from app.main import health, outcome, outcomes, reconcile, summary_export


def test_api_golden_path_and_pagination():
    assert health() == {"status": "ok"}
    summary = reconcile()
    assert summary["payable_amount"] == "12480.00"
    page = outcomes(status="disputed", limit=3)
    assert page["total"] == 1680 and len(page["items"]) == 3
    detail = outcome("OUT-004821")
    assert detail["rule_id"] == "R3" and len(detail["timeline"]) == 4
    assert summary_export()["recommended_deduction"] == "2520.00"
