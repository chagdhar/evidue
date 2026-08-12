import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  Collapse,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  LinearProgress,
  MenuItem,
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
import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import WorkspaceShell from "./WorkspaceShell";
import {
  AIRVersion,
  AgreementBundleView,
  AgreementIRView,
  AuditEvent,
  clearPilotToken,
  CompilerAssurance,
  Determination,
  DerivedFact,
  FinanceView,
  InvoicePreview,
  loadPilotToken,
  MatchCandidate,
  PilotApiError,
  PilotContract,
  pilotApi,
  PilotStatus,
  Reconciliation,
  ReconciliationDelta,
  ReviewItem,
  savePilotToken,
  VerificationPlanEnvelope,
  WorkspaceConfig,
} from "./pilotApi";

export type PilotStage = "agreement" | "invoice" | "evidence" | "verification" | "review" | "export";

export function isPilotEvidenceReady(
  hasActiveInvoice: boolean,
  evidenceRequirementCount: number,
  verificationPlan: VerificationPlanEnvelope | null,
) {
  if (!hasActiveInvoice || !verificationPlan) return false;
  if (evidenceRequirementCount === 0) return true;
  const items = verificationPlan.plan.items;
  return items.length > 0 && items.every((item) => item.status === "ready");
}

export function recommendedPilotStage(input: {
  hasContract: boolean;
  contractApproved: boolean;
  approvedRulesStale: boolean;
  hasInvoice: boolean;
  evidenceReady: boolean;
  hasReconciliation: boolean;
  reconciliationNeedsReview: boolean;
}): PilotStage {
  if (!input.hasContract || !input.contractApproved || input.approvedRulesStale) return "agreement";
  if (!input.hasInvoice) return "invoice";
  if (!input.evidenceReady) return "evidence";
  if (!input.hasReconciliation) return "verification";
  if (input.reconciliationNeedsReview) return "review";
  return "export";
}

export function shouldFollowPilotRecommendation(
  previousRecommendation: PilotStage | null,
  nextRecommendation: PilotStage,
  stageTouched: boolean,
) {
  return previousRecommendation !== nextRecommendation || !stageTouched;
}

const pilotStages: Array<{ id: PilotStage; label: string; hint: string }> = [
  { id: "agreement", label: "Contract", hint: "Approve what counts" },
  { id: "invoice", label: "Invoice", hint: "Confirm what was billed" },
  { id: "evidence", label: "Evidence", hint: "Prove what happened" },
  { id: "verification", label: "Verification", hint: "Determine supported dollars" },
  { id: "review", label: "Review", hint: "Separate facts from action" },
  { id: "export", label: "Commercial action", hint: "Move the result into AP" },
];

const requiredInvoiceFields = ["outcome_id", "customer_id", "intent", "closed_at", "billed_amount"];

function money(value: string | number | undefined, currency = "USD"): string {
  const safeCurrency = /^[A-Z]{3}$/.test(currency) && currency !== "MULTI" ? currency : "USD";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: safeCurrency }).format(Number(value ?? 0));
}

function errorText(error: unknown): string {
  if (error instanceof PilotApiError || error instanceof Error) return error.message;
  return "An unexpected error occurred.";
}

