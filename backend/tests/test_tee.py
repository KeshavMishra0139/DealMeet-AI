"""Protected computation: honest TEE status, attestation checks and the documented fallback.

The enclave and its verifier are replaced by test doubles here only; NitroVerifier itself
is checked against attestation documents signed by a certificate chain made in the test."""
import base64
import dataclasses
import datetime as dt
import hashlib
import json
import time

import cbor2
import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.x509.oid import NameOID

from app import config
from app.engines import audience_overlap as ao
from app.services import tee

VIEW = "/api/brands/br_thalam/creators/cr_b"  # Creator B shares demographics with Thalam Foods
PCR0 = bytes.fromhex("ab" * 48)


@pytest.fixture(autouse=True)
def _fresh():
    tee.reset()
    yield
    tee.reset()


def configure(monkeypatch, **kw):
    values = {"tee_endpoint": "https://enclave.test", "tee_trust_root": "-----BEGIN CERTIFICATE-----x", "tee_measurements": json.dumps({"0": PCR0.hex()}), **kw}
    s = dataclasses.replace(config.get_settings(), **values)
    monkeypatch.setattr(tee, "get_settings", lambda: s)


class Enclave:
    """A fake enclave proxy: records what it's sent and answers like the real one."""

    def __init__(self, bind=True):
        self.calls, self.bind = [], bind

    def post(self, path, body):
        self.calls.append((path, body))
        if path == "/attest":
            return {"document": base64.b64encode(json.dumps({"nonce": body["nonce"]}).encode()).decode()}
        result = ao.compute(body["input"])
        data = hashlib.sha256(tee.canonical(result)).digest() if self.bind else b"other"
        return {"result": result, "document": base64.b64encode(json.dumps({"nonce": body["nonce"], "user_data": data.hex()}).encode()).decode()}


class PassingVerifier:
    """Test double: accepts the fake enclave's documents when the nonce matches."""

    def verify(self, document, nonce):
        d = json.loads(document)
        if d["nonce"] != nonce.hex():
            raise tee.TeeError("nonce_mismatch")
        return {"module_id": "i-test-enc", "pcrs": [0], "user_data": bytes.fromhex(d["user_data"]) if "user_data" in d else None}


class FailingVerifier:
    def verify(self, document, nonce):
        raise tee.TeeError("measurement_mismatch")


# ------------------------------------------------------------------ not configured
def test_not_configured_is_said_plainly_and_the_fallback_runs(client, login, db):
    assert client.get("/api/health").json()["modes"]["tee"] == "not_configured"
    r = login("br_thalam").get(VIEW).json()["audience_overlap"]
    assert r["processed_in"] == "server" and r["tee_status"] == "not_configured" and "JodiDar's server" in r["note"]
    assert [d["key"] for d in r["dimensions"]] and all(d["share"] is None or 0 <= d["share"] <= 1 for d in r["dimensions"])
    ev = db.audit.find_one({"action": "tee_fallback_used"}, sort=[("ts", -1)])
    assert ev["job"] == "audience_overlap" and ev["reason_code"] == "not_configured"
    assert not any(k in str(ev) for k in ("cr_b", "Chennai", "share", "age"))  # no sensitive data in the event


def test_the_view_still_needs_the_brand_and_consent(client, login):
    assert client.get(VIEW).status_code == 401
    assert login("br_senpai").get(VIEW).status_code == 403
    assert login("br_senpai").get("/api/brands/br_senpai/creators/cr_a").json()["audience_overlap"] is None  # no demographics consent


def test_overlap_input_is_minimised():
    m = ao.minimise({"age": {"18-24": 0.5, "35-44": 0.2}, "gender": {"female": 0.7, "male": 0.3}, "cities": [{"name": "Chennai", "share": 0.3}, {"name": "Delhi", "share": 0.1}], "languages": {"ta": 0.8, "en": 0.2}},
                    {"ages": ["18-24"], "gender": "female", "cities": ["Chennai"], "languages": ["ta"]})
    assert m == {"ages": {"18-24": 0.5}, "gender": {"female": 0.7}, "cities": {"Chennai": 0.3}, "languages": {"ta": 0.8},
                 "target": {"ages": ["18-24"], "gender": "female", "cities": ["Chennai"], "languages": ["ta"]}}
    assert [d["share"] for d in ao.compute(m)["dimensions"]] == [0.5, 0.7, 0.3, 0.8]


