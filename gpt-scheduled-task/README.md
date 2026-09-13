# GPT 定时财经日报

这组配置把 ChatGPT Scheduled Task 作为每日财经日报的编排器，用 GitHub Actions 作为云端投递桥接：

```text
ChatGPT 定时任务
    -> NewsNow 当日数据
    -> 时间过滤与标题去重
    -> 读取公开分析框架并做事实/观点区分
    -> 生成 Markdown 日报和大盘总结
    -> GitHub 提交 reports/YYYY-MM-DD.md
    -> GitHub Actions 转成飞书富文本
    -> 飞书群机器人 Webhook
```

## 目标

- 每天北京时间 20:30 运行一次。
- 只处理北京时间当天 00:00 到运行时刻的新内容。
- NewsNow 是主要信息源。
- 使用 ChatGPT 自身分析，不调用 Gemini API、OpenAI API 或其他外部 AI API。
- 电脑关机时仍然可以运行 ChatGPT 网页端任务和 GitHub Actions。
- 日报使用从用户金融课提炼的公开分析框架，必须区分事实、观点和推测，并在末尾给出大盘与经济环境总结。

## 文件

- `task-prompt.md`：可直接粘贴到 ChatGPT Scheduled Task 的任务说明。
- `newsnow_task.json`：无密钥的运行参数和分析要求。
- `knowledge-framework.md`：从用户本地 Obsidian 金融课提炼的公开方法摘要，不上传原笔记全文。
- `validate_config.py`：本地和 GitHub Actions 使用的配置校验。
- `send_feishu.py`：将 Markdown 标题、加粗字段、列表和链接转换成飞书富文本 post。
- `wecom.md`：企业微信 CLI 和飞书自动化桥接路径。

## 一次性配置

1. 在飞书目标群中添加群机器人，复制 Webhook 地址。
2. 在 GitHub 仓库的 Settings → Secrets and variables → Actions 中新建 Secret：
   - Name：`FEISHU_WEBHOOK_URL`
   - Secret：粘贴 Webhook 地址
3. 不要把 Webhook 地址写进 JSON、Markdown、提示词或公开 Issue。
4. 确认 ChatGPT Scheduled Task 所在聊天能使用 GitHub 连接器；飞书连接器不是必需的。
5. 创建定时任务时粘贴 `task-prompt.md`，时区选 `Asia/Shanghai`，时间选 20:30。

## 飞书格式

日报仍然以 Markdown 保存到 GitHub，方便审阅和复用。投递脚本会把一级标题放进飞书消息标题，把二级和三级标题、双星号字段转成加粗文本，把 Markdown 链接转成可点击链接；因此不依赖飞书把原始 Markdown 当作普通文本解析。

## 测试

1. 在 GitHub 网页直接新建或更新 `reports/test.md`，内容必须包含一个一级标题和 `## 七、今日大盘与经济环境总结`。
2. 打开 Actions → Deliver daily report to Feishu，等待工作流运行。
3. 检查飞书群是否收到标题和加粗字段均已格式化的消息。
4. 也可以在该工作流的 Run workflow 中填写已存在的 `reports/*.md` 文件路径进行重发。

## 安全边界

不要把 NewsNow 私钥、飞书 Webhook、企业微信 Secret、Cookie 或任何网页登录凭据提交到此仓库。公开仓库只保留无密钥配置、分析方法摘要、日报正文和来源链接。

## 验收标准

- 每天只生成一份当天日报。
- 每条新闻都有来源、时间和原文链接。
- 事实、机构观点和推测分开标注。
- 日报末尾有宏观环境、流动性与政策、大盘状态、全球联动和基准结论。
- NewsNow 无法访问时不会使用昨天的旧数据。
- GitHub 提交成功后，Actions 能通过 Secret 将富文本日报送到飞书。