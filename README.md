# Campus Customs: multi-agent dispatch desk

MGT 409 Homework 5. Five PydanticAI agents work the three open tickets at Campus Customs, a campus apparel shop:
- **Boss**, who routes each ticket;
- **Inventory**, **Accounting**, **Facilities** and **Customer Service**, the four specialists.

Every shop fact they use comes from a SQLite database, read through an MCP server. Payments are only *staged* by the agents; a human approves them on the dashboard.

```
React board (frontend/, :5173)  →  FastAPI backend (backend/, :8000)  →  MCP server (mcp_server/, stdio)  →  data/campus_customs_new.db
                                         └─ 5 agents on gpt-6-luna via Portkey
```

The full design, covering tables, tools, agents, routes, the dashboard and the safety rules, is in [`output/harness.md`](output/harness.md).

## Setup

You need Python 3.13 and Node 20 or later.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # then set PORTKEY_API_KEY in .env
cd frontend && npm install && cd ..
```

The backend reads `PORTKEY_API_KEY` from `.env` in the project root (or from the parent folder's `.env`). `.env` is git-ignored; never commit it.

## The database

`data/campus_customs.db` is the original, read-only source. The agents and the backend only work on the copy, `data/campus_customs_new.db`. For a clean run, copy the original over the working file:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

> **Note:** the committed `data/campus_customs_new.db` holds the **post-run state**. Checking is at $160.00, all three tickets are resolved, and both payments are approved by Vishal. That matches the files in `output/` (`desk_tickets.html`, `resolved_tickets.json`, `resolved_board.html`, `audit_trail.json`). Only reset it if you want a fresh run.

## The MCP server

`mcp_server/server.py` is a FastMCP server with 13 tools: 11 for the agents and 2 backend-only (`approve_payment`, `reset_database`). See [`mcp_server/README.md`](mcp_server/README.md).

- **With the backend:** you don't start it yourself. When the backend starts, it launches the server as a subprocess and talks to it over stdio, through one shared MCP connection.
- **Standalone:** run it from the project root. It speaks MCP over stdio, so it waits for an MCP client on stdin/stdout:

  ```bash
  .venv/bin/python mcp_server/server.py
  ```

  `.mcp.json` registers the same command as `campus-customs`, so Claude Code (or any MCP client that reads `.mcp.json`) can connect to it directly.

## Run the backend

From `backend/`:

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

It serves `http://localhost:8000`, with CORS allowed for the board at `http://localhost:5173`. Routes:

| Route | What it does |
|---|---|
| `GET /tickets` | The tickets, pending payments and the shop date |
| `POST /tickets/{id}/run` | Starts the agents on a ticket in the background |
| `GET /events` | The audit trail |
| `POST /payments/{id}/approve` | Approves a staged payment; the only route that changes cash |
| `GET /cash` | The checking balance and available cash |
| `POST /reset` | Restores the working database from the original |

## Run the board

From `frontend/`, in a second terminal:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. To build a production bundle, run `npm run build`.

## A full three-ticket run

1. **Reset first.** Click **Reset DB** in the board's top bar and confirm, or use one of these:
   ```bash
   cp data/campus_customs.db data/campus_customs_new.db
   ```
   ```bash
   curl -X POST http://localhost:8000/reset
   ```
   Checking goes back to $3,400.00 and all three tickets to `open`. Reset only touches the database; the audit trail in `output/audit_trail.json` is append-only and is kept.
2. **Ticket 101:** select it and click **Start agents**. It goes Boss → Inventory → Accounting → Customer Service, and Accounting stages the $840.00 Invoice 501 payment. **Approve** it; the name is prefilled with Vishal.
3. **Ticket 102:** run it. It goes Boss → Facilities → Accounting and stages the $2,400.00 Lease 1 rent. **Approve** it.
4. **Ticket 103:** run it. Accounting quotes a bulk price and spends nothing, because the $264.00 restock is more than the $160.00 left. Boss resolves the ticket.

Each run takes about a minute. It's limited to 35 model requests and 3 handoffs deep.

## Repository layout

```
.
├── README.md               this file
├── requirements.txt        Python packages
├── .env.example            PORTKEY_API_KEY= (copy to .env)
├── .mcp.json               MCP client config for the campus-customs server
├── AI_prompts.md           every prompt used, by problem
├── data/
│   ├── campus_customs.db       original database (source)
│   └── campus_customs_new.db   working copy (committed in its post-run state)
├── mcp_server/
│   ├── server.py           FastMCP server: 13 tools
│   └── README.md
├── backend/
│   ├── main.py             FastAPI routes
│   ├── agents.py           the 5 agents, role-limited toolsets, delegation
│   ├── llm.py              gpt-6-luna via Portkey (Responses API)
│   ├── models.py           Pydantic models
│   ├── audit.py            append-only audit trail
│   └── prompts/            boss.md, inventory.md, accounting.md, facilities.md, customer_service.md
├── frontend/               React + Vite + TypeScript board
└── output/
    ├── harness.md          tables, MCP tools, agents, routes, dashboard, safety
    ├── desk_tickets.html   Expected vs. Actual per ticket, Cash, Reflection
    ├── resolved_tickets.json
    ├── resolved_board.html screenshots of the board (embedded)
    ├── ticket_101.png, ticket_102.png, ticket_103.png
    ├── audit_trail.json    every agent step of the real runs
    ├── mcp_smoke.json      first MCP tool smoke test
    ├── design.md           dashboard design notes
    └── github_url.txt
```
