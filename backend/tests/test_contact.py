import asyncio
import hashlib
import hmac
import json
import urllib.error
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from app.api.schemas import ContactSubmissionRequest
from app.contact.google_sheets import (
    GoogleHttpsRedirectHandler,
    _validated_google_https_url,
    contact_sheet_configured,
    deliver_contact_submission,
    google_sheets_webhook_url,
)
from app.contact.protection import (
    enforce_contact_protection,
    release_contact_reservation,
    reset_contact_protection_for_tests,
)
from app.db import repository
from app.main import PUBLIC_CONTACT_ERROR, app
from fastapi import HTTPException
from starlette.requests import Request


def submission_payload(**overrides):
    payload = {
        "name": "Alex Buyer",
        "email": "alex@example.com",
        "company": "Acme Commerce",
        "role": "VP Finance",
        "discussion_type": "Product feedback",
        "billing_model": "",
        "verification_method": "",
        "evidence_location": "",
        "commercial_action": "",
        "feedback_area": "Try flow clarity",
        "message": "Evidence matching takes too long for the finance team.",
        "open_to_call": False,
        "confirmed_no_confidential_data": True,
        "attribution_source": "hacker_news",
        "campaign": "railway_beta",
        "demo_version": "hn_demo",
        "submission_id": str(uuid4()),
        "browser_session_id": str(uuid4()),
        "form_started_at": (datetime.now(UTC) - timedelta(seconds=5)).isoformat(),
        "website": "",
    }
    return {**payload, **overrides}


@pytest.fixture(autouse=True)
def configured_contact_sheet(monkeypatch):
    reset_contact_protection_for_tests()
    monkeypatch.setenv(
        "EVIDUE_CONTACT_SHEET_WEBHOOK_URL",
        "https://script.google.com/macros/s/DEPLOYMENT_ID/exec",
    )
    monkeypatch.setenv("EVIDUE_CONTACT_SHEET_SECRET", "s" * 32)


@pytest.fixture
def client():
    class Client:
        @staticmethod
        def request(method, path, **kwargs):
            async def send_request():
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(
                    transport=transport, base_url="https://evidue.test"
                ) as async_client:
                    return await async_client.request(method, path, **kwargs)

            return asyncio.run(send_request())

        def get(self, path, **kwargs):
            return self.request("GET", path, **kwargs)

        def post(self, path, **kwargs):
            return self.request("POST", path, **kwargs)

    return Client()


def test_contact_page_is_served_for_direct_access_and_refresh(monkeypatch, tmp_path, client):
    index = tmp_path / "index.html"
    index.write_text("<html><body>Evidue frontend entry</body></html>", encoding="utf-8")
    monkeypatch.setattr("app.main.dist", tmp_path)
    first = client.get("/contact")
    refresh = client.get("/contact")

    assert first.status_code == 200
    assert refresh.status_code == 200
    assert "Evidue frontend entry" in first.text


def test_contact_api_forwards_valid_submission(monkeypatch, client):
    captured = {}

    def fake_delivery(submission):
        captured.update(submission.model_dump(mode="json"))

    monkeypatch.setattr("app.main.deliver_contact_submission", fake_delivery)
    response = client.post("/api/contact-submissions", json=submission_payload())

    assert response.status_code == 201
    assert response.json() == {"accepted": True}
    assert captured["email"] == "alex@example.com"
    assert captured["confirmed_no_confidential_data"] is True
    assert captured["attribution_source"] == "hacker_news"


def test_contact_api_accepts_anonymous_product_feedback(monkeypatch, client):
    monkeypatch.setattr("app.main.deliver_contact_submission", lambda _submission: None)
    response = client.post(
        "/api/contact-submissions",
        json=submission_payload(name="", email="", company="", role=""),
    )
    assert response.status_code == 201


