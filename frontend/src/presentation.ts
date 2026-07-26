export const disclosure = "Operationally realistic data generated deterministically. No real customer or vendor data is shown.";

export function formatUsd(amount: string): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(amount));
}
