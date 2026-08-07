import ipaddress
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock

from fastapi import HTTPException, Request

from app.api.schemas import ContactSubmissionRequest

RATE_WINDOW_SECONDS = 60 * 60
MAX_SUBMISSIONS_PER_IP = 5
MAX_SUBMISSIONS_PER_SESSION = 2
MIN_COMPLETION_SECONDS = 3
MAX_FORM_AGE_SECONDS = 24 * 60 * 60
RATE_LIMIT_MESSAGE = "Too many responses have been submitted. Please try again later."

_attempt_lock = Lock()
_ip_attempts: dict[str, deque[float]] = defaultdict(deque)
_session_attempts: dict[str, deque[float]] = defaultdict(deque)
_submission_ids: dict[str, float] = {}


@dataclass(frozen=True)
class ContactReservation:
    ip_key: str
    session_key: str
    submission_key: str
    attempt_timestamp: float


def _client_address(request: Request) -> str:
    railway_request_id = request.headers.get("x-railway-request-id", "").strip()
    railway_client = request.headers.get("x-real-ip", "").strip()
    if railway_request_id and railway_client:
        try:
            parsed = ipaddress.ip_address(railway_client)
            if parsed.is_global:
                return str(parsed)
        except ValueError:
            pass
    return request.client.host if request.client else "unknown"


def _prune(attempts: deque[float], now: float) -> None:
    cutoff = now - RATE_WINDOW_SECONDS
    while attempts and attempts[0] <= cutoff:
        attempts.popleft()


def enforce_contact_protection(
    request: Request, submission: ContactSubmissionRequest
) -> ContactReservation:
    if submission.form_started_at.utcoffset() is None:
        raise HTTPException(status_code=422, detail="The form timing could not be verified.")
    form_age = (datetime.now(UTC) - submission.form_started_at).total_seconds()
    if form_age < MIN_COMPLETION_SECONDS or form_age > MAX_FORM_AGE_SECONDS:
        raise HTTPException(status_code=422, detail="The form timing could not be verified.")

    now = time.monotonic()
    ip_key = _client_address(request)
    session_key = str(submission.browser_session_id)
    submission_key = str(submission.submission_id)
    with _attempt_lock:
        for attempt_store in (_ip_attempts, _session_attempts):
            for key, attempts in list(attempt_store.items()):
                _prune(attempts, now)
                if not attempts:
                    del attempt_store[key]
        expired_ids = [
            identifier
            for identifier, created_at in _submission_ids.items()
            if created_at <= now - RATE_WINDOW_SECONDS
        ]
        for identifier in expired_ids:
            del _submission_ids[identifier]

        if submission_key in _submission_ids:
            raise HTTPException(status_code=429, detail=RATE_LIMIT_MESSAGE)

        ip_attempts = _ip_attempts[ip_key]
        session_attempts = _session_attempts[session_key]
        if (
            len(ip_attempts) >= MAX_SUBMISSIONS_PER_IP
            or len(session_attempts) >= MAX_SUBMISSIONS_PER_SESSION
        ):
            raise HTTPException(status_code=429, detail=RATE_LIMIT_MESSAGE)

        ip_attempts.append(now)
        session_attempts.append(now)
        _submission_ids[submission_key] = now
        return ContactReservation(
            ip_key=ip_key,
            session_key=session_key,
            submission_key=submission_key,
            attempt_timestamp=now,
        )


def reset_contact_protection_for_tests() -> None:
    with _attempt_lock:
        _ip_attempts.clear()
        _session_attempts.clear()
        _submission_ids.clear()


def release_contact_reservation(reservation: ContactReservation) -> None:
    with _attempt_lock:
        if _submission_ids.get(reservation.submission_key) == reservation.attempt_timestamp:
            del _submission_ids[reservation.submission_key]

        for store, key in (
            (_ip_attempts, reservation.ip_key),
            (_session_attempts, reservation.session_key),
        ):
            attempts = store.get(key)
            if attempts is None:
                continue
            try:
                attempts.remove(reservation.attempt_timestamp)
            except ValueError:
                pass
            if not attempts:
                store.pop(key, None)
