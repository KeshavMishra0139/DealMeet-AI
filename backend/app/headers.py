"""Security headers on every response.

The Content Security Policy lists only the origins the web app really uses:

- scripts: the app itself, Razorpay Checkout, and Google's scripts for Firebase sign-in
  and its reCAPTCHA (phone sign-in). The one inline script in index.html (it picks the
  theme before the first paint) is allowed by its SHA-256 hash, read from the build.
- frames: Razorpay Checkout, Firebase's sign-in helper and reCAPTCHA.
- connections: the API (same origin), Firebase Auth and Razorpay.
- images: any HTTPS host, because creator and channel pictures come from YouTube's and
  Instagram's CDNs. Images can't run code.
- styles: inline styles are allowed; the UI libraries (dialogs, toasts) insert them.

The app can't be framed by another site (frame-ancestors, X-Frame-Options), browsers
must not guess content types, HTTPS is remembered for a year once seen over HTTPS (HSTS),
and other sites see only our origin as the referrer.

CSP_REPORT_ONLY=1 sends the policy as Content-Security-Policy-Report-Only instead, so a
deployment that loads something new can be checked in the browser console without
breaking pages.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
from functools import lru_cache
from pathlib import Path

INLINE_SCRIPT = re.compile(r"<script>(.*?)</script>", re.S)

SCRIPTS = (
    "https://checkout.razorpay.com",
    "https://apis.google.com",
    "https://www.google.com/recaptcha/",
    "https://www.gstatic.com/recaptcha/",
)
FRAMES = (
    "https://api.razorpay.com",
    "https://checkout.razorpay.com",
    "https://*.firebaseapp.com",
    "https://*.web.app",
    "https://www.google.com",
    "https://recaptcha.google.com",
)
CONNECT = (
    "https://identitytoolkit.googleapis.com",
    "https://securetoken.googleapis.com",
    "https://www.googleapis.com",
    "https://api.razorpay.com",
    "https://lumberjack.razorpay.com",
)
# The landing page's background video.
MEDIA = ("https://d8j0ntlcm91z4.cloudfront.net",)


def _on(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


@lru_cache
def inline_hashes(index: Path | None) -> tuple[str, ...]:
    """CSP hashes of the inline scripts in the built index.html."""
    if not index or not index.exists():
        return ()
    html = index.read_text(encoding="utf-8")
    return tuple(
        "'sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode() + "'"
        for s in INLINE_SCRIPT.findall(html)
    )


@lru_cache
def policy(index: Path | None) -> str:
    frames = list(FRAMES)
    # A custom Firebase auth domain (not *.firebaseapp.com) hosts the sign-in helper frame.
    auth_domain = os.getenv("VITE_FIREBASE_AUTH_DOMAIN", "").strip()
    if auth_domain and re.fullmatch(r"[a-z0-9.-]+", auth_domain):
        frames.append(f"https://{auth_domain}")
    parts = {
        "default-src": ["'self'"],
        "script-src": ["'self'", *inline_hashes(index), *SCRIPTS],
        "style-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["'self'", "data:", "blob:", "https:"],
        "font-src": ["'self'", "data:"],
        "media-src": ["'self'", *MEDIA],
        "connect-src": ["'self'", *CONNECT],
        "frame-src": frames,
        "worker-src": ["'self'", "blob:"],
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
        "frame-ancestors": ["'none'"],
    }
    return "; ".join(f"{k} {' '.join(v)}" for k, v in parts.items())


def apply(headers, https: bool, index: Path | None) -> None:
    """Sets the security headers on a response's headers."""
    csp = policy(index)
    if https:
        csp += "; upgrade-insecure-requests"
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    headers["Content-Security-Policy-Report-Only" if _on("CSP_REPORT_ONLY") else "Content-Security-Policy"] = csp
    headers["X-Content-Type-Options"] = "nosniff"
    headers["X-Frame-Options"] = "DENY"
    headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()"
    # Sign-in and payment pop-ups (Firebase, Razorpay) must still be able to report back.
    headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
