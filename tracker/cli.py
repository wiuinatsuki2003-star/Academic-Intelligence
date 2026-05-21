"""CLI: python -m tracker --from 2026-05-13 --to 2026-05-20"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta

from .config import OUTPUT_DIR, load_settings
from .pipeline import collect_all, enrich_bodies, summarize_all
from .render import render_weekly
from .sources import load_sources


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="欧洲智库周报追踪")
    p.add_argument("--from", dest="since", help="起始日期 YYYY-MM-DD (含)")
    p.add_argument("--to", dest="until", help="结束日期 YYYY-MM-DD (含)")
    p.add_argument("--week", type=int, default=None,
                   help="不指定 from/to 时用上 N 周 (默认 1 = 过去 7 天)")
    p.add_argument("--only", help="只跑指定 source key (逗号分隔)")
    p.add_argument("--no-summary", action="store_true", help="跳过 LLM 摘要")
    p.add_argument("--no-translate-titles", action="store_true",
                   help="跳过标题翻译")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    today = date.today()
    if args.since and args.until:
        since = _parse_date(args.since)
        until = _parse_date(args.until)
    else:
        weeks = args.week or 1
        until = today - timedelta(days=1)
        since = until - timedelta(days=7 * weeks - 1)

    settings = load_settings()
    sources = load_sources()
    if args.only:
        wanted = {k.strip() for k in args.only.split(",") if k.strip()}
        sources = [s for s in sources if s.key in wanted]
    active = [s for s in sources if s.strategy != "skip"]
    print(f"窗口: {since} → {until}", file=sys.stderr)
    print(f"配置源: {len(sources)}  已启用抓取: {len(active)}", file=sys.stderr)

    raw_items = collect_all(active, settings)
    print(f"初步收到 {len(raw_items)} 条 (含窗口外)", file=sys.stderr)

    # 先按列表页日期粗过滤; 没日期的进详情页阶段再判
    pre = [it for it in raw_items
           if it.pub_date is None or (since <= it.pub_date <= until)]
    print(f"粗过滤后待抓正文: {len(pre)}", file=sys.stderr)

    items = enrich_bodies(pre, settings, since=since, until=until)
    print(f"落入窗口的最终条目: {len(items)}", file=sys.stderr)

    if not args.no_summary:
        items = summarize_all(
            items, settings, translate_titles=not args.no_translate_titles,
        )

    out_html = render_weekly(items, since, until)
    print(f"→ {out_html}", file=sys.stderr)

    # 同时存一份 JSON, 方便复用
    out_json = OUTPUT_DIR / out_html.with_suffix(".json").name
    out_json.write_text(
        json.dumps([it.to_dict() for it in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"→ {out_json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
