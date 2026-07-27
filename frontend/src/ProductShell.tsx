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
  ["Invoices", "/demo/invoices"],
  ["Contracts", "/demo/contracts/current"],
  ["Disputes", "/demo/disputes/current"],
  ["Data sources", "/demo/data-sources"],
] as const;

export function ProductShell() {
  const [aboutOpen, setAboutOpen] = useState(false);
  return (
    <Box className="product-shell">
      <AppBar position="sticky" color="transparent" elevation={0} className="app-header">
        <Toolbar className="product-toolbar">
          <Typography className="wordmark">Evidue</Typography>
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
          <Typography variant="h4">From vendor invoice to defensible payment</Typography>
          <Stack className="how-steps" divider={<Divider flexItem />}>
            {[
              ["01", "Import contract and invoice", "Load outcome-level billing claims and the approved commercial definition of a payable result."],
              ["02", "Configure approved rules", "Translate billing terms into deterministic controls reviewed by the customer."],
              ["03", "Join customer evidence", "Associate support, payment, billing, and product events with every claimed outcome."],
              ["04", "Determine each charge", "Classify claims as payable, disputed, or needs review with decisive evidence."],
              ["05", "Approve and export", "Give finance the corrected payable amount and a dispute-ready evidence package."],
            ].map(([number, title, body]) => (
              <Box className="how-step" key={number}>
                <span>{number}</span>
                <Box><Typography fontWeight={800}>{title}</Typography><Typography color="text.secondary">{body}</Typography></Box>
              </Box>
            ))}
          </Stack>
          <Alert icon={false} className="trust-note">
            No model decides whether a charge is payable. The customer retains final payment authority.
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
      <Box className="overview-grid">
        <Paper className="overview-panel">
          <Typography className="eyebrow">Current control coverage</Typography><Typography variant="h5">One invoice, seven approved rules</Typography>
          <Box className="coverage-row"><span>Invoice lines attributable</span><strong>{invoice.claimed_outcomes.toLocaleString()}</strong></Box>
          <Box className="coverage-row"><span>Evidence source types</span><strong>{contract.evidence_sources.length}</strong></Box>
          <Box className="coverage-row"><span>Executable contract rules</span><strong>{contract.clauses.length}</strong></Box>
          <Button onClick={() => navigate("/demo/contracts/current")}>Review contract controls</Button>
        </Paper>
        <Paper className="overview-panel">
          <Typography className="eyebrow">How Evidue works</Typography><Typography variant="h5">A repeatable monthly control</Typography>
          <ol className="compact-process"><li>Import invoice and approved contract</li><li>Join customer-owned operational evidence</li><li>Calculate payable, disputed, and review amounts</li><li>Export a dispute-ready package</li></ol>
        </Paper>
      </Box>
      <section className="product-section">
        <Typography className="eyebrow">Synthetic invoice history</Typography><Typography variant="h4">Recent activity</Typography>
        <Paper className="activity-list">
          <button onClick={() => navigate("/demo/invoices/current")}><span><strong>Nova Support AI</strong><small>June 2026 · Full working reconciliation</small></span><span>{formatUsd(invoice.submitted_amount)}</span><Chip label={summary ? "Ready to approve" : "Ready to reconcile"} size="small" /></button>
          <div><span><strong>Nova Support AI</strong><small>May 2026 · Illustrative synthetic history</small></span><span>$14,210.00</span><Chip label="Dispute accepted" size="small" variant="outlined" /></div>
          <div><span><strong>Nova Support AI</strong><small>April 2026 · Illustrative synthetic history</small></span><span>$12,940.00</span><Chip label="Paid" size="small" variant="outlined" /></div>
        </Paper>
      </section>
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

function LoadingPage() { return <Box className="center"><CircularProgress/><Typography>Loading Evidue…</Typography></Box>; }
function ErrorPage({ message }: { message: string }) { return <Container className="product-page"><Alert severity="error">{message || "Product data unavailable"}</Alert></Container>; }
