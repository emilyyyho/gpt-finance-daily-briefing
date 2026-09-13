"""Validate the no-secret configuration used 
by the ChatGPT task."""

from __future__ impo
rt annotations

import json
from pathlib impo
rt Path
from urllib.parse import urlparse

RO
OT = Path(__file__).resolve().parent
CONFIG_P
ATH = ROOT / "newsnow_task.json"


def main()
 -> None:
    config = json.loads(CONFIG_PATH
.read_text(encoding="utf-8"))

    assert con
fig["timezone"] == "Asia/Shanghai"
    assert
 config["schedule"]["local_time"] == "20:30"

    assert config["schedule"]["cron_utc"] == 
"30 12 * * *"

    newsnow = config["newsnow"
]
    assert newsnow["base_url"] == "https://
newsnow.busiyi.world/api/s"
    assert len(ne
wsnow["source_ids"]) == 16
    assert len(new
snow["endpoints"]) == 16
    assert newsnow["
max_age_hours"] == 24
    assert 1 <= newsnow
["min_china_items"] <= newsnow["max_items"]


    delivery = config["delivery"]
    assert 
delivery["primary"] == "github-actions-feishu
"

    github = delivery["github"]
    assert
 github["enabled"] is True
    assert github[
"repository"] == "emilyyyho/finance-daily-bri
efing"
    assert github["branch"] == "master
"
    assert github["report_path_template"] =
= "reports/{date}.md"
    assert github["comm
it_required"] is True

    feishu = delivery[
"feishu"]
    assert feishu["enabled"] is Tru
e
    assert feishu["mode"] == "github_action
s_webhook"
    assert feishu["secret_name"] =
= "FEISHU_WEBHOOK_URL"

    assert config["ai
"]["external_api"] is False

    for endpoint
 in newsnow["endpoints"]:
        parsed = ur
lparse(endpoint["url"])
        assert parsed
.scheme == "https", endpoint["url"]
        a
ssert parsed.netloc == "newsnow.busiyi.world"
, endpoint["url"]
        assert "key=" not i
n endpoint["url"].lower(), "API keys must not
 be committed"

    serialized = json.dumps(c
onfig, ensure_ascii=False).lower()
    assert
 "replace-with" not in serialized
    assert 
"replace_with" not in serialized
    assert "
webhook" not in serialized or "github_actions
_webhook" in serialized

    print("GPT sched
uled task configuration: OK")


if __name__ =
= "__main__":
    main()


