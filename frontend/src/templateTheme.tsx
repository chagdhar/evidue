import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import { ReactNode, createContext, useContext, useEffect, useMemo, useState } from "react";

export type EvidueMode = "light" | "dark";

type ThemeModeValue = {
  mode: EvidueMode;
  toggleMode: () => void;
};

const ThemeModeContext = createContext<ThemeModeValue>({
  mode: "light",
  toggleMode: () => undefined,
});

export function useEvidueThemeMode() {
  return useContext(ThemeModeContext);
}

export function EvidueThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<EvidueMode>(() => {
    const version = window.localStorage.getItem("evidue-theme-version");
    if (version !== "finance-v2") return "light";
    const saved = window.localStorage.getItem("evidue-theme");
    return saved === "light" || saved === "dark" ? saved : "light";
  });

  useEffect(() => {
    document.documentElement.dataset.evidueMode = mode;
    window.localStorage.setItem("evidue-theme", mode);
    window.localStorage.setItem("evidue-theme-version", "finance-v2");
  }, [mode]);

  const theme = useMemo(() => {
    const dark = mode === "dark";
    const colors = dark
      ? {
          primary: "#7FA6BC",
          primaryDark: "#6891A8",
          secondary: "#4E8075",
          canvas: "#0F1115",
          paper: "#15181E",
          raised: "#1B1F26",
          text: "#F3F4F6",
          muted: "#9AA3AF",
          divider: "#2A2F38",
          success: "#3AA67E",
          warning: "#D49A3A",
          error: "#D8646F",
        }
      : {
          primary: "#245F80",
          primaryDark: "#1B4E6B",
          secondary: "#2E7368",
          canvas: "#F5F6F8",
          paper: "#FFFFFF",
          raised: "#F8F9FB",
          text: "#171A21",
          muted: "#667085",
          divider: "#E0E4EA",
          success: "#1F7A5C",
          warning: "#A86F16",
          error: "#B94755",
        };

    return createTheme({
      palette: {
        mode,
        primary: { main: colors.primary, dark: colors.primaryDark, contrastText: "#FFFFFF" },
        secondary: { main: colors.secondary, contrastText: "#FFFFFF" },
        success: { main: colors.success },
        warning: { main: colors.warning },
        error: { main: colors.error },
        background: { default: colors.canvas, paper: colors.paper },
        text: { primary: colors.text, secondary: colors.muted },
        divider: colors.divider,
        action: {
          hover: dark ? "rgba(255,255,255,0.045)" : "rgba(15,23,42,0.035)",
          selected: dark ? "rgba(127,166,188,0.14)" : "rgba(36,95,128,0.08)",
          focus: dark ? "rgba(127,166,188,0.18)" : "rgba(36,95,128,0.13)",
        },
      },
      typography: {
        fontFamily: 'Inter, "IBM Plex Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        h2: { fontWeight: 730, letterSpacing: "-0.035em" },
        h3: { fontWeight: 720, letterSpacing: "-0.03em" },
        h4: { fontWeight: 710, letterSpacing: "-0.025em" },
        h5: { fontWeight: 700, letterSpacing: "-0.018em" },
        h6: { fontWeight: 680, letterSpacing: "-0.01em" },
        subtitle1: { fontWeight: 650 },
        body1: { lineHeight: 1.55 },
        body2: { lineHeight: 1.5 },
        button: { fontWeight: 680, textTransform: "none", letterSpacing: "-0.01em" },
        overline: { fontWeight: 760, letterSpacing: "0.09em", fontSize: "0.68rem" },
      },
      shape: { borderRadius: 8 },
      components: {
        MuiCssBaseline: {
          styleOverrides: {
            html: { backgroundColor: colors.canvas },
            body: { backgroundColor: colors.canvas },
            "*::selection": { backgroundColor: dark ? "rgba(127,166,188,0.28)" : "rgba(36,95,128,0.16)" },
          },
        },
        MuiPaper: {
          styleOverrides: {
            root: { backgroundImage: "none", borderColor: colors.divider },
            outlined: { backgroundColor: colors.paper, boxShadow: "none" },
          },
        },
        MuiCard: {
          styleOverrides: {
            root: { background: colors.paper, borderColor: colors.divider, boxShadow: "none" },
          },
        },
        MuiButton: {
          defaultProps: { disableElevation: true },
          styleOverrides: {
            root: {
              borderRadius: 7,
              minHeight: 38,
              paddingInline: 15,
              transition: "background-color 120ms ease, border-color 120ms ease, color 120ms ease",
            },
            containedPrimary: {
              background: colors.primary,
              color: "#FFFFFF",
              boxShadow: "none",
              "&:hover": { background: colors.primaryDark, boxShadow: "none" },
            },
            outlined: {
              borderColor: colors.divider,
              "&:hover": { borderColor: colors.primary, backgroundColor: dark ? "rgba(127,166,188,0.07)" : "rgba(36,95,128,0.035)" },
            },
          },
        },
        MuiChip: {
          styleOverrides: { root: { borderRadius: 5, fontWeight: 650 } },
        },
        MuiTableCell: {
          styleOverrides: {
            head: {
              color: colors.muted,
              backgroundColor: colors.raised,
              fontWeight: 760,
              fontSize: "0.7rem",
              letterSpacing: "0.055em",
              textTransform: "uppercase",
            },
            root: { borderColor: colors.divider, paddingTop: 11, paddingBottom: 11 },
          },
        },
        MuiLinearProgress: {
          styleOverrides: { root: { borderRadius: 999, height: 5 }, bar: { borderRadius: 999 } },
        },
        MuiAlert: {
          styleOverrides: { root: { borderRadius: 7, border: `1px solid ${colors.divider}` } },
        },
        MuiAppBar: { styleOverrides: { root: { boxShadow: "none" } } },
        MuiTextField: { defaultProps: { size: "small" } },
        MuiOutlinedInput: {
          styleOverrides: {
            root: {
              borderRadius: 7,
              backgroundColor: colors.paper,
              transition: "box-shadow 120ms ease",
              "&.Mui-focused": { boxShadow: dark ? "0 0 0 2px rgba(127,166,188,0.14)" : "0 0 0 2px rgba(36,95,128,0.10)" },
            },
          },
        },
      },
    });
  }, [mode]);

  return (
    <ThemeModeContext.Provider value={{ mode, toggleMode: () => setMode((value) => (value === "dark" ? "light" : "dark")) }}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ThemeModeContext.Provider>
  );
}
