# Design: Chapel Street Print Shop & Dispatch Desk

The dashboard in `frontend/` (React + Vite + TypeScript) is the desk where you watch the five agents work a ticket and where you, the human, approve money. The design idea is a real print shop's back room: work orders hang as job tags on a rail, the agents are stations on the shop floor, and the cash sits in a brass-and-slate ledger strip across the top. Every number on screen comes from the backend (`http://localhost:8000`), which reads the shop database only through the MCP tools.

## Layout

Top to bottom:

1. **Ledger strip (top bar).** A slate bar with a brass rule under it, laid out like a ledger line. It has four parts:
   - the shop name;
   - **Shop date**, read from `desk.date_today` through `GET /tickets` (never hard-coded or taken from the computer's clock);
   - **Checking balance**, the cash actually on hand;
   - **Uncommitted cash**, the balance minus staged payments, with a note saying how much is staged. This cell is lit brass because it's the number agents have to respect.

   The **Reset DB** button sits at the right end.
2. **Work orders on the rail.** A legend of the five station badges, then a steel rail with the three tickets hanging from it on strings as kraft-paper job tags. Each tag shows:
   - the ticket type, a large "Job No." and the requester;
   - the item in monospace;
   - a status stamp at the bottom, below a dashed perforation;
   - when relevant, "On the floor" while agents work it, and the staged amount once a payment is staged.

   Click a tag to select it. It straightens, lifts and gets an ink outline.
3. **Workspace** for the selected job, in two columns:
   - **Dispatch floor** (left, wide): the live feed of everything the agents do on this job.
   - **Work order** (right): requester, job line and notes, the **Start agents** button, and a run-progress panel while it runs.
   - **Payments awaiting approval** (right, below): one voucher per staged payment, each with a clear Approve button.
4. **What each station did.** One report card per agent that took part, in handoff order, listing the tools it used, who it handed to, and its final answer in full.

On narrow screens:
- the ledger cells wrap under the shop name;
- the tags stack;
- the work order and payments move *above* the feed, so Start and Approve are reached without scrolling past a long log.

## How the agents read differently

Each agent is a **station** with its own badge: a pill holding an icon, the agent's name and its station name. Colour helps, but the name is always printed, so nothing depends on colour alone.

| Agent | Station | Accent | Icon |
|---|---|---|---|
| Boss | Front Desk | Navy | Counter bell |
| Inventory | Stock Room | Amber/kraft | Shipping box |
| Accounting | Ledger Desk | Emerald ledger green | Ledger book |
| Facilities | Building & Lease | Rust/brick | Shopfront |
| Customer Service | Pickup Counter | Royal blue | Speech slip |

On the dispatch floor, every step is a row with a thick left edge in that station's colour and its badge at the start, so you can scan down the colour and see who is talking. There are three kinds of row:
- **Handoff slips.** "Boss *hands off to* Inventory", with the task written on a lined "Job slip". A handoff refused at the depth cap gets a dashed edge and the refusal shown in red.
- **Tool calls.** "Inventory *calls* `check_order_fulfillment(ticket_id=101)`", with the tool's short result printed below in monospace. A call still in progress shows "waiting for the tool…".
- **Reports.** "Customer Service *reports back*", with the agent's final answer in full on a faint tint of its colour.

While a run is live, the work order's progress panel shows:
- a red pulse and the elapsed seconds;
- the handoff depth out of 3;
- a striped meter of requests used out of 35;
- the handoff chain drawn as linked badges, with the station currently working glowing.

The feed polls every second, follows new steps inside its own scroll area, and never scrolls the page away from you.

## How resolved tickets and cash show up

- **Status stamps.** Statuses look like rubber stamps, in monospace capitals and slightly crooked:
  - `OPEN`: plain ink.
  - `AWAITING APPROVAL`: dashed amber.
  - `RESOLVED`: heavy green.
  - `ESCALATED`: red.

  The same stamp appears on the rail tag and in the work order, so the rail alone tells you where all three jobs stand.
- **When a run finishes,** the progress panel reads "Run finished · ticket awaiting approval" or "Run finished · ticket resolved". The ticket's status comes from the database, so it is resolved only if Boss resolved it or a human approved its payment. A job whose payment is staged stays awaiting approval until you click Approve.
- **Staged payments** appear as vouchers in an amber frame with notched sides. Each shows the voucher number, the amount in large monospace, what it pays (invoice or lease) and for which job. **Approve** opens a slip dialog: the "Approved by" field is prefilled with **Vishal** and can be edited, and the name is sent to `POST /payments/{id}/approve`. On success:
  - the voucher disappears;
  - the tag's stamp turns to RESOLVED;
  - in the ledger strip, the checking balance drops by the amount, and uncommitted cash shows nothing staged.
- **Reset DB** is a button, not a switch, and it always asks first. A confirmation slip explains what happens:
  - every job goes back to open;
  - payments are cleared;
  - checking returns to its starting balance;
  - the audit trail is kept.

  Nothing happens until you confirm "Yes, reset the database". Reset (and starting another job) is disabled while a run is on the floor, because the backend allows one run at a time.

## Creative choices

- **Print-shop materials, not dashboard chrome.** The surfaces are paper:
  - a warm off-white page with a faint woven grain;
  - kraft tags with diagonal fibre texture and a reinforced punch hole;
  - lined handoff slips;
  - notched payment vouchers.

  Brass and slate are kept for the one place that handles money, the ledger strip, so it reads as the till.
- **Type that matches the trade.** *Fraunces*, an old-style serif with a soft wedge, sets the shop name, job numbers and card titles like a letterpress sign. *IBM Plex Sans* covers the working text, and *IBM Plex Mono* sets every figure: balances, amounts, SKUs, tool calls and results. Numbers use tabular figures so dollar amounts line up like a ledger.
- **Tags hang slightly crooked** (each tilted by a different fraction of a degree) and straighten when selected. It is a small physical cue that one job is "pulled off the rail" and on the bench.
- **One accent per station, on a neutral base.** The page is ink and paper, so the five station colours stand out and stay meaningful. They're darkened enough for white label text, and every badge carries the agent's name.
- **Honest numbers only.** The dashboard never invents a figure. The shop date, balances, statuses and payments all come from the backend's MCP routes, and the agent text comes from the audit trail, where final answers are now stored in full so a Customer Service reply is never cut off.
- **Accessible by default.**
  - Real buttons, with `aria-pressed` on the tags.
  - Native modal dialogs for approve and reset (focus trapped, Escape to cancel).
  - Visible focus rings and polite live updates for run progress.
  - Animation turned off for anyone who prefers reduced motion.
