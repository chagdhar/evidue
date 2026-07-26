import csv
import io
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import repository as repo
from app.domain.models import RULES

app = FastAPI(title="Evidue")
def ensure():
    if not repo.exists(): repo.reset()
def row_view(r):
    return {**r, "evidence": json.loads(r["evidence"])}
@app.get("/api/health")
def health(): return {"status":"ok"}
@app.post("/api/demo/reset")
def reset(): return repo.reset()
@app.get("/api/demo/status")
def status(): return {"seeded":repo.exists(), "period":"2026-06-01 through 2026-06-30"}
@app.get("/api/contracts/current")
def contract(): return {"customer":"Acme Commerce","vendor":"Nova Support AI","period":"2026-06-01/2026-06-30","price_per_outcome":"1.50","rules":[r.__dict__ for r in RULES],"evidence_sources":["Nova Support AI agent log","Acme support desk","Payment processor","Order operations"]}
@app.get("/api/invoices/current")
def invoice(): return {"invoice_id":"INV-NOVA-2026-06","submitted_amount":"15000.00","claimed_outcomes":10000,"status":"submitted"}
@app.post("/api/reconciliations")
def reconcile(): return repo.reset()
@app.get("/api/reconciliations/current")
def current(): ensure(); return repo.summary()
@app.get("/api/reconciliations/current/outcomes")
def outcomes(offset:int=0,limit:int=50,status:str|None=None,search:str|None=None,reason:str|None=None):
    ensure(); limit=min(max(limit,1),100); total,rows=repo.list_rows(offset,limit,status,search,reason); return {"total":total,"offset":offset,"limit":limit,"items":[row_view(r) for r in rows]}
@app.get("/api/reconciliations/current/outcomes/{outcome_id}")
def outcome(outcome_id:str):
    ensure(); r=repo.get_row(outcome_id)
    if not r: raise HTTPException(404,"Outcome not found")
    response=row_view(r)
    if outcome_id == "OUT-004821": response["timeline"]=["AI agent initiates a refund","Payment processor rejects the refund","Contractual two-hour completion window expires","Human agent completes the refund later"]
    return response
@app.get("/api/reconciliations/current/exports/disputes.csv")
def disputes():
    ensure(); _, rows=repo.list_rows(0,10000,status="disputed"); out=io.StringIO(); writer=csv.DictWriter(out,fieldnames=["outcome_id","customer_id","intent","status","reason","rule_id","billed","payable","closed_at"]); writer.writeheader(); [writer.writerow({k:r[k] for k in writer.fieldnames}) for r in rows]; return Response(out.getvalue(),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=disputed-lines.csv"})
@app.get("/api/reconciliations/current/exports/evidence.json")
def evidence():
    ensure(); _, rows=repo.list_rows(0,10000); return [row_view(r) for r in rows]
@app.get("/api/reconciliations/current/exports/summary.json")
def summary_export(): ensure(); return repo.summary()
dist = Path(__file__).parents[2] / "frontend_dist"
if dist.exists():
    @app.get("/demo", include_in_schema=False)
    def demo_page():
        return FileResponse(dist / "index.html")

    app.mount("/", StaticFiles(directory=dist, html=True), name="demo")
