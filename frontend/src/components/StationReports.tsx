import { STATIONS, StationBadge } from "../agents";
import { handoffChain } from "../feed";
import type { AgentName, AuditEvent } from "../types";

interface Report {
  agent: AgentName;
  tools: string[];
  handoffs: string[];
  answer: string | null;
}

function reports(events: AuditEvent[]): Report[] {
  const order = [...new Set(handoffChain(events))];
  return order.map((agent) => {
    const mine = events.filter((e) => e.agent === agent);
    return {
      agent,
      tools: [...new Set(mine.filter((e) => e.step_type === "tool_call" && e.tool).map((e) => e.tool as string))],
      handoffs: mine
        .filter((e) => e.step_type === "delegation")
        .map((e) => (e.result.startsWith("Handoff refused") ? `${e.tool} (refused at cap)` : String(e.arguments.to_agent ?? e.tool))),
      answer: mine.filter((e) => e.step_type === "final_answer").at(-1)?.result ?? null,
    };
  });
}

export function StationReports({ events, running }: { events: AuditEvent[]; running: boolean }) {
  const list = reports(events);
  return (
    <section className="reports" aria-labelledby="reports-title">
      <h2 id="reports-title" className="section-title">
        What each station did
      </h2>
      {list.length === 0 ? (
        <p className="muted small">Each agent's summary appears here when it reports back.</p>
      ) : (
        <div className="reports__grid">
          {list.map((r) => (
            <article key={r.agent} className={`report report--${STATIONS[r.agent].key}`}>
              <StationBadge agent={r.agent} />
              <dl className="report__facts">
                <div>
                  <dt>Tools</dt>
                  <dd>
                    {r.tools.length ? (
                      <ul className="report__tools">
                        {r.tools.map((tool) => (
                          <li key={tool}>
                            <code>{tool}</code>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      "none"
                    )}
                  </dd>
                </div>
                {r.handoffs.length > 0 && (
                  <div>
                    <dt>Handed to</dt>
                    <dd>{r.handoffs.join(", ")}</dd>
                  </div>
                )}
              </dl>
              <p className="report__answer">
                {r.answer ?? (running ? "Still working…" : "No report recorded.")}
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
