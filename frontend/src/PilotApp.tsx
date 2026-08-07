import {
  Alert,
  AppBar,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  CircularProgress,
  Collapse,
  Container,
  Divider,
  FormControlLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Stack,
  Step,
  StepLabel,
  Stepper,
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
import {
  AIRVersion,
  AgreementIRView,
  AuditEvent,
  clearPilotToken,
  CompilerAssurance,
  Determination,
  DerivedFact,
  InvoicePreview,
  loadPilotToken,
  MatchCandidate,
  PilotApiError,
  PilotContract,
  pilotApi,
  PilotStatus,
  Reconciliation,
  ReviewItem,
  savePilotToken,
  VerificationPlanEnvelope,
} from "./pilotApi";

const workflowSteps = ["Contract", "Rules", "Invoice", "Evidence", "Reconcile", "Export"];
const requiredInvoiceFields = ["outcome_id", "customer_id", "intent", "closed_at", "billed_amount"];

function money(value: string | number | undefined): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value ?? 0));
}

function errorText(error: unknown): string {
  if (error instanceof PilotApiError || error instanceof Error) return error.message;
  return "An unexpected error occurred.";
}

function readable(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
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
    <Card variant="outlined" sx={{ borderRadius: 3, overflow: "visible" }}>
      <Box sx={{ px: { xs: 2, md: 3 }, py: 2.25, display: "flex", gap: 2, justifyContent: "space-between", alignItems: "flex-start" }}>
        <Box>
          <Typography variant="overline" color="primary.main" fontWeight={800}>{eyebrow}</Typography>
          <Typography variant="h5" fontWeight={760}>{title}</Typography>
        </Box>
        <Stack direction="row" spacing={1} alignItems="center">
          {complete !== undefined && <Chip size="small" color={complete ? "success" : "default"} label={complete ? "Ready" : "Not ready"} />}
          {action}
        </Stack>
      </Box>
      <Divider />
      <CardContent sx={{ p: { xs: 2, md: 3 } }}>{children}</CardContent>
    </Card>
  );
}

function Metric({ label, value, help }: { label: string; value: string; help?: string }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography variant="h6" fontWeight={760} noWrap>{value}</Typography>
      {help && <Typography variant="caption" color="text.secondary">{help}</Typography>}
    </Paper>
  );
}

function StatusChip({ status }: { status: Determination["status"] }) {
  return <Chip size="small" color={status === "payable" ? "success" : status === "disputed" ? "error" : "warning"} label={readable(status)} />;
}

