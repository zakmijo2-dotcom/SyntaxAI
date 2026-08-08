"""Shared output-truncation helpers for tools (mobile/context protection).

Files, shell output and git diffs can be enormous. We cap how much text a tool
returns using a head+tail strategy so a single `cat huge.log` cannot exhaust
RAM or blow the LLM context window on a small device.
"""

from __future__ import annotations

# Default cap applied at the *tool* boundary. The agent/context can tighten this
# further (max_tool_output_chars) before anything is sent to the LLM.
DEFAULT_MAX_CHARS: int = 30000


def truncate_output(text: str, limit: int = DEFAULT_MAX_CHARS) -> str:
    """Return *text* capped to *limit* chars, keeping the head and tail."""
    if limit <= 0 or len(text) <= limit:
        return text
    keep_head = max(limit // 2, 256)
    keep_tail = limit - keep_head
    head = text[:keep_head]
    tail = text[-keep_tail:]
    omitted = len(text) - keep_head - keep_tail
    return (
        f"{head}\n\n"
        f"... [output truncated: {omitted} chars omitted of {len(text)} total] ...\n\n"
        f"{tail}"
    )


def read_text_truncated(
    path, max_chars: int = DEFAULT_MAX_CHARS, encoding: str = "utf-8"
) -> str:
    """Read a text file returning at most *max_chars* (head + tail).

    Avoids loading the whole file into memory for very large files.
    """
    import os

    try:
        size = os.path.getsize(path)
    except OSError:
        size = None

    if size is not None and size <= max_chars:
        with open(path, "r", encoding=encoding, errors="replace") as f:
            return f.read()

    # Too big: read head and tail separately.
    keep_head = max(max_chars // 2, 256)
    keep_tail = max(max_chars - keep_head, 256)
    head_lines: list[str] = []
    head_bytes = 0
    tail_lines: list[str] = []

    try:
        with open(path, "r", encoding=encoding, errors="replace") as f:
            # Read head
            for line in f:
                head_lines.append(line)
                head_bytes += len(line)
                if head_bytes >= keep_head:
                    break
            # Read tail by scanning the rest (acceptable for our size caps)
            tail_lines = f.read().splitlines()[-200:]
    except Exception:
        # Fallback: best-effort full read then truncate
        try:
            with open(path, "r", encoding=encoding, errors="replace") as f:
                return truncate_output(f.read(), max_chars)
        except Exception:
            return ""

    head_text = "".join(head_lines)
    tail_text = "\n".join(tail_lines)
    omitted = (size or 0) - len(head_text) - len(tail_text)
    return (
        f"{head_text}\n\n"
        f"... [file truncated: {max(omitted, 0)} bytes omitted of {size or '?'} total] ...\n\n"
        f"{tail_text}"
    )
