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
  TextField,
  Typography,
} from "@mui/material";
import { TemplateIcon } from "./TemplateIcons";
import { DecisionFlow } from "./DecisionLedger";
import { ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  api,
  Category,
  Contract,
  DataReadiness,
  DataSourceSamples,
  DemoStatus,
  Invoice,
  RawRecordSample,
  RuleCompilation,
  Summary,
} from "./api";
import { DashboardShell } from "./DashboardShell";
import { FeedbackCTA } from "./BetaApplicationCTA";
import { disclosure, formatUsd } from "./presentation";

export function ProductShell() {
  const [aboutOpen, setAboutOpen] = useState(false);
  return (
    <>
      <DashboardShell onOpenHowItWorks={() => setAboutOpen(true)} />
      <Drawer anchor="right" open={aboutOpen} onClose={() => setAboutOpen(false)}>
        <Box className="template-about-drawer">
          <Typography variant="overline" color="primary">Product workflow</Typography>
          <Typography variant="h4" sx={{ mt: 0.5 }}>One financial decision, one authority chain</Typography>
          <Typography color="text.secondary" sx={{ mt: 1 }}>Every Evidue surface uses the same control grammar: interpret the contract, authorize the rule set, verify customer proof, then act on the dollars.</Typography>
          <Box sx={{ mt: 3 }}><DecisionFlow /></Box>
          <Alert severity="info" sx={{ mt: 3 }}>
            Vendor preflight cannot alter customer-approved rules or private evidence. No model decides whether a charge is payable, and the customer retains final payment authority.
          </Alert>
        </Box>
      </Drawer>
    </>
  );
}

