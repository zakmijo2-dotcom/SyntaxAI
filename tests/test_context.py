"""Tests for token-aware context management and output truncation."""

from __future__ import annotations

from syntaxai.core.config import Config
from syntaxai.core.context import ContextManager, truncate_for_context


def _cfg() -> Config:
    return Config()


def test_truncate_head_tail():
    text = "A" * 1000 + "B" * 1000
    out = truncate_for_context(text, 120)
    assert "output truncated" in out
    assert out.startswith("A" * 60)
    assert out.endswith("B" * 58)


def test_truncate_passthrough_when_small():
    assert truncate_for_context("short", 100) == "short"


def test_tool_output_truncated_before_provider():
    cfg = _cfg()
    ctx = ContextManager(cfg)
    big = "x" * 50000
    ctx.add_message("tool", big, tool_results=[{"tool": "read_file", "result": big}])
    msgs = ctx.get_messages_for_provider()
    tool = [m for m in msgs if m["role"] == "tool"][0]
    assert len(tool["content"]) <= cfg.max_tool_output_chars + 200
    assert "output truncated" in tool["content"]


def test_priority_retention_keeps_system_and_latest_user():
    cfg = _cfg()
    ctx = ContextManager(cfg)
    ctx.add_message("system", "SYS-PROMPT")
    ctx.max_context_tokens = 80  # force aggressive trimming
    for i in range(10):
        ctx.add_message("user", "u" * 10)
        ctx.add_message("assistant", "a" * 10)
    ctx.add_message("user", "FINAL-QUESTION")

    msgs = ctx.get_messages_for_provider()
    roles = [m["role"] for m in msgs]
    assert "system" in roles  # never evicted
    assert msgs[-1]["content"] == "FINAL-QUESTION"  # latest user retained


def test_token_budget_evicts_old_messages():
    cfg = _cfg()
    ctx = ContextManager(cfg)
    ctx.max_context_tokens = 60
    for i in range(15):
        ctx.add_message("user", "msg-%d " % i * 5)
    # total tokens should now be within budget (allowing the latest message)
    assert ctx.total_tokens() <= ctx.max_context_tokens + 50
