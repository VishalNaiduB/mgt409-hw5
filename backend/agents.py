"""The 5 Campus Customs agents: Boss, Inventory, Accounting, Facilities, Customer Service.

All 5 share one stdio MCP connection to mcp_server/server.py, so every shop fact
comes through the MCP protocol; nothing here touches SQLite or imports the
server. This PydanticAI version (2.56) replaced MCPServerStdio with MCPToolset,
so MCP_SERVER is a single MCPToolset over a FastMCP stdio transport.

Roles are enforced in code, not just in the prompts: each agent gets its own
filtered view of the one MCP connection, holding the shared read tools plus its
role's tools (stage_payment for Accounting only, update_ticket for Boss only).
Only tools the server tags "agent" can pass the filter, so the backend-only
tools (approve_payment, reset_database) never reach any agent. Every agent can
delegate to each of the other four, with a depth cap of 3 across the whole
handoff chain and UsageLimits(request_limit=35) shared by every agent in a run.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, get_args

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.mcp import CallToolFunc, MCPToolset
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import RunUsage, UsageLimits

from backend.llm import PROJECT_ROOT, build_model
from backend.models import MAX_DELEGATION_DEPTH, AgentHandoff, AgentName, AgentResponse, AuditEntry

PROMPTS_DIR = PROJECT_ROOT / "backend" / "prompts"
USAGE_LIMITS = UsageLimits(request_limit=35)
BACKEND_ONLY_TOOLS = frozenset({"approve_payment", "reset_database"})

AGENT_NAMES: tuple[AgentName, ...] = get_args(AgentName)

# MCP tools every agent may use: read-only views of tickets, tables, cash and payments.
READ_TOOLS = frozenset({"get_ticket", "list_tickets", "list_tables", "read_table", "check_available_cash", "list_payments"})
# MCP tools only one role may use, on top of READ_TOOLS.
ROLE_TOOLS: dict[AgentName, frozenset[str]] = {
    "Boss": frozenset({"update_ticket"}),
    "Inventory": frozenset({"check_order_fulfillment", "quote_bulk_order"}),
    "Accounting": frozenset({"stage_payment"}),
    "Facilities": frozenset({"check_rent_due"}),
    "Customer Service": frozenset(),
}
ALLOWED_MCP_TOOLS: dict[AgentName, frozenset[str]] = {
    name: (READ_TOOLS | ROLE_TOOLS[name]) - BACKEND_ONLY_TOOLS for name in AGENT_NAMES
}
PROMPT_FILES: dict[AgentName, str] = {
    "Boss": "boss.md",
    "Inventory": "inventory.md",
    "Accounting": "accounting.md",
    "Facilities": "facilities.md",
    "Customer Service": "customer_service.md",
}


@dataclass
class ShopDeps:
    """Per-agent run state. `audit` is shared by every agent in one ticket run."""

    ticket_id: int
    agent: AgentName
    depth: int = 0
    chain: list[AgentName] = field(default_factory=list)
    handoffs: list[AgentHandoff] = field(default_factory=list)
    audit: list[AuditEntry] = field(default_factory=list)


async def _audit_tool_call(
    ctx: RunContext[Any], call_tool: CallToolFunc, name: str, tool_args: dict[str, Any]
) -> Any:
    """Record each agent MCP tool call, and refuse any tool outside the calling agent's role.

    The per-agent filters already hide those tools; this is a second check at call time.
    """
    deps = ctx.deps
    if isinstance(deps, ShopDeps):
        if name in BACKEND_ONLY_TOOLS:
            return {"error": f"'{name}' is a backend-only tool; agents can't call it."}
        if name not in ALLOWED_MCP_TOOLS[deps.agent]:
            return {"error": f"'{name}' is not one of the {deps.agent} agent's tools."}
        deps.audit.append(
            AuditEntry(
                actor=deps.agent,
                action="stage_payment" if name == "stage_payment" else "tool_call",
                ticket_id=deps.ticket_id,
                tool=name,
                depth=deps.depth,
                detail={"args": tool_args},
            )
        )
    return await call_tool(name, tool_args)


# The one MCP connection every agent (and later the backend) shares.
MCP_SERVER = MCPToolset(
    Client(
        StdioTransport(
            command=str(PROJECT_ROOT / ".venv" / "bin" / "python"),
            args=[str(PROJECT_ROOT / "mcp_server" / "server.py")],
            cwd=str(PROJECT_ROOT),
        )
    ),
    process_tool_call=_audit_tool_call,
)


def _is_agent_tool(tool_def: ToolDefinition) -> bool:
    """True for tools the server tags "agent"; never true for a backend-only tool."""
    meta = (tool_def.metadata or {}).get("meta") or {}
    tags = (meta.get("fastmcp") or {}).get("tags") or []
    return "agent" in tags and tool_def.name not in BACKEND_ONLY_TOOLS


def _role_toolset(name: AgentName):
    """This agent's filtered view of the shared MCP connection."""
    allowed = ALLOWED_MCP_TOOLS[name]
    return MCP_SERVER.filtered(lambda ctx, tool_def: _is_agent_tool(tool_def) and tool_def.name in allowed)


