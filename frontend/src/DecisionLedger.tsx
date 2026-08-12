import { Box, Typography } from "@mui/material";
import { ReactNode } from "react";

export type DecisionLedgerTone = "neutral" | "verified" | "disputed" | "review";

export function LedgerLabel({ children, tone = "neutral" }: { children: ReactNode; tone?: DecisionLedgerTone }) {
  return <span className={`decision-ledger-label tone-${tone}`}>{children}</span>;
}

export function DecisionFlow({ compact = false }: { compact?: boolean }) {
  const stages = [
    { code: "01", verb: "INTERPRET", title: "Read the contract", detail: "AI proposes structured payment rules." },
    { code: "02", verb: "AUTHORIZE", title: "Approve the rules", detail: "A human establishes financial authority." },
    { code: "03", verb: "VERIFY", title: "Check the proof", detail: "Deterministic logic evaluates customer evidence." },
    { code: "04", verb: "ACT", title: "Resolve the dollars", detail: "Finance pays, disputes, reviews, or true-ups." },
  ];
  return (
    <Box className={`decision-flow${compact ? " compact" : ""}`} aria-label="Evidue decision flow">
      {stages.map((stage, index) => (
        <Box className="decision-flow-stage" key={stage.code}>
          <Box className="decision-flow-index">{stage.code}</Box>
          <Box className="decision-flow-copy">
            <span>{stage.verb}</span>
            <strong>{stage.title}</strong>
            {!compact && <small>{stage.detail}</small>}
          </Box>
          {index < stages.length - 1 && <b className="decision-flow-arrow" aria-hidden="true">→</b>}
        </Box>
      ))}
    </Box>
  );
}

export function FinancialEquation({
  billed,
  disputed,
  substantiated,
  review,
  caption,
}: {
  billed: string;
  disputed: string;
  substantiated: string;
  review?: string;
  caption?: string;
}) {
  return (
    <Box className="decision-equation" aria-label="Invoice financial equation">
      <Box className="decision-equation-term">
        <span>VENDOR CLAIM</span>
        <strong>{billed}</strong>
      </Box>
      <span className="decision-equation-operator">−</span>
      <Box className="decision-equation-term disputed">
        <span>UNSUPPORTED</span>
        <strong>{disputed}</strong>
      </Box>
      <span className="decision-equation-operator">=</span>
      <Box className="decision-equation-term verified">
        <span>SUBSTANTIATED</span>
        <strong>{substantiated}</strong>
      </Box>
      {review && review !== "$0" && review !== "$0.00" && (
        <Box className="decision-equation-review">
          <span>HELD FOR REVIEW</span>
          <strong>{review}</strong>
        </Box>
      )}
      {caption && <Typography className="decision-equation-caption">{caption}</Typography>}
    </Box>
  );
}

export type LedgerEvidence = {
  when?: string;
  source: string;
  event: string;
  tone?: "neutral" | "bad" | "good";
};

export function ClaimDecisionLedger({
  claimId,
  claim,
  authorityId,
  authority,
  evidence,
  determination,
  impact,
  action,
  synthetic = false,
}: {
  claimId: string;
  claim: string;
  authorityId: string;
  authority: string;
  evidence: LedgerEvidence[];
  determination: string;
  impact: string;
  action?: string;
  synthetic?: boolean;
}) {
  const statusClass = determination.toLowerCase().includes("contrad") || determination.toLowerCase().includes("disput")
    ? "disputed"
    : determination.toLowerCase().includes("review") || determination.toLowerCase().includes("insufficient")
      ? "review"
      : "verified";

  return (
    <Box className="decision-ledger" aria-label={`Decision ledger for ${claimId}`}>
      <Box className="decision-ledger-head">
        <Box>
          <LedgerLabel>CLAIM</LedgerLabel>
          <strong>{claimId}</strong>
        </Box>
        {synthetic && <span className="decision-ledger-synthetic">SYNTHETIC EXAMPLE</span>}
      </Box>

      <Box className="decision-ledger-section claim">
        <LedgerLabel>VENDOR CLAIM</LedgerLabel>
        <Typography>{claim}</Typography>
      </Box>

      <Box className="decision-ledger-section authority">
        <Box className="decision-ledger-section-title">
          <LedgerLabel tone="verified">AUTHORITY</LedgerLabel>
          <span>{authorityId}</span>
        </Box>
        <blockquote>{authority}</blockquote>
      </Box>

      <Box className="decision-ledger-section proof">
        <LedgerLabel>PROOF · CUSTOMER-CONTROLLED</LedgerLabel>
        <Box className="decision-ledger-events">
          {evidence.map((item, index) => (
            <Box className={`decision-ledger-event ${item.tone ?? "neutral"}`} key={`${item.source}-${item.event}-${index}`}>
              <span>{item.when ?? "Evidence"}</span>
              <strong>{item.event}</strong>
              <small>{item.source}</small>
            </Box>
          ))}
        </Box>
      </Box>

      <Box className={`decision-ledger-outcome ${statusClass}`}>
        <Box>
          <LedgerLabel tone={statusClass === "disputed" ? "disputed" : statusClass === "review" ? "review" : "verified"}>DETERMINATION</LedgerLabel>
          <strong>{determination.toUpperCase()}</strong>
        </Box>
        <Box>
          <LedgerLabel>FINANCIAL IMPACT</LedgerLabel>
          <strong>{impact}</strong>
        </Box>
        {action && (
          <Box>
            <LedgerLabel>COMMERCIAL ACTION</LedgerLabel>
            <strong>{action}</strong>
          </Box>
        )}
      </Box>
    </Box>
  );
}

export function AuthorityBoundary() {
  return (
    <Box className="authority-boundary-v2" aria-label="Evidue authority boundary">
      <Box>
        <LedgerLabel>AI</LedgerLabel>
        <strong>Proposes</strong>
        <small>Natural-language contract → structured interpretation</small>
      </Box>
      <span aria-hidden="true">→</span>
      <Box className="human">
        <LedgerLabel tone="verified">HUMAN</LedgerLabel>
        <strong>Authorizes</strong>
        <small>Reviewed, approved, versioned rule set</small>
      </Box>
      <span aria-hidden="true">→</span>
      <Box>
        <LedgerLabel>ENGINE</LedgerLabel>
        <strong>Determines</strong>
        <small>Approved rules + evidence → reproducible dollars</small>
      </Box>
    </Box>
  );
}
