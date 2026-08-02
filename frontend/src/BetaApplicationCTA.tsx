import { Box, Button, Typography } from "@mui/material";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, PublicConfig } from "./api";
import { betaFormUrl, track } from "./analytics";
import { contactHref } from "./contact";

type Props = { compact?: boolean };
const PublicConfigContext = createContext<PublicConfig | null>(null);

export function PublicConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<PublicConfig | null>(null);

  useEffect(() => {
    void api.publicConfig()
      .then(setConfig)
      .catch(() => setConfig({ beta_form_configured: false, beta_form_url: null }));
  }, []);

  return <PublicConfigContext.Provider value={config}>{children}</PublicConfigContext.Provider>;
}

export function BetaApplicationCTA({ compact = false }: Props) {
  const config = useContext(PublicConfigContext);

  if (config === null) return null;
  if (!config.beta_form_configured || !config.beta_form_url) {
    return <Button variant={compact ? "text" : "outlined"} href={contactHref} onClick={() => track("contact_clicked")}>Contact Evidue</Button>;
  }
  return (
    <Box className={compact ? "beta-cta compact" : "beta-cta"}>
      {!compact && <Typography color="text.secondary">Reviewing or evaluating outcome-priced AI vendors? Tell me how your company verifies those charges today.</Typography>}
      <Button
        variant="outlined"
        href={betaFormUrl(config.beta_form_url)}
        target="_blank"
        rel="noopener noreferrer"
        onClick={() => track("beta_form_opened")}
      >
        Apply for the Evidue beta
      </Button>
    </Box>
  );
}
