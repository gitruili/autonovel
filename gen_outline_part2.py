#!/usr/bin/env python3
"""Generate remaining chapters + foreshadowing ledger."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6"),
)

def call_writer(prompt, max_tokens=16000):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.5,
        system=(
            "You are a novel architect continuing an outline. Write in the same format "
            "as the preceding chapters. Every chapter needs: POV, Location, Save the Cat beat, "
            "% mark, Emotional arc, Try-fail cycle, Beats, Plants, Payoffs, Character movement, "
            "The lie, Word count target."
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=600,
    )

part1 = open('/tmp/outline_output.md').read()
mystery = (BASE_DIR / "MYSTERY.md").read_text()

prompt = f"""Here are the first 17 chapters of a 24-chapter outline for "The Second Son of the House of Bells."
The outline was cut off mid-chapter-17. Continue from where it left off, then complete chapters 18-24,
then write the Foreshadowing Ledger.

THE OUTLINE SO FAR:
{part1}

THE CENTRAL MYSTERY (for reference):
{mystery}

REMAINING STRUCTURE NEEDED:

Ch 17 (complete it): Maret confrontation -- she reveals the truth about the void
Ch 18: Dark Night of the Soul -- Cass processes what he's learned
Ch 19: Break Into Three -- new information or perspective changes everything  
Ch 20-21: Gathering forces, making a plan
Ch 22: The climax at the Bell Tower -- Cass answers the question
Ch 23: Aftermath and resolution
Ch 24: Final Image (mirror of Opening Image)

Then write:

## Foreshadowing Ledger

| # | Thread | Planted (Ch) | Reinforced (Ch) | Payoff (Ch) | Type |
|---|--------|-------------|-----------------|-------------|------|

Include at LEAST 15 threads. Types: object, dialogue, action, symbolic, structural.
Plant-to-payoff distance must be at least 3 chapters.

REMEMBER:
- The climax uses the fourth option: Cass amplifies the question into audible range
  so the city can hear and answer for themselves
- This doesn't free Perin directly (Stability Trap -- not everything resolves cleanly)
- Cass's lie must be fully shattered by the climax
- Final Image should mirror Ch 1's Opening Image but show transformation
- At least one quiet chapter in the back half
"""

print("Calling writer model...", file=sys.stderr)
result = call_writer(prompt)
print(result)
