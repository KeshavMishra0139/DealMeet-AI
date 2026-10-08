"""Single-port mode serves frontend/dist and must never hand out files outside it
(the repo-root .env holds the MongoDB URI, AI key and Razorpay secret)."""
from urllib.parse import quote

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import mount_spa

INDEX = "<!doctype html><title>JodiDar</title>"


@pytest.fixture()
def spa(tmp_path):
    repo = tmp_path / "repo"
    dist = repo / "frontend" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX, encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('app')", encoding="utf-8")
    (dist / "robots.txt").write_text("User-agent: *", encoding="utf-8")
    secret = repo / ".env.example"
    secret.write_text("AI_API_KEY=leaked", encoding="utf-8")

    app = FastAPI()
    mount_spa(app, dist)
    with TestClient(app) as c:
        yield c, secret


@pytest.mark.parametrize("path", ["/creator", "/demo/compare", "/"])
def test_routes_fall_back_to_index(spa, path):
    client, _ = spa
    r = client.get(path)
    assert r.status_code == 200
    assert r.text == INDEX


def test_serves_files_inside_dist(spa):
    client, _ = spa
    assert client.get("/assets/app.js").text == "console.log('app')"
    assert client.get("/robots.txt").text == "User-agent: *"


@pytest.mark.parametrize(
    "path",
    [
        "/..%2F..%2F.env.example",
        "/..%5C..%5C.env.example",
        "/%2E%2E/%2E%2E/.env.example",
        "/%00",
    ],
)
def test_traversal_returns_index(spa, path):
    client, _ = spa
    r = client.get(path)
    assert r.status_code == 200
    assert r.text == INDEX
    assert "leaked" not in r.text


def test_assets_traversal_is_refused(spa):
    client, _ = spa
    r = client.get("/assets/..%2F..%2F..%2F.env.example")
    assert r.status_code == 404
    assert "leaked" not in r.text


def test_absolute_path_returns_index(spa):
    client, secret = spa
    r = client.get("/" + quote(str(secret), safe=""))
    assert r.status_code == 200
    assert r.text == INDEX
