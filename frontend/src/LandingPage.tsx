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
import { disclosure, formatUsd } from "./presentation";
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
    <Box className="landing-v3-verdict" aria-label="Example Evidue invoice decision">
      <Box className="landing-v3-verdict-top">
        <Box>
          <Typography className="landing-v3-mono-label">NOVA SUPPORT AI · JUNE 2026</Typography>
          <Typography component="h2">Invoice decision</Typography>
        </Box>
        <span className="landing-v3-status">DECISION COMPLETE</span>
      </Box>

      <Box className="landing-v3-money-grid">
        <Box>
          <span>Vendor billed</span>
          <strong>{wholeOrDash(billed)}</strong>
        </Box>
        <Box>
          <span>Verified payable</span>
          <strong>{wholeOrDash(payable)}</strong>
        </Box>
        <Box className="is-dispute">
          <span>Identified for dispute</span>
          <strong>{wholeOrDash(disputed)}</strong>
        </Box>
        <Box>
          <span>Needs review</span>
          <strong>{wholeOrDash(review)}</strong>
        </Box>
      </Box>

      <Box className="landing-v3-disposition">
        <Box className="landing-v3-disposition-copy">
          <strong>{disputedCount === null ? "Loading persisted decision…" : `${disputedCount.toLocaleString()} charges fail approved contract verification.`}</strong>
          <span>{disputePercent ? `${disputePercent} of invoice value is not supported by the approved rules and customer evidence.` : "The result appears only after a persisted reconciliation is available."}</span>
        </Box>
        {disputePercent && (
          <Box className="landing-v3-bar" aria-label={`${disputePercent} identified for dispute`}>
            <Box className="verified" sx={{ width: `${100 - Number(disputePercent.replace("%", ""))}%` }} />
            <Box className="disputed" sx={{ width: disputePercent }} />
          </Box>
        )}
      </Box>

      <Box className="landing-v3-findings">
        <Box className="landing-v3-findings-head"><span>Why the invoice changed</span><span>Exposure</span></Box>
        {summary && Object.entries(summary.categories).length > 0 ? (
          Object.entries(summary.categories).slice(0, 3).map(([ruleId, category]) => (
            <Box key={ruleId} className="landing-v3-finding-row">
              <Box><span>{ruleId}</span><strong>{category.label}</strong><small>{category.count.toLocaleString()} affected claims</small></Box>
              <strong>{formatUsd(category.amount)}</strong>
            </Box>
          ))
        ) : (
          <Box className="landing-v3-finding-row">
            <Box><span>—</span><strong>Loading persisted findings</strong><small>No financial finding is invented before the reconciliation loads.</small></Box><strong>—</strong>
          </Box>
        )}
      </Box>

      <Box className="landing-v3-verdict-foot">
        <TemplateIcon name="check" size={15} />
        <span>Every dollar traces back to an approved rule and customer-controlled evidence.</span>
      </Box>
    </Box>
  );
}

