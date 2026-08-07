import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { DashboardShell } from "./DashboardShell";
import { PublicConfigProvider } from "./BetaApplicationCTA";

afterEach(() => {
  vi.restoreAllMocks();
});

it("keeps contact and landing-page navigation available in the demo header", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const body = String(input).endsWith("/api/public-config")
      ? { beta_form_configured: false, beta_form_url: null, contact_form_configured: true }
      : { public_demo: true };
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
  });

  render(
    <MemoryRouter initialEntries={["/demo/invoices/current"]}>
      <PublicConfigProvider>
      <Routes>
        <Route path="/demo" element={<DashboardShell onOpenHowItWorks={() => undefined} />}>
          <Route path="invoices/current" element={<div>Decision content</div>} />
        </Route>
        <Route path="/" element={<div>Landing content</div>} />
      </Routes>
      </PublicConfigProvider>
    </MemoryRouter>,
  );

  const contact = await screen.findByRole("link", { name: "Send product feedback" });
  expect(contact.closest("header")).not.toBeNull();
  expect(contact).toHaveAttribute("href", "/contact");
  expect(screen.getByRole("link", { name: "Back to landing page" })).toHaveAttribute("href", "/");
  expect(screen.getAllByRole("link", { name: "Evidue landing page" })[0]).toHaveAttribute("href", "/");
});
