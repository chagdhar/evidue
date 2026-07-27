import {
  Alert,
  AppBar,
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Drawer,
  FormControl,
  Grid,
  InputLabel,
  LinearProgress,
  Link,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Toolbar,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  Contract,
  DataReadiness,
  DemoScenario,
  DemoStatus,
  Invoice,
  Outcome,
  OutcomeDetail,
  Rule,
  RuleCompilation,
  Summary,
} from "./api";
import { disclosure, formatPercent, formatUsd } from "./presentation";

const categoryOrder = ["R1", "R2", "R3", "R4", "R5"];
const evidenceLabels: Record<string, string> = {
  ai_closed: "AI marked outcome resolved",
  customer_recontact: "Customer contacted support again",
  human_completion: "Human completed the work",
  human_material_correction: "Human materially corrected the work",
  downstream_succeeded: "Downstream action succeeded",
  downstream_failed: "Downstream action failed",
  human_refund_completed: "Human completed the refund",
  duplicate_attribution: "Duplicate attribution corroborated",
  account_action_mismatch: "Account or action mismatch recorded",
  completion_window_expired: "Completion window expired",
};

function readable(value: string): string {
  return evidenceLabels[value] ?? value.replaceAll("_", " ");
}

function ruleRequirement(rule: Rule): string {
  const value = rule.parameters.window_value;
  const unit = rule.parameters.window_unit;
  if (typeof value === "number" && typeof unit === "string") {
    return `${value}-${unit === "days" ? "day" : "hour"} window`;
  }
  if (rule.parameters.start && rule.parameters.end_exclusive) {
    return `${String(rule.parameters.start).slice(0, 10)} through ${String(
      rule.parameters.end_exclusive,
    ).slice(0, 10)} (exclusive)`;
  }
  return rule.description;
}

function compilerMode(compilation: RuleCompilation): string {
  return compilation.live_model_call ? "Live Gemini call" : "Recorded Gemini fixture";
}

function statusTone(status: string): "success" | "warning" | "error" {
  if (status === "payable") return "success";
  if (status === "needs_review") return "warning";
  return "error";
}

function Workflow({ reconciled }: { reconciled: boolean }) {
  const steps = [
    { label: "Contract loaded", state: "complete" },
    { label: "Evidence reconciled", state: reconciled ? "complete" : "pending" },
    {
      label: "Payment recommendation ready",
      state: reconciled ? "complete" : "pending",
    },
  ];
  return (
    <Box className="workflow" aria-label="Reconciliation workflow">
      {steps.map((step, index) => (
        <Box className={`workflow-step ${step.state}`} key={step.label}>
          <span aria-hidden="true">{step.state === "complete" ? "✓" : index + 1}</span>
          <Typography>{step.label}</Typography>
        </Box>
      ))}
    </Box>
  );
}

function PaymentRecommendation({
  invoice,
  summary,
  running,
  onRun,
}: {
  invoice: Invoice;
  summary: Summary | null;
  running: boolean;
  onRun: () => void;
}) {
  return (
    <Paper className={`recommendation ${summary ? "reconciled" : "ready"}`}>
      {!summary ? (
        <>
          <Box>
            <Typography className="eyebrow">Submitted invoice</Typography>
            <Typography className="submitted-amount">
              {formatUsd(invoice.submitted_amount)}
            </Typography>
            <Typography color="text.secondary">
              {invoice.claimed_outcomes.toLocaleString()} claimed outcomes from the vendor
            </Typography>
          </Box>
          <Box className="ready-action">
            <Chip label="Ready to reconcile" className="ready-chip" />
            <Button variant="contained" size="large" disabled={running} onClick={onRun}>
              {running ? "Running reconciliation…" : "Run reconciliation"}
            </Button>
          </Box>
        </>
      ) : (
        <>
          <Box className="recommendation-primary">
            <Typography className="eyebrow">Corrected payable amount</Typography>
            <Typography className="payable-amount">
              {formatUsd(summary.confirmed_payable_amount)}
            </Typography>
            <Typography className="payable-ratio">
              {summary.payable_outcomes.toLocaleString()} of{" "}
              {summary.claimed_outcomes.toLocaleString()} outcomes payable
            </Typography>
          </Box>
          <Box className="recommendation-facts">
            <Box>
              <Typography className="fact-label">Submitted invoice</Typography>
              <Typography className="fact-value">{formatUsd(summary.submitted_amount)}</Typography>
            </Box>
            <Box>
              <Typography className="fact-label">Recommended deduction</Typography>
              <Typography className="fact-value disputed">
                {formatUsd(summary.recommended_deduction)}
              </Typography>
            </Box>
            <Box>
              <Typography className="fact-label">Needs review</Typography>
              <Typography className="fact-value review">
                {formatUsd(summary.needs_review_amount)}
              </Typography>
            </Box>
          </Box>
        </>
      )}
    </Paper>
  );
}

