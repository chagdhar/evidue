import {
  Alert,
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
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import WorkspaceShell from "./WorkspaceShell";
import {
  clearPilotToken,
  loadPilotToken,
  pilotApi,
  ProductDisputeCase,
  ProductDisputeStatus,
  ProductInvoice,
  ProductOverview,
  ProductReviewCase,
  ProductStatement,
  ProductTrust,
} from "./pilotApi";

type Section = "overview" | "vendors" | "reviews" | "settlements" | "disputes";

type ReviewDialogState = {
  item: ProductReviewCase;
  decision: "payable" | "disputed" | "escalated";
} | null;

function money(value: string | number | null | undefined, currency = "USD") {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(
    Number(value ?? 0),
  );
}

function date(value: string | null | undefined) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function statusColor(status: string): "default" | "success" | "warning" | "error" | "info" {
  if (["approved", "accepted", "resolved_payable"].includes(status)) return "success";
  if (["draft", "open", "escalated", "vendor_responded", "under_review"].includes(status)) {
    return "warning";
  }
  if (["resolved_disputed", "rejected"].includes(status)) return "error";
  return "info";
}

function Metric({ label, value, helper }: { label: string; value: string; helper?: string }) {
  return (
    <Card sx={{ minWidth: 0 }}>
      <CardContent>
        <Typography variant="body2" color="text.secondary">{label}</Typography>
        <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 780 }}>{value}</Typography>
        {helper && <Typography variant="caption" color="text.secondary">{helper}</Typography>}
      </CardContent>
    </Card>
  );
}

function HashRow({ label, value }: { label: string; value: string | null }) {
  return (
    <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "210px 1fr" }, gap: 1, py: 0.75 }}>
      <Typography variant="body2" color="text.secondary">{label}</Typography>
      <Typography component="code" variant="caption" sx={{ overflowWrap: "anywhere" }}>{value ?? "—"}</Typography>
    </Box>
  );
}

