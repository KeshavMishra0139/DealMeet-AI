"""Language-model client with structured (Pydantic) output, caching and a
deterministic fallback for every failure mode.

The demo never depends on this: with no API key, no model ID, no network, a
refusal, invalid JSON, or copy that breaks our rules, callers get the
template result instead. Live output is cached so repeated views are instant.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Callable, TypeVar

from pydantic import BaseModel, ValidationError

from ..config import get_settings
from ..db import get_db

log = logging.getLogger("jodidar.ai")
T = TypeVar("T", bound=BaseModel)

SYSTEM = (
    "You write for JodiDar AI, an app that helps Indian creators earn fairly. "
    "Voice: a smart, warm friend. Plain English with Indian context (rupees, lakh, UPI), short sentences, "
    "no hype, no emojis, no exclamation marks. Never promise results: no promised income, reach or "
    "followers, no instant-success claims, no certainty. Use only the facts provided; do not invent numbers, names, quotes "
    "or statistics. When writing in an Indian language, use its native script."
)

_ROOT = Path(__file__).resolve().parents[3]
_RULES = [
    re.compile(r["pattern"], re.IGNORECASE)
    for r in json.loads((_ROOT / "shared" / "copy-rules.json").read_text(encoding="utf-8"))["banned"]
]
_client = None
# Live calls allowed per hour across all visitors; beyond that, templates are used.
MAX_CALLS_PER_HOUR = int(os.getenv("AI_MAX_CALLS_PER_HOUR", "100") or 100)
_calls: list[float] = []
_calls_lock = threading.Lock()


def _allow_call() -> bool:
    now = time.monotonic()
    with _calls_lock:
        _calls[:] = [t for t in _calls if now - t < 3600]
        if len(_calls) >= MAX_CALLS_PER_HOUR:
            return False
        _calls.append(now)
        return True


def _get_client():
    global _client
    if _client is None:
        import anthropic

        s = get_settings()
        _client = anthropic.Anthropic(api_key=s.ai_api_key, timeout=20.0, max_retries=1)
    return _client


def breaks_copy_rules(text: str) -> bool:
    return any(rx.search(text) for rx in _RULES)


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_grounded(output: str, facts: str) -> bool:
    """Every number in the output must already appear in the facts."""
    def norm(s: str) -> set[str]:
        return {n.replace(",", "").rstrip(".") for n in _NUM.findall(s)}

    return norm(output) <= norm(facts) | {"1", "2", "3"}


def generate(
    task: str,
    prompt: str,
    schema: type[T],
    fallback: Callable[[], T],
    *,
    facts: str | None = None,
    max_tokens: int = 1200,
) -> tuple[T, str]:
    """Returns (result, source) where source is 'ai', 'cache' or 'template'."""
    s = get_settings()
    if not s.has_ai:
        return fallback(), "template"

    key = hashlib.sha1(f"{task}|{s.ai_model}|{schema.__name__}|{prompt}".encode()).hexdigest()
    db = get_db()
    hit = db.ai_cache.find_one({"_id": key})
    if hit:
        try:
            return schema.model_validate(hit["data"]), "cache"
        except ValidationError:
            db.ai_cache.delete_one({"_id": key})
    if not _allow_call():
        log.info("AI %s: hourly limit reached; using template", task)
        return fallback(), "template"

    try:
        import anthropic

        response = _get_client().messages.parse(
            model=s.ai_model,
            max_tokens=max_tokens,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            log.info("AI %s: no usable output (stop_reason=%s); using template", task, response.stop_reason)
            return fallback(), "template"
        result = response.parsed_output
    except anthropic.RateLimitError:
        log.warning("AI %s: rate limited; using template", task)
        return fallback(), "template"
    except anthropic.APIConnectionError:
        log.warning("AI %s: offline; using template", task)
        return fallback(), "template"
    except anthropic.APIStatusError as e:
        log.warning("AI %s: API error %s; using template", task, e.status_code)
        return fallback(), "template"
    except (ValidationError, ValueError) as e:
        log.warning("AI %s: invalid output (%s); using template", task, e)
        return fallback(), "template"
    except Exception as e:  # never let the demo break on an AI call
        log.warning("AI %s: unexpected error (%s); using template", task, type(e).__name__)
        return fallback(), "template"

    text = result.model_dump_json()
    if breaks_copy_rules(text):
        log.info("AI %s: output broke copy rules; using template", task)
        return fallback(), "template"
    if facts is not None and not numbers_grounded(text, facts):
        log.info("AI %s: output used numbers not in the facts; using template", task)
        return fallback(), "template"
    db.ai_cache.replace_one({"_id": key}, {"_id": key, "task": task, "data": result.model_dump()}, upsert=True)
    return result, "ai"
