import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Drawer,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { TemplateIcon } from "./TemplateIcons";
import { ReactNode, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Category, Contract, DemoStatus, Invoice, Summary } from "./api";
import { DashboardShell } from "./DashboardShell";
import { disclosure, formatUsd } from "./presentation";

export function ProductShell() {
  const [aboutOpen, setAboutOpen] = useState(false);
  return (
    <>
      <DashboardShell onOpenHowItWorks={() => setAboutOpen(true)} />
      <Drawer anchor="right" open={aboutOpen} onClose={() => setAboutOpen(false)}>
        <Box className="template-about-drawer">
          <Typography variant="overline" color="primary">Product workflow</Typography>
          <Typography variant="h4" sx={{ mt: 0.5 }}>One outcome record, two independent controls</Typography>
          <Stack spacing={0} sx={{ mt: 3 }} divider={<Divider flexItem />}>
            {[
              ["01", "Instrument the outcome", "The vendor emits a stable outcome ID, claimed action, agent version, and evidence references."],
              ["02", "Preflight before invoicing", "Evidue Prove identifies unsupported claims, duplicates, and missing operational proof."],
              ["03", "Verify independently", "Evidue Verify joins customer-owned evidence to customer-approved contract rules."],
              ["04", "Determine each charge", "Every claim becomes payable, disputed, or needs review with decisive evidence."],
              ["05", "Settle with proof", "Finance receives a corrected payable amount and an exportable dispute package."],
            ].map(([number, title, body]) => (
              <Box className="template-workflow-row" key={number}>
                <span>{number}</span>
                <Box><Typography fontWeight={700}>{title}</Typography><Typography variant="body2" color="text.secondary">{body}</Typography></Box>
              </Box>
            ))}
          </Stack>
          <Alert severity="info" sx={{ mt: 3 }}>
            Vendor preflight cannot alter customer-approved rules or private evidence. No model decides whether a charge is payable, and the customer retains final payment authority.
          </Alert>
        </Box>
      </Drawer>
    </>
  );
}

function PageFrame({ children }: { children: ReactNode }) {
  return <Box className="template-page-container">{children}</Box>;
}

function PageHeader({ eyebrow, title, body, action }: { eyebrow: string; title: string; body: string; action?: ReactNode }) {
  return (
    <Box className="template-page-header">
      <Box>
        <Typography variant="overline" color="primary">{eyebrow}</Typography>
        <Typography variant="h3">{title}</Typography>
        <Typography color="text.secondary" sx={{ mt: 0.75, maxWidth: 760 }}>{body}</Typography>
      </Box>
      {action && <Box>{action}</Box>}
    </Box>
  );
}

function MetricCard({ label, value, helper, tone = "neutral", icon }: { label: string; value: string; helper?: string; tone?: "neutral" | "success" | "error" | "warning"; icon?: ReactNode }) {
  return (
    <Card className={`template-stat-card ${tone}`}>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
          <Typography variant="body2" color="text.secondary">{label}</Typography>
          {icon && <Box className="template-stat-icon">{icon}</Box>}
        </Stack>
        <Typography className="template-stat-value">{value}</Typography>
        {helper && <Typography variant="caption" color="text.secondary">{helper}</Typography>}
      </CardContent>
    </Card>
  );
}

