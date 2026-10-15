# Harness

Source: `data/campus_customs.db` (copied to `data/campus_customs_new.db`). 9 tables.

## Tables

| Table | Columns | Why it matters for the agents |
|---|---|---|
| `desk` | `date_today`, `notes` | `date_today` = 2026-08-31 is the clock agents must use: it makes invoice 501 (due 2026-08-28) three days overdue and puts ticket 102's $2,400 rent (due 2026-09-02) two days out. |
| `tickets` | `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at` | The three open tickets are the agents' whole workload: 101 (`customer_order`, Tauhid Zaman, 1 × CC-TEE-WHITE S, linked to invoice 501), 102 (`rent_notice`, Elm City Properties, lease 1) and 103 (`price_override`, Yale AI Club, 20 × CC-HOOD-NAVY M at a bulk discount). |
| `inventory` | `sku`, `name`, `size`, `qty`, `location` | CC-TEE-WHITE size S has 0 in stock, which blocks ticket 101, and CC-HOOD-NAVY size M has only 8 against the 20 requested in ticket 103, a 12-unit shortfall. |
| `pricing` | `sku`, `unit_cost`, `list_price` | CC-HOOD-NAVY costs $22.00 and lists at $58.00, so any bulk discount on ticket 103's 20 hoodies ($1,160 at list) must keep the unit price above $22.00; CC-TEE-WHITE ($8.00 cost, $28.00 list) prices ticket 101. |
| `vendors` | `id`, `name`, `specialty`, `lead_days` | Bulldog Print Co (vendor 1, apparel reprint, 5 lead days) issued invoice 501 for the CC-TEE-WHITE S reprint behind ticket 101 and is the only apparel vendor for restocking the hoodies in ticket 103. |
| `invoices` | `id`, `vendor_id`, `amount`, `due_date`, `status`, `description` | Invoice 501 for $840.00 to Bulldog Print Co ("Rush reprint CC-TEE-WHITE S") is still `open` and overdue against 2026-08-31, and it is tied to ticket 101's out-of-stock tee. |
| `leases` | `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes` | Lease 1 (Chapel Street shop, Elm City Properties) has $2,400.00 rent due 2026-09-02, which is exactly what ticket 102 is asking the shop to pay. |
| `cash_accounts` | `name`, `balance`, `date` | The `checking` balance of $3,400.00 is a tight constraint: covering the $840.00 invoice 501 and the $2,400.00 rent for ticket 102 totals $3,240.00 and leaves only $160.00. |
| `payments` | `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` | Empty at start. Agents can only stage a payment request (for invoice 501 and the ticket 102 rent): Accounting's `stage_payment` inserts a pending row with `paid_at` and `approved_by` empty. Only a human approval fills those in and deducts the amount from `cash_accounts`. |

## Agents

Five PydanticAI agents in `backend/agents.py`, all on `gpt-6-luna` through the Portkey gateway's Responses API (`/v1/responses`, reasoning on; chat completions rejects tools with reasoning), with prompts in `backend/prompts/`. They share one MCP connection to `mcp_server/server.py`: a single `MCPToolset` over stdio. PydanticAI 2.56 replaced `MCPServerStdio` with `MCPToolset`. Each agent sees a filtered view of that connection with only its role's tools.

Every agent has the 6 shared read tools: `get_ticket`, `list_tickets`, `list_tables`, `read_table`, `check_available_cash`, `list_payments`.

| Agent | Role tools (on top of the read tools) | Can delegate to | Job |
|---|---|---|---|
| Boss | `update_ticket` (the only agent with it) | Inventory, Accounting, Facilities, Customer Service | Routes each ticket by type (101 and 103 to Inventory, 102 to Facilities) and closes it out. Resolves a ticket only when no money is moving. |
| Inventory | `check_order_fulfillment`, `quote_bulk_order` | Boss, Accounting, Facilities, Customer Service | Checks stock for the exact SKU and size, the shortfall, and the restock cost and lead time. Hands off to Accounting. |
| Accounting | `stage_payment` (the only agent with it) | Boss, Inventory, Facilities, Customer Service | Checks uncommitted cash, stages invoice and rent payments for human approval, and sets bulk prices above `unit_cost`. Hands off to Customer Service. |
| Facilities | `check_rent_due` | Boss, Inventory, Accounting, Customer Service | Confirms the lease, rent and due date against the desk date. Hands off to Accounting to stage the rent. |
| Customer Service | none | Boss, Inventory, Accounting, Facilities | Writes the customer reply for 101 and 103, without promising shipment while stock is 0 or a payment awaits approval. |

