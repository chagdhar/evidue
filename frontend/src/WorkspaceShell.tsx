import { Box, Button, Chip, CircularProgress, Divider, Stack, Typography } from "@mui/material";
import { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

export type WorkspaceSection = "overview" | "invoices" | "review" | "vendors" | "settings";

type Props = {
  active: WorkspaceSection;
  workspaceId?: string | null;
  busy?: string;
  onRefresh?: () => void;
  onSignOut?: () => void;
  children: ReactNode;
};

const navItems: Array<{
  id: WorkspaceSection;
  label: string;
  eyebrow: string;
  path: string;
}> = [
  { id: "overview", label: "Overview", eyebrow: "What needs attention", path: "/workspace" },
  { id: "invoices", label: "Invoices", eyebrow: "Review vendor charges", path: "/workspace/invoices" },
  { id: "review", label: "Review queue", eyebrow: "Resolve open decisions", path: "/workspace/review" },
  { id: "vendors", label: "Vendors", eyebrow: "Track commercial history", path: "/workspace/vendors" },
  { id: "settings", label: "Settings", eyebrow: "Workspace controls", path: "/workspace/settings" },
];

const sectionCopy: Record<WorkspaceSection, { eyebrow: string; title: string; detail: string }> = {
  overview: {
    eyebrow: "FINANCE CONTROL",
    title: "Overview",
    detail: "See AI-vendor spend under review, unsupported exposure, and the next finance action.",
  },
  invoices: {
    eyebrow: "INVOICE CONTROL",
    title: "Invoice control",
    detail: "Contract → customer evidence → verified payable → commercial action.",
  },
  review: {
    eyebrow: "DECISION QUEUE",
    title: "Review queue",
    detail: "Resolve evidence gaps, approval decisions, and vendor actions without changing the machine record.",
  },
  vendors: {
    eyebrow: "VENDOR CONTROL",
    title: "Vendors",
    detail: "See spend, exceptions, contracts, and review exposure by AI vendor.",
  },
  settings: {
    eyebrow: "WORKSPACE",
    title: "Workspace settings",
    detail: "Manage defaults and evidence-system preferences without changing approved financial authority.",
  },
};

export default function WorkspaceShell({
  active,
  workspaceId,
  busy = "",
  onRefresh,
  onSignOut,
  children,
}: Props) {
  const navigate = useNavigate();
  const copy = sectionCopy[active];

  return (
    <Box className="workspace-root">
      <Box component="aside" className="workspace-sidebar">
        <Button
          color="inherit"
          onClick={() => navigate("/workspace")}
          className="workspace-brand"
          aria-label="Evidue customer workspace"
        >
          <Box className="workspace-brand-mark">E</Box>
          <Box sx={{ textAlign: "left", minWidth: 0 }}>
            <Typography className="workspace-wordmark">Evidue</Typography>
            <Typography className="workspace-brand-caption">Invoice control</Typography>
          </Box>
        </Button>

        <Box className="workspace-context-card">
          <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
            <Typography className="workspace-context-label">Customer workspace</Typography>
            <Box className="workspace-private-dot" aria-hidden="true" />
          </Stack>
          <Typography className="workspace-context-name" title={workspaceId || "Active workspace"}>
            {workspaceId || "Active workspace"}
          </Typography>
          <Typography className="workspace-context-detail">Private · customer-controlled data</Typography>
        </Box>

        <Box component="nav" aria-label="Workspace navigation" className="workspace-nav">
          <Typography className="workspace-nav-label">WORKSPACE</Typography>
          <Stack spacing={0.25}>
            {navItems.map((item) => {
              const selected = active === item.id;
              return (
                <Button
                  key={item.id}
                  color="inherit"
                  onClick={() => navigate(item.path)}
                  aria-label={item.label}
                  aria-current={selected ? "page" : undefined}
                  className={`workspace-nav-item${selected ? " active" : ""}`}
                >
                  <Box sx={{ textAlign: "left", minWidth: 0 }}>
                    <Typography className="workspace-nav-title">{item.label}</Typography>
                    <Typography className="workspace-nav-detail">{item.eyebrow}</Typography>
                  </Box>
                </Button>
              );
            })}
          </Stack>
        </Box>

        <Box sx={{ flexGrow: 1 }} />
        <Divider />
        <Box className="workspace-sidebar-footer">
          <Typography className="workspace-sidebar-footer-title">Financial authority</Typography>
          <Typography>AI proposes. Finance approves. Deterministic code decides dollars.</Typography>
        </Box>
      </Box>

      <Box className="workspace-main">
        <Box component="header" className="workspace-topbar">
          <Box sx={{ minWidth: 0 }}>
            <Typography className="workspace-page-eyebrow">{copy.eyebrow}</Typography>
            <Typography component="h1" className="workspace-page-title">{copy.title}</Typography>
            <Typography className="workspace-page-detail">{copy.detail}</Typography>
          </Box>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ flex: "0 0 auto" }}>
            {busy && (
              <Chip
                size="small"
                icon={<CircularProgress size={12} thickness={5} />}
                label={busy}
                className="workspace-busy-chip"
              />
            )}
            {onRefresh && (
              <Button color="inherit" onClick={onRefresh} disabled={Boolean(busy)} className="workspace-utility-button">
                Refresh
              </Button>
            )}
            {onSignOut && (
              <Button color="inherit" onClick={onSignOut} className="workspace-utility-button">
                Sign out
              </Button>
            )}
          </Stack>
        </Box>
        <Box className="workspace-content">{children}</Box>
      </Box>
    </Box>
  );
}
