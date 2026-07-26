import {
  Alert,
  AppBar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
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
import { api, Contract, Invoice, Outcome, OutcomeDetail, Summary } from "./api";
import { disclosure, formatUsd } from "./presentation";

const reasonOptions = [
  ["R1", "Same-intent recontacts"],
  ["R2", "Human completions or corrections"],
  ["R3", "Failed downstream actions"],
  ["R4", "Duplicate charges"],
  ["R5", "Account or action mismatches"],
];

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "primary" | "negative";
}) {
  return (
    <Card className={tone === "primary" ? "metric metric-primary" : "metric"}>
      <CardContent>
        <Typography className="eyebrow">{label}</Typography>
        <Typography variant={tone === "primary" ? "h2" : "h4"}>{value}</Typography>
      </CardContent>
    </Card>
  );
}

function ContractPanel({ contract }: { contract: Contract }) {
  return (
    <Paper className="section" id="contract-rules">
      <Box className="section-heading">
        <Box>
          <Typography className="eyebrow">Contract → executable policy</Typography>
          <Typography variant="h5">Seven deterministic billing rules</Typography>
        </Box>
        <Chip label={`${contract.price_per_outcome} USD / payable outcome`} />
      </Box>
      <Stack spacing={1.5}>
        {contract.clauses.map((clause) => (
          <Box className="rule-row" key={clause.id}>
            <Box>
              <Typography fontWeight={700}>
                {clause.rule.id} · {clause.rule.title}
              </Typography>
              <Typography color="text.secondary">{clause.text}</Typography>
            </Box>
            <Box>
              <Typography className="eyebrow">Executable interpretation</Typography>
              <Typography>{clause.rule.description}</Typography>
              <Typography variant="body2" color="text.secondary">
                Evidence: {clause.rule.evidence_required.join(", ")}
              </Typography>
            </Box>
          </Box>
        ))}
      </Stack>
    </Paper>
  );
}

function OutcomeDialog({
  detail,
  onClose,
}: {
  detail: OutcomeDetail | null;
  onClose: () => void;
}) {
  return (
    <Dialog open={Boolean(detail)} onClose={onClose} maxWidth="md" fullWidth>
      {detail && (
        <>
          <DialogTitle>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Box>
                <Typography className="eyebrow">Outcome evidence</Typography>
                <Typography variant="h5">{detail.outcome_id}</Typography>
              </Box>
              <Chip
                color={detail.status === "disputed" ? "error" : "success"}
                label={detail.status.replace("_", " ")}
              />
            </Stack>
          </DialogTitle>
          <DialogContent>
            <Grid container spacing={2} sx={{ mb: 3 }}>
              <Grid item xs={6} md={3}>
                <Typography className="eyebrow">Vendor claim</Typography>
                <Typography>{detail.vendor_claim}</Typography>
              </Grid>
              <Grid item xs={6} md={3}>
                <Typography className="eyebrow">Billed</Typography>
                <Typography>{formatUsd(detail.billed_amount)}</Typography>
              </Grid>
              <Grid item xs={6} md={3}>
                <Typography className="eyebrow">Payable</Typography>
                <Typography fontWeight={700}>{formatUsd(detail.payable_amount)}</Typography>
              </Grid>
              <Grid item xs={6} md={3}>
                <Typography className="eyebrow">Conversation</Typography>
                <Typography>{detail.conversation.id}</Typography>
              </Grid>
            </Grid>
            <Alert severity={detail.status === "disputed" ? "error" : "success"}>
              {detail.reason}
            </Alert>
            {detail.rule && (
              <Box sx={{ my: 3 }}>
                <Typography className="eyebrow">Contract clause and rule</Typography>
                <Typography fontWeight={700}>
                  {detail.rule.id} · {detail.rule.title}
                </Typography>
                <Typography>{detail.contract_clause}</Typography>
                <Typography color="text.secondary">{detail.rule.description}</Typography>
              </Box>
            )}
            <Typography className="eyebrow">Chronological operational evidence</Typography>
            <Box className="timeline">
              {detail.evidence.map((event) => (
                <Box className="timeline-event" key={event.id}>
                  <span />
                  <Box>
                    <Typography fontWeight={700}>
                      {event.event_type.replaceAll("_", " ")}
                    </Typography>
                    <Typography variant="body2">
                      {new Date(event.timestamp).toLocaleString()} · {event.source_system}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Source record {event.source_record_id} · ingested{" "}
                      {new Date(event.ingested_at).toLocaleString()}
                    </Typography>
                  </Box>
                </Box>
              ))}
            </Box>
            <Divider sx={{ my: 2 }} />
            <Typography variant="caption">
              Evaluated {new Date(detail.evaluated_at).toLocaleString()} with engine{" "}
              {detail.engine_version}
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={onClose}>Close</Button>
          </DialogActions>
        </>
      )}
    </Dialog>
  );
}

