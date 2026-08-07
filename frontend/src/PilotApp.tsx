import {
  Alert,
  AppBar,
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
  Toolbar,
  Typography,
} from "@mui/material";
import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useEvidueThemeMode } from "./templateTheme";
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

type PilotStage = "agreement" | "invoice" | "evidence" | "decision" | "export";

const pilotStages: Array<{ id: PilotStage; label: string; hint: string }> = [
  { id: "agreement", label: "Agreement & rules", hint: "Define the payment policy" },
  { id: "invoice", label: "Invoice", hint: "Verify the control totals" },
  { id: "evidence", label: "Evidence", hint: "Prove what happened" },
  { id: "decision", label: "Decision", hint: "See what finance should pay" },
  { id: "export", label: "Send & export", hint: "Move the result into action" },
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
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        overflow: "hidden",
        bgcolor: "#151A22",
        borderColor: "#2A313C",
        boxShadow: "0 24px 70px rgba(0,0,0,0.26)",
        position: "relative",
        "&::before": {
          content: '""',
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          background: "radial-gradient(circle at 82% 0%, rgba(124,92,252,0.10), transparent 34%)",
        },
      }}
    >
      <Box
        sx={{
          px: { xs: 2.25, md: 3 },
          py: 2.2,
          display: "flex",
          gap: 2,
          justifyContent: "space-between",
          alignItems: "center",
          bgcolor: "#171D26",
          borderBottom: "1px solid #2A313C",
          position: "relative",
          zIndex: 1,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, minWidth: 0 }}>
          <Box
            sx={{
              width: 9,
              height: 38,
              borderRadius: 99,
              background: complete === false
                ? "linear-gradient(180deg, #F4B860, #D98C3F)"
                : complete === true
                  ? "linear-gradient(180deg, #4DE0A0, #1FAA76)"
                  : "linear-gradient(180deg, #9B8AFB, #6D54EB)",
              boxShadow: complete === false
                ? "0 0 22px rgba(244,184,96,.18)"
                : complete === true
                  ? "0 0 22px rgba(77,224,160,.16)"
                  : "0 0 22px rgba(124,92,252,.20)",
              flex: "0 0 auto",
            }}
          />
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="overline" sx={{ color: "#8E98A8", lineHeight: 1.1 }}>{eyebrow}</Typography>
            <Typography variant="h5" sx={{ color: "#F7F9FC", fontWeight: 760, mt: 0.25 }}>{title}</Typography>
          </Box>
        </Box>
        <Stack direction="row" spacing={1} alignItems="center">
          {complete !== undefined && (
            <Chip
              size="small"
              label={complete ? "Ready" : "Action needed"}
              sx={{
                color: complete ? "#BFF4D9" : "#FFE0A8",
                bgcolor: complete ? "rgba(77,224,160,.10)" : "rgba(244,184,96,.10)",
                border: `1px solid ${complete ? "rgba(77,224,160,.30)" : "rgba(244,184,96,.30)"}`,
              }}
            />
          )}
          {action}
        </Stack>
      </Box>
      <CardContent
        sx={{
          p: { xs: 2.25, md: 3 },
          bgcolor: "#131820",
          position: "relative",
          zIndex: 1,
          "&:last-child": { pb: { xs: 2.25, md: 3 } },
        }}
      >
        {children}
      </CardContent>
    </Card>
  );
}

type MetricTone = "neutral" | "primary" | "success" | "warning" | "error";

