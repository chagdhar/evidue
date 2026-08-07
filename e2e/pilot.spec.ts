import { expect, test } from "@playwright/test";

const token = "evidue-e2e-pilot-token-32-characters";

test("a first-time finance user can complete the protected product path", async ({ page }) => {
  await page.goto("/pilot");
  await expect(page.getByRole("heading", { name: "Open your reconciliation workspace" })).toBeVisible();
  await page.getByLabel("Workspace access key").fill(token);
  await page.getByRole("button", { name: "Open workspace" }).click();

  await expect(page.getByRole("heading", { name: /start with your agreement/i })).toBeVisible();
  await page.getByRole("button", { name: "Try sample workspace" }).click();

  await expect(page.getByText("Sample workspace is ready.")).toBeVisible();
  await expect(page.getByText("Verified payable")).toBeVisible();
  await expect(page.getByText("Recommended deduction")).toBeVisible();
  await expect(page.getByText("Needs review", { exact: true }).first()).toBeVisible();

  await expect(page.getByText("OUT-SAMPLE-001")).toBeVisible();
  await expect(page.getByText("OUT-SAMPLE-002")).toBeVisible();
  await expect(page.getByText("OUT-SAMPLE-003")).toBeVisible();
  await expect(page.getByText("Contract source").first()).toBeVisible();
  await expect(page.getByText("Evidence timeline").first()).toBeVisible();

  await expect(page.getByRole("button", { name: "Corrected invoice CSV" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Review report" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Summary JSON" })).toBeEnabled();

  await page.getByRole("button", { name: "Show" }).click();
  await expect(
  page.getByText("Compiler assurance", { exact: true }),
).toBeVisible();
  await expect(page.getByText("Workspace audit history")).toBeVisible();
});
