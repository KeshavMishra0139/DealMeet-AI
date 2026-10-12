"""Encryption at rest for third-party tokens (Instagram, and any later OAuth tokens).

Fernet (AES-128-CBC with an HMAC) from `cryptography`, keyed by TOKEN_ENC_KEY.
Generate a key once with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
Tokens are decrypted only in memory, right before an API call. They are never
logged and never sent to the browser.
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings


class TokenKeyMissing(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = get_settings().token_enc_key
    if not key:
        raise TokenKeyMissing("TOKEN_ENC_KEY isn't set")
    return Fernet(key.encode())


def configured() -> bool:
    try:
        _fernet()
        return True
    except (TokenKeyMissing, ValueError):
        return False


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(blob: str) -> str | None:
    """The token, or None if it can't be decrypted (for example after the key changed)."""
    try:
        return _fernet().decrypt(blob.encode()).decode()
    except (InvalidToken, TokenKeyMissing, ValueError):
        return None
