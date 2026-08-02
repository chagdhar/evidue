# Evidue Mobbin Reference Board

**Purpose:** Ground the Evidue redesign in proven product patterns instead of generated-dashboard conventions.

Mobbin is a reference library, not a template to copy. Use it to compare recurring interaction patterns across shipped products, then implement an original system that fits Evidue's buyer, data, and trust boundary.

---

## 1. Research method

For every Evidue screen:

1. Define the user's question.
2. Search Mobbin by screen pattern and UI element.
3. Review at least 8–12 examples.
4. Record recurring structures, not colors or visual decoration.
5. Select one structural pattern and one interaction pattern.
6. Adapt them to Evidue's financial semantics.
7. Never reproduce a screen pixel-for-pixel.

Recommended Mobbin surfaces:

- Web Dashboard
- Web SaaS Dashboard
- Web Internal Tool
- Web Table UI
- Web Filter and Sort
- Web Activity Log
- Drawer UI
- Empty State UI

---

## 2. Pattern map

| Evidue need | Mobbin research area | References to inspect | Pattern to borrow | Avoid |
|---|---|---|---|---|
| Financial decision summary | Dashboard / SaaS Dashboard | dashboards with one dominant metric and compact secondary facts | clear hierarchy, restrained summary strip, one primary CTA | four equal KPI cards, decorative charts |
| Claims comparison | Table UI | Shopify, PandaDoc, OpenSea, Notion table patterns | strong column hierarchy, toolbar, row selection, density | card-per-row, too many columns |
| Filtering | Filter and Sort | Databricks, Front, Better Stack | compact toolbar, popover for advanced filters, visible active filters | a full card of filters occupying the page |
| Evidence inspection | Drawer UI | right-side and floating drawer patterns | maintain list context while revealing detail | full-page navigation for every row, oversized modal |
| Evidence chronology | Activity Log | Mercury, Mixpanel, Better Stack, PlanetScale | timestamped stacked events, filters, progressive detail | colorful project timeline, excessive icons |
| Contract workbench | Internal Tool | Better Stack, Databricks, Jasper | split panes, compact toolbars, clear selection state | generic dashboard cards around document content |
| Empty / no-result states | Empty State | Linear, GitHub, Airbnb examples | explain why, provide a relevant next step | “No data” or decorative empty art without guidance |
| Technical metadata | SaaS Dashboard / Internal Tool | Cloudflare, Better Stack, Databricks | secondary mono metadata and compact status labels | exposing raw JSON as primary UX |

---

## 3. Exact Mobbin searches

Use these search phrases in Mobbin or Mobbin MCP:

### Decision page

- `finance dashboard with one primary amount and supporting metrics`
- `invoice review dashboard enterprise web`
- `payment reconciliation summary web app`
- `SaaS billing dashboard invoice details`

### Findings and claims

- `dense enterprise data table with filters and row detail`
- `transaction table status filters side drawer`
- `exceptions table finance operations`
- `audit findings list with amount and status`

### Evidence Drawer

- `right side drawer record details web app`
- `transaction detail drawer timeline`
- `audit evidence side panel`
- `event detail drawer with metadata`

### Contract rules

- `split pane document review and extracted data`
- `policy editor approval workflow`
- `version history rule configuration web app`
- `JSON schema validation review interface`

### Evidence and audit history

- `activity log with filters web app`
- `audit log timeline enterprise SaaS`
- `data source connection status table`
- `event ledger table detail drawer`

### States

- `read only banner enterprise web app`
- `empty filtered table clear filters`
- `data loading skeleton enterprise dashboard`
- `error state with retry and preserved data`

---

## 4. App-specific reference set

Use these products as structural references when they appear in Mobbin results:

### Mercury

Study:

- calm financial hierarchy;
- activity and timestamp presentation;
- restrained status treatments.

Do not copy consumer-banking metaphors or account-balance visuals.

### Databricks

Study:

- dense technical tables;
- filtering patterns;
- split technical workspaces;
- compact toolbars.

Avoid excessive technical complexity in the default Evidue view.

### Better Stack

Study:

- operational incident detail;
- event history;
- filters and status clarity;
- contextual drawers.

Adapt “incident” severity language into neutral financial determinations.

### Cloudflare

Study:

- precise infrastructure navigation;
- technical metadata hierarchy;
- restrained product surfaces.

Avoid presenting infrastructure as the primary buyer story.

### Shopify / PandaDoc

Study:

- document and transaction tables;
- status columns;
- row actions;
- structured list/detail flows.

### Linear

Study:

- density;
- keyboard/focus polish;
- feature-education empty states;
- minimal chrome.

Avoid turning Evidue into a project-management aesthetic.

### Mixpanel / PlanetScale

Study:

- activity logs;
- version/history views;
- event detail hierarchy.

---

## 5. What not to use from Mobbin

Do not select references because they look trendy. Reject patterns dominated by:

- glassmorphism;
- dark neon AI palettes;
- gradients as primary hierarchy;
- oversized marketing typography inside the app;
- chart-heavy dashboards without an operational action;
- consumer-finance cards and rewards metaphors;
- gamification;
- social proof inside operational screens;
- mobile-first card stacks for desktop financial tables;
- excessive rounded pills;
- floating AI chat boxes.

---

## 6. Design review template

For each redesigned screen, document:

```text
Screen:
User question:
Primary action:
Mobbin patterns reviewed:
Recurring layout pattern:
Recurring interaction pattern:
Pattern selected for Evidue:
What was intentionally not copied:
Evidence/financial semantics added:
Accessibility considerations:
```

Store completed reviews in pull-request descriptions or `docs/design-reviews/`.

---

## 7. Mobbin + Codex workflow

If the user has Mobbin Pro, connect Mobbin MCP to an AI coding client and ask it to return references before coding. Use prompts such as:

> Search Mobbin for enterprise finance dashboards that present one primary payable amount, supporting invoice values, and a clear next action. Return the strongest structural patterns and explain which would fit an audit product. Do not generate code.

Then use a separate implementation prompt that cites the selected pattern decisions and Evidue's local design documents.

Do not ask Codex to “make it look like Stripe/Linear.” Give it named layout, component, density, typography, and interaction requirements from these documents.
