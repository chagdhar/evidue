import { expect, test } from "@playwright/test";

const token = "evidue-e2e-pilot-token-32-characters";

test("a first-time finance user can complete the protected product path", async ({ page }) => {
  await page.goto("/pilot");
  await expect(page.getByRole("heading", { name: "Open your finance workspace" })).toBeVisible();
  await page.getByLabel("Access key").fill(token);
  await page.getByRole("button", { name: "Open workspace" }).click();

  await expect(page.getByRole("heading", { name: /get to a defensible payable amount/i })).toBeVisible();

  // Configuration is a first-class product surface, while secrets remain server-managed.
  await page.getByRole("button", { name: "Configuration" }).click();
  await expect(page.getByRole("heading", { name: "Workspace settings" })).toBeVisible();
  await expect(page.getByText("Integration readiness")).toBeVisible();
  await expect(page.getByText(/never reads or stores API keys/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Reset workspace data" })).toBeDisabled();
  await page.getByRole("button", { name: "Workspace", exact: true }).click();

  await page.getByRole("button", { name: "Try sample workspace" }).click();

  await expect(page.getByText("Sample workspace is ready.")).toBeVisible();
  await expect(page.getByText("Verified payable").first()).toBeVisible();
  await expect(page.getByText("Charges identified for dispute").first()).toBeVisible();
  await expect(page.getByText("Needs review", { exact: true }).first()).toBeVisible();

  await expect(page.getByText("OUT-SAMPLE-001")).toBeVisible();
  await expect(page.getByText("OUT-SAMPLE-002")).toBeVisible();
  await expect(page.getByText("OUT-SAMPLE-003")).toBeVisible();
  await expect(page.getByText("SOURCE AGREEMENT").first()).toBeVisible();
  await expect(page.getByText("EVIDENCE TIMELINE").first()).toBeVisible();
  await expect(page.getByText(/Not payable if/i).first()).toBeVisible();

  // Technical provenance is deliberately progressive disclosure on the Decision stage.
  await page.getByRole("button", { name: "Show", exact: true }).click();
  await expect(page.getByText("Rule verification", { exact: true })).toBeVisible();
  await expect(page.getByText("Workspace audit history")).toBeVisible();

  // The final stage turns the persisted decision into finance/vendor handoff artifacts.
  await page.getByRole("button", { name: /^Send & export/ }).click();
  await expect(page.getByRole("button", { name: "Corrected invoice CSV" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Vendor dispute report" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Copy vendor email" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Disputed lines CSV" })).toBeEnabled();

  // Reset is intentionally kept in Configuration and requires typed confirmation.
  await page.getByRole("button", { name: "Configuration" }).click();
  await expect(page.getByRole("button", { name: "Reset workspace data" })).toBeEnabled();
  await page.getByRole("button", { name: "Reset workspace data" }).click();
  await expect(page.getByRole("button", { name: "Reset workspace" })).toBeDisabled();
  await page.getByLabel('Type "RESET"').fill("RESET");
  await expect(page.getByRole("button", { name: "Reset workspace" })).toBeEnabled();
});
