"""Connection status for each social platform a creator can connect.

A platform is "connected" only through its official login (OAuth, read-only
scopes); a YouTube channel linked by its handle is "linked" (public data, ownership
not verified). When an integration isn't configured on the server it is
"unavailable"; before the creator connects it is "not_connected". Nothing is
simulated for an account that isn't connected.
"""
from __future__ import annotations

from typing import Callable

PLATFORMS = {"instagram": "Instagram", "youtube": "YouTube"}

# platform -> (is the integration configured on this server?, status for one creator)
PROVIDERS: dict[str, tuple[Callable[[], bool], Callable[[dict], dict]]] = {}


def register(platform: str, configured: Callable[[], bool], status_for: Callable[[dict], dict]) -> None:
    PROVIDERS[platform] = (configured, status_for)


def status(creator: dict) -> dict:
    out = []
    for key, label in PLATFORMS.items():
        provider = PROVIDERS.get(key)
        if not provider:
            out.append({"platform": key, "label": label, "status": "unavailable", "detail": f"{label} connect isn't set up on this server yet."})
            continue
        out.append(provider[1](creator))
    return {"platforms": out, "sample_data": creator.get("insights_source") == "synthetic"}


def register_builtin() -> None:
    from . import instagram, youtube_public

    register("instagram", instagram.configured, instagram.status)
    register("youtube", youtube_public.configured, youtube_public.status)


register_builtin()
