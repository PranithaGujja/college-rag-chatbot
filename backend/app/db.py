"""SQLite storage: users, per-user chat history, revoked tokens. (Ephemeral on Render's free tier.)"""
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student','faculty')),
    password_hash TEXT NOT NULL,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    pw_version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sender TEXT NOT NULL CHECK (sender IN ('user','assistant')),
    content TEXT NOT NULL,
    sources TEXT,
    found INTEGER,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, id);
CREATE TABLE IF NOT EXISTS revoked_tokens (jti TEXT PRIMARY KEY, exp REAL NOT NULL);
"""


def connect():
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with closing(connect()) as c:
        c.executescript(SCHEMA)
        # upgrade databases created by older versions
        cols = {r["name"] for r in c.execute("PRAGMA table_info(users)")}
        if "must_change_password" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")
        if "pw_version" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN pw_version INTEGER NOT NULL DEFAULT 0")
        c.execute("DELETE FROM revoked_tokens WHERE exp < ?", (time.time(),))
        c.commit()


def get_user_by_username(username: str):
    with closing(connect()) as c:
        return c.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def get_user_by_id(uid: int):
    with closing(connect()) as c:
        return c.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()


def create_user(username: str, name: str, role: str, password_hash: str, must_change: bool = False):
    """Insert a NEW user. Raises sqlite3.IntegrityError if the ID already exists."""
    with closing(connect()) as c:
        cur = c.execute(
            "INSERT INTO users (username, name, role, password_hash, must_change_password) VALUES (?,?,?,?,?)",
            (username, name, role, password_hash, int(must_change)),
        )
        c.commit()
        return c.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()


def set_password(user_id: int, password_hash: str, must_change: bool = False):
    """Store a new password. Bumping pw_version signs the user out of every other session."""
    with closing(connect()) as c:
        c.execute(
            "UPDATE users SET password_hash = ?, must_change_password = ?, pw_version = pw_version + 1 WHERE id = ?",
            (password_hash, int(must_change), user_id),
        )
        c.commit()
        return c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def upsert_user(username: str, name: str, role: str, password_hash: str):
    with closing(connect()) as c:
        c.execute(
            """INSERT INTO users (username, name, role, password_hash) VALUES (?,?,?,?)
               ON CONFLICT(username) DO UPDATE SET name=excluded.name, role=excluded.role, password_hash=excluded.password_hash,
                 must_change_password=0, pw_version=pw_version+1""",
            (username, name, role, password_hash),
        )
        c.commit()


def revoke_token(jti: str, exp: float):
    with closing(connect()) as c:
        c.execute("INSERT OR IGNORE INTO revoked_tokens (jti, exp) VALUES (?,?)", (jti, exp))
        c.commit()


def is_revoked(jti: str) -> bool:
    with closing(connect()) as c:
        return c.execute("SELECT 1 FROM revoked_tokens WHERE jti = ?", (jti,)).fetchone() is not None


def add_message(user_id: int, sender: str, content: str, sources=None, found=None):
    with closing(connect()) as c:
        c.execute(
            "INSERT INTO messages (user_id, sender, content, sources, found, created_at) VALUES (?,?,?,?,?,?)",
            (user_id, sender, content, json.dumps(sources) if sources else None, None if found is None else int(found), time.time()),
        )
        c.commit()


def get_history(user_id: int, limit: int = 60):
    """Always filtered by user_id: one user can never read another user's history."""
    with closing(connect()) as c:
        rows = c.execute(
            "SELECT sender, content, sources, found, created_at FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [
        {"role": r["sender"], "content": r["content"], "sources": json.loads(r["sources"]) if r["sources"] else [],
         "found": None if r["found"] is None else bool(r["found"]), "created_at": r["created_at"]}
        for r in reversed(rows)
    ]


def recent_questions(user_id: int, n: int = 2):
    with closing(connect()) as c:
        rows = c.execute(
            "SELECT content FROM messages WHERE user_id = ? AND sender = 'user' ORDER BY id DESC LIMIT ?", (user_id, n)
        ).fetchall()
    return [r["content"] for r in reversed(rows)]


def clear_history(user_id: int):
    with closing(connect()) as c:
        c.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        c.commit()
