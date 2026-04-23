#!/usr/bin/env python3
"""Shared Anthropic-compatible LLM client for Anthropic and MiniMax."""

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_MINIMAX = "minimax"
SUPPORTED_PROVIDERS = {PROVIDER_ANTHROPIC, PROVIDER_MINIMAX}

ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_BETA = "context-1m-2025-08-07"

DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_MINIMAX_BASE_URL = "https://api.minimaxi.com/anthropic"
DEFAULT_MINIMAX_MODEL = "MiniMax-M2.7"


def get_provider() -> str:
    provider = os.environ.get("AUTONOVEL_LLM_PROVIDER", PROVIDER_ANTHROPIC).strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            "AUTONOVEL_LLM_PROVIDER must be one of: anthropic, minimax"
        )
    return provider


def provider_api_key_env(provider: str | None = None) -> str:
    provider = provider or get_provider()
    return "MINIMAX_API_KEY" if provider == PROVIDER_MINIMAX else "ANTHROPIC_API_KEY"


def get_api_key(provider: str | None = None) -> str:
    provider = provider or get_provider()
    return os.environ.get(provider_api_key_env(provider), "")


def default_model_for_role(role: str, anthropic_default: str) -> str:
    if get_provider() == PROVIDER_MINIMAX:
        return DEFAULT_MINIMAX_MODEL
    return anthropic_default


def get_api_base_url(provider: str | None = None) -> str:
    provider = provider or get_provider()
    override = os.environ.get("AUTONOVEL_API_BASE_URL", "").strip()
    if override:
        return override.rstrip("/")
    if provider == PROVIDER_MINIMAX:
        return DEFAULT_MINIMAX_BASE_URL
    return DEFAULT_ANTHROPIC_BASE_URL


def messages_endpoint(base_url: str | None = None) -> str:
    base_url = (base_url or get_api_base_url()).rstrip("/")
    if base_url.endswith("/v1"):
        return f"{base_url}/messages"
    return f"{base_url}/v1/messages"


def build_headers(
    api_key: str | None = None,
    provider: str | None = None,
    *,
    include_beta: bool = False,
) -> dict[str, str]:
    provider = provider or get_provider()
    api_key = api_key if api_key is not None else get_api_key(provider)
    if not api_key:
        env_var = provider_api_key_env(provider)
        raise RuntimeError(f"{env_var} is not set")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    if include_beta and provider == PROVIDER_ANTHROPIC:
        headers["anthropic-beta"] = ANTHROPIC_BETA
    return headers


def extract_text_from_response(data: dict) -> str:
    content = data.get("content")
    if isinstance(content, str):
        text = content.strip()
        if text:
            return text
    if not isinstance(content, list):
        raise ValueError(f"LLM response is missing a valid content field. Response: {data}")

    text_blocks = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and block.get("text"):
            text_blocks.append(block["text"])

    text = "".join(text_blocks).strip()
    if not text:
        if data.get("stop_reason") == "max_tokens":
            raise ValueError(f"LLM reached max_tokens limit before outputting text. Please increase max_tokens. Response: {data}")
        raise ValueError(f"LLM response did not contain any text blocks. Response: {data}")
    return text


def call_text_model(
    *,
    model: str,
    messages: list[dict],
    system: str | None = None,
    max_tokens: int,
    temperature: float,
    timeout: int,
    include_beta: bool = False,
    extra_payload: dict | None = None,
) -> str:
    provider = get_provider()
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages,
    }
    if system is not None:
        payload["system"] = system
    if extra_payload:
        payload.update(extra_payload)

    response = httpx.post(
        messages_endpoint(),
        headers=build_headers(provider=provider, include_beta=include_beta),
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return extract_text_from_response(response.json())
