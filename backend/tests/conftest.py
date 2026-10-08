import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.seed.load import seed_all


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    d = get_db()
    seed_all(d, force=True)
    from app.services import cache

    cache.clear_runtime()
    return d
