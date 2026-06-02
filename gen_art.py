#!/usr/bin/env python3
"""
Generate novel art via Nano Banana 2 (fal.ai).

Curation workflow (human-in-the-loop):
  python gen_art.py style                    # Derive visual style from world + voice
  python gen_art.py curate cover --n=4       # Generate 4 cover variants, pick one
  python gen_art.py curate ornament --n=4    # Generate 4 ornament style variants
  python gen_art.py pick cover 2             # Select variant #2 as final
  python gen_art.py pick ornament 3          # Select variant #3 as ornament reference

Batch generation (after picking reference style):
  python gen_art.py ornaments-all            # Generate all chapter ornaments from reference
  python gen_art.py scene-break              # Generate scene break decoration
  python gen_art.py curate map --n=3         # Generate 3 map variants (lore-grounded)

Post-processing:
  python gen_art.py vectorize                # Convert ornaments + scene-break to SVG
  python gen_art.py vectorize ornament_ch01  # Vectorize a single image

Full pipeline:
  python gen_art.py all                      # style → curate → batch → vectorize
"""
import os
import sys
import json
import re
import time
import shutil
import argparse
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from llm_client import call_text_model, default_model_for_role

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)

FAL_KEY = os.environ.get("FAL_KEY", "")
FAL_URL = "https://fal.run/fal-ai/nano-banana-2"
FAL_EDIT_URL = "https://fal.run/fal-ai/nano-banana-2/edit"

ART_DIR = BASE_DIR / "art"
VARIANTS_DIR = ART_DIR / "variants"
SVG_DIR = ART_DIR / "svg"
STYLE_FILE = ART_DIR / "visual_style.json"
PICKS_FILE = ART_DIR / "picks.json"

WRITER_MODEL = os.environ.get(
    "AUTONOVEL_WRITER_MODEL",
    default_model_for_role("writer", "claude-sonnet-4-6"),
)


# ============================================================
# API HELPERS
# ============================================================