export default function FinanceWorkspace() {
  const navigate = useNavigate();
  const [section, setSection] = useState<Section>("overview");
  const [overview, setOverview] = useState<ProductOverview | null>(null);
  const [reviews, setReviews] = useState<ProductReviewCase[]>([]);
  const [disputes, setDisputes] = useState<ProductDisputeCase[]>([]);
  const [statement, setStatement] = useState<ProductStatement | null>(null);
  const [trust, setTrust] = useState<ProductTrust | null>(null);
  const [selectedInvoice, setSelectedInvoice] = useState<ProductInvoice | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reviewDialog, setReviewDialog] = useState<ReviewDialogState>(null);
  const [reviewRationale, setReviewRationale] = useState("");
  const [approvalBy, setApprovalBy] = useState("finance-approver");
  const [approvalNote, setApprovalNote] = useState("");
  const [disputeStatus, setDisputeStatus] = useState<Record<string, ProductDisputeStatus>>({});
  const [vendorResponse, setVendorResponse] = useState<Record<string, string>>({});

  const refresh = useCallback(async () => {
    if (!loadPilotToken()) {
      navigate("/workspace");
      return;
    }
    setBusy("Loading finance operations");
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
      setError(requestError instanceof Error ? requestError.message : "Could not load finance operations");
    } finally {
      setBusy("");
    }
  }, [navigate]);

  useEffect(() => { void refresh(); }, [refresh]);

  const currency = overview?.organization.currency || "USD";
  const openReviews = useMemo(
    () => reviews.filter((item) => item.status === "open" || item.status === "escalated"),
    [reviews],
  );

  async function openSettlement(invoice: ProductInvoice) {
    if (!invoice.latest_run_id) return;
    setBusy("Loading settlement statement");
    setError("");
    try {
      const [nextStatement, nextTrust] = await Promise.all([
        pilotApi.productStatement(invoice.latest_run_id),
        pilotApi.productTrust(invoice.latest_run_id),
      ]);
      setSelectedInvoice(invoice);
      setStatement(nextStatement);
      setTrust(nextTrust);
      setSection("settlements");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load settlement");
    } finally {
      setBusy("");
    }
  }

  async function decideReview() {
    if (!reviewDialog || reviewRationale.trim().length < 3) return;
    setBusy("Recording review decision");
    setError("");
    try {
      await pilotApi.productDecideReview(reviewDialog.item.id, {
        decision: reviewDialog.decision,
        rationale: reviewRationale.trim(),
        decided_by: approvalBy,
      });
      setReviewDialog(null);
      setReviewRationale("");
      setNotice("Review decision recorded without changing the machine determination.");
      await refresh();
      if (statement?.run_id === reviewDialog.item.run_id && selectedInvoice) {
        await openSettlement(selectedInvoice);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not record review decision");
    } finally {
      setBusy("");
    }
  }

  async function approveSettlement() {
    if (!statement) return;
    setBusy("Approving payable amount");
    setError("");
    try {
      const result = await pilotApi.productApprove(statement.run_id, {
        approved_by: approvalBy,
        note: approvalNote,
      });
      setStatement(result.statement);
      setNotice(`Approved ${money(result.approval.approved_payable_amount, currency)} payable.`);
      await refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Approval failed");
    } finally {
      setBusy("");
    }
  }

  async function createDispute() {
    if (!statement) return;
    setBusy("Opening vendor dispute");
    setError("");
    try {
      const created = await pilotApi.productCreateDispute(statement.run_id, {
        created_by: approvalBy,
      });
      setNotice(`${created.case_number} opened with ${created.item_count} disputed lines.`);
      await refresh();
      setSection("disputes");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not create dispute");
    } finally {
      setBusy("");
    }
  }

  async function transitionDispute(item: ProductDisputeCase) {
    const next = disputeStatus[item.id];
    if (!next) return;
    setBusy(`Updating ${item.case_number}`);
    setError("");
    try {
      await pilotApi.productTransitionDispute(item.id, {
        status: next,
        vendor_response: vendorResponse[item.id] || undefined,
      });
      setNotice(`${item.case_number} moved to ${next.replaceAll("_", " ")}.`);
      await refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not update dispute");
    } finally {
      setBusy("");
    }
  }

  async function downloadDispute(item: ProductDisputeCase) {
    setBusy(`Preparing ${item.case_number} PDF`);
    setError("");
    try {
      await pilotApi.downloadProductDispute(item.id);
      setNotice(`${item.case_number} PDF package downloaded.`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not export dispute package");
    } finally {
      setBusy("");
    }
  }

  if (!overview && busy) {
    return <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center" }}><CircularProgress /></Box>;
  }

  return (
    <WorkspaceShell
      active="operations"
      workspaceId={overview?.organization.name ?? "Workspace"}
      busy={busy}
      onRefresh={() => void refresh()}
      onSignOut={() => { clearPilotToken(); navigate("/workspace"); }}
    >
      <Container maxWidth="xl" sx={{ py: { xs: 2.5, md: 3.5 } }}>
        <Stack spacing={2.5}>
          <Paper
            variant="outlined"
            sx={{
              overflow: "hidden",
              borderRadius: 3,
              borderColor: "#2B333E",
              bgcolor: "#11161E",
              backgroundImage: "radial-gradient(circle at 90% 0%, rgba(124,92,252,.18), transparent 32%)",
            }}
          >
            <Box sx={{ p: { xs: 2.5, md: 3.25 }, display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(0,1.35fr) minmax(260px,.65fr)" }, gap: 3, alignItems: "end" }}>
              <Box>
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                  <Chip size="small" label="FINANCE OPERATIONS" sx={{ color: "#B7ABFF", bgcolor: "rgba(124,92,252,.10)", border: "1px solid rgba(124,92,252,.25)", letterSpacing: ".06em", fontSize: 10 }} />
                  <Typography variant="caption" sx={{ color: "#6F7C8D" }}>{overview?.organization.name ?? "Customer workspace"}</Typography>
                </Stack>
                <Typography variant="h3" fontWeight={800}>Invoice control center</Typography>
                <Typography sx={{ mt: 0.8, color: "#8E9AAA", maxWidth: 760 }}>
                  Review exceptions, approve supported payable amounts, and manage vendor disputes without changing the deterministic reconciliation record.
                </Typography>
              </Box>
              <Box sx={{ borderLeft: { md: "1px solid #2B333E" }, pl: { md: 3 } }}>
                <Typography variant="overline" sx={{ color: "#6F7C8D" }}>Open review exposure</Typography>
                <Typography variant="h3" sx={{ mt: 0.25, color: overview?.latest_invoice_totals.open_review_amount && Number(overview.latest_invoice_totals.open_review_amount) > 0 ? "#FFD694" : "#A9EEC9", fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>
                  {money(overview?.latest_invoice_totals.open_review_amount, currency)}
                </Typography>
                <Typography variant="caption" sx={{ color: "#748093" }}>{overview?.counts.open_review_cases ?? 0} review case(s) · {overview?.counts.active_disputes ?? 0} active dispute(s)</Typography>
              </Box>
            </Box>
          </Paper>

          {error && <Alert severity="error" onClose={() => setError("")}>{error}</Alert>}
          {notice && <Alert severity="success" onClose={() => setNotice("")}>{notice}</Alert>}

          <Paper variant="outlined" sx={{ px: 1, borderRadius: 2.25, bgcolor: "#11161E", borderColor: "#2B333E" }}>
            <Tabs value={section} onChange={(_, value: Section) => setSection(value)} variant="scrollable" scrollButtons="auto" aria-label="Finance operation views">
            <Tab value="overview" label="Overview" />
            <Tab value="vendors" label="Vendors" />
            <Tab value="reviews" label={`Review queue${openReviews.length ? ` (${openReviews.length})` : ""}`} />
            <Tab value="settlements" label="Settlement approval" />
            <Tab value="disputes" label={`Disputes${disputes.length ? ` (${disputes.length})` : ""}`} />
            </Tabs>
          </Paper>

          {section === "overview" && overview && (
            <Stack spacing={2}>
              <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(4, 1fr)" }, gap: 1.5 }}>
                <Metric label="Latest invoices" value={money(overview.latest_invoice_totals.submitted_amount, currency)} helper={`${overview.counts.invoices} invoice records`} />
                <Metric label="Recommended payable" value={money(overview.latest_invoice_totals.recommended_payable_amount, currency)} helper={`${overview.counts.approvals} approved settlements`} />
                <Metric label="Disputed" value={money(overview.latest_invoice_totals.disputed_amount, currency)} helper={`${overview.counts.active_disputes} active dispute cases`} />
                <Metric label="Awaiting review" value={money(overview.latest_invoice_totals.open_review_amount, currency)} helper={`${overview.counts.open_review_cases} review cases`} />
              </Box>
              <Card><CardContent>
                <Typography variant="h6" fontWeight={750}>Operating queue</Typography>
                <Typography color="text.secondary" sx={{ mb: 2 }}>Each invoice advances from deterministic reconciliation to exception review, approval, and dispute.</Typography>
                {!overview.invoices.length && <Alert severity="info" sx={{ mb: 2 }}>No invoices are available yet. Import and reconcile an invoice in Reconciliation to create the first finance work item.</Alert>}
                <TableContainer><Table size="small"><TableHead><TableRow><TableCell>Vendor</TableCell><TableCell>Period</TableCell><TableCell>Invoice</TableCell><TableCell align="right">Submitted</TableCell><TableCell align="right">Payable</TableCell><TableCell align="right">Review</TableCell><TableCell>Status</TableCell><TableCell /></TableRow></TableHead><TableBody>
                  {overview.invoices.map((invoice) => <TableRow key={invoice.invoice_id}><TableCell>{invoice.vendor}</TableCell><TableCell>{date(invoice.billing_period_start)} – {date(invoice.billing_period_end)}</TableCell><TableCell><Typography component="code" variant="caption">{invoice.invoice_id}</Typography></TableCell><TableCell align="right">{invoice.submitted_amount ? money(invoice.submitted_amount, currency) : "—"}</TableCell><TableCell align="right">{invoice.recommended_payable_amount ? money(invoice.recommended_payable_amount, currency) : "—"}</TableCell><TableCell align="right">{invoice.open_review_amount ? money(invoice.open_review_amount, currency) : "—"}</TableCell><TableCell><Chip size="small" label={invoice.statement_status.replaceAll("_", " ")} color={statusColor(invoice.statement_status)} /></TableCell><TableCell>{invoice.latest_run_id && <Button size="small" onClick={() => void openSettlement(invoice)}>Open</Button>}</TableCell></TableRow>)}
                </TableBody></Table></TableContainer>
              </CardContent></Card>
            </Stack>
          )}

          {section === "vendors" && overview && (
            <Card><CardContent>
              <Typography variant="h5" fontWeight={750}>Vendor engagements</Typography>
              <Typography color="text.secondary" sx={{ mb: 2 }}>Recurring commercial relationships, not a single active invoice.</Typography>
              {!overview.vendors.length && <Alert severity="info" sx={{ mb: 2 }}>No vendor engagements exist yet. Add an agreement in Reconciliation to create one automatically.</Alert>}
              <TableContainer><Table><TableHead><TableRow><TableCell>Vendor</TableCell><TableCell>Contracts</TableCell><TableCell>Invoices</TableCell><TableCell align="right">Submitted</TableCell><TableCell align="right">Machine payable</TableCell><TableCell align="right">Disputed</TableCell><TableCell>Open reviews</TableCell></TableRow></TableHead><TableBody>
                {overview.vendors.map((vendor) => <TableRow key={vendor.id}><TableCell><Typography fontWeight={700}>{vendor.name}</Typography><Chip size="small" label={vendor.status} color="success" variant="outlined" /></TableCell><TableCell>{vendor.contracts}</TableCell><TableCell>{vendor.invoices}</TableCell><TableCell align="right">{money(vendor.submitted_amount, currency)}</TableCell><TableCell align="right">{money(vendor.machine_payable_amount, currency)}</TableCell><TableCell align="right">{money(vendor.machine_disputed_amount, currency)}</TableCell><TableCell>{vendor.open_review_cases}</TableCell></TableRow>)}
              </TableBody></Table></TableContainer>
            </CardContent></Card>
          )}

          {section === "reviews" && (
            <Card><CardContent>
              <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" spacing={1} sx={{ mb: 2 }}>
                <Box><Typography variant="h5" fontWeight={750}>Exception review queue</Typography><Typography color="text.secondary">Human judgment is recorded separately from the deterministic result.</Typography></Box>
                <Chip label={`${openReviews.length} unresolved`} color={openReviews.length ? "warning" : "success"} />
              </Stack>
              {!reviews.length && <Alert severity="success" sx={{ mb: 2 }}>There are no finance review cases in this workspace.</Alert>}
              <TableContainer><Table><TableHead><TableRow><TableCell>Outcome</TableCell><TableCell>Reason</TableCell><TableCell>Priority</TableCell><TableCell align="right">Exposure</TableCell><TableCell>Status</TableCell><TableCell>Decision</TableCell></TableRow></TableHead><TableBody>
                {reviews.map((item) => <TableRow key={item.id}><TableCell><Typography component="code" variant="caption">{item.outcome_id}</Typography></TableCell><TableCell><Typography fontWeight={650}>{item.reason_code}</Typography><Typography variant="body2" color="text.secondary">{item.reason}</Typography></TableCell><TableCell><Chip size="small" label={item.priority} color={item.priority === "critical" || item.priority === "high" ? "error" : "default"} /></TableCell><TableCell align="right">{money(item.exposure_amount, currency)}</TableCell><TableCell><Chip size="small" label={item.status.replaceAll("_", " ")} color={statusColor(item.status)} /></TableCell><TableCell>{item.status === "open" || item.status === "escalated" ? <Stack direction="row" spacing={0.5}><Button size="small" color="success" onClick={() => setReviewDialog({ item, decision: "payable" })}>Pay</Button><Button size="small" color="error" onClick={() => setReviewDialog({ item, decision: "disputed" })}>Dispute</Button><Button size="small" onClick={() => setReviewDialog({ item, decision: "escalated" })}>Escalate</Button></Stack> : <Typography variant="caption">{item.latest_decision?.decision ?? "Resolved"}</Typography>}</TableCell></TableRow>)}
              </TableBody></Table></TableContainer>
            </CardContent></Card>
          )}

          {section === "settlements" && (
            <Stack spacing={2}>
              {!statement ? <Alert severity="info">Open a reconciled invoice from Overview to inspect and approve its settlement statement.</Alert> : <>
                <Card><CardContent>
                  <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={2}>
                    <Box><Typography variant="overline" color="text.secondary">Final reconciliation statement</Typography><Typography variant="h4" fontWeight={800}>{selectedInvoice?.vendor ?? "Vendor"} · {statement.invoice_id}</Typography><Typography color="text.secondary">Run {statement.run_id}</Typography></Box>
                    <Chip label={statement.status} color={statusColor(statement.status)} />
                  </Stack>
                  <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" }, gap: 1.5, mt: 2 }}>
                    <Metric label="Submitted" value={money(statement.submitted_amount, currency)} />
                    <Metric label="Recommended payable" value={money(statement.recommended_final_payable_amount, currency)} />
                    <Metric label="Disputed" value={money(statement.recommended_final_disputed_amount, currency)} />
                    <Metric label="Open review" value={money(statement.open_review_amount, currency)} />
                  </Box>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="h6" fontWeight={700}>Review overlay</Typography>
                  <Typography variant="body2" color="text.secondary">Machine payable {money(statement.machine_payable_amount, currency)} + reviewed payable {money(statement.review_resolved_payable_amount, currency)}. Machine disputed {money(statement.machine_disputed_amount, currency)} + reviewed disputed {money(statement.review_resolved_disputed_amount, currency)}.</Typography>
                </CardContent></Card>
                <Card><CardContent>
                  <Typography variant="h6" fontWeight={700}>Reproducibility & authority</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>These fingerprints bind the approved agreement, evidence manifest, deterministic kernel output, and review overlay to the settlement dollars.</Typography>
                  <HashRow label="AIR payload hash" value={trust?.agreement?.payload_hash ?? null} />
                  <HashRow label="Evidence/input manifest" value={trust?.input_manifest_hash ?? null} />
                  <HashRow label="Kernel calculation" value={trust?.kernel_calculation_hash ?? null} />
                  <HashRow label="Settlement calculation" value={trust?.settlement_calculation_hash ?? statement.calculation_hash} />
                </CardContent></Card>
                <Card><CardContent>
                  <Typography variant="h6" fontWeight={700}>Finance authority</Typography>
                  {statement.approval ? <Alert severity="success" sx={{ mt: 1 }}>Approved {money(statement.approval.approved_payable_amount, currency)} by {statement.approval.approved_by} on {date(statement.approval.approved_at)}.</Alert> : <Stack spacing={1.25} sx={{ mt: 1.5 }}><TextField label="Approver" value={approvalBy} onChange={(event) => setApprovalBy(event.target.value)} /><TextField label="Approval note" value={approvalNote} onChange={(event) => setApprovalNote(event.target.value)} multiline minRows={2} /><Button variant="contained" disabled={statement.status !== "ready" || Boolean(busy)} onClick={() => void approveSettlement()}>Approve {money(statement.recommended_final_payable_amount, currency)} payable</Button>{statement.status === "draft" && <Alert severity="warning">Resolve {money(statement.open_review_amount, currency)} of review exposure before payment approval.</Alert>}</Stack>}
                  {statement.status === "approved" && <Button sx={{ mt: 1.5 }} variant="outlined" color="error" onClick={() => void createDispute()}>Open vendor dispute for {money(statement.recommended_final_disputed_amount, currency)}</Button>}
                </CardContent></Card>
              </>}
            </Stack>
          )}

          {section === "disputes" && (
            <Stack spacing={2}>
              {!disputes.length && <Alert severity="info">No vendor dispute cases yet. Approve a settlement, then open a dispute from Settlement approval.</Alert>}
              {disputes.map((item) => <Card key={item.id}><CardContent>
                <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={2}><Box><Typography variant="overline" color="text.secondary">{item.case_number}</Typography><Typography variant="h5" fontWeight={750}>{item.subject}</Typography><Typography color="text.secondary">{item.item_count} lines · {money(item.disputed_amount, currency)}</Typography></Box><Chip label={item.status.replaceAll("_", " ")} color={statusColor(item.status)} /></Stack>
                <Divider sx={{ my: 2 }} />
                <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "2fr 1fr auto" }, gap: 1.25, alignItems: "start" }}>
                  <TextField label="Vendor response / case note" value={vendorResponse[item.id] ?? item.vendor_response} onChange={(event) => setVendorResponse((current) => ({ ...current, [item.id]: event.target.value }))} multiline minRows={2} />
                  <FormControl fullWidth><InputLabel>Next status</InputLabel><Select label="Next status" value={disputeStatus[item.id] ?? ""} onChange={(event) => setDisputeStatus((current) => ({ ...current, [item.id]: event.target.value as ProductDisputeStatus }))}>{["ready", "sent", "vendor_responded", "under_review", "accepted", "partially_accepted", "rejected", "closed"].map((status) => <MenuItem key={status} value={status}>{status.replaceAll("_", " ")}</MenuItem>)}</Select></FormControl>
                  <Stack spacing={0.75}><Button variant="contained" disabled={!disputeStatus[item.id] || Boolean(busy)} onClick={() => void transitionDispute(item)}>Update case</Button><Button variant="outlined" disabled={Boolean(busy)} onClick={() => void downloadDispute(item)}>Export PDF package</Button></Stack>
                </Box>
                {item.vendor_response && <Alert severity="info" sx={{ mt: 1.5 }}>Vendor response recorded {date(item.vendor_response_at)}: {item.vendor_response}</Alert>}
                <TableContainer sx={{ mt: 2 }}><Table size="small"><TableHead><TableRow><TableCell>Outcome</TableCell><TableCell>Reason</TableCell><TableCell>Source</TableCell><TableCell align="right">Amount</TableCell></TableRow></TableHead><TableBody>{item.items.slice(0, 25).map((line) => <TableRow key={line.id}><TableCell>{line.outcome_id}</TableCell><TableCell>{line.reason_code}<Typography variant="caption" display="block" color="text.secondary">{line.reason}</Typography></TableCell><TableCell>{line.source}</TableCell><TableCell align="right">{money(line.amount, currency)}</TableCell></TableRow>)}</TableBody></Table></TableContainer>
              </CardContent></Card>)}
            </Stack>
          )}
        </Stack>
      </Container>

      <Dialog open={Boolean(reviewDialog)} onClose={() => setReviewDialog(null)} fullWidth maxWidth="sm">
        <DialogTitle>{reviewDialog ? `${reviewDialog.decision === "payable" ? "Approve" : reviewDialog.decision === "disputed" ? "Dispute" : "Escalate"} ${reviewDialog.item.outcome_id}` : "Review decision"}</DialogTitle>
        <DialogContent>
          {reviewDialog && <Stack spacing={1.5} sx={{ pt: 0.5 }}><Alert severity="info">The original machine determination remains unchanged. This creates an append-only finance review decision.</Alert><Typography><strong>Exposure:</strong> {money(reviewDialog.item.exposure_amount, currency)}</Typography><Typography variant="body2" color="text.secondary">{reviewDialog.item.reason}</Typography><TextField autoFocus label="Rationale" value={reviewRationale} onChange={(event) => setReviewRationale(event.target.value)} multiline minRows={3} helperText="Required for the audit trail." /></Stack>}
        </DialogContent>
        <DialogActions><Button onClick={() => setReviewDialog(null)}>Cancel</Button><Button variant="contained" disabled={reviewRationale.trim().length < 3 || Boolean(busy)} onClick={() => void decideReview()}>Record decision</Button></DialogActions>
      </Dialog>
    </WorkspaceShell>
  );
}
