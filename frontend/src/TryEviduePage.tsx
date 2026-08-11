import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Container,
  Divider,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link as RouterLink } from "react-router-dom";
import { api, PublicTryAnalysis, PublicTryResult } from "./api";
import { track } from "./analytics";
import { formatUsd } from "./presentation";

function Brand() {
  return (
    <Stack direction="row" spacing={1} alignItems="center">
      <Box sx={{ width: 32, height: 32, borderRadius: 1.5, display: "grid", placeItems: "center", bgcolor: "#171D26", border: "1px solid #343D4A", fontWeight: 900 }}>E</Box>
      <Typography fontWeight={850}>Evidue</Typography>
    </Stack>
  );
}

function Step({ number, title, children }: { number: string; title: string; children: ReactNode }) {
  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, md: 3 }, borderRadius: 3, bgcolor: "#131820", borderColor: "#2A313C" }}>
      <Stack direction="row" spacing={1.5} alignItems="center" mb={2}>
        <Box sx={{ width: 30, height: 30, borderRadius: 99, display: "grid", placeItems: "center", bgcolor: "#211D38", color: "#C8BFFF", fontWeight: 800 }}>{number}</Box>
        <Typography variant="h5" fontWeight={780}>{title}</Typography>
      </Stack>
      {children}
    </Paper>
  );
}

