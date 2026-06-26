import os
import re
from pathlib import Path

def rebuild_outline_compatibility_layer(base_dir: Path):
    """
    Rebuild the outline.md compatibility layer from the individual components:
    master_summary.md + volume_*_outline.md
    """
    plans_dir = base_dir / "story" / "plans"
    parts = []

    # 1. Add master summary
    summary_path = plans_dir / "master_summary.md"
    if summary_path.exists():
        parts.append(summary_path.read_text(encoding="utf-8"))

    # 2. Add volume outlines in order
    if plans_dir.exists():
        volume_outlines = sorted(plans_dir.glob("volume_*_outline.md"))
        for vol_outline in volume_outlines:
            parts.append(vol_outline.read_text(encoding="utf-8"))

    # 3. Write combined outline
    if parts:
        combined_text = "\n\n---\n\n".join(parts)
        outline_path = base_dir / "outline.md"
        outline_path.write_text(combined_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Chapter outline extraction helpers
# ---------------------------------------------------------------------------

CHAPTER_HEADING_RE = re.compile(r"###\s*第\s*(\d+)\s*章[\s：:]")


def extract_chapter_outline(outline_text: str, chapter_num: int) -> str:
    """Extract a specific chapter's outline entry from combined or volume outline text.

    Matches headings like:
      ### 第 1 章: 标题
      ### 第 1 章：标题
    """
    if not outline_text:
        return ""
    pattern = rf'###\s*第\s*{chapter_num}\s*章[\s：:]\s*.*?(?=###\s*第\s*\d+\s*章[\s：:]|##\s*第[一二三四]幕|##\s*种田升级|##\s*情感线|##\s*伏笔|##\s*打脸|##\s*文风|###\s*卷<|\*\*卷\d+|\Z)'
    match = re.search(pattern, outline_text, re.DOTALL)
    return match.group(0).strip() if match else ""


def extract_chapter_range_outline(outline_text: str, start: int, end: int) -> str:
    """Extract a range of chapter entries from outline text."""
    if not outline_text or start > end:
        return ""
    parts = [extract_chapter_outline(outline_text, c) for c in range(start, end + 1)]
    parts = [p for p in parts if p]
    return "\n\n---\n\n".join(parts)


def load_volume_outline_for_chapter(chapter: int, base_dir: Path | str | None = None) -> tuple[str, Path | None]:
    """Load the volume_*_outline.md file that contains the given chapter.

    Returns (text, path). If no matching file is found, returns ("", None).
    """
    if base_dir is None:
        base_dir = Path(__file__).parent
    base_dir = Path(base_dir)
    plans_dir = base_dir / "story" / "plans"

    if not plans_dir.exists():
        return "", None

    marker = f"### 第 {chapter} 章"
    for vol_path in sorted(plans_dir.glob("volume_*_outline.md")):
        text = vol_path.read_text(encoding="utf-8")
        if marker in text:
            return text, vol_path

    return "", None
