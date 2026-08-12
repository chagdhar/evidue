# Evidue public proof script

## Recording path: 75–100 seconds

### 0–12 seconds — The financial question

Open `/try`.

> “Nova AI billed Acme $150 for 100 outcomes. Would you pay it? Evidue checks the vendor claim against the approved contract and customer-controlled evidence before finance acts.”

Click **Verify the invoice**.

### 12–30 seconds — Contract interpretation and authority

Show the source clause beside the proposed payment rule.

> “The model can interpret the contract, but it cannot decide the invoice. I explicitly approve the rule set first.”

Click **Approve contract rules**.

### 30–48 seconds — Deterministic verification

Click **Verify 100 claims**.

> “Now the model is out of the decision loop. Deterministic logic evaluates each claim against the approved authority and evidence.”

Show:

- $150 vendor claim
- $124.50 substantiated
- $25.50 identified for dispute
- 17 contradicted claims

### 48–72 seconds — Inspect one failed claim

Open `R3 · OUT-004821` inline.

> “I don’t have to trust the summary. This is the vendor assertion, the exact contract authority, the customer-side evidence, the source-record provenance, and the $1.50 financial consequence.”

Expand raw source records if deeper technical proof is useful.

### 72–90 seconds — Commercial handoff

Show **Copy dispute summary**.

> “Evidue keeps the factual determination separate from the commercial remedy. Finance can use the evidence-backed result to request a credit, true-up, or escalate.”

End on **Talk to us** or **Share your workflow**.

## Product boundary

`/try` is the only public proof surface. `/workspace` is the actual protected product. There is no separate demo product and no separate pilot product; “demo” and “pilot” describe how those two canonical surfaces are used.
