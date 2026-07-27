import {
  Alert,
  AppBar,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Divider,
  Drawer,
  Paper,
  Stack,
  Toolbar,
  Typography,
} from "@mui/material";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api, Category, Contract, DemoStatus, Invoice, Summary } from "./api";
import { disclosure, formatUsd } from "./presentation";

const navItems = [
  ["Overview", "/demo"],
  ["Customer Verify", "/demo/invoices/current"],
  ["Vendor Preflight", "/demo/vendor-preflight"],
  ["Outcome Ledger", "/demo/outcome-ledger"],
  ["Contracts", "/demo/contracts/current"],
  ["Data", "/demo/data-sources"],
] as const;

export function ProductShell() {
  const [aboutOpen, setAboutOpen] = useState(false);
  return (
    <Box className="product-shell">
      <AppBar position="sticky" color="transparent" elevation={0} className="app-header">
        <Toolbar className="product-toolbar">
          <Box className="brand-lockup"><Typography className="wordmark">Evidue</Typography><Typography>Outcome commerce control</Typography></Box>
          <Box className="primary-nav" component="nav" aria-label="Primary navigation">
            {navItems.map(([label, to]) => (
              <NavLink key={to} to={to} end={to === "/demo"}>
                {label}
              </NavLink>
            ))}
          </Box>
          <Box sx={{ flexGrow: 1 }} />
          <Button size="small" onClick={() => setAboutOpen(true)}>How Evidue works</Button>
          <Chip label="Synthetic demonstration" className="synthetic-badge" size="small" />
        </Toolbar>
      </AppBar>
      <Box className="product-body">
        <Outlet />
      </Box>
      <Drawer anchor="right" open={aboutOpen} onClose={() => setAboutOpen(false)}>
        <Box className="about-drawer">
          <Typography className="eyebrow">Product workflow</Typography>
          <Typography variant="h4">One outcome record, two independent controls</Typography>
          <Stack className="how-steps" divider={<Divider flexItem />}>
            {[
              ["01", "Instrument the outcome", "The vendor emits a stable outcome ID, claimed action, agent version, and evidence references."],
              ["02", "Preflight before invoicing", "Evidue Prove identifies unsupported claims, duplicates, and missing operational proof."],
              ["03", "Verify independently", "Evidue Verify joins customer-owned evidence to customer-approved contract rules."],
              ["04", "Determine each charge", "Every claim becomes payable, disputed, or needs review with decisive evidence."],
              ["05", "Settle with proof", "Finance receives a corrected payable amount and an exportable dispute package."],
            ].map(([number, title, body]) => (
              <Box className="how-step" key={number}>
                <span>{number}</span>
                <Box><Typography fontWeight={800}>{title}</Typography><Typography color="text.secondary">{body}</Typography></Box>
              </Box>
            ))}
          </Stack>
          <Alert icon={false} className="trust-note">
            Vendor preflight cannot alter customer-approved rules or private evidence. No model decides whether a charge is payable, and the customer retains final payment authority.
          </Alert>
        </Box>
      </Drawer>
    </Box>
  );
}

function PageIntro({ eyebrow, title, body, action }: { eyebrow: string; title: string; body: string; action?: ReactNode }) {
  return (
    <Box className="product-page-intro">
      <Box><Typography className="eyebrow">{eyebrow}</Typography><Typography variant="h3">{title}</Typography><Typography color="text.secondary">{body}</Typography></Box>
      {action}
    </Box>
  );
}

function useProductData() {
  const [status, setStatus] = useState<DemoStatus | null>(null);
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [contract, setContract] = useState<Contract | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    (async () => {
      try {
        let currentStatus = await api.status();
        if (currentStatus.scenario_id !== "headline") currentStatus = await api.reset("headline");
        const [invoiceResult, contractResult] = await Promise.all([api.invoice(), api.contract()]);
        setStatus(currentStatus); setInvoice(invoiceResult); setContract(contractResult);
        if (currentStatus.reconciled) setSummary(await api.current());
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Could not load product data");
      } finally { setLoading(false); }
    })();
  }, []);
  return { status, invoice, contract, summary, loading, error };
}

