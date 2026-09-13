#!/usr/bin/env python3
"""Send a Markdown rep
ort to a Feishu group bot webhook.

The webho
ok URL is read from the FEISHU_WEBHOOK_URL en
vironment variable.
It is intentionally never
 stored in the repository or printed to logs.

"""

from __future__ import annotations

imp
ort argparse
import json
import os
import sys

import urllib.error
import urllib.request
fr
om pathlib import Path

MAX_CHARS = 28000


d
ef split_text(text: str, limit: int = MAX_CHA
RS) -> list[str]:
    """Split a report into 
bounded chunks without dropping any character
s."""
    if len(text) <= limit:
        retu
rn [text]
    chunks: list[str] = []
    star
t = 0
    while start < len(text):
        en
d = min(start + limit, len(text))
        if 
end < len(text):
            boundary = text.
rfind("\n", start, end)
            if bounda
ry > start + limit // 2:
                end 
= boundary
        chunks.append(text[start:e
nd])
        start = end
    return chunks



def send_chunk(webhook: str, text: str) -> No
ne:
    payload = {"msg_type": "text", "conte
nt": {"text": text}}
    request = urllib.req
uest.Request(
        webhook,
        data=j
son.dumps(payload, ensure_ascii=False).encode
("utf-8"),
        headers={"Content-Type": "
application/json"},
        method="POST",
  
  )
    try:
        with urllib.request.urlo
pen(request, timeout=20) as response:
       
     status = response.status
            bod
y = response.read().decode("utf-8", errors="r
eplace")
    except urllib.error.HTTPError as
 exc:
        raise RuntimeError(f"Feishu web
hook HTTP {exc.code}") from exc
    except ur
llib.error.URLError as exc:
        raise Run
timeError(f"Feishu webhook network error: {ex
c.reason}") from exc

    if status >= 300:
 
       raise RuntimeError(f"Feishu webhook HT
TP {status}")

    try:
        result = json
.loads(body)
    except json.JSONDecodeError:

        result = {}

    # Feishu bot respon
ses use either code or StatusCode depending o
n endpoint.
    code = result.get("code", res
ult.get("StatusCode"))
    if code not in (No
ne, 0, "0"):
        message = result.get("ms
g", result.get("StatusMessage", "unknown erro
r"))
        raise RuntimeError(f"Feishu webh
ook rejected the message: {message}")


def m
ain() -> int:
    parser = argparse.ArgumentP
arser(description=__doc__)
    parser.add_arg
ument("report", type=Path, help="Markdown rep
ort file")
    parser.add_argument(
        "
--dry-run",
        action="store_true",
    
    help="validate and report chunk sizes wit
hout sending",
    )
    args = parser.parse_
args()

    if not args.report.is_file():
   
     print(f"Report file not found: {args.rep
ort}", file=sys.stderr)
        return 2

   
 report = args.report.read_text(encoding="utf
-8").strip()
    if not report:
        print
("Report file is empty", file=sys.stderr)
   
     return 2

    chunks = split_text(report
)
    if args.dry_run:
        print(f"Feishu
 delivery dry-run OK: {len(chunks)} chunk(s),
 {len(report)} characters")
        return 0


    webhook = os.environ.get("FEISHU_WEBHOOK
_URL", "").strip()
    if not webhook.startsw
ith("https://"):
        print("FEISHU_WEBHOO
K_URL is missing or is not an HTTPS URL", fil
e=sys.stderr)
        return 2

    total = l
en(chunks)
    for index, chunk in enumerate(
chunks, start=1):
        prefix = f"【每�
�财经日报 {index}/{total}】\n\n" if tota
l > 1 else "【每日财经日报】\n\n"
   
     send_chunk(webhook, prefix + chunk)
    
print(f"Feishu delivery OK: {total} message(s
)")
    return 0


if __name__ == "__main__":

    raise SystemExit(main())


