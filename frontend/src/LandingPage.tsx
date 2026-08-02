import {
  Alert,
  Box,
  Button,
  Chip,
  Container,
  Divider,
  Link,
  Stack,
  Typography,
} from "@mui/material";
import { ReactNode, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, DemoStatus, Invoice, Summary } from "./api";
import { disclosure, formatUsd } from "./presentation";
import { TemplateIcon } from "./TemplateIcons";

function BrandMark() {
  return <Box className="landing-brand-mark" aria-hidden="true"><span>E</span></Box>;
}

function LandingBrand() {
  return (
    <Stack direction="row" spacing={1.2} alignItems="center">
      <BrandMark />
      <Box>
        <Typography className="landing-wordmark">Evidue</Typography>
        <Typography className="landing-brand-caption">Outcome invoice control</Typography>
      </Box>
    </Stack>
  );
}

function WorkflowStep({ number, icon, title, body }: { number: string; icon: ReactNode; title: string; body: string }) {
  return (
    <Box className="landing-workflow-step">
      <Box className="landing-step-icon">{icon}</Box>
      <Typography className="landing-step-number">{number}</Typography>
      <Typography variant="h6">{title}</Typography>
      <Typography color="text.secondary">{body}</Typography>
    </Box>
  );
}

export default function LandingPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<DemoStatus | null>(null);
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);

  useEffect(() => {
    let active = true;
    void Promise.all([api.status(), api.invoice()]).then(([statusResult, invoiceResult]) => {
      if (!active) return;
      setStatus(statusResult);
      setInvoice(invoiceResult);
      if (statusResult.reconciled) {
        void api.current().then((summaryResult) => {
          if (active) setSummary(summaryResult);
        }).catch(() => undefined);
      }
    }).catch(() => undefined);
    return () => { active = false; };
  }, []);

  return (
    <Box className="landing-page">
      <Box className="landing-nav-wrap">
        <Container maxWidth="lg">
          <Box component="nav" className="landing-nav" aria-label="Main navigation">
            <LandingBrand />
            <Stack direction="row" spacing={3} className="landing-nav-links">
              <Link href="#control-boundary">Control boundary</Link>
              <Link href="#workflow">How it works</Link>
              <Link href="#evidence">Evidence</Link>
            </Stack>
              <Button variant="outlined" endIcon={<TemplateIcon name="arrow" size={17} />} onClick={() => navigate("/demo/invoices/current")}>
              Open demo
            </Button>
          </Box>
        </Container>
      </Box>

      <Box component="main">
        <Container maxWidth="lg">
          <Box className="landing-hero">
            <Box className="landing-hero-copy">
              <Chip className="landing-kicker" label="Financial control for outcome-priced AI" icon={<span className="landing-kicker-dot" />} />
              <Typography component="h1">Know what the AI vendor actually earned.</Typography>
              <Typography className="landing-hero-lede">
                Evidue reconciles outcome-priced AI invoices against the contract and customer-owned operational evidence before money moves.
              </Typography>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1.25} sx={{ mt: 3 }}>
                <Button variant="contained" size="large" endIcon={<TemplateIcon name="arrow" size={17} />} onClick={() => navigate("/demo/invoices/current")}>
                  Review the decision
                </Button>
                <Button variant="outlined" size="large" onClick={() => navigate("/demo/contracts/current")}>
                  Inspect contract rules
                </Button>
              </Stack>
              <Typography className="landing-hero-note">
                One invoice enters. One defensible payable amount leaves.
              </Typography>
            </Box>

            <Box className="landing-decision-preview" aria-label="Live decision preview">
              <Box className="landing-preview-header">
                <Box>
                  <Typography className="landing-overline">Current decision</Typography>
                  <Typography variant="h6">Acme Commerce · June 2026</Typography>
                </Box>
                <Chip label={status?.public_demo ? "Read-only preview" : "Synthetic workspace"} size="small" />
              </Box>
              <Divider />
              <Box className="landing-preview-main">
                <Typography className="landing-overline">Corrected payable amount</Typography>
                <Typography className="landing-payable">{summary ? formatUsd(summary.confirmed_payable_amount) : "Decision workspace"}</Typography>
                <Typography color="text.secondary">
                  {summary ? `${summary.payable_outcomes.toLocaleString()} payable outcomes from ${summary.claimed_outcomes.toLocaleString()} claims` : invoice ? `${invoice.claimed_outcomes.toLocaleString()} submitted outcomes ready for review` : "Contract, evidence, and determinations in one place"}
                </Typography>
              </Box>
              <Box className="landing-preview-facts">
                <Box><span>Submitted invoice</span><strong>{invoice ? formatUsd(invoice.submitted_amount) : "—"}</strong></Box>
                <Box><span>Recommended deduction</span><strong className="disputed">{summary ? formatUsd(summary.recommended_deduction) : "—"}</strong></Box>
                <Box><span>Needs review</span><strong className="review">{summary ? formatUsd(summary.needs_review_amount) : "—"}</strong></Box>
              </Box>
              <Box className="landing-preview-footer">
                <TemplateIcon name="check" size={16} /> Deterministic result · Evidence attached to every finding
              </Box>
            </Box>
          </Box>

          <Alert icon={false} className="landing-disclosure">
            <strong>Synthetic demonstration data.</strong> {disclosure}
          </Alert>

          <Box id="control-boundary" className="landing-boundary">
            <Box>
              <Typography className="landing-overline">The control boundary</Typography>
              <Typography variant="h3">The model can propose. It cannot decide what gets paid.</Typography>
            </Box>
            <Typography color="text.secondary">
              Contract language becomes a constrained rule program. A human approves the immutable version. Deterministic code evaluates every invoice line against evidence that remains customer-controlled.
            </Typography>
          </Box>

          <Box id="workflow" className="landing-section">
            <Box className="landing-section-heading">
              <Typography className="landing-overline">A defensible path to payment</Typography>
              <Typography variant="h3">From vendor claim to payable amount.</Typography>
            </Box>
            <Box className="landing-workflow-grid">
              <WorkflowStep number="01" icon={<TemplateIcon name="contract" size={18} />} title="Read the contract" body="Translate billing terms into explicit, executable rules." />
              <WorkflowStep number="02" icon={<TemplateIcon name="data" size={18} />} title="Join the evidence" body="Connect each claim to customer-owned operational records." />
              <WorkflowStep number="03" icon={<TemplateIcon name="verify" size={18} />} title="Determine every line" body="Classify outcomes as payable, disputed, or needs review." />
              <WorkflowStep number="04" icon={<TemplateIcon name="ledger" size={18} />} title="Hand off with proof" body="Export the corrected amount and evidence-backed dispute package." />
            </Box>
          </Box>

          <Box id="evidence" className="landing-evidence-section">
            <Box className="landing-evidence-copy">
              <Typography className="landing-overline">Built for finance and procurement</Typography>
              <Typography variant="h3">Make the invoice reviewable, not arguable.</Typography>
              <Typography color="text.secondary">
                See the exact clause, source record, timeline, and determination behind a disputed outcome. No quality score stands in for a payment decision.
              </Typography>
              <Button sx={{ mt: 2 }} variant="outlined" endIcon={<TemplateIcon name="arrow" size={17} />} onClick={() => navigate("/demo/invoices/current?outcome=OUT-004821")}>
                Review the example dispute
              </Button>
            </Box>
            <Box className="landing-evidence-list">
              {["Customer-owned evidence stays distinct from vendor claims", "Every deduction references a contract rule", "Exports match the decision shown in the workspace"].map((item) => (
                <Box key={item}><TemplateIcon name="check" size={16} /><Typography>{item}</Typography></Box>
              ))}
            </Box>
          </Box>
        </Container>

        <Box className="landing-cta-band">
          <Container maxWidth="lg">
            <Box className="landing-cta-inner">
              <Box>
                <Typography className="landing-overline">See the control in operation</Typography>
                <Typography variant="h3">Review one complete invoice workflow.</Typography>
              </Box>
              <Button variant="contained" size="large" endIcon={<TemplateIcon name="arrow" size={17} />} onClick={() => navigate("/demo/invoices/current")}>
                Open the Evidue demo
              </Button>
            </Box>
          </Container>
        </Box>
      </Box>

      <Box component="footer" className="landing-footer">
        <Container maxWidth="lg">
          <LandingBrand />
          <Typography>Independent control for outcome-priced AI invoices · Synthetic demonstration only</Typography>
        </Container>
      </Box>
    </Box>
  );
}
