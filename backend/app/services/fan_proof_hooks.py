"""Cleanup when a creator disconnects a platform: anything derived from its posts goes too."""
from __future__ import annotations

from ..db import get_db


def on_disconnect(creator_id: str, platform: str) -> None:
    get_db().fan_proof.delete_many({"creator_id": creator_id, "platform": platform})
