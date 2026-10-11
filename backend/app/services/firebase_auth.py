"""Firebase ID tokens, verified on the server with the Firebase Admin SDK.

The browser signs in with Google or a phone OTP through Firebase, then sends the
ID token once to POST /api/auth/firebase. Here it is verified (signature, expiry,
this project's audience and issuer, and revocation) before any account is found
or created. A uid is never accepted without a verified token.

Credentials: FIREBASE_SERVICE_ACCOUNT_JSON (the service account JSON as one line)
or GOOGLE_APPLICATION_CREDENTIALS (a path to that file). Without them Firebase
sign-in is "not configured" and the route answers 503.
"""
from __future__ import annotations

import json
import logging
import threading

from fastapi import HTTPException

from ..config import get_settings

log = logging.getLogger("jodidar.firebase")
_lock = threading.Lock()
_app = None


def configured() -> bool:
    return get_settings().has_firebase


def _firebase_app():
    """The Admin SDK app, created once from the service account."""
    global _app
    if _app is not None:
        return _app
    with _lock:
        if _app is None:
            import firebase_admin
            from firebase_admin import credentials

            s = get_settings()
            if s.firebase_service_account_json:
                info = json.loads(s.firebase_service_account_json)
                cred = credentials.Certificate(info)
                project = s.firebase_project_id or info.get("project_id")
            else:
                cred = credentials.ApplicationDefault()
                project = s.firebase_project_id
            _app = firebase_admin.initialize_app(cred, {"projectId": project} if project else None, name="jodidar")
    return _app


def verify(id_token: str) -> dict:
    """The verified token's claims. Raises 401 for a forged, expired, revoked or
    wrong-project token, 403 for a disabled user and 503 when Firebase isn't set up."""
    if not configured():
        raise HTTPException(503, "Google and phone sign-in aren't configured on this server.")
    from firebase_admin import auth

    try:
        return auth.verify_id_token(id_token, app=_firebase_app(), check_revoked=True)
    except auth.ExpiredIdTokenError:
        raise HTTPException(401, "That sign-in expired. Sign in again.") from None
    except auth.RevokedIdTokenError:
        raise HTTPException(401, "That sign-in was revoked. Sign in again.") from None
    except auth.UserDisabledError:
        raise HTTPException(403, "This Firebase account is disabled.") from None
    except auth.CertificateFetchError:
        log.warning("Couldn't fetch Firebase signing certificates")
        raise HTTPException(503, "Couldn't reach Firebase to check the sign-in. Try again.") from None
    except (auth.InvalidIdTokenError, ValueError):
        # Forged, malformed, or issued for another Firebase project.
        raise HTTPException(401, "That sign-in couldn't be verified. Sign in again.") from None
