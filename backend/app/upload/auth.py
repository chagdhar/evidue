"""Minimal pilot access control.

This is deliberately smaller than full customer identity/RBAC, but it prevents
public demo visitors from reading or mutating real pilot data.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def _configured_token() -> str:
    token = os.getenv("EVIDUE_PILOT_TOKEN", "").strip()
    if len(token) < 24:
        raise HTTPException(
            status_code=503,
            detail="Pilot access is disabled until EVIDUE_PILOT_TOKEN is configured.",
        )
    return token


def require_pilot_access(
    authorization: str | None = Header(default=None),
    x_evidue_pilot_token: str | None = Header(default=None),
) -> str:
    configured = _configured_token()
    supplied = x_evidue_pilot_token or ""
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not supplied or not hmac.compare_digest(supplied, configured):
        raise HTTPException(status_code=401, detail="Valid pilot access token required")
    return "operator"