function Mechanism() {
  const items = [
    ["01", "Contract", "Natural-language commercial terms"],
    ["02", "AI proposal", "Structured rules, still inert"],
    ["03", "Human approval", "Finance activates the rule set"],
    ["04", "Evidence", "Customer systems prove what happened"],
    ["05", "Deterministic dollars", "Code calculates the financial result"],
  ];
  return (
    <Box className="landing-v3-mechanism" id="how-it-works">
      {items.map(([number, title, detail], index) => (
        <Box className="landing-v3-mechanism-step" key={title}>
          <span>{number}</span>
          <strong>{title}</strong>
          <small>{detail}</small>
          {index < items.length - 1 && <b aria-hidden="true">→</b>}
        </Box>
      ))}
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

  return (
    <Box className="landing-v3-page">
      <Box component="header" className="landing-v3-header">
        <Container maxWidth={false} className="landing-v3-container">
          <Box component="nav" className="landing-v3-nav" aria-label="Main navigation">
            <Brand />
            <Stack direction="row" spacing={3} className="landing-v3-nav-links">
              <Link href="#how-it-works">How it works</Link>
              <Link href="#proof">Evidence</Link>
              <Link href="#boundary">Authority boundary</Link>
            </Stack>
            <Stack direction="row" spacing={1} alignItems="center">
              <BetaApplicationCTA compact />
              <Button variant="contained" className="landing-v3-nav-cta" onClick={() => navigate("/try")}>Verify a sample invoice</Button>
            </Stack>
          </Box>
        </Container>
      </Box>

      <Box className="landing-v3-hero">
        <Container maxWidth={false} className="landing-v3-container landing-v3-hero-grid">
          <Box className="landing-v3-hero-copy">
            <Typography className="landing-v3-kicker">BUYER-SIDE CONTROL FOR OUTCOME-PRICED AI</Typography>
            <Typography component="h1">Stop paying AI vendors for outcomes that didn’t happen.</Typography>
            <Typography className="landing-v3-lede">
              Evidue checks every billed AI outcome against your contract and your own systems, then shows finance exactly what is supported, what is not, and why.
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.25} className="landing-v3-actions">
              <Button variant="contained" size="large" endIcon={<TemplateIcon name="arrow" size={17} />} onClick={() => navigate("/try")}>Verify a sample invoice</Button>
              <Button variant="text" size="large" onClick={() => navigate(`/demo/invoices/current?outcome=${encodeURIComponent(status?.demo_outcome_id ?? "OUT-004821")}`)}>Inspect a disputed claim</Button>
            </Stack>
            <Box className="landing-v3-proofline">
              <span><b>{wholeOrDash(billed)}</b> billed</span>
              <span><b>{wholeOrDash(payable)}</b> verified</span>
              <span className="danger"><b>{wholeOrDash(disputed)}</b> dispute</span>
            </Box>
            <Typography className="landing-v3-synthetic-note">Synthetic demonstration data · no signup · no customer data</Typography>
          </Box>
          <InvoiceVerdict invoice={invoice} summary={summary} />
        </Container>
      </Box>

      <Container maxWidth={false} className="landing-v3-container">
        <Mechanism />

        <Box className="landing-v3-proof-section" id="proof">
          <Box className="landing-v3-section-intro">
            <Typography className="landing-v3-kicker">ONE CHARGE. ONE PROOF CHAIN.</Typography>
            <Typography component="h2">See why a vendor claim stops being payable.</Typography>
            <Typography>Finance does not get a score. It gets the governing clause, the customer-side evidence, and the resulting financial determination.</Typography>
          </Box>
          <Box className="landing-v3-proof-chain">
            <Box className="landing-v3-proof-column">
              <Typography className="landing-v3-mono-label">CONTRACT CLAUSE</Typography>
              <blockquote>“A resolution is billable only if there is no same-intent customer recontact within seven days.”</blockquote>
              <Box className="landing-v3-proof-meta"><span>Approved rule</span><strong>R1 · No same-intent recontact</strong></Box>
            </Box>
            <Box className="landing-v3-proof-column evidence">
              <Typography className="landing-v3-mono-label">CUSTOMER EVIDENCE</Typography>
              <Box className="landing-v3-event"><span>Jun 12 · 14:03</span><strong>Vendor marked outcome resolved</strong><small>Support event</small></Box>
              <Box className="landing-v3-event is-bad"><span>Jun 15 · 09:21</span><strong>Customer recontacted with same intent</strong><small>Customer support system</small></Box>
            </Box>
            <Box className="landing-v3-determination">
              <Typography className="landing-v3-mono-label">DETERMINATION</Typography>
              <strong>CONTRADICTED</strong>
              <Typography>This charge fails the approved rule.</Typography>
              <Box><span>Commercial action</span><b>Identify for dispute</b></Box>
            </Box>
          </Box>
        </Box>

        <Box className="landing-v3-boundary" id="boundary">
          <Box>
            <Typography className="landing-v3-kicker">THE MODEL STOPS BEFORE THE MONEY</Typography>
            <Typography component="h2">The LLM interprets the contract. It never decides the invoice.</Typography>
            <Typography>Evidue keeps interpretation and financial authority separate: the model proposes structured rules, a human approves them, and deterministic code evaluates evidence and calculates the result.</Typography>
          </Box>
          <Box className="landing-v3-boundary-diagram">
            <Box><span>LLM</span><strong>Propose</strong><small>Contract → structured rule proposal</small></Box>
            <b>→</b>
            <Box><span>HUMAN</span><strong>Approve</strong><small>Versioned financial authority</small></Box>
            <b>→</b>
            <Box className="is-final"><span>ENGINE</span><strong>Decide dollars</strong><small>Rules + evidence → financial result</small></Box>
          </Box>
        </Box>

        <Box className="landing-v3-action-section">
          <Box>
            <Typography className="landing-v3-kicker">FROM FINDING TO VENDOR ACTION</Typography>
            <Typography component="h2">The reconciliation ends with something finance can send.</Typography>
            <Typography>Corrected invoice, disputed lines, evidence package, and a pre-written vendor dispute email—all generated from the persisted decision.</Typography>
          </Box>
          <Box className="landing-v3-email">
            <Typography className="landing-v3-mono-label">VENDOR DISPUTE EMAIL</Typography>
            <Typography component="p">We reconciled your June invoice against our agreement and customer systems.</Typography>
            <Typography component="p"><strong>Of $15,000 billed, $12,480 is verified. We are disputing $2,520 across 1,680 claims.</strong></Typography>
            <Typography component="p">Detailed line-level documentation and supporting evidence are attached.</Typography>
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
