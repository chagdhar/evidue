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

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

it("shows a short, privacy-aware feedback form only when delivery is configured", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(() => response({
    beta_form_configured: true,
    beta_form_url: "https://tally.so/r/test-form",
    contact_form_configured: true,
  }));
  render(<ContactPage />, { wrapper: Wrapper });

  expect(await screen.findByRole("heading", { name: "Tell me what you think." })).toBeInTheDocument();
  expect(screen.getByLabelText("Name *")).toBeRequired();
  expect(screen.getByLabelText("Email *")).toBeRequired();
  expect(screen.getByLabelText("Company *")).toBeRequired();
  expect(screen.getByLabelText("Message *")).toBeRequired();
  expect(screen.getByText(/stored in a private Google Sheet and used only for Evidue product research and follow-up/i)).toBeInTheDocument();
  expect(screen.queryByLabelText(/monthly/i)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Submit feedback" })).toBeDisabled();

  const user = userEvent.setup();
  await user.tab();
  expect(screen.getByRole("link", { name: "Evidue landing page" })).toHaveFocus();
});

it("submits attribution and backend-enforced privacy confirmation once", async () => {
  sessionStorage.setItem("evidue-attribution-source", "hacker_news");
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    if (String(input).endsWith("/api/public-config")) {
      return response({
        beta_form_configured: true,
        beta_form_url: "https://tally.so/r/test-form",
        contact_form_configured: true,
      });
    }
    return response({ accepted: true });
  });
  const user = userEvent.setup();
  render(<ContactPage />, { wrapper: Wrapper });

  await user.type(await screen.findByLabelText("Name *"), "Alex Buyer");
  await user.type(screen.getByLabelText("Email *"), "alex@example.com");
  await user.type(screen.getByLabelText("Company *"), "Acme Commerce");
  await user.type(screen.getByLabelText("Message *"), "Evidence matching takes too long for finance.");
  await user.click(screen.getByRole("checkbox", {
    name: "I confirm this message contains no confidential or customer data.",
  }));
  await user.dblClick(screen.getByRole("button", { name: "Submit feedback" }));

  await screen.findByRole("heading", { name: "Response received." });
  const submissionCalls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/api/contact-submissions"));
  expect(submissionCalls).toHaveLength(1);
  const payload = JSON.parse(String(submissionCalls[0][1]?.body));
  expect(payload).toMatchObject({
    email: "alex@example.com",
    company: "Acme Commerce",
    discussion_type: "Product feedback",
    confirmed_no_confidential_data: true,
    attribution_source: "hacker_news",
    campaign: "railway_beta",
    demo_version: "hn_demo",
    website: "",
  });
  expect(payload.submission_id).toMatch(/^[0-9a-f-]{36}$/);
  expect(payload.browser_session_id).toMatch(/^[0-9a-f-]{36}$/);
  expect(payload.form_started_at).toContain("T");
  expect(screen.queryByRole("button", { name: "Submit feedback" })).not.toBeInTheDocument();
});

it("shows and focuses a generic fallback when the backend fails", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    if (String(input).endsWith("/api/public-config")) {
      return response({
        beta_form_configured: false,
        beta_form_url: null,
        contact_form_configured: true,
      });
    }
    return response({ detail: "internal webhook detail" }, false);
  });
  const user = userEvent.setup();
  render(<ContactPage />, { wrapper: Wrapper });

  await user.type(await screen.findByLabelText("Name *"), "Alex Buyer");
  await user.type(screen.getByLabelText("Email *"), "alex@example.com");
  await user.type(screen.getByLabelText("Company *"), "Acme Commerce");
  await user.type(screen.getByLabelText("Message *"), "I have useful product feedback to share.");
  await user.click(screen.getByRole("checkbox"));
  await user.click(screen.getByRole("button", { name: "Submit feedback" }));

  const errorText = await screen.findByText(/Your response could not be submitted right now/);
  const alert = errorText.closest('[role="alert"]');
  expect(alert).not.toBeNull();
  expect(alert).toHaveTextContent("Your response could not be submitted right now");
  expect(alert).not.toHaveTextContent("webhook");
  await waitFor(() => expect(alert).toHaveFocus());
  expect(screen.getByRole("link", { name: "Email Dharun" })).toHaveAttribute("href", expect.stringContaining("mailto:"));
});

it("shows an email fallback before any form work when storage is unavailable", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(() => response({
    beta_form_configured: false,
    beta_form_url: null,
    contact_form_configured: false,
  }));
  render(<ContactPage />, { wrapper: Wrapper });

  expect(await screen.findByRole("heading", { name: "Feedback form unavailable." })).toBeInTheDocument();
  expect(screen.queryByLabelText("Name *")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Email Dharun" })).toHaveAttribute("href", expect.stringContaining("mailto:"));
});
