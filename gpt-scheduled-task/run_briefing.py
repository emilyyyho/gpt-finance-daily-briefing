"""Collect, publish and deliver two daily editions with optional ChatGPT analysis."""
from datetime import datetime
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from collect_news import CST, collect, iso, timestamp
from send_feishu import DeliveryRejected, send_chunk, split_text

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs/data"
REPO_URL = "https://github.com/emilyyyho/gpt-finance-daily-briefing"
SITE_URL = "https://emilyyyho.github.io/gpt-finance-daily-briefing/"


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def checkpoint(enabled):
    if not enabled:
        return
    # The workflow-wide concurrency group serializes all automated writers.
    # If persistence fails, STOP before the next external send.
    subprocess.run(["git", "add", "docs/data", "docs/reports", "reports"], cwd=ROOT, check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
        return
    subprocess.run(["git", "commit", "-m", "Update briefing data and delivery receipts"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)


def due_editions(now):
    date = now.astimezone(CST).date().isoformat()
    return [(f"{date}-{slot}", hour, label) for slot, hour, label in (("am", 8, "早报"), ("pm", 20, "晚报")) if now.astimezone(CST).hour >= hour]


def edition_news(snapshot):
    china = [n for n in snapshot["news"] if n["category"] == "中国财经"]
    world = [n for n in snapshot["news"] if n["category"] == "世界要闻"]
    selected = china[:14] + world[:6]
    return selected


def analysis_path(key):
    return ROOT / "analysis" / f"{key}.md"


def analysis_text(key):
    path = analysis_path(key)
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()[:16000]


def render_report(snapshot, key, label):
    selected = edition_news(snapshot)
    lines = [f"# 财经日报｜{key[:10]} {label}", "", f"**实际数据截止：**{snapshot['generated_at']}",
             "**范围：**最近 24 小时；按来源与发布时间筛选，不代表全网热度。", "",
             f"[打开财经看板]({SITE_URL})", "", "## 新闻要点"]
    if not selected:
        lines.append("本期新闻采集失败：没有可验证发布时间的近期新闻。以下不是完整新闻日报。")
    for i, item in enumerate(selected, 1):
        lines += [f"### {i}. {item['title']}", f"**来源：**{item['source']} · {item['category']}",
                  f"**发布时间：**{item['published_at']}", f"[查看原文]({item['url']})", ""]
    lines += ["## 全球市场"]
    for market in snapshot["markets"]:
        if market["status"] != "ok":
            lines.append(f"- {market['name']}：数据暂不可得。")
            continue
        change = market.get("change_pct")
        change_text = f"{change:+.2f}%" if change is not None else "涨跌幅暂不可得"
        lines.append(f"- {market['name']}：{market['price']:,.2f} {market['unit']}，{change_text}；报价时间 {market['quoted_at']}。[来源]({market['url']})")
    lines += ["", "行情可能延迟；期货为供应商近月连续口径，不等于现货价格。", "", "## AI 与长期配置观察"]
    analysis = analysis_text(key)
    if analysis:
        lines += ["以下为当期独立提交的 AI 分析，事实仍应核对原文。", analysis]
    else:
        lines += ["本期为基础新闻版，AI 分析未生成。", "观察框架：增长与通胀 → 政策与流动性 → 资产估值与盈利。缺少足够宏观证据时不判断周期，也不生成买卖或仓位建议。"]
    bad = [s["name"] for s in snapshot["sources"] if s["status"] != "ok"]
    if bad:
        lines += ["", "**本期无可用新数据的来源：**" + "、".join(bad)]
    lines += ["", f"本期 {len(selected)} 条；数量不足如实展示，不以旧闻补足。"]
    return "\n".join(lines) + "\n"


def render_analysis_addendum(snapshot, key, label):
    analysis = analysis_text(key)
    if not analysis:
        return ""
    return "\n".join([
        f"# AI 与长期配置观察｜{key[:10]} {label}",
        "",
        f"**基于数据截止：**{snapshot['generated_at']}",
        "**说明：**这是对已经发送的基础新闻日报的补充，不构成买卖或仓位建议。",
        "",
        analysis,
        "",
        f"[打开财经看板]({SITE_URL})",
        "",
    ])


def deliver_edition(entry, webhook, save, sender=send_chunk):
    """Persist intent before each message; persist acknowledgements afterwards.

    A crash or timeout leaves 'sending/uncertain' and requires manual review.
    Retrying such a webhook blindly cannot guarantee exactly-once delivery.
    """
    parts = entry["parts"]
    for index, part in enumerate(parts, 1):
        if part["status"] == "sent":
            continue
        if part["status"] in ("sending", "uncertain"):
            entry["status"] = "uncertain"
            save()
            return
        if part.get("attempts", 0) >= 3:
            entry["status"] = "failed"
            save()
            return
        part.update(status="sending", attempts=part.get("attempts", 0) + 1)
        entry["status"] = "sending"
        save()
        try:
            sender(webhook, part["text"], index, len(parts))
        except DeliveryRejected:
            part["status"] = "rejected"
            entry.update(status="retry_pending", error="飞书明确拒绝，最多尝试三次；检查工作流日志与机器人配置。")
            save()
            return
        except Exception:
            part["status"] = "uncertain"
            entry.update(status="uncertain", error="响应不明确；为避免重复未自动重发，请核对飞书群。")
            save()
            return
        part.update(status="sent", acknowledged_at=iso(datetime.now(CST)))
        save()
        if index < len(parts):
            time.sleep(1)
    entry.update(status="sent", sent_at=iso(datetime.now(CST)))
    entry.pop("error", None)
    save()


def public_status(state):
    # Raw message parts stay in the ledger for resumable delivery; public UI
    # only needs the short status summary. Neither contains any credentials.
    return {key: {k: v for k, v in entry.items() if k != "parts"} for key, entry in state.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    now = datetime.now(CST)
    snapshot = collect(now)
    DATA.mkdir(parents=True, exist_ok=True)
    for folder in ("reports", "docs/reports"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    state = read_json(DATA / "ledger.json", {})
    # Keep 30 days of detailed delivery state; report files remain archived.
    state = {k: v for k, v in state.items() if (now.date() - datetime.fromisoformat(k[:10]).date()).days < 30}
    write_json(DATA / "latest.json", snapshot)

    def save():
        write_json(DATA / "ledger.json", state)
        write_json(DATA / "status.json", public_status(state))
        checkpoint(args.persist)

    delivery_keys = []
    for key, hour, label in due_editions(now):
        delivery_keys.append(key)
        recovering = key in state and state[key]["kind"] == "outage" and state[key]["status"] == "sent" and edition_news(snapshot)
        untouched = key in state and all(p['status'] == 'pending' and not p.get('attempts') for p in state[key]['parts'])
        if key not in state or recovering or untouched:
            report = render_report(snapshot, key, label)
            # Create a separate immutable report for every delivery slot.
            (ROOT / "reports" / f"{key}.md").write_text(report, encoding="utf-8")
            (ROOT / "docs/reports" / f"{key}.md").write_text(report, encoding="utf-8")
            state[key] = {"status": "pending", "label": label, "planned_at": f"{key[:10]}T{hour:02d}:00:00+08:00",
                          "generated_at": snapshot["generated_at"], "news_count": len(edition_news(snapshot)),
                          "kind": "news" if edition_news(snapshot) else "outage", "report": f"reports/{key}.md",
                          "ai": bool(analysis_text(key)),
                          "parts": [{"text": chunk, "status": "pending"} for chunk in split_text(report)]}
        elif state[key].get("status") == "sent" and analysis_text(key) and not state[key].get("ai"):
            # If the ChatGPT task commits analysis after the base edition was
            # already delivered, refresh the archived report and send only a
            # separate addendum instead of duplicating the whole briefing.
            report = render_report(snapshot, key, label)
            (ROOT / "reports" / f"{key}.md").write_text(report, encoding="utf-8")
            (ROOT / "docs/reports" / f"{key}.md").write_text(report, encoding="utf-8")
            state[key]["ai"] = True
            analysis_key = f"{key}-analysis"
            addendum = render_analysis_addendum(snapshot, key, label)
            if addendum and analysis_key not in state:
                (ROOT / "reports" / f"{analysis_key}.md").write_text(addendum, encoding="utf-8")
                (ROOT / "docs/reports" / f"{analysis_key}.md").write_text(addendum, encoding="utf-8")
                state[analysis_key] = {
                    "status": "pending",
                    "label": "AI 与长期配置观察",
                    "planned_at": f"{key[:10]}T{hour:02d}:00:00+08:00",
                    "generated_at": snapshot["generated_at"],
                    "news_count": state[key]["news_count"],
                    "kind": "analysis",
                    "report": f"reports/{analysis_key}.md",
                    "ai": True,
                    "parts": [{"text": chunk, "status": "pending"} for chunk in split_text(addendum)],
                }
            if analysis_key in state:
                delivery_keys.append(analysis_key)
        if args.send and state[key]["status"] != "sent":
            webhook = os.environ.get("FEISHU_WEBHOOK_URL", "")
            if not webhook.startswith("https://"):
                state[key].update(status="failed", error="FEISHU_WEBHOOK_URL 未配置")
            else:
                deliver_edition(state[key], webhook, save)
        analysis_key = f"{key}-analysis"
        if analysis_key in state and analysis_key not in delivery_keys:
            delivery_keys.append(analysis_key)
        if args.send and analysis_key in state and state[analysis_key]["status"] != "sent":
            webhook = os.environ.get("FEISHU_WEBHOOK_URL", "")
            if not webhook.startswith("https://"):
                state[analysis_key].update(status="failed", error="FEISHU_WEBHOOK_URL 未配置")
            else:
                deliver_edition(state[analysis_key], webhook, save)
    save()
    problems = [key for key in delivery_keys if state[key]["status"] != "sent" or state[key]["kind"] == "outage"]
    print(json.dumps({"news": len(snapshot["news"]), "sources_ok": sum(s["status"] == "ok" for s in snapshot["sources"]), "unfulfilled_editions": problems}, ensure_ascii=False))
    # workflow still deploys the dashboard when delivery fails, so the failure
    # is visible without treating a successful static deployment as delivery.
    return 1 if args.send and problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
