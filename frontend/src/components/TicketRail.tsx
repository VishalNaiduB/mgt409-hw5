import { formatMoney, humanize } from "../format";
import type { Ticket } from "../types";

const TYPE_LABEL: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Price override",
};

export function ticketLine(ticket: Ticket): string {
  if (ticket.type === "rent_notice") return `Lease ${ticket.lease_id ?? "—"} · ${ticket.subject}`;
  const item = `${ticket.qty ?? "?"} × ${ticket.sku ?? "?"} · size ${ticket.size ?? "?"}`;
  return ticket.type === "price_override" ? `${item} · bulk discount` : item;
}

export function StatusStamp({ status }: { status: string }) {
  return <span className={`stamp stamp--${status}`}>{humanize(status)}</span>;
}

interface TicketRailProps {
  tickets: Ticket[];
  selectedId: number | null;
  runningId: number | null;
  onSelect: (id: number) => void;
}

export function TicketRail({ tickets, selectedId, runningId, onSelect }: TicketRailProps) {
  return (
    <section className="rail" aria-label="Open work orders">
      <div className="rail__bar" aria-hidden="true" />
      <ul className="rail__tags">
        {tickets.map((ticket, i) => {
          const staged = ticket.pending_payments.reduce((sum, p) => sum + p.amount, 0);
          return (
            <li key={ticket.id} className={`rail__slot rail__slot--${i % 3}`}>
              <button
                type="button"
                className={`tag${selectedId === ticket.id ? " tag--selected" : ""}`}
                aria-pressed={selectedId === ticket.id}
                onClick={() => onSelect(ticket.id)}
              >
                <span className="tag__hole" aria-hidden="true" />
                <span className="tag__kind">{TYPE_LABEL[ticket.type] ?? humanize(ticket.type)}</span>
                <span className="tag__no">
                  <span className="tag__no-label">Job No.</span> {ticket.id}
                </span>
                <span className="tag__who">{ticket.requester}</span>
                <span className="tag__what mono">{ticketLine(ticket)}</span>
                <span className="tag__foot">
                  <StatusStamp status={ticket.status} />
                  {runningId === ticket.id && <span className="tag__live">On the floor</span>}
                  {staged > 0 && <span className="tag__staged mono">{formatMoney(staged)} staged</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
