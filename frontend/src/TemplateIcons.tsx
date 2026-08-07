import { SVGProps } from "react";

export type TemplateIconName =
  | "dashboard" | "verify" | "preflight" | "receipt" | "shield" | "contract"
  | "ledger" | "data" | "lab" | "wallet" | "menu" | "sun" | "moon"
  | "help" | "home" | "arrow" | "check" | "warning";

const paths: Record<TemplateIconName, JSX.Element> = {
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="4" rx="1"/><rect x="14" y="11" width="7" height="10" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></>,
  verify: <><path d="M9 11l2 2 4-4"/><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></>,
  preflight: <><path d="M4 19V9"/><path d="M10 19V5"/><path d="M16 19v-7"/><path d="M22 19V3"/><path d="M2 19h20"/></>,
  receipt: <><path d="M6 2h12v20l-3-2-3 2-3-2-3 2V2z"/><path d="M9 7h6M9 11h6M9 15h4"/></>,
  shield: <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></>,
  contract: <><path d="M6 2h9l3 3v17H6z"/><path d="M14 2v4h4M9 10h6M9 14h6M9 18h4"/></>,
  ledger: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></>,
  data: <><path d="M4 4h16v16H4z"/><path d="M4 9h16M9 4v16"/></>,
  lab: <><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.7 3h10.6A2 2 0 0 0 19 18l-5-9V3"/><path d="M8 15h8"/></>,
  wallet: <><path d="M3 6h15a3 3 0 0 1 3 3v9H5a2 2 0 0 1-2-2V6z"/><path d="M3 6l12-3v3M16 11h5v4h-5a2 2 0 0 1 0-4z"/></>,
  menu: <><path d="M4 6h16M4 12h16M4 18h16"/></>,
  sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></>,
  moon: <path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/>,
  help: <><circle cx="12" cy="12" r="10"/><path d="M9.5 9a2.5 2.5 0 1 1 4.3 1.7c-.9.8-1.8 1.3-1.8 2.8M12 18h.01"/></>,
  home: <><path d="M3 11l9-8 9 8"/><path d="M5 10v11h14V10M9 21v-7h6v7"/></>,
  arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
  check: <><circle cx="12" cy="12" r="10"/><path d="M8 12l3 3 5-6"/></>,
  warning: <><path d="M12 3l10 18H2L12 3z"/><path d="M12 9v4M12 17h.01"/></>,
};

export function TemplateIcon({ name, size = 24, ...props }: SVGProps<SVGSVGElement> & { name: TemplateIconName; size?: number }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...props}>{paths[name]}</svg>;
}
