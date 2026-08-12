import {
  Box,
  Button,
  Container,
  Link,
  Stack,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, DemoStatus, Invoice, Summary } from "./api";
import { BetaApplicationCTA, FeedbackCTA } from "./BetaApplicationCTA";
import { AuthorityBoundary, ClaimDecisionLedger, DecisionFlow, FinancialEquation } from "./DecisionLedger";
import { disclosure } from "./presentation";
import { TemplateIcon } from "./TemplateIcons";
import { track } from "./analytics";

function Brand() {
  return (
    <Stack direction="row" spacing={1.1} alignItems="center" className="landing-v3-brand">
      <Box className="landing-v3-mark" aria-hidden="true">E</Box>
      <Box>
        <Typography className="landing-v3-wordmark">Evidue</Typography>
        <Typography className="landing-v3-caption">AI vendor invoice control</Typography>
      </Box>
    </Stack>
  );
}

function formatWholeUsd(amount: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(Number(amount));
}

function wholeOrDash(amount: string | null | undefined): string {
  return amount ? formatWholeUsd(amount) : "—";
}

function percent(part: string, whole: string): string {
  const denominator = Number(whole);
  return denominator > 0 ? `${((Number(part) / denominator) * 100).toFixed(1)}%` : "0.0%";
}

function InvoiceVerdict({ invoice, summary }: { invoice: Invoice | null; summary: Summary | null }) {
  const billed = invoice?.submitted_amount ?? summary?.submitted_amount ?? null;
  const payable = summary?.confirmed_payable_amount ?? null;
  const disputed = summary?.recommended_deduction ?? null;
  const review = summary?.needs_review_amount ?? null;
  const disputedCount = summary?.disputed_outcomes ?? null;
  const disputePercent = billed && disputed ? percent(disputed, billed) : null;

  return (
    <Box className="landing-v4-verdict" aria-label="Example Evidue invoice decision">
      <Box className="landing-v4-document-head">
        <Box>
          <span className="ledger-provenance">EVIDUE / INVOICE CONTROL</span>
          <strong>NOVA SUPPORT AI</strong>
          <small>JUNE 2026 · CASE REC-2026-06-001</small>
        </Box>
        <span className="landing-v4-decision-state">DECISION COMPLETE</span>
      </Box>

      <Box className="landing-v4-document-body">
        <Box className="landing-v4-source-row">
          <span>VENDOR CLAIM</span>
          <strong>{wholeOrDash(billed)}</strong>
          <small>Source: submitted invoice</small>
        </Box>
        <Box className="landing-v4-source-row verified">
          <span>SUBSTANTIATED</span>
          <strong>{wholeOrDash(payable)}</strong>
          <small>Computed from approved authority + customer proof</small>
        </Box>
        <Box className="landing-v4-source-row disputed">
          <span>UNSUPPORTED</span>
          <strong>{wholeOrDash(disputed)}</strong>
          <small>{disputedCount === null ? "Loading persisted findings…" : `${disputedCount.toLocaleString()} contradicted claims`}</small>
        </Box>
        <Box className="landing-v4-source-row review">
          <span>NEEDS REVIEW</span>
          <strong>{wholeOrDash(review)}</strong>
          <small>Never forced into payable or disputed</small>
        </Box>
      </Box>

      <Box className="landing-v4-document-finding">
        <span>FINDING</span>
        <strong>{disputedCount === null ? "Loading persisted decision…" : `${disputedCount.toLocaleString()} charges fail approved contract verification.`}</strong>
        <p>{disputePercent ? `${disputePercent} of invoice value is not supported by the approved rules and customer evidence.` : "The result appears only after a persisted reconciliation is available."}</p>
      </Box>

      <Box className="landing-v4-document-foot">
        <span>AUTHORITY · approved contract rules</span>
        <span>PROOF · customer-controlled systems</span>
        <span>METHOD · deterministic</span>
      </Box>
    </Box>
  );
}

