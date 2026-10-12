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
        # Windows: drive letters, drive-relative paths, network (UNC) paths, backslashes, data streams
        "C:/Windows/win.ini",
        "C:\\Windows\\win.ini",
        "C:secret.txt",
        "\\\\attacker.example\\share\\x",
        "//attacker.example/share/x",
        "..\\..\\.env",
        "robots.txt::$DATA",
    ],
)
def test_static_file_never_leaves_the_build(site, path):
    dist, _ = site
    assert static_file(dist, path) is None


def test_unsafe_paths_are_refused_before_touching_the_disk(site, monkeypatch):
    """On Windows, resolving a network path already connects to that host, so these
    must be rejected as text, without any filesystem call."""
    import pathlib

    def no_disk(*_a, **_k):
        raise AssertionError("filesystem touched")

    dist, _ = site
    monkeypatch.setattr(pathlib.Path, "resolve", no_disk)
    monkeypatch.setattr(pathlib.Path, "is_file", no_disk)
    for path in ["\\\\host\\share\\x", "//host/share/x", "C:/x", "../x", "a\\b", "/abs"]:
        assert static_file(dist, path) is None


def test_build_files_get_javascript_types_even_if_the_registry_says_text(site):
    """Windows' registry can map .js to text/plain; browsers then refuse to run the app."""
    import mimetypes

    mimetypes.add_type("text/plain", ".js")  # what a bad registry entry does
    dist, _ = site
    app = FastAPI()
    mount_spa(app, dist)
    r = TestClient(app).get("/assets/app.js")
    assert r.headers["content-type"].startswith("text/javascript")


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


def test_assets_folder_refuses_traversal(site):
    _, client = site
    r = client.get("/assets/..%2F..%2F..%2F.env")
    assert r.status_code == 404
    assert SECRET not in r.text


def test_absolute_path_to_a_real_file_gets_the_app(site):
    from urllib.parse import quote

    dist, client = site
    secret = dist.parent / ".env"
    r = client.get("/" + quote(str(secret), safe=""))
    assert r.status_code == 200
    assert SECRET not in r.text and "<title>app</title>" in r.text


def test_files_and_client_routes_still_load(site):
    _, client = site
    assert client.get("/robots.txt").text == "User-agent: *"
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert "<title>app</title>" in client.get("/creator/money").text
    assert "<title>app</title>" in client.get("/").text


def test_creator_pages_get_escaped_link_previews(site, db):
    from app.static import with_preview

    dist, client = site
    (dist / "index.html").write_text('<!doctype html><head><meta name="description" content="x" /><title>app</title></head><body></body>', encoding="utf-8")
    db.creators.update_one({"_id": "cr_b"}, {"$set": {"name": 'Meera "<script>alert(1)</script>"', "branding": {"positioning": "Tamil breakfasts & <b>more</b>", "show_on_page": True}}})
    handle = db.creators.find_one({"_id": "cr_b"})["handle"]
    html = client.get(f"/c/{handle}").text
    assert 'property="og:title" content="Meera &quot;&lt;script&gt;' in html and "<script>alert" not in html
    assert 'content="Tamil breakfasts &amp; &lt;b&gt;more&lt;/b&gt;"' in html
    assert f'property="og:url" content="http://testserver/c/{handle}"' in html and html.count("<title>") == 1
    # Unknown or private pages get the plain app.
    assert "og:title" not in client.get("/c/nobody-here").text
    db.creators.update_one({"_id": "cr_b"}, {"$set": {"public_page": False}})
    assert "og:title" not in client.get(f"/c/{handle}").text
    assert with_preview("<html></html>", {"title": "<t>", "description": "d"}, "u").startswith("<meta")
