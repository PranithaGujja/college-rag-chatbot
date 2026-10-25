import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.config import settings
from app.rag import llm, pipeline
from tests.conftest import auth


def _set(**kw):
    old = {k: getattr(settings, k) for k in kw}
    for k, v in kw.items():
        object.__setattr__(settings, k, v)
    return old


# ------------------------------------------------------------------ pipeline behaviour
def test_answer_with_citation_and_correct_page(fake_llm):
    fake_llm.reply = "You need at least 75% attendance in each course. [1][2][3][4][5]"
    res = pipeline.answer("student", "What is the minimum attendance requirement?")
    assert res["found"] and res["sources"]
    assert all(s["handbook"] == "Student Handbook" for s in res["sources"])
    # the general policy (section 3.7) starts on printed page 25 = PDF page 29 (its last line spills onto p.26)
    top = [s for s in res["sources"] if s["section"] and s["section"].startswith("3.7.")]
    assert top and top[0]["page_start"] == 29 and top[0]["page"].startswith("Pages 25-26 (PDF pages 29-30)")
    assert "75%" in fake_llm.last_prompt  # the 75% rule really was in the context given to the LLM


def test_only_cited_sources_are_shown(fake_llm):
    fake_llm.reply = "Answer. [2]"
    res = pipeline.answer("faculty", "What is the dress code for staff?")
    assert [s["ref"] for s in res["sources"]] == [2]


def test_model_says_not_found(fake_llm):
    fake_llm.reply = "NOT_FOUND"
    res = pipeline.answer("student", "What is the fee for the swimming pool?")
    assert res["found"] is False and res["sources"] == []
    assert res["answer"].startswith("I could not find this information in the Student Handbook")


def test_offtopic_never_reaches_llm(fake_llm):
    for q in ("What is the capital of France?", "Who won the cricket world cup?", "What is the best pizza topping?", "Tell me a joke"):
        res = pipeline.answer("student", q)
        assert res["found"] is False and "Student Handbook" in res["answer"]
    assert fake_llm.calls == []


def test_smalltalk_is_free(fake_llm):
    res = pipeline.answer("faculty", "hello!")
    assert "Faculty Handbook" in res["answer"] and fake_llm.calls == []


def test_followup_uses_previous_question_for_retrieval(fake_llm):
    res = pipeline.answer("student", "what about PG?", ["What is the minimum attendance requirement?"])
    assert fake_llm.calls and "attendance" in fake_llm.last_prompt.lower()


def test_prompt_contains_anti_hallucination_rules(fake_llm):
    pipeline.answer("student", "What is the minimum attendance requirement?")
    sys_prompt = fake_llm.calls[-1][0]["content"]
    for must in ("ONLY", "NOT_FOUND", "Never guess", "different groups"):
        assert must in sys_prompt


# ------------------------------------------------------------------ retrieval quality (keyword mode, real handbooks)
CASES = [
    ("student", "What is the minimum attendance requirement?", "3.7."),
    ("student", "What does the R grade mean?", "3.8."),
    ("student", "What is the punishment for ragging?", "4.4."),
    ("student", "Can I change my branch after first year?", "3.11."),
    ("student", "What are the PhD thesis submission requirements?", "8.10."),
    ("faculty", "What is the maternity leave policy?", "ANNEXURE - I"),
    ("faculty", "What is the teaching workload of a professor?", "3.10"),
    ("faculty", "What is the whistleblower policy?", "17."),
    ("faculty", "Is biometric attendance mandatory?", "8.0"),
]


@pytest.mark.parametrize("role,q,prefix", CASES)
def test_retrieval_finds_right_section(role, q, prefix):
    from app.rag.store import get_kb
    r = get_kb(role).search(q)
    assert any(h.chunk["section"].startswith(prefix) for h in r.hits), [h.chunk["section"][:40] for h in r.hits]


# ------------------------------------------------------------------ LLM client + error handling
class _Mock(BaseHTTPRequestHandler):
    behaviour = {}  # model -> (status, body)

    last_body = None

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).last_body = body
        status, payload = self.behaviour.get(body["model"], (500, {"error": "boom"}))
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, *a):
        pass


@pytest.fixture()
def mock_llm_server():
    srv = HTTPServer(("127.0.0.1", 0), _Mock)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    old = _set(llm_base_url=f"http://127.0.0.1:{srv.server_port}/v1", llm_model="primary", llm_fallback_model="fallback", llm_timeout=5)
    yield _Mock
    srv.shutdown()
    _set(**old)