function readable(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function financeVerificationMethod(value: string): string {
  const normalized = value.toLowerCase();
  if (["fully_executable", "deterministic", "automatic", "machine_executable"].includes(normalized)) return "Automatic";
  if (["human_attestation_required", "human_review", "manual", "manual_review"].includes(normalized)) return "Manual review needed";
  return readable(value);
}

function formatDate(value: string | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function exclusiveEndFromDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString();
}

function formatExclusiveEnd(value: string | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  date.setUTCDate(date.getUTCDate() - 1);
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function evidenceSourceExamples(item: FinanceView["evidence_needed"][number], config: WorkspaceConfig | null): string[] {
  const text = `${item.description} ${item.fact_types.join(" ")}`.toLowerCase();
  const values: string[] = [];
  if (/support|recontact|ticket|human|conversation|escalat/.test(text)) {
    if (config?.preferred_support_system) values.push(config.preferred_support_system);
    values.push("Zendesk", "Intercom", "Salesforce Service Cloud");
  } else if (/payment|refund|downstream|transaction|fulfillment/.test(text)) {
    if (config?.preferred_payment_system) values.push(config.preferred_payment_system);
    values.push("Stripe", "billing system", "order or product system");
  } else {
    if (config?.preferred_crm_system) values.push(config.preferred_crm_system);
    values.push("customer system of record", "CRM or product export");
  }
  return [...new Set(values)].slice(0, 4);
}

function evidenceGroupLabel(item: FinanceView["evidence_needed"][number], config: WorkspaceConfig | null): string {
  const text = `${item.description} ${item.fact_types.join(" ")} ${item.preferred_authority}`.toLowerCase();
  if (/support|ticket|conversation|recontact|escalat|human/.test(text)) return config?.preferred_support_system || "Support system";
  if (/payment|refund|transaction|billing/.test(text)) return config?.preferred_payment_system || "Payments & billing";
  if (/account|customer|identity|crm/.test(text)) return config?.preferred_crm_system || "Account mapping";
  if (/product|fulfillment|downstream|action/.test(text)) return "Product events";
  return "Customer system of record";
}

function Surface({
  title,
  eyebrow,
  complete,
  children,
  action,
}: {
  title: string;
  eyebrow: string;
  complete?: boolean;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <Card variant="outlined" className="finance-surface">
      <Box className="finance-surface-header">
        <Box>
          <Typography className="section-kicker">{eyebrow}</Typography>
          <Typography variant="h5" fontWeight={720}>{title}</Typography>
        </Box>
        <Stack direction="row" spacing={1} alignItems="center">
          {complete !== undefined && (
            <Chip
              size="small"
              variant="outlined"
              color={complete ? "success" : "warning"}
              label={complete ? "Ready" : "Action needed"}
            />
          )}
          {action}
        </Stack>
      </Box>
      <CardContent className="finance-surface-body">{children}</CardContent>
    </Card>
  );
}

type MetricTone = "neutral" | "primary" | "success" | "warning" | "error";

function Metric({ label, value, help, tone = "neutral" }: { label: string; value: string; help?: string; tone?: MetricTone }) {
  return (
    <Box className={`inline-metric ${tone}`}>
      <Typography className="inline-metric-label">{label}</Typography>
      <Typography className="inline-metric-value" title={value}>{value}</Typography>
      {help && <Typography className="inline-metric-help">{help}</Typography>}
    </Box>
  );
}

function StatusChip({ status }: { status: Determination["status"] }) {
  return (
    <Chip
      size="small"
      color={status === "payable" ? "success" : status === "disputed" ? "error" : "warning"}
      label={readable(status)}
    />
  );
}

function resolutionHint(row: Determination): string {
  const reason = (row.reason ?? "").toLowerCase();
  if (reason.includes("conflicting") || reason.includes("attribution"))
    return "Upload authoritative evidence from the system of record to replace conflicting data, then rerun reconciliation.";
  if (reason.includes("missing") || reason.includes("could not determine"))
    return "Add the relevant customer-system evidence export (support tickets, payment events, or CRM records) and rerun.";
  if (reason.includes("human"))
    return "This line requires manual verification. Review the evidence and confirm or dispute manually.";
  if (reason.includes("unsupported"))
    return "The contract includes a condition that cannot be verified mechanically. Review the clause and decide manually.";
  return "Review the evidence for this line. Add missing data or confirm the result, then rerun reconciliation.";
}

function Determinations({ rows, currency = "USD" }: { rows: Determination[]; currency?: string }) {
  const [filter, setFilter] = useState<"" | "payable" | "disputed" | "needs_review">("");
  if (!rows.length) return <Typography color="text.secondary">No line decisions yet.</Typography>;
  const filtered = filter ? rows.filter((row) => row.status === filter) : rows;
  const counts = { payable: 0, disputed: 0, needs_review: 0 };
  rows.forEach((row) => { if (row.status in counts) counts[row.status as keyof typeof counts]++; });

  const disputeReasons = new Map<string, { count: number; amount: number }>();
  const reviewReasons = new Map<string, { count: number; amount: number; hint: string }>();
  rows.forEach((row) => {
    const ruleText = row.rule_description || row.reason || "Contract-backed decision";
    if (row.status === "disputed") {
      const entry = disputeReasons.get(ruleText) ?? { count: 0, amount: 0 };
      entry.count++;
      entry.amount += Number(row.confirmed_disputed_amount ?? 0);
      disputeReasons.set(ruleText, entry);
    }
    if (row.status === "needs_review") {
      const entry = reviewReasons.get(ruleText) ?? { count: 0, amount: 0, hint: "" };
      entry.count++;
      entry.amount += Number(row.needs_review_amount ?? row.billed_amount ?? 0);
      entry.hint = resolutionHint(row);
      reviewReasons.set(ruleText, entry);
    }
  });

  return (
    <Stack spacing={2}>
      {disputeReasons.size > 0 && (
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography variant="subtitle2" fontWeight={750} gutterBottom>Why charges were identified for dispute</Typography>
          {[...disputeReasons.entries()].map(([reason, { count, amount }]) => (
            <Box key={reason} sx={{ display: "flex", gap: 2, justifyContent: "space-between", py: 0.75 }}>
              <Typography variant="body2">{reason} <Typography component="span" variant="caption" color="text.secondary">({count} line{count === 1 ? "" : "s"})</Typography></Typography>
              <Typography variant="body2" fontWeight={700}>{money(amount, currency)}</Typography>
            </Box>
          ))}
        </Paper>
      )}
      {reviewReasons.size > 0 && (
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography variant="subtitle2" fontWeight={750} gutterBottom>Needs review — what will resolve it</Typography>
          {[...reviewReasons.entries()].map(([reason, { count, amount, hint }]) => (
            <Box key={reason} sx={{ py: 0.9, borderBottom: 1, borderColor: "divider", "&:last-child": { borderBottom: 0 } }}>
              <Box sx={{ display: "flex", gap: 2, justifyContent: "space-between" }}>
                <Typography variant="body2">{reason} <Typography component="span" variant="caption" color="text.secondary">({count} line{count === 1 ? "" : "s"})</Typography></Typography>
                <Typography variant="body2" fontWeight={700}>{money(amount, currency)}</Typography>
              </Box>
              {hint && <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>{hint}</Typography>}
            </Box>
          ))}
        </Paper>
      )}
      <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }}>
        <Chip label={`All (${rows.length})`} variant={filter === "" ? "filled" : "outlined"} onClick={() => setFilter("")} />
        <Chip label={`Payable (${counts.payable})`} color="success" variant={filter === "payable" ? "filled" : "outlined"} onClick={() => setFilter("payable")} />
        <Chip label={`Disputed (${counts.disputed})`} color="error" variant={filter === "disputed" ? "filled" : "outlined"} onClick={() => setFilter("disputed")} />
        <Chip label={`Needs review (${counts.needs_review})`} color="warning" variant={filter === "needs_review" ? "filled" : "outlined"} onClick={() => setFilter("needs_review")} />
      </Stack>
      <Stack spacing={1.5}>
        {filtered.map((row) => {
          const primary = row.rule_description || row.reason;
          const decisionAmount = row.status === "payable" ? row.confirmed_payable_amount : row.status === "disputed" ? row.confirmed_disputed_amount : row.needs_review_amount;
          return (
            <Paper
              key={row.outcome_id}
              variant="outlined"
              sx={(theme) => ({
                p: 2.25,
                borderRadius: 2,
                bgcolor: row.status === "payable"
                  ? (theme.palette.mode === "dark" ? "#153127" : "#F1F8F5")
                  : row.status === "disputed"
                    ? (theme.palette.mode === "dark" ? "#382025" : "#FCF2F1")
                    : (theme.palette.mode === "dark" ? "#352B18" : "#FCF7EC"),
                borderLeft: "4px solid",
                borderLeftColor: row.status === "payable" ? "success.main" : row.status === "disputed" ? "error.main" : "warning.main",
              })}
            >
              <Stack spacing={1.5}>
                <Stack direction={{ xs: "column", md: "row" }} spacing={2} justifyContent="space-between" alignItems={{ md: "flex-start" }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">Vendor claim</Typography>
                    <Typography fontWeight={800}>{row.outcome_id}</Typography>
                    <Typography variant="body2">Billed {money(row.billed_amount, currency)}</Typography>
                  </Box>
                  <Box sx={{ textAlign: { md: "right" } }}>
                    <StatusChip status={row.status} />
                    <Typography variant="h6" fontWeight={800} sx={{ mt: 0.5 }}>{money(decisionAmount, currency)}</Typography>
                    <Typography variant="caption" color="text.secondary">{row.status === "payable" ? "verified payable" : row.status === "disputed" ? "identified for dispute" : "held for review"}</Typography>
                  </Box>
                </Stack>
                <Box>
                  <Typography variant="caption" fontWeight={850} color="text.secondary">CONTRACT RULE</Typography>
                  <Typography variant="body1" fontWeight={700}>{primary}</Typography>
                </Box>
                {row.reason && row.reason !== primary && (
                  <Box>
                    <Typography variant="caption" fontWeight={850} color="text.secondary">WHAT HAPPENED</Typography>
                    <Typography variant="body2">{row.reason}</Typography>
                  </Box>
                )}
                {row.status === "needs_review" && <Alert severity="info" icon={false}>{resolutionHint(row)}</Alert>}
                {!!row.contract_clauses?.length && (
                  <Box>
                    <Typography variant="caption" fontWeight={850} color="text.secondary">SOURCE AGREEMENT</Typography>
                    {row.contract_clauses.map((clause) => (
                      <Paper key={clause.id} variant="outlined" sx={{ p: 1.25, mt: 0.75, bgcolor: "action.hover" }}>
                        <Typography variant="caption" color="text.secondary">{clause.document_id}</Typography>
                        <Typography variant="body2" sx={{ mt: 0.25 }}>{clause.text}</Typography>
                      </Paper>
                    ))}
                  </Box>
                )}
                {!!row.evidence?.length && (
                  <Box>
                    <Typography variant="caption" fontWeight={850} color="text.secondary">EVIDENCE TIMELINE</Typography>
                    {row.evidence.map((event) => (
                      <Typography key={`${event.event_id}-${event.purpose}`} variant="body2" display="block" sx={{ mt: 0.4 }}>
                        {formatDate(event.timestamp)} · {event.source_system} · {readable(event.event_type)} · {event.source_record_id}
                      </Typography>
                    ))}
                  </Box>
                )}
                {row.rule_id && <Typography variant="caption" color="text.secondary">Technical details: rule {row.rule_id} · engine {row.engine_version}</Typography>}
              </Stack>
            </Paper>
          );
        })}
      </Stack>
    </Stack>
  );
}
export default function PilotApp() {
  const location = useLocation();
  const configPage = location.pathname === "/workspace/settings" || location.pathname === "/pilot/config";

  const [token, setToken] = useState(loadPilotToken());
  const [tokenDraft, setTokenDraft] = useState(loadPilotToken());
  const [status, setStatus] = useState<PilotStatus | null>(null);
  const [contract, setContract] = useState<PilotContract | null>(null);
  const [airVersion, setAirVersion] = useState<(AIRVersion & { agreement_ir?: AgreementIRView; finance_view?: FinanceView }) | null>(null);
  const [assurance, setAssurance] = useState<CompilerAssurance | null>(null);
  const [reconciliation, setReconciliation] = useState<Reconciliation | null>(null);
  const [reconciliationDelta, setReconciliationDelta] = useState<ReconciliationDelta | null>(null);
  const [verificationPlan, setVerificationPlan] = useState<VerificationPlanEnvelope | null>(null);
  const [config, setConfig] = useState<WorkspaceConfig | null>(null);
  const [facts, setFacts] = useState<DerivedFact[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [activeStage, setActiveStage] = useState<PilotStage>("agreement");
  const [stageTouched, setStageTouched] = useState(false);
  const previousRecommendedStage = useRef<PilotStage | null>(null);

  const refresh = useCallback(async () => {
    if (!loadPilotToken()) return;
    setBusy("Loading workspace");
    setError("");
    try {
      const [nextStatus, nextConfig] = await Promise.all([pilotApi.status(), pilotApi.config()]);
      setStatus(nextStatus);
      setConfig(nextConfig);
      if (nextStatus.active_contract_id) {
        setContract(await pilotApi.contract(nextStatus.active_contract_id));
      } else {
        setContract(null);
      }
      if (nextStatus.active_air_version_id) {
        const [version, nextAssurance] = await Promise.all([
          pilotApi.getAIRVersion(nextStatus.active_air_version_id),
          pilotApi.getAIRAssurance(nextStatus.active_air_version_id),
        ]);
        setAirVersion(version);
        setAssurance(nextAssurance);
        try { setVerificationPlan(await pilotApi.getVerificationPlan(nextStatus.active_air_version_id)); } catch { setVerificationPlan(null); }
      } else {
        setAirVersion(null);
        setAssurance(null);
        setVerificationPlan(null);
      }
      if (nextStatus.latest_reconciliation_id) {
        const nextReconciliation = await pilotApi.reconciliation(nextStatus.latest_reconciliation_id);
        setReconciliation(nextReconciliation);
        if (nextReconciliation.supersedes_run_id) {
          try {
            setReconciliationDelta(
              await pilotApi.compare(nextReconciliation.reconciliation_id, nextReconciliation.supersedes_run_id),
            );
          } catch {
            setReconciliationDelta(null);
          }
        } else {
          setReconciliationDelta(null);
        }
      } else {
        setReconciliation(null);
        setReconciliationDelta(null);
      }
      if (nextStatus.active_invoice_id) {
        try { setFacts((await pilotApi.facts(nextStatus.active_invoice_id, nextStatus.active_air_version_id ?? undefined)).facts); } catch { setFacts([]); }
      } else {
        setFacts([]);
      }
      if (advanced) {
        try { setAuditEvents((await pilotApi.auditLog()).events); } catch { setAuditEvents([]); }
      }
    } catch (requestError) {
      setError(errorText(requestError));
      if (requestError instanceof PilotApiError && requestError.status === 401) {
        clearPilotToken();
        setToken("");
      }
    } finally {
      setBusy("");
    }
  }, [advanced]);

  useEffect(() => { if (token) void refresh(); }, [refresh, token]);

  async function act(label: string, action: () => Promise<void>, success?: string) {
    setBusy(label); setError(""); setNotice("");
    try {
      await action();
      if (success) setNotice(success);
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setBusy("");
    }
  }

  function authenticate(event: FormEvent) {
    event.preventDefault();
    const next = tokenDraft.trim();
    if (next.length < 24) { setError("Workspace access key must contain at least 24 characters."); return; }
    savePilotToken(next); setToken(next); setNotice("Workspace opened. The access key stays in this browser session only.");
  }

  function signOut() {
    clearPilotToken(); setToken(""); setStatus(null); setContract(null); setAirVersion(null); setReconciliation(null); setReconciliationDelta(null); setConfig(null); setError("");
  }

  async function resetWorkspace() {
    await act(
      "Resetting workspace",
      async () => { await pilotApi.clear(); await refresh(); },
      "Workspace reset. Your configuration was preserved and you can start a new reconciliation.",
    );
  }

  const evidenceRequirementCount = airVersion?.finance_view?.evidence_needed?.length
    ?? airVersion?.agreement_ir?.proof_requirements?.length
    ?? 0;
  const evidenceReady = isPilotEvidenceReady(
    Boolean(status?.active_invoice_id),
    evidenceRequirementCount,
    verificationPlan,
  );
  const reconciliationNeedsReview = Boolean(
    reconciliation?.determinations?.some((item) => item.status === "needs_review"),
  );
  const stageCompletion: Record<PilotStage, boolean> = {
    agreement: Boolean(contract && status?.contract_approved && !status?.approved_rules_stale),
    invoice: Boolean(status?.active_invoice_id),
    evidence: evidenceReady,
    verification: Boolean(reconciliation),
    review: Boolean(reconciliation && !reconciliationNeedsReview),
    export: Boolean(reconciliation),
  };
  const completedStages = (["agreement", "invoice", "evidence", "verification", "review"] as PilotStage[]).filter((stage) => stageCompletion[stage]).length;
  const readinessPercent = Math.round((completedStages / 5) * 100);

  const recommendedStage = useMemo<PilotStage>(() => {
    return recommendedPilotStage({
      hasContract: Boolean(contract),
      contractApproved: Boolean(status?.contract_approved),
      approvedRulesStale: Boolean(status?.approved_rules_stale),
      hasInvoice: Boolean(status?.active_invoice_id),
      evidenceReady,
      hasReconciliation: Boolean(reconciliation),
      reconciliationNeedsReview,
    });
  }, [contract, evidenceReady, reconciliation, reconciliationNeedsReview, status]);

  useEffect(() => {
    const recommendationChanged = previousRecommendedStage.current !== recommendedStage;
    const shouldFollow = shouldFollowPilotRecommendation(
      previousRecommendedStage.current,
      recommendedStage,
      stageTouched,
    );
    previousRecommendedStage.current = recommendedStage;
    if (recommendationChanged) {
      setStageTouched(false);
    }
    if (shouldFollow) setActiveStage(recommendedStage);
  }, [recommendedStage, stageTouched]);

  function goToStage(stage: PilotStage) {
    setStageTouched(true);
    setActiveStage(stage);
    window.requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  }

  if (!token) {
    return (
      <Box className="workspace-auth-page">
        <Paper variant="outlined" className="workspace-auth-card">
          <Box className="workspace-auth-context">
            <Typography className="section-kicker">EVIDUE · CUSTOMER WORKSPACE</Typography>
            <Typography component="h1">Know what the invoice is actually worth.</Typography>
            <Typography>
              Reconcile outcome-priced AI invoices against approved contract rules and customer-controlled evidence before money moves.
            </Typography>
            <Box className="workspace-auth-principles">
              {[
                ["01", "Contract-backed", "AI proposes the interpretation; finance approves the governing rules."],
                ["02", "Evidence-backed", "Customer-owned records prove what happened after the vendor claim."],
                ["03", "Deterministic dollars", "Approved rules—not an LLM—produce the financial determination."],
              ].map(([number, title, text]) => (
                <Box key={number}><span>{number}</span><div><strong>{title}</strong><p>{text}</p></div></Box>
              ))}
            </Box>
          </Box>
          <Box className="workspace-auth-form">
            <Typography className="section-kicker">PRIVATE ACCESS</Typography>
            <Typography component="h2">Open your reconciliation workspace</Typography>
            <Typography>Use the access key provided for this customer workspace. The key stays in this browser session and is never placed in a URL.</Typography>
            <Box className="workspace-auth-boundary"><strong>Authority boundary</strong><span>AI interprets the agreement. You approve the rules. Deterministic code decides invoice money.</span></Box>
            {error && <Alert severity="error">{error}</Alert>}
            <Box component="form" onSubmit={authenticate}>
              <Stack spacing={1.5}>
                <TextField label="Workspace access key" type="password" value={tokenDraft} onChange={(event) => setTokenDraft(event.target.value)} autoFocus fullWidth helperText="Provided by your Evidue workspace administrator." />
                <Button type="submit" variant="contained" size="large">Open workspace</Button>
              </Stack>
            </Box>
          </Box>
        </Paper>
      </Box>
    );
  }

  const emptyWorkspace = Boolean(status && !status.active_contract_id);

  return (
    <WorkspaceShell
      active={configPage ? "settings" : "invoices"}
      workspaceId={status?.workspace_id}
      busy={busy}
      onRefresh={() => void refresh()}
      onSignOut={signOut}
    >
      {configPage ? (
        <Container maxWidth="lg" sx={{ py: 4 }}>
          {busy && <Alert severity="info" icon={false} sx={{ mb: 2 }}><strong>{busy}</strong>…</Alert>}
          {notice && <Alert severity="success" onClose={() => setNotice("")} sx={{ mb: 2 }}>{notice}</Alert>}
          {error && <Alert severity="error" onClose={() => setError("")} sx={{ mb: 2 }}>{error}</Alert>}
          <PilotConfigurationPage config={config} status={status} act={act} refresh={refresh} resetWorkspace={resetWorkspace} />
        </Container>
      ) : (
        <Box
          sx={{
            width: "100%",
            maxWidth: 1500,
            mx: "auto",
            px: { xs: 1.5, md: 3 },
            py: { xs: 2, md: 3 },
          }}
        >
          <Stack
            spacing={2.25}
            sx={{
              mt: 2.25,
              minWidth: 0,
              p: 0,
              borderRadius: 0,
              background: "transparent",
            }}
          >
            {busy && <Alert severity="info" icon={false}><strong>{busy}</strong>…</Alert>}
            {notice && <Alert severity="success" onClose={() => setNotice("")}>{notice}</Alert>}
            {error && <Alert severity="error" onClose={() => setError("")}>{error}</Alert>}

            {emptyWorkspace && (
              <Paper variant="outlined" className="first-reconciliation-panel">
                <Box className="first-reconciliation-main">
                  <Typography className="section-kicker">FIRST RECONCILIATION</Typography>
                  <Typography component="h2">Get to a defensible payable amount before learning the whole product.</Typography>
                  <Typography>
                    Load the guided sample to see a completed invoice review, or start with your own contract and customer evidence.
                  </Typography>
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1.25}>
                    <Button variant="contained" disabled={Boolean(busy)} onClick={() => void act("Creating sample workspace", async () => { setStageTouched(false); await pilotApi.seedSample(); await refresh(); }, "Guided sample is ready.")}>Load guided sample</Button>
                    <Button variant="outlined" onClick={() => { goToStage("agreement"); window.requestAnimationFrame(() => document.getElementById("contract")?.scrollIntoView({ behavior: "smooth" })); }}>Start with company data</Button>
                  </Stack>
                </Box>
                <Box className="first-reconciliation-proof">
                  <Typography className="section-kicker">WHAT THE SAMPLE PROVES</Typography>
                  {[
                    ["01", "Substantiated", "One charge supported by contract and evidence"],
                    ["02", "Contradicted", "One charge identified for dispute"],
                    ["03", "Insufficient evidence", "One charge held safely for review"],
                  ].map(([index, title, detail]) => (
                    <Box key={index}><span>{index}</span><div><strong>{title}</strong><p>{detail}</p></div></Box>
                  ))}
                  <Typography className="first-reconciliation-note">Synthetic data only. Reset it from Settings at any time.</Typography>
                </Box>
              </Paper>
            )}

            {!emptyWorkspace && (
              <>
                <WorkspaceCommandHeader
                  contract={contract}
                  status={status}
                  reconciliation={reconciliation}
                  activeStage={activeStage}
                  readinessPercent={readinessPercent}
                />
                <PilotStageRail
                  activeStage={activeStage}
                  completion={stageCompletion}
                  readinessPercent={readinessPercent}
                  completedStages={completedStages}
                  onNavigate={goToStage}
                  status={status}
                  reconciliation={reconciliation}
                />
              </>
            )}

            {!emptyWorkspace && (
              <NextAction
                status={status}
                contract={contract}
                reconciliation={reconciliation}
                verificationPlan={verificationPlan}
                onNavigate={goToStage}
              />
            )}

            {activeStage === "agreement" && (
              <ContractWorkspace contract={contract} airVersion={airVersion} assurance={assurance} status={status} config={config} act={act} refresh={refresh} />
            )}

            {activeStage === "invoice" && (
              <InvoiceWorkspace contract={contract} airVersion={airVersion} status={status} config={config} act={act} refresh={refresh} />
            )}

            {activeStage === "evidence" && (
              <EvidenceWorkspace status={status} airVersion={airVersion} verificationPlan={verificationPlan} config={config} act={act} refresh={refresh} />
            )}

            {activeStage === "verification" && (
              <>
                <Overview status={status} reconciliation={reconciliation} />
                <DecisionWorkspace
                  status={status}
                  reconciliation={reconciliation}
                  reconciliationDelta={reconciliationDelta}
                  requiresExternalEvidence={Boolean(airVersion?.agreement_ir?.proof_requirements?.length)}
                  act={act}
                  refresh={refresh}
                />
              </>
            )}

            {activeStage === "review" && (
              <>
                <ReviewWorkspace reconciliation={reconciliation} onNavigate={goToStage} />
                <Surface
                  title="Technical trail"
                  eyebrow="Advanced"
                  action={<Button size="small" onClick={() => { setAdvanced((value) => !value); if (!advanced) void act("Loading audit history", async () => setAuditEvents((await pilotApi.auditLog()).events)); }}>{advanced ? "Hide technical details" : "View technical details"}</Button>}
                >
                  <Collapse in={advanced} unmountOnExit>
                    <AdvancedDetails airVersion={airVersion} assurance={assurance} plan={verificationPlan} facts={facts} audit={auditEvents} />
                  </Collapse>
                  {!advanced && <Typography color="text.secondary">Rule hashes, evidence derivation, runtime identifiers, and audit history stay out of the finance decision until you need them.</Typography>}
                </Surface>
              </>
            )}

            {activeStage === "export" && <ExportWorkspace reconciliation={reconciliation} act={act} />}
          </Stack>
        </Box>
      )}
    </WorkspaceShell>
  );
}

function PilotStageRail({
  activeStage,
  completion,
  readinessPercent,
  completedStages,
  onNavigate,
  reconciliation,
}: {
  activeStage: PilotStage;
  completion: Record<PilotStage, boolean>;
  readinessPercent: number;
  completedStages: number;
  onNavigate: (stage: PilotStage) => void;
  status: PilotStatus | null;
  reconciliation: Reconciliation | null;
}) {
  return (
    <Paper variant="outlined" className="case-progress-shell">
      <Box className="case-progress-summary">
        <Box>
          <Typography className="section-kicker">PAYMENT READINESS</Typography>
          <Stack direction="row" spacing={1.5} alignItems="baseline">
            <Typography variant="h5" fontWeight={800}>{readinessPercent}%</Typography>
            <Typography variant="body2" color="text.secondary">{completedStages} of 5 controls complete</Typography>
          </Stack>
        </Box>
        {reconciliation && (
          <Box sx={{ textAlign: { sm: "right" } }}>
            <Typography variant="caption" color="text.secondary">Verified payable</Typography>
            <Typography variant="h6" fontWeight={800}>{money(reconciliation.confirmed_payable_amount, reconciliation.currency)}</Typography>
          </Box>
        )}
      </Box>
      <LinearProgress variant="determinate" value={readinessPercent} className="case-progress-bar" />
      <Box className="case-lifecycle" role="navigation" aria-label="Invoice verification lifecycle">
        {pilotStages.map((stage, index) => {
          const selected = stage.id === activeStage;
          const done = completion[stage.id];
          return (
            <Button
              key={stage.id}
              aria-current={selected ? "step" : undefined}
              aria-label={stage.label}
              onClick={() => onNavigate(stage.id)}
              className={`${selected ? "active" : ""}${done ? " complete" : ""}`}
            >
              <span className="case-step-index">{done ? "✓" : index + 1}</span>
              <span className="case-step-copy">
                <strong>{stage.label}</strong>
                <small>{stage.hint}</small>
              </span>
            </Button>
          );
        })}
      </Box>
    </Paper>
  );
}

function WorkspaceCommandHeader({
  contract,
  status,
  reconciliation,
  activeStage,
  readinessPercent,
}: {
  contract: PilotContract | null;
  status: PilotStatus | null;
  reconciliation: Reconciliation | null;
  activeStage: PilotStage;
  readinessPercent: number;
}) {
  const stage = pilotStages.find((item) => item.id === activeStage);
  const currency = reconciliation?.currency || "USD";
  return (
    <Paper variant="outlined" className="invoice-control-header">
      <Box className="invoice-control-identity">
        <Box>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.75, flexWrap: "wrap" }}>
            <Typography className="section-kicker">ACTIVE INVOICE REVIEW</Typography>
            <Chip size="small" variant="outlined" label={stage?.label ?? "Invoice"} />
          </Stack>
          <Typography variant="h4" fontWeight={780}>
            {contract ? `${contract.vendor}` : "Invoice reconciliation"}
          </Typography>
          <Typography color="text.secondary" sx={{ mt: 0.35 }}>
            {status?.active_invoice_id || "Invoice not loaded"}
            {contract ? ` · ${formatDate(contract.period_start)} – ${formatExclusiveEnd(contract.period_end)}` : ""}
          </Typography>
        </Box>
        <Box className="invoice-control-status">
          <Typography variant="caption" color="text.secondary">Payment readiness</Typography>
          <Typography variant="h5" fontWeight={800}>{readinessPercent}%</Typography>
        </Box>
      </Box>

      <Box className="invoice-control-numbers">
        <Box>
          <span>Vendor billed</span>
          <strong>{reconciliation ? money(reconciliation.submitted_amount, currency) : status?.active_invoice_id ? "Pending verification" : "—"}</strong>
        </Box>
        <Box>
          <span>Verified payable</span>
          <strong>{reconciliation ? money(reconciliation.confirmed_payable_amount, currency) : "—"}</strong>
        </Box>
        <Box>
          <span>Identified for dispute</span>
          <strong>{reconciliation ? money(reconciliation.recommended_deduction, currency) : "—"}</strong>
        </Box>
        <Box>
          <span>Needs review</span>
          <strong>{reconciliation ? money(reconciliation.needs_review_amount, currency) : "—"}</strong>
        </Box>
      </Box>
    </Paper>
  );
}

