"""The shared demo's caps never apply on a live site; live sites have daily limits instead."""
import pytest
from fastapi import HTTPException

from app import config
from app.services import limits


@pytest.fixture()
def live(monkeypatch, db):
    monkeypatch.setenv("DEMO_MODE", "0")
    config.get_settings.cache_clear()
    db.rate_limits.delete_many({})
    yield
    config.get_settings.cache_clear()


def test_demo_caps_only_in_the_demo(db, live):
    limits.demo_cap(10_000, 50)  # a live site with many brands: no cap


def test_demo_cap_applies_in_the_demo(db):
    with pytest.raises(HTTPException) as e:
        limits.demo_cap(50, 50)
    assert e.value.status_code == 429 and "shared demo" in e.value.detail
    limits.daily("anything", 1, "done it")  # no daily limits in the demo
    limits.daily("anything", 1, "done it")


def test_live_daily_limit(db, live):
    for _ in range(3):
        limits.daily("offer:br_x", 3, "sent 3 offers")
    with pytest.raises(HTTPException) as e:
        limits.daily("offer:br_x", 3, "sent 3 offers")
    assert e.value.status_code == 429 and "sent 3 offers today" in e.value.detail
    limits.daily("offer:br_y", 3, "sent 3 offers")  # per account
