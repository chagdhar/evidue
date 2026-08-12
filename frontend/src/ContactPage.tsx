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
import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { browserSessionId, contactAttribution, track } from "./analytics";
import { usePublicConfig } from "./BetaApplicationCTA";
import { api } from "./api";
import { type ContactDiscussionType, type ContactSubmission } from "./contact";
import { TemplateIcon } from "./TemplateIcons";
import { DecisionFlow } from "./DecisionLedger";

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
  meta: string;
}> = [
  { value: "Invoice review", title: "AI-vendor billing", description: "I deal with outcome, resolution, action, or usage charges.", meta: "Customer discovery" },
  { value: "Product feedback", title: "Product feedback", description: "I tried Evidue and want to tell you what worked or did not.", meta: "Can be anonymous" },
  { value: "Partnership", title: "Partnership", description: "I want to discuss an integration, data source, or partnership.", meta: "Business conversation" },
  { value: "Other", title: "Something else", description: "I have another question, comment, or piece of feedback.", meta: "Open message" },
];

const billingModels = ["Per outcome", "Per resolution", "Per action", "Usage-based", "Fixed / seat-based", "Not sure", "Other"];
const verificationMethods = ["Vendor report only", "Manual spot checks", "Reconcile exports", "Internal tooling", "Not independently verified", "Not sure"];
const evidenceLocations = ["Support / helpdesk data", "Payments / billing records", "CRM / account data", "Product / event logs", "Multiple customer systems", "Mostly vendor-controlled", "Not sure"];
const commercialActions = ["Dispute before payment", "Request a credit", "True-up later", "Use it at renewal", "No financial action today", "Not sure", "Other"];
const feedbackAreas = ["Product idea", "Try flow clarity", "Trust / evidence", "User experience", "Bug", "Positioning", "Other"];

function ContactHeader() {
  return (
    <Box component="header" className="contact-header">
      <Container maxWidth="lg" className="contact-container">
        <RouterLink to="/" className="contact-wordmark" aria-label="Evidue landing page">
          <span aria-hidden="true">E</span><strong>Evidue</strong>
        </RouterLink>
        <Stack direction="row" spacing={1}>
          <Button component={RouterLink} to="/" color="inherit">Home</Button>
          <Button component={RouterLink} to="/try" variant="outlined">Back to demo</Button>
        </Stack>
      </Container>
    </Box>
  );
}

function messageLabel(type: ContactDiscussionType) {
  if (type === "Invoice review") return "What is hardest about verifying the bill today?";
  if (type === "Product feedback") return "What worked, what was confusing, or what would you change?";
  if (type === "Partnership") return "What would you like to explore together?";
  return "What would you like to tell us?";
}

function successMessage(type: ContactDiscussionType) {
  if (type === "Invoice review") return "Thanks. This is exactly the kind of real workflow we are trying to understand.";
  if (type === "Product feedback") return "Thanks. Specific criticism is useful—we read every response.";
  return "Thanks. Your response was received.";
}

