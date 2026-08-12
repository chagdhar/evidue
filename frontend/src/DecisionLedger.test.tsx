import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ClaimDecisionLedger, DecisionFlow, FinancialEquation } from "./DecisionLedger";

it("uses the same claim-authority-proof-decision grammar across surfaces", () => {
  render(
    <>
      <DecisionFlow />
      <FinancialEquation billed="$150.00" disputed="$25.50" substantiated="$124.50" />
      <ClaimDecisionLedger
        claimId="OUT-004821"
        claim="Vendor submitted the outcome as billable."
        authorityId="R1"
        authority="No same-intent recontact within seven days."
        evidence={[{ when: "Jun 15", source: "Customer support", event: "Same-intent recontact", tone: "bad" }]}
        determination="Contradicted"
        impact="$1.50 identified for dispute"
        action="Request vendor credit"
      />
    </>,
  );

  expect(screen.getByText("Read the contract")).toBeInTheDocument();
  expect(screen.getByText("Approve the rules")).toBeInTheDocument();
  expect(screen.getByText("$25.50")).toBeInTheDocument();
  expect(screen.getByText("OUT-004821")).toBeInTheDocument();
  expect(screen.getByText("No same-intent recontact within seven days.")).toBeInTheDocument();
  expect(screen.getByText("CONTRADICTED")).toBeInTheDocument();
  expect(screen.getByText("$1.50 identified for dispute")).toBeInTheDocument();
});
