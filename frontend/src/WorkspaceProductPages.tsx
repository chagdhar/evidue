import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  InputLabel,
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
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import WorkspaceShell from "./WorkspaceShell";
import {
  clearPilotToken,
  loadPilotToken,
  pilotApi,
  ProductDisputeCase,
  ProductInvoice,
  ProductOverview,
  ProductReviewCase,
  ProductStatement,
  ProductTrust,
} from "./pilotApi";

function money(value: string | number | null | undefined, currency = "USD") {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(Number(value ?? 0));
}

function date(value: string | null | undefined) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function readable(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusTone(status: string): "default" | "success" | "warning" | "error" | "info" {
  if (["approved", "accepted", "resolved_payable"].includes(status)) return "success";
  if (["draft", "open", "escalated", "vendor_responded", "under_review", "ready"].includes(status)) return "warning";
  if (["resolved_disputed", "rejected"].includes(status)) return "error";
  return "info";
}

function useWorkspaceData() {
  const navigate = useNavigate();
  const [overview, setOverview] = useState<ProductOverview | null>(null);
  const [reviews, setReviews] = useState<ProductReviewCase[]>([]);
  const [disputes, setDisputes] = useState<ProductDisputeCase[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!loadPilotToken()) {
      navigate("/workspace/invoices/current", { replace: true });
      return;
    }
    setBusy("Refreshing");
    setError("");
    try {
      await pilotApi.productBootstrap();
      const [nextOverview, nextReviews, nextDisputes] = await Promise.all([
        pilotApi.productOverview(),
        pilotApi.productReviewCases(),
        pilotApi.productDisputes(),
      ]);
      setOverview(nextOverview);
      setReviews(nextReviews.items);
      setDisputes(nextDisputes.items);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load workspace");
    } finally {
      setBusy("");
    }
  }, [navigate]);

  useEffect(() => { void refresh(); }, [refresh]);

  const signOut = () => {
    clearPilotToken();
    navigate("/workspace/invoices/current");
  };

  return { overview, reviews, disputes, busy, error, refresh, signOut };
}

function LoadingWorkspace({ active }: { active: "overview" | "invoices" | "review" | "vendors" }) {
  const copy = active === "review"
    ? ["Loading review queue", "Reading unresolved evidence, approval, and vendor-action decisions."]
    : active === "vendors"
      ? ["Loading vendor controls", "Summarizing contracts, spend, and open financial exposure."]
      : active === "invoices"
        ? ["Loading invoice register", "Reading reconciliation and settlement status for each invoice."]
        : ["Loading finance control", "Summarizing spend under review and what needs attention next."];
  return (
    <WorkspaceShell active={active}>
      <Box className="workspace-loading-state" role="status" aria-live="polite">
        <CircularProgress size={22} />
        <Box><Typography fontWeight={740}>{copy[0]}</Typography><Typography>{copy[1]}</Typography></Box>
      </Box>
    </WorkspaceShell>
  );
}

function StatStrip({
  items,
}: {
  items: Array<{ label: string; value: string; detail: string; emphasis?: "neutral" | "warning" | "danger" }>;
}) {
  return (
    <Box className="finance-stat-strip">
      {items.map((item) => (
        <Box className={`finance-stat${item.emphasis ? ` ${item.emphasis}` : ""}`} key={item.label}>
          <Typography className="finance-stat-label">{item.label}</Typography>
          <Typography className="finance-stat-value">{item.value}</Typography>
          <Typography className="finance-stat-detail">{item.detail}</Typography>
        </Box>
      ))}
    </Box>
  );
}

function InvoiceStatus({ invoice }: { invoice: ProductInvoice }) {
  const label = invoice.statement_status === "not_reconciled"
    ? "Needs verification"
    : invoice.statement_status === "draft"
      ? "Needs review"
      : invoice.statement_status === "ready"
        ? "Approval required"
        : "Approved";
  return <Chip size="small" label={label} color={statusTone(invoice.statement_status)} variant="outlined" />;
}

