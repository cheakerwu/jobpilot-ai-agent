"""
数据隔离测试：不同用户只能看到自己的数据
"""
import sys
import os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from src.auth.security import hash_password
from src.storage.database import DatabaseManager
from src.helpers import load_config


@pytest.fixture
def client(tmp_path, monkeypatch):
    """创建测试客户端，使用临时数据库"""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("JOBPILOT_CONFIG", str(tmp_path / "config.yaml"))
    import yaml
    config = {"storage": {"db_path": db_path}, "resume": {"provider": "qwen"}, "server": {"allowed_origins": ["*"]}}
    with open(str(tmp_path / "config.yaml"), "w") as f:
        yaml.dump(config, f)

    # Reload config
    import src.helpers
    src.helpers._cached_config = None

    from web_api.main import app
    return TestClient(app)


def _register(client, username="user1", password="pass123"):
    res = client.post("/api/auth/register", json={"username": username, "email": f"{username}@test.com", "password": password})
    return res.json()


def _login(client, username="user1", password="pass123"):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    return res.json()


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_and_login(client):
    result = _register(client)
    assert result["success"] is True
    assert "token" in result["data"]
    assert result["data"]["user"]["username"] == "user1"


def test_duplicate_register_fails(client):
    _register(client, "dup_user")
    res = client.post("/api/auth/register", json={"username": "dup_user", "email": "dup2@test.com", "password": "pass123"})
    assert res.status_code == 409


def test_wrong_password_fails(client):
    _register(client, "wp_user", "correct")
    res = client.post("/api/auth/login", json={"username": "wp_user", "password": "wrong"})
    assert res.status_code == 401


def test_no_token_returns_401(client):
    res = client.get("/api/jobs")
    assert res.status_code == 401


def test_get_me(client):
    _register(client, "me_user")
    token = _login(client, "me_user")["data"]["token"]
    res = client.get("/api/auth/me", headers=_auth_header(token))
    assert res.status_code == 200
    assert res.json()["data"]["username"] == "me_user"


def test_change_password(client):
    _register(client, "cp_user", "old_pass")
    token = _login(client, "cp_user", "old_pass")["data"]["token"]
    res = client.put("/api/auth/password", json={"old_password": "old_pass", "new_password": "new_pass"}, headers=_auth_header(token))
    assert res.status_code == 200
    # Old password should fail now
    res = client.post("/api/auth/login", json={"username": "cp_user", "password": "old_pass"})
    assert res.status_code == 401
    # New password should work
    res = client.post("/api/auth/login", json={"username": "cp_user", "password": "new_pass"})
    assert res.status_code == 200


def test_user_a_jobs_invisible_to_user_b(client):
    """用户 A 创建的岗位用户 B 看不到"""
    _register(client, "alice", "pass123")
    _register(client, "bob", "pass123")
    token_a = _login(client, "alice")["data"]["token"]
    token_b = _login(client, "bob")["data"]["token"]
    headers_a = _auth_header(token_a)
    headers_b = _auth_header(token_b)

    # Alice creates a job
    res = client.post("/api/imports/manual", json={
        "title": "Python Dev", "company": "Alice Corp", "description": "Build things"
    }, headers=headers_a)
    assert res.status_code == 200

    # Bob's job list should be empty
    res = client.get("/api/jobs", headers=headers_b)
    assert res.status_code == 200
    assert len(res.json()["data"]) == 0

    # Alice should see her job
    res = client.get("/api/jobs", headers=headers_a)
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1


def test_kanban_board_isolated(client):
    """看板只显示当前用户的岗位"""
    _register(client, "user_a", "pass123")
    _register(client, "user_b", "pass123")
    token_a = _login(client, "user_a")["data"]["token"]
    token_b = _login(client, "user_b")["data"]["token"]

    # User A creates a job
    client.post("/api/imports/manual", json={
        "title": "Job A", "company": "Corp A", "description": "Desc"
    }, headers=_auth_header(token_a))

    # User A's board has 1 job
    res = client.get("/api/kanban/board", headers=_auth_header(token_a))
    board = res.json()["data"]
    total_a = sum(len(v) for v in board.values())
    assert total_a == 1

    # User B's board is empty
    res = client.get("/api/kanban/board", headers=_auth_header(token_b))
    board = res.json()["data"]
    total_b = sum(len(v) for v in board.values())
    assert total_b == 0
