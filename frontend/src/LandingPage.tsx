import {
  Alert,
  Box,
  Button,
  Chip,
  Container,
  Link,
  Stack,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, DemoStatus, Invoice, Summary } from "./api";
import { BetaApplicationCTA, FeedbackCTA } from "./BetaApplicationCTA";
import { disclosure, formatPercent, formatUsd } from "./presentation";
import { TemplateIcon } from "./TemplateIcons";
import { track } from "./analytics";

function Brand() {
  return (
    <Stack direction="row" spacing={1.15} alignItems="center">
      <Box className="landing-brand-mark" aria-hidden="true"><span>E</span></Box>
      <Box>
        <Typography className="landing-wordmark">Evidue</Typography>
        <Typography className="landing-brand-caption">Outcome invoice control</Typography>
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

function DecisionSurface({ invoice, summary }: { invoice: Invoice | null; summary: Summary | null }) {
  const categories = summary ? Object.entries(summary.categories) : [];
  return (
    <Box className="landing-product-frame" aria-label="Evidue payment decision preview">
      <Box className="landing-product-bar">
        <Stack direction="row" spacing={1.1} alignItems="center">
          <Box className="landing-mini-mark">E</Box>
          <Box>
            <Typography>Payment decision</Typography>
            <Typography>June 2026 · Nova Support AI</Typography>
          </Box>
        </Stack>
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip label="Decision complete" size="small" />
          <span className="landing-product-avatar">AC</span>
        </Stack>
      </Box>

      <Box className="landing-product-body">
        <Box className="landing-product-heading">
          <Box>
            <Typography className="landing-overline">Invoice control</Typography>
            <Typography variant="h5">Acme Commerce</Typography>
            <Typography>{invoice?.invoice_id ?? "Current invoice"} · Customer-approved rule program</Typography>
          </Box>
          <Button size="small" variant="outlined" href="/api/reconciliations/current/exports/summary.json">
            Export decision
          </Button>
        </Box>

        <Box className="landing-decision-strip">
          <Box className="landing-primary-result">
            <Typography className="landing-overline">Corrected payable amount</Typography>
            <Typography>{summary ? formatUsd(summary.confirmed_payable_amount) : invoice ? "Pending" : "Loading…"}</Typography>
            <Typography>{summary ? `${summary.payable_outcomes.toLocaleString()} outcomes payable` : invoice ? "Open the workspace to complete this decision" : "Loading persisted decision"}</Typography>
          </Box>
          <Box className="landing-secondary-results">
            <Box><span>Submitted</span><strong>{invoice ? formatUsd(invoice.submitted_amount) : "—"}</strong></Box>
            <Box><span>Recommended deduction</span><strong className="is-disputed">{summary ? formatUsd(summary.recommended_deduction) : "—"}</strong></Box>
            <Box><span>Needs review</span><strong className="is-review">{summary ? formatUsd(summary.needs_review_amount) : "—"}</strong></Box>
          </Box>
        </Box>

        <Box className="landing-findings-preview">
          <Box className="landing-findings-head">
            <span>Rule</span><span>Finding</span><span>Outcomes</span><span>Amount</span>
          </Box>
          {categories.slice(0, 3).map(([ruleId, category]) => (
            <Box className="landing-finding-row" key={ruleId}>
              <span>{ruleId}</span>
              <strong>{category.label}</strong>
              <span>{category.count.toLocaleString()}</span>
              <span>{formatUsd(category.amount)}</span>
            </Box>
          ))}
          {!summary && <Box className="landing-product-loading">No determination is available in this workspace yet.</Box>}
        </Box>
        <Box className="landing-product-foot"><TemplateIcon name="check" size={15} /> Every amount is reproduced from stored determinations.</Box>
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

  const categories = summary ? Object.entries(summary.categories) : [];

  return (
    <Box className="landing-page">
      <Box component="header" className="landing-header">
        <Container maxWidth="xl" className="landing-container">
          <Box component="nav" className="landing-nav" aria-label="Main navigation">
            <Brand />
            <Stack direction="row" spacing={3.5} className="landing-nav-links">
              <Link href="#product">Product</Link>
              <Link href="#findings">Findings</Link>
              <Link href="#control">Control boundary</Link>
            </Stack>
            <Stack direction="row" spacing={1} alignItems="center">
              {status?.public_demo && <Chip label="Public technical preview" size="small" className="landing-preview-chip" />}
              <BetaApplicationCTA compact />
              <Button variant="text" endIcon={<TemplateIcon name="arrow" size={16} />} onClick={() => navigate("/try")}>
                Try Evidue
              </Button>
            </Stack>
          </Box>
        </Container>
      </Box>

      <Box className="landing-hero-shell">
        <Container maxWidth="xl" className="landing-container">
          <Box className="landing-hero">
            <Box className="landing-hero-copy">
              <Typography className="landing-hero-eyebrow">Buyer-side control for outcome-priced AI</Typography>
              <Typography component="h1">Pay for outcomes that actually happened.</Typography>
              <Typography className="landing-hero-lede">
                Evidue checks outcome-priced AI vendor invoices against the contract and the customer’s own system evidence.
              </Typography>
              {summary && invoice && (
                <Typography className="landing-preview-result">
                  This technical preview reconciles {summary.claimed_outcomes.toLocaleString()} synthetic outcomes and determines that {formatWholeUsd(summary.confirmed_payable_amount)} of a {formatWholeUsd(invoice.submitted_amount)} invoice is payable.
                </Typography>
              )}
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1.1} sx={{ mt: 3 }}>
                <Button variant="contained" size="large" endIcon={<TemplateIcon name="arrow" size={17} />} onClick={() => navigate("/try")}>
                  Try the reconciliation — no signup
                </Button>
                <Button variant="text" size="large" onClick={() => navigate(`/demo/invoices/current?outcome=${encodeURIComponent(status?.demo_outcome_id ?? "OUT-004821")}`)}>
                  Inspect one disputed outcome
                </Button>
              </Stack>
              <Box className="landing-trust-line">
                <span><TemplateIcon name="check" size={14} /> Customer-owned evidence</span>
                <span><TemplateIcon name="check" size={14} /> Approved contract rules</span>
                <span><TemplateIcon name="check" size={14} /> Deterministic decisions</span>
              </Box>
            </Box>
            <Box id="product" className="landing-product-wrap">
              <DecisionSurface invoice={invoice} summary={summary} />
            </Box>
          </Box>
        </Container>
      </Box>

      <Box className="landing-disclosure-wrap">
        <Container maxWidth="xl" className="landing-container">
          <Alert icon={false} className="landing-disclosure">
            <strong>Synthetic demonstration data.</strong> {disclosure}
          </Alert>
        </Container>
      </Box>

      <Box className="landing-workflow-rail">
        <Container maxWidth="xl" className="landing-container">
          <Box className="landing-workflow-label">One review path</Box>
          {["Decision", "Findings", "Contract rules", "Evidence"].map((item, index) => (
            <Box key={item} className="landing-workflow-item">
              <span>0{index + 1}</span><strong>{item}</strong>{index < 3 && <TemplateIcon name="arrow" size={16} />}
            </Box>
          ))}
        </Container>
      </Box>

      <Container maxWidth="xl" className="landing-container">
        <Box id="findings" className="landing-proof-section">
          <Box className="landing-section-copy">
            <Typography className="landing-overline">The financial consequence is explicit</Typography>
            <Typography variant="h2">A deduction finance can defend.</Typography>
            <Typography>
              Every disputed line points to the rule it failed and the operational records that prove why. Finance gets a corrected payable amount, not another dashboard to interpret.
            </Typography>
            <Button variant="outlined" endIcon={<TemplateIcon name="arrow" size={16} />} onClick={() => navigate("/demo/disputes/current")}>
              Review all findings
            </Button>
          </Box>

          <Box className="landing-proof-table" aria-label="Finding summary preview">
            <Box className="landing-proof-table-head"><span>Finding</span><span>Count</span><span>Amount</span><span>Share</span></Box>
            {categories.map(([ruleId, category]) => (
              <Box className="landing-proof-table-row" key={ruleId}>
                <Box><span>{ruleId}</span><strong>{category.label}</strong></Box>
                <span>{category.count.toLocaleString()}</span>
                <span>{formatUsd(category.amount)}</span>
                <span>{summary ? formatPercent(category.amount, summary.submitted_amount) : "—"}</span>
              </Box>
            ))}
            {summary ? (
              <Box className="landing-proof-total">
                <span>Recommended deduction</span>
                <strong>{formatUsd(summary.recommended_deduction)}</strong>
              </Box>
            ) : <Box className="landing-proof-empty">Run the deterministic reconciliation to populate the finding register.</Box>}
          </Box>
        </Box>

        <Box id="control" className="landing-control-section">
          <Box className="landing-control-heading">
            <Typography className="landing-overline">A hard boundary around the model</Typography>
            <Typography variant="h2">The LLM proposes. Deterministic code decides.</Typography>
          </Box>
          <Box className="landing-control-flow">
            <Box><span>01</span><TemplateIcon name="contract" size={20} /><strong>Contract language</strong><small>Commercial terms supplied by the customer</small></Box>
            <TemplateIcon name="arrow" size={18} />
            <Box><span>02</span><TemplateIcon name="lab" size={20} /><strong>Rule proposal</strong><small>Schema-constrained and inert</small></Box>
            <TemplateIcon name="arrow" size={18} />
            <Box><span>03</span><TemplateIcon name="check" size={20} /><strong>Human approval</strong><small>Immutable version becomes active</small></Box>
            <TemplateIcon name="arrow" size={18} />
            <Box><span>04</span><TemplateIcon name="verify" size={20} /><strong>Invoice decision</strong><small>Evidence and rules determine money</small></Box>
          </Box>
        </Box>

        <Box className="landing-example-section">
          <Box>
            <Typography className="landing-overline">See the proof chain</Typography>
            <Typography variant="h2">One failed refund. Three systems. One non-payable charge.</Typography>
          </Box>
          <Box className="landing-example-facts">
            <Box><span>Vendor assertion</span><strong>Refund resolved</strong><small>Agent execution log</small></Box>
            <Box><span>Customer evidence</span><strong>Processor rejected</strong><small>Payment system of record</small></Box>
            <Box><span>Determination</span><strong>Disputed</strong><small>Rule R3 · downstream completion</small></Box>
          </Box>
          <Button variant="contained" endIcon={<TemplateIcon name="arrow" size={16} />} onClick={() => navigate("/demo/invoices/current?outcome=OUT-004821")}>
            Open OUT-004821
          </Button>
        </Box>
      </Container>

      <Box component="footer" className="landing-footer">
        <Container maxWidth="xl" className="landing-container">
          <Brand />
          <Typography>Independent control for outcome-priced AI invoices</Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            <FeedbackCTA />
            <Typography>Acme Commerce and Nova Support AI are fictional demonstration parties.</Typography>
          </Stack>
        </Container>
      </Box>
    </Box>
  );
}
