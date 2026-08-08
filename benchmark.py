#!/usr/bin/env python3
"""SyntaxAI mobile optimisation benchmark (Before vs After).

Measures concrete "after" metrics and contrasts them with the documented
"before" baseline (unbounded context, full file reads, no token budget).

Run:  python benchmark.py
"""

from __future__ import annotations

import os
import resource
import time

from syntaxai.core.config import Config
from syntaxai.core.context import ContextManager, truncate_for_context


def _rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def bench_startup() -> float:
    from syntaxai.core.agent import Agent

    t0 = time.perf_counter()
    Agent(Config())
    return time.perf_counter() - t0


def bench_context_memory_and_tokens() -> dict:
    cfg = Config()
    ctx = ContextManager(cfg)

    # Simulate reading a 200 KB source file and returning it as a tool result.
    big = ("print('hello world')\n" * 8000)  # ~ 200 KB
    before_chars = len(big)
    after_chars = len(truncate_for_context(big, cfg.max_tool_output_chars))

    ctx.add_message("user", "read the big file")
    ctx.add_message(
        "tool", big,
        tool_results=[{"tool": "read_file", "result": big}],
    )
    # Provider-facing payload (after truncation)
    after_payload = ctx.get_messages_for_provider()
    after_payload_chars = sum(len(str(m.get("content", ""))) for m in after_payload)

    return {
        "before_chars": before_chars,
        "after_chars": after_chars,
        "after_payload_chars": after_payload_chars,
        "token_estimate_after": ctx.estimate_tokens(
            "".join(str(m.get("content", "")) for m in after_payload)
        ),
        "rss_mb": _rss_mb(),
    }


def main() -> None:
    print("=" * 64)
    print(" SyntaxAI Mobile Optimisation Benchmark")
    print("=" * 64)

    cfg = Config()
    startup = bench_startup()
    print(f"\n[Startup] Agent construction time : {startup*1000:.1f} ms")

    metrics = bench_context_memory_and_tokens()
    print("\n[Context / Token efficiency] (200 KB file read)")
    print(f"  Before (no truncation) payload : {metrics['before_chars']:,} chars")
    print(f"  After  (truncated)      payload : {metrics['after_payload_chars']:,} chars")
    saved = 1 - metrics["after_payload_chars"] / max(metrics["before_chars"], 1)
    print(f"  Token/context saving            : {saved*100:.1f}%")
    print(f"  Est. tokens sent to LLM (after) : {metrics['token_estimate_after']:,}")
    print(f"  Process RSS                     : {metrics['rss_mb']:.1f} MB")

    print("\n" + "=" * 64)
    print(" Summary (documented baseline vs optimised)")
    print("=" * 64)
    print(f"  {'Metric':<28}{'Before':>14}{'After':>14}")
    print(f"  {'Max context tokens':<28}{'unbounded':>14}{str(cfg.max_context_tokens):>14}")
    print(f"  {'Tool output cap':<28}{'unbounded':>14}{str(cfg.max_tool_output_chars)+'c':>14}")
    print(f"  {'Concurrency (mobile)':<28}{'unbounded':>14}{str(cfg.max_concurrent_tasks):>14}")
    print(f"  {'Provider retries':<28}{'1 (linear)':>14}{str(cfg.max_retries)+' (exp)':>14}")
    print(f"  {'Context trimming':<28}{'by count':>14}{'by tokens':>14}")
    print(f"  {'Skill loading':<28}{'eager':>14}{'lazy':>14}")
    print("=" * 64)


if __name__ == "__main__":
    main()
