import { TemplateIcon } from "./TemplateIcons";
import {
  AppBar,
  Box,
  Breadcrumbs,
  Button,
  Chip,
  Divider,
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
import { ReactNode, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useEvidueThemeMode } from "./templateTheme";

const DRAWER_WIDTH = 264;

type NavEntry = {
  label: string;
  to: string;
  icon: ReactNode;
  end?: boolean;
};

const navigation: Array<{ label: string; items: NavEntry[] }> = [
  {
    label: "Workspace",
    items: [
      { label: "Overview", to: "/demo", icon: <TemplateIcon name="dashboard" />, end: true },
      { label: "Customer Verify", to: "/demo/invoices/current", icon: <TemplateIcon name="verify" /> },
      { label: "Vendor Preflight", to: "/demo/vendor-preflight", icon: <TemplateIcon name="preflight" /> },
    ],
  },
  {
    label: "Operations",
    items: [
      { label: "Invoices", to: "/demo/invoices", icon: <TemplateIcon name="receipt" /> },
      { label: "Disputes", to: "/demo/disputes/current", icon: <TemplateIcon name="shield" /> },
      { label: "Contracts", to: "/demo/contracts/current", icon: <TemplateIcon name="contract" /> },
    ],
  },
  {
    label: "Infrastructure",
    items: [
      { label: "Outcome Ledger", to: "/demo/outcome-ledger", icon: <TemplateIcon name="ledger" /> },
      { label: "Data Sources", to: "/demo/data-sources", icon: <TemplateIcon name="data" /> },
      { label: "Scenario Lab", to: "/demo/lab", icon: <TemplateIcon name="lab" /> },
    ],
  },
];

const routeTitles: Record<string, string> = {
  "/demo": "Overview",
  "/demo/invoices": "Invoices",
  "/demo/invoices/current": "Customer Verify",
  "/demo/disputes/current": "Dispute package",
  "/demo/contracts/current": "Contract controls",
  "/demo/outcome-ledger": "Outcome Ledger",
  "/demo/data-sources": "Data sources",
  "/demo/vendor-preflight": "Vendor Preflight",
  "/demo/lab": "Scenario Lab",
};

function Brand() {
  return (
    <Stack direction="row" spacing={1.25} alignItems="center" sx={{ minWidth: 0 }}>
      <Box className="template-logo" aria-hidden="true">
        <TemplateIcon name="wallet" size={20} />
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="h6" noWrap>Evidue</Typography>
        <Typography variant="caption" color="text.secondary" noWrap>Outcome commerce control</Typography>
      </Box>
    </Stack>
  );
}

function NavigationContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Box sx={{ px: 2.25, py: 2.1 }}><Brand /></Box>
      <Divider />
      <Box sx={{ px: 1.25, py: 1.5, overflowY: "auto", flex: 1 }}>
        {navigation.map((group) => (
          <Box key={group.label} sx={{ mb: 1.5 }}>
            <Typography variant="overline" color="text.secondary" sx={{ px: 1.5, fontSize: 10.5 }}>
              {group.label}
            </Typography>
            <List disablePadding sx={{ mt: 0.25 }}>
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
      <Box sx={{ p: 1.5 }}>
        <Box className="demo-environment-card">
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Typography variant="subtitle2">Synthetic environment</Typography>
            <Chip label="Demo" color="warning" size="small" />
          </Stack>
          <Typography variant="caption" color="text.secondary">
            Deterministic fixtures. No real customer or vendor data.
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

  const currentTitle = useMemo(() => routeTitles[location.pathname] ?? "Evidue", [location.pathname]);

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
        <NavigationContent />
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
        <NavigationContent onNavigate={() => setMobileOpen(false)} />
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
            <Box sx={{ minWidth: 0 }}>
              <Breadcrumbs aria-label="Breadcrumbs" separator="/" sx={{ mb: 0.15 }}>
                <Typography variant="caption" color="text.secondary">Evidue</Typography>
                <Typography variant="caption" color="text.secondary">Demo</Typography>
              </Breadcrumbs>
              <Typography variant="h6" noWrap>{currentTitle}</Typography>
            </Box>
            <Box sx={{ flex: 1 }} />
            <Stack direction="row" spacing={0.5} alignItems="center">
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
              <Button variant="outlined" size="small" sx={{ display: { xs: "none", sm: "inline-flex" } }}>
                Synthetic demo
              </Button>
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
