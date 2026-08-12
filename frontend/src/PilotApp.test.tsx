import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import PilotApp, {
  isPilotEvidenceReady,
  recommendedPilotStage,
  shouldFollowPilotRecommendation,
} from "./PilotApp";
import type { VerificationPlanEnvelope } from "./pilotApi";

function verificationPlan(statuses: string[]): VerificationPlanEnvelope {
  return {
    id: "plan-1",
    contract_id: "contract-1",
    air_version_id: "air-1",
    version: 1,
    created_at: "2026-08-08T00:00:00Z",
    payload_hash: "hash",
    plan: {
      agreement_id: "agreement-1",
      items: statuses.map((status, index) => ({
        proof_requirement_id: `proof-${index + 1}`,
        status,
        selected_source_ids: [],
        missing_fact_types: [],
        rationale: "test",
      })),
    },
  };
}

describe("Evidue reconciliation workspace", () => {
  beforeEach(() => sessionStorage.clear());

  it("requires a workspace access key before exposing customer data controls", () => {
    render(
      <MemoryRouter initialEntries={["/workspace"]}>
        <PilotApp />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: /open your reconciliation workspace/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/access key/i)).toHaveAttribute("type", "password");
    expect(screen.queryByText(/choose invoice csv/i)).not.toBeInTheDocument();
  });

  it("does not mark evidence ready before the verification plan loads", () => {
    expect(isPilotEvidenceReady(true, 0, null)).toBe(false);
    expect(isPilotEvidenceReady(true, 1, null)).toBe(false);
  });

  it("marks evidence ready only when every required proof is ready", () => {
    expect(isPilotEvidenceReady(true, 0, verificationPlan([]))).toBe(true);
    expect(isPilotEvidenceReady(true, 2, verificationPlan(["ready", "ready"]))).toBe(true);
    expect(isPilotEvidenceReady(true, 2, verificationPlan(["ready", "partial"]))).toBe(false);
  });

  it("advances to export only after a review-free reconciliation", () => {
    const base = {
      hasContract: true,
      contractApproved: true,
      approvedRulesStale: false,
      hasInvoice: true,
      evidenceReady: true,
      hasReconciliation: true,
      reconciliationNeedsReview: false,
    };
    expect(recommendedPilotStage(base)).toBe("export");
    expect(recommendedPilotStage({ ...base, reconciliationNeedsReview: true })).toBe("review");
    expect(recommendedPilotStage({ ...base, hasReconciliation: false })).toBe("verification");
    expect(recommendedPilotStage({ ...base, evidenceReady: false })).toBe("evidence");
  });

  it("resumes automatic guidance when backend progress changes the recommendation", () => {
    expect(shouldFollowPilotRecommendation("invoice", "invoice", true)).toBe(false);
    expect(shouldFollowPilotRecommendation("invoice", "evidence", true)).toBe(true);
    expect(shouldFollowPilotRecommendation("evidence", "evidence", false)).toBe(true);
  });
});
