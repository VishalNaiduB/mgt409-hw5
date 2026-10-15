"""Campus Customs MCP server: read tools over data/campus_customs_new.db."""

import sqlite3
import sys
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

from fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"

mcp = FastMCP("campus-customs")


def _log(tool: str, **args) -> None:
    """Log a tool call to stderr (stdout carries the MCP stdio protocol)."""
    print(f"[tool] {tool}({', '.join(f'{k}={v!r}' for k, v in args.items())})", file=sys.stderr, flush=True)


def _query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a read-only query on a fresh connection that is closed immediately."""
    with closing(sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _one(sql: str, params: tuple = ()) -> dict | None:
    rows = _query(sql, params)
    return rows[0] if rows else None


def _today() -> date:
    return date.fromisoformat(_one("SELECT date_today FROM desk")["date_today"])


def _ticket(ticket_id: int, expected_type: str) -> dict:
    """Fetch a ticket and check its type, or raise ValueError with a clear message."""
    ticket = _one("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    if ticket is None:
        raise ValueError(f"Ticket {ticket_id} not found.")
    if ticket["type"] != expected_type:
        raise ValueError(f"Ticket {ticket_id} is a '{ticket['type']}' ticket, not '{expected_type}'.")
    return ticket


@mcp.tool
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


@mcp.tool
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


@mcp.tool
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


if __name__ == "__main__":
    mcp.run()
