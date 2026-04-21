#!/usr/bin/env python3
"""Minimal live smoke test for the configured text model provider."""

import argparse
import os
import sys

from llm_client import (
    call_text_model,
    default_model_for_role,
    get_api_base_url,
    get_api_key,
    get_provider,
    provider_api_key_env,
)


def main():
    parser = argparse.ArgumentParser(description="Smoke test the configured LLM provider")
    parser.add_argument("--prompt", default="Reply with exactly: OK")
    parser.add_argument("--model", default=None, help="Override the model name")
    parser.add_argument("--max-tokens", type=int, default=32)
    args = parser.parse_args()

    provider = get_provider()
    if not get_api_key():
        print(f"ERROR: Set {provider_api_key_env()} in .env first", file=sys.stderr)
        sys.exit(1)

    model = args.model or os.environ.get(
        "AUTONOVEL_WRITER_MODEL",
        default_model_for_role("writer", "claude-sonnet-4-6"),
    )

    print(f"Provider: {provider}", file=sys.stderr)
    print(f"Base URL: {get_api_base_url()}", file=sys.stderr)
    print(f"Model: {model}", file=sys.stderr)

    result = call_text_model(
        model=model,
        max_tokens=args.max_tokens,
        temperature=0.1,
        system="You are a health check endpoint. Follow the user's instruction exactly.",
        messages=[{"role": "user", "content": args.prompt}],
        timeout=60,
    )
    print(result)


if __name__ == "__main__":
    main()