function Metric({ label, value, help, tone = "neutral" }: { label: string; value: string; help?: string; tone?: MetricTone }) {
  const toneMap: Record<MetricTone, { bg: string; border: string; glow: string; value: string }> = {
    neutral: { bg: "#1B212B", border: "#303844", glow: "transparent", value: "#F5F7FA" },
    primary: { bg: "#211D38", border: "#5E4BC9", glow: "rgba(124,92,252,.12)", value: "#C8BFFF" },
    success: { bg: "#152821", border: "#237B59", glow: "rgba(77,224,160,.10)", value: "#A9EEC9" },
    warning: { bg: "#2A2419", border: "#9C6B2E", glow: "rgba(244,184,96,.10)", value: "#FFD694" },
    error: { bg: "#2D1B21", border: "#9C4052", glow: "rgba(255,107,122,.10)", value: "#FFB0BA" },
  };
  const colors = toneMap[tone];
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        minWidth: 0,
        bgcolor: colors.bg,
        borderColor: colors.border,
        borderRadius: 2.25,
        boxShadow: colors.glow === "transparent" ? "none" : `0 12px 32px ${colors.glow}`,
      }}
    >
      <Typography variant="caption" sx={{ color: "#8F9AAA", fontWeight: 760, letterSpacing: ".025em" }}>{label}</Typography>
      <Typography variant="h6" noWrap sx={{ color: colors.value, fontWeight: 790, mt: 0.35, fontVariantNumeric: "tabular-nums", letterSpacing: "-.025em" }}>{value}</Typography>
      {help && <Typography variant="caption" sx={{ color: "#738094", display: "block", mt: 0.25 }}>{help}</Typography>}
    </Paper>
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
  const { mode, toggleMode } = useEvidueThemeMode();
  const location = useLocation();
  const navigate = useNavigate();
  const configPage = location.pathname === "/pilot/config";

  useEffect(() => {
    if (mode !== "dark") toggleMode();
  }, [mode, toggleMode]);
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
  const verificationItems = verificationPlan?.plan.items ?? [];
  const evidenceReady = Boolean(
    status?.active_invoice_id
      && (evidenceRequirementCount === 0
        || (verificationItems.length > 0 && verificationItems.every((item) => item.status === "ready"))),
  );
  const stageCompletion: Record<PilotStage, boolean> = {
    agreement: Boolean(contract && status?.contract_approved && !status?.approved_rules_stale),
    invoice: Boolean(status?.active_invoice_id),
    evidence: evidenceReady,
    decision: Boolean(reconciliation),
    export: false,
  };
  const completedStages = (["agreement", "invoice", "evidence", "decision"] as PilotStage[]).filter((stage) => stageCompletion[stage]).length;
  const readinessPercent = Math.round((completedStages / 4) * 100);

  const recommendedStage = useMemo<PilotStage>(() => {
    if (!contract || !status?.contract_approved || status?.approved_rules_stale) return "agreement";
    if (!status.active_invoice_id) return "invoice";
    if (!evidenceReady) return "evidence";
    if (!reconciliation) return "decision";
    return "decision";
  }, [contract, evidenceReady, reconciliation, status]);

  useEffect(() => {
    if (!stageTouched) setActiveStage(recommendedStage);
  }, [recommendedStage, stageTouched]);

  function goToStage(stage: PilotStage) {
    setStageTouched(true);
    setActiveStage(stage);
    window.requestAnimationFrame(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  }

  if (!token) {
    return (
      <Box
        sx={(theme) => ({
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          px: 2,
          py: 5,
          bgcolor: theme.palette.mode === "dark" ? "#0D141B" : "#E9EEF2",
        })}
      >
        <Paper
          variant="outlined"
          sx={{
            width: "100%",
            maxWidth: 1040,
            overflow: "hidden",
            borderRadius: 3,
            display: "grid",
            gridTemplateColumns: { xs: "1fr", md: "0.9fr 1.1fr" },
            boxShadow: "0 26px 70px rgba(20,33,43,0.12)",
          }}
        >
          <Box sx={{ bgcolor: "#0F172A", color: "#F8FAFC", p: { xs: 3.5, md: 6 }, display: "flex", flexDirection: "column", justifyContent: "space-between", minHeight: { md: 610 } }}>
            <Box>
              <Typography variant="overline" sx={{ color: "#A5B4FC", fontWeight: 900 }}>Evidue</Typography>
              <Typography variant="h3" sx={{ mt: 1.5, maxWidth: 430 }}>Know what the invoice is actually worth.</Typography>
              <Typography sx={{ mt: 2, color: "#C8D3DA", maxWidth: 460 }}>
                Reconcile outcome-priced AI invoices against the agreement and your own operational evidence before money moves.
              </Typography>
            </Box>
            <Stack spacing={1.5} sx={{ mt: 5 }}>
              {[
                ["01", "Contract-backed", "AI proposes the interpretation; you approve the payment rules."],
                ["02", "Evidence-backed", "Customer-owned records prove what happened after the vendor's claim."],
                ["03", "Deterministic dollars", "Approved rules—not an LLM—produce payable, disputed, or needs-review."],
              ].map(([number, title, text]) => (
                <Box key={number} sx={{ display: "grid", gridTemplateColumns: "36px 1fr", gap: 1.5, alignItems: "start" }}>
                  <Box sx={{ width: 30, height: 30, borderRadius: "50%", border: "1px solid #456171", display: "grid", placeItems: "center", color: "#A5B4FC", fontSize: 11, fontWeight: 800 }}>{number}</Box>
                  <Box><Typography fontWeight={760}>{title}</Typography><Typography variant="body2" sx={{ color: "#94A3B8" }}>{text}</Typography></Box>
                </Box>
              ))}
            </Stack>
          </Box>
          <Box sx={{ p: { xs: 3.5, md: 6 }, bgcolor: "background.paper", alignSelf: "stretch", display: "flex", flexDirection: "column", justifyContent: "center" }}>
            <Typography variant="overline" color="primary.main" fontWeight={820}>Private pilot</Typography>
            <Typography variant="h3" fontWeight={720} sx={{ mt: 0.75 }}>Open your finance workspace</Typography>
            <Typography color="text.secondary" sx={{ mt: 1.5 }}>
              Use the access key provided for your Evidue pilot. Your workspace contains contracts, invoice data, evidence, and reconciliation history.
            </Typography>
            <Box sx={{ mt: 3, p: 2, borderRadius: 2, bgcolor: "action.hover", border: 1, borderColor: "divider" }}>
              <Typography variant="body2" fontWeight={700}>Authority boundary</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.4 }}>
                AI interprets the agreement. You approve the rules. Deterministic code decides invoice money.
              </Typography>
            </Box>
            {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
            <Box component="form" onSubmit={authenticate} sx={{ mt: 3 }}>
              <Stack spacing={2}>
                <TextField label="Pilot access key" type="password" value={tokenDraft} onChange={(event) => setTokenDraft(event.target.value)} autoFocus fullWidth helperText="Provided by your Evidue pilot administrator." />
                <Button type="submit" variant="contained" size="large">Open workspace</Button>
              </Stack>
            </Box>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 2 }}>
              Stored in this browser session only. Never placed in a URL.
            </Typography>
          </Box>
        </Paper>
      </Box>
    );
  }

  const emptyWorkspace = Boolean(status && !status.active_contract_id);

  return (
    <Box
      sx={{
        minHeight: "100vh",
        color: "#F5F7FA",
        bgcolor: "#0B0E13",
        backgroundImage: [
          "radial-gradient(circle at 78% -12%, rgba(124,92,252,.16), transparent 28%)",
          "radial-gradient(circle at 18% 10%, rgba(42,183,255,.07), transparent 24%)",
          "linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px)",
          "linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px)",
        ].join(","),
        backgroundSize: "auto, auto, 36px 36px, 36px 36px",
        "& .MuiPaper-root": { color: "#F5F7FA" },
        "& .MuiOutlinedInput-root": {
          color: "#F5F7FA",
          bgcolor: "#0F141B",
          "& fieldset": { borderColor: "#343D49" },
          "&:hover fieldset": { borderColor: "#596577" },
          "&.Mui-focused fieldset": { borderColor: "#8B76FF" },
        },
        "& .MuiInputLabel-root": { color: "#8995A6" },
        "& .MuiInputLabel-root.Mui-focused": { color: "#B6A9FF" },
        "& .MuiFormHelperText-root": { color: "#778395" },
        "& .MuiDivider-root": { borderColor: "#2B333E" },
        "& .MuiTableCell-root": { color: "#DCE2EA", borderColor: "#2B333E" },
        "& .MuiTableCell-head": { color: "#94A0B1", bgcolor: "#171D26" },
      }}
    >
      <AppBar
        position="sticky"
        elevation={0}
        sx={{
          bgcolor: "rgba(8, 10, 14, 0.92)",
          color: "#F8FAFC",
          borderBottom: "1px solid #242B35",
          backdropFilter: "blur(22px)",
        }}
      >
        <Toolbar sx={{ gap: 1.5, minHeight: 64 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, flexGrow: 1 }}>
            <Box
              sx={{
                width: 36,
                height: 36,
                borderRadius: 2,
                background: "linear-gradient(135deg, #A996FF 0%, #7457F2 100%)",
                color: "#090B10",
                border: "1px solid rgba(255,255,255,0.38)",
                boxShadow: "0 7px 20px rgba(0,0,0,0.18)",
                display: "grid",
                placeItems: "center",
                fontWeight: 950,
                letterSpacing: "-0.06em",
              }}
            >
              E
            </Box>
            <Box>
              <Typography fontWeight={820} lineHeight={1.05}>Evidue</Typography>
              <Typography variant="caption" sx={{ color: "#7F8A9A" }}>Outcome invoice reconciliation</Typography>
            </Box>
          </Box>
          {status?.workspace_id && <Chip size="small" label={status.workspace_id} sx={{ display: { xs: "none", md: "inline-flex" }, bgcolor: "#1E293B", color: "#E2E8F0", border: "1px solid #334155" }} />}
          <Button color="inherit" variant={!configPage ? "outlined" : "text"} sx={{ borderColor: !configPage ? "#64748B" : "transparent" }} onClick={() => navigate("/pilot")}>Workspace</Button>
          <Button color="inherit" variant={configPage ? "outlined" : "text"} sx={{ borderColor: configPage ? "#64748B" : "transparent" }} onClick={() => navigate("/pilot/config")}>Configuration</Button>
          <Button color="inherit" onClick={() => void refresh()} disabled={Boolean(busy)} sx={{ display: { xs: "none", sm: "inline-flex" } }}>Refresh</Button>
          <Button color="inherit" onClick={signOut}>Sign out</Button>
        </Toolbar>
      </AppBar>

      {busy && <LinearProgress sx={{ position: "sticky", top: 64, zIndex: 1200 }} />}

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
            maxWidth: 1600,
            mx: "auto",
            px: { xs: 1.5, md: 3 },
            py: { xs: 2, md: 3 },
            display: "grid",
            gridTemplateColumns: { xs: "1fr", lg: "238px minmax(0, 1fr)" },
            gap: { xs: 2, lg: 2.5 },
            alignItems: "start",
          }}
        >
          <PilotStageRail
            activeStage={activeStage}
            completion={stageCompletion}
            readinessPercent={readinessPercent}
            completedStages={completedStages}
            onNavigate={goToStage}
            status={status}
            reconciliation={reconciliation}
          />

          <Stack
            spacing={2.25}
            sx={{
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
              <Paper variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
                <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1.2fr 0.8fr" } }}>
                  <Box sx={{ bgcolor: "#0F172A", color: "#F8FAFC", p: { xs: 3, md: 4.5 } }}>
                    <Typography variant="overline" sx={{ color: "#AFA4EE" }}>First reconciliation</Typography>
                    <Typography variant="h3" sx={{ mt: 0.8, maxWidth: 700 }}>Get to a defensible payable amount without learning Evidue first.</Typography>
                    <Typography sx={{ mt: 1.5, color: "#CBD5E1", maxWidth: 690 }}>
                      Start with a completed sample to see the end result, or bring your own agreement and build the decision from source terms.
                    </Typography>
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mt: 3 }}>
                      <Button
                        variant="contained"
                        size="large"
                        disabled={Boolean(busy)}
                        onClick={() => void act("Creating sample workspace", async () => { setStageTouched(false); await pilotApi.seedSample(); await refresh(); }, "Sample workspace is ready.")}
                      >
                        Try sample workspace
                      </Button>
                      <Button
                        variant="outlined"
                        size="large"
                        sx={{ color: "#F8FAFC", borderColor: "#64748B", "&:hover": { borderColor: "#A5B4FC", bgcolor: "rgba(255,255,255,0.04)" } }}
                        onClick={() => { goToStage("agreement"); window.requestAnimationFrame(() => document.getElementById("contract")?.scrollIntoView({ behavior: "smooth" })); }}
                      >
                        Use my own data
                      </Button>
                    </Stack>
                  </Box>
                  <Box sx={{ bgcolor: "#171522", color: "#F5F7FA", p: { xs: 3, md: 4.5 }, display: "flex", flexDirection: "column", justifyContent: "center", borderLeft: { md: "1px solid #2B2840" } }}>
                    <Typography variant="overline" sx={{ color: "#AFA4EE" }}>What the sample proves</Typography>
                    <Stack spacing={1.3} sx={{ mt: 1.5 }}>
                      {["One contract-backed payable line", "One evidence-backed disputed line", "One line held safely in Needs review"].map((label, index) => (
                        <Box key={label} sx={{ display: "flex", gap: 1.2, alignItems: "center" }}>
                          <Box sx={{ width: 27, height: 27, borderRadius: "50%", bgcolor: "#242038", border: "1px solid #4E436E", display: "grid", placeItems: "center", fontWeight: 800, color: "#C6BCFF" }}>{index + 1}</Box>
                          <Typography variant="body2" fontWeight={690}>{label}</Typography>
                        </Box>
                      ))}
                    </Stack>
                    <Typography variant="caption" sx={{ mt: 2, color: "#7E899A" }}>Synthetic data is clearly labeled and can be reset afterward.</Typography>
                  </Box>
                </Box>
              </Paper>
            )}

            {!emptyWorkspace && (
              <WorkspaceCommandHeader
                contract={contract}
                status={status}
                reconciliation={reconciliation}
                activeStage={activeStage}
                readinessPercent={readinessPercent}
              />
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
              <InvoiceWorkspace contract={contract} status={status} config={config} act={act} refresh={refresh} />
            )}

            {activeStage === "evidence" && (
              <EvidenceWorkspace status={status} airVersion={airVersion} verificationPlan={verificationPlan} config={config} act={act} refresh={refresh} />
            )}

            {activeStage === "decision" && (
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
                <Surface
                  title="Auditability and runtime details"
                  eyebrow="Advanced"
                  action={<Button size="small" onClick={() => { setAdvanced((value) => !value); if (!advanced) void act("Loading audit history", async () => setAuditEvents((await pilotApi.auditLog()).events)); }}>{advanced ? "Hide" : "Show"}</Button>}
                >
                  <Collapse in={advanced} unmountOnExit>
                    <AdvancedDetails airVersion={airVersion} assurance={assurance} plan={verificationPlan} facts={facts} audit={auditEvents} />
                  </Collapse>
                  {!advanced && <Typography color="text.secondary">Open the technical trail only when you need to verify rule checks, evidence derivation, immutable IDs, or workspace history.</Typography>}
                </Surface>
              </>
            )}

            {activeStage === "export" && <ExportWorkspace reconciliation={reconciliation} act={act} />}
          </Stack>
        </Box>
      )}
    </Box>
  );
}

