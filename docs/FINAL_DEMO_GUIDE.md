# Final Evidue demo guide

## Product truth

The working wedge is **Evidue Verify**: deterministic reconciliation of an
outcome-priced AI-agent invoice against approved contract rules and persisted
customer operational evidence.

**Evidue Prove** is a functional vendor-side preflight using the same synthetic
evidence fixture in this demonstration. The interface states this limitation
explicitly. Production deployments would separate vendor-visible evidence from
customer-private evidence, so vendor preflight would normally be less complete
than customer verification.

The **Outcome Ledger** demonstrates the shared receipt schema and neutrality
model. It is not yet an SDK, signed registry, or production permission system.

## Product demo recording path (85–95 seconds)

1. **Overview — 0–10 seconds**
   - Show `Prove before invoicing. Verify before payment.`
   - Explain that vendors need to prove outcomes and customers need to verify
     what they owe.

2. **Vendor Preflight — 10–25 seconds**
   - Open Vendor Preflight.
   - Read the visible demonstration-evidence disclosure.
   - Run preflight.
   - Show $15,000 proposed, $12,480 preflight-supported, and $2,520 at risk.
   - State: “This synthetic demo uses the same evidence on both sides so the
     mechanism is inspectable. Production evidence stores are separate.”

3. **Data collection — 25–38 seconds**
   - Open Data Sources.
   - Show eight source systems, 100% coverage, 9,975 direct matches, and 25 secondary-key matches.
   - Open one raw payment record briefly.
   - State: “The records are synthetic, but they enter through the same preserve, normalize, match, and evaluate stages planned for customer data.”

4. **Outcome Ledger — 38–46 seconds**
   - Show the outcome receipt and neutrality rule.
   - State: “A receipt supports a claim; it never declares itself payable.”

5. **Customer Verify — 46–67 seconds**
   - Open Customer Verify.
   - Run reconciliation when the demo is reset.
   - Show $15,000 submitted, $12,480 supported, and $2,520 deducted.
   - State that explicit rules, not a model, decide the financial result.

6. **Evidence — 67–84 seconds**
   - Open OUT-004821 through the example-dispute action.
   - Show vendor claim, processor failure, computed deadline, later human
     completion, and $0 payable.

7. **Dispute package — 84–95 seconds**
   - Download the evidence package.
   - End on the corrected payable amount.

## Founder video

The YC founder video is a separate one-minute founder-only video. Do not use the
product screen recording as the founder video.

## Acceptance checks

- No completed results appear before reconciliation.
- Vendor Preflight visibly discloses the shared synthetic fixture.
- Vendor labels are provisional: `Preflight-supported amount` and
  `Likely non-billable`.
- Customer Verify uses definitive `payable`, `disputed`, and `needs review`
  determinations.
- Customer Verify shows evidence coverage and identifier matching before the Run button.
- Data Sources exposes original and normalized payloads without claiming live integrations.
- Illustrative historical invoices do not appear on the primary Overview path.
- Every production route loads directly after browser refresh.
- All three exports download and reconcile to 1,680 disputes and $2,520.
