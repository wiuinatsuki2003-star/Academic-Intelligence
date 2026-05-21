"""端到端编排: collect → date filter → fetch body → summarize → render."""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from .config import BRIEF_DIR, RAW_DIR, Settings
from .fetch import collect_source, fetch_body
from .llm import DeepSeekClient, LLMError
from .models import Item, Source
from .prompts import build_summary_prompt, build_title_prompt

log = logging.getLogger(__name__)


def collect_all(sources: list[Source], settings: Settings) -> list[Item]:
    items: list[Item] = []
    with ThreadPoolExecutor(max_workers=settings.max_concurrency) as pool:
        futures = {pool.submit(collect_source, s, settings): s for s in sources}
        for fut in as_completed(futures):
            src = futures[fut]
            try:
                got = fut.result()
                log.info("[%s] 收到 %d 条", src.key, len(got))
                items.extend(got)
            except Exception as exc:
                log.exception("[%s] collect 失败: %s", src.key, exc)
    return items


def in_window(item: Item, since: date, until: date) -> bool:
    if item.pub_date is None:
        return False
    return since <= item.pub_date <= until


def enrich_bodies(
    items: list[Item], settings: Settings, *, since: date, until: date,
) -> list[Item]:
    """抓正文。列表页没给日期的, 用详情页日期回填后再做窗口过滤。"""
    out: list[Item] = []

    def work(it: Item) -> Item:
        body, detected = fetch_body(it, settings)
        if it.pub_date is None and detected is not None:
            it.pub_date = detected
        it.body_text = body
        if body:
            path = _save_raw(it, body)
            it.body_path = str(path.relative_to(RAW_DIR.parent))
        return it

    with ThreadPoolExecutor(max_workers=settings.max_concurrency) as pool:
        futures = [pool.submit(work, it) for it in items]
        for fut in as_completed(futures):
            try:
                enriched = fut.result()
            except Exception as exc:
                log.warning("详情抓取失败: %s", exc)
                continue
            if in_window(enriched, since, until):
                out.append(enriched)
    return out


def summarize_all(
    items: list[Item], settings: Settings, *, translate_titles: bool = True,
) -> list[Item]:
    try:
        client = DeepSeekClient(settings)
    except LLMError as exc:
        log.warning("LLM 不可用: %s — 跳过摘要", exc)
        return items

    def work(it: Item) -> Item:
        if not it.body_text:
            it.error = "无正文"
            return it
        try:
            body = it.body_text[:12000]  # 防超长
            sys_p, user_p = build_summary_prompt(
                org_name=it.source_name_en,
                title=it.title,
                date=it.pub_date.isoformat() if it.pub_date else "",
                url=it.url,
                body=body,
                min_chars=settings.summary_min_chars,
                max_chars=settings.summary_max_chars,
            )
            it.summary_zh = client.complete(sys_p, user_p, max_tokens=1024)
            if translate_titles and it.language != "zh":
                ts, tu = build_title_prompt(it.title)
                it.title_zh = client.complete(ts, tu, max_tokens=256)
            _save_brief(it)
        except LLMError as exc:
            it.error = f"LLM: {exc}"
            log.warning("[%s] 摘要失败: %s", it.source_key, exc)
        return it

    with ThreadPoolExecutor(max_workers=settings.max_concurrency) as pool:
        futures = [pool.submit(work, it) for it in items]
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as exc:
                log.exception("summarize 异常: %s", exc)
    return items


# ---------------------------------------------------------------------------
def _slug(s: str, maxlen: int = 80) -> str:
    s = re.sub(r"[^\w\-]+", "-", s, flags=re.UNICODE).strip("-")
    return s[:maxlen] or "untitled"


def _save_raw(item: Item, body: str) -> Path:
    d = item.pub_date.isoformat() if item.pub_date else "unknown"
    folder = RAW_DIR / d / item.source_key
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{_slug(item.title)}.txt"
    path.write_text(body, encoding="utf-8")
    meta_path = path.with_suffix(".json")
    meta_path.write_text(
        json.dumps(item.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _save_brief(item: Item) -> Path | None:
    if not item.summary_zh:
        return None
    d = item.pub_date.isoformat() if item.pub_date else "unknown"
    folder = BRIEF_DIR / d / item.source_key
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{_slug(item.title)}.md"
    md = (
        f"# {item.title_zh or item.title}\n\n"
        f"- 机构: {item.source_name_zh} ({item.source_name_en})\n"
        f"- 国家: {item.country}\n"
        f"- 日期: {d}\n"
        f"- 作者: {', '.join(item.authors) or '—'}\n"
        f"- 链接: {item.url}\n\n"
        f"---\n\n{item.summary_zh}\n"
    )
    path.write_text(md, encoding="utf-8")
    return path
