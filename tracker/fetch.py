"""抓取层: RSS/Atom + HTML 列表页 + 详情页正文。

RSS/Atom 解析自己写 (lxml)，因为 feedparser 依赖的 sgmllib3k 在新 Python 上编译失败。
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Iterable
from urllib.parse import urljoin

import requests
from dateutil import parser as dateparser
from lxml import etree, html

from .config import Settings
from .models import Item, Source

log = logging.getLogger(__name__)


NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


def fetch_url(url: str, settings: Settings) -> bytes | None:
    headers = {"User-Agent": settings.http_user_agent, "Accept": "*/*"}
    try:
        resp = requests.get(url, headers=headers, timeout=settings.http_timeout)
        if resp.status_code >= 400:
            log.warning("HTTP %s on %s", resp.status_code, url)
            return None
        return resp.content
    except requests.RequestException as exc:
        log.warning("fetch failed %s: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# RSS / Atom
# ---------------------------------------------------------------------------
def parse_feed(content: bytes, source: Source) -> list[Item]:
    try:
        root = etree.fromstring(content, parser=etree.XMLParser(recover=True))
    except etree.XMLSyntaxError as exc:
        log.warning("[%s] feed parse error: %s", source.key, exc)
        return []
    if root is None:
        return []

    items: list[Item] = []
    tag = etree.QName(root.tag).localname.lower()

    if tag == "rss":
        for it in root.findall(".//item"):
            items.append(_build_from_rss_item(it, source))
    elif tag == "feed":
        for it in root.findall("atom:entry", NS):
            items.append(_build_from_atom_entry(it, source))
    else:
        # Some feeds wrap RSS oddly; try both
        for it in root.findall(".//item"):
            items.append(_build_from_rss_item(it, source))
        for it in root.findall(".//atom:entry", NS):
            items.append(_build_from_atom_entry(it, source))

    return [i for i in items if i.url and i.title]


def _build_from_rss_item(node, source: Source) -> Item:
    title = _text(node.find("title"))
    link = _text(node.find("link"))
    pub = _text(node.find("pubDate")) or _text(node.find("dc:date", NS))
    authors_raw = _text(node.find("dc:creator", NS)) or _text(node.find("author"))
    return Item(
        source_key=source.key,
        source_name_en=source.name_en,
        source_name_zh=source.name_zh,
        country=source.country,
        language=source.language,
        title=(title or "").strip(),
        url=(link or "").strip(),
        pub_date=_parse_date(pub),
        authors=_split_authors(authors_raw),
    )


def _build_from_atom_entry(node, source: Source) -> Item:
    title = _text(node.find("atom:title", NS))
    link_node = node.find("atom:link", NS)
    link = link_node.get("href") if link_node is not None else ""
    pub = (_text(node.find("atom:published", NS))
           or _text(node.find("atom:updated", NS)))
    author_nodes = node.findall("atom:author/atom:name", NS)
    authors = [a.text.strip() for a in author_nodes if a.text]
    return Item(
        source_key=source.key,
        source_name_en=source.name_en,
        source_name_zh=source.name_zh,
        country=source.country,
        language=source.language,
        title=(title or "").strip(),
        url=(link or "").strip(),
        pub_date=_parse_date(pub),
        authors=authors,
    )


def _text(node) -> str:
    if node is None:
        return ""
    return (node.text or "").strip()


def _split_authors(s: str | None) -> list[str]:
    """Split on ; & "and" — NOT bare comma (Last, First is one person)."""
    if not s:
        return []
    parts = re.split(r"\s*(?:;|&|\band\b)\s*", s)
    return [p.strip() for p in parts if p.strip()]


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        dt = dateparser.parse(s)
    except (ValueError, TypeError, dateparser.ParserError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.date()


# ---------------------------------------------------------------------------
# HTML list page
# ---------------------------------------------------------------------------
def parse_html_list(content: bytes, source: Source) -> list[Item]:
    if not source.item_selector:
        log.warning("[%s] html_list strategy 缺 item_selector", source.key)
        return []
    try:
        doc = html.fromstring(content)
    except Exception as exc:
        log.warning("[%s] html parse error: %s", source.key, exc)
        return []

    base = source.base_url or source.list_url or source.url
    items: list[Item] = []
    for node in doc.cssselect(source.item_selector):
        title = _extract(node, source.title_selector, attr=None)
        link = _extract(node, source.link_selector, attr="href")
        if link and not link.startswith(("http://", "https://")):
            link = urljoin(base, link)
        date_raw = _extract(node, source.date_selector, attr=source.date_attr)
        pub = _parse_date(date_raw) if date_raw else None
        author_raw = _extract(node, source.author_selector, attr=None)
        items.append(Item(
            source_key=source.key,
            source_name_en=source.name_en,
            source_name_zh=source.name_zh,
            country=source.country,
            language=source.language,
            title=(title or "").strip(),
            url=(link or "").strip(),
            pub_date=pub,
            authors=_split_authors(author_raw),
        ))
    return [i for i in items if i.url and i.title]


def _extract(node, selector: str | None, *, attr: str | None) -> str | None:
    if not selector:
        return None
    hits = node.cssselect(selector)
    if not hits:
        return None
    first = hits[0]
    if attr:
        return first.get(attr)
    return (first.text_content() or "").strip()


# ---------------------------------------------------------------------------
# Source dispatcher
# ---------------------------------------------------------------------------
def collect_source(source: Source, settings: Settings) -> list[Item]:
    if source.strategy == "skip":
        return []
    if source.strategy in ("rss", "sitemap"):
        out: list[Item] = []
        for feed in source.feeds:
            content = fetch_url(feed, settings)
            if content is None:
                continue
            out.extend(parse_feed(content, source))
        return out
    if source.strategy == "html_list":
        if not source.list_url:
            log.warning("[%s] html_list 缺 list_url", source.key)
            return []
        content = fetch_url(source.list_url, settings)
        if content is None:
            return []
        return parse_html_list(content, source)
    log.warning("[%s] 未知 strategy: %s", source.key, source.strategy)
    return []


# ---------------------------------------------------------------------------
# Detail page extraction (trafilatura)
# ---------------------------------------------------------------------------
def fetch_body(item: Item, settings: Settings) -> tuple[str | None, date | None]:
    """抓详情页, 返回 (正文, 检测到的日期)。

    日期检测兜底: 列表页没给日期时, 用 trafilatura/htmldate 从详情页猜。
    """
    import trafilatura

    content = fetch_url(item.url, settings)
    if content is None:
        return None, None
    extracted = trafilatura.extract(
        content,
        favor_precision=True,
        include_comments=False,
        include_tables=False,
        with_metadata=True,
        output_format="json",
    )
    if not extracted:
        return None, None
    import json
    try:
        meta = json.loads(extracted)
    except Exception:
        return None, None
    body = meta.get("text") or meta.get("raw_text")
    pub = None
    if meta.get("date"):
        pub = _parse_date(meta["date"])
    return body, pub
