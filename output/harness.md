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
| `payments` | `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` | Empty at start; agents only stage payment requests (for invoice 501 and the ticket 102 rent) and never write here, because a human approval is what records the row in `payments` (with `approved_by`) and deducts the amount from `cash_accounts`. |

## MCP tools

Server: `mcp_server/server.py` (FastMCP), reading `data/campus_customs_new.db`. Each tool takes only a `ticket_id` and looks up everything else from `tickets` and its linked rows.

| Tool | Tables read | Unlocks ticket | Why it is the right tool for that ticket |
|---|---|---|---|
| `check_order_fulfillment` | `tickets`, `inventory`, `invoices`, `vendors`, `desk` | 101 | Ticket 101 asks for 1 CC-TEE-WHITE size S, and only this tool puts the 0 units in stock next to linked invoice 501 ($840 to Bulldog Print Co, due 2026-08-28) and the desk date of 2026-08-31, which shows the reprint behind the order is still unpaid and 3 days overdue. |
| `check_rent_due` | `tickets`, `leases`, `desk`, `cash_accounts` | 102 | Ticket 102 is Elm City Properties' rent notice, and this tool follows its `lease_id` to lease 1's $2,400 due 2026-09-02, computes that it is 2 days from the desk date, and shows the $3,400 checking balance would drop to $1,000 after paying it. |
| `quote_bulk_order` | `tickets`, `inventory`, `pricing`, `vendors` | 103 | Ticket 103 is Yale AI Club asking a discount on 20 CC-HOOD-NAVY size M, and this tool shows only 8 are in stock (12 short), the $22 unit cost that sets the discount floor against the $58 list price, and each vendor's lead time for restocking the gap. |