Every agent can delegate to every other (20 one-way links) through `delegate_to_<agent>` tools.

## MCP tools

Server: `mcp_server/server.py` (FastMCP), on `data/campus_customs_new.db`. Each tool call opens a fresh connection and closes it. Every tool is tagged `agent` or `backend`, and an agent's filter only lets through `agent` tools in its role.

| Tool | Tables used | Access |
|---|---|---|
| `check_order_fulfillment` | reads `tickets`, `inventory`, `invoices`, `vendors`, `desk` | Agent tool: Inventory |
| `quote_bulk_order` | reads `tickets`, `inventory`, `pricing`, `vendors`, `desk` | Agent tool: Inventory |
| `check_rent_due` | reads `tickets`, `leases`, `desk`, `cash_accounts` | Agent tool: Facilities |
| `get_ticket` | reads `tickets`, `invoices`, `leases`, `desk` | Agent tool: all agents |
| `list_tickets` | reads `tickets`, `desk` | Agent tool: all agents |
| `list_tables` | reads every table (columns and row counts) | Agent tool: all agents |
| `read_table` | reads one whitelisted table | Agent tool: all agents |
| `check_available_cash` | reads `cash_accounts`, `payments`, `desk` | Agent tool: all agents |
| `list_payments` | reads `payments` | Agent tool: all agents |
| `update_ticket` | reads `payments`, `invoices`, `leases`; writes `tickets` | Agent tool: Boss only |
| `stage_payment` | reads `tickets`, `invoices`, `leases`, `cash_accounts`; writes `payments`, `tickets` | Agent tool: Accounting only |
| `approve_payment` | writes `payments`, `cash_accounts`, `invoices` or `leases`, `tickets` | **Backend-only** (human approval) |
| `reset_database` | replaces the whole `campus_customs_new.db` file from `campus_customs.db` | **Backend-only** |

### Which tool unlocks each ticket

Each ticket tool takes only a `ticket_id` and looks up everything else from `tickets` and its linked rows.

| Tool | Tables read | Unlocks ticket | Why it is the right tool for that ticket |
|---|---|---|---|
| `check_order_fulfillment` | `tickets`, `inventory`, `invoices`, `vendors`, `desk` | 101 | Ticket 101 asks for 1 CC-TEE-WHITE size S, and only this tool puts the 0 units in stock next to linked invoice 501 ($840 to Bulldog Print Co, due 2026-08-28) and the desk date of 2026-08-31, which shows the reprint behind the order is still unpaid and 3 days overdue. |
| `check_rent_due` | `tickets`, `leases`, `desk`, `cash_accounts` | 102 | Ticket 102 is Elm City Properties' rent notice, and this tool follows its `lease_id` to lease 1's $2,400 due 2026-09-02, computes that it is 2 days from the desk date, and shows the $3,400 checking balance would drop to $1,000 after paying it. |
| `quote_bulk_order` | `tickets`, `inventory`, `pricing`, `vendors` | 103 | Ticket 103 is Yale AI Club asking a discount on 20 CC-HOOD-NAVY size M, and this tool shows only 8 are in stock (12 short), the $22 unit cost that sets the discount floor against the $58 list price, and each vendor's lead time for restocking the gap. |

## Safety

- **Only a human approves money.** Agents can only stage a payment. `approve_payment` alone fills in `paid_at` and `approved_by`, deducts from `cash_accounts`, marks the invoice `paid` or moves the lease's `next_due` forward a month, and resolves the ticket. `approve_payment` and `reset_database` are backend-only: they're tagged `backend`, filtered out of every agent's toolset, and refused at call time if an agent ever names them.
- **`stage_payment` guards.** The amount comes from the database (the linked open invoice or the lease rent), never from the agent. The tool refuses:
  - an amount above available cash, which is the `cash_accounts` balance minus pending staged payments only;
  - a duplicate of something already staged, or a ticket already `awaiting_approval` or `resolved`;
  - a ticket with no invoice or lease, or an invoice that isn't `open`.
  On success it sets the ticket to `awaiting_approval`.
