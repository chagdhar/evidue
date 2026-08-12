import csv
import hashlib
import io
import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse, urlsplit

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from app.api.schemas import (
    ContactSubmissionRequest,
    ContactSubmissionResponse,
    ContractCompileRequest,
    DataReadinessResponse,
    DataSourceSamplesResponse,
    HealthResponse,
    OutcomeDetail,
    OutcomePage,
    PublicConfigResponse,
    ReconciliationSummary,
)
from app.contact.body_limit import ContactBodyLimitMiddleware
from app.contact.google_sheets import contact_sheet_configured, deliver_contact_submission
from app.contact.protection import enforce_contact_protection, release_contact_reservation
from app.contracts.compiler import (
    DEFAULT_CONTRACT_PATH,
    compile_with_gemini,
    load_recorded_proposal,
    to_rule_program,
)
from app.db import repository
from app.domain.models import RuleProgram
from app.product.router import router as product_router
from app.upload.pilot_db import initialize_pilot_database
from app.upload.router import router as pilot_router

logger = logging.getLogger(__name__)
MAX_CONTACT_REQUEST_BYTES = 24 * 1024
PUBLIC_CONTACT_ERROR = (
    "Your response could not be submitted right now. Please try again in a moment."
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.initialize()
    initialize_pilot_database()
    if public_demo_enabled():
        repository.prepare_public_demo()
    elif not repository.demo_status()["seeded"]:
        repository.reset()
    yield


app = FastAPI(title="Evidue", version="0.1.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(ContactBodyLimitMiddleware, max_bytes=MAX_CONTACT_REQUEST_BYTES)
app.include_router(pilot_router)
app.include_router(product_router)

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

PUBLIC_TRY_LIVE_WINDOW_SECONDS = 7 * 24 * 60 * 60
PUBLIC_TRY_SESSION_SECONDS = 30 * 60
_public_try_live_usage: dict[str, float] = {}
_public_try_sessions: dict[str, tuple[float, str, RuleProgram, dict[str, object]]] = {}
_public_try_lock = threading.Lock()


def _public_try_client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    host = forwarded or (request.client.host if request.client else "unknown")
    return hashlib.sha256(host.encode("utf-8")).hexdigest()


def _public_try_cleanup(now: float) -> None:
    expired = [
        session_id
        for session_id, (created_at, _client_key, _program, _meta) in _public_try_sessions.items()
        if now - created_at > PUBLIC_TRY_SESSION_SECONDS
    ]
    for session_id in expired:
        _public_try_sessions.pop(session_id, None)


def _public_try_rules(proposal) -> list[dict[str, object]]:
    return [
        {
            "id": rule.id,
            "title": rule.title,
            "description": rule.description,
            "clause_text": rule.clause_text,
            "operation": rule.operation,
            "evidence_required": list(rule.evidence_required),
            "consequence": rule.consequence,
            "priority": rule.priority,
        }
        for rule in sorted(proposal.rules, key=lambda item: item.priority)
    ]


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
        + "; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "accelerometer=(), camera=(), geolocation=(), microphone=(), payment=(), usb=()"
    )
    if public_demo_enabled():
        if request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
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


def talk_booking_url() -> str | None:
    configured = os.getenv("EVIDUE_TALK_BOOKING_URL", "").strip()
    if not configured:
        return None
    parsed = urlsplit(configured)
    try:
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or port not in {None, 443}
        or parsed.fragment
    ):
        return None
    return configured


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
        "contact_form_configured": contact_sheet_configured(),
        "talk_booking_url": talk_booking_url(),
    }


@app.post("/api/contact-submissions", response_model=ContactSubmissionResponse, status_code=201)
def create_contact_submission(
    submission: ContactSubmissionRequest, request: Request
) -> dict[str, bool]:
    if not contact_sheet_configured():
        raise HTTPException(status_code=503, detail=PUBLIC_CONTACT_ERROR)
    reservation = enforce_contact_protection(request, submission)
    try:
        deliver_contact_submission(submission)
    except RuntimeError as exc:
        release_contact_reservation(reservation)
        error_id = uuid.uuid4().hex
        logger.warning("Contact delivery failed error_id=%s reason=%s", error_id, exc)
        raise HTTPException(status_code=503, detail=PUBLIC_CONTACT_ERROR) from exc
    return {"accepted": True}


