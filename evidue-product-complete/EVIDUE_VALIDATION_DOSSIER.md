# Evidue Validation Dossier

## Core hypothesis

Companies paying AI customer-support vendors based on resolutions, outcomes, or successful interactions need an independent way to verify whether each billed outcome satisfies the contract before approving payment.

## Target customer

Primary:
- Head of Customer Support
- Head of CX Operations
- Support Operations Manager
- Finance Operations
- Accounts Payable
- Procurement or Vendor Management

Target companies:
- Use an AI customer-support agent
- Pay based on resolutions, outcomes, conversations, or usage
- Have meaningful support volume
- Spend enough that billing errors matter

## Problem hypothesis

AI-agent vendors determine which interactions count as successful outcomes and generate the invoice using their own systems.

The customer may have separate evidence showing:
- the customer contacted support again;
- the issue was reopened;
- a refund was issued;
- a human agent corrected the work;
- the wrong account or transaction was handled;
- the contractual SLA was missed.

Verifying these cases currently requires manual comparison across the contract, vendor invoice, support platform, CRM, payment system, and internal records.

## Product hypothesis

Evidue independently compares:
- the contract;
- vendor invoice lines;
- customer-owned operational evidence.

It then calculates:
- payable outcomes;
- disputed outcomes;
- outcomes needing human review;
- the corrected payable invoice amount.

## Strong validation criteria

The idea is strongly validated if we find:

1. At least 5 companies currently paying an AI-support vendor using outcome, resolution, or usage-based pricing.
2. At least 3 examples where an outcome was difficult to verify, wrongly classified, or disputed.
3. At least 2 companies willing to test Evidue with historical or synthetic invoice data.
4. At least 1 company willing to share an anonymized contract or billing definition.
5. Evidence that the recoverable amount or saved staff time is substantially greater than Evidue’s likely price.

## Weak validation

These do not count as meaningful validation:

- “Interesting idea.”
- “I would probably use this.”
- Likes or comments from founders.
- Responses from people who do not buy or operate AI support systems.
- Generic complaints that AI software is expensive.

## Disconfirming evidence

The idea may be weak if:

- customers fully trust vendor reporting;
- outcome definitions are simple and rarely disputed;
- invoices are too small to audit;
- vendors already provide sufficient evidence and appeals;
- customers cannot connect internal systems because of security restrictions;
- finance teams do not care about individual outcomes;
- the cost of verification exceeds likely recoveries.