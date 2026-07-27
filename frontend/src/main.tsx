import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import App from "./App";
import {
  ContractsPage,
  DataSourcesPage,
  DisputesPage,
  InvoicesPage,
  OverviewPage,
  OutcomeLedgerPage,
  ProductShell,
  VendorPreflightPage,
} from "./ProductShell";
import "./style.css";

const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#8b8cff", dark: "#6667dc", light: "#b9baff", contrastText: "#090d1a" },
    success: { main: "#42d7a1" },
    warning: { main: "#f6bd62" },
    error: { main: "#ff7b86" },
    text: { primary: "#f2f5ff", secondary: "#9ca9bf" },
    background: { default: "#070b14", paper: "#111827" },
    divider: "#263247",
  },
  typography: {
    fontFamily: '"Inter", "IBM Plex Sans", system-ui, sans-serif',
    h2: { fontWeight: 800, letterSpacing: "-0.04em" },
    h3: { fontWeight: 750, letterSpacing: "-0.035em" },
    h4: { fontWeight: 750 },
    h5: { fontWeight: 700 },
    button: { fontWeight: 750, textTransform: "none" },
  },
  shape: { borderRadius: 8 },
});

createRoot(document.getElementById("root")!).render(
  <ThemeProvider theme={theme}>
    <CssBaseline />
    <BrowserRouter>
      <Routes>
        <Route path="/demo/lab" element={<App scenarioLab />} />
        <Route path="/demo" element={<ProductShell />}>
          <Route index element={<OverviewPage />} />
          <Route path="invoices" element={<InvoicesPage />} />
          <Route path="invoices/current" element={<App embedded />} />
          <Route path="contracts/current" element={<ContractsPage />} />
          <Route path="disputes/current" element={<DisputesPage />} />
          <Route path="data-sources" element={<DataSourcesPage />} />
          <Route path="vendor-preflight" element={<VendorPreflightPage />} />
          <Route path="outcome-ledger" element={<OutcomeLedgerPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/demo" replace />} />
      </Routes>
    </BrowserRouter>
  </ThemeProvider>,
);