function NextAction({
  status,
  contract,
  reconciliation,
  verificationPlan,
  onNavigate,
}: {
  status: PilotStatus | null;
  contract: PilotContract | null;
  reconciliation: Reconciliation | null;
  verificationPlan: VerificationPlanEnvelope | null;
  onNavigate: (stage: PilotStage) => void;
}) {
  let title = "Add your agreement";
  let body = "Upload or paste the agreement that governs this invoice. Evidue will preserve the source and propose payment rules for your review.";
  let cta = "Add agreement";
  let stage: PilotStage = "agreement";

  if (contract && status?.approved_rules_stale) {
    title = "Your approved rules are out of date";
    body = "The governing document set changed. Evidue has stopped using the prior rules until the updated agreement is analyzed and approved.";
    cta = "Review updated agreement";
  } else if (contract && !status?.contract_approved) {
    title = "Approve what the contract means before touching the invoice";
    body = "Compare each proposed payment rule with the original clause. Only the version you approve can govern invoice verification.";
    cta = "Review contract rules";
  } else if (status?.contract_approved && !status.active_invoice_id) {
    title = "Bring in the vendor invoice";
    body = "Map the vendor's columns, verify the control totals, and confirm the file matches the invoice you received before import.";
    cta = "Import invoice";
    stage = "invoice";
  } else if (status?.active_invoice_id) {
    const planItems = verificationPlan?.plan.items ?? [];
    const missing = planItems.filter((item) => item.status !== "ready").length;
    if (!verificationPlan) {
      title = "Verify the evidence plan before deciding money";
      body = "Evidue has not loaded the approved rule-to-evidence plan yet, so it will not treat the evidence stage as complete.";
      cta = "Review evidence readiness";
      stage = "evidence";
    } else if ((planItems.length > 0 && missing > 0) || (planItems.length > 0 && !status.events)) {
      title = "Close the evidence gaps before deciding money";
      body = `${missing || planItems.length} contract evidence requirement(s) are not ready. Affected claims stay in Needs review instead of being silently paid or deducted.`;
      cta = "Add required evidence";
      stage = "evidence";
    } else if (!reconciliation) {
      title = "Everything required for a deterministic decision is ready";
      body = "The approved rules, normalized invoice, and available customer evidence can now be evaluated together.";
      cta = "Review readiness";
      stage = "verification";
    } else if (Number(reconciliation.needs_review_amount) > 0) {
      title = `${money(reconciliation.needs_review_amount, reconciliation.currency)} is still protected from an unsupported decision`;
      body = "Open the Needs review lines to see exactly which evidence or identity decision would resolve them.";
      cta = "Review unresolved lines";
      stage = "review";
    } else {
      title = "The financial decision is complete";
      body = "Review the result, then move the corrected invoice and dispute package into your AP and vendor workflow.";
      cta = "Open finance outputs";
      stage = "export";
    }
  }

  return (
    <Paper variant="outlined" className="recommended-action-panel">
      <Box>
        <Typography className="section-kicker">RECOMMENDED NEXT STEP</Typography>
        <Typography variant="h6" fontWeight={760}>{title}</Typography>
        <Typography color="text.secondary" sx={{ mt: 0.4, maxWidth: 880 }}>{body}</Typography>
      </Box>
      <Button variant="contained" size="large" onClick={() => onNavigate(stage)}>{cta}</Button>
    </Paper>
  );
}

function PilotConfigurationPage({
  config,
  status,
  act,
  refresh,
  resetWorkspace,
}: {
  config: WorkspaceConfig | null;
  status: PilotStatus | null;
  act: (label: string, action: () => Promise<void>, success?: string) => Promise<void>;
  refresh: () => Promise<void>;
  resetWorkspace: () => Promise<void>;
}) {
  const navigate = useNavigate();
  const [draft, setDraft] = useState({
    company_name: "",
    default_vendor: "",
    default_currency: "USD",
    timezone: "UTC",
    date_locale: "en-US",
    default_contract_rate: "",
    preferred_support_system: "",
    preferred_payment_system: "",
    preferred_crm_system: "",
  });
  const [resetOpen, setResetOpen] = useState(false);
  const [resetText, setResetText] = useState("");

  useEffect(() => {
    if (!config) return;
    setDraft({
      company_name: config.company_name,
      default_vendor: config.default_vendor,
      default_currency: config.default_currency,
      timezone: config.timezone,
      date_locale: config.date_locale,
      default_contract_rate: config.default_contract_rate,
      preferred_support_system: config.preferred_support_system,
      preferred_payment_system: config.preferred_payment_system,
      preferred_crm_system: config.preferred_crm_system,
    });
  }, [config]);

  async function save() {
    await pilotApi.updateConfig(draft);
    await refresh();
  }

  async function confirmReset() {
    if (resetText !== "RESET") throw new Error('Type "RESET" exactly to confirm.');
    await resetWorkspace();
    setResetText("");
    setResetOpen(false);
    navigate("/workspace");
  }

  return (
    <Stack spacing={3}>
      <Paper variant="outlined" className="settings-intro">
        <Typography className="section-kicker">CONFIGURATION</Typography>
        <Typography variant="h4" fontWeight={730}>Workspace controls</Typography>
        <Typography color="text.secondary" sx={{ mt: 0.75, maxWidth: 800 }}>
          Set finance defaults and preferred customer systems. Secrets stay on the server; this page never reads or stores API keys.
        </Typography>
      </Paper>

      <Surface title="Finance defaults" eyebrow="Workspace">
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
          <TextField label="Your company" value={draft.company_name} onChange={(e) => setDraft({ ...draft, company_name: e.target.value })} />
          <TextField label="Default vendor" value={draft.default_vendor} onChange={(e) => setDraft({ ...draft, default_vendor: e.target.value })} />
          <TextField label="Default currency" value={draft.default_currency} onChange={(e) => setDraft({ ...draft, default_currency: e.target.value.toUpperCase() })} inputProps={{ maxLength: 3 }} />
          <TextField label="Default contract rate" value={draft.default_contract_rate} onChange={(e) => setDraft({ ...draft, default_contract_rate: e.target.value })} helperText="Optional convenience default; approved contract rules remain authoritative." />
          <TextField label="Timezone" value={draft.timezone} onChange={(e) => setDraft({ ...draft, timezone: e.target.value })} helperText="Example: UTC or America/New_York" />
          <TextField label="Date locale" value={draft.date_locale} onChange={(e) => setDraft({ ...draft, date_locale: e.target.value })} helperText="Example: en-US" />
        </Box>
        <Button variant="contained" sx={{ mt: 2 }} onClick={() => void act("Saving workspace configuration", save, "Workspace configuration saved.")}>Save finance defaults</Button>
      </Surface>

      <Surface title="Preferred evidence systems" eyebrow="Evidence">
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          These names are suggestions in the evidence checklist. Contract evidence requirements still determine what evidence is actually needed.
        </Typography>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" }, gap: 2 }}>
          <TextField label="Support system" value={draft.preferred_support_system} onChange={(e) => setDraft({ ...draft, preferred_support_system: e.target.value })} placeholder="Zendesk" />
          <TextField label="Payment / billing system" value={draft.preferred_payment_system} onChange={(e) => setDraft({ ...draft, preferred_payment_system: e.target.value })} placeholder="Stripe" />
          <TextField label="CRM / account system" value={draft.preferred_crm_system} onChange={(e) => setDraft({ ...draft, preferred_crm_system: e.target.value })} placeholder="Salesforce" />
        </Box>
        <Button variant="contained" sx={{ mt: 2 }} onClick={() => void act("Saving evidence preferences", save, "Evidence preferences saved.")}>Save evidence preferences</Button>
      </Surface>

      <Surface title="Integration readiness" eyebrow="Server-managed">
        <Stack spacing={1.5}>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2}>
              <Box><Typography fontWeight={750}>Contract analysis AI</Typography><Typography variant="body2" color="text.secondary">{config?.integrations.contract_ai.provider ?? "server provider"} · {config?.integrations.contract_ai.model ?? "deployment default"}</Typography></Box>
              <Chip color={config?.integrations.contract_ai.configured ? "success" : "warning"} label={config?.integrations.contract_ai.configured ? "Configured" : "Not configured"} />
            </Stack>
            <Typography variant="caption" color="text.secondary">Provider credentials are managed only by the Evidue backend/deployment. Customers never enter or store LLM API keys here.</Typography>
          </Paper>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2}>
              <Box><Typography fontWeight={750}>Workspace access</Typography><Typography variant="body2" color="text.secondary">{readable(config?.integrations.workspace_access.mode ?? "server managed")}</Typography></Box>
              <Chip color={config?.integrations.workspace_access.configured ? "success" : "warning"} label={config?.integrations.workspace_access.configured ? "Configured" : "Not configured"} />
            </Stack>
          </Paper>
        </Stack>
      </Surface>

      <Surface title="Danger zone" eyebrow="Workspace reset">
        <Alert severity="warning">Reset removes this workspace's agreement, invoice, evidence, reconciliation runs, and audit activity. Workspace configuration is preserved.</Alert>
        <Button color="error" variant="outlined" sx={{ mt: 2 }} disabled={!status?.active_contract_id} onClick={() => setResetOpen(true)}>Reset workspace data</Button>
      </Surface>

      <Dialog open={resetOpen} onClose={() => setResetOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Reset workspace data?</DialogTitle>
        <DialogContent>
          <Typography color="text.secondary" sx={{ mb: 2 }}>This cannot be undone from the product. Type RESET to confirm.</Typography>
          <TextField fullWidth label='Type "RESET"' value={resetText} onChange={(e) => setResetText(e.target.value)} autoFocus />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResetOpen(false)}>Cancel</Button>
          <Button color="error" variant="contained" disabled={resetText !== "RESET"} onClick={() => void act("Resetting workspace", confirmReset)}>Reset workspace</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