def demo_scenarios() -> list[dict[str, str]]:
    """Internal synthetic-fixture catalog; not exposed as a public HTTP surface."""
    return repository.scenario_catalog()


def reset(scenario_id: str = "headline") -> dict[str, object]:
    """Reset deterministic fixtures for tests/local setup; not a public HTTP surface."""
    ensure_mutation_allowed()
    try:
        return {**repository.reset(scenario_id), "public_demo": public_demo_enabled()}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def demo_status() -> dict[str, object]:
    """Return internal fixture state for tests/setup; not a public HTTP surface."""
    return {**repository.demo_status(), "public_demo": public_demo_enabled()}


def demo_input(input_id: str) -> FileResponse:
    """Resolve an internal deterministic fixture file; not a public HTTP surface."""
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


def validate_public_rules() -> dict[str, object]:
    """Validate the recorded fixture proposal internally; not a public HTTP surface."""
    started_at = time.perf_counter()
    result = repository.validate_recorded_proposal()
    return {**result, "duration_ms": round((time.perf_counter() - started_at) * 1000)}


def evaluate_public_outcome(outcome_id: str) -> dict[str, object]:
    """Evaluate one fixture outcome internally; not a public HTTP surface."""
    started_at = time.perf_counter()
    try:
        result = repository.public_outcome_evaluation(outcome_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {**result, "duration_ms": round((time.perf_counter() - started_at) * 1000)}


def run_public_reconciliation_sample() -> dict[str, object]:
    """Run the deterministic fixture sample internally; not a public HTTP surface."""
    started_at = time.perf_counter()
    result = repository.public_reconciliation_sample()
    return {**result, "duration_ms": round((time.perf_counter() - started_at) * 1000)}


@app.post("/api/public-try/analyze")
def analyze_public_try(request: Request) -> dict[str, object]:
    """Compile the bundled synthetic contract without mutating authoritative state.

    A visitor gets at most one live Gemini compilation per network per seven days.
    Additional runs replay the validated recorded Gemini proposal so the deterministic
    part of the public proof remains available without signup or API-cost abuse.
    """
    started_at = time.perf_counter()
    client_key = _public_try_client_key(request)
    now = time.time()
    contract_text = DEFAULT_CONTRACT_PATH.read_text()
    model_configured = bool(os.getenv("GEMINI_API_KEY"))
    with _public_try_lock:
        _public_try_cleanup(now)
        last_live = _public_try_live_usage.get(client_key)
        live_available = model_configured and (
            last_live is None or now - last_live >= PUBLIC_TRY_LIVE_WINDOW_SECONDS
        )
        if live_available:
            # Reserve before making the request so concurrent clicks cannot fan out model calls.
            _public_try_live_usage[client_key] = now

    fallback_reason: str | None = None
    if live_available:
        try:
            result = compile_with_gemini(
                contract_text,
                "CONTRACT-ACME-NOVA-2026",
                "Acme-Nova-Outcome-Pricing-Order-Form.pdf",
            )
            mode = "live_gemini"
        except (RuntimeError, ValueError) as exc:
            fallback_reason = (
                f"Live compiler unavailable; replaying the validated recorded proposal: {exc}"
            )
            result = load_recorded_proposal(contract_text)
            mode = "recorded_replay"
    else:
        result = load_recorded_proposal(contract_text)
        mode = "recorded_replay"
        if not model_configured:
            fallback_reason = "Live Gemini is not configured on this deployment."
        else:
            fallback_reason = "This network already used its weekly live compiler run."

    session_id = f"TRY-{uuid.uuid4().hex[:16].upper()}"
    approval_ready = bool(result.proposal.approval_ready)
    program: RuleProgram | None = None
    if approval_ready:
        program = to_rule_program(
            result.proposal,
            compilation_id=session_id,
            version=1,
            source_hash=result.source_hash,
        )
        metadata: dict[str, object] = {
            "mode": mode,
            "live_model_call": bool(result.live_model_call),
            "compiler_version": result.proposal.compiler_version,
            "model": result.proposal.model,
            "source_hash": result.source_hash,
        }
        with _public_try_lock:
            _public_try_sessions[session_id] = (now, client_key, program, metadata)

    return {
        "sandbox_id": session_id if program else None,
        "contract_text": contract_text,
        "contract_id": result.proposal.contract_id,
        "source_document": result.proposal.source_document,
        "source_hash": result.source_hash,
        "mode": mode,
        "live_model_call": bool(result.live_model_call),
        "model": result.proposal.model,
        "compiler_version": result.proposal.compiler_version,
        "approval_required": True,
        "approval_ready": approval_ready,
        "rules": _public_try_rules(result.proposal),
        "diagnostics": [item.model_dump(mode="json") for item in result.proposal.diagnostics],
        "fallback_reason": fallback_reason,
        "session_expires_in_seconds": PUBLIC_TRY_SESSION_SECONDS,
        "duration_ms": round((time.perf_counter() - started_at) * 1000),
    }


@app.post("/api/public-try/{sandbox_id}/approve-and-reconcile")
def approve_public_try(sandbox_id: str, request: Request) -> dict[str, object]:
    """Record explicit human approval and run the deterministic engine in memory."""
    started_at = time.perf_counter()
    client_key = _public_try_client_key(request)
    now = time.time()
    with _public_try_lock:
        _public_try_cleanup(now)
        entry = _public_try_sessions.get(sandbox_id)
    if entry is None:
        raise HTTPException(404, "This Try Evidue session expired. Analyze the contract again.")
    _created_at, owner_key, program, metadata = entry
    if owner_key != client_key:
        raise HTTPException(403, "This Try Evidue session belongs to another browser network.")
    result = repository.public_reconciliation_sample(program=program)
    return {
        **result,
        "sandbox_id": sandbox_id,
        "human_approval_recorded": True,
        "compiler_mode": metadata["mode"],
        "live_model_call": metadata["live_model_call"],
        "duration_ms": round((time.perf_counter() - started_at) * 1000),
    }


@app.get("/api/public-try/{sandbox_id}/outcomes/{outcome_id}")
def inspect_public_try_outcome(
    sandbox_id: str, outcome_id: str, request: Request
) -> dict[str, object]:
    """Return one representative claim audit using the visitor-approved rule program."""
    client_key = _public_try_client_key(request)
    now = time.time()
    with _public_try_lock:
        _public_try_cleanup(now)
        entry = _public_try_sessions.get(sandbox_id)
    if entry is None:
        raise HTTPException(404, "This Try Evidue session expired. Analyze the contract again.")
    _created_at, owner_key, program, _metadata = entry
    if owner_key != client_key:
        raise HTTPException(403, "This Try Evidue session belongs to another browser network.")

    sample = repository.public_reconciliation_sample(program=program)
    allowed_outcomes = {str(finding["outcome_id"]) for finding in sample["representative_findings"]}
    if outcome_id not in allowed_outcomes:
        raise HTTPException(
            404, "Only representative findings from this Try Evidue run can be inspected."
        )
    try:
        return repository.public_try_outcome_inspection(outcome_id, program=program)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


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


@app.head("/", include_in_schema=False)
@app.get("/", include_in_schema=False)
@app.head("/contact", include_in_schema=False)
@app.get("/contact", include_in_schema=False)
@app.head("/try", include_in_schema=False)
@app.get("/try", include_in_schema=False)
@app.get("/workspace", include_in_schema=False)
@app.get("/workspace/invoices", include_in_schema=False)
@app.get("/workspace/invoices/current", include_in_schema=False)
@app.get("/workspace/invoices/{invoice_id}", include_in_schema=False)
@app.get("/workspace/review", include_in_schema=False)
@app.get("/workspace/vendors", include_in_schema=False)
@app.get("/workspace/settings", include_in_schema=False)
@app.get("/workspace/operations", include_in_schema=False)
@app.get("/pilot", include_in_schema=False)
@app.get("/pilot/config", include_in_schema=False)
@app.get("/pilot/finance", include_in_schema=False)
@app.get("/pilot/operations", include_in_schema=False)
def frontend_page(invoice_id: str | None = None) -> FileResponse:
    index_path = dist / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="Frontend build is unavailable")
    return FileResponse(index_path)


if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
