import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { Button, Card, CardContent, Chip, Container, Typography } from "@mui/material";
import "./style.css";

type Summary = { payable_amount: string; recommended_deduction: string; claimed_outcomes: number; payable_outcomes: number; disputed_outcomes: number };
const api = (path: string, options?: RequestInit) => fetch(`/api${path}`, options).then((response) => response.ok ? response.json() : Promise.reject(new Error("Request failed")));
const money = (value: string) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value));

function App() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  async function run() { setLoading(true); setError(""); try { setSummary(await api("/reconciliations", { method: "POST" })); } catch { setError("Reconciliation could not be completed."); } finally { setLoading(false); } }
  return <Container maxWidth="lg"><header><Typography variant="h3">Evidue</Typography><Chip label="Synthetic demonstration data" color="warning"/><Typography>Operationally realistic data generated deterministically. No real customer or vendor data is shown.</Typography></header><Typography variant="h5">Acme Commerce × Nova Support AI · June 1–30, 2026</Typography><Typography className="promise">Every dollar is produced by deterministic rules evaluated against traceable evidence—not by a model's guess.</Typography><Card sx={{ my: 3 }}><CardContent><Typography variant="h6">Submitted invoice</Typography><Typography variant="h3">$15,000</Typography><Typography>10,000 claimed outcomes at $1.50. Contract rules and customer-owned evidence are ready for evaluation.</Typography><Button variant="contained" disabled={loading} onClick={run}>{loading ? "Applying deterministic rules…" : "Run reconciliation"}</Button>{error && <Typography color="error">{error}</Typography>}</CardContent></Card>{summary && <Card className="dominant"><CardContent><Typography>Correct payable amount</Typography><Typography variant="h2">{money(summary.payable_amount)}</Typography><Typography>{summary.payable_outcomes.toLocaleString()} payable outcomes · {summary.disputed_outcomes.toLocaleString()} disputed · {money(summary.recommended_deduction)} recommended deduction</Typography><Button href="/api/reconciliations/current/exports/disputes.csv">Download dispute CSV</Button><Button href="/api/reconciliations/current/exports/evidence.json">Download evidence JSON</Button><Button href="/api/reconciliations/current/exports/summary.json">Download summary JSON</Button></CardContent></Card>}</Container>;
}
createRoot(document.getElementById("root")!).render(<App/>);
