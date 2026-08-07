import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Container,
  FormControlLabel,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { browserSessionId, contactAttribution, track } from "./analytics";
import { usePublicConfig } from "./BetaApplicationCTA";
import { api } from "./api";
import { contactHref, type ContactSubmission } from "./contact";
import { TemplateIcon } from "./TemplateIcons";

const initialSubmission: ContactSubmission = {
  name: "",
  email: "",
  company: "",
  discussionType: "Product feedback",
  message: "",
};

function ContactHeader() {
  return (
    <Box component="header" className="contact-header">
      <Container maxWidth="lg" className="contact-container">
        <RouterLink to="/" className="contact-wordmark" aria-label="Evidue landing page">
          <span aria-hidden="true">E</span>
          <strong>Evidue</strong>
        </RouterLink>
        <Stack direction="row" spacing={1}>
          <Button component={RouterLink} to="/" color="inherit">Back to landing page</Button>
          <Button component={RouterLink} to="/demo/invoices/current" variant="contained">Open workspace</Button>
        </Stack>
      </Container>
    </Box>
  );
}

export default function ContactPage() {
  const config = usePublicConfig();
  const [submission, setSubmission] = useState(initialSubmission);
  const [safeToShare, setSafeToShare] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const [website, setWebsite] = useState("");
  const [submissionId] = useState(() => crypto.randomUUID());
  const [formStartedAt] = useState(() => new Date().toISOString());
  const errorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  const update = (field: keyof ContactSubmission) => (event: ChangeEvent<HTMLInputElement>) => {
    setSubmission((current) => ({ ...current, [field]: event.target.value }));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError("");
    try {
      await api.createContactSubmission({
        name: submission.name,
        email: submission.email,
        company: submission.company,
        discussion_type: submission.discussionType,
        message: submission.message,
        confirmed_no_confidential_data: true,
        ...contactAttribution(),
        submission_id: submissionId,
        browser_session_id: browserSessionId(),
        form_started_at: formStartedAt,
        website,
      });
      track("contact_form_submitted", { discussion_type: submission.discussionType });
      setSubmitted(true);
    } catch {
      setError("Your response could not be submitted right now. Please try again or email me directly.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box className="contact-page">
      <ContactHeader />
      <Container maxWidth="lg" className="contact-container contact-layout">
        <Box className="contact-intro">
          <Typography className="contact-overline">Send product feedback</Typography>
          <Typography component="h1">Tell me what you think.</Typography>
          <Typography className="contact-lede">
            Share feedback on the demo, describe an invoice-review problem, or start a conversation. Beta qualification is handled separately through the beta application.
          </Typography>
          <Box className="contact-expectations">
            <Typography variant="h5">Useful topics</Typography>
            <Stack spacing={2}>
              <Box><TemplateIcon name="check" size={18} /><span>Where the demo is clear or unconvincing</span></Box>
              <Box><TemplateIcon name="check" size={18} /><span>How your team reviews outcome-priced charges today</span></Box>
              <Box><TemplateIcon name="check" size={18} /><span>What evidence or controls you would need to trust the result</span></Box>
            </Stack>
          </Box>
        </Box>

        {config === null ? (
          <Paper className="contact-form contact-form-status" role="status">
            <CircularProgress size={24} />
            <Typography>Checking feedback availability…</Typography>
          </Paper>
        ) : !config.contact_form_configured ? (
          <Paper className="contact-form contact-form-status" role="status">
            <Typography variant="h4">Feedback form unavailable.</Typography>
            <Typography>The private feedback sheet is not connected, so this form cannot safely deliver a response right now.</Typography>
            <Button href={contactHref} variant="contained">Email Dharun</Button>
          </Paper>
        ) : submitted ? (
          <Paper className="contact-form contact-form-success" role="status">
            <TemplateIcon name="check" size={30} />
            <Typography variant="h4">Response received.</Typography>
            <Typography>Your feedback has been added to my private feedback sheet. I’ll follow up using the email you provided.</Typography>
            <Button component={RouterLink} to="/" variant="outlined">Return to the landing page</Button>
          </Paper>
        ) : (
          <Paper component="form" className="contact-form" onSubmit={(event) => void submit(event)}>
            <input
              className="contact-honeypot"
              type="text"
              name="website"
              value={website}
              onChange={(event) => setWebsite(event.target.value)}
              tabIndex={-1}
              autoComplete="off"
              aria-hidden="true"
            />
            <Box className="contact-form-heading">
              <Typography variant="h4">Send feedback</Typography>
              <Typography>Five short fields. Required fields are marked with an asterisk.</Typography>
            </Box>

            <Box className="contact-form-grid">
              <TextField required label="Name" value={submission.name} onChange={update("name")} autoComplete="name" />
              <TextField required type="email" label="Email" value={submission.email} onChange={update("email")} autoComplete="email" />
              <TextField required label="Company" value={submission.company} onChange={update("company")} autoComplete="organization" />
              <TextField select required label="What would you like to discuss?" value={submission.discussionType} onChange={update("discussionType")}>
                <MenuItem value="Product feedback">Product feedback</MenuItem>
                <MenuItem value="Invoice review">An invoice-review problem</MenuItem>
                <MenuItem value="Partnership">Partnership or integration</MenuItem>
                <MenuItem value="Other">Other</MenuItem>
              </TextField>
              <TextField required multiline minRows={6} label="Message" value={submission.message} onChange={update("message")} className="contact-field-wide" />
            </Box>

            <Alert severity="info" className="contact-privacy-note">
              Do not include confidential contracts, invoices, customer records, credentials, or personal data. We can arrange a safe follow-up separately.
            </Alert>
            <Typography className="contact-data-use-note">
              Your response will be stored in a private Google Sheet and used only for Evidue product research and follow-up.
            </Typography>
            {error && (
              <Alert severity="error" ref={errorRef} tabIndex={-1} aria-live="assertive" sx={{ mb: 2 }}>
                {error} <a href={contactHref}>Email Dharun</a>.
              </Alert>
            )}
            <FormControlLabel
              control={<Checkbox checked={safeToShare} onChange={(event) => setSafeToShare(event.target.checked)} />}
              label="I confirm this message contains no confidential or customer data."
            />
            <Button type="submit" variant="contained" size="large" disabled={!safeToShare || submitting} endIcon={<TemplateIcon name="arrow" size={17} />}>
              {submitting ? "Submitting…" : "Submit feedback"}
            </Button>
          </Paper>
        )}
      </Container>
    </Box>
  );
}
