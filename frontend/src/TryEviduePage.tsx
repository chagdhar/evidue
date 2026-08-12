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
import { AuthorityBoundary, DecisionFlow, FinancialEquation } from "./DecisionLedger";
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

function StageRail({ analysis, rulesApproved, result }: { analysis: PublicTryAnalysis | null; rulesApproved: boolean; result: PublicTryResult | null }) {
  const stages = [
    ["01", "Read contract", Boolean(analysis)],
    ["02", "Approve rules", rulesApproved],
    ["03", "Verify claims", Boolean(result)],
    ["04", "Act on dollars", Boolean(result)],
  ] as const;
  const activeIndex = !analysis ? 0 : !rulesApproved ? 1 : !result ? 2 : 3;
  return (
    <Box className="try-v4-rail" aria-label="Reconciliation progress">
      {stages.map(([number, label, done], index) => (
        <Box key={label} className={`${done ? "done" : ""}${index === activeIndex ? " active" : ""}`}>
          <span>{done ? "✓" : number}</span>
          <strong>{label}</strong>
          {index < stages.length - 1 && <b aria-hidden="true">→</b>}
        </Box>
      ))}
    </Box>
  );
}

export default function TryEviduePage() {
  const [analysis, setAnalysis] = useState<PublicTryAnalysis | null>(null);
  const [rulesApproved, setRulesApproved] = useState(false);
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
    setError(""); setAnalyzing(true); setResult(null); setRulesApproved(false); track("try_evidue_analyze_started");
    try {
      const value = await api.analyzePublicTry();
      setAnalysis(value);
      track("try_evidue_analyzed", { live_model_call: value.live_model_call, rule_count: value.rules.length });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not analyze the demo contract.");
    } finally { setAnalyzing(false); }
  }

  function approveRules() {
    if (!analysis?.approval_ready) return;
    setRulesApproved(true);
    track("try_evidue_rules_authority_confirmed", { rule_count: analysis.rules.length });
  }

  async function verifyClaims() {
    if (!analysis?.sandbox_id || !rulesApproved) return;
    setError(""); setReconciling(true); track("try_evidue_verification_started", { rule_count: analysis.rules.length });
    try {
      const value = await api.approvePublicTry(analysis.sandbox_id);
      setResult(value);
      track("try_evidue_result_seen", { disputed_outcomes: value.disputed_outcomes, recommended_deduction: value.recommended_deduction });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not run the demo reconciliation.");
    } finally { setReconciling(false); }
  }

  return (
    <Box className="try-v4-page decision-ledger-site">
      <Box component="header" className="try-v3-header">
        <Container maxWidth={false} className="try-v3-container try-v3-header-inner">
          <Brand />
          <Stack direction="row" spacing={1}>
            <Button component={RouterLink} to="/" color="inherit">Home</Button>
            <Button component={RouterLink} to="/contact" variant="outlined">Talk to us</Button>
          </Stack>
        </Container>
      </Box>

      <Box className="try-v4-hero">
        <Container maxWidth={false} className="try-v3-container try-v4-hero-grid">
          <Box className="try-v4-hero-copy">
            <Typography className="try-v3-kicker">PUBLIC RECONCILIATION · SYNTHETIC DATA</Typography>
            <Typography component="h1">Nova AI billed Acme $150 for 100 outcomes.</Typography>
            <Typography className="try-v4-question">Would you pay it?</Typography>
            <Typography className="try-v4-lede">Do not trust the vendor number—or the model. Establish contract authority, then verify every claim against customer-side proof.</Typography>
            <Button variant="contained" size="large" onClick={() => void analyze()} disabled={analyzing}>
              {analyzing ? <><CircularProgress size={17} sx={{ mr: 1 }} />Reading contract…</> : analysis ? "Read contract again" : "Verify the invoice"}
            </Button>
          </Box>
          <Box className={`try-v4-challenge${result ? " resolved" : ""}`}>
            <Box className="try-v4-challenge-head"><span>NOVA SUPPORT AI</span><b>INV-JUN-2026</b></Box>
            {!result ? (
              <>
                <Box className="try-v4-vendor-claim"><span>VENDOR ASSERTION</span><strong>100 / 100 outcomes billable</strong></Box>
                <Box className="try-v4-amount-due"><span>AMOUNT DUE</span><strong>$150.00</strong><small>100 claimed outcomes × $1.50</small></Box>
                <Box className="try-v4-challenge-note">The invoice is an assertion. Evidue asks what the contract and your systems can actually substantiate.</Box>
              </>
            ) : (
              <>
                <Box className="try-v4-resolved-label">VERIFIED AGAINST APPROVED AUTHORITY</Box>
                <FinancialEquation billed={formatUsd(result.submitted_amount)} disputed={formatUsd(result.recommended_deduction)} substantiated={formatUsd(result.confirmed_payable_amount)} />
                <Box className="try-v4-challenge-note">{result.disputed_outcomes} claims contradicted approved rules · {result.needs_review_outcomes} require review</Box>
              </>
            )}
          </Box>
        </Container>
      </Box>

      <Container maxWidth={false} className="try-v3-container try-v4-body">
        <StageRail analysis={analysis} rulesApproved={rulesApproved} result={result} />
        {error && <Alert severity="error" sx={{ my: 3 }}>{error}</Alert>}

        <Box className="try-v4-flow-intro">
          <Typography className="try-v3-kicker">THE CONTROL LOOP</Typography>
          <Typography component="h2">Authority before calculation.</Typography>
          <DecisionFlow compact />
        </Box>

        <Box className="try-v4-step" data-step="01">
          <Box className="try-v4-step-rail"><span>01</span><strong>INTERPRET</strong><small>What does the contract make billable?</small></Box>
          <Box className="try-v4-step-body">
            <Box className="try-v3-section-head">
              <Box><Typography className="try-v3-kicker">AI PROPOSAL · NOT YET AUTHORITY</Typography><Typography component="h2">Turn source language into explicit payment rules.</Typography></Box>
              <Button variant="text" onClick={() => setShowContract((value) => !value)}>{showContract ? "Hide source contract" : "View source contract"}</Button>
            </Box>
            {!analysis && <Typography className="try-v3-muted">Start with “Verify the invoice.” Evidue will load the synthetic agreement and propose a structured rule set.</Typography>}
            {showContract && <Box component="pre" className="try-v3-contract-source">{analysis?.contract_text ?? "Run contract analysis to load the exact synthetic contract used by this demo."}</Box>}
            {analysis && (
              <>
                <Box className="try-v4-proposal-meta"><span>{analysis.live_model_call ? `LIVE ${analysis.model}` : "VALIDATED RECORDED MODEL PROPOSAL"}</span><b>{analysis.rules.length} proposed rules</b></Box>
                {analysis.fallback_reason && <Alert severity="warning" sx={{ mb: 2 }}>{analysis.fallback_reason} The financial reconciliation still runs the real deterministic engine.</Alert>}
                <Box className="try-v4-rule-ledger">
                  {analysis.rules.map((rule) => (
                    <Box key={rule.id} className="try-v4-rule-row">
                      <Box className="try-v4-rule-source"><span>SOURCE CLAUSE · {rule.id}</span><blockquote>“{rule.clause_text}”</blockquote></Box>
                      <Box className="try-v4-rule-authority"><span>PROPOSED PAYMENT RULE</span><strong>{rule.title}</strong><p>{rule.description}</p><small>If violated: {rule.consequence.replaceAll("_", " ")}</small></Box>
                    </Box>
                  ))}
                </Box>
              </>
            )}
          </Box>
        </Box>

        <Box className="try-v4-step" data-step="02">
          <Box className="try-v4-step-rail"><span>02</span><strong>AUTHORIZE</strong><small>The model stops here.</small></Box>
          <Box className="try-v4-step-body">
            <Typography className="try-v3-kicker">HUMAN AUTHORITY BOUNDARY</Typography>
            <Typography component="h2">Approve the interpretation—not the invoice.</Typography>
            <Typography className="try-v4-step-copy">Only a reviewed rule set can govern the financial run. Clicking approve does not itself classify a single invoice claim.</Typography>
            <AuthorityBoundary />
            <Box className={`try-v4-approval-action${rulesApproved ? " approved" : ""}`}>
              <Box>
                <span>{rulesApproved ? "AUTHORITY CONFIRMED" : "AWAITING HUMAN APPROVAL"}</span>
                <strong>{rulesApproved ? `Approved ${analysis?.rules.length ?? 0} contract rule${analysis?.rules.length === 1 ? "" : "s"} for this run` : "No payment rule is active yet"}</strong>
              </Box>
              <Button variant={rulesApproved ? "outlined" : "contained"} size="large" onClick={approveRules} disabled={!analysis?.approval_ready || rulesApproved}>
                {rulesApproved ? "Rules approved" : `Approve ${analysis?.rules.length ?? 0} contract rule${analysis?.rules.length === 1 ? "" : "s"}`}
              </Button>
            </Box>
          </Box>
        </Box>

        <Box className="try-v4-step" data-step="03">
          <Box className="try-v4-step-rail"><span>03</span><strong>VERIFY</strong><small>Now apply authority to proof.</small></Box>
          <Box className="try-v4-step-body try-v4-verification-step">
            <Box>
              <Typography className="try-v3-kicker">DETERMINISTIC EXECUTION</Typography>
              <Typography component="h2">Check 100 claims against approved rules and evidence.</Typography>
              <Typography className="try-v4-step-copy">The model is no longer in the decision loop. Every line becomes substantiated, contradicted, or insufficient evidence.</Typography>
            </Box>
            <Button variant="contained" size="large" onClick={() => void verifyClaims()} disabled={!rulesApproved || reconciling || Boolean(result)}>
              {reconciling ? <><CircularProgress size={18} sx={{ mr: 1 }} />Checking 100 claims…</> : result ? "100 claims verified" : "Verify 100 claims"}
            </Button>
          </Box>
        </Box>

        {result && (
          <Box className="try-v4-result-shell" data-step="04">
            <Box className="try-v4-result-head">
              <Box>
                <Typography className="try-v3-kicker">04 · ACT ON DOLLARS</Typography>
                <Typography component="h2">The vendor billed $150. Evidue substantiated $124.50.</Typography>
                <Typography>{deductionPercent?.toFixed(1)}% of invoice value is identified for dispute after deterministic verification.</Typography>
              </Box>
              <span className="try-v4-result-state">DECISION COMPLETE</span>
            </Box>

            <FinancialEquation
              billed={formatUsd(result.submitted_amount)}
              disputed={formatUsd(result.recommended_deduction)}
              substantiated={formatUsd(result.confirmed_payable_amount)}
              caption={`${result.payable_outcomes} substantiated · ${result.disputed_outcomes} contradicted · ${result.needs_review_outcomes} insufficient evidence`}
            />

            <Box className="try-v3-result-money">
              <Box><span>Vendor billed</span><strong>{formatUsd(result.submitted_amount)}</strong><small>{result.sample_size} claims</small></Box>
              <Box><span>Substantiated</span><strong>{formatUsd(result.confirmed_payable_amount)}</strong><small>{result.payable_outcomes} claims</small></Box>
              <Box className="is-dispute"><span>Identified for dispute</span><strong>{formatUsd(result.recommended_deduction)}</strong><small>{result.disputed_outcomes} claims</small></Box>
              <Box><span>Needs review</span><strong>{result.needs_review_outcomes}</strong><small>insufficient evidence</small></Box>
            </Box>

            <Box className="try-v3-result-detail">
              <Box><Typography className="try-v3-kicker">WHAT HAPPENED</Typography><strong>{result.disputed_outcomes} claims contradicted an approved contract rule.</strong><Typography>The factual state comes from approved authority plus customer evidence.</Typography></Box>
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
