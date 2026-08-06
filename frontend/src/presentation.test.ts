import { describe, expect, it } from "vitest";
import { disclosure, formatPercent, formatUsd } from "./presentation";

describe("demo presentation", () => {
  it("formats backend decimal-string money without financial arithmetic", () => {
    expect(formatUsd("12480.00")).toBe("$12,480.00");
  });
  it("contains the mandatory synthetic disclosure", () => {
    expect(disclosure).toContain("No real customer or vendor data is shown");
  });
  it("derives finding percentages from API decimal strings", () => {
    expect(formatPercent("1080.00", "15000.00")).toBe("7.2%");
  });
});