export function OverviewPage() {
  const navigate = useNavigate();
  const { invoice, contract, summary, loading, error } = useProductData();
  if (loading) return <LoadingPage />;
  if (error || !invoice || !contract) return <ErrorPage message={error} />;
  return (
    <Container maxWidth="xl" className="product-page">
      <Alert icon={false} className="disclosure"><strong>Synthetic demonstration data.</strong> {disclosure}</Alert>
      <PageIntro eyebrow="Finance control center" title="What requires attention" body="Review outcome-priced AI vendor spend, payment recommendations, and evidence-ready deductions." action={<Button variant="contained" onClick={() => navigate("/demo/invoices/current")}>Open June invoice</Button>} />
      <Paper className="hero-control">
        <Box>
          <Stack direction="row" spacing={1} alignItems="center"><Chip label={summary ? "Ready for approval" : "Ready to reconcile"} color={summary ? "success" : "warning"} size="small"/><Typography className="mono" color="text.secondary">INV-NOVA-2026-06</Typography></Stack>
          <Typography variant="h4">June 2026 payable recommendation</Typography>
          <Typography color="text.secondary">{contract.vendor} · {contract.customer}</Typography>
        </Box>
        <Box className="overview-money">
          <Box><Typography className="fact-label">Submitted</Typography><Typography>{formatUsd(invoice.submitted_amount)}</Typography></Box>
          <Box><Typography className="fact-label">Recommended payment</Typography><Typography className="primary-money">{summary ? formatUsd(summary.confirmed_payable_amount) : "Pending"}</Typography></Box>
          <Box><Typography className="fact-label">Confirmed deductions</Typography><Typography className="deduction-money">{summary ? formatUsd(summary.recommended_deduction) : "Pending"}</Typography></Box>
          <Box><Typography className="fact-label">Needs review</Typography><Typography>{summary ? formatUsd(summary.needs_review_amount) : "Pending"}</Typography></Box>
        </Box>
      </Paper>
      <section className="platform-story" aria-label="Evidue product architecture">
        <Box className="platform-heading"><Typography className="eyebrow">One financial layer for outcome-priced agents</Typography><Typography variant="h4">Prove before invoicing. Verify before payment.</Typography><Typography color="text.secondary">Evidue connects agent execution to realized revenue without letting vendors control the customer’s payable decision.</Typography></Box>
        <Box className="platform-rail">
          <button onClick={() => navigate("/demo/vendor-preflight")}><span className="surface-mark vendor">P</span><div><strong>Evidue Prove</strong><small>Vendor preflight · Can we defend this charge?</small></div><span>Open →</span></button>
          <div className="shared-rail"><span>Outcome ledger</span><small>Versioned receipts · identifiers · evidence provenance</small></div>
          <button onClick={() => navigate("/demo/invoices/current")}><span className="surface-mark customer">V</span><div><strong>Evidue Verify</strong><small>Customer control · Should we pay this charge?</small></div><span>Open →</span></button>
        </Box>
      </section>
      <Box className="overview-grid">
        <Paper className="overview-panel">
          <Typography className="eyebrow">Current control coverage</Typography><Typography variant="h5">One invoice, seven approved rules</Typography>
          <Box className="coverage-row"><span>Invoice lines attributable</span><strong>{invoice.claimed_outcomes.toLocaleString()}</strong></Box>
          <Box className="coverage-row"><span>Evidence sources available</span><strong>{contract.evidence_sources.length} source categories</strong></Box>
          <Box className="coverage-row"><span>Executable contract rules</span><strong>{contract.clauses.length}</strong></Box>
          <Button onClick={() => navigate("/demo/contracts/current")}>Review contract controls</Button>
        </Paper>
        <Paper className="overview-panel">
          <Typography className="eyebrow">How Evidue works</Typography><Typography variant="h5">A repeatable monthly control</Typography>
          <ol className="compact-process"><li>Import invoice and approved contract</li><li>Join customer-owned operational evidence</li><li>Calculate payable, disputed, and review amounts</li><li>Export a dispute-ready package</li></ol>
        </Paper>
      </Box>
    </Container>
  );
}

