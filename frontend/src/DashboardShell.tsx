import { TemplateIcon } from "./TemplateIcons";
import {
  AppBar,
  Box,
  Chip,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  Toolbar,
  Tooltip,
  Typography,
} from "@mui/material";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useEvidueThemeMode } from "./templateTheme";
import { api } from "./api";

const DRAWER_WIDTH = 252;

type NavEntry = {
  label: string;
  to: string;
  icon: ReactNode;
  end?: boolean;
};

const navigation: Array<{ label: string; items: NavEntry[]; secondary?: boolean }> = [
  {
    label: "Review",
    items: [
      { label: "Decision", to: "/demo/invoices/current", icon: <TemplateIcon name="verify" /> },
      { label: "Findings", to: "/demo/disputes/current", icon: <TemplateIcon name="shield" /> },
      { label: "Contract rules", to: "/demo/contracts/current", icon: <TemplateIcon name="contract" /> },
      { label: "Evidence", to: "/demo/data-sources", icon: <TemplateIcon name="data" /> },
    ],
  },
  {
    label: "Technical",
    secondary: true,
    items: [
      { label: "Overview", to: "/demo", icon: <TemplateIcon name="dashboard" />, end: true },
      { label: "Invoices", to: "/demo/invoices", icon: <TemplateIcon name="receipt" /> },
      { label: "Outcome ledger", to: "/demo/outcome-ledger", icon: <TemplateIcon name="ledger" /> },
      { label: "Vendor preflight", to: "/demo/vendor-preflight", icon: <TemplateIcon name="preflight" /> },
      { label: "Scenario lab", to: "/demo/lab", icon: <TemplateIcon name="lab" /> },
    ],
  },
];

const routeTitles: Record<string, { title: string; context: string }> = {
  "/demo": { title: "Overview", context: "June 2026 control workspace" },
  "/demo/invoices": { title: "Invoices", context: "AI vendor billing periods" },
  "/demo/invoices/current": { title: "Payment decision", context: "June 2026 · Nova Support AI" },
  "/demo/disputes/current": { title: "Findings", context: "Evidence-backed deductions" },
  "/demo/contracts/current": { title: "Contract rules", context: "Approved program and compilation history" },
  "/demo/outcome-ledger": { title: "Outcome ledger", context: "Versioned outcome receipts" },
  "/demo/data-sources": { title: "Evidence", context: "Customer and vendor source records" },
  "/demo/vendor-preflight": { title: "Vendor preflight", context: "Pre-invoice evidence readiness" },
  "/demo/lab": { title: "Scenario lab", context: "Technical demonstration controls" },
};

function Brand() {
  return (
    <Stack direction="row" spacing={1.4} alignItems="center" sx={{ minWidth: 0 }}>
      <Box className="evidue-brand-mark" aria-hidden="true">
        <span>E</span>
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography className="evidue-wordmark" noWrap>Evidue</Typography>
        <Typography className="evidue-brand-caption" noWrap>Outcome invoice control</Typography>
      </Box>
    </Stack>
  );
}

function NavigationContent({ onNavigate, publicDemo }: { onNavigate?: () => void; publicDemo: boolean }) {
  return (
    <Box className="evidue-sidebar-content">
      <Box className="evidue-sidebar-brand"><Brand /></Box>
      <Box className="evidue-sidebar-rule" />
      <Box className="evidue-sidebar-nav">
        {navigation.filter((group) => !publicDemo || !group.secondary).map((group) => (
          <Box key={group.label} className={group.secondary ? "evidue-nav-group secondary" : "evidue-nav-group"}>
            <Typography className="evidue-nav-label">{group.label}</Typography>
            <List disablePadding>
              {group.items.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.end} className="template-nav-link" onClick={onNavigate}>
                  {({ isActive }) => (
                    <ListItemButton selected={isActive}>
                      <ListItemIcon>{item.icon}</ListItemIcon>
                      <ListItemText primary={item.label} />
                    </ListItemButton>
                  )}
                </NavLink>
              ))}
            </List>
          </Box>
        ))}
      </Box>
      <Box className="evidue-sidebar-footer">
        <Box className="evidue-environment-note">
          <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
            <Typography className="evidue-environment-title">Technical preview</Typography>
            <span className="evidue-status-dot" aria-hidden="true" />
          </Stack>
          <Typography className="evidue-environment-copy">
            Synthetic records. Deterministic decisions. No customer data.
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}

export function DashboardShell({ onOpenHowItWorks }: { onOpenHowItWorks: () => void }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const { mode, toggleMode } = useEvidueThemeMode();
  const [publicDemo, setPublicDemo] = useState(false);

  useEffect(() => {
    void api.status().then((status) => setPublicDemo(status.public_demo)).catch(() => undefined);
  }, []);

  const route = useMemo(
    () => routeTitles[location.pathname] ?? { title: "Evidue", context: "Outcome invoice control" },
    [location.pathname],
  );

  return (
    <Box className="template-app-shell">
      <Drawer
        variant="permanent"
        className="template-desktop-drawer"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box" },
        }}
      >
        <NavigationContent publicDemo={publicDemo} />
      </Drawer>

      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: "block", md: "none" },
          "& .MuiDrawer-paper": { width: DRAWER_WIDTH },
        }}
      >
        <NavigationContent publicDemo={publicDemo} onNavigate={() => setMobileOpen(false)} />
      </Drawer>

      <Box className="template-main-column">
        <AppBar position="sticky" color="inherit" elevation={0} className="template-topbar">
          <Toolbar>
            <IconButton
              aria-label="Open navigation"
              onClick={() => setMobileOpen(true)}
              sx={{ display: { md: "none" }, mr: 1 }}
            >
              <TemplateIcon name="menu" />
            </IconButton>
            <Box className="evidue-page-identity">
              <Typography className="evidue-page-title" noWrap>{route.title}</Typography>
              <Typography className="evidue-page-context" noWrap>{route.context}</Typography>
            </Box>
            <Box sx={{ flex: 1 }} />
            <Stack direction="row" spacing={0.75} alignItems="center">
              {publicDemo && <Chip label="Read-only preview" size="small" className="evidue-readonly-chip" />}
              <Tooltip title="How Evidue works">
                <IconButton aria-label="How Evidue works" onClick={onOpenHowItWorks}>
                  <TemplateIcon name="help" />
                </IconButton>
              </Tooltip>
              <Tooltip title={`Switch to ${mode === "dark" ? "light" : "dark"} mode`}>
                <IconButton aria-label="Toggle color mode" onClick={toggleMode}>
                  {mode === "dark" ? <TemplateIcon name="sun" /> : <TemplateIcon name="moon" />}
                </IconButton>
              </Tooltip>
            </Stack>
          </Toolbar>
        </AppBar>
        <Box component="main" className="template-page-stage">
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
}
