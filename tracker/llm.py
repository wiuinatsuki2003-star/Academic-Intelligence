"""DeepSeek V4 Pro 思考模式调用。

接口与 wiuinatsuki2003-star/Journal-Editor-Mode 的 core/api_handler.py 保持一致:
  - OpenAI 兼容 /chat/completions
  - thinking=enabled + reasoning_effort=high, 不传 temperature
  - 4 次指数退避 (1.5 × 1.5^n + jitter), 429/5xx 触发
  - SHA-256 磁盘缓存: 同 (model, system, user) 命中直接读盘

只保留这一条 provider 路径——本项目不混用 Claude / GPT。
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from pathlib import Path

import requests

from .config import CACHE_DIR, Settings

log = logging.getLogger(__name__)


_MAX_RETRIES = 4
_BASE_BACKOFF = 1.5


class LLMError(RuntimeError):
    pass


class DeepSeekClient:
    def __init__(self, settings: Settings, cache_dir: Path | None = CACHE_DIR) -> None:
        if not settings.deepseek_api_key:
            raise LLMError("DEEPSEEK_API_KEY 未设置 (检查 .env)")
        self.s = settings
        self.cache_dir = cache_dir
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def complete(self, system: str, user: str, *, max_tokens: int = 1024) -> str:
        cached = self._cache_get(system, user)
        if cached is not None:
            return cached
        text = self._call(system, user, max_tokens=max_tokens)
        self._cache_put(system, user, text)
        return text

    # ------------------------------------------------------------------
    def _call(self, system: str, user: str, *, max_tokens: int) -> str:
        url = f"{self.s.deepseek_base_url.rstrip('/')}/chat/completions"
        body: dict = {
            "model": self.s.deepseek_model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.s.deepseek_thinking:
            # V4 思考模式: 不支持 temperature/top_p, 传了无效
            body["extra_body"] = {"thinking": {"type": "enabled"}}
            body["reasoning_effort"] = self.s.deepseek_thinking_effort
        else:
            body["temperature"] = 0.3

        headers = {
            "Authorization": f"Bearer {self.s.deepseek_api_key}",
            "content-type": "application/json",
        }
        payload = _post_json_with_retry(url, headers, body, self.s.deepseek_timeout)
        choices = payload.get("choices") or []
        if not choices:
            return ""
        msg = choices[0].get("message") or {}
        if self.s.deepseek_thinking and msg.get("reasoning_content"):
            log.debug(
                "思考 CoT (%d chars): %s",
                len(msg["reasoning_content"]),
                msg["reasoning_content"][:200],
            )
        return (msg.get("content") or "").strip()

    # ------------------------------------------------------------------
    def _cache_key(self, system: str, user: str) -> str:
        h = hashlib.sha256()
        h.update(self.s.deepseek_model.encode())
        h.update(b"\x00")
        h.update(system.encode("utf-8"))
        h.update(b"\x00")
        h.update(user.encode("utf-8"))
        return h.hexdigest()

    def _cache_path(self, system: str, user: str) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / f"{self._cache_key(system, user)}.json"

    def _cache_get(self, system: str, user: str) -> str | None:
        path = self._cache_path(system, user)
        if path is None or not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))["content"]
        except Exception:
            return None

    def _cache_put(self, system: str, user: str, content: str) -> None:
        path = self._cache_path(system, user)
        if path is None:
            return
        path.write_text(
            json.dumps({"content": content}, ensure_ascii=False),
            encoding="utf-8",
        )


def _post_json_with_retry(
    url: str, headers: dict, body: dict, timeout: float,
) -> dict:
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=timeout)
            if 200 <= resp.status_code < 300:
                return resp.json()
            if 400 <= resp.status_code < 500 and resp.status_code != 429:
                raise LLMError(
                    f"HTTP {resp.status_code} from {url}: {resp.text[:400]}",
                )
            wait = _BASE_BACKOFF * (1.5 ** attempt) + random.uniform(0, 0.5)
            log.warning(
                "HTTP %s on %s (%d/%d); sleeping %.1fs",
                resp.status_code, url, attempt + 1, _MAX_RETRIES, wait,
            )
            last_exc = LLMError(f"HTTP {resp.status_code}: {resp.text[:400]}")
            time.sleep(wait)
        except requests.exceptions.Timeout as exc:
            last_exc = LLMError(
                f"请求超时 {url} (超过 {timeout}s)。检查网络/代理/base_url 是否可达"
            )
            log.warning("Timeout %d/%d: %s", attempt + 1, _MAX_RETRIES, exc)
            time.sleep(_BASE_BACKOFF * (1.5 ** attempt))
        except requests.exceptions.ConnectionError as exc:
            last_exc = LLMError(f"网络不可达 {url}: {exc}")
            log.warning("Connection error %d/%d: %s", attempt + 1, _MAX_RETRIES, exc)
            time.sleep(_BASE_BACKOFF * (1.5 ** attempt))
        except requests.exceptions.RequestException as exc:
            last_exc = LLMError(f"{type(exc).__name__}: {exc}")
            break
    assert last_exc is not None
    raise last_exc
