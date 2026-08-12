import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Container,
  Stack,
  Typography,
} from "@mui/material";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { api, PublicTryAnalysis, PublicTryInspection, PublicTryResult } from "./api";
import {
  AuthorityBoundary,
  ClaimDecisionLedger,
  DecisionFlow,
  FinancialEquation,
} from "./DecisionLedger";
import { track } from "./analytics";
import { formatUsd } from "./presentation";
import GuidedTour, { GuidedTourStep } from "./GuidedTour";

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
    <Box className="try-v4-rail" aria-label="Reconciliation progress" data-tour="try-stages">
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

function humanize(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function evidenceSummary(event: PublicTryInspection["evidence"][number]): string {
  const detail = Object.entries(event.values)
    .filter(([, value]) => value !== "")
    .slice(0, 2)
    .map(([key, value]) => `${humanize(key)}: ${value}`)
    .join(" · ");
  return detail ? `${humanize(event.event_type)} · ${detail}` : humanize(event.event_type);
}

function evidenceWhen(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return timestamp;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function inspectionImpact(inspection: PublicTryInspection): string {
  if (inspection.status === "disputed") {
    return `${formatUsd(inspection.confirmed_disputed_amount)} identified for dispute`;
  }
  if (inspection.status === "needs_review") {
    return `${formatUsd(inspection.needs_review_amount)} held for review`;
  }
  return `${formatUsd(inspection.confirmed_payable_amount)} substantiated`;
}

function determinationLabel(status: PublicTryInspection["status"]): string {
  if (status === "disputed") return "Contradicted";
  if (status === "needs_review") return "Insufficient evidence";
  return "Substantiated";
}

function shortHash(value: string | null | undefined): string {
  if (!value) return "—";
  return value.length > 22 ? `${value.slice(0, 12)}…${value.slice(-8)}` : value;
}

const TRY_TOUR_STEPS: GuidedTourStep[] = [
  {
    selector: '[data-tour="try-intro"]',
    kicker: "THE SAMPLE",
    title: "Start with the vendor invoice",
    body: "This public example uses synthetic data. Nova AI says 100 outcomes are billable for $150. Your job is to decide what the contract and customer evidence actually support.",
  },
  {
    selector: '[data-tour="try-invoice"]',
    kicker: "THE ASSERTION",
    title: "Treat the invoice as a claim, not a fact",
    body: "This panel shows what the vendor billed. Evidue reconciles that assertion against approved contract authority and customer-controlled proof.",
  },
  {
    selector: '[data-tour="try-stages"]',
    kicker: "THE CONTROL LOOP",
    title: "Follow four finance-control stages",
    body: "Read the contract, approve the proposed payment rules, verify claims deterministically, then act on the resulting dollars.",
  },
  {
    selector: '[data-tour="try-interpret"]',
    kicker: "01 · INTERPRET",
    title: "The model proposes rules — it does not decide payment",
    body: "Evidue converts contract language into structured payment rules. You can inspect the source clause beside each proposal before anything becomes financial authority.",
  },
  {
    selector: '[data-tour="try-authorize"]',
    kicker: "02 · AUTHORIZE",
    title: "Finance establishes authority",
    body: "Nothing governs the invoice until the proposed rule set is approved. Approval versions the authority; it does not classify a single invoice claim.",
  },
  {
    selector: '[data-tour="try-verify"]',
    kicker: "03 · VERIFY",
    title: "Deterministic code checks the evidence",
    body: "After approval, the rules engine evaluates all 100 claims against customer-side evidence. The LLM is no longer in the decision loop.",
  },
];

function scrollToTryTarget(element: HTMLElement | null) {
  if (!element || typeof element.scrollIntoView !== "function") return;
  element.scrollIntoView({ behavior: "auto", block: "start" });
}



export default function TryEviduePage() {
  const [analysis, setAnalysis] = useState<PublicTryAnalysis | null>(null);
  const [rulesApproved, setRulesApproved] = useState(false);
  const [result, setResult] = useState<PublicTryResult | null>(null);
  const [inspection, setInspection] = useState<PublicTryInspection | null>(null);
  const [inspectingId, setInspectingId] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [reconciling, setReconciling] = useState(false);
  const [error, setError] = useState("");
  const [inspectionError, setInspectionError] = useState("");
  const [showContract, setShowContract] = useState(false);
  const [copied, setCopied] = useState(false);
  const [tutorialReplay, setTutorialReplay] = useState(0);
  const proposalHeadingRef = useRef<HTMLDivElement | null>(null);
  const verifyActionRef = useRef<HTMLButtonElement | null>(null);
  const resultHeadRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => { track("try_evidue_viewed"); }, []);

  // Public Try progression: scroll only after the next UI state has rendered.
  useEffect(() => {
    if (!analysis || rulesApproved || result) return;
    const frame = window.requestAnimationFrame(() => scrollToTryTarget(proposalHeadingRef.current));
    return () => window.cancelAnimationFrame(frame);
  }, [analysis, rulesApproved, result]);

  useEffect(() => {
    if (!rulesApproved || result) return;
    const frame = window.requestAnimationFrame(() => scrollToTryTarget(verifyActionRef.current));
    return () => window.cancelAnimationFrame(frame);
  }, [rulesApproved, result]);

  useEffect(() => {
    if (!result) return;
    const frame = window.requestAnimationFrame(() => scrollToTryTarget(resultHeadRef.current));
    return () => window.cancelAnimationFrame(frame);
  }, [result]);


  const deductionPercent = useMemo(() => {
    if (!result) return null;
    const submitted = Number(result.submitted_amount);
    return submitted > 0 ? (Number(result.recommended_deduction) / submitted) * 100 : 0;
  }, [result]);

  const disputeSummary = useMemo(() => {
    if (!result) return "";
    const example = inspection
      ? `\nRepresentative finding: ${inspection.outcome_id} — ${inspection.reason}`
      : "";
    return [
      "Subject: Nova Support AI invoice — adjustment requested",
      "",
      `We verified ${result.sample_size} billed outcomes against the approved contract rules and customer-controlled evidence.`,
      `Vendor billed: ${formatUsd(result.submitted_amount)}`,
      `Substantiated: ${formatUsd(result.confirmed_payable_amount)}`,
      `Identified for dispute: ${formatUsd(result.recommended_deduction)} (${result.disputed_outcomes} claims)`,
      `Needs review: ${result.needs_review_outcomes} claims`,
      example,
      "",
      "Please review the unsupported claims and issue the appropriate credit or corrected invoice.",
    ].filter(Boolean).join("\n");
  }, [inspection, result]);

  async function analyze() {
    setError("");
    setInspectionError("");
    setAnalyzing(true);
    setResult(null);
    setInspection(null);
    setRulesApproved(false);
    setCopied(false);
    track("try_evidue_analyze_started");
    try {
      const value = await api.analyzePublicTry();
      setAnalysis(value);
      track("try_evidue_analyzed", { live_model_call: value.live_model_call, rule_count: value.rules.length });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not analyze the sample contract.");
    } finally { setAnalyzing(false); }
  }

  function approveRules() {
    if (!analysis?.approval_ready) return;
    setRulesApproved(true);
    track("try_evidue_rules_authority_confirmed", { rule_count: analysis.rules.length });
  }

  async function verifyClaims() {
    if (!analysis?.sandbox_id || !rulesApproved) return;
    setError("");
    setInspectionError("");
    setReconciling(true);
    setInspection(null);
    track("try_evidue_verification_started", { rule_count: analysis.rules.length });
    try {
      const value = await api.approvePublicTry(analysis.sandbox_id);
      setResult(value);
      track("try_evidue_result_seen", { disputed_outcomes: value.disputed_outcomes, recommended_deduction: value.recommended_deduction });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not run the sample reconciliation.");
    } finally { setReconciling(false); }
  }

  async function inspectFinding(outcomeId: string) {
    if (!analysis?.sandbox_id) return;
    setInspectionError("");
    setInspectingId(outcomeId);
    track("try_evidue_finding_inspection_started", { outcome_id: outcomeId });
    try {
      const value = await api.inspectPublicTryOutcome(analysis.sandbox_id, outcomeId);
      setInspection(value);
      track("try_evidue_finding_inspected", {
        outcome_id: outcomeId,
        status: value.status,
        rule_id: value.rule_id ?? undefined,
      });
    } catch (exc) {
      setInspectionError(exc instanceof Error ? exc.message : "Could not inspect this claim.");
    } finally {
      setInspectingId("");
    }
  }

  async function copyDisputeSummary() {
    if (!disputeSummary) return;
    try {
      await navigator.clipboard.writeText(disputeSummary);
      setCopied(true);
      track("try_evidue_dispute_summary_copied", { disputed_outcomes: result?.disputed_outcomes ?? 0 });
    } catch {
      setInspectionError("Could not copy the dispute summary from this browser.");
    }
  }

  return (
    <Box className="try-v4-page decision-ledger-site">
      <Box component="header" className="try-v3-header">
        <Container maxWidth={false} className="try-v3-container try-v3-header-inner">
          <Brand />
          <Stack direction="row" spacing={1}>
            <Button color="inherit" onClick={() => setTutorialReplay((value) => value + 1)}>Show tutorial</Button>
            <Button component={RouterLink} to="/" color="inherit">Home</Button>
            <Button component={RouterLink} to="/contact" variant="outlined">Talk to us</Button>
          </Stack>
        </Container>
      </Box>

      <Box className={`try-v4-hero${analysis ? " is-active" : ""}`}>
        <Container maxWidth={false} className="try-v3-container try-v4-hero-grid">
          <Box className="try-v4-hero-copy" data-tour="try-intro">
            <Typography className="try-v3-kicker">PUBLIC RECONCILIATION · SYNTHETIC DATA</Typography>
            <Typography component="h1">Nova AI billed Acme $150 for 100 outcomes.</Typography>
            <Typography className="try-v4-question">Would you pay it?</Typography>
            <Typography className="try-v4-lede">Do not trust the vendor number—or the model. Establish contract authority, then verify every claim against customer-side proof.</Typography>
            {!analysis ? (
              <Button
                variant="contained"
                size="large"
                onClick={() => void analyze()}
                disabled={analyzing}
              >
                {analyzing
                  ? <><CircularProgress size={17} sx={{ mr: 1 }} />Reading contract…</>
                  : "Verify the invoice"}
              </Button>
            ) : (
              <Box className="try-v4-hero-progress" aria-live="polite">
                <span>CONTRACT INTERPRETED</span>
                <strong>{analysis.rules.length} payment rules proposed</strong>
                <Button
                  variant="contained"
                  size="large"
                  onClick={() => scrollToTryTarget(proposalHeadingRef.current)}
                >
                  Review proposed rules ↓
                </Button>
              </Box>
            )}
          </Box>
          <Box className={`try-v4-challenge${result ? " resolved" : ""}`} data-tour="try-invoice">
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

        <Box className="try-v4-step" data-step="01" data-tour="try-interpret">
          <Box className="try-v4-step-rail"><span>01</span><strong>INTERPRET</strong><small>What does the contract make billable?</small></Box>
          <Box className="try-v4-step-body">
            <Box ref={proposalHeadingRef} tabIndex={-1} className="try-v3-section-head">
              <Box><Typography className="try-v3-kicker">AI PROPOSAL · NOT YET AUTHORITY</Typography><Typography component="h2">Turn source language into explicit payment rules.</Typography></Box>
              <Stack direction="row" spacing={1}>
                {analysis && <Button variant="text" onClick={() => void analyze()}>Re-read contract</Button>}
                <Button variant="text" onClick={() => setShowContract((value) => !value)}>{showContract ? "Hide source contract" : "View source contract"}</Button>
              </Stack>
            </Box>
            {!analysis && <Typography className="try-v3-muted">Start with “Verify the invoice.” Evidue will load the synthetic agreement and propose a structured rule set.</Typography>}
            {showContract && <Box component="pre" className="try-v3-contract-source">{analysis?.contract_text ?? "Run contract analysis to load the exact synthetic contract used by this public try."}</Box>}
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

        <Box className="try-v4-step" data-step="02" data-tour="try-authorize">
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

        <Box className="try-v4-step" data-step="03" data-tour="try-verify">
          <Box className="try-v4-step-rail"><span>03</span><strong>VERIFY</strong><small>Now apply authority to proof.</small></Box>
          <Box className="try-v4-step-body try-v4-verification-step">
            <Box>
              <Typography className="try-v3-kicker">DETERMINISTIC EXECUTION</Typography>
              <Typography component="h2">Check 100 claims against approved rules and evidence.</Typography>
              <Typography className="try-v4-step-copy">The model is no longer in the decision loop. Every line becomes substantiated, contradicted, or insufficient evidence.</Typography>
            </Box>
            <Button ref={verifyActionRef} data-try-target="verify" variant="contained" size="large" onClick={() => void verifyClaims()} disabled={!rulesApproved || reconciling || Boolean(result)}>
              {reconciling ? <><CircularProgress size={18} sx={{ mr: 1 }} />Checking 100 claims…</> : result ? "100 claims verified" : "Verify 100 claims"}
            </Button>
          </Box>
        </Box>

        {result && (
          <Box className="try-v4-result-shell" data-step="04">
            <Box ref={resultHeadRef} tabIndex={-1} className="try-v4-result-head">
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
              <Box>
                <Typography className="try-v3-kicker">DON’T TRUST THE SUMMARY</Typography>
                <Typography component="h3">Inspect a failed claim here—without leaving Try Evidue.</Typography>
                <Typography className="try-v4-step-copy">Each inspection reruns the selected claim against the same approved rule program used for this 100-claim result.</Typography>
              </Box>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {result.representative_findings.map((finding) => (
                  <Button
                    key={finding.rule_id}
                    onClick={() => void inspectFinding(finding.outcome_id)}
                    variant={inspection?.outcome_id === finding.outcome_id ? "contained" : "outlined"}
                    disabled={Boolean(inspectingId)}
                  >
                    {inspectingId === finding.outcome_id ? "Inspecting…" : `${finding.rule_id} · ${finding.outcome_id}`}
                  </Button>
                ))}
              </Stack>
            </Box>

            {inspectionError && <Alert severity="error" sx={{ mt: 2 }}>{inspectionError}</Alert>}

            {inspection && (
              <Box className="try-v5-inspection" aria-label={`Inspection for ${inspection.outcome_id}`}>
                <Box className="try-v5-inspection-heading">
                  <Box>
                    <Typography className="try-v3-kicker">CLAIM AUDIT TRAIL</Typography>
                    <Typography component="h3">One charge, from assertion to financial consequence.</Typography>
                  </Box>
                  <span>{inspection.evidence.length} evidence records</span>
                </Box>

                <ClaimDecisionLedger
                  claimId={inspection.outcome_id}
                  claim={inspection.vendor_claim}
                  authorityId={inspection.rule_id ?? "No single rule"}
                  authority={inspection.rule?.clause_text ?? inspection.reason}
                  evidence={inspection.evidence.map((event) => ({
                    when: evidenceWhen(event.timestamp),
                    source: `${event.provenance.connector_name ?? humanize(event.source_system)} · ${event.source_record_id}`,
                    event: evidenceSummary(event),
                    tone: inspection.status === "disputed" ? "bad" : "neutral",
                  }))}
                  determination={determinationLabel(inspection.status)}
                  impact={inspectionImpact(inspection)}
                  synthetic
                />

                <Box className="try-v5-inspection-grid">
                  <Box className="try-v5-receipt">
                    <Typography className="try-v3-kicker">OUTCOME RECEIPT</Typography>
                    <Typography component="h4">Proof envelope</Typography>
                    <dl>
                      <div><dt>Outcome ID</dt><dd>{inspection.outcome_id}</dd></div>
                      <div><dt>Vendor claim ID</dt><dd>{inspection.vendor_claim_id}</dd></div>
                      <div><dt>Agent version</dt><dd>{inspection.agent_version}</dd></div>
                      <div><dt>Customer / account</dt><dd>{inspection.customer_id} / {inspection.account_id}</dd></div>
                      <div><dt>Approved program</dt><dd>{inspection.compilation_id} · v{inspection.program_version}</dd></div>
                      <div><dt>Engine</dt><dd>{inspection.engine_version}</dd></div>
                    </dl>
                    <Typography className="try-v5-receipt-note">The receipt connects the vendor assertion to rule authority and customer evidence. It never self-declares the charge payable.</Typography>
                  </Box>

                  <Box className="try-v5-provenance">
                    <Typography className="try-v3-kicker">EVIDENCE PROVENANCE</Typography>
                    <Typography component="h4">Where the proof came from</Typography>
                    <Box className="try-v5-provenance-list">
                      {inspection.evidence.map((event) => (
                        <Box key={event.id} className="try-v5-provenance-row">
                          <Box>
                            <strong>{event.provenance.connector_name ?? humanize(event.source_system)}</strong>
                            <small>{event.source_record_id}</small>
                          </Box>
                          <Box>
                            <span>{event.provenance.authority ?? "Customer-controlled source"}</span>
                            <small>{event.provenance.match_status ?? "matched"} · confidence {event.provenance.match_confidence ?? "—"}</small>
                          </Box>
                          <code>{shortHash(event.provenance.payload_hash)}</code>
                        </Box>
                      ))}
                    </Box>
                  </Box>
                </Box>

                <details className="try-v5-raw-proof">
                  <summary>Inspect raw source records and hashes</summary>
                  <Box className="try-v5-raw-proof-grid">
                    {inspection.evidence.map((event) => (
                      <Box key={event.id} className="try-v5-raw-record">
                        <Box className="try-v5-raw-record-head">
                          <strong>{event.provenance.connector_name ?? humanize(event.source_system)}</strong>
                          <span>{event.provenance.raw_record_id ?? event.source_record_id}</span>
                        </Box>
                        <small>{event.provenance.collection_method ?? "Synthetic source fixture"} · schema {event.provenance.schema_version ?? "—"}</small>
                        <code>{event.provenance.payload_hash ?? "No payload hash"}</code>
                        <pre>{JSON.stringify(event.provenance.raw_payload ?? event.values, null, 2)}</pre>
                      </Box>
                    ))}
                  </Box>
                </details>
              </Box>
            )}

            <Box className="try-v5-dispute-package">
              <Box className="try-v5-dispute-package-head">
                <Box>
                  <Typography className="try-v3-kicker">COMMERCIAL HANDOFF</Typography>
                  <Typography component="h3">Turn the verification into a vendor-ready dispute summary.</Typography>
                  <Typography>The factual determination stays separate from the remedy; finance decides whether to request a credit, true-up, or escalate.</Typography>
                </Box>
                <Button variant="outlined" onClick={() => void copyDisputeSummary()}>{copied ? "Copied" : "Copy dispute summary"}</Button>
              </Box>
              <Box component="pre" className="try-v5-dispute-copy">{disputeSummary}</Box>
            </Box>

            <details className="try-v5-audit-details">
              <summary>Show reproducibility details</summary>
              <Box className="try-v5-audit-grid">
                <Box><span>Sampling method</span><strong>{result.sampling_method}</strong></Box>
                <Box><span>Deterministic engine</span><strong>{result.engine_version}</strong></Box>
                <Box><span>Approved program</span><strong>{result.compilation_id} · v{result.program_version}</strong></Box>
                <Box><span>Source hash</span><code>{result.source_hash}</code></Box>
              </Box>
            </details>

            <Box className="try-v3-contact">
              <Box><Typography className="try-v3-kicker">HOW DO YOU DO THIS TODAY?</Typography><Typography component="h3">Tell us how your company verifies AI-vendor charges.</Typography><Typography>“We trust the vendor” is a useful answer.</Typography></Box>
              <Button component={RouterLink} to="/contact" variant="contained" onClick={() => track("try_evidue_talk_clicked")}>Share your workflow</Button>
            </Box>
          </Box>
        )}
      </Container>
      <GuidedTour
        storageKey="evidue.try-tour.v1"
        steps={TRY_TOUR_STEPS}
        replayToken={tutorialReplay}
        finishSelector='[data-tour="try-intro"]'
        finishLabel="Try it now"
      />
    </Box>
  );
}
