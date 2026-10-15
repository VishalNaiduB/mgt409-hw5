# AI Prompts

## Problem 1

Set up AI_prompts.md with sections for Problem 1 through Problem 11 and log this prompt under Problem 1 and Problem 2. Then copy data/campus_customs.db to data/campus_customs_new.db, inspect the full schema and all rows of every table in data/campus_customs.db, print out all table contents for me to see, and start output/harness.md listing every table, its columns, and one sentence on why it matters for the agents.

## Problem 2

Set up AI_prompts.md with sections for Problem 1 through Problem 11 and log this prompt under Problem 1 and Problem 2. Then copy data/campus_customs.db to data/campus_customs_new.db, inspect the full schema and all rows of every table in data/campus_customs.db, print out all table contents for me to see, and start output/harness.md listing every table, its columns, and one sentence on why it matters for the agents.

### Problem 2 follow-up

Update output/harness.md to fix two things from the first pass: first, tie each table's "why it matters" line directly to the specific tickets (101, 102, 103) and real numbers in the database (like CC-TEE-WHITE size S at 0 qty blocking ticket 101 while invoice 501 for $840 is overdue against 2026-08-31, CC-HOOD-NAVY size M having only 8 in stock vs the 20 requested in ticket 103, the $2,400 rent due 2026-09-02 for ticket 102, and the $3,400 checking balance being a tight constraint after covering the $840 invoice and $2,400 rent). Second, fix the payments description so it clearly states that agents only stage payment requests and a human approval is what actually writes to payments and updates cash. Log this as my Problem 2 follow-up in AI_prompts.md along with one sentence noting that the first pass was too general and had the payments approval responsibility backwards.

Note: The first pass of output/harness.md was too general and had the payments approval responsibility backwards, implying agents record approved payments when only a human approval writes to payments and updates cash.

## Problem 3

Build an MCP server in `mcp_server/server.py` using FastMCP that connects to `data/campus_customs_new.db` (open a fresh sqlite connection inside a context manager on each tool call so DB resets never read stale data). Do not run or connect the server yet.
Write 3 clearly named read tools, one for each of the 3 open tickets. Each tool should take a `ticket_id` and look up everything else (sku, size, qty, invoice, lease) from the `tickets` table and the linked tables. Don’t hardcode any values; the numbers below are what the output should show for the current data, not values to put in the code.

1. `check_order_fulfillment` for Ticket 101: checks `inventory`, `invoices`, `vendors`, and `desk` so an agent can see `CC-TEE-WHITE` size S is at 0 stock and linked invoice 501 ($840 to Bulldog Print Co) is overdue against `desk.date_today` (2026-08-31).
2. `check_rent_due` for Ticket 102: checks `leases`, `desk`, and `cash_accounts` so an agent can see lease 1 ($2,400 to Elm City Properties due 2026-09-02) is due in 2 days and compare it against the $3,400 checking balance.
3. `quote_bulk_order` for Ticket 103: checks `inventory`, `pricing`, and `vendors` so an agent can see `CC-HOOD-NAVY` size M only has 8 in stock out of the 20 requested by Yale AI Club, along with its $22 unit cost, $58 list price, and vendor lead time.

Also write a short `mcp_server/README.md` explaining what the MCP server is for, that it uses `data/campus_customs_new.db`, and what the 3 tools are. Finally, add a section to `output/harness.md` listing each of the 3 tools, the exact tables it reads, which ticket (101, 102, or 103) it unlocks, and one specific sentence on why that tool is the right one for that ticket. Log this prompt under Problem 3 in `AI_prompts.md`.

## Problem 4

Create .mcp.json at the project root so Claude Code can connect to the MCP server in mcp_server/server.py. Use the project’s .venv Python with relative paths, so it works on any machine that clones the repo. Log this under Problem 4 in AI_prompts.md.

Use the campus-customs MCP tool to check whether ticket 101 can be fulfilled.

