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
    if (version !== "decision-ledger-v3") return "light";
    const saved = window.localStorage.getItem("evidue-theme");
    return saved === "light" || saved === "dark" ? saved : "light";
  });

  useEffect(() => {
    document.documentElement.dataset.evidueMode = mode;
    window.localStorage.setItem("evidue-theme", mode);
    window.localStorage.setItem("evidue-theme-version", "decision-ledger-v3");
  }, [mode]);

  const theme = useMemo(() => {
    const dark = mode === "dark";
    const colors = dark
      ? {
          primary: "#A78BFA",
          primaryDark: "#8B6FE3",
          secondary: "#B8C0C7",
          canvas: "#111417",
          paper: "#181C20",
          raised: "#20252A",
          text: "#F3F5F7",
          muted: "#AAB1B8",
          divider: "#30363B",
          success: "#57B5A7",
          warning: "#D5A34E",
          error: "#E17A74",
        }
      : {
          primary: "#5B35D5",
          primaryDark: "#4A28B8",
          secondary: "#3C4249",
          canvas: "#F7F8FA",
          paper: "#FFFFFF",
          raised: "#FBFBFC",
          text: "#17191C",
          muted: "#5E6470",
          divider: "#E3E5E8",
          success: "#12645F",
          warning: "#7A5314",
          error: "#963B3B",
        };

    return createTheme({
      palette: {
        mode,
        contrastThreshold: 4.5,
        primary: { main: colors.primary, dark: colors.primaryDark, contrastText: "#FFFFFF" },
        secondary: { main: colors.secondary, contrastText: "#FFFFFF" },
        success: { main: colors.success },
        warning: { main: colors.warning },
        error: { main: colors.error },
        background: { default: colors.canvas, paper: colors.paper },
        text: { primary: colors.text, secondary: colors.muted },
        divider: colors.divider,
        action: {
          hover: dark ? "rgba(255,255,255,0.055)" : "rgba(91,53,213,0.045)",
          selected: dark ? "rgba(167,139,250,0.14)" : "rgba(91,53,213,0.08)",
          focus: dark ? "rgba(167,139,250,0.20)" : "rgba(91,53,213,0.14)",
        },
      },
      typography: {
        fontFamily: 'Inter, "IBM Plex Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        h2: { fontWeight: 700, letterSpacing: "-0.035em" },
        h3: { fontWeight: 700, letterSpacing: "-0.03em" },
        h4: { fontWeight: 700, letterSpacing: "-0.025em" },
        h5: { fontWeight: 680, letterSpacing: "-0.018em" },
        h6: { fontWeight: 660, letterSpacing: "-0.01em" },
        subtitle1: { fontWeight: 650 },
        body1: { fontSize: "1rem", lineHeight: 1.58 },
        body2: { fontSize: "0.9375rem", lineHeight: 1.55 },
        caption: { fontSize: "0.8125rem", lineHeight: 1.45 },
        button: { fontWeight: 650, textTransform: "none", letterSpacing: 0 },
        overline: { fontWeight: 700, letterSpacing: "0.055em", fontSize: "0.75rem" },
      },
      shape: { borderRadius: 7 },
      components: {
        MuiCssBaseline: {
          styleOverrides: {
            html: { backgroundColor: colors.canvas },
            body: { backgroundColor: colors.canvas },
            "*::selection": { backgroundColor: dark ? "rgba(127,166,188,0.28)" : "rgba(13,111,117,0.16)" },
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
              borderRadius: 6,
              minHeight: 40,
              paddingInline: 16,
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
              "&:hover": { borderColor: colors.primary, backgroundColor: dark ? "rgba(127,166,188,0.07)" : "rgba(13,111,117,0.045)" },
            },
          },
        },
        MuiChip: {
          styleOverrides: { root: { borderRadius: 4, fontWeight: 680 } },
        },
        MuiTableCell: {
          styleOverrides: {
            head: {
              color: colors.muted,
              backgroundColor: colors.raised,
              fontWeight: 650,
              fontSize: "0.8125rem",
              letterSpacing: 0,
              textTransform: "none",
            },
            root: { borderColor: colors.divider, paddingTop: 11, paddingBottom: 11 },
          },
        },
        MuiLinearProgress: {
          styleOverrides: { root: { borderRadius: 999, height: 5 }, bar: { borderRadius: 999 } },
        },
        MuiAlert: {
          styleOverrides: { root: { borderRadius: 6, border: `1px solid ${colors.divider}` } },
        },
        MuiAppBar: { styleOverrides: { root: { boxShadow: "none" } } },
        MuiTextField: { defaultProps: { size: "small" } },
        MuiOutlinedInput: {
          styleOverrides: {
            root: {
              borderRadius: 6,
              backgroundColor: colors.paper,
              transition: "box-shadow 120ms ease",
              "&.Mui-focused": { boxShadow: dark ? "0 0 0 2px rgba(167,139,250,0.18)" : "0 0 0 2px rgba(91,53,213,0.12)" },
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
