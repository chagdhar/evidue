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
import {
  api,
  Category,
  Contract,
  DataReadiness,
  DataSourceSamples,
  DemoStatus,
  Invoice,
  RawRecordSample,
  Summary,
} from "./api";
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
    <Card className={`template-stat-card ${tone}`} aria-label={`${label}: ${value}`}>
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
  const [readiness, setReadiness] = useState<DataReadiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    (async () => {
      try {
        let currentStatus = await api.status();
        if (currentStatus.scenario_id !== "headline") currentStatus = await api.reset("headline");
        const [invoiceResult, contractResult, readinessResult] = await Promise.all([
          api.invoice(),
          api.contract(),
          api.dataReadiness(),
        ]);
        setStatus(currentStatus);
        setInvoice(invoiceResult);
        setContract(contractResult);
        setReadiness(readinessResult);
        if (currentStatus.reconciled) setSummary(await api.current());
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Could not load product data");
      } finally { setLoading(false); }
    })();
  }, []);
  return { status, invoice, contract, summary, readiness, loading, error, setSummary };
}

export function OverviewPage() {
  const navigate = useNavigate();
  const { invoice, contract, summary, readiness, loading, error } = useProductData();
  if (loading) return <LoadingPage />;
  if (error || !invoice || !contract || !readiness) return <ErrorPage message={error} />;
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
        <MetricCard label="Submitted invoice" value={formatUsd(invoice.submitted_amount)} helper={`${invoice.claimed_outcomes.toLocaleString()} vendor claims`} icon={<TemplateIcon name="receipt" />} />
        <MetricCard label="Evidence coverage" value={`${readiness.totals.claim_coverage_percent.toFixed(2)}%`} helper={`${readiness.totals.raw_records.toLocaleString()} source records collected`} tone="success" icon={<TemplateIcon name="data" />} />
        <MetricCard label="Secondary-key matches" value={readiness.totals.secondary_matches.toLocaleString()} helper="Resolved without a shared outcome ID" tone="warning" icon={<TemplateIcon name="ledger" />} />
        <MetricCard label="Approved contract rules" value={`${readiness.totals.contract_rules_approved}`} helper="Customer-approved and versioned" icon={<TemplateIcon name="shield" />} />
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
            <Box className="template-detail-row"><span>Direct outcome-ID matches</span><strong>{readiness.totals.direct_matches.toLocaleString()}</strong></Box>
            <Box className="template-detail-row"><span>Verified secondary-key matches</span><strong>{readiness.totals.secondary_matches.toLocaleString()}</strong></Box>
            <Box className="template-detail-row"><span>Records awaiting identity review</span><strong>{readiness.totals.review_records.toLocaleString()}</strong></Box>
          </Stack>
          <Button sx={{ mt: 2 }} onClick={() => navigate("/demo/data-sources")}>Inspect data collection</Button>
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
  const [readiness, setReadiness] = useState<DataReadiness | null>(null);
  const [samples, setSamples] = useState<DataSourceSamples | null>(null);
  const [selectedSource, setSelectedSource] = useState("payment_processor");
  const [selectedRecord, setSelectedRecord] = useState<RawRecordSample | null>(null);
  const [loading, setLoading] = useState(true);
  const [sampleLoading, setSampleLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        setReadiness(await api.dataReadiness());
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Could not load ingestion readiness");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!readiness) return;
    (async () => {
      setSampleLoading(true);
      try {
        const result = await api.sourceSamples(selectedSource, selectedSource === "payment_processor" ? "OUT-004821" : undefined, 8);
        setSamples(result);
        setSelectedRecord(result.records[0] ?? null);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Could not load source records");
      } finally {
        setSampleLoading(false);
      }
    })();
  }, [readiness, selectedSource]);

  if (loading) return <LoadingPage />;
  if (error || !readiness) return <ErrorPage message={error} />;
  const totals = readiness.totals;

  return (
    <PageFrame>
      <Alert severity="info" className="template-disclosure">
        <strong>Synthetic source records, production-shaped pipeline.</strong> The values are generated, but the demo begins with vendor, support, payment, product, billing, identity, and contract-shaped records before normalization and matching.
      </Alert>
      <PageHeader
        eyebrow="Ingestion and evidence attribution"
        title="How real customer data enters Evidue"
        body="Evidue does not expect one clean outcome table. It collects read-only records from several systems, preserves each source payload, resolves identity, and builds a canonical evidence record before any charge is evaluated."
      />

      <Box className="template-stats-grid">
        <MetricCard label="Source records received" value={totals.raw_records.toLocaleString()} helper={`${totals.sampled_raw_records.toLocaleString()} representative payloads inspectable in the demo`} icon={<TemplateIcon name="data" />} />
        <MetricCard label="Vendor claims" value={totals.claimed_outcomes.toLocaleString()} helper="Outcome-level invoice manifest" icon={<TemplateIcon name="receipt" />} />
        <MetricCard label="Secondary identity joins" value={totals.secondary_matches.toLocaleString()} helper="Matched without a source outcome ID" tone="warning" icon={<TemplateIcon name="ledger" />} />
        <MetricCard label="Claim evidence coverage" value={`${totals.claim_coverage_percent.toFixed(2)}%`} helper={`${totals.review_records} claims require identity review`} tone="success" icon={<TemplateIcon name="check" />} />
      </Box>

      <SectionCard title="The ingestion path" eyebrow="Same stages used in production">
        <Box className="ingestion-pipeline">
          {readiness.pipeline.map((step, index) => (
            <Box className="ingestion-stage" key={step.id}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <Box>
                <Typography fontWeight={700}>{step.label}</Typography>
                <Typography variant="body2" color="text.secondary">{step.description}</Typography>
              </Box>
              {index < readiness.pipeline.length - 1 && <TemplateIcon name="arrow" />}
            </Box>
          ))}
        </Box>
      </SectionCard>

      <SectionCard title="Collection plan by source" eyebrow="Demo fixture → production connection">
        <TableContainer className="source-collection-table">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Source</TableCell>
                <TableCell>Authority</TableCell>
                <TableCell>Demo input</TableCell>
                <TableCell>Production collection</TableCell>
                <TableCell>Cadence</TableCell>
                <TableCell align="right">Records</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {readiness.sources.map((source) => (
                <TableRow key={source.id} selected={selectedSource === source.id} hover>
                  <TableCell>
                    <Typography fontWeight={700}>{source.name}</Typography>
                    <Typography variant="caption" color="text.secondary">{source.owner} · {source.category}</Typography>
                  </TableCell>
                  <TableCell><Chip label={source.authority} size="small" variant="outlined" /></TableCell>
                  <TableCell>{source.collection_method}</TableCell>
                  <TableCell>{source.production_method}</TableCell>
                  <TableCell>{source.schedule}</TableCell>
                  <TableCell align="right" className="mono">{source.raw_records.toLocaleString()}</TableCell>
                  <TableCell align="right">
                    <Button size="small" onClick={() => setSelectedSource(source.id)}>Inspect</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </SectionCard>

      <SectionCard
        title="Raw record → normalized evidence"
        eyebrow="Inspect the transformation"
        action={sampleLoading ? <CircularProgress size={20} /> : <Chip label={samples?.source.name ?? "Source"} size="small" />}
      >
        <Typography color="text.secondary" sx={{ mb: 2 }}>{samples?.source.description}</Typography>
        <Box className="raw-explorer">
          <Box className="raw-record-list">
            {(samples?.records ?? []).map((record) => (
              <button
                type="button"
                className={selectedRecord?.id === record.id ? "selected" : ""}
                onClick={() => setSelectedRecord(record)}
                key={record.id}
              >
                <Box>
                  <strong>{record.source_record_id}</strong>
                  <small>{record.record_type.replaceAll("_", " ")}</small>
                </Box>
                <Chip
                  label={record.match_status === "secondary" ? "Secondary match" : record.match_status ?? "Context"}
                  size="small"
                  color={record.match_status === "secondary" ? "warning" : "success"}
                  variant="outlined"
                />
              </button>
            ))}
            {!sampleLoading && (samples?.records.length ?? 0) === 0 && (
              <Alert severity="info">No representative raw payload is stored for this source in the current fixture.</Alert>
            )}
          </Box>

          {selectedRecord && (
            <Box className="record-transformation">
              <Box className="record-match-summary">
                <Box>
                  <Typography variant="overline" color="text.secondary">Attribution result</Typography>
                  <Typography variant="h6">{selectedRecord.matched_outcome_id ?? "Invoice-level context"}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Method</Typography>
                  <Typography fontWeight={700}>{selectedRecord.match_method?.replaceAll("_", " ")}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Confidence</Typography>
                  <Typography fontWeight={700}>{selectedRecord.match_confidence ? `${(Number(selectedRecord.match_confidence) * 100).toFixed(0)}%` : "—"}</Typography>
                </Box>
              </Box>
              <Alert severity={selectedRecord.match_status === "secondary" ? "warning" : "success"} sx={{ mb: 2 }}>
                {selectedRecord.match_reason}
              </Alert>
              <Box className="payload-comparison">
                <Box>
                  <Typography variant="overline" color="text.secondary">As received from source</Typography>
                  <pre>{JSON.stringify(selectedRecord.payload, null, 2)}</pre>
                </Box>
                <Box className="payload-arrow"><TemplateIcon name="arrow" /></Box>
                <Box>
                  <Typography variant="overline" color="text.secondary">Canonical Evidue record</Typography>
                  <pre>{JSON.stringify(selectedRecord.normalized_payload, null, 2)}</pre>
                </Box>
              </Box>
              <Box className="record-provenance-strip">
                <span>Schema <strong>{selectedRecord.schema_version}</strong></span>
                <span>Received <strong>{new Date(selectedRecord.received_at).toLocaleString()}</strong></span>
                <span className="mono">{selectedRecord.payload_hash.slice(0, 26)}…</span>
              </Box>
            </Box>
          )}
        </Box>
        {samples?.sample_note && <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 2 }}>{samples.sample_note}</Typography>}
      </SectionCard>

      <Box className="template-two-column">
        <SectionCard title="How the first customer connects" eyebrow="Practical rollout">
          <Stack divider={<Divider flexItem />}>
            {[
              ["01", "Start with exports", "Vendor claim CSV, support JSON/CSV, payment ledger, product-state export, identity map, and contract upload. Fastest route to the first real reconciliation."],
              ["02", "Move to warehouse views", "The customer exposes approved read-only Snowflake, BigQuery, or Redshift views. Evidue avoids broad production-system permissions."],
              ["03", "Add incremental connectors", "Use read-only APIs, webhooks, object storage, or SFTP for recurring invoice cycles and late-arriving evidence."],
            ].map(([number, title, body]) => (
              <Box className="template-action-row" key={number}>
                <span>{number}</span>
                <Box><strong>{title}</strong><small>{body}</small></Box>
              </Box>
            ))}
          </Stack>
        </SectionCard>
        <SectionCard title="What stays separate" eyebrow="Neutrality and access control">
          <Stack divider={<Divider flexItem />}>
            <Box className="template-detail-row"><span>Vendor claim and execution evidence</span><strong>Vendor-controlled</strong></Box>
            <Box className="template-detail-row"><span>Support, payment, product, and billing evidence</span><strong>Customer-controlled</strong></Box>
            <Box className="template-detail-row"><span>Executable contract rules</span><strong>Customer-approved</strong></Box>
            <Box className="template-detail-row"><span>Final payable decision</span><strong>Customer authority</strong></Box>
          </Stack>
          <Alert severity="warning" sx={{ mt: 2 }}>A vendor can improve its proof before invoicing, but cannot see private customer records or alter the customer determination.</Alert>
        </SectionCard>
      </Box>
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
