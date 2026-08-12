import { AppBar, Box, Button, Chip, LinearProgress, Stack, Toolbar, Typography } from "@mui/material";
import { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

type WorkspaceSection = "reconciliation" | "operations" | "settings";

type Props = {
  active: WorkspaceSection;
  workspaceId?: string | null;
  busy?: string;
  onRefresh?: () => void;
  onSignOut?: () => void;
  children: ReactNode;
};

const navItems: Array<{ id: WorkspaceSection; label: string; path: string }> = [
  { id: "reconciliation", label: "Reconciliation", path: "/workspace" },
  { id: "operations", label: "Finance operations", path: "/workspace/operations" },
  { id: "settings", label: "Settings", path: "/workspace/settings" },
];

export default function WorkspaceShell({ active, workspaceId, busy = "", onRefresh, onSignOut, children }: Props) {
  const navigate = useNavigate();

  return (
    <Box
      sx={{
        minHeight: "100vh",
        color: "#F5F7FA",
        bgcolor: "#0B0E13",
        backgroundImage: [
          "radial-gradient(circle at 78% -12%, rgba(124,92,252,.16), transparent 28%)",
          "radial-gradient(circle at 18% 10%, rgba(42,183,255,.07), transparent 24%)",
          "linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px)",
          "linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px)",
        ].join(","),
        backgroundSize: "auto, auto, 36px 36px, 36px 36px",
        "& .MuiPaper-root": { color: "#F5F7FA" },
        "& .MuiOutlinedInput-root": {
          color: "#F5F7FA",
          bgcolor: "#0F141B",
          "& fieldset": { borderColor: "#343D49" },
          "&:hover fieldset": { borderColor: "#596577" },
          "&.Mui-focused fieldset": { borderColor: "#8B76FF" },
        },
        "& .MuiInputLabel-root": { color: "#8995A6" },
        "& .MuiInputLabel-root.Mui-focused": { color: "#B6A9FF" },
        "& .MuiFormHelperText-root": { color: "#778395" },
        "& .MuiDivider-root": { borderColor: "#2B333E" },
        "& .MuiTableCell-root": { color: "#DCE2EA", borderColor: "#2B333E" },
        "& .MuiTableCell-head": { color: "#94A0B1", bgcolor: "#171D26" },
      }}
    >
      <AppBar
        position="sticky"
        elevation={0}
        sx={{
          bgcolor: "rgba(8,10,14,.94)",
          color: "#F8FAFC",
          borderBottom: "1px solid #242B35",
          backdropFilter: "blur(22px)",
        }}
      >
        <Toolbar sx={{ gap: 1.25, minHeight: 64 }}>
          <Button
            color="inherit"
            onClick={() => navigate("/workspace")}
            sx={{ p: 0.5, minWidth: 0, textTransform: "none", mr: 0.75 }}
            aria-label="Evidue customer workspace"
          >
            <Stack direction="row" spacing={1.1} alignItems="center">
              <Box
                sx={{
                  width: 36,
                  height: 36,
                  borderRadius: 2,
                  background: "linear-gradient(135deg,#A996FF 0%,#7457F2 100%)",
                  color: "#090B10",
                  border: "1px solid rgba(255,255,255,.38)",
                  display: "grid",
                  placeItems: "center",
                  fontWeight: 950,
                  letterSpacing: "-.06em",
                }}
              >
                E
              </Box>
              <Box sx={{ textAlign: "left", display: { xs: "none", sm: "block" } }}>
                <Typography fontWeight={840} lineHeight={1.05}>Evidue</Typography>
                <Typography variant="caption" sx={{ color: "#778395" }}>AI vendor financial control</Typography>
              </Box>
            </Stack>
          </Button>

          {workspaceId && (
            <Chip
              size="small"
              label={workspaceId}
              sx={{ display: { xs: "none", lg: "inline-flex" }, bgcolor: "#151C26", color: "#B9C3D0", border: "1px solid #2B3542", mr: 0.5 }}
            />
          )}

          <Stack direction="row" spacing={0.4} sx={{ flexGrow: 1, overflowX: "auto" }}>
            {navItems.map((item) => (
              <Button
                key={item.id}
                color="inherit"
                onClick={() => navigate(item.path)}
                aria-current={active === item.id ? "page" : undefined}
                sx={{
                  whiteSpace: "nowrap",
                  textTransform: "none",
                  fontWeight: active === item.id ? 760 : 620,
                  color: active === item.id ? "#FFFFFF" : "#8D99A9",
                  bgcolor: active === item.id ? "rgba(124,92,252,.12)" : "transparent",
                  border: active === item.id ? "1px solid rgba(124,92,252,.22)" : "1px solid transparent",
                  "&:hover": { bgcolor: active === item.id ? "rgba(124,92,252,.16)" : "rgba(255,255,255,.04)" },
                }}
              >
                {item.label}
              </Button>
            ))}
          </Stack>

          {onRefresh && (
            <Button color="inherit" onClick={onRefresh} disabled={Boolean(busy)} sx={{ display: { xs: "none", md: "inline-flex" } }}>
              Refresh
            </Button>
          )}
          {onSignOut && <Button color="inherit" onClick={onSignOut}>Sign out</Button>}
        </Toolbar>
        {busy && <LinearProgress aria-label={busy} />}
      </AppBar>
      {children}
    </Box>
  );
}
