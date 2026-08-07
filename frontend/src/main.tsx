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
import { EvidueThemeProvider } from "./templateTheme";
import LandingPage from "./LandingPage";
import ContactPage from "./ContactPage";
import PilotApp from "./PilotApp";
import { PublicConfigProvider } from "./BetaApplicationCTA";
import "./style.css";

createRoot(document.getElementById("root")!).render(
  <EvidueThemeProvider>
    <BrowserRouter>
      <PublicConfigProvider>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/pilot" element={<PilotApp />} />
          <Route path="/pilot/config" element={<PilotApp />} />
          <Route path="/demo" element={<ProductShell />}>
            <Route index element={<OverviewPage />} />
            <Route path="invoices" element={<InvoicesPage />} />
            <Route path="invoices/current" element={<App embedded />} />
            <Route path="contracts/current" element={<ContractsPage />} />
            <Route path="disputes/current" element={<DisputesPage />} />
            <Route path="data-sources" element={<DataSourcesPage />} />
            <Route path="vendor-preflight" element={<VendorPreflightPage />} />
            <Route path="outcome-ledger" element={<OutcomeLedgerPage />} />
            <Route path="lab" element={<App embedded scenarioLab />} />
          </Route>
          <Route path="*" element={<Navigate to="/demo" replace />} />
        </Routes>
      </PublicConfigProvider>
    </BrowserRouter>
  </EvidueThemeProvider>,
);
