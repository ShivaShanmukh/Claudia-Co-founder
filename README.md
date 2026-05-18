# Prototype Pilot

A Claude-powered co-founder agent that takes a raw product idea and outputs a structured build brief.

## What it does

Runs a 4-phase conversation with your idea:

1. **Clarify** — asks 2-3 sharp questions about the user, core action, and success metric
2. **Scope** — defines the smallest shippable MVP with explicit in/out decisions
3. **Risk** — identifies the single riskiest assumption and a cheap way to test it
4. **Brief** — produces a concrete markdown build brief: stack, folder structure, first 3 tasks, definition of done

Output is saved as a `.md` file in `/briefs`.

---

## Setup

```bash
cd prototype-pilot
pip install -r requirements.txt
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
```

---

## Phase 1 — CLI Agent

```bash
# Run with idea as argument
python -m agent.core "An app that helps freelancers track client payments and send reminders automatically"

# Or interactive mode (prompts for idea)
python -m agent.core
```

The agent runs the full 4-phase flow interactively in your terminal. During CLARIFY, you can answer questions or type `next`/`skip` to move on. Phases 2-4 run automatically. Brief is saved to `/briefs`.

---

## Phase 2 — MCP Server

Wraps the agent as an MCP tool for use in Claude Desktop.

```bash
python -m mcp_server.server
```

**Claude Desktop config** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "prototype-pilot": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/absolute/path/to/prototype-pilot",
      "env": { "ANTHROPIC_API_KEY": "your_key_here" }
    }
  }
}
```

Tool exposed: `generate_prototype_brief(idea: str) -> str`

---

## Phase 3 — Web Frontend

**Backend (FastAPI):**
```bash
uvicorn api.main:app --reload --port 8000
```

**Frontend (Next.js):**
```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:3000
```

Endpoints:
- `POST /brief` — full brief as JSON (non-streaming)
- `POST /brief/stream` — SSE streaming, tokens arrive live
- `GET /health` — health check

---

## Project structure

```
prototype-pilot/
├── agent/
│   ├── core.py       # 4-phase agent loop, CLI entry point
│   ├── prompts.py    # all system + phase prompts
│   └── output.py     # markdown extraction, file saving
├── mcp_server/
│   └── server.py     # MCP stdio server, exposes generate_prototype_brief tool
├── api/
│   └── main.py       # FastAPI app, /brief and /brief/stream endpoints
├── frontend/
│   └── src/app/page.tsx  # single-page Next.js UI
├── briefs/           # generated build briefs land here
├── .env.example
├── requirements.txt
└── README.md
```

---

## Design decisions

- **Streaming everywhere** — the CLI, API, and frontend all stream tokens so output feels live rather than waiting for a full response.
- **Phase prompts as injected user turns** — each phase transition is driven by appending a directive to the conversation history rather than changing the system prompt. This keeps the full context intact and lets Claude reason across phases.
- **MCP server runs non-interactively** — when called as an MCP tool, the agent auto-answers its own clarifying questions with "make reasonable assumptions" so it can complete without stdin.
- **No database, no auth** — the frontend is dead simple by design. Briefs are `.md` files on disk. Add persistence only when you need it.
- **Model: claude-sonnet-4-20250514** — good balance of reasoning quality and speed for this use case.
