from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from config import EDITORIAL_DB_PATH


EDITORIAL_STORAGE_CHUNK_LINES = 200


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(EDITORIAL_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS editorial_documents (
            editorial_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            line_count INTEGER NOT NULL,
            character_count INTEGER NOT NULL,
            content_hash TEXT NOT NULL,
            PRIMARY KEY (editorial_id, version)
        );

        CREATE TABLE IF NOT EXISTS editorial_document_chunks (
            editorial_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            line_start INTEGER NOT NULL,
            line_end INTEGER NOT NULL,
            content TEXT NOT NULL,
            PRIMARY KEY (editorial_id, version, chunk_index),
            FOREIGN KEY (editorial_id, version)
                REFERENCES editorial_documents (editorial_id, version)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS editorial_patch_decisions (
            editorial_id TEXT NOT NULL,
            cycle INTEGER NOT NULL,
            patch_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (editorial_id, cycle, patch_id)
        );
        """
    )
    return connection


def _chunk_text(text: str) -> list[tuple[int, int, str]]:
    lines = text.splitlines(keepends=True)
    if not lines:
        return [(1, 1, text)]
    return [
        (line_start, min(line_start + EDITORIAL_STORAGE_CHUNK_LINES - 1, len(lines)), "".join(lines[line_start - 1:line_start + EDITORIAL_STORAGE_CHUNK_LINES - 1]))
        for line_start in range(1, len(lines) + 1, EDITORIAL_STORAGE_CHUNK_LINES)
    ]


def store_editorial_document(*, editorial_id: str, version: int, text: str) -> dict[str, object]:
    chunks = _chunk_text(text)
    manifest = {
        "storage": "sqlite",
        "version": version,
        "chunk_count": len(chunks),
        "line_count": len(text.splitlines()) or 1,
        "character_count": len(text),
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    created_at = datetime.now(timezone.utc).isoformat()
    connection = _connection()
    try:
        with connection:
            connection.execute(
                "DELETE FROM editorial_documents WHERE editorial_id = ? AND version = ?",
                (editorial_id, version),
            )
            connection.execute(
                """
                INSERT INTO editorial_documents (
                    editorial_id, version, created_at, line_count, character_count, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    editorial_id,
                    version,
                    created_at,
                    manifest["line_count"],
                    manifest["character_count"],
                    manifest["content_hash"],
                ),
            )
            connection.executemany(
                """
                INSERT INTO editorial_document_chunks (
                    editorial_id, version, chunk_index, line_start, line_end, content
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (editorial_id, version, chunk_index, line_start, line_end, content)
                    for chunk_index, (line_start, line_end, content) in enumerate(chunks)
                ],
            )
    finally:
        connection.close()
    return manifest


def assemble_editorial_document(*, editorial_id: str, version: int | None = None) -> str | None:
    connection = _connection()
    try:
        target_version = version
        if target_version is None:
            row = connection.execute(
                "SELECT MAX(version) AS version FROM editorial_documents WHERE editorial_id = ?",
                (editorial_id,),
            ).fetchone()
            target_version = row["version"] if row else None
        if target_version is None:
            return None
        chunks = connection.execute(
            """
            SELECT content FROM editorial_document_chunks
            WHERE editorial_id = ? AND version = ?
            ORDER BY chunk_index
            """,
            (editorial_id, target_version),
        ).fetchall()
    finally:
        connection.close()
    return "".join(str(chunk["content"]) for chunk in chunks) if chunks else None


def store_patch_decisions(
    *,
    editorial_id: str,
    cycle: int,
    accepted: list[dict[str, object]],
    rejected: list[dict[str, object]],
) -> None:
    created_at = datetime.now(timezone.utc).isoformat()
    rows = [
        (editorial_id, cycle, str(patch["id"]), "accepted", json.dumps(patch, ensure_ascii=False), created_at)
        for patch in accepted
    ] + [
        (editorial_id, cycle, str(patch["id"]), "rejected", json.dumps(patch, ensure_ascii=False), created_at)
        for patch in rejected
    ]
    connection = _connection()
    try:
        with connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO editorial_patch_decisions (
                    editorial_id, cycle, patch_id, decision, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
    finally:
        connection.close()