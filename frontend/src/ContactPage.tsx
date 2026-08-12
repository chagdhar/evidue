import {
  Alert,
  Box,
  Button,
  Checkbox,
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
import { type ContactDiscussionType, type ContactSubmission } from "./contact";
import { TemplateIcon } from "./TemplateIcons";

const initialSubmission: ContactSubmission = {
  name: "",
  email: "",
  company: "",
  role: "",
  discussionType: "Invoice review",
  billingModel: "",
  verificationMethod: "",
  evidenceLocation: "",
  commercialAction: "",
  feedbackArea: "",
  message: "",
  openToCall: false,
};

const discussionOptions: Array<{
  value: ContactDiscussionType;
  title: string;
  description: string;
}> = [
  {
    value: "Invoice review",
    title: "AI-vendor billing",
    description: "I deal with AI usage, outcome, or resolution charges.",
  },
  {
    value: "Product feedback",
    title: "Product feedback",
    description: "I tried Evidue and want to tell you what worked or didn't.",
  },
  {
    value: "Partnership",
    title: "Partnership",
    description: "I want to discuss an integration, data source, or partnership.",
  },
  {
    value: "Other",
    title: "Something else",
    description: "I have another question or comment.",
  },
];

const billingModels = [
  "Per outcome",
  "Per resolution",
  "Per action",
  "Usage-based",
  "Fixed / seat-based",
  "Not sure",
  "Other",
];

const verificationMethods = [
  "Vendor report only",
  "Manual spot checks",
  "Reconcile exports",
  "Internal tooling",
  "Not independently verified",
  "Not sure",
];

const evidenceLocations = [
  "Support / helpdesk data",
  "Payments / billing records",
  "CRM / account data",
  "Product / event logs",
  "Multiple customer systems",
  "Mostly vendor-controlled",
  "Not sure",
];

const commercialActions = [
  "Dispute before payment",
  "Request a credit",
  "True-up later",
  "Use it at renewal",
  "No financial action today",
  "Not sure",
  "Other",
];

const feedbackAreas = [
  "Product idea",
  "Demo clarity",
  "Trust / evidence",
  "User experience",
  "Bug",
  "Positioning",
  "Other",
];

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
          <Button component={RouterLink} to="/try" variant="contained">Try Evidue</Button>
        </Stack>
      </Container>
    </Box>
  );
}

function messageLabel(discussionType: ContactDiscussionType) {
  if (discussionType === "Invoice review") return "What is hardest about verifying the bill today?";
  if (discussionType === "Product feedback") return "What worked, what was confusing, or what would you change?";
  if (discussionType === "Partnership") return "What would you like to explore together?";
  return "What would you like to tell us?";
}

