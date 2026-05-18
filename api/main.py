"""
FastAPI backend for Prototype Pilot.

Endpoints:
  POST /brief        — non-streaming, returns full brief JSON
  POST /brief/stream — SSE streaming, sends tokens as they arrive

Run:
    uvicorn api.main:app --reload --port 8000
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import anthropic
from dotenv import load_dotenv

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

app = FastAPI(title="Prototype Pilot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://frontend-production-a0d53.up.railway.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class IdeaRequest(BaseModel):
    idea: str


def get_api_key() -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
    return key


# ── Non-streaming endpoint ────────────────────────────────────────────────────

async def _call_async(client: anthropic.AsyncAnthropic, messages: list[dict]) -> str:
    """Single async Claude call, returns full text."""
    msg = await client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return msg.content[0].text


async def build_full_history_async(idea: str) -> list[dict]:
    client = anthropic.AsyncAnthropic(api_key=get_api_key())
    history: list[dict] = [{"role": "user", "content": f"Here's my idea: {idea}"}]

    # CLARIFY
    history.append({"role": "user", "content": CLARIFY_INTRO})
    history.append({"role": "assistant", "content": await _call_async(client, history)})
    history.append({
        "role": "user",
        "content": "Make reasonable assumptions and proceed to scoping. No more questions.",
    })
    history.append({"role": "assistant", "content": await _call_async(client, history)})

    # SCOPE
    history.append({"role": "user", "content": SCOPE_INTRO})
    history.append({"role": "assistant", "content": await _call_async(client, history)})

    # RISK
    history.append({"role": "user", "content": RISK_INTRO})
    history.append({"role": "assistant", "content": await _call_async(client, history)})

    # BRIEF
    history.append({"role": "user", "content": BRIEF_INTRO})
    history.append({"role": "assistant", "content": await _call_async(client, history)})

    return history


@app.post("/brief")
async def generate_brief(req: IdeaRequest):
    """Non-streaming: runs all phases, returns completed brief as JSON."""
    if not req.idea.strip():
        raise HTTPException(status_code=400, detail="idea cannot be empty")

    history = await build_full_history_async(req.idea)

    brief_md = extract_brief_markdown(history)
    if not brief_md:
        for msg in reversed(history):
            if msg["role"] == "assistant":
                brief_md = msg["content"]
                break

    filepath = await asyncio.to_thread(save_brief, brief_md, req.idea)
    return {"brief": brief_md, "filepath": filepath}


# ── Streaming endpoint ────────────────────────────────────────────────────────

PHASES = [
    ("CLARIFY", CLARIFY_INTRO),
    ("AUTO_REPLY", "Make reasonable assumptions and proceed. No more questions."),
    ("SCOPE", SCOPE_INTRO),
    ("RISK", RISK_INTRO),
    ("BRIEF", BRIEF_INTRO),
]


@app.post("/brief/stream")
async def stream_brief(req: IdeaRequest):
    """
    SSE streaming endpoint. Uses AsyncAnthropic so tokens flush immediately.
    Frontend reads this as a fetch() stream.
    """
    if not req.idea.strip():
        raise HTTPException(status_code=400, detail="idea cannot be empty")

    api_key = get_api_key()

    async def event_generator():
        try:
            client = anthropic.AsyncAnthropic(api_key=api_key)
            history: list[dict] = [
                {"role": "user", "content": f"Here's my idea: {req.idea}"}
            ]

            for phase_name, phase_prompt in PHASES:
                history.append({"role": "user", "content": phase_prompt})
                yield f"data: [PHASE:{phase_name}]\n\n"

                full_text = ""
                async with client.messages.stream(
                    model=MODEL,
                    max_tokens=2048,
                    system=SYSTEM_PROMPT,
                    messages=history,
                ) as stream:
                    async for token in stream.text_stream:
                        full_text += token
                        escaped = token.replace("\n", "\\n")
                        yield f"data: {escaped}\n\n"

                history.append({"role": "assistant", "content": full_text})

            brief_md = extract_brief_markdown(history)
            if not brief_md:
                brief_md = history[-1]["content"]

            filepath = await asyncio.to_thread(save_brief, brief_md, req.idea)
            yield f"data: [SAVED:{filepath}]\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: ERROR: {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}
