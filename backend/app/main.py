import hmac
import logging
import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import db, security
from app.config import settings
from app.rag import llm, pipeline
from app.rag.ingest import HANDBOOKS
from app.rag.store import KnowledgeBaseMissing, get_kb

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("api")


def _seed_one(username: str, name: str, role: str, pw: str):
    """Create the account, or reset it to the configured password if it differs."""
    existing = db.get_user_by_username(username)
    if existing is None or existing["role"] != role or not security.verify_password(pw, existing["password_hash"]):
        db.upsert_user(username, name, role, security.hash_password(pw))
        log.info("Seeded %s account '%s'", role, username)


def _seed_demo_users():
    for username, name, role, pw in (
        (settings.demo_student_id, settings.demo_student_name, "student", settings.demo_student_password),
        (settings.demo_faculty_id, settings.demo_faculty_name, "faculty", settings.demo_faculty_password),
    ):
        if not pw:
            log.warning("DEMO_%s_PASSWORD is not set: the demo %s account was not created.", role.upper(), role)
            continue
        _seed_one(username, name, role, pw)


def _seed_extra_users() -> int:
    """EXTRA_USERS='3421|Dr. Rao|faculty|Pass-1234;2303A52481||student|Other-5678'. Bad entries are skipped, never fatal."""
    import re
    count = 0
    for entry in filter(None, (e.strip() for e in settings.extra_users.split(";"))):
        parts = [p.strip() for p in entry.split("|")]
        if len(parts) != 4:
            log.warning("EXTRA_USERS: skipped an entry that does not have 4 parts (id|name|role|password)")
            continue
        uid, name, role, pw = parts
        if not re.fullmatch(r"[A-Za-z0-9._@-]{3,40}", uid) or role not in ("student", "faculty") or not (8 <= len(pw.encode()) <= 72):
            log.warning("EXTRA_USERS: skipped '%s' (invalid ID, role, or password length 8-72)", uid[:40])
            continue
        _seed_one(uid, name or uid, role, pw)
        count += 1
    if count:
        log.info("EXTRA_USERS: %d account(s) ready", count)
    return count


@asynccontextmanager
async def lifespan(app: FastAPI):
    if len(settings.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET is missing or too short (need 32+ characters). Run: python scripts/init_env.py")
    db.init_db()
    _seed_demo_users()
    _seed_extra_users()
    for role in HANDBOOKS:  # load indexes at start-up so the first question is fast
        try:
            kb = get_kb(role)
            log.info("Loaded %s: %d chunks, retrieval=%s", kb.label, len(kb.chunks), kb.mode)
        except KnowledgeBaseMissing as e:
            log.error("%s", e)
    yield


prod = os.getenv("ENV", "development") == "production"
app = FastAPI(title="College Handbook Portal API", lifespan=lifespan, docs_url=None if prod else "/docs", redoc_url=None, openapi_url=None if prod else "/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=False,  # we use Authorization headers, not cookies
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def _validation(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Please check your input and try again."})


@app.exception_handler(Exception)
async def _unexpected(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)  # details stay in server logs only
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side. Please try again."})


# ----------------------------------------------------------------- schemas
class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    portal: str | None = Field(default=None, pattern="^(student|faculty)$")  # UX hint only, never used for authorization


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9._@-]+$")
    password: str = Field(min_length=8, max_length=72)
    portal: str = Field(pattern="^(student|faculty)$")
    access_code: str = Field(min_length=1, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=72)


class ChatIn(BaseModel):
    question: str = Field(max_length=2000)


# ----------------------------------------------------------------- auth
def _public(user) -> dict:
    return {"username": user["username"], "name": user["name"], "role": user["role"], "must_change_password": bool(user["must_change_password"])}


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request):
    username = body.username.strip()
    key = f"{request.client.host if request.client else '?'}:{username.lower()}"
    if security.login_failures.blocked(key):
        raise HTTPException(429, f"Too many failed attempts. Try again in {security.login_failures.retry_after(key) // 60 + 1} minute(s).")
    user = db.get_user_by_username(username)
    if not security.verify_password(body.password, user["password_hash"] if user else None):
        security.login_failures.add(key)
        raise HTTPException(401, "Incorrect ID or password.")
    if body.portal and body.portal != user["role"]:
        raise HTTPException(403, f"This is a {user['role']} account. Please use the {user['role'].capitalize()} Login.")
    security.login_failures.reset(key)
    token, exp = security.create_token(user)
    return {"access_token": token, "token_type": "bearer", "expires_at": int(exp), "user": _public(user)}


@app.post("/api/auth/register", status_code=201)
def register(body: RegisterIn, request: Request):
    """Self sign-up. The role comes from which access code was supplied, so only people who were given
    the faculty code can ever create a faculty account."""
    ip = request.client.host if request.client else "?"
    if security.register_failures.blocked(ip):
        raise HTTPException(429, f"Too many wrong access codes. Try again in {security.register_failures.retry_after(ip) // 60 + 1} minute(s).")
    expected = {"student": settings.student_signup_code, "faculty": settings.faculty_signup_code}[body.portal]
    if not expected:
        raise HTTPException(403, f"Sign-up for {body.portal} accounts is not open yet. Please contact the administrator.")
    if not hmac.compare_digest(body.access_code.strip().encode(), expected.encode()):
        security.register_failures.add(ip)
        raise HTTPException(403, f"That access code is not correct. Ask your college office for the {body.portal} access code.")
    if len(body.password.encode("utf-8")) > 72:
        raise HTTPException(400, "Password is too long (maximum 72 characters).")
    name, username = " ".join(body.name.split()), body.username.strip()
    try:
        user = db.create_user(username, name, body.portal, security.hash_password(body.password))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "This ID is already registered. Please log in instead.")
    log.info("New %s account registered: %s", body.portal, username)
    token, exp = security.create_token(user)
    return {"access_token": token, "token_type": "bearer", "expires_at": int(exp), "user": _public(user)}


