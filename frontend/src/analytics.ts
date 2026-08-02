type EventProperties = Record<string, string | number | boolean | undefined>;
type AnalyticsEnvironment = { VITE_POSTHOG_KEY?: string; VITE_POSTHOG_HOST?: string };

const environment = (import.meta as ImportMeta & { env: AnalyticsEnvironment }).env;
const key = environment.VITE_POSTHOG_KEY?.trim();
const host = environment.VITE_POSTHOG_HOST?.replace(/\/$/, "").trim();

type AttributionSource = "hacker_news" | "yc_demo" | "direct_outreach" | "unknown";

function source(): AttributionSource {
  const storageKey = "evidue-attribution-source";
  const current = new URLSearchParams(window.location.search).get("source");
  const allowed = new Set(["hacker_news", "yc_demo", "direct_outreach"]);
  if (current && allowed.has(current)) sessionStorage.setItem(storageKey, current);
  const stored = sessionStorage.getItem(storageKey);
  return stored && allowed.has(stored) ? (stored as Exclude<AttributionSource, "unknown">) : "unknown";
}

/** Adds only Evidue's fixed, non-sensitive attribution values to a Tally URL. */
export function betaFormUrl(configuredUrl: string): string {
  const url = new URL(configuredUrl);
  url.searchParams.set("source", source());
  url.searchParams.set("campaign", "railway_beta");
  url.searchParams.set("demo_version", "hn_demo");
  return url.toString();
}

function anonymousSessionId(): string {
  const storageKey = "evidue-anonymous-session-id";
  const existing = sessionStorage.getItem(storageKey);
  if (existing) return existing;
  const identifier = crypto.randomUUID();
  sessionStorage.setItem(storageKey, identifier);
  return identifier;
}

/** Optional, deliberately minimal product analytics. No replay, autocapture, or identify calls. */
export function track(event: string, properties: EventProperties = {}): void {
  if (!key || !host) return;
  void fetch(`${host}/capture/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    keepalive: true,
    body: JSON.stringify({
      api_key: key,
      event,
      properties: { distinct_id: anonymousSessionId(), source: source(), ...properties },
    }),
  }).catch(() => undefined);
}