export default function LandingPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<DemoStatus | null>(null);
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);

  useEffect(() => {
    track("landing_viewed");
    let active = true;
    void Promise.all([api.status(), api.invoice()]).then(([statusResult, invoiceResult]) => {
      if (!active) return;
      setStatus(statusResult);
      setInvoice(invoiceResult);
      if (statusResult.reconciled) {
        void api.current().then((result) => { if (active) setSummary(result); }).catch(() => undefined);
      }
    }).catch(() => undefined);
    return () => { active = false; };
  }, []);

  const billed = invoice?.submitted_amount ?? summary?.submitted_amount ?? null;
  const payable = summary?.confirmed_payable_amount ?? null;
  const disputed = summary?.recommended_deduction ?? null;
  const review = summary?.needs_review_amount ?? null;

  return (
    <Box className="landing-v3-page decision-ledger-site">
      <Box component="header" className="landing-v3-header">
        <Container maxWidth={false} className="landing-v3-container">
          <Box component="nav" className="landing-v3-nav" aria-label="Main navigation">
            <Brand />
            <Stack direction="row" spacing={3} className="landing-v3-nav-links">
              <Link href="#how-it-works">How it works</Link>
              <Link href="#proof">See a decision</Link>
              <Link href="#boundary">Authority boundary</Link>
            </Stack>
            <Stack direction="row" spacing={1} alignItems="center">
              <BetaApplicationCTA compact />
              <Button variant="contained" className="landing-v3-nav-cta" onClick={() => navigate("/try")}>Verify a sample invoice</Button>
            </Stack>
          </Box>
        </Container>
      </Box>

      <Box className="landing-v4-hero">
        <Container maxWidth={false} className="landing-v3-container landing-v4-hero-grid">
          <Box className="landing-v4-hero-copy">
            <Typography className="landing-v3-kicker">BUYER-SIDE CONTROL FOR OUTCOME-PRICED AI</Typography>
            <Typography component="h1">Stop paying AI vendors for outcomes that didn’t happen.</Typography>
            <Typography className="landing-v4-lede">
              Evidue checks every billed outcome against the contract you approved and evidence from your own systems—then gives finance a traceable dollar decision.
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.25} className="landing-v3-actions">
              <Button variant="contained" size="large" endIcon={<TemplateIcon name="arrow" size={17} />} onClick={() => navigate("/try")}>Verify a sample invoice</Button>
              <Button variant="text" size="large" onClick={() => navigate(`/demo/invoices/current?outcome=${encodeURIComponent(status?.demo_outcome_id ?? "OUT-004821")}`)}>Inspect a disputed claim</Button>
            </Stack>
            <Box className="landing-v4-trust-row">
              <span>AI proposes</span><b>→</b><span>Human approves</span><b>→</b><span>Code decides dollars</span>
            </Box>
            <Typography className="landing-v3-synthetic-note">Synthetic demonstration data · no signup · no customer data</Typography>
          </Box>
          <InvoiceVerdict invoice={invoice} summary={summary} />
        </Container>
      </Box>

      <Container maxWidth={false} className="landing-v3-container">
        <Box id="how-it-works" className="landing-v4-flow-section">
          <Box className="landing-v3-section-intro">
            <Typography className="landing-v3-kicker">ONE CONTROL LOOP</Typography>
            <Typography component="h2">From vendor assertion to finance action.</Typography>
            <Typography>The interface follows the same authority chain on every surface, so users never have to guess which system or model produced a number.</Typography>
          </Box>
          <DecisionFlow />
        </Box>

        <Box className="landing-v4-equation-section">
          <Box>
            <Typography className="landing-v3-kicker">THE FINANCIAL QUESTION FIRST</Typography>
            <Typography component="h2">What is this invoice actually worth?</Typography>
            <Typography>Evidue keeps unsupported and insufficient-evidence dollars visible instead of burying them in a confidence score.</Typography>
          </Box>
          <FinancialEquation
            billed={wholeOrDash(billed)}
            disputed={wholeOrDash(disputed)}
            substantiated={wholeOrDash(payable)}
            review={wholeOrDash(review)}
            caption="Persisted synthetic June reconciliation. No value is invented before the result loads."
          />
        </Box>

        <Box className="landing-v4-proof-section" id="proof">
          <Box className="landing-v3-section-intro">
            <Typography className="landing-v3-kicker">THE EVIDUE DECISION LEDGER</Typography>
            <Typography component="h2">Every disputed dollar has a claim, authority, and proof chain.</Typography>
            <Typography>Finance can move from the invoice-level difference down to the exact contract clause and customer event that changed a charge.</Typography>
          </Box>
          <ClaimDecisionLedger
            claimId="OUT-004821"
            claim="Vendor marked this customer outcome as successfully resolved and billable."
            authorityId="R1 · NO SAME-INTENT RECONTACT"
            authority="A resolution is billable only if there is no same-intent customer recontact within seven days."
            evidence={[
              { when: "JUN 12 · 14:03", source: "Vendor resolution event", event: "Outcome marked resolved", tone: "neutral" },
              { when: "JUN 15 · 09:21", source: "Customer support system", event: "Customer recontacted with the same intent", tone: "bad" },
            ]}
            determination="Contradicted"
            impact="$1.50 identified for dispute"
            action="Request vendor credit / dispute per contract"
            synthetic
          />
        </Box>

        <Box className="landing-v4-boundary" id="boundary">
          <Box className="landing-v3-section-intro">
            <Typography className="landing-v3-kicker">THE MODEL STOPS BEFORE THE MONEY</Typography>
            <Typography component="h2">The LLM interprets the contract. It never decides the invoice.</Typography>
            <Typography>The model can propose a structured interpretation. A human must authorize it. Only then can deterministic logic apply those rules to customer evidence.</Typography>
          </Box>
          <AuthorityBoundary />
        </Box>

        <Box className="landing-v4-action-section">
          <Box>
            <Typography className="landing-v3-kicker">FROM FINDING TO VENDOR ACTION</Typography>
            <Typography component="h2">The decision ends in an artifact finance can use.</Typography>
            <Typography>Corrected invoice, disputed lines, evidence package, and vendor communication are all generated from the same persisted reconciliation.</Typography>
          </Box>
          <Box className="landing-v4-email">
            <Box className="landing-v4-email-head"><span>COMMERCIAL ACTION</span><strong>REQUEST VENDOR CREDIT</strong></Box>
            <Typography component="p">We reconciled your June invoice against our agreement and customer-controlled systems.</Typography>
            <Typography component="p"><strong>Of $15,000 billed, $12,480 is substantiated. We identified $2,520 across 1,680 claims for dispute.</strong></Typography>
            <Typography component="p">The attached package includes affected invoice lines, governing rules, and supporting evidence references.</Typography>
            <Box className="landing-v4-email-actions"><span>COPY EMAIL</span><span>DISPUTE PACKAGE</span><span>DISPUTED LINES</span></Box>
          </Box>
        </Box>

        <Box className="landing-v3-final-cta">
          <Box><Typography className="landing-v3-kicker">TRY THE CONTROL LOOP</Typography><Typography component="h2">Would you pay the vendor’s number?</Typography></Box>
          <Button variant="contained" size="large" onClick={() => navigate("/try")}>Verify the sample invoice →</Button>
        </Box>
      </Container>

      <Box component="footer" className="landing-v3-footer">
        <Container maxWidth={false} className="landing-v3-container">
          <Brand />
          <Typography>{disclosure}</Typography>
          <FeedbackCTA />
        </Container>
      </Box>
    </Box>
  );
}