# ------------------------------------------------------------------ configured
def test_failed_attestation_sends_nothing_and_falls_back(client, login, db, monkeypatch):
    configure(monkeypatch)
    enclave = Enclave()
    monkeypatch.setattr(tee, "_post", enclave.post)
    monkeypatch.setattr(tee, "_verifier", lambda: FailingVerifier())
    assert client.get("/api/health").json()["modes"]["tee"] == "failed"
    r = login("br_thalam").get(VIEW).json()["audience_overlap"]
    assert r["processed_in"] == "server" and r["tee_status"] == "failed" and "Nothing was sent to it" in r["note"]
    assert all(path == "/attest" for path, _ in enclave.calls)  # no job input left the server
    assert db.audit.find_one({"action": "tee_attestation_failed", "reason_code": "measurement_mismatch"})
    assert db.audit.find_one({"action": "tee_fallback_used", "reason_code": "measurement_mismatch"})


def test_a_verified_enclave_runs_the_job_on_minimised_input(client, login, monkeypatch, db):
    configure(monkeypatch)
    enclave = Enclave()
    monkeypatch.setattr(tee, "_post", enclave.post)
    monkeypatch.setattr(tee, "_verifier", lambda: PassingVerifier())
    assert client.get("/api/health").json()["modes"]["tee"] == "available"
    r = login("br_thalam").get(VIEW).json()["audience_overlap"]
    assert r["processed_in"] == "tee" and r["tee_status"] == "available" and "attested enclave" in r["note"]
    path, body = enclave.calls[-1]
    assert path == "/jobs/audience_overlap" and set(body["input"]) == {"ages", "gender", "cities", "languages", "target"}
    assert "cr_b" not in json.dumps(body)
    assert db.audit.find_one({"action": "tee_attestation_checked", "ok": True})


def test_an_answer_not_bound_to_the_attestation_is_rejected(login, monkeypatch, db):
    configure(monkeypatch)
    monkeypatch.setattr(tee, "_post", Enclave(bind=False).post)
    monkeypatch.setattr(tee, "_verifier", lambda: PassingVerifier())
    r = login("br_thalam").get(VIEW).json()["audience_overlap"]
    assert r["processed_in"] == "server" and r["tee_status"] == "failed"
    assert db.audit.find_one({"action": "tee_fallback_used", "reason_code": "result_not_bound"})


def test_an_unreachable_enclave_is_failed(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(tee, "_verifier", lambda: PassingVerifier())

    def down(*a, **kw):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "post", down)
    assert tee.status() == {"status": "failed", "provider": "aws_nitro", "reason": "unreachable"}


@pytest.mark.parametrize("kw,code", [({"tee_trust_root": None}, "no_trust_root"), ({"tee_measurements": "not json"}, "no_measurement_policy"),
                                     ({"tee_measurements": "{}"}, "no_measurement_policy"), ({"tee_trust_root": "/no/such/file.pem"}, "bad_trust_root")])
def test_missing_or_bad_config_is_failed_never_available(monkeypatch, kw, code):
    configure(monkeypatch, **kw)
    monkeypatch.setattr(tee, "_post", Enclave().post)
    assert tee.status(refresh=True)["reason"] == code


def test_fallback_events_are_throttled(login, db):
    since = time.time()
    a = login("br_thalam")
    for _ in range(3):
        a.get(VIEW)
    assert db.audit.count_documents({"action": "tee_fallback_used", "ts": {"$gte": since}}) == 1


# ------------------------------------------------------------------ the real Nitro verifier
def _cert(subject, issuer_key, key, issuer=None, ca=True, days=30):
    now = dt.datetime.now(dt.timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject)])
    b = (x509.CertificateBuilder().subject_name(name).issuer_name(issuer or name).public_key(key.public_key()).serial_number(x509.random_serial_number())
         .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=days))
         .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
    return b.sign(issuer_key, hashes.SHA384())