Use the campus-customs MCP tool to check the rent for ticket 102: when it’s due and what it would leave in checking.

Use the campus-customs MCP tool to get the facts for quoting the bulk order in ticket 103.

Save those three MCP tool calls in output/mcp_smoke.json: for each, the exact prompt I asked, the tool name, and the tool’s actual output. Update mcp_server/README.md, which still says the server isn’t wired up, to explain it’s connected through .mcp.json. Log my Problem 4 prompts in AI_prompts.md, then commit as “P4”.

## Problem 5

Let’s start Problem 5 in three passes. For Pass 5a:

1. Load `PORTKEY_API_KEY` from `.env` in the project root and run a quick test call to check if `gpt-6-luna` responds before we wire the agents. If it fails, stop and tell me; don’t switch to another model.
2. Expand `mcp_server/server.py` with the additional MCP tools our 5 agents (Boss, Inventory, Accounting, Facilities, Customer Service) and the backend routes will need to read/update tickets, inspect tables, stage payments, and execute human approvals or DB resets. For staging payments, do NOT create any new database tables. Insert a row into the existing `payments` table with `paid_at` and `approved_by` left empty (`NULL`), and set the ticket to `awaiting_approval`. Staging should refuse an amount above available cash and refuse a duplicate for something already staged. Available cash = `cash_accounts` balance minus pending staged payments only (completed payments are already deducted from the balance). Only the human approval tool should fill in `paid_at` and `approved_by`, deduct from `cash_accounts`, mark the invoice paid or advance the lease’s next due date, and set the ticket to `resolved`. The approval and reset tools are backend-only: agents must never be given them.
3. Update `mcp_server/README.md` so the tool list matches all tools now in the server, and mark which tools are agent tools vs backend-only.
4. Create `backend/models.py` with the Pydantic models for tickets, agent handoffs/responses, staged payments, and audit trail entries.

Log this prompt under Problem 5 in `AI_prompts.md`.

Note: The `payments` table declares `paid_at` and `approved_by` as NOT NULL, so `NULL` was rejected by the schema; I chose to store staged payments with empty strings (`''`) in both columns instead of changing the schema.

### Pass 5a follow-ups

Also tighten update_ticket: it must refuse to set a ticket to resolved if that ticket has a pending staged payment (empty paid_at); only approve_payment can resolve those. And make sure read_table only accepts names from the real table list, so it can’t run arbitrary SQL.

Yes, close that gap too: update_ticket should refuse resolved while a ticket’s linked invoice is still open or its lease rent for the current due date hasn’t been approved and paid. Then log this and my previous prompt under Problem 5 in AI_prompts.md as Pass 5a follow-ups, with one sentence noting that the first pass let agents resolve tickets around the approval gate and read_table needed injection hardening. Re-run your tests, confirm data/campus_customs_new.db is still identical to the original, and commit as “P5a follow-up”.

Note: The first pass did not tie resolving a ticket to the approval gate, so once agents were allowed to resolve tickets they could get around it, and read_table needed injection hardening.

### Pass 5b

Now for Pass 5b, create the 5 prompt files in `backend/prompts/` (`boss.md`, `inventory.md`, `accounting.md`, `facilities.md`, `customer_service.md`) expanding on my shop rules below while keeping my wording and specific rules intact. In every prompt file, add this line: “The figures above are examples from today’s data; always get current numbers from the MCP tools before deciding.”
Then build the 5 PydanticAI agents in `backend/` using `gpt-6-luna` and `PORTKEY_API_KEY` loaded from the `.env` in the project root. Make sure all 5 agents share a single `MCPServerStdio` connection to `mcp_server/server.py` (do not import functions from `mcp_server` or call sqlite3 directly). Give every agent a delegate tool for each of the other four agents, so any agent can hand off to any other (full connectivity), with a delegation depth cap of 3 enforced across the whole chain, and set `UsageLimits(request_limit=35)`. The backend-only MCP tools `approve_payment` and `reset_database` must not be given to any agent; filter them out of the agents’ toolset.
When done, don’t run a real ticket yet. Instead list each agent’s tools, show that `approve_payment` and `reset_database` aren’t among them, and confirm the delegate tools connect all five agents. Log this prompt under Problem 5 in `AI_prompts.md`.
Shop rules for each agent:
Boss:

* Route tickets based on what they actually need instead of calling every agent on the floor: send customer_order (101) to Inventory first, rent_notice (102) to Facilities first, and price_override (103) to Inventory first so we know our stock position before quoting a discount.
* Keep uninvolved specialists out of the loop: Facilities has nothing to do with apparel orders (101, 103), and Inventory/Customer Service don’t need to be called on shop rent (102).
* Let specialists hand off directly to each other (like Inventory → Accounting → Customer Service) rather than bouncing back to Boss after every single step, and cap handoffs at 3 so agents don’t loop forever.
* When a run finishes, only mark the ticket resolved if no money is moving; if Accounting staged a payment, leave the ticket in awaiting_approval until a human clicks approve.

Inventory:

* Always check current stock in the inventory table for the exact SKU and size on the ticket, plus vendor lead days if we are short.
* Never promise an item can ship if qty is 0 or if there is an unpaid vendor invoice blocking the restock.
* On Ticket 101, CC-TEE-WHITE size S is at 0 stock and linked to Invoice 501 ($840 to Bulldog Print Co, 5 lead days), so hand off directly to Accounting to handle the unpaid invoice before Customer Service replies to Tauhid.
* On Ticket 103, Yale AI Club wants 20 CC-HOOD-NAVY size M hoodies but we only have 8 in Aisle A (short by 12, which costs $22/unit = $264 from Bulldog Print Co with a 5-day lead time), so pass those stock and restock numbers directly to Accounting.

Accounting:

* Always compare due dates against desk.date_today (2026-08-31), never the system clock, so Invoice 501 (due 2026-08-28) is already 3 days overdue, and Lease 1 (due 2026-09-02) is due in 2 days.
* Never deduct money from cash_accounts or mark a payment as paid yourself; only stage payments by inserting a row in payments with paid_at and approved_by left empty (empty, not yet filled) for human approval.
* Before staging any payment or approving a restock spend, check uncommitted cash: start with cash_accounts.balance ($3,400) and subtract only pending staged payments (completed payments are already deducted from the balance).
* Once $840 (Invoice 501) and $2,400 (Lease 1 rent) are accounted for, only $160 in uncommitted cash remains, which is not enough to cover the $264 cost to restock 12 hoodies on Ticket 103 right now.
* For price overrides (Ticket 103), never quote below unit_cost ($22 for CC-HOOD-NAVY vs $58 list price); set a sensible bulk price above $22 that preserves margin and hand off to Customer Service.

Facilities:

* Handle only shop lease and property matters (Lease 1 for the Chapel Street shop with Elm City Properties).
* Check leases.next_due (2026-09-02) against desk.date_today (2026-08-31) to confirm the $2,400 monthly rent is coming due in 2 days.
* Facilities cannot touch cash_accounts or stage payments directly; hand off to Accounting to verify cash and stage the $2,400 rent payment for human approval.

Customer Service:

