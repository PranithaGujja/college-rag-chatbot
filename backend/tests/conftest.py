import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.update(
    JWT_SECRET="test-secret-" + "x" * 48,
    DB_PATH=os.path.join(_tmp, "test.db"),
    DEMO_STUDENT_ID="student1", DEMO_STUDENT_PASSWORD="StudentPass!123",
    DEMO_FACULTY_ID="faculty1", DEMO_FACULTY_PASSWORD="FacultyPass!123",
    STUDENT_SIGNUP_CODE="STU-CODE-1", FACULTY_SIGNUP_CODE="FAC-CODE-1", LLM_API_KEY="test-key", RETRIEVAL_MODE="bm25", CHAT_RATE_PER_MINUTE="1000", ENV="development",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import security  # noqa: E402
from app.main import app  # noqa: E402
from app.rag import llm  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_limiters():
    security.login_failures.events.clear()
    security.chat_limiter.events.clear()
    security.register_failures.events.clear()


def login(client, user, password):
    r = client.post("/api/auth/login", json={"username": user, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture()
def student_token(client):
    return login(client, "student1", "StudentPass!123")


@pytest.fixture()
def faculty_token(client):
    return login(client, "faculty1", "FacultyPass!123")


def auth(token):
    return {"Authorization": f"Bearer {token}"}


class FakeLLM:
    """Records every prompt and returns a scripted reply."""
    def __init__(self):
        self.calls, self.reply = [], "Students need at least 75% attendance. [1]"

    def __call__(self, messages, max_tokens=None):
        self.calls.append(messages)
        return self.reply

    @property
    def last_prompt(self):
        return "\n".join(m["content"] for m in self.calls[-1])


@pytest.fixture()
def fake_llm(monkeypatch):
    f = FakeLLM()
    monkeypatch.setattr(llm, "complete", f)
    return f
