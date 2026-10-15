# Campus Customs MCP server

`server.py` is a FastMCP server that gives the shop's agents and the backend access to the Campus Customs database through the MCP protocol. Agents and `backend/` never touch SQLite directly; every shop fact they use comes from these tools.

## Database

The server works on `data/campus_customs_new.db`, a working copy of `data/campus_customs.db`. Each tool call opens a fresh SQLite connection and closes it right away, so a reset of the database file is visible on the very next call. Read tools open the file read-only; only the tools that write (`update_ticket`, `stage_payment`, `approve_payment`) open it read-write, inside a single transaction.

## Agent tools vs backend-only tools

Every tool is tagged in its MCP metadata: `agent` tools may be given to the 5 agents (Boss, Inventory, Accounting, Facilities, Customer Service), while `backend` tools are for backend routes only and must **never** be handed to an agent. Only a human, through the backend, can approve a payment or reset the database.

### Agent tools

Each ticket tool takes a `ticket_id` and looks up everything else (SKU, size, quantity, linked invoice or lease) from the `tickets` table and the tables it links to.

| Tool | Tables read / written | What it does |
|---|---|---|
| `check_order_fulfillment` | reads `tickets`, `inventory`, `invoices`, `vendors`, `desk` | For a `customer_order` ticket (101): stock on hand for its SKU and size, the shortfall, and the linked vendor invoice with days overdue against the desk date. |
| `check_rent_due` | reads `tickets`, `leases`, `desk`, `cash_accounts` | For a `rent_notice` ticket (102): the linked lease's rent, landlord and next due date, days until due, and each cash account's balance before and after paying the rent. |
| `quote_bulk_order` | reads `tickets`, `inventory`, `pricing`, `vendors` | For a `price_override` ticket (103): stock versus quantity requested, unit cost (the price floor) and list price, order totals, and each vendor's lead time and restock-ready date. |
| `list_tickets` | reads `tickets`, `desk` | All tickets, or only those with a given status. |
| `get_ticket` | reads `tickets`, `invoices`, `leases`, `desk` | One ticket with its linked invoice and lease rows. |
| `update_ticket` | reads `payments`; writes `tickets` | Sets a ticket's status to `open`, `in_progress`, `escalated` or `resolved` and/or appends a dated note. It refuses `awaiting_approval` (only staging sets it) and won't change the status of a ticket that is already awaiting approval or resolved. It refuses `resolved` while the ticket has a pending staged payment, while its linked invoice is still `open`, or while its lease rent hasn't been approved and paid since the notice came in (a completed rent payment dated on or after the ticket's `created_at`, since approval moves `next_due` forward). So a ticket with a bill behind it can't be resolved around the approval gate. |
| `list_tables` | reads every table | Each shop table's columns and row count (SQLite's internal `sqlite_*` tables are left out). |
| `read_table` | reads one table | Up to 200 rows of one table. The name must exactly match a table from `list_tables`; anything else (SQL fragments, `sqlite_master`, different case) is refused, so no caller-supplied SQL reaches the database. |
| `check_available_cash` | reads `cash_accounts`, `payments` | An account's balance, total of pending staged payments, and available cash. |
| `list_payments` | reads `payments` | All payments, or only `pending` (staged) or `completed` (approved) ones. |
| `stage_payment` | reads `tickets`, `invoices`, `leases`, `cash_accounts`; writes `payments`, `tickets` | Stages the payment a ticket needs for human approval. It moves no money (see below). |

### Backend-only tools

| Tool | Tables written | What it does |
|---|---|---|
| `approve_payment` | `payments`, `cash_accounts`, `invoices` or `leases`, `tickets` | Records a human's approval of a staged payment: fills in `paid_at` (the desk date) and `approved_by`, deducts the amount from the cash account, marks the invoice `paid` or moves the lease's `next_due` forward one month, and sets the linked ticket to `resolved`. |
| `reset_database` | the whole file | Restores `data/campus_customs_new.db` from `data/campus_customs.db`. |

## Staging and approving payments

No new tables are used. `stage_payment` inserts a row into the existing `payments` table, taking the amount from the database (the ticket's linked open invoice, kind `invoice`, or its lease's monthly rent, kind `rent`), and sets the ticket to `awaiting_approval`. The `payments` table declares `paid_at` and `approved_by` as `NOT NULL`, so a staged row stores an empty string (`''`) in both; that empty `paid_at` is what marks a payment as pending.

Staging refuses:
- an amount above available cash, where **available cash = `cash_accounts` balance − pending staged payments** (completed payments are already deducted from the balance, so they are not subtracted again);
- a duplicate: an invoice or lease rent that already has a pending staged payment, or a ticket that is already `awaiting_approval` or `resolved`;
- a ticket with no linked invoice or lease, or an invoice that is not `open`.

Only `approve_payment` fills in `paid_at` and `approved_by`, changes `cash_accounts`, marks invoices paid, advances leases, and resolves a ticket that has a pending staged payment. An agent can resolve a ticket only when nothing is left for a human to approve.

A tool returns `{"error": "..."}` instead of raising, for example when the ticket does not exist or is the wrong type for that tool. Tool calls are logged to stderr, since stdout carries the MCP stdio protocol.

## Running

The server is connected through `.mcp.json` at the project root, which registers it as `campus-customs` and launches it over stdio with `.venv/bin/python mcp_server/server.py`. The paths are relative, so it works in any clone that has the project's `.venv`. Claude Code starts the server automatically when it opens the project.

A smoke test of the 3 ticket tools against the current data (tickets 101, 102 and 103) is saved in `output/mcp_smoke.json`, with each prompt, the tool called and its actual output.