function OutcomesTable({ summary }: { summary: Summary }) {
  const [rows, setRows] = useState<Outcome[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [status, setStatus] = useState("");
  const [reason, setReason] = useState("");
  const [outcomeId, setOutcomeId] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [intent, setIntent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<OutcomeDetail | null>(null);
  const limit = 25;

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

  function updateFilter(setter: (value: string) => void, value: string) {
    setPage(0);
    setter(value);
  }

  return (
    <Paper className="section" id="outcomes">
      <Box className="section-heading">
        <Box>
          <Typography className="eyebrow">Claim-level audit</Typography>
          <Typography variant="h5">Outcome determinations</Typography>
        </Box>
        <Chip label={`${total.toLocaleString()} matching outcomes`} />
      </Box>
      <Grid container spacing={1.5} sx={{ mb: 2 }}>
        <Grid item xs={12} md={2}>
          <FormControl fullWidth size="small">
            <InputLabel id="status-label">Status</InputLabel>
            <Select
              labelId="status-label"
              label="Status"
              value={status}
              onChange={(event) => updateFilter(setStatus, event.target.value)}
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
            <InputLabel id="reason-label">Dispute reason</InputLabel>
            <Select
              labelId="reason-label"
              label="Dispute reason"
              value={reason}
              onChange={(event) => updateFilter(setReason, event.target.value)}
            >
              <MenuItem value="">All reasons</MenuItem>
              {reasonOptions.map(([id, label]) => (
                <MenuItem value={id} key={id}>{label}</MenuItem>
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
            onChange={(event) => updateFilter(setOutcomeId, event.target.value)}
          />
        </Grid>
        <Grid item xs={12} md={2}>
          <TextField
            fullWidth
            size="small"
            label="Customer ID"
            value={customerId}
            onChange={(event) => updateFilter(setCustomerId, event.target.value)}
          />
        </Grid>
        <Grid item xs={12} md={2}>
          <FormControl fullWidth size="small">
            <InputLabel id="intent-label">Intent</InputLabel>
            <Select
              labelId="intent-label"
              label="Intent"
              value={intent}
              onChange={(event) => updateFilter(setIntent, event.target.value)}
            >
              <MenuItem value="">All intents</MenuItem>
              <MenuItem value="order_support">Order support</MenuItem>
              <MenuItem value="cancel_subscription">Cancel subscription</MenuItem>
              <MenuItem value="refund">Refund</MenuItem>
            </Select>
          </FormControl>
        </Grid>
        <Grid item xs={12} md={2}>
          <Button
            fullWidth
            variant="outlined"
            onClick={() => {
              setStatus("");
              setReason("");
              setOutcomeId("");
              setCustomerId("");
              setIntent("");
              setPage(0);
            }}
          >
            Clear filters
          </Button>
        </Grid>
      </Grid>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {loading && <LinearProgress />}
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              {["Outcome ID", "Customer ID", "Intent", "Vendor claim", "Evidue status", "Dispute reason", "Billed", "Payable", "Closed"].map((heading) => (
                <TableCell key={heading}>{heading}</TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {!loading && rows.length === 0 && (
              <TableRow><TableCell colSpan={9}>No outcomes match these filters.</TableCell></TableRow>
            )}
            {rows.map((row) => (
              <TableRow hover key={row.outcome_id} onClick={() => void openOutcome(row.outcome_id)} className="clickable-row">
                <TableCell><Link component="button">{row.outcome_id}</Link></TableCell>
                <TableCell>{row.customer_id}</TableCell>
                <TableCell>{row.intent.replaceAll("_", " ")}</TableCell>
                <TableCell>{row.vendor_claim}</TableCell>
                <TableCell><Chip size="small" color={row.status === "disputed" ? "error" : "success"} label={row.status.replace("_", " ")} /></TableCell>
                <TableCell>{row.status === "disputed" ? row.reason : "—"}</TableCell>
                <TableCell>{formatUsd(row.billed_amount)}</TableCell>
                <TableCell>{formatUsd(row.payable_amount)}</TableCell>
                <TableCell>{new Date(row.closed_at).toLocaleString()}</TableCell>
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
      <OutcomeDialog detail={detail} onClose={() => setDetail(null)} />
    </Paper>
  );
}

export default function App() {
  const [contract, setContract] = useState<Contract | null>(null);
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function initialize() {
      try {
        const [status, contractResult, invoiceResult] = await Promise.all([
          api.status(),
          api.contract(),
          api.invoice(),
        ]);
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
  }, []);

  const categoryRows = useMemo(
    () => summary ? Object.entries(summary.categories) : [],
    [summary],
  );

  async function run(resetFirst = false) {
    setRunning(true);
    setError("");
    try {
      if (resetFirst) await api.reset();
      setSummary(await api.reconcile());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Reconciliation failed");
    } finally {
      setRunning(false);
    }
  }

  if (loading) {
    return <Box className="center"><CircularProgress /><Typography>Loading deterministic demo inputs…</Typography></Box>;
  }
  if (!contract || !invoice) {
    return <Container sx={{ py: 8 }}><Alert severity="error">{error || "Demo inputs unavailable"}</Alert></Container>;
  }

  return (
    <>
      <AppBar position="static" color="transparent" elevation={0}>
        <Toolbar>
          <Typography variant="h5" fontWeight={800}>Evidue</Typography>
          <Box sx={{ flexGrow: 1 }} />
          <Chip label="Synthetic demonstration data" color="warning" />
        </Toolbar>
      </AppBar>
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Alert icon={false} severity="info" className="disclosure">
          <strong>Synthetic demonstration data.</strong> {disclosure}
        </Alert>
        <Box className="hero">
          <Box>
            <Typography className="eyebrow">Independent invoice reconciliation</Typography>
            <Typography variant="h3">{contract.customer} × {contract.vendor}</Typography>
            <Typography color="text.secondary">
              June 1–30, 2026 · {invoice.claimed_outcomes.toLocaleString()} vendor-claimed outcomes
            </Typography>
          </Box>
          <Button variant="contained" size="large" disabled={running} onClick={() => void run(Boolean(summary))}>
            {running ? "Running reconciliation…" : summary ? "Reset and run again" : "Run reconciliation"}
          </Button>
        </Box>
        {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}
        {running && (
          <Paper className="running">
            <CircularProgress size={24} />
            <Box><Typography fontWeight={700}>Evaluating persisted claims and evidence</Typography><Typography color="text.secondary">The backend is applying the executable contract to every outcome.</Typography></Box>
          </Paper>
        )}
        {!summary ? (
          <Grid container spacing={2} sx={{ mb: 4 }}>
            <Grid item xs={12} md={4}><Metric label="Vendor invoice" value={formatUsd(invoice.submitted_amount)} /></Grid>
            <Grid item xs={12} md={4}><Metric label="Claimed outcomes" value={invoice.claimed_outcomes.toLocaleString()} /></Grid>
            <Grid item xs={12} md={4}><Metric label="Reconciliation status" value="Ready to run" /></Grid>
          </Grid>
        ) : (
          <>
            <Grid container spacing={2} sx={{ mb: 2 }}>
              <Grid item xs={12} md={6}><Metric tone="primary" label="Correct payable amount" value={formatUsd(summary.payable_amount)} /></Grid>
              <Grid item xs={12} md={3}><Metric label="Vendor invoice" value={formatUsd(summary.submitted_amount)} /></Grid>
              <Grid item xs={12} md={3}><Metric label="Recommended deduction" value={formatUsd(summary.recommended_deduction)} /></Grid>
            </Grid>
            <Alert severity="success" className="deterministic-message">
              Every dollar is produced by deterministic rules evaluated against traceable evidence—not by a model&apos;s guess.
            </Alert>
            <Grid container spacing={2} sx={{ my: 2 }}>
              <Grid item xs={12} md={4}><Metric label="Claimed outcomes" value={summary.claimed_outcomes.toLocaleString()} /></Grid>
              <Grid item xs={12} md={4}><Metric label="Payable outcomes" value={summary.payable_outcomes.toLocaleString()} /></Grid>
              <Grid item xs={12} md={4}><Metric label="Disputed outcomes" value={summary.disputed_outcomes.toLocaleString()} /></Grid>
            </Grid>
            <Paper className="section">
              <Box className="section-heading">
                <Box><Typography className="eyebrow">Recommended deduction</Typography><Typography variant="h5">Dispute breakdown</Typography></Box>
                <Stack direction="row" spacing={1}>
                  <Button href="/api/reconciliations/current/exports/disputes.csv" variant="outlined">Dispute CSV</Button>
                  <Button href="/api/reconciliations/current/exports/evidence.json" variant="outlined">Evidence JSON</Button>
                  <Button href="/api/reconciliations/current/exports/summary.json" variant="outlined">Summary JSON</Button>
                </Stack>
              </Box>
              <Grid container spacing={1.5}>
                {categoryRows.map(([ruleId, category]) => (
                  <Grid item xs={12} sm={6} lg key={ruleId}>
                    <Box className="category-card"><Typography className="eyebrow">{ruleId}</Typography><Typography fontWeight={700}>{category.label}</Typography><Typography variant="h5">{category.count.toLocaleString()}</Typography><Typography color="text.secondary">{formatUsd(category.amount)}</Typography></Box>
                  </Grid>
                ))}
              </Grid>
            </Paper>
            <OutcomesTable summary={summary} />
          </>
        )}
        <ContractPanel contract={contract} />
        <Paper className="section">
          <Typography className="eyebrow">Customer-owned operational evidence</Typography>
          <Typography variant="h5" sx={{ mb: 2 }}>Available evidence sources</Typography>
          <Stack direction="row" useFlexGap flexWrap="wrap" spacing={1}>
            {contract.evidence_sources.map((source) => <Chip key={source} label={source} variant="outlined" />)}
          </Stack>
        </Paper>
      </Container>
    </>
  );
}
