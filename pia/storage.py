"""SQLite history of assessments."""

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from .analysis import Assessment

SCHEMA = """
CREATE TABLE IF NOT EXISTS assessments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dependency  TEXT NOT NULL,
    version     TEXT NOT NULL,
    score       REAL NOT NULL,
    grade       TEXT NOT NULL,
    policy_url  TEXT NOT NULL,
    provider    TEXT NOT NULL,
    model       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    report_json TEXT NOT NULL
)
"""


def db_path() -> Path:
    return Path(os.environ.get("PIA_DB") or Path.home() / ".pia" / "assessments.db").expanduser()


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(SCHEMA)
    return conn


def save(a: Assessment) -> int:
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO assessments (dependency, version, score, grade, policy_url, provider, model,"
            " created_at, report_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (a.dependency, a.version, a.score, a.grade, a.policy_url, a.provider, a.model,
             a.created_at, json.dumps(a.to_dict())),
        )
        return cur.lastrowid


def history(limit: int = 50) -> list[tuple]:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT id, dependency, version, score, grade, provider, model, created_at"
            " FROM assessments ORDER BY id DESC LIMIT ?", (limit,),
        ).fetchall()


def load(assessment_id: int) -> Assessment | None:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT report_json FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
    return Assessment.from_dict(json.loads(row[0])) if row else None
