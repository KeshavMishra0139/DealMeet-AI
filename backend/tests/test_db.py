"""The database: explicit mock mode, no silent fallback, indexes, health and the seed script."""
import os
import sys
from pathlib import Path

import pytest

from app import config, db as dbmod

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import seed as seed_script  # noqa: E402


@pytest.fixture()
def env(monkeypatch):
    def set_env(**kw):
        for k, v in kw.items():
            if v is None:
                monkeypatch.delenv(k, raising=False)
            else:
                monkeypatch.setenv(k, v)
        config.get_settings.cache_clear()

    yield set_env
    config.get_settings.cache_clear()


def test_without_mock_mode_a_missing_uri_stops_startup(env):
    env(USE_MOCK_DB="0", MONGODB_URI=None)
    with pytest.raises(dbmod.DatabaseNotConfigured, match="MONGODB_URI"):
        dbmod._connect()


def test_an_unreachable_database_stops_startup(env, monkeypatch):
    import pymongo

    class Down:
        def __init__(self, *a, **kw):
            self.admin = self

        def command(self, *_):
            raise pymongo.errors.ServerSelectionTimeoutError("no route")

        def close(self):
            pass

    monkeypatch.setattr(pymongo, "MongoClient", Down)
    env(USE_MOCK_DB="0", MONGODB_URI="mongodb+srv://user:pw@cluster0.example.mongodb.net/")
    with pytest.raises(dbmod.DatabaseNotConfigured, match="Network Access") as e:
        dbmod._connect()
    assert "pw@" not in str(e.value)  # the connection string (and its password) is never echoed


def test_mock_mode_is_explicit_and_reported(client, db):
    h = client.get("/api/health").json()
    assert h["modes"]["db"] == "mock" and h["modes"]["db_ok"] is True and h["status"] == "ok"


def test_unique_indexes_hold(db):
    import pymongo

    with pytest.raises(pymongo.errors.DuplicateKeyError):
        db.creators.insert_one({"_id": "cr_dup", "handle": "creator.a", "name": "x", "niche": "food"})
    db.users.insert_one({"_id": "us_f1", "firebase_uid": "uid-1", "role": "creator"})
    with pytest.raises(pymongo.errors.DuplicateKeyError):
        db.users.insert_one({"_id": "us_f2", "firebase_uid": "uid-1", "role": "creator"})
    db.connections.insert_one({"_id": "cn1", "user_id": "us_f1", "platform": "instagram"})
    with pytest.raises(pymongo.errors.DuplicateKeyError):
        db.connections.insert_one({"_id": "cn2", "user_id": "us_f1", "platform": "instagram"})


def test_seeded_records_are_marked_synthetic(db):
    for name in ("creators", "brands", "listings", "deals"):
        assert db[name].count_documents({}) == db[name].count_documents({"source": "synthetic"}), name


def test_seed_script_only_fills_empty_collections(db, capsys):
    assert seed_script.main([]) == 0
    assert "nothing was changed" in capsys.readouterr().out
    assert seed_script.main(["--reset"]) == 0  # in-memory: fine without confirmation


def test_seed_script_reset_on_a_real_database_needs_confirmation(db, monkeypatch, capsys):
    monkeypatch.setattr(seed_script, "db_mode", lambda: "atlas")
    assert seed_script.main(["--reset"]) == 2
    assert "--confirm-reset" in capsys.readouterr().out


def test_reset_on_a_real_database_keeps_real_accounts_and_data(db):
    from app.seed.load import seed_all

    db.users.insert_one({"_id": "us_real", "role": "creator", "email": "real@example.com", "creator_id": "cr_real"})
    db.creators.insert_one({"_id": "cr_real", "handle": "real.one", "name": "Real", "niche": "food", "source": "manual"})
    seed_all(db, force=True, sandbox=False)
    assert db.users.find_one({"_id": "us_real"}) and db.creators.find_one({"_id": "cr_real"})
    assert db.creators.find_one({"_id": "cr_a"})["source"] == "synthetic"


@pytest.mark.skipif(not os.getenv("TEST_MONGODB_URI"), reason="set TEST_MONGODB_URI to run against a real MongoDB")
def test_data_survives_a_client_restart(env):
    env(USE_MOCK_DB="0", MONGODB_URI=os.environ["TEST_MONGODB_URI"], MONGODB_DB="jodidar_test")
    dbmod.reset_client()
    try:
        dbmod.get_db().restart_check.replace_one({"_id": "k"}, {"_id": "k", "v": 42}, upsert=True)
        dbmod.reset_client()  # a fresh client, as after a restart
        assert dbmod.get_db().restart_check.find_one({"_id": "k"})["v"] == 42
        dbmod.get_db().restart_check.drop()
    finally:
        dbmod.reset_client()
        env(USE_MOCK_DB="1", MONGODB_URI=None, MONGODB_DB=None)
