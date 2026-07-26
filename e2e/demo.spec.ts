import { expect, test } from "@playwright/test";

test("complete Evidue golden demo path", async ({ page }) => {
  await page.request.post("/api/demo/reset");
  await page.goto("/demo");

  await expect(page.getByText("Synthetic demonstration data.")).toBeVisible();
  await expect(
    page.getByText(
      "Operationally realistic data generated deterministically. No real customer or vendor data is shown.",
    ),
  ).toBeVisible();
  await expect(page.getByText("$15,000.00")).toBeVisible();
  await expect(page.getByText("$12,480.00")).not.toBeVisible();
  await expect(page.getByText("Seven deterministic billing rules")).toBeVisible();
  await expect(page.getByText("Available evidence sources")).toBeVisible();

  await page.getByRole("button", { name: "Run reconciliation" }).click();
  await expect(page.getByText("Evaluating persisted claims and evidence")).toBeVisible();
  await expect(page.getByText("$12,480.00")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("$2,520.00")).toBeVisible();
  await expect(page.getByText("8,320")).toBeVisible();
  await expect(page.getByText("1,680").first()).toBeVisible();

  await page.getByRole("combobox", { name: "Status" }).click();
  await page.getByRole("option", { name: "Disputed" }).click();
  await expect(page.getByText("1,680 matching outcomes")).toBeVisible();

  await page.getByLabel("Outcome ID").fill("OUT-004821");
  await expect(page.getByRole("button", { name: "OUT-004821" })).toBeVisible();
  await page.getByRole("button", { name: "OUT-004821" }).click();
  await expect(page.getByRole("heading", { name: "OUT-004821", exact: true })).toBeVisible();
  await expect(page.getByText("downstream failed")).toBeVisible();
  await expect(page.getByText("completion window expired")).toBeVisible();
  await expect(page.getByText("human refund completed")).toBeVisible();
  await expect(page.getByRole("dialog").getByText("$0.00")).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

  const csvDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: "Dispute CSV" }).click();
  await expect((await csvDownload).suggestedFilename()).toBe("disputed-lines.csv");

  const evidenceResponse = page.waitForResponse(
    (response) => response.url().endsWith("/exports/evidence.json") && response.ok(),
  );
  await page.getByRole("link", { name: "Evidence JSON" }).click();
  await evidenceResponse;
  await page.goBack();

  const summaryResponse = page.waitForResponse(
    (response) => response.url().endsWith("/exports/summary.json") && response.ok(),
  );
  await page.getByRole("link", { name: "Summary JSON" }).click();
  await summaryResponse;
});
