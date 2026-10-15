import type { ReactNode } from "react";
import type { AgentName } from "./types";

export interface Station {
  name: AgentName;
  station: string;
  /** CSS custom property suffix: --agent-boss, --agent-inventory, ... */
  key: string;
  icon: ReactNode;
}

const stroke = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" } as const;

export const STATIONS: Record<AgentName, Station> = {
  Boss: {
    name: "Boss",
    station: "Front Desk",
    key: "boss",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path {...stroke} d="M5 17h14M7 17a5 5 0 0 1 10 0M12 9v3M10 7h4" />
        <circle cx="12" cy="6" r="1" fill="currentColor" />
      </svg>
    ),
  },
  Inventory: {
    name: "Inventory",
    station: "Stock Room",
    key: "inventory",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path {...stroke} d="M4 8l8-4 8 4v8l-8 4-8-4zM4 8l8 4 8-4M12 12v8" />
      </svg>
    ),
  },
  Accounting: {
    name: "Accounting",
    station: "Ledger Desk",
    key: "accounting",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path {...stroke} d="M6 4h11a1 1 0 0 1 1 1v15H7a1 1 0 0 1-1-1zM9 8h6M9 11h6M9 14h4" />
      </svg>
    ),
  },
  Facilities: {
    name: "Facilities",
    station: "Building & Lease",
    key: "facilities",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path {...stroke} d="M4 20V9l8-5 8 5v11M9 20v-6h6v6M3 20h18" />
      </svg>
    ),
  },
  "Customer Service": {
    name: "Customer Service",
    station: "Pickup Counter",
    key: "customer-service",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path {...stroke} d="M5 6h14a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1h-8l-4 3v-3H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1zM8 10h8M8 13h5" />
      </svg>
    ),
  },
};

export const STATION_ORDER: AgentName[] = ["Boss", "Inventory", "Accounting", "Facilities", "Customer Service"];

/** Map a delegate tool name (delegate_to_customer_service) back to the agent. */
export function delegateTarget(tool: string | null): AgentName | null {
  if (!tool?.startsWith("delegate_to_")) return null;
  const slug = tool.slice("delegate_to_".length);
  return STATION_ORDER.find((name) => STATIONS[name].key.replace(/-/g, "_") === slug) ?? null;
}

export function StationBadge({ agent, compact = false }: { agent: AgentName; compact?: boolean }) {
  const s = STATIONS[agent];
  return (
    <span className={`badge badge--${s.key}${compact ? " badge--compact" : ""}`}>
      <span className="badge__icon">{s.icon}</span>
      <span className="badge__name">{s.name}</span>
      {!compact && <span className="badge__station">{s.station}</span>}
    </span>
  );
}
