import csv
import sqlite3

import pytest

from app import db
from scripts import import_users as imp
from tests.conftest import auth


class Roster(str):
    """Path to a CSV whose IDs are unique per test (the test database is shared)."""
    ids: tuple


@pytest.fixture()
def roster(tmp_path):
    import uuid
    tag = uuid.uuid4().hex[:6]
    a, b, f = f"2303A{tag}1", f"2303a{tag}2", f"EMP{tag}"
    p = tmp_path / "users.csv"
    p.write_text(f"id,name,role\n{a},Ravi Kumar,student\n{b},,student\n{f},Dr. Rao,faculty\nbad id,,student\n{a}Z,,principal\n", encoding="utf-8")
    r = Roster(p)
    r.ids = (a, b, f)
    return r


def test_import_creates_accounts_with_unique_temp_passwords(roster):
    created, skipped, errors = imp.import_users(roster)
    a, b, f = roster.ids
    assert [c["id"] for c in created] == [a, b, f]
    assert len({c["temporary_password"] for c in created}) == 3 and all(len(c["temporary_password"]) == 10 for c in created)
    assert {c["id"]: c["role"] for c in created}[f] == "faculty"
    assert len(errors) == 2 and skipped == []
    u = db.get_user_by_username(a)
    assert u["must_change_password"] == 1 and u["name"] == "Ravi Kumar"
    assert db.get_user_by_username(b)["name"] == b  # name defaults to the ID
    assert "temporary" not in u["password_hash"] and u["password_hash"].startswith("$2")


def test_import_twice_skips_existing_and_keeps_passwords(roster, client):
    first, _, _ = imp.import_users(roster)
    second, skipped, _ = imp.import_users(roster)
    assert second == [] and len(skipped) == 3
    c = first[0]
    assert client.post("/api/auth/login", json={"username": c["id"].lower(), "password": c["temporary_password"]}).status_code == 200  # ID is case-insensitive


def test_must_change_flag_then_change_password_flow(client, roster):
    c = imp.import_users(roster)[0][0]
    login = client.post("/api/auth/login", json={"username": c["id"], "password": c["temporary_password"], "portal": "student"}).json()
    assert login["user"]["must_change_password"] is True
    old_tok = login["access_token"]
    other_device = client.post("/api/auth/login", json={"username": c["id"], "password": c["temporary_password"]}).json()["access_token"]

    ch = lambda cur, new, tok=old_tok: client.post("/api/auth/change-password", json={"current_password": cur, "new_password": new}, headers=auth(tok))
    assert ch("wrong-password", "NewPass12345").status_code == 400
    assert ch(c["temporary_password"], "short").status_code == 422
    assert ch(c["temporary_password"], c["temporary_password"]).status_code == 400
    assert ch(c["temporary_password"], c["id"].lower() + "x" * 0).status_code in (400, 422)  # ID itself is rejected (or too short)
    r = ch(c["temporary_password"], "MyNewPass2026")
    assert r.status_code == 200 and r.json()["user"]["must_change_password"] is False
    new_tok = r.json()["access_token"]

    assert client.get("/api/auth/me", headers=auth(new_tok)).status_code == 200
    assert client.get("/api/auth/me", headers=auth(old_tok)).status_code == 401        # old session ended
    assert client.get("/api/auth/me", headers=auth(other_device)).status_code == 401   # other devices signed out
    assert client.post("/api/auth/login", json={"username": c["id"], "password": c["temporary_password"]}).status_code == 401
    assert client.post("/api/auth/login", json={"username": c["id"], "password": "MyNewPass2026"}).status_code == 200


def test_change_password_requires_login_and_throttles_guessing(client, student_token):
    assert client.post("/api/auth/change-password", json={"current_password": "a", "new_password": "NewPass12345"}).status_code == 401
    for _ in range(5):
        assert client.post("/api/auth/change-password", json={"current_password": "nope", "new_password": "NewPass12345"}, headers=auth(student_token)).status_code == 400
    assert client.post("/api/auth/change-password", json={"current_password": "StudentPass!123", "new_password": "NewPass12345"}, headers=auth(student_token)).status_code == 429


def test_reset_password_script_logic(client, roster):
    c = imp.import_users(roster)[0][0]
    tok = client.post("/api/auth/login", json={"username": c["id"], "password": c["temporary_password"]}).json()["access_token"]
    u = db.get_user_by_username(c["id"])
    from app import security
    db.set_password(u["id"], security.hash_password("ResetPass999"), must_change=True)
    assert client.get("/api/auth/me", headers=auth(tok)).status_code == 401
    assert client.post("/api/auth/login", json={"username": c["id"], "password": "ResetPass999"}).json()["user"]["must_change_password"] is True


def test_old_database_is_upgraded(tmp_path):
    """A database made by the previous version (no new columns) must keep working."""
    from app.config import settings
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT NOT NULL, role TEXT NOT NULL, password_hash TEXT NOT NULL);"
                      "INSERT INTO users (username,name,role,password_hash) VALUES ('old','Old User','student','$2b$x');")
    con.commit(); con.close()
    prev = settings.db_path
    object.__setattr__(settings, "db_path", str(path))
    try:
        db.init_db()
        u = db.get_user_by_username("old")
        assert u["must_change_password"] == 0 and u["pw_version"] == 0
    finally:
        object.__setattr__(settings, "db_path", prev)


def test_health_reports_signup_state(client):
    s = client.get("/api/health").json()["signup"]
    assert s == {"student": True, "faculty": True}  # codes are set in the test environment


def test_prompt_demands_short_answers(fake_llm):
    from app.rag import pipeline
    pipeline.answer("student", "What is the minimum attendance requirement?")
    sp = fake_llm.calls[-1][0]["content"]
    assert "SHORT" in sp and "at most 3 short bullet points" in sp and "**bold**" in sp and "ONLY when the question is a yes/no" in sp


def test_faculty_ids_flow_end_to_end(client, tmp_path):
    """Numeric faculty IDs (e.g. 3421): import -> faculty login -> forced change -> faculty-only access."""
    import uuid
    base = str(int(uuid.uuid4().int % 9000) + 1000)  # 4-digit ID, unique per run
    p = tmp_path / "fac.csv"
    p.write_text(f"id,name,role\n{base},,faculty\n", encoding="utf-8")
    c = imp.import_users(str(p))[0][0]
    # a faculty ID cannot sign in through the student portal
    assert client.post("/api/auth/login", json={"username": base, "password": c["temporary_password"], "portal": "student"}).status_code == 403
    r = client.post("/api/auth/login", json={"username": base, "password": c["temporary_password"], "portal": "faculty"}).json()
    assert r["user"]["role"] == "faculty" and r["user"]["must_change_password"] is True
    new = client.post("/api/auth/change-password", json={"current_password": c["temporary_password"], "new_password": "FacultyNew2026"}, headers=auth(r["access_token"])).json()
    tok = new["access_token"]
    assert client.post("/api/student/chat", json={"question": "x"}, headers=auth(tok)).status_code == 403
    assert client.post("/api/faculty/chat", json={"question": "hello"}, headers=auth(tok)).status_code in (200, 503)