function PageFrame({ children, testId }: { children: ReactNode; testId?: string }) {
  return <Box className="template-page-container" data-testid={testId}>{children}</Box>;
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
        if (!currentStatus.public_demo && currentStatus.scenario_id !== "headline") {
          currentStatus = await api.reset("headline");
        }
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
  const { status, invoice, contract, summary, readiness, loading, error, setSummary } = useProductData();
  const [running, setRunning] = useState(false);
  const [actionError, setActionError] = useState("");

  if (loading) return <LoadingPage />;
  if (error || !status || !invoice || !contract || !readiness) return <ErrorPage message={error} />;

  const periodStart = new Date(invoice.billing_period_start).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const periodEnd = new Date(invoice.billing_period_end).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  const sourceCount = readiness.sources.length;
  const customerSources = readiness.sources.filter((source) => source.authority.toLowerCase().includes("customer")).length;
  const vendorSources = readiness.sources.filter((source) => source.authority.toLowerCase().includes("vendor")).length;

  async function runReconciliation() {
    if (status?.public_demo) return;
    setRunning(true);
    setActionError("");
    try {
      setSummary(await api.reconcile());
    } catch (requestError) {
      setActionError(requestError instanceof Error ? requestError.message : "Reconciliation failed");
    } finally {
      setRunning(false);
    }
  }

  const stages = [
    {
      label: "Invoice received",
      value: `${invoice.claimed_outcomes.toLocaleString()} claims`,
      detail: `${contract.vendor} submitted ${formatUsd(invoice.submitted_amount)}`,
      complete: true,
    },
    {
      label: "Evidence collected",
      value: `${readiness.totals.raw_records.toLocaleString()} records`,
      detail: `${sourceCount} vendor and customer sources`,
      complete: true,
    },
    {
      label: "Identity resolved",
      value: `${readiness.totals.claim_coverage_percent.toFixed(2)}% coverage`,
      detail: `${readiness.totals.secondary_matches} claims required secondary-key joins`,
      complete: readiness.totals.review_records === 0,
    },
    {
      label: "Payable determined",
      value: summary ? formatUsd(summary.confirmed_payable_amount) : "Not run",
      detail: summary ? `${formatUsd(summary.recommended_deduction)} supported deduction` : "Run the customer-side contract evaluation",
      complete: Boolean(summary),
    },
  ];

  return (
    <PageFrame testId="overview-page">
      <Alert severity="warning" className="template-disclosure"><strong>Synthetic demonstration data.</strong> {disclosure}</Alert>
      <PageHeader
        eyebrow="Independent control for outcome-priced AI"
        title="Know what the AI vendor actually earned"
        body="Evidue joins the vendor invoice to customer-owned operational evidence, applies customer-approved contract rules, and gives finance a reproducible payable amount—not a quality score."
        action={
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
            <Button variant="outlined" onClick={() => navigate("/demo/data-sources?source=payment_processor&inspect=1")}>Inspect example evidence</Button>
            <Button
              variant="contained"
              disabled={running || (!summary && status.public_demo)}
              onClick={summary ? () => navigate("/demo/invoices/current") : runReconciliation}
            >
              {running ? "Reconciling…" : summary ? "Open full decision" : status.public_demo ? "Decision unavailable" : "Run June reconciliation"}
            </Button>
          </Stack>
        }
      />
      {!summary && status.public_demo && (
        <Alert severity="info" sx={{ mb: 2 }}>
          This public preview is read-only. Open a private pilot workspace to run a new reconciliation; the public demo only exposes recorded deterministic results.
        </Alert>
      )}
      {actionError && <Alert severity="error" sx={{ mb: 2 }}>{actionError}</Alert>}

      <Card className="overview-command-card">
        <CardContent>
          <Box className="overview-command-main">
            <Box>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                <Chip label={summary ? "Decision ready" : "Evidence ready"} color={summary ? "success" : "warning"} size="small" />
                <Typography variant="caption" className="mono">{invoice.invoice_id}</Typography>
              </Stack>
              <Typography variant="h4" sx={{ mt: 1.5 }}>June vendor invoice</Typography>
              <Typography color="text.secondary">{contract.vendor} bills {contract.customer} for completed AI-agent outcomes.</Typography>
              <Box className="overview-invoice-meta">
                <span><small>Billing period</small><strong>{periodStart}–{periodEnd}</strong></span>
                <span><small>Unit price</small><strong>{formatUsd(contract.price_per_outcome)}</strong></span>
                <span><small>Claims</small><strong>{invoice.claimed_outcomes.toLocaleString()}</strong></span>
                <span><small>Contract rules</small><strong>{contract.clauses.length}</strong></span>
              </Box>
            </Box>
            <Box className="overview-decision-panel" aria-label="Current invoice decision">
              <Typography variant="overline" color="text.secondary">Submitted</Typography>
              <Typography className="overview-submitted-amount">{formatUsd(invoice.submitted_amount)}</Typography>
              <Divider sx={{ my: 1.5 }} />
              <Box className="overview-decision-row">
                <span>Supported payable</span>
                <strong className={summary ? "payable" : "pending"}>{summary ? formatUsd(summary.confirmed_payable_amount) : "Pending"}</strong>
              </Box>
              <Box className="overview-decision-row">
                <span>Supported deduction</span>
                <strong className={summary ? "disputed" : "pending"}>{summary ? formatUsd(summary.recommended_deduction) : "Pending"}</strong>
              </Box>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1.5, display: "block" }}>
                {summary ? `${summary.payable_outcomes.toLocaleString()} payable · ${summary.disputed_outcomes.toLocaleString()} disputed` : "No financial result is shown until the deterministic rules run."}
              </Typography>
            </Box>
          </Box>
        </CardContent>
      </Card>

      <section className="overview-decision-path" aria-labelledby="decision-path-title">
        <Box className="section-intro">
          <Typography variant="overline" color="primary">Decision path</Typography>
          <Typography variant="h4" id="decision-path-title">How Evidue reaches a payable amount</Typography>
          <Typography color="text.secondary">Each stage is inspectable. Evidence attribution is completed before contract rules can affect money.</Typography>
        </Box>
        <Box className="overview-stage-grid">
          {stages.map((stage, index) => (
            <Box className={`overview-stage ${stage.complete ? "complete" : "pending"}`} key={stage.label}>
              <span className="overview-stage-marker">{stage.complete ? "✓" : String(index + 1).padStart(2, "0")}</span>
              <Typography variant="overline" color="text.secondary">{stage.label}</Typography>
              <Typography variant="h6">{stage.value}</Typography>
              <Typography variant="body2" color="text.secondary">{stage.detail}</Typography>
            </Box>
          ))}
        </Box>
      </section>

      <Box className="template-two-column overview-detail-grid">
        <SectionCard
          title={summary ? "What changed the invoice" : "What the contract will test"}
          eyebrow={summary ? "Confirmed deductions" : "Eight executable controls"}
        >
          <Box className="overview-rule-grid">
            {summary
              ? (Object.entries(summary.categories) as Array<[string, Category]>).map(([ruleId, category]) => (
                  <Box className="overview-rule-item overview-deduction-item" key={ruleId}>
                    <Chip label={ruleId} size="small" />
                    <Box>
                      <strong>{category.label}</strong>
                      <small>{category.count.toLocaleString()} charges</small>
                    </Box>
                    <strong className="money">−{formatUsd(category.amount)}</strong>
                  </Box>
                ))
              : contract.clauses.map((clause) => (
                  <Box className="overview-rule-item" key={clause.id}>
                    <Chip label={clause.rule.id} size="small" />
                    <Box>
                      <strong>{clause.rule.title}</strong>
                      <small>{clause.rule.consequence}</small>
                    </Box>
                  </Box>
                ))}
          </Box>
          <Button sx={{ mt: 2 }} onClick={() => navigate(summary ? "/demo/invoices/current" : "/demo/contracts/current")}>
            {summary ? "Review all disputed claims" : "View approved contract mapping"}
          </Button>
        </SectionCard>

        <SectionCard title="Example charge path" eyebrow="OUT-004821 · refund claim">
          <Box className="example-evidence-flow">
            <Box className="example-evidence-step">
              <span>1</span><Box><strong>Vendor assertion</strong><small>Refund marked resolved by agent version refund-v2.4.</small></Box>
            </Box>
            <Box className="example-evidence-step">
              <span>2</span><Box><strong>Customer evidence</strong><small>Payment processor record and support audit trail are available.</small></Box>
            </Box>
            <Box className="example-evidence-step">
              <span>3</span><Box><strong>Contract determination</strong><small>{summary ? "Processor rejection and late human completion make the charge non-payable." : "Status remains pending until the customer-side rules run."}</small></Box>
            </Box>
          </Box>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ mt: 2 }}>
            <Button variant="outlined" onClick={() => navigate("/demo/data-sources?source=payment_processor&inspect=1")}>Inspect original records</Button>
            <Button onClick={() => navigate("/demo/invoices/current")}>Open Evidue reconciliation</Button>
          </Stack>
        </SectionCard>
      </Box>

      <Alert severity="info" sx={{ mt: 2 }}>
        <Stack direction={{ xs: "column", sm: "row" }} alignItems={{ sm: "center" }} justifyContent="space-between" spacing={1}>
          <span>Have feedback on this technical preview or the invoice-review workflow?</span>
          <FeedbackCTA />
        </Stack>
      </Alert>

      <Box data-testid="product-story">
        <SectionCard title="Evidence and authority stay separated" eyebrow="Neutral financial infrastructure">
        <Box className="overview-authority-grid">
          <Box><Typography variant="overline" color="text.secondary">Vendor side</Typography><Typography variant="h6">{vendorSources} evidence sources</Typography><Typography variant="body2" color="text.secondary">Claims and execution proof can support an invoice, but cannot declare it payable.</Typography></Box>
          <Box><Typography variant="overline" color="text.secondary">Customer side</Typography><Typography variant="h6">{customerSources} private sources</Typography><Typography variant="body2" color="text.secondary">Support, payment, product, billing, and identity records remain customer-controlled.</Typography></Box>
          <Box><Typography variant="overline" color="text.secondary">Decision authority</Typography><Typography variant="h6">Customer-approved rules</Typography><Typography variant="body2" color="text.secondary">No model or vendor system can alter the final payment recommendation.</Typography></Box>
        </Box>
        <Box className="template-product-flow" sx={{ mt: 2 }}>
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
          <button onClick={() => navigate("/demo/invoices/current?outcome=OUT-004821")}>
            <Box className="template-flow-icon"><TemplateIcon name="verify" /></Box>
            <Box><strong>Evidue</strong><small>Customer control · Should we pay this charge?</small></Box>
            <TemplateIcon name="arrow" />
          </button>
        </Box>
        </SectionCard>
      </Box>
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
            <TableCell><strong>Nova Support AI</strong></TableCell><TableCell>June 2026</TableCell><TableCell align="right">{formatUsd(invoice.submitted_amount)}</TableCell><TableCell align="right">{summary ? formatUsd(summary.confirmed_payable_amount) : "Pending"}</TableCell><TableCell><Chip label={summary ? "Ready to approve" : "Ready to reconcile"} color={summary ? "success" : "warning"} size="small" /></TableCell><TableCell align="right"><Button onClick={() => navigate("/demo/invoices/current?outcome=OUT-004821")}>Open</Button></TableCell>
            </TableRow>
            <TableRow><TableCell colSpan={6}><Typography variant="caption" color="text.secondary">Only the June invoice is a fully interactive fixture in this demonstration.</Typography></TableCell></TableRow>
          </TableBody>
        </Table>
      </TableContainer>
    </PageFrame>
  );
}

