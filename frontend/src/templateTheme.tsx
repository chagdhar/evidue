import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import { ReactNode, createContext, useContext, useEffect, useMemo, useState } from "react";

export type EvidueMode = "light" | "dark";

type ThemeModeValue = {
  mode: EvidueMode;
  toggleMode: () => void;
};

const ThemeModeContext = createContext<ThemeModeValue>({
  mode: "dark",
  toggleMode: () => undefined,
});

export function useEvidueThemeMode() {
  return useContext(ThemeModeContext);
}

export function EvidueThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<EvidueMode>(() => {
    const saved = window.localStorage.getItem("evidue-theme");
    return saved === "light" || saved === "dark" ? saved : "dark";
  });

  useEffect(() => {
    document.documentElement.dataset.evidueMode = mode;
    window.localStorage.setItem("evidue-theme", mode);
  }, [mode]);

  const theme = useMemo(() => {
    const dark = mode === "dark";
    return createTheme({
      palette: {
        mode,
        primary: {
          main: dark ? "#99C2FF" : "#0B6BCB",
          dark: dark ? "#6EA6F4" : "#074A8A",
          light: dark ? "#C7DCFF" : "#D9EAFD",
          contrastText: dark ? "#07182D" : "#FFFFFF",
        },
        success: { main: dark ? "#57C98B" : "#168453" },
        warning: { main: dark ? "#F2B95D" : "#A15C00" },
        error: { main: dark ? "#FF8A8A" : "#C23434" },
        background: {
          default: dark ? "#0B0F14" : "#F6F7F9",
          paper: dark ? "#121821" : "#FFFFFF",
        },
        text: {
          primary: dark ? "#F3F6FA" : "#1B2430",
          secondary: dark ? "#A8B3C2" : "#5E6B7A",
        },
        divider: dark ? "#263140" : "#E0E5EB",
      },
      typography: {
        fontFamily: 'Inter, "IBM Plex Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        h2: { fontWeight: 700, letterSpacing: "-0.04em" },
        h3: { fontWeight: 700, letterSpacing: "-0.035em" },
        h4: { fontWeight: 700, letterSpacing: "-0.025em" },
        h5: { fontWeight: 650, letterSpacing: "-0.015em" },
        h6: { fontWeight: 650 },
        button: { fontWeight: 650, textTransform: "none" },
        overline: { fontWeight: 700, letterSpacing: "0.08em" },
      },
      shape: { borderRadius: 10 },
      components: {
        MuiCssBaseline: {
          styleOverrides: {
            body: {
              scrollbarColor: dark ? "#384658 #0B0F14" : "#C5CDD8 #F6F7F9",
            },
          },
        },
        MuiPaper: {
          styleOverrides: {
            root: {
              backgroundImage: "none",
              border: `1px solid ${dark ? "#263140" : "#E0E5EB"}`,
            },
          },
        },
        MuiCard: {
          styleOverrides: {
            root: {
              backgroundImage: "none",
              border: `1px solid ${dark ? "#263140" : "#E0E5EB"}`,
              boxShadow: dark ? "0 8px 28px rgba(0,0,0,.20)" : "0 2px 10px rgba(31,45,61,.06)",
            },
          },
        },
        MuiButton: {
          defaultProps: { disableElevation: true },
          styleOverrides: {
            root: { borderRadius: 8, minHeight: 38 },
            containedPrimary: {
              boxShadow: dark ? "0 0 0 1px rgba(153,194,255,.18)" : "none",
            },
          },
        },
        MuiChip: {
          styleOverrides: {
            root: { borderRadius: 7, fontWeight: 650 },
          },
        },
        MuiTableCell: {
          styleOverrides: {
            head: {
              color: dark ? "#C8D2DF" : "#445164",
              backgroundColor: dark ? "#171F2A" : "#F3F5F7",
              fontWeight: 700,
            },
            root: { borderColor: dark ? "#263140" : "#E0E5EB" },
          },
        },
        MuiDrawer: {
          styleOverrides: {
            paper: { backgroundImage: "none" },
          },
        },
        MuiAlert: {
          styleOverrides: {
            root: { borderRadius: 9 },
          },
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
