"""
认证系统测试
"""
import sys
import os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.auth.security import hash_password, verify_password, create_access_token, decode_access_token
from src.storage.database import DatabaseManager


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.close()


def test_hash_and_verify_password():
    hashed = hash_password("test123")
    assert hashed != "test123"
    assert verify_password("test123", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_and_decode_token():
    token = create_access_token({"sub": "42"})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "42"
    assert "exp" in payload


def test_decode_invalid_token():
    assert decode_access_token("invalid.token.here") is None


def test_create_user(db):
    user = db.create_user("alice", "alice@test.com", hash_password("pass123"))
    assert user is not None
    assert user.username == "alice"
    assert user.email == "alice@test.com"


def test_get_user_by_username(db):
    db.create_user("bob", "bob@test.com", hash_password("pass"))
    user = db.get_user_by_username("bob")
    assert user is not None
    assert user.username == "bob"


def test_get_user_by_email(db):
    db.create_user("carol", "carol@test.com", hash_password("pass"))
    user = db.get_user_by_email("carol@test.com")
    assert user is not None


def test_get_user_by_id(db):
    user = db.create_user("dave", "dave@test.com", hash_password("pass"))
    fetched = db.get_user_by_id(user.id)
    assert fetched.username == "dave"


def test_duplicate_username_rejected(db):
    db.create_user("eve", "eve1@test.com", hash_password("pass"))
    result = db.create_user("eve", "eve2@test.com", hash_password("pass"))
    assert result is None


def test_duplicate_email_rejected(db):
    db.create_user("frank", "frank@test.com", hash_password("pass"))
    result = db.create_user("frank2", "frank@test.com", hash_password("pass"))
    assert result is None
