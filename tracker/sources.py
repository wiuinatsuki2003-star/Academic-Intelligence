"""sources.yaml 装载器。"""

from __future__ import annotations

from pathlib import Path

import yaml

from .config import SOURCES_FILE
from .models import Source


def load_sources(path: Path = SOURCES_FILE) -> list[Source]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: list[Source] = []
    for entry in raw.get("sources", []):
        out.append(Source(
            key=entry["key"],
            name_en=entry["name_en"],
            name_zh=entry.get("name_zh", entry["name_en"]),
            country=entry.get("country", ""),
            country_code=entry.get("country_code", ""),
            language=entry.get("language", "en"),
            url=entry.get("url", ""),
            strategy=entry.get("strategy", "skip"),
            feeds=entry.get("feeds", []) or [],
            list_url=entry.get("list_url"),
            item_selector=entry.get("item_selector"),
            title_selector=entry.get("title_selector"),
            link_selector=entry.get("link_selector"),
            date_selector=entry.get("date_selector"),
            date_attr=entry.get("date_attr"),
            date_format=entry.get("date_format"),
            base_url=entry.get("base_url"),
            author_selector=entry.get("author_selector"),
            note=entry.get("note"),
        ))
    return out
