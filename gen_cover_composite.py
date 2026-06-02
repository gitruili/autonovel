#!/usr/bin/env python3
"""
Composite title, author, and subtitle text over cover art.
Typography rendered by Pillow — crisp, controllable, no AI text artifacts.

Usage:
  python gen_cover_composite.py art/variants/cover_refine_01_tight.png
  python gen_cover_composite.py art/cover.png --title "My Novel" --author "Name"
  python gen_cover_composite.py art/cover.png --preset dark   # light text on dark art
  python gen_cover_composite.py art/cover.png --preset light  # dark text on light art
"""
import argparse
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE_DIR = Path(__file__).parent


def find_font(name, style="Regular"):
    """Find a font file by name."""
    import subprocess
    result = subprocess.run(
        ["fc-match", f"{name}:style={style}", "--format=%{file}"],
        capture_output=True, text=True,
    )
    path = result.stdout.strip()
    if path and Path(path).exists():
        return path
    return None


def analyze_image_brightness(img, region="top"):
    """Analyze average brightness of a region to choose text color."""
    w, h = img.size
    if region == "top":
        box = (0, 0, w, h // 4)
    elif region == "bottom":
        box = (0, h * 3 // 4, w, h)
    else:
        box = (0, 0, w, h)

    cropped = img.crop(box).convert("L")
    pixels = list(cropped.getdata())
    avg = sum(pixels) / len(pixels)
    return avg  # 0=black, 255=white


def draw_text_with_shadow(draw, position, text, font, fill, shadow_color, shadow_offset=2):
    """Draw text with a subtle shadow for readability."""
    x, y = position
    # Shadow
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color, anchor="mt")
    # Main text
    draw.text((x, y), text, font=font, fill=fill, anchor="mt")


def composite_cover(
    art_path,
    title="The Second Son of the House of Bells",
    author="Claude Hermes",
    subtitle="A Novel",
    preset="auto",
    output_path=None,
):
    img = Image.open(art_path, encoding="utf-8").convert("RGBA")
    w, h = img.size

    # Auto-detect light/dark
    if preset == "auto":
        top_brightness = analyze_image_brightness(img, "top")
        bottom_brightness = analyze_image_brightness(img, "bottom")
        preset = "dark" if (top_brightness + bottom_brightness) / 2 < 140 else "light"

    if preset == "dark":
        text_color = (255, 250, 240, 255)  # bright warm white
        shadow_color = (0, 0, 0, 200)
        band_color = (0, 0, 0, 140)
    else:
        text_color = (255, 250, 240, 255)  # still light — use band for contrast
        shadow_color = (0, 0, 0, 200)
        band_color = (0, 0, 0, 140)

    # Font sizing — LARGE, airport-shelf readable
    title_size = max(int(w * 0.09), 36)
    author_size = max(int(w * 0.045), 20)
    subtitle_size = max(int(w * 0.03), 14)

    # Find fonts
    garamond_bold = find_font("EB Garamond", "Bold")
    garamond_regular = find_font("EB Garamond", "Regular")
    garamond_italic = find_font("EB Garamond", "Italic")

    # Fallbacks
    if not garamond_bold:
        garamond_bold = find_font("Liberation Serif", "Bold")
    if not garamond_regular:
        garamond_regular = find_font("Liberation Serif", "Regular")
    if not garamond_italic:
        garamond_italic = find_font("Liberation Serif", "Italic")

    title_font = ImageFont.truetype(garamond_bold, title_size) if garamond_bold else ImageFont.load_default()
    author_font = ImageFont.truetype(garamond_regular, author_size) if garamond_regular else ImageFont.load_default()
    subtitle_font = ImageFont.truetype(garamond_italic, subtitle_size) if garamond_italic else ImageFont.load_default()

    # Create overlay
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    center_x = w // 2

    # --- TITLE BAND (semi-transparent dark band behind title area) ---
    title_band_top = int(h * 0.04)
    title_band_bottom = int(h * 0.38)
    draw.rectangle(
        [(0, title_band_top), (w, title_band_bottom)],
        fill=band_color,
    )

    # --- AUTHOR BAND (semi-transparent dark band behind author) ---
    author_band_top = int(h * 0.78)
    author_band_bottom = int(h * 0.96)
    draw.rectangle(
        [(0, author_band_top), (w, author_band_bottom)],
        fill=band_color,
    )

    # --- TITLE TEXT ---
    title_parts = title.upper().split(" OF THE ")
    if len(title_parts) == 2:
        line1 = title_parts[0].strip()
        line2 = "OF THE"
        line3 = title_parts[1].strip()

        small_size = max(int(title_size * 0.5), 16)
        small_font = ImageFont.truetype(garamond_regular, small_size) if garamond_regular else title_font

        title_y = int(h * 0.08)
        spacing = int(title_size * 1.5)
        small_spacing = int(small_size * 2.0)

        if line1.startswith("THE "):
            draw_text_with_shadow(draw, (center_x, title_y), "THE", small_font, text_color, shadow_color, shadow_offset=3)
            title_y += small_spacing
            draw_text_with_shadow(draw, (center_x, title_y), line1[4:], title_font, text_color, shadow_color, shadow_offset=3)
        else:
            draw_text_with_shadow(draw, (center_x, title_y), line1, title_font, text_color, shadow_color, shadow_offset=3)

        title_y += spacing
        draw_text_with_shadow(draw, (center_x, title_y), line2, small_font, text_color, shadow_color, shadow_offset=3)
        title_y += small_spacing
        draw_text_with_shadow(draw, (center_x, title_y), line3, title_font, text_color, shadow_color, shadow_offset=3)
    else:
        title_y = int(h * 0.15)
        draw_text_with_shadow(draw, (center_x, title_y), title.upper(), title_font, text_color, shadow_color, shadow_offset=3)

    # --- AUTHOR + SUBTITLE ---
    author_y = int(h * 0.90)
    draw_text_with_shadow(draw, (center_x, author_y), author.upper(), author_font, text_color, shadow_color, shadow_offset=3)

    if subtitle:
        subtitle_y = int(h * 0.84)
        draw_text_with_shadow(draw, (center_x, subtitle_y), subtitle, subtitle_font, text_color, shadow_color, shadow_offset=3)

    # Composite
    result = Image.alpha_composite(img, overlay).convert("RGB")

    if not output_path:
        stem = Path(art_path).stem
        output_path = BASE_DIR / "art" / f"{stem}_titled.png"

    result.save(str(output_path), "PNG")
    print(f"Saved: {output_path} ({Path(output_path).stat().st_size:,} bytes)")
    print(f"  Preset: {preset}, title size: {title_size}px")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(description="Composite text over cover art")
    parser.add_argument("art_path", help="Path to the cover art image")
    parser.add_argument("--title", default="The Second Son of the House of Bells")
    parser.add_argument("--author", default="Claude Hermes")
    parser.add_argument("--subtitle", default="A Novel")
    parser.add_argument("--preset", choices=["auto", "dark", "light"], default="auto")
    parser.add_argument("--output", default=None)

    args = parser.parse_args()
    composite_cover(args.art_path, args.title, args.author, args.subtitle, args.preset, args.output)


if __name__ == "__main__":
    main()
