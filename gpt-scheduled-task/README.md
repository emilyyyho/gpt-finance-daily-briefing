# GPT 财经日报工作流

完整运行、补发、安全边界和配置说明见仓库根目录 README.md。

- run_briefing.py：独立采集、分期归档、持久化投递状态。
- collect_news.py：多来源新闻与市场快照。
- send_feishu.py：严格确认响应与卡片分片。
- task-prompt.md：每天 07:40 / 19:40 执行的 ChatGPT 分析任务提示词。
- knowledge-framework.md：金融课方法摘要。
- analysis/YYYY-MM-DD-am.md：早报 AI 分析归档。
- analysis/YYYY-MM-DD-pm.md：晚报 AI 分析归档。

## 两条职责边界

ChatGPT 只负责读取公开新闻和市场快照、生成带证据的 AI 分析，并通过 GitHub 连接器写入 `analysis/`。它不读取或发送飞书 Webhook，也不直接修改 `reports/` 和 `docs/data/`。

GitHub Actions 负责采集 NewsNow、生成基础日报、合并已经归档的 AI 分析、发送飞书群机器人消息和发布看板。若 AI 分析晚到，Actions 会补发一条分析附加消息，不重复发送整篇新闻。

如果 ChatGPT 任务无法写入仓库，基础新闻版仍可投递；看板和日报会明确显示“AI 分析未生成”，不能把基础新闻版误称为完整研判。
