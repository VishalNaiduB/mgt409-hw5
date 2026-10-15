"""Campus Customs MCP server: tools over data/campus_customs_new.db.

Tools tagged "agent" may be given to the shop's agents. Tools tagged "backend"
(human approval and DB reset) are for backend routes only and must never be
handed to an agent.
"""

import calendar
import os
import shutil
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import date, timedelta
from pathlib import Path

from fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "campus_customs_new.db"
SOURCE_DB_PATH = DATA_DIR / "campus_customs.db"

# Statuses an agent may set directly. "awaiting_approval" is set only by
# stage_payment and "resolved" only by approve_payment.
AGENT_STATUSES = {"open", "in_progress", "escalated"}

# The payments table declares paid_at and approved_by NOT NULL, so a staged
# (pending) payment stores an empty string in both until a human approves it.
PENDING = ""

AGENT = {"agent"}
BACKEND = {"backend"}

mcp = FastMCP("campus-customs")


def _log(tool: str, **args) -> None:
    """Log a tool call to stderr (stdout carries the MCP stdio protocol)."""
    print(f"[tool] {tool}({', '.join(f'{k}={v!r}' for k, v in args.items())})", file=sys.stderr, flush=True)


@contextmanager
def _connect(readonly: bool = True) -> Iterator[sqlite3.Connection]:
    """Open a fresh connection for one tool call and close it immediately."""
    mode = "ro" if readonly else "rw"
    with closing(sqlite3.connect(f"{DB_PATH.as_uri()}?mode={mode}", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        yield conn


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _row(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    rows = _rows(conn, sql, params)
    return rows[0] if rows else None


def _query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a read-only query on a fresh connection that is closed immediately."""
    with _connect() as conn:
        return _rows(conn, sql, params)


def _one(sql: str, params: tuple = ()) -> dict | None:
    rows = _query(sql, params)
    return rows[0] if rows else None


def _today(conn: sqlite3.Connection | None = None) -> date:
    sql = "SELECT date_today FROM desk"
    value = (_row(conn, sql) if conn else _one(sql))["date_today"]
    return date.fromisoformat(value)


def _ticket(ticket_id: int, expected_type: str) -> dict:
    """Fetch a ticket and check its type, or raise ValueError with a clear message."""
    ticket = _one("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    if ticket is None:
        raise ValueError(f"Ticket {ticket_id} not found.")
    if ticket["type"] != expected_type:
        raise ValueError(f"Ticket {ticket_id} is a '{ticket['type']}' ticket, not '{expected_type}'.")
    return ticket


def _table_names(conn: sqlite3.Connection) -> list[str]:
    return [r["name"] for r in _rows(conn, "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]


def _pending_total(conn: sqlite3.Connection, account: str) -> float:
    row = _row(
        conn,
        "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE account = ? AND paid_at = ?",
        (account, PENDING),
    )
    return round(row["total"], 2)


def _cash(conn: sqlite3.Connection, account: str) -> dict:
    """Balance, pending staged payments and available cash for one account."""
    acct = _row(conn, "SELECT name, balance, date FROM cash_accounts WHERE name = ?", (account,))
    if acct is None:
        raise ValueError(f"Cash account '{account}' not found.")
    pending = _pending_total(conn, account)
    return {**acct, "pending_staged": pending, "available": round(acct["balance"] - pending, 2)}


def _payment_status(payment: dict) -> dict:
    payment["status"] = "pending" if payment["paid_at"] == PENDING else "completed"
    return payment


def _add_month(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


# ---------------------------------------------------------------------------
# Agent tools: ticket facts
# ---------------------------------------------------------------------------


@mcp.tool(tags=AGENT)
def check_order_fulfillment(ticket_id: int) -> dict:
    """Check whether a customer_order ticket can be filled from stock.

    Returns the ticket, current stock for its SKU and size, the linked vendor
    invoice (with vendor and days overdue against the desk date), and the desk date.
    """
    _log("check_order_fulfillment", ticket_id=ticket_id)
    try:
        ticket = _ticket(ticket_id, "customer_order")
        today = _today()
        stock = _one(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (ticket["sku"], ticket["size"]),
        )
        on_hand = stock["qty"] if stock else 0

        invoice = None
        if ticket["invoice_id"] is not None:
            invoice = _one(
                """SELECT i.id, i.amount, i.due_date, i.status, i.description,
                          v.id AS vendor_id, v.name AS vendor_name, v.specialty, v.lead_days
                   FROM invoices i JOIN vendors v ON v.id = i.vendor_id
                   WHERE i.id = ?""",
                (ticket["invoice_id"],),
            )
            if invoice:
                days_past_due = (today - date.fromisoformat(invoice["due_date"])).days
                invoice["days_overdue"] = max(days_past_due, 0)
                invoice["is_overdue"] = invoice["status"] == "open" and days_past_due > 0

        return {
            "ticket": ticket,
            "date_today": today.isoformat(),
            "stock": stock,
            "qty_requested": ticket["qty"],
            "qty_on_hand": on_hand,
            "can_fulfill_from_stock": on_hand >= (ticket["qty"] or 0),
            "shortfall": max((ticket["qty"] or 0) - on_hand, 0),
            "linked_invoice": invoice,
        }
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool(tags=AGENT)
def check_rent_due(ticket_id: int) -> dict:
    """Check the lease payment behind a rent_notice ticket.

    Returns the ticket, the linked lease (rent, landlord, next due date), days
    until due against the desk date, and each cash account's balance before and
    after paying the rent.
    """
    _log("check_rent_due", ticket_id=ticket_id)
    try:
        ticket = _ticket(ticket_id, "rent_notice")
        if ticket["lease_id"] is None:
            return {"error": f"Ticket {ticket_id} has no linked lease."}
        lease = _one("SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],))
        if lease is None:
            return {"error": f"Lease {ticket['lease_id']} not found."}

        today = _today()
        accounts = _query("SELECT name, balance, date FROM cash_accounts ORDER BY name")
        for account in accounts:
            account["balance_after_rent"] = round(account["balance"] - lease["monthly_rent"], 2)
            account["covers_rent"] = account["balance"] >= lease["monthly_rent"]

        return {
            "ticket": ticket,
            "date_today": today.isoformat(),
            "lease": lease,
            "days_until_due": (date.fromisoformat(lease["next_due"]) - today).days,
            "cash_accounts": accounts,
        }
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool(tags=AGENT)
def quote_bulk_order(ticket_id: int) -> dict:
    """Gather the facts needed to quote a price_override (bulk discount) ticket.

    Returns the ticket, stock for its SKU and size versus the quantity requested,
    unit cost and list price (the cost is the price floor), the order total at
    list price, and every vendor with lead time and restock-ready date.
    """
    _log("quote_bulk_order", ticket_id=ticket_id)
    try:
        ticket = _ticket(ticket_id, "price_override")
        today = _today()
        stock = _one(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (ticket["sku"], ticket["size"]),
        )
        pricing = _one("SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (ticket["sku"],))
        if pricing is None:
            return {"error": f"No pricing found for {ticket['sku']}."}

        requested = ticket["qty"] or 0
        on_hand = stock["qty"] if stock else 0
        vendors = _query("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id")
        for vendor in vendors:
            vendor["restock_ready_by"] = (today + timedelta(days=vendor["lead_days"])).isoformat()

        return {
            "ticket": ticket,
            "date_today": today.isoformat(),
            "stock": stock,
            "qty_requested": requested,
            "qty_on_hand": on_hand,
            "shortfall": max(requested - on_hand, 0),
            "unit_cost": pricing["unit_cost"],
            "list_price": pricing["list_price"],
            "unit_margin_at_list": round(pricing["list_price"] - pricing["unit_cost"], 2),
            "order_total_at_list": round(requested * pricing["list_price"], 2),
            "order_cost": round(requested * pricing["unit_cost"], 2),
            "vendors": vendors,
        }
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Agent tools: tickets
# ---------------------------------------------------------------------------


@mcp.tool(tags=AGENT)
def list_tickets(status: str | None = None) -> dict:
    """List tickets, optionally only those with the given status (e.g. "open")."""
    _log("list_tickets", status=status)
    try:
        if status is None:
            tickets = _query("SELECT * FROM tickets ORDER BY id")
        else:
            tickets = _query("SELECT * FROM tickets WHERE status = ? ORDER BY id", (status,))
        return {"date_today": _today().isoformat(), "tickets": tickets}
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool(tags=AGENT)
def get_ticket(ticket_id: int) -> dict:
    """Get one ticket with its linked invoice and lease rows, if any."""
    _log("get_ticket", ticket_id=ticket_id)
    try:
        ticket = _one("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return {"error": f"Ticket {ticket_id} not found."}
        invoice = lease = None
        if ticket["invoice_id"] is not None:
            invoice = _one("SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],))
        if ticket["lease_id"] is not None:
            lease = _one("SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],))
        return {"date_today": _today().isoformat(), "ticket": ticket, "invoice": invoice, "lease": lease}
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool(tags=AGENT)
def update_ticket(ticket_id: int, status: str | None = None, note: str | None = None) -> dict:
    """Set a ticket's status and/or append a note to it.

    Agents may set status to "open", "in_progress" or "escalated" only:
    "awaiting_approval" comes from stage_payment and "resolved" from a human
    approval. A note is appended to the ticket's notes with the desk date.
    """
    _log("update_ticket", ticket_id=ticket_id, status=status, note=note)
    try:
        if status is None and not note:
            return {"error": "Nothing to update: give a status, a note, or both."}
        if status is not None and status not in AGENT_STATUSES:
            return {"error": f"Agents cannot set status '{status}'. Allowed: {sorted(AGENT_STATUSES)}."}
        with _connect(readonly=False) as conn, conn:
            ticket = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
            if ticket is None:
                return {"error": f"Ticket {ticket_id} not found."}
            if ticket["status"] in ("awaiting_approval", "resolved") and status is not None:
                return {"error": f"Ticket {ticket_id} is '{ticket['status']}'; its status can only change through a human approval."}
            if status is not None:
                conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
            if note:
                stamped = f"[{_today(conn).isoformat()}] {note}"
                notes = f"{ticket['notes']}\n{stamped}" if ticket["notes"] else stamped
                conn.execute("UPDATE tickets SET notes = ? WHERE id = ?", (notes, ticket_id))
            return {"ticket": _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Agent tools: inspecting tables, cash and payments
# ---------------------------------------------------------------------------


@mcp.tool(tags=AGENT)
def list_tables() -> dict:
    """List every table in the shop database with its columns and row count."""
    _log("list_tables")
    try:
        with _connect() as conn:
            tables = []
            for name in _table_names(conn):
                columns = [c["name"] for c in _rows(conn, f'PRAGMA table_info("{name}")')]
                count = _row(conn, f'SELECT COUNT(*) AS n FROM "{name}"')["n"]
                tables.append({"table": name, "columns": columns, "row_count": count})
            return {"tables": tables}
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool(tags=AGENT)
def read_table(table: str, limit: int = 50) -> dict:
    """Read up to `limit` rows (max 200) from one table, read-only."""
    _log("read_table", table=table, limit=limit)
    try:
        with _connect() as conn:
            if table not in _table_names(conn):
                return {"error": f"Unknown table '{table}'. Use list_tables to see the tables."}
            rows = _rows(conn, f'SELECT * FROM "{table}" LIMIT ?', (max(1, min(limit, 200)),))
            return {"table": table, "rows": rows}
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool(tags=AGENT)
def check_available_cash(account: str = "checking") -> dict:
    """Show a cash account's balance, pending staged payments and available cash.

    Available cash = balance minus pending staged payments. Completed payments
    are already deducted from the balance, so they are not subtracted again.
    """
    _log("check_available_cash", account=account)
    try:
        with _connect() as conn:
            return {"date_today": _today(conn).isoformat(), "account": _cash(conn, account)}
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool(tags=AGENT)
def list_payments(status: str | None = None) -> dict:
    """List payments, optionally only "pending" (staged) or "completed" (approved) ones."""
    _log("list_payments", status=status)
    try:
        if status not in (None, "pending", "completed"):
            return {"error": "status must be 'pending', 'completed' or omitted."}
        payments = [_payment_status(p) for p in _query("SELECT * FROM payments ORDER BY id")]
        if status is not None:
            payments = [p for p in payments if p["status"] == status]
        return {"payments": payments}
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool(tags=AGENT)
def stage_payment(ticket_id: int, account: str = "checking") -> dict:
    """Stage the payment a ticket needs, for a human to approve later.

    The amount comes from the database: a ticket's linked open invoice
    (kind "invoice") or its linked lease's monthly rent (kind "rent"). Inserts a
    pending row in payments (paid_at and approved_by left empty) and sets the
    ticket to "awaiting_approval". Refuses an amount above available cash, or a
    duplicate of a payment that is already staged. Moves no money.
    """
    _log("stage_payment", ticket_id=ticket_id, account=account)
    try:
        with _connect(readonly=False) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            ticket = _row(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
            if ticket is None:
                return {"error": f"Ticket {ticket_id} not found."}
            if ticket["status"] in ("awaiting_approval", "resolved"):
                return {"error": f"Ticket {ticket_id} is already '{ticket['status']}'."}

            if ticket["invoice_id"] is not None:
                invoice = _row(conn, "SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],))
                if invoice is None:
                    return {"error": f"Invoice {ticket['invoice_id']} not found."}
                if invoice["status"] != "open":
                    return {"error": f"Invoice {invoice['id']} is '{invoice['status']}', not open."}
                kind, ref_id, amount = "invoice", invoice["id"], invoice["amount"]
            elif ticket["lease_id"] is not None:
                lease = _row(conn, "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],))
                if lease is None:
                    return {"error": f"Lease {ticket['lease_id']} not found."}
                kind, ref_id, amount = "rent", lease["id"], lease["monthly_rent"]
            else:
                return {"error": f"Ticket {ticket_id} has no linked invoice or lease, so there is nothing to pay."}

            duplicate = _row(
                conn,
                "SELECT * FROM payments WHERE kind = ? AND ref_id = ? AND paid_at = ?",
                (kind, ref_id, PENDING),
            )
            if duplicate:
                label = "Invoice" if kind == "invoice" else "Rent for lease"
                return {"error": f"{label} {ref_id} is already staged as payment {duplicate['id']}."}

            cash = _cash(conn, account)
            if amount > cash["available"]:
                return {
                    "error": f"${amount:,.2f} is more than the ${cash['available']:,.2f} available in '{account}'.",
                    "account": cash,
                }

            cur = conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
                (kind, ref_id, amount, account, PENDING, PENDING),
            )
            conn.execute("UPDATE tickets SET status = 'awaiting_approval' WHERE id = ?", (ticket_id,))
            payment = _payment_status(_row(conn, "SELECT * FROM payments WHERE id = ?", (cur.lastrowid,)))
            return {"staged_payment": payment, "ticket_id": ticket_id, "account": _cash(conn, account)}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Backend-only tools: never give these to an agent
# ---------------------------------------------------------------------------


@mcp.tool(tags=BACKEND)
def approve_payment(payment_id: int, approved_by: str) -> dict:
    """BACKEND ONLY: record a human's approval of a staged payment.

    Fills in paid_at (the desk date) and approved_by, deducts the amount from the
    cash account, marks the invoice paid or advances the lease's next due date
    by one month, and sets the linked ticket to "resolved".
    """
    _log("approve_payment", payment_id=payment_id, approved_by=approved_by)
    try:
        if not approved_by or not approved_by.strip():
            return {"error": "approved_by must name the human approving the payment."}
        with _connect(readonly=False) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            payment = _row(conn, "SELECT * FROM payments WHERE id = ?", (payment_id,))
            if payment is None:
                return {"error": f"Payment {payment_id} not found."}
            if payment["paid_at"] != PENDING:
                return {"error": f"Payment {payment_id} was already approved on {payment['paid_at']} by {payment['approved_by']}."}
            acct = _row(conn, "SELECT * FROM cash_accounts WHERE name = ?", (payment["account"],))
            if acct is None:
                return {"error": f"Cash account '{payment['account']}' not found."}
            if payment["amount"] > acct["balance"]:
                return {"error": f"${payment['amount']:,.2f} is more than the ${acct['balance']:,.2f} balance in '{acct['name']}'."}

            today = _today(conn).isoformat()
            conn.execute(
                "UPDATE payments SET paid_at = ?, approved_by = ? WHERE id = ?",
                (today, approved_by.strip(), payment_id),
            )
            conn.execute(
                "UPDATE cash_accounts SET balance = ROUND(balance - ?, 2), date = ? WHERE name = ?",
                (payment["amount"], today, acct["name"]),
            )
            if payment["kind"] == "invoice":
                conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (payment["ref_id"],))
                link = "invoice_id"
            elif payment["kind"] == "rent":
                lease = _row(conn, "SELECT next_due FROM leases WHERE id = ?", (payment["ref_id"],))
                next_due = _add_month(date.fromisoformat(lease["next_due"])).isoformat()
                conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, payment["ref_id"]))
                link = "lease_id"
            else:
                raise ValueError(f"Unknown payment kind '{payment['kind']}'.")

            resolved = [
                r["id"]
                for r in _rows(
                    conn,
                    f"SELECT id FROM tickets WHERE {link} = ? AND status = 'awaiting_approval'",
                    (payment["ref_id"],),
                )
            ]
            conn.executemany("UPDATE tickets SET status = 'resolved' WHERE id = ?", [(i,) for i in resolved])
            return {
                "payment": _payment_status(_row(conn, "SELECT * FROM payments WHERE id = ?", (payment_id,))),
                "account": _cash(conn, acct["name"]),
                "resolved_ticket_ids": resolved,
            }
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool(tags=BACKEND)
def reset_database() -> dict:
    """BACKEND ONLY: restore data/campus_customs_new.db from data/campus_customs.db.

    Every tool call opens a fresh connection, so the reset is visible on the next call.
    """
    _log("reset_database")
    try:
        tmp = DB_PATH.with_suffix(".db.tmp")
        shutil.copyfile(SOURCE_DB_PATH, tmp)
        os.replace(tmp, DB_PATH)
        with _connect() as conn:
            counts = {name: _row(conn, f'SELECT COUNT(*) AS n FROM "{name}"')["n"] for name in _table_names(conn)}
        return {"reset": True, "source": SOURCE_DB_PATH.name, "row_counts": counts}
    except Exception as exc:
        return {"error": str(exc)}


if __name__ == "__main__":
    mcp.run()
