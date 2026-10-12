"""Protected computation in a trusted execution environment (TEE), handled honestly.

What it protects: audience demographics. A brand that a creator shares demographics with
sees how much of the creator's audience overlaps its target (ages, gender, cities,
languages). With a TEE that overlap is computed inside an attested enclave; the server
sends it only the bucket percentages the job needs and checks that the answer came from
that enclave.

Status is one of:
- ``not_configured``: no TEE_ENDPOINT. Nothing claims to be protected.
- ``available``: the enclave's attestation verified against the configured trust root
  (TEE_TRUST_ROOT) and measurement policy (TEE_MEASUREMENTS), with a fresh nonce.
- ``failed``: configured, but the endpoint is unreachable, the policy is missing, or the
  attestation didn't verify. Nothing is sent to it.

Fallback (one rule, documented in the README): when the status isn't ``available``, or a
job's answer doesn't verify, the job runs on our own server with the same minimised input
(bucket percentages only: no ids, names or handles), and the result says so. An ordinary
container, TLS or a mock attestation is never described as a TEE.

Supported enclave: AWS Nitro Enclaves. The enclave app (not part of this repository) is
reached through a proxy on the parent instance and answers two calls:

    POST {TEE_ENDPOINT}/attest            {"nonce": hex}                 -> {"document": base64}
    POST {TEE_ENDPOINT}/jobs/{name}       {"nonce": hex, "input": {...}} -> {"result": {...}, "document": base64}

``document`` is the Nitro attestation document (COSE_Sign1). For a job, its ``nonce`` is
ours and its ``user_data`` is the SHA-256 of the result's canonical JSON, which binds the
answer to the attested enclave.

Security events (attestation checked or failed, fallback used) go to the audit log with a
reason code only: no documents, inputs, results or keys.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Callable, Protocol

import httpx

from ..config import get_settings
from . import auth as au

log = logging.getLogger("jodidar.tee")

CACHE_S = 60  # how long an attestation result is trusted before checking again
EVENT_EVERY_S = 600  # at most one fallback event per job and reason in this window
PROVIDER = "aws_nitro"

_lock = threading.Lock()
_cache: dict[str, Any] = {}
_events: dict[tuple[str, str], float] = {}


class TeeError(Exception):
    """The enclave or its attestation can't be trusted. `code` is safe to log."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


class Verifier(Protocol):
    def verify(self, document: bytes, nonce: bytes) -> dict: ...


# ------------------------------------------------------------------ AWS Nitro attestation
class NitroVerifier:
    """Verifies an AWS Nitro Enclaves attestation document.

    Checks, in order: the COSE_Sign1 structure and ES384; that the certificate bundle starts
    at the configured trust root and each certificate is issued by the one before it and
    valid now; the signature with the enclave's certificate; every PCR named in the
    measurement policy; the nonce; and that the document is fresh."""

    def __init__(self, trust_root_pem: bytes, measurements: dict[int, str], max_age_s: int = 300):
        from cryptography import x509

        if not measurements:
            raise TeeError("no_measurement_policy", "TEE_MEASUREMENTS lists no PCR values to check.")
        try:
            self.root = x509.load_pem_x509_certificate(trust_root_pem)
        except ValueError:
            raise TeeError("bad_trust_root", "TEE_TRUST_ROOT isn't a PEM certificate.") from None
        self.measurements = {int(k): v.lower() for k, v in measurements.items()}
        self.max_age_s = max_age_s

    def verify(self, document: bytes, nonce: bytes) -> dict:
        import cbor2
        from cryptography import x509
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

        try:
            cose = cbor2.loads(document)
            if isinstance(cose, cbor2.CBORTag):
                cose = cose.value
            protected, _unprotected, payload_raw, signature = cose
            header = cbor2.loads(protected) if protected else {}
            doc = cbor2.loads(payload_raw)
        except Exception:
            raise TeeError("malformed_document") from None
        if header.get(1) != -35 or doc.get("digest") != "SHA384":
            raise TeeError("unsupported_algorithm")

        try:
            leaf = x509.load_der_x509_certificate(doc["certificate"])
            bundle = [x509.load_der_x509_certificate(c) for c in doc["cabundle"]]
        except Exception:
            raise TeeError("malformed_certificates") from None
        der = serialization.Encoding.DER
        if not bundle or bundle[0].public_bytes(der) != self.root.public_bytes(der):
            raise TeeError("untrusted_root")
        chain = [*bundle, leaf]
        now = time.time()
        for parent, child in zip(chain, chain[1:]):
            try:
                child.verify_directly_issued_by(parent)
            except (ValueError, TypeError, InvalidSignature):
                raise TeeError("broken_chain") from None
        for cert in chain:
            if not cert.not_valid_before_utc.timestamp() <= now <= cert.not_valid_after_utc.timestamp():
                raise TeeError("certificate_expired")

        if len(signature) != 96:
            raise TeeError("bad_signature")
        r, s = int.from_bytes(signature[:48], "big"), int.from_bytes(signature[48:], "big")
        signed = cbor2.dumps(["Signature1", protected, b"", payload_raw])
        key = leaf.public_key()
        if not isinstance(key, ec.EllipticCurvePublicKey):
            raise TeeError("bad_signature")
        try:
            key.verify(encode_dss_signature(r, s), signed, ec.ECDSA(hashes.SHA384()))
        except InvalidSignature:
            raise TeeError("bad_signature") from None

        pcrs = doc.get("pcrs") or {}
        for index, expected in self.measurements.items():
            got = pcrs.get(index)
            if not isinstance(got, bytes) or got.hex() != expected:
                raise TeeError("measurement_mismatch")
        if doc.get("nonce") != nonce:
            raise TeeError("nonce_mismatch")
        ts = (doc.get("timestamp") or 0) / 1000
        if not now - self.max_age_s <= ts <= now + 60:
            raise TeeError("stale_document")
        return {"module_id": doc.get("module_id"), "pcrs": sorted(self.measurements), "timestamp": ts, "user_data": doc.get("user_data")}