def fal_generate(prompt, resolution="1K", aspect_ratio="auto", seed=None):
    import httpx
    payload = {
        "prompt": prompt,
        "num_images": 1,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "output_format": "png",
        "safety_tolerance": "6",
        "limit_generations": True,
        "thinking_level": "high",
    }
    if seed is not None:
        payload["seed"] = seed
    resp = httpx.post(
        FAL_URL,
        headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
        json=payload, timeout=300,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["images"][0]["url"], data.get("description", "")


def fal_edit(prompt, image_urls, resolution="1K", aspect_ratio="1:1", seed=None):
    import httpx
    payload = {
        "prompt": prompt,
        "image_urls": image_urls,
        "num_images": 1,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "output_format": "png",
        "safety_tolerance": "6",
        "limit_generations": True,
        "thinking_level": "high",
    }
    if seed is not None:
        payload["seed"] = seed
    resp = httpx.post(
        FAL_EDIT_URL,
        headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
        json=payload, timeout=300,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["images"][0]["url"], data.get("description", "")


def download_image(url, dest_path):
    import httpx
    resp = httpx.get(url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(resp.content)
    return len(resp.content)


def call_claude(prompt, max_tokens=1500):
    return call_text_model(
        model=WRITER_MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
        timeout=120,
    )


def load_style():
    if not STYLE_FILE.exists():
        print("No visual style found. Run: gen_art.py style")
        sys.exit(1)
    return json.loads(STYLE_FILE.read_text(encoding="utf-8"))


def load_picks():
    if PICKS_FILE.exists():
        return json.loads(PICKS_FILE.read_text(encoding="utf-8"))
    return {}


def save_picks(picks):
    PICKS_FILE.write_text(json.dumps(picks, indent=2, encoding="utf-8"))


def get_reference_url(art_type):
    """Get the URL of the picked reference image for a type."""
    picks = load_picks()
    if art_type in picks:
        return picks[art_type].get("url")
    return None


# ============================================================
# STYLE
# ============================================================

def cmd_style(args):
    world = (BASE_DIR / "world.md").read_text(encoding="utf-8")[:5000]
    voice = (BASE_DIR / "voice.md").read_text(encoding="utf-8")[:3000]
    title = "Unknown"
    outline = BASE_DIR / "outline.md"
    if outline.exists():
        title = outline.read_text(encoding="utf-8").split("\n")[0].lstrip("# ").strip()

    prompt = f"""You are an art director designing the visual identity for a fantasy novel.

NOVEL TITLE: {title}

WORLD DESCRIPTION (excerpts):
{world}

VOICE/TONE:
{voice}

Define a VISUAL STYLE for all art in this novel. Output valid JSON:

{{
  "art_style": "one sentence describing illustration style",
  "color_palette": "5-7 specific colors",
  "texture": "dominant visual texture",
  "mood": "visual mood",
  "reference_artists": "2-3 real artists whose style approximates this",
  "cover_concept": "specific image for the cover — concrete, no spoilers",
  "ornament_concept": "what chapter ornaments should look like — symbolic, small",
  "scene_break_concept": "what goes between scenes — minimal, horizontal",
  "map_concept": "what the map shows and its style (if applicable)"
}}

JSON only."""

    print("Deriving visual style from world + voice...")
    result = call_claude(prompt)
    text = result.strip()
    if text.startswith("```"):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    style = json.loads(text)

    ART_DIR.mkdir(exist_ok=True)
    STYLE_FILE.write_text(json.dumps(style, indent=2, encoding="utf-8"))

    print(f"\nVisual style saved to {STYLE_FILE}")
    for k, v in style.items():
        print(f"  {k}: {str(v)[:80]}")
    return style


# ============================================================
# CURATE: generate N variants, human picks
# ============================================================

def cmd_curate(args):
    style = load_style()
    art_type = args.art_type
    n = args.n

    VARIANTS_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Generate fundamentally different art directions via Claude
    from gen_art_directions import generate_directions

    world = ""
    if (BASE_DIR / "world.md").exists():
        world = (BASE_DIR / "world.md").read_text(encoding="utf-8")[:3000]

    print(f"Generating {n} radically different {art_type} directions...")
    directions = generate_directions(art_type, style, n, world)

    # Resolution/aspect per type
    resolutions = {
        "cover": ("1K", "2:3"),
        "ornament": ("0.5K", "1:1"),
        "map": ("1K", "4:3"),
        "scene-break": ("0.5K", "4:1"),
    }
    resolution, aspect = resolutions.get(art_type, ("1K", "auto"))

    # Step 2: Generate one image per direction
    directions_log = []
    for i, d in enumerate(directions, 1):
        prompt = d["prompt"]
        # Append universal constraints
        if art_type == "cover":
            prompt += " No text, no title, no lettering. Pure illustration."
        elif art_type in ("ornament", "scene-break"):
            prompt += " White background. No text."

        label = d.get("direction", f"variant_{i}")
        print(f"\n  [{i}/{n}] {label.upper()}: {d.get('concept', '')[:80]}")
        print(f"    Medium: {d.get('medium', 'N/A')}")

        url, desc = fal_generate(prompt, resolution=resolution, aspect_ratio=aspect)
        dest = VARIANTS_DIR / f"{art_type}_{i:02d}.png"
        size = download_image(url, dest)

        # Cache URL and direction info
        picks = load_picks()
        picks[f"variant_{art_type}_{i}"] = {
            "url": url,
            "path": str(dest),
            "direction": label,
            "concept": d.get("concept", ""),
            "medium": d.get("medium", ""),
            "prompt": prompt,
        }
        save_picks(picks)

        directions_log.append({
            "num": i, "direction": label,
            "concept": d.get("concept", ""),
            "medium": d.get("medium", ""),
            "file": dest.name, "size": size,
        })

        print(f"    → {dest.name} ({size:,} bytes)")
        if i < n:
            time.sleep(1)

    # Save directions log for reference
    log_path = VARIANTS_DIR / f"{art_type}_directions.json"
    log_path.write_text(json.dumps(directions_log, indent=2, encoding="utf-8"))

    print(f"\n{'='*50}")
    print(f"{n} DIRECTIONS for {art_type}:")
    for d in directions_log:
        print(f"  {d['num']}. [{d['direction'].upper():12s}] {d['concept'][:60]}")
    print(f"\nFiles in: {VARIANTS_DIR}/")
    print(f"Pick one: gen_art.py pick {art_type} <number>")
    print(f"Details:  {log_path}")


def _extract_geography(world_text):
    """Extract location names and spatial relationships from world.md."""
    # Look for district/location names
    locations = []
    for pattern in [
        r'\*\*([^*]+)\*\*\s*[—–-]',  # **Name** — description
        r'###\s+(.+)',  # ### Section headers
    ]:
        for m in re.finditer(pattern, world_text):
            name = m.group(1).strip()
            if len(name) < 40 and not name.startswith("Note"):
                locations.append(name)

    # Also extract named places from text
    for pattern in [r'the ([A-Z][a-z]+ (?:Quarter|District|Tier|Line|Square|Tower|Settlement)s?)']:
        for m in re.finditer(pattern, world_text):
            loc = m.group(1)
            if loc not in locations:
                locations.append(loc)

    if locations:
        return ", ".join(locations[:15])
    return "the main city districts and landmarks described in the world bible"


# ============================================================
# PICK: select a variant as the final
# ============================================================

def cmd_pick(args):
    art_type = args.art_type
    number = args.number

    variant_path = VARIANTS_DIR / f"{art_type}_{number:02d}.png"
    if not variant_path.exists():
        print(f"Variant not found: {variant_path}")
        print(f"Available: {sorted(VARIANTS_DIR.glob(f'{art_type}_*.png'))}")
        sys.exit(1)

    # Copy to final location
    if art_type == "cover":
        final = ART_DIR / "cover.png"
    elif art_type == "ornament":
        final = ART_DIR / "ornament_reference.png"
    elif art_type == "map":
        final = ART_DIR / "map.png"
    elif art_type == "scene-break":
        final = ART_DIR / "scene_break.png"
    else:
        final = ART_DIR / f"{art_type}.png"

    shutil.copy2(variant_path, final)

    # Save the pick with its URL for reference
    picks = load_picks()
    variant_key = f"variant_{art_type}_{number}"
    url = picks.get(variant_key, {}).get("url", "")
    picks[art_type] = {"variant": number, "url": url, "path": str(final)}
    save_picks(picks)

    print(f"Selected variant {number} as final {art_type}")
    print(f"  {variant_path} → {final}")
    if art_type == "ornament":
        print(f"\nOrnament reference set. Run: gen_art.py ornaments-all")


# ============================================================
# BATCH ORNAMENTS (use reference)
# ============================================================

def cmd_ornaments_all(args):
    style = load_style()
    ref_url = get_reference_url("ornament")

    chapters = sorted(BASE_DIR.glob("chapters/ch_*.md"))
    print(f"Generating ornaments for {len(chapters)} chapters...")
    if ref_url:
        print(f"  Using ornament reference for style consistency")

    for ch_path in chapters:
        num = int(ch_path.stem.split("_")[1])
        title = ch_path.read_text(encoding="utf-8").split("\n")[0].lstrip("# ").strip()
        if ": " in title:
            title = title.split(": ", 1)[1]

        prompt = (
            f"Small ornamental chapter illustration for '{title}'. "
            f"{style['ornament_concept']}. "
            f"Style: {style['art_style']}. Colors: {style['color_palette']}. "
            f"Simple, symbolic. White background. No text."
        )

        print(f"  Ch {num}: '{title}'", end="", flush=True)

        if ref_url:
            url, _ = fal_edit(prompt, [ref_url], resolution="0.5K", aspect_ratio="1:1")
        else:
            url, _ = fal_generate(prompt, resolution="0.5K", aspect_ratio="1:1")

        dest = ART_DIR / f"ornament_ch{num:02d}.png"
        size = download_image(url, dest)
        print(f" → {dest.name} ({size:,} bytes)")
        time.sleep(1)


def cmd_scene_break(args):
    style = load_style()
    prompt = (
        f"Minimal decorative scene break. {style['scene_break_concept']}. "
        f"Style: {style['art_style']}. Very simple. White background. No text."
    )
    print("Generating scene break...")
    url, _ = fal_generate(prompt, resolution="0.5K", aspect_ratio="4:1")
    dest = ART_DIR / "scene_break.png"
    size = download_image(url, dest)
    print(f"  Saved: {dest} ({size:,} bytes)")


# ============================================================
# VECTORIZE: raster → SVG via potrace
# ============================================================

def cmd_vectorize(args):
    target = args.target if args.target else "all"

    # Check potrace is available
    potrace = shutil.which("potrace")
    if not potrace:
        print("ERROR: potrace not found. Install it or add to PATH.")
        sys.exit(1)

    SVG_DIR.mkdir(parents=True, exist_ok=True)

    if target == "all":
        # Vectorize ornaments + scene break (not cover or map)
        files = sorted(ART_DIR.glob("ornament_ch*.png"))
        sb = ART_DIR / "scene_break.png"
        if sb.exists():
            files.append(sb)
    else:
        f = ART_DIR / f"{target}.png"
        if not f.exists():
            print(f"Not found: {f}")
            sys.exit(1)
        files = [f]

    print(f"Vectorizing {len(files)} images...")

    for png_path in files:
        svg_path = SVG_DIR / f"{png_path.stem}.svg"

        try:
            # Step 1: Convert to grayscale PBM using Pillow
            from PIL import Image
            img = Image.open(png_path, encoding="utf-8").convert("L")
            # Threshold to black and white
            bw = img.point(lambda x: 0 if x < 180 else 255, "1")
            pbm_path = png_path.with_suffix(".pbm")
            bw.save(pbm_path)

            # Step 2: Run potrace
            result = subprocess.run(
                [potrace, str(pbm_path), "-s", "-o", str(svg_path),
                 "--turdsize", "4", "--opttolerance", "0.2"],
                capture_output=True, text=True
            )

            # Cleanup temp file
            pbm_path.unlink(missing_ok=True)

            if result.returncode == 0 and svg_path.exists():
                svg_size = svg_path.stat().st_size
                print(f"  {png_path.name} → {svg_path.name} ({svg_size:,} bytes)")
            else:
                print(f"  {png_path.name} → FAILED: {result.stderr[:100]}")

        except Exception as e:
            print(f"  {png_path.name} → ERROR: {e}")

    print(f"\nSVGs saved to {SVG_DIR}/")


# ============================================================
# ALL: full pipeline with human curation points
# ============================================================

def cmd_all(args):
    print("=" * 60)
    print("AUTONOVEL ART PIPELINE (interactive)")
    print("=" * 60)

    print("\n--- Step 1: Visual Style ---")
    if not STYLE_FILE.exists():
        cmd_style(args)
    else:
        print(f"  Using existing style from {STYLE_FILE}")

    print("\n--- Step 2: Generate Cover Variants ---")
    class CurateArgs:
        pass
    ca = CurateArgs()
    ca.art_type = "cover"
    ca.n = 4
    cmd_curate(ca)
    print("\n>>> HUMAN ACTION: Review art/variants/cover_*.png")
    print(">>> Then run: gen_art.py pick cover <number>")
    print(">>> Then re-run: gen_art.py all")
    
    if not get_reference_url("cover"):
        print("\n(Stopping here — pick a cover first)")
        return

    print("\n--- Step 3: Generate Ornament Style Variants ---")
    ca.art_type = "ornament"
    cmd_curate(ca)
    print("\n>>> HUMAN ACTION: Review art/variants/ornament_*.png")
    print(">>> Then run: gen_art.py pick ornament <number>")

    if not get_reference_url("ornament"):
        print("\n(Stopping here — pick an ornament style first)")
        return

    print("\n--- Step 4: Generate All Chapter Ornaments ---")
    cmd_ornaments_all(args)

    print("\n--- Step 5: Scene Break ---")
    cmd_scene_break(args)

    print("\n--- Step 6: Map Variants ---")
    ca.art_type = "map"
    ca.n = 3
    cmd_curate(ca)

    print("\n--- Step 7: Vectorize ---")
    cmd_vectorize(args)

    print("\n" + "=" * 60)
    print("ART PIPELINE COMPLETE")
    print("  Review maps in art/variants/map_*.png")
    print("  Pick one: gen_art.py pick map <number>")
    print("  SVG ornaments in art/svg/")
    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Generate novel art via Nano Banana 2")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("style", help="Derive visual style from world + voice")

    p = sub.add_parser("curate", help="Generate N variants for human selection")
    p.add_argument("art_type", choices=["cover", "ornament", "map", "scene-break"])
    p.add_argument("--n", type=int, default=4, help="Number of variants")

    p = sub.add_parser("pick", help="Select a variant as final")
    p.add_argument("art_type")
    p.add_argument("number", type=int)

    sub.add_parser("ornaments-all", help="Generate ornaments for all chapters")
    sub.add_parser("scene-break", help="Generate scene break decoration")

    p = sub.add_parser("vectorize", help="Convert raster art to SVG")
    p.add_argument("target", nargs="?", default="all", help="Image name or 'all'")

    sub.add_parser("all", help="Full pipeline with human curation points")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if not FAL_KEY and args.command not in ("vectorize",):
        print("ERROR: FAL_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    ART_DIR.mkdir(exist_ok=True)

    commands = {
        "style": cmd_style,
        "curate": cmd_curate,
        "pick": cmd_pick,
        "ornaments-all": cmd_ornaments_all,
        "scene-break": cmd_scene_break,
        "vectorize": cmd_vectorize,
        "all": cmd_all,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