@app.post("/api/auth/logout")
def logout(user=Depends(security.get_current_user)):
    db.revoke_token(user["_jti"], user["_exp"])
    return {"ok": True}


@app.post("/api/auth/change-password")
def change_password(body: ChangePasswordIn, user=Depends(security.get_current_user)):
    key = f"chg:{user['id']}"
    if security.login_failures.blocked(key):
        raise HTTPException(429, f"Too many wrong attempts. Try again in {security.login_failures.retry_after(key) // 60 + 1} minute(s).")
    if not security.verify_password(body.current_password, user["password_hash"]):
        security.login_failures.add(key)
        raise HTTPException(400, "Your current password is not correct.")
    if len(body.new_password.encode("utf-8")) > 72:
        raise HTTPException(400, "New password is too long (maximum 72 characters).")
    if body.new_password == body.current_password:
        raise HTTPException(400, "Your new password must be different from the current one.")
    if body.new_password.strip().lower() == user["username"].lower():
        raise HTTPException(400, "Your password cannot be the same as your ID.")
    security.login_failures.reset(key)
    updated = db.set_password(user["id"], security.hash_password(body.new_password), must_change=False)
    token, exp = security.create_token(updated)  # fresh session; all older tokens stop working
    return {"access_token": token, "token_type": "bearer", "expires_at": int(exp), "user": _public(updated)}


@app.get("/api/auth/me")
def me(user=Depends(security.get_current_user)):
    return _public(user) | {"handbook": HANDBOOKS[user["role"]]["label"]}


# ----------------------------------------------------------------- chat
def _chat(user: dict, body: ChatIn) -> dict:
    question = " ".join(body.question.split())
    if not question:
        raise HTTPException(400, "Please type a question.")
    if len(question) > settings.max_question_chars:
        raise HTTPException(400, f"Your question is too long (maximum {settings.max_question_chars} characters).")
    if security.chat_limiter.blocked(user["id"]):
        raise HTTPException(429, f"You are asking too fast. Please wait {security.chat_limiter.retry_after(user['id'])} seconds.")
    security.chat_limiter.add(user["id"])
    try:
        # user["role"] comes from the database via the verified token. Nothing from the request body is used.
        result = pipeline.answer(user["role"], question, db.recent_questions(user["id"]))
    except KnowledgeBaseMissing:
        raise HTTPException(503, "The handbook knowledge base has not been built yet. Please contact the administrator.")
    except llm.LLMNotConfigured:
        raise HTTPException(503, "The AI assistant is not configured yet (missing LLM API key). Please contact the administrator.")
    except llm.LLMUnavailable as e:
        log.warning("LLM unavailable: %s", e)
        raise HTTPException(503, "The AI service is busy or temporarily unavailable. Please try again in a minute.")
    db.add_message(user["id"], "user", question)
    db.add_message(user["id"], "assistant", result["answer"], result["sources"], result["found"])
    return result


# Two role-locked endpoints. A student token is rejected by the faculty route (403) and vice versa.
@app.post("/api/student/chat")
def student_chat(body: ChatIn, user=Depends(security.require_role("student"))):
    return _chat(user, body)


@app.post("/api/faculty/chat")
def faculty_chat(body: ChatIn, user=Depends(security.require_role("faculty"))):
    return _chat(user, body)


@app.get("/api/history")
def history(user=Depends(security.get_current_user)):
    return {"messages": db.get_history(user["id"])}


@app.delete("/api/history")
def clear(user=Depends(security.get_current_user)):
    db.clear_history(user["id"])
    return {"ok": True}


@app.get("/api/health")
def health():
    info = {}
    for role in HANDBOOKS:
        try:
            kb = get_kb(role)
            info[role] = {"chunks": len(kb.chunks), "retrieval": kb.mode}
        except Exception:
            info[role] = {"chunks": 0, "retrieval": "missing"}
    return {
        "status": "ok",
        "llm_configured": bool(settings.llm_api_key),
        "knowledge_bases": info,
        "signup": {"student": bool(settings.student_signup_code), "faculty": bool(settings.faculty_signup_code)},
    }
