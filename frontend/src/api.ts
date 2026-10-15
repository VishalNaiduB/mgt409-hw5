import type { CashResponse, EventsResponse, TicketsResponse } from "./types";

export const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

function detailMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => (d as { msg?: string }).msg ?? String(d)).join("; ");
  if (detail && typeof detail === "object" && "error" in detail) return String((detail as { error: unknown }).error);
  return "Request failed.";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(`Can't reach the backend at ${API_BASE}.`, 0);
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(detailMessage((body as { detail?: unknown }).detail), response.status);
  return body as T;
}

export const api = {
  tickets: () => request<TicketsResponse>("/tickets"),
  cash: () => request<CashResponse>("/cash"),
  events: (ticketId: number) => request<EventsResponse>(`/events?ticket_id=${ticketId}&limit=1000`),
  run: (ticketId: number) => request<{ run: unknown }>(`/tickets/${ticketId}/run`, { method: "POST" }),
  approve: (paymentId: number, approvedBy: string) =>
    request<unknown>(`/payments/${paymentId}/approve`, {
      method: "POST",
      body: JSON.stringify({ approved_by: approvedBy }),
    }),
  reset: () => request<unknown>("/reset", { method: "POST" }),
};