export function Overview({ status, reconciliation }: { status: PilotStatus | null; reconciliation: Reconciliation | null }) {
  if (!reconciliation) {
    return (
      <Paper variant="outlined" className="result-placeholder">
        <Typography className="section-kicker">VERIFICATION RESULT</Typography>
        <Typography variant="h5" fontWeight={730}>The financial decision will appear here.</Typography>
        <Typography color="text.secondary" sx={{ mt: 0.75, maxWidth: 760 }}>
          Evidue does not estimate before the approved rules and required evidence are ready. Run verification to produce the amount finance can act on.
        </Typography>
        {status && (
          <Box className="result-placeholder-stats">
            <span>{status.claims} invoice lines</span>
            <span>{status.events} evidence records</span>
            <span>{status.accepted_match_rate}% evidence match rate</span>
          </Box>
        )}
      </Paper>
    );
  }

  const reviewAmount = Number(reconciliation.needs_review_amount || 0);
  const disputeAmount = Number(reconciliation.recommended_deduction || 0);
  const billedAmount = Number(reconciliation.submitted_amount || 0);
  const payableAmount = Number(reconciliation.confirmed_payable_amount || 0);
  const payableShare = billedAmount > 0 ? (payableAmount / billedAmount) * 100 : 0;
  const disputeShare = billedAmount > 0 ? (disputeAmount / billedAmount) * 100 : 0;
  const reviewShare = billedAmount > 0 ? (reviewAmount / billedAmount) * 100 : 0;
  const identifiedDisputePercent = billedAmount > 0 ? disputeShare : Number(reconciliation.identified_dispute_percent || 0);

  const headline = [
    ["Vendor billed", money(reconciliation.submitted_amount, reconciliation.currency), `${reconciliation.claimed_outcomes ?? 0} claimed outcomes`],
    ["Verified payable", money(reconciliation.confirmed_payable_amount, reconciliation.currency), `${reconciliation.payable_outcomes ?? 0} substantiated`],
    ["Identified for dispute", money(reconciliation.recommended_deduction, reconciliation.currency), `${reconciliation.disputed_outcomes ?? 0} contradicted`],
    ["Needs review", money(reconciliation.needs_review_amount, reconciliation.currency), reviewAmount > 0 ? `${reconciliation.needs_review_outcomes ?? 0} insufficient evidence` : "No unresolved dollars"],
  ] as const;

  return (
    <Paper variant="outlined" className="verification-result">
      <Box className="verification-result-lead">
        <Box>
          <Typography className="section-kicker">VERIFICATION COMPLETE</Typography>
          <Typography variant="h4" fontWeight={760}>
            {identifiedDisputePercent.toFixed(1)}% of invoice value identified for dispute.
          </Typography>
          <Typography color="text.secondary" sx={{ mt: 0.65 }}>
            Finance can see the billed amount, the substantiated payable amount, and every unresolved dollar without interpreting model output.
          </Typography>
        </Box>
        <Chip size="small" variant="outlined" color="success" label={`${reconciliation.claimed_outcomes ?? 0} claims evaluated`} />
      </Box>

      <Box className="verification-result-numbers">
        {headline.map(([label, value, help]) => (
          <Box key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{help}</small>
          </Box>
        ))}
      </Box>

      <Box className="amount-waterfall" aria-label="Invoice disposition">
        <Box className="amount-waterfall-labels">
          <span>Disposition of billed amount</span>
          <span>{payableShare.toFixed(1)}% payable · {disputeShare.toFixed(1)}% disputed · {reviewShare.toFixed(1)}% review</span>
        </Box>
        <Box className="amount-waterfall-track">
          {payableShare > 0 && <span className="payable" style={{ width: `${payableShare}%` }} />}
          {disputeShare > 0 && <span className="disputed" style={{ width: `${disputeShare}%` }} />}
          {reviewShare > 0 && <span className="review" style={{ width: `${reviewShare}%` }} />}
        </Box>
      </Box>

      <Box className={reviewAmount > 0 ? "result-protection warning" : "result-protection success"}>
        {reviewAmount > 0
          ? `${money(reviewAmount, reconciliation.currency)} remains protected from an unsupported decision until its evidence gap is resolved.`
          : "Every invoice line has a contract-backed deterministic decision."}
      </Box>
    </Paper>
  );
}

function ContractWorkspace({
  contract,
  airVersion,
  assurance,
  status,
  config,
  act,
  refresh,
}: {
  contract: PilotContract | null;
  airVersion: (AIRVersion & { agreement_ir?: AgreementIRView; finance_view?: FinanceView }) | null;
  assurance: CompilerAssurance | null;
  status: PilotStatus | null;
  config: WorkspaceConfig | null;
  act: (label: string, action: () => Promise<void>, success?: string) => Promise<void>;
  refresh: () => Promise<void>;
}) {
  const [customer, setCustomer] = useState("");
  const [vendor, setVendor] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [price, setPrice] = useState("");
  const [contractFile, setContractFile] = useState<File | null>(null);
  const [pasted, setPasted] = useState("");
  const [ruleReviewSummary, setRuleReviewSummary] = useState({ reviewed: 0, total: 0, flagged: 0 });
  const [latestCandidateId, setLatestCandidateId] = useState("");
  const [latestCandidate, setLatestCandidate] = useState<(AIRVersion & { agreement_ir?: AgreementIRView; finance_view?: FinanceView }) | null>(null);
  const [latestAssurance, setLatestAssurance] = useState<CompilerAssurance | null>(null);
  const [bundle, setBundle] = useState<AgreementBundleView | null>(null);

  useEffect(() => {
    if (!config) return;
    setCustomer((value) => value || config.company_name);
    setVendor((value) => value || config.default_vendor);
    setPrice((value) => value || config.default_contract_rate);
  }, [config]);

  useEffect(() => {
    let cancelled = false;
    if (!contract) {
      setBundle(null);
      return () => { cancelled = true; };
    }
    pilotApi.getAgreementBundle(contract.id)
      .then((value) => { if (!cancelled) setBundle(value); })
      .catch(() => { if (!cancelled) setBundle(null); });
    return () => { cancelled = true; };
  }, [contract]);

  const candidate = latestCandidate ?? airVersion;
  const candidateAssurance = latestAssurance ?? assurance;
  const agreement = candidate?.agreement_ir;
  const financeView = candidate?.finance_view;
  const approved = Boolean(status?.contract_approved && airVersion?.approved_at);
  const rulesStale = Boolean(status?.approved_rules_stale);

  async function upload() {
    if (!customer.trim()) throw new Error("Enter your company name.");
    if (!vendor.trim()) throw new Error("Enter the vendor name.");
    if (!periodStart || !periodEnd) throw new Error("Choose the agreement start and end dates.");
    if (periodEnd <= periodStart) throw new Error("Agreement end date must be after the start date.");
    if (!contractFile && pasted.trim().length < 50) throw new Error("Choose a contract file or paste at least 50 characters of contract language.");
    const start = `${periodStart}T00:00:00Z`;
    const end = exclusiveEndFromDate(periodEnd);
    if (contractFile) {
      await pilotApi.uploadContract({ file: contractFile, customer, vendor, periodStart: start, periodEnd: end, pricePerOutcome: price || "0.00" });
    } else {
      await pilotApi.createContractFromText({ customer, vendor, periodStart: start, periodEnd: end, pricePerOutcome: price || "0.00", sourceText: pasted });
    }
    await refresh();
  }

  async function analyze() {
    if (!contract) throw new Error("Add an agreement first.");
    const result = await pilotApi.compileNative(contract.id, "auto");
    const [version, nextAssurance] = await Promise.all([
      pilotApi.getAIRVersion(result.air_version_id),
      pilotApi.getAIRAssurance(result.air_version_id),
    ]);
    setLatestCandidateId(result.air_version_id);
    setLatestCandidate(version);
    setLatestAssurance(nextAssurance);
    setRuleReviewSummary({ reviewed: 0, total: 0, flagged: 0 });
  }

  async function approve() {
    const id = latestCandidateId || candidate?.id;
    if (!id) throw new Error("Analyze the agreement first.");
    if (!ruleReviewSummary.total || ruleReviewSummary.reviewed !== ruleReviewSummary.total || ruleReviewSummary.flagged > 0) {
      throw new Error("Review every proposed contract rule and resolve any flagged interpretation before approval.");
    }
    await pilotApi.approveAIR(id);
    setLatestCandidate(null);
    setLatestCandidateId("");
    setLatestAssurance(null);
    await refresh();
  }

  return (
    <Box id="contract">
      <Surface title="Agreement and approved rules" eyebrow="01 · Contract" complete={approved}>
        {!contract ? (
          <Stack spacing={2.25}>
            <Alert severity="info">Upload PDF, DOCX, TXT, or Markdown, or paste the agreement language. Evidue keeps the source text and its fingerprint so every approved rule can be traced back to the contract.</Alert>
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
              <TextField label="Your company" value={customer} onChange={(e) => setCustomer(e.target.value)} placeholder="Acme Inc." />
              <TextField label="Vendor" value={vendor} onChange={(e) => setVendor(e.target.value)} placeholder="Zendesk" />
              <TextField label="Agreement starts" type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} InputLabelProps={{ shrink: true }} />
              <TextField label="Agreement ends" type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} InputLabelProps={{ shrink: true }} helperText="Use the end of the commercial term; Evidue stores the boundary precisely." />
              <TextField label="Default contract rate (optional)" value={price} onChange={(e) => setPrice(e.target.value)} helperText="Convenience fallback only. Pricing terms extracted and approved from the agreement remain authoritative." />
            </Box>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
              <Button component="label" variant="outlined">Choose agreement file<input hidden type="file" accept=".pdf,.docx,.txt,.md,text/plain,application/pdf" onChange={(e) => setContractFile(e.target.files?.[0] ?? null)} /></Button>
              <Typography variant="body2" color="text.secondary">{contractFile?.name ?? "No file selected"}</Typography>
            </Stack>
            <Typography variant="overline" color="text.secondary">or paste the agreement</Typography>
            <TextField multiline minRows={6} label="Agreement language" value={pasted} onChange={(e) => setPasted(e.target.value)} placeholder="Paste the agreement, order form, pricing addendum, or other governing commercial terms…" />
            <Button variant="contained" size="large" sx={{ alignSelf: "flex-start" }} onClick={() => void act("Saving the agreement", upload, "Agreement saved. Analyze its payment rules next.")}>Save agreement</Button>
          </Stack>
        ) : (
          <Stack spacing={2.5}>
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" }, gap: 2 }}>
              <Metric label="Customer" value={contract.customer} />
              <Metric label="Vendor" value={contract.vendor} />
              <Metric label="Agreement period" value={`${formatDate(contract.period_start)} – ${formatExclusiveEnd(contract.period_end)}`} />
              <Metric label="Source" value={contract.source_document} help={`Fingerprint ${contract.source_hash.slice(0, 12)}…`} />
            </Box>
            <AgreementBundleManager
              contract={contract}
              bundle={bundle}
              setBundle={setBundle}
              rulesStale={rulesStale}
              act={act}
              refresh={refresh}
            />
            {rulesStale && (
              <Alert severity="warning">The governing agreement documents changed after the current rules were approved. Re-analyze the agreement bundle and approve a new rule version before importing or reconciling an invoice.</Alert>
            )}
            {!candidate && <Button variant="contained" sx={{ alignSelf: "flex-start" }} onClick={() => void act("Reading the agreement and proposing payment rules", analyze, "Contract analysis is ready for your review.")}>Analyze contract with AI</Button>}
            {candidate && (
              <>
                <Alert severity={candidateAssurance?.hard_gate_passed ? "success" : "error"}>
                  {candidateAssurance?.hard_gate_passed
                    ? "Rule verification checks passed. Evidue confirmed that the proposal is structurally valid, source-grounded, and executable where marked automatic. You still decide whether it accurately reflects the commercial agreement."
                    : "This proposed rule version failed a required verification check and cannot be approved. Review the failures below before continuing."}
                </Alert>
                <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" }, gap: 2 }}>
                  <Metric label="Key contract terms" value={String(agreement?.clauses?.filter((item) => item.material).length ?? 0)} />
                  <Metric label="Contract rules" value={String(financeView?.contract_rules.length ?? agreement?.norms?.length ?? 0)} />
                  <Metric label="Evidence needed" value={String(financeView?.evidence_needed.length ?? agreement?.proof_requirements?.length ?? 0)} />
                  <Metric label="Pricing terms" value={String(financeView?.pricing_terms.length ?? agreement?.settlement_policies?.length ?? 0)} />
                </Box>
                <RuleReview agreement={agreement} financeView={financeView} onProgress={setRuleReviewSummary} />
                {!approved && (
                  <Paper variant="outlined" className="rule-approval-footer">
                    <Box>
                      <Typography className="section-kicker">APPROVAL PROGRESS</Typography>
                      <Typography variant="h6" fontWeight={740}>{ruleReviewSummary.reviewed} of {ruleReviewSummary.total} contract rules reviewed</Typography>
                      <Typography color="text.secondary">{ruleReviewSummary.flagged > 0 ? `${ruleReviewSummary.flagged} interpretation(s) are flagged and block approval.` : "Approval freezes this rule set as financial authority for reconciliation."}</Typography>
                    </Box>
                    <Button variant="contained" disabled={!ruleReviewSummary.total || ruleReviewSummary.reviewed !== ruleReviewSummary.total || ruleReviewSummary.flagged > 0 || !candidateAssurance?.hard_gate_passed} onClick={() => void act("Approving contract rules", approve, "Approved contract rules are now immutable and active for invoice verification.")}>Approve reviewed rules</Button>
                  </Paper>
                )}
                {approved && <Alert severity="success">Approved contract rules v{airVersion?.version_number} are active. Recompiling the agreement creates a new candidate version; historical reconciliations remain pinned to the exact version they used.</Alert>}
              </>
            )}
          </Stack>
        )}
      </Surface>
    </Box>
  );
}

