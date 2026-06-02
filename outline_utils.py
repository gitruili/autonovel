import os
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
