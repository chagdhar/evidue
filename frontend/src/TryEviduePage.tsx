import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Container,
  Stack,
  Typography,
} from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { api, PublicTryAnalysis, PublicTryResult } from "./api";
import { track } from "./analytics";
import { formatUsd } from "./presentation";

function Brand() {
  return (
    <Stack direction="row" spacing={1} alignItems="center" className="try-v3-brand">
      <Box className="try-v3-mark">E</Box>
      <Box><Typography fontWeight={820}>Evidue</Typography><Typography>Invoice control</Typography></Box>
    </Stack>
  );
}

function StageRail({ analysis, result }: { analysis: PublicTryAnalysis | null; result: PublicTryResult | null }) {
  const stages = [
    ["01", "Read contract", Boolean(analysis)],
    ["02", "Approve rules", Boolean(result)],
    ["03", "Verify evidence", Boolean(result)],
    ["04", "Act on dollars", Boolean(result)],
  ] as const;
  return (
    <Box className="try-v3-rail" aria-label="Reconciliation progress">
      {stages.map(([number, label, done], index) => (
        <Box key={label} className={`${done ? "done" : ""}${(!analysis && index === 0) || (analysis && !result && index === 1) ? " active" : ""}`}>
          <span>{done ? "✓" : number}</span><strong>{label}</strong>
          {index < stages.length - 1 && <b>→</b>}
        </Box>
      ))}
    </Box>
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
    setError(""); setAnalyzing(true); setResult(null); track("try_evidue_analyze_started");
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
    setError(""); setReconciling(true); track("try_evidue_rules_approved", { rule_count: analysis.rules.length });
    try {
      const value = await api.approvePublicTry(analysis.sandbox_id);
      setResult(value);
      track("try_evidue_result_seen", { disputed_outcomes: value.disputed_outcomes, recommended_deduction: value.recommended_deduction });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not run the demo reconciliation.");
    } finally { setReconciling(false); }
  }

  return (
    <Box className="try-v3-page">
      <Box component="header" className="try-v3-header">
        <Container maxWidth={false} className="try-v3-container try-v3-header-inner">
          <Brand />
          <Stack direction="row" spacing={1}>
            <Button component={RouterLink} to="/" color="inherit">Home</Button>
            <Button component={RouterLink} to="/contact" variant="outlined">Talk to us</Button>
          </Stack>
        </Container>
      </Box>

      <Box className="try-v3-hero">
        <Container maxWidth={false} className="try-v3-container try-v3-hero-grid">
          <Box>
            <Typography className="try-v3-kicker">PUBLIC RECONCILIATION · SYNTHETIC DATA</Typography>
            <Typography component="h1">Nova AI billed Acme $150 for 100 outcomes.</Typography>
            <Typography className="try-v3-question">Would you pay it?</Typography>
            <Typography className="try-v3-lede">Run the contract → approval → evidence → financial-decision loop yourself. No signup. No customer data.</Typography>
            <Button variant="contained" size="large" onClick={() => void analyze()} disabled={analyzing}>
              {analyzing ? <><CircularProgress size={17} sx={{ mr: 1 }} />Reading contract…</> : analysis ? "Read contract again" : "Verify the invoice"}
            </Button>
          </Box>
          <Box className="try-v3-challenge">
            <Box className="try-v3-challenge-top"><span>NOVA SUPPORT AI</span><b>INV-JUN-2026</b></Box>
            <Box className="try-v3-challenge-money"><span>Amount due</span><strong>$150.00</strong><small>100 claimed outcomes × $1.50</small></Box>
            <Box className="try-v3-challenge-claim"><span>Vendor assertion</span><strong>All 100 outcomes are billable</strong></Box>
            <Box className="try-v3-challenge-footer">Your contract and systems—not the vendor report—decide what is supported.</Box>
          </Box>
        </Container>
      </Box>

      <Container maxWidth={false} className="try-v3-container">
        <StageRail analysis={analysis} result={result} />
        {error && <Alert severity="error" sx={{ my: 3 }}>{error}</Alert>}

        <Box className="try-v3-flow">
          <Box className="try-v3-flow-label"><span>01</span><strong>Contract</strong><small>What counts as billable?</small></Box>
          <Box className="try-v3-flow-body">
            <Box className="try-v3-section-head">
              <Box><Typography className="try-v3-kicker">AI PROPOSES · HUMAN REVIEWS</Typography><Typography component="h2">Turn contract language into explicit payment rules.</Typography></Box>
              <Button variant="text" onClick={() => setShowContract((value) => !value)}>{showContract ? "Hide source contract" : "View source contract"}</Button>
            </Box>
            {!analysis && <Typography className="try-v3-muted">Start with “Verify the invoice.” Evidue will load the synthetic agreement and propose a structured rule set.</Typography>}
            {showContract && <Box component="pre" className="try-v3-contract-source">{analysis?.contract_text ?? "Run contract analysis to load the exact synthetic contract used by this demo."}</Box>}
            {analysis && (
              <>
                <Box className="try-v3-model-row"><span>{analysis.live_model_call ? `Live ${analysis.model}` : "Validated recorded model proposal"}</span><b>{analysis.rules.length} rules awaiting approval</b></Box>
                {analysis.fallback_reason && <Alert severity="warning" sx={{ mb: 2 }}>{analysis.fallback_reason} The financial reconciliation still runs the real deterministic engine.</Alert>}
                <Box className="try-v3-rules">
                  {analysis.rules.map((rule) => (
                    <Box key={rule.id} className="try-v3-rule">
                      <Box><span>{rule.id}</span><strong>{rule.title}</strong><p>{rule.description}</p></Box>
                      <Box><small>EVIDENCE NEEDED</small><b>{rule.evidence_required.join(", ") || "None"}</b></Box>
                      <Box><small>FINANCIAL EFFECT</small><b>{rule.consequence.replaceAll("_", " ")}</b></Box>
                    </Box>
                  ))}
                </Box>
              </>
            )}
          </Box>
        </Box>

        <Box className="try-v3-flow">
          <Box className="try-v3-flow-label"><span>02</span><strong>Approval</strong><small>The model stops here.</small></Box>
          <Box className="try-v3-flow-body try-v3-approval">
            <Box><Typography className="try-v3-kicker">HUMAN AUTHORITY BOUNDARY</Typography><Typography component="h2">Approve the interpretation—not the invoice.</Typography><Typography>The approved rule set becomes the only authority the deterministic engine can use for this run.</Typography></Box>
            <Button variant="contained" size="large" onClick={() => void approveAndRun()} disabled={!analysis?.approval_ready || reconciling || !analysis?.sandbox_id}>
              {reconciling ? <><CircularProgress size={18} sx={{ mr: 1 }} />Checking 100 claims…</> : "Approve rules & verify invoice"}
            </Button>
          </Box>
        </Box>

        {result && (
          <Box className="try-v3-result-shell">
            <Box className="try-v3-result-intro">
              <Typography className="try-v3-kicker">THE PAYOFF</Typography>
              <Typography component="h2">The vendor billed $150. Evidue can substantiate $124.50.</Typography>
              <Typography>{deductionPercent?.toFixed(1)}% of invoice value is identified for dispute after deterministic verification.</Typography>
            </Box>
            <Box className="try-v3-result-money">
              <Box><span>Vendor billed</span><strong>{formatUsd(result.submitted_amount)}</strong><small>{result.sample_size} claims</small></Box>
              <Box><span>Verified payable</span><strong>{formatUsd(result.confirmed_payable_amount)}</strong><small>{result.payable_outcomes} claims</small></Box>
              <Box className="is-dispute"><span>Identified for dispute</span><strong>{formatUsd(result.recommended_deduction)}</strong><small>{result.disputed_outcomes} claims</small></Box>
              <Box><span>Needs review</span><strong>{result.needs_review_outcomes}</strong><small>insufficient evidence</small></Box>
            </Box>
            <Box className="try-v3-result-bar"><Box className="verified" sx={{ width: `${100 - (deductionPercent ?? 0)}%` }} /><Box className="disputed" sx={{ width: `${deductionPercent ?? 0}%` }} /></Box>

            <Box className="try-v3-result-detail">
              <Box><Typography className="try-v3-kicker">WHAT HAPPENED</Typography><strong>{result.disputed_outcomes} claims contradicted an approved contract rule.</strong><Typography>The factual determination comes from rules plus customer evidence.</Typography></Box>
              <Box><Typography className="try-v3-kicker">WHAT FINANCE CAN DO</Typography><strong>Dispute, request credit, true-up, or escalate.</strong><Typography>The commercial remedy remains separate from the factual result.</Typography></Box>
            </Box>

            <Box className="try-v3-inspect">
              <Box><Typography className="try-v3-kicker">DON’T TRUST THE SUMMARY</Typography><Typography component="h3">Inspect a failed claim yourself.</Typography></Box>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {result.representative_findings.map((finding) => (
                  <Button key={finding.rule_id} component={RouterLink} to={`/demo/invoices/current?outcome=${encodeURIComponent(finding.outcome_id)}`} variant="outlined">{finding.rule_id} · {finding.outcome_id}</Button>
                ))}
              </Stack>
            </Box>

            <Box className="try-v3-contact">
              <Box><Typography className="try-v3-kicker">HOW DO YOU DO THIS TODAY?</Typography><Typography component="h3">Tell us how your company verifies AI-vendor charges.</Typography><Typography>“We trust the vendor” is a useful answer.</Typography></Box>
              <Button component={RouterLink} to="/contact" variant="contained" onClick={() => track("try_evidue_talk_clicked")}>Share your workflow</Button>
            </Box>
          </Box>
        )}
      </Container>
    </Box>
  );
}
