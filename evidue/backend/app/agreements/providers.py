"""Provider-independent structured LLM inference for contract compilation.

Evidue owns provider credentials.  This module deliberately knows nothing about
Agreement IR or invoice adjudication: it only returns schema-constrained JSON.
Qualification can pin a provider/model; production can retry and fall back.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
BASE_DELAY = 1.0


@dataclass(frozen=True)
class ProviderResult:
    payload: dict[str, Any]
    provider: str
    model: str
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    prompt_hash: str = ""
    response_text: str = ""


class ProviderError(RuntimeError):
    """Sanitized provider failure suitable for backend control flow."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        provider: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.provider = provider
        self.status_code = status_code


def _prompt_hash(prompt: str) -> str:
    return "sha256:" + sha256(prompt.encode("utf-8")).hexdigest()


def _json_object(text: str, *, provider: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"{provider} returned invalid JSON", provider=provider) from exc
    if not isinstance(value, dict):
        raise ProviderError(f"{provider} returned a non-object JSON payload", provider=provider)
    return value


# ---------------------------------------------------------------------------
# Gemini generateContent adapter
# ---------------------------------------------------------------------------


def _gemini_call(
    prompt: str,
    response_schema: dict[str, Any],
    *,
    model: str,
    api_key: str,
    timeout: int = 120,
) -> ProviderResult:
    # Gemini 3.x accepts JSON Schema through responseJsonSchema on the legacy
    # generateContent REST endpoint. Deprecated sampling knobs are intentionally
    # omitted so this remains valid for current 3.x models.
    body = json.dumps(
        {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": response_schema,
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))

    candidates = data.get("candidates") or []
    if not candidates:
        raise ProviderError("Gemini returned no candidates", provider="gemini")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(str(part.get("text", "")) for part in parts).strip()
    if not text:
        raise ProviderError("Gemini returned an empty response", provider="gemini")
    return ProviderResult(
        payload=_json_object(text, provider="gemini"),
        provider="google-gemini",
        model=model,
        raw_metadata={
            "usage": data.get("usageMetadata"),
            "finish_reason": candidates[0].get("finishReason"),
        },
        prompt_hash=_prompt_hash(prompt),
        response_text=text,
    )


# ---------------------------------------------------------------------------
# OpenAI Chat Completions adapter
# ---------------------------------------------------------------------------


def _openai_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            value = part.get("text")
            if isinstance(value, str):
                chunks.append(value)
        return "".join(chunks).strip()
    return ""


def _openai_call(
    prompt: str,
    response_schema: dict[str, Any],
    *,
    model: str,
    api_key: str,
    timeout: int = 120,
) -> ProviderResult:
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "evidue_agreement_compilation",
                    "strict": True,
                    "schema": response_schema,
                },
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))

    choices = data.get("choices") or []
    if not choices:
        raise ProviderError("OpenAI returned no choices", provider="openai")
    text = _openai_message_text(choices[0].get("message", {}).get("content"))
    if not text:
        raise ProviderError("OpenAI returned an empty response", provider="openai")
    return ProviderResult(
        payload=_json_object(text, provider="openai"),
        provider="openai",
        model=model,
        raw_metadata={
            "usage": data.get("usage"),
            "finish_reason": choices[0].get("finish_reason"),
            "request_id": data.get("id"),
        },
        prompt_hash=_prompt_hash(prompt),
        response_text=text,
    )


PROVIDERS: dict[str, dict[str, Any]] = {
    "gemini": {
        "call": _gemini_call,
        "key_env": "GEMINI_API_KEY",
        "model_env": "GEMINI_MODEL",
        "default_model": "gemini-3.6-flash",
        "aliases": {"google", "google-gemini"},
    },
    "openai": {
        "call": _openai_call,
        "key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        # Model availability changes independently of Evidue. Require an
        # explicit server-side model instead of silently pinning a stale ID.
        "default_model": None,
        "aliases": {"gpt"},
    },
}


def _resolve_provider(name: str) -> tuple[str, dict[str, Any]]:
    normalized = name.strip().lower()
    compact = normalized.replace("-", "").replace("_", "")
    for key, config in PROVIDERS.items():
        aliases = {str(item).lower() for item in config.get("aliases", set())}
        if normalized == key or normalized in aliases:
            return key, config
        if compact == key.replace("-", ""):
            return key, config
    raise ProviderError(f"Unknown LLM provider: {name}", provider=normalized)


def canonical_provider_name(provider_name: str) -> str:
    """Return the stable provider identifier used for routing/comparison."""

    name, _config = _resolve_provider(provider_name)
    return name