@pytest.fixture(scope="module")
def chain():
    root_key = ec.generate_private_key(ec.SECP384R1())
    root = _cert("test-root", root_key, root_key)
    mid_key = ec.generate_private_key(ec.SECP384R1())
    mid = _cert("test-intermediate", root_key, mid_key, issuer=root.subject)
    leaf_key = ec.generate_private_key(ec.SECP384R1())
    leaf = _cert("i-test-enc", mid_key, leaf_key, issuer=mid.subject, ca=False)
    return {"root": root, "mid": mid, "leaf": leaf, "leaf_key": leaf_key}


def _document(chain, nonce, pcr0=PCR0, ts=None, tamper=False, cabundle=None):
    payload = cbor2.dumps({
        "module_id": "i-test-enc", "digest": "SHA384", "timestamp": int((ts or time.time()) * 1000), "pcrs": {0: pcr0, 1: b"\0" * 48},
        "certificate": chain["leaf"].public_bytes(serialization.Encoding.DER),
        "cabundle": cabundle or [chain["root"].public_bytes(serialization.Encoding.DER), chain["mid"].public_bytes(serialization.Encoding.DER)],
        "public_key": None, "user_data": b"bound", "nonce": nonce,
    })
    protected = cbor2.dumps({1: -35})
    der = chain["leaf_key"].sign(cbor2.dumps(["Signature1", protected, b"", payload]), ec.ECDSA(hashes.SHA384()))
    r, s = decode_dss_signature(der)
    sig = r.to_bytes(48, "big") + s.to_bytes(48, "big")
    if tamper:
        payload = payload.replace(b"bound", b"BOUND")
    return cbor2.dumps(cbor2.CBORTag(18, [protected, {}, payload, sig]))


def _verifier(chain, pcr0=PCR0):
    return tee.NitroVerifier(chain["root"].public_bytes(serialization.Encoding.PEM), {0: pcr0.hex()}, max_age_s=300)


def test_nitro_verifier_accepts_a_valid_document(chain):
    claims = _verifier(chain).verify(_document(chain, b"n" * 32), b"n" * 32)
    assert claims["module_id"] == "i-test-enc" and claims["pcrs"] == [0] and claims["user_data"] == b"bound"


@pytest.mark.parametrize("change,code", [
    (lambda c: {"doc": _document(c, b"n" * 32, pcr0=b"\1" * 48)}, "measurement_mismatch"),
    (lambda c: {"doc": _document(c, b"n" * 32, tamper=True)}, "bad_signature"),
    (lambda c: {"doc": _document(c, b"other nonce")}, "nonce_mismatch"),
    (lambda c: {"doc": _document(c, b"n" * 32, ts=time.time() - 3600)}, "stale_document"),
    (lambda c: {"doc": b"not cbor at all"}, "malformed_document"),
    (lambda c: {"doc": _document(c, b"n" * 32, cabundle=[c["mid"].public_bytes(serialization.Encoding.DER)])}, "untrusted_root"),
    (lambda c: {"doc": _document(c, b"n" * 32, cabundle=[c["root"].public_bytes(serialization.Encoding.DER)])}, "broken_chain"),
])
def test_nitro_verifier_rejects_anything_that_doesnt_verify(chain, change, code):
    with pytest.raises(tee.TeeError) as e:
        _verifier(chain).verify(change(chain)["doc"], b"n" * 32)
    assert e.value.code == code


def test_nitro_verifier_rejects_another_trust_root(chain):
    other_key = ec.generate_private_key(ec.SECP384R1())
    other = _cert("someone-else", other_key, other_key)
    v = tee.NitroVerifier(other.public_bytes(serialization.Encoding.PEM), {0: PCR0.hex()})
    with pytest.raises(tee.TeeError) as e:
        v.verify(_document(chain, b"n" * 32), b"n" * 32)
    assert e.value.code == "untrusted_root"


def test_nitro_verifier_needs_a_measurement_policy(chain):
    with pytest.raises(tee.TeeError) as e:
        tee.NitroVerifier(chain["root"].public_bytes(serialization.Encoding.PEM), {})
    assert e.value.code == "no_measurement_policy"
