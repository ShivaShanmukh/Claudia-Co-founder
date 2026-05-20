"""
Prototype Pilot — core agent logic.

Flow: CLARIFY → SCOPE → RISK → BRIEF
Each phase is driven by a phase-specific prompt injected as a user turn,
keeping the conversation history intact for context.

Run directly:
    python -m agent.core "my idea here"
"""

import sys
import io
import os
import anthropic
from dotenv import load_dotenv

# Windows terminals default to cp1252; Claude output contains Unicode.
if hasattr(sys.stdout, "buffer") and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from .prompts import (
    SYSTEM_PROMPT,
    CLARIFY_INTRO,
    SCOPE_INTRO,
    RISK_INTRO,
    BRIEF_INTRO,
)
from .output import extract_brief_markdown, save_brief, format_phase_header

load_dotenv()

MODEL = "claude-3-7-sonnet-latest"
MAX_CLARIFY_ROUNDS = 3  # max back-and-forth before forcing scope transition


def stream_response(client: anthropic.Anthropic, messages: list[dict]) -> str:
    """Stream a response from Claude, printing tokens live. Returns full text."""
    full_text = ""
    with client.messages.stream(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            full_text += text
    print()  # newline after stream ends
    return full_text


def run_phase(
    client: anthropic.Anthropic,
    history: list[dict],
    phase_name: str,
    phase_prompt: str,
    interactive: bool = False,
    max_turns: int = 1,
) -> list[dict]:
    """
    Run one phase of the conversation.

    If interactive=True, loop for up to max_turns collecting user replies.
    The phase_prompt is injected as a hidden system nudge (assistant-side instruction).
    """
    print(format_phase_header(phase_name))

    # Inject phase direction as a user message so Claude knows what mode it's in
    history.append({"role": "user", "content": phase_prompt})
    response = stream_response(client, history)
    history.append({"role": "assistant", "content": response})

    if not interactive:
        return history

    # Interactive loop — collect user replies until max_turns
    turns = 0
    while turns < max_turns:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue

        if user_input.lower() in ("done", "skip", "next", "q"):
            break

        history.append({"role": "user", "content": user_input})
        response = stream_response(client, history)
        history.append({"role": "assistant", "content": response})
        turns += 1

    return history


def run_agent(idea: str) -> str:
    """
    Run the full 4-phase agent on an idea string.
    Returns the filepath of the saved brief.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key."
        )

    client = anthropic.Anthropic(api_key=api_key)

    print(f"\nPrototype Pilot — co-founder mode\n")
    print(f'Idea: "{idea}"\n')

    # Seed conversation with the user's raw idea
    history: list[dict] = [
        {"role": "user", "content": f"Here's my idea: {idea}"}
    ]

    # ── Phase 1: CLARIFY ──────────────────────────────────────────────────────
    history = run_phase(
        client, history,
        phase_name="PHASE 1 — CLARIFY",
        phase_prompt=CLARIFY_INTRO,
        interactive=True,
        max_turns=MAX_CLARIFY_ROUNDS,
    )

    # ── Phase 2: SCOPE ────────────────────────────────────────────────────────
    history = run_phase(
        client, history,
        phase_name="PHASE 2 — SCOPE",
        phase_prompt=SCOPE_INTRO,
        interactive=False,
    )

    # ── Phase 3: RISK ─────────────────────────────────────────────────────────
    history = run_phase(
        client, history,
        phase_name="PHASE 3 — RISK",
        phase_prompt=RISK_INTRO,
        interactive=False,
    )

    # ── Phase 4: BRIEF ────────────────────────────────────────────────────────
    history = run_phase(
        client, history,
        phase_name="PHASE 4 — BUILD BRIEF",
        phase_prompt=BRIEF_INTRO,
        interactive=False,
    )

    # Extract and save
    brief_md = extract_brief_markdown(history)
    if not brief_md:
        # Fallback: save full last assistant message
        for msg in reversed(history):
            if msg["role"] == "assistant":
                brief_md = msg["content"]
                break

    filepath = save_brief(brief_md, idea)
    print(f"\n✓ Brief saved to: {filepath}\n")
    return filepath


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m agent.core \"your idea here\"")
        print("       python -m agent.core  (interactive mode — prompts for idea)")
        idea = input("\nWhat's your idea? ").strip()
        if not idea:
            sys.exit(1)
    else:
        idea = " ".join(sys.argv[1:])

    run_agent(idea)


if __name__ == "__main__":
    main()
