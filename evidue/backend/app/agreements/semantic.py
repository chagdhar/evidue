"""Narrow semantic fact extraction with strict evidence binding.

Semantic evaluators are intentionally isolated from settlement. They answer one
fact question from cited evidence artifacts and may only return true, false, or
unknown. Financial context is neither accepted nor produced here.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from hashlib import sha256
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from .models import TruthValue

SEMANTIC_PROMPT_VERSION = "semantic-fact-v1"


class SemanticEvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    span_id: str
    quote: str = Field(min_length=1, max_length=500)


class SemanticFactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_type: str
    question: str = Field(min_length=3, max_length=1000)
    artifact_ids: list[str] = Field(min_length=1, max_length=100)
    allowed_values: list[str] = Field(default_factory=lambda: ["true", "false", "unknown"])


class SemanticFactResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_type: str
    truth: TruthValue
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[SemanticEvidenceSpan] = Field(default_factory=list)
    explanation: str = Field(max_length=1000)
    model: str
    prompt_version: str
    input_hash: str
    requires_review: bool = False


class SemanticFactExtractor(Protocol):
    def extract(
        self, request: SemanticFactRequest, artifacts: dict[str, str]
    ) -> SemanticFactResult:
        """Extract one narrow semantic fact with source citations."""
        ...


def _input_hash(request: SemanticFactRequest, artifacts: dict[str, str]) -> str:
    payload = {
        "request": request.model_dump(mode="json"),
        "artifacts": {key: artifacts[key] for key in sorted(artifacts)},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def validate_semantic_result(
    result: SemanticFactResult,
    *,
    request: SemanticFactRequest,
    artifacts: dict[str, str],
    minimum_confidence: float,
) -> SemanticFactResult:
    """Bind a model result to the requested fact and exact source evidence."""

    if result.fact_type != request.fact_type:
        raise ValueError("Semantic result fact_type does not match the request")
    unknown_artifacts = set(request.artifact_ids) - set(artifacts)
    if unknown_artifacts:
        raise ValueError(f"Requested semantic artifacts are missing: {sorted(unknown_artifacts)}")
    for citation in result.citations:
        if citation.artifact_id not in request.artifact_ids:
            raise ValueError("Semantic citation references an artifact outside the request")
        text = artifacts.get(citation.artifact_id)
        if text is None or citation.quote not in text:
            raise ValueError("Semantic citation quote is not an exact span of its artifact")

    bound = result.model_copy(update={"input_hash": _input_hash(request, artifacts)})
    if bound.confidence < minimum_confidence or bound.truth == TruthValue.CONFLICTING:
        bound = bound.model_copy(
            update={
                "truth": TruthValue.UNKNOWN,
                "requires_review": True,
                "explanation": (
                    "Semantic evaluator confidence was below the configured threshold; "
                    "human review is required."
                ),
            }
        )
    if bound.truth in {TruthValue.TRUE, TruthValue.FALSE} and not bound.citations:
        raise ValueError("A decisive semantic fact must cite source evidence")
    return bound


class GeminiSemanticFactExtractor:
    """Gemini-backed narrow fact extractor, deliberately disconnected from settlement."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        minimum_confidence: float | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("EVIDUE_SEMANTIC_MODEL", "gemini-3.6-flash")
        configured_threshold = os.getenv("EVIDUE_SEMANTIC_FACT_MIN_CONFIDENCE", "0.85")
        self.minimum_confidence = (
            float(configured_threshold) if minimum_confidence is None else minimum_confidence
        )
        if not 0 <= self.minimum_confidence <= 1:
            raise ValueError("Semantic minimum confidence must be between 0 and 1")
        self.timeout_seconds = timeout_seconds

    def extract(
        self, request: SemanticFactRequest, artifacts: dict[str, str]
    ) -> SemanticFactResult:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        missing = set(request.artifact_ids) - set(artifacts)
        if missing:
            raise ValueError(f"Requested semantic artifacts are missing: {sorted(missing)}")

        artifact_block = "\n\n".join(
            f"ARTIFACT_ID: {artifact_id}\n---\n{artifacts[artifact_id]}"
            for artifact_id in request.artifact_ids
        )
        prompt = f"""You extract one narrow evidentiary fact for Evidue.

You are NOT deciding whether an invoice is payable. Do not calculate money,
recommend a dispute, or infer facts that the supplied artifacts do not support.
If the evidence is insufficient or ambiguous, return truth='unknown'. Every
true/false answer must cite an exact quote copied from an artifact.

FACT_TYPE: {request.fact_type}
QUESTION: {request.question}
ALLOWED_VALUES: true, false, unknown

EVIDENCE:
{artifact_block}
"""
        response_schema = SemanticFactResult.model_json_schema()
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": response_schema,
            },
        }
        request_obj = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request_obj, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Gemini semantic extraction failed ({exc.code}): {detail[:500]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Gemini semantic extraction failed: {exc.reason}") from exc

        candidates = raw.get("candidates") or []
        if not candidates:
            raise ValueError("Gemini returned no semantic-fact candidate")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(str(part.get("text", "")) for part in parts).strip()
        if not text:
            raise ValueError("Gemini returned an empty semantic-fact response")
        payload = json.loads(text)
        payload.update(
            {
                "fact_type": request.fact_type,
                "model": self.model,
                "prompt_version": SEMANTIC_PROMPT_VERSION,
                "input_hash": _input_hash(request, artifacts),
            }
        )
        result = SemanticFactResult.model_validate(payload)
        return validate_semantic_result(
            result,
            request=request,
            artifacts=artifacts,
            minimum_confidence=self.minimum_confidence,
        )
