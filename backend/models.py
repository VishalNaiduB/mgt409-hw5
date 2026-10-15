"""Pydantic models shared by the backend and the agents.

The shapes mirror what the campus-customs MCP tools return. No model here reads
the database; all values arrive through MCP tool calls.
"""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field

MAX_DELEGATION_DEPTH = 3

AgentName = Literal["Boss", "Inventory", "Accounting", "Facilities", "Customer Service"]
TicketType = Literal["customer_order", "rent_notice", "price_override"]
TicketStatus = Literal["open", "in_progress", "escalated", "awaiting_approval", "resolved"]
PaymentKind = Literal["invoice", "rent"]


class Ticket(BaseModel):
    """One row of the `tickets` table."""

    id: int
    type: TicketType
    requester: str
    subject: str
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    status: TicketStatus
    notes: str | None = None
    created_at: str


class AgentHandoff(BaseModel):
    """A delegation from one agent to another, capped at MAX_DELEGATION_DEPTH."""

    from_agent: AgentName
    to_agent: AgentName
    ticket_id: int
    task: str = Field(description="What the receiving agent is asked to find out or do.")
    depth: int = Field(ge=1, le=MAX_DELEGATION_DEPTH, description="1 for the Boss's first handoff.")


class AgentResponse(BaseModel):
    """What an agent reports back about a ticket."""

    agent: AgentName
    ticket_id: int
    summary: str = Field(description="Plain-language answer, using only facts returned by MCP tools.")
    facts: dict[str, Any] = Field(default_factory=dict, description="Key numbers from tool output, e.g. qty_on_hand.")
    tools_used: list[str] = Field(default_factory=list)
    recommended_action: str | None = None
    needs_human_approval: bool = False
    staged_payment_id: int | None = None
    handoffs: list[AgentHandoff] = Field(default_factory=list)


class StagedPayment(BaseModel):
    """One row of the `payments` table.

    A staged payment has empty-string `paid_at` and `approved_by` (the columns are
    NOT NULL); a human approval fills both in.
    """

    id: int
    kind: PaymentKind
    ref_id: int | None = Field(description="Invoice id for kind 'invoice', lease id for kind 'rent'.")
    amount: float
    account: str
    paid_at: str = ""
    approved_by: str = ""

    @computed_field
    @property
    def status(self) -> Literal["pending", "completed"]:
        return "pending" if self.paid_at == "" else "completed"


AuditStep = Literal["delegation", "tool_call", "tool_result", "final_answer"]


class AuditEntry(BaseModel):
    """One agent-loop step, as appended to output/audit_trail.json."""

    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ticket_id: int
    agent: AgentName
    step_type: AuditStep
    tool: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: str = Field(default="", description="The full text for a final answer; a short, truncated summary otherwise.")
    depth: int = Field(ge=0, le=MAX_DELEGATION_DEPTH)
    requests_used: int = Field(ge=0, description="Model requests used so far in this run, across all agents.")
