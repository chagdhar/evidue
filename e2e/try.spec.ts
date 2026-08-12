import { expect, test } from "@playwright/test";

test("public Try Evidue carries the full proof path without a separate demo", async ({ page }) => {
  await page.goto("/try");

  await expect(page.getByRole("dialog", { name: "Start with the vendor invoice" })).toBeVisible();
  await page.getByRole("button", { name: "Skip tour" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await expect(page.getByRole("heading", { name: /Nova AI billed Acme \$150 for 100 outcomes/i })).toBeVisible();
  await page.getByRole("button", { name: "Verify the invoice" }).click();
  await expect(page.getByRole("button", { name: "Verify the invoice" })).toHaveCount(0);
  await expect(page.getByText("CONTRACT INTERPRETED", { exact: true })).toBeVisible();

  const proposalHeading = page.getByRole("heading", { name: "Turn source language into explicit payment rules." });
  await expect(proposalHeading).toBeVisible();
  await expect(proposalHeading).toBeInViewport();
  await expect(page.getByText("No same-intent recontact", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Review proposed rules/i })).toBeVisible();

  await page.getByRole("button", { name: /Approve 8 contract rules/i }).click();
  const verifyClaims = page.getByRole("button", { name: "Verify 100 claims" });
  await expect(verifyClaims).toBeInViewport();
  await verifyClaims.click();

  const resultHeading = page.getByRole("heading", { name: /The vendor billed \$150\. Evidue substantiated \$124\.50/i });
  await expect(resultHeading).toBeVisible();
  await expect(resultHeading).toBeInViewport();
  await expect(page.getByText("17 claims contradicted an approved contract rule.", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "R3 · OUT-004821" }).click();
  await expect(page.getByRole("heading", { name: /One charge, from assertion to financial consequence/i })).toBeVisible();
  await expect(page.getByText("OUTCOME RECEIPT", { exact: true })).toBeVisible();
  await expect(page.getByText("EVIDENCE PROVENANCE", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Copy dispute summary" })).toBeVisible();

  await expect(page.locator('a[href^="/demo"], button[data-demo-link]')).toHaveCount(0);
});

test("the retired demo URL is no longer a product surface", async ({ page }) => {
  await page.goto("/demo");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: /Stop paying AI vendors for outcomes that didn’t happen/i })).toBeVisible();
});
