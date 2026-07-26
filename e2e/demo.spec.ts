import { expect, test } from "@playwright/test";

test("complete Evidue financial-decision demo path", async ({ page }) => {
  await page.request.post("/api/demo/reset");
  await page.goto("/demo");

  await expect(page.getByText("Synthetic demonstration data.")).toBeVisible();
  await expect(
    page.getByText(
      "Operationally realistic data generated deterministically. No real customer or vendor data is shown.",
    ),
  ).toBeVisible();
  await expect(page.getByText("$15,000.00")).toBeVisible();
  await expect(page.getByText("10,000 claimed outcomes from the vendor")).toBeVisible();
  await expect(page.getByText("Ready to reconcile")).toBeVisible();
  await expect(page.getByText("$12,480.00")).not.toBeVisible();
  await expect(page.getByRole("heading", { name: "Executable billing terms" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Available source systems" })).toBeVisible();

  await page.getByRole("button", { name: "Run reconciliation" }).click();
  await expect(page.getByText("Evaluating persisted claims and evidence")).toBeVisible();
  await expect(page.locator(".payable-amount")).toHaveText("$12,480.00", {
    timeout: 60_000,
  });
  await expect(page.getByText("$2,520.00").first()).toBeVisible();
  await expect(page.getByText("8,320 of 10,000 outcomes payable")).toBeVisible();
  await expect(
    page.getByText(
      "No model decides whether a charge is payable. Every amount is reproduced from contract rules and traceable source evidence.",
    ),
  ).toBeVisible();
  await expect(page.getByText("1,680 matching outcomes")).toBeVisible();

  await page.getByRole("button", { name: /Failed downstream actions/ }).click();
  await expect(page.getByText("300 matching outcomes · R3 selected")).toBeVisible();

  await page.getByRole("button", { name: "Advanced filters" }).click();
  await page.getByLabel("Outcome ID").fill("OUT-004821");
  await expect(page.getByText("Demo example")).toBeVisible();
  await page.getByRole("button", { name: "Review OUT-004821 evidence" }).click();

  await expect(page.getByRole("heading", { name: "OUT-004821", exact: true })).toBeVisible();
  await expect(page.getByText("Vendor claim")).toBeVisible();
  await expect(page.getByText("Contract obligation")).toBeVisible();
  await expect(page.getByText("Evidue determination")).toBeVisible();
  await expect(page.getByText("Downstream action failed", { exact: true })).toBeVisible();
  await expect(page.getByText("Completion window expired", { exact: true })).toBeVisible();
  await expect(page.getByText("Human completed the refund", { exact: true })).toBeVisible();
  await expect(page.getByText("Imported operational evidence").first()).toBeVisible();
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

  const csvDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: "Disputed-lines CSV" }).click();
  await expect((await csvDownload).suggestedFilename()).toBe("disputed-lines.csv");
});
