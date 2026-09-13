#!/usr/bin/env python3
"""Send a Markdown report to a Feishu group bot as a Markdown card.

The webhook URL is read from FEISHU_WEBHOOK_URL. The report remains Markdown
in GitHub; the card body renders bold labels and links in Feishu so it does
not depend on Feishu showing raw Markdown syntax as plain text.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

MAX_CHARS = 16000


def split_text(text: str, limit: int = MAX_CHARS) -> list[str]:
    """Split a report into bounded chunks without dropping any characters."""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            boundary = text.rfind("\n", start, end)
            if boundary > start + limit // 2:
                end = boundary
        chunks.append(text[start:end])
        start = end
    return chunks


def markdown_body(markdown: str, fallback_title: str) -> tuple[str, str]:
    """Extract the H1 title and make H2/H3 headings visibly bold in lark_md."""
    title = fallback_title
    body_lines: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip() or fallback_title
            continue
        if stripped.startswith("## "):
            body_lines.append(f"**{stripped[3:].strip()}**")
            continue
        if stripped.startswith("### ") or stripped.startswith("#### "):
            heading = stripped.lstrip("#").strip()
            body_lines.append(f"  **{heading}**")
            continue
        body_lines.append(line)
    body = "\n".join(body_lines).strip() or "（日报内容为空）"
    return title[:80], body


def markdown_to_card(markdown: str, fallback_title: str) -> dict[str, object]:
    """Map report Markdown to a Feishu interactive card with lark_md content."""
    title, body = markdown_body(markdown, fallback_title)
    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "blue",
                "title": {"tag": "plain_text", "content": title},
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": body},
                }
            ],
        },
    }


def send_chunk(webhook: str, text: str, index: int, total: int) -> None:
    fallback_title = "每日财经日报" if total == 1 else f"每日财经日报（{index}/{total}）"
    payload = markdown_to_card(text, fallback_title)
    if total > 1:
        title = payload["card"]["header"]["title"]["content"]
        payload["card"]["header"]["title"]["content"] = f"{title}（{index}/{total}）"[:80]
    request = urllib.request.Request(
        webhook,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Feishu webhook HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Feishu webhook network error: {exc.reason}") from exc

    if status >= 300:
        raise RuntimeError(f"Feishu webhook HTTP {status}")
    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        result = {}
    code = result.get("code", result.get("StatusCode"))
    if code not in (None, 0, "0"):
        message = result.get("msg", result.get("StatusMessage", "unknown error"))
        raise RuntimeError(f"Feishu webhook rejected the message: {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Markdown report file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and report Markdown-card chunk sizes without sending",
    )
    args = parser.parse_args()

    if not args.report.is_file():
        print(f"Report file not found: {args.report}", file=sys.stderr)
        return 2
    report = args.report.read_text(encoding="utf-8").strip()
    if not report:
        print("Report file is empty", file=sys.stderr)
        return 2

    chunks = split_text(report)
    cards = [markdown_to_card(chunk, "每日财经日报") for chunk in chunks]
    if args.dry_run:
        body_chars = sum(len(card["card"]["elements"][0]["text"]["content"]) for card in cards)
        print(f"Feishu Markdown-card dry-run OK: {len(chunks)} chunk(s), {len(report)} characters, {body_chars} body characters")
        return 0

    webhook = os.environ.get("FEISHU_WEBHOOK_URL", "").strip()
    if not webhook.startswith("https://"):
        print("FEISHU_WEBHOOK_URL is missing or is not an HTTPS URL", file=sys.stderr)
        return 2

    total = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        send_chunk(webhook, chunk, index, total)
    print(f"Feishu Markdown-card delivery OK: {total} message(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())