function Determinations({ rows }: { rows: Determination[] }) {
  if (!rows.length) return <Typography color="text.secondary">No line decisions yet.</Typography>;
  return (
    <TableContainer sx={{ border: 1, borderColor: "divider", borderRadius: 2 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Outcome</TableCell><TableCell>Decision</TableCell><TableCell align="right">Billed</TableCell><TableCell align="right">Payable</TableCell><TableCell>Why</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.outcome_id} hover>
              <TableCell><Typography fontFamily="monospace" variant="body2">{row.outcome_id}</Typography></TableCell>
              <TableCell><StatusChip status={row.status} /></TableCell>
              <TableCell align="right">{money(row.billed_amount)}</TableCell>
              <TableCell align="right">{money(row.confirmed_payable_amount)}</TableCell>
              <TableCell sx={{ maxWidth: 460 }}>
                <Typography variant="body2">{row.reason}</Typography>
                {row.rule_id && <Typography variant="caption" color="text.secondary">Approved rule: {row.rule_id}</Typography>}
                {row.contract_clauses?.map((clause) => (
                  <Paper key={clause.id} variant="outlined" sx={{ p: 1.25, mt: 1, bgcolor: "action.hover" }}>
                    <Typography variant="caption" fontWeight={800}>{clause.id} · Contract source</Typography>
                    <Typography variant="body2" sx={{ mt: 0.5 }}>{clause.text}</Typography>
                  </Paper>
                ))}
                {!!row.evidence?.length && (
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="caption" fontWeight={800}>Evidence timeline</Typography>
                    {row.evidence.map((event) => (
                      <Typography key={`${event.event_id}-${event.purpose}`} variant="caption" display="block" color="text.secondary">
                        {new Date(event.timestamp).toLocaleString()} · {event.source_system} · {readable(event.event_type)} · {event.source_record_id}
                      </Typography>
                    ))}
                  </Box>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export default function PilotApp() {
  const [token, setToken] = useState(loadPilotToken());
  const [tokenDraft, setTokenDraft] = useState(loadPilotToken());
  const [status, setStatus] = useState<PilotStatus | null>(null);
  const [contract, setContract] = useState<PilotContract | null>(null);
  const [airVersion, setAirVersion] = useState<(AIRVersion & { agreement_ir?: AgreementIRView }) | null>(null);
  const [assurance, setAssurance] = useState<CompilerAssurance | null>(null);
  const [reconciliation, setReconciliation] = useState<Reconciliation | null>(null);
  const [verificationPlan, setVerificationPlan] = useState<VerificationPlanEnvelope | null>(null);
  const [facts, setFacts] = useState<DerivedFact[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [advanced, setAdvanced] = useState(false);

  const refresh = useCallback(async () => {
    if (!loadPilotToken()) return;
    setBusy("Loading workspace");
    setError("");
    try {
      const nextStatus = await pilotApi.status();
      setStatus(nextStatus);
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
        setReconciliation(await pilotApi.reconciliation(nextStatus.latest_reconciliation_id));
      } else {
        setReconciliation(null);
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
    clearPilotToken(); setToken(""); setStatus(null); setContract(null); setAirVersion(null); setReconciliation(null); setError("");
  }

  async function resetWorkspace() {
    if (!window.confirm("Reset this workspace? This deletes the current contract, invoice, evidence, reconciliations, and audit history for this workspace only.")) return;
    await act(
      "Resetting workspace",
      async () => { await pilotApi.clear(); await refresh(); },
      "Workspace reset. You can start a new reconciliation.",
    );
  }

  const activeStep = useMemo(() => {
    if (!contract) return 0;
    if (!status?.contract_approved) return 1;
    if (!status.active_invoice_id) return 2;
    if (!status.events) return 3;
    if (!reconciliation) return 4;
    return 5;
  }, [contract, reconciliation, status]);

  if (!token) {
    return (
      <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", px: 2, bgcolor: "background.default" }}>
        <Card variant="outlined" sx={{ maxWidth: 560, width: "100%", borderRadius: 4 }}>
          <CardContent sx={{ p: { xs: 3, md: 5 } }}>
            <Typography variant="overline" color="primary.main" fontWeight={800}>Evidue</Typography>
            <Typography variant="h3" fontWeight={780} sx={{ mt: 1 }}>Open your reconciliation workspace</Typography>
            <Typography color="text.secondary" sx={{ mt: 2 }}>
              Verify outcome-priced vendor invoices against the agreement and your own operational evidence, then export what finance should actually pay.
            </Typography>
            <Alert severity="info" sx={{ mt: 3 }}>
              AI interprets the agreement and proposes rules. You approve a version. The approved deterministic rule graph—not the AI—decides invoice lines.
            </Alert>
            {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
            <Box component="form" onSubmit={authenticate} sx={{ mt: 3 }}>
              <Stack spacing={2}>
                <TextField label="Workspace access key" type="password" value={tokenDraft} onChange={(event) => setTokenDraft(event.target.value)} autoFocus fullWidth helperText="Provided by your Evidue deployment administrator." />
                <Button type="submit" variant="contained" size="large">Open workspace</Button>
              </Stack>
            </Box>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 2 }}>
              The key is stored in sessionStorage only and is never placed in a URL.
            </Typography>
          </CardContent>
        </Card>
      </Box>
    );
  }

  const emptyWorkspace = Boolean(status && !status.active_contract_id);

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Toolbar sx={{ gap: 2 }}>
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="overline" color="primary.main" fontWeight={900}>Evidue</Typography>
            <Typography fontWeight={760}>Invoice reconciliation</Typography>
          </Box>
          {status?.workspace_id && <Chip size="small" label={`Workspace · ${status.workspace_id}`} />}
          <Button onClick={() => void refresh()} disabled={Boolean(busy)}>Refresh</Button>
          {status?.active_contract_id && <Button color="error" onClick={() => void resetWorkspace()} disabled={Boolean(busy)}>Reset workspace</Button>}
          <Button color="inherit" onClick={signOut}>Sign out</Button>
        </Toolbar>
      </AppBar>

      {busy && <LinearProgress />}
      <Container maxWidth="xl" sx={{ py: 4 }}>
        {notice && <Alert severity="success" onClose={() => setNotice("")} sx={{ mb: 2 }}>{notice}</Alert>}
        {error && <Alert severity="error" onClose={() => setError("")} sx={{ mb: 2 }}>{error}</Alert>}

        {emptyWorkspace && (
          <Paper variant="outlined" sx={{ p: { xs: 3, md: 5 }, borderRadius: 4, mb: 4 }}>
            <Typography variant="overline" color="primary.main" fontWeight={800}>First reconciliation</Typography>
            <Typography variant="h3" fontWeight={780} sx={{ maxWidth: 800 }}>Start with your agreement, or explore a complete sample first.</Typography>
            <Typography color="text.secondary" sx={{ mt: 2, maxWidth: 760 }}>
              The sample creates an approved contract interpretation, three invoice lines, customer evidence, and one payable, one disputed, and one needs-review result. You can reset it afterward.
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mt: 3 }}>
              <Button variant="contained" size="large" disabled={Boolean(busy)} onClick={() => void act("Creating sample workspace", async () => { await pilotApi.seedSample(); await refresh(); }, "Sample workspace is ready.")}>Try sample workspace</Button>
              <Button variant="outlined" size="large" href="#contract">Use my own data</Button>
            </Stack>
          </Paper>
        )}

        <Stepper activeStep={activeStep} alternativeLabel sx={{ mb: 4, display: { xs: "none", md: "flex" } }}>
          {workflowSteps.map((step) => <Step key={step}><StepLabel>{step}</StepLabel></Step>)}
        </Stepper>

        <Stack spacing={3}>
          <Overview status={status} reconciliation={reconciliation} />
          <ContractWorkspace contract={contract} airVersion={airVersion} assurance={assurance} status={status} act={act} refresh={refresh} />
          <InvoiceWorkspace contract={contract} status={status} act={act} refresh={refresh} />
          <EvidenceWorkspace status={status} airVersion={airVersion} verificationPlan={verificationPlan} act={act} refresh={refresh} />
          <DecisionWorkspace
            status={status}
            reconciliation={reconciliation}
            requiresExternalEvidence={Boolean(airVersion?.agreement_ir?.proof_requirements?.length)}
            act={act}
            refresh={refresh}
          />
          <ExportWorkspace reconciliation={reconciliation} act={act} />

          <Surface
            title="Auditability and runtime details"
            eyebrow="Advanced"
            action={<Button size="small" onClick={() => { setAdvanced((value) => !value); if (!advanced) void act("Loading audit history", async () => setAuditEvents((await pilotApi.auditLog()).events)); }}>{advanced ? "Hide" : "Show"}</Button>}
          >
            <Collapse in={advanced} unmountOnExit>
              <AdvancedDetails airVersion={airVersion} assurance={assurance} plan={verificationPlan} facts={facts} audit={auditEvents} />
            </Collapse>
            {!advanced && <Typography color="text.secondary">Compiler assurance, evidence-plan details, derived facts, immutable IDs, and workspace audit history are available here without cluttering the finance workflow.</Typography>}
          </Surface>
        </Stack>
      </Container>
    </Box>
  );
}

function Overview({ status, reconciliation }: { status: PilotStatus | null; reconciliation: Reconciliation | null }) {
  return (
    <Surface title="What finance should pay" eyebrow="Overview" complete={Boolean(reconciliation)}>
      {reconciliation ? (
        <>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" }, gap: 2 }}>
            <Metric label="Vendor billed" value={money(reconciliation.submitted_amount)} help={`${reconciliation.claimed_outcomes ?? 0} outcomes`} />
            <Metric label="Verified payable" value={money(reconciliation.confirmed_payable_amount)} help={`${reconciliation.payable_outcomes ?? 0} payable`} />
            <Metric label="Recommended deduction" value={money(reconciliation.recommended_deduction)} help={`${reconciliation.disputed_outcomes ?? 0} disputed`} />
            <Metric label="Needs review" value={money(reconciliation.needs_review_amount)} help={`${reconciliation.needs_review_outcomes ?? 0} unresolved`} />
          </Box>
          <Alert severity={(Number(reconciliation.needs_review_amount) || 0) > 0 ? "warning" : "success"} sx={{ mt: 2 }}>
            {Number(reconciliation.needs_review_amount) > 0
              ? "There are invoice lines that Evidue will not deduct or approve until the evidence is sufficient. Review those lines below."
              : "Every invoice line has a deterministic contract-backed decision."}
          </Alert>
        </>
      ) : (
        <Stack spacing={1}>
          <Typography color="text.secondary">Complete the steps below to produce a corrected payable amount.</Typography>
          {status && <Typography variant="body2">Current data: {status.claims} invoice lines · {status.events} evidence events · {status.accepted_match_rate}% accepted evidence matches.</Typography>}
        </Stack>
      )}
    </Surface>
  );
}

function ContractWorkspace({
  contract,
  airVersion,
  assurance,
  status,
  act,
  refresh,
}: {
  contract: PilotContract | null;
  airVersion: (AIRVersion & { agreement_ir?: AgreementIRView }) | null;
  assurance: CompilerAssurance | null;
  status: PilotStatus | null;
  act: (label: string, action: () => Promise<void>, success?: string) => Promise<void>;
  refresh: () => Promise<void>;
}) {
  const [customer, setCustomer] = useState("My company");
  const [vendor, setVendor] = useState("");
  const [periodStart, setPeriodStart] = useState("2026-06-01T00:00:00Z");
  const [periodEnd, setPeriodEnd] = useState("2026-07-01T00:00:00Z");
  const [price, setPrice] = useState("0.00");
  const [contractFile, setContractFile] = useState<File | null>(null);
  const [pasted, setPasted] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [latestCandidateId, setLatestCandidateId] = useState("");
  const [latestCandidate, setLatestCandidate] = useState<(AIRVersion & { agreement_ir?: AgreementIRView }) | null>(null);
  const [latestAssurance, setLatestAssurance] = useState<CompilerAssurance | null>(null);

  const candidate = latestCandidate ?? airVersion;
  const candidateAssurance = latestAssurance ?? assurance;
  const agreement = candidate?.agreement_ir;
  const approved = Boolean(status?.contract_approved && airVersion?.approved_at);

  async function upload() {
    if (!vendor.trim()) throw new Error("Enter the vendor name.");
    if (!contractFile && pasted.trim().length < 50) throw new Error("Choose a contract file or paste at least 50 characters of contract language.");
    if (contractFile) {
      await pilotApi.uploadContract({ file: contractFile, customer, vendor, periodStart, periodEnd, pricePerOutcome: price });
    } else {
      await pilotApi.createContractFromText({ customer, vendor, periodStart, periodEnd, pricePerOutcome: price, sourceText: pasted });
    }
    await refresh();
  }

  async function analyze() {
    if (!contract) throw new Error("Add a contract first.");
    const result = await pilotApi.compileNative(contract.id, "auto");
    const [version, nextAssurance] = await Promise.all([pilotApi.getAIRVersion(result.air_version_id), pilotApi.getAIRAssurance(result.air_version_id)]);
    setLatestCandidateId(result.air_version_id);
    setLatestCandidate(version);
    setLatestAssurance(nextAssurance);
    setReviewed(false);
  }

  async function approve() {
    const id = latestCandidateId || candidate?.id;
    if (!id) throw new Error("Analyze the contract first.");
    if (!reviewed) throw new Error("Confirm that you reviewed the source clauses and proposed rules before approval.");
    await pilotApi.approveAIR(id);
    setLatestCandidate(null); setLatestCandidateId(""); setLatestAssurance(null);
    await refresh();
  }

  return (
    <Box id="contract">
      <Surface title="Agreement and approved rules" eyebrow="01 · Contract" complete={approved}>
        {!contract ? (
          <Stack spacing={2.25}>
            <Alert severity="info">Upload PDF, DOCX, TXT, or Markdown, or paste the agreement language. Evidue preserves a source hash and exact clause provenance.</Alert>
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
              <TextField label="Your company" value={customer} onChange={(e) => setCustomer(e.target.value)} />
              <TextField label="Vendor" value={vendor} onChange={(e) => setVendor(e.target.value)} />
              <TextField label="Agreement period start" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
              <TextField label="Agreement period end (exclusive)" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
              <TextField label="Fallback unit price (optional)" value={price} onChange={(e) => setPrice(e.target.value)} helperText="The approved contract interpretation remains the source of truth." />
            </Box>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
              <Button component="label" variant="outlined">Choose agreement file<input hidden type="file" accept=".pdf,.docx,.txt,.md,text/plain,application/pdf" onChange={(e) => setContractFile(e.target.files?.[0] ?? null)} /></Button>
              <Typography variant="body2" color="text.secondary">{contractFile?.name ?? "No file selected"}</Typography>
            </Stack>
            <Typography variant="overline" color="text.secondary">or paste the agreement</Typography>
            <TextField multiline minRows={6} label="Contract language" value={pasted} onChange={(e) => setPasted(e.target.value)} placeholder="Paste the relevant agreement, order form, or pricing addendum…" />
            <Button variant="contained" size="large" sx={{ alignSelf: "flex-start" }} onClick={() => void act("Saving agreement", upload, "Agreement saved. Analyze it next.")}>Save agreement</Button>
          </Stack>
        ) : (
          <Stack spacing={2.5}>
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" }, gap: 2 }}>
              <Metric label="Customer" value={contract.customer} /><Metric label="Vendor" value={contract.vendor} /><Metric label="Source" value={contract.source_document} /><Metric label="Source fingerprint" value={contract.source_hash.slice(0, 14) + "…"} />
            </Box>
            {!candidate && <Button variant="contained" sx={{ alignSelf: "flex-start" }} onClick={() => void act("Analyzing contract", analyze, "Contract analysis is ready for review.")}>Analyze contract with AI</Button>}
            {candidate && (
              <>
                <Alert severity={candidateAssurance?.hard_gate_passed ? "success" : "error"}>
                  {candidateAssurance?.hard_gate_passed
                    ? "Mechanical compiler assurance passed. Review the actual clauses and deterministic rules below before approval."
                    : "This proposed rule version failed a hard compiler assurance check and cannot be approved."}
                </Alert>
                <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" }, gap: 2 }}>
                  <Metric label="Material clauses" value={String(agreement?.clauses?.filter((item) => item.material).length ?? 0)} />
                  <Metric label="Deterministic norms" value={String(agreement?.norms?.length ?? 0)} />
                  <Metric label="Proof requirements" value={String(agreement?.proof_requirements?.length ?? 0)} />
                  <Metric label="Settlement policies" value={String(agreement?.settlement_policies?.length ?? 0)} />
                </Box>
                <RuleReview agreement={agreement} />
                {!approved && (
                  <Stack spacing={1.5}>
                    <FormControlLabel control={<Checkbox checked={reviewed} onChange={(e) => setReviewed(e.target.checked)} />} label="I reviewed the source clauses and the proposed deterministic interpretation." />
                    <Button variant="contained" disabled={!reviewed || !candidateAssurance?.hard_gate_passed} sx={{ alignSelf: "flex-start" }} onClick={() => void act("Approving rule version", approve, "Approved rule version is now immutable and active.")}>Approve this rule version</Button>
                  </Stack>
                )}
                {approved && <Alert severity="success">Version {airVersion?.version_number} is approved and immutable. Historical reconciliations remain pinned to the exact version used.</Alert>}
              </>
            )}
          </Stack>
        )}
      </Surface>
    </Box>
  );
}

function RuleReview({ agreement }: { agreement?: AgreementIRView }) {
  if (!agreement) return <Typography color="text.secondary">Rule details are unavailable.</Typography>;
  const normsByClause = new Map<string, AgreementIRView["norms"]>();
  agreement.norms.forEach((norm) => norm.source_clause_ids.forEach((id) => normsByClause.set(id, [...(normsByClause.get(id) ?? []), norm])));
  return (
    <Stack spacing={1.5}>
      <Typography variant="h6" fontWeight={750}>Review source-to-rule mapping</Typography>
      {agreement.clauses.filter((item) => item.material).map((clause) => (
        <Paper key={clause.id} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography variant="body2" fontWeight={700}>{clause.text}</Typography>
          <Stack spacing={0.75} sx={{ mt: 1.25 }}>
            {(normsByClause.get(clause.id) ?? []).map((norm) => (
              <Box key={norm.id} sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap" }}>
                <Chip size="small" label={readable(norm.norm_type)} /><Typography variant="body2">{norm.id} → {readable(norm.consequence)}</Typography><Typography variant="caption" color="text.secondary">{readable(norm.automation_class)}</Typography>
              </Box>
            ))}
          </Stack>
        </Paper>
      ))}
      {agreement.diagnostics?.length > 0 && agreement.diagnostics.map((diag) => <Alert key={`${diag.code}-${diag.message}`} severity={diag.severity === "blocking" ? "error" : diag.severity === "warning" ? "warning" : "info"}>{diag.message}</Alert>)}
    </Stack>
  );
}

function InvoiceWorkspace({ contract, status, act, refresh }: { contract: PilotContract | null; status: PilotStatus | null; act: (label: string, action: () => Promise<void>, success?: string) => Promise<void>; refresh: () => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<InvoicePreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>( {} );
  const [invoiceId, setInvoiceId] = useState(`INV-${new Date().toISOString().slice(0, 10)}`);

  async function previewFile(next: File | null) {
    setFile(next); setPreview(null); setMapping({});
    if (!next) return;
    const result = await pilotApi.previewInvoice(next);
    setPreview(result);
    const nextMap: Record<string, string> = {};
    Object.entries(result.auto_mapping).forEach(([key, value]) => { if (value) nextMap[key] = value; });
    setMapping(nextMap);
  }

  const mappingComplete = requiredInvoiceFields.every((field) => Boolean(mapping[field]));

  async function upload() {
    if (!contract || !file) throw new Error("Choose an invoice CSV first.");
    if (!mappingComplete) throw new Error("Map each required invoice field before importing.");
    await pilotApi.uploadInvoice({ file, contractId: contract.id, invoiceId, periodStart: contract.period_start, periodEnd: contract.period_end, columnMapping: mapping });
    await refresh();
  }

  return (
    <Surface title="Vendor invoice" eyebrow="02 · Invoice" complete={Boolean(status?.active_invoice_id)}>
      {!status?.contract_approved ? <Alert severity="info">Approve the contract rules before adding an invoice.</Alert> : status.active_invoice_id ? (
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(3, 1fr)" }, gap: 2 }}>
          <Metric label="Invoice" value={status.active_invoice_id} /><Metric label="Accepted lines" value={String(status.claims)} /><Metric label="Upload status" value="Normalized" />
        </Box>
      ) : (
        <Stack spacing={2}>
          <Alert severity="info">CSV headers do not have to match Evidue. We preview the file and let you confirm column mapping before anything is persisted as an invoice.</Alert>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
            <Button component="label" variant="outlined">Choose invoice CSV<input hidden type="file" accept=".csv,text/csv" onChange={(e) => void act("Inspecting invoice", () => previewFile(e.target.files?.[0] ?? null))} /></Button>
            <Typography variant="body2">{file?.name ?? "No file selected"}</Typography>
          </Stack>
          {preview && (
            <>
              <TextField label="Invoice ID" value={invoiceId} onChange={(e) => setInvoiceId(e.target.value)} sx={{ maxWidth: 420 }} />
              <Typography variant="h6" fontWeight={750}>Confirm the columns</Typography>
              <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
                {requiredInvoiceFields.map((field) => (
                  <TextField key={field} select label={readable(field)} value={mapping[field] ?? ""} onChange={(e) => setMapping((current) => ({ ...current, [field]: e.target.value }))} helperText={mapping[field] ? "Mapped" : "Required"}>
                    {preview.headers.map((header) => <MenuItem key={header} value={header}>{header}</MenuItem>)}
                  </TextField>
                ))}
              </Box>
              <TableContainer sx={{ border: 1, borderColor: "divider", borderRadius: 2, maxHeight: 260 }}><Table size="small"><TableHead><TableRow>{preview.headers.map((header) => <TableCell key={header}>{header}</TableCell>)}</TableRow></TableHead><TableBody>{preview.sample_rows.slice(0, 3).map((row, index) => <TableRow key={index}>{preview.headers.map((header) => <TableCell key={header}>{row[header]}</TableCell>)}</TableRow>)}</TableBody></Table></TableContainer>
              <Button variant="contained" disabled={!mappingComplete} sx={{ alignSelf: "flex-start" }} onClick={() => void act("Importing invoice", upload, "Invoice imported and normalized.")}>Import {file?.name}</Button>
            </>
          )}
        </Stack>
      )}
    </Surface>
  );
}

function EvidenceWorkspace({ status, airVersion, verificationPlan, act, refresh }: { status: PilotStatus | null; airVersion: (AIRVersion & { agreement_ir?: AgreementIRView }) | null; verificationPlan: VerificationPlanEnvelope | null; act: (label: string, action: () => Promise<void>, success?: string) => Promise<void>; refresh: () => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("customer_system");
  const [complete, setComplete] = useState(false);

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
  const externalRequirements = airVersion?.agreement_ir?.proof_requirements?.length ?? 0;
  const evidenceComplete = Boolean(
    status?.active_invoice_id && (externalRequirements === 0 || (status.events && status.accepted_matches)),
  );

  return (
    <Surface title="Customer-side verification evidence" eyebrow="03 · Evidence" complete={evidenceComplete}>
      {!status?.active_invoice_id ? <Alert severity="info">Import an invoice first.</Alert> : externalRequirements === 0 ? (
        <Alert severity="success">This approved rule version has no external evidence requirements. No customer-system export is required; continue to reconciliation.</Alert>
      ) : (
        <Stack spacing={2}>
          {status.events > 0 && (
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" }, gap: 2 }}>
              <Metric label="Evidence events" value={String(status.events)} /><Metric label="Accepted matches" value={String(status.accepted_matches)} /><Metric label="Needs identity review" value={String((status.suggested_matches ?? 0) + status.unresolved_events)} /><Metric label="Proof plan" value={planItems.length ? `${ready}/${planItems.length} ready` : "Not planned"} />
            </Box>
          )}
          <Alert severity="info">Upload CSV, JSON, or JSONL exports from systems such as support, payments, CRM, or product logs. Evidue normalizes records and matches them to invoice outcomes before rules can inspect them.</Alert>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
            <Button component="label" variant="outlined">Choose evidence export<input hidden type="file" accept=".csv,.json,.jsonl,text/csv,application/json,application/x-ndjson" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Button>
            <Typography variant="body2">{file?.name ?? "No file selected"}</Typography>
            <TextField label="Source system" value={source} onChange={(e) => setSource(e.target.value)} size="small" sx={{ minWidth: 220 }} />
          </Stack>
          <FormControlLabel control={<Checkbox checked={complete} onChange={(e) => setComplete(e.target.checked)} />} label="This export completely covers the relevant billing/evidence period." />
          <Typography variant="caption" color="text.secondary">Only a source explicitly marked complete may be used to prove that an event did not occur. Leaving this unchecked is safer for partial exports.</Typography>
          <Button variant="contained" disabled={!file} sx={{ alignSelf: "flex-start" }} onClick={() => void act("Importing and matching evidence", upload, "Evidence imported, matched, and proof coverage recalculated.")}>Import evidence</Button>
          {planItems.length > 0 && ready < planItems.length && <Alert severity="warning">{planItems.length - ready} proof requirement(s) still lack a capability-complete evidence source. Evidue will not silently turn missing evidence into a deduction.</Alert>}
        </Stack>
      )}
    </Surface>
  );
}

function DecisionWorkspace({
  status,
  reconciliation,
  requiresExternalEvidence,
  act,
  refresh,
}: {
  status: PilotStatus | null;
  reconciliation: Reconciliation | null;
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
    <Surface title="Reconciliation and exception review" eyebrow="04 · Decision" complete={Boolean(reconciliation)}>
      {!status?.active_invoice_id ? <Alert severity="info">Import an invoice before reconciling.</Alert> : (
        <Stack spacing={2.5}>
          {!status.events && (
            <Alert severity={requiresExternalEvidence ? "warning" : "success"}>
              {requiresExternalEvidence
                ? "No customer-side evidence has been added. You can still run reconciliation safely; evidence-dependent lines will remain in Needs review rather than becoming deductions."
                : "This approved contract interpretation has no external proof requirements. Reconciliation can run from the invoice claims and approved contract rules alone."}
            </Alert>
          )}
          {((status.suggested_matches ?? 0) + status.unresolved_events > 0) && (
            <>
              <Alert severity="warning">{(status.suggested_matches ?? 0) + status.unresolved_events} evidence record(s) need identity review. Heuristic suggestions never affect money until you confirm them.</Alert>
              <Button variant="outlined" sx={{ alignSelf: "flex-start" }} onClick={() => void act("Loading identity review", loadIdentityReview)}>Review unmatched evidence</Button>
              {reviewItems.map((item) => <Paper key={String(item.event_id)} variant="outlined" sx={{ p: 2 }}><Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}><Box sx={{ flex: 1 }}><Typography fontWeight={700}>{String(item.event_type ?? "Evidence")}</Typography><Typography variant="body2" color="text.secondary">{String(item.match_reason ?? "No authoritative identity match")}</Typography></Box><Button onClick={() => void act("Finding candidate invoice lines", () => choose(item))}>Match manually</Button></Stack></Paper>)}
              {selected && <Paper variant="outlined" sx={{ p: 2 }}><Stack spacing={2}><Typography fontWeight={750}>Confirm evidence → invoice line</Typography><TextField select label="Invoice line" value={claimId} onChange={(e) => setClaimId(e.target.value)}>{candidates.map((candidate) => <MenuItem key={candidate.claim_id} value={candidate.claim_id}>{String(candidate.outcome_id ?? candidate.claim_id)} · {String(candidate.reason ?? "candidate")}</MenuItem>)}</TextField><TextField label="Why this match is correct" value={rationale} onChange={(e) => setRationale(e.target.value)} /><Button variant="contained" onClick={() => void act("Confirming match", confirm, "Manual identity decision recorded in the audit trail.")}>Confirm match</Button></Stack></Paper>}
            </>
          )}
          {!reconciliation && <Button variant="contained" size="large" sx={{ alignSelf: "flex-start" }} disabled={(status.suggested_matches ?? 0) + status.unresolved_events > 0} onClick={() => void act("Running deterministic reconciliation", reconcile, "Reconciliation completed from the approved contract version.")}>Run reconciliation</Button>}
          {reconciliation && (
            <>
              <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" }, gap: 2 }}><Metric label="Billed" value={money(reconciliation.submitted_amount)} /><Metric label="Payable" value={money(reconciliation.confirmed_payable_amount)} /><Metric label="Disputed" value={money(reconciliation.recommended_deduction)} /><Metric label="Needs review" value={money(reconciliation.needs_review_amount)} /></Box>
              <Determinations rows={rows} />
              {needsReview.length > 0 && <Alert severity="warning">Needs-review lines are deliberately held out of both payable and disputed totals. Add the missing/authoritative evidence and rerun; Evidue will create a new append-only reconciliation version.</Alert>}
              <Button variant="outlined" sx={{ alignSelf: "flex-start" }} onClick={() => void act("Rerunning reconciliation", reconcile, "A new append-only reconciliation run was created.")}>Rerun after evidence changes</Button>
            </>
          )}
        </Stack>
      )}
    </Surface>
  );
}

function ExportWorkspace({ reconciliation, act }: { reconciliation: Reconciliation | null; act: (label: string, action: () => Promise<void>, success?: string) => Promise<void> }) {
  if (!reconciliation) return <Surface title="Finance-ready outputs" eyebrow="05 · Export" complete={false}><Typography color="text.secondary">Run a reconciliation to unlock exports.</Typography></Surface>;
  const id = reconciliation.reconciliation_id;
  return (
    <Surface title="Finance-ready outputs" eyebrow="05 · Export" complete>
      <Stack spacing={2}>
        <Typography color="text.secondary">Exports are generated from the exact persisted reconciliation run; historical files remain tied to the approved rule version and evidence used.</Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
          <Button variant="contained" onClick={() => void act("Preparing corrected invoice", () => pilotApi.downloadExport(id, "corrected-invoice.csv"))}>Corrected invoice CSV</Button>
          <Button variant="outlined" onClick={() => void act("Preparing review report", () => pilotApi.downloadExport(id, "review-report.html"))}>Review report</Button>
          <Button variant="outlined" onClick={() => void act("Preparing corrected summary", () => pilotApi.downloadExport(id, "summary.json"))}>Summary JSON</Button>
          <Button variant="outlined" onClick={() => void act("Preparing disputes", () => pilotApi.downloadExport(id, "disputes.csv"))}>Dispute CSV</Button>
          <Button variant="outlined" onClick={() => void act("Preparing evidence package", () => pilotApi.downloadExport(id, "evidence.json"))}>Evidence package</Button>
        </Stack>
      </Stack>
    </Surface>
  );
}

function AdvancedDetails({ airVersion, assurance, plan, facts, audit }: { airVersion: (AIRVersion & { agreement_ir?: AgreementIRView }) | null; assurance: CompilerAssurance | null; plan: VerificationPlanEnvelope | null; facts: DerivedFact[]; audit: AuditEvent[] }) {
  return (
    <Stack spacing={3}>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
        <Paper variant="outlined" sx={{ p: 2 }}><Typography fontWeight={750}>Approved AIR</Typography><Typography variant="body2" fontFamily="monospace">{airVersion?.id ?? "—"}</Typography><Typography variant="caption">Payload {airVersion?.payload_hash ?? "—"}</Typography></Paper>
        <Paper variant="outlined" sx={{ p: 2 }}><Typography fontWeight={750}>Compiler assurance</Typography><Chip size="small" color={assurance?.hard_gate_passed ? "success" : "default"} label={assurance?.hard_gate_passed ? "Hard gate passed" : "Not available"} /><Typography variant="caption" display="block" sx={{ mt: 1 }}>{assurance?.checks?.filter((item) => item.status === "pass").length ?? 0}/{assurance?.checks?.length ?? 0} checks passed</Typography></Paper>
      </Box>
      {assurance?.checks?.map((check) => <Alert key={check.id} severity={check.status === "pass" ? "success" : check.hard_gate ? "error" : "warning"}><strong>{readable(check.id)}</strong> — {check.summary}{check.details.length ? ` (${check.details.join("; ")})` : ""}</Alert>)}
      {plan && <Box><Typography variant="h6" fontWeight={750} gutterBottom>Evidence verification plan</Typography>{plan.plan.items.map((item) => <Paper key={item.proof_requirement_id} variant="outlined" sx={{ p: 1.5, mb: 1 }}><Stack direction="row" spacing={1} alignItems="center"><Chip size="small" color={item.status === "ready" ? "success" : item.status === "partial" ? "warning" : "error"} label={item.status} /><Typography variant="body2" fontFamily="monospace">{item.proof_requirement_id}</Typography></Stack><Typography variant="caption">{item.rationale}</Typography></Paper>)}</Box>}
      {facts.length > 0 && <Box><Typography variant="h6" fontWeight={750} gutterBottom>Derived deterministic facts</Typography><TableContainer sx={{ border: 1, borderColor: "divider", borderRadius: 2 }}><Table size="small"><TableHead><TableRow><TableCell>Fact</TableCell><TableCell>Truth</TableCell><TableCell>Authority</TableCell><TableCell>Input hash</TableCell></TableRow></TableHead><TableBody>{facts.slice(0, 100).map((fact) => <TableRow key={fact.id}><TableCell>{fact.fact_type}</TableCell><TableCell>{fact.truth}</TableCell><TableCell>{readable(fact.authority)}</TableCell><TableCell><Typography variant="caption" fontFamily="monospace">{fact.input_hash.slice(0, 18)}…</Typography></TableCell></TableRow>)}</TableBody></Table></TableContainer></Box>}
      <Box><Typography variant="h6" fontWeight={750} gutterBottom>Workspace audit history</Typography>{audit.length ? audit.map((event) => <Box key={event.id} sx={{ py: 1, borderBottom: 1, borderColor: "divider", display: "grid", gridTemplateColumns: { xs: "1fr", md: "180px 1fr 180px" }, gap: 1 }}><Typography variant="caption">{new Date(event.occurred_at).toLocaleString()}</Typography><Typography variant="body2"><strong>{readable(event.action)}</strong> · {event.object_type}</Typography><Typography variant="caption" fontFamily="monospace">{event.object_id?.slice(0, 20) ?? "workspace"}</Typography></Box>) : <Typography color="text.secondary">Open Advanced after activity to load the audit trail.</Typography>}</Box>
    </Stack>
  );
}
