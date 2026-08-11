import { Box, Button, Typography } from "@mui/material";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Link as RouterLink } from "react-router-dom";
import { api, PublicConfig } from "./api";
import { track } from "./analytics";
import { contactHref } from "./contact";

type Props = { compact?: boolean };
const PublicConfigContext = createContext<PublicConfig | null>(null);

export function usePublicConfig() {
  return useContext(PublicConfigContext);
}

export function PublicConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<PublicConfig | null>(null);

  useEffect(() => {
    void api.publicConfig()
      .then(setConfig)
      .catch(() => setConfig({
        beta_form_configured: false,
        beta_form_url: null,
        contact_form_configured: false,
      }));
  }, []);

  return <PublicConfigContext.Provider value={config}>{children}</PublicConfigContext.Provider>;
}

export function BetaApplicationCTA({ compact = false }: Props) {
  const config = useContext(PublicConfigContext);

  if (config === null) return null;
  if (!config.contact_form_configured) {
    return <Button variant={compact ? "text" : "outlined"} href={contactHref}>{compact ? "Contact" : "Talk to us"}</Button>;
  }
  return (
    <Box className={compact ? "beta-cta compact" : "beta-cta"}>
      {!compact && <Typography color="text.secondary">Paying an AI vendor by outcome, resolution, action, or usage? Tell us how your team verifies those charges today.</Typography>}
      <Button
        component={RouterLink}
        to="/contact"
        variant={compact ? "contained" : "outlined"}
        onClick={() => track("talk_to_us_clicked")}
      >
        {compact ? "Contact" : "Talk to us"}
      </Button>
    </Box>
  );
}

export function FeedbackCTA() {
  const config = usePublicConfig();
  if (config === null) return null;
  return config.contact_form_configured ? (
    <Button component={RouterLink} to="/contact" variant="text" onClick={() => track("talk_to_us_clicked")}>
      Talk to us
    </Button>
  ) : <Button href={contactHref} variant="text">Email Dharun</Button>;
}