def test_contact_api_requires_high_signal_fields_for_invoice_review(monkeypatch, client):
    monkeypatch.setattr("app.main.deliver_contact_submission", lambda _submission: None)
    base = submission_payload(
        discussion_type="Invoice review",
        feedback_area="",
        billing_model="Per outcome",
        verification_method="Reconcile exports",
        evidence_location="Multiple customer systems",
        commercial_action="Request a credit",
    )
    assert client.post("/api/contact-submissions", json=base).status_code == 201

    for field in (
        "billing_model",
        "verification_method",
        "evidence_location",
        "commercial_action",
    ):
        invalid = {**base, field: "", "submission_id": str(uuid4())}
        assert client.post("/api/contact-submissions", json=invalid).status_code == 422


def test_contact_api_requires_email_when_open_to_call(client):
    response = client.post(
        "/api/contact-submissions",
        json=submission_payload(email="", open_to_call=True),
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "override",
    [
        {"website": "spam.example"},
        {"email": "not-an-email"},
        {"confirmed_no_confidential_data": False},
        {"confirmed_no_confidential_data": None},
        {"message": "short"},
        {"feedback_area": ""},
    ],
)
def test_contact_api_rejects_invalid_and_unconfirmed_submissions(override, client):
    response = client.post("/api/contact-submissions", json=submission_payload(**override))
    assert response.status_code == 422


def test_contact_api_rejects_implausibly_fast_submission(client):
    response = client.post(
        "/api/contact-submissions",
        json=submission_payload(form_started_at=datetime.now(UTC).isoformat()),
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "The form timing could not be verified."


def test_contact_api_sanitizes_storage_failure(monkeypatch, client):
    def fail_delivery(_submission):
        raise RuntimeError("private webhook rejected secret")

    monkeypatch.setattr("app.main.deliver_contact_submission", fail_delivery)
    response = client.post("/api/contact-submissions", json=submission_payload())

    assert response.status_code == 503
    assert response.json()["detail"] == PUBLIC_CONTACT_ERROR
    assert "webhook" not in response.text


def test_delivery_failures_do_not_consume_rate_limit(monkeypatch, client):
    delivery_attempts = {"count": 0}

    def fail_twice(_submission):
        delivery_attempts["count"] += 1
        if delivery_attempts["count"] <= 2:
            raise RuntimeError("temporary storage outage")

    monkeypatch.setattr("app.main.deliver_contact_submission", fail_twice)
    session_id = str(uuid4())
    payloads = [submission_payload(browser_session_id=session_id) for _ in range(3)]

    responses = [client.post("/api/contact-submissions", json=payload) for payload in payloads]

    assert [response.status_code for response in responses] == [503, 503, 201]


def test_contact_api_rejects_oversized_request_body(client):
    response = client.post(
        "/api/contact-submissions",
        content=json.dumps(submission_payload(message="x" * 30_000)),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_contact_api_limits_each_ip_to_five_submissions(monkeypatch, client):
    monkeypatch.setattr("app.main.deliver_contact_submission", lambda _submission: None)
    headers = {"X-Railway-Request-Id": "railway-request", "X-Real-IP": "8.8.8.8"}

    responses = [
        client.post("/api/contact-submissions", json=submission_payload(), headers=headers)
        for _ in range(6)
    ]

    assert [response.status_code for response in responses[:5]] == [201] * 5
    assert responses[5].status_code == 429


def test_contact_api_limits_browser_session_and_duplicate_ids(monkeypatch, client):
    monkeypatch.setattr("app.main.deliver_contact_submission", lambda _submission: None)
    session_id = str(uuid4())
    first_payload = submission_payload(browser_session_id=session_id)

    assert client.post("/api/contact-submissions", json=first_payload).status_code == 201
    assert client.post("/api/contact-submissions", json=first_payload).status_code == 429

    second = submission_payload(browser_session_id=session_id)
    third = submission_payload(browser_session_id=session_id)
    assert client.post("/api/contact-submissions", json=second).status_code == 201
    assert client.post("/api/contact-submissions", json=third).status_code == 429


def test_public_config_reports_contact_storage_without_exposing_secrets(client):
    response = client.get("/api/public-config")
    assert response.status_code == 200
    assert response.json()["contact_form_configured"] is True
    assert "secret" not in response.text.casefold()
    assert "webhook" not in response.text.casefold()


def test_google_sheet_configuration_accepts_only_deployed_apps_script_urls(monkeypatch):
    assert contact_sheet_configured() is True
    monkeypatch.setenv("EVIDUE_CONTACT_SHEET_WEBHOOK_URL", "https://example.com/collect")
    assert google_sheets_webhook_url() is None
    assert contact_sheet_configured() is False


def test_contact_protection_enforces_session_limit_without_trusting_forwarded_for():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/contact-submissions",
            "headers": [(b"x-real-ip", b"8.8.8.8")],
            "client": ("127.0.0.1", 1234),
            "scheme": "https",
            "server": ("evidue.test", 443),
            "query_string": b"",
        }
    )
    session_id = str(uuid4())
    submissions = [
        ContactSubmissionRequest.model_validate(submission_payload(browser_session_id=session_id))
        for _ in range(3)
    ]

    enforce_contact_protection(request, submissions[0])
    enforce_contact_protection(request, submissions[1])
    with pytest.raises(HTTPException) as error:
        enforce_contact_protection(request, submissions[2])
    assert error.value.status_code == 429


