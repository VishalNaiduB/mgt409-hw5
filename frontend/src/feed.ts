import { delegateTarget } from "./agents";
import type { AgentName, AuditEvent } from "./types";

export type FeedItem =
  | { kind: "handoff"; key: string; from: AgentName; to: AgentName | null; task: string; refused: boolean; note: string; event: AuditEvent }
  | { kind: "tool"; key: string; agent: AgentName; tool: string; args: Record<string, unknown>; result: string | null; event: AuditEvent }
  | { kind: "report"; key: string; agent: AgentName; text: string; event: AuditEvent };

/** Events of the most recent run in the list (the trail holds every run, oldest first). */
export function latestRun(events: AuditEvent[]): { runId: string | null; events: AuditEvent[]; runCount: number } {
  const runIds = [...new Set(events.map((e) => e.run_id))];
  const runId = runIds.at(-1) ?? null;
  return { runId, events: events.filter((e) => e.run_id === runId), runCount: runIds.length };
}

/** Turn raw audit steps into feed items, pairing each tool call with its result. */
export function buildFeed(events: AuditEvent[]): FeedItem[] {
  const items: FeedItem[] = [];
  const waiting = new Map<string, Extract<FeedItem, { kind: "tool" }>[]>();
  events.forEach((event, i) => {
    const key = `${event.run_id}-${i}`;
    if (event.step_type === "delegation") {
      const refused = event.result.startsWith("Handoff refused");
      items.push({
        kind: "handoff",
        key,
        from: event.agent,
        to: (event.arguments.to_agent as AgentName | undefined) ?? delegateTarget(event.tool),
        task: String(event.arguments.task ?? ""),
        refused,
        note: event.result,
        event,
      });
    } else if (event.step_type === "tool_call" && event.tool) {
      const item = { kind: "tool" as const, key, agent: event.agent, tool: event.tool, args: event.arguments, result: null, event };
      const pairKey = `${event.agent}|${event.tool}|${JSON.stringify(event.arguments)}`;
      waiting.set(pairKey, [...(waiting.get(pairKey) ?? []), item]);
      items.push(item);
    } else if (event.step_type === "tool_result" && event.tool) {
      const pairKey = `${event.agent}|${event.tool}|${JSON.stringify(event.arguments)}`;
      const queue = waiting.get(pairKey);
      const call = queue?.shift();
      if (call) call.result = event.result;
      else items.push({ kind: "tool", key, agent: event.agent, tool: event.tool, args: event.arguments, result: event.result, event });
    } else if (event.step_type === "final_answer") {
      items.push({ kind: "report", key, agent: event.agent, text: event.result, event });
    }
  });
  return items;
}

/** The chain of stations the run actually visited, in handoff order. */
export function handoffChain(events: AuditEvent[]): AgentName[] {
  const chain: AgentName[] = events.length ? ["Boss"] : [];
  for (const e of events) {
    if (e.step_type !== "delegation" || e.result.startsWith("Handoff refused")) continue;
    const to = (e.arguments.to_agent as AgentName | undefined) ?? delegateTarget(e.tool);
    if (to) chain.push(to);
  }
  return chain;
}
