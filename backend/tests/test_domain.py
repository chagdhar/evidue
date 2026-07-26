from decimal import Decimal

from app.domain.engine import summarize
from app.fixtures import demo_records, review_record


def test_exact_demo_totals_and_mutual_categories():
    s=summarize(demo_records()); assert s["claimed_outcomes"]==10000; assert s["payable_outcomes"]==8320; assert s["disputed_outcomes"]==1680; assert s["submitted_amount"]=="15000.00"; assert s["payable_amount"]=="12480.00"; assert s["recommended_deduction"]=="2520.00"; assert s["categories"]=={"R1":720,"R2":360,"R3":300,"R4":180,"R5":120}
def test_failed_refund_and_review_are_deterministic():
    record=next(x for x in demo_records() if x.claim.outcome_id=="OUT-004821"); assert record.status=="disputed" and record.rule_id=="R3" and record.payable_amount==Decimal("0.00"); assert review_record().status=="needs_review"