def test_released_delivery_reservations_restore_ip_and_session_capacity():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/contact-submissions",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "scheme": "https",
            "server": ("evidue.test", 443),
            "query_string": b"",
        }
    )
    session_id = str(uuid4())
    submissions = [
        ContactSubmissionRequest.model_validate(submission_payload(browser_session_id=session_id))
        for _ in range(3)
    ]

    for failed_submission in submissions[:2]:
        reservation = enforce_contact_protection(request, failed_submission)
        release_contact_reservation(reservation)

    assert enforce_contact_protection(request, submissions[2]) is not None


def test_google_sheet_delivery_is_signed_and_keeps_secret_server_side(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        @staticmethod
        def read(_size):
            return b'{"ok":true}'

    captured = {}

    def fake_open(request, timeout):
        captured["url"] = request.full_url
        captured["envelope"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Response()

    secret = "secret-value-that-is-at-least-32-chars"
    monkeypatch.setenv("EVIDUE_CONTACT_SHEET_SECRET", secret)
    monkeypatch.setattr("app.contact.google_sheets._open_google_webhook", fake_open)

    deliver_contact_submission(ContactSubmissionRequest.model_validate(submission_payload()))

    assert captured["url"].endswith("/exec")
    assert captured["timeout"] == 10
    assert "secret" not in captured["envelope"]
    serialized = captured["envelope"]["payload"]
    expected_signature = hmac.new(secret.encode(), serialized.encode(), hashlib.sha256).hexdigest()
    assert captured["envelope"]["signature"] == expected_signature
    payload = json.loads(serialized)
    assert payload["submission_channel"] == "native_contact_form"
    assert payload["campaign"] == "railway_beta"
    assert payload["role"] == "VP Finance"
    assert payload["feedback_area"] == "Try flow clarity"
    assert payload["open_to_call"] is False
    assert "website" not in payload


def test_google_delivery_refuses_tls_downgrades_and_untrusted_redirects():
    assert _validated_google_https_url("http://script.google.com/macros/s/ID/exec") is False
    assert _validated_google_https_url("https://evil.example/collect") is False
    assert (
        _validated_google_https_url("https://script.googleusercontent.com/result?token=1") is True
    )

    handler = GoogleHttpsRedirectHandler()
    with pytest.raises(urllib.error.URLError, match="Unsafe Google Apps Script redirect refused"):
        handler.redirect_request(None, None, 302, "Found", {}, "http://script.google.com/next")


def test_public_evidence_package_is_generated_lazily_and_cached(monkeypatch):
    monkeypatch.setattr(repository, "_public_evidence_package_cache", None)
    calls = {"disputes": 0}

    def disputes():
        calls["disputes"] += 1
        return [{"outcome_id": "OUT-1"}]

    monkeypatch.setattr(repository, "all_disputes", disputes)
    monkeypatch.setattr(repository, "summary", lambda: {"status": "completed"})
    monkeypatch.setattr(repository, "outcome_detail", lambda outcome_id: {"id": outcome_id})

    first = repository.evidence_package()
    second = repository.evidence_package()

    assert first is second
    assert calls["disputes"] == 1
