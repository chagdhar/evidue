"""Separate database/session for operator-assisted real-customer pilots."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.upload import models as _pilot_models  # noqa: F401  (register metadata)

ROOT = Path(__file__).parents[3]
PILOT_DB_PATH = Path(os.getenv("EVIDUE_PILOT_DB_PATH", str(ROOT / "data" / "evidue-pilot.db")))
PILOT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

pilot_engine = create_engine(f"sqlite:///{PILOT_DB_PATH}", future=True)
PilotSessionLocal = sessionmaker(pilot_engine, expire_on_commit=False)


def initialize_pilot_database() -> None:
    Base.metadata.create_all(pilot_engine)
