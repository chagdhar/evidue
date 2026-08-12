import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { PublicConfigProvider } from "./BetaApplicationCTA";
import ContactPage from "./ContactPage";

function Wrapper({ children }: { children: ReactNode }) { return <MemoryRouter><PublicConfigProvider>{children}</PublicConfigProvider></MemoryRouter>; }
function response(body: unknown, ok = true) { return Promise.resolve({ ok, text: () => Promise.resolve(JSON.stringify(body)), json: () => Promise.resolve(body) } as Response); }
function publicConfig(configured = true) { return { beta_form_configured: false, beta_form_url: null, contact_form_configured: configured, talk_booking_url: "https://cal.com/evidue/15min" }; }
async function chooseSelect(user: ReturnType<typeof userEvent.setup>, label: string, option: string) { await user.click(screen.getByLabelText(label)); await user.click(await screen.findByRole("option", { name: option })); }
afterEach(() => { vi.restoreAllMocks(); sessionStorage.clear(); });

it("starts with one explicit intent choice before revealing the form", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(() => response(publicConfig(false)));
  render(<ContactPage />, { wrapper: Wrapper });
  expect(await screen.findByRole("heading", { name: "One minute. Useful context only." })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /AI-vendor billing/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Product feedback/ })).toBeInTheDocument();
  expect(screen.queryByLabelText("Name *")).not.toBeInTheDocument();
});

it("accepts anonymous product feedback and sends structured context", async () => {
  sessionStorage.setItem("evidue-attribution-source", "indie_hackers");
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => String(input).endsWith("/api/public-config") ? response(publicConfig()) : response({ accepted: true }));
  const user = userEvent.setup(); render(<ContactPage />, { wrapper: Wrapper });
  await user.click(await screen.findByRole("button", { name: /Product feedback/ }));
  expect(screen.getByLabelText("Name (optional)")).not.toBeRequired();
  await chooseSelect(user, "What is your feedback mainly about? *", "Demo clarity");
  await user.type(screen.getByLabelText("What worked, what was confusing, or what would you change? *"), "The result is compelling, but the evidence trail should appear earlier.");
  await user.click(screen.getByRole("checkbox", { name: "I confirm this message contains no confidential or customer data." }));
  await user.click(screen.getByRole("button", { name: "Send feedback" }));
  await screen.findByRole("heading", { name: "Thank you." });
  const calls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/api/contact-submissions"));
  const payload = JSON.parse(String(calls[0][1]?.body));
  expect(payload).toMatchObject({ discussion_type: "Product feedback", feedback_area: "Demo clarity", attribution_source: "indie_hackers", confirmed_no_confidential_data: true });
});

it("captures the core Evidue qualification gates and offers booking after call opt-in", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => String(input).endsWith("/api/public-config") ? response(publicConfig()) : response({ accepted: true }));
  const user = userEvent.setup(); render(<ContactPage />, { wrapper: Wrapper });
  await user.click(await screen.findByRole("button", { name: /AI-vendor billing/ }));
  await user.type(screen.getByLabelText("Name *"), "Alex Buyer"); await user.type(screen.getByLabelText("Work email *"), "alex@example.com"); await user.type(screen.getByLabelText("Company *"), "Acme Commerce");
  await chooseSelect(user, "How are you charged? *", "Per outcome"); await chooseSelect(user, "How is it verified today? *", "Reconcile exports"); await chooseSelect(user, "Where does the evidence live? *", "Multiple customer systems"); await chooseSelect(user, "If the numbers don't match, what happens? *", "Request a credit");
  await user.type(screen.getByLabelText("What is hardest about verifying the bill today? *"), "Joining vendor claims to customer records is manual.");
  await user.click(screen.getByRole("checkbox", { name: "I'm open to a 15-minute conversation about this." })); await user.click(screen.getByRole("checkbox", { name: "I confirm this message contains no confidential or customer data." })); await user.click(screen.getByRole("button", { name: "Send response" }));
  await screen.findByRole("heading", { name: "Thank you." });
  const calls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/api/contact-submissions")); const payload = JSON.parse(String(calls[0][1]?.body));
  expect(payload).toMatchObject({ discussion_type: "Invoice review", billing_model: "Per outcome", verification_method: "Reconcile exports", evidence_location: "Multiple customer systems", commercial_action: "Request a credit", open_to_call: true });
  expect(screen.getByRole("link", { name: "Book 15 minutes" })).toHaveAttribute("href", "https://cal.com/evidue/15min");
});

it("preserves answers when delivery fails", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => String(input).endsWith("/api/public-config") ? response(publicConfig(false)) : response({ detail: "internal" }, false));
  const user = userEvent.setup(); render(<ContactPage />, { wrapper: Wrapper });
  await user.click(await screen.findByRole("button", { name: /Product feedback/ })); await chooseSelect(user, "What is your feedback mainly about? *", "User experience");
  const message = screen.getByLabelText("What worked, what was confusing, or what would you change? *"); await user.type(message, "The contract approval step needs a clearer explanation.");
  await user.click(screen.getByRole("checkbox", { name: "I confirm this message contains no confidential or customer data." })); await user.click(screen.getByRole("button", { name: "Send feedback" }));
  const error = await screen.findByText(/We couldn't send your response right now/); const alert = error.closest('[role="alert"]'); expect(alert).not.toBeNull(); await waitFor(() => expect(alert).toHaveFocus()); expect(message).toHaveValue("The contract approval step needs a clearer explanation.");
});
