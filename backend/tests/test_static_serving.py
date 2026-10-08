"""Single-port mode must only ever serve files from the web build folder."""
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.static import mount_spa, static_file

SECRET = "ANTHROPIC_API_KEY=do-not-serve"


@pytest.fixture()
def site(tmp_path):
    """A build folder (dist) with a secret file next to it, like backend/.env beside frontend/dist."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>app</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "robots.txt").write_text("User-agent: *", encoding="utf-8")
    (tmp_path / ".env").write_text(SECRET, encoding="utf-8")
    try:
        (dist / "linked.env").symlink_to(tmp_path / ".env")
    except (OSError, NotImplementedError):  # symlinks need privileges on Windows
        pass
    app = FastAPI()
    mount_spa(app, dist)
    return dist, TestClient(app)


@pytest.mark.parametrize(
    "path",
    [
        "../.env",
        "assets/../../.env",
        "./../.env",
        "..\\.env",
        "/etc/passwd",
        os.path.abspath(os.sep + "etc"),
        "linked.env",
        "a\x00b",
        "",
    ],
)
def test_static_file_never_leaves_the_build(site, path):
    dist, _ = site
    assert static_file(dist, path) is None


def test_static_file_finds_real_files(site):
    dist, _ = site
    assert static_file(dist, "robots.txt") == (dist / "robots.txt").resolve()
    assert static_file(dist, "assets/app.js") == (dist / "assets" / "app.js").resolve()
    assert static_file(dist, "assets") is None  # a folder is not a file


@pytest.mark.parametrize(
    "url",
    [
        "/..%2F.env",
        "/%2e%2e/.env",
        "/%2e%2e%2f.env",
        "/assets%2f..%2f..%2f.env",
        "/..%5c.env",
        "/linked.env",
    ],
)
def test_traversal_requests_get_the_app_not_the_file(site, url):
    _, client = site
    r = client.get(url)
    assert SECRET not in r.text
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert "<title>app</title>" in r.text


def test_files_and_client_routes_still_load(site):
    _, client = site
    assert client.get("/robots.txt").text == "User-agent: *"
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert "<title>app</title>" in client.get("/creator/money").text
    assert "<title>app</title>" in client.get("/").text
