# 财经观察 · 每日财经看板

一个基于 GitHub Actions 的中文财经信息工作台：定时采集最近 24 小时的财经与世界新闻，整理主要市场行情，生成早晚报，通过飞书群机器人发送，并将静态看板发布到 GitHub Pages。

- 看板地址：<https://emilyyyho.github.io/gpt-finance-daily-briefing/>
- 运行方式：公开 GitHub Actions + GitHub Pages
- 数据形态：静态 JSON、Markdown 报告和原生 HTML / CSS / JavaScript
- 付费依赖：不依赖付费模型 API、独立服务器或数据库

## 能够产生什么效果

### 每日信息看板

页面提供以下内容：

- 上证指数、恒生指数、纳斯达克综合指数，以及黄金、白银、WTI 原油期货的价格、涨跌幅、趋势线、报价时间和来源。
- 最近 24 小时的中国财经与世界要闻，按来源时间排序。
- 全部、中国财经、世界要闻三类筛选，以及标题和来源搜索、分页查看。
- 根据标题规则标记宏观焦点、市场异动和风险事件，并显示“影响方向待核实”提示。
- 今日早报、晚报的生成和送达状态。
- 数据来源健康度、历史报告归档和日报弹窗阅读。
- 数据延迟、空结果、加载中、发送失败等状态提示。

颜色含义遵循中国市场常见表达：红色表示上涨，绿色表示下跌。金色表示宏观焦点或重点提示；紫色表示市场异动；暖红色表示风险事件。

### 飞书消息

到达投递时间后，工作流会把 Markdown 报告转换成飞书卡片，并发送到 `FEISHU_WEBHOOK_URL` 对应的飞书群机器人。

这里的“发送成功”表示飞书 webhook 返回了明确的成功响应，不等于每一位群成员都已收到、阅读或确认。当前方案是群机器人投递，不是向个人账号发送私信。

## 工作原理

整体流程如下：

```text
GitHub Actions 定时触发
        ↓
运行配置检查和单元测试
        ↓
采集新闻、市场行情并过滤无效时间范围
        ↓
写入 docs/data/latest.json 和报告文件
        ↓
判断早报 / 晚报是否到点且尚未成功
        ↓
发送飞书群机器人卡片，并记录每个分片状态
        ↓
提交数据快照并发布 docs/ 到 GitHub Pages
        ↓
看板读取 JSON，展示最新数据和投递状态
```

### 1. 定时触发

工作流文件是 `.github/workflows/deliver-feishu.yml`，包含两类定时任务：

- `7 8,20 * * *`（`Asia/Shanghai`）：在北京时间 08:07 和 20:07 错峰执行，负责目标为 08:00 / 20:00 的期次投递。
- `37 * * * *`（`Asia/Shanghai`）：每小时第 37 分钟兜底刷新，检查是否存在已经到点但尚未完成的期次。

GitHub Actions 的定时任务可能排队或延迟，不能把 cron 视为严格准点服务。工作流使用同一个 `finance-pipeline` 并发组，避免多个任务同时修改快照或重复发送。

### 2. 采集和整理

`gpt-scheduled-task/collect_news.py` 负责采集和规范化数据：

- 财经新闻主要来自 NewsNow 聚合的财联社、华尔街见闻、金十数据等来源。
- 中新网财经、中新网国际和 BBC World 使用独立的官方 RSS 来源。
- 只保留最近 24 小时内、发布时间明确且不晚于当前时间的内容。
- 新闻按发布时间排序，不把抓取数量当作全网热度。
- 市场行情来自 Yahoo Finance，标明报价时间、数据延迟和来源。
- 缺失或异常数据会逐项展示，不用示例数据掩盖问题。

ChatGPT Scheduled Task 每天 07:40 / 19:40 将带证据的 AI 分析写入 `analysis/YYYY-MM-DD-am.md` 或 `analysis/YYYY-MM-DD-pm.md`。文件存在时，首次生成日报会合并分析；如果分析晚到，流水线会单独补发 AI 分析附加消息。文件不存在时，页面明确显示“基础新闻版”，不会虚构分析结论。

