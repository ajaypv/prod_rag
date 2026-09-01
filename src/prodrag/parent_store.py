from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from prodrag.domain import ParentSection


@dataclass(frozen=True, slots=True)
class StoredParent:
    """One durable parent section fetched after a child wins retrieval."""

    tenant_id: str
    document_id: str
    parent_id: str
    checksum: str
    heading: str
    text: str
    section_order: int
    product: str | None
    version: str | None
    part: int = 1
    part_count: int = 1
    previous_parent_id: str | None = None
    next_parent_id: str | None = None


class ParentStore(Protocol):
    def upsert_revision(
        self,
        sections: Sequence[ParentSection],
        *,
        tenant_id: str,
        document_id: str,
        checksum: str,
        product: str | None,
        version: str | None,
    ) -> None: ...

    def prune_revision(
        self,
        checksum: str,
        *,
        tenant_id: str,
        document_id: str,
    ) -> None: ...

    def get_parent(
        self, *, tenant_id: str, document_id: str, parent_id: str
    ) -> StoredParent | None: ...

    def delete_document(self, document_id: str, *, tenant_id: str) -> None: ...

    def ping(self) -> bool: ...


class ParentNotFoundError(LookupError):
    pass


class SQLiteParentStore:
    """Persistent local parent store shared by the API and ingestion worker.

    Each operation opens a short-lived SQLite connection. WAL mode permits the API to
    read parent sections while the worker writes another document revision.
    """

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS parent_sections (
                    tenant_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    parent_id TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    heading TEXT NOT NULL,
                    parent_text TEXT NOT NULL,
                    section_order INTEGER NOT NULL,
                    part INTEGER NOT NULL DEFAULT 1,
                    part_count INTEGER NOT NULL DEFAULT 1,
                    previous_parent_id TEXT,
                    next_parent_id TEXT,
                    product TEXT,
                    version TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, document_id, parent_id)
                )
                """
            )
            existing_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(parent_sections)")
            }
            migrations = {
                "part": "ALTER TABLE parent_sections ADD COLUMN part INTEGER NOT NULL DEFAULT 1",
                "part_count": (
                    "ALTER TABLE parent_sections ADD COLUMN part_count INTEGER NOT NULL DEFAULT 1"
                ),
                "previous_parent_id": (
                    "ALTER TABLE parent_sections ADD COLUMN previous_parent_id TEXT"
                ),
                "next_parent_id": "ALTER TABLE parent_sections ADD COLUMN next_parent_id TEXT",
            }
            for column, statement in migrations.items():
                if column not in existing_columns:
                    connection.execute(statement)
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_parent_document_revision
                ON parent_sections (tenant_id, document_id, checksum)
                """
            )

    def upsert_revision(
        self,
        sections: Sequence[ParentSection],
        *,
        tenant_id: str,
        document_id: str,
        checksum: str,
        product: str | None,
        version: str | None,
    ) -> None:
        if not sections:
            raise ValueError("Refusing to store a revision with zero parent sections")
        updated_at = datetime.now(UTC).isoformat()
        rows = [
            (
                tenant_id,
                document_id,
                section.section_id,
                checksum,
                section.heading,
                section.text,
                section.order,
                section.part,
                section.part_count,
                section.previous_parent_id,
                section.next_parent_id,
                product,
                version,
                updated_at,
            )
            for section in sections
        ]
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO parent_sections (
                    tenant_id, document_id, parent_id, checksum, heading,
                    parent_text, section_order, part, part_count,
                    previous_parent_id, next_parent_id, product, version, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, document_id, parent_id) DO UPDATE SET
                    checksum = excluded.checksum,
                    heading = excluded.heading,
                    parent_text = excluded.parent_text,
                    section_order = excluded.section_order,
                    part = excluded.part,
                    part_count = excluded.part_count,
                    previous_parent_id = excluded.previous_parent_id,
                    next_parent_id = excluded.next_parent_id,
                    product = excluded.product,
                    version = excluded.version,
                    updated_at = excluded.updated_at
                """,
                rows,
            )

    def prune_revision(
        self,
        checksum: str,
        *,
        tenant_id: str,
        document_id: str,
    ) -> None:
        if not checksum:
            raise ValueError("Refusing to prune without a current revision checksum")
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM parent_sections
                WHERE tenant_id = ? AND document_id = ?
                  AND checksum != ?
                """,
                (tenant_id, document_id, checksum),
            )

    def get_parent(
        self, *, tenant_id: str, document_id: str, parent_id: str
    ) -> StoredParent | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT tenant_id, document_id, parent_id, checksum, heading,
                       parent_text, section_order, part, part_count,
                       previous_parent_id, next_parent_id, product, version
                FROM parent_sections
                WHERE tenant_id = ? AND document_id = ? AND parent_id = ?
                """,
                (tenant_id, document_id, parent_id),
            ).fetchone()
        if row is None:
            return None
        return StoredParent(
            tenant_id=row["tenant_id"],
            document_id=row["document_id"],
            parent_id=row["parent_id"],
            checksum=row["checksum"],
            heading=row["heading"],
            text=row["parent_text"],
            section_order=row["section_order"],
            product=row["product"],
            version=row["version"],
            part=row["part"],
            part_count=row["part_count"],
            previous_parent_id=row["previous_parent_id"],
            next_parent_id=row["next_parent_id"],
        )

    def delete_document(self, document_id: str, *, tenant_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM parent_sections WHERE tenant_id = ? AND document_id = ?",
                (tenant_id, document_id),
            )

    def ping(self) -> bool:
        with self._connect() as connection:
            connection.execute("SELECT 1").fetchone()
        return True
