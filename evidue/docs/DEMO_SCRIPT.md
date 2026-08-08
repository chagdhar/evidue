# Evidue Demo Script

## Recording path: 105–120 seconds

### 0–15 seconds — Operating overview

Open `/demo`.

> "Outcome-priced AI vendors calculate their own bills. Evidue gives finance an independent control over what the contract and the customer’s systems actually support paying. This is synthetic, deterministic demonstration data."

Show the finance-control overview: Nova Support AI, June 2026, $15,000 submitted, 50,302 collected source records, 100% claim coverage, seven approved rules, and the four-stage decision path. Point to the OUT-004821 example charge path, then click **Open Evidue reconciliation**.

### 15–38 seconds — Real-data collection and readiness

Open **Data Sources**.

> "Real systems do not arrive already joined. Evidue collects vendor claims and customer-owned support, payment, product, billing, identity, and contract records; preserves the originals; normalizes them; and resolves identifiers before any payment rule runs."

Show 10,000 claims, the aggregate source-record count, 9,975 direct matches, 25 secondary-key matches, and zero identity reviews. Click **Inspect** on Payment processor. The right-side inspector must open and show the rejected raw payload, canonical Evidue event, match method, confidence, schema version, and content hash. Close the inspector, then return to Evidue reconciliation.

> "These records are synthetic, but they use the same ingestion stages planned for customer data. We start with exports, then replace them with read-only APIs or warehouse views."

### 38–63 seconds — Reconciliation

Click **Run reconciliation**.

> "The engine evaluates every invoice line deterministically. No model decides whether money is payable."

Land on:

- $12,480 corrected payable amount
- $15,000 submitted invoice
- $2,520 recommended deduction
- $0 needs review

Show the reconciliation bridge.

### 63–93 seconds — One disputed outcome

Click **Failed downstream actions**, then **Review example dispute**.

> "The vendor marked this refund resolved. But the payment processor rejected it, the contractual two-hour deadline expired, and a human completed the refund later. The vendor billed $1.50; the supported payable amount is zero."

Show vendor claim, contract obligation, Evidue determination, source records, and the computed deadline. Close the inspector.

### 93–115 seconds — Dispute handoff

Click **Download dispute package**, or open **Disputes** in the product navigation.

> "Evidue packages 1,680 disputed lines, the applicable contract rules, and decisive evidence for a $2,520 deduction. Finance retains the final payment decision. One invoice enters; one defensible payable amount leaves."

End on the $12,480 recommended payment or the dispute package summary.

## Interview-only surfaces

- `/demo/contracts/current` — complete clause-to-rule mappings
- `/demo/disputes/current` — aggregate package and financial handoff
- `/demo/data-sources` — fixture provenance and production ingestion model
- `/demo/lab` — contradictory evidence, recovery, and duplicate-window cases

Do not show the lab in the submitted recording unless asked about edge cases.

## Extended product demo path

The primary demo recording should remain focused while showing the larger company:

1. **Overview:** show the Prove → Outcome Ledger → Evidue architecture.
2. **Vendor Preflight:** show $15,000 proposed, $12,480 defensible, and $2,520 at risk before invoicing.
3. **Outcome Ledger:** open OUT-004821 and explain the versioned proof envelope.
4. **Evidue reconciliation:** run the independent reconciliation and show the same $12,480 supported payable amount.
5. **Evidence:** open OUT-004821 and show the processor rejection, computed deadline, and later human completion.
6. **Dispute package:** download the evidence-backed package.

Narration boundary: “Prove helps the vendor prepare a defensible claim. Reconcile independently determines what the customer should pay. The vendor cannot change customer rules or private evidence.”

## Final recording note

Use `docs/FINAL_DEMO_GUIDE.md` for the final 75–85 second product recording.
The one-minute founder video is a separate founder-only asset.

## Contract compiler insert (45 seconds)

Before the reconciliation, open **Contracts**.

> "The contract is not hardcoded into the adjudicator. Gemini reads the natural-language terms and proposes this constrained rule program. It can only select reviewed operators such as a time window, required success evidence, or uniqueness. It cannot emit code and it never sees an invoice outcome. I approve this version, then the deterministic engine applies it to all 10,000 charges."

Click **Compile contract**, inspect one generated operation and its source clause, then click **Approve rule version**. Continue to the invoice and run reconciliation.
