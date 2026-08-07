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
    return saved === "light" || saved === "dark" ? saved : "dark";
  });

  useEffect(() => {
    document.documentElement.dataset.evidueMode = mode;
    window.localStorage.setItem("evidue-theme", mode);
  }, [mode]);

  const theme = useMemo(() => {
    const dark = mode === "dark";
    const colors = dark
      ? {
          primary: "#7C5CFC",
          primaryDark: "#9B88FF",
          secondary: "#2AB7FF",
          canvas: "#0B0E13",
          paper: "#151A22",
          raised: "#1B222C",
          text: "#F5F7FA",
          muted: "#8995A6",
          divider: "#2B333E",
          success: "#4DE0A0",
          warning: "#F4B860",
          error: "#FF6B7A",
        }
      : {
          primary: "#5B5BD6",
          primaryDark: "#4545B5",
          secondary: "#0F766E",
          canvas: "#E3E7EF",
          paper: "#EEF1F6",
          raised: "#E5E9F1",
          text: "#151925",
          muted: "#626A7A",
          divider: "#C8D0DC",
          success: "#16815D",
          warning: "#B7791F",
          error: "#C74655",
        };

    return createTheme({
      palette: {
        mode,
        primary: {
          main: colors.primary,
          dark: colors.primaryDark,
          light: dark ? "#24264A" : "#EEEEFF",
          contrastText: "#FFFFFF",
        },
        secondary: {
          main: colors.secondary,
          contrastText: "#FFFFFF",
        },
        success: { main: colors.success },
        warning: { main: colors.warning },
        error: { main: colors.error },
        background: { default: colors.canvas, paper: colors.paper },
        text: { primary: colors.text, secondary: colors.muted },
        divider: colors.divider,
        action: {
          hover: dark ? "rgba(255,255,255,0.06)" : "rgba(91,91,214,0.055)",
          selected: dark ? "rgba(139,140,247,0.18)" : "rgba(91,91,214,0.11)",
          focus: dark ? "rgba(139,140,247,0.24)" : "rgba(91,91,214,0.18)",
        },
      },
      typography: {
        fontFamily: 'Inter, "IBM Plex Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        h2: { fontWeight: 760, letterSpacing: "-0.048em" },
        h3: { fontWeight: 750, letterSpacing: "-0.043em" },
        h4: { fontWeight: 730, letterSpacing: "-0.038em" },
        h5: { fontWeight: 710, letterSpacing: "-0.028em" },
        h6: { fontWeight: 690, letterSpacing: "-0.015em" },
        subtitle1: { fontWeight: 650 },
        body1: { lineHeight: 1.58 },
        body2: { lineHeight: 1.5 },
        button: { fontWeight: 720, textTransform: "none", letterSpacing: "-0.014em" },
        overline: { fontWeight: 820, letterSpacing: "0.11em" },
      },
      shape: { borderRadius: 14 },
      components: {
        MuiCssBaseline: {
          styleOverrides: {
            html: { backgroundColor: colors.canvas },
            body: {
              background: dark
                ? "radial-gradient(circle at 78% -10%, rgba(124,92,252,0.14), transparent 30%), #0B0E13"
                : "radial-gradient(circle at 8% -8%, rgba(91,91,214,0.16), transparent 34%), radial-gradient(circle at 92% 2%, rgba(15,118,110,0.09), transparent 28%), linear-gradient(180deg, #E7EAF2 0%, #DDE3EC 100%)",
              backgroundAttachment: "fixed",
              scrollbarColor: dark ? "#434D5B #0B0E13" : "#AEB3C1 #F3F4F8",
            },
            "*::selection": {
              backgroundColor: dark ? "rgba(139,140,247,0.32)" : "rgba(91,91,214,0.20)",
            },
          },
        },
        MuiPaper: {
          styleOverrides: {
            root: {
              backgroundImage: "none",
              borderColor: colors.divider,
            },
            outlined: {
              backgroundColor: dark ? "#111722" : "#EEF1F6",
              boxShadow: dark
                ? "0 14px 34px rgba(0,0,0,0.14)"
                : "0 12px 30px rgba(31,42,62,0.07)",
            },
          },
        },
        MuiCard: {
          styleOverrides: {
            root: {
              background: dark
                ? "linear-gradient(180deg, #171D26 0%, #141920 100%)"
                : "linear-gradient(180deg, #F1F3F8 0%, #E9EDF4 100%)",
              borderColor: colors.divider,
              boxShadow: dark
                ? "0 18px 48px rgba(0,0,0,0.18)"
                : "0 18px 48px rgba(27,31,57,0.055)",
            },
          },
        },
        MuiButton: {
          defaultProps: { disableElevation: true },
          styleOverrides: {
            root: {
              borderRadius: 10,
              minHeight: 40,
              paddingInline: 17,
              transition: "background-color 140ms ease, border-color 140ms ease, color 140ms ease, transform 140ms ease, box-shadow 140ms ease",
            },
            containedPrimary: {
              background: dark
                ? "linear-gradient(135deg, #7778EF 0%, #6466E8 100%)"
                : "linear-gradient(135deg, #6366E8 0%, #5151C8 100%)",
              color: "#FFFFFF",
              boxShadow: dark
                ? "0 8px 24px rgba(99,102,232,0.20)"
                : "0 8px 22px rgba(81,81,200,0.22)",
              "&:hover": {
                background: dark
                  ? "linear-gradient(135deg, #8586F5 0%, #6D6FEF 100%)"
                  : "linear-gradient(135deg, #595CDD 0%, #4545B5 100%)",
                boxShadow: dark
                  ? "0 10px 28px rgba(99,102,232,0.28)"
                  : "0 10px 28px rgba(81,81,200,0.28)",
                transform: "translateY(-1px)",
              },
            },
            outlined: {
              borderColor: colors.divider,
              "&:hover": {
                borderColor: colors.primary,
                backgroundColor: dark ? "rgba(139,140,247,0.07)" : "rgba(91,91,214,0.045)",
              },
            },
          },
        },
        MuiChip: {
          styleOverrides: {
            root: { borderRadius: 7, fontWeight: 700 },
          },
        },
        MuiTableCell: {
          styleOverrides: {
            head: {
              color: colors.muted,
              backgroundColor: colors.raised,
              fontWeight: 800,
              fontSize: "0.72rem",
              letterSpacing: "0.06em",
              textTransform: "uppercase",
            },
            root: {
              borderColor: colors.divider,
              paddingTop: 12,
              paddingBottom: 12,
            },
          },
        },
        MuiLinearProgress: {
          styleOverrides: {
            root: { borderRadius: 999, height: 7 },
            bar: { borderRadius: 999 },
          },
        },
        MuiAlert: {
          styleOverrides: {
            root: { borderRadius: 11, border: `1px solid ${colors.divider}` },
          },
        },
        MuiAppBar: { styleOverrides: { root: { boxShadow: "none" } } },
        MuiTextField: {
          defaultProps: { size: "small" },
        },
        MuiOutlinedInput: {
          styleOverrides: {
            root: {
              borderRadius: 10,
              backgroundColor: dark ? "#0F141B" : "#F7F8FB",
              transition: "box-shadow 140ms ease, background-color 140ms ease",
              "&.Mui-focused": {
                boxShadow: dark
                  ? "0 0 0 3px rgba(139,140,247,0.14)"
                  : "0 0 0 3px rgba(91,91,214,0.10)",
              },
            },
          },
        },
      },
    });
  }, [mode]);

  return (
    <ThemeModeContext.Provider
      value={{ mode, toggleMode: () => setMode((value) => (value === "dark" ? "light" : "dark")) }}
    >
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ThemeModeContext.Provider>
  );
}
