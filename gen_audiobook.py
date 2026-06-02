#!/usr/bin/env python3
"""
Generate audiobook from parsed scripts using ElevenLabs Text to Dialogue.

Usage:
  python gen_audiobook.py                # Generate all chapters
  python gen_audiobook.py 1              # Single chapter
  python gen_audiobook.py 1 5            # Range
  python gen_audiobook.py --list-voices  # List available ElevenLabs voices
  python gen_audiobook.py --test 1       # Generate first 30 seconds of ch 1 (test)
"""
import os
import sys
import json
import io
import re
import time
import argparse
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env", override=True)

ELEVENLABS_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

AUDIO_DIR = BASE_DIR / "audiobook"
SCRIPTS_DIR = AUDIO_DIR / "scripts"
OUTPUT_DIR = AUDIO_DIR / "chapters"
VOICES_FILE = BASE_DIR / "audiobook_voices.json"

MAX_CHARS_PER_CALL = 4500  # stay under 5000 limit with overhead
PAUSE_BETWEEN_CALLS = 3.0  # rate limiting — ElevenLabs has per-minute caps


def get_client():
    """Initialize ElevenLabs client."""
    from elevenlabs.client import ElevenLabs
    if not ELEVENLABS_KEY:
        print("ERROR: ELEVENLABS_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)
    return ElevenLabs(api_key=ELEVENLABS_KEY)


def load_voices():
    """Load voice mapping from audiobook_voices.json."""
    if not VOICES_FILE.exists():
        print(f"ERROR: {VOICES_FILE} not found. Create it first.", file=sys.stderr)
        sys.exit(1)
    data = json.loads(VOICES_FILE.read_text(encoding="utf-8"))
    voices = {}
    for name, info in data.items():
        if name.startswith("_"):
            continue
        vid = info.get("voice_id", "")
        if vid and vid != "REPLACE_WITH_VOICE_ID":
            voices[name] = vid
    return voices


def load_script(ch_num):
    """Load a chapter's parsed script."""
    path = SCRIPTS_DIR / f"ch{ch_num:02d}_script.json"
    if not path.exists():
        print(f"  Script not found: {path}. Run gen_audiobook_script.py first.", file=sys.stderr)
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def chunk_segments(segments, voices, max_chars=MAX_CHARS_PER_CALL):
    """Split segments into chunks that fit within the API character limit.
    
    Each chunk is a list of {text, voice_id} dicts suitable for text_to_dialogue.
    We try to keep dialogue exchanges together (don't split mid-conversation).
    """
    chunks = []
    current_chunk = []
    current_chars = 0
    fallback_voice = list(voices.values())[0] if voices else None

    for seg in segments:
        speaker = seg["speaker"]
        text = seg["text"]

        # Resolve voice_id
        voice_id = voices.get(speaker)
        if not voice_id:
            voice_id = voices.get("MINOR", voices.get("NARRATOR", fallback_voice))
        if not voice_id:
            continue

        seg_chars = len(text)

        # If this single segment exceeds the limit, split it
        if seg_chars > max_chars:
            # Flush current chunk
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_chars = 0
            
            # Split long text into sentences
            sentences = text.replace(". ", ".\n").split("\n")
            sub_chunk = []
            sub_chars = 0
            for sent in sentences:
                if sub_chars + len(sent) > max_chars and sub_chunk:
                    chunks.append([{"text": " ".join(sub_chunk), "voice_id": voice_id}])
                    sub_chunk = []
                    sub_chars = 0
                sub_chunk.append(sent)
                sub_chars += len(sent) + 1
            if sub_chunk:
                chunks.append([{"text": " ".join(sub_chunk), "voice_id": voice_id}])
            continue

        # Would adding this segment exceed the limit?
        if current_chars + seg_chars > max_chars and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_chars = 0

        # Skip empty/whitespace-only segments
        clean_text = re.sub(r'\[.*?\]', '', text).strip()
        if not clean_text:
            continue

        current_chunk.append({"text": text, "voice_id": voice_id})
        current_chars += seg_chars

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def generate_chapter(ch_num, client, voices, test_mode=False):
    """Generate audio for a single chapter."""
    script = load_script(ch_num)
    if not script:
        return None

    title = script.get("title", f"Chapter {ch_num}")
    segments = script["segments"]
    
    if test_mode:
        # Only use first 10 segments for testing
        segments = segments[:10]
        print(f"  TEST MODE: using first 10 segments only")

    chunks = chunk_segments(segments, voices)
    total_chunks = len(chunks)
    
    print(f"  Ch {ch_num}: '{title}' → {len(segments)} segments → {total_chunks} API calls")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audio_parts = []

    failed_chunks = []
    
    for i, chunk in enumerate(chunks, 1):
        chars = sum(len(s['text']) for s in chunk)
        print(f"    [{i}/{total_chunks}] {chars} chars, "
              f"{len(chunk)} segments...", end="", flush=True)

        # Retry logic: up to 3 attempts with backoff
        audio_bytes = None
        last_error = None
        for attempt in range(1, 4):
            try:
                audio = client.text_to_dialogue.convert(inputs=chunk)
                audio_bytes = b""
                for chunk_data in audio:
                    if isinstance(chunk_data, bytes):
                        audio_bytes += chunk_data
                    else:
                        audio_bytes += chunk_data
                break  # success
            except Exception as e:
                last_error = str(e)
                if attempt < 3:
                    wait = attempt * 10  # 10s, 20s backoff
                    print(f" retry in {wait}s...", end="", flush=True)
                    time.sleep(wait)

        if audio_bytes and len(audio_bytes) > 0:
            audio_parts.append(audio_bytes)
            print(f" ✓ ({len(audio_bytes):,} bytes)")
        else:
            failed_chunks.append(i)
            print(f" ✗ FAILED after 3 attempts: {last_error[:120] if last_error else 'unknown'}")

        if i < total_chunks:
            time.sleep(PAUSE_BETWEEN_CALLS)

    if failed_chunks:
        print(f"\n  ⚠ WARNING: {len(failed_chunks)} chunks FAILED: {failed_chunks}")
        print(f"  The audio file will have GAPS. Re-run to retry failed chunks.")
        print(f"  Failed chunk numbers: {failed_chunks} of {total_chunks}")
        
        # Save a manifest of what succeeded and what failed
        manifest = {
            "chapter": ch_num,
            "total_chunks": total_chunks,
            "succeeded": [i for i in range(1, total_chunks+1) if i not in failed_chunks],
            "failed": failed_chunks,
            "complete": len(failed_chunks) == 0,
        }
        manifest_path = OUTPUT_DIR / f"ch_{ch_num:02d}_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, encoding="utf-8"))

    if not audio_parts:
        print(f"  No audio generated for Ch {ch_num}")
        return None

    # Concatenate all audio parts
    combined = b"".join(audio_parts)
    
    suffix = "_test" if test_mode else ""
    out_path = OUTPUT_DIR / f"ch_{ch_num:02d}{suffix}.mp3"
    out_path.write_bytes(combined)

    size_mb = len(combined) / (1024 * 1024)
    print(f"  Saved: {out_path} ({size_mb:.1f} MB)")
    return str(out_path)


def list_voices(client):
    """List available ElevenLabs voices."""
    response = client.voices.get_all()
    print(f"\n{'='*60}")
    print(f"AVAILABLE VOICES ({len(response.voices)})")
    print(f"{'='*60}")
    for voice in response.voices:
        labels = voice.labels or {}
        accent = labels.get("accent", "")
        age = labels.get("age", "")
        gender = labels.get("gender", "")
        desc = labels.get("description", "")
        use_case = labels.get("use_case", "")
        print(f"\n  {voice.name}")
        print(f"    ID: {voice.voice_id}")
        print(f"    {gender} | {age} | {accent}")
        if desc:
            print(f"    {desc}")
        if use_case:
            print(f"    Use case: {use_case}")


def assemble_full_audiobook():
    """Concatenate all chapter audio files into one."""
    chapter_files = sorted(OUTPUT_DIR.glob("ch_*.mp3"))
    chapter_files = [f for f in chapter_files if "_test" not in f.name]
    
    if not chapter_files:
        print("No chapter audio files found.")
        return
    
    print(f"\nAssembling {len(chapter_files)} chapters into full audiobook...")
    
    combined = b""
    # Add 2 seconds of silence between chapters (simple approach: just concatenate)
    for f in chapter_files:
        combined += f.read_bytes()
    
    out = AUDIO_DIR / "full_audiobook.mp3"
    out.write_bytes(combined)
    size_mb = len(combined) / (1024 * 1024)
    print(f"  Full audiobook: {out} ({size_mb:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Generate audiobook from parsed scripts")
    parser.add_argument("start", nargs="?", type=int, help="Start chapter")
    parser.add_argument("end", nargs="?", type=int, help="End chapter")
    parser.add_argument("--list-voices", action="store_true", help="List available voices")
    parser.add_argument("--test", type=int, metavar="CH", help="Test mode: first 10 segments of chapter")
    parser.add_argument("--assemble", action="store_true", help="Assemble full audiobook from chapters")
    parser.add_argument("--status", action="store_true", help="Show generation status for all chapters")

    args = parser.parse_args()
    
    client = get_client()

    if args.list_voices:
        list_voices(client)
        return

    if args.assemble:
        assemble_full_audiobook()
        return

    if args.status:
        print(f"\n{'='*50}")
        print("AUDIOBOOK GENERATION STATUS")
        print(f"{'='*50}")
        scripts = sorted(SCRIPTS_DIR.glob("ch*_script.json"))
        for script_f in scripts:
            ch_num = int(script_f.stem.replace("_script", "").replace("ch", ""))
            audio_f = OUTPUT_DIR / f"ch_{ch_num:02d}.mp3"
            manifest_f = OUTPUT_DIR / f"ch_{ch_num:02d}_manifest.json"
            if audio_f.exists():
                size_mb = audio_f.stat().st_size / (1024*1024)
                if manifest_f.exists():
                    m = json.loads(manifest_f.read_text(encoding="utf-8"))
                    if m.get("failed"):
                        print(f"  Ch {ch_num:2d}: ⚠ PARTIAL ({size_mb:.1f} MB, chunks {m['failed']} failed)")
                    else:
                        print(f"  Ch {ch_num:2d}: ✓ complete ({size_mb:.1f} MB)")
                else:
                    print(f"  Ch {ch_num:2d}: ✓ ({size_mb:.1f} MB)")
            else:
                print(f"  Ch {ch_num:2d}: ✗ not generated")
        return

    voices = load_voices()
    if not voices:
        print("ERROR: No voices configured. Edit audiobook_voices.json with real voice IDs.")
        print("Run: python gen_audiobook.py --list-voices")
        sys.exit(1)

    unconfigured = [name for name, info in json.loads(VOICES_FILE.read_text(encoding="utf-8")).items()
                    if not name.startswith("_") and info.get("voice_id") == "REPLACE_WITH_VOICE_ID"]
    if unconfigured:
        print(f"WARNING: {len(unconfigured)} voices unconfigured: {unconfigured[:5]}")
        print(f"Edit audiobook_voices.json to set voice IDs.")

    if args.test:
        generate_chapter(args.test, client, voices, test_mode=True)
        return

    # Determine chapter range
    scripts = sorted(SCRIPTS_DIR.glob("ch*_script.json"))
    total = len(scripts)
    
    start = args.start or 1
    end = args.end or total

    print(f"Generating audiobook: chapters {start}-{end}")
    print(f"  Voices configured: {list(voices.keys())}")
    print()

    for ch_num in range(start, end + 1):
        generate_chapter(ch_num, client, voices)
        print()

    # Assemble
    assemble_full_audiobook()


if __name__ == "__main__":
    main()