- **`update_ticket` guards.** It never sets `awaiting_approval` and won't change a ticket that is already `awaiting_approval` or `resolved`. It refuses `resolved` while the ticket has a pending staged payment, while its invoice is still `open`, or while its lease rent hasn't been approved and paid since the notice came in. So no agent can resolve a ticket around the approval gate.
- **`read_table` whitelist.** The table name must exactly match one of the shop's real tables from `sqlite_master`, which excludes SQLite's internal `sqlite_*` tables. The query uses the name from that list, never the caller's string, so no caller-supplied SQL reaches the database. Read tools open the file read-only.
- **Role-limited toolsets.** Each agent gets its own filtered view of the shared MCP connection:
  - `stage_payment` for Accounting only;
  - `update_ticket` for Boss only;
  - the stock and quote tools for Inventory;
  - `check_rent_due` for Facilities;
  - the 6 read tools for everyone.
  A second check in the tool-call hook refuses any out-of-role tool. Roles are enforced in code, not just in the prompts.
- **Pending payments use empty strings.** The `payments` columns `paid_at` and `approved_by` are `NOT NULL`, so a staged payment stores `''` in both instead of `NULL`. An empty `paid_at` is what marks a payment as pending.
- **One clock: `desk.date_today`.** Every due-date and overdue calculation uses `desk.date_today` (2026-08-31), never the system clock. Approvals record that date as `paid_at`.
- **No direct database access.** `backend/` and the agents never call `sqlite3` or import from `mcp_server/`. Every shop fact comes through MCP tool calls.

## Token and loop limits

- **`UsageLimits(request_limit=35)`** covers a whole ticket run. Every delegated agent shares the caller's usage counter, so all agents in one run together get at most 35 model requests.
- **Delegation depth cap of 3** across the whole handoff chain. Boss → Inventory → Accounting → Customer Service is the longest a chain can get. A fourth handoff is refused with a message telling the agent to finish with the facts it has, so agents can't loop.

## Audit trail

Every agent-loop step is appended to `output/audit_trail.json`, a single JSON array that stays valid after every write. Each append atomically replaces the file with the earlier entries plus the new one. Earlier entries are never changed or dropped, and a run never clears the file; `reset_database` doesn't touch it either. Each entry has:
- `run_id`, `timestamp`, `ticket_id` and `agent`;
- `step_type` (`delegation`, `tool_call`, `tool_result` or `final_answer`);
- `tool` and `arguments`;
- a `result`: the full text for a `final_answer` (so Customer Service replies and agent summaries are never cut off), and a short summary of at most 200 characters for tool results;
- the delegation `depth`;
- `requests_used` so far in the run.

## Backend routes

FastAPI server in `backend/main.py`, started from `backend/` with `uvicorn main:app --reload --port 8000`, with CORS allowed for `http://localhost:5173`. Every route reaches the database through the shared MCP connection, never SQLite.

- `GET /tickets`: returns the shop date (`desk.date_today`) and lists the three tickets with their status, any pending staged payments (also attached to each ticket), and the current agent run's state.
- `POST /tickets/{ticket_id}/run`: starts the agent team on a ticket in the background and returns `202` right away. It returns `409` if a run is already in progress and `404` for an unknown ticket.
- `GET /events?ticket_id=&limit=`: recent audit-trail entries (delegations, tool calls and results, final answers), optionally for one ticket.
- `POST /payments/{payment_id}/approve` (body `{"approved_by": "<name>"}`): a human approves a staged payment through the backend-only `approve_payment` tool. This is the only route that changes cash.
- `GET /cash`: the checking balance, pending staged payments and available cash, via `check_available_cash`.
- `POST /reset`: restores `data/campus_customs_new.db` from the original via the backend-only `reset_database` tool. The audit trail is kept. Returns `409` while a run is in progress.
