# GPT Finance Daily Briefing

这是一个独立的每日财经日报仓库，不修改 TrendRadar 原项目。它由 ChatGPT Scheduled Task 获取并整理 NewsNow 当日信息，再由 GitHub Actions 云端投递到飞书。

## 工作流

```text
ChatGPT Scheduled Task
  -> NewsNow 当日财经信息
  -> ChatGPT 整理事实、主题和影响
  -> GitHub 连接器提交 reports/YYYY-MM-DD.md
  -> GitHub Actions
  -> 飞书群机器人 Webhook
```

## 快速配置

1. 在飞书目标群添加群机器人，复制 Webhook 地址。
2. 在本仓库 **Settings -> Secrets and variables -> Actions** 新建 Secret：
   - Name：`FEISHU_WEBHOOK_URL`
   - Value：飞书群机器人 Webhook 地址
3. 将 [gpt-scheduled-task/task-prompt.md](gpt-scheduled-task/task-prompt.md) 全文粘贴到 ChatGPT Scheduled Task。
4. 确认 Scheduled Task 能使用 GitHub 连接器，并设置为每天 20:30（Asia/Shanghai）。
5. 在 **Actions -> Deliver daily report to Feishu -> Run workflow** 中运行：
   `gpt-scheduled-task/connection-test.md`
6. 飞书收到测试消息后，等待日报任务提交 `reports/YYYY-MM-DD.md)。

## 目录

- [定时任务说明](gpt-scheduled-task/README.md)
- [任务提示词](gpt-scheduled-task/task-prompt.md)
- [NewsNow 配置](gpt-scheduled-task/newsnow_task.json)
- [飞书发送脚本](gpt-scheduled-task/send_feishu.py)
- [企业微信桥接说明](gpt-scheduled-task/wecom.md)

本仓库不保存飞书 Webhook、Cookie、Token 或其他私密凭据，也不调用 Gemini/OpenAI API。
