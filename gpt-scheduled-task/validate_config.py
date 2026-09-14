"""Validate the no-secret configuration used by the ChatGPT task."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "newsnow_task.json"


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["timezone"] == "Asia/Shanghai"
    assert config["schedule"]["local_times"] == ["08:00", "20:00"]
    assert config["schedule"]["cron_utc"] == "0 0,12 * * *"
    assert config["schedule"]["refresh_cron_utc"] == "17,47 * * * *"
    workflow = (ROOT.parent / ".github/workflows/deliver-feishu.yml").read_text(encoding="utf-8")
    assert "cron: '0 0,12 * * *'" in workflow
    assert "cron: '17,47 * * * *'" in workflow

    newsnow = config["newsnow"]
    assert newsnow["base_url"] == "https://newsnow.busiyi.world/api/s"
    assert len(newsnow["source_ids"]) == 16
    assert len(newsnow["endpoints"]) == 16
    assert newsnow["max_age_hours"] == 24
    assert 1 <= newsnow["min_china_items"] <= newsnow["max_items"]

    analysis = config["analysis"]
    framework_url = analysis["knowledge_framework_url"]
    assert framework_url.startswith("https://raw.githubusercontent.com/emilyyyho/")
    assert framework_url.endswith("/gpt-scheduled-task/knowledge-framework.md")
    assert analysis["require_evidence_labels"] is True
    assert analysis["require_market_summary"] is True
    assert analysis["market_summary_labels"] == [
        "宏观环境",
        "流动性与政策",
        "大盘状态",
        "全球联动",
        "基准结论",
    ]

    delivery = config["delivery"]
    assert delivery["primary"] == "github-actions-feishu"

    github = delivery["github"]
    assert github["enabled"] is True
    assert github["repository"] == "emilyyyho/gpt-finance-daily-briefing"
    assert github["branch"] == "main"
    assert github["report_path_template"] == "reports/{date}-{slot}.md"
    assert github["commit_required"] is True

    feishu = delivery["feishu"]
    assert feishu["enabled"] is True
    assert feishu["mode"] == "github_actions_webhook"
    assert feishu["secret_name"] == "FEISHU_WEBHOOK_URL"

    assert config["ai"]["external_api"] is False

    for endpoint in newsnow["endpoints"]:
        parsed = urlparse(endpoint["url"])
        assert parsed.scheme == "https", endpoint["url"]
        assert parsed.netloc == "newsnow.busiyi.world", endpoint["url"]
        assert "key=" not in endpoint["url"].lower(), "API keys must not be committed"

    serialized = json.dumps(config, ensure_ascii=False).lower()
    assert "replace-with" not in serialized
    assert "replace_with" not in serialized
    assert "webhook" not in serialized or "github_actions_webhook" in serialized

    print("GPT scheduled task configuration: OK")


if __name__ == "__main__":
    main()
