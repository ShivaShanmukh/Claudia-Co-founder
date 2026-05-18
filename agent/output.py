import os
import re
from datetime import datetime


def extract_brief_markdown(conversation_history: list[dict]) -> str:
    """Pull the final build brief from conversation history."""
    for msg in reversed(conversation_history):
        if msg["role"] == "assistant" and "# Build Brief:" in msg["content"]:
            # Extract from "# Build Brief:" onward
            idx = msg["content"].index("# Build Brief:")
            return msg["content"][idx:]
    return ""


def save_brief(brief_text: str, idea: str) -> str:
    """Save brief markdown to /briefs folder. Returns the file path."""
    briefs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "briefs")
    os.makedirs(briefs_dir, exist_ok=True)

    # Slug from first 5 words of idea
    slug = re.sub(r"[^a-z0-9]+", "-", idea.lower().strip())
    slug = "-".join(slug.split("-")[:5]).strip("-")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}-{slug}.md"
    filepath = os.path.join(briefs_dir, filename)

    # Add metadata header
    header = f"""---
idea: {idea}
generated: {datetime.now().isoformat()}
---

"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header + brief_text)

    return filepath


def format_phase_header(phase: str) -> str:
    """Print a visible phase separator to the console."""
    width = 60
    line = "-" * width
    return f"\n{line}\n  {phase}\n{line}\n"