function ReconciliationBridge({ summary }: { summary: Summary }) {
  return (
    <section className="major-section" aria-labelledby="bridge-title">
      <Box className="section-intro">
        <Typography className="eyebrow">Reconciliation bridge</Typography>
        <Typography variant="h4" id="bridge-title">
          From submitted invoice to payable amount
        </Typography>
      </Box>
      <Paper className="bridge">
        <Box className="bridge-line start">
          <Typography>Submitted invoice</Typography>
          <Typography className="money">{formatUsd(summary.submitted_amount)}</Typography>
        </Box>
        {categoryOrder.map((ruleId) => {
          const category = summary.categories[ruleId];
          if (!category) return null;
          return (
            <Box className="bridge-line deduction" key={ruleId}>
              <Typography>
                <span aria-hidden="true">−</span> {category.label}
              </Typography>
              <Typography className="money">− {formatUsd(category.amount)}</Typography>
            </Box>
          );
        })}
        {summary.needs_review_amount !== "0.00" && (
          <Box className="bridge-line review">
            <Typography>
              <span aria-hidden="true">−</span> Held for evidence review
            </Typography>
            <Typography className="money">
              − {formatUsd(summary.needs_review_amount)}
            </Typography>
          </Box>
        )}
        <Box className="bridge-line result">
          <Typography>Corrected payable amount</Typography>
          <Typography className="money">
            = {formatUsd(summary.confirmed_payable_amount)}
          </Typography>
        </Box>
      </Paper>
    </section>
  );
}

function Findings({
  summary,
  selectedRule,
  onSelect,
}: {
  summary: Summary;
  selectedRule: string;
  onSelect: (ruleId: string) => void;
}) {
  const categories = categoryOrder.filter((ruleId) => summary.categories[ruleId]);
  return (
    <section className="major-section" aria-labelledby="findings-title">
      <Box className="section-intro">
        <Typography className="eyebrow">Confirmed findings</Typography>
        <Typography variant="h4" id="findings-title">
          Why {formatUsd(summary.recommended_deduction)} should be deducted
        </Typography>
        <Typography color="text.secondary">
          Select a finding to review the affected claims and their evidence.
        </Typography>
      </Box>
      <Paper className="findings-list">
        {categories.length > 0 && (
          <Box className="finding-heading" aria-hidden="true">
            <span>Rule</span>
            <span>Finding</span>
            <span>Outcomes</span>
            <span>Amount</span>
            <span>% of invoice</span>
          </Box>
        )}
        {categories.map((ruleId) => {
          const category = summary.categories[ruleId];
          return (
            <button
              type="button"
              className={`finding-row${selectedRule === ruleId ? " selected" : ""}`}
              onClick={() => onSelect(ruleId)}
              aria-pressed={selectedRule === ruleId}
              key={ruleId}
            >
              <span className="rule-id">{ruleId}</span>
              <span className="finding-label">{category.label}</span>
              <span className="numeric">{category.count.toLocaleString()}</span>
              <span className="numeric">{formatUsd(category.amount)}</span>
              <span className="numeric">
                {formatPercent(category.amount, summary.submitted_amount)}
              </span>
            </button>
          );
        })}
        {categories.length === 0 && (
          <Box className="empty-findings">
            <Typography variant="h6">No confirmed deductions</Typography>
            <Typography color="text.secondary">
              This data set holds {formatUsd(summary.needs_review_amount)} for
              evidence review without recommending a deduction.
            </Typography>
          </Box>
        )}
      </Paper>
    </section>
  );
}

function ContractRulesDialog({
  contract,
  open,
  onClose,
}: {
  contract: Contract;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle component="div">
        <Typography className="eyebrow">Clause-to-rule mapping</Typography>
        <Typography variant="h4" component="h2">Approved deterministic program</Typography>
      </DialogTitle>
      <DialogContent>
        <Alert severity="info" sx={{ mb: 2 }}>
          {contract.compilation.safety_boundary}
        </Alert>
        <Stack divider={<Divider flexItem />} spacing={0}>
          {contract.clauses.map((clause) => (
            <Box className="rule-detail" key={clause.id}>
              <Box>
                <Typography className="rule-id">{clause.rule.id}</Typography>
                <Typography variant="h6">{clause.rule.title}</Typography>
                <Typography color="text.secondary">{clause.text}</Typography>
              </Box>
              <Box>
                <Typography className="eyebrow">Validated operation</Typography>
                <Typography className="operation-code">{clause.rule.operation}</Typography>
                <Typography>{clause.rule.description}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Priority {clause.rule.priority} · Failure → {readable(clause.rule.consequence)}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  Evidence required: {clause.rule.evidence_required.join(", ")}
                </Typography>
              </Box>
            </Box>
          ))}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close contract rules</Button>
      </DialogActions>
    </Dialog>
  );
}