export function InvoicesPage() {
  const navigate = useNavigate();
  const { invoice, summary, loading, error } = useProductData();
  if (loading) return <LoadingPage />;
  if (error || !invoice) return <ErrorPage message={error} />;
  return <Container maxWidth="xl" className="product-page"><PageIntro eyebrow="Invoice operations" title="AI vendor invoices" body="Track submitted amounts, verified payables, and dispute status by billing period." />
    <Paper className="invoice-list-table"><Box className="invoice-list-head"><span>Vendor</span><span>Period</span><span>Submitted</span><span>Recommended</span><span>Status</span></Box>
      <button onClick={() => navigate("/demo/invoices/current")}><span><strong>Nova Support AI</strong><small>Working demonstration</small></span><span>June 2026</span><span>{formatUsd(invoice.submitted_amount)}</span><span>{summary ? formatUsd(summary.confirmed_payable_amount) : "Pending"}</span><Chip label={summary ? "Ready" : "Unreconciled"} size="small" color={summary ? "success" : "warning"}/></button>
      <div><span><strong>Nova Support AI</strong><small>Illustrative synthetic history</small></span><span>May 2026</span><span>$14,210.00</span><span>$13,608.00</span><Chip label="Closed" size="small" variant="outlined"/></div>
      <div><span><strong>Nova Support AI</strong><small>Illustrative synthetic history</small></span><span>April 2026</span><span>$12,940.00</span><span>$12,940.00</span><Chip label="Paid" size="small" variant="outlined"/></div>
    </Paper></Container>;
}

export function ContractsPage() {
  const { contract, loading, error } = useProductData();
  if (loading) return <LoadingPage />;
  if (error || !contract) return <ErrorPage message={error} />;
  return <Container maxWidth="xl" className="product-page"><PageIntro eyebrow="Contract control center" title={`${contract.vendor} services agreement`} body="Approved commercial terms translated into deterministic, reviewable billing rules." />
    <Box className="contract-meta"><Paper><Typography className="fact-label">Effective billing period</Typography><Typography>June 1–30, 2026</Typography></Paper><Paper><Typography className="fact-label">Pricing</Typography><Typography>{formatUsd(contract.price_per_outcome)} per payable outcome</Typography></Paper><Paper><Typography className="fact-label">Rules configured</Typography><Typography>{contract.clauses.length}</Typography></Paper><Paper><Typography className="fact-label">Approval status</Typography><Typography>Approved for demo</Typography></Paper></Box>
    <Stack className="contract-mapping-list" spacing={2}>{contract.clauses.map((clause) => <Paper className="contract-mapping" key={clause.id}><Box><Typography className="eyebrow">Contract clause</Typography><Typography>“{clause.text}”</Typography></Box><Box><Stack direction="row" spacing={1} alignItems="center"><Chip label={clause.rule.id} size="small"/><Typography variant="h6">{clause.rule.title}</Typography></Stack><Typography>{clause.rule.description}</Typography><Typography variant="body2" color="text.secondary">Required evidence: {clause.rule.evidence_required.join(", ")}</Typography></Box></Paper>)}</Stack>
    <Alert icon={false} className="approval-note">A human-approved rule configuration controls money. Automated systems may propose mappings, but they do not silently change payable logic.</Alert>
  </Container>;
}

export function DisputesPage() {
  const navigate = useNavigate();
  const { summary, loading, error } = useProductData();
  if (loading) return <LoadingPage />;
  if (error) return <ErrorPage message={error} />;
  if (!summary) return <Container maxWidth="lg" className="product-page"><PageIntro eyebrow="Dispute operations" title="No package generated yet" body="Run the June reconciliation before preparing the vendor dispute." action={<Button variant="contained" onClick={() => navigate("/demo/invoices/current")}>Open invoice</Button>} /></Container>;
  return <Container maxWidth="xl" className="product-page"><PageIntro eyebrow="Dispute operations" title="June 2026 dispute package" body="Confirmed non-payable charges with contract rules and decisive evidence attached." action={<Button variant="contained" href="/api/reconciliations/current/exports/evidence.json">Download dispute package</Button>} />
    <Paper className="dispute-hero"><Box><Typography className="fact-label">Recommended deduction</Typography><Typography className="dispute-total">{formatUsd(summary.recommended_deduction)}</Typography><Typography>{summary.disputed_outcomes.toLocaleString()} disputed charges</Typography></Box><Box className="dispute-readiness"><Typography fontWeight={800}>Detected ✓</Typography><span>→</span><Typography fontWeight={800}>Evidenced ✓</Typography><span>→</span><Typography fontWeight={800}>Ready to export ✓</Typography></Box></Paper>
    <Paper className="dispute-categories">{(Object.entries(summary.categories) as Array<[string, Category]>).map(([ruleId, category]) => <Box key={ruleId}><Chip label={ruleId} size="small"/><span>{category.label}</span><strong>{category.count.toLocaleString()}</strong><strong>{formatUsd(category.amount)}</strong></Box>)}</Paper>
    <Box className="package-actions"><Paper><Typography className="eyebrow">Package contents</Typography><Typography variant="h5">Evidence attached to every disputed line</Typography><Typography color="text.secondary">Invoice line, contract rule, decisive source records, determination, and engine version.</Typography></Paper><Paper><Typography className="eyebrow">Customer authority</Typography><Typography variant="h5">Ready for internal approval</Typography><Typography color="text.secondary">Evidue prepares the package; finance or procurement decides what to submit and pay.</Typography></Paper></Box>
  </Container>;
}

