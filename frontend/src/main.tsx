import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import App from "./App";
import "./style.css";

const theme = createTheme({
  palette: {
    primary: { main: "#0b5d50" },
    background: { default: "#f4f6f3", paper: "#ffffff" },
  },
  typography: {
    fontFamily: '"Inter", "IBM Plex Sans", system-ui, sans-serif',
    h2: { fontWeight: 800, letterSpacing: "-0.04em" },
    h3: { fontWeight: 750, letterSpacing: "-0.035em" },
    h4: { fontWeight: 750 },
    h5: { fontWeight: 700 },
  },
  shape: { borderRadius: 10 },
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