function ContractSummary({ contract }: { contract: Contract }) {
  const [rulesOpen, setRulesOpen] = useState(false);
  const [activeCompilation, setActiveCompilation] = useState(contract.compilation);
  const [latestCompilation, setLatestCompilation] = useState(contract.latest_compilation);
  const [compiling, setCompiling] = useState(false);
  const [approving, setApproving] = useState(false);
  const [compilerMessage, setCompilerMessage] = useState("");
  const [compilerError, setCompilerError] = useState("");
  const rules = Object.fromEntries(
    contract.clauses.map((clause) => [clause.rule.id, clause.rule]),
  );
  const items = [
    ["Price per payable outcome", formatUsd(contract.price_per_outcome)],
    ["Recontact window", ruleRequirement(rules.R1)],
    ["Human correction window", ruleRequirement(rules.R2)],
    ["Downstream completion window", ruleRequirement(rules.R3)],
    ["Duplicate attribution window", ruleRequirement(rules.R4)],
    ["Account and action matching", rules.R5.description],
  ];

  async function compileRules() {
    setCompiling(true);
    setCompilerError("");
    setCompilerMessage("");
    try {
      const proposal = await api.compileContract("auto");
      setLatestCompilation(proposal);
      setCompilerMessage(
        proposal.live_model_call
          ? "Gemini returned a schema-validated proposal. Review and approve it before use."
          : proposal.fallback_reason ??
            "No Gemini key was configured, so the validated recorded proposal was loaded for the offline demo.",
      );
    } catch (requestError) {
      setCompilerError(
        requestError instanceof Error ? requestError.message : "Contract compilation failed",
      );
    } finally {
      setCompiling(false);
    }
  }

  async function approveRules() {
    setApproving(true);
    setCompilerError("");
    try {
      const approved = await api.approveCompilation(latestCompilation.id);
      setActiveCompilation(approved);
      setLatestCompilation(approved);
      setCompilerMessage(
        `Version ${approved.version} is approved. Reconciliation will now use this immutable rule program.`,
      );
    } catch (requestError) {
      setCompilerError(
        requestError instanceof Error ? requestError.message : "Approval failed",
      );
    } finally {
      setApproving(false);
    }
  }

  const pending = latestCompilation.status === "pending_approval";
  return (
    <section className="major-section" aria-labelledby="contract-title">
      <Box className="section-intro horizontal">
        <Box>
          <Typography className="eyebrow">Contract compiler</Typography>
          <Typography variant="h4" id="contract-title">
            Natural language in. Deterministic disputes out.
          </Typography>
          <Typography color="text.secondary">
            The LLM proposes a constrained program; a person approves it; the model never adjudicates an invoice line.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
          <Button variant="outlined" onClick={() => setRulesOpen(true)}>
            Inspect approved rules
          </Button>
          <Button variant="contained" onClick={() => void compileRules()} disabled={compiling}>
            {compiling ? "Compiling…" : "Compile contract"}
          </Button>
          {pending && (
            <Button variant="contained" color="success" onClick={() => void approveRules()} disabled={approving}>
              {approving ? "Approving…" : `Approve v${latestCompilation.version}`}
            </Button>
          )}
        </Stack>
      </Box>

      <Paper className="compiler-panel">
        <Box className="compiler-source">
          <Typography className="eyebrow">Source contract</Typography>
          <Typography variant="h6">{activeCompilation.source_document}</Typography>
          <Typography className="contract-excerpt">{contract.contract_text}</Typography>
        </Box>
        <Box className="compiler-flow" aria-label="Contract compilation safety flow">
          <Box className="compiler-step">
            <span>1</span>
            <div><strong>LLM proposes</strong><small>{compilerMode(latestCompilation)}</small></div>
          </Box>
          <Box className="compiler-arrow">→</Box>
          <Box className="compiler-step">
            <span>2</span>
            <div><strong>Schema validates</strong><small>{latestCompilation.rules.length} rules · allowlisted operations</small></div>
          </Box>
          <Box className="compiler-arrow">→</Box>
          <Box className={`compiler-step ${pending ? "pending" : "approved"}`}>
            <span>3</span>
            <div><strong>Human {pending ? "approval required" : "approved"}</strong><small>Immutable version {latestCompilation.version}</small></div>
          </Box>
          <Box className="compiler-arrow">→</Box>
          <Box className="compiler-step approved">
            <span>4</span>
            <div><strong>Engine executes</strong><small>No LLM in payable/dispute decision</small></div>
          </Box>
        </Box>
        <Box className="compiler-meta">
          <Chip label={`Active v${activeCompilation.version}`} color="success" size="small" />
          <Chip label={activeCompilation.model} variant="outlined" size="small" />
          <Typography variant="body2" color="text.secondary">
            Program {activeCompilation.id} · source {activeCompilation.source_hash.slice(0, 20)}…
          </Typography>
        </Box>
      </Paper>

      {compilerMessage && <Alert severity={pending ? "warning" : "success"} sx={{ mt: 2 }}>{compilerMessage}</Alert>}
      {compilerError && <Alert severity="error" sx={{ mt: 2 }}>{compilerError}</Alert>}

      <Paper className="contract-summary">
        {items.map(([label, value]) => (
          <Box className="contract-item" key={label}>
            <Typography className="fact-label">{label}</Typography>
            <Typography>{value}</Typography>
          </Box>
        ))}
      </Paper>
      <ContractRulesDialog
        contract={contract}
        open={rulesOpen}
        onClose={() => setRulesOpen(false)}
      />
    </section>
  );
}