function compilationStatusColor(status: RuleCompilation["status"]): "success" | "warning" | "default" {
  if (status === "approved") return "success";
  if (status === "pending_approval") return "warning";
  return "default";
}

function ruleFingerprint(rule: RuleCompilation["rules"][number]): string {
  return JSON.stringify({
    operation: rule.operation,
    parameters: rule.parameters,
    consequence: rule.consequence,
    priority: rule.priority,
    evidence_required: rule.evidence_required,
    clause_text: rule.clause_text,
  });
}

export function ContractsPage() {
  const [demoStatus, setDemoStatus] = useState<DemoStatus | null>(null);
  const [contract, setContract] = useState<Contract | null>(null);
  const [history, setHistory] = useState<RuleCompilation[]>([]);
  const [draft, setDraft] = useState("");
  const [sourceDocument, setSourceDocument] = useState("Acme-Nova-Outcome-Pricing-Order-Form.pdf");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [workingAction, setWorkingAction] = useState<"compile" | "approve" | null>(null);
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async (preserveDraft = true) => {
    const [contractResult, historyResult] = await Promise.all([api.contract(), api.compilations()]);
    setContract(contractResult);
    setHistory(historyResult);
    setSourceDocument(contractResult.latest_compilation.source_document);
    if (!preserveDraft || !draft) {
      const visibleSource = contractResult.latest_compilation.status === "pending_approval"
        ? contractResult.latest_compilation.source_text
        : contractResult.contract_text;
      setDraft(visibleSource);
    }
    return contractResult;
  }, [draft]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setLoadError("");
      try {
        const [contractResult, historyResult, statusResult] = await Promise.all([api.contract(), api.compilations(), api.status()]);
        if (cancelled) return;
        setContract(contractResult);
        setHistory(historyResult);
        setDraft(
          contractResult.latest_compilation.status === "pending_approval"
            ? contractResult.latest_compilation.source_text
            : contractResult.contract_text,
        );
        setSourceDocument(contractResult.latest_compilation.source_document);
        setDemoStatus(statusResult);
      } catch (requestError) {
        if (!cancelled) setLoadError(requestError instanceof Error ? requestError.message : "Could not load contract controls");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  async function compileRules(mode: "auto" | "recorded") {
    if (!contract || demoStatus?.public_demo) return;
    const text = mode === "recorded" ? contract.demo_contract_text : draft;
    setWorkingAction("compile");
    setActionError("");
    setNotice("");
    if (mode === "recorded") {
      setDraft(contract.demo_contract_text);
      setSourceDocument("Acme-Nova-Outcome-Pricing-Order-Form.pdf");
    }
    try {
      const proposal = await api.compileContract(
        mode,
        text,
        mode === "recorded" ? "Acme-Nova-Outcome-Pricing-Order-Form.pdf" : sourceDocument,
      );
      await refresh(true);
      setNotice(
        proposal.live_model_call
          ? `Gemini produced proposal v${proposal.version}. It is validated but cannot affect an invoice until a person approves it.`
          : `Recorded Gemini proposal v${proposal.version} was replayed and validated for the bundled contract.`,
      );
    } catch (requestError) {
      setActionError(requestError instanceof Error ? requestError.message : "Rule compilation failed");
    } finally {
      setWorkingAction(null);
    }
  }

  async function approveRules() {
    if (!contract || demoStatus?.public_demo || contract.latest_compilation.status !== "pending_approval") return;
    setWorkingAction("approve");
    setActionError("");
    setNotice("");
    try {
      const approved = await api.approveCompilation(contract.latest_compilation.id);
      await refresh(true);
      setNotice(
        `Version ${approved.version} is active. Existing determinations were invalidated and the next reconciliation will run only the deterministic program shown below.`,
      );
    } catch (requestError) {
      setActionError(requestError instanceof Error ? requestError.message : "Approval failed");
    } finally {
      setWorkingAction(null);
    }
  }

  async function validateRecordedProposal() {
    setWorkingAction("compile");
    setActionError("");
    setNotice("");
    try {
      const result = await api.validateRecordedProposal();
      setNotice(`Recorded proposal validated: ${result.rule_count} allowlisted rules in ${result.duration_ms} ms. No model call or shared-state write occurred.`);
    } catch (requestError) {
      setActionError(requestError instanceof Error ? requestError.message : "Rule validation failed");
    } finally {
      setWorkingAction(null);
    }
  }

  if (loading) return <LoadingPage />;
  if (loadError || !contract) return <ErrorPage message={loadError || "Contract controls are unavailable"} />;

  const active = contract.compilation;
  const latest = contract.latest_compilation;
  const pending = latest.status === "pending_approval";
  const proposal = pending ? latest : active;
  const sourceTextChanged = draft.trim() !== proposal.source_text.trim();
  const sourceDocumentChanged = sourceDocument.trim() !== proposal.source_document.trim();
  const draftChanged = sourceTextChanged || sourceDocumentChanged;
  const customDraftWithoutKey = !contract.live_compilation_available && draft.trim() !== contract.demo_contract_text.trim();
  const activeRules = new Map(active.rules.map((rule) => [rule.id, rule]));
  const proposalRules = new Map(proposal.rules.map((rule) => [rule.id, rule]));
  const changedRules = proposal.rules.filter((rule) => {
    const previous = activeRules.get(rule.id);
    return !previous || ruleFingerprint(previous) !== ruleFingerprint(rule);
  }).length;
  const removedRules = active.rules.filter((rule) => !proposalRules.has(rule.id)).length;
  const publicDemo = demoStatus?.public_demo === true;

  return (
    <PageFrame testId="contracts-page">
      <PageHeader
        eyebrow={publicDemo ? "Approved rule program" : "Contract rule compiler"}
        title={publicDemo ? "Approved billing rules" : "Compile contract language into an approvable rule program"}
        body={publicDemo ? "Public technical preview: shared state is read-only, but selected rule validation and deterministic evaluations can be rerun safely." : "The visible contract text is sent to Gemini, the response is constrained to allowlisted operations, and a human-approved immutable version is the only input the deterministic reconciliation engine can execute."}
        action={
          publicDemo ? <Button variant="contained" onClick={() => void validateRecordedProposal()} disabled={workingAction !== null}>Validate recorded proposal</Button> : <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
            <Button
              variant="outlined"
              disabled={publicDemo || workingAction !== null}
              onClick={() => void compileRules("recorded")}
            >
              Replay recorded Gemini result
            </Button>
            <Button
              variant="contained"
              disabled={publicDemo || workingAction !== null || draft.trim().length < 50 || customDraftWithoutKey}
              onClick={() => void compileRules("auto")}
              startIcon={workingAction === "compile" ? <CircularProgress size={18} color="inherit" /> : undefined}
            >
              {contract.live_compilation_available ? "Compile with Gemini" : "Compile bundled contract"}
            </Button>
          </Stack>
        }
      />

      {actionError && <Alert severity="error" sx={{ mb: 2 }}>{actionError}</Alert>}
      {publicDemo && <Alert severity="info" sx={{ mb: 2 }}>Public technical preview: shared state is read-only, but selected rule validation and deterministic evaluations can be rerun safely.</Alert>}
      {notice && <Alert severity="success" sx={{ mb: 2 }}>{notice}</Alert>}
      {customDraftWithoutKey && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          This draft differs from the bundled contract. Add <code>GEMINI_API_KEY</code> to compile custom terms, or restore/replay the recorded demo contract.
        </Alert>
      )}

      <Alert severity="info" sx={{ mb: 2 }}>
        The LLM proposes contract rules. A human approves and versions them. Deterministic code evaluates every invoice line.
      </Alert>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        The bundled proposal was previously generated by Gemini and validated against Evidue’s restricted rule schema. Viewing this page does not trigger a live model call.
      </Typography>

      <Box className="contract-compiler-flow" aria-label="Contract compilation trust boundary">
        {[
          ["1", "Contract source", "Editable natural-language terms"],
          ["2", "Gemini proposal", "No access to invoice outcomes"],
          ["3", "Schema validator", "Allowlisted operations only"],
          ["4", pending ? "Human approval" : "Approved version", pending ? "Required before execution" : `Active v${active.version}`],
          ["5", "Deterministic engine", "Evaluates evidence and money"],
        ].map(([number, title, body], index) => (
          <Box className={`contract-compiler-stage ${index === 3 && pending ? "pending" : ""}`} key={number}>
            <span>{number}</span><Box><strong>{title}</strong><small>{body}</small></Box>
          </Box>
        ))}
      </Box>

      <Box className="template-stats-grid template-stats-grid-3" sx={{ mt: 2 }}>
        <MetricCard label="Active program" value={`v${active.version}`} helper={`${active.rules.length} rules · ${active.id}`} tone="success" />
        <MetricCard label="Latest proposal" value={`v${proposal.version}`} helper={pending ? `${changedRules} changed/added · ${removedRules} removed` : "Matches active program"} tone={pending ? "warning" : "neutral"} />
        <MetricCard label="Compiler mode" value={proposal.live_model_call ? "Live Gemini" : "Recorded Gemini"} helper={`${proposal.model} · schema constrained`} />
      </Box>

      <Box className="contract-workbench">
        <SectionCard
          title="Contract source"
          eyebrow="Exactly what the compiler reads"
          action={!publicDemo ? (
            <Button
              size="small"
              disabled={publicDemo || workingAction !== null || draft === contract.demo_contract_text}
              onClick={() => {
                setDraft(contract.demo_contract_text);
                setSourceDocument("Acme-Nova-Outcome-Pricing-Order-Form.pdf");
                setActionError("");
              }}
            >
              Restore bundled contract
            </Button>
          ) : undefined}
        >
          {publicDemo ? <Typography component="pre" className="contract-excerpt">{proposal.source_text}</Typography> : <><TextField
            label="Source document"
            fullWidth
            value={sourceDocument}
            onChange={(event) => setSourceDocument(event.target.value)}
            disabled={publicDemo || workingAction !== null}
            sx={{ mb: 1.5 }}
          />
          <TextField
            label="Contract text"
            fullWidth
            multiline
            minRows={15}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={publicDemo || workingAction !== null}
            helperText={`${draft.length.toLocaleString()} characters${draftChanged ? " · source differs from the displayed proposal" : " · exact source for the displayed proposal"}`}
          />
          </>}
        </SectionCard>

        <SectionCard
          title={pending ? `Review proposal v${proposal.version}` : `Approved program v${active.version}`}
          eyebrow="Validated compiler output"
          action={pending ? (
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
              <Button
                variant="outlined"
                disabled={publicDemo || workingAction !== null || !draftChanged}
                onClick={() => {
                  setDraft(proposal.source_text);
                  setSourceDocument(proposal.source_document);
                  setActionError("");
                }}
              >
                Load proposal source
              </Button>
              <Button
                variant="contained"
                color="success"
                disabled={publicDemo || workingAction !== null || draftChanged}
                onClick={() => void approveRules()}
                startIcon={workingAction === "approve" ? <CircularProgress size={18} color="inherit" /> : undefined}
              >
                Approve immutable version
              </Button>
            </Stack>
          ) : <Chip label="Active and executable" color="success" size="small" />}
        >
          {pending && draftChanged && (
            <Alert severity="error" sx={{ mb: 1.5 }}>
              The visible source no longer matches proposal v{proposal.version}. Recompile it, or load the exact proposal source before approval.
            </Alert>
          )}
          <Alert severity={pending ? "warning" : "info"}>
            {pending
              ? "This proposal is inert. Approval replaces the active rule program and invalidates previous reconciliation results."
              : proposal.safety_boundary}
          </Alert>
          {proposal.fallback_reason && <Alert severity="warning" sx={{ mt: 1.5 }}>{proposal.fallback_reason}</Alert>}
          <Stack direction="row" gap={0.75} flexWrap="wrap" sx={{ mt: 1.5 }}>
            <Chip size="small" color="success" variant="outlined" label="JSON schema valid" />
            <Chip size="small" color="success" variant="outlined" label="Operations allowlisted" />
            <Chip size="small" color="success" variant="outlined" label="Rule IDs unique" />
            <Chip size="small" color="success" variant="outlined" label="Priorities unique" />
          </Stack>
          <Box className="contract-audit-grid">
            <Box><small>Source hash</small><code>{proposal.source_hash}</code></Box>
            <Box><small>Prompt hash</small><code>{proposal.prompt_hash}</code></Box>
            <Box><small>Created</small><strong>{new Date(proposal.created_at).toLocaleString("en-US")}</strong></Box>
            <Box><small>Compiler</small><strong>{proposal.provider} / {proposal.compiler_version}</strong></Box>
          </Box>
        </SectionCard>
      </Box>

      <SectionCard
        title="Executable rule mapping"
        eyebrow={pending ? "Proposed changes versus active version" : "Rules used by reconciliation"}
        action={<Chip label={`${proposal.rules.length} validated rules`} variant="outlined" size="small" />}
      >
        <Stack spacing={1.25}>
          {[...proposal.rules].sort((a, b) => a.priority - b.priority).map((rule) => {
            const previous = activeRules.get(rule.id);
            const change = !pending ? "active" : !previous ? "added" : ruleFingerprint(previous) !== ruleFingerprint(rule) ? "changed" : "unchanged";
            return (
              <Box className="contract-rule-row" key={rule.id}>
                <Box className="contract-rule-identity">
                  <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap">
                    <Chip label={rule.id} size="small" color="primary" />
                    <Chip
                      label={change}
                      size="small"
                      color={change === "added" || change === "changed" ? "warning" : change === "active" ? "success" : "default"}
                      variant={change === "unchanged" ? "outlined" : "filled"}
                    />
                    <Typography variant="h6">{rule.title}</Typography>
                  </Stack>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>{rule.description}</Typography>
                  <Typography variant="body2" sx={{ mt: 1 }}><strong>Clause:</strong> {rule.clause_text}</Typography>
                </Box>
                <Box className="contract-rule-program">
                  <Typography variant="overline" color="text.secondary">Deterministic program</Typography>
                  <code>{rule.operation}</code>
                  <Typography variant="caption" color="text.secondary">Priority {rule.priority} · failure → {rule.consequence}</Typography>
                  <Typography component="pre" variant="caption">{JSON.stringify(rule.parameters, null, 2)}</Typography>
                </Box>
                <Box className="contract-rule-evidence">
                  <Typography variant="overline" color="text.secondary">Required evidence</Typography>
                  <Stack direction="row" gap={0.5} flexWrap="wrap">
                    {rule.evidence_required.map((evidence) => <Chip key={evidence} label={evidence} size="small" variant="outlined" />)}
                  </Stack>
                </Box>
              </Box>
            );
          })}
          {pending && active.rules.filter((rule) => !proposalRules.has(rule.id)).map((rule) => (
            <Box className="contract-rule-row removed" key={rule.id}>
              <Box className="contract-rule-identity">
                <Stack direction="row" spacing={0.75} alignItems="center"><Chip label={rule.id} size="small" /><Chip label="removed" size="small" color="error" /><Typography variant="h6">{rule.title}</Typography></Stack>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>This active rule would not exist in the proposed version.</Typography>
              </Box>
            </Box>
          ))}
        </Stack>
      </SectionCard>

      <SectionCard title="Compilation history" eyebrow="Versioned audit trail">
        <TableContainer>
          <Table size="small">
            <TableHead><TableRow><TableCell>Version</TableCell><TableCell>Status</TableCell><TableCell>Compiler</TableCell><TableCell>Rules</TableCell><TableCell>Created</TableCell><TableCell>Source hash</TableCell></TableRow></TableHead>
            <TableBody>
              {history.map((item) => (
                <TableRow key={item.id} selected={item.id === proposal.id}>
                  <TableCell><strong>v{item.version}</strong><Typography variant="caption" display="block" color="text.secondary">{item.id}</Typography></TableCell>
                  <TableCell><Chip size="small" label={item.status.replace("_", " ")} color={compilationStatusColor(item.status)} /></TableCell>
                  <TableCell>{item.live_model_call ? "Live Gemini" : "Recorded Gemini"}</TableCell>
                  <TableCell>{item.rules.length}</TableCell>
                  <TableCell>{new Date(item.created_at).toLocaleString("en-US")}</TableCell>
                  <TableCell><code>{item.source_hash.slice(0, 20)}…</code></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </SectionCard>
    </PageFrame>
  );
}

export function DisputesPage() {
  const navigate = useNavigate();
  const { summary, loading, error } = useProductData();
  if (loading) return <LoadingPage />;
  if (error) return <ErrorPage message={error} />;
  if (!summary) return <PageFrame><Alert severity="info">Run the June reconciliation before preparing the dispute package.</Alert><Button sx={{ mt: 2 }} variant="contained" onClick={() => navigate("/demo/invoices/current")}>Open Evidue reconciliation</Button></PageFrame>;
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
  const [searchParams] = useSearchParams();
  const requestedSource = searchParams.get("source") ?? "payment_processor";
  const shouldOpenRequestedSource = searchParams.get("inspect") === "1";
  const [readiness, setReadiness] = useState<DataReadiness | null>(null);
  const [samples, setSamples] = useState<DataSourceSamples | null>(null);
  const [selectedSource, setSelectedSource] = useState(requestedSource);
  const [selectedRecord, setSelectedRecord] = useState<RawRecordSample | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sampleLoading, setSampleLoading] = useState(false);
  const [error, setError] = useState("");
  const [sampleError, setSampleError] = useState("");
  const sampleRequestId = useRef(0);

  const loadSourceSamples = useCallback(async (sourceId: string) => {
    const requestId = ++sampleRequestId.current;
    setSampleLoading(true);
    setSampleError("");
    setSamples(null);
    setSelectedRecord(null);
    try {
      const result = await api.sourceSamples(sourceId, sourceId === "payment_processor" ? "OUT-004821" : undefined, 8);
      if (requestId !== sampleRequestId.current) return;
      setSamples(result);
      setSelectedRecord(result.records[0] ?? null);
    } catch (requestError) {
      if (requestId !== sampleRequestId.current) return;
      setSampleError(requestError instanceof Error ? requestError.message : "Could not load source records");
    } finally {
      if (requestId === sampleRequestId.current) setSampleLoading(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const result = await api.dataReadiness();
        setReadiness(result);
        setSelectedSource(requestedSource);
        setInspectorOpen(shouldOpenRequestedSource);
        await loadSourceSamples(requestedSource);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Could not load ingestion readiness");
      } finally {
        setLoading(false);
      }
    })();
  }, [loadSourceSamples, requestedSource, shouldOpenRequestedSource]);

  function inspectSource(sourceId: string) {
    setSelectedSource(sourceId);
    setInspectorOpen(true);
    void loadSourceSamples(sourceId);
  }

  if (loading) return <LoadingPage />;
  if (error || !readiness) return <ErrorPage message={error} />;
  const totals = readiness.totals;
  const selectedSourceMetadata = readiness.sources.find((source) => source.id === selectedSource);

  return (
    <PageFrame testId="data-sources-page">
      <Alert severity="info" className="template-disclosure">
        <strong>Synthetic source records, production-shaped pipeline.</strong> The values are generated, but the demo begins with vendor, support, payment, product, billing, identity, and contract-shaped records before normalization and matching.
      </Alert>
      <PageHeader
        eyebrow="Ingestion and evidence attribution"
        title="How real customer data enters Evidue"
        body="Evidue does not expect one clean outcome table. It collects read-only records from several systems, preserves each source payload, resolves identity, and builds a canonical evidence record before any charge is evaluated."
        action={<Button variant="contained" onClick={() => inspectSource("payment_processor")}>Inspect rejected refund example</Button>}
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
        <Typography color="text.secondary" sx={{ mb: 2 }}>Choose any source to open its original payloads, normalized records, match method, confidence, schema version, and content hash.</Typography>
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
                    <Button
                      size="small"
                      aria-label={`Inspect ${source.name}`}
                      onClick={() => inspectSource(source.id)}
                    >
                      Inspect
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </SectionCard>

      <Box className="template-two-column">
        <SectionCard title="Example: a real claim spans multiple systems" eyebrow="OUT-004821">
          <Box className="example-evidence-flow">
            <Box className="example-evidence-step"><span>1</span><Box><strong>Vendor claim manifest</strong><small>Agent asserts that the refund was completed.</small></Box></Box>
            <Box className="example-evidence-step"><span>2</span><Box><strong>Payment processor</strong><small>The refund attempt is rejected and carries transaction processor-4821.</small></Box></Box>
            <Box className="example-evidence-step"><span>3</span><Box><strong>Support audit trail</strong><small>A human later completes the refund after the contractual window.</small></Box></Box>
          </Box>
          <Button variant="outlined" sx={{ mt: 2 }} onClick={() => inspectSource("payment_processor")}>Inspect the rejected payment record</Button>
        </SectionCard>
        <SectionCard title="What the inspector proves" eyebrow="Traceability">
          <Stack divider={<Divider flexItem />}>
            <Box className="template-detail-row"><span>Original source payload</span><strong>Preserved</strong></Box>
            <Box className="template-detail-row"><span>Normalized Evidue event</span><strong>Visible</strong></Box>
            <Box className="template-detail-row"><span>Identity match method</span><strong>Explained</strong></Box>
            <Box className="template-detail-row"><span>Content integrity</span><strong>SHA-256 hash</strong></Box>
          </Stack>
        </SectionCard>
      </Box>

      <Box className="template-two-column">
        <SectionCard title="How the first customer connects" eyebrow="Practical rollout">
          <Stack divider={<Divider flexItem />}>
            {readiness.onboarding.map((phase) => (
              <Box className="template-action-row" key={phase.phase}>
                <span>{phase.phase.padStart(2, "0")}</span>
                <Box><strong>{phase.label}</strong><small>{phase.description}</small></Box>
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

      <Drawer
        anchor="right"
        open={inspectorOpen}
        onClose={() => setInspectorOpen(false)}
        PaperProps={{ sx: { width: { xs: "100%", sm: "min(760px, 94vw)" } } }}
      >
        <Box className="source-inspector-drawer" data-testid="source-inspector" role="dialog" aria-modal="true" aria-labelledby="source-inspector-title" aria-busy={sampleLoading}>
          <Box className="source-inspector-header">
            <Box>
              <Typography variant="overline" color="primary">Raw source inspector</Typography>
              <Typography variant="h4" id="source-inspector-title">{selectedSourceMetadata?.name ?? "Source records"}</Typography>
              <Typography color="text.secondary">{selectedSourceMetadata?.description}</Typography>
            </Box>
            <Button variant="outlined" onClick={() => setInspectorOpen(false)}>Close inspector</Button>
          </Box>

          {selectedSourceMetadata && (
            <Box className="source-inspector-context">
              <span><small>Authority</small><strong>{selectedSourceMetadata.authority}</strong></span>
              <span><small>Production collection</small><strong>{selectedSourceMetadata.production_method}</strong></span>
              <span><small>Cadence</small><strong>{selectedSourceMetadata.schedule}</strong></span>
            </Box>
          )}

          {sampleLoading && <Box className="source-inspector-loading" role="status" aria-live="polite"><CircularProgress size={28} /><Typography>Loading representative source records…</Typography></Box>}
          {sampleError && <Alert severity="error" role="alert">{sampleError}</Alert>}

          {!sampleLoading && !sampleError && samples && (
            <>
              <Box className="raw-record-list source-inspector-records" aria-label="Representative source records">
                {samples.records.map((record) => (
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
              </Box>

              {samples.records.length === 0 && <Alert severity="info">No representative raw payload is stored for this source in the current fixture.</Alert>}

              {selectedRecord && (
                <Box className="record-transformation source-inspector-transformation">
                  <Box className="record-match-summary">
                    <Box><Typography variant="overline" color="text.secondary">Attribution result</Typography><Typography variant="h6">{selectedRecord.matched_outcome_id ?? "Invoice-level context"}</Typography></Box>
                    <Box><Typography variant="caption" color="text.secondary">Method</Typography><Typography fontWeight={700}>{selectedRecord.match_method?.replaceAll("_", " ") ?? "Context record"}</Typography></Box>
                    <Box><Typography variant="caption" color="text.secondary">Confidence</Typography><Typography fontWeight={700}>{selectedRecord.match_confidence ? `${(Number(selectedRecord.match_confidence) * 100).toFixed(0)}%` : "—"}</Typography></Box>
                  </Box>
                  {selectedRecord.match_reason && <Alert severity={selectedRecord.match_status === "secondary" ? "warning" : "success"} sx={{ mb: 2 }}>{selectedRecord.match_reason}</Alert>}
                  <Box className="payload-comparison">
                    <Box><Typography variant="overline" color="text.secondary">As received from source</Typography><pre>{JSON.stringify(selectedRecord.payload, null, 2)}</pre></Box>
                    <Box className="payload-arrow"><TemplateIcon name="arrow" /></Box>
                    <Box><Typography variant="overline" color="text.secondary">Canonical Evidue record</Typography><pre>{JSON.stringify(selectedRecord.normalized_payload, null, 2)}</pre></Box>
                  </Box>
                  <Box className="record-provenance-strip">
                    <span>Schema <strong>{selectedRecord.schema_version}</strong></span>
                    <span>Received <strong>{new Date(selectedRecord.received_at).toLocaleString()}</strong></span>
                    <span className="mono">{selectedRecord.payload_hash.slice(0, 32)}…</span>
                  </Box>
                </Box>
              )}
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 2 }}>{samples.sample_note}</Typography>
            </>
          )}
        </Box>
      </Drawer>
    </PageFrame>
  );
}

export function VendorPreflightPage() {
  const navigate = useNavigate();
  const { status, invoice, contract, summary: existingSummary, loading, error, setSummary } = useProductData();
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState("");
  const [summary, setLocalSummary] = useState<Summary | null>(existingSummary);
  useEffect(() => setLocalSummary(existingSummary), [existingSummary]);
  if (loading) return <LoadingPage />;
  if (error || !invoice || !contract) return <ErrorPage message={error} />;

  async function runPreflight() {
    if (status?.public_demo) return;
    setRunning(true); setRunError("");
    try { const result = await api.reconcile(); setLocalSummary(result); setSummary(result); }
    catch (requestError) { setRunError(requestError instanceof Error ? requestError.message : "Could not run preflight"); }
    finally { setRunning(false); }
  }

  return (
    <PageFrame>
      <Alert severity="info" sx={{ mb: 2 }}><strong>Demonstration evidence model.</strong> This synthetic demo uses one shared evidence fixture so both calculations are inspectable. Production vendor evidence and customer-private evidence remain separate.</Alert>
      <PageHeader eyebrow="Evidue Prove · Agent vendor workspace" title="Send an invoice you can defend" body="Preflight proposed outcome charges against approved billing rules before they reach the customer." action={status?.public_demo ? undefined : <Button variant="contained" disabled={running} onClick={runPreflight}>{running ? "Running preflight…" : "Run invoice preflight"}</Button>} />
      {status?.public_demo && <Alert severity="info" sx={{ mb: 2 }}>Public technical preview: shared state is read-only, but selected rule validation and deterministic evaluations can be rerun safely.</Alert>}
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
        <SectionCard title="Prove prepares. Evidue decides." eyebrow="Neutrality boundary">
          <Typography color="text.secondary">The vendor may improve evidence and remove unsupported claims. It cannot edit customer rules, customer evidence, internal notes, or the final payment recommendation.</Typography>
          <Box className="template-boundary-flow">
            <div><strong>Prove</strong><span>Vendor claim</span></div><TemplateIcon name="arrow" /><div><strong>Ledger</strong><span>Proof envelope</span></div><TemplateIcon name="arrow" /><div><strong>Evidue</strong><span>Customer decision</span></div>
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
              <Button sx={{ mt: 2 }} onClick={() => navigate("/demo/invoices/current?outcome=OUT-004821")}>Review customer-side evidence</Button>
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
        <SectionCard title="OUT-004821" eyebrow="Outcome receipt" action={<Chip label="Disputed by Evidue" color="error" size="small" />}>
          <Box className="template-receipt-grid">
            {[ ["Claimed outcome", "Refund completed"], ["Agent status", "Resolved"], ["Downstream status", "Processor rejected"], ["Contract window", "2 hours"], ["Customer result", "$0.00 payable"], ["Evidence state", "Complete"] ].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}
          </Box>
        </SectionCard>
        <SectionCard title="Proof that travels with the claim" eyebrow="Canonical receipt schema">
          <Box className="template-schema-grid">{["Stable outcome ID", "Customer and account IDs", "Agent and workflow version", "Claimed outcome and action", "Downstream source record", "Execution and completion timestamps", "Contract-rule version", "Evidence provenance"].map((field) => <span key={field}>✓ {field}</span>)}</Box>
          <Alert severity="info" sx={{ mt: 2 }}>A receipt supports a claim; it never self-declares the charge payable.</Alert>
          <Button href="/demo/invoices/current" sx={{ mt: 2 }}>Evidue reconciliation</Button>
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
