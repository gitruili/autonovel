#!/usr/bin/env python3
"""
Compose a print-ready book cover from panoramic art.
Handles Lulu.com / KDP / IngramSpark cover specs.

Usage:
  python gen_cover_print.py art/variants/cover_wrap_01.png
  python gen_cover_print.py art/variants/cover_wrap_01.png --pages 300
  python gen_cover_print.py art/variants/cover_wrap_01.png --preview  # low-res with guides

The panoramic art should be wider than tall (4:3 or wider).
RIGHT side = front cover, CENTER = spine, LEFT side = back cover.
"""
import argparse
import io
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).parent
ART_DIR = BASE_DIR / "art"

# Standard trade paperback dimensions
TRIM_W = 5.5   # inches
TRIM_H = 8.5   # inches
BLEED = 0.125  # inches
DPI = 300

# Spine width per page count (Lulu cream paper, approximate)
# formula: pages * 0.0025" for cream, 0.002" for white
SPINE_PER_PAGE = 0.0025


def find_font(name, style="Regular"):
    import subprocess
    result = subprocess.run(
        ["fc-match", f"{name}:style={style}", "--format=%{file}"],
        capture_output=True, text=True,
    )
    path = result.stdout.strip()
    if path and Path(path).exists():
        return path
    return None


def compose_cover(
    art_path,
    title="The Second Son of the House of Bells",
    author="Claude Hermes",
    subtitle="A Novel",
    blurb="",
    pages=300,
    preview=False,
    output_path=None,
    canvas_width=None,
    canvas_height=None,
    spine_width=None,
):
    # Use exact printer dimensions if provided, otherwise calculate
    if canvas_width and canvas_height and spine_width:
        canvas_w = canvas_width
        canvas_h = canvas_height
        spine_w = spine_width
    else:
        spine_w = pages * SPINE_PER_PAGE
        canvas_w = BLEED + TRIM_W + spine_w + TRIM_W + BLEED
        canvas_h = BLEED + TRIM_H + BLEED

    # Convert to pixels
    px_w = int(canvas_w * DPI)
    px_h = int(canvas_h * DPI)
    px_bleed = int(BLEED * DPI)
    px_trim_w = int(TRIM_W * DPI)
    px_spine = int(spine_w * DPI)

    print(f"Cover spec:")
    print(f"  Trim: {TRIM_W}\" x {TRIM_H}\"")
    print(f"  Spine: {spine_w:.3f}\" ({pages} pages)")
    print(f"  Canvas: {canvas_w:.3f}\" x {canvas_h:.3f}\"")
    print(f"  Pixels: {px_w} x {px_h} @ {DPI} DPI")

    # Load and scale art to fill canvas
    art = Image.open(art_path, encoding="utf-8").convert("RGB")
    art_ratio = art.width / art.height
    canvas_ratio = px_w / px_h

    if art_ratio > canvas_ratio:
        # Art is wider — scale by height, crop sides
        scale_h = px_h
        scale_w = int(px_h * art_ratio)
        art = art.resize((scale_w, scale_h), Image.LANCZOS)
        x_offset = (scale_w - px_w) // 2
        art = art.crop((x_offset, 0, x_offset + px_w, px_h))
    else:
        # Art is taller — scale by width, crop top/bottom
        scale_w = px_w
        scale_h = int(px_w / art_ratio)
        art = art.resize((scale_w, scale_h), Image.LANCZOS)
        y_offset = (scale_h - px_h) // 2
        art = art.crop((0, y_offset, px_w, y_offset + px_h))

    canvas = art.convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    # Zone positions (from left edge of canvas)
    back_left = px_bleed
    back_right = px_bleed + px_trim_w
    spine_left = back_right
    spine_right = spine_left + px_spine
    front_left = spine_right
    front_right = spine_right + px_trim_w

    # Font setup
    gb = find_font("EB Garamond", "Bold")
    gr = find_font("EB Garamond", "Regular")
    gi = find_font("EB Garamond", "Italic")
    bebas = find_font("Bebas Neue", "Regular")  # ultra-heavy display face

    # Display font for title/spine (Bebas Neue if available, else Garamond Bold)
    display_face = bebas if bebas else gb

    # Front cover text sizes (relative to trim width in pixels)
    title_large = int(px_trim_w * 0.10)
    title_small = int(title_large * 0.55)
    author_size = int(px_trim_w * 0.06)
    subtitle_size = int(px_trim_w * 0.032)

    title_font = ImageFont.truetype(display_face, title_large) if display_face else ImageFont.load_default()
    title_small_font = ImageFont.truetype(display_face, title_small) if display_face else ImageFont.load_default()
    # Colors — amber/bronze that belongs in the linocut palette
    title_color = (218, 165, 72, 255)    # warm amber-gold
    author_color = (218, 165, 72, 255)   # same amber
    accent_color = (180, 140, 65, 255)   # slightly muted for small text
    shadow_color = (5, 5, 3, 220)        # near-black, heavy

    def text_drawn(pos, text, font, fill, shadow_offset=4):
        """Bold text with heavy dark shadow for max readability."""
        x, y = pos
        # Double shadow for extra punch
        draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color, anchor="mt")
        draw.text((x + shadow_offset//2, y + shadow_offset//2), text, font=font, fill=(0,0,0,140), anchor="mt")
        draw.text(pos, text, font=font, fill=fill, anchor="mt")

    # === FRONT COVER TEXT ===
    front_cx = front_left + px_trim_w // 2

    title_parts = title.upper().split(" OF THE ")
    if len(title_parts) == 2:
        line1 = title_parts[0].strip()
        line3 = title_parts[1].strip()

        # "THE" and "OF THE" in bold too, just smaller
        connector_size = max(int(title_large * 0.42), 16)
        connector_font = ImageFont.truetype(display_face, connector_size) if display_face else title_font

        y = px_bleed + int(px_trim_w * 0.18)
        title_gap = int(title_large * 1.55)
        connector_gap = int(connector_size * 2.2)

        if line1.startswith("THE "):
            text_drawn((front_cx, y), "THE", connector_font, accent_color, shadow_offset=3)
            y += connector_gap
            text_drawn((front_cx, y), line1[4:], title_font, title_color, shadow_offset=5)
        else:
            text_drawn((front_cx, y), line1, title_font, title_color, shadow_offset=5)

        y += title_gap
        text_drawn((front_cx, y), "OF THE", connector_font, accent_color, shadow_offset=3)
        y += connector_gap
        text_drawn((front_cx, y), line3, title_font, title_color, shadow_offset=5)
    else:
        y = px_bleed + int(px_trim_w * 0.3)
        text_drawn((front_cx, y), title.upper(), title_font, title_color, shadow_offset=5)

    # Author — bold, at bottom
    auth_y = px_h - px_bleed - int(TRIM_H * DPI * 0.10)
    author_bold_font = ImageFont.truetype(display_face, author_size) if display_face else ImageFont.load_default()
    text_drawn((front_cx, auth_y), author.upper(), author_bold_font, author_color, shadow_offset=4)

    # === SPINE TEXT ===
    if px_spine > 30:
        spine_cx = spine_left + px_spine // 2

        # Bebas Neue for spine — single line, title + author fills the full height
        spine_face = display_face
        spine_text = f"{title.upper()}   \u2022   {author.upper()}"

        # After rotation: text WIDTH becomes the spine's vertical length.
        # We want text to stretch across ~90% of page height.
        target_text_w = int(px_h * 0.90)
        max_glyph_h = int(px_spine * 0.70)

        # Find font size where text width fills the spine length
        spine_font_size = 8
        for try_size in range(8, 120):
            test_font = ImageFont.truetype(spine_face, try_size) if spine_face else ImageFont.load_default()
            bbox = test_font.getbbox(spine_text)
            text_w = bbox[2] - bbox[0]
            glyph_h = bbox[3] - bbox[1]
            if text_w > target_text_w or glyph_h > max_glyph_h:
                break
            spine_font_size = try_size

        spine_font = ImageFont.truetype(spine_face, spine_font_size) if spine_face else ImageFont.load_default()

        # Crimson-red
        spine_color = (200, 50, 40, 255)

        # Render horizontally, then rotate
        temp = Image.new("RGBA", (px_h, px_spine), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp)
        temp_draw.text((px_h // 2 + 2, px_spine // 2 + 2), spine_text,
                       font=spine_font, fill=(0, 0, 0, 220), anchor="mm")
        temp_draw.text((px_h // 2, px_spine // 2), spine_text,
                       font=spine_font, fill=spine_color, anchor="mm")
        temp = temp.rotate(90, expand=True)
        paste_x = spine_cx - temp.width // 2
        paste_y = (px_h - temp.height) // 2
        canvas.paste(temp, (paste_x, paste_y), temp)

    # === BACK COVER TEXT (on dark panel for readability) ===
    if blurb:
        back_cx = back_left + px_trim_w // 2
        blurb_font_size = int(px_trim_w * 0.03)
        blurb_font = ImageFont.truetype(gr, blurb_font_size) if gr else ImageFont.load_default()
        blurb_margin = int(px_trim_w * 0.10)
        blurb_width = px_trim_w - 2 * blurb_margin

        # Word wrap respecting paragraph breaks
        paragraphs = blurb.split("\n\n") if "\n\n" in blurb else [blurb]
        all_lines = []
        for para in paragraphs:
            words = para.split()
            current = ""
            for word in words:
                test = f"{current} {word}".strip()
                bbox = blurb_font.getbbox(test)
                if bbox[2] > blurb_width:
                    all_lines.append(current)
                    current = word
                else:
                    current = test
            if current:
                all_lines.append(current)
            all_lines.append("")  # paragraph break

        line_height = int(blurb_font_size * 1.65)
        total_text_height = len(all_lines) * line_height

        # Center blurb vertically on back cover
        blurb_start_y = px_bleed + (int(TRIM_H * DPI) - total_text_height) // 2
        panel_pad = int(blurb_margin * 0.6)

        # Draw dark panel behind blurb
        panel_rect = [
            (back_left + blurb_margin - panel_pad, blurb_start_y - panel_pad),
            (back_left + px_trim_w - blurb_margin + panel_pad, blurb_start_y + total_text_height + panel_pad),
        ]
        draw.rectangle(panel_rect, fill=(10, 10, 8, 190))

        # Draw blurb text (regular weight, warm cream, left-aligned)
        blurb_y = blurb_start_y
        for line in all_lines:
            if line:
                draw.text(
                    (back_left + blurb_margin, blurb_y),
                    line, font=blurb_font, fill=(235, 230, 215, 255),
                )
            blurb_y += line_height

    # === NOUS LOGO on back cover (bottom left, white background) ===
    nous_svg = BASE_DIR / "art" / "NOUS-F-badge.svg"
    if nous_svg.exists():
        try:
            import cairosvg
            # Render SVG to PNG at appropriate size
            logo_size = int(px_trim_w * 0.15)  # 15% of trim width
            png_data = cairosvg.svg2png(
                url=str(nous_svg),
                output_width=logo_size, output_height=logo_size,
            )
            logo_img = Image.open(io.BytesIO(png_data, encoding="utf-8")).convert("RGBA")

            # White background with equal padding on all sides
            pad = int(logo_size * 0.15)
            padded_size = (logo_img.width + 2 * pad, logo_img.height + 2 * pad)
            logo_bg = Image.new("RGBA", padded_size, (255, 255, 255, 255))
            logo_bg.paste(logo_img, (pad, pad), logo_img)
            logo_composite = logo_bg

            # Position: bottom-left of back cover, with margin
            logo_x = back_left + int(blurb_margin * 0.5) if blurb else back_left + int(px_trim_w * 0.1)
            logo_y = px_h - px_bleed - int(TRIM_H * DPI * 0.20)
            canvas.paste(logo_composite, (logo_x, logo_y), logo_composite)
        except Exception as e:
            print(f"  (Nous logo skipped: {e})")

    # === PREVIEW: draw trim/spine guides ===
    if preview:
        guide_color = (255, 0, 0, 100)
        # Trim lines
        draw.line([(back_left, 0), (back_left, px_h)], fill=guide_color, width=2)
        draw.line([(back_right, 0), (back_right, px_h)], fill=guide_color, width=2)
        draw.line([(front_left, 0), (front_left, px_h)], fill=guide_color, width=2)
        draw.line([(front_right, 0), (front_right, px_h)], fill=guide_color, width=2)
        # Spine
        draw.line([(spine_left, 0), (spine_left, px_h)], fill=(0, 255, 0, 100), width=2)
        draw.line([(spine_right, 0), (spine_right, px_h)], fill=(0, 255, 0, 100), width=2)

    # Save
    result = canvas.convert("RGB")
    if not output_path:
        stem = Path(art_path).stem
        suffix = "_preview" if preview else "_print"
        output_path = ART_DIR / f"{stem}{suffix}.png"

    ext = Path(output_path).suffix.lower()
    if ext == ".pdf":
        # Save as PDF for print
        result_rgb = result.convert("RGB")
        result_rgb.save(str(output_path), "PDF", resolution=DPI)
    else:
        result.convert("RGB").save(str(output_path), "PNG", dpi=(DPI, DPI))
    size = Path(output_path).stat().st_size
    print(f"\nSaved: {output_path}")
    print(f"  {px_w} x {px_h} px @ {DPI} DPI ({size:,} bytes)")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(description="Compose print-ready book cover")
    parser.add_argument("art_path", help="Path to panoramic cover art")
    parser.add_argument("--title", default="The Second Son of the House of Bells")
    parser.add_argument("--author", default="Claude Hermes")
    parser.add_argument("--subtitle", default="A Novel")
    parser.add_argument("--blurb", default="")
    parser.add_argument("--pages", type=int, default=300)
    parser.add_argument("--preview", action="store_true", help="Show trim/spine guides")
    parser.add_argument("--output", default=None)
    parser.add_argument("--canvas-width", type=float, default=None, help="Exact canvas width in inches (from printer)")
    parser.add_argument("--canvas-height", type=float, default=None, help="Exact canvas height in inches (from printer)")
    parser.add_argument("--spine-width", type=float, default=None, help="Exact spine width in inches (from printer)")
    args = parser.parse_args()
    compose_cover(args.art_path, args.title, args.author, args.subtitle,
                  args.blurb, args.pages, args.preview, args.output,
                  args.canvas_width, args.canvas_height, args.spine_width)


if __name__ == "__main__":
    main()