export default function ContactPage() {
  const config = usePublicConfig();
  const [submission, setSubmission] = useState(initialSubmission);
  const [intentChosen, setIntentChosen] = useState(false);
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
  const currentStep = submitted ? 3 : intentChosen ? 2 : 1;
  const completion = useMemo(() => Math.round((currentStep / 3) * 100), [currentStep]);

  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);

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
    setIntentChosen(true);
    setError("");
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true); setError("");
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
      track("contact_form_submitted", { discussion_type: submission.discussionType, open_to_call: submission.openToCall });
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
          <Typography className="contact-overline">TALK TO EVIDUE</Typography>
          <Typography component="h1">One minute. Useful context only.</Typography>
          <Typography className="contact-lede">
            Tell us why you came. We ask only the questions relevant to that reason. Product feedback can be anonymous.
          </Typography>
          <Box className="contact-signal-list">
            <Box><strong>&lt; 1 min</strong><span>Typical completion time</span></Box>
            <Box><strong>No signup</strong><span>Nothing to create or configure</span></Box>
            <Box><strong>No sensitive data</strong><span>Keep contracts and customer records out of this form</span></Box>
          </Box>
          <Box className="contact-expectations">
            <Typography variant="h5">We want the inconvenient answer.</Typography>
            <Typography>If you never verify vendor charges, say that. If the demo was confusing or unconvincing, say that too.</Typography>
          </Box>
          <Box className="contact-decision-grammar">
            <Typography className="contact-section-kicker">THE CONTROL WE ARE TESTING</Typography>
            <DecisionFlow compact />
          </Box>
        </Box>

        <Paper className="contact-form-shell" variant="outlined">
          <Box className="contact-progress" aria-label={`Contact form ${completion}% complete`}>
            {["Choose", "Context", "Sent"].map((label, index) => {
              const step = index + 1;
              return <Box key={label} className={`contact-progress-step${step <= currentStep ? " active" : ""}`}><span>{step < currentStep ? "✓" : step}</span><Typography>{label}</Typography></Box>;
            })}
          </Box>

          {submitted ? (
            <Box className="contact-success" role="status">
              <Box className="contact-success-mark"><TemplateIcon name="check" size={24} /></Box>
              <Typography className="contact-section-kicker">RESPONSE RECEIVED</Typography>
              <Typography component="h2">Thank you.</Typography>
              <Typography>{successMessage(submission.discussionType)}</Typography>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1.25} sx={{ mt: 2 }}>
                {submission.openToCall && config?.talk_booking_url && <Button href={config.talk_booking_url} target="_blank" rel="noreferrer" variant="contained">Book 15 minutes</Button>}
                <Button component={RouterLink} to="/try" variant="outlined">Return to demo</Button>
              </Stack>
            </Box>
          ) : !intentChosen ? (
            <Box className="contact-intent-stage">
              <Typography className="contact-section-kicker">STEP 1 OF 3</Typography>
              <Typography component="h2">What brought you here?</Typography>
              <Typography className="contact-stage-copy">Choose the closest match. Nothing else is shown until you do.</Typography>
              <Box className="contact-intent-grid" role="group" aria-label="What would you like to share?">
                {discussionOptions.map((option) => (
                  <Button key={option.value} type="button" variant="outlined" onClick={() => chooseDiscussion(option.value)} className="contact-intent-option">
                    <Box className="contact-intent-copy"><strong>{option.title}</strong><span>{option.description}</span><small>{option.meta}</small></Box>
                    <span className="contact-intent-arrow" aria-hidden="true">→</span>
                  </Button>
                ))}
              </Box>
            </Box>
          ) : (
            <Box component="form" onSubmit={(event) => void submit(event)} className="contact-form">
              <input className="contact-honeypot" type="text" name="website" value={website} onChange={(event) => setWebsite(event.target.value)} tabIndex={-1} autoComplete="off" aria-hidden="true" />
              <Box className="contact-stage-header">
                <Box>
                  <Typography className="contact-section-kicker">STEP 2 OF 3</Typography>
                  <Typography component="h2">Add only the context that matters.</Typography>
                  <Typography className="contact-stage-copy">
                    {identityRequired ? "We need enough context to understand the workflow and follow up intelligently." : "Identity is optional. Add an email only if you want a reply."}
                  </Typography>
                </Box>
                <Button type="button" variant="text" onClick={() => setIntentChosen(false)}>Change reason</Button>
              </Box>

              <Box className="contact-form-grid">
                <TextField required={identityRequired} label={identityRequired ? "Name" : "Name (optional)"} value={submission.name} onChange={update("name")} autoComplete="name" />
                <TextField required={emailRequired} type="email" label={emailRequired ? "Work email" : "Email (optional)"} value={submission.email} onChange={update("email")} autoComplete="email" helperText={!emailRequired ? "Only if you'd like a reply." : undefined} />
                <TextField required={identityRequired} label={identityRequired ? "Company" : "Company (optional)"} value={submission.company} onChange={update("company")} autoComplete="organization" />
                <TextField label="Role (optional)" value={submission.role} onChange={update("role")} autoComplete="organization-title" placeholder="Finance, procurement, CX, support…" />
              </Box>

              {billingConversation && (
                <Box className="contact-adaptive-section">
                  <Box className="contact-section-heading"><Typography className="contact-section-kicker">4 QUALIFICATION SIGNALS</Typography><Typography component="h3">How does the control work today?</Typography></Box>
                  <Box className="contact-form-grid">
                    <TextField select required label="How are you charged?" value={submission.billingModel} onChange={update("billingModel")}><MenuItem value="" disabled>Select one</MenuItem>{billingModels.map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}</TextField>
                    <TextField select required label="How is it verified today?" value={submission.verificationMethod} onChange={update("verificationMethod")}><MenuItem value="" disabled>Select one</MenuItem>{verificationMethods.map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}</TextField>
                    <TextField select required label="Where does the evidence live?" value={submission.evidenceLocation} onChange={update("evidenceLocation")}><MenuItem value="" disabled>Select one</MenuItem>{evidenceLocations.map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}</TextField>
                    <TextField select required label="If the numbers don't match, what happens?" value={submission.commercialAction} onChange={update("commercialAction")}><MenuItem value="" disabled>Select one</MenuItem>{commercialActions.map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}</TextField>
                  </Box>
                </Box>
              )}

              {submission.discussionType === "Product feedback" && (
                <Box className="contact-adaptive-section">
                  <TextField select required fullWidth label="What is your feedback mainly about?" value={submission.feedbackArea} onChange={update("feedbackArea")}><MenuItem value="" disabled>Select one</MenuItem>{feedbackAreas.map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}</TextField>
                </Box>
              )}

              <Box className="contact-message-section">
                <Typography className="contact-section-kicker">YOUR WORDS</Typography>
                <TextField required multiline minRows={5} fullWidth label={messageLabel(submission.discussionType)} value={submission.message} onChange={update("message")} helperText={`${submission.message.length}/4000`} inputProps={{ maxLength: 4000 }} />
              </Box>

              <FormControlLabel control={<Checkbox checked={submission.openToCall} onChange={(event) => setSubmission((current) => ({ ...current, openToCall: event.target.checked }))} />} label="I'm open to a 15-minute conversation about this." />
              <Typography className="contact-privacy-copy">Do not include confidential contracts, invoices, credentials, customer records, or production data.</Typography>
              {error && <Alert severity="error" ref={errorRef} tabIndex={-1} aria-live="assertive">{error}</Alert>}
              <FormControlLabel control={<Checkbox checked={safeToShare} onChange={(event) => setSafeToShare(event.target.checked)} />} label="I confirm this message contains no confidential or customer data." />
              <Box className="contact-submit-row">
                <Button type="submit" variant="contained" size="large" disabled={!safeToShare || submitting} endIcon={<TemplateIcon name="arrow" size={17} />}>
                  {submitting ? "Submitting…" : submission.discussionType === "Product feedback" ? "Send feedback" : "Send response"}
                </Button>
                <Typography>Step 3 completes when the response is received.</Typography>
              </Box>
            </Box>
          )}
        </Paper>
      </Container>
    </Box>
  );
}
