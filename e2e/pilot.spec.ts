import { expect, test } from "@playwright/test";

const token = "evidue-e2e-pilot-token-32-characters";

test("a first-time finance user can complete the invoice-centered protected product path", async ({ page }) => {
  await page.goto("/pilot");
  await expect(page).toHaveURL(/\/workspace\/invoices\/current$/);
  await expect(page.getByRole("heading", { name: "Open your reconciliation workspace" })).toBeVisible();
  await page.getByLabel("Workspace access key").fill(token);
  await page.getByRole("button", { name: "Open workspace" }).click();

  await expect(page.getByRole("button", { name: "Invoices" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { name: /Get to a defensible payable amount/i })).toBeVisible();

  // Workspace configuration remains available without exposing server-managed secrets.
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(page).toHaveURL(/\/workspace\/settings$/);
  await expect(page.getByRole("heading", { name: "Workspace settings" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Workspace controls" })).toBeVisible();
  await expect(page.getByText("Integration readiness")).toBeVisible();
  await expect(page.getByText(/never reads or stores API keys/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Reset workspace data" })).toBeDisabled();

  // Return through the real invoice register rather than a separate pilot application.
  await page.getByRole("button", { name: "Invoices", exact: true }).click();
  await expect(page).toHaveURL(/\/workspace\/invoices$/);
  await expect(page.getByRole("heading", { name: "Vendor invoice register" })).toBeVisible();
  await page.getByRole("button", { name: "New reconciliation" }).click();
  await expect(page).toHaveURL(/\/workspace\/invoices\/current$/);

  await page.getByRole("button", { name: "Load guided sample" }).click();
  await expect(page.getByText("Guided sample is ready.")).toBeVisible();

  // The invoice itself stays visible while finance moves through the lifecycle.
  await expect(page.getByText("Vendor billed").first()).toBeVisible();
  await expect(page.getByText("Verified payable").first()).toBeVisible();
  await expect(page.getByText("Identified for dispute").first()).toBeVisible();
  await expect(page.getByText("Needs review", { exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "Verification" }).click();
  await expect(page.getByText(/invoice value identified for dispute/i)).toBeVisible();

  await page.getByRole("button", { name: "Review", exact: true }).click();
  await expect(page.getByRole("heading", { name: /Facts first\. Commercial action second/i })).toBeVisible();
  await expect(
    page.locator("p.section-kicker").filter({ hasText: /^WHAT HAPPENED$/ }),
  ).toBeVisible();
  await expect(
    page.locator("p.section-kicker").filter({ hasText: /^WHAT FINANCE CAN DO$/ }),
  ).toBeVisible();

  // Technical provenance is progressive disclosure, not primary finance copy.
  await page.getByRole("button", { name: "View technical details" }).click();
  await expect(page.getByText("Rule verification", { exact: true })).toBeVisible();
  await expect(page.getByText("Workspace audit history")).toBeVisible();

  // Commercial action closes the loop with vendor/AP artifacts.
  await page.getByRole("button", { name: "Commercial action" }).click();
  await expect(page.getByRole("button", { name: "Corrected invoice CSV" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Copy vendor dispute email" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Download dispute package" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Download disputed lines" })).toBeEnabled();

  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(page.getByRole("button", { name: "Reset workspace data" })).toBeEnabled();
  await page.getByRole("button", { name: "Reset workspace data" }).click();
  await expect(page.getByRole("button", { name: "Reset workspace" })).toBeDisabled();
  await page.getByLabel('Type "RESET"').fill("RESET");
  await expect(page.getByRole("button", { name: "Reset workspace" })).toBeEnabled();
});
