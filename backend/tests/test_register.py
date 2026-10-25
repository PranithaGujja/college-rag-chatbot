from app.config import settings
from tests.conftest import auth


def _body(**kw):
    b = {"name": "Asha Rao", "username": "asha.rao", "password": "GoodPass123", "portal": "student", "access_code": "STU-CODE-1"}
    b.update(kw)
    return b


def test_student_can_register_and_then_login(client):
    r = client.post("/api/auth/register", json=_body(username="new.student1"))
    assert r.status_code == 201 and r.json()["user"]["role"] == "student"
    assert client.get("/api/auth/me", headers=auth(r.json()["access_token"])).json()["name"] == "Asha Rao"
    assert client.post("/api/auth/login", json={"username": "NEW.student1", "password": "GoodPass123", "portal": "student"}).status_code == 200


def test_faculty_registration_needs_faculty_code(client):
    ok = client.post("/api/auth/register", json=_body(username="new.fac1", portal="faculty", access_code="FAC-CODE-1"))
    assert ok.status_code == 201 and ok.json()["user"]["role"] == "faculty"
    # the STUDENT code must never create a faculty account
    bad = client.post("/api/auth/register", json=_body(username="sneaky", portal="faculty", access_code="STU-CODE-1"))
    assert bad.status_code == 403
    from app import db
    assert db.get_user_by_username("sneaky") is None


def test_wrong_code_and_duplicate_and_weak_password(client):
    assert client.post("/api/auth/register", json=_body(username="usr1", access_code="nope")).status_code == 403
    assert client.post("/api/auth/register", json=_body(username="student1")).status_code == 409  # demo user already exists
    assert client.post("/api/auth/register", json=_body(username="usr2", password="short")).status_code == 422
    assert client.post("/api/auth/register", json=_body(username="bad id!")).status_code == 422
    assert client.post("/api/auth/register", json=_body(username="usr3", password="é" * 40)).status_code == 400  # >72 bytes


def test_new_student_cannot_reach_faculty_handbook(client, fake_llm):
    tok = client.post("/api/auth/register", json=_body(username="new.student2")).json()["access_token"]
    assert client.post("/api/faculty/chat", json={"question": "leave policy"}, headers=auth(tok)).status_code == 403
    assert client.post("/api/student/chat", json={"question": "What is the minimum attendance requirement?"}, headers=auth(tok)).status_code == 200


def test_signup_closed_when_no_code_configured(client):
    old = settings.faculty_signup_code
    object.__setattr__(settings, "faculty_signup_code", "")
    try:
        r = client.post("/api/auth/register", json=_body(username="usr4", portal="faculty", access_code="anything"))
        assert r.status_code == 403 and "not open" in r.json()["detail"]
    finally:
        object.__setattr__(settings, "faculty_signup_code", old)


def test_access_code_guessing_is_throttled(client):
    for _ in range(5):
        assert client.post("/api/auth/register", json=_body(username="guess1", access_code="guess")).status_code == 403
    assert client.post("/api/auth/register", json=_body(username="guess1", access_code="STU-CODE-1")).status_code == 429
