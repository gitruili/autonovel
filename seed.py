#!/usr/bin/env python3
"""
seed.py -- Generate fantasy novel seed concepts.

Usage:
  uv run python seed.py              # Generate 10 concepts, pick one
  uv run python seed.py --count=5    # Generate 5 concepts
  uv run python seed.py --riff "magic costs memories"  # Riff on an idea
"""

import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from llm_client import (
    call_text_model,
    default_model_for_role,
    get_api_key,
    provider_api_key_env,
)

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6-20250217"),
)


def call_writer(prompt, max_tokens=4000):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=1.0,
        system=(
            "You are a fantasy novelist with deep knowledge of the genre's "
            "best works -- Tolkien, Le Guin, Rothfuss, Wolfe, Jemisin, Peake, "
            "Susanna Clarke, Andrew Peterson, Sofia Samatar. You generate "
            "novel concepts that are SPECIFIC, SURPRISING, and STRUCTURALLY "
            "SOUND. You never propose generic medieval Europe + elves. Each "
            "concept should make a reader think 'I've never seen THAT before.'"
        ),
        messages=[{"role": "user", "content": prompt}],
        timeout=720,
        include_beta=True,
    )


GENERATE_PROMPT = """Generate {count} fantasy novel seed concepts. Each should be
a complete premise you could build a novel from.

For EACH concept, provide:

NUMBER. TITLE (a working title, evocative, not generic)
HOOK: One sentence that would make someone pick up the book. Specific
  and surprising, not "In a world where..."
WORLD: What makes this world different? Not just "there's magic" but
  what specific, unusual thing defines this place? Be concrete --
  salt flats, inverted towers, cities that migrate, a sea that
  remembers, whatever. Make it SENSORY.
MAGIC/COST: What is the core speculative element and what does it
  COST? Per Sanderson's Second Law, limitations > powers. The cost
  should create interesting dilemmas.
TENSION: What's the central conflict? It must be both PERSONAL (one
  character's specific problem) and COSMIC (affects the world).
  These two must be in tension with each other.
THEME: What question does this story explore? Not a message -- a
  genuine question with no easy answer.
WHY IT'S NOT GENERIC: One sentence on what makes this different from
  standard fantasy fare.

Aim for DIVERSITY across the {count} concepts:
  - At least one with a non-human-centric world
  - At least one that's more literary/quiet than epic
  - At least one with an unusual narrative structure idea
  - At least one set outside the typical European-inspired setting
  - Mix of tones: dark, warm, weird, melancholy, whimsical

DO NOT generate:
  - Chosen one prophecies (unless subverted in an interesting way)
  - Dark lord / ultimate evil as the main antagonist
  - Medieval Europe + elves/dwarves/orcs
  - "Academy" or "school for magic" settings
  - Love triangles as the central plot
"""

RIFF_PROMPT = """I have a seed idea for a fantasy novel:

"{idea}"

Generate 5 variations on this concept. Keep what's interesting about
the core idea but push it in different directions. For each variation:

NUMBER. TITLE
HOOK: One sentence.
HOW IT DIFFERS: What did you change from the original seed and why?
WORLD: Concrete, sensory world details.
MAGIC/COST: The speculative element and its cost.
TENSION: Personal + cosmic conflict.
THEME: The question it explores.

Make the variations genuinely different from each other -- don't just
tweak surface details. Change the protagonist, the setting, the tone,
the structure, the thematic focus.
"""


def main():
    parser = argparse.ArgumentParser(description="Generate novel seed concepts")
    parser.add_argument("--count", type=int, default=10,
                        help="Number of concepts to generate (default: 10)")
    parser.add_argument("--riff", type=str, default=None,
                        help="Riff on an existing idea")
    args = parser.parse_args()

    if not get_api_key():
        print(f"ERROR: Set {provider_api_key_env()} in .env first")
        sys.exit(1)

    if args.riff:
        print(f"Riffing on: {args.riff}\n")
        prompt = RIFF_PROMPT.format(idea=args.riff)
    else:
        print(f"Generating {args.count} seed concepts...\n")
        prompt = GENERATE_PROMPT.format(count=args.count)

    result = call_writer(prompt, max_tokens=4000)
    print(result)
    print("\n" + "=" * 60)
    print("To pick a seed, copy the concept you like into seed.txt:")
    print("  nano seed.txt")
    print("Or remix several concepts into your own seed.")
    print("Then proceed to Step 2 in WORKFLOW.md.")


if __name__ == "__main__":
    main()
