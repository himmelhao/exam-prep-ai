"""SQLite storage: creates the tables and has small helper functions to read/write them.
Everything lives in one file, data.db, next to this script."""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    name TEXT NOT NULL,
    description TEXT,
    goals TEXT              -- JSON list of learning goals
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id),
    type TEXT NOT NULL,         -- 'mcq' or 'short'
    difficulty TEXT NOT NULL,   -- 'easy', 'medium', 'hard'
    question TEXT NOT NULL,
    options_json TEXT,          -- JSON list for mcq, NULL for short answer
    answer TEXT NOT NULL,
    explanation TEXT,
    source_quote TEXT
);
-- The tables below are used from Phase 2 onward; created now so the schema is complete.
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL REFERENCES questions(id),
    user_answer TEXT,
    score INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS mastery (
    topic_id INTEGER PRIMARY KEY REFERENCES topics(id),
    score REAL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reviews (
    question_id INTEGER PRIMARY KEY REFERENCES questions(id),
    next_review_date TEXT,
    interval_days INTEGER
);
"""


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us use row["name"] instead of row[1]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)


# ---------- documents ----------

def find_document_by_text(text: str):
    """Return an existing document with exactly this text, or None (used for caching)."""
    with connect() as conn:
        return conn.execute("SELECT * FROM documents WHERE text = ?", (text,)).fetchone()


def add_document(title: str, text: str) -> int:
    with connect() as conn:
        cur = conn.execute("INSERT INTO documents (title, text) VALUES (?, ?)", (title, text))
        return cur.lastrowid


def get_document(document_id: int):
    with connect() as conn:
        return conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()


# ---------- topics ----------

def add_topic(document_id: int, name: str, description: str, goals: list) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO topics (document_id, name, description, goals) VALUES (?, ?, ?, ?)",
            (document_id, name, description, json.dumps(goals, ensure_ascii=False)),
        )
        return cur.lastrowid


def delete_topics(document_id: int):
    """Remove a document's topics and their questions (used to clean up a failed run)."""
    with connect() as conn:
        conn.execute(
            "DELETE FROM questions WHERE topic_id IN (SELECT id FROM topics WHERE document_id = ?)",
            (document_id,),
        )
        conn.execute("DELETE FROM topics WHERE document_id = ?", (document_id,))


def get_topics(document_id: int):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM topics WHERE document_id = ? ORDER BY id", (document_id,)
        ).fetchall()


# ---------- questions ----------

def add_question(topic_id: int, q: dict) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO questions
               (topic_id, type, difficulty, question, options_json, answer, explanation, source_quote)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                topic_id,
                q["type"],
                q["difficulty"],
                q["question"],
                json.dumps(q["options"], ensure_ascii=False) if q.get("options") else None,
                q["answer"],
                q.get("explanation", ""),
                q.get("source_quote", ""),
            ),
        )
        return cur.lastrowid


def get_questions(topic_id: int):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM questions WHERE topic_id = ? ORDER BY id", (topic_id,)
        ).fetchall()


# ---------- added in Phase 2 ----------

def list_documents():
    with connect() as conn:
        return conn.execute(
            "SELECT id, title, created_at FROM documents ORDER BY id DESC"
        ).fetchall()


def get_question(question_id: int):
    """One question plus its topic name (handy for showing results)."""
    with connect() as conn:
        return conn.execute(
            """SELECT q.*, t.name AS topic_name FROM questions q
               JOIN topics t ON t.id = q.topic_id WHERE q.id = ?""",
            (question_id,),
        ).fetchone()


def add_attempt(question_id: int, user_answer: str, score: int) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO attempts (question_id, user_answer, score) VALUES (?, ?, ?)",
            (question_id, user_answer, score),
        )
        return cur.lastrowid
