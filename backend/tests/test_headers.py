"""Security headers: on every response, HSTS only over HTTPS, the inline script by hash."""
import base64
import hashlib

from fastapi.testclient import TestClient

from app import headers
from app.main import app


def test_every_response_carries_the_security_headers(client):
    for r in (client.get("/api/health"), client.get("/api/nope"), client.post("/api/auth/demo", headers={"X-Requested-With": ""})):
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        csp = r.headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in csp and "object-src 'none'" in csp
        assert "'unsafe-eval'" not in csp
        # The script policy never allows arbitrary inline code.
        script = next(p for p in csp.split("; ") if p.startswith("script-src"))
        assert "'unsafe-inline'" not in script
        assert "Strict-Transport-Security" not in r.headers  # plain HTTP


def test_https_adds_hsts_and_upgrades_requests():
    with TestClient(app, base_url="https://testserver") as c:
        r = c.get("/api/health")
    assert r.headers["Strict-Transport-Security"].startswith("max-age=31536000")
    assert "upgrade-insecure-requests" in r.headers["Content-Security-Policy"]


def test_the_inline_theme_script_is_allowed_by_its_hash(tmp_path):
    body = '\n      if (location.pathname === "/") document.documentElement.className = "theme-site";\n    '
    index = tmp_path / "index.html"
    index.write_text(f'<html><head><script>{body}</script><script type="module" src="/assets/app.js"></script></head></html>')
    want = "'sha256-" + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode() + "'"
    assert headers.inline_hashes(index) == (want,)
    assert want in headers.policy(index)


def test_report_only_switch(client, monkeypatch):
    monkeypatch.setenv("CSP_REPORT_ONLY", "1")
    r = client.get("/api/health")
    assert "Content-Security-Policy" not in r.headers
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy-Report-Only"]