function EvidenceReadiness({ readiness }: { readiness: DataReadiness }) {
  return (
    <section className="major-section" aria-labelledby="evidence-readiness-title" data-testid="evidence-readiness">
      <Box className="section-intro readiness-intro">
        <Box>
          <Typography className="eyebrow">Evidence readiness</Typography>
          <Typography variant="h4" id="evidence-readiness-title">
            Real records are collected and matched before reconciliation
          </Typography>
          <Typography color="text.secondary">{readiness.collection_note}</Typography>
        </Box>
        <Button href="/demo/data-sources" variant="outlined">Inspect collection pipeline</Button>
      </Box>
      <Paper className="readiness-panel">
        <Box className="readiness-metrics">
          <div><span>Claim coverage</span><strong>{readiness.totals.claim_coverage_percent.toFixed(2)}%</strong></div>
          <div><span>Direct outcome-ID matches</span><strong>{readiness.totals.direct_matches.toLocaleString()}</strong></div>
          <div><span>Secondary-key matches</span><strong>{readiness.totals.secondary_matches.toLocaleString()}</strong></div>
          <div><span>Needs identity review</span><strong>{readiness.totals.review_records.toLocaleString()}</strong></div>
        </Box>
        <LinearProgress variant="determinate" value={readiness.totals.claim_coverage_percent} />
        <Box className="readiness-source-strip">
          {readiness.sources.map((source) => (
            <Box key={source.id}>
              <span aria-hidden="true" />
              <strong>{source.name}</strong>
              <small>{source.raw_records.toLocaleString()} records · {source.collection_method}</small>
            </Box>
          ))}
        </Box>
      </Paper>
    </section>
  );
}

function OutcomeInspector({
  detail,
  demoOutcomeId,
  onClose,
}: {
  detail: OutcomeDetail | null;
  demoOutcomeId: string;
  onClose: () => void;
}) {
  const timeline = detail
    ? [
        ...detail.evidence.map((event) => ({
          kind:
            event.source_system === "nova_agent"
              ? ("vendor" as const)
              : ("operational" as const),
          id: event.id,
          timestamp: event.timestamp,
          title: readable(event.event_type),
          source: event.source_system.replaceAll("_", " "),
          record: event.source_record_id,
          caption:
            event.source_system === "nova_agent"
              ? "Vendor-provided evidence"
              : "Customer-owned operational evidence",
          provenance: event.provenance,
        })),
        ...detail.computed_timeline_markers.map((marker) => ({
          kind: "computed" as const,
          id: marker.id,
          timestamp: marker.timestamp,
          title: readable(marker.marker_type),
          source: "Evidue contract engine",
          record: marker.id,
          caption: `${marker.description}. Evidue-computed deadline—not imported evidence.`,
          provenance: null,
        })),
      ].sort((left, right) => left.timestamp.localeCompare(right.timestamp))
    : [];

  return (
    <Drawer
      anchor="right"
      open={Boolean(detail)}
      onClose={onClose}
      PaperProps={{ className: "evidence-drawer" }}
    >
      {detail && (
        <Box className="inspector">
          <Box className="inspector-header">
            <Box>
              <Typography className="eyebrow">Outcome evidence inspector</Typography>
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="h4" className="mono">
                  {detail.outcome_id}
                </Typography>
                {detail.outcome_id === demoOutcomeId && (
                  <Chip label="Demo example" className="demo-chip" size="small" />
                )}
              </Stack>
            </Box>
            <Button onClick={onClose}>Close</Button>
          </Box>

          {detail.claim_provenance && (
            <Paper className="claim-provenance-strip">
              <Box><Typography variant="caption" color="text.secondary">Vendor claim ID</Typography><strong className="mono">{detail.vendor_claim_id}</strong></Box>
              <Box><Typography variant="caption" color="text.secondary">Agent version</Typography><strong>{detail.agent_version}</strong></Box>
              <Box><Typography variant="caption" color="text.secondary">Collected through</Typography><strong>{detail.claim_provenance.collection_method}</strong></Box>
              <Box><Typography variant="caption" color="text.secondary">Raw record</Typography><strong className="mono">{detail.claim_provenance.raw_record_id}</strong></Box>
            </Paper>
          )}

          <Box className="comparison-grid">
            <Box className="comparison-panel vendor">
              <Typography className="eyebrow">Vendor claim</Typography>
              <Typography variant="h6">Marked {detail.vendor_claim}</Typography>
              <dl>
                <dt>Claimed action</dt>
                <dd>{readable(detail.expected_action)}</dd>
                <dt>Billed amount</dt>
                <dd>{formatUsd(detail.billed_amount)}</dd>
              </dl>
            </Box>
            <Box className="comparison-panel contract">
              <Typography className="eyebrow">Contract obligation</Typography>
              {detail.rule ? (
                <>
                  <Typography variant="h6">
                    {detail.rule.id} · {detail.rule.title}
                  </Typography>
                  <Typography>{detail.contract_clause}</Typography>
                  <Typography className="requirement">
                    {ruleRequirement(detail.rule)}
                  </Typography>
                </>
              ) : (
                <Typography>All applicable billing rules must pass.</Typography>
              )}
            </Box>
            <Box className="comparison-panel determination">
              <Typography className="eyebrow">Evidue determination</Typography>
              <Chip
                size="small"
                color={statusTone(detail.status)}
                label={detail.status.replace("_", " ")}
              />
              <Typography className="determination-reason">{detail.reason}</Typography>
              <Box>
                <Typography className="fact-label">Confirmed payable</Typography>
                <Typography className="inspector-payable">
                  {formatUsd(detail.confirmed_payable_amount)}
                </Typography>
              </Box>
            </Box>
          </Box>

          <Box className="timeline-heading">
            <Typography className="eyebrow">Evidence timeline</Typography>
            <Typography variant="h5">What happened, in order</Typography>
          </Box>
          <Box className="timeline">
            {timeline.map((item) => (
              <Box className={`timeline-event ${item.kind}`} key={item.id}>
                <span aria-hidden="true" />
                <Box>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                    <Typography fontWeight={800}>{item.title}</Typography>
                    <Chip size="small" variant="outlined" label={item.caption} />
                  </Stack>
                  <Typography className="timeline-time">
                    {new Date(item.timestamp).toLocaleString()}
                  </Typography>
                  <Typography variant="body2">
                    Source: {item.source} · Record:{" "}
                    <span className="mono">{item.record}</span>
                  </Typography>
                  {item.provenance && (
                    <details className="timeline-provenance">
                      <summary>View source provenance</summary>
                      <dl>
                        <dt>Connector</dt><dd>{item.provenance.connector_name}</dd>
                        <dt>Authority</dt><dd>{item.provenance.authority}</dd>
                        <dt>Collected</dt><dd>{item.provenance.collection_method}</dd>
                        <dt>Production path</dt><dd>{item.provenance.production_method}</dd>
                        <dt>Match</dt><dd>{item.provenance.match_method} · {item.provenance.match_confidence}</dd>
                        <dt>Payload hash</dt><dd className="mono">{item.provenance.payload_hash}</dd>
                      </dl>
                      {item.provenance.raw_payload && <pre>{JSON.stringify(item.provenance.raw_payload, null, 2)}</pre>}
                    </details>
                  )}
                </Box>
              </Box>
            ))}
          </Box>
          <Divider />
          <Typography variant="caption" color="text.secondary">
            Evaluated {new Date(detail.evaluated_at).toLocaleString()} · Engine{" "}
            {detail.engine_version}
          </Typography>
        </Box>
      )}
    </Drawer>
  );
}

