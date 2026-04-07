import jwt
from datetime import datetime, timezone

from core.security.security import (
    hash_password,
    verify_password,
    create_access_token,
)
from core.config import settings


class TestHashPassword:
    def test_hash_returns_string(self):
        hashed = hash_password("mypassword")
        assert isinstance(hashed, str)
        assert hashed != "mypassword"

    def test_different_calls_produce_different_hashes(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2


class TestVerifyPassword:
    def test_correct_password(self):
        hashed = hash_password("correct")
        assert verify_password("correct", hashed) is True

    def test_wrong_password(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False


class TestCreateAccessToken:
    def test_token_contains_subject(self):
        token = create_access_token({"sub": "testuser"})
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        assert payload["sub"] == "testuser"

    def test_token_contains_expiration(self):
        token = create_access_token({"sub": "testuser"})
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        assert "exp" in payload
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp > datetime.now(timezone.utc)

    def test_token_does_not_mutate_input(self):
        data = {"sub": "testuser"}
        create_access_token(data)
        assert "exp" not in data