function SectionCard({ title, eyebrow, action, children, className = "" }: { title: string; eyebrow?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <Card className={`template-section-card ${className}`}>
      <Box className="template-section-card-header">
        <Box>
          {eyebrow && <Typography variant="overline" color="text.secondary">{eyebrow}</Typography>}
          <Typography variant="h5">{title}</Typography>
        </Box>
        {action}
      </Box>
      <Divider />
      <CardContent>{children}</CardContent>
    </Card>
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
  return { status, invoice, contract, summary, loading, error, setSummary };
}

export function OverviewPage() {
  const navigate = useNavigate();
  const { invoice, contract, summary, loading, error } = useProductData();
  if (loading) return <LoadingPage />;
  if (error || !invoice || !contract) return <ErrorPage message={error} />;
  return (
    <PageFrame>
      <Alert severity="warning" className="template-disclosure"><strong>Synthetic demonstration data.</strong> {disclosure}</Alert>
      <PageHeader
        eyebrow="Finance control center"
        title="What requires attention"
        body="Review outcome-priced AI vendor spend, payment recommendations, and evidence-ready deductions."
        action={<Button variant="contained" onClick={() => navigate("/demo/invoices/current")}>Open June invoice</Button>}
      />

      <Box className="template-stats-grid">
        <MetricCard label="Submitted invoice" value={formatUsd(invoice.submitted_amount)} helper="10,000 claimed outcomes" icon={<TemplateIcon name="receipt" />} />
        <MetricCard label="Recommended payment" value={summary ? formatUsd(summary.confirmed_payable_amount) : "Pending"} helper={summary ? "8,320 outcomes supported" : "Run reconciliation"} tone="success" icon={<TemplateIcon name="check" />} />
        <MetricCard label="Confirmed deductions" value={summary ? formatUsd(summary.recommended_deduction) : "Pending"} helper={summary ? "1,680 disputed outcomes" : "Awaiting evidence review"} tone="error" icon={<TemplateIcon name="warning" />} />
        <MetricCard label="Contract controls" value={`${contract.clauses.length}`} helper={`${contract.evidence_sources.length} evidence source categories`} icon={<TemplateIcon name="shield" />} />
      </Box>

      <Box className="template-overview-grid">
        <Card className="template-highlight-card">
          <CardContent>
            <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={3}>
              <Box>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Chip label={summary ? "Ready for approval" : "Ready to reconcile"} color={summary ? "success" : "warning"} size="small" />
                  <Typography variant="caption" className="mono">INV-NOVA-2026-06</Typography>
                </Stack>
                <Typography variant="h4" sx={{ mt: 2 }}>June 2026 payable recommendation</Typography>
                <Typography color="text.secondary">{contract.vendor} · {contract.customer}</Typography>
              </Box>
              <Box className="template-highlight-money">
                <Typography variant="overline">Supported payable</Typography>
                <Typography>{summary ? formatUsd(summary.confirmed_payable_amount) : "Pending"}</Typography>
              </Box>
            </Stack>
            <Box className="template-highlight-rail">
              <span>Invoice {formatUsd(invoice.submitted_amount)}</span>
              <TemplateIcon name="arrow" />
              <span>Deduction {summary ? formatUsd(summary.recommended_deduction) : "Pending"}</span>
              <TemplateIcon name="arrow" />
              <strong>Pay {summary ? formatUsd(summary.confirmed_payable_amount) : "Pending"}</strong>
            </Box>
          </CardContent>
        </Card>

        <SectionCard title="One invoice, seven approved rules" eyebrow="Control coverage">
          <Stack divider={<Divider flexItem />}>
            <Box className="template-detail-row"><span>Invoice lines attributable</span><strong>{invoice.claimed_outcomes.toLocaleString()}</strong></Box>
            <Box className="template-detail-row"><span>Evidence sources available</span><strong>{contract.evidence_sources.length} source categories</strong></Box>
            <Box className="template-detail-row"><span>Executable billing rules</span><strong>{contract.clauses.length}</strong></Box>
          </Stack>
          <Button sx={{ mt: 2 }} onClick={() => navigate("/demo/contracts/current")}>Review contract controls</Button>
        </SectionCard>
      </Box>

      <SectionCard title="Prove before invoicing. Verify before payment." eyebrow="One financial layer for outcome-priced agents">
        <Box className="template-product-flow">
          <button onClick={() => navigate("/demo/vendor-preflight")}>
            <Box className="template-flow-icon"><TemplateIcon name="preflight" /></Box>
            <Box><strong>Evidue Prove</strong><small>Vendor preflight · Can we defend this charge?</small></Box>
            <TemplateIcon name="arrow" />
          </button>
          <Box className="template-flow-connector">
            <TemplateIcon name="ledger" />
            <strong>Outcome Ledger</strong>
            <small>Versioned receipts · identifiers · evidence provenance</small>
          </Box>
          <button onClick={() => navigate("/demo/invoices/current")}>
            <Box className="template-flow-icon"><TemplateIcon name="verify" /></Box>
            <Box><strong>Evidue Verify</strong><small>Customer control · Should we pay this charge?</small></Box>
            <TemplateIcon name="arrow" />
          </button>
        </Box>
      </SectionCard>
    </PageFrame>
  );
}

export function InvoicesPage() {
  const navigate = useNavigate();
  const { invoice, summary, loading, error } = useProductData();
  if (loading) return <LoadingPage />;
  if (error || !invoice) return <ErrorPage message={error} />;
  return (
    <PageFrame>
      <PageHeader eyebrow="Invoice operations" title="AI vendor invoices" body="Track submitted amounts, verified payables, and dispute status by billing period." />
      <TableContainer component={Paper}>
        <Table>
          <TableHead><TableRow><TableCell>Vendor</TableCell><TableCell>Period</TableCell><TableCell align="right">Submitted</TableCell><TableCell align="right">Recommended</TableCell><TableCell>Status</TableCell><TableCell /></TableRow></TableHead>
          <TableBody>
            <TableRow hover>
              <TableCell><strong>Nova Support AI</strong></TableCell><TableCell>June 2026</TableCell><TableCell align="right">{formatUsd(invoice.submitted_amount)}</TableCell><TableCell align="right">{summary ? formatUsd(summary.confirmed_payable_amount) : "Pending"}</TableCell><TableCell><Chip label={summary ? "Ready to approve" : "Ready to reconcile"} color={summary ? "success" : "warning"} size="small" /></TableCell><TableCell align="right"><Button onClick={() => navigate("/demo/invoices/current")}>Open</Button></TableCell>
            </TableRow>
            <TableRow><TableCell colSpan={6}><Typography variant="caption" color="text.secondary">Only the June invoice is a fully interactive fixture in this demonstration.</Typography></TableCell></TableRow>
          </TableBody>
        </Table>
      </TableContainer>
    </PageFrame>
  );
}

export function ContractsPage() {
  const { contract, loading, error } = useProductData();
  if (loading) return <LoadingPage />;
  if (error || !contract) return <ErrorPage message={error} />;
  return (
    <PageFrame>
      <PageHeader eyebrow="Contract control center" title="Commercial terms made executable" body="Every payable decision is tied to an approved clause, explicit parameters, and required evidence." />
      <Box className="template-stats-grid template-stats-grid-3">
        <MetricCard label="Vendor" value={contract.vendor} helper={contract.customer} />
        <MetricCard label="Price per outcome" value={formatUsd(contract.price_per_outcome)} helper="Monthly outcome pricing" />
        <MetricCard label="Approved rules" value={`${contract.clauses.length}`} helper={`${contract.evidence_sources.length} evidence source categories`} />
      </Box>
      <Stack spacing={1.5}>
        {contract.clauses.map((clause) => (
          <Card key={clause.id} className="template-rule-card">
            <CardContent>
              <Box className="template-rule-grid">
                <Box><Typography variant="overline" color="text.secondary">Contract clause</Typography><Typography>{clause.text}</Typography></Box>
                <Box><Stack direction="row" spacing={1} alignItems="center"><Chip label={clause.rule.id} color="primary" size="small" /><Typography variant="h6">{clause.rule.title}</Typography></Stack><Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{clause.rule.description}</Typography></Box>
                <Box><Typography variant="overline" color="text.secondary">Evidence required</Typography><Stack direction="row" gap={0.75} flexWrap="wrap">{clause.rule.evidence_required.map((evidence) => <Chip key={evidence} label={evidence} size="small" variant="outlined" />)}</Stack></Box>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Stack>
    </PageFrame>
  );
}

export function DisputesPage() {
  const navigate = useNavigate();
  const { summary, loading, error } = useProductData();
  if (loading) return <LoadingPage />;
  if (error) return <ErrorPage message={error} />;
  if (!summary) return <PageFrame><Alert severity="info">Run the June reconciliation before preparing the dispute package.</Alert><Button sx={{ mt: 2 }} variant="contained" onClick={() => navigate("/demo/invoices/current")}>Open Customer Verify</Button></PageFrame>;
  return (
    <PageFrame>
      <PageHeader eyebrow="Dispute operations" title="Prepare vendor dispute" body="Package confirmed deductions, contract controls, and decisive evidence for finance or procurement." />
      <Box className="template-stats-grid template-stats-grid-3">
        <MetricCard label="Disputed charges" value={summary.disputed_outcomes.toLocaleString()} helper="Evidence attached to every determination" tone="error" />
        <MetricCard label="Recommended deduction" value={formatUsd(summary.recommended_deduction)} helper="Confirmed by deterministic rules" tone="error" />
        <MetricCard label="Package status" value="Ready" helper="Detected → Evidenced → Exportable" tone="success" />
      </Box>
      <SectionCard title="Confirmed deductions" eyebrow="By contract rule">
        <Stack divider={<Divider flexItem />}>
          {(Object.entries(summary.categories) as Array<[string, Category]>).map(([ruleId, category]) => (
            <Box className="template-category-row" key={ruleId}>
              <Chip label={ruleId} size="small" /><Box><strong>{category.label}</strong><small>{category.count.toLocaleString()} charges</small></Box><strong>{formatUsd(category.amount)}</strong>
            </Box>
          ))}
        </Stack>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mt: 3 }}>
          <Button variant="contained" href="/api/reconciliations/current/exports/evidence.json" download>Download dispute package</Button>
          <Button variant="outlined" href="/api/reconciliations/current/exports/disputes.csv" download>Disputed-lines CSV</Button>
          <Button variant="text" onClick={() => navigate("/demo/invoices/current")}>Return to reconciliation</Button>
        </Stack>
      </SectionCard>
    </PageFrame>
  );
}

export function DataSourcesPage() {
  const { contract, loading, error } = useProductData();
  if (loading) return <LoadingPage />;
  if (error || !contract) return <ErrorPage message={error} />;
  const sources = [
    ["Support conversations", "Zendesk-format fixture", "Ticket and recontact evidence"],
    ["Payment events", "Stripe-format fixture", "Refund and credit completion state"],
    ["Billing records", "Subscription ledger fixture", "Invoice and attribution records"],
    ["Product events", "Account event fixture", "Downstream account changes"],
    ["Vendor invoice", "Outcome-level CSV fixture", "10,000 claimed outcomes"],
  ];
  return (
    <PageFrame>
      <PageHeader eyebrow="Evidence infrastructure" title="Customer-owned systems of record" body="Synthetic connector fixtures model the provenance Evidue would ingest through APIs, webhooks, or scheduled exports." />
      <Alert severity="info" sx={{ mb: 2 }}>These are deterministic local fixtures, not live authenticated integrations.</Alert>
      <Box className="template-source-grid">
        {sources.map(([name, status, description]) => (
          <Card key={name}>
            <CardContent>
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start"><Typography variant="h6">{name}</Typography><Chip label="Fixture loaded" size="small" color="success" /></Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{status}</Typography>
              <Typography variant="body2" sx={{ mt: 2 }}>{description}</Typography>
              <LinearProgress variant="determinate" value={100} sx={{ mt: 2 }} />
            </CardContent>
          </Card>
        ))}
      </Box>
      <SectionCard title="Provenance retained" eyebrow="Operational event model">
        <Box className="template-schema-grid">{["Source system", "Source record ID", "Event type", "Event timestamp", "Customer ID", "Outcome ID", "Normalized values", "Ingestion timestamp"].map((field) => <span key={field}>✓ {field}</span>)}</Box>
      </SectionCard>
    </PageFrame>
  );
}

export function VendorPreflightPage() {
  const navigate = useNavigate();
  const { invoice, contract, summary: existingSummary, loading, error, setSummary } = useProductData();
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState("");
  const [summary, setLocalSummary] = useState<Summary | null>(existingSummary);
  useEffect(() => setLocalSummary(existingSummary), [existingSummary]);
  if (loading) return <LoadingPage />;
  if (error || !invoice || !contract) return <ErrorPage message={error} />;

  async function runPreflight() {
    setRunning(true); setRunError("");
    try { const result = await api.reconcile(); setLocalSummary(result); setSummary(result); }
    catch (requestError) { setRunError(requestError instanceof Error ? requestError.message : "Could not run preflight"); }
    finally { setRunning(false); }
  }

  return (
    <PageFrame>
      <Alert severity="info" sx={{ mb: 2 }}><strong>Demonstration evidence model.</strong> This synthetic demo uses one shared evidence fixture so both calculations are inspectable. Production vendor evidence and customer-private evidence remain separate.</Alert>
      <PageHeader eyebrow="Evidue Prove · Agent vendor workspace" title="Send an invoice you can defend" body="Preflight proposed outcome charges against approved billing rules before they reach the customer." action={<Button variant="contained" disabled={running} onClick={runPreflight}>{running ? "Running preflight…" : "Run invoice preflight"}</Button>} />
      {runError && <Alert severity="error" sx={{ mb: 2 }}>{runError}</Alert>}
      <Box className="template-stats-grid">
        <MetricCard label="Proposed invoice" value={formatUsd(invoice.submitted_amount)} helper={`${invoice.claimed_outcomes.toLocaleString()} proposed claims`} />
        <MetricCard label="Preflight-supported amount" value={summary ? formatUsd(summary.confirmed_payable_amount) : "Pending"} helper="Claims currently supported by evidence" tone="success" />
        <MetricCard label="Revenue at risk" value={summary ? formatUsd(summary.recommended_deduction) : "Pending"} helper="Likely customer dispute exposure" tone="error" />
        <MetricCard label="Claims at risk" value={summary ? summary.disputed_outcomes.toLocaleString() : "Pending"} helper="Remove or repair before billing" tone="warning" />
      </Box>

      <Box className="template-two-column">
        <SectionCard title="Recommended billing cleanup" eyebrow="Before sending this invoice">
          <Stack divider={<Divider flexItem />}>
            {[
              ["01", "Remove unsupported claims", summary ? `${summary.disputed_outcomes.toLocaleString()} claims currently fail approved rules.` : "Run preflight to identify unsupported claims."],
              ["02", "Attach missing operational proof", "Stable IDs, downstream confirmations, account IDs, and action records make claims defensible."],
              ["03", "Fix agent completion semantics", "Do not close an outcome when a downstream action was only attempted."],
              ["04", "Prevent duplicate attribution", "One customer intent should map to one otherwise-payable outcome inside the contract window."],
            ].map(([number, title, body]) => <Box className="template-action-row" key={number}><span>{number}</span><Box><strong>{title}</strong><small>{body}</small></Box></Box>)}
          </Stack>
        </SectionCard>
        <SectionCard title="Prove prepares. Verify decides." eyebrow="Neutrality boundary">
          <Typography color="text.secondary">The vendor may improve evidence and remove unsupported claims. It cannot edit customer rules, customer evidence, internal notes, or the final payment recommendation.</Typography>
          <Box className="template-boundary-flow">
            <div><strong>Prove</strong><span>Vendor claim</span></div><TemplateIcon name="arrow" /><div><strong>Ledger</strong><span>Proof envelope</span></div><TemplateIcon name="arrow" /><div><strong>Verify</strong><span>Customer decision</span></div>
          </Box>
        </SectionCard>
      </Box>

      {summary ? (
        <Box className="template-two-column">
          <SectionCard title={`Why ${formatUsd(summary.recommended_deduction)} is at risk`} eyebrow="Revenue leakage diagnosis">
            <Stack divider={<Divider flexItem />}>
              {(Object.entries(summary.categories) as Array<[string, Category]>).map(([ruleId, category]) => <button className="template-risk-row" key={ruleId} onClick={() => navigate(`/demo/invoices/current?rule=${ruleId}`)}><Chip label={ruleId} size="small"/><Box><strong>{category.label}</strong><small>{category.count.toLocaleString()} proposed charges</small></Box><strong>{formatUsd(category.amount)}</strong><TemplateIcon name="arrow" /></button>)}
            </Stack>
          </SectionCard>
          <Card className="template-example-card">
            <CardContent>
              <Typography variant="overline" color="error">Example outcome · OUT-004821</Typography>
              <Typography variant="h4">Likely non-billable</Typography>
              <Typography color="text.secondary" sx={{ mt: 1 }}>The agent marked a refund resolved, but the payment processor rejected it and a human completed it after the contract window.</Typography>
              <Box className="template-example-amount"><span>Revenue at risk</span><strong>$1.50</strong></Box>
              <Alert severity="warning" sx={{ mt: 2 }}>Keep the outcome open until the payment processor confirms the refund successfully posted.</Alert>
              <Button sx={{ mt: 2 }} onClick={() => navigate("/demo/invoices/current")}>Review customer-side evidence</Button>
            </CardContent>
          </Card>
        </Box>
      ) : <Alert severity="info">Run preflight to classify the 10,000 proposed invoice lines.</Alert>}
    </PageFrame>
  );
}

export function OutcomeLedgerPage() {
  const navigate = useNavigate();
  const { invoice, contract, summary, loading, error } = useProductData();
  if (loading) return <LoadingPage />;
  if (error || !invoice || !contract) return <ErrorPage message={error} />;
  return (
    <PageFrame>
      <PageHeader eyebrow="Shared outcome infrastructure" title="A financial record for every agent outcome" body="The Outcome Ledger gives vendors a standard proof envelope and customers an independently verifiable record—without merging permissions or incentives." action={<Button variant="contained" onClick={() => navigate("/demo/vendor-preflight")}>Open vendor preflight</Button>} />
      <Box className="template-ledger-flow">
        <Card><CardContent><Typography variant="overline" color="text.secondary">Agent execution</Typography><Typography variant="h5">Nova claims an outcome</Typography><Typography variant="body2" color="text.secondary">Agent version, attempted action, timestamps, and vendor-side evidence are recorded.</Typography></CardContent></Card>
        <TemplateIcon name="arrow" />
        <Card className="featured"><CardContent><Typography variant="overline" color="primary">Outcome receipt</Typography><Typography variant="h5">Versioned proof envelope</Typography><Typography variant="body2" color="text.secondary">Stable identifiers connect the claim to rules and source-system records.</Typography></CardContent></Card>
        <TemplateIcon name="arrow" />
        <Card><CardContent><Typography variant="overline" color="text.secondary">Independent verification</Typography><Typography variant="h5">Acme verifies what it owes</Typography><Typography variant="body2" color="text.secondary">Customer-owned evidence and approved rules determine the payable amount.</Typography></CardContent></Card>
      </Box>
      <Box className="template-two-column">
        <SectionCard title="OUT-004821" eyebrow="Outcome receipt" action={<Chip label="Disputed by Verify" color="error" size="small" />}>
          <Box className="template-receipt-grid">
            {[ ["Claimed outcome", "Refund completed"], ["Agent status", "Resolved"], ["Downstream status", "Processor rejected"], ["Contract window", "2 hours"], ["Customer result", "$0.00 payable"], ["Evidence state", "Complete"] ].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}
          </Box>
        </SectionCard>
        <SectionCard title="Proof that travels with the claim" eyebrow="Canonical receipt schema">
          <Box className="template-schema-grid">{["Stable outcome ID", "Customer and account IDs", "Agent and workflow version", "Claimed outcome and action", "Downstream source record", "Execution and completion timestamps", "Contract-rule version", "Evidence provenance"].map((field) => <span key={field}>✓ {field}</span>)}</Box>
          <Alert severity="info" sx={{ mt: 2 }}>A receipt supports a claim; it never self-declares the charge payable.</Alert>
        </SectionCard>
      </Box>
      <Box className="template-two-column">
        <SectionCard title="Fewer rejected invoices" eyebrow="For agent vendors"><Typography color="text.secondary">Find unsupported outcomes, missing evidence, and duplicate attribution before billing.</Typography><Typography variant="h5" sx={{ mt: 2 }}>{summary ? `${formatUsd(summary.recommended_deduction)} currently at risk` : `${invoice.claimed_outcomes.toLocaleString()} claims ready for preflight`}</Typography></SectionCard>
        <SectionCard title="A defensible payable amount" eyebrow="For customers"><Typography color="text.secondary">Reconcile claims against the contract and customer systems without trusting vendor self-reporting.</Typography><Typography variant="h5" sx={{ mt: 2 }}>{summary ? `${formatUsd(summary.confirmed_payable_amount)} supported payable` : `${contract.clauses.length} approved controls loaded`}</Typography></SectionCard>
      </Box>
    </PageFrame>
  );
}

function LoadingPage() { return <Box className="template-loading"><CircularProgress/><Typography>Loading Evidue…</Typography></Box>; }
function ErrorPage({ message }: { message: string }) { return <PageFrame><Alert severity="error">{message || "Product data unavailable"}</Alert></PageFrame>; }
