"""SQLite persistence layer using asyncio thread executor."""
import asyncio
import json
import logging
import sqlite3
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

_DB_PATH = settings.sqlite_path

CREATE_TABLES_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    email       TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role        TEXT DEFAULT 'user',
    daily_quota INTEGER DEFAULT 5,
    reports_today INTEGER DEFAULT 0,
    quota_reset_date TEXT DEFAULT '',
    is_active   INTEGER DEFAULT 1,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    user_id     TEXT,
    topic       TEXT NOT NULL,
    status      TEXT DEFAULT 'pending',
    report      TEXT DEFAULT '',
    bibliography TEXT DEFAULT '[]',
    all_sources TEXT DEFAULT '{}',
    word_count  INTEGER DEFAULT 0,
    sources_count INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL,
    completed_at TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS user_documents (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    filename        TEXT NOT NULL,
    content_type    TEXT DEFAULT 'text/plain',
    text_content    TEXT DEFAULT '',
    chroma_collection TEXT DEFAULT '',
    file_size       INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL
);
"""


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


async def init_db() -> None:
    """Create tables on startup."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _init_sync)
    logger.info(f"[DB] SQLite initialised at {Path(_DB_PATH).absolute()}")


def _init_sync() -> None:
    conn = _get_conn()
    conn.executescript(CREATE_TABLES_SQL)
    conn.commit()
    conn.close()


async def _run(fn, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(fn, *args))


# ─── User CRUD ───────────────────────────────────────────────────────────────

def _create_user_sync(id_, email, password_hash, role, created_at):
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, role, daily_quota, created_at) VALUES (?,?,?,?,?,?)",
            (id_, email, password_hash, role, settings.default_daily_quota, created_at),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


async def create_user(id_: str, email: str, password_hash: str, role: str, created_at: str) -> bool:
    return await _run(_create_user_sync, id_, email, password_hash, role, created_at)


def _get_user_by_email_sync(email: str):
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


async def get_user_by_email(email: str):
    return await _run(_get_user_by_email_sync, email)


def _get_user_by_id_sync(user_id: str):
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


async def get_user_by_id(user_id: str):
    return await _run(_get_user_by_id_sync, user_id)


def _check_and_increment_quota_sync(user_id: str, today: str) -> bool:
    """Return True if quota allows, and increment counter."""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT daily_quota, reports_today, quota_reset_date FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return False
        quota, today_count, reset_date = row
        if reset_date != today:
            conn.execute("UPDATE users SET reports_today=0, quota_reset_date=? WHERE id=?", (today, user_id))
            today_count = 0
        if today_count >= quota:
            conn.commit()
            return False
        conn.execute("UPDATE users SET reports_today=reports_today+1 WHERE id=?", (user_id,))
        conn.commit()
        return True
    finally:
        conn.close()


async def check_and_increment_quota(user_id: str, today: str) -> bool:
    return await _run(_check_and_increment_quota_sync, user_id, today)


# ─── Session CRUD ─────────────────────────────────────────────────────────────

def _upsert_session_sync(id_, user_id, topic, status, report, bibliography, all_sources, word_count, sources_count, created_at, completed_at):
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO sessions
               (id, user_id, topic, status, report, bibliography, all_sources,
                word_count, sources_count, created_at, completed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (id_, user_id, topic, status, report,
             json.dumps(bibliography, ensure_ascii=False),
             json.dumps(all_sources, ensure_ascii=False, default=str),
             word_count, sources_count, created_at, completed_at),
        )
        conn.commit()
    finally:
        conn.close()


async def upsert_session(id_: str, user_id: str | None, topic: str, status: str,
                          report: str = "", bibliography=None, all_sources=None,
                          word_count: int = 0, sources_count: int = 0,
                          created_at: str = "", completed_at: str = "") -> None:
    await _run(_upsert_session_sync, id_, user_id, topic, status, report,
               bibliography or [], all_sources or {}, word_count, sources_count,
               created_at, completed_at)


def _get_session_sync(session_id: str):
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["bibliography"] = json.loads(d["bibliography"] or "[]")
        d["all_sources"] = json.loads(d["all_sources"] or "{}")
        return d
    finally:
        conn.close()


async def get_session(session_id: str):
    return await _run(_get_session_sync, session_id)


def _list_sessions_sync(user_id, limit, offset):
    conn = _get_conn()
    try:
        if user_id:
            rows = conn.execute(
                "SELECT id, user_id, topic, status, word_count, sources_count, created_at, completed_at FROM sessions WHERE user_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, user_id, topic, status, word_count, sources_count, created_at, completed_at FROM sessions ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


async def list_sessions(user_id: str | None = None, limit: int = 20, offset: int = 0):
    return await _run(_list_sessions_sync, user_id, limit, offset)


# ─── Document CRUD ───────────────────────────────────────────────────────────

def _create_document_sync(id_, user_id, filename, content_type, text_content, chroma_collection, file_size, created_at):
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO user_documents (id, user_id, filename, content_type, text_content, chroma_collection, file_size, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (id_, user_id, filename, content_type, text_content, chroma_collection, file_size, created_at),
        )
        conn.commit()
    finally:
        conn.close()


async def create_document(id_: str, user_id: str, filename: str, content_type: str,
                           text_content: str, chroma_collection: str,
                           file_size: int, created_at: str) -> None:
    await _run(_create_document_sync, id_, user_id, filename, content_type,
               text_content, chroma_collection, file_size, created_at)


def _list_documents_sync(user_id: str):
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, user_id, filename, content_type, chroma_collection, file_size, created_at FROM user_documents WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


async def list_documents(user_id: str):
    return await _run(_list_documents_sync, user_id)


def _delete_document_sync(doc_id: str, user_id: str):
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM user_documents WHERE id=? AND user_id=?", (doc_id, user_id))
        conn.commit()
    finally:
        conn.close()


async def delete_document(doc_id: str, user_id: str) -> None:
    await _run(_delete_document_sync, doc_id, user_id)
