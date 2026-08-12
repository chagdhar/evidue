# Evidue Product

Evidue is the independent financial control for outcome-priced AI-agent invoices. It reads the commercial agreement, turns material terms into a human-approved deterministic Agreement IR (AIR), verifies vendor claims against customer-owned operational evidence, and produces the amount finance should pay.

## Product outcome

A finance/AP operator can complete the product without terminal access:

1. Open a workspace with its access key.
2. Upload or paste the agreement (TXT, Markdown, DOCX, or text-based PDF).
3. Generate a constrained AIR proposal with the contract compiler.
4. Review exact source clauses, executable norms, proof requirements, settlement terms, conformance, and compiler assurance.
5. Approve one immutable AIR version.
6. Upload a vendor invoice CSV; preview and map arbitrary source columns to the canonical invoice schema.
7. Upload customer evidence (CSV, JSON, or JSONL), mark complete exports explicitly when appropriate, and run deterministic identity matching.
8. Resolve any non-authoritative identity suggestions manually.
9. Run reconciliation. The approved AIR—not an LLM and not legacy rule IDs—is the financial authority.
10. Review each line with the contract source and evidence timeline.
11. Export a corrected invoice CSV, dispute CSV, JSON summary, evidence package, or standalone HTML review report.

A fresh workspace also supports **Try sample workspace**, which produces payable, disputed, and needs-review outcomes in one deterministic flow.

## Safety boundary

The model proposes contract interpretation. It never adjudicates invoice lines. AIR approval is blocked unless mechanical compiler assurance and conformance gates pass. Missing or ambiguous evidence resolves conservatively to `needs_review`; it is never silently converted into a deduction.

## Primary surface

`/workspace` is the authenticated finance-control home. The product is invoice-centered: `/workspace/invoices` is the register, `/workspace/invoices/current` is the active contract → evidence → verification → review → commercial-action case, `/workspace/review` is the exception queue, `/workspace/vendors` is vendor history, and `/workspace/settings` holds configuration. `/demo` remains a synthetic narrative surface and `/try` is the zero-signup guided reconciliation.

## Current product boundary

The product supports operator-assisted ingestion rather than live SaaS connectors. Evidence files must already be legitimately exported from the customer's systems. Scanned/image-only PDFs require OCR outside this runtime; the built-in PDF path is for PDFs with extractable text. Authentication is workspace access-key based for the pilot/beta boundary, with server-side database isolation per workspace.
