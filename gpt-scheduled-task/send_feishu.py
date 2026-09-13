#!/usr/bin/env python3
"""Send a Markdown report to a Feishu group bot as a rich-text post.

The webhook URL is read from FEISHU_WEBHOOK_URL. Markdown headings, bold
labels, lists, and links are converted to Feishu post elements so the
message does not depend on Feishu rendering raw Markdown text.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

MAX_CHARS = 18000
INLINE_MARKUP = re.compile(r"(\*\*.+?\*\*|\[[^\]]+\]\([^)]+\))")


def split_text(text: str, limit: int = MAX_CHARS) -> list[str]:
    """Split a report into bounded chunks without dropping characters."""
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


def inline_elements(text: str) -> list[dict[str, object]]:
    """Convert the small Markdown subset used by the report into post tags."""
    elements: list[dict[str, object]] = []
    cursor = 0
    for match in INLINE_MARKUP.finditer(text):
        if match.start() > cursor:
            elements.append({"tag": "text", "text": text[cursor:match.start()]})
        token = match.group(0)
        if token.startswith("**") and token.endswith("**"):
            elements.append({"tag": "text", "text": token[2:-2], "style": ["bold"]})
        else:
            link = re.match(r"\[([^\]]+)\]\(([^)]+)\)", token)
            if link:
                elements.append({"tag": "a", "text": link.group(1), "href": link.group(2)})
            else:
                elements.append({"tag": "text", "text": token})
        cursor = match.end()
    if cursor < len(text):
        elements.append({"tag": "text", "text": text[cursor:]})
    return elements or [{"tag": "text", "text": ""}]


def markdown_to_post(markdown: str, fallback_title: str) -> dict[str, object]:
    """Map report Markdown to Feishu's zh_cn post payload."""
    title = fallback_title
    rows: list[list[dict[str, object]]] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            rows.append([{"tag": "text", "text": "\n"}])
            continue
        if line.startswith("# "):
            title = line[2:].strip() or fallback_title
            continue
        if line.startswith("## ") or line.startswith("### ") or line.startswith("#### "):
            level = len(line) - len(line.lstrip("#"))
            heading = line[level:].strip()
            if level >= 3:
                heading = "  " + heading
            rows.append([{ "tag": "text", "text": heading, "style": ["bold"] }])
            continue
        if line.startswith("- "):
            line = "• " + line[2:].strip()
        rows.append(inline_elements(line))
    if not rows:
        rows = [[{"tag": "text", "text": "（日报内容为空）"}]]
    return {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title[:80],
                    "content": rows,
                }
            }
        },
    }


def send_chunk(webhook: str, text: str, index: int, total: int) -> None:
    fallback_title = "每日财经日报" if total == 1 else f"每日财经日报（{index}/{total}）"
    payload = markdown_to_post(text, fallback_title)
    if total > 1:
        post = payload["content"]["post"]["zh_cn"]
        post["title"] = f"{post['title']}（{index}/{total}）"[:80]
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
        help="validate and report rich-text chunk sizes without sending",
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
    posts = [markdown_to_post(chunk, "每日财经日报") for chunk in chunks]
    if args.dry_run:
        rows = sum(len(post["content"]["post"]["zh_cn"]["content"]) for post in posts)
        print(f"Feishu rich-text dry-run OK: {len(chunks)} chunk(s), {len(report)} characters, {rows} rows")
        return 0

    webhook = os.environ.get("FEISHU_WEBHOOK_URL", "").strip()
    if not webhook.startswith("https://"):
        print("FEISHU_WEBHOOK_URL is missing or is not an HTTPS URL", file=sys.stderr)
        return 2

    total = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        send_chunk(webhook, chunk, index, total)
    print(f"Feishu rich-text delivery OK: {total} message(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())