* Write the final customer-facing response on customer orders and quote requests, and never claim an order has shipped when stock is 0 or a vendor invoice is still awaiting human approval.
* For Ticket 101 (Tauhid Zaman), clearly explain that CC-TEE-WHITE size S is out of stock, the $840 rush reprint invoice (#501) with Bulldog Print Co is staged for human approval, and fulfillment will take 5 lead days once approved.
* For Ticket 103 (Yale AI Club), share the bulk price Accounting set per hoodie, confirm that 8 size M hoodies are ready in Aisle A right now, and explain that the remaining 12 need a 5-day reprint from Bulldog Print Co (which can’t be ordered from shop cash yet since uncommitted cash is down to $160 vs the $264 restock cost, unless the club pays up front or splits the shipment).

Note: PydanticAI 2.56 (the installed version) no longer has `MCPServerStdio`; its replacement is `MCPToolset`, so the 5 agents share a single `MCPToolset` over a FastMCP stdio transport to `mcp_server/server.py`.

### Pass 5b follow-up

Yes, enforce roles in code, not just prompts. Give stage_payment to Accounting only, and update_ticket to Boss only. Keep the read tools (get_ticket, list_tickets, list_tables, read_table, check_available_cash, list_payments) available to everyone, and the ticket-check tools to the roles that need them: check_order_fulfillment and quote_bulk_order for Inventory, check_rent_due for Facilities. Show me each agent’s final tool list. Also update the MCPServerStdio line in CLAUDE.md to say MCPToolset, so the rules match the code. Log this as a Pass 5b follow-up in AI_prompts.md, with one sentence noting that the first pass enforced role limits only in prompts. Confirm the database is unchanged, then commit as “P5b”.

Note: The first pass enforced role limits only in the prompts, so every agent's toolset still included `stage_payment` and `update_ticket`.

### Pass 5c

Pass 5c: wire the agents so every agent-loop step appends to `output/audit_trail.json`. Never wipe or overwrite it between runs, and keep the file valid JSON. Each entry should have a run id, timestamp, ticket id, agent, step type (delegation, tool call, tool result, final answer), tool name and arguments, a short result, delegation depth, and requests used so far.
Then update `output/harness.md` with:

* all 5 agents, with their role tools and who they can delegate to;
* every MCP tool, the table it uses, and whether it’s an agent tool or backend-only;
* a safety section: approval only by a human, guards on `update_ticket` and `stage_payment`, the `read_table` whitelist, role-limited toolsets, pending payments stored with empty strings because those columns are NOT NULL, and using `desk.date_today`;
* token and loop limits: `UsageLimits(request_limit=35)` and the delegation depth cap of 3.

Test the audit trail with the scripted test model only, without a real ticket run. Confirm the file appends across two test runs, then clear the test entries so it starts empty. Confirm the database is unchanged. Log this under Problem 5 in `AI_prompts.md` and commit as “P5c”.

### Problem 5 follow-up: model fix

Switch backend/llm.py to the Responses API through Portkey, keeping gpt-6-luna and reasoning on. Then redo the real run of ticket 101 the same way as before: scratch audit file, no approvals, then reset and confirm the real audit trail is still []. Show me the chain, tools, requests used, final status and any staged payment. Log this under Problem 5 in AI_prompts.md as a follow-up, with one sentence noting the first setup used chat completions, which gpt-6-luna rejects once agents have tools. Commit as “P5 model fix”.

Note: The first setup used chat completions (`/v1/chat/completions`), which gpt-6-luna rejects once agents have tools while reasoning is on, so the first real run failed on its first request.

## Problem 6

Build `output/desk_tickets.html`, a page I can double-click, with tabs for Ticket 101, Ticket 102, Ticket 103, Cash, and Reflection. Leave Cash and Reflection as “coming later” stubs. On each ticket tab, add an Expected section with my plan below, and an empty Actual section to fill in later. Keep my wording and make sure any MCP tool names in my notes match the exact tool names defined in our server/harness; you can format it cleanly. Log this under Problem 6 in `AI_prompts.md` and commit as “P6”.
Run order assumption: We run tickets in sequential order (101 → 102 → 103) starting from the $3,400.00 checking balance on shop date 2026-08-31.
Ticket 101 (Tauhid Zaman: 1x CC-TEE-WHITE size S, customer_order):

* Who Boss calls first & why: Boss reads the ticket with `get_ticket` and calls Inventory first because it is a customer order for physical merch (CC-TEE-WHITE size S) and we need to verify if we have stock on the shelf before doing anything else.
* Handoff chain & who is left out: Boss → Inventory → Accounting → Customer Service, and Customer Service’s reply returns up the chain to Boss (not a new handoff, since 3 handoffs is our depth cap). Inventory sees 0 units of size S in Aisle B and sees linked Invoice 501 ($840.00 to Bulldog Print Co for a rush reprint), so Inventory hands off directly to Accounting (specialist-to-specialist) to handle the bill. Accounting verifies Invoice 501 was due 2026-08-28 (3 days overdue against desk.date_today 2026-08-31), checks cash ($3,400.00 available), stages the $840.00 payment, and hands off directly to Customer Service to draft the update for Tauhid: size S is out of stock, the reprint is waiting on payment approval, and the tee should be ready about 5 days after approval. Facilities is deliberately left out because this ticket has nothing to do with the shop lease.
* Expected MCP tools: Boss uses `get_ticket`; Inventory uses `check_order_fulfillment` (plus `read_table` on inventory/vendors if needed); Accounting uses `check_available_cash` and `read_table` on invoices, then calls `stage_payment` for Invoice 501 ($840.00), which automatically moves the ticket to awaiting_approval; Customer Service only reads to confirm facts before drafting the reply.
* Expected end state: awaiting_approval (since $840.00 is staged for Invoice 501 and a human has to click approve before cash moves and the ticket resolves).

Ticket 102 (Elm City Properties: $2,400 Chapel Street shop rent, rent_notice):

* Who Boss calls first & why: Boss reads the ticket with `get_ticket` and calls Facilities first because this is a property/lease rent notice for the Chapel Street shop (Lease 1), which falls strictly under Facilities’ scope.
* Handoff chain & who is left out: Boss → Facilities → Accounting, and Accounting’s result returns up the chain to Boss. Facilities checks Lease 1 and confirms the $2,400.00 monthly rent to Elm City Properties is due 2026-09-02 (2 days away from desk.date_today 2026-08-31). Since Facilities cannot touch cash or stage payments, Facilities hands off directly to Accounting (specialist-to-specialist). Accounting checks uncommitted cash ($3,400.00 minus the $840.00 staged for Ticket 101 leaves $2,560.00), confirms we can cover the $2,400.00 rent, and stages the $2,400.00 lease payment. Inventory and Customer Service are both deliberately left out because there is no merchandise or external customer order involved.
* Expected MCP tools: Boss uses `get_ticket`; Facilities calls `check_rent_due` to verify lease terms and due date; Accounting uses `check_available_cash` and calls `stage_payment` for Lease 1 ($2,400.00), which automatically moves the ticket to awaiting_approval.
* Expected end state: awaiting_approval (waiting for a human to approve the $2,400.00 rent payment, which will take uncommitted checking down from $2,560.00 to $160.00).

Ticket 103 (Yale AI Club: 20x CC-HOOD-NAVY size M bulk discount, price_override):

* Who Boss calls first & why: Boss reads the ticket with `get_ticket` and calls Inventory first because before we can quote a bulk discount on 20 navy hoodies, we have to check how many size M hoodies are actually sitting in Aisle A and what the restock math looks like.
* Handoff chain & who is left out: Boss → Inventory → Accounting → Customer Service, and Customer Service’s reply returns up the chain to Boss (not a new handoff, since 3 handoffs is our depth cap). Inventory checks stock and finds only 8 size M hoodies in Aisle A (short by 12 units; restocking 12 from Bulldog Print Co takes 5 lead days and costs 12 × $22.00 = $264.00). Inventory hands off directly to Accounting (specialist-to-specialist) to check our cash position and set the bulk override price. Accounting sees that after Ticket 101 ($840.00) and Ticket 102 ($2,400.00), uncommitted cash is down to $160.00, meaning we cannot stage the $264.00 vendor restock right now without going negative (and if we had run 103 before 102, spending $264.00 would have left $2,296.00 and caused us to miss the $2,400.00 rent!). Accounting sets a profitable bulk discount price per hoodie well above the $22.00 unit cost (down from the $58.00 list price), refuses to stage the $264.00 restock out of shop cash, and hands off directly to Customer Service to pitch the quote to Yale AI Club (deliver the 8 in-stock hoodies now at the discounted rate, and order the remaining 12 with a 5-day lead time once customer payment/deposit clears). Facilities is deliberately left out.
* Expected MCP tools: Boss uses `get_ticket`; Inventory calls `quote_bulk_order` to get stock (8 on hand), unit cost ($22.00), list price ($58.00), and vendor lead days (5 days); Accounting uses `check_available_cash` ($160.00 remaining) and `read_table` on pricing, and calculates the discount without calling `stage_payment`; Boss records the quote and marks the ticket resolved with `update_ticket` (only Boss has it).
* Expected end state: resolved directly (because no shop cash is staged or spent on this run).

## Problem 7

Build the FastAPI server in `backend/main.py` so it starts from the `backend/` folder with `uvicorn main:app --reload --port 8000`, and allow CORS from `http://localhost:5173`. Routes:

1. List the three tickets with their status, plus any pending staged payments.
2. Run the agent team on a ticket id in the background and return right away, so the board can poll while it runs. Refuse a second run while one is already in progress.
3. Return recent agent events from the audit trail (what each agent said and which tools it used), filterable by ticket.
4. Approve a staged payment when a human clicks approve, by calling the backend-only `approve_payment` MCP tool. This is the only route that changes cash.
5. Return the current checking balance and available cash.
6. Reset `data/campus_customs_new.db` to the original by calling the `reset_database` MCP tool, without touching the audit trail.

Every route goes through MCP, never sqlite directly. Test every route except the real agent run (use the scripted test model for that), confirm the database is back to the original afterwards and the audit trail is still `[]`, then add the routes to `output/harness.md` (one line each: method, path, what it does). Log this under Problem 7 in `AI_prompts.md` and commit as “P7”.

## Problem 8

Build the dashboard in `frontend/` with React + Vite + TypeScript, calling the backend at `http://localhost:8000`. Design concept: style it like a vintage-meets-modern “Chapel Street Print Shop & Dispatch Desk”: warm off-white/kraft paper surfaces, crisp dark ink typography, monospace ledger numbers, and tactile work-order ticket cards that look like physical screen-printing job tags clipped to a shop rail. Give the top bar a brass-and-slate ledger strip showing the shop date, live Checking Balance, uncommitted cash (after staged payments), and a Reset DB button. Give each of the 5 agents their own distinct shop-station badge and accent color (e.g., Navy for Boss, Amber/Kraft for Inventory, Emerald Ledger Green for Accounting, Rust/Brick for Facilities, and Royal Blue for Customer Service) so you can immediately tell who is talking and handing off on the floor.
It must:

* list all three tickets with status;
* let me pick one and start the agents;
* show each agent’s messages and tool calls live while it runs (a run takes about a minute, so the progress must be visible), with each agent visually distinct;
* mark the ticket resolved when it finishes (or awaiting_approval until I click Approve when a payment is staged);
* show a short summary of what each agent did;
* show a clear Approve button for any staged payment;
* show the checking balance and available cash, updating after approval;
* include a Reset button;
* read the shop date from `desk.date_today` through the backend (add it to a route if needed), never hard-coded;
* make Approve ask for an “approved by” name, prefilled with Vishal, and send it to the approve route;
* make Reset a button with a confirmation step, not a switch;
* don’t rely on color alone: label each agent badge with its name too.

Make it look designed, not like a stock template. Also update the audit trail so agents’ final answers are stored in full (tool results can stay short) so Customer Service replies and agent summaries never get cut off at 200 characters. Write `output/design.md` explaining the layout, how agents read differently, how resolved tickets and cash show up, and the creative choices behind it.
Test it with the scripted model only, no real run, and make sure `npm run build` passes with no TypeScript errors. Then confirm the database matches the original and the audit trail is `[]`. Log this under Problem 8 in `AI_prompts.md` and commit as “P8”.

## Problem 9

## Problem 10

## Problem 11
