#!/usr/bin/env python3
"""Tests for the shared Anthropic-compatible LLM client."""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))

import llm_client


class LlmClientTests(unittest.TestCase):
    def test_anthropic_defaults(self):
        with mock.patch.dict(
            llm_client.os.environ,
            {"AUTONOVEL_LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "ant-key"},
            clear=True,
        ):
            self.assertEqual(llm_client.get_provider(), "anthropic")
            self.assertEqual(llm_client.get_api_key(), "ant-key")
            self.assertEqual(llm_client.get_api_base_url(), llm_client.DEFAULT_ANTHROPIC_BASE_URL)
            self.assertEqual(
                llm_client.default_model_for_role("writer", "claude-sonnet-4-6"),
                "claude-sonnet-4-6",
            )

    def test_minimax_defaults(self):
        with mock.patch.dict(
            llm_client.os.environ,
            {"AUTONOVEL_LLM_PROVIDER": "minimax", "MINIMAX_API_KEY": "mini-key"},
            clear=True,
        ):
            self.assertEqual(llm_client.get_provider(), "minimax")
            self.assertEqual(llm_client.get_api_key(), "mini-key")
            self.assertEqual(llm_client.get_api_base_url(), llm_client.DEFAULT_MINIMAX_BASE_URL)
            self.assertEqual(
                llm_client.default_model_for_role("judge", "claude-opus-4-6"),
                llm_client.DEFAULT_MINIMAX_MODEL,
            )

    def test_base_url_override_wins(self):
        with mock.patch.dict(
            llm_client.os.environ,
            {
                "AUTONOVEL_LLM_PROVIDER": "minimax",
                "MINIMAX_API_KEY": "mini-key",
                "AUTONOVEL_API_BASE_URL": "https://example.com/custom/",
            },
            clear=True,
        ):
            self.assertEqual(llm_client.get_api_base_url(), "https://example.com/custom")
            self.assertEqual(
                llm_client.messages_endpoint(),
                "https://example.com/custom/v1/messages",
            )

    def test_extract_text_blocks(self):
        data = {
            "content": [
                {"type": "text", "text": "hello"},
                {"type": "text", "text": " world"},
            ]
        }
        self.assertEqual(llm_client.extract_text_from_response(data), "hello world")

    def test_extract_text_ignores_thinking_blocks(self):
        data = {
            "content": [
                {"type": "thinking", "thinking": "step 1"},
                {"type": "text", "text": "final answer"},
            ]
        }
        self.assertEqual(llm_client.extract_text_from_response(data), "final answer")

    def test_extract_text_requires_text_blocks(self):
        with self.assertRaisesRegex(ValueError, "text blocks"):
            llm_client.extract_text_from_response(
                {"content": [{"type": "thinking", "thinking": "internal"}]}
            )

    def test_minimax_headers_skip_beta(self):
        response = mock.Mock()
        response.json.return_value = {"content": [{"type": "text", "text": "ok"}]}
        response.raise_for_status.return_value = None

        with mock.patch.dict(
            llm_client.os.environ,
            {"AUTONOVEL_LLM_PROVIDER": "minimax", "MINIMAX_API_KEY": "mini-key"},
            clear=True,
        ):
            with mock.patch("llm_client.httpx.post", return_value=response) as post_mock:
                llm_client.call_text_model(
                    model="MiniMax-M2.7",
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=16,
                    temperature=0.1,
                    timeout=5,
                    include_beta=True,
                )

        headers = post_mock.call_args.kwargs["headers"]
        self.assertNotIn("anthropic-beta", headers)
        self.assertEqual(headers["x-api-key"], "mini-key")

    def test_anthropic_headers_include_beta_when_requested(self):
        response = mock.Mock()
        response.json.return_value = {"content": [{"type": "text", "text": "ok"}]}
        response.raise_for_status.return_value = None

        with mock.patch.dict(
            llm_client.os.environ,
            {"AUTONOVEL_LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "ant-key"},
            clear=True,
        ):
            with mock.patch("llm_client.httpx.post", return_value=response) as post_mock:
                llm_client.call_text_model(
                    model="claude-sonnet-4-6",
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=16,
                    temperature=0.1,
                    timeout=5,
                    include_beta=True,
                )

        headers = post_mock.call_args.kwargs["headers"]
        self.assertEqual(headers["anthropic-beta"], llm_client.ANTHROPIC_BETA)


if __name__ == "__main__":
    unittest.main()