const agreementDocumentTypes = [
  { value: "primary_agreement", label: "Primary agreement", precedence: 100 },
  { value: "master_agreement", label: "Master agreement", precedence: 100 },
  { value: "service_terms", label: "Service / additional terms", precedence: 200 },
  { value: "sla", label: "Service level agreement", precedence: 200 },
  { value: "order_form", label: "Order form", precedence: 300 },
  { value: "amendment", label: "Amendment", precedence: 400 },
  { value: "other", label: "Other governing document", precedence: 150 },
];

function agreementDocumentLabel(value?: string): string {
  return agreementDocumentTypes.find((item) => item.value === value)?.label ?? readable(value || "agreement");
}

function AgreementBundleManager({
  contract,
  bundle,
  setBundle,
  rulesStale,
  act,
  refresh,
}: {
  contract: PilotContract;
  bundle: AgreementBundleView | null;
  setBundle: (value: AgreementBundleView | null) => void;
  rulesStale: boolean;
  act: (label: string, action: () => Promise<void>, success?: string) => Promise<void>;
  refresh: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [documentType, setDocumentType] = useState("order_form");
  const [effectiveFrom, setEffectiveFrom] = useState(contract.period_start.slice(0, 10));
  const [effectiveUntil, setEffectiveUntil] = useState("");
  const [precedence, setPrecedence] = useState(300);
  const [relation, setRelation] = useState<"" | "amends" | "supersedes" | "incorporates">("");
  const [targetDocumentId, setTargetDocumentId] = useState("");

  useEffect(() => {
    setEffectiveFrom(contract.period_start.slice(0, 10));
  }, [contract.period_start]);

  function chooseDocumentType(value: string) {
    setDocumentType(value);
    const next = agreementDocumentTypes.find((item) => item.value === value);
    if (next) setPrecedence(next.precedence);
  }

  async function addDocument() {
    if (!file) throw new Error("Choose the governing document file first.");
    if (!title.trim()) throw new Error("Enter a document title.");
    if (!effectiveFrom) throw new Error("Choose when this document becomes effective.");
    if (effectiveUntil && effectiveUntil <= effectiveFrom) throw new Error("Document end date must be after its start date.");
    if (relation && !targetDocumentId) throw new Error("Choose which existing document this one relates to.");

    const beforeIds = new Set(bundle?.documents.map((item) => item.id) ?? []);
    let next = await pilotApi.uploadAgreementDocument({
      contractId: contract.id,
      file,
      title: title.trim(),
      documentType,
      effectiveFrom: `${effectiveFrom}T00:00:00Z`,
      effectiveUntil: effectiveUntil ? exclusiveEndFromDate(effectiveUntil) : undefined,
      precedence,
    });
    const created = next.documents.find((item) => !beforeIds.has(item.id));
    if (relation && targetDocumentId && created) {
      next = await pilotApi.addAgreementRelation(contract.id, {
        source_document_id: created.id,
        target_document_id: targetDocumentId,
        relation,
      });
    }
    setBundle(next);
    setFile(null);
    setTitle("");
    setRelation("");
    setTargetDocumentId("");
    setEffectiveUntil("");
    setOpen(false);
    await refresh();
  }

  const documents = bundle?.documents ?? [];
  const relationDescription = relation === "amends"
    ? "This document changes specific terms in the selected earlier document."
    : relation === "supersedes"
      ? "This document replaces the selected earlier document where applicable."
      : relation === "incorporates"
        ? "This document incorporates the selected document by reference."
        : "Optional. Use this when the document explicitly changes, replaces, or incorporates another governing document.";

  return (
    <Paper variant="outlined" sx={{ p: 2.25, borderRadius: 2.5 }}>
      <Stack spacing={1.75}>
        <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, alignItems: { xs: "flex-start", sm: "center" }, flexDirection: { xs: "column", sm: "row" } }}>
          <Box>
            <Typography variant="subtitle1" fontWeight={800}>Governing agreement documents</Typography>
            <Typography variant="body2" color="text.secondary">Add the Order Form, master agreement, amendments, service terms, or SLA that together determine what is payable. Evidue compiles the effective bundle, not just the first file.</Typography>
          </Box>
          <Button variant="outlined" onClick={() => setOpen((value) => !value)}>{open ? "Close" : "Add governing document"}</Button>
        </Box>

        {documents.length > 0 && (
          <Stack spacing={1}>
            {documents.map((document) => {
              const outgoing = bundle?.relations.filter((item) => item.source_document_id === document.id) ?? [];
              return (
                <Box key={document.id} sx={{ display: "flex", gap: 1.25, alignItems: "flex-start", justifyContent: "space-between", py: 1, borderTop: "1px solid", borderColor: "divider" }}>
                  <Box>
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ flexWrap: "wrap" }}>
                      <Typography fontWeight={730}>{document.title}</Typography>
                      <Chip size="small" label={agreementDocumentLabel(document.document_type)} variant="outlined" />
                      <Chip size="small" color={document.effective ? "success" : "default"} label={document.effective ? "Effective for this agreement" : "Not effective at start date"} />
                    </Stack>
                    <Typography variant="caption" color="text.secondary">
                      Effective {formatDate(document.effective_from)}{document.effective_until ? ` – ${formatExclusiveEnd(document.effective_until)}` : " onward"}
                    </Typography>
                    {outgoing.map((item) => {
                      const target = documents.find((candidate) => candidate.id === item.target_document_id);
                      return <Typography key={`${item.source_document_id}-${item.target_document_id}-${item.relation}`} variant="caption" display="block" color="text.secondary">{readable(item.relation)} {target?.title ?? "another governing document"}</Typography>;
                    })}
                  </Box>
                  <Typography variant="caption" color="text.secondary">Priority {document.precedence}</Typography>
                </Box>
              );
            })}
          </Stack>
        )}

        {(bundle?.internal_effective_boundaries?.length ?? 0) > 0 && (
          <Alert severity="warning">
            This agreement changes inside the configured period ({bundle?.internal_effective_boundaries?.[0]?.title} {bundle?.internal_effective_boundaries?.[0]?.kind} on {formatDate(bundle?.internal_effective_boundaries?.[0]?.boundary)}). Evidue will fail closed instead of applying one rule set across that boundary. Split the reconciliation into periods with one governing rule set each.
          </Alert>
        )}

        {open && (
          <Box sx={{ bgcolor: "action.hover", p: 2, borderRadius: 2 }}>
            <Stack spacing={1.75}>
              <Alert severity="info">Add every document that can change pricing, billability, service credits, exclusions, definitions, or effective dates before approving the rules. Higher-priority documents control when terms conflict.</Alert>
              <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
                <Button component="label" variant="outlined">Choose document<input hidden type="file" accept=".pdf,.docx,.txt,.md,text/plain,application/pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></Button>
                <Typography variant="body2" color="text.secondary">{file?.name ?? "No file selected"}</Typography>
              </Stack>
              <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
                <TextField label="Document title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="June 2026 Order Form" />
                <TextField select label="Document type" value={documentType} onChange={(event) => chooseDocumentType(event.target.value)}>
                  {agreementDocumentTypes.map((item) => <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>)}
                </TextField>
                <TextField label="Effective from" type="date" value={effectiveFrom} onChange={(event) => setEffectiveFrom(event.target.value)} InputLabelProps={{ shrink: true }} />
                <TextField label="Effective through (optional)" type="date" value={effectiveUntil} onChange={(event) => setEffectiveUntil(event.target.value)} InputLabelProps={{ shrink: true }} />
                <TextField select label="Conflict priority" value={String(precedence)} onChange={(event) => setPrecedence(Number(event.target.value))} helperText="Use the contract's stated order of precedence. Higher priority wins when effective terms conflict.">
                  <MenuItem value="100">100 · Base terms</MenuItem>
                  <MenuItem value="200">200 · Supplemental / service terms</MenuItem>
                  <MenuItem value="300">300 · Order-specific terms</MenuItem>
                  <MenuItem value="400">400 · Amendment / replacement terms</MenuItem>
                </TextField>
                <TextField select label="Relationship to an existing document (optional)" value={relation} onChange={(event) => setRelation(event.target.value as "" | "amends" | "supersedes" | "incorporates")}>
                  <MenuItem value="">No explicit relationship</MenuItem>
                  <MenuItem value="amends">Amends</MenuItem>
                  <MenuItem value="supersedes">Supersedes</MenuItem>
                  <MenuItem value="incorporates">Incorporates</MenuItem>
                </TextField>
              </Box>
              {relation && (
                <TextField select label="Related earlier document" value={targetDocumentId} onChange={(event) => setTargetDocumentId(event.target.value)} helperText={relationDescription}>
                  {documents.map((document) => <MenuItem key={document.id} value={document.id}>{document.title}</MenuItem>)}
                </TextField>
              )}
              <Typography variant="caption" color="text.secondary">The priority selector is an explicit operator input because contract precedence is a legal/commercial fact, not something Evidue should silently guess from filenames.</Typography>
              <Button variant="contained" sx={{ alignSelf: "flex-start" }} disabled={!file || !title.trim()} onClick={() => void act("Adding governing agreement document", addDocument, "Governing document added. Re-analyze the agreement bundle before approval.")}>Add to agreement</Button>
            </Stack>
          </Box>
        )}
        {rulesStale && <Typography variant="caption" color="warning.main">The current approved rules no longer match this governing document set.</Typography>}
      </Stack>
    </Paper>
  );
}

