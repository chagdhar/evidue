# Evidue UI Template Foundation

The demo interface is structurally adapted from Material UI's official free Dashboard template:

- Template overview: https://mui.com/material-ui/getting-started/templates/
- Source directory: https://github.com/mui/material-ui/tree/master/docs/data/material/getting-started/templates/dashboard
- License: Material UI repository license (MIT)

## What was adopted

- Persistent desktop side navigation
- Responsive mobile drawer and application toolbar
- Grouped navigation sections
- Page-level headers and actions
- Grid-based statistic cards
- Highlighted primary-decision card
- Structured section cards with consistent headers
- Template-style data tables and filters
- Responsive page container and spacing system
- Integrated light/dark mode switch
- Central MUI component overrides instead of page-by-page color patches

## Evidue-specific adaptation

The template structure was adapted to Evidue's product hierarchy:

1. Workspace
   - Overview
   - Evidue reconciliation
   - Vendor Preflight
2. Operations
   - Invoices
   - Disputes
   - Contracts
3. Infrastructure
   - Outcome Ledger
   - Data Sources
   - Scenario Lab

The financial semantic colors remain separate from the template brand system:

- Green: confirmed payable
- Red: confirmed disputed / revenue at risk
- Amber: needs review
- Blue: navigation, selection, and product actions

The reconciliation engine, API contracts, fixture totals, and export behavior were not changed by the template migration.
