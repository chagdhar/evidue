import csv
import io
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.schemas import (
    ContractCompileRequest,
    DataReadinessResponse,
    DataSourceSamplesResponse,
    DemoScenarioResponse,
    DemoStatusResponse,
    HealthResponse,
    OutcomeDetail,
    OutcomePage,
    ReconciliationSummary,
)
from app.db import repository


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.initialize()
    if not repository.demo_status()["seeded"]:
        repository.reset()
    yield


app = FastAPI(title="Evidue", version="0.1.0", lifespan=lifespan)


@app.get("/api/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/demo/scenarios", response_model=list[DemoScenarioResponse])
def demo_scenarios() -> list[dict[str, str]]:
    return repository.scenario_catalog()


@app.post("/api/demo/reset", response_model=DemoStatusResponse)
def reset(scenario_id: str = "headline") -> dict[str, object]:
    try:
        return repository.reset(scenario_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/demo/status", response_model=DemoStatusResponse)
def demo_status() -> dict[str, object]:
    return repository.demo_status()


@app.get("/api/data-readiness", response_model=DataReadinessResponse)
def data_readiness() -> dict[str, object]:
    return repository.data_readiness()


@app.get(
    "/api/data-sources/{source_id}/samples",
    response_model=DataSourceSamplesResponse,
)
def data_source_samples(
    source_id: str,
    limit: int = Query(5, ge=1, le=25),
    outcome_id: str | None = None,
) -> dict[str, object]:
    try:
        return repository.source_samples(source_id, limit, outcome_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/contracts/current")
def current_contract() -> dict[str, object]:
    try:
        return repository.contract()
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/contracts/current/compile")
def compile_contract(
    request: ContractCompileRequest | None = None,
    mode: str = Query("auto", pattern="^(auto|live|recorded)$"),
) -> dict[str, object]:
    try:
        return repository.compile_contract_rules(
            mode,
            contract_text=request.contract_text if request else None,
            source_document=request.source_document if request else None,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/contracts/current/compilations")
def contract_compilations() -> list[dict[str, object]]:
    return repository.list_compilations()


@app.post("/api/contracts/current/compilations/{compilation_id}/approve")
def approve_contract_compilation(compilation_id: str) -> dict[str, object]:
    try:
        return repository.approve_compilation(compilation_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/api/invoices/current")
def current_invoice() -> dict[str, object]:
    try:
        return repository.invoice()
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/reconciliations", response_model=ReconciliationSummary)
def reconcile() -> dict[str, object]:
    return repository.run_reconciliation()


@app.get("/api/reconciliations/current", response_model=ReconciliationSummary)
def current_reconciliation() -> dict[str, object]:
    if not repository.demo_status()["reconciled"]:
        raise HTTPException(404, "Reconciliation has not been run")
    return repository.summary()


@app.get("/api/reconciliations/current/outcomes", response_model=OutcomePage)
def outcomes(
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    status: str | None = None,
    reason: str | None = None,
    outcome_id: str | None = None,
    customer_id: str | None = None,
    intent: str | None = None,
    search: str | None = None,
) -> dict[str, object]:
    if not repository.demo_status()["reconciled"]:
        raise HTTPException(409, "Run reconciliation before requesting determinations")
    total, rows = repository.list_outcomes(
        offset, limit, status, reason, outcome_id, customer_id, intent, search
    )
    return {"total": total, "offset": offset, "limit": limit, "items": rows}


@app.get(
    "/api/reconciliations/current/outcomes/{outcome_id}",
    response_model=OutcomeDetail,
)
def outcome(outcome_id: str) -> dict[str, object]:
    detail = repository.outcome_detail(outcome_id)
    if detail is None:
        raise HTTPException(404, "Outcome not found")
    return detail


@app.get("/api/reconciliations/current/exports/disputes.csv")
def disputes_csv() -> Response:
    rows = repository.all_disputes()
    output = io.StringIO()
    fields = [
        "outcome_id",
        "customer_id",
        "intent",
        "vendor_claim",
        "status",
        "reason",
        "rule_id",
        "billed_amount",
        "confirmed_payable_amount",
        "confirmed_disputed_amount",
        "needs_review_amount",
        "closed_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row[field] for field in fields})
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=disputed-lines.csv"},
    )


@app.get("/api/reconciliations/current/exports/evidence.json")
def evidence_json() -> dict[str, object]:
    return repository.evidence_package()


@app.get("/api/reconciliations/current/exports/summary.json")
def summary_json() -> dict[str, object]:
    return repository.summary()


dist = Path(__file__).parents[2] / "frontend_dist"
if dist.exists():

    @app.get("/demo/lab", include_in_schema=False)
    @app.get("/demo/outcome-ledger", include_in_schema=False)
    @app.get("/demo/vendor-preflight", include_in_schema=False)
    @app.get("/demo/data-sources", include_in_schema=False)
    @app.get("/demo/disputes/current", include_in_schema=False)
    @app.get("/demo/contracts/current", include_in_schema=False)
    @app.get("/demo/invoices/current", include_in_schema=False)
    @app.get("/demo/invoices", include_in_schema=False)
    @app.get("/demo", include_in_schema=False)
    def demo_page() -> FileResponse:
        return FileResponse(dist / "index.html")

    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