def _slug(name: AgentName) -> str:
    return name.lower().replace(" ", "_")


def _finalize(output: AgentResponse, deps: ShopDeps) -> AgentResponse:
    """Stamp who answered and the handoffs that really happened, rather than trusting the model."""
    return output.model_copy(update={"agent": deps.agent, "ticket_id": deps.ticket_id, "handoffs": deps.handoffs})


def _delegate_tool(target: AgentName) -> Tool[ShopDeps]:
    async def delegate(ctx: RunContext[ShopDeps], task: str) -> str:
        deps = ctx.deps
        if deps.depth >= MAX_DELEGATION_DEPTH:
            return (
                f"Handoff refused: the chain {' -> '.join(deps.chain)} already has {MAX_DELEGATION_DEPTH} "
                "handoffs, the cap. Finish with the facts you have."
            )
        handoff = AgentHandoff(
            from_agent=deps.agent, to_agent=target, ticket_id=deps.ticket_id, task=task, depth=deps.depth + 1
        )
        deps.handoffs.append(handoff)
        deps.audit.append(
            AuditEntry(
                actor=deps.agent,
                action="handoff",
                ticket_id=deps.ticket_id,
                depth=handoff.depth,
                detail=handoff.model_dump(),
            )
        )
        child = ShopDeps(
            ticket_id=deps.ticket_id,
            agent=target,
            depth=handoff.depth,
            chain=[*deps.chain, target],
            audit=deps.audit,
        )
        result = await AGENTS[target].run(
            f"Ticket {deps.ticket_id}. Handoff {handoff.depth} of at most {MAX_DELEGATION_DEPTH}, "
            f"from {deps.agent}: {task}",
            deps=child,
            usage=ctx.usage,
            usage_limits=USAGE_LIMITS,
        )
        response = _finalize(result.output, child)
        deps.audit.append(
            AuditEntry(
                actor=target,
                action="response",
                ticket_id=deps.ticket_id,
                depth=child.depth,
                detail=response.model_dump(),
            )
        )
        return response.model_dump_json()

    return Tool(
        delegate,
        name=f"delegate_to_{_slug(target)}",
        description=(
            f"Hand this ticket to the {target} agent with a specific task, and get its report back. "
            f"The whole handoff chain is capped at {MAX_DELEGATION_DEPTH}."
        ),
    )


def _build_agent(name: AgentName, model) -> Agent[ShopDeps, AgentResponse]:
    return Agent(
        model,
        name=name,
        instructions=(PROMPTS_DIR / PROMPT_FILES[name]).read_text(),
        deps_type=ShopDeps,
        output_type=AgentResponse,
        toolsets=[_role_toolset(name)],
        tools=[_delegate_tool(other) for other in AGENT_NAMES if other != name],
    )


_MODEL = build_model()
AGENTS: dict[AgentName, Agent[ShopDeps, AgentResponse]] = {name: _build_agent(name, _MODEL) for name in AGENT_NAMES}


async def run_ticket(ticket_id: int) -> tuple[AgentResponse, list[AuditEntry]]:
    """Run one ticket through Boss, who routes it to the specialists."""
    deps = ShopDeps(ticket_id=ticket_id, agent="Boss", chain=["Boss"])
    async with MCP_SERVER:
        result = await AGENTS["Boss"].run(f"Handle ticket {ticket_id}.", deps=deps, usage_limits=USAGE_LIMITS)
    return _finalize(result.output, deps), deps.audit


async def agent_tool_names() -> dict[AgentName, list[str]]:
    """Every tool each agent can call, as the model would see them (MCP tools after filtering)."""
    names: dict[AgentName, list[str]] = {}
    async with MCP_SERVER:
        for agent_name, agent in AGENTS.items():
            ctx = RunContext(deps=ShopDeps(ticket_id=0, agent=agent_name), model=agent.model, usage=RunUsage())
            tools: list[str] = []
            for toolset in agent.toolsets:
                tools.extend((await toolset.get_tools(ctx)).keys())
            names[agent_name] = tools
    return names


if __name__ == "__main__":
    for agent_name, tools in asyncio.run(agent_tool_names()).items():
        print(f"{agent_name}: {', '.join(tools)}")
