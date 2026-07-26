import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import App from "./App";
import "./style.css";

const theme = createTheme({
  palette: {
    primary: { main: "#1d624c", contrastText: "#ffffff" },
    success: { main: "#1d624c" },
    warning: { main: "#986513" },
    error: { main: "#8d2f2a" },
    text: { primary: "#17201f", secondary: "#63706d" },
    background: { default: "#f5f3ed", paper: "#fffefb" },
  },
  typography: {
    fontFamily: '"Inter", "IBM Plex Sans", system-ui, sans-serif',
    h2: { fontWeight: 800, letterSpacing: "-0.04em" },
    h3: { fontWeight: 750, letterSpacing: "-0.035em" },
    h4: { fontWeight: 750 },
    h5: { fontWeight: 700 },
    button: { fontWeight: 750, textTransform: "none" },
  },
  shape: { borderRadius: 8 },
});

createRoot(document.getElementById("root")!).render(
  <ThemeProvider theme={theme}>
    <CssBaseline />
    <BrowserRouter>
      <Routes>
        <Route path="/demo" element={<App />} />
        <Route path="*" element={<Navigate to="/demo" replace />} />
      </Routes>
    </BrowserRouter>
  </ThemeProvider>,
);
