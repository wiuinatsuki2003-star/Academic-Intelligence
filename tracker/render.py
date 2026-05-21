"""静态 HTML 树渲染。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import OUTPUT_DIR, TEMPLATES_DIR
from .models import Item


def render_weekly(
    items: list[Item], since: date, until: date,
    output_path: Path | None = None,
) -> Path:
    by_country: dict[str, dict[str, list[Item]]] = defaultdict(lambda: defaultdict(list))
    for it in items:
        by_country[it.country or "其它"][it.source_name_zh].append(it)

    # 排序: 国家按条目数倒序; 机构按条目数倒序; 篇目按日期倒序
    countries = []
    for country, orgs in by_country.items():
        org_list = []
        for org_name, org_items in orgs.items():
            org_items.sort(
                key=lambda i: (i.pub_date or date.min),
                reverse=True,
            )
            # 注意: key 不能叫 "items", 否则 Jinja 取属性时撞到 dict.items 方法
            org_list.append({"name": org_name, "entries": org_items})
        org_list.sort(key=lambda o: len(o["entries"]), reverse=True)
        countries.append({
            "name": country,
            "orgs": org_list,
            "count": sum(len(o["entries"]) for o in org_list),
        })
    countries.sort(key=lambda c: c["count"], reverse=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("weekly.html")
    html = template.render(
        since=since.isoformat(),
        until=until.isoformat(),
        countries=countries,
        total=len(items),
        total_orgs=sum(len(c["orgs"]) for c in countries),
    )

    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"weekly-{since.isoformat()}-to-{until.isoformat()}.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path
