"""Independent compiler-consensus safety checks.

A second model is never allowed to vote a financial interpretation into
existence. Instead, two independently source-grounded AIR candidates are
compared after deterministic lowering. Material disagreement becomes a blocking
human-review diagnostic. This module is pure and does not call any provider.
"""

from __future__ import annotations

from typing import Any

from .models import AgreementIR, CompilerDiagnostic
from .semantics import semantic_delta


def compiler_consensus_report(
    primary: AgreementIR,
    secondary: AgreementIR,
    *,
    primary_provenance: dict[str, Any] | None = None,
    secondary_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare independently compiled AIRs by normalized contractual semantics."""

    delta = semantic_delta(primary, secondary)
    changed = list(delta["changed_sections"])
    agreed = not changed
    return {
        "version": "compiler-consensus-1",
        "status": "agreed" if agreed else "material_disagreement",
        "agreed": agreed,
        "approval_blocked": not agreed,
        "changed_sections": changed,
        "unchanged_sections": list(delta["unchanged_sections"]),
        "primary_fingerprint": delta["before_fingerprint"],
        "secondary_fingerprint": delta["after_fingerprint"],
        "primary_provenance": primary_provenance or {},
        "secondary_provenance": secondary_provenance or {},
        "policy": (
            "Independent compilers must agree on normalized material semantics; "
            "disagreement is routed to human review and is never resolved by model voting."
        ),
    }


def consensus_blocking_diagnostic(report: dict[str, Any]) -> CompilerDiagnostic | None:
    """Convert a material compiler disagreement into an AIR approval hard gate."""

    if report.get("agreed") is True:
        return None
    sections = ", ".join(str(item) for item in report.get("changed_sections", [])) or "unknown"
    return CompilerDiagnostic(
        code="INDEPENDENT_COMPILER_DISAGREEMENT",
        severity="blocking",
        message=(
            "Independent contract compilers disagreed on material normalized semantics "
            f"({sections}). Human review is required; Evidue will not choose a model by vote."
        ),
        clause_ids=[],
    )


def assurance_provider_unavailable_diagnostic(provider: str) -> CompilerDiagnostic:
    """Fail closed when a workspace explicitly requires independent compilation assurance."""

    return CompilerDiagnostic(
        code="INDEPENDENT_COMPILER_UNAVAILABLE",
        severity="blocking",
        message=(
            f"Independent compiler assurance provider {provider!r} was unavailable. "
            "The primary proposal remains a candidate but cannot be approved under the "
            "configured dual-compiler policy."
        ),
        clause_ids=[],
    )
