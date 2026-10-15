# Campus Customs MCP server

`server.py` is a FastMCP server that gives the shop's agents read access to the Campus Customs database through the MCP protocol. Agents and `backend/` never touch SQLite directly; every shop fact they use comes from these tools.

## Database

The server reads `data/campus_customs_new.db` (a working copy of `data/campus_customs.db`). Each tool call opens a fresh read-only SQLite connection and closes it right away, so a reset of the database file is visible on the very next call.

## Tools

Each tool takes a `ticket_id` and looks up everything else (SKU, size, quantity, linked invoice or lease) from the `tickets` table and the tables it links to.

| Tool | Ticket type | Tables read | What it returns |
|---|---|---|---|
| `check_order_fulfillment` | `customer_order` (ticket 101) | `tickets`, `inventory`, `invoices`, `vendors`, `desk` | Stock on hand for the ticket's SKU and size, the shortfall, and the linked vendor invoice with days overdue against the desk date. |
| `check_rent_due` | `rent_notice` (ticket 102) | `tickets`, `leases`, `desk`, `cash_accounts` | The linked lease's rent, landlord and next due date, days until due, and each cash account's balance before and after paying the rent. |
| `quote_bulk_order` | `price_override` (ticket 103) | `tickets`, `inventory`, `pricing`, `vendors` | Stock versus quantity requested, unit cost (the price floor) and list price, order totals, and each vendor's lead time and restock-ready date. |

A tool returns `{"error": "..."}` instead of raising, for example when the ticket does not exist or is the wrong type for that tool. Tool calls are logged to stderr, since stdout carries the MCP stdio protocol.

## Running

The server is connected through `.mcp.json` at the project root, which registers it as `campus-customs` and launches it over stdio with `.venv/bin/python mcp_server/server.py`. The paths are relative, so it works in any clone that has the project's `.venv`. Claude Code starts the server automatically when it opens the project.

A smoke test of all 3 tools against the current data (tickets 101, 102 and 103) is saved in `output/mcp_smoke.json`, with each prompt, the tool called and its actual output.