function RuleReview({
  agreement,
  financeView,
  onProgress,
}: {
  agreement?: AgreementIRView;
  financeView?: FinanceView;
  onProgress: (summary: { reviewed: number; total: number; flagged: number }) => void;
}) {
  const rules = financeView?.contract_rules ?? [];
  const [states, setStates] = useState<Record<string, "pending" | "reviewed" | "flagged">>({});

  useEffect(() => {
    const ids = rules.length ? rules.map((rule) => rule.id) : (agreement?.norms ?? []).map((rule) => rule.id);
    const reviewed = ids.filter((id) => states[id] === "reviewed").length;
    const flagged = ids.filter((id) => states[id] === "flagged").length;
    onProgress({ reviewed, total: ids.length, flagged });
  }, [agreement?.norms, onProgress, rules, states]);

  if (!agreement) return <Typography color="text.secondary">Contract rule details are unavailable.</Typography>;

  if (rules.length) {
    return (
      <Stack spacing={2}>
        <Box className="workspace-section-heading compact">
          <Box>
            <Typography className="section-kicker">RULE REVIEW</Typography>
            <Typography variant="h6" fontWeight={740}>Compare the contract language with Evidue’s interpretation</Typography>
            <Typography color="text.secondary">The left side is the governing source. The right side is the finance rule the deterministic engine will execute after approval.</Typography>
          </Box>
        </Box>

        <Stack spacing={1.25}>
          {rules.map((rule, index) => {
            const state = states[rule.id] ?? "pending";
            return (
              <Paper key={rule.id} variant="outlined" className={`contract-rule-review ${state}`}>
                <Box className="contract-rule-source">
                  <Stack direction="row" justifyContent="space-between" spacing={1} alignItems="center">
                    <Typography className="section-kicker">SOURCE CLAUSE {index + 1}</Typography>
                    <Typography variant="caption" color="text.secondary">{rule.source_clauses[0]?.document_id ?? "Agreement"}</Typography>
                  </Stack>
                  {rule.source_clauses.length ? rule.source_clauses.map((clause) => (
                    <Typography key={clause.id} className="contract-source-quote">{clause.text}</Typography>
                  )) : <Typography color="text.secondary">No source clause was attached to this finance view.</Typography>}
                </Box>

                <Box className="contract-rule-interpretation">
                  <Stack direction="row" justifyContent="space-between" spacing={1} alignItems="flex-start">
                    <Box>
                      <Typography className="section-kicker">PROPOSED CONTRACT RULE</Typography>
                      <Typography variant="h6" fontWeight={740}>{rule.description}</Typography>
                    </Box>
                    <Chip size="small" variant="outlined" color={state === "reviewed" ? "success" : state === "flagged" ? "error" : "default"} label={state === "reviewed" ? "Reviewed" : state === "flagged" ? "Flagged" : "Pending"} />
                  </Stack>
                  <Box className="rule-facts-grid">
                    <Box><span>Rule type</span><strong>{rule.rule_type}</strong></Box>
                    <Box><span>Verification</span><strong>{rule.verification_method}</strong></Box>
                    <Box><span>Financial effect</span><strong>{readable(rule.consequence)}</strong></Box>
                    <Box><span>Evidence needed</span><strong>{rule.evidence_needed.length ? rule.evidence_needed.join(" · ") : "None"}</strong></Box>
                  </Box>
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ mt: 1.5 }}>
                    <Button size="small" variant={state === "reviewed" ? "contained" : "outlined"} color="success" onClick={() => setStates((current) => ({ ...current, [rule.id]: "reviewed" }))}>Approve interpretation</Button>
                    <Button size="small" variant={state === "flagged" ? "contained" : "outlined"} color="error" onClick={() => setStates((current) => ({ ...current, [rule.id]: "flagged" }))}>Flag for correction</Button>
                  </Stack>
                  {state === "flagged" && <Alert severity="warning" sx={{ mt: 1.5 }}>Evidue will not silently rewrite a commercial term. Correct the governing document set or re-run analysis before approving this rule version.</Alert>}
                </Box>
              </Paper>
            );
          })}
        </Stack>

        {financeView?.pricing_terms?.length ? (
          <Paper variant="outlined" className="pricing-terms-panel">
            <Typography className="section-kicker">PRICING TERMS</Typography>
            {financeView.pricing_terms.map((term) => (
              <Box key={term.id} className="pricing-term-row">
                <Typography fontWeight={700}>{term.description}</Typography>
                <Typography variant="caption" color="text.secondary">{term.currency}</Typography>
              </Box>
            ))}
          </Paper>
        ) : null}

        {agreement.diagnostics?.map((diag) => <Alert key={`${diag.code}-${diag.message}`} severity={diag.severity === "blocking" ? "error" : diag.severity === "warning" ? "warning" : "info"}>{diag.message}</Alert>)}
      </Stack>
    );
  }

  const normsByClause = new Map<string, AgreementIRView["norms"]>();
  agreement.norms.forEach((norm) => norm.source_clause_ids.forEach((id) => normsByClause.set(id, [...(normsByClause.get(id) ?? []), norm])));
  return (
    <Stack spacing={1.5}>
      <Alert severity="warning">Finance-language rendering is unavailable for this candidate. Review every source mapping before approval.</Alert>
      {agreement.clauses.filter((item) => item.material).map((clause) => (
        <Paper key={clause.id} variant="outlined" className="contract-rule-review fallback">
          <Box className="contract-rule-source"><Typography className="contract-source-quote">{clause.text}</Typography></Box>
          <Box className="contract-rule-interpretation">{(normsByClause.get(clause.id) ?? []).map((norm) => <Box key={norm.id} sx={{ mb: 1 }}><Typography fontWeight={700}>Contract rule · {readable(norm.consequence)}</Typography><Typography variant="body2" color="text.secondary">{financeVerificationMethod(norm.automation_class)}</Typography><Stack direction="row" spacing={1} sx={{ mt: 1 }}><Button size="small" variant={states[norm.id] === "reviewed" ? "contained" : "outlined"} color="success" onClick={() => setStates((current) => ({ ...current, [norm.id]: "reviewed" }))}>Approve interpretation</Button><Button size="small" variant={states[norm.id] === "flagged" ? "contained" : "outlined"} color="error" onClick={() => setStates((current) => ({ ...current, [norm.id]: "flagged" }))}>Flag</Button></Stack></Box>)}</Box>
        </Paper>
      ))}
    </Stack>
  );
}

function InvoiceWorkspace({ contract, airVersion, status, config, act, refresh }: { contract: PilotContract | null; airVersion: AIRVersion | null; status: PilotStatus | null; config: WorkspaceConfig | null; act: (label: string, action: () => Promise<void>, success?: string) => Promise<void>; refresh: () => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<InvoicePreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [invoiceId, setInvoiceId] = useState(`INV-${new Date().toISOString().slice(0, 10)}`);
  const [totalsReviewed, setTotalsReviewed] = useState(false);

  async function previewFile(next: File | null) {
    setFile(next);
    setPreview(null);
    setMapping({});
    setTotalsReviewed(false);
    if (!next) return;
    const result = await pilotApi.previewInvoice(next);
    setPreview(result);
    const nextMap: Record<string, string> = {};
    Object.entries(result.auto_mapping).forEach(([key, value]) => { if (value) nextMap[key] = value; });
    setMapping(nextMap);
    const completeMap = requiredInvoiceFields.every((field) => Boolean(nextMap[field]));
    if (completeMap) {
      const withTotals = await pilotApi.previewInvoice(next, nextMap);
      setPreview(withTotals);
    }
  }

  const mappingComplete = requiredInvoiceFields.every((field) => Boolean(mapping[field]));

  async function calculateTotals() {
    if (!file || !mappingComplete) throw new Error("Map each required invoice field first.");
    const next = await pilotApi.previewInvoice(file, mapping);
    setPreview(next);
    setTotalsReviewed(false);
  }

  async function upload() {
    if (!contract || !file) throw new Error("Choose an invoice CSV first.");
    if (!mappingComplete) throw new Error("Map each required invoice field before importing.");
    if (!preview?.control_totals || !totalsReviewed) throw new Error("Review the invoice control totals and confirm they match the invoice you received before import.");
    const result = await pilotApi.uploadInvoice({ file, contractId: contract.id, invoiceId, periodStart: contract.period_start, periodEnd: contract.period_end, columnMapping: mapping });
    const importedInvoiceId = result.invoice_id ?? invoiceId;
    if (airVersion?.id) {
      await pilotApi.autoVerificationPlan(airVersion.id, importedInvoiceId);
    }
    await refresh();
  }

  const totals = preview?.control_totals;
  return (
    <Box id="invoice">
      <Surface title="Vendor invoice" eyebrow="02 · Invoice" complete={Boolean(status?.active_invoice_id)}>
        {!status?.contract_approved ? <Alert severity="info">Approve the contract rules before adding an invoice.</Alert> : status.active_invoice_id ? (
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(3, 1fr)" }, gap: 2 }}>
            <Metric label="Invoice" value={status.active_invoice_id} /><Metric label="Accepted lines" value={String(status.claims)} /><Metric label="Import status" value="Normalized" />
          </Box>
        ) : (
          <Stack spacing={2}>
            <Alert severity="info">CSV headers do not have to match Evidue. Confirm the mapping and finance control totals before any invoice lines are persisted.</Alert>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
              <Button component="label" variant="outlined">Choose invoice CSV<input hidden type="file" accept=".csv,text/csv" onChange={(e) => void act("Inspecting the invoice file", () => previewFile(e.target.files?.[0] ?? null))} /></Button>
              <Typography variant="body2">{file?.name ?? "No file selected"}</Typography>
            </Stack>
            {preview && (
              <>
                <TextField label="Invoice ID" value={invoiceId} onChange={(e) => setInvoiceId(e.target.value)} sx={{ maxWidth: 420 }} />
                <Typography variant="h6" fontWeight={750}>Confirm the columns</Typography>
                <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
                  {requiredInvoiceFields.map((field) => (
                    <TextField key={field} select label={readable(field)} value={mapping[field] ?? ""} onChange={(e) => { setMapping((current) => ({ ...current, [field]: e.target.value })); setPreview((current) => current ? { ...current, control_totals: null } : current); setTotalsReviewed(false); }} helperText={mapping[field] ? "Mapped" : "Required"}>
                      {preview.headers.map((header) => <MenuItem key={header} value={header}>{header}</MenuItem>)}
                    </TextField>
                  ))}
                </Box>
                <TableContainer sx={{ border: 1, borderColor: "divider", borderRadius: 2, maxHeight: 260 }}><Table size="small"><TableHead><TableRow>{preview.headers.map((header) => <TableCell key={header}>{header}</TableCell>)}</TableRow></TableHead><TableBody>{preview.sample_rows.slice(0, 3).map((row, index) => <TableRow key={index}>{preview.headers.map((header) => <TableCell key={header}>{row[header]}</TableCell>)}</TableRow>)}</TableBody></Table></TableContainer>
                {!totals && <Button variant="outlined" disabled={!mappingComplete} sx={{ alignSelf: "flex-start" }} onClick={() => void act("Calculating invoice control totals", calculateTotals)}>Review invoice totals</Button>}
                {totals && (
                  <Paper variant="outlined" sx={(theme) => ({ p: 2.5, borderRadius: 2, bgcolor: theme.palette.mode === "dark" ? "#1B2040" : "#EEF6FA", borderColor: "primary.main" })}>
                    <Typography variant="overline" color="primary.main">Control-total check</Typography>
                    <Typography variant="h6" fontWeight={760}>Does this match the invoice you received?</Typography>
                    <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" }, gap: 1.5, mt: 2 }}>
                      <Metric label="Total lines" value={String(totals.total_rows)} help={`${totals.accepted_rows} valid · ${totals.rejected_rows} rejected`} />
                      <Metric label="Amount awaiting verification" value={money(totals.total_billed, config?.default_currency)} tone="primary" />
                      <Metric label="Unique customers" value={String(totals.unique_customers)} />
                      <Metric label="Billing activity" value={`${formatDate(totals.period_start)} – ${formatDate(totals.period_end)}`} />
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
                      This billed amount is not treated as overbilling. It is simply the amount being put through contract and evidence verification before finance acts.
                    </Typography>
                    {totals.outcome_mix.length > 0 && <Stack direction="row" spacing={1} sx={{ mt: 2, flexWrap: "wrap" }}>{totals.outcome_mix.slice(0, 8).map((item) => <Chip key={item.name} size="small" label={`${readable(item.name)} · ${item.count} (${item.percent.toFixed(1)}%)`} />)}</Stack>}
                    {totals.rejected_rows > 0 && <Alert severity="warning" sx={{ mt: 2 }}>{totals.rejected_rows} row(s) would be rejected. Review the file before import.{totals.rejection_reasons[0] ? ` First issue: ${totals.rejection_reasons[0].reason}` : ""}</Alert>}
                    <FormControlLabel sx={{ mt: 1 }} control={<Checkbox checked={totalsReviewed} onChange={(e) => setTotalsReviewed(e.target.checked)} />} label="These control totals match the invoice I received." />
                  </Paper>
                )}
                {(!mappingComplete || !totals || !totalsReviewed) && (
                  <Alert severity="info">
                    {!mappingComplete
                      ? "Import is waiting for all required invoice columns to be mapped."
                      : !totals
                        ? "Import is waiting for invoice control totals to be calculated."
                        : "Import is waiting for you to confirm that the control totals match the vendor invoice."}
                  </Alert>
                )}
                <Button variant="contained" disabled={!mappingComplete || !totals || !totalsReviewed} sx={{ alignSelf: "flex-start" }} onClick={() => void act("Importing the verified invoice file", upload, "Invoice imported and normalized.")}>Import invoice</Button>
              </>
            )}
          </Stack>
        )}
      </Surface>
    </Box>
  );
}

function EvidenceWorkspace({ status, airVersion, verificationPlan, config, act, refresh }: { status: PilotStatus | null; airVersion: (AIRVersion & { agreement_ir?: AgreementIRView; finance_view?: FinanceView }) | null; verificationPlan: VerificationPlanEnvelope | null; config: WorkspaceConfig | null; act: (label: string, action: () => Promise<void>, success?: string) => Promise<void>; refresh: () => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("customer_system");
  const [complete, setComplete] = useState(false);

  useEffect(() => {
    if (source !== "customer_system") return;
    const preferred = config?.preferred_support_system || config?.preferred_payment_system || config?.preferred_crm_system;
    if (preferred) setSource(preferred);
  }, [config, source]);

  async function upload() {
    if (!status?.active_invoice_id || !file) throw new Error("Choose an evidence export first.");
    await pilotApi.uploadEvidence(file, status.active_invoice_id, source, complete);
    await pilotApi.match(status.active_invoice_id);
    if (airVersion?.id) {
      await pilotApi.autoVerificationPlan(airVersion.id, status.active_invoice_id);
      await pilotApi.deriveFacts(status.active_invoice_id, airVersion.id);
    }
    await refresh();
  }

  async function rebuildVerificationPlan() {
    if (!status?.active_invoice_id) throw new Error("Import an invoice before building the verification plan.");
    if (!airVersion?.id) throw new Error("Approve a contract rule version before building the verification plan.");
    await pilotApi.autoVerificationPlan(airVersion.id, status.active_invoice_id);
    await refresh();
  }

  const planItems = verificationPlan?.plan.items ?? [];
  const ready = planItems.filter((item) => item.status === "ready").length;
  const requirements = airVersion?.finance_view?.evidence_needed ?? [];
  const externalRequirements = requirements.length || airVersion?.agreement_ir?.proof_requirements?.length || 0;
  const evidenceComplete = isPilotEvidenceReady(Boolean(status?.active_invoice_id), externalRequirements, verificationPlan);
  const planById = new Map(planItems.map((item) => [item.proof_requirement_id, item]));
  const groupedRequirements = new Map<string, typeof requirements>();
  requirements.forEach((item) => {
    const group = evidenceGroupLabel(item, config);
    groupedRequirements.set(group, [...(groupedRequirements.get(group) ?? []), item]);
  });

  return (
    <Box id="evidence">
      <Surface title="Evidence needed by the contract" eyebrow="03 · Evidence" complete={evidenceComplete}>
        {!status?.active_invoice_id ? <Alert severity="info">Import an invoice first.</Alert> : !verificationPlan ? (
          <Stack spacing={1.5}>
            <Alert severity="info">The approved verification plan has not loaded yet. Evidue will not treat evidence as complete until the plan exists.</Alert>
            <Button variant="outlined" sx={{ alignSelf: "flex-start" }} onClick={() => void act("Building the evidence verification plan", rebuildVerificationPlan, "Verification plan rebuilt from the approved contract and current evidence sources.")}>Build verification plan</Button>
          </Stack>
        ) : externalRequirements === 0 ? (
          <Alert severity="success">These approved contract rules do not require external customer-system evidence. Continue to reconciliation.</Alert>
        ) : (
          <Stack spacing={2.5}>
            <Typography color="text.secondary">Evidue derives this checklist from the approved contract rules. Missing evidence never becomes an automatic deduction or approval; affected claims remain in Needs review.</Typography>
            {requirements.length > 0 && (
              <Stack spacing={1.5}>
                {[...groupedRequirements.entries()].map(([group, items]) => {
                  const states = items.map((item) => planById.get(item.id)?.status ?? "missing");
                  const groupState = states.every((state) => state === "ready") ? "ready" : states.some((state) => state === "ready" || state === "partial") ? "partial" : "missing";
                  return (
                    <Paper key={group} variant="outlined" className={`evidence-source-group ${groupState}`}>
                      <Box className="evidence-source-header">
                        <Box>
                          <Typography className="section-kicker">SOURCE SYSTEM</Typography>
                          <Typography variant="h6" fontWeight={740}>{group}</Typography>
                        </Box>
                        <Chip size="small" variant="outlined" color={groupState === "ready" ? "success" : groupState === "partial" ? "warning" : "default"} label={groupState === "ready" ? "Ready" : groupState === "partial" ? "Incomplete" : "Missing"} />
                      </Box>
                      <Stack spacing={1}>
                        {items.map((item) => {
                          const plan = planById.get(item.id);
                          const state = plan?.status ?? "missing";
                          return (
                            <Box key={item.id} className="evidence-requirement-row">
                              <Box>
                                <Typography fontWeight={700}>{item.description}</Typography>
                                <Typography variant="body2" color="text.secondary"><strong>Required by:</strong> {item.rule_description}</Typography>
                                <Typography variant="caption" color="text.secondary">Typical evidence: {evidenceSourceExamples(item, config).join(", ")}</Typography>
                              </Box>
                              <Box className="evidence-requirement-status">
                                <strong>{state === "ready" ? "Ready" : state === "partial" ? "Incomplete" : "Missing"}</strong>
                                <small>{state === "ready" ? "Evidence can support verification" : item.missing_evidence_effect || "Affected claims remain in Needs review"}</small>
                              </Box>
                            </Box>
                          );
                        })}
                      </Stack>
                    </Paper>
                  );
                })}
              </Stack>
            )}
            {status.events > 0 && (
              <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" }, gap: 2 }}>
                <Metric label="Evidence records" value={String(status.events)} /><Metric label="Accepted matches" value={String(status.accepted_matches)} tone="success" /><Metric label="Needs identity review" value={String((status.suggested_matches ?? 0) + status.unresolved_events)} tone={(status.suggested_matches ?? 0) + status.unresolved_events > 0 ? "warning" : "success"} /><Metric label="Contract evidence" value={planItems.length ? `${ready}/${planItems.length} ready` : "Recalculate after import"} tone={planItems.length > 0 && ready === planItems.length ? "success" : "warning"} />
              </Box>
            )}
            <Divider />
            <Typography variant="h6" fontWeight={750}>Add evidence export</Typography>
            <Alert severity="info">Upload CSV, JSON, or JSONL from the relevant source system. The source name is descriptive; the actual fields and capabilities are checked after import against the approved contract requirements.</Alert>
            <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
              <Button component="label" variant="outlined">Choose evidence export<input hidden type="file" accept=".csv,.json,.jsonl,text/csv,application/json,application/x-ndjson" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Button>
              <Typography variant="body2">{file?.name ?? "No file selected"}</Typography>
              <TextField label="Source system" value={source} onChange={(e) => setSource(e.target.value)} size="small" sx={{ minWidth: 240 }} placeholder="Zendesk" />
            </Stack>
            <FormControlLabel control={<Checkbox checked={complete} onChange={(e) => setComplete(e.target.checked)} />} label="This export completely covers the relevant billing/evidence period." />
            <Typography variant="caption" color="text.secondary">Only an export explicitly marked complete may prove that an event did not occur. Leave this unchecked for partial exports.</Typography>
            <Button variant="contained" disabled={!file} sx={{ alignSelf: "flex-start" }} onClick={() => void act("Importing and matching customer evidence", upload, "Evidence imported, matched, and checked against the contract requirements.")}>Import evidence</Button>
            {planItems.length > 0 && ready < planItems.length && <Alert severity="warning">{planItems.length - ready} evidence requirement(s) are still incomplete. Claims depending on them will remain in Needs review.</Alert>}
          </Stack>
        )}
      </Surface>
    </Box>
  );
}

function ReconciliationDeltaView({ delta, currency = "USD" }: { delta: ReconciliationDelta; currency?: string }) {
  const transitions = new Map<string, number>();
  delta.changes.forEach((change) => {
    const key = `${readable(change.status_before ?? "new")} → ${readable(change.status_after ?? "removed")}`;
    transitions.set(key, (transitions.get(key) ?? 0) + 1);
  });
  const disputeBefore = Number(delta.recommended_deduction_before || 0);
  const disputeAfter = Number(delta.recommended_deduction_after || 0);
  return (
    <Paper variant="outlined" sx={(theme) => ({ p: 2.25, borderRadius: 2, bgcolor: theme.palette.mode === "dark" ? "#1B2040" : "#EEF6FA", borderColor: "primary.main" })}>
      <Typography variant="overline" color="primary.main">New evidence changed the decision</Typography>
      <Typography variant="subtitle1" fontWeight={800}>What changed since the previous run</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.25 }}>{delta.changed_outcomes} claim(s) changed because the available evidence or matching state changed.</Typography>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ flexWrap: "wrap" }}>
        {[...transitions.entries()].map(([label, count]) => <Chip key={label} variant="outlined" label={`${count} · ${label}`} />)}
      </Stack>
      <Typography variant="body2" fontWeight={750} sx={{ mt: 1.25 }}>Charges identified for dispute: {money(disputeBefore, currency)} → {money(disputeAfter, currency)} ({money(disputeAfter - disputeBefore, currency)})</Typography>
    </Paper>
  );
}

