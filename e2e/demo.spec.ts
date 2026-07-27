import { expect, test } from "@playwright/test";

test("complete Evidue financial-decision demo path", async ({ page }) => {
  await page.request.post("/api/demo/reset?scenario_id=evidence_review");
  await page.goto("/demo");

  await expect(page.getByText("Synthetic demonstration data.")).toBeVisible();
  await expect(
    page.getByText(
      "Operationally realistic data generated deterministically. No real customer or vendor data is shown.",
    ),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "What requires attention" })).toBeVisible();
  await expect(page.getByText("$15,000.00", { exact: true })).toBeVisible();
  await expect(page.getByText("One invoice, seven approved rules")).toBeVisible();
  await expect(page.getByLabel("Synthetic data set")).toHaveCount(0);
  await expect(page.getByText("$12,480.00")).not.toBeVisible();

  await page.getByRole("button", { name: "Open June invoice" }).click();
  await expect(page).toHaveURL(/\/demo\/invoices\/current$/);
  await expect(page.getByText("10,000 claimed outcomes from the vendor")).toBeVisible();
  await expect(page.getByText("Ready to reconcile")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Executable billing terms" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Real records are collected and matched before reconciliation" }).first()).toBeVisible();

  await page.getByRole("button", { name: "Run reconciliation" }).click();
  await expect(page.getByText("Evaluating persisted claims and evidence")).toBeVisible();
  await expect(page.locator(".payable-amount")).toHaveText("$12,480.00", {
    timeout: 60_000,
  });
  await expect(page.getByText("$2,520.00", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("8,320 of 10,000 outcomes payable")).toBeVisible();
  await expect(
    page.getByText(
      "No model decides whether a charge is payable. Every amount is reproduced from contract rules and traceable source evidence.",
    ),
  ).toBeVisible();
  await expect(page.getByText("1,680 matching outcomes")).toBeVisible();

  await page.getByRole("button", { name: /Failed downstream actions/ }).click();
  await expect(page.getByText("300 matching outcomes · R3 selected")).toBeVisible();

  await page.getByRole("button", { name: "Review example dispute" }).click();

  await expect(page.getByRole("heading", { name: "OUT-004821", exact: true })).toBeVisible();
  await expect(page.getByText("Vendor claim")).toBeVisible();
  await expect(page.getByText("Contract obligation")).toBeVisible();
  await expect(page.getByText("Evidue determination")).toBeVisible();
  await expect(page.getByText("Downstream action failed", { exact: true })).toBeVisible();
  await expect(page.getByText("Completion window expired", { exact: true })).toBeVisible();
  await expect(page.getByText("Human completed the refund", { exact: true })).toBeVisible();
  await expect(page.getByText("Customer-owned operational evidence").first()).toBeVisible();
  await expect(page.getByText(/Evidue-computed deadline/)).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

  await page.getByRole("button", { name: "View all contract rules" }).click();
  await expect(
    page.getByRole("heading", { name: "All contract rules", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Among claims that pass R1, R2, R3, R5, R6, and R7/)).toBeVisible();
  await page.getByRole("button", { name: "Close contract rules" }).click();

  const packageDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download dispute package" }).click();
  await expect((await packageDownload).suggestedFilename()).toBe(
    "evidue-dispute-package.json",
  );
  await expect(
    page.getByText("Dispute package ready: 1,680 disputed outcomes · $2,520.00."),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Prepare vendor dispute" })).toBeVisible();
  await expect(page.getByText("Ready to dispute ✓")).toBeVisible();

  const csvDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: "Disputed-lines CSV" }).click();
  await expect((await csvDownload).suggestedFilename()).toBe("disputed-lines.csv");
});


test("production-shaped data collection is inspectable before reconciliation", async ({ page }) => {
  await page.request.post("/api/demo/reset?scenario_id=headline");
  await page.goto("/demo/data-sources");

  await expect(page.getByRole("heading", { name: "How real customer data enters Evidue" })).toBeVisible();
  await expect(page.getByText("50,302")).toBeVisible();
  await expect(page.getByText("100.00%")).toBeVisible();
  await expect(page.getByText("25", { exact: true })).toBeVisible();
  await expect(page.getByText("Vendor claim manifest", { exact: true })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "Payment processor" })).toBeVisible();
  await expect(page.getByText("Contract documents", { exact: true })).toBeVisible();

  await expect(page.getByRole("heading", { name: "Raw record → normalized evidence" })).toBeVisible();
  await expect(page.getByText("As received from source")).toBeVisible();
  await expect(page.getByText("Canonical Evidue record")).toBeVisible();
  await expect(page.locator(".payload-comparison pre").first()).toContainText("rejected");
  await expect(page.getByText(/Production retains every permitted raw record/)).toBeVisible();
});

