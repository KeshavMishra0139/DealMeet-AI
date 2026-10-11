"""Automatic checks of a submitted deal post, through the creator's connected account.

Returns None when no connection can check the post, and the deal shows every
check as "not checked". The Instagram and YouTube connections register here.
"""
from __future__ import annotations

from typing import Callable

# (deal) -> check result, or None if this checker can't check that post
CHECKERS: list[Callable[[dict], dict | None]] = []


def run(deal: dict) -> dict | None:
    for check in CHECKERS:
        result = check(deal)
        if result:
            return result
    return None
