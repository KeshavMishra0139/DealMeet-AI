"""Fixed-window rate limits, kept in the database so every worker shares them."""
from __future__ import annotations

import time

from fastapi import HTTPException, Request
from pymongo import ReturnDocument

from ..db import get_db


def client_ip(request: Request) -> str:
    # uvicorn runs with --proxy-headers, so this is the visitor's address behind Render's proxy.
    return request.client.host if request.client else "unknown"


def hit(key: str, limit: int, window_s: int) -> bool:
    """Counts one use of `key`. False once `limit` uses happened in the current window."""
    bucket = int(time.time() // window_s)
    doc = get_db().rate_limits.find_one_and_update(
        {"_id": f"{key}:{bucket}"},
        {"$inc": {"n": 1}, "$setOnInsert": {"expires": (bucket + 1) * window_s}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc["n"] <= limit


def enforce(key: str, limit: int, window_s: int, message: str) -> None:
    if not hit(key, limit, window_s):
        raise HTTPException(429, message)


def sweep() -> None:
    get_db().rate_limits.delete_many({"expires": {"$lt": time.time()}})