function ClaimsReview({
  summary,
  selectedRule,
  demoOutcomeId,
  onRuleChange,
}: {
  summary: Summary;
  selectedRule: string;
  demoOutcomeId: string;
  onRuleChange: (ruleId: string) => void;
}) {
  const defaultStatus =
    summary.disputed_outcomes > 0
      ? "disputed"
      : summary.needs_review_outcomes > 0
        ? "needs_review"
        : "payable";
  const [rows, setRows] = useState<Outcome[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [status, setStatus] = useState(defaultStatus);
  const [reason, setReason] = useState(selectedRule);
  const [outcomeId, setOutcomeId] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [intent, setIntent] = useState("");
  const [draftStatus, setDraftStatus] = useState(defaultStatus);
  const [draftReason, setDraftReason] = useState(selectedRule);
  const [draftOutcomeId, setDraftOutcomeId] = useState("");
  const [draftCustomerId, setDraftCustomerId] = useState("");
  const [draftIntent, setDraftIntent] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<OutcomeDetail | null>(null);
  const requestSequence = useRef(0);
  const limit = 25;

  useEffect(() => {
    if (!selectedRule) {
      setReason("");
      setDraftReason("");
      setPage(0);
      return;
    }
    setReason(selectedRule);
    setStatus("disputed");
    setDraftReason(selectedRule);
    setDraftStatus("disputed");
    setPage(0);
  }, [selectedRule]);

  const load = useCallback(async () => {
    const requestId = ++requestSequence.current;
    setLoading(true);
    setError("");
    const query = new URLSearchParams({
      offset: String(page * limit),
      limit: String(limit),
    });
    if (status) query.set("status", status);
    if (reason) query.set("reason", reason);
    if (outcomeId) query.set("outcome_id", outcomeId);
    if (customerId) query.set("customer_id", customerId);
    if (intent) query.set("intent", intent);
    try {
      const result = await api.outcomes(query);
      if (requestId !== requestSequence.current) return;
      setRows(result.items);
      setTotal(result.total);
    } catch (requestError) {
      if (requestId !== requestSequence.current) return;
      setError(requestError instanceof Error ? requestError.message : "Could not load outcomes");
    } finally {
      if (requestId === requestSequence.current) setLoading(false);
    }
  }, [customerId, intent, outcomeId, page, reason, status]);

  useEffect(() => {
    void load();
  }, [load, summary.reconciliation_id]);

  async function openOutcome(id: string) {
    setError("");
    try {
      setDetail(await api.outcome(id));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load evidence");
    }
  }

  function applyFilters() {
    setStatus(draftStatus);
    setReason(draftReason);
    setOutcomeId(draftOutcomeId.trim());
    setCustomerId(draftCustomerId.trim());
    setIntent(draftIntent);
    onRuleChange(draftReason);
    setPage(0);
  }

  function clearAllFilters() {
    setDraftStatus("");
    setDraftReason("");
    setDraftOutcomeId("");
    setDraftCustomerId("");
    setDraftIntent("");
    setStatus("");
    setReason("");
    setOutcomeId("");
    setCustomerId("");
    setIntent("");
    onRuleChange("");
    setPage(0);
  }

  function showAllClaims() {
    clearAllFilters();
  }

  const activeFilterCount = [status, reason, outcomeId, customerId, intent].filter(Boolean).length;

  return (
    <section className="major-section" aria-labelledby="claims-title">
      <Box className="section-intro horizontal">
        <Box>
          <Typography className="eyebrow">Claims review</Typography>
          <Typography variant="h4" id="claims-title">
            {defaultStatus === "needs_review"
              ? "Needs-review outcome evidence"
              : defaultStatus === "payable"
                ? "Payable outcome evidence"
                : "Disputed outcome evidence"}
          </Typography>
          <Typography color="text.secondary">
            {total.toLocaleString()} matching outcomes
            {reason ? ` · ${reason} selected` : ""}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} flexWrap="wrap">
          <Button variant="contained" onClick={() => void openOutcome(demoOutcomeId)}>
            Review example dispute
          </Button>
          <Button onClick={showAllClaims}>Show all claims</Button>
          <Button
            variant="outlined"
            onClick={() => setFiltersOpen((current) => !current)}
            aria-expanded={filtersOpen}
          >
            {filtersOpen ? "Hide advanced filters" : "Advanced filters"}
          </Button>
        </Stack>
      </Box>

      <Collapse in={filtersOpen}>
        <Paper className="filter-panel">
          <Grid container spacing={1.5}>
            <Grid item xs={12} md={2}>
              <FormControl fullWidth size="small">
                <InputLabel id="status-label">Status</InputLabel>
                <Select
                  labelId="status-label"
                  label="Status"
                  value={draftStatus}
                  onChange={(event) => setDraftStatus(event.target.value)}
                >
                  <MenuItem value="">All statuses</MenuItem>
                  <MenuItem value="payable">Payable</MenuItem>
                  <MenuItem value="disputed">Disputed</MenuItem>
                  <MenuItem value="needs_review">Needs review</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={2}>
              <FormControl fullWidth size="small">
                <InputLabel id="reason-label">Failed rule</InputLabel>
                <Select
                  labelId="reason-label"
                  label="Failed rule"
                  value={draftReason}
                  onChange={(event) => setDraftReason(event.target.value)}
                >
                  <MenuItem value="">All rules</MenuItem>
                  {categoryOrder.map((ruleId) => (
                    <MenuItem value={ruleId} key={ruleId}>
                      {ruleId} · {summary.categories[ruleId]?.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={2}>
              <TextField
                fullWidth
                size="small"
                label="Outcome ID"
                value={draftOutcomeId}
                onChange={(event) => setDraftOutcomeId(event.target.value)}
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <TextField
                fullWidth
                size="small"
                label="Customer ID"
                value={draftCustomerId}
                onChange={(event) => setDraftCustomerId(event.target.value)}
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <FormControl fullWidth size="small">
                <InputLabel id="intent-label">Intent</InputLabel>
                <Select
                  labelId="intent-label"
                  label="Intent"
                  value={draftIntent}
                  onChange={(event) => setDraftIntent(event.target.value)}
                >
                  <MenuItem value="">All intents</MenuItem>
                  <MenuItem value="order_support">Order support</MenuItem>
                  <MenuItem value="cancel_subscription">Cancel subscription</MenuItem>
                  <MenuItem value="refund">Refund</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={2}>
              <Stack direction={{ xs: "column", sm: "row", md: "column" }} spacing={1}>
                <Button fullWidth variant="contained" onClick={applyFilters}>
                  Apply filters
                </Button>
                <Button fullWidth variant="outlined" onClick={clearAllFilters}>
                  Clear all
                </Button>
              </Stack>
            </Grid>
            <Grid item xs={12}>
              <Typography variant="caption" color="text.secondary" aria-live="polite">
                {activeFilterCount === 0
                  ? "No filters applied."
                  : `${activeFilterCount} filter${activeFilterCount === 1 ? "" : "s"} applied.`}
              </Typography>
            </Grid>
          </Grid>
        </Paper>
      </Collapse>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Paper className="claims-table">
        {loading && <LinearProgress />}
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                {[
                  "Outcome",
                  "Customer",
                  "Issue",
                  "Failed rule",
                  "Evidence summary",
                  "Billed",
                  "Payable",
                  "Status",
                ].map((heading) => (
                  <TableCell key={heading}>{heading}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {!loading && rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8}>No outcomes match these filters.</TableCell>
                </TableRow>
              )}
              {rows.map((row) => (
                <TableRow
                  hover
                  key={row.outcome_id}
                  className={row.outcome_id === demoOutcomeId ? "demo-row" : ""}
                >
                  <TableCell>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Link
                        component="button"
                        className="mono"
                        onClick={() => void openOutcome(row.outcome_id)}
                        aria-label={`Review ${row.outcome_id} evidence`}
                      >
                        {row.outcome_id}
                      </Link>
                      {row.outcome_id === demoOutcomeId && (
                        <Chip label="Demo example" size="small" className="demo-chip" />
                      )}
                    </Stack>
                  </TableCell>
                  <TableCell className="mono">{row.customer_id}</TableCell>
                  <TableCell>{row.reason}</TableCell>
                  <TableCell>
                    <span className="rule-id">{row.rule_id ?? "—"}</span>
                  </TableCell>
                  <TableCell>
                    <Button size="small" onClick={() => void openOutcome(row.outcome_id)}>
                      Review timeline
                    </Button>
                  </TableCell>
                  <TableCell className="numeric">{formatUsd(row.billed_amount)}</TableCell>
                  <TableCell className="numeric">
                    {formatUsd(row.confirmed_payable_amount)}
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      color={statusTone(row.status)}
                      label={row.status.replace("_", " ")}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          component="div"
          count={total}
          page={page}
          rowsPerPage={limit}
          rowsPerPageOptions={[limit]}
          onPageChange={(_, nextPage) => setPage(nextPage)}
        />
      </Paper>
      <OutcomeInspector
        detail={detail}
        demoOutcomeId={demoOutcomeId}
        onClose={() => setDetail(null)}
      />
    </section>
  );
}

function Exports({ summary }: { summary: Summary }) {
  const [message, setMessage] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");

  async function downloadPackage() {
    setDownloading(true);
    setError("");
    try {
      const response = await fetch(
        "/api/reconciliations/current/exports/evidence.json",
      );
      if (!response.ok) throw new Error(`Export failed (${response.status})`);
      const payload = await response.json();
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "evidue-dispute-package.json";
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage(
        `Dispute package ready: ${summary.disputed_outcomes.toLocaleString()} disputed outcomes · ${formatUsd(summary.recommended_deduction)}.`,
      );
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not export package");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <section className="major-section export-section" aria-labelledby="exports-title">
      <Box className="section-intro">
        <Typography className="eyebrow">Defensible handoff</Typography>
        <Typography variant="h4" id="exports-title">
          Prepare vendor dispute
        </Typography>
        <Typography color="text.secondary">
          Package the disputed invoice lines, contract rules, and decisive
          evidence for finance or procurement.
        </Typography>
      </Box>
      <Box className="dispute-state" aria-label="Dispute preparation status">
        <span>Detected ✓</span>
        <span aria-hidden="true">→</span>
        <span>Evidenced ✓</span>
        <span aria-hidden="true">→</span>
        <span>Ready to dispute ✓</span>
      </Box>
      <Paper className="export-actions">
        <Button
          variant="contained"
          size="large"
          disabled={downloading}
          onClick={() => void downloadPackage()}
        >
          {downloading ? "Preparing dispute package…" : "Download dispute package"}
        </Button>
        <Box className="secondary-exports" aria-label="Other export formats">
          <Link href="/api/reconciliations/current/exports/disputes.csv">
            Disputed-lines CSV
          </Link>
          <Link href="/api/reconciliations/current/exports/evidence.json">
            Evidence JSON
          </Link>
          <Link href="/api/reconciliations/current/exports/summary.json">
            Summary JSON
          </Link>
        </Box>
      </Paper>
      {message && <Alert severity="success" sx={{ mt: 2 }}>{message}</Alert>}
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
    </section>
  );
}

export default function App({ scenarioLab = false, embedded = false }: { scenarioLab?: boolean; embedded?: boolean }) {
  const [demoStatus, setDemoStatus] = useState<DemoStatus | null>(null);
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [contract, setContract] = useState<Contract | null>(null);
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [readiness, setReadiness] = useState<DataReadiness | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [selectedRule, setSelectedRule] = useState("");
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function initialize() {
      try {
        const [initialStatus, scenarioResults, contractResult, initialInvoice, readinessResult] =
          await Promise.all([
            api.status(),
            scenarioLab ? api.scenarios() : Promise.resolve([]),
            api.contract(),
            api.invoice(),
            api.dataReadiness(),
          ]);
        let status = initialStatus;
        let invoiceResult = initialInvoice;
        let readinessValue = readinessResult;
        if (!scenarioLab && status.scenario_id !== "headline") {
          status = await api.reset("headline");
          [invoiceResult, readinessValue] = await Promise.all([api.invoice(), api.dataReadiness()]);
        }
        setDemoStatus(status);
        setScenarios(scenarioResults);
        setContract(contractResult);
        setInvoice(invoiceResult);
        setReadiness(readinessValue);
        if (status.reconciled) setSummary(await api.current());
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Could not load demo");
      } finally {
        setLoading(false);
      }
    }
    void initialize();
  }, [scenarioLab]);

  const month = useMemo(() => {
    if (!invoice) return "";
    const date = new Date(`${invoice.billing_period_start.slice(0, 10)}T00:00:00Z`);
    return date.toLocaleDateString("en-US", {
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    });
  }, [invoice]);

  async function run(resetFirst = false) {
    setRunning(true);
    setError("");
    try {
      if (resetFirst && demoStatus) {
        setDemoStatus(await api.reset(demoStatus.scenario_id));
      }
      setSummary(await api.reconcile());
      setSelectedRule("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Reconciliation failed");
    } finally {
      setRunning(false);
    }
  }

  async function selectScenario(scenarioId: string) {
    setSwitching(true);
    setError("");
    try {
      const status = await api.reset(scenarioId);
      const [invoiceResult, readinessResult] = await Promise.all([api.invoice(), api.dataReadiness()]);
      setDemoStatus(status);
      setInvoice(invoiceResult);
      setReadiness(readinessResult);
      setSummary(null);
      setSelectedRule("");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load synthetic data set",
      );
    } finally {
      setSwitching(false);
    }
  }

  if (loading) {
    return (
      <Box className="center">
        <CircularProgress />
        <Typography>Loading deterministic demo inputs…</Typography>
      </Box>
    );
  }
  if (!contract || !invoice || !readiness) {
    return (
      <Container sx={{ py: 8 }}>
        <Alert severity="error">{error || "Demo inputs unavailable"}</Alert>
      </Container>
    );
  }

  return (
    <>
      {!embedded && <AppBar position="sticky" color="transparent" elevation={0} className="app-header">
        <Toolbar className="header-inner">
          <Typography className="wordmark">Evidue</Typography>
          <Box sx={{ flexGrow: 1 }} />
          <Chip label="Synthetic demonstration data" className="synthetic-badge" />
        </Toolbar>
      </AppBar>}
      <Container maxWidth="lg" className={`page-shell${embedded ? " embedded-page" : ""}`}>
        <Alert icon={false} className="disclosure">
          <strong>Synthetic demonstration data.</strong> {disclosure}
        </Alert>

        <header className="reconciliation-header">
          <Box>
            <Typography className="eyebrow">Independent invoice reconciliation</Typography>
            <Typography variant="h2">{contract.customer}</Typography>
            <Typography className="vendor-line">
              Vendor: <strong>{contract.vendor}</strong> · {month}
            </Typography>
            {scenarioLab && demoStatus && (
              <Box className="scenario-control">
                <FormControl size="small">
                  <InputLabel id="scenario-label">Synthetic data set</InputLabel>
                  <Select
                    labelId="scenario-label"
                    label="Synthetic data set"
                    value={demoStatus.scenario_id}
                    disabled={running || switching}
                    onChange={(event) => void selectScenario(event.target.value)}
                  >
                    {scenarios.map((scenario) => (
                      <MenuItem value={scenario.id} key={scenario.id}>
                        {scenario.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                <Typography color="text.secondary" className="scenario-description">
                  {demoStatus.scenario_description}
                </Typography>
              </Box>
            )}
          </Box>
          <Box className="header-action">
            <Workflow reconciled={Boolean(summary)} />
            {summary && (
              <Button
                variant="outlined"
                disabled={running}
                onClick={() => void run(true)}
              >
                {running ? "Running reconciliation…" : "Reset and run"}
              </Button>
            )}
          </Box>
        </header>

        {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}
        {(running || switching) && (
          <Paper className="running">
            <CircularProgress size={22} />
            <Box>
              <Typography fontWeight={800}>
                {switching
                  ? "Loading deterministic synthetic data set"
                  : "Evaluating persisted claims and evidence"}
              </Typography>
              <Typography color="text.secondary">
                {switching
                  ? "Resetting claims and operational evidence for this case."
                  : "Applying executable contract rules to every claimed outcome."}
              </Typography>
            </Box>
          </Paper>
        )}

        {readiness && <EvidenceReadiness readiness={readiness} />}

        <PaymentRecommendation
          invoice={invoice}
          summary={summary}
          running={running || switching}
          onRun={() => void run(false)}
        />

        {summary && (
          <>
            <ReconciliationBridge summary={summary} />
            <Box className="trust-strip">
              <Typography>
                No model decides whether a charge is payable. Every amount is
                reproduced from contract rules and traceable source evidence.
              </Typography>
            </Box>
            <Findings
              summary={summary}
              selectedRule={selectedRule}
              onSelect={setSelectedRule}
            />
            <ClaimsReview
              key={summary.reconciliation_id}
              summary={summary}
              selectedRule={selectedRule}
              demoOutcomeId={demoStatus?.demo_outcome_id ?? ""}
              onRuleChange={setSelectedRule}
            />
            <Exports summary={summary} />
          </>
        )}

        <ContractSummary contract={contract} />
      </Container>
    </>
  );
}
