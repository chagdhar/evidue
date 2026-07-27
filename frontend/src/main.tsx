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
    mode: "light",
    primary: { main: "#315f73", dark: "#244956", light: "#6f96a6", contrastText: "#f7f2e8" },
    success: { main: "#2f735f", dark: "#245948", light: "#6ca08f" },
    warning: { main: "#9a6c2f", dark: "#755022", light: "#c59d67" },
    error: { main: "#a24f56", dark: "#7d3b41", light: "#c77c82" },
    text: { primary: "#20282d", secondary: "#687177" },
    background: { default: "#cbc5ba", paper: "#e6e1d8" },
    divider: "#b8b1a6",
  },
  typography: {
    fontFamily: '"Inter", "IBM Plex Sans", system-ui, sans-serif',
    h2: { fontWeight: 800, letterSpacing: "-0.04em" },
    h3: { fontWeight: 750, letterSpacing: "-0.035em" },
    h4: { fontWeight: 750 },
    h5: { fontWeight: 700 },
    button: { fontWeight: 750, textTransform: "none" },
  },
  shape: { borderRadius: 10 },
  components: {
    MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
    MuiButton: { styleOverrides: { root: { boxShadow: "none", borderRadius: 8 } } },
    MuiChip: { styleOverrides: { root: { borderRadius: 7 } } },
  },
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
