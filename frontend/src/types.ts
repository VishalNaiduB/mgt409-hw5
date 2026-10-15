// Shapes returned by the FastAPI backend (backend/main.py), which reads everything through MCP.

export type AgentName = "Boss" | "Inventory" | "Accounting" | "Facilities" | "Customer Service";

export type TicketStatus = "open" | "in_progress" | "escalated" | "awaiting_approval" | "resolved";

export interface Payment {
  id: number;
  kind: "invoice" | "rent";
  ref_id: number | null;
  amount: number;
  account: string;
  paid_at: string;
  approved_by: string;
  status: "pending" | "completed";
}

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  status: TicketStatus | string;
  notes: string | null;
  created_at: string;
  pending_payments: Payment[];
}

export interface RunState {
  ticket_id: number | null;
  status: "idle" | "running" | "finished" | "failed";
  started_at: string | null;
  finished_at: string | null;
  summary: string | null;
  error: string | null;
}

export interface TicketsResponse {
  date_today: string;
  tickets: Ticket[];
  pending_payments: Payment[];
  run: RunState;
}

export interface CashAccount {
  name: string;
  balance: number;
  date: string;
  pending_staged: number;
  available: number;
}

export interface CashResponse {
  date_today: string;
  account: CashAccount;
}

export type StepType = "delegation" | "tool_call" | "tool_result" | "final_answer";

export interface AuditEvent {
  run_id: string;
  timestamp: string;
  ticket_id: number;
  agent: AgentName;
  step_type: StepType;
  tool: string | null;
  arguments: Record<string, unknown>;
  result: string;
  depth: number;
  requests_used: number;
}

export interface EventsResponse {
  events: AuditEvent[];
  total: number;
}
