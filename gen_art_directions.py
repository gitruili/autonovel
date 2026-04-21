#!/usr/bin/env python3
"""
Generate diverse art direction concepts from a novel's visual style.
Called by gen_art.py curate to produce genuinely different variants.
"""
import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6"),
)


def call_claude(prompt, max_tokens=3000):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.9,
        messages=[{"role": "user", "content": prompt}],
        timeout=120,
    )


def generate_directions(art_type, style, n=6, world_excerpt=""):
    """Generate N fundamentally different art direction prompts."""

    if art_type == "cover":
        task = f"""You are an art director generating {n} RADICALLY DIFFERENT cover concepts for a fantasy novel.

The novel's visual style brief:
  Style: {style.get('art_style', '')}
  Palette: {style.get('color_palette', '')}
  Mood: {style.get('mood', '')}
  Reference artists: {style.get('reference_artists', '')}
  Original cover concept: {style.get('cover_concept', '')}

Generate {n} cover art prompts that are FUNDAMENTALLY DIFFERENT from each other.
They should explore different:
  - Levels of abstraction (photorealistic → pure abstract)
  - Composition approaches (single figure → landscape → close-up detail → typographic → symbolic)
  - Art media (oil painting → woodcut → ink wash → digital → collage → linocut)
  - Subject matter (character → object → place → concept → texture)
  - Color approaches (full palette → monochrome → limited palette → high contrast)

DO NOT just vary the same concept. Each should look like it came from a DIFFERENT designer.

Examples of the range I want:
  Direction 1: "Abstract — a single bronze bell cross-section rendered as a geological diagram, layers of metal shown like strata, the sound wave visible as concentric rings. Monochrome with one warm accent. Linocut style."
  Direction 2: "Figurative — a boy's hands on a workbench, seen from above. Bronze filings, a pitch-gauge, a letter half-unfolded. Photorealistic, shallow depth of field. Warm lamplight."
  Direction 3: "Typographic — the title constructed from overlapping sound waves, the letterforms vibrating. Pure geometry. Black on cream."
  Direction 4: "Atmospheric — a limestone bowl city seen from the rim at dawn, tiny and detailed, the bell tower as the only vertical element. Watercolor. Pale gold and gray."

Output a JSON array of {n} objects, each with:
  "direction": one-word label (e.g. "abstract", "figurative", "atmospheric")
  "concept": one sentence describing the image
  "medium": the art medium/technique
  "prompt": the FULL image generation prompt (detailed, specific, 2-3 sentences)

JSON array only."""

    elif art_type == "ornament":
        task = f"""You are a book designer generating {n} RADICALLY DIFFERENT chapter ornament styles for a fantasy novel.

The novel's visual style:
  Style: {style.get('art_style', '')}
  Ornament concept: {style.get('ornament_concept', '')}

Generate {n} ornament style directions that are FUNDAMENTALLY DIFFERENT:
  - Abstract geometric → figurative symbolic → minimal line → detailed engraving
  - Single motif vs changing per chapter
  - Monochrome vs colored
  - Realistic rendering vs pure black-and-white vs stipple vs woodcut

Each prompt should describe a SMALL, CENTERED ornamental image suitable as a chapter header on a white page. Max 2 inches wide.

Output a JSON array of {n} objects with: direction, concept, medium, prompt

JSON array only."""

    elif art_type == "map":
        task = f"""You are a cartographer generating {n} RADICALLY DIFFERENT fantasy map styles.

The world geography:
{world_excerpt[:2000]}

Visual style: {style.get('art_style', '')}
Map concept: {style.get('map_concept', '')}

Generate {n} map prompts that are FUNDAMENTALLY DIFFERENT:
  - Traditional parchment fantasy map vs acoustic/scientific diagram vs birds-eye illustration
  - Labeled vs unlabeled vs symbolically coded
  - Full color vs sepia vs black and white
  - Detailed vs schematic vs impressionistic

CRITICAL: Each prompt must reference these SPECIFIC locations from the world:
{world_excerpt[:500]}

Output a JSON array of {n} objects with: direction, concept, medium, prompt

JSON array only."""

    elif art_type == "scene-break":
        task = f"""You are a typographer generating {n} RADICALLY DIFFERENT scene break decorations for a book.

Visual style: {style.get('art_style', '')}
Scene break concept: {style.get('scene_break_concept', '')}

Each should be a SMALL horizontal decorative element. Think printer's ornaments, fleurons, dingbats.
Some should be abstract, some symbolic, some minimal, some ornate.

Output a JSON array of {n} objects with: direction, concept, medium, prompt

JSON array only."""

    else:
        raise ValueError(f"Unknown art type: {art_type}")

    result = call_claude(task)
    text = result.strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)

    return json.loads(text)


if __name__ == "__main__":
    import sys
    style_file = BASE_DIR / "art" / "visual_style.json"
    if not style_file.exists():
        print("Run gen_art.py style first")
        sys.exit(1)
    style = json.loads(style_file.read_text())
    
    art_type = sys.argv[1] if len(sys.argv) > 1 else "cover"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    
    world = ""
    if (BASE_DIR / "world.md").exists():
        world = (BASE_DIR / "world.md").read_text()[:3000]
    
    directions = generate_directions(art_type, style, n, world)
    for i, d in enumerate(directions, 1):
        print(f"\n--- Direction {i}: {d['direction'].upper()} ---")
        print(f"  Concept: {d['concept']}")
        print(f"  Medium:  {d['medium']}")
        print(f"  Prompt:  {d['prompt'][:150]}...")