function successMessage(discussionType: ContactDiscussionType) {
  if (discussionType === "Invoice review") {
    return "Thanks — this is exactly the kind of real workflow we're trying to understand.";
  }
  if (discussionType === "Product feedback") {
    return "Thanks — your feedback helps us see what is clear, confusing, or unconvincing.";
  }
  return "Thanks — your response was received.";
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

  const billingConversation = submission.discussionType === "Invoice review";
  const partnershipConversation = submission.discussionType === "Partnership";
  const identityRequired = billingConversation || partnershipConversation;
  const emailRequired = identityRequired || submission.openToCall;

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  const update = (field: keyof ContactSubmission) => (event: ChangeEvent<HTMLInputElement>) => {
    setSubmission((current) => ({ ...current, [field]: event.target.value }));
  };

  const chooseDiscussion = (discussionType: ContactDiscussionType) => {
    setSubmission((current) => ({
      ...current,
      discussionType,
      billingModel: discussionType === "Invoice review" ? current.billingModel : "",
      verificationMethod: discussionType === "Invoice review" ? current.verificationMethod : "",
      evidenceLocation: discussionType === "Invoice review" ? current.evidenceLocation : "",
      commercialAction: discussionType === "Invoice review" ? current.commercialAction : "",
      feedbackArea: discussionType === "Product feedback" ? current.feedbackArea : "",
    }));
    setError("");
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
        role: submission.role,
        discussion_type: submission.discussionType,
        billing_model: submission.billingModel,
        verification_method: submission.verificationMethod,
        evidence_location: submission.evidenceLocation,
        commercial_action: submission.commercialAction,
        feedback_area: submission.feedbackArea,
        message: submission.message,
        open_to_call: submission.openToCall,
        confirmed_no_confidential_data: true,
        ...contactAttribution(),
        submission_id: submissionId,
        browser_session_id: browserSessionId(),
        form_started_at: formStartedAt,
        website,
      });
      track("contact_form_submitted", {
        discussion_type: submission.discussionType,
        billing_model: submission.billingModel || "n/a",
        feedback_area: submission.feedbackArea || "n/a",
        open_to_call: submission.openToCall,
      });
      setSubmitted(true);
    } catch {
      setError("We couldn't send your response right now. Your answers are still here — please try again shortly.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box className="contact-page">
      <ContactHeader />
      <Container maxWidth="lg" className="contact-container contact-layout">
        <Box className="contact-intro">
          <Typography className="contact-overline">Talk to us</Typography>
          <Typography component="h1">Tell us what's true.</Typography>
          <Typography className="contact-lede">
            If you handle AI-vendor billing, help us understand how the numbers are checked today. If you just tried Evidue, tell us what was useful, confusing, or unconvincing.
          </Typography>
          <Box className="contact-expectations">
            <Typography variant="h5">What we value</Typography>
            <Stack spacing={2}>
              <Box><TemplateIcon name="check" size={18} /><span>Real workflows, including “we don't verify it”</span></Box>
              <Box><TemplateIcon name="check" size={18} /><span>Specific criticism of the demo or product idea</span></Box>
              <Box><TemplateIcon name="check" size={18} /><span>What would have to be true for you to trust the result</span></Box>
            </Stack>
          </Box>
        </Box>

        {submitted ? (
          <Paper className="contact-form contact-form-success" role="status">
            <TemplateIcon name="check" size={30} />
            <Typography variant="h4">Response received.</Typography>
            <Typography>{successMessage(submission.discussionType)}</Typography>
            {submission.email && (
              <Typography className="contact-success-detail">
                {submission.openToCall
                  ? "You said you're open to a conversation, so we can follow up using the email you provided."
                  : "If a reply is useful, we can follow up using the email you provided."}
              </Typography>
            )}
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
              {submission.openToCall && config?.talk_booking_url && (
                <Button href={config.talk_booking_url} target="_blank" rel="noreferrer" variant="contained">
                  Book a 15-minute conversation
                </Button>
              )}
              <Button component={RouterLink} to="/try" variant="outlined">Return to the demo</Button>
            </Stack>
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
              <Typography variant="h4">What would you like to share?</Typography>
              <Typography>Choose a path. We only ask follow-up questions that are useful for that response.</Typography>
            </Box>

            <Box className="contact-intent-grid" role="group" aria-label="What would you like to share?">
              {discussionOptions.map((option) => {
                const selected = submission.discussionType === option.value;
                return (
                  <Button
                    key={option.value}
                    type="button"
                    variant={selected ? "contained" : "outlined"}
                    aria-pressed={selected}
                    onClick={() => chooseDiscussion(option.value)}
                    className="contact-intent-option"
                  >
                    <strong>{option.title}</strong>
                    <span>{option.description}</span>
                  </Button>
                );
              })}
            </Box>

            <Box className="contact-section-heading">
              <Typography variant="h6">
                {identityRequired ? "About you" : "About you — optional"}
              </Typography>
              <Typography>
                {identityRequired
                  ? "Enough context to understand the workflow and follow up intelligently."
                  : "You can leave feedback without identifying yourself. Add an email only if you'd like a reply."}
              </Typography>
            </Box>

            <Box className="contact-form-grid">
              <TextField
                required={identityRequired}
                label={identityRequired ? "Name" : "Name (optional)"}
                value={submission.name}
                onChange={update("name")}
                autoComplete="name"
              />
              <TextField
                required={emailRequired}
                type="email"
                label={emailRequired ? "Work email" : "Email (optional)"}
                value={submission.email}
                onChange={update("email")}
                autoComplete="email"
                helperText={!emailRequired ? "Only if you'd like a reply." : undefined}
              />
              <TextField
                required={identityRequired}
                label={identityRequired ? "Company" : "Company (optional)"}
                value={submission.company}
                onChange={update("company")}
                autoComplete="organization"
              />
              <TextField
                label="Role (optional)"
                value={submission.role}
                onChange={update("role")}
                autoComplete="organization-title"
                placeholder="Finance, procurement, CX, support, engineering…"
              />
            </Box>

            {billingConversation && (
              <>
                <Box className="contact-section-heading">
                  <Typography variant="h6">Your current control</Typography>
                  <Typography>Three quick answers tell us far more than a generic “interested” submission.</Typography>
                </Box>
                <Box className="contact-form-grid">
                  <TextField select required label="How are you charged?" value={submission.billingModel} onChange={update("billingModel")}>
                    <MenuItem value="" disabled>Select one</MenuItem>
                    {billingModels.map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}
                  </TextField>
                  <TextField select required label="How is it verified today?" value={submission.verificationMethod} onChange={update("verificationMethod")}>
                    <MenuItem value="" disabled>Select one</MenuItem>
                    {verificationMethods.map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}
                  </TextField>
                  <TextField select required label="Where does the evidence live?" value={submission.evidenceLocation} onChange={update("evidenceLocation")}>
                    <MenuItem value="" disabled>Select one</MenuItem>
                    {evidenceLocations.map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}
                  </TextField>
                  <TextField select required label="If the numbers don't match, what happens?" value={submission.commercialAction} onChange={update("commercialAction")}>
                    <MenuItem value="" disabled>Select one</MenuItem>
                    {commercialActions.map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}
                  </TextField>
                </Box>
              </>
            )}

            {submission.discussionType === "Product feedback" && (
              <>
                <Box className="contact-section-heading">
                  <Typography variant="h6">Your feedback</Typography>
                  <Typography>Tell us where your reaction came from so we can act on it.</Typography>
                </Box>
                <TextField
                  select
                  required
                  fullWidth
                  label="What is your feedback mainly about?"
                  value={submission.feedbackArea}
                  onChange={update("feedbackArea")}
                >
                  <MenuItem value="" disabled>Select one</MenuItem>
                  {feedbackAreas.map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}
                </TextField>
              </>
            )}

            <Box className="contact-section-heading contact-message-heading">
              <Typography variant="h6">In your own words</Typography>
            </Box>
            <TextField
              required
              multiline
              minRows={6}
              fullWidth
              label={messageLabel(submission.discussionType)}
              value={submission.message}
              onChange={update("message")}
              helperText={`${submission.message.length}/4000 characters`}
              inputProps={{ maxLength: 4000 }}
            />

            <FormControlLabel
              className="contact-call-opt-in"
              control={(
                <Checkbox
                  checked={submission.openToCall}
                  onChange={(event) => setSubmission((current) => ({ ...current, openToCall: event.target.checked }))}
                />
              )}
              label="I'm open to a 15-minute conversation about this."
            />

            <Alert severity="info" className="contact-privacy-note">
              Please don't paste confidential contracts, invoices, customer records, credentials, or production data here. If we need to inspect something sensitive, we'll arrange a safer path separately.
            </Alert>
            {error && (
              <Alert severity="error" ref={errorRef} tabIndex={-1} aria-live="assertive" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}
            <FormControlLabel
              control={<Checkbox checked={safeToShare} onChange={(event) => setSafeToShare(event.target.checked)} />}
              label="I confirm this message contains no confidential or customer data."
            />
            <Box className="contact-submit-row">
              <Button type="submit" variant="contained" size="large" disabled={!safeToShare || submitting} endIcon={<TemplateIcon name="arrow" size={17} />}>
                {submitting
                  ? "Submitting…"
                  : submission.discussionType === "Product feedback"
                    ? "Send feedback"
                    : "Send response"}
              </Button>
              <Typography>Usually under a minute.</Typography>
            </Box>
          </Paper>
        )}
      </Container>
    </Box>
  );
}
