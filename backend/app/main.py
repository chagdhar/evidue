import csv
import io
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse, urlsplit

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from app.api.schemas import (
    ContractCompileRequest,
    DataReadinessResponse,
    DataSourceSamplesResponse,
    DemoScenarioResponse,
    DemoStatusResponse,
    HealthResponse,
    OutcomeDetail,
    OutcomePage,
    PublicConfigResponse,
    PublicOutcomeEvaluationResponse,
    PublicReconciliationSampleResponse,
    ReconciliationSummary,
    RecordedProposalValidationResponse,
)
from app.db import repository


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.initialize()
    if public_demo_enabled():
        repository.prepare_public_demo()
    elif not repository.demo_status()["seeded"]:
        repository.reset()
    yield


app = FastAPI(title="Evidue", version="0.1.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1024)

DEMO_INPUTS = {
    "contract": (
        "contract/acme-nova-outcome-pricing-order-form.txt",
        "evidue-demo-contract.txt",
        "text/plain",
    ),
    "invoice": (
        "vendor/june-claim-manifest.csv",
        "evidue-demo-vendor-invoice.csv",
        "text/csv",
    ),
    "support-events": (
        "customer/support-events.jsonl",
        "evidue-demo-support-events.jsonl",
        "application/x-ndjson",
    ),
    "payment-events": (
        "customer/payment-events.jsonl",
        "evidue-demo-payment-events.jsonl",
        "application/x-ndjson",
    ),
    "rule-proposal": (
        "contract/recorded-gemini-rule-proposal.json",
        "evidue-approved-rule-proposal.json",
        "application/json",
    ),
}
DEMO_DATA_ROOT = Path(__file__).parents[2] / "demo-data"

PUBLIC_DEMO_MESSAGE = (
    "Public technical preview: shared state is read-only, but selected rule validation "
    "and deterministic evaluations can be rerun safely."
)


def public_demo_enabled() -> bool:
    return os.getenv("EVIDUE_PUBLIC_DEMO", "false").strip().lower() in {"1", "true", "yes", "on"}


def ensure_mutation_allowed() -> None:
    if public_demo_enabled():
        raise HTTPException(status_code=403, detail=PUBLIC_DEMO_MESSAGE)


@app.middleware("http")
async def security_and_cache_headers(request, call_next):
    response = await call_next(request)
    posthog_host = os.getenv("POSTHOG_HOST", "").strip()
    connect_sources = ["'self'"]
    parsed_host = urlparse(posthog_host)
    if parsed_host.scheme == "https" and parsed_host.netloc:
        connect_sources.append(f"https://{parsed_host.netloc}")
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self' data:; connect-src "
        + " ".join(connect_sources)
        + "; base-uri 'self'; frame-ancestors 'none'; form-action 'self' mailto:"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "accelerometer=(), camera=(), geolocation=(), microphone=(), payment=(), usb=()"
    )
    if public_demo_enabled():
        if request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif request.url.path.startswith("/api/demo/inputs/"):
            response.headers["Cache-Control"] = "public, max-age=86400"
        elif request.url.path in {
            "/api/reconciliations/current",
            "/api/reconciliations/current/exports/evidence.json",
            "/api/reconciliations/current/exports/summary.json",
        }:
            response.headers["Cache-Control"] = "public, max-age=300"
    return response


@app.get("/api/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    return {"status": "ok"}


def beta_form_url() -> str | None:
    configured = os.getenv("EVIDUE_BETA_FORM_URL", "").strip()
    if not configured:
        return None
    parsed = urlsplit(configured)
    hostname = parsed.hostname.casefold() if parsed.hostname else ""
    try:
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username
        or parsed.password
        or (port not in {None, 443})
        or not (hostname == "tally.so" or hostname.endswith(".tally.so"))
    ):
        return None
    return configured


@app.get("/api/public-config", response_model=PublicConfigResponse)
def public_config() -> dict[str, object]:
    configured_url = beta_form_url()
    return {
        "beta_form_configured": configured_url is not None,
        "beta_form_url": configured_url,
    }


@app.get("/api/demo/scenarios", response_model=list[DemoScenarioResponse])
def demo_scenarios() -> list[dict[str, str]]:
    return repository.scenario_catalog()


@app.post("/api/demo/reset", response_model=DemoStatusResponse)
def reset(scenario_id: str = "headline") -> dict[str, object]:
    ensure_mutation_allowed()
    try:
        return {**repository.reset(scenario_id), "public_demo": public_demo_enabled()}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/demo/status", response_model=DemoStatusResponse)
def demo_status() -> dict[str, object]:
    return {**repository.demo_status(), "public_demo": public_demo_enabled()}


@app.get("/api/demo/inputs/{input_id}")
def demo_input(input_id: str) -> FileResponse:
    input_spec = DEMO_INPUTS.get(input_id)
    if input_spec is None:
        raise HTTPException(404, "Demo input not found")
    relative_path, filename, media_type = input_spec
    path = DEMO_DATA_ROOT / relative_path
    if not path.is_file():
        raise HTTPException(404, "Demo input is unavailable")
    return FileResponse(path, media_type=media_type, filename=filename)


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
    ensure_mutation_allowed()
    try:
        return repository.compile_contract_rules(
            mode,
            contract_text=request.contract_text if request else None,
            source_document=request.source_document if request else None,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post(
    "/api/public-demo/rules/validate",
    response_model=RecordedProposalValidationResponse,
)
def validate_public_rules() -> dict[str, object]:
    started_at = time.perf_counter()
    result = repository.validate_recorded_proposal()
    return {**result, "duration_ms": round((time.perf_counter() - started_at) * 1000)}


@app.post(
    "/api/public-demo/outcomes/{outcome_id}/evaluate",
    response_model=PublicOutcomeEvaluationResponse,
)
def evaluate_public_outcome(outcome_id: str) -> dict[str, object]:
    started_at = time.perf_counter()
    try:
        result = repository.public_outcome_evaluation(outcome_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {**result, "duration_ms": round((time.perf_counter() - started_at) * 1000)}


@app.post(
    "/api/public-demo/reconciliations/sample",
    response_model=PublicReconciliationSampleResponse,
)
def run_public_reconciliation_sample() -> dict[str, object]:
    started_at = time.perf_counter()
    result = repository.public_reconciliation_sample()
    return {**result, "duration_ms": round((time.perf_counter() - started_at) * 1000)}


@app.get("/api/contracts/current/compilations")
def contract_compilations() -> list[dict[str, object]]:
    return repository.list_compilations()


@app.post("/api/contracts/current/compilations/{compilation_id}/approve")
def approve_contract_compilation(compilation_id: str) -> dict[str, object]:
    ensure_mutation_allowed()
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
    ensure_mutation_allowed()
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
