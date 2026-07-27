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
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  Contract,
  DemoScenario,
  DemoStatus,
  Invoice,
  Outcome,
  OutcomeDetail,
  Rule,
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
  if (rule.parameters.window_days) return `${rule.parameters.window_days}-day window`;
  if (rule.parameters.window_hours) return `${rule.parameters.window_hours}-hour window`;
  if (rule.parameters.start && rule.parameters.end_exclusive) {
    return `${rule.parameters.start} through ${rule.parameters.end_exclusive} (exclusive)`;
  }
  return rule.description;
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
        <Typography variant="h4" component="h2">All contract rules</Typography>
      </DialogTitle>
      <DialogContent>
        <Stack divider={<Divider flexItem />} spacing={0}>
          {contract.clauses.map((clause) => (
            <Box className="rule-detail" key={clause.id}>
              <Box>
                <Typography className="rule-id">{clause.rule.id}</Typography>
                <Typography variant="h6">{clause.rule.title}</Typography>
                <Typography color="text.secondary">{clause.text}</Typography>
              </Box>
              <Box>
                <Typography className="eyebrow">Executable rule</Typography>
                <Typography>{clause.rule.description}</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
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
  return (
    <section className="major-section" aria-labelledby="contract-title">
      <Box className="section-intro horizontal">
        <Box>
          <Typography className="eyebrow">Contract controls</Typography>
          <Typography variant="h4" id="contract-title">
            Executable billing terms
          </Typography>
        </Box>
        <Button variant="outlined" onClick={() => setRulesOpen(true)}>
          View all contract rules
        </Button>
      </Box>
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

function EvidenceReadiness({ sources }: { sources: string[] }) {
  return (
    <section className="major-section" aria-labelledby="evidence-readiness-title">
      <Box className="section-intro">
        <Typography className="eyebrow">Evidence coverage</Typography>
        <Typography variant="h4" id="evidence-readiness-title">
          Available source systems
        </Typography>
      </Box>
      <Paper className="source-list">
        {sources.map((source) => (
          <Box className="source-row" key={source}>
            <span aria-hidden="true" />
            <Typography fontWeight={700}>{source}</Typography>
            <Typography color="text.secondary">
              Available for deterministic reconciliation
            </Typography>
          </Box>
        ))}
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
              : "Imported operational evidence",
        })),
        ...detail.computed_timeline_markers.map((marker) => ({
          kind: "computed" as const,
          id: marker.id,
          timestamp: marker.timestamp,
          title: readable(marker.marker_type),
          source: "Evidue contract engine",
          record: marker.id,
          caption: `${marker.description}. Evidue-computed deadline—not imported evidence.`,
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
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<OutcomeDetail | null>(null);
  const limit = 25;

  useEffect(() => {
    setReason(selectedRule);
    setStatus(selectedRule ? "disputed" : defaultStatus);
    setPage(0);
  }, [defaultStatus, selectedRule]);

  const load = useCallback(async () => {
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
      setRows(result.items);
      setTotal(result.total);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load outcomes");
    } finally {
      setLoading(false);
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

  function clearAdvanced() {
    setOutcomeId("");
    setCustomerId("");
    setIntent("");
    setPage(0);
  }

  function showAllClaims() {
    setStatus("");
    setReason("");
    onRuleChange("");
    clearAdvanced();
  }

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
                  value={status}
                  onChange={(event) => {
                    setStatus(event.target.value);
                    setPage(0);
                  }}
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
                  value={reason}
                  onChange={(event) => {
                    setReason(event.target.value);
                    onRuleChange(event.target.value);
                    setPage(0);
                  }}
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
                value={outcomeId}
                onChange={(event) => {
                  setOutcomeId(event.target.value);
                  setPage(0);
                }}
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <TextField
                fullWidth
                size="small"
                label="Customer ID"
                value={customerId}
                onChange={(event) => {
                  setCustomerId(event.target.value);
                  setPage(0);
                }}
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <FormControl fullWidth size="small">
                <InputLabel id="intent-label">Intent</InputLabel>
                <Select
                  labelId="intent-label"
                  label="Intent"
                  value={intent}
                  onChange={(event) => {
                    setIntent(event.target.value);
                    setPage(0);
                  }}
                >
                  <MenuItem value="">All intents</MenuItem>
                  <MenuItem value="order_support">Order support</MenuItem>
                  <MenuItem value="cancel_subscription">Cancel subscription</MenuItem>
                  <MenuItem value="refund">Refund</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={2}>
              <Button fullWidth variant="outlined" onClick={clearAdvanced}>
                Clear advanced
              </Button>
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

export default function App({ scenarioLab = false }: { scenarioLab?: boolean }) {
  const [demoStatus, setDemoStatus] = useState<DemoStatus | null>(null);
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [contract, setContract] = useState<Contract | null>(null);
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [selectedRule, setSelectedRule] = useState("");
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function initialize() {
      try {
        const [initialStatus, scenarioResults, contractResult, initialInvoice] =
          await Promise.all([
            api.status(),
            scenarioLab ? api.scenarios() : Promise.resolve([]),
            api.contract(),
            api.invoice(),
          ]);
        let status = initialStatus;
        let invoiceResult = initialInvoice;
        if (!scenarioLab && status.scenario_id !== "headline") {
          status = await api.reset("headline");
          invoiceResult = await api.invoice();
        }
        setDemoStatus(status);
        setScenarios(scenarioResults);
        setContract(contractResult);
        setInvoice(invoiceResult);
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
      const invoiceResult = await api.invoice();
      setDemoStatus(status);
      setInvoice(invoiceResult);
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
  if (!contract || !invoice) {
    return (
      <Container sx={{ py: 8 }}>
        <Alert severity="error">{error || "Demo inputs unavailable"}</Alert>
      </Container>
    );
  }

  return (
    <>
      <AppBar position="sticky" color="transparent" elevation={0} className="app-header">
        <Toolbar className="header-inner">
          <Typography className="wordmark">Evidue</Typography>
          <Box sx={{ flexGrow: 1 }} />
          <Chip label="Synthetic demonstration data" className="synthetic-badge" />
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" className="page-shell">
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
        <EvidenceReadiness sources={contract.evidence_sources} />
      </Container>
    </>
  );
}
