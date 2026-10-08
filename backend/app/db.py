"""MongoDB access. Uses Atlas when MONGODB_URI is set and reachable, otherwise an
in-memory mongomock database so the demo never depends on the network."""
from __future__ import annotations

import logging
import threading
from typing import Any

from .config import get_settings

log = logging.getLogger("jodidar.db")

_lock = threading.Lock()
_db = None
_mode = "in-memory"

COLLECTIONS = [
    "creators",
    "brands",
    "listings",
    "collectives",
    "consents",
    "consent_audit",
    "deals",
    "plans",
    "invoices",
    "applications",
    "notifications",
    "ai_cache",
]


def get_db():
    global _db, _mode
    if _db is not None:
        return _db
    with _lock:
        if _db is not None:
            return _db
        settings = get_settings()
        if settings.mongodb_uri:
            try:
                from pymongo import MongoClient

                client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=2500)
                client.admin.command("ping")
                _db = client[settings.mongodb_db]
                _mode = "atlas"
                log.info("Connected to MongoDB Atlas")
            except Exception as exc:  # network down, bad URI, etc.
                log.warning("MongoDB unreachable (%s); using in-memory database", exc)
        if _db is None:
            import mongomock

            _db = mongomock.MongoClient()[settings.mongodb_db]
            _mode = "in-memory"
        return _db


def db_mode() -> str:
    get_db()
    return _mode


def out(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Mongo document -> API dict (`_id` becomes `id`)."""
    if doc is None:
        return None
    d = dict(doc)
    d["id"] = d.pop("_id")
    return d


def out_many(docs) -> list[dict[str, Any]]:
    return [out(d) for d in docs]  # type: ignore[misc]
