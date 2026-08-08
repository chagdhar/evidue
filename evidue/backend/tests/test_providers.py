from __future__ import annotations

import io
import json
import urllib.error

import pytest
from app.agreements import providers
from app.agreements.providers import ProviderError, call_provider


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return json.dumps(self.payload).encode()


def test_gemini_uses_json_schema_not_deprecated_response_schema(monkeypatch) -> None:
    captured = {}

    def fake_open(req, timeout):
        captured["body"] = json.loads(req.data)
        return _Response(
            {
                "candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}],
                "usageMetadata": {"promptTokenCount": 1},
            }
        )

    monkeypatch.setattr(providers.urllib.request, "urlopen", fake_open)
    result = providers._gemini_call(
        "prompt",
        {"type": "object", "properties": {"ok": {"type": "boolean"}}},
        model="gemini-3.6-flash",
        api_key="secret",
    )
    config = captured["body"]["generationConfig"]
    assert "responseJsonSchema" in config
    assert "responseSchema" not in config
    assert "temperature" not in config
    assert result.payload == {"ok": True}


def test_openai_uses_strict_json_schema(monkeypatch) -> None:
    captured = {}

    def fake_open(req, timeout):
        captured["body"] = json.loads(req.data)
        return _Response(
            {
                "id": "req-1",
                "choices": [
                    {
                        "message": {"content": '{"ok": true}'},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"total_tokens": 10},
            }
        )

    monkeypatch.setattr(providers.urllib.request, "urlopen", fake_open)
    providers._openai_call(
        "prompt",
        {"type": "object", "additionalProperties": False, "properties": {}},
        model="configured-model",
        api_key="secret",
    )
    response_format = captured["body"]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert "temperature" not in captured["body"]


def test_retryable_503_is_retried_then_succeeds(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    attempts = {"count": 0}

    def fake_call(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise urllib.error.HTTPError(
                "https://example",
                503,
                "unavailable",
                hdrs=None,
                fp=io.BytesIO(b"provider detail"),
            )
        return providers.ProviderResult(
            payload={"ok": True},
            provider="google-gemini",
            model="gemini-3.6-flash",
        )

    monkeypatch.setitem(providers.PROVIDERS["gemini"], "call", fake_call)
    sleeps = []
    result = call_provider(
        "prompt",
        {},
        provider="gemini",
        max_retries=2,
        pin_provider=True,
        sleep_fn=sleeps.append,
    )
    assert result.payload == {"ok": True}
    assert attempts["count"] == 3
    assert len(sleeps) == 2


def test_nonretryable_400_does_not_retry(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    attempts = {"count": 0}

    def fake_call(*args, **kwargs):
        attempts["count"] += 1
        raise urllib.error.HTTPError(
            "https://example", 400, "bad request", hdrs=None, fp=io.BytesIO(b"sensitive")
        )

    monkeypatch.setitem(providers.PROVIDERS["gemini"], "call", fake_call)
    with pytest.raises(ProviderError, match="pin_provider"):
        call_provider(
            "prompt",
            {},
            provider="gemini",
            max_retries=3,
            pin_provider=True,
            sleep_fn=lambda _: None,
        )
    assert attempts["count"] == 1


def test_provider_configuration_status_never_exposes_secret(monkeypatch) -> None:
    from app.agreements.providers import provider_configuration_status

    secret = "secret-value-that-must-never-be-returned"
    monkeypatch.setenv("GEMINI_API_KEY", secret)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    status = provider_configuration_status("gemini")
    assert status == {
        "provider": "gemini",
        "configured": True,
        "model": "gemini-test-model",
        "credential_source": "server_environment",
        "secret_location": "server_environment",
        "customer_key_required": False,
    }
    assert secret not in repr(status)


def test_provider_aliases_have_stable_canonical_identity() -> None:
    from app.agreements.providers import canonical_provider_name

    assert canonical_provider_name("google-gemini") == "gemini"
    assert canonical_provider_name("google") == "gemini"
    assert canonical_provider_name("gpt") == "openai"


def test_fallback_alias_cannot_masquerade_as_independent_provider(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    attempts = {"count": 0}

    def unavailable(*args, **kwargs):
        attempts["count"] += 1
        raise urllib.error.HTTPError(
            "https://example",
            503,
            "unavailable",
            hdrs=None,
            fp=io.BytesIO(b"provider detail"),
        )

    monkeypatch.setitem(providers.PROVIDERS["gemini"], "call", unavailable)
    with pytest.raises(ProviderError, match="HTTP 503"):
        call_provider(
            "prompt",
            {},
            provider="google-gemini",
            fallback_provider="gemini",
            max_retries=0,
            sleep_fn=lambda _: None,
        )
    assert attempts["count"] == 1
