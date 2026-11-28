import base64
import json
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "unit-test-secret-key-at-least-32-characters"
ALGO = "HS256"


def _token(user_id=None, **overrides):
    kwargs = {"secret_key": SECRET, "algorithm": ALGO, "expires_minutes": 30, **overrides}
    return create_access_token(user_id or uuid.uuid4(), **kwargs)


# --- passwords -------------------------------------------------------------------------


def test_hash_is_not_plaintext_and_verifies():
    hashed = hash_password("correct horse battery")
    assert "correct horse" not in hashed
    assert hashed.startswith("$argon2id$")
    assert verify_password("correct horse battery", hashed) is True


def test_wrong_password_is_rejected():
    assert verify_password("wrong", hash_password("right-password")) is False


def test_same_password_gets_different_hashes():
    assert hash_password("same-password") != hash_password("same-password")  # random salt


def test_corrupt_stored_hash_is_rejected_not_raised():
    assert verify_password("anything", "not-a-valid-hash") is False


# --- tokens ----------------------------------------------------------------------------


def test_token_roundtrip():
    user_id = uuid.uuid4()
    token, issued = _token(user_id)

    claims = decode_access_token(token, secret_key=SECRET, algorithm=ALGO)

    assert claims.user_id == user_id
    assert claims.jti == issued.jti
    assert abs(claims.expires_at - issued.expires_at) < timedelta(seconds=1)


def test_each_token_has_a_unique_jti():
    user_id = uuid.uuid4()
    assert _token(user_id)[1].jti != _token(user_id)[1].jti


def test_expired_token_is_rejected():
    token, _ = _token(now=datetime.now(UTC) - timedelta(hours=1))
    with pytest.raises(UnauthorizedError, match="expired"):
        decode_access_token(token, secret_key=SECRET, algorithm=ALGO)


def test_token_signed_with_another_key_is_rejected():
    token, _ = _token(secret_key="a-completely-different-secret-key-0123456789")
    with pytest.raises(UnauthorizedError):
        decode_access_token(token, secret_key=SECRET, algorithm=ALGO)


def test_tampered_payload_is_rejected():
    token, _ = _token()
    header, payload, signature = token.split(".")
    forged = json.loads(base64.urlsafe_b64decode(payload + "=="))
    forged["sub"] = str(uuid.uuid4())
    forged_payload = base64.urlsafe_b64encode(json.dumps(forged).encode()).rstrip(b"=").decode()
    with pytest.raises(UnauthorizedError):
        decode_access_token(f"{header}.{forged_payload}.{signature}", secret_key=SECRET, algorithm=ALGO)


def test_alg_none_token_is_rejected():
    now = datetime.now(UTC)
    unsigned = jwt.encode(
        {"sub": str(uuid.uuid4()), "jti": "x", "iat": now, "exp": now + timedelta(minutes=5)},
        key=None,
        algorithm="none",
    )
    with pytest.raises(UnauthorizedError):
        decode_access_token(unsigned, secret_key=SECRET, algorithm=ALGO)


def test_token_missing_required_claim_is_rejected():
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "iat": now, "exp": now + timedelta(minutes=5)},  # no jti
        SECRET,
        algorithm=ALGO,
    )
    with pytest.raises(UnauthorizedError):
        decode_access_token(token, secret_key=SECRET, algorithm=ALGO)


def test_non_uuid_subject_is_rejected():
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": "not-a-uuid", "jti": "x", "iat": now, "exp": now + timedelta(minutes=5)},
        SECRET,
        algorithm=ALGO,
    )
    with pytest.raises(UnauthorizedError):
        decode_access_token(token, secret_key=SECRET, algorithm=ALGO)


def test_garbage_is_rejected():
    with pytest.raises(UnauthorizedError):
        decode_access_token("not.a.jwt", secret_key=SECRET, algorithm=ALGO)