def _trust_root(value: str) -> bytes:
    if "-----BEGIN" in value:
        return value.encode()
    path = Path(value)
    if not path.is_file():
        raise TeeError("bad_trust_root", "TEE_TRUST_ROOT is neither PEM text nor a readable file.")
    return path.read_bytes()


def _verifier() -> Verifier:
    """The verifier from config. Tests swap in a test double here."""
    s = get_settings()
    if not s.tee_trust_root:
        raise TeeError("no_trust_root", "TEE_TRUST_ROOT isn't set.")
    if not s.tee_measurements:
        raise TeeError("no_measurement_policy", "TEE_MEASUREMENTS isn't set.")
    try:
        policy = json.loads(s.tee_measurements)
        assert isinstance(policy, dict)
        measurements = {int(k): str(v) for k, v in policy.items()}
    except (ValueError, AssertionError):
        raise TeeError("no_measurement_policy", 'TEE_MEASUREMENTS must be JSON like {"0": "<hex>"}.') from None
    return NitroVerifier(_trust_root(s.tee_trust_root), measurements, s.tee_max_age_s)


# ------------------------------------------------------------------ talking to the enclave
def _post(path: str, body: dict) -> dict:
    url = f"{get_settings().tee_endpoint}{path}"
    try:
        r = httpx.post(url, json=body, timeout=10)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError:
        raise TeeError("unreachable") from None
    except ValueError:
        raise TeeError("bad_response") from None


def _document(body: dict) -> bytes:
    try:
        return base64.b64decode(body["document"], validate=True)
    except (KeyError, TypeError, binascii.Error):
        raise TeeError("bad_response") from None


def canonical(result: Any) -> bytes:
    return json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _security_event(action: str, **detail: Any) -> None:
    au.audit(action, None, "system", provider=PROVIDER, **detail)


def _attest() -> dict:
    nonce = secrets.token_bytes(32)
    claims = _verifier().verify(_document(_post("/attest", {"nonce": nonce.hex()})), nonce)
    return {"module_id": claims.get("module_id"), "pcrs_checked": claims.get("pcrs")}


# ------------------------------------------------------------------ public API
def status(refresh: bool = False) -> dict:
    """The real TEE status: not_configured, available or failed (with a reason code)."""
    if not get_settings().tee_endpoint:
        return {"status": "not_configured", "provider": None, "reason": None}
    with _lock:
        if not refresh and _cache and time.time() - _cache["at"] < CACHE_S:
            return dict(_cache["status"])
    try:
        info = _attest()
        out = {"status": "available", "provider": PROVIDER, "reason": None, **info}
        _security_event("tee_attestation_checked", ok=True, pcrs_checked=info.get("pcrs_checked"))
    except TeeError as e:
        out = {"status": "failed", "provider": PROVIDER, "reason": e.code}
        _security_event("tee_attestation_failed", reason_code=e.code)
    with _lock:
        _cache.update({"at": time.time(), "status": out})
    return dict(out)


def run(job: str, payload: dict) -> dict:
    """Run a job in the enclave. Raises TeeError unless it's available and the answer verifies."""
    st = status()
    if st["status"] != "available":
        raise TeeError(st["status"] if st["status"] == "not_configured" else (st["reason"] or "failed"))
    nonce = secrets.token_bytes(32)
    body = _post(f"/jobs/{job}", {"nonce": nonce.hex(), "input": payload})
    if not isinstance(body.get("result"), dict):
        raise TeeError("bad_response")
    claims = _verifier().verify(_document(body), nonce)
    if claims.get("user_data") != hashlib.sha256(canonical(body["result"])).digest():
        raise TeeError("result_not_bound")
    return body["result"]


def protected(job: str, payload: dict, fallback: Callable[[dict], dict]) -> dict:
    """Run `job` in the TEE if it's available and verifies; otherwise the documented
    fallback: our own server, on the same minimised `payload`."""
    try:
        return {"result": run(job, payload), "processed_in": "tee", "tee_status": "available", "reason": None}
    except TeeError as e:
        code = e.code
    except Exception:  # a bug on the TEE path must not take the page down, nor pass as protected
        log.exception("TEE job %s failed", job)
        code = "error"
    if code not in ("not_configured",):
        with _lock:  # a job that didn't verify: check attestation again before the next job
            _cache.clear()
    status_now = "not_configured" if code == "not_configured" else "failed"
    key, now = (job, code), time.time()
    with _lock:
        due = now - _events.get(key, 0) >= EVENT_EVERY_S
        if due:
            _events[key] = now
    if due:
        _security_event("tee_fallback_used", job=job, reason_code=code)
    return {"result": fallback(payload), "processed_in": "server", "tee_status": status_now, "reason": code}


def reset() -> None:
    """Forget cached attestation and event throttles (config changes, tests)."""
    with _lock:
        _cache.clear()
        _events.clear()
