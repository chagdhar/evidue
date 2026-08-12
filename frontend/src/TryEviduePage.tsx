import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Container,
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
    <Stack direction="row" spacing={1} alignItems="center" className="try-brand">
      <Box className="try-brand-mark">E</Box>
      <Typography fontWeight={820}>Evidue</Typography>
    </Stack>
  );
}

function Step({
  number,
  title,
  complete = false,
  children,
}: {
  number: string;
  title: string;
  complete?: boolean;
  children: ReactNode;
}) {
  return (
    <Paper variant="outlined" className={`try-step${complete ? " complete" : ""}`}>
      <Box className="try-step-heading">
        <Box className="try-step-index">{complete ? "✓" : number}</Box>
        <Box>
          <Typography className="try-step-kicker">CONTROL {number}</Typography>
          <Typography component="h2">{title}</Typography>
        </Box>
      </Box>
      <Box className="try-step-body">{children}</Box>
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
    setError("");
    setAnalyzing(true);
    setResult(null);
    track("try_evidue_analyze_started");
    try {
      const value = await api.analyzePublicTry();
      setAnalysis(value);
      track("try_evidue_analyzed", { live_model_call: value.live_model_call, rule_count: value.rules.length });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not analyze the demo contract.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function approveAndRun() {
    if (!analysis?.sandbox_id) return;
    setError("");
    setReconciling(true);
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
    } finally {
      setReconciling(false);
    }
  }

  const progress = result ? 100 : analysis ? 66 : 33;

  return (
    <Box className="try-page">
      <Box component="header" className="try-header">
        <Container maxWidth="lg" className="try-header-inner">
          <Brand />
          <Stack direction="row" spacing={1}>
            <Button component={RouterLink} to="/" color="inherit">Home</Button>
            <Button component={RouterLink} to="/contact" variant="outlined">Talk to us</Button>
          </Stack>
        </Container>
      </Box>

      <Container maxWidth="lg" className="try-container">
        <Box className="try-hero">
          <Typography className="try-eyebrow">PUBLIC RECONCILIATION · SYNTHETIC DATA</Typography>
          <Typography component="h1">Nova AI billed Acme $150 for 100 outcomes. Verify the invoice.</Typography>
          <Typography className="try-lede">
            Review the contract interpretation, approve the rules, and run the same deterministic verification boundary used by the customer workspace. No signup and no customer data.
          </Typography>
          <Box className="try-progress" aria-label={`${progress}% of demo complete`}>
            <Box sx={{ width: `${progress}%` }} />
          </Box>
          <Stack direction="row" spacing={2.5} useFlexGap flexWrap="wrap" className="try-trust-line">
            <span>AI proposes rules</span>
            <span>Human approves</span>
            <span>Deterministic code decides dollars</span>
          </Stack>
        </Box>

        {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

        <Stack spacing={2.25}>
          <Step number="1" title="Review the contract interpretation" complete={Boolean(analysis)}>
            <Typography className="try-step-copy">
              The model can propose contract rules, but it cannot decide whether a vendor charge is supported.
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.25} alignItems={{ sm: "center" }}>
              <Button variant="contained" onClick={() => void analyze()} disabled={analyzing}>
                {analyzing ? <><CircularProgress size={16} sx={{ mr: 1 }} />Analyzing contract…</> : analysis ? "Analyze again" : "Analyze synthetic contract"}
              </Button>
              <Button variant="text" onClick={() => setShowContract((value) => !value)}>
                {showContract ? "Hide source contract" : "View source contract"}
              </Button>
            </Stack>

            {showContract && (
              <Box component="pre" className="try-contract-source">
                {analysis?.contract_text ?? "Run contract analysis to load the exact synthetic contract used by this demo."}
              </Box>
            )}

            {analysis && (
              <Box className="try-rule-review">
                <Box className="try-rule-review-header">
                  <Box>
                    <Typography className="try-section-kicker">PROPOSED RULE SET</Typography>
                    <Typography component="h3">{analysis.rules.length} rules require human approval</Typography>
                  </Box>
                  <Typography className="try-model-note">
                    {analysis.live_model_call ? `Live ${analysis.model}` : "Validated recorded model proposal"}
                  </Typography>
                </Box>
                {analysis.fallback_reason && (
                  <Alert severity="warning" sx={{ mb: 2 }}>
                    {analysis.fallback_reason} The financial reconciliation still runs the real deterministic engine.
                  </Alert>
                )}
                <Box className="try-rule-table">
                  {analysis.rules.map((rule) => (
                    <Box key={rule.id} className="try-rule-row">
                      <Box>
                        <Typography className="try-rule-id">{rule.id}</Typography>
                        <Typography fontWeight={740}>{rule.title}</Typography>
                        <Typography className="try-rule-description">{rule.description}</Typography>
                      </Box>
                      <Box>
                        <Typography className="try-rule-meta-label">Evidence required</Typography>
                        <Typography className="try-rule-meta">{rule.evidence_required.join(", ") || "None"}</Typography>
                      </Box>
                      <Box>
                        <Typography className="try-rule-meta-label">Financial effect</Typography>
                        <Typography className="try-rule-meta">{rule.consequence.replaceAll("_", " ")}</Typography>
                      </Box>
                    </Box>
                  ))}
                </Box>
              </Box>
            )}
          </Step>

          <Step number="2" title="Approve the rules and run verification" complete={Boolean(result)}>
            {!analysis ? (
              <Typography className="try-muted">Complete the contract review first. Evidue will not make a financial determination from an unreviewed model response.</Typography>
            ) : !analysis.approval_ready ? (
              <Alert severity="warning">The proposed rule set has blocking diagnostics and cannot be approved.</Alert>
            ) : (
              <Box className="try-approval-boundary">
                <Box>
                  <Typography className="try-section-kicker">HUMAN APPROVAL BOUNDARY</Typography>
                  <Typography component="h3">You are approving the interpretation, not the invoice.</Typography>
                  <Typography className="try-step-copy">
                    After approval, deterministic code evaluates all 100 claims against customer-side support, payment, billing, and product evidence. The public run is isolated from the customer workspace.
                  </Typography>
                </Box>
                <Button variant="contained" size="large" onClick={() => void approveAndRun()} disabled={reconciling || !analysis.sandbox_id}>
                  {reconciling ? <><CircularProgress size={18} sx={{ mr: 1 }} />Verifying 100 claims…</> : "Approve rules & verify invoice"}
                </Button>
              </Box>
            )}
          </Step>

          {result && (
            <Step number="3" title="Decide what deserves action" complete>
              <Box className="try-result-lead">
                <Typography className="try-section-kicker">FINANCIAL RESULT</Typography>
                <Typography component="h3">
                  {deductionPercent?.toFixed(1)}% of invoice value is not supported by the approved rules and evidence.
                </Typography>
              </Box>
              <Box className="try-result-numbers">
                <Box><Typography>Vendor billed</Typography><strong>{formatUsd(result.submitted_amount)}</strong><span>{result.sample_size} claims</span></Box>
                <Box><Typography>Verified payable</Typography><strong>{formatUsd(result.confirmed_payable_amount)}</strong><span>{result.payable_outcomes} claims</span></Box>
                <Box className="attention"><Typography>Identified for dispute</Typography><strong>{formatUsd(result.recommended_deduction)}</strong><span>{result.disputed_outcomes} claims</span></Box>
                <Box><Typography>Needs review</Typography><strong>{result.needs_review_outcomes}</strong><span>insufficient evidence</span></Box>
              </Box>

              <Box className="try-disposition-bar" aria-label="Invoice disposition">
                <Box className="payable" sx={{ width: `${100 - (deductionPercent ?? 0)}%` }} />
                <Box className="disputed" sx={{ width: `${deductionPercent ?? 0}%` }} />
              </Box>

              <Box className="try-result-explain">
                <Box>
                  <Typography className="try-section-kicker">WHAT HAPPENED</Typography>
                  <Typography><strong>{result.payable_outcomes}</strong> claims were substantiated by the approved contract rules and customer evidence.</Typography>
                  <Typography><strong>{result.disputed_outcomes}</strong> claims contradicted at least one approved rule.</Typography>
                </Box>
                <Box>
                  <Typography className="try-section-kicker">WHAT FINANCE CAN DO</Typography>
                  <Typography>Use the contract remedy to dispute, request a credit, true-up, or escalate the unsupported amount. Evidue keeps that commercial action separate from the factual determination.</Typography>
                </Box>
              </Box>

              <Box className="try-findings">
                <Typography className="try-section-kicker">INSPECT THE EVIDENCE</Typography>
                <Typography component="h4">Open a representative failed claim</Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  {result.representative_findings.map((finding) => (
                    <Button key={finding.rule_id} component={RouterLink} to={`/demo/invoices/current?outcome=${encodeURIComponent(finding.outcome_id)}`} variant="outlined">
                      {finding.rule_id} · {finding.outcome_id}
                    </Button>
                  ))}
                </Stack>
              </Box>

              <Box className="try-conversation-cta">
                <Box>
                  <Typography className="try-section-kicker">DOES THIS EXIST IN YOUR WORKFLOW?</Typography>
                  <Typography component="h3">Tell us how your company verifies AI-vendor charges today.</Typography>
                  <Typography>We want the real answer—including “we just trust the vendor.”</Typography>
                </Box>
                <Button component={RouterLink} to="/contact" variant="contained" onClick={() => track("try_evidue_talk_clicked")}>
                  Share your workflow
                </Button>
              </Box>
            </Step>
          )}
        </Stack>
      </Container>
    </Box>
  );
}
