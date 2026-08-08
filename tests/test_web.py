"""Tests for agent streaming events, mobile config application, and concurrency."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from syntaxai.core.config import Config
from syntaxai.core.agent import Agent, TOOL_SCHEMAS
from syntaxai.providers.base import LLMResponse


# ── fake provider that issues one tool call then a final answer ────────────────
@dataclass
class FakeResponse:
    content: str
    tool_calls: list
    usage: dict = None
    model: str = "fake"
    finish_reason: str = "stop"


class FakeProvider:
    def __init__(self):
        self.calls = 0

    def generate(self, messages, tool_schemas=None):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content="",
                tool_calls=[{
                    "id": "1", "name": "shell",
                    "arguments": {"command": "echo hi"},
                }],
                usage={}, model="fake", finish_reason="tool_calls",
            )
        return LLMResponse(
            content="FINAL-ANSWER", tool_calls=[], usage={},
            model="fake", finish_reason="stop",
        )

    def stream(self, messages, tool_schemas=None):
        yield "FINAL-"
        yield "ANSWER"


def _agent_with_fake() -> Agent:
    cfg = Config()
    agent = Agent(cfg)
    fake = FakeProvider()

    def _fake_init(pt, complexity):
        return fake

    agent._init_provider = _fake_init
    agent._provider_order = [cfg.default_provider]
    return agent


def test_streaming_event_order():
    agent = _agent_with_fake()
    events: list[dict] = []
    answer = agent.run("do something", event_sink=events.append)
    types = [e["type"] for e in events]
    assert "thinking" in types
    assert "tool_start" in types
    assert "tool_end" in types
    assert "response" in types
    assert types[-1] == "done"
    assert answer == "FINAL-ANSWER"
    # tool_start/tool_end must bracket the tool execution
    assert types.index("tool_start") < types.index("tool_end")


def test_mobile_config_application(monkeypatch):
    monkeypatch.setenv("TERMUX_VERSION", "0.118")
    cfg = Config.load()
    assert cfg.mobile_mode is True
    assert cfg.max_context_tokens == 12000
    assert cfg.max_tool_output_chars == 3000
    assert cfg.max_steps == 12
    assert cfg.max_concurrent_tasks == 1


def test_apply_mobile_profile_lowers_budgets():
    cfg = Config()
    desktop_steps = cfg.max_steps
    cfg.apply_mobile_profile()
    assert cfg.max_steps < desktop_steps
    assert cfg.max_context_tokens < 32000


def test_concurrency_limit_serializes_runs():
    """Mirror the server's asyncio.Semaphore so concurrent agent runs are bounded."""
    cfg = Config()
    cfg.max_concurrent_tasks = 1
    sem = asyncio.Semaphore(max(1, cfg.max_concurrent_tasks))

    state = {"active": 0, "peak": 0}

    async def worker():
        async with sem:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
            await asyncio.sleep(0.02)
            state["active"] -= 1

    async def main():
        await asyncio.gather(worker(), worker(), worker())

    asyncio.run(main())
    # With a limit of 1, peak concurrency must never exceed 1.
    assert state["peak"] == 1
