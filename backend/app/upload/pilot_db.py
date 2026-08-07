"""Workspace-isolated database/session management for real customer data."""

from __future__ import annotations

import os
from pathlib import Path
import re
from threading import Lock
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.upload import models as _pilot_models  # noqa: F401  (register metadata)
from app.upload.auth import current_workspace_id

ROOT = Path(__file__).parents[3]
PILOT_DB_PATH = Path(os.getenv("EVIDUE_PILOT_DB_PATH", str(ROOT / "data" / "evidue-pilot.db")))
PILOT_DB_DIR = Path(os.getenv("EVIDUE_PILOT_DB_DIR", str(PILOT_DB_PATH.parent / "workspaces")))
PILOT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
PILOT_DB_DIR.mkdir(parents=True, exist_ok=True)
_SAFE_WORKSPACE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")

_engines: dict[str, Engine] = {}
_factories: dict[str, sessionmaker] = {}
_initialized: set[str] = set()
_lock = Lock()


def _workspace_path(workspace_id: str) -> Path:
    if workspace_id == "default":
        return PILOT_DB_PATH
    if not _SAFE_WORKSPACE.fullmatch(workspace_id):
        raise RuntimeError("Unsafe workspace identifier")
    return PILOT_DB_DIR / f"{workspace_id}.db"


def _engine_for(workspace_id: str) -> Engine:
    with _lock:
        engine = _engines.get(workspace_id)
        if engine is None:
            path = _workspace_path(workspace_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            engine = create_engine(f"sqlite:///{path}", future=True)
            _engines[workspace_id] = engine
            _factories[workspace_id] = sessionmaker(engine, expire_on_commit=False)
        return engine


def _ensure_column(engine: Engine, table: str, column: str, ddl: str) -> None:
    inspector = inspect(engine)
    existing = (
        {item["name"] for item in inspector.get_columns(table)}
        if inspector.has_table(table)
        else set()
    )
    if column in existing:
        return
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def initialize_workspace_database(workspace_id: str) -> None:
    if workspace_id in _initialized:
        return
    engine = _engine_for(workspace_id)
    Base.metadata.create_all(engine)
    # create_all does not alter pre-existing SQLite tables. Keep additive local
    # migrations explicit so an existing pilot database upgrades in place.
    _ensure_column(engine, "pilot_uploads", "coverage_complete", "BOOLEAN DEFAULT 0")
    _ensure_column(engine, "pilot_contracts", "agreement_bundle_id", "VARCHAR")
    _ensure_column(engine, "pilot_reconciliation_runs", "air_version_id", "VARCHAR")
    _ensure_column(engine, "pilot_reconciliation_runs", "verification_plan_id", "VARCHAR")
    _ensure_column(engine, "pilot_air_versions", "assurance_json", "JSON")
    _ensure_column(engine, "pilot_facts", "predicate_id", "VARCHAR")
    _ensure_column(engine, "pilot_facts", "model_name", "VARCHAR")
    _ensure_column(engine, "pilot_facts", "prompt_version", "VARCHAR")
    _ensure_column(engine, "pilot_facts", "confidence", "FLOAT")
    _ensure_column(engine, "pilot_facts", "explanation", "VARCHAR")
    _ensure_column(engine, "pilot_facts", "reviewed_truth", "VARCHAR")
    _ensure_column(engine, "pilot_facts", "review_rationale", "VARCHAR")
    _ensure_column(engine, "pilot_facts", "reviewed_by", "VARCHAR")
    _ensure_column(engine, "pilot_facts", "reviewed_at", "DATETIME")
    _initialized.add(workspace_id)


def initialize_pilot_database() -> None:
    initialize_workspace_database("default")


class _WorkspaceSessionFactory:
    """Drop-in sessionmaker facade that follows the request workspace context."""

    def _factory(self) -> sessionmaker:
        workspace_id = current_workspace_id()
        initialize_workspace_database(workspace_id)
        return _factories[workspace_id]

    def __call__(self, *args: Any, **kwargs: Any):
        return self._factory()(*args, **kwargs)

    def begin(self):
        return self._factory().begin()


PilotSessionLocal = _WorkspaceSessionFactory()