function DecisionWorkspace({
  status,
  reconciliation,
  reconciliationDelta,
  requiresExternalEvidence,
  act,
  refresh,
}: {
  status: PilotStatus | null;
  reconciliation: Reconciliation | null;
  reconciliationDelta: ReconciliationDelta | null;
  requiresExternalEvidence: boolean;
  act: (label: string, action: () => Promise<void>, success?: string) => Promise<void>;
  refresh: () => Promise<void>;
}) {
  const [reviewItems, setReviewItems] = useState<ReviewItem[]>([]);
  const [selected, setSelected] = useState<ReviewItem | null>(null);
  const [candidates, setCandidates] = useState<MatchCandidate[]>([]);
  const [claimId, setClaimId] = useState("");
  const [rationale, setRationale] = useState("Confirmed from source identifiers");

  async function loadIdentityReview() {
    if (!status?.active_invoice_id) throw new Error("Import an invoice before reviewing evidence identity matches.");
    const result = await pilotApi.unmatched(status.active_invoice_id);
    setReviewItems(result.items);
    if (!result.items.length && (status.suggested_matches ?? 0) + status.unresolved_events > 0) {
      await refresh();
    }
  }
  async function choose(item: ReviewItem) {
    if (!status?.active_invoice_id) throw new Error("Import an invoice before matching evidence.");
    if (!item.event_id) throw new Error("This evidence item has no event identifier and cannot be matched manually.");
    const next = (await pilotApi.candidates(status.active_invoice_id, item.event_id)).candidates;
    if (!next.length) {
      setSelected(null);
      setCandidates([]);
      setClaimId("");
      throw new Error("No invoice-line candidates were found for this evidence record. Check the source identifiers or remove the unusable evidence record.");
    }
    setSelected(item); setCandidates(next); setClaimId(next[0]?.claim_id ?? "");
  }
  async function confirm() {
    if (!status?.active_invoice_id || !selected?.event_id || !claimId) throw new Error("Choose an evidence event and invoice line.");
    await pilotApi.confirmMatch({ invoiceId: status.active_invoice_id, eventId: selected.event_id, claimId, rationale });
    await pilotApi.match(status.active_invoice_id); setSelected(null); setCandidates([]); await loadIdentityReview(); await refresh();
  }
  async function reconcile() {
    if (!status?.active_invoice_id) throw new Error("Import an invoice first.");
    if ((status.suggested_matches ?? 0) + status.unresolved_events > 0) throw new Error("Resolve or remove unmatched evidence before reconciliation.");
    await pilotApi.reconcile(status.active_invoice_id); await refresh();
  }

  const rows = (reconciliation?.determinations ?? []) as Determination[];
  const needsReview = rows.filter((row) => row.status === "needs_review");

  return (
    <Box id="verification">
      <Surface title="Deterministic verification" eyebrow="04 · Verification" complete={Boolean(reconciliation)}>
        {!status?.active_invoice_id ? <Alert severity="info">Import an invoice before reconciling.</Alert> : (
          <Stack spacing={2.5}>
            {!status.events && (
              <Alert severity={requiresExternalEvidence ? "warning" : "success"}>
                {requiresExternalEvidence
                  ? "No customer-side evidence has been added. You can still run reconciliation safely; evidence-dependent lines will remain in Needs review rather than becoming deductions."
                  : "These approved contract rules have no external evidence requirements. Reconciliation can run from the invoice claims and approved rules alone."}
              </Alert>
            )}
            {((status.suggested_matches ?? 0) + status.unresolved_events > 0) && (
              <>
                <Alert severity="warning">{(status.suggested_matches ?? 0) + status.unresolved_events} evidence record(s) need identity review. Suggestions never affect money until you confirm them.</Alert>
                <Button variant="outlined" sx={{ alignSelf: "flex-start" }} onClick={() => void act("Loading evidence that needs identity review", loadIdentityReview)}>Review unmatched evidence</Button>
                {reviewItems.map((item) => <Paper key={String(item.event_id)} variant="outlined" sx={{ p: 2 }}><Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}><Box sx={{ flex: 1 }}><Typography fontWeight={700}>{String(item.event_type ?? "Evidence")}</Typography><Typography variant="body2" color="text.secondary">{String(item.match_reason ?? "No authoritative identity match")}</Typography></Box><Button onClick={() => void act("Finding possible invoice-line matches", () => choose(item))}>Match manually</Button></Stack></Paper>)}
                {selected && <Paper variant="outlined" sx={{ p: 2 }}><Stack spacing={2}><Typography fontWeight={750}>Confirm evidence → invoice line</Typography><TextField select label="Invoice line" value={claimId} onChange={(e) => setClaimId(e.target.value)}>{candidates.map((candidate) => <MenuItem key={candidate.claim_id} value={candidate.claim_id}>{String(candidate.outcome_id ?? candidate.claim_id)} · {String(candidate.reason ?? "candidate")}</MenuItem>)}</TextField><TextField label="Why this match is correct" value={rationale} onChange={(e) => setRationale(e.target.value)} /><Button variant="contained" disabled={!claimId || rationale.trim().length < 3} onClick={() => void act("Recording the confirmed evidence match", confirm, "Manual identity decision recorded in the audit trail.")}>Confirm match</Button></Stack></Paper>}
              </>
            )}
            {!reconciliation && ((status.suggested_matches ?? 0) + status.unresolved_events > 0) && (
              <Alert severity="info">
                Run reconciliation is blocked until the {(status.suggested_matches ?? 0) + status.unresolved_events} unmatched evidence record(s) above are resolved or removed.
              </Alert>
            )}
            {!reconciliation && <Button variant="contained" size="large" sx={{ alignSelf: "flex-start" }} disabled={(status.suggested_matches ?? 0) + status.unresolved_events > 0} onClick={() => void act("Matching claims to the approved rules and evidence", reconcile, "Reconciliation completed from the approved contract version.")}>Run reconciliation</Button>}
            {reconciliation && (
              <>
                {reconciliationDelta && <ReconciliationDeltaView delta={reconciliationDelta} currency={reconciliation.currency} />}
                <Paper variant="outlined" className="verification-complete-panel">
                  <Box>
                    <Typography className="section-kicker">VERIFICATION COMPLETE</Typography>
                    <Typography variant="h6" fontWeight={760}>Every invoice line has a reproducible factual state.</Typography>
                    <Typography color="text.secondary" sx={{ mt: 0.5 }}>Review separates those facts from the commercial action finance is allowed to take.</Typography>
                  </Box>
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                    <Chip size="small" color="success" variant="outlined" label={`${reconciliation.payable_outcomes} substantiated`} />
                    <Chip size="small" color="error" variant="outlined" label={`${reconciliation.disputed_outcomes} contradicted`} />
                    <Chip size="small" color="warning" variant="outlined" label={`${reconciliation.needs_review_outcomes} insufficient evidence`} />
                  </Stack>
                </Paper>
                {needsReview.length > 0 && <Alert severity="warning">{money(reconciliation.needs_review_amount, reconciliation.currency)} remains outside both payable and disputed totals until the evidence gap is resolved.</Alert>}
                <Button variant="outlined" sx={{ alignSelf: "flex-start" }} onClick={() => void act("Rerunning reconciliation with the latest evidence", reconcile, "A new append-only reconciliation run was created.")}>Rerun after evidence changes</Button>
              </>
            )}
          </Stack>
        )}
      </Surface>
    </Box>
  );
}