export function DataSourcesPage() {
  const { contract, invoice, loading, error } = useProductData();
  const sourceDetails = useMemo(() => ({
    "Nova vendor claims": ["Outcome-level invoice fixture", invoice?.claimed_outcomes ?? 0],
    "Acme support desk": ["Conversation and human-action events", "Schema validated"],
    "Payment processor": ["Refund and payment-state events", "Schema validated"],
    "Billing ledger": ["Invoice and attribution records", "Schema validated"],
    "Product database": ["Account and action-state events", "Schema validated"],
  } as Record<string, [string, string | number]>), [invoice]);
  if (loading) return <LoadingPage />;
  if (error || !contract || !invoice) return <ErrorPage message={error} />;
  return <Container maxWidth="xl" className="product-page"><PageIntro eyebrow="Evidence infrastructure" title="Data sources and provenance" body="Synthetic connector fixtures model the schemas Evidue would ingest through APIs, webhooks, files, or scheduled imports." />
    <Alert icon={false} severity="info">These are deterministic local fixtures—not live production integrations. Source systems and record IDs are retained so every decision can be reproduced.</Alert>
    <Box className="source-grid">{(Object.entries(sourceDetails) as Array<[string, [string, string | number]]>).map(([name, [description, metric]]) => <Paper key={name}><Stack direction="row" justifyContent="space-between"><Typography fontWeight={850}>{name}</Typography><Chip label="Fixture loaded" size="small" variant="outlined"/></Stack><Typography color="text.secondary">{description}</Typography><Divider/><Typography className="fact-label">Availability</Typography><Typography>{typeof metric === "number" ? `${metric.toLocaleString()} invoice claims` : metric}</Typography></Paper>)}</Box>
    <Paper className="provenance-model"><Typography className="eyebrow">Evidence retained per event</Typography><Box>{["Source system", "Source record ID", "Event type", "Event timestamp", "Customer and outcome IDs", "Normalized values", "Ingestion timestamp"].map((item) => <span key={item}>✓ {item}</span>)}</Box></Paper>
  </Container>;
}


