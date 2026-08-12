import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { PublicConfigProvider } from "./BetaApplicationCTA";
import ContactPage from "./ContactPage";

function Wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter><PublicConfigProvider>{children}</PublicConfigProvider></MemoryRouter>;
}

function response(body: unknown, ok = true) {
  return Promise.resolve({
    ok,
    text: () => Promise.resolve(JSON.stringify(body)),
    json: () => Promise.resolve(body),
  } as Response);
}

function publicConfig(configured = true) {
  return {
    beta_form_configured: false,
    beta_form_url: null,
    contact_form_configured: configured,
    talk_booking_url: "https://cal.com/evidue/15min",
  };
}

async function chooseSelect(user: ReturnType<typeof userEvent.setup>, label: string, option: string) {
  await user.click(screen.getByLabelText(label));
  await user.click(await screen.findByRole("option", { name: option }));
}

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

it("always renders a progressive contact form and asks billing visitors for high-signal context", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(() => response(publicConfig(false)));
  render(<ContactPage />, { wrapper: Wrapper });

  expect(await screen.findByRole("heading", { name: "Tell us what's true." })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /AI-vendor billing/ })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByLabelText("Name *")).toBeRequired();
  expect(screen.getByLabelText("Work email *")).toBeRequired();
  expect(screen.getByLabelText("Company *")).toBeRequired();
  expect(screen.getByLabelText("Role (optional)")).not.toBeRequired();
  expect(screen.getByLabelText("How are you charged? *")).toBeRequired();
  expect(screen.getByLabelText("How is it verified today? *")).toBeRequired();
  expect(screen.getByLabelText("Where does the evidence live? *")).toBeRequired();
  expect(screen.getByLabelText("If the numbers don't match, what happens? *")).toBeRequired();
  expect(screen.getByRole("button", { name: "Send response" })).toBeDisabled();
  expect(screen.queryByText(/personal email/i)).not.toBeInTheDocument();
});

it("accepts anonymous generic product feedback and sends structured feedback context", async () => {
  sessionStorage.setItem("evidue-attribution-source", "indie_hackers");
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    if (String(input).endsWith("/api/public-config")) return response(publicConfig());
    return response({ accepted: true });
  });
  const user = userEvent.setup();
  render(<ContactPage />, { wrapper: Wrapper });

  await user.click(await screen.findByRole("button", { name: /Product feedback/ }));
  expect(screen.getByLabelText("Name (optional)")).not.toBeRequired();
  expect(screen.getByLabelText("Email (optional)")).not.toBeRequired();
  expect(screen.getByLabelText("Company (optional)")).not.toBeRequired();

  await chooseSelect(user, "What is your feedback mainly about? *", "Demo clarity");
  await user.type(
    screen.getByLabelText("What worked, what was confusing, or what would you change? *"),
    "The deterministic result is compelling, but I wanted the evidence trail earlier.",
  );
  await user.click(screen.getByRole("checkbox", {
    name: "I confirm this message contains no confidential or customer data.",
  }));
  await user.click(screen.getByRole("button", { name: "Send feedback" }));

  await screen.findByRole("heading", { name: "Response received." });
  const calls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/api/contact-submissions"));
  expect(calls).toHaveLength(1);
  const payload = JSON.parse(String(calls[0][1]?.body));
  expect(payload).toMatchObject({
    name: "",
    email: "",
    company: "",
    role: "",
    discussion_type: "Product feedback",
    feedback_area: "Demo clarity",
    billing_model: "",
    verification_method: "",
    evidence_location: "",
    commercial_action: "",
    open_to_call: false,
    attribution_source: "indie_hackers",
    confirmed_no_confidential_data: true,
  });
  expect(screen.queryByRole("link", { name: "Book a 15-minute conversation" })).not.toBeInTheDocument();
});

it("captures the core Evidue qualification gates and offers booking only after call opt-in", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    if (String(input).endsWith("/api/public-config")) return response(publicConfig());
    return response({ accepted: true });
  });
  const user = userEvent.setup();
  render(<ContactPage />, { wrapper: Wrapper });

  await user.type(await screen.findByLabelText("Name *"), "Alex Buyer");
  await user.type(screen.getByLabelText("Work email *"), "alex@example.com");
  await user.type(screen.getByLabelText("Company *"), "Acme Commerce");
  await user.type(screen.getByLabelText("Role (optional)"), "VP Finance");
  await chooseSelect(user, "How are you charged? *", "Per outcome");
  await chooseSelect(user, "How is it verified today? *", "Reconcile exports");
  await chooseSelect(user, "Where does the evidence live? *", "Multiple customer systems");
  await chooseSelect(user, "If the numbers don't match, what happens? *", "Request a credit");
  await user.type(
    screen.getByLabelText("What is hardest about verifying the bill today? *"),
    "Joining the vendor claims to our own support and payment records is manual.",
  );
  await user.click(screen.getByRole("checkbox", { name: "I'm open to a 15-minute conversation about this." }));
  await user.click(screen.getByRole("checkbox", {
    name: "I confirm this message contains no confidential or customer data.",
  }));
  await user.click(screen.getByRole("button", { name: "Send response" }));

  await screen.findByRole("heading", { name: "Response received." });
  const calls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/api/contact-submissions"));
  const payload = JSON.parse(String(calls[0][1]?.body));
  expect(payload).toMatchObject({
    role: "VP Finance",
    discussion_type: "Invoice review",
    billing_model: "Per outcome",
    verification_method: "Reconcile exports",
    evidence_location: "Multiple customer systems",
    commercial_action: "Request a credit",
    feedback_area: "",
    open_to_call: true,
  });
  expect(screen.getByRole("link", { name: "Book a 15-minute conversation" })).toHaveAttribute(
    "href",
    "https://cal.com/evidue/15min",
  );
});

it("keeps the form visible and preserves answers when delivery fails", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    if (String(input).endsWith("/api/public-config")) return response(publicConfig(false));
    return response({ detail: "internal webhook detail" }, false);
  });
  const user = userEvent.setup();
  render(<ContactPage />, { wrapper: Wrapper });

  await user.click(await screen.findByRole("button", { name: /Product feedback/ }));
  await chooseSelect(user, "What is your feedback mainly about? *", "User experience");
  const message = screen.getByLabelText("What worked, what was confusing, or what would you change? *");
  await user.type(message, "The contract rule approval step needs a clearer explanation before the result.");
  await user.click(screen.getByRole("checkbox", {
    name: "I confirm this message contains no confidential or customer data.",
  }));
  await user.click(screen.getByRole("button", { name: "Send feedback" }));

  const errorText = await screen.findByText(/We couldn't send your response right now/);
  const alert = errorText.closest('[role="alert"]');
  expect(alert).not.toBeNull();
  await waitFor(() => expect(alert).toHaveFocus());
  expect(message).toHaveValue("The contract rule approval step needs a clearer explanation before the result.");
  expect(screen.getByRole("button", { name: "Send feedback" })).toBeInTheDocument();
  expect(alert).not.toHaveTextContent("webhook");
  expect(screen.queryByRole("link", { name: /email/i })).not.toBeInTheDocument();
});
