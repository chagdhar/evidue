import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { EvidueThemeProvider } from "./templateTheme";
import LandingPage from "./LandingPage";
import ContactPage from "./ContactPage";
import PilotApp from "./PilotApp";
import TryEviduePage from "./TryEviduePage";
import { InvoiceQueuePage, InvoiceRecordPage, ReviewQueuePage, VendorsPage, WorkspaceOverview } from "./WorkspaceProductPages";
import { PublicConfigProvider } from "./BetaApplicationCTA";
import ScrollToTop from "./ScrollToTop";
import "./style.css";

createRoot(document.getElementById("root")!).render(
  <EvidueThemeProvider>
    <BrowserRouter>
      <ScrollToTop />
      <PublicConfigProvider>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/try" element={<TryEviduePage />} />
          <Route path="/workspace" element={<WorkspaceOverview />} />
          <Route path="/workspace/invoices" element={<InvoiceQueuePage />} />
          <Route path="/workspace/invoices/current" element={<PilotApp />} />
          <Route path="/workspace/invoices/:invoiceId" element={<InvoiceRecordPage />} />
          <Route path="/workspace/review" element={<ReviewQueuePage />} />
          <Route path="/workspace/vendors" element={<VendorsPage />} />
          <Route path="/workspace/settings" element={<PilotApp />} />
          <Route path="/workspace/operations" element={<Navigate to="/workspace/review" replace />} />
          <Route path="/pilot" element={<Navigate to="/workspace/invoices/current" replace />} />
          <Route path="/pilot/config" element={<Navigate to="/workspace/settings" replace />} />
          <Route path="/pilot/finance" element={<Navigate to="/workspace/review" replace />} />
          <Route path="/pilot/operations" element={<Navigate to="/workspace/review" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </PublicConfigProvider>
    </BrowserRouter>
  </EvidueThemeProvider>,
);
