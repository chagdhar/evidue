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
    const saved = window.localStorage.getItem("evidue-theme");
    return saved === "light" || saved === "dark" ? saved : "light";
  });

  useEffect(() => {
    document.documentElement.dataset.evidueMode = mode;
    window.localStorage.setItem("evidue-theme", mode);
  }, [mode]);

  const theme = useMemo(() => {
    const dark = mode === "dark";
    const colors = dark
      ? {
          primary: "#7FA7C8",
          primaryDark: "#A7C5DD",
          canvas: "#111820",
          paper: "#18222C",
          text: "#F3F6F8",
          muted: "#A6B2BC",
          divider: "#2A3946",
          success: "#58B58B",
          warning: "#D4A84F",
          error: "#DB7A70",
        }
      : {
          primary: "#275D82",
          primaryDark: "#183F5D",
          canvas: "#F4F6F8",
          paper: "#FFFFFF",
          text: "#17212B",
          muted: "#66727D",
          divider: "#DCE2E8",
          success: "#1E7657",
          warning: "#956A12",
          error: "#B54A42",
        };

    return createTheme({
      palette: {
        mode,
        primary: {
          main: colors.primary,
          dark: colors.primaryDark,
          light: dark ? "#C4D9E8" : "#E7F0F6",
          contrastText: "#FFFFFF",
        },
        success: { main: colors.success },
        warning: { main: colors.warning },
        error: { main: colors.error },
        background: { default: colors.canvas, paper: colors.paper },
        text: { primary: colors.text, secondary: colors.muted },
        divider: colors.divider,
      },
      typography: {
        fontFamily: 'Inter, "IBM Plex Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        h2: { fontWeight: 680, letterSpacing: "-0.04em" },
        h3: { fontWeight: 680, letterSpacing: "-0.035em" },
        h4: { fontWeight: 660, letterSpacing: "-0.03em" },
        h5: { fontWeight: 640, letterSpacing: "-0.02em" },
        h6: { fontWeight: 620 },
        subtitle1: { fontWeight: 600 },
        body1: { lineHeight: 1.55 },
        body2: { lineHeight: 1.5 },
        button: { fontWeight: 650, textTransform: "none", letterSpacing: "-0.01em" },
        overline: { fontWeight: 750, letterSpacing: "0.09em" },
      },
      shape: { borderRadius: 6 },
      components: {
        MuiCssBaseline: {
          styleOverrides: {
            body: {
              scrollbarColor: dark ? "#52616D #111820" : "#B8C1C9 #F4F6F8",
            },
          },
        },
        MuiPaper: {
          styleOverrides: {
            root: {
              backgroundImage: "none",
              border: `1px solid ${colors.divider}`,
              boxShadow: "none",
            },
          },
        },
        MuiCard: {
          styleOverrides: {
            root: {
              backgroundImage: "none",
              border: `1px solid ${colors.divider}`,
              boxShadow: "none",
            },
          },
        },
        MuiButton: {
          defaultProps: { disableElevation: true },
          styleOverrides: {
            root: { borderRadius: 5, minHeight: 38, paddingInline: 14 },
            containedPrimary: {
              background: colors.primary,
              color: "#FFFFFF",
              "&:hover": { background: colors.primaryDark },
            },
            outlined: { borderColor: colors.divider },
          },
        },
        MuiChip: {
          styleOverrides: {
            root: { borderRadius: 4, fontWeight: 650 },
          },
        },
        MuiTableCell: {
          styleOverrides: {
            head: {
              color: colors.muted,
              backgroundColor: dark ? "#1D2934" : "#F7F9FA",
              fontWeight: 750,
              fontSize: "0.74rem",
              letterSpacing: "0.045em",
              textTransform: "uppercase",
            },
            root: {
              borderColor: colors.divider,
              paddingTop: 12,
              paddingBottom: 12,
            },
          },
        },
        MuiDrawer: { styleOverrides: { paper: { backgroundImage: "none" } } },
        MuiAlert: { styleOverrides: { root: { borderRadius: 6 } } },
        MuiAppBar: { styleOverrides: { root: { boxShadow: "none" } } },
        MuiTextField: {
          defaultProps: { size: "small" },
        },
      },
    });
  }, [mode]);

  return (
    <ThemeModeContext.Provider value={{ mode, toggleMode: () => setMode((value) => value === "dark" ? "light" : "dark") }}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ThemeModeContext.Provider>
  );
}