export default function TryEviduePage() {
  const [analysis, setAnalysis] = useState<PublicTryAnalysis | null>(null);
  const [result, setResult] = useState<PublicTryResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [reconciling, setReconciling] = useState(false);
  const [error, setError] = useState("");
  const [showContract, setShowContract] = useState(false);

  useEffect(() => { track("try_evidue_viewed"); }, []);

  const deductionPercent = useMemo(() => {
    if (!result) return null;
    const submitted = Number(result.submitted_amount);
    return submitted > 0 ? (Number(result.recommended_deduction) / submitted) * 100 : 0;
  }, [result]);

  async function analyze() {
    setError(""); setAnalyzing(true); setResult(null);
    track("try_evidue_analyze_started");
    try {
      const value = await api.analyzePublicTry();
      setAnalysis(value);
      track("try_evidue_analyzed", { live_model_call: value.live_model_call, rule_count: value.rules.length });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not analyze the demo contract.");
    } finally { setAnalyzing(false); }
  }

  async function approveAndRun() {
    if (!analysis?.sandbox_id) return;
    setError(""); setReconciling(true);
    track("try_evidue_rules_approved", { rule_count: analysis.rules.length });
    try {
      const value = await api.approvePublicTry(analysis.sandbox_id);
      setResult(value);
      track("try_evidue_result_seen", {
        disputed_outcomes: value.disputed_outcomes,
        recommended_deduction: value.recommended_deduction,
      });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not run the demo reconciliation.");
    } finally { setReconciling(false); }
  }

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "#0D1117", color: "#F5F7FA" }}>
      <Box component="header" sx={{ borderBottom: "1px solid #222A35", bgcolor: "rgba(13,17,23,.94)", position: "sticky", top: 0, zIndex: 5 }}>
        <Container maxWidth="lg" sx={{ py: 1.5, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Brand />
          <Stack direction="row" spacing={1}>
            <Button component={RouterLink} to="/demo" color="inherit">Full sample workspace</Button>
            <Button component={RouterLink} to="/contact" variant="outlined">Contact</Button>
          </Stack>
        </Container>
      </Box>

      <Container maxWidth="lg" sx={{ py: { xs: 5, md: 8 } }}>
        <Box sx={{ maxWidth: 880, mb: 5 }}>
          <Stack direction="row" spacing={1} mb={2} flexWrap="wrap" useFlexGap>
            <Chip label="No signup" size="small" />
            <Chip label="Synthetic data" size="small" />
            <Chip label="Real deterministic engine" size="small" />
          </Stack>
          <Typography component="h1" sx={{ fontSize: { xs: "2.55rem", md: "4.4rem" }, lineHeight: .98, letterSpacing: "-.055em", fontWeight: 850 }}>
            See whether an AI vendor’s billed outcomes actually count.
          </Typography>
          <Typography sx={{ mt: 2.5, maxWidth: 760, color: "#A7B0BE", fontSize: { xs: "1.05rem", md: "1.25rem" }, lineHeight: 1.6 }}>
            A synthetic AI vendor submitted 100 billable outcomes. Evidue reads the contract, turns it into reviewable rules, then checks the invoice against customer-side support, payment, billing, and product evidence.
          </Typography>
          <Alert severity="info" icon={false} sx={{ mt: 3, bgcolor: "#141B24", color: "#C9D2DF", border: "1px solid #273240" }}>
            This page never accepts customer data. The public demo uses only fictional Acme Commerce / Nova Support AI records.
          </Alert>
        </Box>

        {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

        <Stack spacing={3}>
          <Step number="1" title="Analyze the contract">
            <Typography color="#A7B0BE" mb={2}>
              The model is allowed to propose rules only. It cannot decide whether a charge is payable or disputed.
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }}>
              <Button variant="contained" size="large" onClick={() => void analyze()} disabled={analyzing}>
                {analyzing ? <><CircularProgress size={18} sx={{ mr: 1 }} />Analyzing contract…</> : analysis ? "Analyze again" : "Analyze the synthetic contract"}
              </Button>
              <Button variant="text" onClick={() => setShowContract((value) => !value)}>
                {showContract ? "Hide contract" : "Inspect contract text"}
              </Button>
            </Stack>
            {showContract && (
              <Paper variant="outlined" sx={{ mt: 2, p: 2, maxHeight: 280, overflow: "auto", whiteSpace: "pre-wrap", fontFamily: "monospace", fontSize: 13, bgcolor: "#0B0F14", borderColor: "#2A313C" }}>
                {analysis?.contract_text ?? "Run contract analysis to load the exact synthetic contract used by this demo."}
              </Paper>
            )}

            {analysis && (
              <Box sx={{ mt: 3 }}>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap mb={2}>
                  <Chip color={analysis.live_model_call ? "success" : "default"} label={analysis.live_model_call ? `Live ${analysis.model}` : "Validated recorded model proposal"} />
                  <Chip label={`${analysis.rules.length} proposed rules`} />
                  <Chip color={analysis.approval_ready ? "success" : "warning"} label={analysis.approval_ready ? "Ready for human review" : "Review blocked"} />
                  <Typography variant="caption" color="#7F8A99">{analysis.duration_ms.toFixed(0)} ms</Typography>
                </Stack>
                {analysis.fallback_reason && <Alert severity="warning" sx={{ mb: 2 }}>{analysis.fallback_reason} The financial reconciliation still runs the real deterministic engine.</Alert>}
                <Stack spacing={1.25}>
                  {analysis.rules.map((rule) => (
                    <Paper key={rule.id} variant="outlined" sx={{ p: 1.75, bgcolor: "#171D26", borderColor: "#303844", borderRadius: 2 }}>
                      <Stack direction={{ xs: "column", md: "row" }} spacing={2} justifyContent="space-between">
                        <Box sx={{ minWidth: 0 }}>
                          <Typography fontWeight={780}>{rule.id} · {rule.title}</Typography>
                          <Typography variant="body2" color="#9FA9B7" sx={{ mt: .5 }}>{rule.description}</Typography>
                          <Typography variant="caption" color="#778392" display="block" sx={{ mt: .75 }}>Evidence: {rule.evidence_required.join(", ") || "none"}</Typography>
                        </Box>
                        <Chip size="small" label={rule.consequence.replaceAll("_", " ")} color={rule.consequence === "disputed" ? "error" : rule.consequence === "needs_review" ? "warning" : "success"} />
                      </Stack>
                    </Paper>
                  ))}
                </Stack>
              </Box>
            )}
          </Step>

          <Step number="2" title="Approve the rules, then audit the invoice">
            {!analysis ? (
              <Typography color="#7F8A99">Analyze the contract first. Evidue will not run a financial decision from an unreviewed model response.</Typography>
            ) : !analysis.approval_ready ? (
              <Alert severity="warning">The compiler found blocking diagnostics, so the invoice cannot be adjudicated automatically.</Alert>
            ) : (
              <>
                <Typography color="#A7B0BE" mb={2}>
                  Clicking below is the human-approval boundary for this synthetic demo. The approved rule program is then handed to deterministic code that evaluates 100 vendor claims in memory. Nothing is written into the authoritative customer workspace.
                </Typography>
                <Button variant="contained" size="large" onClick={() => void approveAndRun()} disabled={reconciling || !analysis.sandbox_id}>
                  {reconciling ? <><CircularProgress size={18} sx={{ mr: 1 }} />Reconciling 100 claims…</> : "Approve demo rules & reconcile 100 claims"}
                </Button>
              </>
            )}
          </Step>

          {result && (
            <Step number="3" title="See what changed before payment">
              <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr 1fr", md: "repeat(4, 1fr)" }, gap: 1.5 }}>
                <Paper variant="outlined" sx={{ p: 2, bgcolor: "#1A2029", borderColor: "#303844" }}><Typography variant="caption" color="#8E98A8">Vendor billed</Typography><Typography variant="h4" fontWeight={840}>{formatUsd(result.submitted_amount)}</Typography><Typography variant="caption">{result.sample_size} claims</Typography></Paper>
                <Paper variant="outlined" sx={{ p: 2, bgcolor: "#152821", borderColor: "#237B59" }}><Typography variant="caption" color="#8E98A8">Substantiated</Typography><Typography variant="h4" fontWeight={840} color="#A9EEC9">{formatUsd(result.confirmed_payable_amount)}</Typography><Typography variant="caption">{result.payable_outcomes} claims</Typography></Paper>
                <Paper variant="outlined" sx={{ p: 2, bgcolor: "#2D1B21", borderColor: "#9C4052" }}><Typography variant="caption" color="#8E98A8">Unsupported</Typography><Typography variant="h4" fontWeight={840} color="#FFB0BA">{formatUsd(result.recommended_deduction)}</Typography><Typography variant="caption">{result.disputed_outcomes} claims</Typography></Paper>
                <Paper variant="outlined" sx={{ p: 2, bgcolor: "#2A2419", borderColor: "#9C6B2E" }}><Typography variant="caption" color="#8E98A8">Needs review</Typography><Typography variant="h4" fontWeight={840} color="#FFD694">{result.needs_review_outcomes}</Typography><Typography variant="caption">insufficient evidence</Typography></Paper>
              </Box>

              <Typography sx={{ mt: 2.5, fontSize: "1.15rem", fontWeight: 750 }}>
                Evidue identified {formatUsd(result.recommended_deduction)} of the {formatUsd(result.submitted_amount)} sample invoice as unsupported ({deductionPercent?.toFixed(1)}%).
              </Typography>
              <Typography color="#8E98A8" variant="body2" sx={{ mt: .75 }}>
                Deterministic engine · {result.engine_version} · compilation {result.compilation_id} · {result.duration_ms.toFixed(0)} ms
              </Typography>

              <Divider sx={{ my: 3, borderColor: "#2A313C" }} />
              <Typography variant="h6" fontWeight={780}>Inspect why charges failed</Typography>
              <Typography color="#A7B0BE" sx={{ mt: .5, mb: 1.5 }}>Each example opens the full contract-rule and customer-evidence chain.</Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {result.representative_findings.map((finding) => (
                  <Button key={finding.rule_id} component={RouterLink} to={`/demo/invoices/current?outcome=${encodeURIComponent(finding.outcome_id)}`} variant="outlined">
                    {finding.rule_id} · {finding.outcome_id}
                  </Button>
                ))}
              </Stack>

              <Paper sx={{ mt: 3, p: { xs: 2.5, md: 3.5 }, bgcolor: "#201C35", border: "1px solid #5E4BC9", borderRadius: 3 }}>
                <Typography variant="h4" fontWeight={820}>Does your company pay AI vendors by outcome, resolution, action, or usage?</Typography>
                <Typography color="#C8C0DD" sx={{ mt: 1, maxWidth: 720 }}>
                  We’re talking to finance, procurement, CX, and operations teams about how these charges are verified today. No sales call required—tell us what the real workflow looks like.
                </Typography>
                <Button component={RouterLink} to="/contact" variant="contained" size="large" sx={{ mt: 2 }} onClick={() => track("try_evidue_talk_clicked")}>
                  Talk to us
                </Button>
              </Paper>
            </Step>
          )}
        </Stack>
      </Container>
    </Box>
  );
}
