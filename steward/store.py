"""Document store with SQLite (local/dev) and Firestore (production) backends.

Records are stored as JSON documents keyed by (collection, id) with org_id
pulled out for indexing. At small-organization scale the remaining filtering is
cheap in Python, which keeps the two backends behaviourally identical instead of
splitting query logic across dialects.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from typing import Any, Iterable

from .config import settings
from .models import Base

ISO_HINTS = (
    "created_at",
    "scheduled_at",
    "due_date",
    "paid_at",
    "enrolled_at",
)


def _revive(doc: dict[str, Any]) -> dict[str, Any]:
    """Turn stored ISO strings back into datetimes for the known date fields."""
    for key in ISO_HINTS:
        value = doc.get(key)
        if isinstance(value, str):
            try:
                doc[key] = datetime.fromisoformat(value)
            except ValueError:
                pass
    return doc


class Store:
    def put(self, collection: str, record: Base | dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def query(self, collection: str, org_id: str | None = None, **equals: Any) -> list[dict]:
        raise NotImplementedError

    def _match(self, docs: Iterable[dict], equals: dict[str, Any]) -> list[dict]:
        out = []
        for doc in docs:
            if all(doc.get(field) == value for field, value in equals.items()):
                out.append(_revive(doc))
        return out


class SqliteStore(Store):
    def __init__(self, path: str) -> None:
        self.path = path
        self._local = threading.local()
        self._init_schema()

    @property
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS docs (
                collection TEXT NOT NULL,
                id         TEXT NOT NULL,
                org_id     TEXT,
                data       TEXT NOT NULL,
                PRIMARY KEY (collection, id)
            );
            CREATE INDEX IF NOT EXISTS idx_docs_org ON docs (collection, org_id);
            """
        )
        self._conn.commit()

    def put(self, collection: str, record: Base | dict[str, Any]) -> dict[str, Any]:
        doc = record.to_dict() if isinstance(record, Base) else dict(record)
        self._conn.execute(
            "INSERT OR REPLACE INTO docs (collection, id, org_id, data) VALUES (?,?,?,?)",
            (collection, doc["id"], doc.get("org_id"), json.dumps(doc, default=str)),
        )
        self._conn.commit()
        return _revive(doc)

    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT data FROM docs WHERE collection=? AND id=?", (collection, doc_id)
        ).fetchone()
        return _revive(json.loads(row["data"])) if row else None

    def query(self, collection: str, org_id: str | None = None, **equals: Any) -> list[dict]:
        if org_id:
            rows = self._conn.execute(
                "SELECT data FROM docs WHERE collection=? AND org_id=?", (collection, org_id)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT data FROM docs WHERE collection=?", (collection,)
            ).fetchall()
        return self._match((json.loads(r["data"]) for r in rows), equals)


class FirestoreStore(Store):
    """Firestore backend - the Google Cloud data product behind the deployment."""

    def __init__(self, project: str) -> None:
        from google.cloud import firestore  # imported lazily so local dev needs no creds

        self.db = firestore.Client(project=project)

    def put(self, collection: str, record: Base | dict[str, Any]) -> dict[str, Any]:
        doc = record.to_dict() if isinstance(record, Base) else dict(record)
        payload = json.loads(json.dumps(doc, default=str))
        self.db.collection(collection).document(doc["id"]).set(payload)
        return _revive(doc)

    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        snap = self.db.collection(collection).document(doc_id).get()
        return _revive(snap.to_dict()) if snap.exists else None

    def query(self, collection: str, org_id: str | None = None, **equals: Any) -> list[dict]:
        ref = self.db.collection(collection)
        if org_id:
            ref = ref.where("org_id", "==", org_id)
        return self._match((snap.to_dict() for snap in ref.stream()), equals)


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        if settings.use_firestore and settings.gcp_project:
            _store = FirestoreStore(settings.gcp_project)
        else:
            _store = SqliteStore(settings.sqlite_path)
    return _store


def reset_store() -> None:
    """Test hook."""
    global _store
    _store = None
