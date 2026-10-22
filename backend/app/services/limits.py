"""Limits on how much one account can create.

- The shared demo (DEMO_MODE=1) has fixed caps so one visitor can't fill it up before the
  next reset ("This shared demo is full").
- A live site never has those caps. It has per-account daily limits instead, high enough
  for real work and low enough to stop a script or a stolen session from flooding
  creators or the directory.
"""
from __future__ import annotations

from fastapi import HTTPException

from ..config import get_settings
from . import ratelimit

DEMO_FULL = "This shared demo is full. It resets soon; please try again later."
DAY = 86400


def demo_cap(count: int, cap: int) -> None:
    """The shared demo's cap; does nothing on a live site."""
    if get_settings().demo_mode and count >= cap:
        raise HTTPException(429, DEMO_FULL)


def daily(key: str, limit: int, what: str) -> None:
    """A live site's per-account daily limit; the demo has its caps instead."""
    if not get_settings().demo_mode:
        ratelimit.enforce(f"day:{key}", limit, DAY, f"You've {what} today, the most for one day. Try again tomorrow, or contact us if you need more.")