export function VendorPreflightPage() {
  const navigate = useNavigate();
  const { invoice, contract, summary: initialSummary, loading, error } = useProductData();
  const [summary, setSummary] = useState<Summary | null>(initialSummary);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState("");

  useEffect(() => setSummary(initialSummary), [initialSummary]);

  async function runPreflight() {
    setRunning(true);
    setRunError("");
    try {
      const result = await api.reconcile();
      setSummary(result);
    } catch (requestError) {
      setRunError(requestError instanceof Error ? requestError.message : "Could not run invoice preflight");
    } finally {
      setRunning(false);
    }
  }

  if (loading) return <LoadingPage />;
  if (error || !invoice || !contract) return <ErrorPage message={error} />;

  return <Container maxWidth="xl" className="product-page vendor-page">
    <Alert icon={false} className="disclosure"><strong>Demonstration evidence model.</strong> This synthetic demo uses one shared evidence fixture so both calculations are inspectable. In production, vendor evidence and customer-private evidence are stored and evaluated separately; vendor preflight is typically less complete than the customer determination.</Alert>
    <PageIntro
      eyebrow="Evidue Prove · vendor workspace"
      title="Send an invoice you can defend"
      body="Preflight every proposed outcome against contract requirements and available operational proof before finance sees the bill."
      action={<Stack direction="row" spacing={1}><Button variant="outlined" onClick={() => navigate("/demo/outcome-ledger")}>View outcome ledger</Button><Button variant="contained" disabled={running} onClick={runPreflight}>{running ? "Running preflight…" : summary ? "Rerun preflight" : "Run invoice preflight"}</Button></Stack>}
    />
    {runError && <Alert severity="error">{runError}</Alert>}

    <Paper className="vendor-hero">
      <Box className="vendor-hero-copy">
        <Chip label="Nova Support AI · June 2026" size="small" className="vendor-chip" />
        <Typography variant="h4">Invoice readiness</Typography>
        <Typography color="text.secondary">Know which claims are defensible, which need evidence, and which should never reach the customer invoice.</Typography>
      </Box>
      <Box className="vendor-kpis">
        <Box><Typography className="fact-label">Proposed invoice</Typography><Typography>{formatUsd(invoice.submitted_amount)}</Typography></Box>
        <Box><Typography className="fact-label">Preflight-supported amount</Typography><Typography className="primary-money">{summary ? formatUsd(summary.confirmed_payable_amount) : "Pending"}</Typography></Box>
        <Box><Typography className="fact-label">Revenue at risk</Typography><Typography className="deduction-money">{summary ? formatUsd(summary.recommended_deduction) : "Pending"}</Typography></Box>
        <Box><Typography className="fact-label">Claims at risk</Typography><Typography>{summary ? summary.disputed_outcomes.toLocaleString() : "Pending"}</Typography></Box>
      </Box>
    </Paper>

    <Box className="workspace-split">
      <Paper className="workspace-panel">
        <Typography className="eyebrow">Before sending this invoice</Typography>
        <Typography variant="h5">Recommended billing cleanup</Typography>
        <Stack className="preflight-actions" divider={<Divider flexItem />}>
          <Box><span>01</span><div><strong>Remove unsupported claims</strong><small>{summary ? `${summary.disputed_outcomes.toLocaleString()} claims currently fail approved billing rules.` : "Run preflight to identify unsupported claims."}</small></div></Box>
          <Box><span>02</span><div><strong>Attach missing operational proof</strong><small>Stable outcome IDs, downstream confirmations, account IDs, and action records make claims defensible.</small></div></Box>
          <Box><span>03</span><div><strong>Fix agent completion semantics</strong><small>Do not close an outcome when a downstream action was only attempted rather than completed.</small></div></Box>
          <Box><span>04</span><div><strong>Prevent duplicate attribution</strong><small>One customer intent should map to one otherwise-payable outcome inside the contract window.</small></div></Box>
        </Stack>
      </Paper>
      <Paper className="workspace-panel separation-panel">
        <Typography className="eyebrow">Neutrality boundary</Typography>
        <Typography variant="h5">Prove prepares. Verify decides.</Typography>
        <Typography color="text.secondary">The vendor may improve evidence and remove unsupported claims. It cannot edit customer rules, customer evidence, internal notes, or the final payment recommendation.</Typography>
        <Box className="boundary-flow">
          <div><strong>Evidue Prove</strong><span>Vendor claim + execution evidence</span></div>
          <span>→</span>
          <div><strong>Outcome ledger</strong><span>Versioned proof envelope</span></div>
          <span>→</span>
          <div><strong>Evidue Verify</strong><span>Customer contract + private evidence</span></div>
        </Box>
      </Paper>
    </Box>

    {summary ? <>
      <section className="product-section">
        <Typography className="eyebrow">Revenue leakage diagnosis</Typography>
        <Typography variant="h4">Why {formatUsd(summary.recommended_deduction)} is at risk</Typography>
        <Paper className="preflight-risk-list">
          {(Object.entries(summary.categories) as Array<[string, Category]>).map(([ruleId, category]) => <button key={ruleId} onClick={() => navigate(`/demo/invoices/current?rule=${ruleId}`)}><Chip label={ruleId} size="small"/><span><strong>{category.label}</strong><small>{category.count.toLocaleString()} proposed charges</small></span><strong>{formatUsd(category.amount)}</strong><span className="risk-action">Inspect →</span></button>)}
        </Paper>
      </section>
      <section className="product-section">
        <Box className="example-preflight">
          <Box><Typography className="eyebrow">Example outcome · OUT-004821</Typography><Typography variant="h4">Likely non-billable</Typography><Typography color="text.secondary">The agent marked a refund resolved, but the payment processor rejected it and a human completed it after the contract window. Customer verification still makes the final determination.</Typography></Box>
          <Box className="preflight-verdict"><Chip label="Unsupported" color="error"/><Typography className="dispute-total">$1.50</Typography><Typography>revenue at risk</Typography></Box>
          <Box className="fix-callout"><strong>Required agent fix</strong><span>Keep the outcome open until the payment processor confirms the refund successfully posted.</span><Button onClick={() => navigate("/demo/invoices/current")}>Review customer-side evidence</Button></Box>
        </Box>
      </section>
    </> : <Paper className="empty-preflight"><Typography variant="h5">Preflight has not run</Typography><Typography color="text.secondary">Run the deterministic reconciliation engine from the vendor perspective to classify all 10,000 proposed invoice lines.</Typography></Paper>}
  </Container>;
}

