import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, api } from "./api";
import { STATION_ORDER, StationBadge } from "./agents";
import { DispatchFloor } from "./components/DispatchFloor";
import { LedgerStrip } from "./components/LedgerStrip";
import { PaymentDesk } from "./components/PaymentDesk";
import { StationReports } from "./components/StationReports";
import { TicketRail } from "./components/TicketRail";
import { WorkOrder } from "./components/WorkOrder";
import { latestRun } from "./feed";
import type { AuditEvent, CashResponse, TicketsResponse } from "./types";

const POLL_RUNNING_MS = 1000;
const POLL_IDLE_MS = 5000;

export default function App() {
  const [board, setBoard] = useState<TicketsResponse | null>(null);
  const [cash, setCash] = useState<CashResponse | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [offline, setOffline] = useState<string | null>(null);
  const selectedRef = useRef<number | null>(null);
  selectedRef.current = selectedId;

  const running = board?.run.status === "running";

  const refreshBoard = useCallback(async () => {
    try {
      const [b, c] = await Promise.all([api.tickets(), api.cash()]);
      setBoard(b);
      setCash(c);
      setOffline(null);
      if (selectedRef.current === null && b.tickets.length > 0) {
        setSelectedId(b.run.status === "running" && b.run.ticket_id ? b.run.ticket_id : b.tickets[0].id);
      }
    } catch (e) {
      setOffline(e instanceof Error ? e.message : "Backend unavailable.");
    }
  }, []);

  const refreshEvents = useCallback(async (ticketId: number) => {
    try {
      const { events } = await api.events(ticketId);
      if (selectedRef.current === ticketId) setEvents(events);
    } catch {
      /* the board poll reports connection problems */
    }
  }, []);

  // Poll quickly while the agents are on the floor, slowly otherwise.
  useEffect(() => {
    void refreshBoard();
    const id = window.setInterval(() => {
      void refreshBoard();
      if (selectedRef.current !== null) void refreshEvents(selectedRef.current);
    }, running ? POLL_RUNNING_MS : POLL_IDLE_MS);
    return () => window.clearInterval(id);
  }, [running, refreshBoard, refreshEvents]);

  // New selection, or a run just ended: fetch that ticket's trail right away.
  useEffect(() => {
    if (selectedId === null) return;
    setEvents((prev) => (prev[0]?.ticket_id === selectedId ? prev : []));
    void refreshEvents(selectedId);
  }, [selectedId, board?.run.status, refreshEvents]);

  async function startRun(ticketId: number) {
    await api.run(ticketId);
    await refreshBoard();
  }

  async function approve(paymentId: number, approvedBy: string) {
    await api.approve(paymentId, approvedBy);
    await refreshBoard();
    if (selectedId !== null) await refreshEvents(selectedId);
  }

  async function reset() {
    await api.reset();
    await refreshBoard();
  }

  const ticket = board?.tickets.find((t) => t.id === selectedId) ?? null;
  const run = latestRun(events);
  const runActiveHere = running && board?.run.ticket_id === selectedId;

  return (
    <div className="shop">
      <LedgerStrip shopDate={board?.date_today ?? cash?.date_today ?? null} cash={cash} running={running} onReset={reset} />

      <main className="floorplan">
        {offline && (
          <div className="banner" role="alert">
            <strong>{offline}</strong> Start it from <code>backend/</code> with{" "}
            <code>../.venv/bin/uvicorn main:app --reload --port 8000</code>. Retrying every few seconds ({API_BASE}).
          </div>
        )}

        <div className="floorplan__intro">
          <h1 className="section-title">Work orders on the rail</h1>
          <ul className="legend" aria-label="Stations">
            {STATION_ORDER.map((agent) => (
              <li key={agent}>
                <StationBadge agent={agent} />
              </li>
            ))}
          </ul>
        </div>

        {board ? (
          <TicketRail
            tickets={board.tickets}
            selectedId={selectedId}
            runningId={running ? board.run.ticket_id : null}
            onSelect={setSelectedId}
          />
        ) : (
          !offline && <p className="muted">Loading the rail…</p>
        )}

        {board && ticket && (
          <div className="workspace">
            <DispatchFloor ticketId={ticket.id} events={run.events} runCount={run.runCount} running={runActiveHere} />
            <aside className="workspace__side">
              <WorkOrder ticket={ticket} run={board.run} runEvents={run.events} onStart={() => startRun(ticket.id)} />
              <PaymentDesk payments={board.pending_payments} tickets={board.tickets} onApprove={approve} />
            </aside>
          </div>
        )}

        {board && ticket && <StationReports events={run.events} running={runActiveHere} />}
      </main>

      <footer className="colophon">
        Every figure comes from the shop database through the backend's MCP tools. Payments move only when a person
        approves them.
      </footer>
    </div>
  );
}