function PilotStageRail({
  activeStage,
  completion,
  readinessPercent,
  completedStages,
  onNavigate,
  status,
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
    <Box
      component="aside"
      sx={{
        position: { lg: "sticky" },
        top: { lg: 84 },
        color: "#DDE3EC",
        px: { xs: 0, lg: 0.5 },
      }}
    >
      <Box sx={{ px: 1.2, pb: 2.1, borderBottom: "1px solid #242B35" }}>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-end">
          <Box>
            <Typography variant="overline" sx={{ color: "#777FF2" }}>Readiness</Typography>
            <Typography variant="h3" sx={{ mt: 0.2, fontWeight: 780, letterSpacing: "-.055em", color: "#F7F9FC" }}>{readinessPercent}%</Typography>
          </Box>
          <Typography variant="caption" sx={{ color: "#707C8D", pb: 0.45 }}>{completedStages}/4 controls</Typography>
        </Stack>
        <LinearProgress
          variant="determinate"
          value={readinessPercent}
          sx={{
            mt: 1.35,
            height: 5,
            bgcolor: "#202731",
            "& .MuiLinearProgress-bar": {
              bgcolor: readinessPercent === 100 ? "#4DE0A0" : "#7C5CFC",
              boxShadow: readinessPercent === 100 ? "0 0 18px rgba(77,224,160,.24)" : "0 0 18px rgba(124,92,252,.25)",
            },
          }}
        />
      </Box>

      <Stack direction={{ xs: "row", lg: "column" }} spacing={0} sx={{ py: 1.5, overflowX: { xs: "auto", lg: "visible" } }}>
        {pilotStages.map((stage, index) => {
          const selected = stage.id === activeStage;
          const done = completion[stage.id];
          const statusLabel = done ? "complete" : selected ? "current" : "not complete";
          return (
            <Button
              key={stage.id}
              aria-current={selected ? "step" : undefined}
              aria-label={`${stage.label}: ${statusLabel}. ${stage.hint}`}
              onClick={() => onNavigate(stage.id)}
              sx={{
                position: "relative",
                px: 1.15,
                py: 1.1,
                minHeight: 58,
                width: { xs: 190, lg: "100%" },
                flex: { xs: "0 0 auto", lg: "1 1 auto" },
                justifyContent: "flex-start",
                textAlign: "left",
                color: selected ? "#FFFFFF" : done ? "#BAC4D0" : "#758193",
                borderRadius: 1.8,
                bgcolor: selected ? "rgba(124,92,252,.12)" : "transparent",
                border: selected ? "1px solid rgba(124,92,252,.22)" : "1px solid transparent",
                "&::before": {
                  content: '""',
                  position: "absolute",
                  left: 0,
                  top: 11,
                  bottom: 11,
                  width: 3,
                  borderRadius: 99,
                  bgcolor: selected ? "#8B76FF" : "transparent",
                  boxShadow: selected ? "0 0 18px rgba(139,118,255,.42)" : "none",
                },
                "&:hover": { bgcolor: selected ? "rgba(124,92,252,.16)" : "rgba(255,255,255,.035)" },
              }}
            >
              <Box
                sx={{
                  width: 27,
                  height: 27,
                  flex: "0 0 27px",
                  borderRadius: "50%",
                  display: "grid",
                  placeItems: "center",
                  mr: 1.15,
                  bgcolor: done ? "#173D30" : selected ? "#7C5CFC" : "#171D25",
                  border: `1px solid ${done ? "#2E8A67" : selected ? "#9A88FF" : "#2B333E"}`,
                  color: done ? "#8FF0BE" : selected ? "#FFFFFF" : "#657184",
                  fontWeight: 850,
                  fontSize: 11,
                }}
              >
                {done ? "✓" : stage.id === "export" && reconciliation ? "→" : index + 1}
              </Box>
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="body2" sx={{ fontWeight: 730, color: "inherit" }}>{stage.label}</Typography>
                <Typography variant="caption" sx={{ color: selected ? "#AFA4EE" : "#687587", display: "block", mt: 0.1 }}>{stage.hint}</Typography>
              </Box>
            </Button>
          );
        })}
      </Stack>

      <Box sx={{ mt: 1, p: 1.5, borderTop: "1px solid #242B35" }}>
        {reconciliation ? (
          <>
            <Typography variant="caption" sx={{ color: "#6F7A8A" }}>Latest verified payable</Typography>
            <Typography variant="h5" sx={{ mt: 0.35, color: "#A9EEC9", fontWeight: 790, fontVariantNumeric: "tabular-nums" }}>{money(reconciliation.confirmed_payable_amount, reconciliation.currency)}</Typography>
          </>
        ) : (
          <>
            <Typography variant="caption" sx={{ color: "#6F7A8A" }}>Workspace</Typography>
            <Typography variant="body2" sx={{ mt: 0.35, color: "#A6B0BF" }}>{status?.claims ?? 0} claims · {status?.events ?? 0} evidence records</Typography>
          </>
        )}
      </Box>
    </Box>
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
  return (
    <Paper
      variant="outlined"
      sx={{
        overflow: "hidden",
        borderRadius: 3,
        bgcolor: "#11161E",
        borderColor: "#2B333E",
        boxShadow: "0 30px 80px rgba(0,0,0,.28)",
        backgroundImage: "radial-gradient(circle at 92% 15%, rgba(124,92,252,.18), transparent 28%), radial-gradient(circle at 70% 110%, rgba(42,183,255,.08), transparent 30%)",
      }}
    >
      <Box sx={{ p: { xs: 2.5, md: 3 }, display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(0,1.4fr) minmax(280px,.6fr)" }, gap: 3, alignItems: "end" }}>
        <Box>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.2 }}>
            <Chip size="small" label="LIVE WORKSPACE" sx={{ color: "#B7ABFF", bgcolor: "rgba(124,92,252,.10)", border: "1px solid rgba(124,92,252,.25)", letterSpacing: ".06em", fontSize: 10 }} />
            <Typography variant="caption" sx={{ color: "#667385" }}>{stage?.label}</Typography>
          </Stack>
          <Typography variant="h3" sx={{ color: "#F8FAFC", fontWeight: 790, letterSpacing: "-.05em", maxWidth: 900 }}>
            {contract ? `${contract.customer} × ${contract.vendor}` : "Invoice reconciliation"}
          </Typography>
          <Typography sx={{ mt: 1, color: "#8E9AAA", maxWidth: 760 }}>
            {contract
              ? `Governing agreement ${formatDate(contract.period_start)} – ${formatExclusiveEnd(contract.period_end)}. Every payable dollar is tied back to approved terms and customer evidence.`
              : "Turn contract terms, invoice claims, and customer evidence into an auditable payment decision."}
          </Typography>
        </Box>

        <Box sx={{ borderLeft: { md: "1px solid #2B333E" }, pl: { md: 3 } }}>
          {reconciliation ? (
            <>
              <Typography variant="overline" sx={{ color: "#6F7C8D" }}>Verified payable</Typography>
              <Typography variant="h3" sx={{ color: "#A9EEC9", fontWeight: 800, mt: 0.25, fontVariantNumeric: "tabular-nums" }}>{money(reconciliation.confirmed_payable_amount, reconciliation.currency)}</Typography>
              <Stack direction="row" spacing={1} sx={{ mt: 1.1, flexWrap: "wrap" }}>
                <Chip size="small" label={`${money(reconciliation.recommended_deduction, reconciliation.currency)} disputed`} sx={{ color: "#FFB0BA", bgcolor: "rgba(255,107,122,.08)", border: "1px solid rgba(255,107,122,.22)" }} />
                <Chip size="small" label={`${money(reconciliation.needs_review_amount, reconciliation.currency)} review`} sx={{ color: "#FFD694", bgcolor: "rgba(244,184,96,.08)", border: "1px solid rgba(244,184,96,.22)" }} />
              </Stack>
            </>
          ) : (
            <>
              <Typography variant="overline" sx={{ color: "#6F7C8D" }}>Controls ready</Typography>
              <Box sx={{ display: "flex", alignItems: "baseline", gap: 1 }}>
                <Typography variant="h3" sx={{ color: "#C8BFFF", fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>{readinessPercent}%</Typography>
                <Typography variant="body2" sx={{ color: "#667385" }}>before payment decision</Typography>
              </Box>
              <Typography variant="caption" sx={{ display: "block", mt: 1, color: "#748093" }}>{status?.active_invoice_id ? "Invoice loaded" : "Invoice not yet loaded"} · {status?.events ?? 0} evidence records</Typography>
            </>
          )}
        </Box>
      </Box>
      <Box sx={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", borderTop: "1px solid #252D37" }}>
        {[
          ["Contract", status?.contract_approved ? "Approved" : "Needs review", Boolean(status?.contract_approved)],
          ["Invoice", status?.active_invoice_id ? `${status.claims ?? 0} claims` : "Not loaded", Boolean(status?.active_invoice_id)],
          ["Evidence", `${status?.events ?? 0} records`, Boolean(status?.events)],
          ["Decision", reconciliation ? "Complete" : "Not run", Boolean(reconciliation)],
        ].map(([label, value, ready], index) => (
          <Box key={String(label)} sx={{ px: 2.25, py: 1.4, borderLeft: index ? "1px solid #252D37" : "none", bgcolor: ready ? "rgba(77,224,160,.025)" : "rgba(255,255,255,.01)" }}>
            <Typography variant="caption" sx={{ color: "#687486" }}>{label}</Typography>
            <Typography variant="body2" sx={{ mt: 0.15, color: ready ? "#B7EED1" : "#9AA5B4", fontWeight: 700 }}>{String(value)}</Typography>
          </Box>
        ))}
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
    if ((planItems.length > 0 && missing > 0) || (planItems.length > 0 && !status.events)) {
      title = "Close the evidence gaps before deciding money";
      body = `${missing || planItems.length} contract evidence requirement(s) are not ready. Affected claims stay in Needs review instead of being silently paid or deducted.`;
      cta = "Add required evidence";
      stage = "evidence";
    } else if (!reconciliation) {
      title = "Everything required for a deterministic decision is ready";
      body = "The approved rules, normalized invoice, and available customer evidence can now be evaluated together.";
      cta = "Review readiness";
      stage = "decision";
    } else if (Number(reconciliation.needs_review_amount) > 0) {
      title = `${money(reconciliation.needs_review_amount, reconciliation.currency)} is still protected from an unsupported decision`;
      body = "Open the Needs review lines to see exactly which evidence or identity decision would resolve them.";
      cta = "Review unresolved lines";
      stage = "decision";
    } else {
      title = "The financial decision is complete";
      body = "Review the result, then move the corrected invoice and dispute package into your AP and vendor workflow.";
      cta = "Open finance outputs";
      stage = "export";
    }
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        overflow: "hidden",
        borderRadius: 2.5,
        borderColor: "#443A75",
        bgcolor: "#171522",
        backgroundImage: "linear-gradient(115deg, rgba(124,92,252,.17) 0%, rgba(124,92,252,.04) 42%, rgba(42,183,255,.035) 100%)",
        boxShadow: "0 16px 48px rgba(0,0,0,.22)",
      }}
    >
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(0,1fr) auto" }, gap: 2, p: { xs: 2.2, md: 2.5 }, alignItems: "center" }}>
        <Box sx={{ display: "grid", gridTemplateColumns: "10px minmax(0,1fr)", gap: 1.5, alignItems: "stretch" }}>
          <Box sx={{ borderRadius: 99, background: "linear-gradient(180deg,#A18BFF,#6D54EB)", boxShadow: "0 0 22px rgba(124,92,252,.28)" }} />
          <Box>
            <Typography variant="overline" sx={{ color: "#AFA4EE" }}>Next control</Typography>
            <Typography variant="h5" sx={{ color: "#F8FAFC", fontWeight: 760, mt: 0.15 }}>{title}</Typography>
            <Typography sx={{ mt: 0.45, color: "#8F9AAA", maxWidth: 900 }}>{body}</Typography>
          </Box>
        </Box>
        <Button
          variant="contained"
          size="large"
          onClick={() => onNavigate(stage)}
          sx={{
            minWidth: 190,
            bgcolor: "#7C5CFC",
            color: "#FFFFFF",
            boxShadow: "0 10px 28px rgba(124,92,252,.24)",
            "&:hover": { bgcolor: "#8A6DFF", boxShadow: "0 12px 34px rgba(124,92,252,.34)" },
          }}
        >
          {cta}
        </Button>
      </Box>
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
    navigate("/pilot");
  }

  return (
    <Stack spacing={3}>
      <Paper variant="outlined" sx={{ p: { xs: 3, md: 4 }, bgcolor: "#11161E", color: "#F8FAFC", borderColor: "#2B333E", borderRadius: 2.5 }}>
        <Typography variant="overline" sx={{ color: "#A5B4FC" }} fontWeight={850}>Configuration</Typography>
        <Typography variant="h3" fontWeight={720}>Workspace settings</Typography>
        <Typography sx={{ mt: 1, maxWidth: 800, color: "#CBD5E1" }}>
          Set finance-friendly defaults and preferred customer systems. Secrets stay on the server; this page never reads or stores API keys.
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
          These names are suggestions in the evidence checklist. Contract proof requirements still determine what evidence is actually needed.
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
              <Box><Typography fontWeight={750}>Contract analysis AI</Typography><Typography variant="body2" color="text.secondary">{config?.integrations.contract_ai.provider ?? "Google Gemini"} · {config?.integrations.contract_ai.model ?? "default model"}</Typography></Box>
              <Chip color={config?.integrations.contract_ai.configured ? "success" : "warning"} label={config?.integrations.contract_ai.configured ? "Configured" : "Not configured"} />
            </Stack>
            <Typography variant="caption" color="text.secondary">Configure GEMINI_API_KEY in the backend environment. The value is never exposed to this page.</Typography>
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

function Overview({ status, reconciliation }: { status: PilotStatus | null; reconciliation: Reconciliation | null }) {
  if (!reconciliation) {
    return (
      <Paper
        variant="outlined"
        sx={(theme) => ({
          p: { xs: 2.5, md: 3.25 },
          borderRadius: 2.5,
          bgcolor: theme.palette.mode === "dark" ? "#171E2A" : "#F7F7FD",
        })}
      >
        <Typography variant="overline" color="primary.main">Decision preview</Typography>
        <Typography variant="h4" fontWeight={720} sx={{ mt: 0.4 }}>The payable amount will land here.</Typography>
        <Typography color="text.secondary" sx={{ mt: 1, maxWidth: 760 }}>
          Evidue does not estimate before the approved rules and required evidence are ready. Run reconciliation to produce the amount finance can act on.
        </Typography>
        {status && (
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.25} sx={{ mt: 2.25 }}>
            <Chip variant="outlined" label={`${status.claims} invoice lines`} />
            <Chip variant="outlined" label={`${status.events} evidence records`} />
            <Chip variant="outlined" label={`${status.accepted_match_rate}% evidence match rate`} />
          </Stack>
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

  return (
    <Paper variant="outlined" sx={{ borderRadius: 3, overflow: "hidden", borderColor: "#263E4D" }}>
      <Box sx={{ bgcolor: "#0F172A", color: "#F8FAFC", p: { xs: 3, md: 4 } }}>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(0,1.4fr) minmax(280px,0.6fr)" }, gap: 3, alignItems: "end" }}>
          <Box>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5, flexWrap: "wrap" }}>
              <Chip size="small" label="Reconciliation complete" sx={{ bgcolor: "#203746", color: "#DDEAF1", border: "1px solid #365366" }} />
              <Typography variant="caption" sx={{ color: "#94A8B5" }}>{reconciliation.claimed_outcomes ?? 0} vendor claims evaluated</Typography>
            </Stack>
            <Typography variant="overline" sx={{ color: "#A5B4FC" }}>Verified payable</Typography>
            <Typography variant="h2" sx={{ mt: 0.15, fontSize: { xs: "2.7rem", md: "4.25rem" }, fontWeight: 760, letterSpacing: "-0.055em", fontVariantNumeric: "tabular-nums" }}>
              {money(reconciliation.confirmed_payable_amount, reconciliation.currency)}
            </Typography>
            <Typography sx={{ mt: 1.25, color: "#BAC8D0", maxWidth: 710 }}>
              This is the amount supported by the approved contract rules and the evidence currently available. Needs-review dollars stay outside both payable and dispute totals.
            </Typography>
          </Box>
          <Box sx={{ p: 2.25, borderRadius: 2, bgcolor: disputeAmount > 0 ? "#2E2221" : "#1A2C30", border: "1px solid", borderColor: disputeAmount > 0 ? "#74443F" : "#31504B" }}>
            <Typography variant="caption" sx={{ color: disputeAmount > 0 ? "#E3AAA4" : "#A8CFBF" }}>Charges identified for dispute</Typography>
            <Typography variant="h4" sx={{ mt: 0.45, fontWeight: 760, fontVariantNumeric: "tabular-nums" }}>{money(reconciliation.recommended_deduction, reconciliation.currency)}</Typography>
            <Typography variant="body2" sx={{ mt: 0.4, color: "#CBD5E1" }}>{reconciliation.identified_dispute_percent ?? "0.0"}% of invoice value · {reconciliation.disputed_outcomes ?? 0} line(s)</Typography>
          </Box>
        </Box>
      </Box>
      <Box sx={(theme) => ({ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" }, bgcolor: theme.palette.mode === "dark" ? "#17212A" : "#FFFFFF" })}>
        {[
          ["Vendor billed", money(reconciliation.submitted_amount, reconciliation.currency), `${reconciliation.claimed_outcomes ?? 0} claimed outcomes`],
          ["Charges identified for dispute", money(reconciliation.recommended_deduction, reconciliation.currency), `${reconciliation.disputed_outcomes ?? 0} contract-backed disputes`],
          ["Needs review", money(reconciliation.needs_review_amount, reconciliation.currency), reviewAmount > 0 ? `${reconciliation.needs_review_outcomes ?? 0} unresolved line(s)` : "No unresolved dollars"],
        ].map(([label, value, help], index) => (
          <Box key={label} sx={{ p: 2.5, borderRight: { sm: index < 2 ? 1 : 0 }, borderBottom: { xs: index < 2 ? 1 : 0, sm: 0 }, borderColor: "divider" }}>
            <Typography variant="caption" color="text.secondary" fontWeight={700}>{label}</Typography>
            <Typography variant="h5" fontWeight={730} sx={{ mt: 0.25, fontVariantNumeric: "tabular-nums" }}>{value}</Typography>
            <Typography variant="caption" color="text.secondary">{help}</Typography>
          </Box>
        ))}
      </Box>
      <Box sx={(theme) => ({ px: 2.5, py: 2.1, bgcolor: theme.palette.mode === "dark" ? "#17212A" : "#F7F7FA", borderTop: 1, borderColor: "divider" })}>
        <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, mb: 0.9 }}>
          <Typography variant="caption" color="text.secondary" fontWeight={750}>Disposition of billed amount</Typography>
          <Typography variant="caption" color="text.secondary">Payable · Disputed · Needs review</Typography>
        </Box>
        <Box sx={{ display: "flex", height: 10, borderRadius: 999, overflow: "hidden", bgcolor: "action.hover", border: 1, borderColor: "divider" }} aria-label="Disposition of billed amount">
          {payableShare > 0 && <Box sx={{ width: `${payableShare}%`, bgcolor: "success.main" }} title={`Verified payable ${payableShare.toFixed(1)}%`} />}
          {disputeShare > 0 && <Box sx={{ width: `${disputeShare}%`, bgcolor: "error.main" }} title={`Disputed ${disputeShare.toFixed(1)}%`} />}
          {reviewShare > 0 && <Box sx={{ width: `${reviewShare}%`, bgcolor: "warning.main" }} title={`Needs review ${reviewShare.toFixed(1)}%`} />}
        </Box>
      </Box>
      <Box sx={(theme) => ({ px: 2.5, py: 1.75, bgcolor: reviewAmount > 0 ? (theme.palette.mode === "dark" ? "#322A18" : "#FFF7E8") : (theme.palette.mode === "dark" ? "#153127" : "#EAF8F2"), borderTop: 1, borderColor: "divider" })}>
        <Typography variant="body2" fontWeight={650}>
          {reviewAmount > 0
            ? `${money(reviewAmount, reconciliation.currency)} remains protected from an unsupported decision until its evidence gap is resolved.`
            : "Every invoice line has a contract-backed deterministic decision."}
        </Typography>
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
  const [reviewed, setReviewed] = useState(false);
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
    setReviewed(false);
  }

  async function approve() {
    const id = latestCandidateId || candidate?.id;
    if (!id) throw new Error("Analyze the agreement first.");
    if (!reviewed) throw new Error("Confirm that you reviewed the proposed contract rules against the source agreement.");
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
                <RuleReview agreement={agreement} financeView={financeView} />
                {!approved && (
                  <Stack spacing={1.5}>
                    <FormControlLabel control={<Checkbox checked={reviewed} onChange={(e) => setReviewed(e.target.checked)} />} label="I reviewed these contract rules against the source agreement and approve them for invoice verification." />
                    <Button variant="contained" disabled={!reviewed || !candidateAssurance?.hard_gate_passed} sx={{ alignSelf: "flex-start" }} onClick={() => void act("Approving contract rules", approve, "Approved contract rules are now immutable and active for invoice verification.")}>Approve contract rules</Button>
                  </Stack>
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

function RuleReview({ agreement, financeView }: { agreement?: AgreementIRView; financeView?: FinanceView }) {
  if (!agreement) return <Typography color="text.secondary">Contract rule details are unavailable.</Typography>;
  const rules = financeView?.contract_rules ?? [];
  const pricing = financeView?.pricing_terms ?? [];
  if (rules.length) {
    return (
      <Stack spacing={2}>
        <Typography variant="h6" fontWeight={750}>Did Evidue understand the agreement correctly?</Typography>
        <Typography color="text.secondary">Review each proposed payment rule against the original language. Finance-facing descriptions below are rendered from the same structured rule that the deterministic engine will execute.</Typography>
        {rules.map((rule) => (
          <Paper
            key={rule.id}
            variant="outlined"
            sx={(theme) => ({
              p: 2.25,
              borderRadius: 2,
              bgcolor: theme.palette.mode === "dark" ? "#18242D" : "#F9FBFC",
              borderLeft: "4px solid",
              borderLeftColor: rule.consequence === "disputed" ? "error.main" : rule.consequence === "needs_review" ? "warning.main" : "success.main",
            })}
          >
            <Stack spacing={1.25}>
              <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", alignItems: "center" }}>
                <Chip size="small" color={rule.consequence === "disputed" ? "error" : rule.consequence === "needs_review" ? "warning" : "success"} label={rule.rule_type} />
                <Chip size="small" variant="outlined" label={rule.verification_method} />
              </Box>
              <Typography variant="h6" fontWeight={760}>{rule.description}</Typography>
              {rule.evidence_needed.length > 0 && <Typography variant="body2"><strong>Evidence needed:</strong> {rule.evidence_needed.join(" · ")}</Typography>}
              <Box>
                <Typography variant="caption" fontWeight={850} color="text.secondary">SOURCE AGREEMENT</Typography>
                {rule.source_clauses.map((clause) => (
                  <Paper key={clause.id} variant="outlined" sx={{ p: 1.5, mt: 0.75, bgcolor: "action.hover" }}>
                    <Typography variant="caption" color="text.secondary">{clause.document_id}</Typography>
                    <Typography variant="body2" sx={{ mt: 0.25 }}>{clause.text}</Typography>
                  </Paper>
                ))}
              </Box>
              <Typography variant="caption" color="text.secondary">Technical rule ID: {rule.id}</Typography>
            </Stack>
          </Paper>
        ))}
        {pricing.length > 0 && (
          <Box>
            <Typography variant="h6" fontWeight={750} gutterBottom>Pricing terms</Typography>
            {pricing.map((term) => (
              <Paper key={term.id} variant="outlined" sx={(theme) => ({ p: 2, mb: 1, bgcolor: theme.palette.mode === "dark" ? "#1B2040" : "#EEF6FA", borderLeft: "4px solid", borderLeftColor: "primary.main" })}>
                <Typography fontWeight={730}>{term.description}</Typography>
                {term.source_clauses.map((clause) => <Typography key={clause.id} variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>“{clause.text}”</Typography>)}
              </Paper>
            ))}
          </Box>
        )}
        {agreement.diagnostics?.map((diag) => <Alert key={`${diag.code}-${diag.message}`} severity={diag.severity === "blocking" ? "error" : diag.severity === "warning" ? "warning" : "info"}>{diag.message}</Alert>)}
      </Stack>
    );
  }

  const normsByClause = new Map<string, AgreementIRView["norms"]>();
  agreement.norms.forEach((norm) => norm.source_clause_ids.forEach((id) => normsByClause.set(id, [...(normsByClause.get(id) ?? []), norm])));
  return (
    <Stack spacing={1.5}>
      <Alert severity="warning">Finance-language rule rendering is unavailable for this candidate. Review the source mapping carefully before approval.</Alert>
      {agreement.clauses.filter((item) => item.material).map((clause) => (
        <Paper key={clause.id} variant="outlined" sx={{ p: 2 }}>
          <Typography variant="body2" fontWeight={700}>{clause.text}</Typography>
          {(normsByClause.get(clause.id) ?? []).map((norm) => <Typography key={norm.id} variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>{norm.id} · {readable(norm.consequence)} · {readable(norm.automation_class)}</Typography>)}
        </Paper>
      ))}
    </Stack>
  );
}

function InvoiceWorkspace({ contract, status, config, act, refresh }: { contract: PilotContract | null; status: PilotStatus | null; config: WorkspaceConfig | null; act: (label: string, action: () => Promise<void>, success?: string) => Promise<void>; refresh: () => Promise<void> }) {
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
    await pilotApi.uploadInvoice({ file, contractId: contract.id, invoiceId, periodStart: contract.period_start, periodEnd: contract.period_end, columnMapping: mapping });
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

  const planItems = verificationPlan?.plan.items ?? [];
  const ready = planItems.filter((item) => item.status === "ready").length;
  const requirements = airVersion?.finance_view?.evidence_needed ?? [];
  const externalRequirements = requirements.length || airVersion?.agreement_ir?.proof_requirements?.length || 0;
  const evidenceComplete = Boolean(status?.active_invoice_id && (externalRequirements === 0 || (planItems.length > 0 && ready === planItems.length)));
  const planById = new Map(planItems.map((item) => [item.proof_requirement_id, item]));

  return (
    <Box id="evidence">
      <Surface title="Evidence needed by the contract" eyebrow="03 · Evidence" complete={evidenceComplete}>
        {!status?.active_invoice_id ? <Alert severity="info">Import an invoice first.</Alert> : externalRequirements === 0 ? (
          <Alert severity="success">These approved contract rules do not require external customer-system evidence. Continue to reconciliation.</Alert>
        ) : (
          <Stack spacing={2.5}>
            <Typography color="text.secondary">Evidue derives this checklist from the approved contract rules. Missing evidence never becomes an automatic deduction or approval; affected claims remain in Needs review.</Typography>
            {requirements.length > 0 && (
              <Stack spacing={1.25}>
                {requirements.map((item) => {
                  const plan = planById.get(item.id);
                  const state = plan?.status ?? "missing";
                  return (
                    <Paper
                      key={item.id}
                      variant="outlined"
                      sx={(theme) => ({
                        p: 2,
                        borderRadius: 2,
                        bgcolor: state === "ready"
                          ? (theme.palette.mode === "dark" ? "#153127" : "#EEF8F3")
                          : state === "partial"
                            ? (theme.palette.mode === "dark" ? "#352B18" : "#FBF5E8")
                            : (theme.palette.mode === "dark" ? "#171E2A" : "#F7F7FA"),
                        borderLeft: "4px solid",
                        borderLeftColor: state === "ready" ? "success.main" : state === "partial" ? "warning.main" : "divider",
                      })}
                    >
                      <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "flex-start" }}>
                        <Box sx={{ flex: 1 }}>
                          <Stack direction="row" spacing={1} alignItems="center" sx={{ flexWrap: "wrap" }}>
                            <Chip size="small" color={state === "ready" ? "success" : state === "partial" ? "warning" : "default"} label={state === "ready" ? "Ready" : state === "partial" ? "Partial" : "Needed"} />
                            <Typography fontWeight={760}>{item.description}</Typography>
                          </Stack>
                          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}><strong>Required by:</strong> {item.rule_description}</Typography>
                          <Typography variant="body2" sx={{ mt: 0.75 }}><strong>Typical sources:</strong> {evidenceSourceExamples(item, config).join(", ")}</Typography>
                          {plan?.rationale && <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.75 }}>{plan.rationale}</Typography>}
                          <Typography variant="caption" display="block" color="text.secondary">If missing: {item.missing_evidence_effect || "affected claims remain in Needs review"}</Typography>
                        </Box>
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
    if (!status?.active_invoice_id) return;
    setReviewItems((await pilotApi.unmatched(status.active_invoice_id)).items);
  }
  async function choose(item: ReviewItem) {
    if (!status?.active_invoice_id || !item.event_id) return;
    const next = (await pilotApi.candidates(status.active_invoice_id, item.event_id)).candidates;
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
    <Box id="decision">
      <Surface title="Reconciliation and exception review" eyebrow="04 · Decision" complete={Boolean(reconciliation)}>
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
                {selected && <Paper variant="outlined" sx={{ p: 2 }}><Stack spacing={2}><Typography fontWeight={750}>Confirm evidence → invoice line</Typography><TextField select label="Invoice line" value={claimId} onChange={(e) => setClaimId(e.target.value)}>{candidates.map((candidate) => <MenuItem key={candidate.claim_id} value={candidate.claim_id}>{String(candidate.outcome_id ?? candidate.claim_id)} · {String(candidate.reason ?? "candidate")}</MenuItem>)}</TextField><TextField label="Why this match is correct" value={rationale} onChange={(e) => setRationale(e.target.value)} /><Button variant="contained" onClick={() => void act("Recording the confirmed evidence match", confirm, "Manual identity decision recorded in the audit trail.")}>Confirm match</Button></Stack></Paper>}
              </>
            )}
            {!reconciliation && <Button variant="contained" size="large" sx={{ alignSelf: "flex-start" }} disabled={(status.suggested_matches ?? 0) + status.unresolved_events > 0} onClick={() => void act("Matching claims to the approved rules and evidence", reconcile, "Reconciliation completed from the approved contract version.")}>Run reconciliation</Button>}
            {reconciliation && (
              <>
                {reconciliationDelta && <ReconciliationDeltaView delta={reconciliationDelta} currency={reconciliation.currency} />}
                <Determinations rows={rows} currency={reconciliation.currency} />
                {needsReview.length > 0 && <Alert severity="warning">Needs-review lines are deliberately excluded from both payable and disputed totals. Each line below explains what evidence or action would resolve it.</Alert>}
                <Button variant="outlined" sx={{ alignSelf: "flex-start" }} onClick={() => void act("Rerunning reconciliation with the latest evidence", reconcile, "A new append-only reconciliation run was created.")}>Rerun after evidence changes</Button>
              </>
            )}
          </Stack>
        )}
      </Surface>
    </Box>
  );
}

function ExportWorkspace({ reconciliation, act }: { reconciliation: Reconciliation | null; act: (label: string, action: () => Promise<void>, success?: string) => Promise<void> }) {
  const [advanced, setAdvanced] = useState(false);
  if (!reconciliation) {
    return (
      <Box id="export">
        <Surface title="Finance-ready outputs" eyebrow="05 · Send & export" complete={false}>
          <Typography color="text.secondary">Complete reconciliation first. Evidue will then generate the files finance needs internally and the package you can send to the vendor.</Typography>
        </Surface>
      </Box>
    );
  }
  const id = reconciliation.reconciliation_id;
  async function copyEmail() {
    const text = await pilotApi.vendorEmail(id);
    await navigator.clipboard.writeText(text);
  }
  return (
    <Box id="export">
      <Surface title="Move the decision into action" eyebrow="05 · Send & export" complete>
        <Stack spacing={2.5}>
          <Paper sx={{ bgcolor: "#0F172A", color: "#F8FAFC", p: { xs: 2.5, md: 3 }, borderRadius: 2, borderColor: "#294050" }}>
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr auto" }, gap: 2.5, alignItems: "center" }}>
              <Box>
                <Typography variant="overline" sx={{ color: "#A5B4FC" }}>Decision package ready</Typography>
                <Typography variant="h4" sx={{ mt: 0.35 }}>Finance can act on {money(reconciliation.confirmed_payable_amount, reconciliation.currency)}.</Typography>
                <Typography sx={{ mt: 0.9, color: "#CBD5E1", maxWidth: 720 }}>
                  The corrected invoice and vendor dispute report are generated from the exact persisted reconciliation run, including the approved rule version and evidence provenance.
                </Typography>
              </Box>
              <Box sx={{ minWidth: 220 }}>
                <Typography variant="caption" sx={{ color: "#DFA39D" }}>Charges identified for dispute</Typography>
                <Typography variant="h5" sx={{ mt: 0.25, fontVariantNumeric: "tabular-nums" }}>{money(reconciliation.recommended_deduction, reconciliation.currency)}</Typography>
                <Typography variant="caption" sx={{ color: "#94A3B8" }}>{reconciliation.disputed_outcomes ?? 0} disputed line(s)</Typography>
              </Box>
            </Box>
          </Paper>

          <Box>
            <Typography variant="subtitle1" fontWeight={800}>Recommended handoff</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.35 }}>Start with the two artifacts a finance operator is most likely to use. Technical exports stay available below.</Typography>
          </Box>

          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 1.5 }}>
            <Paper variant="outlined" sx={(theme) => ({ p: 2.25, bgcolor: theme.palette.mode === "dark" ? "#153127" : "#EEF8F3", borderColor: "success.main" })}>
              <Typography variant="overline" color="success.main">For Accounts Payable</Typography>
              <Typography variant="h6">Corrected invoice</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 1.75 }}>A line-level CSV with the contract-backed payable disposition for your AP workflow.</Typography>
              <Button variant="contained" onClick={() => void act("Preparing corrected invoice", () => pilotApi.downloadExport(id, "corrected-invoice.csv"))}>Corrected invoice CSV</Button>
            </Paper>
            <Paper variant="outlined" sx={(theme) => ({ p: 2.25, bgcolor: theme.palette.mode === "dark" ? "#382025" : "#FCF2F1", borderColor: "error.main" })}>
              <Typography variant="overline" color="error.main">For the vendor</Typography>
              <Typography variant="h6">Dispute package</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 1.75 }}>A readable explanation of disputed charges with contract and evidence references.</Typography>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                <Button variant="contained" color="secondary" onClick={() => void act("Preparing vendor dispute report", () => pilotApi.downloadExport(id, "vendor-dispute.html"))}>Vendor dispute report</Button>
                <Button variant="outlined" onClick={() => void act("Copying vendor email", copyEmail, "Vendor dispute email copied to your clipboard.")}>Copy vendor email</Button>
              </Stack>
            </Paper>
          </Box>

          <Button variant="outlined" sx={{ alignSelf: "flex-start" }} onClick={() => void act("Preparing disputed line items", () => pilotApi.downloadExport(id, "disputes.csv"))}>Disputed lines CSV</Button>

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
        <Paper variant="outlined" sx={{ p: 2 }}><Typography fontWeight={750}>Approved contract rules (AIR)</Typography><Typography variant="body2" fontFamily="monospace">{airVersion?.id ?? "—"}</Typography><Typography variant="caption">Payload {airVersion?.payload_hash ?? "—"}</Typography></Paper>
        <Paper variant="outlined" sx={{ p: 2 }}><Typography fontWeight={750}>Rule verification</Typography><Chip size="small" color={assurance?.hard_gate_passed ? "success" : "default"} label={assurance?.hard_gate_passed ? "Hard gate passed" : "Not available"} /><Typography variant="caption" display="block" sx={{ mt: 1 }}>{assurance?.checks?.filter((item) => item.status === "pass").length ?? 0}/{assurance?.checks?.length ?? 0} checks passed</Typography></Paper>
      </Box>
      {assurance?.checks?.map((check) => <Alert key={check.id} severity={check.status === "pass" ? "success" : check.hard_gate ? "error" : "warning"}><strong>{readable(check.id)}</strong> — {check.summary}{check.details.length ? ` (${check.details.join("; ")})` : ""}</Alert>)}
      {plan && <Box><Typography variant="h6" fontWeight={750} gutterBottom>Evidence verification plan (technical)</Typography>{plan.plan.items.map((item) => <Paper key={item.proof_requirement_id} variant="outlined" sx={{ p: 1.5, mb: 1 }}><Stack direction="row" spacing={1} alignItems="center"><Chip size="small" color={item.status === "ready" ? "success" : item.status === "partial" ? "warning" : "error"} label={item.status} /><Typography variant="body2" fontFamily="monospace">{item.proof_requirement_id}</Typography></Stack><Typography variant="caption">{item.rationale}</Typography></Paper>)}</Box>}
      {facts.length > 0 && <Box><Typography variant="h6" fontWeight={750} gutterBottom>Derived deterministic facts</Typography><TableContainer sx={{ border: 1, borderColor: "divider", borderRadius: 2 }}><Table size="small"><TableHead><TableRow><TableCell>Fact</TableCell><TableCell>Truth</TableCell><TableCell>Authority</TableCell><TableCell>Input hash</TableCell></TableRow></TableHead><TableBody>{facts.slice(0, 100).map((fact) => <TableRow key={fact.id}><TableCell>{fact.fact_type}</TableCell><TableCell>{fact.truth}</TableCell><TableCell>{readable(fact.authority)}</TableCell><TableCell><Typography variant="caption" fontFamily="monospace">{fact.input_hash.slice(0, 18)}…</Typography></TableCell></TableRow>)}</TableBody></Table></TableContainer></Box>}
      <Box><Typography variant="h6" fontWeight={750} gutterBottom>Workspace audit history</Typography>{audit.length ? audit.map((event) => <Box key={event.id} sx={{ py: 1, borderBottom: 1, borderColor: "divider", display: "grid", gridTemplateColumns: { xs: "1fr", md: "180px 1fr 180px" }, gap: 1 }}><Typography variant="caption">{new Date(event.occurred_at).toLocaleString()}</Typography><Typography variant="body2"><strong>{readable(event.action)}</strong> · {event.object_type}</Typography><Typography variant="caption" fontFamily="monospace">{event.object_id?.slice(0, 20) ?? "workspace"}</Typography></Box>) : <Typography color="text.secondary">Open Advanced after activity to load the audit trail.</Typography>}</Box>
    </Stack>
  );
}