test("focused synthetic data sets demonstrate distinct contract decisions", async ({
  page,
}) => {
  await page.request.post("/api/demo/reset?scenario_id=headline");
  await page.goto("/demo/lab");

  const selector = page.getByLabel("Synthetic data set");

  await selector.click();
  await page.getByRole("option", { name: "Contradictory evidence" }).click();
  await expect(page.getByText("$3.00")).toBeVisible();
  await expect(page.getByText("2 claimed outcomes from the vendor")).toBeVisible();
  await expect(page.getByText("Ready to reconcile")).toBeVisible();
  await page.getByRole("button", { name: "Run reconciliation" }).click();
  await expect(
    page.getByRole("heading", { name: "Needs-review outcome evidence" }),
  ).toBeVisible();
  await expect(page.getByText("No confirmed deductions")).toBeVisible();
  await expect(page.locator(".fact-value.disputed")).toHaveText("$0.00");
  await expect(page.locator(".fact-value.review")).toHaveText("$1.50");
  await expect(page.getByText("CASE-REVIEW-001")).toBeVisible();

  await selector.click();
  await page.getByRole("option", { name: "Failed action, valid follow-up" }).click();
  await expect(page.getByText("2 claimed outcomes from the vendor")).toBeVisible();
  await page.getByRole("button", { name: "Run reconciliation" }).click();
  await expect(page.getByText("1 of 2 outcomes payable")).toBeVisible();
  await expect(page.getByText("1 matching outcomes")).toBeVisible();
  await expect(page.getByText("CASE-RECOVERY-001")).toBeVisible();
  await expect(
    page.getByRole("button", { name: /R3 Failed downstream actions/ }),
  ).toBeVisible();

  await selector.click();
  await page.getByRole("option", { name: "Duplicate attribution window" }).click();
  await expect(page.getByText("$4.50")).toBeVisible();
  await expect(page.getByText("3 claimed outcomes from the vendor")).toBeVisible();
  await page.getByRole("button", { name: "Run reconciliation" }).click();
  await expect(page.getByText("1 of 3 outcomes payable")).toBeVisible();
  await expect(page.getByText("2 matching outcomes")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Review CASE-DUP-002 evidence" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Duplicate charges.*2.*\$3.00/ }),
  ).toBeVisible();
});

test("two-sided product story connects vendor preflight to independent verification", async ({ page }) => {
  await page.request.post("/api/demo/reset?scenario_id=headline");
  await page.goto("/demo");

  await expect(page.getByRole("heading", { name: "Prove before invoicing. Verify before payment." })).toBeVisible();
  await expect(page.getByText("Evidue Prove")).toBeVisible();
  await expect(page.getByRole("main").getByText("Outcome Ledger", { exact: true })).toBeVisible();
  await expect(page.getByText("Evidue Verify")).toBeVisible();

  await page.getByRole("link", { name: "Vendor Preflight" }).click();
  await expect(page).toHaveURL(/\/demo\/vendor-preflight$/);
  await expect(page.getByRole("heading", { name: "Send an invoice you can defend" })).toBeVisible();
  await page.getByRole("button", { name: "Run invoice preflight" }).click();
  await expect(page.getByText("$12,480.00")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("$2,520.00")).toBeVisible();
  await expect(page.getByText("Prove prepares. Verify decides.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Likely non-billable" })).toBeVisible();

  await page.getByRole("link", { name: "Outcome Ledger" }).click();
  await expect(page).toHaveURL(/\/demo\/outcome-ledger$/);
  await expect(page.getByRole("heading", { name: "A financial record for every agent outcome" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "OUT-004821" })).toBeVisible();
  await expect(page.getByText("A receipt supports a claim; it never self-declares the charge payable.")).toBeVisible();

  await page.getByRole("link", { name: "Customer Verify" }).click();
  await expect(page).toHaveURL(/\/demo\/invoices\/current$/);
  await expect(page.locator(".payable-amount")).toHaveText("$12,480.00");
});
