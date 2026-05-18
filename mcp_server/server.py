"""
MCP server wrapper for Prototype Pilot.

Exposes one tool: generate_prototype_brief(idea: str) -> str

Run via stdio (for Claude Desktop):
    python -m mcp_server.server

Claude Desktop config (claude_desktop_config.json):
    {
      "mcpServers": {
        "prototype-pilot": {
          "command": "python",
          "args": ["-m", "mcp_server.server"],
          "cwd": "/path/to/prototype-pilot"
        }
      }
    }
"""

import asyncio
import os
import sys

# Ensure project root is on path when run as module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from dotenv import load_dotenv

import anthropic
from agent.prompts import (
    SYSTEM_PROMPT,
    CLARIFY_INTRO,
    SCOPE_INTRO,
    RISK_INTRO,
    BRIEF_INTRO,
)
from agent.output import extract_brief_markdown, save_brief

load_dotenv()

MODEL = "claude-sonnet-4-6"

server = Server("prototype-pilot")


async def run_non_interactive_agent(idea: str) -> str:
    """
    Run the full agent flow non-interactively (no stdin).
    Clarify phase uses a single auto-pass — agent asks questions then answers
    them with reasonable defaults based on the idea itself.
    Returns the final brief as markdown text.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    history: list[dict] = [
        {"role": "user", "content": f"Here's my idea: {idea}"}
    ]

    def call(messages: list[dict]) -> str:
        result = ""
        with client.messages.stream(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            result = stream.get_final_text()
        return result

    # CLARIFY — ask questions, then auto-answer them from context
    history.append({"role": "user", "content": CLARIFY_INTRO})
    clarify_q = call(history)
    history.append({"role": "assistant", "content": clarify_q})

    # Auto-respond: tell the agent to proceed with best assumptions
    history.append({
        "role": "user",
        "content": (
            "Make reasonable assumptions based on the idea and proceed. "
            "Don't ask more questions — move straight to scoping."
        ),
    })
    clarify_a = call(history)
    history.append({"role": "assistant", "content": clarify_a})

    # SCOPE
    history.append({"role": "user", "content": SCOPE_INTRO})
    scope = call(history)
    history.append({"role": "assistant", "content": scope})

    # RISK
    history.append({"role": "user", "content": RISK_INTRO})
    risk = call(history)
    history.append({"role": "assistant", "content": risk})

    # BRIEF
    history.append({"role": "user", "content": BRIEF_INTRO})
    brief = call(history)
    history.append({"role": "assistant", "content": brief})

    # Extract brief markdown
    brief_md = extract_brief_markdown(history)
    if not brief_md:
        brief_md = brief  # fallback to raw last response

    filepath = save_brief(brief_md, idea)
    return f"{brief_md}\n\n---\n*Brief saved to: {filepath}*"


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="generate_prototype_brief",
            description=(
                "Takes a product idea in plain English and runs it through a "
                "structured co-founder flow: clarify → scope → risk → brief. "
                "Returns a complete build brief as markdown and saves it to /briefs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "idea": {
                        "type": "string",
                        "description": "The product idea to evaluate, in plain English.",
                    }
                },
                "required": ["idea"],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name != "generate_prototype_brief":
        raise ValueError(f"Unknown tool: {name}")

    idea = arguments.get("idea", "").strip()
    if not idea:
        raise ValueError("idea cannot be empty")

    result = await asyncio.to_thread(run_non_interactive_agent, idea)
    return [types.TextContent(type="text", text=result)]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
