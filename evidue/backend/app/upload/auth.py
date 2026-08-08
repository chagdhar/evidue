"""Workspace-scoped access control for real customer/product data.

The public demo remains separate.  Each configured workspace token selects an
isolated SQLite database through a request-local ContextVar.  Legacy
``EVIDUE_PILOT_TOKEN`` deployments continue to work as the ``default``
workspace.
"""

from __future__ import annotations

import hmac
import json
import os
import re
from collections.abc import AsyncGenerator
from contextvars import ContextVar, Token
from dataclasses import dataclass

from fastapi import Header, HTTPException

_SAFE_WORKSPACE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")
_current_workspace: ContextVar[str] = ContextVar("evidue_workspace", default="default")
_current_actor: ContextVar[str] = ContextVar("evidue_actor", default="operator")


@dataclass(frozen=True)
class PilotPrincipal:
    workspace_id: str
    actor: str = "operator"


def current_workspace_id() -> str:
    return _current_workspace.get()


def current_actor() -> str:
    return _current_actor.get()


def set_workspace_context(
    workspace_id: str, actor: str = "operator"
) -> tuple[Token[str], Token[str]]:
    return _current_workspace.set(workspace_id), _current_actor.set(actor)


def reset_workspace_context(tokens: tuple[Token[str], Token[str]]) -> None:
    workspace_token, actor_token = tokens
    _current_workspace.reset(workspace_token)
    _current_actor.reset(actor_token)


def _workspace_tokens() -> dict[str, str]:
    configured = os.getenv("EVIDUE_WORKSPACE_TOKENS", "").strip()
    if configured:
        try:
            payload = json.loads(configured)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=503,
                detail="EVIDUE_WORKSPACE_TOKENS is not valid JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=503,
                detail="EVIDUE_WORKSPACE_TOKENS must be a JSON object of workspace -> token.",
            )
        tokens: dict[str, str] = {}
        for workspace, token in payload.items():
            if not isinstance(workspace, str) or not _SAFE_WORKSPACE.fullmatch(workspace):
                raise HTTPException(status_code=503, detail="A configured workspace ID is invalid.")
            if not isinstance(token, str) or len(token.strip()) < 24:
                raise HTTPException(
                    status_code=503,
                    detail=f"Workspace {workspace!r} has an invalid access token.",
                )
            tokens[workspace] = token.strip()
        if tokens:
            return tokens

    legacy = os.getenv("EVIDUE_PILOT_TOKEN", "").strip()
    if len(legacy) >= 24:
        return {"default": legacy}
    raise HTTPException(
        status_code=503,
        detail=(
            "Product access is disabled until EVIDUE_WORKSPACE_TOKENS or "
            "EVIDUE_PILOT_TOKEN is configured."
        ),
    )


def _resolve_principal(supplied: str) -> PilotPrincipal | None:
    for workspace_id, token in _workspace_tokens().items():
        if hmac.compare_digest(supplied, token):
            return PilotPrincipal(workspace_id=workspace_id)
    return None


async def require_pilot_access(
    authorization: str | None = Header(default=None),
    x_evidue_pilot_token: str | None = Header(default=None),
) -> AsyncGenerator[PilotPrincipal]:
    supplied = x_evidue_pilot_token or ""
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    principal = _resolve_principal(supplied) if supplied else None
    if principal is None:
        raise HTTPException(status_code=401, detail="Valid workspace access key required")
    tokens = set_workspace_context(principal.workspace_id, principal.actor)
    try:
        yield principal
    finally:
        reset_workspace_context(tokens)
