import { Box, Button, Typography } from "@mui/material";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Link as RouterLink } from "react-router-dom";
import { api, PublicConfig } from "./api";
import { track } from "./analytics";

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
        talk_booking_url: null,
      }));
  }, []);

  return <PublicConfigContext.Provider value={config}>{children}</PublicConfigContext.Provider>;
}

export function BetaApplicationCTA({ compact = false }: Props) {
  const config = useContext(PublicConfigContext);

  if (config === null) return null;
  if (!config.contact_form_configured) {
    if (!config.talk_booking_url) return null;
    return (
      <Button
        variant={compact ? "text" : "outlined"}
        href={config.talk_booking_url}
        target="_blank"
        rel="noreferrer"
      >
        {compact ? "Book time" : "Book a 15-minute conversation"}
      </Button>
    );
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
  if (config.contact_form_configured) {
    return (
      <Button component={RouterLink} to="/contact" variant="text" onClick={() => track("talk_to_us_clicked")}>
        Talk to us
      </Button>
    );
  }
  if (!config.talk_booking_url) return null;
  return (
    <Button href={config.talk_booking_url} target="_blank" rel="noreferrer" variant="text">
      Book a 15-minute conversation
    </Button>
  );
}
