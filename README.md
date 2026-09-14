# 财经观察 · 免费云端早晚报与看板

看板：https://emilyyyho.github.io/gpt-finance-daily-briefing/

## 运行方式

GitHub Actions 独立抓取 → 保存最新快照 → 生成早晚报 → 飞书群机器人 → 发布 GitHub Pages。
电脑关机不影响云端任务。不调用付费模型 API，不需要新增服务器或数据库。

- 北京时间 08:07、20:07 两期；使用 GitHub Actions 的 Asia/Shanghai 时区。避开整点高峰；每小时 37 分再做一次漏期兜底，账本会防止重复发送。
- GitHub 调度可能排队，目标是 08:07/20:07；实际发送时间以飞书送达记录为准。
- 页面每分钟读取新快照，手动刷新只重新读取，不会即时启动云端采集。快照超过 75 分钟提示延迟。
- 新闻：财联社、华尔街见闻、金十经 NewsNow；中新网财经/国际、BBC 世界新闻独立官方 RSS。发布时间不明确、超过 24 小时、未来时间的项目均排除；按时间排序，不声称全网热度。
- 行情：Yahoo Finance 的上证、恒生、纳斯达克综合及黄金/白银/WTI 期货；显示来源、报价时间、近月日线和五交易日变化。不是逐笔实时，也不混用期货与现货。
- AI 仅为可选增强：预先提交 analysis/YYYY-MM-DD-am.md 或 pm.md。缺失时明确显示基础新闻版，不虚构研判。

## 送达记录与补发

`docs/data/ledger.json` 保存每期、每分片状态；`status.json` 供页面显示。Webhook 只从 FEISHU_WEBHOOK_URL Secret 读取。

发送前提交 sending 状态，成功后提交 sent。重跑跳过成功分片。明确拒绝最多尝试三次；超时或进程中断留下 uncertain/sending，需核实群内实际消息，避免盲目重发。Webhook 无端到端幂等保证，无法承诺绝对恰好一次。

若收到数据异常通知，随后采集恢复，则自动补发真实新闻。异常通知不算新闻日报成功。缺失行情逐项说明。

所有写入/发送共用 finance-pipeline 并发组，不取消进行中的任务。脚本用 GitHub token 提交不会触发另一条 push 工作流，因此发送和 Pages 发布在同一流程完成。

## 配置

1. 保留原 Secret FEISHU_WEBHOOK_URL。
2. 仓库 Settings → Pages → Source 选择 GitHub Actions。
3. 公开仓库标准运行器和 Pages 使用免费资源；不使用付费运行器。
4. 原 ChatGPT 08:30/20:30 任务不再是发送主链路，可暂停或替换为 gpt-scheduled-task/task-prompt.md 的可选增强提示词。代码无法自动修改已有 ChatGPT 任务。
5. 手动运行 Refresh dashboard and deliver daily editions，send=true 会补发当日已到点、尚未成功的期次；send=false 只采集和发布。

## 检查

```sh
python -m unittest discover -s gpt-scheduled-task -p 'test_*.py'
python gpt-scheduled-task/validate_config.py
node --check docs/app.js
python gpt-scheduled-task/run_briefing.py
```

最后一条仅在本地抓取与生成文件，不发送消息、不提交 Git。真实投递只在配置了 Secret 的云端执行。

上线后需要连续观察 7 天 14 期的实际调度与送达，不能用一次手动成功替代持续运行验收。
