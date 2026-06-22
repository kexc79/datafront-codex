import sys
import types

import pytest

pytest.importorskip("passlib")

fake_jose = types.ModuleType("jose")
fake_jose.JWTError = Exception
fake_jose.jwt = types.SimpleNamespace(encode=lambda *args, **kwargs: "token", decode=lambda *args, **kwargs: {})
sys.modules.setdefault("jose", fake_jose)

from app.security import get_password_hash, verify_password


def test_long_password_can_be_hashed_and_verified() -> None:
    password = "very-long-admin-password-" * 8

    hashed = get_password_hash(password)

    assert hashed.startswith("$pbkdf2-sha256$")
    assert verify_password(password, hashed)
