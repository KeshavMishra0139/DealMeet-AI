"""Small in-process caches for expensive, deterministic computations
(trust model, price model). Cleared when the demo resets."""
from __future__ import annotations

from typing import Any, Callable

_store: dict[str, Any] = {}


def memo(key: str, fn: Callable[[], Any]) -> Any:
    if key not in _store:
        _store[key] = fn()
    return _store[key]


def invalidate(prefix: str = "") -> None:
    for k in [k for k in _store if k.startswith(prefix)]:
        del _store[k]


def clear_runtime() -> None:
    _store.clear()
