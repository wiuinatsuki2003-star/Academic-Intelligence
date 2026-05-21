"""数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any


@dataclass(slots=True)
class Source:
    key: str
    name_en: str
    name_zh: str
    country: str
    country_code: str
    language: str       # ISO 639-1: en/fr/de/es/ru
    url: str
    strategy: str       # rss | sitemap | html_list | skip
    # rss / sitemap
    feeds: list[str] = field(default_factory=list)
    # html_list 用
    list_url: str | None = None
    item_selector: str | None = None
    title_selector: str | None = None
    link_selector: str | None = None
    date_selector: str | None = None
    date_attr: str | None = None
    date_format: str | None = None
    base_url: str | None = None
    author_selector: str | None = None
    note: str | None = None


@dataclass(slots=True)
class Item:
    source_key: str
    source_name_en: str
    source_name_zh: str
    country: str
    language: str
    title: str
    url: str
    pub_date: date | None
    authors: list[str] = field(default_factory=list)
    title_zh: str | None = None
    body_text: str | None = None
    body_path: str | None = None
    summary_zh: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.pub_date is not None:
            d["pub_date"] = self.pub_date.isoformat()
        return d
