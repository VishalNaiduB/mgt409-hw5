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

## Problem 6

## Problem 7

## Problem 8

## Problem 9

## Problem 10

## Problem 11