### 3. 报告和状态

`gpt-scheduled-task/run_briefing.py` 会同时维护报告和投递状态：

- `docs/data/latest.json`：页面读取的最新新闻、行情和来源状态。
- `docs/data/ledger.json`：每一期报告和每个飞书消息分片的详细状态，仅用于工作流恢复和审计。
- `docs/data/status.json`：去除消息正文后的公开状态，供页面显示。
- `reports/`：仓库中的报告归档。
- `docs/reports/`：随 GitHub Pages 发布，供看板弹窗阅读。

发送前先记录 `sending`，得到明确确认后再记录 `sent`。成功的分片不会重复发送；遇到超时、网络中断或不明确响应时会记录 `uncertain`，需要人工核对飞书群后再决定是否补发。系统不会为了追求“看起来成功”而盲目重试。

### 4. 页面和发布

看板是无构建依赖的原生前端：

- `docs/index.html`：页面结构、可访问性标签和固定交互挂点。
- `docs/style.css`：视觉 tokens、深色金融工作台主题和响应式布局。
- `docs/app.js`：读取 JSON、渲染行情和新闻、处理筛选搜索分页、读取报告弹窗。

GitHub Actions 使用 `actions/upload-pages-artifact` 和 `actions/deploy-pages` 发布 `docs/`。浏览器每分钟检查一次新快照；手动点击“刷新数据”只重新读取已经发布的数据，不会即时启动云端采集。

## 目录结构

```text
.
├── .github/workflows/
│   ├── deliver-feishu.yml                 # 采集、投递和 Pages 发布
│   └── validate-gpt-scheduled-task.yml    # 配置校验
├── docs/
│   ├── index.html                          # 看板入口
│   ├── style.css                           # 看板样式
│   ├── app.js                              # 看板交互和数据渲染
│   ├── data/                               # 发布到 Pages 的 JSON 快照
│   └── reports/                            # 发布到 Pages 的报告
├── gpt-scheduled-task/
│   ├── collect_news.py                     # 新闻和行情采集
│   ├── run_briefing.py                     # 报告、状态和投递编排
│   ├── send_feishu.py                      # 飞书卡片转换和 webhook 发送
│   ├── newsnow_task.json                   # 来源和采集规则
│   └── test_*.py                           # 投递与流水线测试
├── analysis/                               # ChatGPT Scheduled Task 写入的 AI 观察文件
└── reports/                                # 仓库报告归档
```

## 配置和运行

### GitHub 配置

1. 在仓库 Settings → Secrets and variables → Actions 中创建 Secret：`FEISHU_WEBHOOK_URL`。
2. Secret 的值只填写飞书群机器人的 HTTPS webhook，不要写入代码、README、Issue、报告或页面数据。
3. 在仓库 Settings → Pages → Build and deployment → Source 中选择 GitHub Actions。
4. 如需手动运行，选择工作流 `Refresh dashboard and deliver daily editions`：
   - `send = true`：采集并投递已经到点且尚未成功的期次。
   - `send = false`：只采集和发布看板，不发送飞书消息。

工作流中的 `SEND` 只控制当前运行是否允许发送；脚本仍会根据 `ledger.json` 判断期次是否到点，以及成功分片是否已经存在。

### 本地检查

以下命令只做本地检查或本地采集，不会自动向飞书发送消息：

```sh
python -m unittest discover -s gpt-scheduled-task -p 'test_*.py'
python gpt-scheduled-task/validate_config.py
node --check docs/app.js
python gpt-scheduled-task/run_briefing.py
```

真实投递由 GitHub Actions 提供 `FEISHU_WEBHOOK_URL` 后执行。不要在本地命令、终端输出或调试日志中打印 Secret 值。

## 安全和隐私注意事项

### 公开内容边界