export function OutcomeLedgerPage() {
  const navigate = useNavigate();
  const { invoice, contract, summary, loading, error } = useProductData();
  if (loading) return <LoadingPage />;
  if (error || !invoice || !contract) return <ErrorPage message={error} />;
  const receiptFields = ["Stable outcome ID", "Customer and account IDs", "Agent and workflow version", "Claimed outcome and action", "Downstream source record", "Execution and completion timestamps", "Contract-rule version", "Evidence provenance"];
  return <Container maxWidth="xl" className="product-page ledger-page">
    <PageIntro eyebrow="Shared outcome infrastructure" title="A financial record for every agent outcome" body="The outcome ledger gives vendors a standard proof envelope and customers an independently verifiable record—without merging their permissions or incentives." action={<Button variant="contained" onClick={() => navigate("/demo/vendor-preflight")}>Open vendor preflight</Button>} />
    <Box className="ledger-story">
      <Paper className="ledger-node vendor"><Typography className="eyebrow">Agent execution</Typography><Typography variant="h5">Nova claims an outcome</Typography><Typography>Agent version, attempted action, timestamps, and vendor-side evidence are recorded.</Typography></Paper>
      <span className="ledger-arrow">→</span>
      <Paper className="ledger-node receipt"><Typography className="eyebrow">Outcome receipt</Typography><Typography variant="h5">Versioned proof envelope</Typography><Typography>Stable identifiers connect the claim to contract rules and source-system records.</Typography></Paper>
      <span className="ledger-arrow">→</span>
      <Paper className="ledger-node customer"><Typography className="eyebrow">Independent verification</Typography><Typography variant="h5">Acme verifies what it owes</Typography><Typography>Customer-owned evidence and approved rules determine the payable amount.</Typography></Paper>
    </Box>
    <Box className="ledger-grid">
      <Paper className="receipt-card">
        <Stack direction="row" justifyContent="space-between" alignItems="center"><Box><Typography className="eyebrow">Outcome receipt</Typography><Typography variant="h4">OUT-004821</Typography></Box><Chip label="Disputed by Verify" color="error"/></Stack>
        <Divider/>
        <Box className="receipt-fields"><div><span>Claimed outcome</span><strong>Refund completed</strong></div><div><span>Agent status</span><strong>Resolved</strong></div><div><span>Downstream status</span><strong>Processor rejected</strong></div><div><span>Contract window</span><strong>2 hours</strong></div><div><span>Customer result</span><strong>$0.00 payable</strong></div><div><span>Evidence state</span><strong>Complete</strong></div></Box>
      </Paper>
      <Paper className="workspace-panel">
        <Typography className="eyebrow">Canonical receipt schema</Typography><Typography variant="h5">Proof that travels with the claim</Typography>
        <Box className="schema-list">{receiptFields.map(field => <span key={field}>✓ {field}</span>)}</Box>
        <Alert icon={false} className="trust-note">A receipt supports a claim; it never self-declares the charge payable.</Alert>
      </Paper>
    </Box>
    <section className="product-section">
      <Typography className="eyebrow">Two-sided value</Typography><Typography variant="h4">The same record reduces friction for both parties</Typography>
      <Box className="two-sided-grid"><Paper><Typography className="eyebrow">For agent vendors</Typography><Typography variant="h5">Fewer rejected invoices</Typography><p>Find unsupported outcomes, missing evidence, and duplicate attribution before billing.</p><strong>{summary ? `${formatUsd(summary.recommended_deduction)} currently at risk` : `${invoice.claimed_outcomes.toLocaleString()} claims ready for preflight`}</strong></Paper><Paper><Typography className="eyebrow">For customers</Typography><Typography variant="h5">A defensible payable amount</Typography><p>Reconcile vendor claims against the contract and customer systems without trusting vendor self-reporting.</p><strong>{summary ? `${formatUsd(summary.confirmed_payable_amount)} supported payable` : `${contract.clauses.length} approved controls loaded`}</strong></Paper></Box>
    </section>
  </Container>;
}

function LoadingPage() { return <Box className="center"><CircularProgress/><Typography>Loading Evidue…</Typography></Box>; }
function ErrorPage({ message }: { message: string }) { return <Container className="product-page"><Alert severity="error">{message || "Product data unavailable"}</Alert></Container>; }