OK = lambda t: (200, {"choices": [{"message": {"content": t}}]})


def test_llm_falls_back_when_primary_rate_limited(mock_llm_server):
    mock_llm_server.behaviour = {"primary": (429, {"error": "rate limit"}), "fallback": OK("from fallback")}
    assert llm.complete([{"role": "user", "content": "hi"}]) == "from fallback"


def test_reasoning_effort_is_sent_when_configured(mock_llm_server):
    mock_llm_server.behaviour = {"primary": OK("hi")}
    old = _set(llm_reasoning_effort="low")
    try:
        llm.complete([{"role": "user", "content": "x"}])
    finally:
        _set(**old)
    assert mock_llm_server.last_body["reasoning_effort"] == "low" and mock_llm_server.last_body["max_tokens"] == settings.llm_max_tokens


def test_empty_model_reply_is_an_error_not_a_false_not_found(mock_llm_server):
    mock_llm_server.behaviour = {"primary": OK(""), "fallback": OK("   ")}
    with pytest.raises(llm.LLMUnavailable, match="empty"):
        llm.complete([{"role": "user", "content": "x"}])


def test_llm_all_models_fail(mock_llm_server):
    mock_llm_server.behaviour = {"primary": (500, {}), "fallback": (404, {})}
    with pytest.raises(llm.LLMUnavailable):
        llm.complete([{"role": "user", "content": "hi"}])


def test_api_maps_llm_failure_to_friendly_503(client, student_token, mock_llm_server):
    mock_llm_server.behaviour = {"primary": (500, {"error": "SECRET INTERNAL TRACE"}), "fallback": (500, {})}
    r = client.post("/api/student/chat", json={"question": "What is the minimum attendance requirement?"}, headers=auth(student_token))
    assert r.status_code == 503
    assert "temporarily unavailable" in r.json()["detail"] and "SECRET" not in r.text


def test_api_missing_api_key(client, student_token):
    old = _set(llm_api_key="")
    try:
        r = client.post("/api/student/chat", json={"question": "What is the minimum attendance requirement?"}, headers=auth(student_token))
        assert r.status_code == 503 and "missing LLM API key" in r.json()["detail"]
    finally:
        _set(**old)


def test_failed_question_is_not_saved_to_history(client, student_token):
    client.delete("/api/history", headers=auth(student_token))
    old = _set(llm_api_key="")
    try:
        client.post("/api/student/chat", json={"question": "What is the minimum attendance requirement?"}, headers=auth(student_token))
    finally:
        _set(**old)
    assert client.get("/api/history", headers=auth(student_token)).json()["messages"] == []


# ------------------------------------------------------------------ hybrid (FAISS) plumbing with a stub embedder
def _stub_embed(text, dim=256):
    import hashlib
    import numpy as np
    from app.rag.bm25 import tokenize
    v = np.zeros(dim, dtype="float32")
    for t in tokenize(text):
        v[int(hashlib.md5(t.encode()).hexdigest(), 16) % dim] += 1
    n = np.linalg.norm(v)
    return (v / n if n else v).tolist()


def test_hybrid_index_build_and_search(tmp_path, monkeypatch):
    from app.rag import embeddings, ingest, store
    monkeypatch.setattr(embeddings, "embed_passages", lambda texts: [_stub_embed(t) for t in texts])
    monkeypatch.setattr(embeddings, "embed_query", lambda t: _stub_embed(t))
    old = _set(index_dir=tmp_path, retrieval_mode="hybrid")
    try:
        ingest.ingest_role("faculty", embed=True)
        assert (tmp_path / "faculty" / "vectors.faiss").exists()
        kb = store.KnowledgeBase("faculty")
        assert kb.mode == "hybrid"
        r = kb.search("What is the maternity leave policy?")
        assert r.best_dense is not None and r.best_dense > 0.2
        assert any(h.dense is not None for h in r.hits) and all(h.chunk["role"] == "faculty" for h in r.hits)
        # a vector index built with a different model must not be trusted
        object.__setattr__(settings, "embed_model", "some/other-model")
        assert store.KnowledgeBase("faculty").mode == "bm25"
    finally:
        _set(**old)
        object.__setattr__(settings, "embed_model", "BAAI/bge-small-en-v1.5")