def _provider_credentials(
    provider_name: str,
    *,
    model: str | None,
    api_key: str | None,
) -> tuple[str, dict[str, Any], str, str]:
    name, config = _resolve_provider(provider_name)
    key = api_key or os.getenv(str(config["key_env"]), "")
    if not key:
        raise ProviderError(
            f"Server credential {config['key_env']} is not configured for provider {name}",
            provider=name,
        )
    selected_model = model or os.getenv(str(config["model_env"]), "") or config.get("default_model")
    if not selected_model:
        raise ProviderError(
            f"Server model {config['model_env']} is not configured for provider {name}",
            provider=name,
        )
    return name, config, str(selected_model), key


def _safe_http_error(exc: urllib.error.HTTPError, provider: str) -> ProviderError:
    # Never surface response bodies to customer-facing code; they can contain
    # request echoes. Status and provider are sufficient for routing/retry.
    retryable = exc.code in RETRYABLE_STATUS
    return ProviderError(
        f"{provider} inference failed with HTTP {exc.code}",
        retryable=retryable,
        provider=provider,
        status_code=exc.code,
    )


def _jitter(prompt: str, attempt: int) -> float:
    digest = sha256(f"{attempt}:{prompt}".encode()).digest()
    return int.from_bytes(digest[:2], "big") / 65535.0 * 0.5


def _call_with_retry(
    prompt: str,
    response_schema: dict[str, Any],
    *,
    provider_name: str,
    model: str | None,
    api_key: str | None,
    timeout: int,
    max_retries: int,
    sleep_fn: Callable[[float], None],
) -> ProviderResult:
    name, config, selected_model, key = _provider_credentials(
        provider_name,
        model=model,
        api_key=api_key,
    )
    call_fn = config["call"]
    last_error: ProviderError | None = None

    for attempt in range(max_retries + 1):
        try:
            return call_fn(
                prompt,
                response_schema,
                model=selected_model,
                api_key=key,
                timeout=timeout,
            )
        except urllib.error.HTTPError as exc:
            error = _safe_http_error(exc, name)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            error = ProviderError(
                f"{name} inference transport failure: {type(exc).__name__}",
                retryable=True,
                provider=name,
            )
        except ProviderError as exc:
            error = exc

        last_error = error
        if not error.retryable or attempt >= max_retries:
            raise error
        delay = min(BASE_DELAY * (2**attempt) + _jitter(prompt, attempt), 30.0)
        sleep_fn(delay)

    assert last_error is not None
    raise last_error


def call_provider(
    prompt: str,
    response_schema: dict[str, Any],
    *,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    fallback_provider: str | None = None,
    timeout: int = 120,
    max_retries: int = MAX_RETRIES,
    pin_provider: bool = False,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> ProviderResult:
    """Call a structured-output provider with bounded retry and optional fallback."""

    primary = provider or os.getenv("EVIDUE_LLM_PRIMARY", "gemini")
    fallback = fallback_provider
    if fallback is None:
        fallback = os.getenv("EVIDUE_LLM_FALLBACK", "") or None

    try:
        return _call_with_retry(
            prompt,
            response_schema,
            provider_name=primary,
            model=model,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            sleep_fn=sleep_fn,
        )
    except ProviderError as primary_error:
        if pin_provider:
            # Qualification must never silently switch providers. Preserve both
            # the pinning decision and the sanitized underlying provider error.
            raise ProviderError(
                (
                    f"Provider {primary} failed and pin_provider=True prevents fallback: "
                    f"{primary_error}"
                ),
                retryable=primary_error.retryable,
                provider=primary_error.provider,
                status_code=primary_error.status_code,
            ) from primary_error

        if not fallback:
            raise
        if canonical_provider_name(fallback) == canonical_provider_name(primary):
            raise

    return _call_with_retry(
        prompt,
        response_schema,
        provider_name=fallback,
        model=None,
        api_key=None,
        timeout=timeout,
        max_retries=max_retries,
        sleep_fn=sleep_fn,
    )


def provider_is_configured(provider_name: str) -> bool:
    """Return whether Evidue server-side credentials/model are available."""

    _name, config = _resolve_provider(provider_name)
    if not os.getenv(str(config["key_env"]), ""):
        return False
    return bool(os.getenv(str(config["model_env"]), "") or config.get("default_model"))


def provider_configuration_status(provider_name: str) -> dict[str, Any]:
    """Return secret-free server configuration metadata for product surfaces."""

    name, config = _resolve_provider(provider_name)
    model = os.getenv(str(config["model_env"]), "") or config.get("default_model")
    return {
        "provider": name,
        "configured": provider_is_configured(name),
        "model": str(model) if model else None,
        "credential_source": "server_environment",
        "secret_location": "server_environment",
        "customer_key_required": False,
    }


def compilation_provenance(result: ProviderResult, **extra: Any) -> dict[str, Any]:
    """Build a secret-free compilation provenance record."""

    return {
        "provider": result.provider,
        "model": result.model,
        "prompt_hash": result.prompt_hash,
        **extra,
    }
