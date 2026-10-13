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

import httpx
from pydantic import BaseModel, ValidationError

from ..config import get_settings
from ..db import get_db

log = logging.getLogger("jodidar.ai")
T = TypeVar("T", bound=BaseModel)

SYSTEM = (
    "You write for DealMeet AI, an app that helps Indian creators earn fairly. "
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


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class _NoOutput(Exception):
    """The model answered without usable output (a refusal, a cut-off or an empty reply)."""


def _json_object(text: str) -> str:
    """The JSON object in a reply, without ```json fences or a sentence around it."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in the reply")
    return text[start : end + 1]


def _openrouter(prompt: str, schema: type[T], max_tokens: int) -> T:
    """One call through OpenRouter's chat completions API (AI_MODEL is its model id, such as
    a Claude model under "anthropic/"). The reply must be JSON for `schema`; it's checked with
    Pydantic like the direct path's structured output."""
    s = get_settings()
    shape = json.dumps(schema.model_json_schema(), separators=(",", ":"))
    r = httpx.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {s.openrouter_api_key}", "X-Title": "DealMeet AI"},
        json={
            "model": s.ai_model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": f"{SYSTEM}\n\nReply with one JSON object only, no other text, matching this JSON Schema: {shape}"},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=30.0,
    )
    r.raise_for_status()
    choice = (r.json().get("choices") or [{}])[0]
    text = (choice.get("message") or {}).get("content") or ""
    if choice.get("finish_reason") in ("content_filter", "length") or not text.strip():
        raise _NoOutput(choice.get("finish_reason") or "empty")
    return schema.model_validate_json(_json_object(text))


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

    if s.ai_provider == "openrouter":
        try:
            result = _openrouter(prompt, schema, max_tokens)
        except _NoOutput as e:
            log.info("AI %s: no usable output from OpenRouter (%s); using template", task, e)
            return fallback(), "template"
        except httpx.HTTPStatusError as e:
            # 401: wrong key; 402: no credits on the OpenRouter account; 429: rate limited.
            log.warning("AI %s: OpenRouter error %s; using template", task, e.response.status_code)
            return fallback(), "template"
        except httpx.HTTPError:
            log.warning("AI %s: OpenRouter unreachable; using template", task)
            return fallback(), "template"
        except (ValidationError, ValueError) as e:
            log.warning("AI %s: invalid output from OpenRouter (%s); using template", task, type(e).__name__)
            return fallback(), "template"
        except Exception as e:  # never let the demo break on an AI call
            log.warning("AI %s: unexpected OpenRouter error (%s); using template", task, type(e).__name__)
            return fallback(), "template"
        return _checked(task, key, result, fallback, facts)

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

    return _checked(task, key, result, fallback, facts)


def _checked(task: str, key: str, result: T, fallback: Callable[[], T], facts: str | None) -> tuple[T, str]:
    """Live output is used only if it keeps the copy rules and cites only numbers in the facts."""
    text = result.model_dump_json()
    if breaks_copy_rules(text):
        log.info("AI %s: output broke copy rules; using template", task)
        return fallback(), "template"
    if facts is not None and not numbers_grounded(text, facts):
        log.info("AI %s: output used numbers not in the facts; using template", task)
        return fallback(), "template"
    get_db().ai_cache.replace_one({"_id": key}, {"_id": key, "task": task, "data": result.model_dump()}, upsert=True)
    return result, "ai"