仓库和 GitHub Pages 上的内容应当按“完全公开”处理。`docs/data/`、`docs/reports/`、`reports/` 和页面 HTML 都可能被任何访问者读取，因此只发布公开新闻、公开行情和必要的投递摘要。

不要把以下内容写入仓库、报告、页面、Issue、Pull Request 或 Actions 日志：

- 个人姓名、手机号、邮箱、住址、身份证件信息或其他可识别个人的信息。
- 飞书 `open_id`、用户 ID、群 ID、个人账号信息、私聊内容、通讯录截图或聊天记录。
- `FEISHU_WEBHOOK_URL` 的完整值、GitHub Token、Cookie、Session、API Key、验证码或任何凭据。
- 能够推断个人作息、位置、联系人、工作单位或私人资产的信息。

即使内容已经删除，Git 历史、Actions 日志、缓存或搜索引擎仍可能保留副本。若凭据曾经被提交、粘贴或发送到不应出现的位置，应立即在对应平台撤销并重新生成，不能只依赖“删除文件”解决。

### 飞书机器人安全

- 使用专用的飞书群机器人和专用群，不要复用个人账号或个人私聊凭据。
- 只在 GitHub Actions Secret 中保存 webhook；不要把 Secret 同步到本地配置文件或前端。
- 遵循最小权限原则，仅授予机器人发送所需的权限。
- 定期核对机器人实际所属群和接收范围。`status.json` 中的 `sent` 只代表接口确认，不代表你的个人账号一定能看到消息。
- 不要为了测试把真实 webhook 放进本地 Markdown、截图、录屏、聊天或公开 Issue。
- 如果怀疑 webhook 泄露，先撤销或轮换机器人 webhook，再检查 GitHub 提交、日志和外部聊天记录。

### 外部数据和消息内容

新闻标题、摘要、来源页面和 RSS 内容都属于外部输入，不能当作可信指令执行。发布前应关注：

- 标题、摘要和链接是否包含隐私、恶意脚本或不应公开的信息。
- 报告是否误把媒体观点写成事实，是否缺少来源和时间。
- 新闻标记只表示标题规则命中，不代表利好、利空或投资建议。
- 行情可能延迟，不应据此自动交易或作出高风险决策。

前端对文本进行转义，对外部链接限制为 HTTP / HTTPS；修改数据层或链接处理逻辑时，应继续保持这些边界。

## 故障排查

### 没有收到飞书消息

按以下顺序检查：

1. 查看工作流是否真的触发，注意 GitHub Actions 定时任务可能延迟。
2. 查看 `docs/data/status.json` 中对应日期和期次的状态。
3. 查看 Actions 日志中的 `Collect and deliver` 步骤，不要复制或公开其中的 Secret。
4. 确认 `FEISHU_WEBHOOK_URL` Secret 仍存在，且对应的机器人仍在目标群中。
5. 如果状态为 `uncertain` 或 `sending`，先到飞书群核对实际消息，再决定是否人工补发。
6. 如果状态为 `sent` 但群里没有消息，优先检查 webhook 对应群、机器人权限和消息被过滤情况，不要直接盲目重跑。

### 看板数据没有更新

检查 Pages 部署是否成功、`docs/data/latest.json` 的生成时间是否变化，以及浏览器是否仍在使用缓存。页面提示“更新已延迟”时，以来源报价时间和工作流日志为准。

## 维护原则

- 不修改推送链路前，先阅读 `gpt-scheduled-task/test_*.py` 并补充失败场景测试。
- 不用示例新闻替代真实采集失败，不隐藏来源异常和发送不确定性。
- 不把 ChatGPT 私人任务、个人账号或私聊当作主发送链路；当前主链路是 GitHub Actions 到飞书群机器人。
- ChatGPT 只提交脱敏后的公开新闻分析到 `analysis/`，不读取或发送飞书 Webhook；GitHub Actions 负责统一投递。
- 任何涉及账号、凭据、群成员或公开范围的变更，都先确认目标和权限，再进行最小范围修改。
