"""Automatic checks of a submitted deal post, through the creator's connected account.

Returns None when no connection can check the post, and the deal shows every
check as "not checked". Instagram checks the post against the connected account.
"""
from __future__ import annotations


def run(deal: dict) -> dict | None:
    from . import instagram

    return instagram.check_post(deal)