export function WorkspaceOverview() {
  const navigate = useNavigate();
  const { overview, reviews, disputes, busy, error, refresh, signOut } = useWorkspaceData();
  if (!overview) return <LoadingWorkspace active="overview" />;

  const currency = overview.organization.currency || "USD";
  const openReviews = reviews.filter((item) => ["open", "escalated"].includes(item.status));
  const activeDisputes = disputes.filter((item) => !["accepted", "rejected", "closed"].includes(item.status));
  const unreconciled = overview.invoices.filter((invoice) => invoice.statement_status === "not_reconciled");
  const attentionCount = openReviews.length + activeDisputes.length + unreconciled.length;

  const nextAction = openReviews.length
    ? { title: `Resolve ${openReviews.length} review decision${openReviews.length === 1 ? "" : "s"}`, detail: `${money(openReviews.reduce((sum, row) => sum + Number(row.exposure_amount || 0), 0), currency)} is waiting on evidence or finance judgment.`, label: "Open review queue", path: "/workspace/review" }
    : overview.invoices.some((invoice) => invoice.statement_status === "ready")
      ? { title: "Approve a settlement", detail: "A reconciled invoice is ready for finance approval.", label: "Review invoices", path: "/workspace/invoices" }
      : activeDisputes.length
        ? { title: `Follow up on ${activeDisputes.length} vendor dispute${activeDisputes.length === 1 ? "" : "s"}`, detail: "Vendor action is still open after reconciliation.", label: "Open review queue", path: "/workspace/review" }
        : { title: "Run the next invoice control", detail: "Bring a vendor invoice through contract, evidence, verification, and commercial action.", label: "Start reconciliation", path: "/workspace/invoices/current" };

  return (
    <WorkspaceShell
      active="overview"
      workspaceId={overview.organization.name}
      busy={busy}
      onRefresh={() => void refresh()}
      onSignOut={signOut}
    >
      <Box className="workspace-page-frame">
        {error && <Alert severity="error">{error}</Alert>}

        <StatStrip items={[
          {
            label: "AI spend under review",
            value: money(overview.latest_invoice_totals.submitted_amount, currency),
            detail: `${overview.counts.invoices} invoice${overview.counts.invoices === 1 ? "" : "s"}`,
          },
          {
            label: "Unsupported exposure",
            value: money(overview.latest_invoice_totals.disputed_amount, currency),
            detail: "Contract-backed exceptions",
            emphasis: Number(overview.latest_invoice_totals.disputed_amount) > 0 ? "danger" : "neutral",
          },
          {
            label: "Needs attention",
            value: String(attentionCount),
            detail: money(overview.latest_invoice_totals.open_review_amount, currency) + " unresolved",
            emphasis: attentionCount > 0 ? "warning" : "neutral",
          },
        ]} />

        <Paper variant="outlined" className="recommended-action-panel">
          <Box>
            <Typography className="section-kicker">RECOMMENDED NEXT ACTION</Typography>
            <Typography variant="h5" fontWeight={760}>{nextAction.title}</Typography>
            <Typography color="text.secondary" sx={{ mt: 0.5 }}>{nextAction.detail}</Typography>
          </Box>
          <Button variant="contained" onClick={() => navigate(nextAction.path)}>{nextAction.label}</Button>
        </Paper>

        <Box className="workspace-section-heading">
          <Box>
            <Typography className="section-kicker">INVOICE QUEUE</Typography>
            <Typography variant="h5" fontWeight={760}>Recent vendor invoices</Typography>
            <Typography color="text.secondary">The financial object is the invoice. Open one to see its contract, evidence, verification, review, and commercial action.</Typography>
          </Box>
          <Button variant="outlined" onClick={() => navigate("/workspace/invoices")}>View all invoices</Button>
        </Box>

        <Paper variant="outlined" className="data-table-panel">
          {!overview.invoices.length ? (
            <Box className="empty-state">
              <Typography variant="h6" fontWeight={740}>No invoices yet</Typography>
              <Typography color="text.secondary">Start a reconciliation to create the first finance-control record.</Typography>
              <Button variant="contained" onClick={() => navigate("/workspace/invoices/current")}>Start reconciliation</Button>
            </Box>
          ) : (
            <TableContainer>
              <Table size="small" aria-label="Recent AI vendor invoices">
                <TableHead>
                  <TableRow>
                    <TableCell>Vendor</TableCell>
                    <TableCell>Billing period</TableCell>
                    <TableCell align="right">Billed</TableCell>
                    <TableCell align="right">Verified payable</TableCell>
                    <TableCell align="right">Exceptions</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell align="right" />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {overview.invoices.slice(0, 8).map((invoice) => (
                    <TableRow key={invoice.invoice_id} hover>
                      <TableCell><Typography fontWeight={700}>{invoice.vendor}</Typography><Typography variant="caption" color="text.secondary">{invoice.invoice_id}</Typography></TableCell>
                      <TableCell>{date(invoice.billing_period_start)} – {date(invoice.billing_period_end)}</TableCell>
                      <TableCell align="right">{money(invoice.submitted_amount, currency)}</TableCell>
                      <TableCell align="right">{invoice.recommended_payable_amount ? money(invoice.recommended_payable_amount, currency) : "—"}</TableCell>
                      <TableCell align="right">{money(Number(invoice.disputed_amount || 0) + Number(invoice.open_review_amount || 0), currency)}</TableCell>
                      <TableCell><InvoiceStatus invoice={invoice} /></TableCell>
                      <TableCell align="right"><Button size="small" onClick={() => navigate(`/workspace/invoices/${encodeURIComponent(invoice.invoice_id)}`)}>Open</Button></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>
      </Box>
    </WorkspaceShell>
  );
}

export function InvoiceQueuePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { overview, busy, error, refresh, signOut } = useWorkspaceData();
  const [query, setQuery] = useState(() => searchParams.get("query") ?? "");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(0);
  const rowsPerPage = 10;
  if (!overview) return <LoadingWorkspace active="invoices" />;
  const currency = overview.organization.currency || "USD";

  const filtered = overview.invoices.filter((invoice) => {
    const needle = query.trim().toLowerCase();
    const searchOk = !needle || `${invoice.vendor} ${invoice.invoice_id}`.toLowerCase().includes(needle);
    const statusOk = status === "all" || invoice.statement_status === status;
    return searchOk && statusOk;
  });
  const pageRows = filtered.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  return (
    <WorkspaceShell active="invoices" workspaceId={overview.organization.name} busy={busy} onRefresh={() => void refresh()} onSignOut={signOut}>
      <Box className="workspace-page-frame">
        {error && <Alert severity="error">{error}</Alert>}
        <Box className="workspace-section-heading">
          <Box>
            <Typography className="section-kicker">INVOICE CONTROL</Typography>
            <Typography variant="h5" fontWeight={760}>Vendor invoice register</Typography>
            <Typography color="text.secondary">Search by vendor or invoice ID, then open the record that needs work.</Typography>
          </Box>
          <Button variant="contained" onClick={() => navigate("/workspace/invoices/current")}>New reconciliation</Button>
        </Box>

        <Paper variant="outlined" className="table-toolbar">
          <TextField size="small" label="Search invoices" value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} />
          <FormControl size="small" sx={{ minWidth: 190 }}>
            <InputLabel>Status</InputLabel>
            <Select label="Status" value={status} onChange={(event) => { setStatus(event.target.value); setPage(0); }}>
              <MenuItem value="all">All statuses</MenuItem>
              <MenuItem value="not_reconciled">Needs verification</MenuItem>
              <MenuItem value="draft">Needs review</MenuItem>
              <MenuItem value="ready">Approval required</MenuItem>
              <MenuItem value="approved">Approved</MenuItem>
            </Select>
          </FormControl>
          <Typography variant="body2" color="text.secondary" sx={{ ml: { md: "auto" } }}>{filtered.length} invoice{filtered.length === 1 ? "" : "s"}</Typography>
        </Paper>

        <Paper variant="outlined" className="data-table-panel">
          <TableContainer>
            <Table size="small" aria-label="AI vendor invoice register">
              <TableHead>
                <TableRow>
                  <TableCell>Vendor / invoice</TableCell>
                  <TableCell>Billing period</TableCell>
                  <TableCell align="right">Billed</TableCell>
                  <TableCell align="right">Verified payable</TableCell>
                  <TableCell align="right">Disputed</TableCell>
                  <TableCell align="right">Needs review</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Next action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {pageRows.map((invoice) => (
                  <TableRow key={invoice.invoice_id} hover>
                    <TableCell><Typography fontWeight={700}>{invoice.vendor}</Typography><Typography variant="caption" color="text.secondary">{invoice.invoice_id}</Typography></TableCell>
                    <TableCell>{date(invoice.billing_period_start)} – {date(invoice.billing_period_end)}</TableCell>
                    <TableCell align="right">{money(invoice.submitted_amount, currency)}</TableCell>
                    <TableCell align="right">{invoice.recommended_payable_amount ? money(invoice.recommended_payable_amount, currency) : "—"}</TableCell>
                    <TableCell align="right">{money(invoice.disputed_amount, currency)}</TableCell>
                    <TableCell align="right">{money(invoice.open_review_amount, currency)}</TableCell>
                    <TableCell><InvoiceStatus invoice={invoice} /></TableCell>
                    <TableCell align="right"><Button size="small" variant={invoice.statement_status === "not_reconciled" ? "contained" : "text"} onClick={() => navigate(`/workspace/invoices/${encodeURIComponent(invoice.invoice_id)}`)}>{invoice.statement_status === "not_reconciled" ? "Continue" : "Open"}</Button></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <TablePagination component="div" count={filtered.length} page={page} onPageChange={(_, next) => setPage(next)} rowsPerPage={rowsPerPage} rowsPerPageOptions={[rowsPerPage]} />
        </Paper>
      </Box>
    </WorkspaceShell>
  );
}

type QueueFilter = "needs_review" | "approval_required" | "vendor_action" | "ready_to_settle";

type ReviewDialogState = {
  item: ProductReviewCase;
  decision: "payable" | "disputed" | "escalated";
} | null;

export function ReviewQueuePage() {
  const navigate = useNavigate();
  const { overview, reviews, disputes, busy, error, refresh, signOut } = useWorkspaceData();
  const [filter, setFilter] = useState<QueueFilter>("needs_review");
  const [dialog, setDialog] = useState<ReviewDialogState>(null);
  const [rationale, setRationale] = useState("");
  const [notice, setNotice] = useState("");
  if (!overview) return <LoadingWorkspace active="review" />;
  const currency = overview.organization.currency || "USD";
  const openReviews = reviews.filter((item) => ["open", "escalated"].includes(item.status));
  const approvalInvoices = overview.invoices.filter((item) => item.statement_status === "ready");
  const vendorActions = disputes.filter((item) => !["accepted", "rejected", "closed"].includes(item.status));
  const readyToSettle = overview.invoices.filter((item) => item.statement_status === "approved");

  async function decideReview() {
    if (!dialog || rationale.trim().length < 3) return;
    await pilotApi.productDecideReview(dialog.item.id, {
      decision: dialog.decision,
      rationale: rationale.trim(),
      decided_by: "finance-approver",
    });
    setNotice("Review decision recorded. The machine determination remains unchanged.");
    setDialog(null);
    setRationale("");
    await refresh();
  }

  const tabs: Array<{ id: QueueFilter; label: string; count: number }> = [
    { id: "needs_review", label: "Needs review", count: openReviews.length },
    { id: "approval_required", label: "Approval required", count: approvalInvoices.length },
    { id: "vendor_action", label: "Vendor action", count: vendorActions.length },
    { id: "ready_to_settle", label: "Ready to settle", count: readyToSettle.length },
  ];

  return (
    <WorkspaceShell active="review" workspaceId={overview.organization.name} busy={busy} onRefresh={() => void refresh()} onSignOut={signOut}>
      <Box className="workspace-page-frame">
        {error && <Alert severity="error">{error}</Alert>}
        {notice && <Alert severity="success" onClose={() => setNotice("")}>{notice}</Alert>}

        <Paper variant="outlined" className="queue-filter-bar">
          {tabs.map((tab) => (
            <Button key={tab.id} onClick={() => setFilter(tab.id)} aria-pressed={filter === tab.id} className={filter === tab.id ? "active" : ""}>
              <span>{tab.label}</span><Chip size="small" label={tab.count} />
            </Button>
          ))}
        </Paper>

        <Paper variant="outlined" className="data-table-panel">
          {filter === "needs_review" && (
            openReviews.length ? (
              <TableContainer><Table size="small" aria-label="Needs review queue"><TableHead><TableRow><TableCell>Claim</TableCell><TableCell>Why it needs judgment</TableCell><TableCell align="right">Exposure</TableCell><TableCell>Priority</TableCell><TableCell align="right">Decision</TableCell></TableRow></TableHead><TableBody>
                {openReviews.map((item) => <TableRow key={item.id} hover><TableCell><Typography fontWeight={700}>{item.outcome_id}</Typography><Typography variant="caption" color="text.secondary">{item.reason_code}</Typography></TableCell><TableCell>{item.reason}</TableCell><TableCell align="right">{money(item.exposure_amount, currency)}</TableCell><TableCell><Chip size="small" variant="outlined" label={readable(item.priority)} color={item.priority === "critical" || item.priority === "high" ? "error" : "default"} /></TableCell><TableCell align="right"><Stack direction="row" justifyContent="flex-end" spacing={0.5}><Button size="small" onClick={() => setDialog({ item, decision: "payable" })}>Pay</Button><Button size="small" color="error" onClick={() => setDialog({ item, decision: "disputed" })}>Dispute</Button><Button size="small" onClick={() => setDialog({ item, decision: "escalated" })}>Escalate</Button></Stack></TableCell></TableRow>)}
              </TableBody></Table></TableContainer>
            ) : <Box className="empty-state"><Typography variant="h6" fontWeight={740}>Nothing needs manual review</Typography><Typography color="text.secondary">Every current claim has enough evidence for a deterministic result.</Typography></Box>
          )}

          {filter === "approval_required" && (
            approvalInvoices.length ? (
              <TableContainer><Table size="small"><TableHead><TableRow><TableCell>Vendor</TableCell><TableCell>Period</TableCell><TableCell align="right">Payable</TableCell><TableCell align="right">Disputed</TableCell><TableCell align="right" /></TableRow></TableHead><TableBody>{approvalInvoices.map((invoice) => <TableRow key={invoice.invoice_id}><TableCell>{invoice.vendor}</TableCell><TableCell>{date(invoice.billing_period_start)} – {date(invoice.billing_period_end)}</TableCell><TableCell align="right">{money(invoice.recommended_payable_amount, currency)}</TableCell><TableCell align="right">{money(invoice.disputed_amount, currency)}</TableCell><TableCell align="right"><Button onClick={() => navigate(`/workspace/invoices/${encodeURIComponent(invoice.invoice_id)}`)}>Review settlement</Button></TableCell></TableRow>)}</TableBody></Table></TableContainer>
            ) : <Box className="empty-state"><Typography variant="h6" fontWeight={740}>No approvals waiting</Typography><Typography color="text.secondary">Reconciled invoices appear here once review exposure is resolved.</Typography></Box>
          )}

          {filter === "vendor_action" && (
            vendorActions.length ? (
              <TableContainer><Table size="small"><TableHead><TableRow><TableCell>Case</TableCell><TableCell>Subject</TableCell><TableCell align="right">Disputed</TableCell><TableCell>Status</TableCell><TableCell align="right" /></TableRow></TableHead><TableBody>{vendorActions.map((item) => <TableRow key={item.id}><TableCell>{item.case_number}</TableCell><TableCell>{item.subject}</TableCell><TableCell align="right">{money(item.disputed_amount, currency)}</TableCell><TableCell><Chip size="small" variant="outlined" label={readable(item.status)} color={statusTone(item.status)} /></TableCell><TableCell align="right"><Button onClick={() => navigate("/workspace/invoices")}>Open invoice</Button></TableCell></TableRow>)}</TableBody></Table></TableContainer>
            ) : <Box className="empty-state"><Typography variant="h6" fontWeight={740}>No vendor action open</Typography><Typography color="text.secondary">Dispute cases appear here after finance approves a settlement.</Typography></Box>
          )}

          {filter === "ready_to_settle" && (
            readyToSettle.length ? (
              <TableContainer><Table size="small"><TableHead><TableRow><TableCell>Vendor</TableCell><TableCell>Invoice</TableCell><TableCell align="right">Payable</TableCell><TableCell>Status</TableCell><TableCell align="right" /></TableRow></TableHead><TableBody>{readyToSettle.map((invoice) => <TableRow key={invoice.invoice_id}><TableCell>{invoice.vendor}</TableCell><TableCell>{invoice.invoice_id}</TableCell><TableCell align="right">{money(invoice.recommended_payable_amount, currency)}</TableCell><TableCell><Chip size="small" color="success" variant="outlined" label="Approved" /></TableCell><TableCell align="right"><Button onClick={() => navigate(`/workspace/invoices/${encodeURIComponent(invoice.invoice_id)}`)}>Open settlement</Button></TableCell></TableRow>)}</TableBody></Table></TableContainer>
            ) : <Box className="empty-state"><Typography variant="h6" fontWeight={740}>Nothing ready to settle</Typography><Typography color="text.secondary">Approved payable amounts appear here for AP handoff.</Typography></Box>
          )}
        </Paper>
      </Box>

      <Dialog open={Boolean(dialog)} onClose={() => setDialog(null)} fullWidth maxWidth="sm">
        <DialogTitle>{dialog ? `${readable(dialog.decision)} ${dialog.item.outcome_id}` : "Review decision"}</DialogTitle>
        <DialogContent>
          {dialog && <Stack spacing={1.5} sx={{ pt: 0.5 }}><Alert severity="info">This creates an append-only finance review decision. It does not rewrite the deterministic machine record.</Alert><Typography><strong>Exposure:</strong> {money(dialog.item.exposure_amount, currency)}</Typography><Typography color="text.secondary">{dialog.item.reason}</Typography><TextField label="Rationale" multiline minRows={3} value={rationale} onChange={(event) => setRationale(event.target.value)} helperText="Required for the audit trail." /></Stack>}
        </DialogContent>
        <DialogActions><Button onClick={() => setDialog(null)}>Cancel</Button><Button variant="contained" disabled={rationale.trim().length < 3} onClick={() => void decideReview()}>Record decision</Button></DialogActions>
      </Dialog>
    </WorkspaceShell>
  );
}

export function VendorsPage() {
  const navigate = useNavigate();
  const { overview, busy, error, refresh, signOut } = useWorkspaceData();
  if (!overview) return <LoadingWorkspace active="vendors" />;
  const currency = overview.organization.currency || "USD";
  return (
    <WorkspaceShell active="vendors" workspaceId={overview.organization.name} busy={busy} onRefresh={() => void refresh()} onSignOut={signOut}>
      <Box className="workspace-page-frame">
        {error && <Alert severity="error">{error}</Alert>}
        <Box className="workspace-section-heading"><Box><Typography className="section-kicker">VENDOR HISTORY</Typography><Typography variant="h5" fontWeight={760}>AI vendor controls</Typography><Typography color="text.secondary">Compare spend, verified payable amounts, disputed exposure, and open reviews by vendor.</Typography></Box></Box>
        <Paper variant="outlined" className="data-table-panel">
          <TableContainer><Table size="small"><TableHead><TableRow><TableCell>Vendor</TableCell><TableCell align="right">Invoices</TableCell><TableCell align="right">Billed</TableCell><TableCell align="right">Verified payable</TableCell><TableCell align="right">Disputed</TableCell><TableCell align="right">Open reviews</TableCell><TableCell>Status</TableCell><TableCell /></TableRow></TableHead><TableBody>
            {overview.vendors.map((vendor) => <TableRow key={vendor.id} hover><TableCell><Typography fontWeight={700}>{vendor.name}</Typography><Typography variant="caption" color="text.secondary">{vendor.contracts} contract{vendor.contracts === 1 ? "" : "s"}</Typography></TableCell><TableCell align="right">{vendor.invoices}</TableCell><TableCell align="right">{money(vendor.submitted_amount, currency)}</TableCell><TableCell align="right">{money(vendor.machine_payable_amount, currency)}</TableCell><TableCell align="right">{money(vendor.machine_disputed_amount, currency)}</TableCell><TableCell align="right">{vendor.open_review_cases}</TableCell><TableCell><Chip size="small" variant="outlined" label={readable(vendor.status)} color={statusTone(vendor.status)} /></TableCell><TableCell><Button size="small" onClick={() => navigate(`/workspace/invoices?query=${encodeURIComponent(vendor.name)}`)}>Invoices</Button></TableCell></TableRow>)}
          </TableBody></Table></TableContainer>
        </Paper>
      </Box>
    </WorkspaceShell>
  );
}

export function InvoiceRecordPage() {
  const navigate = useNavigate();
  const { invoiceId = "" } = useParams();
  const { overview, reviews, disputes, busy, error, refresh, signOut } = useWorkspaceData();
  const [statement, setStatement] = useState<ProductStatement | null>(null);
  const [trust, setTrust] = useState<ProductTrust | null>(null);
  const [status, setStatus] = useState<"summary" | "review" | "action" | "audit">("summary");
  const [approvalBy, setApprovalBy] = useState("finance-approver");
  const [approvalNote, setApprovalNote] = useState("");
  const [notice, setNotice] = useState("");
  const decodedId = decodeURIComponent(invoiceId);
  const invoice = overview?.invoices.find((item) => item.invoice_id === decodedId) ?? null;

  useEffect(() => {
    if (!invoice?.latest_run_id) {
      setStatement(null);
      setTrust(null);
      return;
    }
    void Promise.all([pilotApi.productStatement(invoice.latest_run_id), pilotApi.productTrust(invoice.latest_run_id)])
      .then(([nextStatement, nextTrust]) => { setStatement(nextStatement); setTrust(nextTrust); })
      .catch(() => { setStatement(null); setTrust(null); });
  }, [invoice?.latest_run_id]);

  if (!overview) return <LoadingWorkspace active="invoices" />;
  if (!invoice) {
    return <WorkspaceShell active="invoices" workspaceId={overview.organization.name} onSignOut={signOut}><Box className="workspace-page-frame"><Alert severity="warning">That invoice is not available in this workspace.</Alert><Button onClick={() => navigate("/workspace/invoices")}>Back to invoices</Button></Box></WorkspaceShell>;
  }
  const currency = overview.organization.currency || "USD";
  const runReviews = invoice.latest_run_id ? reviews.filter((item) => item.run_id === invoice.latest_run_id) : [];
  const runDisputes = invoice.latest_run_id ? disputes.filter((item) => item.run_id === invoice.latest_run_id) : [];
  const factualState = Number(invoice.open_review_amount || 0) > 0 ? "Insufficient evidence" : Number(invoice.disputed_amount || 0) > 0 ? "Contradicted claims found" : invoice.latest_run_id ? "Substantiated" : "Not verified";
  const commercialAction = invoice.statement_status === "not_reconciled"
    ? "Complete verification"
    : invoice.statement_status === "draft"
      ? "Resolve review exposure"
      : invoice.statement_status === "ready"
        ? "Approve settlement"
        : Number(invoice.disputed_amount || 0) > 0
          ? "Send vendor dispute"
          : "Pay approved amount";

  async function approve() {
    if (!statement) return;
    const result = await pilotApi.productApprove(statement.run_id, { approved_by: approvalBy, note: approvalNote });
    setStatement(result.statement);
    setNotice(`Approved ${money(result.approval.approved_payable_amount, currency)} payable.`);
    await refresh();
  }

  async function createDispute() {
    if (!statement) return;
    const created = await pilotApi.productCreateDispute(statement.run_id, { created_by: approvalBy });
    setNotice(`${created.case_number} opened for ${money(created.disputed_amount, currency)}.`);
    await refresh();
    setStatus("action");
  }

  return (
    <WorkspaceShell active="invoices" workspaceId={overview.organization.name} busy={busy} onRefresh={() => void refresh()} onSignOut={signOut}>
      <Box className="invoice-case-page">
        {error && <Alert severity="error">{error}</Alert>}
        {notice && <Alert severity="success" onClose={() => setNotice("")}>{notice}</Alert>}

        <Box className="invoice-case-header">
          <Box>
            <Button size="small" onClick={() => navigate("/workspace/invoices")} sx={{ mb: 1 }}>← All invoices</Button>
            <Typography className="section-kicker">INVOICE REVIEW</Typography>
            <Typography variant="h4" fontWeight={780}>{invoice.vendor} · {invoice.invoice_id}</Typography>
            <Typography color="text.secondary">{date(invoice.billing_period_start)} – {date(invoice.billing_period_end)}</Typography>
          </Box>
          <InvoiceStatus invoice={invoice} />
          <Box className="invoice-case-numbers">
            <Box><span>Vendor billed</span><strong>{money(invoice.submitted_amount, currency)}</strong></Box>
            <Box><span>Verified payable</span><strong>{invoice.recommended_payable_amount ? money(invoice.recommended_payable_amount, currency) : "—"}</strong></Box>
            <Box><span>Exception amount</span><strong>{money(Number(invoice.disputed_amount || 0) + Number(invoice.open_review_amount || 0), currency)}</strong></Box>
          </Box>
        </Box>

        <Box className="case-lifecycle" role="navigation" aria-label="Invoice record sections">
          {(["summary", "review", "action", "audit"] as const).map((item) => <Button key={item} className={status === item ? "active" : ""} aria-pressed={status === item} onClick={() => setStatus(item)}>{item === "action" ? "Commercial action" : readable(item)}</Button>)}
        </Box>

        {status === "summary" && <Stack spacing={2}>
          <Paper variant="outlined" className="decision-separation-panel">
            <Box><Typography className="section-kicker">WHAT HAPPENED</Typography><Typography variant="h6" fontWeight={760}>{factualState}</Typography><Typography color="text.secondary">This is the evidence-backed factual determination. It does not itself decide the contractual remedy.</Typography></Box>
            <Divider orientation="vertical" flexItem />
            <Box><Typography className="section-kicker">WHAT FINANCE CAN DO</Typography><Typography variant="h6" fontWeight={760}>{commercialAction}</Typography><Typography color="text.secondary">The commercial action depends on the approved agreement, review state, and settlement authority.</Typography></Box>
          </Paper>
          {invoice.statement_status === "not_reconciled" && <Paper variant="outlined" className="recommended-action-panel"><Box><Typography className="section-kicker">NEXT STEP</Typography><Typography variant="h6" fontWeight={760}>Complete the active verification case</Typography><Typography color="text.secondary">Review contract rules, invoice mapping, customer evidence, and deterministic verification.</Typography></Box><Button variant="contained" onClick={() => navigate("/workspace/invoices/current")}>Continue verification</Button></Paper>}
          {statement && <StatStrip items={[
            { label: "Vendor billed", value: money(statement.submitted_amount, currency), detail: "Submitted invoice" },
            { label: "Verified payable", value: money(statement.recommended_final_payable_amount, currency), detail: statement.status === "approved" ? "Approved" : "Recommended" },
            { label: "Identified for dispute", value: money(statement.recommended_final_disputed_amount, currency), detail: "Contract-backed exceptions", emphasis: Number(statement.recommended_final_disputed_amount) > 0 ? "danger" : "neutral" },
            { label: "Needs review", value: money(statement.open_review_amount, currency), detail: `${runReviews.filter((item) => ["open", "escalated"].includes(item.status)).length} open cases`, emphasis: Number(statement.open_review_amount) > 0 ? "warning" : "neutral" },
          ]} />}
        </Stack>}

        {status === "review" && <Paper variant="outlined" className="data-table-panel">
          {!runReviews.length ? <Box className="empty-state"><Typography variant="h6" fontWeight={740}>No manual review cases</Typography><Typography color="text.secondary">This invoice has no unresolved finance review overlay.</Typography></Box> : <TableContainer><Table size="small"><TableHead><TableRow><TableCell>Claim</TableCell><TableCell>Reason</TableCell><TableCell align="right">Exposure</TableCell><TableCell>Status</TableCell></TableRow></TableHead><TableBody>{runReviews.map((item) => <TableRow key={item.id}><TableCell>{item.outcome_id}</TableCell><TableCell>{item.reason}</TableCell><TableCell align="right">{money(item.exposure_amount, currency)}</TableCell><TableCell><Chip size="small" variant="outlined" label={readable(item.status)} color={statusTone(item.status)} /></TableCell></TableRow>)}</TableBody></Table></TableContainer>}
        </Paper>}

        {status === "action" && <Stack spacing={2}>
          {!statement ? <Alert severity="info">Complete reconciliation before a commercial action is available.</Alert> : <>
            <Paper variant="outlined" className="action-panel">
              <Box><Typography className="section-kicker">SETTLEMENT</Typography><Typography variant="h5" fontWeight={760}>{statement.status === "approved" ? "Settlement approved" : statement.status === "ready" ? "Ready for approval" : "Review exposure first"}</Typography><Typography color="text.secondary" sx={{ mt: 0.5 }}>Finance authority is applied after deterministic verification; the underlying machine result remains immutable.</Typography></Box>
              {statement.status === "ready" && <Box className="action-form"><TextField size="small" label="Approver" value={approvalBy} onChange={(event) => setApprovalBy(event.target.value)} /><TextField size="small" label="Approval note" value={approvalNote} onChange={(event) => setApprovalNote(event.target.value)} /><Button variant="contained" onClick={() => void approve()}>Approve {money(statement.recommended_final_payable_amount, currency)} payable</Button></Box>}
              {statement.status === "draft" && <Alert severity="warning">Resolve {money(statement.open_review_amount, currency)} in the Review queue before approval.</Alert>}
              {statement.status === "approved" && Number(statement.recommended_final_disputed_amount) > 0 && !runDisputes.length && <Button color="error" variant="outlined" onClick={() => void createDispute()}>Open vendor dispute for {money(statement.recommended_final_disputed_amount, currency)}</Button>}
            </Paper>
            {runDisputes.map((item) => <Paper key={item.id} variant="outlined" className="action-panel"><Box><Typography className="section-kicker">VENDOR ACTION</Typography><Typography variant="h6" fontWeight={760}>{item.case_number} · {readable(item.status)}</Typography><Typography color="text.secondary">{item.item_count} claims · {money(item.disputed_amount, currency)}</Typography></Box></Paper>)}
          </>}
        </Stack>}

        {status === "audit" && <Paper variant="outlined" className="audit-disclosure"><Typography className="section-kicker">TECHNICAL DETAILS</Typography><Typography variant="h6" fontWeight={760}>Reproducibility and authority</Typography><Typography color="text.secondary" sx={{ mb: 2 }}>Technical fingerprints are available when finance, audit, or engineering needs to reproduce the settlement.</Typography><Box className="audit-grid"><Box><span>Approved rule-set hash</span><code>{trust?.agreement?.payload_hash ?? "—"}</code></Box><Box><span>Evidence/input manifest</span><code>{trust?.input_manifest_hash ?? "—"}</code></Box><Box><span>Kernel calculation</span><code>{trust?.kernel_calculation_hash ?? "—"}</code></Box><Box><span>Settlement calculation</span><code>{trust?.settlement_calculation_hash ?? statement?.calculation_hash ?? "—"}</code></Box></Box></Paper>}
      </Box>
    </WorkspaceShell>
  );
}
