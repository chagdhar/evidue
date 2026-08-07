import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearPilotToken,
  loadPilotToken,
  pilotApi,
  savePilotToken,
} from "./pilotApi";

describe("pilot API client", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("stores the pilot token in session storage only", () => {
    savePilotToken("  token-that-is-long-enough-for-pilot  ");
    expect(loadPilotToken()).toBe("token-that-is-long-enough-for-pilot");
    expect(localStorage.getItem("evidue.pilot.token")).toBeNull();
    clearPilotToken();
    expect(loadPilotToken()).toBe("");
  });

  it("sends the token in the Authorization header and never the URL", async () => {
    savePilotToken("token-that-is-long-enough-for-pilot");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ initialized: true, uploads: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await pilotApi.status();

    const [url, options] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("/api/pilot/status");
    expect(String(url)).not.toContain("token-that-is-long-enough-for-pilot");
    expect(new Headers(options?.headers).get("Authorization")).toBe(
      "Bearer token-that-is-long-enough-for-pilot",
    );
  });

  it("surfaces backend detail messages", async () => {
    savePilotToken("token-that-is-long-enough-for-pilot");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Compilation cannot be approved" }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(pilotApi.approve("PCOMP-1")).rejects.toThrow(
      "Compilation cannot be approved",
    );
  });
});