function ReviewWorkspace({
  reconciliation,
  onNavigate,
}: {
  reconciliation: Reconciliation | null;
  onNavigate: (stage: PilotStage) => void;
}) {
  if (!reconciliation) {
    return (
      <Surface title="Review the factual result" eyebrow="05 · Review" complete={false}>
        <Alert severity="info">Run deterministic verification first. Review begins only after Evidue has a reproducible line-level result.</Alert>
      </Surface>
    );
  }

  const rows = (reconciliation.determinations ?? []) as Determination[];
  const needsReview = rows.filter((row) => row.status === "needs_review");
  const disputed = rows.filter((row) => row.status === "disputed");
  const payable = rows.filter((row) => row.status === "payable");
  const currency = reconciliation.currency || "USD";

  return (
    <Box id="review">
      <Surface title="Facts first. Commercial action second." eyebrow="05 · Review" complete={needsReview.length === 0}>
        <Stack spacing={2.5}>
          <Box className="decision-separation-panel">
            <Box>
              <Typography className="section-kicker">WHAT HAPPENED</Typography>
              <Typography variant="h5" fontWeight={760}>Evidence-backed determination</Typography>
              <Typography color="text.secondary" sx={{ mt: 0.5 }}>
                Each claim is classified from approved contract rules and customer-controlled evidence. This is the factual layer.
              </Typography>
              <Stack spacing={1.1} sx={{ mt: 2 }}>
                <Box className="fact-action-row"><span>Substantiated</span><strong>{payable.length} claims · {money(reconciliation.confirmed_payable_amount, currency)}</strong></Box>
                <Box className="fact-action-row"><span>Contradicted</span><strong>{disputed.length} claims · {money(reconciliation.recommended_deduction, currency)}</strong></Box>
                <Box className="fact-action-row"><span>Insufficient evidence</span><strong>{needsReview.length} claims · {money(reconciliation.needs_review_amount, currency)}</strong></Box>
              </Stack>
            </Box>
            <Box>
              <Typography className="section-kicker">WHAT FINANCE CAN DO</Typography>
              <Typography variant="h5" fontWeight={760}>Commercial action</Typography>
              <Typography color="text.secondary" sx={{ mt: 0.5 }}>
                The remedy is separate from the factual determination. Evidue never assumes every contradiction automatically authorizes withholding.
              </Typography>
              <Stack spacing={1.1} sx={{ mt: 2 }}>
                <Box className="fact-action-row"><span>Substantiated claims</span><strong>Pay</strong></Box>
                <Box className="fact-action-row"><span>Contradicted claims</span><strong>Dispute / credit / true-up per contract</strong></Box>
                <Box className="fact-action-row"><span>Insufficient evidence</span><strong>Hold for review</strong></Box>
              </Stack>
            </Box>
          </Box>

          {needsReview.length > 0 && (
            <Paper variant="outlined" className="recommended-action-panel">
              <Box>
                <Typography className="section-kicker">UNRESOLVED</Typography>
                <Typography variant="h6" fontWeight={760}>{money(reconciliation.needs_review_amount, currency)} still needs evidence or judgment</Typography>
                <Typography color="text.secondary">These dollars are deliberately excluded from both payable and disputed totals until the evidence gap is resolved.</Typography>
              </Box>
              <Button variant="contained" onClick={() => onNavigate("evidence")}>Resolve evidence gaps</Button>
            </Paper>
          )}

          <Determinations rows={rows} currency={currency} />
        </Stack>
      </Surface>
    </Box>
  );
}

export function ExportWorkspace({ reconciliation, act }: { reconciliation: Reconciliation | null; act: (label: string, action: () => Promise<void>, success?: string) => Promise<void> }) {
  const [advanced, setAdvanced] = useState(false);
  const [emailText, setEmailText] = useState("");
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailError, setEmailError] = useState("");
  const id = reconciliation?.reconciliation_id ?? "";
  const hasDispute = Number(reconciliation?.recommended_deduction || 0) > 0;
  const hasReview = Number(reconciliation?.needs_review_amount || 0) > 0;

  useEffect(() => {
    if (!id || !hasDispute) {
      setEmailText("");
      setEmailError("");
      return;
    }
    let cancelled = false;
    setEmailLoading(true);
    setEmailError("");
    void pilotApi.vendorEmail(id)
      .then((text) => {
        if (!cancelled) setEmailText(text);
      })
      .catch((error) => {
        if (!cancelled) setEmailError(errorText(error));
      })
      .finally(() => {
        if (!cancelled) setEmailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [hasDispute, id]);

  if (!reconciliation) {
    return (
      <Box id="export">
        <Surface title="Finance-ready outputs" eyebrow="06 · Commercial action" complete={false}>
          <Typography color="text.secondary">Complete reconciliation first. Evidue will then prepare the corrected invoice, vendor communication, and supporting evidence package.</Typography>
        </Surface>
      </Box>
    );
  }

  async function copyEmail() {
    const text = emailText || await pilotApi.vendorEmail(id);
    if (!navigator.clipboard?.writeText) throw new Error("Clipboard access is unavailable in this browser.");
    await navigator.clipboard.writeText(text);
    if (!emailText) setEmailText(text);
  }

  return (
    <Box id="export">
      <Surface title="Move the decision into action" eyebrow="06 · Commercial action" complete>
        <Stack spacing={2.5}>
          <Paper variant="outlined" className="commercial-action-summary">
            <Box>
              <Typography className="section-kicker">DECISION PACKAGE READY</Typography>
              <Typography component="h3">
                {hasReview
                  ? `${money(reconciliation.needs_review_amount, reconciliation.currency)} still needs review before final action.`
                  : `Finance can act on ${money(reconciliation.confirmed_payable_amount, reconciliation.currency)}.`}
              </Typography>
              <Typography>
                {hasDispute
                  ? "The payable output, vendor dispute communication, and line-level evidence all come from this persisted reconciliation."
                  : "The payable output and evidence package come from this persisted reconciliation. No contract-backed disputed charges were identified."}
              </Typography>
            </Box>
            <Box className="commercial-action-amount">
              <span>Identified for dispute</span>
              <strong>{money(reconciliation.recommended_deduction, reconciliation.currency)}</strong>
              <small>{reconciliation.disputed_outcomes ?? 0} line(s)</small>
            </Box>
          </Paper>

          {hasDispute ? (
            <Paper variant="outlined" className="vendor-dispute-panel">
            <Stack spacing={1.5}>
              <Box>
                <Typography variant="overline" color="error.main">Recommended next action</Typography>
                <Typography variant="h5" fontWeight={800}>Send the vendor dispute</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 820 }}>
                  The message below is generated from the persisted reconciliation: billed amount, verified payable amount, disputed amount, affected claim count, and supporting documentation references.
                </Typography>
              </Box>

              {emailLoading && <Alert severity="info">Preparing the vendor email from this reconciliation…</Alert>}
              {emailError && <Alert severity="warning">Email preview is temporarily unavailable. You can retry with Copy vendor dispute email.</Alert>}
              {emailText && (
                <Paper variant="outlined" sx={{ p: 2, bgcolor: "background.paper", maxHeight: 320, overflow: "auto" }}>
                  <Typography component="pre" variant="body2" sx={{ m: 0, whiteSpace: "pre-wrap", fontFamily: "inherit", lineHeight: 1.65 }}>{emailText}</Typography>
                </Paper>
              )}

              <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ flexWrap: "wrap" }}>
                <Button variant="contained" color="error" onClick={() => void act("Copying vendor dispute email", copyEmail, "Vendor dispute email copied to your clipboard.")}>Copy vendor dispute email</Button>
                <Button variant="outlined" onClick={() => void act("Preparing vendor dispute report", () => pilotApi.downloadExport(id, "vendor-dispute.html"))}>Download dispute package</Button>
                <Button variant="outlined" onClick={() => void act("Preparing disputed line items", () => pilotApi.downloadExport(id, "disputes.csv"))}>Download disputed lines</Button>
              </Stack>
            </Stack>
          </Paper>

          ) : (
            <Alert severity="success">No vendor dispute is needed for this reconciliation. No contract-backed disputed charges were identified.</Alert>
          )}

          <Paper variant="outlined" className="ap-output-panel">
            <Typography variant="overline" color="success.main">For Accounts Payable</Typography>
            <Typography variant="h6">Corrected invoice</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 1.75 }}>A line-level CSV with the contract-backed payable disposition for your AP workflow.</Typography>
            <Button variant="contained" onClick={() => void act("Preparing corrected invoice", () => pilotApi.downloadExport(id, "corrected-invoice.csv"))}>Corrected invoice CSV</Button>
          </Paper>

          <Button size="small" sx={{ alignSelf: "flex-start" }} onClick={() => setAdvanced((value) => !value)}>{advanced ? "Hide audit exports" : "Show audit exports"}</Button>
          <Collapse in={advanced}>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ flexWrap: "wrap" }}>
              <Button variant="outlined" onClick={() => void act("Preparing review report", () => pilotApi.downloadExport(id, "review-report.html"))}>Internal review report</Button>
              <Button variant="outlined" onClick={() => void act("Preparing summary data", () => pilotApi.downloadExport(id, "summary.json"))}>Summary JSON</Button>
              <Button variant="outlined" onClick={() => void act("Preparing evidence package", () => pilotApi.downloadExport(id, "evidence.json"))}>Evidence package JSON</Button>
            </Stack>
          </Collapse>
        </Stack>
      </Surface>
    </Box>
  );
}

function AdvancedDetails({ airVersion, assurance, plan, facts, audit }: { airVersion: (AIRVersion & { agreement_ir?: AgreementIRView }) | null; assurance: CompilerAssurance | null; plan: VerificationPlanEnvelope | null; facts: DerivedFact[]; audit: AuditEvent[] }) {
  return (
    <Stack spacing={3}>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
        <Paper variant="outlined" sx={{ p: 2 }}><Typography fontWeight={750}>Approved rule set</Typography><Typography variant="body2" fontFamily="monospace">{airVersion?.id ?? "—"}</Typography><Typography variant="caption">Rule-set fingerprint {airVersion?.payload_hash ?? "—"}</Typography></Paper>
        <Paper variant="outlined" sx={{ p: 2 }}><Typography fontWeight={750}>Rule verification</Typography><Chip size="small" color={assurance?.hard_gate_passed ? "success" : "default"} label={assurance?.hard_gate_passed ? "Verification passed" : "Not available"} /><Typography variant="caption" display="block" sx={{ mt: 1 }}>{assurance?.checks?.filter((item) => item.status === "pass").length ?? 0}/{assurance?.checks?.length ?? 0} checks passed</Typography></Paper>
      </Box>
      {assurance?.checks?.map((check) => <Alert key={check.id} severity={check.status === "pass" ? "success" : check.hard_gate ? "error" : "warning"}><strong>{readable(check.id)}</strong> — {check.summary}{check.details.length ? ` (${check.details.join("; ")})` : ""}</Alert>)}
      {plan && <Box><Typography variant="h6" fontWeight={750} gutterBottom>Evidence verification plan (technical)</Typography>{plan.plan.items.map((item) => <Paper key={item.proof_requirement_id} variant="outlined" sx={{ p: 1.5, mb: 1 }}><Stack direction="row" spacing={1} alignItems="center"><Chip size="small" color={item.status === "ready" ? "success" : item.status === "partial" ? "warning" : "error"} label={item.status} /><Typography variant="body2" fontFamily="monospace">{item.proof_requirement_id}</Typography></Stack><Typography variant="caption">{item.rationale}</Typography></Paper>)}</Box>}
      {facts.length > 0 && <Box><Typography variant="h6" fontWeight={750} gutterBottom>Derived deterministic facts</Typography><TableContainer sx={{ border: 1, borderColor: "divider", borderRadius: 2 }}><Table size="small"><TableHead><TableRow><TableCell>Fact</TableCell><TableCell>Truth</TableCell><TableCell>Authority</TableCell><TableCell>Input hash</TableCell></TableRow></TableHead><TableBody>{facts.slice(0, 100).map((fact) => <TableRow key={fact.id}><TableCell>{fact.fact_type}</TableCell><TableCell>{fact.truth}</TableCell><TableCell>{readable(fact.authority)}</TableCell><TableCell><Typography variant="caption" fontFamily="monospace">{fact.input_hash.slice(0, 18)}…</Typography></TableCell></TableRow>)}</TableBody></Table></TableContainer></Box>}
      <Box><Typography variant="h6" fontWeight={750} gutterBottom>Workspace audit history</Typography>{audit.length ? audit.map((event) => <Box key={event.id} sx={{ py: 1, borderBottom: 1, borderColor: "divider", display: "grid", gridTemplateColumns: { xs: "1fr", md: "180px 1fr 180px" }, gap: 1 }}><Typography variant="caption">{new Date(event.occurred_at).toLocaleString()}</Typography><Typography variant="body2"><strong>{readable(event.action)}</strong> · {event.object_type}</Typography><Typography variant="caption" fontFamily="monospace">{event.object_id?.slice(0, 20) ?? "workspace"}</Typography></Box>) : <Typography color="text.secondary">Open Advanced after activity to load the audit trail.</Typography>}</Box>
    </Stack>
  );
}
