import time

import jwt

from app import security
from app.config import settings
from tests.conftest import auth, login


def test_student_and_faculty_login(client):
    r = client.post("/api/auth/login", json={"username": "student1", "password": "StudentPass!123"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "student"
    r = client.post("/api/auth/login", json={"username": "faculty1", "password": "FacultyPass!123"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "faculty"


def test_invalid_credentials(client):
    assert client.post("/api/auth/login", json={"username": "student1", "password": "wrong"}).status_code == 401
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401 and r.json()["detail"] == "Incorrect ID or password."  # same message: no user enumeration


def test_portal_mismatch_blocks_token_issue(client):
    r = client.post("/api/auth/login", json={"username": "faculty1", "password": "FacultyPass!123", "portal": "student"})
    assert r.status_code == 403 and "access_token" not in r.text


def test_passwords_are_hashed_in_db():
    from app import db
    u = db.get_user_by_username("student1")
    assert u["password_hash"].startswith("$2") and "StudentPass" not in u["password_hash"]


def test_logout_revokes_token(client, student_token):
    assert client.get("/api/auth/me", headers=auth(student_token)).status_code == 200
    assert client.post("/api/auth/logout", headers=auth(student_token)).status_code == 200
    assert client.get("/api/auth/me", headers=auth(student_token)).status_code == 401
    assert client.get("/api/history", headers=auth(student_token)).status_code == 401


def test_no_token_expired_tampered(client, student_token):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=auth("garbage")).status_code == 401
    expired = jwt.encode({"sub": "1", "role": "student", "jti": "e1", "exp": int(time.time()) - 10}, settings.jwt_secret, algorithm="HS256")
    r = client.get("/api/auth/me", headers=auth(expired))
    assert r.status_code == 401 and "expired" in r.json()["detail"].lower()
    tampered = student_token[:-3] + ("AAA" if not student_token.endswith("AAA") else "BBB")
    assert client.get("/api/auth/me", headers=auth(tampered)).status_code == 401


def test_alg_none_token_rejected(client):
    import base64, json
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    tok = f"{b({'alg': 'none', 'typ': 'JWT'})}.{b({'sub': '1', 'role': 'faculty', 'jti': 'x', 'exp': int(time.time()) + 999})}."
    assert client.get("/api/auth/me", headers=auth(tok)).status_code == 401


def test_login_lockout_after_repeated_failures(client):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "student1", "password": "bad"}).status_code == 401
    r = client.post("/api/auth/login", json={"username": "student1", "password": "StudentPass!123"})
    assert r.status_code == 429  # even the right password is refused while locked


def test_empty_and_overlong_questions(client, student_token, fake_llm):
    h = auth(student_token)
    assert client.post("/api/student/chat", json={"question": "   "}, headers=h).status_code == 400
    assert client.post("/api/student/chat", json={"question": "a" * 600}, headers=h).status_code == 400
    assert fake_llm.calls == []


def test_chat_rate_limit(client, student_token, fake_llm, monkeypatch):
    monkeypatch.setattr(security.chat_limiter, "limit", 2)
    h = auth(student_token)
    codes = [client.post("/api/student/chat", json={"question": "What is the minimum attendance?"}, headers=h).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
