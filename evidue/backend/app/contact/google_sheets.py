import hashlib
import hmac
import json
import os
import ssl
import urllib.error
import urllib.request
from datetime import UTC, datetime
from urllib.parse import urlsplit

from app.api.schemas import ContactSubmissionRequest

ALLOWED_GOOGLE_DELIVERY_HOSTS = {"script.google.com", "script.googleusercontent.com"}
MAX_RESPONSE_BYTES = 16_384


def _validated_google_https_url(url: str, *, require_exec_path: bool = False) -> bool:
    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_GOOGLE_DELIVERY_HOSTS
        or parsed.username
        or parsed.password
        or port not in {None, 443}
        or parsed.fragment
    ):
        return False
    return not require_exec_path or (
        parsed.hostname == "script.google.com"
        and parsed.path.startswith("/macros/s/")
        and parsed.path.endswith("/exec")
        and not parsed.query
    )


class GoogleHttpsRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        if not _validated_google_https_url(new_url):
            raise urllib.error.URLError("Unsafe Google Apps Script redirect refused")
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


def _open_google_webhook(request: urllib.request.Request, timeout: int):
    tls_context = ssl.create_default_context()
    tls_context.minimum_version = ssl.TLSVersion.TLSv1_2
    tls_context.check_hostname = True
    tls_context.verify_mode = ssl.CERT_REQUIRED
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=tls_context),
        GoogleHttpsRedirectHandler(),
    )
    return opener.open(request, timeout=timeout)


def google_sheets_webhook_url() -> str | None:
    configured = os.getenv("EVIDUE_CONTACT_SHEET_WEBHOOK_URL", "").strip()
    if not configured:
        return None
    return configured if _validated_google_https_url(configured, require_exec_path=True) else None


def contact_sheet_secret() -> str | None:
    secret = os.getenv("EVIDUE_CONTACT_SHEET_SECRET", "").strip()
    return secret if len(secret) >= 32 else None


def contact_sheet_configured() -> bool:
    return google_sheets_webhook_url() is not None and contact_sheet_secret() is not None


def deliver_contact_submission(submission: ContactSubmissionRequest) -> None:
    webhook_url = google_sheets_webhook_url()
    secret = contact_sheet_secret()
    if webhook_url is None or secret is None:
        raise RuntimeError("Contact submission storage is not configured")

    payload = {
        "submitted_at": datetime.now(UTC).isoformat(),
        "submission_channel": "native_contact_form",
        **submission.model_dump(mode="json", exclude={"website"}),
    }
    serialized_payload = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    signature = hmac.new(
        secret.encode("utf-8"), serialized_payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    envelope = {"payload": serialized_payload, "signature": signature}
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps(envelope).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Evidue/0.1"},
        method="POST",
    )

    try:
        with _open_google_webhook(request, timeout=10) as response:
            response_body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(response_body) > MAX_RESPONSE_BYTES:
                raise RuntimeError("Contact submission storage returned an invalid response")
            result = json.loads(response_body.decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ssl.SSLError, json.JSONDecodeError) as exc:
        raise RuntimeError("Contact submission storage is temporarily unavailable") from exc

    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Contact submission storage rejected the request")
