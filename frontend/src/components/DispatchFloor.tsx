import { useEffect, useRef } from "react";
import { STATIONS, StationBadge } from "../agents";
import { buildFeed, type FeedItem } from "../feed";
import { formatArgs, formatClock } from "../format";
import type { AuditEvent } from "../types";

interface DispatchFloorProps {
  ticketId: number;
  events: AuditEvent[];
  runCount: number;
  running: boolean;
}

function Row({ item }: { item: FeedItem }) {
  if (item.kind === "handoff") {
    return (
      <li className={`feed__row feed__row--${STATIONS[item.from].key} feed__handoff${item.refused ? " feed__handoff--refused" : ""}`}>
        <div className="feed__meta">
          <StationBadge agent={item.from} />
          <span className="feed__verb">{item.refused ? "tried to hand off to" : "hands off to"}</span>
          {item.to && <StationBadge agent={item.to} />}
          <time className="feed__time mono">{formatClock(item.event.timestamp)}</time>
        </div>
        <p className="feed__slip">{item.task}</p>
        {item.refused && <p className="feed__refusal">{item.note}</p>}
      </li>
    );
  }
  if (item.kind === "tool") {
    return (
      <li className={`feed__row feed__row--${STATIONS[item.agent].key}`}>
        <div className="feed__meta">
          <StationBadge agent={item.agent} />
          <span className="feed__verb">calls</span>
          <code className="feed__tool">
            {item.tool}({formatArgs(item.args)})
          </code>
          <time className="feed__time mono">{formatClock(item.event.timestamp)}</time>
        </div>
        <pre className={`feed__result${item.result === null ? " feed__result--pending" : ""}`}>
          {item.result ?? "waiting for the tool…"}
        </pre>
      </li>
    );
  }
  return (
    <li className={`feed__row feed__row--${STATIONS[item.agent].key} feed__report`}>
      <div className="feed__meta">
        <StationBadge agent={item.agent} />
        <span className="feed__verb">reports back</span>
        <time className="feed__time mono">{formatClock(item.event.timestamp)}</time>
      </div>
      <p className="feed__text">{item.text}</p>
    </li>
  );
}

export function DispatchFloor({ ticketId, events, runCount, running }: DispatchFloorProps) {
  const items = buildFeed(events);
  const listRef = useRef<HTMLOListElement>(null);

  // Follow new steps inside the feed while a run is live, unless the reader has scrolled up.
  // Only the feed scrolls; the page itself stays where the reader left it.
  useEffect(() => {
    const list = listRef.current;
    if (!running || !list) return;
    const nearBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 240;
    if (nearBottom) list.scrollTo({ top: list.scrollHeight, behavior: "smooth" });
  }, [items.length, running]);

  return (
    <section className="card floor" aria-labelledby="floor-title">
      <div className="card__head">
        <h2 id="floor-title" className="card__title">
          Dispatch floor · Job {ticketId}
        </h2>
        <span className="muted small">
          {items.length === 0 ? "no runs yet" : `${events.length} steps · latest of ${runCount} run${runCount === 1 ? "" : "s"}`}
        </span>
      </div>
      {items.length === 0 ? (
        <div className="floor__empty">
          <p>The floor is quiet.</p>
          <p className="muted small">Start the agents on this job to watch each station's messages and tool calls here, live.</p>
        </div>
      ) : (
        <ol className="feed" ref={listRef}>
          {items.map((item) => (
            <Row key={item.key} item={item} />
          ))}
          {running && (
            <li className="feed__row feed__waiting">
              <span className="pulse" aria-hidden="true" /> Working…
            </li>
          )}
        </ol>
      )}
    </section>
  );
}
