# Product v1 Domain Model

## Commercial hierarchy

```text
Organization
└── VendorEngagement
    ├── Agreements / AIR versions
    ├── Invoices
    │   └── ReconciliationRuns
    │       ├── Determinations (machine, immutable)
    │       ├── ReviewCases
    │       │   └── ReviewDecisions (append-only)
    │       ├── ReconciliationStatement
    │       ├── Approval
    │       └── DisputeCase
    │           └── DisputeItems
    └── Evidence sources
```

## Ownership boundaries

`PilotContractRow`, `PilotAIRVersionRow`, `PilotInvoiceRow`, `PilotReconciliationRunRow`, and `PilotDeterminationRow` remain verification-kernel records. Product records link to them rather than copying their semantics.

### ProductOrganization
Represents the finance customer/workspace. In the current pilot architecture each authenticated workspace has an isolated database; the explicit organization object prepares the domain for row-level multitenancy.

### Vendor / VendorEngagement
A vendor is a normalized commercial counterparty. A vendor engagement is that counterparty's ongoing relationship with the organization and owns contract/invoice history.

### ReviewCase
Created only for a `needs_review` machine determination. Stores operational ownership, priority, exposure, and status. It never changes the source determination.

### ReviewDecision
Append-only disposition of a review case: `payable`, `disputed`, or `escalated`. The latest decision is the current overlay; previous decisions remain history.

### ReconciliationStatement
Materialized financial bridge from machine result plus review overlay to the recommended final payable/disputed/open-review amounts. It carries a settlement calculation hash.

### Approval
Immutable finance authority for a ready statement. One approval per reconciliation run. The approval captures payable, disputed amount, actor, timestamp, note, and calculation hash.

### DisputeCase
A lifecycle object opened only from an approved reconciliation. Items are derived from machine-disputed lines plus review cases resolved as disputed.
