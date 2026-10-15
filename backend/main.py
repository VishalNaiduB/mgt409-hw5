"""FastAPI server for the Campus Customs desk.

Start it from the backend/ folder:

    ../.venv/bin/uvicorn main:app --reload --port 8000

Every route reaches the shop database through the one shared MCP connection
(agents.MCP_SERVER); nothing here touches SQLite. The backend-only MCP tools,
approve_payment and reset_database, are called only from the approve and reset
routes, and only those routes are triggered by a human click.
"""

import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# `uvicorn main:app` runs from backend/, so put the project root on the path for `backend.*` imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend.agents import MCP_SERVER, run_ticket  # noqa: E402
from backend.audit import read_audit  # noqa: E402

FRONTEND_ORIGIN = "http://localhost:5173"


class RunState(BaseModel):
    """The one agent run the server allows at a time."""

    ticket_id: int | None = None
    status: str = "idle"  # idle | running | finished | failed
    started_at: datetime | None = None
    finished_at: datetime | None = None
    summary: str | None = None
    error: str | None = None


class ApprovalRequest(BaseModel):
    approved_by: str = Field(min_length=1, description="Name of the human approving the payment.")


run_state = RunState()
_run_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Hold the shared MCP connection open for the server's lifetime.
    async with MCP_SERVER:
        yield
        if _run_task and not _run_task.done():
            _run_task.cancel()


app = FastAPI(title="Campus Customs desk", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def mcp(tool: str, **args: Any) -> dict:
    """Call one MCP tool over the shared connection; turn a tool error into an HTTP error."""
    result = await MCP_SERVER.direct_call_tool(tool, args)
    if isinstance(result, dict) and "error" in result:
        message = str(result["error"])
        raise HTTPException(status_code=404 if "not found" in message.lower() else 409, detail=result)
    return result


def _running() -> bool:
    return _run_task is not None and not _run_task.done()


async def _run_in_background(ticket_id: int) -> None:
    global run_state
    try:
        response, _ = await run_ticket(ticket_id)
        run_state = run_state.model_copy(
            update={"status": "finished", "finished_at": datetime.now(timezone.utc), "summary": response.summary}
        )
    except Exception as exc:
        run_state = run_state.model_copy(
            update={"status": "failed", "finished_at": datetime.now(timezone.utc), "error": f"{type(exc).__name__}: {exc}"}
        )


# 1. Tickets and pending payments
@app.get("/tickets")
async def list_tickets() -> dict:
    """The tickets with their status, any pending staged payments, and the current run."""
    tickets = (await mcp("list_tickets"))["tickets"]
    pending = (await mcp("list_payments", status="pending"))["payments"]
    for ticket in tickets:
        ticket["pending_payments"] = [
            p
            for p in pending
            if (p["kind"] == "invoice" and p["ref_id"] == ticket["invoice_id"])
            or (p["kind"] == "rent" and p["ref_id"] == ticket["lease_id"])
        ]
    return {"tickets": tickets, "pending_payments": pending, "run": run_state}


# 2. Run the agent team in the background
@app.post("/tickets/{ticket_id}/run", status_code=202)
async def start_run(ticket_id: int) -> dict:
    """Start the agents on a ticket and return right away; poll /tickets and /events while it runs."""
    global run_state, _run_task
    if _running():
        raise HTTPException(status_code=409, detail=f"A run on ticket {run_state.ticket_id} is already in progress.")
    await mcp("get_ticket", ticket_id=ticket_id)  # 404 if the ticket doesn't exist
    run_state = RunState(ticket_id=ticket_id, status="running", started_at=datetime.now(timezone.utc))
    _run_task = asyncio.create_task(_run_in_background(ticket_id))
    return {"run": run_state}


# 3. Agent events from the audit trail
@app.get("/events")
async def events(
    ticket_id: int | None = Query(default=None, description="Only events for this ticket."),
    limit: int = Query(default=100, ge=1, le=1000, description="Most recent N events."),
) -> dict:
    """Recent audit-trail entries: delegations, tool calls and results, and each agent's final answer."""
    entries = read_audit()
    if ticket_id is not None:
        entries = [e for e in entries if e.get("ticket_id") == ticket_id]
    return {"events": entries[-limit:], "total": len(entries)}


# 4. Human approval: the only route that changes cash
@app.post("/payments/{payment_id}/approve")
async def approve(payment_id: int, body: ApprovalRequest) -> dict:
    """A human approves a staged payment via the backend-only approve_payment tool."""
    return await mcp("approve_payment", payment_id=payment_id, approved_by=body.approved_by)


# 5. Checking balance and available cash
@app.get("/cash")
async def cash() -> dict:
    """The checking balance, pending staged payments, and available (uncommitted) cash."""
    return await mcp("check_available_cash", account="checking")


# 6. Reset the working database
@app.post("/reset")
async def reset() -> dict:
    """Restore data/campus_customs_new.db from the original via reset_database. The audit trail is kept."""
    global run_state
    if _running():
        raise HTTPException(status_code=409, detail="Can't reset while an agent run is in progress.")
    result = await mcp("reset_database")
    run_state = RunState()
    return result
