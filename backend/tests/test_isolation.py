"""The most important tests: students never reach the faculty handbook and vice versa."""
import json

import jwt
import pytest

from app import db
from app.config import settings
from tests.conftest import auth

STUDENT_QS = ["What is the minimum attendance requirement?", "What is the punishment for ragging?", "What are the hostel rules?",
              "Tell me about casual leave", "What is the faculty workload for a professor?", "What is the relocation allowance?"]
FACULTY_QS = ["How many casual leaves can a faculty member take?", "What is the maternity leave policy?", "What are the examination duties?",
              "What is the minimum attendance requirement for students?", "What is the punishment for ragging?", "What is the CGPA to percentage formula?"]


def _texts(role):
    return [c["text"][:90] for c in json.load(open(settings.index_dir / role / "chunks.json", encoding="utf-8"))]


def test_cross_role_endpoints_forbidden(client, student_token, faculty_token, fake_llm):
    q = {"question": "What is the leave policy?"}
    assert client.post("/api/faculty/chat", json=q, headers=auth(student_token)).status_code == 403
    assert client.post("/api/student/chat", json=q, headers=auth(faculty_token)).status_code == 403
    assert client.post("/api/student/chat", json=q).status_code == 401
    assert fake_llm.calls == []  # the LLM was never even called


@pytest.mark.parametrize("q", STUDENT_QS)
def test_student_prompt_contains_only_student_text(client, student_token, fake_llm, q):
    r = client.post("/api/student/chat", json={"question": q}, headers=auth(student_token))
    assert r.status_code == 200
    for s in r.json()["sources"]:
        assert s["handbook"] == "Student Handbook"
    if fake_llm.calls:
        prompt = fake_llm.last_prompt
        assert "Student Handbook" in prompt and "Faculty Handbook" not in prompt
        assert not any(t in prompt for t in _texts("faculty")), "faculty text leaked into a student prompt"


@pytest.mark.parametrize("q", FACULTY_QS)
def test_faculty_prompt_contains_only_faculty_text(client, faculty_token, fake_llm, q):
    r = client.post("/api/faculty/chat", json={"question": q}, headers=auth(faculty_token))
    assert r.status_code == 200
    for s in r.json()["sources"]:
        assert s["handbook"] == "Faculty Handbook"
    if fake_llm.calls:
        prompt = fake_llm.last_prompt
        assert "Faculty Handbook" in prompt and "Student Handbook" not in prompt
        assert not any(t in prompt for t in _texts("student")), "student text leaked into a faculty prompt"


def test_role_in_request_body_is_ignored(client, student_token, fake_llm):
    body = {"question": "How many casual leaves can a faculty member take?", "role": "faculty", "handbook": "faculty", "kb": "faculty"}
    r = client.post("/api/student/chat", json=body, headers=auth(student_token))
    assert r.status_code == 200
    assert all(s["handbook"] == "Student Handbook" for s in r.json()["sources"])
    if fake_llm.calls:
        assert "Faculty Handbook" not in fake_llm.last_prompt


def test_forged_and_mismatched_tokens(client):
    student = db.get_user_by_username("student1")
    # 1) signed with the wrong secret, claims faculty
    bad = jwt.encode({"sub": str(student["id"]), "role": "faculty", "jti": "f1", "exp": 9999999999}, "attacker-secret-" + "y" * 40, algorithm="HS256")
    assert client.post("/api/faculty/chat", json={"question": "x"}, headers=auth(bad)).status_code == 401
    # 2) correctly signed but the role claim disagrees with the database -> rejected
    liar = jwt.encode({"sub": str(student["id"]), "role": "faculty", "jti": "f2", "exp": 9999999999}, settings.jwt_secret, algorithm="HS256")
    assert client.post("/api/faculty/chat", json={"question": "x"}, headers=auth(liar)).status_code == 401


def test_chat_history_is_private(client, student_token, faculty_token, fake_llm):
    client.delete("/api/history", headers=auth(student_token))  # earlier tests also write history
    client.delete("/api/history", headers=auth(faculty_token))
    client.post("/api/student/chat", json={"question": "What is the minimum attendance requirement?"}, headers=auth(student_token))
    client.post("/api/faculty/chat", json={"question": "What is the dress code for staff?"}, headers=auth(faculty_token))
    s = client.get("/api/history", headers=auth(student_token)).json()["messages"]
    f = client.get("/api/history", headers=auth(faculty_token)).json()["messages"]
    s_txt, f_txt = json.dumps(s), json.dumps(f)
    assert "attendance" in s_txt and "dress code for staff" not in s_txt
    assert "dress code for staff" in f_txt and "minimum attendance requirement" not in f_txt
    client.delete("/api/history", headers=auth(student_token))
    assert client.get("/api/history", headers=auth(student_token)).json()["messages"] == []
    assert client.get("/api/history", headers=auth(faculty_token)).json()["messages"] != []


def test_knowledge_base_refuses_foreign_chunks(tmp_path):
    """A tampered index (faculty chunks inside the student folder) must refuse to load."""
    from app.rag.store import KnowledgeBase
    real = settings.index_dir
    (tmp_path / "student").mkdir()
    chunks = json.load(open(real / "faculty" / "chunks.json", encoding="utf-8"))
    (tmp_path / "student" / "chunks.json").write_text(json.dumps(chunks))
    object.__setattr__(settings, "index_dir", tmp_path)
    try:
        with pytest.raises(RuntimeError, match="foreign chunks"):
            KnowledgeBase("student")
    finally:
        object.__setattr__(settings, "index_dir", real)
