"""Connection status for each social platform a creator can connect.

A platform is "connected" only through its official login (OAuth, read-only
scopes). Until that integration is configured on the server it is "unavailable";
until the creator connects it is "not_connected". Nothing is simulated for an
account that isn't connected.
"""
from __future__ import annotations

from ..db import get_db

PLATFORMS = {
    "instagram": "Instagram",
    "youtube": "YouTube",
}

# Each integration registers (is_configured, connection_for_creator) here when it exists.
PROVIDERS: dict[str, tuple] = {}


def status(creator: dict) -> dict:
    db = get_db()
    out = []
    for key, label in PLATFORMS.items():
        provider = PROVIDERS.get(key)
        if not provider or not provider[0]():
            out.append({"platform": key, "label": label, "status": "unavailable", "detail": f"{label} connect isn't set up on this server yet."})
            continue
        conn = db.connections.find_one({"creator_id": creator["_id"], "platform": key})
        if not conn:
            out.append({"platform": key, "label": label, "status": "not_connected", "detail": f"Connect {label} with its official login to use your real numbers."})
            continue
        out.append(provider[1](conn))
    return {"platforms": out, "sample_data": creator.get("insights_source") == "synthetic"}
