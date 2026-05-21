"""Environment + path config. Loads .env if present."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
BRIEF_DIR = DATA_DIR / "briefs"
CACHE_DIR = ROOT / "cache" / "llm"
OUTPUT_DIR = ROOT / "output"
SOURCES_FILE = ROOT / "sources.yaml"
TEMPLATES_DIR = ROOT / "templates"


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


_load_dotenv()


@dataclass(slots=True)
class Settings:
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    deepseek_thinking: bool
    deepseek_thinking_effort: str
    deepseek_timeout: float
    summary_min_chars: int
    summary_max_chars: int
    http_timeout: float
    http_user_agent: str
    max_concurrency: int


def load_settings() -> Settings:
    return Settings(
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", "").strip(),
        deepseek_base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip(),
        deepseek_model=os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro").strip(),
        deepseek_thinking=os.environ.get("DEEPSEEK_THINKING", "true").strip().lower()
            in ("true", "1", "yes", "on"),
        deepseek_thinking_effort=os.environ.get("DEEPSEEK_THINKING_EFFORT", "high").strip(),
        deepseek_timeout=float(os.environ.get("DEEPSEEK_TIMEOUT", "180")),
        summary_min_chars=int(os.environ.get("SUMMARY_MIN_CHARS", "200")),
        summary_max_chars=int(os.environ.get("SUMMARY_MAX_CHARS", "400")),
        http_timeout=float(os.environ.get("HTTP_TIMEOUT", "30")),
        http_user_agent=os.environ.get(
            "HTTP_USER_AGENT",
            "Mozilla/5.0 (Academic-Intelligence weekly tracker)",
        ),
        max_concurrency=int(os.environ.get("MAX_CONCURRENCY", "4")),
    )
