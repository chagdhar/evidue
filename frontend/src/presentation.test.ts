import { describe, expect, it } from "vitest";
import { disclosure, formatUsd } from "./presentation";

describe("demo presentation", () => {
  it("formats backend decimal-string money without financial arithmetic", () => {
    expect(formatUsd("12480.00")).toBe("$12,480.00");
  });
  it("contains the mandatory synthetic disclosure", () => {
    expect(disclosure).toContain("No real customer or vendor data is shown");
  });
});
