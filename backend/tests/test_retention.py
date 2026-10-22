"""The retention sweep removes only what's past its time."""
import time

from app.services import retention

DAY = 86400


def test_sweep_removes_expired_and_old_records_only(db):
    now = time.time()
    db.sessions.insert_many([
        {"_id": "s_live", "user_id": "u", "expires_at": now + DAY, "revoked_at": None},
        {"_id": "s_expired", "user_id": "u", "expires_at": now - 1, "revoked_at": None},
        {"_id": "s_out_recent", "user_id": "u", "expires_at": now + DAY, "revoked_at": now - 2 * DAY},
        {"_id": "s_out_old", "user_id": "u", "expires_at": now + DAY, "revoked_at": now - 31 * DAY},
    ])
    for name in ("login_codes", "claim_codes", "oauth_states", "rate_limits"):
        db[name].insert_many([{"_id": f"{name}_live", "expires": now + 60}, {"_id": f"{name}_old", "expires": now - 60}])
    db.login_failures.insert_many([{"_id": "f_new", "email": "x@example.test", "at": now - 60}, {"_id": "f_old", "email": "x@example.test", "at": now - 2 * DAY}])
    db.audit.insert_many([{"_id": "a_new", "ts": now - 200 * DAY}, {"_id": "a_old", "ts": now - 366 * DAY}])
    db.email_log.insert_many([{"_id": "e_new", "ts": now - 30 * DAY}, {"_id": "e_old", "ts": now - 400 * DAY}])
    db.email_optouts.insert_one({"_id": "brand@example.in", "at": now - 900 * DAY})

    removed = retention.sweep(now)

    assert {d["_id"] for d in db.sessions.find({"user_id": "u"})} == {"s_live", "s_out_recent"}
    for name in ("login_codes", "claim_codes", "oauth_states", "rate_limits"):
        assert db[name].find_one({"_id": f"{name}_live"}) and not db[name].find_one({"_id": f"{name}_old"})
    assert db.login_failures.find_one({"_id": "f_new"}) and not db.login_failures.find_one({"_id": "f_old"})
    # The audit log keeps at least 180 days (CERT-In); a year here.
    assert db.audit.find_one({"_id": "a_new"}) and not db.audit.find_one({"_id": "a_old"})
    assert db.email_log.find_one({"_id": "e_new"}) and not db.email_log.find_one({"_id": "e_old"})
    # An unsubscribe is honoured for good.
    assert db.email_optouts.find_one({"_id": "brand@example.in"})
    assert removed["sessions"] >= 2 and removed["audit"] >= 1
    # Running it again changes nothing.
    assert retention.sweep(now) == {}
