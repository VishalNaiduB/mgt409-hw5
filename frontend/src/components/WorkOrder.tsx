import { useEffect, useState } from "react";
import { StationBadge } from "../agents";
import { handoffChain } from "../feed";
import type { AuditEvent, RunState, Ticket } from "../types";
import { StatusStamp, ticketLine } from "./TicketRail";

const REQUEST_LIMIT = 35;
const DEPTH_CAP = 3;

interface WorkOrderProps {
  ticket: Ticket;
  run: RunState;
  runEvents: AuditEvent[];
  onStart: () => Promise<void>;
}

function useElapsed(startedAt: string | null, active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [active]);
  if (!startedAt) return 0;
  return Math.max(0, Math.round(((active ? now : Date.now()) - new Date(startedAt).getTime()) / 1000));
}

export function WorkOrder({ ticket, run, runEvents, onStart }: WorkOrderProps) {
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const thisRun = run.ticket_id === ticket.id;
  const running = run.status === "running";
  const runningHere = running && thisRun;
  const elapsed = useElapsed(thisRun ? run.started_at : null, runningHere);

  const chain = handoffChain(runEvents);
  const active = runningHere ? runEvents.at(-1)?.agent : undefined;
  const requests = runEvents.reduce((max, e) => Math.max(max, e.requests_used), 0);
  const depth = runEvents.reduce((max, e) => Math.max(max, e.depth), 0);

  const blocked =
    running && !thisRun
      ? `Ticket ${run.ticket_id} is on the floor; one run at a time.`
      : ticket.status === "resolved"
        ? "This job is resolved. Reset the database to run it again."
        : ticket.status === "awaiting_approval"
          ? "A payment is staged for this job. Approve it below, or reset."
          : null;

  async function start() {
    setStarting(true);
    setError(null);
    try {
      await onStart();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the run.");
    } finally {
      setStarting(false);
    }
  }

  return (
    <section className="card workorder" aria-labelledby="workorder-title">
      <div className="card__head">
        <h2 id="workorder-title" className="card__title">
          Work order · Job {ticket.id}
        </h2>
        <StatusStamp status={ticket.status} />
      </div>

      <dl className="workorder__facts">
        <div>
          <dt>Requester</dt>
          <dd>{ticket.requester}</dd>
        </div>
        <div>
          <dt>Job</dt>
          <dd className="mono">{ticketLine(ticket)}</dd>
        </div>
        {ticket.notes && (
          <div className="workorder__notes">
            <dt>Notes</dt>
            <dd>{ticket.notes}</dd>
          </div>
        )}
      </dl>

      <button
        type="button"
        className="btn btn--ink btn--wide"
        onClick={start}
        disabled={starting || running || blocked !== null}
      >
        {runningHere ? "Agents on the floor…" : starting ? "Sending to the floor…" : `Start agents on Job ${ticket.id}`}
      </button>
      {blocked && !runningHere && <p className="muted small">{blocked}</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      {thisRun && run.status !== "idle" && (
        <div className={`progress progress--${run.status}`} aria-live="polite">
          <div className="progress__line">
            <span className="progress__state">
              {runningHere ? (
                <>
                  <span className="pulse" aria-hidden="true" /> Running · {elapsed}s
                </>
              ) : run.status === "failed" ? (
                "Run failed"
              ) : (
                `Run finished · ticket ${ticket.status.replace(/_/g, " ")}`
              )}
            </span>
            <span className="mono small">
              Handoff {depth}/{DEPTH_CAP}
            </span>
          </div>

          <div className="meter" role="img" aria-label={`${requests} of ${REQUEST_LIMIT} model requests used`}>
            <span className="meter__fill" style={{ width: `${Math.min(100, (requests / REQUEST_LIMIT) * 100)}%` }} />
          </div>
          <p className="mono small">
            {requests} of {REQUEST_LIMIT} requests used
          </p>

          {chain.length > 0 && (
            <ol className="chain" aria-label="Handoff chain">
              {chain.map((agent, i) => (
                <li key={`${agent}-${i}`} className={agent === active ? "chain__step chain__step--active" : "chain__step"}>
                  <StationBadge agent={agent} compact />
                </li>
              ))}
            </ol>
          )}

          {run.status === "failed" && run.error && <p className="form-error">{run.error}</p>}
        </div>
      )}
    </section>
  );
}
