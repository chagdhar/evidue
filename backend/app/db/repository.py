import json
from pathlib import Path

from sqlalchemy import create_engine, text

from app.fixtures.demo import demo_records, events_for

DB_PATH = Path(__file__).parents[3] / "data" / "evidue.db"
engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
def initialize():
    DB_PATH.parent.mkdir(exist_ok=True)
    with engine.begin() as c:
        c.execute(text("CREATE TABLE IF NOT EXISTS determinations (outcome_id TEXT PRIMARY KEY, customer_id TEXT, intent TEXT, status TEXT, reason TEXT, rule_id TEXT, billed TEXT, payable TEXT, closed_at TEXT, evidence TEXT)"))
def reset():
    initialize(); records = demo_records()
    with engine.begin() as c:
        c.execute(text("DELETE FROM determinations"))
        category = {"R1":"recontact","R2":"human","R3":"downstream","R4":"duplicate","R5":"mismatch"}
        c.execute(text("INSERT INTO determinations VALUES (:outcome_id,:customer_id,:intent,:status,:reason,:rule_id,:billed,:payable,:closed_at,:evidence)"), [{"outcome_id":d.claim.outcome_id,"customer_id":d.claim.customer_id,"intent":d.claim.intent,"status":d.status,"reason":d.reason,"rule_id":d.rule_id,"billed":f"{d.claim.billed_amount:.2f}","payable":f"{d.payable_amount:.2f}","closed_at":d.claim.closed_at.isoformat(),"evidence":json.dumps([{"id":e.id,"source_system":e.source_system,"source_record_id":e.source_record_id,"event_type":e.event_type,"timestamp":e.timestamp.isoformat(),"customer_id":e.customer_id,"outcome_id":e.outcome_id,"values":e.values,"ingested_at":e.ingested_at.isoformat()} for e in events_for(d.claim, category.get(d.rule_id))])} for d in records])
    return summary()
def exists():
    initialize()
    with engine.connect() as c: return c.execute(text("SELECT count(*) FROM determinations")).scalar_one() > 0
def summary():
    with engine.connect() as c:
        rows = c.execute(text("SELECT status,rule_id,billed,payable FROM determinations")).mappings().all()
    from decimal import Decimal
    categories = {}; billed = Decimal(); payable = Decimal()
    for r in rows:
        billed += Decimal(r["billed"]); payable += Decimal(r["payable"])
        if r["status"] == "disputed": categories[r["rule_id"]] = categories.get(r["rule_id"], 0)+1
    return {"claimed_outcomes":len(rows),"payable_outcomes":sum(r["status"]=="payable" for r in rows),"disputed_outcomes":sum(r["status"]=="disputed" for r in rows),"needs_review_outcomes":sum(r["status"]=="needs_review" for r in rows),"submitted_amount":f"{billed:.2f}","payable_amount":f"{payable:.2f}","recommended_deduction":f"{billed-payable:.2f}","categories":categories,"synthetic_disclosure":"Operationally realistic data generated deterministically. No real customer or vendor data is shown."}
def list_rows(offset=0, limit=50, status=None, search=None, reason=None):
    clauses=[]; params={"limit":limit,"offset":offset}
    if status: clauses.append("status=:status"); params["status"]=status
    if reason: clauses.append("rule_id=:reason"); params["reason"]=reason
    if search: clauses.append("(outcome_id LIKE :search OR customer_id LIKE :search OR intent LIKE :search)"); params["search"]=f"%{search}%"
    where = " WHERE "+" AND ".join(clauses) if clauses else ""
    with engine.connect() as c:
        total=c.execute(text("SELECT count(*) FROM determinations"+where),params).scalar_one(); rows=c.execute(text("SELECT * FROM determinations"+where+" ORDER BY outcome_id LIMIT :limit OFFSET :offset"),params).mappings().all()
    return total,[dict(r) for r in rows]
def get_row(outcome_id):
    with engine.connect() as c: r=c.execute(text("SELECT * FROM determinations WHERE outcome_id=:id"),{"id":outcome_id}).mappings().first()
    return dict(r) if r else None
