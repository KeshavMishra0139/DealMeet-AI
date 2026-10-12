"""The one place the app talks to MongoDB.

- USE_MOCK_DB=1: an in-memory mongomock database (tests and the local demo).
  Data is gone when the process stops.
- Otherwise MONGODB_URI (MongoDB Atlas or any MongoDB) with TLS certificates
  from certifi. A missing or unreachable URI stops startup with a clear message:
  the app never falls back to memory on its own, so data can't silently vanish.

Every module gets the database from `get_db()`; nothing else creates a client.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

from .config import get_settings

log = logging.getLogger("jodidar.db")

_lock = threading.Lock()
_client = None
_db = None
_mode = "unset"

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
    "payments",
    "webhook_events",
    "manual_metrics",
    "connections",
    "posts",
    "metric_snapshots",
    "oauth_states",
    "fan_proof",
    "coach_answers",
    "rate_cards",
    "kit_versions",
    "shortlists",
    "offer_drafts",
    "wishlists",
    "claim_requests",
    "removal_requests",
    "pitches",
    "ai_cache",
]
# Accounts live apart from the demo data: a demo reset keeps the seeded persona
# accounts (and their sessions) and never touches the audit log.
ACCOUNT_COLLECTIONS = ["users", "sessions", "login_failures", "audit"]


class DatabaseNotConfigured(RuntimeError):
    pass


def _connect():
    settings = get_settings()
    if settings.use_mock_db:
        import mongomock

        return mongomock.MongoClient(), "mock"
    if not settings.mongodb_uri:
        raise DatabaseNotConfigured(
            "No database configured. Set MONGODB_URI to your MongoDB Atlas connection string, "
            "or set USE_MOCK_DB=1 for an in-memory database whose data is lost on restart."
        )
    import certifi
    from pymongo import MongoClient

    client = MongoClient(settings.mongodb_uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
    except Exception as exc:  # bad URI, wrong password, IP not allowed, network down
        client.close()
        raise DatabaseNotConfigured(
            f"Can't reach the database in MONGODB_URI ({type(exc).__name__}). Check the connection string, "
            "the database user's password, and that this server's IP is allowed in Atlas Network Access."
        ) from None
    uri = settings.mongodb_uri
    return client, "atlas" if (uri.startswith("mongodb+srv://") or "mongodb.net" in uri) else "mongodb"


def get_db():
    global _client, _db, _mode
    if _db is not None:
        return _db
    with _lock:
        if _db is None:
            client, mode = _connect()
            db = client[get_settings().mongodb_db]
            # Indexes come first, while a fresh in-memory database is still empty.
            ensure_indexes(db)
            _client, _mode, _db = client, mode, db
            log.info("Database: %s (%s)", _mode, get_settings().mongodb_db)
        return _db


def reset_client() -> None:
    """Drop the cached client, so the next get_db() connects again (tests, restarts)."""
    global _client, _db, _mode
    with _lock:
        if _client is not None and _mode != "mock":
            _client.close()
        _client, _db, _mode = None, None, "unset"


def db_mode() -> str:
    get_db()
    return _mode


def ping() -> bool:
    try:
        get_db().command("ping")
        return True
    except Exception:
        return False


def ensure_indexes(db) -> None:
    """Create the indexes the app relies on. Runs on every connect; safe to repeat."""
    text = {"$type": "string"}
    db.users.create_index("firebase_uid", unique=True, partialFilterExpression={"firebase_uid": text})
    db.users.create_index("email", unique=True, partialFilterExpression={"email": text})
    db.users.create_index("creator_id")
    db.users.create_index("brand_id")
    db.sessions.create_index("user_id")
    db.login_failures.create_index([("email", 1), ("at", 1)])
    db.audit.create_index([("ts", -1)])
    db.audit.create_index("user_id")
    db.creators.create_index("handle", unique=True, partialFilterExpression={"handle": text})
    db.brands.create_index("slug", unique=True, partialFilterExpression={"slug": text})
    db.connections.create_index([("user_id", 1), ("platform", 1)], unique=True)
    db.connections.create_index([("creator_id", 1), ("platform", 1)])
    db.metric_snapshots.create_index([("creator_id", 1), ("platform", 1), ("date", 1)])
    db.posts.create_index([("creator_id", 1), ("platform", 1), ("post_id", 1)], unique=True)
    db.listings.create_index("owner_id")
    db.listings.create_index("status")
    db.deals.create_index("creator_id")
    db.deals.create_index("brand_id")
    db.deals.create_index("stage")
    db.deals.create_index("collective_id")
    db.collectives.create_index("brand_id")
    db.consents.create_index([("creator_id", 1), ("lister_id", 1)])
    db.consent_audit.create_index([("creator_id", 1), ("at", -1)])
    db.applications.create_index("listing_id")
    db.invoices.create_index("creator_id")
    db.invoices.create_index("deal_id")
    db.payments.create_index([("kind", 1), ("ref_id", 1)])
    db.payments.create_index("payment_id", unique=True, partialFilterExpression={"payment_id": text})
    db.notifications.create_index("to")
    db.manual_metrics.create_index([("creator_id", 1), ("ts", -1)])
    db.rate_limits.create_index("expires")
    db.oauth_states.create_index("expires")
    db.fan_proof.create_index([("creator_id", 1), ("platform", 1)])
    db.rate_cards.create_index("creator_id")
    db.kit_versions.create_index([("creator_id", 1), ("number", 1)], unique=True)
    db.kit_versions.create_index([("creator_id", 1), ("content_sha256", 1)], unique=True)
    db.shortlists.create_index([("listing_id", 1), ("creator_id", 1)], unique=True)
    db.offer_drafts.create_index("listing_id")
    db.wishlists.create_index("brand_id")
    db.wishlists.create_index("creator_id")
    db.pitches.create_index([("creator_id", 1), ("sent_ts", -1)])
    db.pitches.create_index([("brand_id", 1), ("status", 1)])
    db.pitches.create_index("share_slug", unique=True, partialFilterExpression={"share_slug": text})
    db.fan_proof.create_index("brand_id")


def out(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Mongo document -> API dict (`_id` becomes `id`)."""
    if doc is None:
        return None
    d = dict(doc)
    d["id"] = d.pop("_id")
    return d


def out_many(docs) -> list[dict[str, Any]]:
    return [out(d) for d in docs]  # type: ignore[misc]
