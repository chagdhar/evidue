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
    return createTheme({
      palette: {
        mode,
        primary: {
          main: dark ? "#9DB6FF" : "#2B59F0",
          dark: dark ? "#7F9FFF" : "#1E43C7",
          light: dark ? "#C9D6FF" : "#DDE6FF",
          contrastText: dark ? "#0F1728" : "#FFFFFF",
        },
        success: { main: dark ? "#61C39A" : "#1C7C54" },
        warning: { main: dark ? "#E4BD67" : "#A87311" },
        error: { main: dark ? "#E8897D" : "#C85246" },
        background: {
          default: dark ? "#16181C" : "#F7F7F5",
          paper: dark ? "#202328" : "#FFFFFF",
        },
        text: {
          primary: dark ? "#F4F3EF" : "#171717",
          secondary: dark ? "#B7B4AE" : "#6B6B68",
        },
        divider: dark ? "#353942" : "#E3E1DC",
      },
      typography: {
        fontFamily: 'Inter, "IBM Plex Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        h2: { fontWeight: 700, letterSpacing: "-0.045em" },
        h3: { fontWeight: 700, letterSpacing: "-0.04em" },
        h4: { fontWeight: 700, letterSpacing: "-0.03em" },
        h5: { fontWeight: 640, letterSpacing: "-0.02em" },
        h6: { fontWeight: 620 },
        subtitle1: { fontWeight: 590 },
        button: { fontWeight: 620, textTransform: "none", letterSpacing: "-0.01em" },
        overline: { fontWeight: 700, letterSpacing: "0.08em" },
      },
      shape: { borderRadius: 8 },
      components: {
        MuiCssBaseline: {
          styleOverrides: {
            body: {
              scrollbarColor: dark ? "#575C64 #16181C" : "#C7C3BB #F7F7F5",
            },
          },
        },
        MuiPaper: {
          styleOverrides: {
            root: {
              backgroundImage: "none",
              border: `1px solid ${dark ? "#353942" : "#E3E1DC"}`,
              boxShadow: "none",
            },
          },
        },
        MuiCard: {
          styleOverrides: {
            root: {
              backgroundImage: "none",
              border: `1px solid ${dark ? "#353942" : "#E3E1DC"}`,
              boxShadow: dark ? "0 1px 0 rgba(255,255,255,.03)" : "0 1px 0 rgba(23,23,23,.03)",
            },
          },
        },
        MuiButton: {
          defaultProps: { disableElevation: true },
          styleOverrides: {
            root: { borderRadius: 7, minHeight: 38, paddingInline: 14 },
            containedPrimary: {
              background: dark ? "#F3F1EC" : "#171717",
              color: dark ? "#171717" : "#FFFFFF",
              '&:hover': { background: dark ? "#FFFFFF" : "#0F0F10" },
            },
            outlined: {
              borderColor: dark ? "#4D545F" : "#D7D3CC",
            },
          },
        },
        MuiChip: {
          styleOverrides: {
            root: { borderRadius: 6, fontWeight: 620 },
          },
        },
        MuiTableCell: {
          styleOverrides: {
            head: {
              color: dark ? "#D7D2C9" : "#5B5B58",
              backgroundColor: dark ? "#24282F" : "#F5F4F1",
              fontWeight: 700,
            },
            root: { borderColor: dark ? "#353942" : "#E9E6E0" },
          },
        },
        MuiDrawer: {
          styleOverrides: {
            paper: { backgroundImage: "none" },
          },
        },
        MuiAlert: {
          styleOverrides: {
            root: { borderRadius: 8 },
          },
        },
        MuiAppBar: {
          styleOverrides: {
            root: {
              boxShadow: "none",
            },
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
