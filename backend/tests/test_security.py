"""JWT creation and validation. These tests do not need a database."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token


def _encode(payload: dict, key: str | None = None, algorithm: str = "HS256") -> str:
    return jwt.encode(payload, key or settings.jwt_secret_key, algorithm=algorithm)


def test_round_trip_returns_the_user_id() -> None:
    user_id = uuid.uuid4()

    assert decode_access_token(create_access_token(user_id)) == user_id


def test_token_contains_only_subject_and_timestamps() -> None:
    token = create_access_token(uuid.uuid4())
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])

    assert set(payload) == {"sub", "iat", "exp"}
    assert payload["exp"] - payload["iat"] == settings.access_token_expire_minutes * 60


def test_rejects_token_signed_with_another_secret() -> None:
    token = _encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(UTC) + timedelta(minutes=5)},
        key="a-different-secret-that-is-long-enough-for-hs256",
    )

    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(token)


def test_rejects_tampered_payload() -> None:
    header, _, signature = create_access_token(uuid.uuid4()).split(".")
    forged_payload = jwt.utils.base64url_encode(
        f'{{"sub":"{uuid.uuid4()}","exp":9999999999}}'.encode()
    ).decode()

    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(f"{header}.{forged_payload}.{signature}")


def test_rejects_expired_token() -> None:
    token = _encode({"sub": str(uuid.uuid4()), "exp": datetime.now(UTC) - timedelta(seconds=1)})

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_rejects_unsigned_alg_none_token() -> None:
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(UTC) + timedelta(minutes=5)},
        key="",  # alg=none ignores the key; PyJWT's types want a str
        algorithm="none",
    )

    with pytest.raises(jwt.InvalidAlgorithmError):
        decode_access_token(token)


@pytest.mark.parametrize("missing_claim", ["sub", "exp"])
def test_rejects_token_without_required_claim(missing_claim: str) -> None:
    payload = {"sub": str(uuid.uuid4()), "exp": datetime.now(UTC) + timedelta(minutes=5)}
    del payload[missing_claim]

    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(_encode(payload))


def test_rejects_subject_that_is_not_a_uuid() -> None:
    token = _encode({"sub": "not-a-uuid", "exp": datetime.now(UTC) + timedelta(minutes=5)})

    with pytest.raises(ValueError, match="badly formed"):
        decode_access_token(token)
