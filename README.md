# Academic-Intelligence

欧洲智库每周学术追踪。给定时间窗口 (如 `2026-05-13` → `2026-05-20`)，抓取 56 家欧洲智库当周产出的标题、作者、日期、链接、原文，再用 DeepSeek V4 Pro 思考模式生成 200-400 字中文摘要，渲染成「国家 → 机构 → 篇目」的折叠静态 HTML 周报。

## 快速开始 (IDLE / VSCode 一键运行)

最简单的路：

1. 用 IDLE 或 VSCode 打开 `run.py`
2. 顶部「配置区」把 `DEEPSEEK_API_KEY` 填上（去 https://platform.deepseek.com 拿）
3. 按 **F5** 跑 —— 第一次会自动装依赖（1-2 分钟），跑完浏览器自动弹周报

不想改代码也行：留空 `DEEPSEEK_API_KEY`、把 `SKIP_SUMMARY = True`，先抓取+渲染看流水线通不通。

### 自定义时间窗口

`run.py` 顶部改 `DATE_FROM` / `DATE_TO`，例如：
```python
DATE_FROM = "2026-05-13"
DATE_TO   = "2026-05-20"
```
留空就是过去 7 天。

### 进阶：命令行

```bash
pip install -r requirements.txt
cp .env.example .env       # 填 DEEPSEEK_API_KEY
python -m tracker --from 2026-05-13 --to 2026-05-20
python -m tracker --only swp,elcano       # 只跑指定源 (调试)
python -m tracker --no-summary            # 不调 LLM
python -m tracker --week 1 -v             # 过去 7 天, 详细日志
```

## 目录

```
sources.yaml              # 56 家配置 (国家/语种/抓取策略/RSS 地址)
tracker/
  cli.py                  # 入口
  llm.py                  # DeepSeek V4 Pro 思考模式客户端 (含磁盘缓存+重试)
  fetch.py                # RSS/Atom + HTML 列表 + trafilatura 正文提取
  pipeline.py             # collect → 日期过滤 → 取正文 → 摘要 → 落盘
  render.py               # Jinja2 渲染折叠 HTML 树
  prompts.py              # 摘要 / 标题翻译提示词
  config.py / models.py / sources.py
templates/weekly.html     # 树状周报模板
data/
  raw/<date>/<org>/*.txt  # 原文落地 (gitignored)
  briefs/<date>/<org>/*.md  # 单篇中文摘要 (gitignored)
output/weekly-*.html      # 周报 (gitignored)
cache/llm/*.json          # LLM 响应缓存 (gitignored)
```

## 状态

- 12 家给了候选 RSS 地址 (Chatham House / RUSI / IRIS / Institut Montaigne /
  ifo / SWP / DGAP / Elcano / RIAC / Valdai 等), 字段标了 `verified: false`。
  本地跑一次, 看日志哪几家解析为 0 条或 404, 改 `strategy: html_list` 写选择器或换其他 feed。
- 其余 44 家先 `strategy: skip`, 加适配器是机械活, 每家约 10-30 行 YAML/代码。

## DeepSeek 思考模式

接口与 `wiuinatsuki2003-star/Journal-Editor-Mode` 的 `core/api_handler.py` 一致：

- `POST https://api.deepseek.com/chat/completions`
- `extra_body={"thinking":{"type":"enabled"}}` + `reasoning_effort=high`
- 不传 `temperature` (V4 思考模式不支持)
- 4 次指数退避重试 (1.5×1.5^n + jitter)，429/5xx 触发
- SHA-256 磁盘缓存：相同 (model, system, user) 命中读盘，零 token
